# Target Alignment and Granularity Evaluators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent read-only corpus, structure-aware granularity evaluation, dual target-alignment/completeness scoring, hard gates, explainable attribution, and a real Phase 5.1 baseline.

**Architecture:** `gve16_alignment_corpus.py` loads a sanitized immutable corpus artifact. `granularity_evaluator.py` evaluates final carriers against Rule/MechanismBlock provenance. `target_alignment_evaluator.py` composes the granularity report with trusted Rules, Facts, Gaps, VisualBlocks, and optional ParameterContracts to produce independent Paradigm Alignment and Execution Completeness scores plus hard gates and deterministic findings. A baseline generator consumes Phase 5.1 artifacts only and writes independent reports.

**Tech Stack:** Python 3.12, JSON/YAML, pytest, immutable mapping wrappers, existing Phase 3/4.3/5/5.1 artifacts.

## Global Constraints

- Do not import or reuse `backend/document_quality_evaluator.py` scoring, thresholds, or findings.
- Do not change the approved scoring formulas or corpus values to fit the current project.
- Evaluators are read-only and cannot participate in rendering.
- Paradigm Alignment excludes evidence-insufficient content and missing Gaps/ParameterContracts from its denominator.
- Execution Completeness independently evaluates missing mechanism, parameter, and Gap information.
- Hard Gate failure always sets `qualificationStatus=fail`.
- Do not modify正文、P7、UI、Entity Graph、Rule、Gap、Parameter data, or enter ParameterResolver.

---

### Task 1: Sanitized immutable GVE16AlignmentCorpus

**Files:**
- Create: `backend/gve16_alignment_corpus.py`
- Create: `data/quality/gve16-alignment-corpus-v1.json`
- Create: `tests/test_gve16_alignment_corpus.py`

**Interfaces:**
- Produces: `load_gve16_alignment_corpus(path) -> GVE16AlignmentCorpus`.

- [ ] **Step 1: Write RED tests for schema, provisional ranges, forbidden content, and immutability**

```python
corpus = load_gve16_alignment_corpus(CORPUS_PATH)
assert corpus["corpusVersion"] == "gve16-alignment-corpus-v1"
assert all(item["provisional"] is True for item in corpus["provisionalReferences"].values())
assert corpus["hardConstraints"]["crossSemanticDomainParagraphCount"] == 0
with pytest.raises(TypeError):
    corpus["hardConstraints"]["crossSemanticDomainParagraphCount"] = 1
```

Also assert serialized corpus contains no known project values, Rule IDs, chapter tree, raw sentences, or project-specific object names.

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_gve16_alignment_corpus.py -q`

Expected: import/file failure.

- [ ] **Step 3: Add sanitized corpus artifact**

Copy only the existing Phase 3.6 anonymous distributions for title length, chapter depth, bullets per chapter, rule length, rules per bullet, semantic-pattern counts, and subject rate. Add carrier/mechanism fields only when a source statistic exists; mark unavailable statistics as `available:false` rather than inventing values. Keep hard constraints in a separate section.

- [ ] **Step 4: Implement recursive immutable loader and validation**

Use `MappingProxyType` and tuples recursively. Reject missing `provisional`, content-authority fields, raw text arrays, project entities, and non-v1 schema.

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest tests/test_gve16_alignment_corpus.py -q`

Commit: `feat: add immutable alignment corpus`

### Task 2: Structure-aware GranularityEvaluator

**Files:**
- Create: `backend/granularity_evaluator.py`
- Create: `tests/test_granularity_evaluator.py`

**Interfaces:**
- Consumes: `evaluate_granularity(execution_delivery, mechanism_blocks, alignment_corpus)`.
- Produces: `GranularityReport` with metrics, score components, hard/provisional labels, and findings.

- [ ] **Step 1: Write RED tests for carrier metrics and provenance-aware domains**

Lock literal metrics for a fixed fixture:

```python
assert report["metrics"]["oneRuleOneSentenceRatio"] == 0.5
assert report["metrics"]["averageRulesPerParagraph"] == 1.5
assert report["metrics"]["carrierDistribution"] == {"prose": 1, "bullet": 1, "numbered": 0, "table": 0}
assert report["metrics"]["crossSemanticDomainParagraphCount"] == 0
```

- [ ] **Step 2: Run RED and implement basic metrics**

Parse structured paragraph `format`, `ruleIds`, heading, text, and Visual-reference kind. Derive Rule domains from MechanismBlock owner, `mechanismSemantic`, and entry SchemaSlot families; never derive a domain from Markdown keywords.

- [ ] **Step 3: Add anti-Goodhart RED/GREEN cases**

Tests must prove:

```python
assert forced_cross_domain["score"] <= clean["score"]
assert deleted_rule["score"] <= complete["score"]
assert meaningless_heading["score"] <= clean["score"]
```

Implement `forcedMultiRuleMergeCount`, `lostEligibleRuleCount`, `lowInformationSingleBodyHeadingCount`, `overSplitHeadingCount`, and `isolatedParagraphsPerMechanism` before provisional distribution fit.

- [ ] **Step 4: Add explainability snapshot**

For the forced-merge fixture, assert the leading finding exactly includes:

```python
{
  "metric": "granularity.cross_semantic_domain_paragraph_count",
  "ownerLayer": "Granularity / Editorial",
  "minimalFix": "Split the paragraph at the semantic-domain boundary; keep only Rules with the same owner and mechanism semantic together."
}
```

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest tests/test_granularity_evaluator.py -q`

Commit: `feat: evaluate planning granularity structurally`

### Task 3: TargetAlignmentEvaluator, completeness, hard gates, and attribution

**Files:**
- Create: `backend/target_alignment_evaluator.py`
- Create: `tests/test_target_alignment_evaluator.py`
- Create: `tests/test_evaluator_explainability_snapshots.py`

**Interfaces:**
- Consumes the locked `evaluate_target_alignment(...)` signature.
- Produces Paradigm Alignment, Execution Completeness, hard gates, attributed findings, target delta, minimum next-fix module, and qualification status.

- [ ] **Step 1: Write RED tests proving score independence**

Use the same delivery organization with open versus closed Gaps:

```python
assert open_result["paradigmAlignment"] == closed_result["paradigmAlignment"]
assert open_result["executionCompleteness"]["total"] < closed_result["executionCompleteness"]["total"]
```

Repeat for absent versus complete ParameterContracts.

- [ ] **Step 2: Implement the six Paradigm dimensions exactly as the spec**

Compose normalized submetrics from the GranularityReport and eligible trusted units. Return integer/one-decimal dimension scores capped at 20/20/20/15/15/10. Exclude `evidence_insufficient` blocks and absent contracts from Paradigm denominators.

- [ ] **Step 3: Implement the five Execution Completeness dimensions**

Use block empty fields/open Gap slots, Rule resolution status and structured roles, QA severity, required parameter needs, and Gap status. Inferred Facts never cover a role.

- [ ] **Step 4: Add RED/GREEN tests for all five Hard Gates**

Cover:

- inferred Fact in confirmed paragraph;
- Presentation Rule in Logic paragraph;
- confirmed paragraph with `gapIds`;
- paragraph with no Rule IDs;
- eligible Rule missing from final output.

Each must set `qualificationStatus=fail`.

- [ ] **Step 5: Add attribution and minimum-fix selection**

Every deduction emits `metric`, `observed`, `reference`, `impact`, `ownerLayer`, and `minimalFix`. Select the responsibility layer with the largest summed negative impact; ties resolve by the fixed layer order in the spec.

- [ ] **Step 6: Add explainability snapshots**

Lock exact total/dimension scores and leading finding `ownerLayer`, `impact`, and `minimalFix` for:

- clean organized fixture;
- forced cross-domain merge;
- missing Rule trace;
- Presentation contamination;
- open-Gap/absent-parameter completeness fixture.

- [ ] **Step 7: Run GREEN and commit**

Run: `python -m pytest tests/test_target_alignment_evaluator.py tests/test_evaluator_explainability_snapshots.py -q`

Commit: `feat: evaluate alignment completeness and hard gates`

### Task 4: Real Phase 5.1 baseline and legacy comparison

**Files:**
- Create: `scripts/evaluate_phase51_baseline.py`
- Create: `tests/test_phase51_evaluator_baseline.py`
- Create: `artifacts/planning-content-phase5.1-evaluation-2026-08-17/target-alignment-report.json`
- Create: `artifacts/planning-content-phase5.1-evaluation-2026-08-17/granularity-report.json`
- Create: `artifacts/planning-content-phase5.1-evaluation-2026-08-17/baseline-summary.md`
- Create: `artifacts/planning-content-phase5.1-evaluation-2026-08-17/legacy-comparison.json`
- Create: `artifacts/planning-content-phase5.1-evaluation-2026-08-17/provenance.json`

**Interfaces:**
- Consumes current frozen Phase 5.1 delivery, Phase 4.3 blocks, Phase 3 Rules/Facts/Gaps, Phase 5 VisualBlocks, empty current ParameterContracts, and the immutable corpus.
- Produces one real baseline without product write-back.

- [ ] **Step 1: Write RED baseline contract tests**

Assert both score sets/dimensions, all five gates, findings, target delta, next-fix module, status, and labeled legacy comparison exist. Assert legacy values are absent from every new-score calculation input/provenance list.

- [ ] **Step 2: Implement baseline adapter**

Load existing artifacts read-only, preserve accepted in-memory Rule approval projection, map Phase 3 Facts by ID, and pass `parameter_contracts=[]`. Do not modify final text.

- [ ] **Step 3: Generate baseline and assert qualification semantics**

Single run can only produce `not_qualified`, `pending`, or `fail`; never `qualified`. Persist project/evaluator/corpus fingerprints.

- [ ] **Step 4: Run all evaluator and Phase 5.1 regressions**

Run:

```powershell
python -m pytest tests/test_gve16_alignment_corpus.py tests/test_granularity_evaluator.py tests/test_target_alignment_evaluator.py tests/test_evaluator_explainability_snapshots.py tests/test_phase51_evaluator_baseline.py -q
python -m pytest tests/test_visual_delivery.py tests/test_logic_delivery.py tests/test_phase51_delivery_separation.py tests/test_mechanism_composer.py tests/test_mechanism_block_renderer.py tests/test_entity_builder.py tests/test_phase5_entity_graph.py -q
```

- [ ] **Step 5: Record stable conventions and commit**

Update `.claude/memory/` with the independent dual-score and automatic-attribution contract.

Commit: `feat: add phase 5.1 alignment evaluation baseline`

