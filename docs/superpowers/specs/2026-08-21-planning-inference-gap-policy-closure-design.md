# Planning Inference & Gap Policy Closure Design

## Goal

让结构化规则链在不放松高风险 Guard 的前提下，将安全闭环补全为策划规则、将中风险补全变成可审核 Proposal，并阻止 Technical Gap 污染 Final。

## Authority model

- `infer_and_publish`: 仅使用已确认 Rule/Fact，生成 `inferenceLevel=planner_inference` 的派生 Rule，保留 `sourceRuleIds/sourceFactIds`。
- `infer_with_review`: 生成 Review Proposal；确认前不可进入 Publication。
- `evidence_required`: 保持 Gap，不生成确定性规则。
- Hard Guard 始终禁止 Pattern→Formula、Random→Equal Probability/Without Replacement/Weight/Guarantee，以及视觉观察→隐藏玩法规则。

## Gap model

Gap 新增 `gapDomain`、`inferencePermission`、`applicabilityStatus` 和可选 `proposalId`。Schema Slot 必须先经过 Applicability Check；没有机制存在证据的 optional/conditional 高风险 Slot 记为 `not_observed`，不生成 blocking Gap。Technical Gap 留在内部审计，Final 只展示 Planning Gap。

## Architecture

声明式知识图谱保存通用 Closure inference policy；通用引擎根据已确认 intent/slot 组合匹配策略，生成派生 Rule 或 Proposal。项目特定文案、标题、品类标签和 Pattern 不参与激活。`build_rule_intelligence_projection` 是规则/Proposal/Gap 权威 seam，`build_final_document` 是最终污染防线。

## Test seams

1. `build_rule_intelligence_projection`: T1、T3、T4、T5、T6。
2. `build_final_document`: T2，并验证未审核 Proposal 不发布。

## Scope exclusions

不改 UI，不改 Temporal Pipeline，不扩完整 taxonomy，不新增玩法特判，不将 Schema Question 当项目答案。
