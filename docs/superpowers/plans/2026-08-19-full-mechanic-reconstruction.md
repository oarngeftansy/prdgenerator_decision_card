# Full Mechanic Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct the three focus mechanics as coherent, executable Review-Layer models and independently evaluate their Core Design Depth.

**Architecture:** Add a focused reconstruction module beside the existing depth evaluator. It consumes structured rules, evidence references, proposals, and mechanic-specific execution priors; it emits model-level design items, relations, parameter contracts, QA contracts, lineage, and gates without mutating upstream data. A separate benchmark generator builds the three current-case inputs and renders deterministic Review artifacts.

**Tech Stack:** Python 3.11+, pytest, JSON, Markdown.

## Global Constraints

- Remediation operates on complete Mechanic Models, never isolated Depth Dimensions.
- Only `MDES-CHOICE`, `MDES-WEAPON`, and `MDES-MONSTER` are reconstructed in this iteration.
- GVE16 Planner Knowledge is an execution-question prior with `contentAuthority=none`.
- Do not generate Approved Rules or mutate Requirement status, Evidence, Fact, Rule, Planning Hierarchy, Final Publication, or `job.json`.
- Projected Design Coverage is diagnostic and cannot stop reconstruction at 100%.
- Core Design Depth excludes QA, Presentation, placeholders, proposal/rule counts, document length, and auxiliary parameter facets.
- Conditional second- and third-order questions require a current-project existence signal.
- A proposed design item counts only after Information Gain, Compatibility, Coherence, Granularity, and Planner Relevance gates pass.
- No score gain may come from weaker Satisfaction Contracts, synonymous dimensions, duplicated generic rules, or one rule satisfying unrelated responsibilities.

---

### Task 1: Reconstruction contracts and Core Design Depth evaluator

**Files:**
- Create: `backend/full_mechanic_reconstruction.py`
- Test: `tests/test_full_mechanic_reconstruction.py`

**Interfaces:**
- Produces: `reconstruct_mechanic_model(reconstruction_input: dict) -> dict`
- Produces: `evaluate_core_design_depth(model: dict, contract: dict) -> dict`
- Produces: `validate_reconstruction(model: dict, contract: dict) -> dict`

- [ ] **Step 1: Write the failing public-seam test for core-depth exclusions**

```python
from backend.full_mechanic_reconstruction import evaluate_core_design_depth


def test_core_depth_excludes_qa_presentation_placeholder_and_auxiliary_parameter():
    contract = {
        "responsibilities": [
            {"id": "state", "weight": 1, "requiredSemantics": ["state_model"]},
            {"id": "repeat", "weight": 1, "requiredSemantics": ["repeat_model"]},
        ]
    }
    model = {
        "designItems": [
            {"id": "D1", "knowledgeClass": "design_inference", "gateStatus": "pass",
             "semanticResponsibilities": ["state_model"]},
            {"id": "D2", "knowledgeClass": "qa", "gateStatus": "pass",
             "semanticResponsibilities": ["repeat_model"]},
            {"id": "D3", "knowledgeClass": "placeholder", "gateStatus": "pass",
             "semanticResponsibilities": ["repeat_model"]},
        ]
    }
    result = evaluate_core_design_depth(model, contract)
    assert result["coveredResponsibilityIds"] == ["state"]
    assert result["coverage"] == 50.0
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'runtime_packages_pytest').Path
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_full_mechanic_reconstruction.py::test_core_depth_excludes_qa_presentation_placeholder_and_auxiliary_parameter -q
```

Expected: FAIL because `backend.full_mechanic_reconstruction` does not exist.

- [ ] **Step 3: Implement the minimal evaluator and validation result**

Implement literal semantic-responsibility matching. Count only `confirmed`, `conservative_proposal`, `design_inference`, and `recommended_alternative` items whose `gateStatus` is `pass`. Return:

```python
{
    "coverage": 50.0,
    "coveredResponsibilityIds": ["state"],
    "missingResponsibilityIds": ["repeat"],
    "failedResponsibilityIds": [],
}
```

`validate_reconstruction` must independently report lifecycle, branch, repeat, data-flow, rule-reuse, information-gain, compatibility, coherence, granularity, and planner-relevance gates.

- [ ] **Step 4: Add failing tests for anti-inflation and depth readiness**

Add tests asserting:

- the same item cannot satisfy unrelated responsibilities without listing both explicit semantics;
- a failed Compatibility or Coherence gate removes that responsibility from coverage;
- QA and Presentation never increase Core Design Depth;
- parameter items count only when `coreMechanicResponsibility=true` and `consumerDesignItemIds` is non-empty;
- 100% Projected Design Coverage does not override a missing core responsibility.

- [ ] **Step 5: Implement only enough validation to pass Task 1**

Use stable IDs and structured fields. Do not use title/text similarity, embeddings, or LLM inference in the evaluator.

- [ ] **Step 6: Run Task 1 tests and commit**

Run the entire `tests/test_full_mechanic_reconstruction.py`; expect PASS.

Commit:

```powershell
git add backend/full_mechanic_reconstruction.py tests/test_full_mechanic_reconstruction.py
git commit -m "feat: evaluate full mechanic reconstruction"
```

### Task 2: Three mechanic-aware reconstruction profiles

**Files:**
- Create: `data/planner_knowledge/full_mechanic_reconstruction_profiles_v1.json`
- Create: `tests/fixtures/full_mechanic_reconstruction_gold_v1.json`
- Modify: `backend/full_mechanic_reconstruction.py`
- Test: `tests/test_full_mechanic_reconstruction.py`

**Interfaces:**
- Consumes: `reconstruct_mechanic_model(reconstruction_input)`
- Produces: `load_reconstruction_profile(mechanic_design_id: str, path: Path) -> dict`
- Produces profiles for `MDES-CHOICE`, `MDES-WEAPON`, and `MDES-MONSTER` only.

- [ ] **Step 1: Write the failing applicability and higher-order discovery tests**

Use independent Gold literals to assert:

- Choice discovers Candidate Pool, Eligibility, Pool Shortage, Candidate Stability, Refresh Invalidation, Commit Boundary, Apply Consumer, Cleanup, and Resume responsibilities.
- Weapon discovers Instance Identity, Result Classification, Slot Branches, Activation, Target Validity, Attack Cycle, Damage Attribution, Interrupt, and Removal/Cleanup responsibilities.
- Monster discovers Target, Move, Contact Evaluation, First Damage, Repeat, Movement Lock, Exit, Resume, Pause, Death/Pending Damage, and Cleanup responsibilities.
- consecutive level-up, repeat interval, replacement/removal, and other conditional children remain dormant without explicit parent/existence signals.

- [ ] **Step 2: Run the focused discovery tests and verify RED**

Expected: FAIL because the production profiles and discovery logic do not exist.

- [ ] **Step 3: Implement production profiles as question priors, not answers**

Each responsibility record contains:

```json
{
  "responsibilityId": "choice.candidate_pool",
  "family": "algorithm",
  "role": "core",
  "executionQuestion": "候选从哪些当前可用内容中构成？",
  "parentResponsibilityId": "choice.candidate_generation",
  "requiredExistenceSignals": [],
  "satisfactionCriteria": ["candidate source", "eligible content boundary"],
  "insufficientPatterns": ["生成候选", "按候选规则处理"]
}
```

The profile must not include an answer, project number, GVE16 field/table, or fixed chapter title. The Gold fixture remains under `tests/fixtures` and production code must never read it.

- [ ] **Step 4: Implement deterministic applicability and granularity checks**

Activate core responsibilities after mechanic recognition. Activate conditional children only after their explicit signal or parent existence result. Reject synonymous siblings and parameter facets without a distinct consumer responsibility.

- [ ] **Step 5: Run Task 1–2 tests and commit**

Expected: all focused tests PASS and production Gold access count remains zero.

Commit:

```powershell
git add data/planner_knowledge/full_mechanic_reconstruction_profiles_v1.json tests/fixtures/full_mechanic_reconstruction_gold_v1.json backend/full_mechanic_reconstruction.py tests/test_full_mechanic_reconstruction.py
git commit -m "feat: discover full mechanic responsibilities"
```

### Task 3: Model-level synthesis for Choice, Weapon, and Monster

**Files:**
- Modify: `backend/full_mechanic_reconstruction.py`
- Create: `scripts/generate_full_mechanic_reconstruction.py`
- Test: `tests/test_current_full_mechanic_reconstruction.py`

**Interfaces:**
- Consumes current structured artifacts through `build_current_reconstruction_inputs(root: Path) -> list[dict]`
- Produces: `synthesize_reconstruction(input: dict, profile: dict) -> dict`
- Produces exactly three `MechanicReconstruction` objects.

- [ ] **Step 1: Write a failing Choice model test**

Assert the reconstructed Choice model contains an ordered lifecycle with stable design-item IDs and structured relations covering:

`trigger → pause → pool/eligibility → generate temporary candidates → refresh or confirm → apply → cleanup → resume`.

Assert Pool Shortage and Duplicate Handling are either executable recommended designs or explicit true alternatives; generic text such as “按规则生成候选” fails Information Gain.

- [ ] **Step 2: Implement the minimal Choice synthesis and make the test GREEN**

Reuse Existing/Approved items first. Add model-level Conservative/Design Inference items only for uncovered applicable responsibilities. Every item records:

```python
{
    "designItemId": "MREC-CHOICE-POOL-001",
    "sequence": 30,
    "text": "...",
    "knowledgeClass": "design_inference",
    "semanticResponsibilities": ["choice.candidate_pool", "choice.eligibility"],
    "sourceRuleIds": [],
    "sourceProposalIds": [],
    "requirementIds": [],
    "parameterRefs": [],
    "gateStatus": "pass",
}
```

- [ ] **Step 3: Write a failing Weapon model test**

Assert one coherent flow covers acquisition, result classification, instance/slot handling, activation, target/attack cycle, damage/statistics handoff, interrupt, and removal cleanup. Assert full-slot behavior has one recommended alternative set with 2–3 options and does not duplicate slot handling in Draw.

- [ ] **Step 4: Implement the minimal Weapon synthesis and make the test GREEN**

Use structured references for Draw and Statistics dependencies. Keep exact cooldown/damage/range values as `{x}` parameter contracts with explicit consumers; do not let those placeholders count as core coverage unless the mechanism responsibility is defined.

- [ ] **Step 5: Write a failing Monster model test**

Assert a state/flow model covers enter, target, move, contact evaluation, first damage, repeat when activated, exit/resume, pause, death/pending damage, and cleanup. Assert observation order and causal rule are distinct fields. Assert no unsupported state name is marked Confirmed.

- [ ] **Step 6: Implement the minimal Monster synthesis and make the test GREEN**

Represent states using natural planner labels while preserving knowledge class. Conditional repeat children activate only because the current approved periodic-contact rule supplies an existence signal.

- [ ] **Step 7: Add cross-model coherence tests and commit**

Assert:

- Choice pause/resume dependencies are referenced by Weapon and Monster rather than redefined;
- Weapon damage output is consumed by Statistics through a structured relation;
- each design responsibility has one Primary Mechanic Owner;
- no branch lacks a next state;
- every parameter has a mechanic and design-item consumer.

Commit:

```powershell
git add backend/full_mechanic_reconstruction.py scripts/generate_full_mechanic_reconstruction.py tests/test_current_full_mechanic_reconstruction.py
git commit -m "feat: synthesize three full mechanic models"
```

### Task 4: Review artifact, structural thresholds, and frozen-output verification

**Files:**
- Modify: `scripts/generate_full_mechanic_reconstruction.py`
- Modify: `.claude/memory/memory.md`
- Test: `tests/test_current_full_mechanic_reconstruction.py`
- Create: `artifacts/full-mechanic-reconstruction-2026-08-19/before-models.json`
- Create: `artifacts/full-mechanic-reconstruction-2026-08-19/reconstructed-models.json`
- Create: `artifacts/full-mechanic-reconstruction-2026-08-19/core-design-depth.json`
- Create: `artifacts/full-mechanic-reconstruction-2026-08-19/reconstruction-quality-gate.json`
- Create: `artifacts/full-mechanic-reconstruction-2026-08-19/full-mechanic-design-review-preview.md`
- Create: `artifacts/full-mechanic-reconstruction-2026-08-19/reconstruction-lineage.json`

**Interfaces:**
- Consumes the three reconstruction objects and evaluator results.
- Produces deterministic JSON and one natural-language Review Preview.

- [ ] **Step 1: Write a failing end-to-end artifact test**

Hash before generation:

- `data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json`;
- `artifacts/planning-content-phase6.5-chapter-assembly-2026-08-18/human-planning-preview.md`;
- `artifacts/mechanic-design-synthesis-2026-08-18/planning-hierarchy-preview.md`;
- current Rule and Requirement artifacts.

Run the generator and assert all hashes remain unchanged, exactly six reconstruction artifacts exist, and no Approved Rule or Requirement status has been created or changed.

- [ ] **Step 2: Add failing structural-success assertions**

For all three mechanics assert:

- Core Design Depth Coverage is at least 80%;
- Projected Design Coverage improves by at least 20 percentage points or is at least 80%;
- all structural remediation gates pass;
- the natural Review Preview includes Before Model, Reconstructed Model, high-value questions, recommended answers, alternatives where applicable, parameter contracts, dependencies, ordered flow/state model, QA outcomes, remaining gaps, and lineage summary;
- review output is mechanic-level and does not render engineering Dimension IDs as headings.

- [ ] **Step 3: Implement deterministic rendering and threshold classification**

If any threshold fails, emit `remediationStatus: root_cause_failure`; do not recommend Dimension-level patching. Render coherent subsections and ordered execution flows, not Atomic Proposal lists.

- [ ] **Step 4: Generate artifacts and run focused regression**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'runtime_packages_pytest').Path
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/generate_full_mechanic_reconstruction.py
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_full_mechanic_reconstruction.py tests/test_current_full_mechanic_reconstruction.py tests/test_mechanic_execution_depth.py tests/test_current_mechanic_execution_depth.py tests/test_mechanic_design_synthesis.py tests/test_mechanic_requirement_discovery.py tests/test_current_ai_rule_proposals.py -q
```

Expected: all tests PASS; quality gate passes; all frozen hashes are unchanged.

- [ ] **Step 5: Update stable memory and commit**

Record only stable contracts: Mechanic Model remediation unit, independent Core Design Depth, and two-stage acceptance. Do not record current benchmark answers as general planner knowledge.

Commit:

```powershell
git add backend/full_mechanic_reconstruction.py scripts/generate_full_mechanic_reconstruction.py tests/test_full_mechanic_reconstruction.py tests/test_current_full_mechanic_reconstruction.py data/planner_knowledge/full_mechanic_reconstruction_profiles_v1.json tests/fixtures/full_mechanic_reconstruction_gold_v1.json artifacts/full-mechanic-reconstruction-2026-08-19 .claude/memory/memory.md
git commit -m "feat: reconstruct three full mechanic models"
```

### Task 5: Verification and remediation handoff

**Files:**
- Verify only; no additional production changes unless a failing test proves a defect.

**Interfaces:**
- Consumes all Task 1–4 outputs.
- Produces the user-facing remediation report.

- [ ] **Step 1: Run `git diff --check` on scoped files**

Expected: no whitespace errors.

- [ ] **Step 2: Run the full focused regression from Task 4 again**

Expected: fresh PASS output, not a cached claim.

- [ ] **Step 3: Report structural evidence**

For each mechanic report:

- Before Mechanic Model;
- structural root cause;
- Reconstructed Mechanic Model;
- newly discovered high-value questions and recommended answers;
- true alternatives;
- parameter contracts;
- dependencies;
- ordered flow/state model;
- QA outcomes;
- Projected Design and Core Design Depth before/after;
- remaining GVE16-depth gaps.

Also report frozen-output hashes, unsupported invention, duplication, common-sense filler, Presentation pollution, and prohibited mutation guards.

- [ ] **Step 4: Stop at the Review gate**

Do not generate Approved Rules or Final Publication. The next authorized transition is lead-planner Accept/Edit at design-item granularity.
