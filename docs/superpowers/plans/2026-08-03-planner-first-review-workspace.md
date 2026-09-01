# Planner-First Review Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the model-oriented interaction review screen with a Chinese, single-operation review flow that automatically advances and still produces two interaction boards plus gameplay in one Feishu document.

**Architecture:** Keep the review model, operation queue, persistence APIs, whiteboard compiler, and gameplay publisher intact. Add a presentation adapter in `stage-review.js` that maps each stage into four planner-readable steps, and make `backend.js` own visible save/confirm state and deterministic navigation. Hide internal evidence by default without deleting it.

**Tech Stack:** Vanilla JavaScript, DOM APIs, CSS, Node test runner, Python/pytest, Playwright browser QA.

## Global Constraints

- Input remains 2–30 ordered screenshots; video is optional context only.
- Internal order is interaction review followed by gameplay review.
- Interaction output is exactly `策划草图`, then `竞品参考`; UX is legacy only.
- Interaction and gameplay publish into one Feishu document.
- Default UI contains no internal English labels, SCN/EVT IDs, evidence wall, representative-frame form, or component table.
- Reading order is `操作前 → 玩家操作 → 系统反馈 → 操作结果`.
- Successful confirmation advances automatically; failed saves never advance or lose edits.
- Preserve unrelated dirty files and never include them in task commits.

---

### Task 1: Semantic navigation and phase language

**Files:**
- Modify: `js/review-workspace.js`
- Modify: `index.html`
- Test: `tests/js/review-workspace.test.js`
- Test: `tests/test_review_workspace_ui_contract.py`

**Interfaces:**
- Consumes: `stages[]`, `confirmation.confirmed`, and validation warnings.
- Produces: `stageStatus(stage)` and `nextUnconfirmedStageId(model, currentStageId)`.

- [ ] **Step 1: Write failing helper tests**

```js
test("stage status uses planner states", () => {
  assert.equal(ReviewWorkspace.stageStatus({ confirmation: { confirmed: false } }), "pending");
  assert.equal(ReviewWorkspace.stageStatus({ confirmation: { confirmed: false }, validation: { warnings: ["补充反馈"] } }), "needs_attention");
  assert.equal(ReviewWorkspace.stageStatus({ confirmation: { confirmed: true } }), "complete");
});

test("next stage skips confirmed stages", () => {
  const model = { stages: [
    { id: "STG-001", order: 1, confirmation: { confirmed: true } },
    { id: "STG-002", order: 2, confirmation: { confirmed: false } },
  ] };
  assert.equal(ReviewWorkspace.nextUnconfirmedStageId(model, "STG-001"), "STG-002");
  model.stages[1].confirmation.confirmed = true;
  assert.equal(ReviewWorkspace.nextUnconfirmedStageId(model, "STG-002"), null);
});
```

- [ ] **Step 2: Add a failing static copy test**

```python
def test_workspace_uses_planner_facing_phase_copy():
    html = Path("index.html").read_text(encoding="utf-8")
    for label in ["确认交互流程", "逐步检查页面反馈", "预览交互交付物", "审核玩法规则", "预览并发布完整文档"]:
        assert label in html
    for legacy in [">1 流程<", ">2 页面<", ">3 交互预览<", ">5 图解<", ">6 最终预览<"]:
        assert legacy not in html
```

- [ ] **Step 3: Run tests and confirm they fail**

Run: `node --test tests/js/review-workspace.test.js`

Run: `python -m pytest tests/test_review_workspace_ui_contract.py -q`

Expected: helpers and new labels are missing.

- [ ] **Step 4: Implement helpers and labels**

```js
function stageStatus(stage = {}) {
  if (stage.confirmation?.confirmed) return "complete";
  return (stage.validation?.warnings || stage.warnings || []).length ? "needs_attention" : "pending";
}

function nextUnconfirmedStageId(model = {}, currentStageId = "") {
  const stages = [...(model.stages || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  const index = stages.findIndex((stage) => stage.id === currentStageId);
  return [...stages.slice(index + 1), ...stages.slice(0, Math.max(index, 0))]
    .find((stage) => !stage.confirmation?.confirmed)?.id || null;
}
```

Export both helpers. Replace the six short tabs with the five tested planner tasks; keep existing route values and move diagram review under gameplay.

- [ ] **Step 5: Run both tests and confirm they pass**

- [ ] **Step 6: Commit Task 1**

Run: `git add -- js/review-workspace.js index.html tests/js/review-workspace.test.js tests/test_review_workspace_ui_contract.py`

Run: `git commit -m "feat: use planner-facing review navigation"`

### Task 2: Four-step planner presentation

**Files:**
- Modify: `js/stage-review.js`
- Test: `tests/js/stage-review.test.js`

**Interfaces:**
- Consumes: stage entry, trigger, response, result, rules, and unresolved questions.
- Produces: `plannerSteps(model, stage): Array<{key,title,content,rules,questions}>`.

- [ ] **Step 1: Write the failing adapter test**

```js
test("planner steps preserve causal reading order", () => {
  const stage = {
    entryCondition: "升级菜单尚未打开",
    trigger: "玩家点击升级按钮",
    systemResponse: "弹出三个武器选项",
    exitCondition: "玩家可以选择一种强化",
    unresolvedQuestions: ["是否允许重复选择？"],
  };
  const steps = StageReview.plannerSteps({}, stage);
  assert.deepEqual(steps.map((item) => item.title), ["操作前", "玩家操作", "系统反馈", "操作结果"]);
  assert.equal(steps[1].content, "玩家点击升级按钮");
  assert.deepEqual(steps[3].questions, ["是否允许重复选择？"]);
});
```

- [ ] **Step 2: Write the failing Chinese fallback test**

```js
test("unknown values become Chinese questions", () => {
  const steps = StageReview.plannerSteps({}, { trigger: "unknown" });
  assert.equal(steps[1].content, "需要补充玩家如何触发这一步");
  assert.doesNotMatch(JSON.stringify(steps), /unknown|component|entry|result/i);
});
```

- [ ] **Step 3: Run `node --test tests/js/stage-review.test.js` and confirm failure**

- [ ] **Step 4: Implement the adapter**

```js
const STEP_FIELDS = [
  ["before", "操作前", "entryCondition", "需要补充操作发生前的页面状态"],
  ["action", "玩家操作", "trigger", "需要补充玩家如何触发这一步"],
  ["feedback", "系统反馈", "systemResponse", "需要补充系统给玩家的即时反馈"],
  ["result", "操作结果", "exitCondition", "需要补充操作完成后的状态"],
];

function readableValue(value, fallback) {
  const text = String(value || "").trim();
  return !text || /^(unknown|n\/a|null)$/i.test(text) ? fallback : text;
}

function plannerSteps(model = {}, stage = {}) {
  return STEP_FIELDS.map(([key, title, fieldName, fallback]) => ({
    key, title, content: readableValue(stage[fieldName], fallback),
    rules: contextualRules(model, stage, key),
    questions: key === "result" ? [...(stage.unresolvedQuestions || [])] : [],
  }));
}
```

Map input/mutual exclusion rules to action, visible/audio/animation feedback to feedback, and persistence/navigation/state changes to result. Put unmapped non-blockers under `稍后补充`.

- [ ] **Step 5: Replace the default renderer**

Render semantic stage navigation and four vertical cards. Add a closed `查看原始截图` disclosure that reuses existing frame/region tools when opened. Remove always-visible representative-frame selectors, component table, summary, `small loop`, and raw region list.

- [ ] **Step 6: Add source assertions for the four labels and absence of old concepts**

- [ ] **Step 7: Run the stage tests and commit**

Run: `git add -- js/stage-review.js tests/js/stage-review.test.js`

Run: `git commit -m "feat: add single-operation planner review"`

### Task 3: Deterministic confirmation and readable failures

**Files:**
- Modify: `js/backend.js`
- Modify: `js/review-workspace.js`
- Test: `tests/js/screenshot-backend.test.js`

**Interfaces:**
- Consumes: `nextUnconfirmedStageId()`, `confirmStage()`, and `loadReviewPreview({flushPending:false})`.
- Produces: `confirmStatus: idle|saving|failed`, `confirmError`, and automatic selection/routing.

- [ ] **Step 1: Add a failing pending/success test**

```js
test("confirmation shows progress then advances", async () => {
  const pending = deferred();
  context.state.reviewClient.confirmStage = () => pending.promise;
  const action = context.confirmReviewEntity("stage");
  assert.equal(context.state.reviewWorkspace.confirmStatus, "saving");
  pending.resolve(modelWithFirstStageConfirmed);
  await action;
  assert.equal(context.state.reviewWorkspace.selectedStageId, "STG-002");
});
```

- [ ] **Step 2: Add a failing error test**

```js
test("failure keeps selection and exposes retryable Chinese feedback", async () => {
  context.state.reviewClient.confirmStage = async () => { throw new Error("HTTP 400 internal detail"); };
  await context.confirmReviewEntity("stage");
  assert.equal(context.state.reviewWorkspace.selectedStageId, "STG-001");
  assert.equal(context.state.reviewWorkspace.confirmStatus, "failed");
  assert.match(context.state.reviewWorkspace.confirmError, /保存失败|重试/);
  assert.doesNotMatch(context.state.reviewWorkspace.confirmError, /HTTP 400|internal detail/);
});
```

- [ ] **Step 3: Run the focused backend JS tests and confirm failure**

- [ ] **Step 4: Implement pending, success, and failure transitions**

Before awaiting, set saving state and disable the button. On success select the next unconfirmed stage or load interaction preview after the last stage. On failure preserve the model and selection and show: `当前环节保存失败，内容仍已保留。请检查服务状态后重试。` Raw errors go only to diagnostic logging.

- [ ] **Step 5: Render `正在保存…`, a live status, and retry button**

- [ ] **Step 6: Run `node --test tests/js/screenshot-backend.test.js tests/js/review-workspace.test.js` and commit**

Run: `git add -- js/backend.js js/review-workspace.js tests/js/screenshot-backend.test.js`

Run: `git commit -m "fix: make stage confirmation deterministic"`

### Task 4: Planner-first responsive layout

**Files:**
- Modify: `css/review-workspace.css`
- Modify: `index.html`
- Test: `tests/test_review_workspace_ui_contract.py`

**Interfaces:**
- Consumes: planner navigation/cards/drawer/status classes from Tasks 1–3.
- Produces: desktop and mobile reading hierarchy with visible interaction states.

- [ ] **Step 1: Add a failing CSS contract**

```python
def test_planner_layout_has_reading_and_feedback_states():
    css = Path("css/review-workspace.css").read_text(encoding="utf-8")
    for selector in [".planner-stage-nav", ".planner-step-list", ".planner-step-card",
                     ".planner-evidence-drawer", ".review-confirm-status.is-error",
                     ".review-confirm-status.is-saving"]:
        assert selector in css
    assert "@media (max-width: 900px)" in css
    assert ":focus-visible" in css
```

- [ ] **Step 2: Run the contract and confirm failure**

- [ ] **Step 3: Implement desktop hierarchy**

Use a neutral background, one blue action color, 16–20 px headings, 14–16 px body copy, 24 px section rhythm, and no decorative gradients. Use a 220–260 px stage navigation and a central reading column no wider than 960 px.

```css
.planner-step-list { display: grid; gap: 16px; max-width: 960px; margin-inline: auto; }
.planner-step-card { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 20px; padding: 22px 24px; }
.review-confirm-status.is-saving { color: var(--brand); }
.review-confirm-status.is-error { color: #b42318; background: #fff4f2; }
```

- [ ] **Step 4: At 900 px and below, stack navigation and cards; preserve 44 px targets, focus outlines, reduced motion, and native disclosure keyboard behavior**

- [ ] **Step 5: Run UI contracts and stage tests, then commit**

Run: `git add -- css/review-workspace.css index.html tests/test_review_workspace_ui_contract.py`

Run: `git commit -m "style: establish planner-first review hierarchy"`

### Task 5: Two-board and one-document guardrails

**Files:**
- Modify: `js/export-preview.js`
- Modify: `backend/feishu_native_board.py`
- Modify: `backend/gameplay_render.py`
- Test: `tests/js/export-preview.test.js`
- Test: `tests/test_gve16_native_whiteboard.py`
- Test: `tests/test_gameplay_render.py`

**Interfaces:**
- Consumes: confirmed interaction revision, planning board, optional competitor assets, gameplay chapters.
- Produces: exactly two boards and one combined document.

- [ ] **Step 1: Add tightened delivery tests**

```python
def test_active_delivery_has_two_boards_in_one_document(rendered_delivery):
    assert [board.title for board in rendered_delivery.native_boards] == ["策划草图", "竞品参考"]
    xml = rendered_delivery.xml
    assert xml.index("策划草图") < xml.index("竞品参考") < xml.index("玩法章节")
    assert "UX设计" not in xml
```

```js
test("preview hides internal diagnostics", () => {
  const html = ExportPreview.renderFixture(twoBoardPreview);
  assert.match(html, /策划草图/);
  assert.match(html, /竞品参考/);
  assert.doesNotMatch(html, /代表帧|component|SCN-|EVT-|UX设计/);
});
```

- [ ] **Step 2: Run focused delivery tests and identify gaps**

- [ ] **Step 3: Replace diagnostic preview copy with outcome copy while retaining internal data**

- [ ] **Step 4: Verify active whiteboards are planning then competitor, and gameplay plus pending checklist append to the same document tree**

- [ ] **Step 5: Run delivery tests and commit only changed files**

Run: `node --test tests/js/export-preview.test.js && python -m pytest tests/test_gve16_native_whiteboard.py tests/test_gameplay_render.py tests/test_feishu_publish.py -q`

Run: `git commit -m "fix: guard unified two-board delivery"`

### Task 6: Browser regression and lead-planner audit

**Files:**
- Modify: `tools/review-workspace-browser-qa.js`
- Modify: `tests/test_review_workspace_browser_qa_contract.py`
- Create: `docs/research/2026-08-03-lead-planner-workspace-audit.md`

**Interfaces:**
- Consumes: running local service and seeded review task.
- Produces: reproducible browser QA and P0–P3 audit results.

- [ ] **Step 1: Add browser checks for four-step order, keyboard navigation, evidence drawer, mutual exclusion, auto-advance, save failure/retry, refresh restoration, empty competitor assets, long Chinese copy, 1440×900, and 390×844**

```js
await expect(page.getByText("操作前")).toBeVisible();
await expect(page.getByText("玩家操作")).toBeVisible();
await expect(page.getByText("系统反馈")).toBeVisible();
await expect(page.getByText("操作结果")).toBeVisible();
await page.getByRole("button", { name: /确认当前环节/ }).click();
await expect(page.locator("body")).not.toContainText(/unknown|component|代表帧|small loop/i);
```

- [ ] **Step 2: Run `python -m pytest tests/test_review_workspace_browser_qa_contract.py -q`**

- [ ] **Step 3: Run full automated suites**

Run: `node --test tests/js/*.test.js`

Run: `python -m pytest -q`

Expected: all tests pass; if an unrelated optional package cannot load in the bundled runtime, record the exact error and run every touched suite explicitly.

- [ ] **Step 4: Run `node tools/review-workspace-browser-qa.js --base-url http://127.0.0.1:8000` and inspect desktop/mobile screenshots**

- [ ] **Step 5: Write the lead-planner audit**

```markdown
| Priority | Location | Finding | User impact | Required fix | Status |
|---|---|---|---|---|---|
```

Use P0 for data loss/unusable publishing, P1 for blocked or incorrect main flow, P2 for serious comprehension or interaction inconsistency, and P3 for visual/copy polish. Fix all P0/P1 issues before completion; list remaining P2/P3 items explicitly.

- [ ] **Step 6: Run `git diff --check` and `git status --short`; verify unrelated dirty files remain untouched**

- [ ] **Step 7: Commit QA and audit files**

Run: `git add -- tools/review-workspace-browser-qa.js tests/test_review_workspace_browser_qa_contract.py docs/research/2026-08-03-lead-planner-workspace-audit.md`

Run: `git commit -m "test: audit planner review workflow"`
