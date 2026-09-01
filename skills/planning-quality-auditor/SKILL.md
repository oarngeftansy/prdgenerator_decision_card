---
name: planning-quality-auditor
description: Audit gameplay and interaction planning documents against timestamped video evidence. Use when Codex must check coverage, causal accuracy, evidence links, uncertainty discipline, terminology consistency, missing states, unreachable flows, unsupported claims, or readiness for implementation and acceptance.
---

# Planning Quality Auditor

## Workflow

1. Read the plan, fact table, scene specifications, review queue, and evidence index.
2. Verify coverage of every material scene and event.
3. Trace rules and behavior claims to timestamps and evidence frames.
4. Check causal completeness, state reachability, terminology, and confidence labels.
5. Penalize unsupported certainty more heavily than explicit unknowns.
6. Score and report findings using [references/audit-rubric.md](references/audit-rubric.md).
7. Return blocking issues, important improvements, and optional refinements separately.

## Rules

- Do not award evidence credit for a link that points to the wrong state or time.
- Do not require unshown product behavior to be specified as fact.
- Keep gameplay mechanics separate from navigation and presentation.
- Treat unresolved critical causal gaps as delivery blockers.
