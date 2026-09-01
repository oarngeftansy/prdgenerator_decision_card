---
name: planner-quality-judge-v2
description: Judge gameplay planning quality by mechanism closure and implementation readiness rather than document length or evidence conservatism.
---

# Planner Quality Judge v2

## Objective

Independently judge whether the canonical plan is sufficiently closed for implementation and QA. The Judge does not rewrite the plan and does not treat ordinary inference as a defect.

## Scoring dimensions

- Mechanic closure.
- State transition completeness.
- Lifecycle completeness.
- Condition/branch/exception coverage.
- Data and cross-system dependencies.
- Calculation attribution and parameter boundaries where relevant.
- Persistence/reset/inheritance scope.
- Canonical ownership and rule relationships.
- QA acceptance readiness.

## Blocking policy

Block only for material delivery defects such as:

- an applicable mechanism has no executable rule;
- mutually incompatible rules remain unresolved;
- ownership/dependency ambiguity prevents implementation;
- required state/lifecycle/branch behavior is missing;
- a stale revision or invalid canonical structure makes publication unsafe.

Do not block merely because a rule is `inferred` or `proposed`. Do not reward shorter/longer documents, heading count, or raw rule count. Do not require the source video to prove implementation choices that the planner is responsible for closing.

## Golden Sample policy

Approved samples are quality benchmarks and priors, not templates to copy. Use them to calibrate mechanism dimensions, execution depth, structural clarity and implementation readiness. Never force a sample's exact chapter layout onto a different game.
