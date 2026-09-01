# Hierarchical Loop Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace flat scene/frame planning with a GVE16-aligned hierarchy of large loops, stages, small loops, steps, and evidence; review it top-down; publish only quality-qualified content; render Feishu documents and boards around the same hierarchy.

**Architecture:** Preserve scenes and frames as immutable evidence. Add a normalized loop hierarchy synthesized from semantic analyses with a deterministic fallback, then derive planning documents, review progress, quality gates, and Feishu artifacts from that hierarchy. The website presents a progressive review ladder and keeps the existing frame reviewer as the final evidence layer.

**Tech Stack:** Python 3.11, FastAPI, vanilla JavaScript/CSS, installed `lark-cli`, pytest, Node test runner.

## Global Constraints

- Default GVE16 remains enabled for gameplay and interaction.
- A visual scene is evidence, never a document chapter by default.
- Hierarchy is `largeLoop -> stages -> smallLoops -> steps -> evidence`.
- Every loop has entry, repeat, and exit conditions plus confidence and evidence.
- Manual confirmations and edits are never overwritten by reanalysis.
- Publishing is blocked when the hierarchy quality gate fails.
- No new third-party dependency.

---

### Task 1: Loop hierarchy model and deterministic fallback

**Files:**
- Create: `backend/loop_hierarchy.py`
- Test: `tests/test_loop_hierarchy.py`

**Interfaces:**
- Consumes: scenes, events, and metadata from a completed job.
- Produces: `build_loop_hierarchy(job) -> dict`, `validate_loop_hierarchy(hierarchy) -> list[str]`, and `loop_quality_gate(hierarchy, quality_report) -> dict`.

- [ ] Write failing tests for one/multiple large loops, stage nesting, small-loop closure, evidence preservation, and quality-gate failure.
- [ ] Run `python -m pytest tests/test_loop_hierarchy.py -q` and verify RED.
- [ ] Implement the smallest normalizer and deterministic fallback.
- [ ] Re-run the focused test and verify GREEN.

### Task 2: Loop-first semantic synthesis

**Files:**
- Modify: `backend/analysis_service.py`
- Modify: `backend/planner.py`
- Test: `tests/test_loop_synthesis_contract.py`

**Interfaces:**
- Consumes: completed scene/event analyses.
- Produces: `job["loopHierarchy"]` before planning-model generation.

- [ ] Write a failing contract test proving the prompt asks for large loops, stages, and small loops instead of scene chapters.
- [ ] Verify RED.
- [ ] Add one text-only hierarchy synthesis call with deterministic fallback and incremental stage status.
- [ ] Verify GREEN and preserve fallback behavior when the provider fails.

### Task 3: Planning model, document, and quality gate

**Files:**
- Modify: `backend/planning_model.py`
- Modify: `backend/planner.py`
- Modify: `backend/quality.py`
- Test: `tests/test_hierarchical_planning_model.py`

**Interfaces:**
- Produces: schema version 2 with `loopHierarchy`, mode-specific fields, gate status, and evidence-backed acceptance criteria.

- [ ] Write failing tests proving documents render hierarchy before evidence and do not create one chapter per frame.
- [ ] Verify RED.
- [ ] Implement hierarchy-backed planning output and publish gate.
- [ ] Verify GREEN.

### Task 4: Staircase review API and website interaction

**Files:**
- Modify: `backend/server.py`
- Create: `js/hierarchy-review.js`
- Modify: `js/backend.js`
- Modify: `js/app.js`
- Modify: `index.html`
- Modify: `css/style.css`
- Test: `tests/test_hierarchy_review_api.py`
- Test: `tests/js/hierarchy-review.test.js`
- Test: `tests/test_hierarchy_review_ui_contract.py`

**Interfaces:**
- Review order: large loop, stage, small loop, then evidence.
- Each node supports confirmed, edited, or pending state.

- [ ] Write failing backend and frontend tests for hierarchical progress, top-down navigation, edits, and evidence drill-down.
- [ ] Verify RED.
- [ ] Implement API persistence and progressive UI.
- [ ] Verify GREEN, keyboard behavior, responsive states, and empty/error states.

### Task 5: Sample-aligned Feishu document and screenshot flow board

**Files:**
- Modify: `backend/feishu_render.py`
- Modify: `backend/feishu_publish.py`
- Test: `tests/test_feishu_hierarchy_render.py`

**Interfaces:**
- Document sections follow large loop, stage, and small-loop hierarchy.
- Board groups key evidence screenshots by loop and connects them in event order with consistent operation/response/condition text.

- [ ] Write failing renderer tests for hierarchy order, selected evidence only, screenshot nodes, labels, and branch connections.
- [ ] Verify RED.
- [ ] Implement hierarchy XML plus board SVG/DSL update and verification.
- [ ] Verify GREEN with fake CLI and one real board acceptance.

#### 5A. 90% 复刻门槛（先做最小切片）

- 只选一个阶段、2–4 张关键截图、1 条主路径和 1 条回环，不先运行完整视频。
- 结构 25 分：阶段分区、步骤顺序、入口/出口/回环齐全。
- 截图 25 分：真实证据截图是主节点，裁切比例清晰且无重复堆帧。
- 连线 20 分：连线连接截图或状态节点，并区分推进、分支和回环。
- 文字 15 分：使用策划可读的“操作 / 系统反馈 / 条件”，不使用工程状态码。
- 版式 15 分：分区、间距、字号和阅读方向与 GVE16 样例一致。
- 总分低于 90，或任一项低于该项满分的 70%，均不得推广到完整生成器。
- 达标后再把同一契约写入项目 Skill，并用 `D:\20260722-171746*` 跑完整交互流程。

### Task 6: Reusable project Skill

**Files:**
- Create: `skills/hierarchical-game-design-review/SKILL.md`
- Create: `skills/hierarchical-game-design-review/references/schema.md`
- Create: `skills/hierarchical-game-design-review/agents/openai.yaml`
- Modify: `tests/test_skill_deployment.py`

**Interfaces:**
- Skill triggers on video-to-gameplay/interaction planning, loop decomposition, staged review, GVE16 sample alignment, and Feishu flow-board generation.

- [ ] Add a failing deployment/contract test for the missing Skill and required hierarchy terms.
- [ ] Verify RED.
- [ ] Create the concise Skill and schema reference, then deploy it to the project runtime skill tree.
- [ ] Run validation and verify GREEN.

### Task 7: Verification with the replacement video

**Files:**
- Update: `progress.md`
- Update: `findings.md`

- [ ] Run all focused Python and JavaScript tests plus compilation checks.
- [ ] Locate `D:\20260722-171746*` without using prior videos.
- [ ] Run the interaction workflow end to end, complete hierarchical review, publish to Feishu, and compare document/board structure with the GVE16 sample.
- [ ] Record actual duration, hierarchy counts, gate score, missing information, and visual-format gaps.
