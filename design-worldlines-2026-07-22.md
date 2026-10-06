# Worldlines: tracking the full lifecycle of files that become objects

Design proposal, 2026-07-22. Prompted by Jeremy's question: blob storage assumes a static file with one sha256, but every file is the end state of a trajectory of edits, and the trajectory is where the information lives. How a document was written is arguably more informative than what it says, and the current model integrates all of it out. Status: proposal for discussion. Nothing here has been inserted into the database.

## 1. The diagnosis, stated in the project's own language

The current blob store treats a file as an object with no morphisms except identity. That is the precise sense in which something is missing, and it is anti-Yoneda: the lemma says an object is known by its maps, and a version of a document has maps (edits, to its successors and from its predecessors) that carry exactly the information Jeremy wants: tempo, revision style, what got cut, when, by whom. Storing only the endpoint keeps the objects and throws away the hom-sets. In physics terms: we store boundary conditions and integrate out the path, and then wonder why we cannot recover the action.

The fix is not a new storage engine. It is to notice that the database already solved this exact problem once, for people, and to apply the same move to documents.

## 2. What a .doc actually is, and what the industry's fossil record teaches

Jeremy asked what underlies .doc and whether it generalizes. The answer is a short archaeology, and every layer teaches the same lesson.

**Legacy .doc** is an OLE2 Compound File: a miniature FAT filesystem inside a single file, with streams and sector allocation tables. Text lives in a piece table: the document is a sequence of pointers into fragments. And here is the remarkable part: under "Fast Save" (the default through Word 2000), an edit did not rewrite the file; it appended new pieces and updated the table. A fast-saved .doc literally contained its own edit trajectory, including text the author believed deleted. This is the closest any mainstream format ever came to what Jeremy is proposing, and Microsoft killed it, for two reasons worth remembering: it leaked (deleted text and prior authors were recoverable by adversaries, which caused real scandals), and it was fragile (one corrupt piece chain lost the document). The trajectory existed but was unintentional, untimestamped, unattributed, and trapped in a word-processor-specific encoding.

**.docx** is the opposite reaction: an OPC zip of XML parts, pure snapshot, history amputated. Tracked changes (`w:ins`/`w:del` with author and timestamp) are the vestigial trajectory, present only when the author opts in and flattened forever on accept.

**Google Docs** answers the format question by refusing it: there is no file. A doc is a server-side operation log (insert, delete, format, each with author, timestamp, and revision number, composed by operational transformation), and the "document" you see is a fold over that log. Export to .docx is a render. Roll-back-the-clock works because the log is the document. This is the model Jeremy keeps coming back to, and its storage layer is exactly right. Its merge layer is exactly what `divergence-is-data-v1` already rejected: OT forces convergence at write time and discards the disagreement. The 2026-07-16 session separated those two properties. Take the log, refuse the forced merge. Everett, not Copenhagen.

**Overleaf**, painfully relevant: it keeps a full per-edit history server-side and exposes a git bridge per project. Jeremy's manuscripts, the highest-value trajectories he owns, are being written inside a system that records them at fine grain, and the Dropbox sync he uses flattens that history into snapshot files on every sync. The most useful writing-process data in his life is being actively integrated out by his own plumbing, today. Recovering it is an ingest problem, not a research problem.

The generalization, then, is not a file format. Every vendor that ever solved this built the same thing (an initial state plus timed, attributed deltas) and then hid it, leaked it, or amputated it. The universal format is event sourcing over content-addressed states. We already have the table for it.

## 3. The proposal: a document is a person

The substrate principle: persons are never stored; they are connected components of `same` witnesses over observed addresses. Apply it verbatim:

**Documents are never stored. A version is a content-addressed blob (existing `blob()` machinery, unchanged). A lineage witness is an `r` row asserting that one version revises another. The document is the connected component.**

Concretely, and with zero new tables:

- A version enters exactly as blobs enter today: `blob(hash, meta)`, id minted by `uuid_from_sha256`, so two machines that capture the same version agree on its identity without coordination.
- Lineage is a witness: `r(o1=child_ref, o2=parent_ref, d={type:'revises', source:..., method:...}, c, t)`. Multiple parents on one child is a merge. Multiple children on one parent is a fork. The structure is a DAG by construction, which `divergence-is-data-v1` requires; a chain is merely the sole-author special case.
- The document is `component()` over active `revises` witnesses, exactly as a person is `component()` over `same` witnesses. Its current state is the set of DAG tips. Its birth is the earliest version *in the corpus*, which per `window-censoring-v1` is a claim about the corpus and never about the world: we usually meet a document mid-life (an emailed v3), and discovering an earlier ancestor later must merge components without re-keying anything, which is precisely what component identity gives us and what a root-keyed document id would break.
- A wrong lineage edge (two files that look related but are genuinely independent) is retracted by an outcome row. Standard machinery, nothing new.

This answers "how do we give these objects the respect they deserve": the same respect persons get. Not an entity with attributes, but a cloud of evidence with computed structure.

### Refinements to Jeremy's chain-of-diffs scheme

The instinct is right and is a Merkle DAG; three refinements make it the git construction rather than a reinvention with known defects:

1. **Parent hash only, not all previous hashes.** A version that commits to its parent's hash transitively commits to the entire history by induction. Carrying every ancestor hash in every link is O(n²) and adds nothing: this is exactly why a git commit stores one tree hash and its parent hashes, and nothing else, and yet the tip hash seals all of history.
2. **Snapshots are the truth; diffs are derived.** Jeremy's "keep the integral so you don't have to recompute it" is the right allocation, inverted from how delta systems usually do it. Store the full state at every version (the integral); treat the diff as computed structure, like `coauthor`: derivable from any two versions on demand, cacheable, never load-bearing. The deep reason is canonicality: a snapshot's hash is algorithm-free, but a diff depends on the diff algorithm (Myers vs patience vs xdelta produce different bytes for the same edit), so diff-primary storage breaks the "identical bytes mint identical ids on machines that never communicated" property the merge story rests on. It is also why git conceptually stores full snapshots per commit and relegates deltas to packfile compression, an implementation detail below the object model. Copy that layering: object model is snapshots plus DAG; the blob store may delta-compress underneath, invisibly.
3. **The trajectory lives beside the file, not inside it.** Rewriting the artifact to carry its own history changes its hash, fights every producing application, and is the .doc fast-save mistake: history embedded in the artifact leaks with the artifact and corrupts with it. The file stays exactly what Word or the AFM wrote; the worldline is the CDB's knowledge *about* it. When a self-contained shippable trajectory is genuinely wanted, that is an export (all version blobs plus a lineage manifest, morally a git bundle), not the storage-native form.

## 4. The granularity ladder, and where trajectories actually come from

Storage is the easy half. The binding constraint is capture: you cannot store a trajectory you never observed, and per `source-as-instrument-v1` every capture channel is an instrument with its own sampling rate and censoring window. Four levels, degrading gracefully:

- **Level 0, existence:** `seen-at` observations. Already implemented. A path over time is already a crude worldline hint.
- **Level 1, lineage:** version A revises version B, at time t, probably by author x. Universal: needs no format knowledge, works for .tex, .tdms, .docx, AFM images alike. This is the proposal's core and is cheap.
- **Level 2, delta:** what changed. Derived for free from any two text snapshots; captured natively where a source provides ops.
- **Level 3, process:** keystrokes, pauses, cursor motion, the order in which sentences were born. Only exists where the editor cooperates. This is where "writing style" in the strong sense lives.

The instruments already available, with their windows:

- **Dropbox version history.** Dropbox is already snapshotting most of Jeremy's files on every save and retains revisions for months. An ingester walking `/list_revisions` per path recovers dense recent trajectories for the entire workspace retroactively. (Caveat: Dropbox's `content_hash` is their own block-wise construction, not plain sha256; ingest must re-hash downloaded bytes.)
- **Overleaf.** The git bridge gives commit-grain history per project; the internal history API is finer. This single source covers the manuscripts.
- **The email archive.** 592k messages are a twenty-year fossil record of document trajectories: every attachment is a dated, sender-attributed version observation. Lineage edges between attachment versions are inferable (name similarity, content overlap, temporal order) with honest confidence values. The old universe already contains the deep past of Jeremy's documents; no time machine needed.
- **Git repos** embed losslessly: a commit graph is already this design.
- **Filesystem watchers** (pixelfold-watch.py is the local precedent; NTFS USN journal is the OS-native one): hash-on-change gives level 1 at save granularity for any folder we care to watch. Note that a change event with no captured bytes is still a witness ("something happened at t") and belongs in the record.
- **Editors, opportunistically:** vim's persistent undofile is literally a branching op-log with timestamps; VS Code local history similar; the Claude archive records exact before/after of every file I have ever edited for Jeremy, timestamped. All level 2 to 3.
- **Instrument files:** TDMS is natively append-only segments, so version n is a byte-prefix of version n+1 and chunk-level dedup stores the whole trajectory for the cost of the final file plus epsilon. AFM images are typically born complete: a worldline of length 1, which the model handles by degenerating exactly to today's `blob()`. Nothing is lost for write-once files; nothing changes for them at all.

Different instruments sample the same worldline at different rates and over different windows (email: sparse, decades; Dropbox: dense, months; instrumented editor: continuous, from installation onward). All enter as witnesses with source and confidence; the reconstructed trajectory is a consensus over them, computed, never materialized. We never have the path, only measurements of it. Do not fake continuity between samples.

### Confidence on lineage edges is measurable, not decreed

A `revises` witness from a watcher that saw the save happen carries c near 1. An inferred edge between two email attachments can take c from content overlap: the fraction of shared chunks between the two versions is a number in [0,1] that already behaves like a likelihood, is trivial to compute in a chunked store, and can later be calibrated against ground truth (pairs where a watcher or git also recorded the edge). This gives the consensus-law fit a second corpus, and it means document boundary questions (is this a revision or a new document that plagiarized an old one?) become threshold questions on component confidence, exactly like person-merge questions. Same machinery, same open empirical law.

## 5. Cost, honestly

- **Storage.** With content-defined chunking plus compression in the blob store, a version costs roughly its changed bytes plus a constant. A 300 KB .tex saved 500 times: single-digit MB, not 150 MB. TDMS trajectories: final size plus epsilon. Write-once files: zero extra, by degeneracy. The pathological case is compressed containers (.docx is a zip: one character rewrites the stream and defeats chunk dedup), where each version costs a full copy; even the pathology is only, say, 2 MB x 100 saves = 200 MB per heavily-edited docx, which at current disk prices is noise. Jeremy's instinct that "you could efficiently store the full temporal trajectory" is simply correct, and the known mitigation for containers (chunk the decompressed parts for formats we understand) is an optimization, not a prerequisite.
- **Compute.** sha256 and chunking both run at GB/s. Negligible against instrument data rates and absurdly negligible against typing.
- **The real cost is capture infrastructure:** one watcher per machine, one ingester per source (Dropbox revisions, Overleaf, attachment sweep), each an instrument to be stood up and calibrated. This is honest work but it is plumbing, and it can be built incrementally; every source added back-fills independently because versions mint machine-independent ids.
- **The other real cost is ethical, and deserves its own rule before the group instances get this.** Level 3 capture is surveillance of the writing process. For Jeremy capturing Jeremy, that is a diary. For a lab instance capturing students' drafting, it is a chilling effect and arguably an IRB question. Proposal: process-grain capture is opt-in per author per source, the consent is itself a row, and absence of consent censors capture at level 1 (lineage), which is no more than Dropbox already records about everyone.

## 6. Where the fine grain goes: the existing fork already decides it

`oplog-vs-blob-v1` classifies by concurrency, and it classifies the new material correctly without amendment. A keystroke stream from one author's editor session is a sole-author append-only stream: a blob, entering as a content-addressed file attached to the lineage edge it explains (`d.ops_sha`), keeping `r` skinny. A genuinely multi-author live document is the op-log-in-`r` case the rule already reserved, branched by `r.b`, compacted to hashed snapshots that are exactly the version objects of section 3. The two regimes meet at the snapshot: versions are the compactions, worldline edges connect them, op blobs annotate the edges where we have them. Nothing in the 2026-07-16 rules needs revision; this proposal is their closure under "and files, too."

## 7. Files as tiny universes, taken seriously

Jeremy's framing holds up under the substrate's own cosmology, with one correction. A document has a big bang (its first version) but, unlike a database instance, its identity cannot be its birth event, because instances declare their birth and documents have theirs discovered, usually late and sometimes never: window censoring again. Component identity absorbs this. And files do not die; we stop sampling them. "Static" is a property of the observation channel, not of the file: last-seen is corpus-censored, dormancy is `staleness-decay-v1` applied to a worldline, and a photograph is not a corpse but a universe born complete, a worldline of length 1. The degenerate case is not a failure mode. Most of the universe's files are such universes, which is exactly why the trajectory of the ones that are not is so informative.

## 8. Proposed rule rows (drafts, for discussion; not inserted)

```
{"type":"rule","level":2,"name":"worldline-v1","date":"2026-07-22",
 "under":"oplog-vs-blob-v1",
 "definition":"Documents are never stored: they are connected components of
 revises-witnesses over content-addressed version blobs, exactly as persons are
 components of same-witnesses over addresses. Snapshots are primary and diffs
 are derived structure, computed never materialized, because a snapshot hash is
 algorithm-free and a diff is not. Lineage is a DAG per divergence-is-data-v1.
 A version commits to its parents' hashes only; ancestry follows by induction.
 The trajectory lives beside the artifact, never inside it. Confidence on
 inferred lineage edges is measured (chunk overlap), not decreed, and is
 calibration material for the consensus law. Trajectory granularity is
 source-censored per window-censoring-v1: first-version and last-touched are
 corpus claims, never world claims."}

{"type":"rule","level":2,"name":"process-capture-consent-v1","date":"2026-07-22",
 "status":"proposed",
 "definition":"Capture of the writing process (keystroke or op grain, level 3)
 is opt-in per author per source; the consent is itself a row and is
 retractable by outcome. Absent consent, capture is censored at lineage grain
 (level 1: dated version snapshots), which records no more than commodity file
 sync already records. A lab instance holding students' worldlines holds them
 under this rule."}
```

## 9. Open questions

1. **Chunking in the blob store.** The store is currently whole-file. Content-defined chunking (FastCDC-style) is what makes dense text trajectories nearly free and makes chunk-overlap confidence cheap. It is also a real piece of engineering (a manifest layer: file hash to chunk hashes). Worth it, but sequence it after the first ingester proves the model.
2. **First ingester.** Candidates, in order of value density: Overleaf git bridges (manuscripts, fine grain, small volume), Dropbox revisions (everything, save grain, retroactive months), email attachment sweep (decades, sparse, big). My vote: Overleaf first, because it rescues the data currently being destroyed by the sync flattening, and it is small enough to prove the schema in a day.
3. **The `revises` vs `derives` distinction.** A figure exported from a .tdms, a PDF compiled from a .tex: same lineage machinery, different edge type (`derives`, cross-format), and it unifies provenance ("which sweep is behind this figure in the paper") with revision history. Probably v1 should include both edge types from the start since the mechanism is identical.
4. **Where trajectory blobs physically live** inherits the open question from the 2026-07-16 session (Y: per-PC, never NAS) unchanged.
