---
name: visual-prd-reconstruction
description: Interpret finished vibe-coding web project demo videos and screenshots, as well as gameplay demo videos, through an AI-first staged workflow: extract key frames, use a vision model to explain what each frame shows, what requirement it implies, and the visual/motion/gameplay details, ask the user to confirm/correct the AI frame interpretations, then generate a concise PRD only from confirmed frames. Use when the user uploads final product showcase videos/images and wants a PRD, clone spec, one-to-one reconstruction, "关键帧确认后生成PRD", "视频转需求文档", "vibe coding 小项目复刻", "玩法Demo复刻", "游戏原型拆解", or "看成品演示写需求". Avoid direct long PRDs before AI frame interpretation and user confirmation.
---

# Visual PRD Reconstruction

## Purpose

Use this skill for final showcase videos or screenshots of vibe-coding web projects and gameplay demos. The correct workflow is:

1. Extract key product frames.
2. Use a vision model to explain each frame.
3. Let the user confirm or correct the explanations.
4. Generate a concise PRD from confirmed frames only.

## Step 1: Extract Key Frames

Sample meaningful product states:

- landing / hook screen.
- first CTA or entry point.
- create/edit screen.
- user input state.
- option selection state.
- live preview or generated output.
- submit/share action.
- result/shared viewer page.
- restart/create-your-own loop.

Ignore non-product visual noise: device frame, browser chrome unless route matters, hands, desk, room, camera angle, and social media overlay text unless it describes product steps.

## Step 2: AI-Explain Each Frame

For every key frame, call the available vision model first. Capture:

- Evidence ID.
- What this frame shows.
- What the user is doing or seeing.
- Product state.
- Requirement implication.
- Typography/layout formula and visual skeleton.
- Visual/font/composition/style details.
- Motion/transition/state feedback details.
- **For gameplay demos**: game mechanics, game state (menu/playing/victory/defeat), scoring/feedback system, core loop.
- Confidence and unknowns.

Do not leave frame interpretation blank for the user to fill from scratch. The user reviews and corrects AI output.

## Step 3: User Confirmation

Ask the user to confirm, edit, remove, or merge frame interpretations. The PRD should use only confirmed frame interpretations.

## Step 4: Concise PRD

Include:

1. Product summary.
2. Confirmed evidence table.
3. User flow / game flow.
4. Pages/states / game states.
5. Functional requirements.
6. Data and interaction rules.
7. **For gameplay demos**: game mechanics, core loop, game state machine, scoring and feedback system.
8. Component-level reconstruction requirements.
9. Visual reconstruction requirements.
10. Motion and feedback requirements.
11. Acceptance criteria.
12. Codex implementation prompt.

Avoid oversized PRD sections unless the user explicitly asks for a detailed product document.

## Frame Interpretation Format

Use this format before PRD generation:

| Evidence | Frame interpretation | Requirement implication | Layout formula | Visual style | Motion/feedback | Confidence | Needs user check |
|---|---|---|---|---|---|---|---|

## Typography Formula Layer

Use the bundled 54-formula typography model when interpreting visual frames. Read [references/formulas.md](references/formulas.md) when the task needs detailed layout diagnosis.

For every frame, identify 1-3 likely formulas and explain the visual skeleton:

- focal point and first visual hit.
- visual path: centered, circular, diagonal, column, collage, curve, top/down, left/right.
- whitespace ratio and density.
- hierarchy: type scale, weight, image scale, decorative layer.
- material formula: paper, glass, grain, tape, textile, shadow, torn edge, pixel, sticky note, etc.
- whether the frame uses a formula as the primary structure or only as decoration.

Never describe layout only as "clean", "nice", "simple", or "advanced". Translate it into a formula and implementation constraint.

## Visual And Motion Requirements

For visual details, capture:

- typography style and hierarchy.
- layout, alignment, spacing, and composition.
- formula-driven composition: full-screen, faded, circular, floral, module, symmetry, asymmetry, centered, line, border, white-space, column, curved, retro, minimalist, collage, glass, dynamic, overlapping, shadow, grainy, sticky-note, golden-ratio, etc.
- color palette and contrast.
- material style, borders, shadows, radius, cards, paper/glass/3D/flat treatment.
- generated artifact style.
- image, icon, illustration, and asset style.

For motion details, capture:

- page transitions.
- card flips, fades, slide-ins, scale, reveal, or hover/click feedback.
- live preview update behavior.
- loading/submission/share feedback.
- button enabled/disabled transitions.

If no motion is visible, state that the frame should be implemented as a static state, and mark any proposed motion as inference.

## Rules

- Never treat unconfirmed frame interpretations as final PRD facts.
- Do not invent exact copy if it is unreadable.
- Mark inferred routes, backend persistence, share IDs, and hidden states as inference.
- Keep output in the user's language; use Chinese by default for Chinese requests.
