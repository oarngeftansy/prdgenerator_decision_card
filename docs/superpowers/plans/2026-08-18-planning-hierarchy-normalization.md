# Planning Hierarchy Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将七个 Mechanic Review Unit 确定性投影为基于现有 Owner Audit 的自然 Planning Hierarchy，并输出带内容摘要的双结构 Preview。

**Architecture:** 新建独立 normalization 模块，消费 review unit、design item 与显式 owner assignment，输出 Planning Node、Title Quality、Owner Structure Finding 和 lineage。现有 Benchmark 生成器只增加双结构产物，不修改 Proposal 内容、规则源或正式 Publication。

**Tech Stack:** Python 3、pytest、JSON/Markdown artifacts。

## Global Constraints

- 不新增 Pipeline Phase、Taxonomy、Closure Status 或固定章节 Schema。
- Current System Hierarchy Audit 是本轮 owner assignment 权威输入，但 Normalization 只记录结构风险，不自动迁移 Owner。
- Planning Title Quality Gate 同时执行 Composite Check 与 Single Responsibility Check。
- Preview 默认隐藏 Proposal/Requirement/Dimension ID，Audit 保留完整 lineage。
- 不修改 Evidence、Fact、Rule、Requirement、Proposal、`job.json` 或 Final Publication。
- 不扩展 Project Fit、Parameter Necessity、Impact Preview。

---

### Task 1: Planning Title Quality Gate

**Files:**
- Create: `backend/planning_hierarchy_normalization.py`
- Create: `tests/test_planning_hierarchy_normalization.py`

**Interfaces:**
- Produces: `evaluate_composite_title(title, *, business_concept_evidence_refs=()) -> dict`。
- Produces: `evaluate_single_responsibility(node) -> dict`。

- [ ] Write a failing public-interface test for composite titles, evidence exemption, mixed peer responsibilities, invalid parent-child responsibility and generic container titles.
- [ ] Run the targeted test and verify failure because the module does not exist.
- [ ] Implement only the two deterministic checks and combined `evaluate_planning_title_quality(...)` result.
- [ ] Run the targeted test and verify pass.

### Task 2: Owner Projection and Structure Findings

**Files:**
- Modify: `backend/planning_hierarchy_normalization.py`
- Modify: `tests/test_planning_hierarchy_normalization.py`

**Interfaces:**
- Produces: `normalize_planning_hierarchy(review_units, owner_assignments) -> dict`。

- [ ] Write failing tests that require one Primary Planning Node per design item, one Review Unit projecting to multiple nodes, no text inference, stable PNODE IDs and ownerStructureFindings without owner mutation.
- [ ] Run tests and verify the new assertions fail.
- [ ] Implement explicit-ID projection, hierarchy tree assembly, lineage preservation and advisory owner findings.
- [ ] Run tests and verify pass.

### Task 3: Benchmark Dual Hierarchy Artifacts

**Files:**
- Modify: `scripts/generate_current_mechanic_design_synthesis.py`
- Modify: `tests/test_current_mechanic_design_synthesis.py`
- Modify/Create: `artifacts/mechanic-design-synthesis-2026-08-18/*`

**Interfaces:**
- Consumes: existing seven synthesis units plus explicit current-project owner assignments.
- Produces: `review-hierarchy.json`, `planning-hierarchy.json`, both previews and normalization audit.

- [ ] Write failing artifact tests for seven Review Units, dynamic Planning roots, forbidden composite titles, design item summaries under nodes, correct statistics/settlement/outcome Owner, 100% assignment and zero source mutation.
- [ ] Run artifact tests and verify missing-output failures.
- [ ] Extend the generator with explicit assignments and natural preview rendering; attach `planningNodeId/planningOwnerPath/planningOwnerEvidenceRefs` to design items.
- [ ] Regenerate artifacts and run tests to verify pass.

### Task 4: Regression and Immutable Boundaries

**Files:**
- Modify: `.claude/memory/memory.md`

- [ ] Run normalization, Mechanic Synthesis, Proposal, Carrier and Assembly regression suites.
- [ ] Verify `job.json` and formal Publication hashes are unchanged by the generator.
- [ ] Record Review/Planning decoupling, advisory owner findings and Title Quality Gate in project memory.
