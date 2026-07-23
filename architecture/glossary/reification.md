---
type: glossary-term
slug: reification
updated: 2026-06-29
status: living
related:
  - "[[surrogate-key]]"
  - "[[open-world-ontology]]"
  - "[[graph-curation-surface]]"
---

# reification (reifikacja)

**Definition:** turning a **relationship into a thing** — promoting an edge (a plain `subject —predicate→
object` triple) into a first-class object that can itself carry properties, be pointed at, and be
qualified. "Reify" = "make into a thing" (Latin *res*). In a knowledge graph it is how you say something
*about a statement* rather than about an entity: not "Elara is on the Wave-Cutter" but "*the fact that*
Elara is on the Wave-Cutter was true only in chapter 3 / is rumoured, not certain / began at timestamp
T." Modality, temporal validity, n-ary arity, and provenance are all reification: each needs a place to
hang a qualifier *on the edge itself*.

**Answers:** "how do I record that a relationship is uncertain, time-bounded, or has more than two
participants — when an edge is just two endpoints and a label?"

**First encountered in:** [[graph-curation-surface]]

Why it matters *here* even though Story Forge is **not building it** (deferred, Graph-quality §5): the
milestone's §4 forward-compatibility call is precisely "don't make future reification *harder*." A
reifiable edge needs a **stable identity** to attach qualifiers to — which a content-addressed natural
key cannot give across curation (see [[surrogate-key]]). So the *only* reification-shaped decision in
scope now is whether to reserve that stable handle; the qualifiers themselves (the open-world set of
them — [[open-world-ontology]] applies to edge qualifiers just as it does to entity types) stay a later,
separate pass. The teachable line: **"design the constraint now, defer the feature"** — reserve the
hook reification will need, build none of reification.
