# 玩法章节生成反馈修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复“确认交互，生成玩法章节”点击后无反馈，并移除预览页内部提醒编号。

**Architecture:** 前端生成请求复用截图分析时的视觉模型表单配置；生成状态在预览主按钮附近渲染，成功后路由到玩法目录。后端持久化安全中文失败原因，前端轮询并展示。预览页不再渲染非核心提醒列表。

**Tech Stack:** 原生 JavaScript、FastAPI、pytest、Node.js test runner。

## Global Constraints

- 页面不得展示 `STG-*`、`TRN-*`、`COMPETITOR_BOARD_PENDING` 等内部编号。
- 点击后必须立即显示运行状态；失败必须原位显示中文原因和重试入口。
- 成功后自动进入“确认玩法目录”。
- 不允许重复点击创建并行生成任务。

---

### Task 1: 让生成请求携带视觉模型配置

**Files:**
- Modify: `js/gameplay-review-client.js`
- Modify: `js/backend.js`
- Test: `tests/js/gameplay-review-client.test.js`
- Test: `tests/js/screenshot-backend.test.js`

**Interfaces:**
- Consumes: `backendConfigForm(): FormData`
- Produces: `GameplayReviewClient.generate(config: FormData): Promise<object>`

- [ ] **Step 1: 写失败测试**

断言 `generate(formData)` 将该表单作为 POST body；断言 `runGameplayGeneration` 调用生成接口后立即进入 busy 状态。

- [ ] **Step 2: 运行测试并确认因请求 body 缺失而失败**

Run: `node --test tests/js/gameplay-review-client.test.js tests/js/screenshot-backend.test.js`
Expected: FAIL，生成请求的 `body` 为 `undefined`。

- [ ] **Step 3: 最小实现**

将客户端方法改为 `generate(config) { return this.request("/gameplay-review/generate", { method: "POST", body: config }); }`，调用端使用 `state.gameplayReviewClient.generate(backendConfigForm())`。

- [ ] **Step 4: 运行测试并确认通过**

Run: `node --test tests/js/gameplay-review-client.test.js tests/js/screenshot-backend.test.js`
Expected: PASS。

### Task 2: 展示生成状态并自动进入目录

**Files:**
- Modify: `js/export-preview.js`
- Modify: `js/backend.js`
- Modify: `backend/server.py`
- Test: `tests/js/export-preview.test.js`
- Test: `tests/js/screenshot-backend.test.js`
- Test: `tests/test_review_api.py`

**Interfaces:**
- Consumes: `gameplayReviewGeneration.status/progress/message/error`
- Produces: 预览页原位状态、重试按钮、成功后的 `setReviewWorkspaceView("gameplay_directory")`

- [ ] **Step 1: 写失败测试**

覆盖 queued/running/failed/completed 四种状态；失败状态必须显示中文原因，完成状态必须路由到玩法目录；后端失败记录必须包含安全中文 `error`。

- [ ] **Step 2: 运行目标测试并确认失败**

Run: `node --test tests/js/export-preview.test.js tests/js/screenshot-backend.test.js`
Run: `python -m pytest tests/test_review_api.py -q`
Expected: FAIL，失败原因未渲染且完成后未路由。

- [ ] **Step 3: 最小实现**

轮询时同步 progress/error；失败时保持按钮可重试并在按钮上方显示原因；完成后同步模型并进入玩法目录。后端只保存可公开的中文错误分类，不回传密钥或原始响应。

- [ ] **Step 4: 运行目标测试并确认通过**

Run: `node --test tests/js/export-preview.test.js tests/js/screenshot-backend.test.js`
Run: `python -m pytest tests/test_review_api.py -q`
Expected: PASS。

### Task 3: 删除非核心提醒列表

**Files:**
- Modify: `js/export-preview.js`
- Test: `tests/js/export-preview.test.js`

**Interfaces:**
- Consumes: `warningIds` 仅供内部状态使用
- Produces: 不包含“非核心提醒”及内部编号的策划预览 DOM

- [ ] **Step 1: 写失败测试**

使用包含 `STG-001_PENDING_DETAILS`、`TRN-001_PENDING_DETAILS` 的预览数据，断言渲染结果不包含这些文本和“非核心提醒”。

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test tests/js/export-preview.test.js`
Expected: FAIL，当前页面仍渲染 warningIds。

- [ ] **Step 3: 最小实现**

删除 `root.append(issueList("可以稍后补充", view.warningIds || [], model, onRoute))`；阻断项仍保留中文可操作入口。

- [ ] **Step 4: 运行测试并确认通过**

Run: `node --test tests/js/export-preview.test.js`
Expected: PASS。

### Task 4: 真实任务验收

**Files:**
- Test: `tests/js/*.test.js`
- Test: `tests/test_review_api.py`

**Interfaces:**
- Consumes: 当前任务 `183261b4137e40a59596b3afcaad4f18`
- Produces: 可观察的生成进度或明确中文失败；成功后自动打开玩法目录

- [ ] **Step 1: 运行相关完整测试**

Run: `node --test tests/js/*.test.js`
Run: `python -m pytest tests/test_review_api.py tests/test_review_preview.py -q`
Expected: PASS。

- [ ] **Step 2: 重启本地服务并在当前任务重试**

确认按钮进入 busy 状态，接口获得视觉模型配置；完成后工作台进入玩法目录。
