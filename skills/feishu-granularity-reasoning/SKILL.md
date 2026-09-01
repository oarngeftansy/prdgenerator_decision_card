---
name: feishu-granularity-reasoning
description: Use when turning screenshots, video, reference documents, configuration tables, or planner decisions into a Feishu gameplay PRD whose claims are traceable, whose depth follows the available evidence, and whose prose does not use fixed mechanism templates.
---

# Feishu Granularity Reasoning

## Purpose

Produce implementation-useful gameplay prose by separating three decisions: what the evidence proves, what this mechanism needs to answer, and which carrier expresses each fact most clearly. Read [references/provenance-rules.md](references/provenance-rules.md) before generating or auditing a chapter.

## Workflow

1. Inventory evidence before drafting. Keep screenshot facts, video sequence, reference-document rules, configuration fields, planner decisions, and context inference distinct.
2. Write one provenance record per business claim. Context inference must include premises, reasoning steps, competing explanations, confidence, and an explicit publication decision.
3. Decide which depth dimensions apply. The minimum six are content inventory, configuration, execution sequence, formula, boundary, and lifecycle. Also check interaction/feedback, runtime responsibility, and presentation/carrier authority. A dimension applies only when evidence or a confirmed planner decision supports it.
4. Choose the carrier. Put behavior and intent in prose, enumerated objects in a list, repeated fields in one table, spatial/state relations in a board, and formulas in a formula block. Do not repeat the same fact across carriers.
5. Organize by the mechanism's causal shape. Lead with the player goal or entry condition, then the system action and response. Put a short failure or reset clause in the same paragraph; split a section only when it has several independently useful rules.
6. Run the provenance and six-axis audit. Missing applicable depth blocks generation, P7 preview, and Feishu publication. Inapplicable axes stay absent.

## Writing Rules

- Prefer a condition-action-result sentence: “满足条件后，系统执行动作；结果如何反馈或保留。”
- Number only a real ordered algorithm. Do not number descriptive facts.
- Merge several short sibling mechanisms under one business heading; strip redundant suffixes such as “机制” and “状态管理” from paragraph labels.
- Do not restate fields already visible in the adjacent configuration table.
- Do not infer formulas, probability, refresh behavior, persistence, reset timing, or server ownership from a screenshot alone.
- Do not write “待确认” as body copy. When multiple explanations remain plausible, create a planner decision card; before a choice is made, exclude that proposition from confirmed prose.

## Stop Conditions

Stop publication when a supported axis is missing, a claim has no source category, or an inference chain cannot eliminate a material alternative. Do not stop merely because an unsupported axis is absent.

## Transfer Test

Before treating a new rule as reusable, test it on non-sample material in two passes: first build only the fact model and an explicit excluded-inference list, then independently organize the prose. Run at least one sparse mechanism, one interaction/feedback mechanism, and one real ordered algorithm. Their carriers and section counts should differ when their causal shapes differ. Reject the rule if it copies sample names, values, headings, or forces the same section layout onto a different mechanism.

## Traceability Gate

Do not call the distillation complete until every technique has a current source block, content-selection rationale, language rationale, Skill rule, project location, regression test, and observable generation/P7/Feishu effect. The project calibration file `data/calibration/gve16/skill-traceability.json` is the canonical mapping. A research insight without project behavior, or a project gate without a source or explicit user requirement, is an orphan and fails the gate.
