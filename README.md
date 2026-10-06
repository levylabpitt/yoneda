# Yoneda

A place to put your data before you know what it is.

## The problem

You make a file. Before you can store it you have to say what it is: which
folder, what to call it, which fields it has. You are being asked to write down
what a thing is before anyone knows what it means, at the moment you are least
able to answer. So it gets called `final_v3_actually.dat`, and a year later
nobody can say which sample it came from, who took it, or whether the copy on
this drive is the same bytes as the copy on that one. The data is not lost. It
is sitting right there, and you cannot trust it.

The usual remedy is to design a schema first. That works when you already know
what you are collecting. It fails when the useful connections are the ones
nobody anticipated, and it fails hardest at the moment of saving, because it
asks whoever is at the instrument at two in the morning to invent a
categorization before they are allowed to save anything. They will not do it,
and they are right not to.

## The other order

Save the bytes the instant they exist, under a name that takes no decision,
because it is computed from the bytes themselves. Two people who capture the
same file arrive at the same name without talking to each other, and a name can
never come to mean different bytes.

What the file means accrues afterward, as relationships. This scan is of that
sample. This image became figure 3. Someone adds a link when they learn one, and
so can a program. Nothing has to be right the first time, because a wrong link
is superseded rather than repaired, and the wrong link stays as a record that
the mistake happened.

Save first, name by fingerprint, connect later.

## What you get

Your own copy. It is empty, it is yours, and nothing precedes it.

```
cd stem-cell
docker compose up -d
```

Docker Desktop is the entire dependency list. First boot takes about twenty
seconds, and when it finishes your database has a big bang: the moment it was
brought to life, recorded once, as the first thing it knows. Your copy is
identified by that moment, which is why there is no name to configure and no id
to register. Two copies in the same group can be merged later without either of
them having to have been present at the other's birth.

Three things will look wrong at first, and each is load-bearing.

Nothing is ever deleted. A correction is a new record pointing at the one it
supersedes, and reading the present means taking the latest word. Your bad run
stays, because how often you are wrong is a measurement, and a tidy database
that throws away its mistakes can never tell you.

Identity is never a description. A thing's name is not what it is called. That
is what lets you record something before deciding what it is.

Entities are assembled, not stored. There is no master row for a sample. A
sample is the collection of records claimed to refer to the same physical thing,
and any description of it is produced on demand. Learn later that two labels
meant the same sample and you add a claim; you never merge rows and you never
lose the evidence.

## What a cell is

Every record is a cell: an identity, a JSON payload, the instance that wrote
it, the time the thing happened, and the time the cell said so. A payload whose
`faces` field points at other cells is a relationship, so a file, a sample, an
instrument, a claim about a claim, and a correction to one are all the same kind
of row. One specification (`cell/genome.py`) generates both dialects, SQLite for
a machine sitting at an instrument and PostgreSQL with TimescaleDB for a hub, so
rows copy from one to the other with no conversion step. In SQLite the whole
schema is this:

```sql
CREATE TABLE cell(
  i   TEXT PRIMARY KEY,  -- content hash (immutable cells) OR uuidv7 (authored)
  j   TEXT NOT NULL,     -- payload: {kind, faces:{role -> cell id}, data:{...}}
  b   TEXT,              -- authoring big-bang id (NULL => content-addressed)
  t   REAL,              -- event time, unix seconds (NULL => content-addressed)
  rt  REAL               -- record time: when this cell was asserted
);
CREATE TABLE edge(             -- derived, rebuildable, maintained by trigger
  cell TEXT NOT NULL, role TEXT NOT NULL, endpoint TEXT NOT NULL,
  PRIMARY KEY(cell, role, endpoint)
);
```

plus three indexes on `cell` (`t`, `rt`, and `(b, t DESC)`) and one on
`edge(endpoint)`. `edge` holds no truth. It is one row per face, so that asking
what touches a given cell is a B-tree lookup instead of a scan over payloads,
and you can drop it and rebuild it from `j`.

### A worked example

Take an invented lab. A sweep comes off an instrument and lands in a watched
folder. Two of the resulting cells, printed from a throwaway instance:

```
file  i = 0de0b894-5c5c-8e11-9ef5-a45f45c170dc
      j = {"bytes":41213,"kind":"file","sha256":"9f2c0e1a...1a"}
      b = NULL   t = NULL   rt = 1789956858.677

run   i = 01a0c1be-2334-751d-bb52-695fa72a96bb
      j = {"kind":"run","data":{"file_name":"sweep-0412.dat"},
           "faces":{"file":"0de0b894-...","sample":"d48aca4c-...",
                    "instrument":"320539fd-..."}}
      b = 01a0c1be-2334-7825-b070-f0cace5864cd
      t = 1776000000.0   rt = 1789956858.677
```

The file cell is definitional, so its identity is computed from its content: a
UUID v8 carrying the first 122 bits of the SHA-256 of the canonical payload. The
full hash stays in the payload, because the id is an index and the hash is the
evidence. It has no `b` and no `t`, since a definition is not something that
happened, and `rt` is stamped anyway, because when this instance first saw it is
a fact about this instance. Run the same insert on a second instance that has
never heard of the first and the id comes back identical.

The run cell is somebody's claim that those bytes came off bench-2 with sample
S-12 in it, and it can be wrong. It is authored, so it gets a uuidv7, it carries
`b`, the instance that wrote it, and it carries both times. Its three faces
become three `edge` rows by trigger, one each for `file`, `sample` and
`instrument`.

### Corrections

Say another cell claims S-12 carries coating A, and the notebook later shows it
was coating B. The correction is a cell of kind `outcome` pointing at the first
claim with `{"status":"retracted"}`, plus a new claim naming coating B. Run it
and the first claim is absent from the `active` view and still present in
`cell`, which is the whole of what retraction means here. It keeps its author,
its date and its evidence. How often a label gets revised is then a number you
can compute, which a database that edits in place cannot tell you at all.

### Order of statement

An outcome is an ordinary cell, so it can itself be the target of one. The same
sweep supports a stack five deep: the file, the run that claims it came from
S-12, the retraction of that claim, a colleague's objection to the retraction,
and an analysis that rests on the objection. Each level is a cell pointing at a
cell, the number of tables never changes, and `active` applies at every level
unmodified. A schema that separates nodes from edges holds the first two levels
and needs a new table at the third, which is what happened to the `o`/`r`
prototype the first time a retraction appeared.

### Identity is a property of the cell

A cell that is a function of its content is named by that content, by the same
computation on every machine. Two people who save the same file from two copies
of a drive produce one cell carrying two provenance records, and no merge step
runs. A cell that is somebody's assertion gets a time-ordered random identifier
instead, and carries the instance that authored it. Identical bytes converge and
independent claims do not: two people calling the same material coating A
produce two cells, both kept, weighted when you ask for a consensus.

### Merging without remapping

Copies exist whether or not you plan for them: the machine at the instrument, a
hub, a copy on a laptop, an archive dump. Merging any two of them is a union on
identity, with no remapping table to build and none to keep forever, because no
identifier comes from a counter that two machines could each start at 1. An
earlier version of this design used exactly such counters, and that was the
defect that made painless local copies impossible.

### Two times

An event happening and an event being written down are different facts. A file
acquired in 2016 and recovered from a departing student's drive in 2027 carries
`t` in 2016 and `rt` in 2027. One column would date the measurement to the day
it was recovered, or else hide the recovery behind every sync watermark in the
system. Measured over 20,699 pages of one lab's notebooks, 58% were written
after the day they describe, median lag one day, and 3.5% before it, because
sessions get laid out in advance. Both times are indexed, so a file that carries
no sample label still joins to the cooldown it was taken in, through the
instrument log.

## The compendium

`compendium/` builds a book about all of this. You should not have to read it,
and you should certainly not have to read any of the code in this repository.
The generator (`generator/`, in progress) takes a few DOIs and a group web page
and produces a version of the book aimed at you: your instruments, your file
formats, your vocabulary, and worked examples built from your own publications
rather than someone else's. It renders LaTeX, then PDF.

By default the generated document contains no code at all. Ask for the builder
edition if you want it back.

## The name

The Yoneda lemma says a thing is completely determined by its relationships to
everything else. You never have to write down what a sample is: record every
relationship it takes part in, and you have captured it completely. A
conventional database asks you to define the thing first and hang data off it.
This one works in the direction data actually arrives.

Design questions — how this relates to W3C PROV, why entities are computed rather
than stored — are collected in [FAQ.md](FAQ.md).

## Status

Running, in use, and honest about its bugs. The compendium names the ones that
are known and prints the command to reproduce each. As of 2026-07-17 there are
no known unfixed defects in the stem cell, which is a statement with a date on
it and not a promise.

Not yet built: the sync channels are proven in tests and by hand, and do not
yet run unattended as a service. The confidence-weighting law is a seed prior
that has never been fit to data.

## License

Code is BSD 3-Clause, in [LICENSE](LICENSE). The prose, which is the compendium, the design documents and
this README, and the brush mark in `brand/`, are CC-BY-4.0: use them, change them, say where they came
from.

This repository is the public record of the design. It is published as a single commit from a working
repository that holds laboratory operations, correspondence and other material that is nobody else's
business.
