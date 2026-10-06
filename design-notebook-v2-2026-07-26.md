# The Notebook, second draft: an advisor instead of a compiler

Design discussion, 2026-07-26 (Jeremy and Claude). Supersedes the onboarding design
in `yoneda-notebook/ai.py`. Decisions here are Jeremy's and are settled unless
marked open; the candidate rule rows at the end are proposals, not yet written into
any database.

## What was actually wrong with v1

The first Notebook did not have a weak AI. It had an AI doing the wrong job. In
`ai.py`, Claude is a **one-shot form-schema compiler**: one API call, evidence in,
one JSON object out, no second turn. Its output is confined to five field types
(`text, date, select, ref, file`) inside a fixed forms-and-views shape, and the
prompt ends with "Return ONE JSON object, and nothing else, no prose." The entire
budget for talking to a human is `manual_intro`, two to four sentences.

So the ceiling was structural. That design cannot tell you your TDMS headers name
the sample, cannot suggest moving photos out of Google Photos, and cannot ask you a
question. It was never going to, no matter how good the model got.

**The change is the AI's role, and nearly everything else follows from it.** Claude
stops being a compiler in the data path and becomes a consultant on novelty.

## Use the database for the routine and Claude for the new

The rule Jeremy set: *only where there is something new.* Routine ingest is
relations, costs nothing, and involves no model at all. The database already knows
what it has seen, which extensions have probes, which directory shapes have
patterns, which instruments have been met. A cheap deterministic check answers "do I
have machinery for this?" and only a miss escalates.

**The part that makes this economical is the write-back.** Claude's answer is not a
response to a request, it is a durable extension of the deterministic layer: a new
probe, a new pattern, a new rule row. The same novelty is never paid for twice, and
the fraction of files needing a model asymptotes toward zero as the lab's actual
formats get covered. The AI's job is to grow the deterministic layer, not to sit
inside it.

This also inverts the usual worry about cost. A system that calls a model per file
gets more expensive as it succeeds. This one gets cheaper.

## Bring your own key

Rejected: a Cloudflare Worker holding Jeremy's key behind Cloudflare Access, with
the lab authenticating through levylab.org. Chosen: **each person supplies their own
API key, issued from the lab's Anthropic account.**

The hosted-proxy design exists to solve two problems, protect a shared key and
enforce budgets centrally, and the novelty rule dissolves both. Consultation is
sparse rather than conversational, so there is no runaway loop to cap; per-person
keys carry Anthropic's own limits, so the ceiling is enforced upstream for free; and
per-person keys are per-person line items, so spend tracking gets *easier* rather
than requiring a proxy to be instrumented for accounting it would otherwise not see.

Two further points in its favour. It is already built, since `ai.py`'s Mode A is
exactly this shape. And it generalizes outside the lab, which a levylab.org-gated
service cannot.

The awkwardness Jeremy objected to was never the key. It was offering two modes and
making the user choose. Collapse to one: paste the lab key. Mode B (copy a prompt
into any AI, paste JSON back) goes away once the lab account can issue a key to
anyone who needs one.

Housekeeping when this is implemented: the model is `claude-opus-5`, not the
`claude-opus-4-8` currently pinned in `ai.py`, and the call should stream, because a
dialogue that walks a file tree runs long.

**Reopened 2026-07-28.** Jeremy's objection: "I feel like we are in a transition
phase as though we had to register for every power outlet. One org account should be
enough. Place limits on AI spend but should not need to paste some damn token." He is
right about the destination, and the section above underrates the cost of issuance by
treating "the lab account can issue a key to anyone who needs one" as free. It is not
free; it is the registration. See *Four levels* below, which does not overturn this
decision so much as narrow what it has to decide.

**Settled the same day, and built.** One path, no fallbacks. Jeremy: "Without AI this
tool is useless, so there should not be a non-AI option. The paste-into-another-AI
loop is a poor approximation and not useful beyond initial base setup." The deciding
argument was not technical. Handing a group of four something half-working spends
credibility that does not come back: they learn to discount the next attempt, and
there are only so many next attempts. A tool that cannot reach an AI is not a degraded
notebook, it is a different and worse tool wearing the same name, so the honest
failure is to say the key is missing. Both offline onboarding paths and the
copy-paste mode are gone from `yoneda-notebook`, along with `/api/ai-prompt` and
`/api/ai-apply`. Cost is expected to fall, and the store lowers it further by making
one yoneda's format work answer the same question for everyone.

## Where data lives

**Nextcloud is the data lake.** This settles the long-open question of where blob
bytes physically live cross-machine, and it does so consistently with
`foundational-config`: a local replica that syncs, never a mounted network share.

- **Instrument yoneda** writes to a local directory that is mirrored to a `yoneda`
  folder on Nextcloud. Local for speed and for surviving a network outage at 2am;
  synced for backup and for the lab to see.
- **Personal yoneda** lives in the person's university OneDrive. Pitt's consent
  policy blocks Graph OAuth, but this does not matter, because OneDrive syncs a
  local replica and the watcher reads the folder. The API was never needed.

The general point, worth holding onto: **every cloud we care about has a local sync
client, so ingest never needs a cloud API.** APIs are only for what the replica
cannot tell you, such as server-side sharing state.

One gotcha that applies to all of them: sync clients use placeholders for
files not currently downloaded, and hashing a placeholder forces a hydrate. A
watcher that naively hashes an online-only account will try to pull the whole thing
down. The watcher needs a placeholder policy.

## Identity when the hash arrives late

Jeremy: use the Nextcloud fileID immediately, compute sha256 in the background with
no urgency. This is right, and it raises a question the design has to answer, since
`uuid_from_sha256()` mints `o.i` from content and the content is not yet known.

The answer is the one the system already gives everywhere else:

1. At first sight, mint the object with a `uuidv7` and record the fileID as a dated
   observation. The fileID is a hint, exactly as the 2026-07-25 rule says, but a
   better hint than a path because it survives renames and moves.
2. When the hash lands, mint the content-addressed id and write a `same` witness
   between it and the provisional object.

Never merge, always witness. **The late hash is not a compromise, it is the thesis
running on schedule:** save first, name by fingerprint, connect later. The
fingerprint arriving an hour later is just "later."

It also hands us the merge story. Two machines that see the same file mint different
provisional ids and converge on one content id the moment either finishes hashing.

## The SQLite file may sync. Three conditions.

An earlier draft of this advice said not to sync the database at all. That was too
strong, and Jeremy was right to push back: syncing *is* backing up, and adding a
separate dump pipeline buys little.

The real hazard is that a WAL-mode database is three files, not one.

- The main `.db` is **always a valid database**. Committed transactions may still be
  in the `-wal`, so a lone copy can be stale, but stale-and-valid is a fine backup.
- Syncing **all three** is what breaks. A sync client uploads each file when it
  happens to notice it changed, so it can pair a `.db` from one moment with a `-wal`
  from another. That mismatched pair is worse on restore than no `-wal` at all.
- `-shm` is shared memory and is meaningless off the machine.

So the rule is three lines, not a pipeline:

1. Exclude `*.db-wal` and `*.db-shm` from sync.
2. Checkpoint (`PRAGMA wal_checkpoint(TRUNCATE)`) on close or on a timer, so the
   synced `.db` is current rather than lagging.
3. One machine opens a given database at a time, which "one yoneda per PC" already
   guarantees. This is the condition that would actually hurt: two writers behind a
   sync client produce conflicted copies, and unlike a text file there is no merging
   your way out. We produced exactly that conflict on `NEEDS-JEREMY.md` on
   2026-07-26.

What makes this comfortable rather than fragile is that **Nextcloud keeps file
versions**, so even a torn upload mid-checkpoint is recoverable by rolling back.

## Probes and tools add zero tables

Two of the wanted features turn out to be the same shape as everything else.

A **format probe** takes bytes and returns properties that become relations. TDMS
carries a rich property set readable without loading the data arrays; Igor `.ibw`
notes carry the full scan parameter set for the MFP3D and Cypher; likewise HDF5 and
Nanonis `.sxm`. Each probe is itself a tool object, which is a pleasing recursion
rather than a special case.

A **tool** is an object, content-addressed as a boundary ref to a repo at a commit
sha, exactly like a blob. "Reads TDMS" is a relation. "Produced this figure from
that dataset" is a relation, and that is the worldline idea from
`design-worldlines-2026-07-22.md` arriving without new machinery. When the lab can
ask which analysis produced figure 3 and on which scan, that is not a feature that
was built; it is a query that became answerable.

Known cost: probes need third-party libraries (npTDMS, h5py), which breaks the
Notebook's zero-dependency PyInstaller property. Open: accept the dependencies, run
probes server-side, or ship them as optional plugins.

## The interview's output is rows, not config

What Claude learns about a person during onboarding ("works on STO membranes", "data
lands in Nextcloud/LevyLab/AFM") are claims about the world: revisable, retractable,
supersedable. They belong in `o`/`r` like everything else. A settings file would be
the single place in this system where we store a description instead of witnessing
one.

## The store: sharing learnings between yonedas

The novelty rule makes one instance cheaper as it succeeds. Sharing makes the cost
of teaching amortize across everyone who shares. Ten labs each teaching their yoneda
one format, pulling from a common peer, each pay a tenth of the total and all get
ten formats.

**There is nothing new to build for this, only the merge channel that was already
designed.** A probe is a tool, a tool is a content-addressed object, and
`uuid_from_sha256` is a function of the bytes. So if two labs independently learn
the same probe they do not mint matching ids, they mint **the same id**, verified in
2026-07-17 with two containers that never communicated. Sharing learnings is a union
of rows in which duplicates collapse by construction. There is no conflict
resolution to write.

### A peer, not a registry

The store is **an instance like any other**, with its own big bang, that happens to
be public and to hold mostly class-level rows. You pull from it as you would from a
colleague's yoneda. It is a peer that many people point at, which is a social fact
and not an architectural one.

Rejecting the central-registry version is not fastidiousness. A registry forces
convergence, which `divergence-is-data-v1` forbids, and the thing it would silently
overwrite is exactly the thing you want kept: two labs write different probes for
one format because their instrument variants differ, and the one that "loses" may be
the one correct for your rig. Keep both, let `consensus` weigh them.

Content addressing also removes the problem package registries exist to solve. There
is no namespace, so no ownership of the name `tdms`, no version conflict, no
squatting. Identity is intrinsic.

Rules travel the same way. A hard-won rule row like `window-censoring-v1` is exactly
what another lab should not have to rediscover, and it arrives as a claim at a
level, not as law.

### Format learnings travel, filesystem learnings do not

The line is sharper than "sensitive or not":

- *"TDMS property `wf_increment` gives the sample interval"* is about the **format**.
  Universal. Publishable.
- *"Files under `/LevyLab/AFM/<name>/` are that person's scans"* is about **this
  filesystem**. A real learning, worth keeping locally, and it must never leave. It
  also leaks a layout and a person.

Claude is in the loop at the moment a learning is created, so that is where the split
belongs: an escalation returns a universal part and a local part **separately**, and
only the universal part is marked publishable. Marking at write time rather than
deriving it later is the honest version, since the mark is a claim like everything
else, and the escalation path is the only writer that has to be taught.

### Where it lives

**yoneda.store**, its own host, served by the existing `yoneda-site` Worker via a
third route block. The Worker already spans two zones, so a third costs three lines
and no second deploy. `CANONICAL_REDIRECT` matches the hostname `yoneda.science`
exactly, so the store is not swallowed into the apex.

Its own host rather than `yoneda.app/store` because **the URL should express the
architecture**. A store is a peer; at a path it reads as a feature of the mothership,
at a host it reads as something you point at, and another lab running theirs is then
the same shape rather than a special case.

Prerequisite, checked 2026-07-26: yoneda.store is still on Porkbun nameservers while
the other two are on Cloudflare. Tracked in Asana "Needs."

Back half, when it exists: `/api/store/...` on the same Worker. Cloudflare **D1 is
SQLite**, so the genome runs there roughly as written rather than needing a second
port.

### First increment

The merge channels do not exist, and this depends on them. But the class-level subset
is **the easy case**: a union of rows whose ids already agree, append-only, with no
requirement to resolve disagreement. No conflict resolution, no deletion, no
ordering. That is the wedge. Build merge for the publishable subset, point it at one
public peer, and let the general case follow once it has run for a while.

### The first one is real: escaping Paperpile (2026-07-28)

Jeremy, having watched the notebook work out how to import his 7,100-record
library: "so this is a yoneda skill for people who want to escape Paperpile."

That is the first concrete thing the store has to carry, and it arrived from use
rather than from design, which is the right way round. It also fits
`learnings-are-shareable-v1` exactly: **an importer knows about a format, not
about a filesystem.** It knows what Paperpile means by `id_list` and
`attachments`; it knows nothing about `G:\My Drive`. That is precisely the split
the rule already draws, so the shareable unit needs no new category.

What makes the difference between a skill and a chore done twice is small and
mechanical: every path lives in a named settings block at the top of the script
and nowhere else. Hardcoding somebody's folders into the body is what stops the
thing travelling, and it is the only thing that does.

The notebook is now told this when it writes anything that writes. Approved
scripts are already recorded as objects with their source and purpose, so the
artifact exists; what is missing is only the channel that moves it.

**The skill includes getting the input, and that is the part nobody writes down.**
The first attempt built a whole plan on the `.bib`, which needed fuzzy
title/author/year matching and left 57 PDFs unmatched and 56 weakly matched. The
JSON export names the file against the record outright and carries identifiers
pre-normalised as `doi:10.1063/…` beside Paperpile's own content hash.

But the JSON **was not on disk**. Jeremy had to go and download it. So this is
not "read the folder and choose the better file" -- the notebook surveyed
everything present and could not have known a better export existed, because it
did not. Neither could I: I inspected the directory instead of asking the one
person who knew what the tool could produce.

Which means a format skill that begins at the file is already too late. The
useful unit starts a step earlier: *this tool can export JSON as well as BibTeX,
here is how to get it, and it is worth the extra minute because it removes the
guessing entirely.* Everything downstream is easy once that is known, and no
amount of cleverness downstream recovers it if it is not.

The behavioural rule that follows, and that cost a day to learn twice: when
something arrives from a tool that has other export formats, **ask before
optimising what happens to be lying there.**

### Emit, do not only ingest (2026-07-28)

Jeremy, on being asked whether he still needed the BibTeX export once he had the
JSON: "I want to generate .bib files on demand from yoneda, not be a slave to
paperpile."

That is the inversion that makes leaving real rather than nominal. A reference
manager keeps its hold not by storing things but by being the only thing that can
emit what your LaTeX needs. Import alone relocates the data and changes nothing;
**a skill for escaping a tool is only finished when it can produce that tool's
output**, at which point the original becomes one exporter among several and can
be dropped without ceremony.

For DOIs this is easy in a way it is not for most formats, because the identifier
is the work and everything else is an assertion about it: given a set of works,
BibTeX is a rendering, and any subset is a query. "What this paper cites",
"everything on KTaO3", "what the group read this year" all become the same
operation.

**The one thing that must survive the import is the citekey.** Paperpile's are in
the JSON, 7,100 of 7,100, unique but for four collisions -- `Qin2026-zo`,
`Dai2026-he`. Regenerating a bibliography with freshly minted keys silently
breaks every `\cite` in every existing `.tex`, which is the kind of damage
noticed months later by a coauthor. So citekeys are carried through as data, not
regenerated, and the collisions are recorded as the disagreement they are rather
than resolved by picking.

This also closes a loop with the Overleaf mirror: a generated `.bib` lands in
`docs/`, the hourly job carries it to GitHub, and Overleaf sees it like any other
source file. Nothing new is needed for that; it already runs.

### Open: what to call the unit

The place is the store, in the App Store sense of somewhere you *get* capabilities.
The unit needs a name.

Proposal: a **plasmid**. Transfer here is horizontal, not vertical. Instances descend
from a stem cell and each has its own big bang; a probe moving between unrelated
instances, conferring one capability in a small self-contained package the recipient
may keep or drop, is the bacterial case exactly. Multiple variants circulating at
once is `divergence-is-data` stated in biology, and it sits in the language this
project already speaks.

Plain alternative: the store carries **probes** (format readers) and **rules**
(learned rules). Legible, accurate, forgettable.

Undecided. Either way one line belongs on the page, because it is what people will
get wrong: *what circulates is what your yoneda learned about a format, never
anything about your files.*

## Four levels (notes, not rules)

Jeremy's framing, 2026-07-28, recorded because it explains why the credential
question keeps failing to settle: **there is not one audience, there are four, and
they want different mechanisms.** Him alone. The yoneda project members, a handful of
people, before group accounts exist. LevyLab, once they do. Then other groups
entirely.

The shape worth noticing is that **the outermost level collapses back to the
simplest.** Someone in another lab has no levylab.org identity and no access to any
service the lab runs, so for them the answer is a key in a file, which is the level-two
answer with the lab removed. Anything elaborate built for level three is something
level four has to route around. That argues against building level three early, not
against building it.

But the pasting is a real cost and the section above underrates it. Jeremy's analogy
is the right one: needing a personal credential for each service is like registering
for every power outlet, and it reads as transitional rather than permanent. At the org
level the socket should simply be live for anyone the org recognises, with spend
limits set centrally and no token in anyone's hands. That is what levylab.org already
does for mail, calendar, and drive, and it is the thing that already works.

**The decision does not have to be made, only left open.** Both answers are the same
call with two of its arguments filled differently: an endpoint and a credential. Today
the endpoint is `api.anthropic.com` and the credential is a pasted key. At the org
level the endpoint becomes a lab Worker holding the one org key, and the credential
becomes a Cloudflare Access session obtained by signing in with Google, which is a
sign-in people already perform daily and not a token anyone copies. Per-person spend
accounting lands at that Worker, where the Access identity and Anthropic's returned
token counts are both in hand. All of that infrastructure is already deployed and
already understood: Workers on `yoneda.app`, Access with Google as the provider on
`groove.yoneda.app`.

So the only thing that matters now is not foreclosing it. **Keep the endpoint and the
credential as configuration rather than assumptions baked through `ai.py`.** That
costs nothing today and is the difference between an afternoon and a rewrite when
person two arrives.

One correction to a rule proposed earlier the same day and immediately too broad. The
constraint is not that the notebook never requires network or login. It is that the
notebook must **record, hash, watch, and answer offline**, while AI consultation may
require both, since it inherently requires the network anyway. An instrument writing
files at two in the morning must not stop because a token expired. Nothing is lost by
gating the part that was already online.

## Paused: the org tier (2026-07-28)

Deliberately parked, not dropped. Jeremy: "We are in develop mode, not deploy mode.
Individual and PC level deploy is in reasonable shape. Any org level decision should
respect what we have done so far, so no harm no foul." Nothing built so far forecloses
it, which is what makes pausing cheap: the substrate is identical across tiers, and
`sync.py` already exists to push a local instance into a shared one.

He is patient zero from this date, running a personal notebook on DAVIS. Two questions
he expects his own use to answer, both recorded here so they are not re-derived:

1. **Is a references yoneda separate from a personal one?** The design's own answer is
   no: one graph, nothing merged, and a paper should be able to relate to the
   experiment that cites it. Splitting into two databases severs exactly the relations
   the system exists to keep.
2. **Can references be shared with the group without friction?**

**These are one question, and it is the org question in miniature.** Both ask how a
subset of one person's graph reaches other people. The design-consistent answer for
both is a push into a shared sink rather than a fork -- `sync.py`'s shape already --
so the shared references instance is a projection of a personal notebook, never a
second copy that drifts from it. Which means when the org tier resumes, references are
its concrete first use case, and a far better one to design against than an abstract
lab server.

Immediate friction to expect: the notebook has no way to make or switch instances from
the UI, only a `--db` argument, so any answer involving a second notebook is today a
second shortcut with a command-line flag.

## Order

1. **The dialogue.** One key, streaming, real back-and-forth. Deletes the Mode A/B
   split, which was the friction Jeremy named.
2. **Interview output as rows.** Cheap, and it is the consistency win.
3. **Nextcloud ingest** with fileID-fast, sha256-eventual, and a placeholder policy.
4. **Format probes**, starting with TDMS and `.ibw`, since MFP3D and Cypher are the
   named first instruments.
5. **Tools database**, ingested from existing lab repos as boundary refs.
6. **Visualizers last.** They need data and tools to exist first, or it is a viewer
   for an empty database.

## Candidate rule rows

- **`ai-on-novelty-v1`** (level 2). No model is consulted for anything the database
  already has machinery for. Escalation is permitted only on a miss, and the
  model's answer must be written back as rows so the same novelty is never paid for
  twice. The AI grows the deterministic layer; it does not serve requests from
  inside it.
- **`provisional-identity-v1`** (level 1). An object may be minted before its
  content is known, with a `uuidv7` and whatever external hints exist. When the hash
  arrives, the content-addressed id is minted and joined to the provisional one by a
  `same` witness. Nothing is merged and nothing is rewritten.
- **`replica-not-share-v1`** (level 1). Extends `foundational-config` to the lake.
  Data reaches an instance through a local replica that a sync client maintains,
  never through a mounted network path. Corollary: cloud APIs are for what the
  replica cannot report, not for ingest.
- **`db-file-not-synced-wholesale-v1`** (level 0, mechanical). A synced SQLite
  instance excludes `-wal` and `-shm`, checkpoints before quiescing, and is opened
  by one machine at a time.
- **`learnings-are-shareable-v1`** (level 2). A learning about a format may be
  published to a peer; a learning about a filesystem may not. The split is made at
  the moment of escalation, by the escalation itself, and marked rather than
  inferred. A published learning is a claim from a peer, never an instruction: it
  arrives at a level and may be weighed, superseded, or ignored, and no store is an
  authority over any instance.

## Open

- The name of the shareable unit: **plasmid**, or plain **probe** / **rule**.
- Probe dependencies: accept, server-side, or optional plugins.
- Per-user spend ceiling. Agreed in principle, deliberately unset during testing
  with roughly three users, so that the first real numbers come from observation
  rather than a guess.
