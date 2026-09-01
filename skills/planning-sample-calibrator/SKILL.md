---
name: planning-sample-calibrator
description: Learn reusable gameplay or interaction planning standards from benchmark pairs containing an original video and an approved planning document. Use when Codex must derive schemas, terminology, evidence-to-conclusion rules, writing style, required sections, quality rubrics, or regression cases from user-provided gold examples.
---

# Planning Sample Calibrator

## Workflow

1. Pair each approved document statement with supporting video scenes, frames, and timestamps.
2. Classify the statement as observed, inferred, externally supplied, or unsupported.
3. Extract required sections, field granularity, terminology, tone, and table conventions.
4. Separate shared rules from gameplay-only and interaction-only rules.
5. Create or update schemas, prompt rules, document templates, and evaluation fixtures.
6. Score a fresh tool output against the approved document using [references/calibration-rubric.md](references/calibration-rubric.md).
7. Preserve unresolved disagreements as explicit calibration questions.

## Rules

- Never learn unsupported claims as video inference rules.
- Do not overfit wording from one sample; require repeated evidence before making a rule mandatory.
- Keep source-specific names separate from reusable terminology.
- Version calibration rules whenever a benchmark changes expected behavior.
