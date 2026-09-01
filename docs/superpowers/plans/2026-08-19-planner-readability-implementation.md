# Planner Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将三套 Full Mechanic Review 模型中的低价值 AI 推荐压制，并生成短句、自然分组、无程序术语的主策默认阅读稿。

**Architecture:** 原始 Mechanic Model、design item、Depth 与 Evidence / Fact / Rule / Requirement / Proposal lineage 保持权威不变。生成器只新增只读 `plannerReadableSections` 投影；网页默认消费可读投影，原始内容留在折叠详情。

**Tech Stack:** Python 3.12、JSON artifact、FastAPI 静态 Review API、原生 JavaScript/CSS、pytest。

## Global Constraints

- 不修改 Evidence / Fact / Rule / Requirement / Proposal lineage。
- `implementation_suppressed` 只属于展示投影，不回写原始 design item，也不改变 Coverage。
- 常识性 Entry/Exit/Cleanup 在展示投影中合并进所属核心规则，不作为独立默认 bullet。
- Design Inference 只保留会改变玩家结果、玩法分支、数值、QA 预期或跨系统职责的内容。
- 压缩前后 Core Design Depth 必须完全一致。
- 表现内容继续进入策划草图 / Visual & Interaction Board。

---

### Task 1: 只读 Readability Projection

**Files:**
- Modify: `tests/test_full_mechanic_reconstruction.py`
- Modify: `tests/test_current_full_mechanic_reconstruction.py`
- Modify: `backend/full_mechanic_reconstruction.py`
- Modify: `data/planner_knowledge/full_mechanic_reconstruction_profiles_v1.json`
- Modify: `scripts/generate_full_mechanic_reconstruction.py`

**Interfaces:**
- Consumes: `designItems[]`, reconstruction responsibilities 与 Design Lever contract。
- Produces: `plannerReadableSections[]` 与投影内部 `implementation_suppressed` 分类；原始 `coreDesignDepth` 不变。

- [ ] **Step 1: 写失败测试**

断言提交锁、实例寻址、目标引用释放、未结算指向取消、纯清理步骤不进入默认投影；候选池、Pool 不足、满栏、攻击周期、伤害归属、多怪口径仍保留；原始 design item 与 Core Depth 哈希不变。

- [ ] **Step 2: 运行定点测试并确认失败**

Run: bundled Python `-m pytest tests/test_full_mechanic_reconstruction.py tests/test_current_full_mechanic_reconstruction.py -q`

Expected: 新 suppression/readability 断言失败。

- [ ] **Step 3: 最小实现**

不改写三套模型；基于稳定 design item ID 生成核心规则、分支、参数、跨系统关系四类可读投影，并将被隐藏的原始项仅记录为投影 metadata。

- [ ] **Step 4: 运行定点测试并确认通过**

Expected: Task 1 测试全部通过。

### Task 2: Planning Language Compression

**Files:**
- Modify: `tests/test_current_full_mechanic_reconstruction.py`
- Modify: `scripts/generate_full_mechanic_reconstruction.py`
- Modify: `artifacts/full-mechanic-reconstruction-2026-08-19/full-mechanic-design-review-preview.md`
- Modify: `artifacts/full-mechanic-reconstruction-2026-08-19/reconstructed-models.json`

**Interfaces:**
- Consumes: 原始 `designItems[]` 与 suppression 分类。
- Produces: 每条带 `sourceDesignItemIds[]` 的短规则，以及压缩前后统计。

- [ ] **Step 1: 写失败测试**

断言默认规则不含禁用技术词、每条只表达一个独立结论、长句数量显著下降、每条均有原始 design item 来源，Depth 与 lineage 值在压缩前后相同。

- [ ] **Step 2: 运行测试并确认失败**

Expected: 当前长句与技术词命中导致失败。

- [ ] **Step 3: 最小实现并重新生成 artifact**

以确定性分组与人工策划短句映射生成三个 Mechanic 的核心规则、分支、参数及跨系统关系；原始 item 不被可读文本覆盖。

- [ ] **Step 4: 运行测试并确认通过**

Expected: 语言 Gate、语义守恒与 lineage Gate 全部通过。

### Task 3: 网页默认阅读层

**Files:**
- Modify: `tests/test_full_mechanic_review_web.py`
- Modify: `js/mechanic-review.js`
- Modify: `css/mechanic-review.css`

**Interfaces:**
- Consumes: `plannerReadableSections[]` 与原始折叠详情。
- Produces: `/mechanic-review` 主策默认视图。

- [ ] **Step 1: 写失败测试**

断言页面默认消费 `plannerReadableSections`，不逐条显示“AI 推荐”，不显示 implementation_suppressed；Evidence、Inference、QA、lineage 与表现引用位于折叠层。

- [ ] **Step 2: 运行测试并确认失败**

Expected: 当前页面仍直接渲染长 `designItems`，测试失败。

- [ ] **Step 3: 最小实现**

按核心规则、分支、参数、跨系统关系渲染短规则；用侧标/颜色表达知识类型；技术详情与策划草图引用折叠展示。

- [ ] **Step 4: 运行测试并确认通过**

Expected: 网页 seam 测试通过。

### Task 4: 回归、网页复核与提交

**Files:**
- Modify: `.claude/memory/memory.md`
- Regenerate: `artifacts/full-mechanic-reconstruction-2026-08-19/*`

**Interfaces:**
- Consumes: 三项实现结果。
- Produces: 可访问网页、前后指标、稳定项目记忆与提交。

- [ ] **Step 1: 运行完整相关回归**

Expected: Full Mechanic、Depth、Requirement、Proposal 与网页测试全部通过。

- [ ] **Step 2: 浏览器核验**

确认三个 Mechanic 可在 10 秒扫读核心规则，技术词为 0，AI 标签不重复，折叠层存在且策划草图分流明确。

- [ ] **Step 3: 更新稳定记忆并提交范围内文件**

只提交本轮明确文件，不纳入工作区其他历史改动。

- [ ] **Step 4: 合并到 `main` 并验证局域网页面**

重新加载服务，验证 `http://192.168.50.67:8000/mechanic-review` 返回新稿。
