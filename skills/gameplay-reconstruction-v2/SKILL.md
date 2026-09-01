---
name: gameplay-reconstruction-v2
description: Reconstruct underlying gameplay systems and mechanisms from screenshots, video and reviewed evidence without stopping at visible presentation.
---

# Gameplay Reconstruction v2

## Objective

Recover the playable system behind the observed presentation. Visual events are evidence inputs, not the final level of description.

## Required reconstruction dimensions

- Core loop and player objective.
- System -> subsystem -> mechanism hierarchy.
- Entities, resources, states and events.
- Trigger, precondition, execution, result and exit conditions.
- State transitions and lifecycle.
- Random pools, eligibility filters, draw count, duplicate rules, rerolls and empty-pool behavior.
- Progression, combination and in-run growth.
- Wave/spawn/progression cadence when relevant.
- Combat targeting, damage, death and cleanup when relevant.
- Economy/source/sink/settlement when relevant.
- Cross-system dependencies and reset/persistence boundaries.

## Authority rules

1. Confirmed evidence remains authoritative for what is directly established.
2. Missing evidence does not prohibit mechanism reconstruction. When the source mechanic is strongly implied by observed behavior and system context, reconstruct a concrete rule and mark its provenance as `inferred` outside the visible rule copy.
3. Never write provenance labels such as “推断”“可能”“待确认” into the rule sentence itself.
4. Do not invent implementation-specific class names, IDs or configuration field names that are not supplied.
5. A screenshot-level description is incomplete if it does not explain the gameplay mechanism that makes the observed state reachable.
6. Directory/chapter count is not fixed. Derive structure from the reconstructed systems and mechanisms.

## Completion criterion

Reconstruction is complete when downstream planning can identify each material mechanism, its state/lifecycle/dependencies, and any remaining implementation decisions that must be closed by the Execution Planning skill.
