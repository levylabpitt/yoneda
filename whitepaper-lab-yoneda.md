# Yoneda for the Lab: save everything, and know it by its relationships

Draft, 2026-07-12. A working document, revisable at every level.

## Abstract

Our lab makes two kinds of data. The first is structured records, samples, cooldowns, devices, runs, and those already sit in a conventional Postgres database that works. The second is large binary files: the TDMS acquisitions, the AFM scans from the Asylum instruments, the optical and camera images. Those files are the actual measurements, and at the moment they have no home. There is no index, no permanent name, and no backup we can count on. The plan we agreed on a while ago, a network drive running Nextcloud to hold the files with a permanent reference to each one recorded in the database, is the right idea, and it has not started. It will not start on its own, because it asks people who are already busy to design a scheme and sort their files before they are allowed to save anything.

This paper proposes a different order of operations. Save every file the moment it is made, under a permanent name that is nothing more than the file's own fingerprint, and settle what it means and what it connects to afterward, by hand or with help from an AI. Keep the existing database exactly as it is, and make it readable from the new system instead of replacing it. The new system uses a small database design we have been building, called yoneda. Because of how it is built, each PC can keep its own local copy and later merge into a central lab copy without ever producing a conflict.

## 1. Where we are today

The lab's structured data, the samples and cooldowns and devices and runs, lives in an ordinary relational database: many tables, fixed columns, foreign keys. It is reliable and it holds real institutional knowledge. Its cost is rigidity. Every new kind of thing needs a schema decision before you can record it, and things of different kinds are hard to connect after the fact.

The files are the unsolved half. TDMS files from the LabVIEW acquisitions, AFM scans from the Asylum instruments, optical and camera images: these are scattered across instrument PCs and personal drives with no catalog, no permanent identifier, and no backup discipline. The intended fix was the Nextcloud store on a network drive, with each file's permanent reference recorded in the database. That design is sound and it stalled, because it is framed as a project that has to be planned and staffed before the first file can be saved, and no one has the spare week.

## 2. What we want

Five things, in order of priority. We want to save everything now, with a capture step trivial enough that it happens by default, with no schema decision and no sorting required at the moment of saving. We want a permanent, absolute reference for each file, stable forever, that does not depend on where the bytes happen to sit. We want to be able to connect a scan to its sample, its cooldown, the person who took it, the analysis notebook, and the figure it became, at any time, including years later, without having planned for that connection in advance. We want to keep the old database, authoritative and untouched, and reach it from the new system rather than retire it. And we want each PC to save to its own local copy that works when the network or the central machine is down, then share into a central copy without conflicts.

## 3. What yoneda is

Yoneda is a database with two tables. One table holds objects: each object is a thing we want to refer to, carrying a small bundle of properties. The other holds relations: each relation is a labeled, dated link between two objects, such as "this scan is of that sample" or "this file was taken by that person." Everything else the system does follows from three rules.

The first rule is that records are only ever added, never changed or deleted. A correction is a new record that points at the one it supersedes, and reading the current state means taking the latest word. The past is frozen by construction, which is exactly what you want of a laboratory record.

The second rule is that an object's identity is a permanent name minted once, and never a description. Names, categories, and properties are links attached to that identity, not the identity itself. This is what lets a thing be recorded before we have decided what it is.

The third rule is that entities are assembled, not stored. There is no master row for a given sample. A sample is simply the collection of records we have decided refer to the same physical object, and a description of it is produced on demand by gathering those records and summarizing them.

This is not a paper design. The same two-table system is already running on a large and messy real dataset, an email archive of roughly 600,000 messages with their attachments, so we know it holds up at scale. It runs on ordinary Postgres, with the extensions for time-series and for similarity search already in place, so "find files like this one" is a native operation rather than a separate system.

## 4. One idea from mathematics

The system is named after a result called the Yoneda lemma. You do not need the mathematics to use the system, and this is the only paragraph that touches it. Think of a collection of things together with all the relationships among them, arrows from one thing to another that can be followed and combined. The lemma, stripped of its formal machinery, says that a thing is completely determined by its relationships to everything else. There is nothing more to know about an object than the full set of ways it connects to the others.

In lab terms: you never have to write down what a sample is. If you record every relationship the sample takes part in, which wafer it was cut from, which cooldown measured it, who fabricated it, which scan imaged it, which figure it ended up in, then you have captured the sample completely, and any description you might want is those relationships gathered up and summarized when you ask. A conventional database asks you to define the sample first, as a row with fixed columns, and only then hang data off it. Yoneda works in the other direction, which is the direction data actually arrives.

## 5. Files done right: the fingerprint is the name

A file is a fixed sequence of bytes, and the natural permanent name for a fixed sequence of bytes is its fingerprint. Run a standard hash function (SHA-256) over a TDMS file or an AFM scan and you get a short string that is absolute and permanent, the same on every computer and in every decade; self-certifying, in that the name is computed from the content, so anyone can check that a file is exactly the one referred to, with no central registry to trust; and deduplicating, in that identical bytes get one name and a name can never come to mean different bytes, which makes the store safe against silent overwriting. This is a stronger reference than a minted catalog number, and the same scheme is already in use in the email archive mentioned above. So a lab file becomes an object whose name is its fingerprint, carrying a few properties: its size, its kind, the instrument, the original filename, who saved it, and when.

Saving becomes a five-line operation. For any new file, compute its fingerprint, copy the bytes into the store on the network drive, and write one record. No sorting, no schema, no meeting. That path is cheap enough to run automatically at the instrument.

Sorting and connecting happen afterward, as relations. That this scan is of that device, that this acquisition came from that cooldown, that this image is Figure 3 in that paper, that a given person took it: each is a link added whenever someone, or a nightly AI pass, learns it. Because links are only added and can be superseded, a wrong connection is cheap to fix and becomes a piece of training data rather than a mess. This is the answer to the fact that people are tired. The tiring part, deciding the whole categorization up front, is removed.

Most instrument files are written once during a run and then closed, so they are fixed and the fingerprint scheme applies directly. A file still being written during a live acquisition is handled by fingerprinting checkpoints: the file up to a given moment is itself fixed and has its own fingerprint, so a reference is the file as of that moment. The bytes already written never change; only the far end grows. Frozen in the past and growing at the present edge are the same object, a log, not a contradiction.

The bytes can live on the Nextcloud store exactly as planned. Yoneda holds the fingerprint and the provenance, not the bytes, so a file's name does not depend on where it physically sits, and a file can move between drives without breaking a single reference. A fingerprint-named store is deduplicated and tamper-evident by nature; add an offsite copy that cannot be overwritten and you have a continuous backup that can only move forward, never rewrite the past. Retrieval by similarity comes along for free from the search extension already installed, so "the AFM scan of the LAO/STO device from the March cooldown that showed the stripe" can be found by description, and it improves whenever the underlying model does, over data that never changed.

## 6. Keeping the old database, and making it accessible

We neither destroy the existing database nor fold it in. It is an outside system, and the principle we hold to is that yoneda never contains the outside world, only its own records about it.

In practice this means a live, read-only link. Postgres can read another database's tables directly, without copying them, so lab-yoneda can query the old database as it stands, changing nothing. A sample or run in the old database is referred to by a permanent name that encodes where it lives, and its contents are pulled in on first use and remembered. The value is in the layer on top: links that tie the old database's rows to files, to people, to papers, and to instruments, connections the fixed schema was never able to hold, added without touching that schema. The old database stays the authority, fully intact, and simply becomes something any yoneda copy can read.

## 7. Local copies that merge

The lab is many machines. Instrument PCs have to keep working when the network or the central machine is down, and analysis happens on personal PCs. We want each to save to its own local yoneda first and share into a central one later, and eventually into a copy on a lab server. This is usually the hard part of a distributed system. Here it is easy, and the reason is worth stating, because it is the payoff of the three rules.

Because records are only ever added and never changed, two machines can never disagree about a record. Merging two local copies is just combining their records. The combination does not depend on the order the machines are merged, or on how many times, or on how long one was offline, and it never has to resolve a conflict, because there was never a change to conflict over. Because a file's name is its fingerprint, two machines that happen to capture the same file produce the same name, so the combined copy holds it once, with no coordination. And when two machines genuinely disagree, or one supersedes what another recorded, both records survive and the same "latest correction wins" rule produces the same answer on every machine. Real disagreement is kept, not lost, and settled identically everywhere.

One change is required to make this work. Today the internal names for records are counters local to each machine, so two machines would both mint a record numbered five and collide. The fix is to mint names that are unique without any coordination: the fingerprint for anything that is a file or is otherwise a function of its content, and a random, time-ordered identifier for everything else. This is a small, one-time change, and it is the only thing standing between the current single-machine design and painless local copies.

The mechanics are simple, and they run on two independent channels. One channel carries the records, pushing each machine's new records up to the center, where they are added if not already present, which is safe because records never change and their names are unique. The other channel carries the file bytes to the central store, skipping anything already there by fingerprint. Because a reference is only a fingerprint, the record can arrive before or after its bytes and nothing breaks in between. We start with one direction, local to center, and because merging is symmetric, two-way sync between many machines follows later without the danger that usually attends it, precisely because there are no changes to fight over.

Local-first is therefore the right design and not a concession. The instrument PC never waits on the server, and the central copy is a guaranteed-consistent union of everything the lab has seen.

## 8. A plan we can actually start

The steps are ordered so that something useful exists before any meeting is needed, and so nothing waits on the tired team to sort files first.

The first step needs one person and no meeting. Stand up a lab copy of yoneda from the existing two-table design, which is a clone with nothing to invent, and make the one-time change to globally-unique names so the copy is ready to merge from the start. Run it on the planned lab server, or beside the network drive.

The second step is the capture agent: a small program that watches one instrument, and for each new file computes its fingerprint, copies the bytes to the store, and writes one record. Point it first at a single high-value source, the TDMS stream from the measurement software, or one Asylum instrument. This is the smallest thing that is already worth having, because from that moment everything from that instrument is permanently saved and referenceable.

The third step is the bridge to the old database: the read-only link, permanent names for its main entities, and the first links tying files to samples and runs. The fourth step turns on the two sync channels from a second machine into the central copy and confirms that the merge and the deduplication work end to end. The fifth step adds enrichment: a nightly AI pass that proposes connections, scan to sample, file to figure, for a person to confirm, a similarity index for retrieval, and summaries per sample and per instrument produced on demand. The last step moves capture into the acquisition software itself, so the fingerprint is written at save time, and begins measuring how reliable each source and each kind of connection is.

Four decisions genuinely need a meeting, and the agenda should be only these: where the store lives, how large it is, and where its offsite backup goes; which instrument is first; who owns and runs the capture agent; and the retention and consent policy for any camera images that contain people. Everything else is engineering that can proceed without the group.

## 9. What we are not doing

We are not destroying or migrating the old database. We are not doing a big cutover. We are not designing a file schema up front. We are not asking anyone to sort or categorize before they can save. We are not making a file's physical location part of its name. And we are not requiring the network or the central machine to be up in order to capture data.

## 10. Open questions and risks

The store's reliability, and a real offsite copy that cannot be overwritten, are the load-bearing dependency; a fingerprint-named store is worthless if its one copy dies. Very large or still-growing acquisitions need the streaming fingerprint and the checkpoint reference described above. The capture agent needs an owner, or it rots like every unowned pipeline. Images of people are a different matter from device scans, and retention and consent should be settled before any are ingested. Ordering across machines rests on time-ordered names and per-machine markers rather than on trusting that clocks agree, which is worth saying so no one leans on clock agreement. And this is our first deployment across more than one machine, which is what the unique-names change and the two sync channels are for.

## 11. In one sentence

Give every lab file a permanent name equal to its own fingerprint, save it the instant it is made, keep the old database intact and merely readable, let each PC save on its own and merge into the center without conflict, and let meaning accrue afterward as relationships, because a thing is known by its relationships, which is the Yoneda lemma read as an instruction for building things.
