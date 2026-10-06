# Yoneda — design FAQ

A living set of design questions and their answers: the conceptual ones about
*why the substrate is shaped the way it is* and how it relates to ideas and
standards outside the project. This is not a how-to (see `README.md`,
`stem-cell/BOOT.md`) — it is the place where "how does this relate to X?" and
"why not Y?" get written down once, with the reasoning, so the argument is
recorded rather than re-derived each time.

Add a new question as an `## H2` heading, newest at the top.

---

## How does Yoneda relate to W3C PROV?

Short answer: **Yoneda's `o`/`r` *is* a provenance graph, and PROV is essentially
one vocabulary you can differentiate the stem cell into.** Yoneda then extends
provenance in four ways PROV does not natively cover, and conversely PROV offers
an interchange standard Yoneda lacks. (The PROV data model:
<https://www.w3.org/TR/prov-overview/>.)

### The structural correspondence

PROV is nodes (Entity / Activity / Agent) plus typed directed edges (`used`,
`wasGeneratedBy`, …) with attributes and time. That is exactly Yoneda's shape:
`o` is the node, an `r` row is the typed directed edge (`o1 → o2`, `d->>'type'`,
at time `t`).

| PROV | Yoneda encoding |
|---|---|
| Entity / Activity / Agent | an object `o` with `j.kind = 'entity' / 'activity' / 'agent'` |
| `used`, `wasGeneratedBy`, `wasAttributedTo`, `wasDerivedFrom`, `wasAssociatedWith`, `actedOnBehalfOf` | an `r` row with `d.type` set to that name |
| `wasInvalidatedBy` | `retract()` — an outcome row; `r_active` then hides the target |
| `specializationOf` / `alternateOf` (same thing, different aspect) | a `same` witness; the entity is `component()` over them |
| `hadMember` (collections) | ordinary `r` rows |
| bundle (a named provenance set) | a branch `b`, or an object the rows point at |
| qualified relation (role/time on an edge) | fields inside `d` |

So **PROV ⊆ what Yoneda expresses.** The instrument lineage already emits
provenance without calling it that: `email —from→ contact` is `wasAttributedTo`;
`blob —measured→ sample` is `used` / `wasGeneratedBy`; an agent asserting a
`same` link is `alternateOf`.

### Where Yoneda goes beyond PROV

PROV is categorical — an edge holds or it does not, and assertions are given, not
weighed. The substrate adds four things PROV has no native slot for:

1. **Confidence and consensus.** `r.c` and the `consensus` view
   (`sum(v·c)/sum(c)`) make provenance *probabilistic and fitted*. PROV cannot say
   "this derivation holds with confidence 0.7" or compute weighted truth over
   competing claims.
2. **Never delete; retraction as event.** PROV's `wasInvalidatedBy` removes a
   thing from play. Yoneda keeps the retracted witness forever — "preserved
   disagreement *is* the training corpus" (`divergence-is-data-v1`). Provenance
   becomes calibration data, not merely record.
3. **Branches — concurrent competing accounts.** `r.b` + `realize()` model
   divergent authors where no branch is privileged and none is discarded (Everett,
   not Copenhagen). PROV bundles can hold alternate accounts; Yoneda makes
   non-convergence structural.
4. **Entities computed, not stored.** A "person" is not an asserted node with
   `specializationOf` edges — it is the connected component over active `same`
   witnesses at a confidence threshold, assembled on demand. Identity is never
   description.

Two further reflexive properties: **rules are data** (the consensus law,
`boundary-ref-v1`, and the rest are rows, revisable by superseding rows — PROV-O
is a fixed external ontology), and **reification is uniform** (`r.i` gives every
witness an identity, so a claim can be the subject of another claim — PROV's
provenance-of-provenance taken to an unbounded tower).

### Where PROV helps Yoneda

PROV has the thing Yoneda lacks: a standard for interchange — PROV-O (RDF/OWL),
PROV-N, PROV-JSON, a constraints/validation spec, and tooling. The provenance-
typed subset of `r` maps onto PROV cleanly (`from` → `wasAttributedTo`, etc.),
carrying `c`, `b`, and retraction as PROV *attributes* on qualified relations —
lossy but valid, and instantly interoperable with any provenance-aware tool.

**This is a view, not a feature.** Because everything is witnesses, a PROV
rendering is a query/transform over `r` — producible on demand (by a person or by
the AI acting as a source that reads the graph and emits PROV), exactly like
`consensus` or `component`. It does not need to live in the codebase; it is
generated when it is actually needed.

### The name is not a coincidence

The Yoneda lemma says an object is determined, up to isomorphism, by the totality
of its relationships — its hom-functor. The substrate operationalizes exactly
that: an entity is nothing but its witnesses. PROV is a relations-first model of
the same intuition (a thing is known by its provenance edges); Yoneda generalizes
those edges to weighted, branched, retractable, and computed. PROV is the
standardized, categorical slice; Yoneda is the probabilistic, non-destructive,
self-describing generalization.
