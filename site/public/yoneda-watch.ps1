# ============================================================================
# yoneda-watch.ps1: the capture instrument. PC tier, SQLite backend.
# ============================================================================
# Watches the folders where this PC's instruments save data. Every time a file
# appears or changes, its bytes are hashed, copied into the content-addressed
# blob store, and registered in the ONE yoneda database on this machine
# (one-instance-per-pc-v1: the PC owns the instance; each instrument is a
# device object inside it):
#
#   blob ref                    idempotent; same bytes, same id, on every machine
#   seen-at                     a dated observation of WHERE the bytes were
#   produced-by                 provenance edge to the owning instrument's object
#   revises                     lineage edge from the previous state of the
#                               same path, when there was one
#
# The watcher is deliberately FORMAT-BLIND. Capture now, interpret later: the
# bytes are immutable evidence, and any internal timeline can be derived from
# the stored blobs at any point in the future. The one structural thing it
# notices is APPEND GROWTH: if the previous state of a path is a byte-prefix
# of the new state (TDMS streaming does this), the lineage edge is recorded as
# method=append with c=1, and the edge's own timestamp t is the observed
# arrival time of that segment, censored by the poll interval per
# window-censoring-v1.
#
# Requirements: Windows PowerShell 5.1+ and a sqlite3.exe (>= 3.42). Nothing
# else. No Docker, no Postgres, no Python, no admin rights, no network.
#
# Run:      powershell -ExecutionPolicy Bypass -File yoneda-watch.ps1
# Config:   yoneda-watch.json next to this script (written at genesis).
# State:    yoneda-watch.state.json next to this script (safe to delete; the
#           database is idempotent, you only lose revises-continuity across
#           the gap).
# ============================================================================

param(
  [string]$ConfigPath = (Join-Path $PSScriptRoot 'yoneda-watch.json'),
  [switch]$Once   # single sweep then exit (used by genesis for verification)
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
if (-not (Test-Path $ConfigPath)) {
  Write-Host "No config at $ConfigPath. Genesis writes it; see yoneda.app/genesis.md" -ForegroundColor Red
  exit 1
}
$cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
# Expected fields:
#   db               path to the PC's yoneda database, e.g. "C:\yoneda\yoneda.db"
#   sqlite3          path to sqlite3.exe, e.g. "C:\yoneda\bin\sqlite3.exe"
#   blobRoot         the content-addressed store, e.g. "C:\yoneda\blobs"
#   hostLabel        short name for this machine, e.g. "cypher-pc"
#   instruments      array of { "id": <o.i of the device object>,
#                               "name": <label for logs>,
#                               "watch": [folders this instrument saves into] }
#   pollSeconds      how often to sweep (default 30)
#   quiesceSeconds   file must be untouched this long before hashing (default 15)
#   ignore           array of wildcard patterns to skip

$pollSeconds    = if ($cfg.pollSeconds)    { [int]$cfg.pollSeconds }    else { 30 }
$quiesceSeconds = if ($cfg.quiesceSeconds) { [int]$cfg.quiesceSeconds } else { 15 }
# Sync-client droppings are ignored by default: the Nextcloud journal lives
# inside the sync folder and changes on every sync, so watching it would churn
# out an endless revises chain of a file that is pure plumbing.
$ignore         = @('*.tmp','~$*','*.partial','Thumbs.db','desktop.ini',
                    '._sync_*.db','.sync_*.db','*.db-wal','*.db-shm',
                    '.owncloudsync.log','*.~cloudf') + @($cfg.ignore)

$statePath = Join-Path $PSScriptRoot 'yoneda-watch.state.json'
$state = @{}      # path (lowercased) -> { hash, bytes, mtime }
$byFileId = @{}   # nextcloud fileid  -> { hash, bytes, mtime }  (rename survival)
if (Test-Path $statePath) {
  $loaded = Get-Content $statePath -Raw | ConvertFrom-Json
  # Current shape is { files: {...}, fileids: {...} }; the original flat shape
  # (paths at top level) is still read so an existing state file keeps working.
  $filesNode = if ($loaded.PSObject.Properties['files']) { $loaded.files } else { $loaded }
  if ($filesNode) {
    $filesNode.PSObject.Properties | ForEach-Object { $state[$_.Name] = $_.Value }
  }
  if ($loaded.PSObject.Properties['fileids'] -and $loaded.fileids) {
    $loaded.fileids.PSObject.Properties | ForEach-Object { $byFileId[$_.Name] = $_.Value }
  }
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Invoke-Ydb([string]$Sql) {
  # Pipe SQL into sqlite3 in batch mode. -bail stops on first error.
  $out = ("PRAGMA busy_timeout = 5000;`n" + $Sql) | & $cfg.sqlite3 -batch -bail $cfg.db
  if ($LASTEXITCODE -ne 0) { throw "sqlite3 failed: $out" }
  return $out
}

function Sql-Quote([string]$s) { "'" + ($s -replace "'", "''") + "'" }

function UuidFromSha256([string]$Hash) {
  # String-level port of the Postgres uuid_from_sha256(): UUID v8 carrying the
  # leading 122 bits of the digest. MUST stay bit-identical to the SQL
  # expression in the genome (cell.sql) and to the Postgres function, so the
  # same bytes mint the same o.i on every machine and every tier.
  $h = $Hash.ToLower()
  $v = [Convert]::ToInt32($h.Substring(16, 1), 16)
  $variant = '89ab'[$v -band 3]
  return $h.Substring(0,8) + '-' + $h.Substring(8,4) + '-8' + $h.Substring(13,3) +
         '-' + $variant + $h.Substring(17,3) + '-' + $h.Substring(20,12)
}

# ---------------------------------------------------------------------------
# Cloud sync awareness (Nextcloud is the lab's data lake; OneDrive for personal
# machines). Two concerns, per the notebook-v2 decisions of 2026-07-26:
#
#  * PLACEHOLDERS. A virtual-files mirror shows every remote file as a local
#    path, but the bytes may be cloud-only. Hashing such a file forces a full
#    download (a "hydrate"), which for a folder of AFM scans is gigabytes the
#    operator never asked to pull. Placeholders are skipped and counted unless
#    the config sets "hydratePlaceholders": true.
#
#  * FILEID. Nextcloud gives each file a numeric id that survives renames and
#    moves within one Nextcloud instance. It is a HINT, not an identity (sha256
#    is the identity; identical bytes on two Nextcloud instances carry
#    different fileids), so it enters the database only as part of the dated
#    seen-at observation. Its practical value here is rename survival: a moved
#    file keeps its fileid, so if size and mtime also match, the sighting is
#    recorded WITHOUT re-hashing gigabytes. The id is read from the Nextcloud
#    desktop client's own sync journal (._sync_*.db at the sync-folder root, a
#    SQLite file), read-only; no server call, no credentials.
# ---------------------------------------------------------------------------
$PLACEHOLDER_MASK = 0x441000  # OFFLINE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS

function Test-Placeholder($file) {
  if ($cfg.hydratePlaceholders) { return $false }
  return (([int]$file.Attributes) -band $PLACEHOLDER_MASK) -ne 0
}

$script:syncRootCache = @{}   # directory -> @{ root; journal } or $false

function Find-SyncJournal([string]$Dir) {
  # Walk up from $Dir looking for a Nextcloud sync journal. Cached per directory.
  if ($script:syncRootCache.ContainsKey($Dir)) { return $script:syncRootCache[$Dir] }
  $probe = $Dir
  $found = $false
  while ($probe -and (Test-Path $probe)) {
    $j = Get-ChildItem -Path $probe -Filter '*_sync_*.db' -File -Force -ErrorAction SilentlyContinue |
         Where-Object { $_.Name -match '^\.?_?sync_[0-9a-f]+\.db$' } | Select-Object -First 1
    if ($j) { $found = @{ root = $probe; journal = $j.FullName }; break }
    $parent = Split-Path $probe -Parent
    if ($parent -eq $probe) { break }
    $probe = $parent
  }
  $script:syncRootCache[$Dir] = $found
  return $found
}

function Get-NextcloudFileId([string]$Path) {
  $sync = Find-SyncJournal (Split-Path $Path -Parent)
  if (-not $sync) { return $null }
  $rel = $Path.Substring($sync.root.Length).TrimStart('\','/') -replace '\\','/'
  try {
    # -readonly: never write the client's journal; busy is fine, the id is a
    # hint and a miss only costs one re-hash.
    $out = & $cfg.sqlite3 -readonly -batch $sync.journal `
           "SELECT fileid FROM metadata WHERE path = $(Sql-Quote $rel) LIMIT 1;" 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { return [string]($out | Select-Object -First 1) }
  } catch {}
  return $null
}

$mediaTypes = @{
  '.ibw'='application/x-igor-binary-wave'; '.pxp'='application/x-igor-packed-experiment'
  '.tdms'='application/x-tdms'; '.tdms_index'='application/x-tdms-index'
  '.h5'='application/x-hdf5'; '.hdf5'='application/x-hdf5'
  '.csv'='text/csv'; '.txt'='text/plain'; '.png'='image/png'; '.tif'='image/tiff'
  '.tiff'='image/tiff'; '.jpg'='image/jpeg'; '.spm'='application/octet-stream'
}

function Hash-Prefix([string]$Path, [long]$Length) {
  # sha256 of the first $Length bytes: detects append-only growth.
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $fs = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
  try {
    $buf = New-Object byte[] 1048576
    $left = $Length
    while ($left -gt 0) {
      $n = $fs.Read($buf, 0, [Math]::Min($buf.Length, $left))
      if ($n -le 0) { break }
      $sha.TransformBlock($buf, 0, $n, $null, 0) | Out-Null
      $left -= $n
    }
    $sha.TransformFinalBlock($buf, 0, 0) | Out-Null
    return ([BitConverter]::ToString($sha.Hash) -replace '-','').ToLower()
  } finally { $fs.Dispose(); $sha.Dispose() }
}

function Ingest-File($file, [string]$InstrumentId) {
  $path = $file.FullName
  $key  = $path.ToLower()
  $prev = $state[$key]

  # Cheap skip: unchanged size and mtime since last sweep.
  if ($prev -and [long]$prev.bytes -eq $file.Length -and
      [string]$prev.mtime -eq $file.LastWriteTimeUtc.ToString('o')) { return }

  $mtime = $file.LastWriteTimeUtc.ToString('o')
  $fid = Get-NextcloudFileId $path

  # Rename survival: a fileid we have already hashed, appearing at a new path
  # with unchanged size and mtime, is the same bytes moved within the sync
  # folder. Record the sighting; do not re-hash gigabytes to learn nothing.
  if (-not $prev -and $fid -and $byFileId["$fid"]) {
    $known = $byFileId["$fid"]
    if ([long]$known.bytes -eq $file.Length -and [string]$known.mtime -eq $mtime) {
      $ident = UuidFromSha256 $known.hash
      Invoke-Ydb @"
INSERT INTO r (o1, d)
VALUES ($(Sql-Quote $ident),
        json_object('type','seen-at','path',$(Sql-Quote $path),
                    'host',$(Sql-Quote $cfg.hostLabel),
                    'nextcloud_fileid',$(Sql-Quote "$fid")));
"@ | Out-Null
      $state[$key] = @{ hash=$known.hash; bytes=$file.Length; mtime=$mtime; fileid="$fid" }
      Write-Host "$(Get-Date -Format 'HH:mm:ss')  moved  $($known.hash.Substring(0,12))  $path"
      return
    }
  }

  $hash = (Get-FileHash -Path $path -Algorithm SHA256).Hash.ToLower()
  if ($prev -and $prev.hash -eq $hash) {   # touched but identical
    $state[$key] = @{ hash=$hash; bytes=$file.Length; mtime=$mtime; fileid="$fid" }
    return
  }

  # Copy bytes into the content-addressed store (idempotent by construction).
  $dest = Join-Path (Join-Path $cfg.blobRoot $hash.Substring(0,2)) $hash
  if (-not (Test-Path $dest)) {
    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
    Copy-Item $path $dest
  }

  $ident = UuidFromSha256 $hash
  $ext   = $file.Extension.ToLower()
  $mt    = if ($mediaTypes.ContainsKey($ext)) { $mediaTypes[$ext] } else { 'application/octet-stream' }
  $meta  = (@{ bytes = $file.Length; media_type = $mt } | ConvertTo-Json -Compress)

  $sql = @()
  # blob ref: meta is the base and the computed identity fields are patched
  # OVER it (json_patch right operand wins), so meta can never overwrite the
  # identity. Mirrors the 2026-07-17 blob() fix in the Postgres lineage.
  # Plain INSERT, no UPSERT clause: o is a VIEW over the cell table and SQLite
  # forbids UPSERT syntax on views; the view's INSTEAD OF trigger is
  # INSERT OR IGNORE on i underneath, which is the same dedupe.
  $sql += @"
INSERT INTO o (i, j)
VALUES ($(Sql-Quote $ident),
        json_patch($(Sql-Quote $meta),
                   json_object('kind','ref','scheme','sha256','id',$(Sql-Quote $hash))));
"@
  $seenFields = "'type','seen-at','path',$(Sql-Quote $path),'host',$(Sql-Quote $cfg.hostLabel)"
  if ($fid) { $seenFields += ",'nextcloud_fileid',$(Sql-Quote "$fid")" }
  $sql += @"
INSERT INTO r (o1, d)
VALUES ($(Sql-Quote $ident), json_object($seenFields));
"@

  # Provenance: this instrument produced these bytes. Guarded against
  # re-insertion so a rebuilt state file does not spam duplicate witnesses.
  $sql += @"
INSERT INTO r (o1, o2, d)
SELECT $(Sql-Quote $ident), $(Sql-Quote $InstrumentId),
       '{"type":"produced-by","source":"yoneda-watch"}'
WHERE NOT EXISTS (SELECT 1 FROM r WHERE o1 = $(Sql-Quote $ident)
                  AND o2 = $(Sql-Quote $InstrumentId) AND d->>'type' = 'produced-by');
"@

  # Lineage: the previous state of this path, if any, is this state's parent.
  # Append growth (old bytes are a prefix of new bytes) is detected exactly,
  # and is what turns a streaming TDMS file into a timestamped worldline.
  if ($prev -and $prev.hash -ne $hash) {
    $prevIdent = UuidFromSha256 $prev.hash
    $method = 'same-path-succession'; $c = 0.8
    if ($file.Length -gt [long]$prev.bytes) {
      if ((Hash-Prefix $path ([long]$prev.bytes)) -eq $prev.hash) { $method = 'append'; $c = 1 }
    }
    $d = (@{ type='revises'; method=$method; path=$path; source='yoneda-watch' } | ConvertTo-Json -Compress)
    $sql += @"
INSERT INTO r (o1, o2, d, c)
SELECT $(Sql-Quote $ident), $(Sql-Quote $prevIdent), $(Sql-Quote $d), $c
WHERE NOT EXISTS (SELECT 1 FROM r WHERE o1 = $(Sql-Quote $ident)
                  AND o2 = $(Sql-Quote $prevIdent) AND d->>'type' = 'revises');
"@
  }

  Invoke-Ydb ($sql -join "`n") | Out-Null
  $state[$key] = @{ hash=$hash; bytes=$file.Length; mtime=$mtime; fileid="$fid" }
  if ($fid) { $byFileId["$fid"] = @{ hash=$hash; bytes=$file.Length; mtime=$mtime } }
  $what = if ($prev) { "revised ($($file.Length - [long]$prev.bytes) bytes delta)" } else { 'new' }
  Write-Host "$(Get-Date -Format 'HH:mm:ss')  $what  $($hash.Substring(0,12))  $path"
}

# ---------------------------------------------------------------------------
# Main loop. One database, many instruments: each instrument's watch folders
# are swept with its own device id on the produced-by edge.
# ---------------------------------------------------------------------------
Write-Host "yoneda-watch: db $($cfg.db) on $($cfg.hostLabel)"
foreach ($ins in $cfg.instruments) {
  Write-Host "  instrument $($ins.name) ($($ins.id)): $($ins.watch -join '; ')"
}

$placeholdersReported = 0
while ($true) {
  $cutoff = (Get-Date).AddSeconds(-$quiesceSeconds)
  $script:placeholdersSkipped = 0
  foreach ($ins in $cfg.instruments) {
    foreach ($dir in $ins.watch) {
      if (-not (Test-Path $dir)) { continue }
      Get-ChildItem -Path $dir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
          $f = $_
          if (Test-Placeholder $f) { $script:placeholdersSkipped++; return $false }
          $f.LastWriteTime -lt $cutoff -and
          $f.FullName -notlike (Join-Path $cfg.blobRoot '*') -and
          -not ($ignore | Where-Object { $f.Name -like $_ })
        } |
        ForEach-Object {
          try { Ingest-File $_ $ins.id }
          catch { Write-Host "ERROR $($_.Exception.Message)" -ForegroundColor Red }
        }
    }
  }
  if ($script:placeholdersSkipped -ne $placeholdersReported) {
    $msg = "{0}  {1} cloud-only placeholder(s) skipped, not hydrated (set hydratePlaceholders:true in the config to pull them)" -f `
      (Get-Date -Format 'HH:mm:ss'), $script:placeholdersSkipped
    Write-Host $msg
    $placeholdersReported = $script:placeholdersSkipped
  }
  @{ files = $state; fileids = $byFileId } | ConvertTo-Json -Depth 5 |
    Set-Content -Path $statePath -Encoding UTF8
  if ($Once) { break }
  Start-Sleep -Seconds $pollSeconds
}
