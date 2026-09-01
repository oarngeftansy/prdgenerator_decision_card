---
name: temporal-event-reconciler
description: Reconcile frame-level and scene-level video analysis into a consistent temporal model. Use when Codex must merge duplicate events, normalize state and component names, detect causal gaps or contradictions, build a global fact table, and connect operations across gameplay or product interaction scenes.
---

# Temporal Event Reconciler

## Workflow

1. Order all scenes, frames, component observations, transcripts, and sound cues by timestamp.
2. Normalize synonymous component, page, game-state, action, and feedback names.
3. Merge duplicate event descriptions that refer to the same temporal transition.
4. Validate each `before → input → response → after` chain against neighboring evidence.
5. Detect impossible transitions, unexplained state changes, conflicting values, and identity changes.
6. Produce a fact table and conflict queue using [references/reconciliation-schema.md](references/reconciliation-schema.md).
7. Preserve alternatives when evidence cannot resolve a conflict.

## Rules

- Prefer direct temporal evidence over scene summaries.
- Never repair a contradiction by inventing an unshown event.
- Keep confidence and evidence levels attached after merging.
- Treat stable component tracks as stronger identity evidence than visual labels alone.
