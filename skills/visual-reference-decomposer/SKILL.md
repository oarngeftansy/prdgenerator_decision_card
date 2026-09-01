---
name: visual-reference-decomposer
description: Decompose screenshots or video scenes into visual foundations, page or scene topology, component specifications, behaviors, assets, and visual-QA checks. Use when absorbing a reference product, website, game UI, or interaction demo into an implementation-ready planning specification.
---

# Visual Reference Decomposer

Adapt the useful decomposition and QA methods from `ai-website-cloner-template` to video-driven planning. Do not assume Next.js, Tailwind, or browser access unless the target actually uses them.

## Workflow

1. Establish source viewport, visual states, fonts, colors, spacing, icons, images, and recurring containers.
2. Build scene/page topology before writing isolated component descriptions.
3. Perform an interaction sweep: trigger, target, before state, response, after state, animation, and failure/unknown path.
4. Write one specification per meaningful scene or page with evidence IDs and reusable assets.
5. Compare planned topology, component inventory, behavior, and visual hierarchy against the source.
6. Record mismatches as acceptance issues, not silent approximations.

## Video Adaptation

- Replace browser screenshots with timestamped keyframes and scene representatives.
- Replace route discovery with scene/page/dialog state discovery.
- Replace DOM inspection with ScreenCoder region trees plus visual-model semantics.
- Preserve the original clone workflow's desktop/mobile and behavior checks only when those states are visible or explicitly requested.

## Output

Produce foundations, topology, scene/component specs, interaction inventory, asset inventory, and a visual/behavior QA checklist suitable for `$gve16-planning-schema`.
