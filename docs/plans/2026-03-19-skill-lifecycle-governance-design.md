# Skill Lifecycle And Governance Design

## Summary

Synthesis needs to support two truths at the same time:

1. it is a self-extension engine, so agents must be able to generate and use low-maturity draft skills
2. it is building a canonical public corpus, so the registry must stay narrow, highly curated, and resistant to duplicate or mediocre skills

The way to reconcile those truths is to separate:

- **lifecycle stage**: where a skill sits in the publication and curation flow
- **trust level**: how much operational confidence Synthesis places in that skill

Draft creation should be permissive. Promotion should be strict.

## Goals

- allow agents to self-extend quickly through local draft skills
- keep the canonical registry small, sharp, and high-signal
- make duplicate handling explicit rather than ad hoc
- support improvement of existing skills without encouraging sibling sprawl
- incorporate the existing graduated trust model cleanly
- make `skill-miner` a candidate generator, not an auto-publisher

## Non-Goals

- building an open marketplace of all plausible skills
- allowing miner output to publish directly into the canonical set
- treating STSS or any LLM review as a replacement for human curation

## Two Axes: Stage vs Trust

Synthesis should model skill maturity on two independent axes.

### Lifecycle Stage

- `draft`: local or mined candidate, not yet submitted for curation
- `challenger`: proposed addition or replacement under review
- `canonical`: accepted skill for a capability family
- `deprecated`: retained only for redirection, provenance, or migration

### Trust Level

- `UNTRUSTED`: new local draft or unproven mined output
- `PROBATION`: submitted challenger or limited-distribution candidate
- `TRUSTED`: merged canonical skill with curator approval
- `VERIFIED`: elevated canonical skill with stronger long-run evidence

This separation matters. A skill can be `canonical + trusted` without being `verified`. A skill can be `challenger + probation` without being low-quality in principle. A local draft can be useful while still remaining `draft + untrusted`.

## Canonicality Policy

The registry should optimize for quality and clarity, not breadth.

### Rule

Each **capability family** gets one primary canonical skill.

Examples of capability families:

- systematic debugging
- test-driven development
- repo surveying
- writing clearly and concisely

### Implications

- most new submissions should improve an existing family rather than create a new canonical sibling
- duplicates should be rejected by default
- variants should be rare and accepted only when the difference is structural

### Allowed Reasons For A Variant

- different host or runtime constraints
- meaningfully different tool surface
- materially different security model
- clearly distinct workflow that would confuse a unified skill

Minor wording differences, packaging differences, or slightly different emphasis are not enough.

## Submission Types

Every submitted skill should declare one of these intents:

- `new_family_candidate`
- `canonical_improvement_candidate`
- `variant_candidate`
- `supersedes_existing`

This should be required in PR metadata and eventually represented in the machine-readable submission schema.

## Recommended Lifecycle

### 1. Draft

Origin:

- synthesized from a live agent task
- mined from an external repository
- hand-authored locally

Properties:

- local-only by default
- visible to the originating agent or scope
- may overlap freely with other drafts
- trust level defaults to `UNTRUSTED`

Requirements:

- valid package shape
- provenance captured
- minimal evaluation scenarios

### 2. Challenger

Origin:

- a draft skill submitted for review
- a miner candidate opened as a PR
- a proposed revision to an existing canonical skill

Properties:

- explicitly mapped to a capability family
- compared against nearest canonical alternatives
- trust level defaults to `PROBATION`

Requirements:

- validation passes
- provenance is clear
- STSS scan passes
- overlap analysis is attached
- evidence is provided for why this should exist

### 3. Canonical

Origin:

- accepted by curator review

Properties:

- primary skill for its capability family
- trust level defaults to `TRUSTED`
- discoverable and preferred in the canonical registry

Requirements:

- clearly better than alternatives or fills a truly new family
- well-written trigger and instructions
- demonstrated cross-task value
- packaging and references are clean

### 4. Verified

Origin:

- explicit elevation after longer-run evidence

Properties:

- still canonical, but now treated as a stronger teaching asset
- trust level is `VERIFIED`

Requirements:

- repeated successful use across real tasks
- low ambiguity in triggering
- stable behavior under review
- optional stronger attestation or evaluation requirements

## Promotion Rules

### Draft -> Challenger

Allowed when:

- the skill solved a real problem
- the package is coherent
- provenance is captured
- there is enough evidence to compare it against the canon

### Challenger -> Canonical

Allowed only when one of these is true:

- it establishes a genuinely new capability family
- it is materially better than the existing canonical skill
- it should replace a weak or outdated canonical skill

### Canonical -> Verified

Allowed only when:

- long-run evidence supports it
- curators believe it is a stable exemplar worth preferential reuse

## Duplicate Management

Duplicate management should be a first-class part of the governance model.

### Duplicate Rule

Canonical duplicates should not exist.

### What Can Overlap

- local drafts
- temporary challengers during review

### What Should Not Overlap

- canonical skills within the same capability family

### Duplicate Decision Order

1. deterministic checks: name, trigger overlap, host scope, tool scope
2. embedding retrieval against registry skills
3. cross-encoder reranking of nearest neighbors
4. curator decision: new family, improvement, variant, or reject

The existing retrieval shape in `skill-miner` Stage 2 is a strong fit for this. Reuse the same bi-encoder and cross-encoder approach for skill-to-skill overlap analysis.

## Quality Gate

The canonical registry should use a layered gate.

### Gate Order

1. provenance and licensing
2. family classification and duplicate check
3. package validation
4. writing quality and trigger clarity
5. behavioral evidence
6. STSS scan and optional attestation verification
7. human curation

This order is deliberate. A perfectly scanned duplicate is still low-value.

## Evidence Standard

A candidate should have to answer:

- what exact trigger or problem does this skill solve
- what existing skill is closest
- why this is better or different
- what evidence shows that another agent would benefit from this skill

If those answers are weak, the skill should not land in the canon.

## How Skill Miner Fits

`skill-miner` should be treated as a scout.

It should not behave like a publisher. Its outputs should be candidate classifications, not assumed merges.

### Desired Miner Output

- `new_family_candidate`
- `canonical_improvement_candidate`
- `variant_candidate`
- `reject_as_duplicate`

### Desired Miner Behavior

- bias toward improvement of existing canon before proposing new families
- attach nearest-neighbor comparisons
- provide extraction evidence, not just generated text
- expect human review for final promotion

## LLM Assistance

LLMs are useful here, but only as reviewer assistants.

Good uses:

- draft family classification
- duplicate suspicion
- comparison summaries against existing canon
- writing quality critique
- trigger clarity critique

Bad uses:

- direct merge decisions
- replacing curator judgment
- being the sole arbiter of whether a skill is canonical

## Operational Principle

All agents may draft.
Very few skills may graduate.

That is the core reconciliation between self-extension and curation quality.

## Recommended Next Steps

1. Add `lifecycle_stage` as a first-class field alongside `trust_level`
2. Add `capability_family` and `submission_type` to registry metadata
3. Create a challenger workflow in the registry rather than treating all submissions as equal
4. Reuse `skill-miner` retrieval for duplicate and family analysis
5. Define the canonical reviewer rubric and PR template around this lifecycle
