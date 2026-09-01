# TargetAlignmentEvaluator and GranularityEvaluator Design

## Objective

Create a new quality infrastructure that evaluates generated planning delivery independently from generation. It must expose two separate scores:

- **GVE16 Paradigm Alignment**: how well existing trusted content is organized and expressed.
- **Execution Completeness**: whether the available specification is complete enough for implementation and QA.

The new evaluator is independent of `backend/document_quality_evaluator.py`. Legacy scores and thresholds may appear only in a labeled historical comparison and never enter a new score, finding, hard gate, threshold, or qualification decision.

## Locked interfaces

```python
evaluate_target_alignment(
    execution_delivery,
    mechanism_blocks,
    visual_blocks,
    rules,
    facts,
    gaps,
    parameter_contracts,
    alignment_corpus,
    qualification_evidence=None,
) -> TargetAlignmentReport

evaluate_granularity(
    execution_delivery,
    mechanism_blocks,
    alignment_corpus,
) -> GranularityReport

load_gve16_alignment_corpus(path) -> GVE16AlignmentCorpus
```

All inputs are immutable. Evaluators do not call an LLM, do not write project state, and do not participate in rendering.

## Read-only GVE16AlignmentCorpus

The corpus stores only anonymized abstract statistics:

- title-length distribution;
- chapter-depth distribution;
- mechanism-grouping distribution;
- rules-per-group distribution;
- sentence-length distribution;
- bullet/prose/numbered/table carrier distribution;
- condition/action/result ordering;
- lifecycle position;
- Logic/Presentation adjacency policy;
- mechanism-semantic subheading usage.

It must not contain GVE16 sentences, project fields, values, rules, chapter trees, named game objects, or Gap answers. Every range derived from the current limited sample has:

```yaml
provisional: true
source_scope: anonymized_limited_corpus
```

Hard constraints are stored separately from provisional reference ranges. Corpus files are loaded into immutable data structures. The evaluator never rewrites them.

## Eligibility sets

Paradigm Alignment evaluates only trusted content already present in the delivery:

- approved/confirmed Rules;
- valid Rules with non-inferred source Facts;
- confirmed or partial MechanismBlocks containing at least one eligible Rule;
- final paragraphs traceable to eligible Rules.

It excludes from its denominator:

- `evidence_insufficient` chapters;
- missing Rule roles;
- open or unreviewed Gaps;
- absent ParameterContracts;
- mechanisms not proven to exist.

Execution Completeness evaluates applicable Schema expectations, open Gaps, parameter needs, and incomplete mechanism roles. It may therefore be low when evidence is incomplete.

## Hard Gates

Hard Gates are independent of both scores. Any failure sets:

```text
qualificationStatus = fail
```

Required gates:

1. `unsupported semantic addition = 0`
   - confirmed execution paragraph with no Rule provenance;
   - delivery-reported unsupported addition;
   - paragraph semantic domain absent from all supporting Rules.
2. `Presentation mixed into Logic body = 0`
   - any confirmed execution paragraph references a Presentation Rule;
   - a Presentation description is duplicated in Logic body.
3. `Gap rendered as confirmed rule = 0`
   - confirmed paragraph carries `gapIds`;
   - a Gap ID appears in confirmed Rule provenance;
   - a delivery unit marked open decision is presented as confirmed execution text.
4. `Rule → Final Output traceability = 100%`
   - every eligible non-presentation Rule assigned to evaluated MechanismBlocks appears in at least one final output unit.
5. `Inferred Fact rendered as confirmed = 0`
   - a confirmed paragraph traces through a Rule to a source Fact whose `evidenceLevel` is `inferred`.

Visual-reference paragraphs are allowed only when they carry existing Logic Rule IDs and resolve to an existing VisualBlock. Their fixed reference sentence is delivery metadata, not a semantic addition.

## GVE16 Paradigm Alignment — 100 points

All ratios use eligible units only. `clamp(x)` limits values to `[0, 1]`.

### 1. Chapter organization — 20

- Heading integrity — 8:
  `8 × (1 - invalid_heading_count / eligible_heading_count)`
  Invalid means duplicate sibling, unsupported semantic heading, sentence-like heading, or heading with no eligible content.
- Mechanism grouping — 8:
  `8 × (1 - (orphan_group_count + over_split_heading_count) / eligible_mechanism_count)`
- Carrier hierarchy — 4:
  `4 × (1 - carrier_hierarchy_mismatch_count / eligible_carrier_count)`

`evidence_insufficient` headings are excluded rather than penalized.

### 2. Body granularity — 20

Consumes `GranularityReport`:

- Semantic-domain isolation — 8:
  proportional penalty for cross-domain paragraphs and forced merges.
- Mechanism cohesion — 8:
  proportional penalty for isolated fragments, orphan single-Rule headings, and over-split mechanism groups.
- Provisional distribution fit — 4:
  compares one-Rule sentence rate, rules per paragraph, paragraph length, and carrier mix with provisional corpus distributions. For each available distribution, fit is `1 - min(1, distance_to_corpus_central_band / corpus_observed_span)`; unavailable statistics are reported as unavailable and removed from this four-point denominator rather than invented. This component is capped at four points so limited corpus statistics cannot dominate.

Deleting Rules cannot improve this score because the denominator is the MechanismBlock eligible Rule set, not only remaining final paragraphs.

### 3. Planning language — 20

- Complete executable syntax — 8:
  penalizes fragments, incomplete predicates, and ambiguous subject omission.
- Condition/action/state order — 6:
  evaluates only Rules that already contain those structured roles; missing roles do not reduce this score.
- AI/meta/common-sense language — 6:
  proportional penalty for forbidden expressions and explanatory filler.

### 4. Information density — 15

- Supported information retention — 8:
  `8 × traced_eligible_rule_count / eligible_rule_count`.
- Redundancy and fragment control — 7:
  proportional penalty for duplicate semantic keys, repeated descriptions, consecutive short fragments, and paragraphs that add no condition/action/limit/state/result/numeric/config/boundary information.

Because eligible Rule count is fixed before inspecting the final text, deleting necessary Rules cannot raise density.

### 5. MechanismBlock organization — 15

- Rule assignment and provenance — 6.
- Same-mechanism grouping without cross-domain merge — 5.
- Ordering of roles that are actually present — 4.

Missing trigger/result/exit roles do not reduce Paradigm Alignment. Incorrect ordering of roles that are present does.

### 6. Logic / Presentation / Parameter delivery layering — 10

- Logic/Presentation carrier separation — 5.
- stable Logic → VisualBlock references and no duplicated presentation prose — 3.
- parameter/config carrier correctness — 2.

Absent ParameterContracts do not reduce this score. Only misplaced existing parameter/config content does.

## Execution Completeness — 100 points

### 1. Mechanism-chain completeness — 30

For each applicable ChapterSchema role, classify `covered`, `open_gap`, or `not_applicable`. Score is `30 × covered / (covered + open_gap)`. Inferred Facts cannot count as covered.

### 2. Program executability — 25

Eligible confirmed Rules are checked for executable trigger/condition/processing/result/boundary fields according to ChapterType and SchemaSlot. `unresolved_dependency` is not executable. Score is the weighted covered fraction.

### 3. QA testability — 20

Measures whether applicable Rules provide observable condition/input and expected result/state/boundary. Open QA-blocking Gaps reduce this score.

### 4. Parameter-contract completeness — 15

- If no Rule or Schema requires parameters: full 15, marked `not_applicable_no_parameter_need`.
- If numeric/config Rules or parameter Gaps exist: score by resolved required contract fields.
- Missing ParameterResolver output may therefore lower Execution Completeness but never Paradigm Alignment.

### 5. Gap closure — 10

`10 × closed_applicable_gaps / applicable_gaps`. No applicable Gaps yields 10 with an explicit N/A reason.

## GranularityEvaluator

The evaluator consumes Markdown carriers and structural provenance together. It reports:

- one-Rule-one-sentence ratio;
- single-Rule independent-heading ratio;
- average Rules per paragraph;
- average paragraph length;
- bullet/prose/numbered/table distribution;
- semicolon-stitching ratio;
- consecutive-short-fragment count;
- isolated paragraphs per mechanism;
- cross-semantic-domain paragraph count;
- low-information single-body heading count;
- over-split heading count per mechanism;
- forced multi-Rule merge count;
- lost eligible Rule count.

### Semantic-domain rules

A paragraph domain is derived from supporting Rule `semanticKey`, Chapter ownership, SchemaSlot family, and MechanismBlock `mechanismSemantic`. Text keywords alone cannot determine domain.

A multi-Rule paragraph is a forced merge when its supporting Rules do not share compatible owner, mechanism semantic, or SchemaSlot family. Such a merge increases the penalty even if it lowers one-Rule-one-sentence ratio.

A removed Rule remains in the eligible MechanismBlock denominator and increases `lostEligibleRuleCount`, preventing density or granularity gains from deletion.

### Reference ranges

Initial ranges are copied without modification from the anonymized Phase 3.6 profile and marked provisional. They are diagnostic bands, not hard pass thresholds. Hard constraints such as no mixed semantic domains and full provenance remain non-provisional.

## Attribution contract

Every failed or deducted metric emits:

```json
{
  "metric": "body_granularity.one_rule_one_sentence_ratio",
  "observed": 0.81,
  "reference": {"distributionId": "rules_per_group", "provisional": true},
  "impact": -6,
  "ownerLayer": "Granularity / Editorial",
  "minimalFix": "Group adjacent Rules only when owner, mechanismSemantic and semantic domain match."
}
```

`ownerLayer` must be exactly one of:

- Evidence / Fact
- Rule
- Gap
- Entity
- Parameter
- MechanismComposer
- Renderer
- Granularity / Editorial
- Delivery Separation

Findings are deterministic and sorted by score impact, then metric ID.

## Anti-Goodhart requirements

Automated tests must prove:

- merging different semantic domains cannot raise granularity score;
- deleting a necessary Rule cannot raise information-density score;
- adding meaningless mechanism headings cannot raise organization score;
- inferred Fact in confirmed text fails a Hard Gate;
- Presentation in Logic body fails a Hard Gate;
- Gap rewritten as a confirmed statement fails a Hard Gate;
- final text without Rule provenance fails both unsupported-addition and traceability gates.

Corpus values are versioned artifacts. Evaluator code cannot alter or calibrate them against the current project.

## Qualification status

- Any Hard Gate failure: `fail`.
- Paradigm Alignment below 80: `not_qualified`.
- Paradigm Alignment at least 80 but fewer than two recorded complete runs at least 80, or no non-current-project blind run at least 75: `pending`.
- All score and run conditions met: `qualified`.

Qualification evidence records immutable run IDs, project fingerprints, corpus version, evaluator version, and score. Current-project duplicate runs with the same generation fingerprint do not count as two independent complete generations.

## Baseline output

The Phase 5.1 baseline writes:

- Paradigm Alignment total and six dimensions;
- Execution Completeness total and five dimensions;
- Granularity Report;
- Hard Gates;
- attributed findings;
- delta to 80;
- automatically selected minimum next-fix module;
- qualificationStatus;
- labeled legacy comparison whose values do not contribute to the new result.

The baseline is read-only and stops before ParameterResolver.
