# Gameplay Flow Semantic Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent structure evidence, presentation copy and numeric facts from becoming gameplay flow, and apply one isolated quality contract to every project.

**Architecture:** Add a focused backend semantic router that owns rule responsibility and FlowChain validation. The model builder, detail quality report and P4 renderer consume the same routed fields; structure and detail quality are stored separately. Project fixtures exercise the shared implementation without project-name branches.

**Tech Stack:** Python 3.11, JavaScript, Node test runner, pytest, existing Gameplay Review Model.

## Global Constraints

- All projects use the same validators and gates; no project-name conditionals.
- Cache and model recovery remain isolated by job identity, evidence revision and approved model revision.
- Approved rule text, values, triggers and authority are never rewritten.
- Pure presentation and numeric chapters may have no gameplay flow.
- P4–P7 remain closed while detail generation or detail semantic quality is incomplete.
- Do not modify `scripts/publish_current_alignment_to_feishu.py`.
- Do not push GitHub, SVN or deployment artifacts during implementation.

---

### Task 1: Shared rule responsibility router and FlowChain validator

**Files:**
- Create: `backend/gameplay_flow_semantics.py`
- Create: `tests/test_gameplay_flow_semantics.py`
- Create: `tests/fixtures/gameplay-flow-semantic-cases-v1.json`

**Interfaces:**
- Produces: `route_structured_rules(rules: list[dict]) -> dict[str, list[str]]`
- Produces: `flow_chain_report(chapter: dict) -> dict`
- Output slots: `normalFlow`, `keyRules`, `presentationRules`, `numericRules`, `configurationRules`.

- [ ] Write failing tests proving presentation/numeric/config rules never enter `normalFlow`, a static-only flow fails, a causal flow passes, and pure presentation chapters pass with an empty flow.
- [ ] Run `python -m pytest -q tests/test_gameplay_flow_semantics.py` and confirm failures are caused by the missing module.
- [ ] Implement deterministic routing from `ruleType`; classify FlowChain roles from structured metadata and behavior without changing source text.
- [ ] Run the targeted test and confirm all cases pass.

### Task 2: Model projection and separate quality truth sources

**Files:**
- Modify: `backend/gameplay_review_model.py`
- Modify: `backend/gameplay_generation_quality.py`
- Modify: `tests/test_gameplay_generation_quality.py`
- Modify: `tests/test_gameplay_review_model.py`

**Interfaces:**
- Consumes: `route_structured_rules`, `flow_chain_report`.
- Produces: `model.structureQuality`, `model.detailQuality`; keeps `generationQuality` only as a compatibility mirror.

- [ ] Write failing tests proving `_sync_structured_review_cache` routes each rule type to its correct slot and preserves original behavior text.
- [ ] Write failing tests proving detail quality rejects a declared static-only flow, accepts a causal flow, and does not require flow from a presentation-only chapter.
- [ ] Write failing tests proving structure and detail quality survive as separate fields after both phase checks.
- [ ] Run the targeted tests and confirm the expected failures.
- [ ] Replace the unconditional `visible → normalFlow` projection with the shared router.
- [ ] Add FlowChain errors to detail quality and write phase reports into separate fields.
- [ ] Run the targeted tests and confirm they pass.

### Task 3: P4 rendering and navigation gates

**Files:**
- Modify: `js/gameplay-review.js`
- Modify: `js/backend.js`
- Modify: `tests/js/gameplay-review.test.js`
- Modify: `tests/js/screenshot-backend.test.js`

**Interfaces:**
- Consumes: routed planner-section fields and `detailQuality.passed`.
- Produces: P4 sections that distinguish gameplay flow, key rules, presentation rules and parameters.

- [ ] Write failing browser-DOM tests proving static/numeric copy is absent from “玩法流程” and rendered in its owned section.
- [ ] Write failing navigation tests proving `detailQuality.passed=false` routes P4–P7 back to P1 while legacy models without the new field retain compatible behavior.
- [ ] Run the two JS test files and confirm the failures.
- [ ] Render only routed `normalFlow` as gameplay flow; add a presentation-rule section without creating empty headings.
- [ ] Extend `gameplayModelReviewReady` to reject explicit failed detail quality.
- [ ] Run the targeted JS tests and confirm they pass.

### Task 4: Cross-project isolation matrix and System Lesson

**Files:**
- Modify: `tests/fixtures/gameplay-flow-semantic-cases-v1.json`
- Modify: `tests/test_gameplay_flow_semantics.py`
- Modify: `tests/test_gameplay_generation_quality.py`
- Modify: `tests/js/gameplay-review.test.js`
- Modify: `data/planner_knowledge/system-lessons-v1.json`
- Modify: `tests/test_system_lesson_registry.py`
- Modify: `tests/test_system_lesson_traceability.py`

**Interfaces:**
- Fixtures: `yilu`, `grocery`, `character_creation`, `new_project` all call the same public validator.
- Lesson policy: `gameplay.flow_semantic_ownership_and_isolation`.

- [ ] Add the four fixtures and an identity-swap case that changes job/evidence/approved revision while retaining similar screenshots.
- [ ] Verify no fixture relies on a project-name branch and no generated/cache payload crosses identities.
- [ ] Add a System Lesson stating that evidence modality and rule type determine ownership, while task identity determines data isolation.
- [ ] Run targeted Python and JS suites.
- [ ] Run all JS tests and full pytest.
- [ ] Execute local browser screenshot acceptance for P1 blocking and P4 routed content.
- [ ] Commit only production code, tests, fixtures, lesson and docs; keep deployment and push paused.
