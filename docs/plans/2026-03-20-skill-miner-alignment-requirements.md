# Skill Miner Alignment Requirements

> **Context:** This document is for the separate `skill-miner` implementation session. It defines what `skill-miner` must produce for Synthesis. It does not require implementation work in this repository.

## Purpose

Align `skill-miner` with the Synthesis governance model.

`skill-miner` should not behave like a publisher of new canonical skills. It should behave like a scout that produces high-quality challenger candidates, family classifications, duplicate analysis, and evidence for curator review.

This document defines the minimum requirements for that alignment.

## Outcome

`skill-miner` should become a candidate-generation and review-support system for Synthesis.

It should:

- surface high-signal skill candidates
- compare them against the current canon
- reject or downgrade likely duplicates
- emit challenger-ready packages and review artifacts when a candidate is worth human attention

It should not:

- publish directly into the canonical registry
- treat mined output as canonical by default
- optimize for ingestion volume over curator quality

## Background

Synthesis now has:

- a canonical registry with one primary skill per capability family
- lifecycle stages: `draft`, `challenger`, `canonical`, `deprecated`
- trust levels: `untrusted`, `probation`, `trusted`, `verified`
- challenger workflow rules in `synthesis-skills`
- family-level duplicate constraints in the registry

That means `skill-miner` must stop thinking in terms of:

- "I found a skill, publish it"

and start thinking in terms of:

- "I found a candidate; how does it relate to the current canon?"

## Governance Mapping

`skill-miner` output must map cleanly onto the Synthesis lifecycle and trust model.

Expected mapping:

- mined local candidate: `draft + untrusted`
- emitted submission package: `challenger + probation`
- accepted registry skill: handled by registry curation, not by `skill-miner`

Implication:

- `skill-miner` may recommend promotion into challenger status
- `skill-miner` must never assign canonical or verified status

## Core Product Requirement

For every mined candidate, `skill-miner` must produce a governance-aware recommendation:

- `new_family_candidate`
- `canonical_improvement_candidate`
- `variant_candidate`
- `reject_as_duplicate`

The default bias should be toward:

- `canonical_improvement_candidate`

not toward minting new families.

## Non-Goals

- auto-merging skills into the canonical registry
- replacing curator judgment with an LLM
- creating an open marketplace of overlapping skills
- treating extraction quality alone as sufficient for publication

## Functional Requirements

### 1. Registry-Aware Input

`skill-miner` must be able to load the current canonical registry as reference context.

Minimum required inputs from the registry:

- skill name
- description
- keywords
- capability family
- lifecycle stage
- trust level
- provenance summary

Preferred input source:

- `catalog/skills.json` from `synthesis-skills`

Nice-to-have:

- ability to distinguish current primary canon from non-primary variants and challengers if the catalog contains them

### 2. Capability Family Classification

For every mined candidate, `skill-miner` must assign a proposed `capability_family`.

Rules:

- if the candidate clearly matches an existing canonical family, reuse that family
- if it does not match an existing family strongly enough, propose a new family
- family names must be lowercase kebab-case

Output must include:

- `capability_family`
- confidence or rationale

Quality bar:

- family assignment should prefer an existing family unless the evidence for a new family is strong
- a weakly justified new family is worse than a conservative improvement recommendation

### 3. Duplicate And Nearest-Neighbor Analysis

For every mined candidate, `skill-miner` must identify nearest existing skills.

Minimum required output:

- top nearest canonical skill
- top 3 nearest neighbors overall
- similarity scores
- recommended disposition

Recommended method:

1. deterministic checks
   - name overlap
   - trigger overlap
   - host/tool overlap
2. embedding retrieval
3. cross-encoder reranking
4. LLM summary only as an assistant layer

Required decision question:

- "Should this candidate compete with an existing canonical skill, exist as a true variant, or be rejected as overlap?"

### 4. Submission Type Classification

For every mined candidate, `skill-miner` must emit exactly one of:

- `new_family_candidate`
- `canonical_improvement_candidate`
- `variant_candidate`
- `reject_as_duplicate`

Rules:

- if the candidate is materially the same as an existing canonical skill and not clearly better, classify as `reject_as_duplicate`
- if it improves the same family, classify as `canonical_improvement_candidate`
- if it differs structurally by host, tool surface, security model, or clearly distinct workflow, classify as `variant_candidate`
- only use `new_family_candidate` when no strong existing family match exists

Default bias:

- prefer `canonical_improvement_candidate`
- use `new_family_candidate` sparingly
- use `variant_candidate` only with an explicit structural reason

### 5. Challenger Evidence

Every non-rejected candidate must include evidence sufficient for challenger review.

Required evidence fields:

- `evidence_summary`
- `why_not_duplicate`
- `why_better_or_different`
- `nearest_canonical`
- `source_repository`
- `source_paths`

Preferred additional evidence:

- extraction criteria results
- usage examples or task examples
- verification or test signals
- notes on non-obviousness and generalizability

Reviewer standard:

- a human curator should be able to read the evidence and understand why the candidate deserves review in under two minutes

### 6. Registry-Compatible Output Package

For candidates that are not rejected, `skill-miner` should be able to emit a Synthesis-compatible candidate package.

Required files:

- `SKILL.md`
- `PROVENANCE.json`
- `REGISTRY.json`

Optional files:

- `scripts/`
- `references/`
- `assets/`
- `agents/`

`REGISTRY.json` must be challenger-aware.

Minimum expected values for miner output:

- `lifecycle_stage: "challenger"`
- `trust_level: "probation"`
- `is_primary: false`
- `submission_type: <classified value>`
- `capability_family: <classified family>`
- `nearest_canonical: <if applicable>`
- `evidence_summary: <required>`

If the disposition is `reject_as_duplicate`, `skill-miner` may skip writing the package and instead emit a review artifact only.

`PROVENANCE.json` must preserve source truth.

Minimum provenance expectations:

- upstream repository or origin
- license status
- extraction mode such as `first_party`, `mirrored_external`, or `adapted_external`
- source paths or source files used

### 7. Review Artifact

In addition to package output, `skill-miner` should emit a reviewer-facing summary artifact.

Suggested file:

- `MINER_REPORT.md`

Required sections:

- mined capability summary
- proposed capability family
- nearest canonical skill
- submission type
- why this should exist
- why this is not a duplicate
- provenance and license notes
- extraction evidence
- risks or open questions

Preferred additions:

- variant justification, if applicable
- curator recommendation
- confidence notes for family classification

## Quality Requirements

### 1. Precision Over Recall

The miner must optimize for precision, not coverage.

Preferred failure mode:

- reject or downgrade a plausible skill

Avoided failure mode:

- flood the registry with overlapping mediocre candidates

### 2. Canon Preservation

The miner must treat the canonical registry as scarce editorial surface.

Implication:

- candidate generation is easy
- challenger recommendation is harder
- new-family recommendation is rare

### 2a. Editorial Standard

The registry should behave more like an editorial canon than a marketplace.

Implication:

- being plausible is not enough
- being useful once is not enough
- a candidate should usually have to beat or sharpen the current canon

### 3. No Canonical Claims

`skill-miner` must never declare something canonical by itself.

It may only recommend:

- challenger
- variant
- new family candidate
- duplicate rejection

### 4. Explainability

Every classification should be explainable to a human reviewer.

At minimum, the miner should be able to answer:

- what problem this skill solves
- what the closest current canonical skill is
- why this is meaningfully different or better
- why this belongs in the registry at all

## LLM Requirements

LLM usage is allowed, but only as a supporting layer.

Good uses:

- candidate family classification
- tie-break reasoning between close neighbors
- writing quality critique
- generating reviewer summaries

Bad uses:

- deciding publication on its own
- serving as the only duplicate detector
- overriding deterministic or retrieval-based evidence silently

If an OpenRouter-backed model is used, it should be:

- optional
- advisory
- failure-tolerant

The miner must still produce usable results if the LLM layer is unavailable.

Recommended role for LLM assistance:

- PR or report commentary
- tie-break critique
- writing and trigger-quality review

Not recommended as:

- a hard merge gate
- the sole duplicate detector
- the sole arbiter of family creation

## Suggested Output Schema

Minimum candidate object:

```json
{
  "name": "systematic-debugging-next",
  "description": "Use when ...",
  "capability_family": "systematic-debugging",
  "submission_type": "canonical_improvement_candidate",
  "nearest_canonical": "systematic-debugging",
  "top_neighbors": [
    {"name": "systematic-debugging", "score": 0.93},
    {"name": "verification-before-completion", "score": 0.68}
  ],
  "why_not_duplicate": "...",
  "why_better_or_different": "...",
  "evidence_summary": "...",
  "source_repository": "https://github.com/owner/repo",
  "source_paths": ["src/foo.py", "README.md"],
  "write_package": true
}
```

## Acceptance Criteria

Milestone complete when:

1. `skill-miner` can ingest the registry catalog as reference context
2. every mined candidate gets a `capability_family`
3. every mined candidate gets one required disposition
4. duplicate candidates are rejected by default
5. non-rejected candidates emit registry-compatible `REGISTRY.json`
6. non-rejected candidates emit reviewer-facing evidence
7. the pipeline can run without an LLM, with reduced quality but valid outputs
8. emitted challenger packages never claim `canonical`, `trusted`, or `verified`
9. emitted artifacts make provenance and duplicate reasoning explicit

## Recommended Implementation Order

1. load canonical catalog into `skill-miner`
2. add nearest-neighbor retrieval against registry skills
3. add family classification and submission type classification
4. add challenger evidence fields
5. emit `REGISTRY.json`
6. emit `MINER_REPORT.md`
7. optionally add LLM-assisted review summaries

## Explicit Non-Requirements

The first `skill-miner` alignment milestone does not need to:

- auto-open GitHub PRs
- auto-sign candidates
- auto-promote skills beyond challenger
- replace registry-side validation, STSS gates, or human review
- solve long-run quality scoring perfectly

## Handoff Note

If tradeoffs are needed, preserve these in order:

1. duplicate rejection quality
2. family classification quality
3. evidence quality
4. package generation quality
5. LLM-assisted polish

If there is tension between throughput and quality, choose quality.

The miner is useful only if it protects the canon while surfacing genuinely strong candidates.
