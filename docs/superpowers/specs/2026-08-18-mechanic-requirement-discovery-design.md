# Mechanic Requirement Discovery Design

Date: 2026-08-18  
Status: approved for TDD implementation  
Scope: first benchmark iteration for 《一路狂飙》

## 1. Objective

The current publication path, dynamic owner resolution, authoritative Rule-to-Synthesis provenance bridge, and RuleChain publication are working. The remaining benchmark bottleneck is upstream: Mechanic Reconstruction organizes existing rules but does not discover which execution definitions are still required for a mature mechanic closure.

This design adds `Execution Requirement / Missing Rule Requirement` discovery inside the existing pipeline. A Requirement asks what still needs to be defined. It is not a project Rule, does not contain an answer, and cannot enter confirmed publication.

The implementation must not:

- add a Phase, taxonomy, Closure Status, fixed chapter schema, or diagnostic override;
- change the Evidence or Fact source of truth;
- copy GVE16 project-specific rules, parameters, formulas, owners, or chapter structure;
- create project Rules from planner knowledge;
- modify Carrier, Renderer, provenance bridge, final chapter schema, or `job.json`;
- use word count, rule count, or heading count as an alignment proxy.

## 2. Pipeline Placement

The capability is embedded in the existing layers:

```text
Evidence / Fact / Existing Rule
→ Mechanic Recognition
→ Execution Prior
→ Expected Dimension Applicability
→ Existing Coverage Resolution
→ Missing Requirement
→ Evidence Probe or P4/P6 Review Routing
→ Evidence → Fact → Rule
→ Requirement Satisfaction Re-evaluation
→ RuleChain
→ Publication
```

`gve16-system-planner` is an Execution Prior Library only. It can propose dimensions to inspect but cannot provide current-project answers. The original video and ordered screenshots are formal Evidence Sources.

## 3. Requirement Identity and Lineage

Every Requirement has a stable `REQ-*` identity. It must not be reconstructed ad hoc from mutable display values. Repeated runs over the same stable mechanic identity and dimension identity produce the same ID. Owner labels, titles, routing, and status changes do not change it.

Required fields include:

```json
{
  "requirementId": "REQ-*",
  "mechanicId": "...",
  "executionDimensionId": "...",
  "ownerPath": {
    "system": "...",
    "subsystem": "...",
    "mechanic": "..."
  },
  "priorSources": [
    {
      "type": "gve16_skill|mechanic_schema|rule_gap|relation_gap",
      "sourceRef": "...",
      "reason": "..."
    }
  ],
  "status": "resolved|evidence_probe|evidence_resolvable|evidence_unknown|review_required|dormant_optional|not_applicable",
  "statusHistory": [],
  "reopenable": false
}
```

Evidence Candidates, P4/P6 review items, Facts, and Rules retain reverse references. Rules use `originRequirementIds[]` for provenance and `satisfiesRequirementIds[]` for deterministic closure.

## 4. Final Status Flow

```text
Expected Dimension
↓
Applicability Gate
├─ not applicable → not_applicable
├─ optional/conditional without existence signal → dormant_optional
└─ active
    ↓
Existing Evidence / Fact / Rule Check
├─ Dimension Satisfaction Contract met → resolved
└─ Missing Requirement
    ↓
Observability Routing
    ├─ static / temporal / mixed
    │    ↓
    │ evidence_probe
    │    ├─ reliable candidate evidence
    │    │   → evidence_resolvable
    │    │   → Evidence → Fact → Rule
    │    │   → satisfaction re-evaluation
    │    │   → resolved
    │    └─ probe exhausted
    │        → evidence_unknown (reopenable)
    └─ hidden
         ↓
      review_required
         ├─ behavior → P4
         └─ parameter → P6
              ↓
         Approved Decision
              ↓
         Evidence → Fact → Rule
              ↓
         satisfaction re-evaluation
              ↓
         resolved
```

P4/P6 are routing targets, not Closure Status values:

```json
{
  "status": "review_required",
  "reviewType": "behavior|parameter",
  "routingTarget": "P4|P6"
}
```

`evidence_unknown` remains reopenable. New screenshots, a new video, higher frame rate, or a new candidate window can transition it back to `evidence_probe`.

Approved Decision alone never closes a Requirement. Closure occurs only after a Valid Rule at the correct mechanic and dimension satisfies its contract.

No `partially_resolved` or `parameter_required` status is introduced. Partial coverage is represented by parent/child dimensions at the correct granularity.

## 5. Benchmark Execution Prior

The first runtime library is explicitly provisional and benchmark-scoped: `benchmark_execution_prior_v1`. It is not a complete universal Planner Library.

Each dimension defines:

```json
{
  "dimensionId": "...",
  "parentDimensionId": null,
  "dimensionRole": "core|conditional|optional",
  "applicableMechanicSignals": [],
  "requiredExistenceSignals": [],
  "observableModes": [
    {"mode": "temporal", "priority": 1},
    {"mode": "static", "priority": 2}
  ],
  "satisfactionContract": {
    "criteria": [],
    "insufficientPatterns": []
  },
  "priorSources": []
}
```

Dimension Satisfaction Contracts describe what information is sufficient, never the project-specific answer. A semantically related Rule does not resolve a Requirement unless it meets the contract. Examples of insufficient patterns include an observation without an exit result, a timing value without a confirmed repeat behavior, or a display label without attribution logic.

Dimension roles:

- `core`: normally required to inspect for minimum mechanic closure;
- `conditional`: activated only by its required existence signals;
- `optional`: an extension, dormant by default.

Parent resolution does not activate every child. Each child passes its own Applicability Gate. A core child activates; a conditional child requires its own existence signal; otherwise it remains dormant.

The seven benchmark mechanic families are:

1. Monster movement and attack
   - Core: movement state, attack entry, attack execution, attack exit, post-exit state, death interrupt.
   - Conditional: target selection, repeat attack, attack interval, target invalidation.
2. Weapon execution chain
   - Core: acquire, slot/activation, attack trigger, damage trigger, attribution.
   - Conditional: target selection, cooldown, slot full, replacement/removal.
3. Battle level and three-choice
   - Core: trigger, candidate generation, temporary decision state, confirm, apply, exit.
   - Conditional: pause/resume, refresh, refresh cost, duplicate rule, pool algorithm, cross-run reset.
4. Independent weapon draw
   - Core: entry, result generation, result commitment, downstream effect.
   - Conditional: cost, pool, weight, pity, animation relation, abandon/replacement.
5. Normal stage to Boss to end
   - Core: stage transition, Boss entry, Boss termination, next state.
   - Conditional: Boss initialization details, interruption/failure branch, level reset.
6. Damage statistics
   - Core: start, attribution, aggregation, end.
   - Conditional: DPS, ranking, refresh frequency, persistence.
7. Success/failure to settlement
   - Core: success trigger, failure trigger, termination, settlement entry, next state.
   - Conditional: priority, pending event handling, reward calculation, persistence.

These dimensions ask questions only. For example, `attack.exit_condition` asks how attack state ends; it does not imply range exit or resumed movement.

The Expected Dimension Library never determines chapter titles, chapter boundaries, or Carrier choice.

## 6. Applicability and Existing Coverage

The Applicability Evaluator consumes only current structured Evidence, Fact, Rule, Mechanic Recognition, and explicit relation signals.

- Core dimensions enter the coverage check without a default answer.
- Conditional and optional dimensions without required existence signals do not enter Probe, P4, P6, Missing counts, or Recall denominator; they remain `dormant_optional`.
- `not_applicable` is used only when current structured information positively excludes a dimension.

The Existing Coverage Resolver uses the Dimension Satisfaction Contract at exact dimension granularity. It may use explicit dimension membership, stable identities, lineage, and structured relations. It must not use text, title, embedding, LLM, or semantic-nearness guessing.

Examples of separate child states are valid:

```text
attack.repeat.exists = resolved
attack.repeat.interval = review_required / P6
attack.repeat.interruption = evidence_probe
```

## 7. Evidence Source Selection and Probe

Evidence selection follows ordered `observableModes`, not a universal screenshot-first fallback:

- `static`: screenshot-first;
- `temporal`: video or continuous-frame-first;
- `mixed`: select or combine sources based on coverage, temporal continuity, and state completeness.

Entry, Exit, Repeat, Pause, Resume, Interrupt, and State Transition dimensions treat video as a first-class formal Evidence Source. Dense ordered screenshots may provide sufficient continuous evidence, but sparse screenshots cannot replace required temporal inspection.

Probe workflow:

1. Build a lightweight time/scene index without producing Rules.
2. Build a Requirement-specific plan describing observable before, transition, and after signals and falsification conditions.
3. Search screenshot anchors and/or the full video timeline as selected by observable mode.
4. Expand every candidate window and repeat until no new candidate windows appear.
5. Inspect positive examples, counterexamples, repeated instances, and interruption cases.
6. Emit Evidence Candidates or an auditable Exhaustion Record.

Probe Exhaustion requires all applicable conditions:

- the complete selected source timeline/sequence was scanned;
- all known anchor windows were scanned;
- candidate windows were expanded and reviewed;
- the latest scan produced no new candidate windows;
- scanned ranges, strategies, candidates, exclusion reasons, and material gaps were recorded.

Without exhaustion, a Requirement stays `evidence_probe`; it cannot become `evidence_unknown`.

Evidence Candidate contract:

```json
{
  "evidenceCandidateId": "EVC-*",
  "requirementId": "REQ-*",
  "sourceId": "...",
  "eventWindow": {"startMs": 0, "endMs": 0},
  "beforeObservation": {"timestampMs": 0, "frameRef": "...", "state": "..."},
  "transitionObservation": {"timestampMs": 0, "frameRef": "...", "event": "..."},
  "afterObservation": {"timestampMs": 0, "frameRef": "...", "state": "..."},
  "supportingWindows": [],
  "counterexampleWindows": [],
  "eventRecognitionConfidence": 0.0,
  "transitionCausalityConfidence": 0.0,
  "observedOrder": "...",
  "stateCorrelation": "supported|uncertain|unsupported",
  "causalSupport": "supported|uncertain|unsupported",
  "causalLimitations": [],
  "probeCoverageRef": "PRB-*"
}
```

Observation, correlation, and causality are distinct. Observing A before B does not establish that A causes B. A single sample can produce an Evidence Candidate but caps confidence for Repeat, Interval, and causal claims. `evidence_resolvable` still enters the normal Evidence → Fact → Rule promotion chain and cannot publish directly.

## 8. P4/P6 Review Routing

Only active hidden Requirements enter review routing.

P4 receives hidden behavior definitions. P6 receives hidden numeric/parameter definitions. A measurable number remains on the Evidence Probe path.

P4 default presentation has two layers:

```text
已确认
- concise confirmed rule context

仍需定义
- one planner-level missing behavior question
```

Frame references, confidence, and Probe debug details are expandable evidence, not default reading burden.

P6 records:

```json
{
  "requirementId": "REQ-*",
  "consumerMechanicId": "...",
  "consumerDimensionId": "...",
  "consumerRuleIds": []
}
```

Mechanic and Dimension consumers are mandatory. Rule consumers are attached when available and may be added later.

## 9. Components

The minimal components are:

- Execution Prior Provider: reads runtime prior only.
- Applicability Evaluator: gates expected dimensions.
- Requirement Registry: stable identity, state history, reopenability, lineage.
- Existing Coverage Resolver: exact Dimension Satisfaction Contract evaluation.
- Evidence Source Selector: chooses static, temporal, or mixed source strategy.
- Requirement-driven Probe Adapter: emits observations and exhaustion records, never Rules.
- Review Router: attaches P4/P6 items to System → Subsystem → Mechanic → Dimension.
- Requirement Satisfaction Resolver: closes Requirements only after a Valid satisfying Rule.
- Benchmark Evaluator: test-only comparison against an independent Gold Set.

Runtime `benchmark_execution_prior_v1` and test-only `benchmark_expected_dimensions_gold_v1` are independent artifacts. The Gold Set is authored separately, cannot be generated from the runtime library, contains only which dimensions should be checked under fixture conditions, contains no 《一路狂飙》 rule answers, and cannot be imported or read by production code.

## 10. TDD Acceptance

Tests cover:

1. stable Requirement identity and reverse lineage;
2. Core/Conditional/Optional applicability and child gates;
3. exact Dimension Satisfaction Contract behavior;
4. observability routing and evidence source selection;
5. Probe Exhaustion and reopenability;
6. Evidence Candidate integrity and observation/causality separation;
7. P4/P6 routing without new statuses;
8. Requirement closure after Valid Rule satisfaction;
9. runtime Prior versus test-only Gold dependency isolation;
10. all seven benchmark mechanics.

Metrics:

- Core Dimension Recall ≥ 90%.
- Overall Active Requirement Recall ≥ 80%.
- Unsupported Requirement Rate ≤ 5%.
- Routing Accuracy ≥ 90%.
- Probe Integrity critical cases = 100%.
- New confirmed project Rules = 0 during discovery.
- Final Publication consumes zero unresolved Requirements.

Recall measures correctly activated expected dimensions, not whether the runtime library contains those dimensions.

Probe Integrity is a hard gate: missing verifiable evidence packages, premature exhaustion, causal promotion from mere temporal order, or direct Requirement-to-Rule publication fails the iteration.

## 11. Implementation Order

1. Add failing tests for ID stability, applicability, parent/child gating, Satisfaction Contracts, and Gold isolation.
2. Implement the runtime Prior Provider, Applicability Evaluator, Requirement Registry, and Coverage Resolver.
3. Add failing tests for source selection, Exhaustion, Evidence Candidate integrity, and causality separation.
4. Implement the Requirement-driven Probe Adapter over existing screenshot/video facilities.
5. Add failing tests for P4/P6 routing and Rule-to-Requirement closure.
6. Integrate into existing Mechanic Structuring and RuleChain Reconstruction.
7. Run the seven-mechanic benchmark and publish classification, Recall, routing, P4/P6 questions, and guardrails.

This implementation round intentionally does not regenerate Final Publication because unresolved Requirements cannot enter it. If all discovery thresholds pass, the next action is not another design or Audit. It is the existing operational loop:

```text
Requirement
→ Probe
→ Evidence / Fact / Rule
→ P4 / P6
→ Approved Rule
→ RuleChain
→ Final Publication
→ GVE16 Benchmark
```

The final product-stage acceptance remains whether the complete planning document raises A–H toward at least 80% while keeping unsupported invention, duplication, common-sense filler, Presentation pollution, and publication loss within guardrails.
