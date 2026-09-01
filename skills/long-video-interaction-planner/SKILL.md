---
name: long-video-interaction-planner
description: Reconstruct product interaction specifications from 10–20 minute screen recordings. Use when Codex must identify user tasks, pages, dialogs, component hierarchies, click/drag/swipe/scroll/input behaviors, before/after states, transitions, validation, errors, responsive unknowns, and timestamped evidence.
---

# Long Video Interaction Planner

## Workflow

1. Confirm full-duration coverage and scene boundaries.
2. Read ScreenCoder region trees, component tracks, visible assets, scene summaries, and detailed event frames.
3. Classify each interaction as click, tap, long-press, drag, swipe, scroll, input, wait, time-driven, or unknown.
4. Reconstruct `before state → user input → system response → after state`.
5. Track persistent components across frames and record appearance, disappearance, enablement, selection, and content changes.
6. Produce the specification using [references/interaction-schema.md](references/interaction-schema.md).
7. Mark unshown loading, empty, error, permission, network, validation, and responsive states as unknowns.

## Rules

- Do not infer DOM, exact CSS, or breakpoint values from video alone.
- Do not convert scroll-driven behavior into click tabs without temporal evidence.
- Capture transient feedback and animation stages, not only stable screens.
- Link every important behavior to scene IDs, frame IDs, and timestamps.
