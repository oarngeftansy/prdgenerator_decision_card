# 玩法章节结论卡片式审核 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把玩法章节审核改成以玩法结论、参考画面和三个互斥判断为核心的策划审核卡片。

**Architecture:** 保留现有玩法审核模型与后端操作协议，只调整 `gameplay-review.js` 的前端视图分层和 `backend.js` 的审核结果映射。补充细节继续使用现有操作类型，通过显式展开状态控制显示，不增加数据迁移。

**Tech Stack:** 原生 JavaScript、DOM、CSS、Node.js `node:test`、Python/pytest 后端契约测试。

## Global Constraints

- 默认只展示章节名称、不超过四句话的玩法结论、最多三张原比例参考画面和三个互斥判断。
- 判断文案必须是“识别正确”“部分正确，需要修改”“这一章不适用”。
- 空白数值、内部字段、关联标识和程序状态不得出现在默认界面。
- 补充细节只能由有效内容、阻断问题、选择修改或策划主动展开触发。
- 保存或点击空白处不得自动收起用户已经展开的内容。
- 不修改视觉模型识别、玩法目录自动拆分或最终飞书章节结构。

---

### Task 1: 章节结论与互斥判断卡片

**Files:**
- Modify: `js/gameplay-review.js`
- Modify: `css/gameplay-review.css`
- Test: `tests/js/gameplay-review.test.js`

**Interfaces:**
- Consumes: `workspace.model.chapters[]`、`workspace.state.selectedChapterId`、`workspace.onDecision(decision)`。
- Produces: `decisionOptions()`，返回 `{ value, label }[]`；章节卡片通过 `data-gameplay-decision` 暴露三种用户判断。

- [ ] **Step 1: 写默认卡片的失败测试**

```javascript
test("planner first sees the gameplay conclusion evidence and three decisions", () => {
  const current = chapter({ plannerSections: { summary: "玩家升级后选择一项强化，选择后立即生效并继续战斗。" } });
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  assert.match(root.textContent, /玩家升级后选择一项强化/);
  assert.deepEqual(root.querySelectorAll("[data-gameplay-decision]").map(node => node.textContent), ["识别正确", "部分正确，需要修改", "这一章不适用"]);
  assert.equal(root.querySelector(".gameplay-parameters"), null);
  assert.equal(root.querySelector(".gameplay-dependency-editor"), null);
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test tests/js/gameplay-review.test.js`

Expected: FAIL，现有判断仍显示“通过／有条件通过／退回修改”，或者默认渲染补充字段。

- [ ] **Step 3: 实现三个策划判断和默认精简视图**

```javascript
function decisionOptions() {
  return [
    { value: "approved", label: "识别正确" },
    { value: "needs_edit", label: "部分正确，需要修改" },
    { value: "not_applicable", label: "这一章不适用" },
  ];
}

function renderDecisionCard(editor, workspace, chapter) {
  const section = el("section", "", { class: "gameplay-decision-card" });
  section.append(el("h3", "AI 对这部分玩法的理解正确吗？"));
  const choices = el("div", "", { class: "gameplay-decision-options", role: "radiogroup" });
  decisionOptions().forEach(({ value, label }) => {
    const choice = button(label, () => workspace.onDecision?.(value), "gameplay-decision-option");
    choice.setAttribute("data-gameplay-decision", value);
    choice.setAttribute("role", "radio");
    choice.setAttribute("aria-checked", String(workspace.state?.draftDecision === value));
    choices.append(choice);
  });
  section.append(choices);
  editor.append(section);
}
```

在章节主体中只调用结论、`renderInlineEvidence` 和 `renderDecisionCard`；不要默认调用 `renderParameters` 或 `renderIssues`。导出 `decisionOptions` 供测试使用。

- [ ] **Step 4: 添加卡片布局并运行测试**

```css
.gameplay-decision-card { display: grid; gap: 12px; padding: 20px; border: 1px solid var(--line); border-radius: 12px; background: #fff; }
.gameplay-decision-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.gameplay-decision-option[aria-checked="true"] { border-color: #315efb; background: #eef3ff; color: #163fbd; }
@media (max-width: 760px) { .gameplay-decision-options { grid-template-columns: 1fr; } }
```

Run: `node --test tests/js/gameplay-review.test.js`

Expected: PASS，包括原有原比例图片、展开状态和无 `undefined` 文案测试。

- [ ] **Step 5: 提交本任务**

```bash
git add js/gameplay-review.js css/gameplay-review.css tests/js/gameplay-review.test.js
git commit -m "feat: lead gameplay review with planner decisions"
```

### Task 2: 需要修改与按需补充细节

**Files:**
- Modify: `js/gameplay-review.js`
- Modify: `js/backend.js`
- Modify: `css/gameplay-review.css`
- Test: `tests/js/gameplay-review.test.js`
- Test: `tests/js/screenshot-backend.test.js`

**Interfaces:**
- Consumes: `workspace.state.draftDecision`、`workspace.state.expandedGroups`、现有 `workspace.onOperation(batch)` 和 `workspace.onToggleGroup(chapterId, group)`。
- Produces: `hasSupplementalDetails(chapter, findings)`；选择 `needs_edit` 时显示 `.gameplay-planner-summary-editor`，有效补充内容显示 `.gameplay-supplemental-details`。

- [ ] **Step 1: 写按需编辑与补充细节的失败测试**

```javascript
test("editing appears only for a partial result and supplemental details require real content", () => {
  const current = chapter({ parameters: {}, dependencies: [], acceptanceCases: [], unknowns: [] });
  const compact = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  assert.equal(compact.root.querySelector(".gameplay-planner-summary-editor"), null);
  assert.equal(compact.root.querySelector(".gameplay-supplemental-details"), null);

  const editing = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id, draftDecision: "needs_edit" });
  assert.ok(editing.root.querySelector(".gameplay-planner-summary-editor"));
  assert.ok(editing.root.querySelector(".gameplay-supplemental-details"));
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test tests/js/gameplay-review.test.js`

Expected: FAIL，编辑区和统一补充入口尚不存在。

- [ ] **Step 3: 实现内容判断、编辑区和统一补充入口**

```javascript
function hasSupplementalDetails(chapter, findings = []) {
  return configuredParameterFields(chapter).length > 0
    || (chapter.dependencies || []).length > 0
    || (chapter.acceptanceCases || []).length > 0
    || (chapter.unknowns || []).length > 0
    || findings.some(item => item.chapterId === chapter.id && item.status !== "resolved");
}

function renderSummaryEditor(parent, workspace, chapter) {
  const editor = field("修改后的玩法说明", chapterSummary(chapter), "textarea");
  editor.wrap.setAttribute("class", "gameplay-field gameplay-planner-summary-editor");
  editor.input.addEventListener("blur", () => {
    const value = required(editor.input, "玩法说明");
    if (value) workspace.onOperation?.([chapterOperation(chapter.id, "plannerSummary", value)]);
  });
  parent.append(editor.wrap);
}
```

选择 `needs_edit` 时渲染编辑区。存在有效内容、阻断问题或 `needs_edit` 时渲染标题为“补充细节”的 `details.gameplay-supplemental-details`，内部复用已有 `renderParameters`、`renderIssues` 和规则来源编辑能力；空分组不追加到 DOM。

- [ ] **Step 4: 把选择状态接入工作台且不清空草稿**

```javascript
onDecision(value) {
  state.gameplayDraftDecision = value;
  renderGameplayReview();
}
```

`renderGameplayReview` 将 `state.gameplayDraftDecision` 传入 `workspace.state.draftDecision`。只有最终提交成功后才清空当前章节的草稿判断；重新渲染、保存失败和切换补充细节不得清空。

- [ ] **Step 5: 运行前端测试并提交**

Run: `node --test tests/js/gameplay-review.test.js tests/js/screenshot-backend.test.js`

Expected: PASS，并继续满足“展开区域只能手动收起”。

```bash
git add js/gameplay-review.js js/backend.js css/gameplay-review.css tests/js/gameplay-review.test.js tests/js/screenshot-backend.test.js
git commit -m "feat: reveal gameplay details only when needed"
```

### Task 3: 判断结果保存、自动下一章和兼容性回归

**Files:**
- Modify: `js/backend.js`
- Modify: `js/gameplay-review.js`
- Modify: `backend/gameplay_review_service.py`
- Test: `tests/js/gameplay-review.test.js`
- Test: `tests/js/screenshot-backend.test.js`
- Test: `tests/test_gameplay_review_service.py`

**Interfaces:**
- Consumes: 前端判断 `approved | needs_edit | not_applicable`。
- Produces: 现有确认请求；`approved` 保存为通过，`needs_edit` 只保存草稿并留在当前章，`not_applicable` 保存为不适用且从最终正文排除。

- [ ] **Step 1: 写三个判断结果的失败契约测试**

```javascript
test("planner decisions map to save stay or skip behavior", () => {
  assert.deepEqual(GameplayReview.decisionAction("approved"), { decision: "approved", advance: true });
  assert.deepEqual(GameplayReview.decisionAction("needs_edit"), { decision: null, advance: false });
  assert.deepEqual(GameplayReview.decisionAction("not_applicable"), { decision: "not_applicable", advance: true });
});
```

```python
def test_not_applicable_chapter_is_saved_and_excluded_from_publishable_chapters():
    updated = review_service.confirm_chapter(job_id, chapter_id, "not_applicable")
    assert updated["status"] == "not_applicable"
    assert chapter_id not in [item["id"] for item in review_service.publishable_chapters(job_id)]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test tests/js/gameplay-review.test.js tests/js/screenshot-backend.test.js`

Run: `python -m pytest tests/test_gameplay_review_service.py -q`

Expected: FAIL，当前服务没有完整的 `not_applicable` 映射或发布过滤。

- [ ] **Step 3: 实现前端动作映射和保存反馈**

```javascript
function decisionAction(value) {
  if (value === "approved") return { decision: "approved", advance: true };
  if (value === "not_applicable") return { decision: "not_applicable", advance: true };
  return { decision: null, advance: false };
}
```

`needs_edit` 只展开并保存修改，不提交章节结论；另外两项复用现有确认接口。提交期间禁用三个判断按钮并显示“正在保存审核结果…”。失败保留当前章节和草稿；成功使用现有 `nextPending` 进入下一章。

- [ ] **Step 4: 实现后端不适用状态兼容**

```python
if decision == "not_applicable":
    chapter["status"] = "not_applicable"
    chapter["confirmation"] = {"confirmed": True, "decision": "not_applicable"}
```

最终正文选择章节时过滤 `status == "not_applicable"`。旧任务没有该状态时保持原有行为，不迁移历史数据。

- [ ] **Step 5: 运行相关测试与完整前端回归**

Run: `node --test tests/js/gameplay-directory.test.js tests/js/gameplay-review.test.js tests/js/export-preview.test.js tests/js/screenshot-backend.test.js`

Run: `python -m pytest tests/test_gameplay_review_service.py tests/test_gameplay_render.py tests/test_feishu_publish.py -q`

Expected: 全部 PASS；已确认章节、最终预览和飞书发布测试不回退。

- [ ] **Step 6: 浏览器验收**

在当前任务中逐项验证：默认卡片、三项互斥、修改后编辑、按需补充、保存失败保留、保存成功自动下一章、刷新后状态恢复。浏览器控制台不得出现错误，界面不得出现 `undefined`、英文状态或空字段。

- [ ] **Step 7: 提交本任务**

```bash
git add js/backend.js js/gameplay-review.js backend/gameplay_review_service.py tests/js/gameplay-review.test.js tests/js/screenshot-backend.test.js tests/test_gameplay_review_service.py
git commit -m "feat: complete planner gameplay review decisions"
```
