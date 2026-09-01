# Full Mechanic Reconstruction Design

## Goal

Reconstruct three high-value mechanics as mature, review-layer execution models:

1. 战斗等级与三选一
2. 武器获取、栏位与攻击
3. 普通怪物移动与攻击

The remediation unit is a complete Mechanic Model, not an individual Depth Dimension. The output must let a lead planner review an executable design chapter rather than answer a list of gaps.

This iteration does not create Approved Rules, close Requirements, modify Final Publication, change Planning Hierarchy, or write `job.json`.

## Acceptance Model

Acceptance has two separate stages:

- Remediation acceptance evaluates the reconstructed model, Projected Design Coverage, Core Design Depth Coverage, executable information density, compatibility, and lifecycle coherence.
- After lead-planner Accept/Edit, accepted design items become Approved Rules with Requirement lineage. Only then are Current Coverage, Requirement Closure, RuleChain Reconstruction, Final Publication, and GVE16 A–J rescored.

Projected Design Coverage remains diagnostic. A score of 100% does not prove mature execution depth and cannot stop reconstruction.

## Authoritative Inputs

Each reconstruction may consume:

- Existing and Approved Logic Rules with deterministic lineage;
- current video and screenshot Evidence, including temporal observations;
- existing AI Design Proposals;
- a mechanic-aware depth profile;
- planner common sense;
- GVE16 Planner Knowledge as an execution-question prior only.

GVE16 content has no project rule authority. Prior knowledge may propose what should be defined but may not supply current-project facts or masquerade as Evidence.

## Reconstruction Boundary

The runtime may discover second- and third-order execution questions beyond the current Active Depth Dimension list. New questions must pass:

- mechanic existence and applicability gates;
- Depth Granularity Gate;
- Planner Relevance Gate;
- Information Gain Gate;
- compatibility with Existing Evidence, Facts, Rules, UI, and upstream/downstream mechanics.

Discovery must not inflate the denominator with synonyms, implementation events, presentation details, or parameter facets that do not carry distinct mechanic responsibility.

## Mechanic Model Contract

Every reconstructed model contains:

- core objects and owned state;
- lifecycle and ordered execution flow;
- triggers and conditions;
- running behavior;
- applicable branches and repeat behavior;
- interrupts and exceptions;
- data flow and ownership;
- algorithms or calculations when applicable;
- parameter contracts with consumer, meaning, unit/type, source, and review/config state;
- cross-system dependencies and structured references;
- reset and persistence boundaries when applicable;
- QA-observable outcomes;
- lineage to Evidence, Rule, Requirement, and Atomic Proposal sources;
- unresolved differences from GVE16-level execution depth.

The Review Layer must distinguish Confirmed, Conservative Proposal, Design Inference, Alternative Design, Parameter Placeholder, and genuine Human Decision. None of these review labels enter Final Publication.

## Model-specific Reconstruction

### 战斗等级与三选一

The model must cover the complete Candidate and Decision Lifecycle:

`level-up trigger → pause/freeze scope → candidate pool → eligibility → generation → temporary result → refresh branch → confirmation → effect application → cleanup → resume`

It must actively evaluate, when applicable:

- candidate source and eligible content;
- exclusion and duplicate handling;
- pool-shortage behavior;
- candidate stability before confirmation;
- refresh consumption, regeneration, and old-result invalidation;
- confirmation boundary and write target;
- failure handling when application cannot complete;
- transient-state cleanup;
- repeated level-up handling, activated only by a current-project existence signal;
- run-scoped reset and persistence.

### 武器获取、栏位与攻击

The model must cover the Weapon Instance, Slot, Activation, and Attack Lifecycle:

`acquire → classify result → slot handling → create/upgrade/replace instance → activate → select target → attack cycle → damage and attribution → interrupt → removal/reset`

It must actively evaluate, when applicable:

- weapon instance identity and ownership;
- new versus duplicate result classification;
- empty-slot, full-slot, upgrade, replacement, and rejection branches;
- activation timing and combat eligibility;
- target validity and retargeting;
- continuous versus interval-based attack execution;
- cooldown/interval consumer and timing boundary;
- damage ownership and statistics handoff;
- interruption by pause, result lock, target invalidation, and removal;
- replacement/removal cleanup and parameter ownership.

Full-slot handling is a genuine design fork and may expose 2–3 alternatives. Other ordinary lifecycle closures should use one recommended design.

### 普通怪物移动与攻击

The model must cover a complete Behavior State Model:

`enter/spawn → acquire target → move → detect contact/attack condition → damage execution → repeat → exit contact → resume/transition → interrupt/death → cleanup`

It must actively evaluate, when applicable:

- behavior states without inventing unsupported project state names;
- target validity and reacquisition;
- contact/attack condition evaluation;
- first-damage timing;
- repeat existence before expanding interval children;
- movement lock while damage processing is active;
- separation between observed sequence and causal rule;
- multiple attackers;
- pause/resume semantics;
- death, target invalidation, and pending-damage handling;
- parameter consumers and QA-observable transitions.

## Mechanic-level Synthesis Output

Each model produces one review artifact containing:

1. Before Mechanic Model;
2. structural root cause;
3. Reconstructed Mechanic Model;
4. newly discovered high-value depth questions;
5. recommended executable answers;
6. true design alternatives only;
7. parameter contracts;
8. cross-system dependencies and references;
9. ordered flow or state model;
10. QA verification model;
11. remaining GVE16-depth gaps;
12. before/after metrics and lineage.

The default presentation is a coherent mechanic chapter. Atomic dimensions and proposals remain expandable metadata and must not become one-dimension-per-heading output.

## Core Design Depth Coverage

Core Design Depth Coverage is separate from Projected Design Coverage. Its denominator contains only applicable core execution responsibilities:

- state model;
- trigger and condition model;
- branch and repeat model;
- algorithm/calculation model when applicable;
- data-flow and ownership model;
- lifecycle, interrupt, exit, and reset model;
- cross-mechanic dependency model.

QA outcomes, presentation, document length, proposal count, rule count, and auxiliary parameter completeness do not increase this score. Parameter responsibilities count only when the parameter changes a core mechanic decision and has a defined consumer.

A responsibility is covered only when one or more coherent design items provide executable decisions and pass Information Gain, Compatibility, and Coherence gates. Placeholders and generic statements never count.

## Structural Remediation Gates

Each reconstructed model must pass:

- lifecycle closure: entry, running behavior, exit, next state, and applicable reset are connected;
- branch closure: each branch has a consequence and follow-up state;
- repeat closure: repeat existence, condition, timing consumer, and interruption are consistent;
- data-flow closure: upstream output maps to a downstream consumer and owned state;
- rule reuse: every rule has one Primary Mechanic Owner; other mechanics use structured references;
- compatibility: no recommended item conflicts with Confirmed Evidence, Fact, Rule, UI, or object model;
- information gain: every proposed item adds an executable condition, state change, branch, calculation, data relation, lifecycle result, configuration meaning, or QA-relevant boundary;
- granularity: no synonymous question splitting or implementation-event inflation.

## Success Criteria

For each focus mechanic:

- the reconstructed model must visibly progress from a gameplay summary to an execution model;
- Projected Design Coverage must improve by at least 20 percentage points or reach at least 80%;
- Core Design Depth Coverage must reach at least 80%;
- the model must pass all structural remediation gates;
- the result must require more than a five- or six-sentence summary to preserve its executable decisions;
- Human Decisions are limited to genuinely project-specific intent, exact commercial choices, or unresolved true forks.

Across the three mechanics:

- the lowest three models must materially improve;
- no gain may come from additional easy dimensions, weaker Satisfaction Contracts, placeholders, duplicated generic rules, or word/rule/proposal counts;
- the review artifact must show the complete Candidate Lifecycle, Weapon Lifecycle, and Monster Behavior State Model.

If a model fails the threshold, the iteration is classified as a root-cause failure. It must not continue with isolated Dimension patches.

## TDD Seams

Tests exercise public behavior at three seams:

1. `reconstruct_mechanic_model(inputs) -> MechanicReconstruction`
   - discovers applicable higher-order questions;
   - synthesizes a coherent model;
   - preserves knowledge class and lineage.
2. `evaluate_core_design_depth(model, contract) -> CoreDepthResult`
   - independently scores core responsibilities;
   - excludes QA, presentation, placeholders, and unrelated parameter facets.
3. benchmark generation command
   - emits exactly three model-level Review artifacts;
   - reports before/after structural metrics and gates;
   - proves Final Publication, Planning Hierarchy, Rule/Requirement state, and `job.json` are unchanged.

Gold expectations are test-only and must not be read by production code.

## Explicit Non-goals

- no Approved Rule generation;
- no Requirement status mutation;
- no Final Publication or Planning Hierarchy changes;
- no `job.json` write;
- no new Pipeline phase or closure taxonomy;
- no hardcoded final chapter schema;
- no GVE16 project-rule migration;
- no remediation of the remaining four benchmark mechanics in this iteration.
