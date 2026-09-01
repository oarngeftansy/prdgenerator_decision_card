# Planner Feedback Assimilation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立结构化、可审核、可撤销的 Planner Feedback Assimilation seam。

**Architecture:** 独立 Assimilator 在 Pipeline 前生成 ApprovedData 派生副本；Gameplay Review operations 管理反馈注册、审批与历史；system feedback 仅输出架构候选。

**Tech Stack:** Python、pytest、现有 Rule Intelligence / Gameplay Review revision 链。

## Global Constraints

- Feedback text 不直接成为 Fact/Rule 或 Prompt 权威。
- system_feedback 不改变当前项目。
- 未审核 operation 不进入 Publication。
- 不修改 taxonomy、Renderer、Inference Policy。

### Task 1: Structured assimilation engine

**Files:** `backend/planner_feedback_assimilation.py`, `tests/test_planner_feedback_assimilation.py`

- [x] RED：project/system/unreviewed/lineage 测试。
- [x] GREEN：实现类型化 operation、派生 ApprovedData 与 revision lineage。

### Task 2: Rule Intelligence integration

**Files:** `backend/rule_intelligence_pipeline.py`, `tests/test_planner_feedback_assimilation.py`

- [x] RED：反馈操作后 Projection 必须重算 Rule Intent/Slot。
- [x] GREEN：Pipeline 前应用 Assimilator，输出 feedbackAssimilation ledger。

### Task 3: Review, undo and redo

**Files:** `backend/gameplay_review_service.py`, `tests/test_planner_feedback_assimilation.py`

- [x] RED：register/review/undo/redo 行为测试。
- [x] GREEN：复用现有 revision/history 与 Projection rebuild。

### Task 4: Frozen Feedback A/B

**Files:** `artifacts/yilu-kuangbiao-feedback-assimilation-ab-2026-08-21/*`

- [ ] 冻结 HEAD、Evidence、ApprovedData。
- [ ] A 不加载反馈；B 只加载六条反馈。
- [ ] 输出 Projection、Final、lineage 和 Feedback Effect Matrix。
- [ ] 跑完整回归并提交推送。
