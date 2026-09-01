# GVE16 Benchmark Iteration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the truthful 《一路狂飙》 A–H benchmark from 51.3 to at least 80 by making existing rule chains drive dynamic chapter assembly.

**Architecture:** Existing approved rules and closure classifications remain authoritative. The existing rule-chain reconstruction output supplies ordering and relations to the existing mechanic structuring and chapter assembly layers; planning language renders confirmed rules, parameters, and review gaps in their natural chain positions.

**Tech Stack:** Python 3, pytest, existing JSON/Markdown artifact generators.

## Global Constraints

- Do not add a pipeline phase or taxonomy.
- Do not add fixed chapter schemas or titles.
- Do not generate new project rules or diagnostic overrides.
- Do not migrate GVE16-specific mechanics, fields, formulas, or values.
- Do not use document length, title count, or rule count as alignment proxies.
- Preserve unsupported invention, duplicate rule, common-sense, Logic/Presentation, and publication-integrity guardrails.

---

### Task 1: Chain-complete mechanic structuring

**Files:**
- Modify: `backend/mechanic_rule_structuring.py`
- Test: `tests/test_mechanic_rule_structuring.py`

**Interfaces:**
- Consumes: existing Rule Semantic Contracts and their source dimensions.
- Produces: existing hierarchy shape with grounded relation/order metadata; no new rules.

- [ ] Write failing tests for monster movement/contact, weapon acquisition-to-attack, and level-to-choice ordering with provenance.
- [ ] Run the focused tests and verify failures are caused by missing relation/order output.
- [ ] Implement the minimal generic relation preservation in `build_mechanic_rule_hierarchy`.
- [ ] Run focused and existing mechanic-structuring tests.

### Task 2: Seven benchmark rule chains

**Files:**
- Modify: `backend/gameplay_rule_chain_reconstruction.py`
- Test: `tests/test_gameplay_rule_chain_reconstruction.py`

**Interfaces:**
- Consumes: existing GameRuleGroups, MechanicModels, missing rules, and gameplay parameters.
- Produces: existing GameplayRuleChain records with grounded entry, processing, state change, result, exit, missing-link, and parameter attachments.

- [ ] Write one failing test per missing benchmark relation, grouped into the seven requested chains.
- [ ] Verify every new test fails for a missing or misplaced existing relation, not for absent project facts.
- [ ] Implement the smallest generic chain composition changes.
- [ ] Run focused tests and assert implementation-detail pollution remains zero.

### Task 3: Dynamic owner and chain-driven assembly

**Files:**
- Modify: `backend/gve16_chapter_assembly.py`
- Modify: `backend/gve16_native_planning_language.py`
- Test: `tests/test_gve16_chapter_assembly.py`
- Test: `tests/test_gve16_native_planning_language.py`

**Interfaces:**
- Consumes: existing carrier plans, dynamic owner paths, chain blocks, parameters, and review gaps.
- Produces: the existing chapter assembly result and Markdown preview.

- [ ] Write failing tests proving dynamic owner paths replace presentation grouping.
- [ ] Write failing tests proving parameters and review gaps attach beneath the relevant chain step.
- [ ] Write failing tests proving confirmed rules keep sequence/branch relationships in natural language.
- [ ] Implement minimal assembly and renderer changes without changing rule authority.
- [ ] Run focused tests and all existing language/assembly guardrails.

### Task 4: Regenerate and benchmark iteration 1

**Files:**
- Regenerate: existing Phase 6.2.5 through Phase 6.5 artifact directories.
- Create: `artifacts/gve16-benchmark-iteration-2026-08-18/iteration-1/benchmark-report.md`
- Create: `artifacts/gve16-benchmark-iteration-2026-08-18/iteration-1/human-planning-preview.md`

**Interfaces:**
- Consumes: existing generation scripts and truthful approved/review state.
- Produces: complete preview, A–J score, seven-chain comparison, paragraph diff, and guardrail report.

- [ ] Run the existing generators in dependency order.
- [ ] Run relevant Python regression tests.
- [ ] Score A–J using the approved rubric and record evidence for each score.
- [ ] If A–H gain is below 10, stop and reassess root cause; otherwise continue to Task 5.

### Task 5: Iteration 2 against the three lowest dimensions

**Files:**
- Modify only files already listed in Tasks 1–3.
- Add tests only to the corresponding existing test files.
- Create: `artifacts/gve16-benchmark-iteration-2026-08-18/iteration-2/benchmark-report.md`
- Create: `artifacts/gve16-benchmark-iteration-2026-08-18/iteration-2/human-planning-preview.md`

**Interfaces:**
- Consumes: iteration-1 score and root-cause evidence.
- Produces: a second complete truthful preview and score.

- [ ] Write failing tests for the three lowest remaining dimensions.
- [ ] Verify RED, implement minimal changes, and verify GREEN.
- [ ] Regenerate the complete preview and score A–J.
- [ ] Continue the same bounded loop until A–H is at least 80 or an allowed escalation condition is discovered.

### Task 6: Final verification

**Files:**
- Create: `artifacts/gve16-benchmark-iteration-2026-08-18/final-summary.md`

**Interfaces:**
- Consumes: baseline and all iteration reports.
- Produces: before/after scores, actual paragraph differences, code-to-score mapping, remaining root causes, and guardrail status.

- [ ] Run focused and relevant regression tests.
- [ ] Verify unsupported invention, duplicate full definitions, common-sense filler, and publication-lost counts.
- [ ] Verify Logic/Presentation cleanliness remains at least 90.
- [ ] Record the final truthful preview SHA-256 and remaining blockers.

