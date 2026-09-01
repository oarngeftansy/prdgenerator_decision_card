# Mechanic Execution Depth Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a review-only seven-Mechanic execution-depth benchmark with precise current/conservative/design coverage and anti-inflation gates.

**Architecture:** Add one focused backend module that evaluates benchmark depth profiles against structured Existing/Approved Rules and proposals. Add one generator that loads current artifacts and emits five audit/review artifacts without mutating upstream data or Final Publication. Tests exercise public evaluator and generator seams with independent literals.

**Tech Stack:** Python 3.11+, pytest, JSON/Markdown artifacts.

## Global Constraints

- Do not add a Pipeline phase, Requirement closure status, fixed chapter schema, or Approved Rule.
- GVE16 and planner knowledge have `contentAuthority=none`.
- Do not modify Planning Hierarchy, Final Publication, `job.json`, Evidence, Fact, Rule, Requirement status, or Approved Data.
- Production code must not read benchmark Gold fixtures.
- Depth Coverage requires semantic responsibility matching; Presentation/UI rules cannot satisfy Logic dimensions.
- Repeat/periodic behavior activates only from a current-project existence signal.
- Report Current, Projected Conservative, Projected Design, and compatibility alias Projected Coverage.
- `depthReady=false` if unresolved Core, human decision, failed Compatibility/Coherence, or unroutable active dimensions remain.

---

### Task 1: Depth contracts, applicability, and coverage gates

**Files:**
- Create: `backend/mechanic_execution_depth.py`
- Test: `tests/test_mechanic_execution_depth.py`

**Interfaces:**
- Produces: `evaluate_depth_profile(profile: dict, rules: list[dict], proposals: list[dict]) -> dict`
- Produces: `evaluate_depth_benchmark(profiles: list[dict], rules: list[dict], proposals: list[dict]) -> dict`

- [ ] **Step 1: Write the failing semantic-responsibility test**

```python
def test_logic_dimension_rejects_presentation_rule_and_accepts_matching_approved_rule():
    profile = fixture_profile("statistics.attribution", required_semantics=["statistics_attribution"])
    presentation = {"ruleId": "P", "ruleType": "presentation", "semanticResponsibilities": ["statistics_attribution"]}
    approved = {"ruleId": "R", "valid": True, "ruleStatus": "approved_review", "semanticResponsibilities": ["statistics_attribution"]}
    assert evaluate_depth_profile(profile, [presentation], [])["currentCoverage"] == 0
    assert evaluate_depth_profile(profile, [approved], [])["currentCoverage"] == 100
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest tests/test_mechanic_execution_depth.py -q`
Expected: FAIL because the module/interface does not exist.

- [ ] **Step 3: Implement the minimal evaluator**

Implement stable-dimension validation, Core/Conditional/Optional activation, parent existence gating, semantic responsibility matching, and Satisfaction Contract facet checks. Accept only valid statuses `existing_valid`, `approved_review`, and `evidence_derived_valid` for current coverage.

- [ ] **Step 4: Add and pass vertical tests for Granularity and projection tiers**

Tests must independently assert: synonymous duplicate dimensions are rejected; parameter facets do not inflate the denominator; a Conservative Proposal affects only conservative/design coverage; Design Inference affects only design coverage; a failed proposal affects neither; and `depthReady` remains false at projected 100% when a human decision exists.

- [ ] **Step 5: Run Task 1 tests**

Run: `python -m pytest tests/test_mechanic_execution_depth.py -q`
Expected: all Task 1 tests PASS.

### Task 2: Seven benchmark profiles and routing

**Files:**
- Create: `scripts/generate_mechanic_execution_depth_benchmark.py`
- Create: `tests/fixtures/benchmark_execution_depth_profiles_v1.json`
- Test: `tests/test_current_mechanic_execution_depth.py`

**Interfaces:**
- Consumes: `evaluate_depth_benchmark(...)`
- Produces: `build_benchmark_inputs(root: Path) -> tuple[list[dict], list[dict], list[dict]]`
- Produces: `main() -> None`

- [ ] **Step 1: Write a failing benchmark-profile test**

Assert exactly seven Mechanic profiles; every dimension has a stable ID, family, role, execution question, applicability signals, and Satisfaction Contract; no profile stores a project answer; Repeat is conditional and dormant without a Repeat signal.

- [ ] **Step 2: Run the benchmark test and verify RED**

Run: `python -m pytest tests/test_current_mechanic_execution_depth.py -q`
Expected: FAIL because the fixture/generator does not exist.

- [ ] **Step 3: Implement the seven profiles and deterministic input adapters**

Use current structured Mechanic synthesis, Approved Rules, existing valid Rule artifacts, Evidence/Requirement references, and AI Proposal artifacts. Map source semantics explicitly; do not use text similarity, embeddings, LLM guessing, or test Gold.

- [ ] **Step 4: Implement completion routing and proposal quality fields**

Each active missing dimension must resolve to exactly one of `evidence_probe`, `conservative_proposal`, `design_inference`, `alternative_design`, `parameter`, or `human_decision`. Proposed executable text must pass Information Gain, Compatibility, and Coherence gates; low-information filler remains missing and lowers projected coverage.

- [ ] **Step 5: Run Task 1 and Task 2 tests**

Run: `python -m pytest tests/test_mechanic_execution_depth.py tests/test_current_mechanic_execution_depth.py -q`
Expected: all tests PASS.

### Task 3: Review artifacts and frozen-output integrity

**Files:**
- Modify: `scripts/generate_mechanic_execution_depth_benchmark.py`
- Test: `tests/test_current_mechanic_execution_depth.py`
- Create: `artifacts/mechanic-execution-depth-2026-08-19/execution-depth-profiles.json`
- Create: `artifacts/mechanic-execution-depth-2026-08-19/execution-depth-coverage.json`
- Create: `artifacts/mechanic-execution-depth-2026-08-19/execution-depth-expansion-preview.md`
- Create: `artifacts/mechanic-execution-depth-2026-08-19/execution-depth-lineage.json`
- Create: `artifacts/mechanic-execution-depth-2026-08-19/execution-depth-quality-gate.json`

**Interfaces:**
- Consumes: Task 2 benchmark evaluation.
- Produces: five deterministic Review/Audit artifacts.

- [ ] **Step 1: Write a failing end-to-end artifact test**

Hash `data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json`, Planning Hierarchy outputs, and `artifacts/mechanic-requirement-closure-publication-2026-08-18/human-planning-preview.md`; run the generator; assert all hashes are unchanged and all five outputs exist.

- [ ] **Step 2: Run the end-to-end test and verify RED**

Run: `python -m pytest tests/test_current_mechanic_execution_depth.py -q`
Expected: FAIL because outputs are absent.

- [ ] **Step 3: Implement deterministic JSON and Markdown rendering**

Preview each Mechanic with Structural Completeness, Current Coverage, Projected Conservative Coverage, Projected Design Coverage, applicable/covered/missing routes, AI-direct proposals, alternatives, parameters, human decisions, `depthReady`, and complete lineage. Engineering IDs remain in JSON, not headings.

- [ ] **Step 4: Run generator and focused regression**

Run: `python scripts/generate_mechanic_execution_depth_benchmark.py`

Run: `python -m pytest tests/test_mechanic_execution_depth.py tests/test_current_mechanic_execution_depth.py tests/test_mechanic_design_synthesis.py tests/test_mechanic_requirement_discovery.py -q`

Expected: all tests PASS; prohibited hashes unchanged.

- [ ] **Step 5: Report benchmark metrics**

Report each Mechanic's applicable, covered, AI-direct, Alternative, Parameter, Human Decision, Current Coverage, Conservative Coverage, Design Coverage, and `depthReady`, plus aggregate Granularity, Information Gain, Compatibility, Coherence, unsupported-requirement, and mutation gates.
