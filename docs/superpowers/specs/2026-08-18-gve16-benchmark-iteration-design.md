# GVE16 Benchmark Iteration Design

## Goal

Raise the truthful 《一路狂飙》 gameplay-document benchmark from A–H 51.3 to at least 80 without adding a pipeline phase, taxonomy, fixed chapter schema, new project rule, or diagnostic override.

## Scope

The implementation changes only the existing mechanic structuring, gameplay rule-chain reconstruction, chapter assembly, and planning-language behavior. It covers seven benchmark chains: monster movement/attack; weapon acquisition/slot/attack/cooldown/attribution; battle level/three-choice/candidate/refresh/confirm/effect; independent weapon draw; normal stage/Boss/end; damage statistics; success/failure/settlement.

## Design

1. Mechanic structuring preserves existing approved dimensions and their provenance, but emits explicit ordering and relation hints only when those relations already exist in source contracts or rule chains.
2. Gameplay rule-chain reconstruction becomes the primary sequencing input for the final document. Missing links remain review or evidence items and never become rules.
3. Chapter assembly consumes dynamic owner paths and chain blocks. Rule groups remain internal organization; presentation grouping cannot create owners.
4. Parameters and review gaps are attached to the chain step they qualify. They do not become extra gameplay steps.
5. Planning language renders confirmed rules, parameters, and pending decisions distinctly while preserving traceability and suppressing common-sense filler.

## Benchmark and guardrails

Every iteration regenerates the complete `human-planning-preview.md`, scores A–J, and records paragraph-level differences. A–H is the arithmetic mean of the eight execution dimensions. I and J remain guardrails. Unsupported invention, duplicate full definitions, common-sense filler, and publication-lost rules must remain zero or near zero.

Iteration 1 stops for root-cause reassessment if A–H improves by less than 10 points. If it improves by at least 10 points, iteration 2 targets the three remaining lowest dimensions without expanding scope.

## Baseline

- Git: `f929c0b`; safe implementation baseline: `b5589ed`.
- Truthful preview SHA-256: `71F44D14368C44748366E18E7786ADD44EC225D6962EC467C685465A39645B24`.
- A–J: 42, 71, 44, 86, 43, 31, 54, 39, 94, 97.
- A–H: 51.3.

