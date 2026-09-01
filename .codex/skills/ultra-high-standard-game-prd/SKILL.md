---
name: ultra-high-standard-game-prd
description: Upgrade an evidence-backed gameplay or interaction draft into a precise, implementation-ready, GVE16-compatible PRD with explicit structures, states, rules, flows, uncertainties, and acceptance criteria. Use for high-standard planning output, sample-matched PRDs, gameplay specifications, or interaction specifications.
---

# Ultra-High-Standard Game PRD

Absorb the useful precision rules from `ultra-high-standard-prd` while keeping video evidence authoritative.

## Upgrade Rules

1. Define the scene/page and component tree before presentation details.
2. Replace vague behavior with explicit trigger, prerequisite, target, system response, resulting state, feedback, and failure path.
3. Preserve exact visible values; do not invent pixels, timing, economy values, or hidden rules from style conventions.
4. Label each statement as observed, inferred, default, or unknown. Defaults and inferences never become facts.
5. Use stable IDs so tables, UE flows, acceptance criteria, and design handoff reference the same entities.
6. Add loading, empty, error, permission, retry, cancellation, input lock, and responsive states only as observed facts or explicit pending confirmations.
7. Write acceptance criteria that can be checked against timestamps and implementation recordings.

## Mode Requirements

- Gameplay: objective/fantasy, core loop, player operations, causal chains, state machine, rules, resources/values, win/loss/settlement/retry, feedback, HUD.
- Interaction: user goal, task flow, pages/dialogs, component hierarchy, events, states/validation, motion, assets/content, errors, device/responsive unknowns.

Run `$planning-quality-auditor` after upgrading and keep unresolved items visible.
