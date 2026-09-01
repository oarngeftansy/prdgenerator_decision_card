# Phase 5 EntityBuilder Implementation Plan

> Scope stop: do not enter ParameterResolver or Phase 5.1.

## Task 1: Lock contracts with failing tests

- Add tests for the seven EntityType values and stable Entity serialization.
- Add tests proving directory headings do not automatically become entities.
- Add tests for primary/reference chapter ownership and explicit owner/parent-child relations.
- Add tests for source/target edges backed by approved non-presentation Rules.
- Add tests proving Presentation Rules only receive `relatedEntityIds[]` and never create graph nodes or edges.
- Add input immutability tests.

## Task 2: Implement EntityBuilder

- Add Entity and relationship models.
- Implement declaration normalization and alias resolution.
- Link approved non-presentation Rules and reviewed Gaps.
- Resolve primary definition and reference chapters.
- Build only evidence-backed core relations.
- Attach Presentation Rule references after graph construction.
- Produce a deterministic pollution audit.

## Task 3: Generate the Phase 5 reference audit

- Read the existing Phase 3 structured result without changing it.
- Project the already accepted in-memory approval state used by Phase 4.x.
- Build the ten requested reference entities and graph.
- Generate JSON and human-readable graph artifacts.
- Record source and output hashes, including unchanged `job.json`.

## Task 4: Verify and stop

- Run focused EntityBuilder tests.
- Run Phase 2–4.3 regression tests.
- Verify no changes to Rules, Gaps, six-chapter reference document, P7 export, or source job.
- Commit only Phase 5 files and report graph/audit results.

