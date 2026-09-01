# Planner Feedback Assimilation Design

## Goal

将 Planner Feedback 转换为可审核、可追踪、可撤销的结构化操作；操作批准后作用于 ApprovedData 派生副本，再运行现有 Rule Intelligence Pipeline。

## Authority boundary

- `project_feedback`：只有 approved operation 可以修改当前项目的 Rule、Intent、Schema Slot、Owner、Gap 或 Parameter。
- `system_feedback`：只能生成 Architecture Improvement Candidate，不得修改当前项目事实或 Publication。
- 原始反馈文本不进入 Fact/Rule，不影响 Prompt，不获得证据权威。
- 未审核 operation 只进入 ReviewProjection；Rejected operation 永不应用。

## Operation contract

支持 `patch_rule_intent`、`move_rule_schema_slot`、`set_canonical_owner`、`upsert_gap`、`resolve_gap`、`patch_parameter`、`mark_evidence_required`。每次应用记录 feedbackId、operationId、目标、before、after、sourceRevision、appliedRevision。

## Review and recovery

`register_planner_feedback` 和 `review_planner_feedback_operation` 复用 Gameplay Review revision/history。确认、拒绝、undo、redo 后重新构建 Rule Intelligence Projection；未确认操作不能进入 Publication。

## Scope exclusions

本阶段不修改 Intent taxonomy、Renderer、Inference Policy 或《一路狂飙》特定规则。
