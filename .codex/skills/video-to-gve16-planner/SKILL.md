---
name: video-to-gve16-planner
description: Orchestrate the complete 10–20 minute video-to-planning workflow, routing gameplay or interaction recordings through evidence extraction, ScreenCoder UI understanding, temporal reconciliation, GVE16 modeling, sample calibration, high-standard PRD generation, quality audit, and optional design handoff.
---

# Video to GVE16 Planner

This is the default orchestrator for the website's 玩法 and 交互 modes.

## Required Chain

1. Use `$video-evidence-extractor` for full-timeline scanning, scene detection, deduplication, and dense transition sampling.
2. Use `$screencoder-video-ui-analyzer` for region trees, components, tracks, state deltas, and asset candidates.
3. Use `$video-audio-evidence-aligner` when speech, subtitles, UI text, or sound cues add evidence.
4. Use `$temporal-event-reconciler` to merge frame/scene facts and close causal chains.
5. Route gameplay to `$long-video-gameplay-planner`; route interaction to `$long-video-interaction-planner`.
6. Use `$planning-sample-calibrator` with the default GVE16 profile and approved examples.
7. Build and validate `$gve16-planning-schema`.
8. Upgrade wording and implementation detail with `$ultra-high-standard-game-prd`.
9. Run `$planning-quality-auditor`; do not hide unresolved evidence or contradictions.
10. Call `$gve16-feishu-whiteboard` for screenshot-first native Feishu UE boards; use `$planning-to-design-handoff` for other design targets.

## Completion Gate

- Full video duration is covered, including both example levels when supplied.
- Each core event has before state, input, response, after state, evidence, and confidence.
- Gameplay and interaction chapters follow their respective GVE16 schemas.
- The gameplay directory has passed a system-boundary audit: distinct goals, entities, resource loops, state lifecycles, and independently testable outcomes are not flattened into one catch-all chapter.
- Multi-step pages advance from the canonical response state. Confirming P1 system groups must render the P1 mechanism step, keep `ui=gameplay_directory`, and reset the review canvas to the new step; only the final P1 confirmation may enter interaction review.
- Every P1–P7 result action has a visible planner-facing gate beside it: name the remaining work, explain why the action is disabled, and name the exact destination after completion. A disabled button or percentage without this copy is a product failure. The gate may stay sticky inside the content flow but must never overlay review content, decision cards, or controls.
- Human-readable Markdown and `planningModel` agree on IDs and conclusions.
- External design artifacts are claimed only after connector success.

## Runtime Credential Gate

- Treat the API base URL, model name, and API Key as separate runtime inputs. A saved task may restore the first two, but must never persist or expose the user's API Key in task data.
- Before every model-triggering action—including first analysis, failed-task retry, whole-job reinterpretation, single-frame reinterpretation, and automatic completion—verify that the current browser session or trusted server configuration has a Key.
- If credentials are missing, open the model settings and stop before sending any request. Do not run a no-model placeholder pipeline and do not report its `0 qualified / 0 request failures` result as a content-quality failure.
- A valid retry must reuse the failed task ID and preserved evidence, submit the current credentials, and record `modelEnabled=true` plus a non-zero model-call count before quality evaluation begins.

## Workbench Entry Contract

- The delivery summary card must expose separate actions for `进入工作台` and `生成完整策划案`; entering review and generating a document are different user intents and must not share one ambiguous button.
- `进入工作台` restores the current task and its saved P1–P7 view when a review model exists. It must not redirect to an unrelated recent task.
- If the current task has not produced a review model, keep the entry visible but explain that analysis must finish first; do not pretend that an empty workspace was opened.
