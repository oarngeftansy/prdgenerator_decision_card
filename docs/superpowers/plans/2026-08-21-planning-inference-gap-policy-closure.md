# Planning Inference & Gap Policy Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通安全策划推断、审核 Proposal、Gap domain/applicability 与 Final 过滤链。

**Architecture:** 在现有 Rule Intelligence 深模块内增加通用声明式 policy evaluator，复用 Review/Publication seam。Gap Analyzer 只为 applicable planning behavior 生成阻断项，Renderer 过滤 technical domain。

**Tech Stack:** Python dataclasses、JSON knowledge graph、pytest。

## Global Constraints

- 禁止玩法特定 if/else、品类标签激活和 Pattern 项目答案。
- 未审核 Proposal 不进入 Publication。
- 公式、概率、权重、放回、保底与隐藏实现继续 Hard Guard。
- 不改 UI、Temporal Pipeline 或 Phase 3 taxonomy。

---

### Task 1: Policy contract and safe closure

**Files:**
- Modify: `backend/planning_content_models.py`
- Modify: `backend/rule_intelligence_pipeline.py`
- Modify: `data/planner_knowledge/mechanic-knowledge-graph-v1.json`
- Test: `tests/test_planning_inference_gap_policy.py`

**Interfaces:**
- Consumes: `build_rule_intelligence_projection(approved_data=..., chapters=...)`
- Produces: `plannerInferences`, `reviewProposals`, enriched `gaps`.

- [ ] Write T1 failing test for confirmed target selection + target death → reselect planner inference with lineage.
- [ ] Run T1 and verify RED.
- [ ] Add minimal declarative policy evaluator and fields.
- [ ] Run T1 and verify GREEN.

### Task 2: Gap domain, applicability and proposals

**Files:**
- Modify: `backend/planning_content_models.py`
- Modify: `backend/gap_analyzer.py`
- Modify: `backend/rule_intelligence_pipeline.py`
- Test: `tests/test_planning_inference_gap_policy.py`

**Interfaces:**
- Consumes: applicable schema slots and confirmed structured evidence.
- Produces: `gapDomain`, `inferencePermission`, `applicabilityStatus`, proposal linkage.

- [ ] Add T3 optional Weight without evidence → `not_observed`, no blocking Gap.
- [ ] Add T4 sufficient context → Proposal rather than blank question.
- [ ] Add T6 unknown VictoryCondition → blocking Planning Gap.
- [ ] Implement minimal applicability and proposal behavior.
- [ ] Run T3/T4/T6 and verify GREEN.

### Task 3: Final filtering and hard guards

**Files:**
- Modify: `backend/document_assembler.py`
- Modify: `backend/rule_intelligence_pipeline.py`
- Test: `tests/test_planning_inference_gap_policy.py`

**Interfaces:**
- Consumes: PublicationProjection chapters and gaps.
- Produces: Final containing publishable rules and Planning Gaps only.

- [ ] Add T2 Technical Gap filtering test.
- [ ] Add T5 random candidate hard-guard test.
- [ ] Implement filtering without altering internal audit gaps.
- [ ] Run T2/T5 and verify GREEN.

### Task 4: Regression and real sample regeneration

**Files:**
- Create: `artifacts/yilu-kuangbiao-inference-closure-2026-08-21/*`

**Interfaces:**
- Consumes: existing structured 《一路狂飙》 snapshot.
- Produces: new Final, projection, manifest, before/after Gap metrics.

- [ ] Run six focused tests and Phase 1/2 regression.
- [ ] Run full Python suite.
- [ ] Regenerate Result A through current Projection/Publication/Final chain.
- [ ] Measure inference/proposal/evidence-required/technical Gap counts and contamination.
- [ ] Commit only task files; do not include user-owned changes or unrelated artifacts.
