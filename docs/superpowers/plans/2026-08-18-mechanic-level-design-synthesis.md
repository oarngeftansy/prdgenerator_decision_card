# Mechanic-level Design Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 18 条 Atomic Proposal 确定性聚合为七套可整体审核、可逐 design item 审批且与 Final Publication 隔离的 Mechanic Design。

**Architecture:** 新建聚焦的 `mechanic_design_synthesis` 模块，消费现有 Proposal、Requirement 和显式 owner/reference 配置，输出稳定 design item、完整度、一致性、兼容性及审核视图。独立生成脚本产出七 Mechanic Benchmark，不修改 Requirement、Rule、`job.json` 或 Final Publication。

**Tech Stack:** Python 3、pytest、JSON/Markdown artifacts。

## Global Constraints

- 不新增 Pipeline Phase、Taxonomy、Closure Status 或固定章节 Schema。
- `reviewEligibility=ready` 仅表示适合主策审核。
- Accept Mechanic 按 design item/Requirement 分别生成 Approved Rule，不合并成单条 Rule。
- 每个 Atomic Proposal 只有一个 Primary Mechanic Owner；跨 Mechanic 只使用结构化 Reference。
- Review Layer 与 Final Publication 硬隔离；本轮不生成 Approved/Confirmed Rule。
- 不修改 `job.json` 或正式策划案。

---

### Task 1: Stable Design Item and Mechanic Synthesis

**Files:**
- Create: `backend/mechanic_design_synthesis.py`
- Create: `tests/test_mechanic_design_synthesis.py`

**Interfaces:**
- Consumes: Atomic Proposal、Requirement、Confirmed context、Mechanic spec。
- Produces: `synthesize_mechanic_design(*, mechanic_spec, proposals, confirmed_rules=(), parameter_placeholders=(), rule_references=()) -> dict`。

- [ ] **Step 1: Write the failing test**

测试怪物五个 Dimension 聚合为稳定 `designItemId` 的有序 design items；每项包含 `sequence/text/knowledgeClass/sourceProposalIds/requirementIds/parameterRefs/approvalState`，且 `ready` 不授予 Confirmed/Resolved/Publication。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mechanic_design_synthesis.py::test_synthesizes_stable_review_only_design_items -q`
Expected: FAIL because module/interface does not exist.

- [ ] **Step 3: Write minimal implementation**

以 mechanic ID、sequence 和 source Proposal IDs 生成稳定 `MDI-*`；按 spec 的显式 item 定义聚合，不使用文本相似度。

- [ ] **Step 4: Run test to verify it passes**

Run the same command. Expected: PASS.

### Task 2: Coherence, Reuse, Compatibility and Completeness

**Files:**
- Modify: `backend/mechanic_design_synthesis.py`
- Modify: `tests/test_mechanic_design_synthesis.py`

**Interfaces:**
- Produces: `coherenceFindings/compatibilityFindings/ruleReferences/unclosedLifecycleSlots/executionCompleteness/reviewEligibility`。

- [ ] **Step 1: Write failing tests**

覆盖 Entry/Core Processing/Branch or Repeat/Exit/Next State 完整度、Pause/Resume 配对、分支后继、参数 Consumer、Confirmed conflict、Primary Owner 重复定义和跨 Mechanic Reference。

- [ ] **Step 2: Run tests to verify failures**

Run: `python -m pytest tests/test_mechanic_design_synthesis.py -q`
Expected: new behavior assertions fail.

- [ ] **Step 3: Implement minimal gates**

只消费显式 item roles、relations、consumer 和 conflict refs；Coherence 与 Completeness 分开；真实冲突使 `reviewEligibility != ready`。

- [ ] **Step 4: Run tests to verify pass**

Run the same command. Expected: PASS.

### Task 3: Mechanic Review View and Publication Isolation

**Files:**
- Modify: `backend/mechanic_design_synthesis.py`
- Modify: `tests/test_mechanic_design_synthesis.py`

**Interfaces:**
- Produces: `build_mechanic_review_view(synthesis, *, expand_lineage=False) -> dict`。

- [ ] **Step 1: Write failing tests**

默认视图只能出现自然标题与机制方案；展开后才出现 Dimension/Proposal/Requirement lineage。审核字段不得获得 Publication eligibility，Publication Blocked 原因不得渲染为正式正文。

- [ ] **Step 2: Run tests to verify failures**

Run targeted tests. Expected: FAIL.

- [ ] **Step 3: Implement minimal review projection**

默认返回自然机制内容、比例和操作；lineage 置于可选展开字段；所有 design items 保持 `publicationEligible=false`。

- [ ] **Step 4: Run tests to verify pass**

Run targeted tests. Expected: PASS.

### Task 4: Seven-Mechanic Benchmark Generator

**Files:**
- Create: `scripts/generate_current_mechanic_design_synthesis.py`
- Create: `tests/test_current_mechanic_design_synthesis.py`
- Create: `artifacts/mechanic-design-synthesis-2026-08-18/*`

**Interfaces:**
- Consumes: `artifacts/mechanic-requirement-ai-proposals-2026-08-18/ai-proposed-rules.json` and current Requirement/Rule/Evidence artifacts.
- Produces: seven syntheses, review queue, natural Markdown preview and audit metrics.

- [ ] **Step 1: Write failing benchmark test**

断言恰好七 Mechanic、18 Atomic Proposal 各有唯一 Primary Owner、跨 Mechanic 复用为 Reference、怪物生命周期合并、无工程 ID 标题、零 Confirmed/Requirement/Publication mutation。

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_current_mechanic_design_synthesis.py -q`
Expected: FAIL because artifacts do not exist.

- [ ] **Step 3: Implement generator and artifact rendering**

使用显式七 Mechanic specs、自然 title/owner path、design item sequence/role/knowledge class、Primary owner/reference；输出所需四个 artifact。

- [ ] **Step 4: Generate and run benchmark tests**

Run generator, then targeted tests. Expected: PASS.

### Task 5: Regression and Integrity

**Files:**
- Modify: `.claude/memory/memory.md`

- [ ] **Step 1: Run focused and broad regression**

Run Requirement、Proposal、Chain、Carrier、Assembly 与新 Synthesis tests. Expected: all pass.

- [ ] **Step 2: Verify immutable artifacts**

确认 `job.json` 和 formal `human-planning-preview.md` 未由生成器写入；新 artifact 中 Confirmed/Valid/Publication Eligible count 均为 0。

- [ ] **Step 3: Record stable product contract**

向 memory 追加 Mechanic-level Review、design item approval、Completeness/Coherence 分离和 Review/Publication 隔离约定。
