---
name: long-video-gameplay-planner
description: Analyze 10–20 minute gameplay demonstration videos and produce evidence-backed game design documents. Use when Codex must reconstruct player goals, operations, core loops, rules, state machines, scoring, resources, win/loss conditions, feedback, or unknowns from gameplay footage and timestamped keyframes.
---

# Long Video Gameplay Planner

## Workflow

1. Verify that the full video duration was scanned; never infer the whole design from an opening clip.
2. Read scene groups, timestamped frames, ScreenCoder region trees, component tracks, and asset candidates.
3. Reconstruct causal chains as `before state → player input → rule evaluation → feedback → after state`.
4. Separate observed facts, reasonable inferences, and unknowns. Downgrade confidence when only a static frame supports a temporal claim.
5. Derive the core loop only after comparing repeated event chains across scenes.
6. Produce the document using [references/gameplay-schema.md](references/gameplay-schema.md).
7. Ensure every material rule links to scene IDs, frame IDs, and timestamps.

## Rules

- Do not treat ordinary navigation as a gameplay mechanic.
- Do not invent backend values, complete level tables, monetization, or unshown states.
- Preserve short-lived feedback such as score popups, combo effects, particles, health changes, and screen shake.
- List missing pause, retry, interruption, and recovery states as open questions.
- Prefer causal and state language over visual-only descriptions.

## Gameplay System Decomposition

- Build the directory as `gameplay systems -> cohesive mechanisms -> detailed rules`; do not place every detected mechanic under one catch-all system.
- Split top-level systems when mechanisms have materially different player goals, operated entities, resources, state machines, lifecycle/reset rules, implementation owners, or independent acceptance boundaries. Combat progression, territory acquisition, formation setup, growth effects, and settlement are separate systems when the evidence supports those boundaries.
- Keep mechanisms together when they are successive steps of one loop and share the same entity, resource flow, state lifecycle, and acceptance outcome.
- A single top-level system is allowed only when the evidence truly describes one inseparable loop. Never manufacture extra systems to satisfy a fixed count.
- Before detailed generation, audit the proposed hierarchy. If many heterogeneous mechanisms sit under one feature name, return to system classification instead of treating that feature name as the entire gameplay.
