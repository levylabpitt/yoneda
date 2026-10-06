# Genesis: bringing a yoneda to life on an instrument PC

These are the bring-up instructions for a PC that controls one or more laboratory instruments. Follow them top to bottom; every step is ordinary command-line work and the whole thing takes about ten minutes plus however long the backlog takes to hash. If the machine happens to have an AI coding assistant, you can hand it this file and let it do the mechanical parts; either way the steps are the same.

One yoneda per PC: the PC owns the instance, and each instrument on it enters as an ordinary device object inside it. The instance will be born empty, and that is correct: an instance is given an origin, never a history, and every machine configures itself from scratch.

Ground rules, which outrank everything below: every step runs at user level, so a UAC prompt means something has gone wrong; the watcher and the database only ever READ the instrument's files, and you should keep it that way; and if an assistant is doing the work, it must gather the steps that need a human (normally just the GitHub sign-in in section 2) and hand them over in one batch.

## 1. Preflight

The Notebook is standard-library-only Python: the list below is everything the machine needs. Check each one, and install what is missing at user level:

- `python --version` is 3.10 or newer. If missing: `winget install --scope user Python.Python.3.12`, or the python.org installer run with `InstallAllUsers=0 /passive`.
- `git --version` works. If missing: `winget install --scope user Git.Git`, or the portable MinGit zip if winget insists on elevating.
- A `sqlite3.exe` (3.42+) for the watcher. Download the sqlite-tools zip from sqlite.org and place `sqlite3.exe` at `C:\yoneda\bin\sqlite3.exe`.
- Internet reach to yoneda.app (you are reading this file, so yes) and to github.com.

## 2. Fetch the Notebook (the one sign-in)

The Notebook lives in the **private** repo `levylabpitt/yoneda-notebook`; cloning it needs a GitHub account that is in the levylabpitt org. A browser sign-in window will appear once, then never again on this machine:

```
git clone -b instrument https://github.com/levylabpitt/yoneda-notebook.git C:\yoneda\app
```

Git Credential Manager opens the browser; sign in with the org account; the credential is stored. Updating the Notebook later is `git pull` in `C:\yoneda\app`.

The machine root is `C:\yoneda\`, so it is the same yoneda whoever signs in:

```
C:\yoneda\app\        the Notebook checkout (branch: instrument)
C:\yoneda\yoneda.db   the instance (created at the big bang below)
C:\yoneda\blobs\      the content-addressed store; create it empty now
C:\yoneda\bin\        sqlite3.exe
```

Also fetch `yoneda-watch.ps1` from the same site root you fetched this file from, into `C:\yoneda\`.

## 3. The big bang

```
python C:\yoneda\app\app.py --db C:\yoneda\yoneda.db --no-browser
```

The first launch creates the database and boots the genome: that is the birth. Verify, with the app still running:

- `http://127.0.0.1:8787/api/state` answers.
- `C:\yoneda\bin\sqlite3.exe C:\yoneda\yoneda.db "SELECT * FROM instance;"` returns one row.
- `... "SELECT j->>'name' FROM o WHERE j->>'type'='rule';"` lists the genome rules.

The `instance_id` is this instance's identity forever; there is no id in any config file, because the birth event's own row id is who this instance is. Record it; it goes in the final checklist.

About API keys: the Notebook has optional AI features, and Jeremy or the yoneda team installs the key for those when they set the machine up. Leave that to them. Everything in this file (hashing, provenance, worldlines, the watcher) runs on its own.

## 4. Give each instrument a body

Every instrument on this PC enters the database as an ordinary object. For each one, record its model and serial (the serial is usually on the controller's back panel; approximate is fine, it can be witnessed better later):

```
C:\yoneda\bin\sqlite3.exe C:\yoneda\yoneda.db "INSERT INTO o (j) VALUES ('{\"kind\":\"device\",\"class\":\"<what kind of instrument, in your own words>\",\"model\":\"<model>\",\"serial\":\"<serial>\",\"label\":\"<short name>\"}') RETURNING i;"
```

Keep each returned uuid: they go in the watcher config.

## 5. Find the data streams

Find where each instrument saves its data, and confirm it against real evidence: search the likeliest roots for the most recently modified files of whatever type that instrument writes (the acquisition software's save dialog usually shows the base path). Check each folder before wiring it in. Multiple save locations per instrument are fine; the watcher takes a list.

## 6. Configure and start the watcher

Write `C:\yoneda\yoneda-watch.json`:

```json
{
  "db": "C:\\yoneda\\yoneda.db",
  "sqlite3": "C:\\yoneda\\bin\\sqlite3.exe",
  "blobRoot": "C:\\yoneda\\blobs",
  "hostLabel": "<short machine name>",
  "instruments": [
    { "id": "<uuid from step 4>", "name": "<short name>",
      "watch": ["<save folder>", "<another save folder if any>"] }
  ],
  "pollSeconds": 30,
  "quiesceSeconds": 15
}
```

Run one sweep in the foreground to ingest the backlog of existing files:

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\yoneda\yoneda-watch.ps1 -Once
```

A folder of past data may take a while to hash on the first pass; that is the corpus arriving. Per window-censoring-v1, the timestamps of this backlog are observation times, not acquisition times: the corpus begins today even though the files are older. Their internal timelines can be derived later from the bytes, which is why the bytes are kept.

Then make both the Notebook and the watcher permanent without elevation. Instrument PCs normally auto-logon to one operator account; put two one-line `.cmd` launchers in that account's Startup folder (`shell:startup`):

```
start "yoneda-notebook" pythonw C:\yoneda\app\app.py --db C:\yoneda\yoneda.db --no-browser
```

```
start "yoneda-watch" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\yoneda\yoneda-watch.ps1
```

Start both now as well, so they are running before you finish. True at-boot start, before any logon, needs an admin-created scheduled task: put it on the homework list rather than elevating for it now.

## 7. Prove it with a live measurement

This is the acceptance test and it is not optional. Take a real scan, or save any measurement, the way it is normally done on this instrument. Within about a minute of the file quiescing, it must appear:

```
C:\yoneda\bin\sqlite3.exe C:\yoneda\yoneda.db "SELECT sha256, bytes, last_seen_path, last_seen_at FROM blobs ORDER BY last_seen_at DESC LIMIT 5;"
C:\yoneda\bin\sqlite3.exe C:\yoneda\yoneda.db "SELECT count(*) FROM r_active WHERE d->>'type'='produced-by';"
```

The first query's top row should be the scan you just took, by hash. If the instrument streams to a growing file (TDMS-style), let it grow through two poll cycles and check the `revises` edge with `method=append`: that edge's `t` is the measured arrival time of the appended segment, the beginning of this instrument's worldline data.

## 8. Mirror to the lab's cloud storage

Data belongs in cloud storage, synced from a local replica, never parked on one machine's disk. If the lab's Nextcloud client is on this PC, sync `C:\yoneda\` (the db and the blobs) into the lab's `yoneda` folder, and **exclude `*.db-wal` and `*.db-shm` from sync**: the main `.db` alone is always a valid database, only possibly stale, and syncing the sidecar files is what corrupts. If the client is not installed, put it on the homework list and continue; it is a mirror, not a dependency.

**Backups are a different thing and go somewhere else.** The mirror above keeps the data where the lab can reach it; it does not protect you from the database itself going wrong, because a mistake is mirrored as faithfully as anything else. The Notebook takes its own consistent snapshots while it runs, and those go to **Google Drive**, which is the lab's backup target for everyone because it has been the more stable of the two. Nextcloud is for data. Keeping the copies that rescue you separate from the store they would rescue is the whole point.

Answer it in the Notebook, not on a command line: **right-click the tray icon by the clock, open Backups, and pick the folder.** The menu lists the cloud folders this machine actually has, ticks the one in use, and says so when the location was picked automatically rather than chosen by a person. The same question sits in the backup panel in the Notebook's own header. The answer is remembered per notebook, so this is asked once.

Until someone answers, snapshots still happen, into the best folder found. The operator who never gets around to it is exactly the one who must not end up with no backups.

## 9. Leave a note for whoever comes next

Write `C:\yoneda\README.md` recording: what this PC is, each instrument on it (class, model, serial, its device uuid), the `instance_id`, the db path and the Notebook checkout, the watched folders, where the watcher lives and how both processes start, and a pointer to https://yoneda.app and to the rules inside the database itself (`SELECT j FROM o WHERE j->>'type'='rule'`). State plainly: nothing is ever deleted; a bad run is retracted (kept as calibration data), never removed, from the Notebook UI or via the client library's `retract`; new lessons become rule rows, and get reported to Jeremy.

## 10. Done when

All of these are true, and anything that is not goes on a homework list with a name next to it:

- The instance id is recorded in `C:\yoneda\README.md`.
- The backlog is ingested and the count of files is known.
- The live-measurement file from step 7 appeared by hash within a minute.
- The Notebook and the watcher are running now and restart on logon.
- The Nextcloud mirror is syncing (or is explicitly on the homework list), with `*.db-wal` and `*.db-shm` excluded.
- The backup destination was **chosen**, not guessed: the tray's Backups menu shows a tick beside a folder a person picked.
