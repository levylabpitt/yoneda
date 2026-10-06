# Yoneda: a categorical brain for people, and ultimately everything

(Project formerly "Names"; renamed 2026-07-04. The Yoneda lemma is the design philosophy stated as a theorem: an object is completely determined by its web of morphisms. Nobody observes a person; a person IS the totality of observations attached to them, and a compiled profile is the Yoneda embedding evaluated lazily. The working directory remains `Names` to preserve session/memory continuity; the database, container, and brand are `yoneda`.)

**Status 2026-07-03:** Phase 0 is live. The substrate is Jeremy's own CDB (7-line categorical database, June 2025; see the Overleaf projects "Categorical Database Architecture" and "Spacetime Database Topology"), which turned out to be this design arrived at from the physics side, plus branch superposition (`b`) for unresolved identity. Deployed with three amendments (reifiable arrows, realize-as-event instead of delete, consensus law as data) in Docker container `names-cdb` (timescale/timescaledb-ha:pg17), localhost:5434, database `names`. See schema.sql and seed.sql.

Founding design document, distilled from discussion 2026-07-03. Everything here is a draft in the usual sense: revisable at every level, including this sentence.

## 1. The problem

People information (names, partial identities, collaborators, personalities, baggage, relationships) is scattered across surfaces: Claude memory files, Gmail, contacts, Asana, LinkedIn, Paperpile coauthors, the Pixel Watch Loop Recorder, Chandralekha's memory. There is no uniform representation. The goal is a pervasive "brain" that remembers names and relationships better than a human can: better at ingestion, retrieval, mining, and contribution, and woven into every Claude session rather than bolted on.

## 2. The wrong framing, and the right one

The first-pass framing (five rival database designs: markdown vault, event ledger, graph, relational, federation) treated the plans as objects to choose between. The correct framing is categorical: the plans are functors, and the design question is what their common domain is.

### The site

The primitive category is **Obs**: observations. A watch recording, an email, a bib entry, a mention in conversation, a remark from Chandralekha. Each has timestamp, source, raw content. Persons are not objects of Obs; nobody observes a person, only encounters and mentions.

Identity enters as morphisms: an **identification witness** is a span `o1 <- w -> o2` asserting co-reference, carrying evidence type, provenance, and confidence. Entity resolution is the morphism data of the category, not a preprocessing step.

### Persons are computed, never stored

A person is a connected component (pi_0) of the observation graph under identification spans.

- Merge = add a span. Split = retract a span. Both are reversible edits to morphism data; observations are never touched.
- Store the groupoid, not the skeleton. A CRM stores one canonical record per person and discards the isomorphisms; here the witnesses (the evidence of co-reference) are exactly what gets revised, so they are the data.
- "Same person" means equivalent-up-to-revision: witnesses are 1-morphisms, revisions of witnesses are 2-morphisms.

### Profiles are Kan extensions

A profile (markdown dossier, SQL row, graph node) is the left Kan extension of observation data along `Obs -> Person`: the colimit of everything observed in that person's component, with an LLM as the colimit-taking machine for unstructured content. Universal property as correctness spec: the profile contains exactly what the observations force, and any other summary factors through it.

### Surfaces are functors; pervasive means the diagram commutes

Every surface is a functor out of the site: the markdown vault, Postgres rows, the relationship graph (a profunctor Person -|-> Person composed through co-occurrence; coauthorship is Person -|-> Paper composed with its opposite), external services via the identity map. "Piecemeal" is precisely non-commutativity: functors from different unsynchronized domains. "Pervasive" is one site, every surface a functor out of it, sync jobs as the natural transformations keeping the diagram commuting. No surface is authoritative; the site is.

### Write-back is a lens

Hand-edits on a compiled view ("actually she moved to Maryland") flow back as new observations through a delta lens: get = compile, put = translate the view edit into events, lens laws as the consistency spec.

### Fuzzy recall is enrichment

Embedding-based memory is the same category enriched over the Lawvere metric ([0,inf], >=, +): hom-objects become distances. "The tall Dutch guy who does qubits" is a query object; retrieval is proximity. Not a separate system: a change of enrichment on the one site. Recall improves whenever the embedding model does, over unchanged data.

### Time

The whole system is a functor from the poset of times: nothing is overwritten, because morphisms in time are not invertible.

## 3. The empirical tower

What counts as evidence of co-reference, and how confidence composes, are not design decisions. They are empirical, answered one level up, and the observation stream supplies its own ground truth.

- Every identification is eventually tested by the future: coherence (same email keeps co-occurring, consistent timeline, explicit confirmation) or clash (two cities at once, contradictory affiliations, a correction). **Confirmations and retractions of witnesses are first-class data** (2-morphisms; the level-2 ledger).
- **Confidence per evidence type is calibrated, not assigned**: email match, name+context match, LLM judgment, spousal testimony each accrue a measured precision. Evidence strength is context-dependent and learnable (a name match on "Chandralekha Singh" is strong; on "Wei Zhang" it is weak, and per-name collision rates are learnable from the corpus).
- **The composition law for confidence along zigzags is fit, not decreed**: which monoidal structure ([0,1] with product, min, Lukasiewicz, ...) matches the observed failure rate of multi-hop identifications is an empirical parameter.
- **Everything is retractable by default**, because retractions are the training data.
- **Witnesses keep their raw signals**, so an improved resolver re-runs over the past and the entire history of the social world improves from unchanged observations. This, not storage capacity, is the precise sense in which the brain beats human memory: a resolver whose calibration monotonically improves.
- **No level is architecturally privileged.** The resolver's rules, the calibration procedure, the procedure for revising the calibration procedure: all live in the same ledger as ordinary objects. A rule is a document; a change to a rule is an event; a rule's performance is measured from outcomes exactly like a witness's reliability. "Level" is a column, not a tier of the software.
- **The tower is coinductive**: at any moment the system operates at a finite truncation, but the truncation level is state, not specification. Ascend a level when the current top level's residual errors are systematic rather than noise (the renormalization criterion). Whether the tower "truncates" is itself always a question one level up; the architecture's only obligation is never to foreclose the ascent. Corollary: the system's description of itself is inside the system, which is what makes it a brain rather than a database.

The only genuine free choices remaining: **seed priors** for evidence types at day zero (stored as priors, marked for replacement by measurement) and the **current truncation** (part of state).

## 4. The plan

Substrate note: because every surface is compiled and disposable, the storage choice is low-stakes and changeable. Default: SQLite or Postgres (Postgres MCP already connected) for the ledger; markdown for the compiled vault.

**Phase 0: the site.** One append-only store with the uniformity constraint (everything is an observation, including rules and rules-about-rules; level is a column). Tables:
- `observation(id, ts, source, kind, raw, extracted_mentions, location, meta)` : append-only
- `witness(id, ts, o1, o2, evidence_type, raw_signal, confidence, provenance, level)` : first-class, retractable
- `outcome(id, ts, witness_id, verdict{confirmed|retracted}, cause, provenance)` : the level-2 ledger
- Rules, calibration procedures, priors: rows in `observation` with kind = rule, level >= 2.

**Phase 1: ingestion functors.**
- Watch Loop Recorder -> observations (favor Jeremy's own post-hoc voice memos over verbatim capture of others; Pennsylvania is all-party consent for audio).
- Nightly harvester over the Claude archive (already semantically indexed) sweeping person-mentions from all sessions: this is what makes it pervasive on the write side with zero manual effort.
- Email / calendar adapters.
- Paperpile bib import: LevyPubs.bib and paperpile-clean.bib compile into thousands of coauthorship observations on day one.

**Phase 2: the compiler and the read surface.**
- pi_0 over witnesses -> person components; Kan extension (LLM compile) -> one markdown profile per person in a `People/` vault (frontmatter skeleton + prose richness + encounter log + [[wikilinks]]).
- Pervasiveness on the read side: a People skill/MCP available in every session plus a global CLAUDE.md rule (consult on any person mention; contribute after any session where person information surfaced).

**Phase 3: lenses and enrichment.**
- Write-back lens: edits on a profile become observations/witness-retractions on the site.
- Embedding index over observations (reuse the Voyage machinery from claude-archive) for fuzzy recall.

**Phase 4: the calibration loop.**
- Outcomes accumulate; per-evidence-type reliability measured; composition law fit; resolver recalibrated; full re-resolution recompiles history. Watch for systematic residuals as the signal to ascend a level.

**Deferred until the data speaks:** graph-native query layer (Kuzu or edge tables) for multi-hop mining; multi-user (Chandralekha as contributor changes storage and privacy posture); scope (200 close people vs 5000 total); external-surface sync (Asana, Google Contacts) as outbound natural transformations.

**Standing cautions:** this is a database about third parties: keep it local (Dropbox), be deliberate about recordings and consent, and treat exports to any external service as publication.

## 5. Beyond people: the CDB as universal substrate (added 2026-07-04)

People were the first external dataset. The person machinery (observation streams, identity witnesses, compiled profiles, calibrated trust) is the general machinery for ALL information, because "nobody observes a person" generalizes to "nobody observes an external system."

**Identifiers.** Identity is a rigid designator (o.i, Asana gid, DOI, git sha), minted at spawn, immutable while state evolves. Names are witnesses attached to IDs, never identities. Control x mutability taxonomy:
- controlled + immutable: content-addressed (sha256 is the ID)
- controlled + mutable: ordinary CDB object (o.i + append-only relations)
- external + immutable: boundary ref {kind:'ref', scheme:'doi'|'arxiv'|'orcid'|'asana-gid'|..., id:...}. Referential integrity, NOT epistemic warrant: immutability is not truth.
- external + mutable: snapshot-on-observation (dated, hashed). You cannot control the object; you fully control your observations of it.

The boundary of control IS the boundary between objects and observations. The CDB never contains the external world, only its own observations of it. Boundary refs are dereferenced lazily (metadata/content ingested as observations on first query, then memoized). Cross-scheme identity = same witnesses.

**Trust.** Internal: the calibration loop, plus staleness decay c(t) = c0 * decay(fact_type, age) with decay curves FIT from the corpus (the email archive measures the empirical half-life of an address, an affiliation, a phone number).
External: a source is an instrument; estimate its transfer function, not its truth. Sources are evidence-types writ large:
- calibrate on overlap (external claims that collide with our own data produce outcome rows attributed to the source)
- replication = witness between claim objects; failed replication = retraction outcome
- trust composes along provenance with the same empirically-fit composition law; queries return (value, confidence, provenance)
- structural priors (venue, retraction history, N) seed and are replaced by measurement.

**Mental models of external datasets** = compiled profiles of sources, produced by the same Kan-extension compiler as person profiles: coverage, schema-as-observed, quirks, known systematics, calibration record. Profiles make foreign data computable: queries consult the model to interpret the source. (CDA paper precedent: instruments as observers.)

**Concrete next steps on this axis:** Asana ingest (tasks as boundary refs with gid; assignee/collaborator edges join people to work), Paperpile seed (DOI boundary refs + coauthorship edges in one import), fact-half-life measurement from the archive.
