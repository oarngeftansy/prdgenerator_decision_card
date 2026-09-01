# Planner Review Density Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Mechanic Review 默认层压缩为核心规则、特殊分支、参数和真实设计分叉，并保持完整模型与 P7 不变。

**Architecture:** 在现有 `plannerReadableSections` 之上生成只读 `defaultReview` 与 `expandDetail`。默认规则通过 Importance、去重和数量 Gate；隐藏信息仍由原始 artifact 提供，Depth 与 lineage 不读取展示投影。

**Tech Stack:** Python 3.12、JSON、FastAPI、原生 JavaScript/CSS、pytest、Playwright。

## Global Constraints

- 不修改 P7、Final Publication、Mechanic Model、原始 design item、Depth、lineage 或 `job.json`。
- 默认层只显示 3～6 核心、0～4 分支、0～3 参数、0～2 决策点。
- 默认信息量至少减少 40%，每条规则保留来源。
- 已确认与 AI 补全仅以颜色区分。
- 完整信息保留于 Expand Detail。

---

### Task 1: 密度投影

**Files:**
- Modify: `tests/test_current_full_mechanic_reconstruction.py`
- Modify: `scripts/generate_full_mechanic_reconstruction.py`

**Interfaces:**
- Consumes: `build_planner_readability_projection(models)`。
- Produces: `defaultReview`、`expandDetail`、密度与完整性指标。

- [ ] 写失败测试：断言每个 Mechanic 的数量上限、总体减少率≥40%、去重/降级计数、来源映射与哈希守恒。
- [ ] 运行定点测试，确认当前完整投影因信息量过高而失败。
- [ ] 最小实现 Importance 与去重 Gate，生成三套 Before/After。
- [ ] 重跑定点测试并通过。

### Task 2: 默认页面与 Expand Detail

**Files:**
- Modify: `tests/test_full_mechanic_review_web.py`
- Modify: `js/mechanic-review.js`
- Modify: `css/mechanic-review.css`

**Interfaces:**
- Consumes: `defaultReview` 与 `expandDetail`。
- Produces: `/mechanic-review` 精简默认层。

- [ ] 写失败测试：默认 DOM 不含 Depth、QA、依据、依赖和补齐说明，详情包含这些内容。
- [ ] 运行网页 seam 测试并确认失败。
- [ ] 最小修改网页，只展示四层并将其他内容装入单个 Expand Detail。
- [ ] 重跑网页测试并通过。

### Task 3: 产物、回归与真实浏览器

**Files:**
- Regenerate: `artifacts/full-mechanic-reconstruction-2026-08-19/*`
- Modify: `.claude/memory/memory.md`

**Interfaces:**
- Consumes: 完成后的投影和页面。
- Produces: Before/After 报告、浏览器截图、测试与合并证据。

- [ ] 重新生成 Review JSON 与 Markdown。
- [ ] 验证 P7、Depth 与 lineage 哈希不变。
- [ ] 运行完整相关 pytest。
- [ ] 用真实浏览器验证三张卡、折叠状态、默认规则数量和技术信息泄漏。
- [ ] 更新稳定记忆、提交范围内文件并合并到 `main`。
