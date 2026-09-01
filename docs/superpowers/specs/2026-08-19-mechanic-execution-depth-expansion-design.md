# Mechanic Execution Depth Expansion Design

## 1. Objective

The seven benchmark Mechanic Review Units are structurally closed, but structural closure does not prove GVE16-level execution depth. This design adds a review-only depth expansion capability inside the existing Mechanic Requirement Discovery boundary.

It does not add a Pipeline phase, Requirement closure status, chapter schema, project rule, or GVE16-specific answer. GVE16 and planner knowledge remain `contentAuthority=none`: they may identify what deserves inspection, but never provide current-project facts.

The benchmark scope remains:

1. Weapon acquisition, slots, and attack
2. Independent weapon draw
3. Combat level and three-choice
4. Monster movement and attack
5. Normal stage, Boss, and level completion
6. Damage statistics
7. Outcome and settlement

## 2. Separate Quality Metrics

### 2.1 Structural Completeness

Measures whether the applicable lifecycle roles form a closed structure:

```text
closed applicable lifecycle roles / applicable lifecycle roles
```

Entry, core processing, applicable branch/repeat, exit, and next state are lifecycle roles. A score of 100% only means the mechanism has a closed skeleton.

### 2.2 Current Execution Depth Coverage

Measures whether Existing Valid Rules and Approved Rules satisfy the active execution questions:

```text
active Depth Dimensions satisfied by Existing/Approved Rules
------------------------------------------------------------
active Depth Dimensions
```

Semantic similarity is insufficient. Each dimension is evaluated against its Dimension Satisfaction Contract.
Only Existing/Approved Rules with a matching semantic responsibility may satisfy a dimension. UI, interaction, or Presentation Rules cannot satisfy a Logic Depth Dimension merely because their text mentions the same object or action.

### 2.3 Projected Execution Depth Coverage

Measures the additional dimensions that a reviewable AI design could cover:

```text
currently covered dimensions
+ dimensions covered by proposals that pass Quality, Compatibility, and Coherence Gates
-------------------------------------------------------------------------------
active Depth Dimensions
```

- Placeholder and Human Decision do not count.
- An Alternative counts only when its recommended option passes all gates.
- A `{x}` parameter proposal covers parameter meaning, consumer, unit type, and configuration responsibility, but not an approved value.
- Proposal count, Rule count, title count, word count, and document length never affect coverage.

The preview additionally separates:

- `Projected Conservative Coverage`: Existing/Approved coverage plus Conservative Proposals that pass all gates.
- `Projected Design Coverage`: Conservative coverage plus Design Inference and the recommended option of a valid Alternative Design.

`Projected Execution Depth Coverage` is an alias of Projected Design Coverage in this iteration, retained for compatibility with the confirmed reporting contract.

### 2.4 depthReady

Coverage is not a readiness verdict. `depthReady` is false whenever any of the following is true:

- an unresolved Core Depth Dimension remains active;
- an active dimension routes to `human_decision`;
- an active proposal fails Compatibility or Coherence;
- an active dimension has no valid current or projected completion route.

Therefore Projected Coverage may equal 100% while `depthReady=false`.

## 3. Depth Dimension Contract

Each benchmark depth check has a stable identity and remains review metadata:

```json
{
  "depthDimensionId": "DEPTH-MONSTER-ATTACK-REPEAT",
  "mechanicDesignId": "MDES-MONSTER",
  "dimensionFamily": "repeat_timing",
  "dimensionRole": "core|conditional|optional",
  "parentDepthDimensionId": null,
  "executionQuestion": "保持接触期间是否重复产生伤害；若重复，按什么时点结算？",
  "applicability": {
    "status": "active|dormant_optional|not_applicable",
    "signals": []
  },
  "satisfactionContract": {
    "requiredInformation": [],
    "insufficientPatterns": []
  },
  "coverage": {
    "currentStatus": "covered|missing",
    "supportingRuleIds": []
  },
  "completionRoute": "existing_rule|evidence_probe|conservative_proposal|design_inference|alternative_design|parameter|human_decision",
  "proposalIds": []
}
```

`depthDimensionId` is not a Rule ID, Requirement status, or publication title. A missing active dimension may create or link to a stable `REQ-*`, but the existing Requirement and Closure taxonomies remain authoritative.

The only dimension families in this iteration are:

- lifecycle
- state_definition
- entry_trigger
- condition
- repeat_timing
- branch
- exception_interrupt
- data_flow
- calculation_algorithm
- parameter_configuration
- cross_system_dependency
- reset_persistence
- qa_observable_outcome

These are inspection families, not a fixed chapter schema. A Mechanic activates only the families and questions that are applicable to its confirmed behavior.

## 4. Depth Granularity Gate

A Depth Dimension must be an execution question whose coverage can be judged independently.

The gate rejects:

- synonymous fragments of one design decision;
- facets separated only to enlarge the denominator;
- child dimensions whose parent existence signal is absent;
- value, unit, source, and consumer split into separate dimensions when they serve one parameter responsibility;
- implementation event architecture that does not change gameplay, configuration, QA expectations, or player-visible state.

Child activation follows:

```text
parent existence resolved
→ child applicability evaluation
   ├─ core child: active
   ├─ child existence signal found: active
   └─ otherwise: dormant_optional
```

Precise parameters become independent dimensions only when they control different mechanic responsibilities. Otherwise their value, unit, source, consumer, and approval state are Satisfaction Contract facets of one dimension.

## 5. Applicability and Satisfaction

Every dimension first passes the existing Core/Conditional/Optional Applicability Gate.

- `core`: normally required for the minimum executable responsibility of this confirmed Mechanic.
- `conditional`: active only when current Evidence, Fact, Rule, UI, relation, or Approved Design proves the corresponding behavior exists.
- `optional`: dormant by default.

The Existing Coverage Resolver must use the Dimension Satisfaction Contract. A semantically related Rule is not sufficient when it lacks the information required by the execution question.

Example:

```text
Dimension: attack.repeat
Required: repeat existence + repeat trigger + termination condition
Insufficient: “怪物满足攻击条件后攻击”
```

Partial coverage is represented through correctly granular parent/child dimensions. No `partially_resolved` status is introduced.

## 6. Completion Routing

Every active missing dimension follows:

```text
Existing Rule Satisfaction
→ Evidence Observability
→ Planner Relevance
→ AI Design Capability
→ Human Review
```

Routes:

- `existing_rule`: all required Satisfaction Contract facets are supported.
- `evidence_probe`: static or temporal evidence can answer the execution question; temporal state changes use continuous behavior as first-class evidence.
- `conservative_proposal`: strong context or an unambiguous planner default can produce a high-confidence executable answer.
- `design_inference`: AI selects the most compatible playable model using confirmed goals, rules, relations, observed behavior, and planner knowledge.
- `alternative_design`: two or more materially different playable outcomes exist and no single answer is clearly dominant.
- `parameter`: the behavior exists and needs a `{x}` parameter contract without inventing a value.
- `human_decision`: commercial goals, exact economy/weight values, core project intent, or genuinely unresolved alternatives prevent a responsible recommendation.

Observation and causality remain separate. A temporal sequence does not become a causal Rule unless the evidence supports causality.

## 7. Proposal Quality Gates

### 7.1 Information Gain Gate

A proposal must add at least one executable decision:

- trigger or condition;
- state transition;
- object or data relationship;
- repeat/timing behavior;
- branch result;
- interruption or exception handling;
- data source and consumer;
- aggregation/calculation semantics;
- lifecycle/reset result;
- QA-observable outcome.

The following are invalid:

- “开始时开始统计。”
- “满足攻击条件后攻击。”
- “满足升级条件后升级。”
- “按规则计算伤害。”

### 7.2 Compatibility Gate

A recommended design must not conflict with:

- Evidence;
- Confirmed Fact;
- Existing or Approved Rule;
- current UI and temporal behavior;
- upstream/downstream Mechanics;
- current-project objects.

Planner knowledge may support `reasoningBasis`, but never Evidence lineage.

### 7.3 Cross-Proposal Coherence Gate

Within each Mechanic, the gate checks:

- Entry, running behavior, exit, and next state close;
- pause and resume are paired when applicable;
- upstream outputs can be consumed downstream;
- branches have a resulting state;
- repeated rules retain one Primary Mechanic Owner;
- parameter contracts name a Mechanic/Dimension consumer;
- proposals do not contradict Approved Rules or each other.

## 8. Benchmark Depth Profiles

### 8.1 Monster Movement and Attack

Core checks: lifecycle, movement/attack state relationship, movement start, first contact damage, movement target, active contact condition, death/pause/target-loss interruption, contact damage responsibilities, and QA-observable movement/contact/exit/death results.

Conditional checks: periodic/repeated damage processing and interval, target selection/replacement, multiple attackers, pending-damage cancellation, and detailed contact detection semantics. These activate only when the corresponding current-project signal exists. The benchmark profile never pre-activates Repeat from planner prior alone.

First damage timing and periodic repeat timing are independent responsibilities. Attack interval value/unit/source/consumer remain facets of one parameter dimension.

### 8.2 Weapon Acquisition, Slots, and Attack

Core checks: acquisition result, slot/same-weapon handling, activation, attack trigger/method, damage production and weapon attribution, acquisition-to-attack data flow, parameter consumers, and QA-observable acquisition/activation/attack results.

Conditional checks: full-slot handling, replacement/removal, target selection, cooldown or continuous attack, projectile versus persistent-area boundaries, and attached-damage attribution.

### 8.3 Combat Level and Three-choice

Core checks: level-up trigger, pause scope, temporary decision state, candidate result, confirm timing, effect consumer, temporary-state cleanup, exit/resume, consecutive level-up handling, and run lifecycle.

Conditional checks: pool, eligibility, duplicate handling, insufficient pool, refresh, replacement after refresh, refresh cost/count, random algorithm/weight, and cross-run reset. Refresh-related children may activate because refresh exists; weight and pity remain dormant without their own signals.

### 8.4 Independent Weapon Draw

Core checks: entry, battle state during draw, result generation, display-versus-commit boundary, downstream weapon processing, exit/return, temporary-result cleanup, and QA-observable outcome.

Conditional checks: pool, weight, duplicates, abandon/replacement, animation-skip relation, cost, pity, and cross-run accumulation.

### 8.5 Normal Stage, Boss, and Level Completion

Core checks: normal-stage exit, Boss entry/initialization, Boss running state, Boss termination, post-Boss battle state, formal level-completion condition, next state, success/failure interruption, and QA-observable stage transitions.

Conditional checks: residual-enemy cleanup, presentation/progression completion condition, Boss subphases, timeout, respawn, and stage parameter sources. Boss HP reaching zero and formal level completion remain separate dimensions.

### 8.6 Damage Statistics

Core checks: window start, statistical object/unit, attribution semantics, aggregation, total-versus-per-weapon relationship, behavior during pause screens, end/freeze, settlement consumption, run reset, and QA-verifiable results.

Conditional checks: attached-effect attribution, live refresh, DPS, ranking, share formula, unattributed damage, and multiple-instance merging. Bottom-level event/listener architecture is Planner-irrelevant and excluded.

### 8.7 Outcome and Settlement

Core checks: success trigger, failure trigger, result lock, combat termination scope, settlement entry, outcome branches, settlement inputs, exit/next state, player-visible duplicate-trigger behavior, and QA-observable terminal states.

Conditional checks: success/failure priority, pending-event handling, reward calculation, record writes, retry, and cross-run persistence. Pure implementation de-duplication is excluded unless it changes the player-visible result.

## 9. Outputs

This iteration produces Review/Audit Layer artifacts only:

- `execution-depth-profiles.json`
- `execution-depth-coverage.json`
- `execution-depth-expansion-preview.md`
- `execution-depth-lineage.json`
- `execution-depth-quality-gate.json`

For each Mechanic, the preview reports:

1. Structural Completeness
2. Current Execution Depth Coverage
3. Applicable Depth Dimensions
4. Existing Covered
5. AI-direct completion
6. Alternative Design
7. Parameter
8. Human Decision
9. Projected Coverage
10. Evidence/Rule/Requirement lineage

Engineering IDs remain in JSON lineage and do not become review titles.

## 10. Quality and Test Boundaries

Production code must not read benchmark Gold fixtures. Gold defines only what should be checked under the current fixture conditions and stores no project answers.

The implementation must test:

- stable Depth Dimension IDs;
- Core/Conditional/Optional activation;
- parent existence gating;
- Satisfaction Contract precision;
- Depth Granularity Gate duplicate suppression;
- Information Gain rejection;
- Compatibility/Coherence routing;
- current versus projected coverage calculation;
- parameter facet accounting;
- no Gold access from production;
- no Final Publication, Planning Hierarchy, `job.json`, Rule, Fact, Evidence, Requirement status, or Approved Data mutation.

## 11. Hard Boundaries

- No new Pipeline phase.
- No new Requirement closure status.
- No fixed chapter schema.
- No new Approved Rule in this iteration.
- No Planning Hierarchy changes.
- No Final Publication changes.
- No `job.json` changes.
- No GVE16 project rule, value, field, formula, or lifecycle answer migration.
- No Depth Dimension as a publication heading.
- No claim that the seven benchmark profiles are a complete universal planner library.

## 12. Exit Criteria

The implementation iteration is complete only when it outputs all seven benchmark profiles with independently auditable current/projected coverage, passes every quality gate above, and proves zero mutation of prohibited sources and outputs.

It does not claim final GVE16 alignment success. After this review-only depth expansion is accepted, proposals proceed through the existing Review → Approved Rule → Requirement Closure → RuleChain → Final Publication loop before A–J is recalculated.
