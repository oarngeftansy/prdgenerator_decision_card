# 本机任务历史与飞书瞬时失败恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复仅本机可见的任务历史，并让飞书导出能自动恢复文档读取阶段的瞬时 EOF，同时准确表达 partial 状态。

**Architecture:** 前端用 `location.hostname` 控制历史入口，后端用请求来源 loopback 校验保护历史列表与归档接口。飞书发布器只对 `docs +media-insert` 内部读取阶段暴露的 EOF/连接中断做有限重试，其他错误继续进入可恢复 partial 状态。

**Tech Stack:** HTML、原生 JavaScript、FastAPI、Python 标准库、pytest、Node test runner、lark-cli。

## Global Constraints

- 本机指 IPv4 `127.0.0.0/8`、IPv6 `::1` 和前端主机名 `localhost`。
- 局域网用户仍可创建任务并按已知任务 ID 轮询，不可枚举或归档历史。
- 不增加管理员账号、密码、数据库或第三方依赖。
- 飞书重试只覆盖可识别的读取阶段瞬时错误，不能重试普通写入错误。

---

### Task 1: 本机任务历史访问边界

**Files:**
- Modify: `backend/server.py`
- Modify: `js/backend.js`
- Modify: `js/app.js`
- Modify: `index.html`
- Create: `tests/test_history_access.py`
- Modify: `tests/js/archive-history.test.js`
- Modify: `tests/test_feishu_publish_ui_contract.py`

**Interfaces:**
- Produces: `isLocalHistoryHost(hostname: string) -> boolean` and `initializeJobHistory() -> Promise<void>` in the browser runtime.
- Produces: `_require_loopback(request: Request) -> None` in `backend.server`.
- Protects: `GET /api/jobs` and `POST /api/jobs/{job_id}/archive`.

- [ ] **Step 1: Write failing frontend and backend tests**

Add assertions that loopback hostnames show/load history, LAN hostnames keep it hidden, loopback requests can list/archive, and remote requests receive HTTP 403.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='runtime_packages;calibration_packages;.'
python -m pytest tests\test_history_access.py tests\test_feishu_publish_ui_contract.py -q
node --test tests\js\archive-history.test.js
```

Expected: failures because hostname gating, loopback enforcement, and restored list output do not exist.

- [ ] **Step 3: Implement the minimal history boundary**

Use `ipaddress.ip_address(request.client.host).is_loopback` on the backend. Restore `list_jobs(include_archived)` only after the guard. On the frontend, reveal and load history only when the current hostname is loopback/localhost; show a scoped error inside `historyList` if loading fails.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 commands. Expected: all focused tests pass.

---

### Task 2: 飞书瞬时读取失败自动恢复

**Files:**
- Modify: `backend/feishu_publish.py`
- Modify: `js/feishu-publish.js`
- Modify: `tests/test_feishu_publish.py`
- Modify: `tests/js/feishu-publish.test.js`

**Interfaces:**
- Produces: `FeishuPublisher._insert_media_with_retry(args: list[str]) -> None`.
- Preserves: existing `mediaDone` checkpoint and partial retry behavior.

- [ ] **Step 1: Write failing retry and copy tests**

Extend `FakeCli` with a one-time `API call failed: Get ... EOF` media insertion failure. Assert automatic recovery publishes successfully with two attempts, while the existing ordinary `media failed` case remains partial. Assert partial UI says “文档已创建，但导出尚未完成”.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='runtime_packages;calibration_packages;.'
python -m pytest tests\test_feishu_publish.py -q
node --test tests\js\feishu-publish.test.js
```

Expected: transient EOF test fails and old partial copy remains.

- [ ] **Step 3: Implement bounded retry and precise partial copy**

Retry the media insertion at delays `0`, `1`, and `2` seconds only when the exception contains both a read marker (`API call failed: Get`) and a transient marker (`EOF`, `connection reset`, or `timed out`). After the final failure, persist partial with message `飞书文档已创建，但导出尚未完成；可继续重试`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 commands. Expected: all focused tests pass, including the unchanged ordinary-failure partial test.

---

### Task 3: 集成验证与现有 partial 任务恢复

**Files:**
- Modify: `progress.md`

**Interfaces:**
- Consumes: Task 1 and Task 2 behavior.

- [ ] **Step 1: Run the combined regression suite**

```powershell
$env:PYTHONPATH='runtime_packages;calibration_packages;.'
python -m pytest tests\test_history_access.py tests\test_feishu_publish.py tests\test_feishu_publish_api.py tests\test_feishu_publish_ui_contract.py -q
node --test tests\js\*.test.js
python -m py_compile backend\server.py backend\feishu_publish.py
node --check js\backend.js js\app.js js\feishu-publish.js
git diff --check
```

Expected: zero failures; only existing FastAPI lifespan deprecation warnings are allowed.

- [ ] **Step 2: Restart and verify access behavior**

Verify `http://127.0.0.1:8000` renders a visible populated history panel. Verify a request with a non-loopback client scope receives HTTP 403 from list/archive while single-job polling remains available.

- [ ] **Step 3: Retry the existing partial publication**

Reuse job `faaf4c2d8cb24e9b940067577d3b46ef` and its saved request ID so the existing document and 21 completed media checkpoints are preserved. Poll until `published`, `partial`, `failed`, or `conflict`; do not create a new version.

- [ ] **Step 4: Record verified outcome**

Append the exact test counts, access checks, and real Feishu publication terminal state to `progress.md`.
