# Things, photographs, and where identity comes from

Design discussion, 2026-07-25/26 (Jeremy and Claude). Continues the QR-code-as-hash
thread. Nothing here has been written into the database; the candidate rule rows at
the end are proposals.

## The problem

A file has computable identity: it *is* its bytes, so sha256 is intrinsic, and two
machines that never communicate agree. A screwdriver is not its pixels. Every
photograph of it is a lossy projection that depends on angle, lighting and time, so
two photographs of one object hash differently, and two objects can photograph
almost identically. The mapping fails in both directions. Which gives the flat
answer to "photographs of things really should have a hash, but how to assign?":

**You cannot compute the identity of a physical thing. You can only witness it.**

## A Thing is a component, so there is no new machinery

This is the same problem as persons, already solved here. Persons are never stored;
a person is a connected component of `same` witnesses. A physical thing is the
same: give it an internal id that means nothing by design, attach every external
identifier you actually have, attach every observation, and let the thing be the
component. Nothing in the substrate has to change to hold the physical world.

The consequence worth stating out loud: **hashes stabilize evidence, components
establish identity.** The photograph's sha256 is not a name for the screwdriver. It
makes the evidence immutable and citable, so that later arguments about which thing
the photo shows cannot quietly change the photo underneath the argument.

## The QR code was never the hash

Correcting the analogy that started this. A QR code is not a physical object's
hash, because it is attached rather than computed. It is a witness of near-unit
confidence that two observations are of the same individual. That reframing pays
for itself immediately: when a label falls off, nothing becomes corrupt, we simply
lose a witness, and the component holds together by whatever else we recorded.

## Serial numbers are the DOIs of equipment

An external authority (the manufacturer) has already assigned an identifier, and it
is stable, printed on the thing, and not ours to invent. That is exactly a boundary
ref, the same shape as a DOI: `{type:'ref', scheme:'serial', mfr:'Oxford', sn:'...'}`.
The level-crossing caution from the DOI discussion applies unchanged. A serial
identifies a manufactured unit; it does not identify a configuration, so a fridge
that has been rebuilt twice is one serial and several states, and the states are
dated observations.

## Samples cannot be labeled, so their identity is relational

The objects this lab cares most about are the ones with no room for a marker. A
5 mm chip cannot usefully carry a QR code, so its identity is, in practice,
entirely its provenance: the growth run it came from, the position in that run, the
cleave it survived. This is the Yoneda claim in the most literal possible setting.
The sample is determined by its relationships because there is nowhere to write a
name.

Practical consequence: for samples, provenance capture is not metadata, it is the
identification system. A sample whose growth run was never recorded has no identity
at all, and no amount of later photography recovers it.

## Photographs carry two hashes doing two different jobs

1. **sha256 of the image file.** Identity of the evidence, confidence 1. The photo
   is an ordinary hashed file like any other, with the camera as its source
   instrument (`source-as-instrument-v1`).
2. **A perceptual descriptor** (pHash, or an embedding). This is not identity and
   must never be stored as one. It is an *instrument for proposing sameness*: it
   emits `same` witnesses between a photo and a Thing, or between two photos, with
   confidence below 1, retractable like any other instrument's claim. It belongs in
   the same slot as the deterministic matcher in `ai_link.py`.

EXIF is free witness material and should be harvested rather than discarded: the
timestamp, the GPS fix, the camera body. A photo taken in the lab at a known time
constrains which thing it can be, which is often enough to promote a weak match.

## Fungibility becomes a modeling decision, not a policy

The lab's QR decision (label the small and expensive, ignore the 1/4-20 screws) is
not a decision about whether to bother recording something. It is a decision about
*which level* gets individuated, and the schema can say it exactly:

- **Fungible things exist once, as a type.** One object for "1/4-20 x 3/8 stainless
  socket head", never one per screw. Quantities and locations hang off the type as
  dated observations.
- **Individuated things exist as items,** each with its own object, linked to its
  type by `is-a`.

So the criterion from the earlier discussion (irreplaceability, for which $/size is
a good cheap proxy) decides type-node versus item-node, and the answer is legible
in the data instead of living in someone's memory of where we stopped.

## Containment composes; location is never a property

A sample sits on a carrier, in a puck, in a fridge, in a room. Containment is
transitive, so it composes, which makes this genuinely categorical rather than a bag
of nodes: `in` relations chain, and "where is this sample" is a traversal.

Location is always a dated observation, never a field on the thing
(`snapshot-on-observation-v1`). "The thing in slot 3" is the physical analogue of a
file path: a hint, true at a moment, and the weakest of the identity instruments.
That is precisely the dangerous quadrant from the earlier discussion, an
irreplaceable object tracked by a weak proxy, and it is where lab knowledge dies.

## Candidate rule rows (proposed, not inserted)

- **`physical-identity-is-witnessed-v1`** (level 2): identity of a physical thing is
  never computed, only witnessed. Markers, serials, photographs and provenance are
  all instruments with their own confidence; the thing is the component. A lost
  label removes a witness and corrupts nothing.
- **`fungible-as-type-v1`** (level 2): individuate an item only when it is
  irreplaceable; otherwise record the type once. Cost to regenerate over cost to
  record is the criterion ($/size is the physical proxy the lab already uses).
- **`perceptual-hash-is-not-identity-v1`** (level 2): cryptographic hashes name
  evidence, perceptual descriptors propose sameness with c < 1. Never store a
  perceptual hash where an identity is expected.
- **`marker-threshold-asymmetry-v1`** (level 2): labels detach and cost recurring
  effort, computed hashes cannot detach and cost once. So the threshold for
  individuating digital objects sits far below the threshold for labeling physical
  ones, and the lab's screw threshold is not precedent for files.

## Photograph now, interpret later (2026-07-26, Jeremy's survey plan)

The goal: photograph the lab and the office, have an AI turn each photograph into
claims ("this shelf holds N books, with these titles"; "this BNC leaves CH1 of the
lock-in at rack position 4"), and build up evidence of how the instruments are
actually connected, because that connectivity is what makes a TDMS file
interpretable later. Jeremy wants the substrate stable before launching his own
instance, and has no database he wants to keep yet.

**That hesitation costs nothing, because the two halves have opposite economics.**
A photograph of the rack as it is wired today is irreplaceable: tomorrow it is
rewired and the evidence is gone forever. An interpretation of that photograph is
infinitely regenerable, and next year's model will do it better. So by the
irreplaceability criterion from the earlier discussion, capture is eager and
interpretation is lazy. Start photographing immediately; let the database be born
later and ingest the corpus retroactively, which works because every photograph
carries its own timestamp.

### Capture protocol (needs no software, start this week)

- Shoot at full resolution and never downscale for the AI. A better model later
  will want the pixels, and this is the same irreplaceability argument.
- Preserve EXIF. The timestamp is what makes retroactive ingest possible, and some
  sharing paths strip it. Move files as files, not through anything that
  re-encodes.
- Overlapping coverage: a wide shot of the bench or rack face, then closer frames,
  so context is recoverable when a detail shot is ambiguous on its own.
- Anchor the room. Indoors GPS is useless, so open each session with a frame that
  fixes the location (the door plate, the room number, a recognizable corner).
- Do not name the files. That is the whole thesis on the front page: save the bytes
  first, decide what they are later.
- Photograph the same shelf or rack face more than once, from different angles.
  Independent frames become independent witnesses, and agreement between them is
  what the consensus view is for.
- Deliberately: whiteboards and monitors can hold unpublished results or student
  information, and these files are headed for cloud storage and possibly a shared
  server later.

### What to ask the model for, and what not to

Ask for local, checkable observations, not for the answer. Each claim should carry
what it asserts, a bounding box, its own confidence, and the model and version that
produced it. Then reinterpreting the whole corpus with a better model is an ordinary
operation: a new instrument emitting new witnesses, with the old ones retained, not
a migration and not an overwrite. This is what makes "it will never be perfect" a
non-problem: imperfection is recorded as confidence, and improvement is another
source.

Two specific cautions from the two tasks Jeremy named.

**Book spines.** Vision models hallucinate plausible titles, and a hallucinated
title is indistinguishable from a real one once it is in the record. Require a
bounding box per title so any claim can be re-checked against the pixels, and
cross-check every title against an authority (the Paperpile library first, then an
ISBN or Open Library lookup). A title that resolves gets promoted; one that does not
stays low-confidence and flagged. Never let an unresolved title enter at c = 1.

**Cables.** Do not ask for the graph. Tracing a cable through an occluded bundle is
beyond current vision, and a wrong topology is worse than none. Ask instead for
endpoints, which is all the TDMS problem actually needs: which instrument port fed
which channel, not the route the wire took through the rack. Connectivity is then
assembled from many local endpoint observations, the same way a person is assembled
from `same` witnesses, and it is never stored as ground truth.

This is also the one place where the labeling threshold argues *for* markers.
Cable ends are small, and a mislabeled cable misinterprets an entire dataset, so
they sit squarely in the small-and-expensive quadrant. Numbered heat-shrink or a
small tag at both ends converts an intractable vision problem into OCR.

### Why this is calibration metadata, not documentation

A TDMS file records channel names and some hardware configuration. It does not
record what was on the other end of the wire, and that is exactly the context needed
to interpret it years later. Since a rack gets rewired, every connectivity claim is
a dated observation with a validity interval, and photographs are what bound the
interval: a wiring configuration witnessed in February and again in April can be
carried across a March data file, and a photograph showing a change closes the
window. This is `snapshot-on-observation-v1` and `window-censoring-v1` doing real
work on the physical world, and it means the photographs are part of the
measurement chain rather than a record of it.

A framing note: this is the opposite of an internet of things. The instruments stay
dumb, with no firmware, no network and no batteries, and the observer does all the
work. That is why it will work on a 1980s lock-in amplifier, which no IoT scheme
ever will.

## Capture that people will actually do (2026-07-26)

Credit where it belongs: **temporal proximity between two scans as evidence of
spatial proximity is Jeremy's idea**, from January 2025, and it is one of the
reasons the stack is on TimescaleDB in the first place. The hypertable was chosen
for this.

Ellis Island (a photostation beside a laptop for new acquisitions) has poor
adherence. The diagnosis is on the project's own front page: it asked people to
classify at capture time, walk to a station, use a laptop, fill something in. Save
the bytes first and decide what they are later applies to human behavior as much as
to files. So move every requirement to the interpretation side and leave the capture
path as close to what people already do as possible.

- **Phone to Google Drive, which is already the default here.** A shared Drive
  folder syncs to Jeremy's PC through File Stream, so the ingest side is a local
  folder watch and no new infrastructure exists at all.
- **Upload as files to Drive, not through Google Photos storage-saver,** which
  re-encodes and downsamples. That collides directly with the never-downscale rule,
  and it is silent when it happens.
- **Video beats stills for racks and optical tables.** Parallax from a slow walking
  pan defeats occlusion in a way no single-image model can, since you genuinely see
  behind the bundle, and frames can be extracted at any resolution later. It is also
  less work than a careful set of stills, which is the point.
- **Ask for many photographs of a new item, not one good one.** Burst-shooting is
  natural on a phone and compliance is higher than for a single deliberate frame.
  Box, serial plate, manual, and the thing itself from several angles.
- **Trigger nags on physical events, not on a calendar.** A package arriving is the
  cue. And a specific tiny request to a specific person ("four angles of the thing
  you just unboxed") gets acted on where a standing policy does not.

## People are authors, not instruments

Jeremy pushed back on calling GSRs instruments, and he is right; the term is
retired here. The distinction that survives is real and worth stating precisely.

**Attribute every observation to the person who made it.** That is provenance, it is
necessary, and it serves the person: their careful work stays visible, their claims
can be defended, and nobody's sighting is silently overwritten by someone else's.
This is authorship, the same thing an author line on a paper does.

**Do not fit a per-person reliability weight.** A number attached to a student that
says how much their observations count is a performance metric, in a relationship
that already has a power gradient, and it will drift into being evaluative no matter
how it is introduced. Refuse it.

Almost all of the real signal is available without it, because reliability is
mostly a property of the evidence and the conditions rather than of the person: a
blurry frame is weak evidence whoever took it, a hurried batch scan is weaker than a
deliberate one, an old sighting is weaker than a new one. **Grade the evidence, not
the author.** Where two sightings conflict, the newer wins under the decay law, not
because someone is rated lower.

Rule of thumb: authorship is credit, not calibration.

## Open

- Which kinds the `Things` category actually needs (equipment, part, sample,
  container, space, consumable-type) and whether kind is even worth enumerating,
  given that kinds here have historically been claims rather than schema.
- A `yoneda\Things\` dossier vault, one file per individuated thing, mirroring the
  People vault so Everything finds a thing by name. Cheap, and the compiler pattern
  already exists in `compile_people.py`.
- What a QR code should encode. A URL that resolves to the thing's dossier is the
  useful choice, but the site is public and distribution is currently lab-only, so
  resolution probably has to be local or gated.
- Whether a photo's perceptual descriptor should be stored in the record or
  recomputed on demand, which is the eager-versus-lazy question again, and by the
  irreplaceability criterion the answer is lazy: the photo's bytes are kept, so the
  descriptor is always regenerable.
