# Compact Interaction Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and review 3–7 functional interaction stages with 1–3 representative frames, a compact Chinese summary, and one on-demand component editor without changing the GVE16 export schema.

**Architecture:** Add deterministic adjacent-stage compaction to review-model generation, leaving confirmed persisted models untouched. Keep the canonical model as the source of truth; add pure workspace selection helpers and render the compact stage UI from existing stage, region, component, transition, and source fields.

**Tech Stack:** Python 3.12, FastAPI, pytest, vanilla JavaScript, Node `node:test`, existing GVE16 review model schema.

## Global Constraints

- New generated review models contain 3–7 functional stages when at least three meaningful stages exist.
- Merge only adjacent stages and preserve screenshot/video order.
- Each stage contains 1–3 representative frames; remaining sources stay available through “查看全部截图”.
- `unknown` is displayed as “待确认” and does not block flow-order confirmation.
- Existing manually confirmed review models are never silently regrouped.
- No English internal field names appear in the default stage summary.
- Existing planning, competitor, preview, and Feishu export contracts remain unchanged.
- Add no production dependency.

---

### Task 1: Deterministic functional-stage compaction

**Files:**
- Modify: `backend/review_model.py`
- Test: `tests/test_review_model_seed.py`

**Interfaces:**
- Consumes: `job["scenes"]`, `_stage(index, scene)` and each stage's `sourceSceneId`, `name`, `goal`, `entry`, `representativeFrames`.
- Produces: `compact_generated_stages(stages: list[dict[str, Any]], sources: dict[str, Any], minimum: int = 3, maximum: int = 7) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write failing tests for the stage ceiling, adjacency, and order**

```python
def test_generated_review_compacts_adjacent_functional_stages_to_seven():
    job = seeded_job_with_scene_titles([
        "普通战斗-开始", "普通战斗-持续", "武器选择-展开", "武器选择-结果",
        "技能选择", "Boss预警", "Boss战斗", "Boss战斗-持续", "胜利结算",
    ])
    model = build_review_model(job)
    assert 3 <= len(model["stages"]) <= 7
    assert [source["frameId"] for source in model["sources"].values()] == [f"F{i:04d}" for i in range(1, 10)]
    assert all(1 <= len(stage["representativeFrames"]) <= 3 for stage in model["stages"])


def test_generated_review_never_merges_non_adjacent_matching_titles():
    model = build_review_model(seeded_job_with_scene_titles(["普通战斗", "武器选择", "普通战斗"]))
    assert [stage["name"] for stage in model["stages"]] == ["普通战斗", "武器选择", "普通战斗"]
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_review_model_seed.py -q`

Expected: the nine-scene fixture produces more than seven stages.

- [ ] **Step 3: Implement normalized adjacent grouping and stable frame selection**

```python
FUNCTION_SUFFIX = re.compile(r"(?:[-—：:]?(?:开始|持续|展开|结果|过程|阶段\d+))$")


def _functional_key(stage: dict[str, Any]) -> str:
    return FUNCTION_SUFFIX.sub("", str(stage.get("name") or "").strip()).strip().lower()


def _compact_representatives(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    ordered = []
    seen = set()
    for stage in items:
        for frame in stage.get("representativeFrames") or []:
            frame_id = frame.get("frameId")
            if frame_id and frame_id not in seen:
                seen.add(frame_id)
                ordered.append({"frameId": frame_id, "role": frame.get("role") or "change"})
    if len(ordered) <= 3:
        return ordered
    return [ordered[0], ordered[len(ordered) // 2], ordered[-1]]


def compact_generated_stages(stages, sources, minimum=3, maximum=7):
    groups = [[stage] for stage in stages]
    while len(groups) > maximum:
        index = next((i for i in range(len(groups) - 1) if _functional_key(groups[i][-1]) == _functional_key(groups[i + 1][0])), None)
        if index is None:
            index = min(range(len(groups) - 1), key=lambda i: len(groups[i]) + len(groups[i + 1]))
        groups[index:index + 2] = [groups[index] + groups[index + 1]]
    return [_merge_generated_stage_group(group, order) for order, group in enumerate(groups, 1)]
```

`_merge_generated_stage_group` must retain the first stage ID and source scene ID, use the first non-unknown name/goal/entry, concatenate owned source IDs in input order, call `_compact_representatives`, and set `order` to the supplied value.

- [ ] **Step 4: Apply compaction only while building a new model**

Call `compact_generated_stages` inside `build_review_model()` before transitions are created. Do not call it from `ensure_review_model()` when `job["reviewModel"]` already exists.

- [ ] **Step 5: Run focused and model validation tests**

Run: `python -m pytest tests/test_review_model_seed.py tests/test_review_model.py tests/test_review_workflow_integration.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/review_model.py tests/test_review_model_seed.py
git commit -m "feat: compact generated interaction stages"
```

### Task 2: Stage switching resets frame and component context

**Files:**
- Modify: `js/review-workspace.js`
- Modify: `js/backend.js`
- Test: `tests/js/review-workspace.test.js`

**Interfaces:**
- Consumes: canonical `model.stages`, stage `representativeFrames`, current workspace state.
- Produces: `selectStage(state, model, stageId)` returning a new workspace state.

- [ ] **Step 1: Write the failing state-reset test**

```javascript
test("selecting another stage resets frame region component and transition context", () => {
  const model = { stages: [
    { id: "STG-001", representativeFrames: [{ frameId: "F1" }] },
    { id: "STG-002", representativeFrames: [{ frameId: "F2" }] },
  ], sources: { F1: {}, F2: {} } };
  const current = { ...ReviewWorkspace.initialState(model), selectedFrameId: "F1", selectedTransitionId: "TRN-1", selection: { type: "component", id: "CMP-1", stageId: "STG-001", frameId: "F1" } };
  assert.deepEqual(ReviewWorkspace.selectStage(current, model, "STG-002"), {
    ...current, selectedStageId: "STG-002", selectedFrameId: "F2", selectedTransitionId: null, selection: null,
  });
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test tests/js/review-workspace.test.js`

Expected: FAIL because `selectStage` is not exported.

- [ ] **Step 3: Implement the pure transition**

```javascript
function selectStage(state, model, stageId) {
  const stage = (model.stages || []).find((item) => item.id === stageId);
  if (!stage || stage.id === state.selectedStageId) return state;
  return { ...state, selectedStageId: stage.id, selectedFrameId: stage.representativeFrames?.[0]?.frameId || null, selectedTransitionId: null, selection: null };
}
```

Export it through the existing `ReviewWorkspace` CommonJS/browser export block.

- [ ] **Step 4: Route every stage-title click through `selectStage`**

In `js/backend.js`, replace direct `selectedStageId` assignment for the stage rail with:

```javascript
state.reviewWorkspace = ReviewWorkspace.selectStage(state.reviewWorkspace, model, stageId);
renderReviewWorkspace(model);
persistReviewUiState();
```

- [ ] **Step 5: Run focused tests**

Run: `node --test tests/js/review-workspace.test.js tests/js/review-persistence.test.js`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add js/review-workspace.js js/backend.js tests/js/review-workspace.test.js
git commit -m "fix: reset stage review context on navigation"
```

### Task 3: Compact Chinese stage summary

**Files:**
- Modify: `js/stage-review.js`
- Modify: `css/review-workspace.css`
- Test: `tests/js/stage-review.test.js`

**Interfaces:**
- Consumes: stage `name`, `goal`, `entry`, `smallLoop`, owned components, and `unknown` values.
- Produces: `stageSummary(stage, components) -> Array<{label: string, value: string}>` and a `.stage-summary-card` renderer.

- [ ] **Step 1: Write failing summary tests**

```javascript
test("stage summary uses six Chinese labels and maps unknown to pending", () => {
  assert.deepEqual(StageReview.stageSummary({ name: "武器选择", goal: "unknown", entry: "点击武器栏", smallLoop: { trigger: "tap", feedback: "弹出三选一", result: "装备武器" } }, [{ name: "武器卡" }]), [
    { label: "页面/环节名称", value: "武器选择" },
    { label: "当前目标", value: "待确认" },
    { label: "如何进入", value: "点击武器栏" },
    { label: "用户操作或自动触发", value: "tap" },
    { label: "系统反馈与结果", value: "弹出三选一；装备武器" },
    { label: "关键组件", value: "武器卡" },
  ]);
});
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test tests/js/stage-review.test.js`

Expected: FAIL because `stageSummary` is not defined.

- [ ] **Step 3: Implement normalization and summary projection**

```javascript
function plannerText(value) {
  const text = String(value || "").trim();
  return !text || text.toLowerCase() === "unknown" ? "待确认" : text;
}

function stageSummary(stage = {}, components = []) {
  const loop = stage.smallLoop || {};
  return [
    ["页面/环节名称", stage.name], ["当前目标", stage.goal], ["如何进入", stage.entry],
    ["用户操作或自动触发", loop.trigger],
    ["系统反馈与结果", [loop.feedback, loop.result].filter(Boolean).join("；")],
    ["关键组件", components.map((item) => item.name || item.title).filter(Boolean).join("、")],
  ].map(([label, value]) => ({ label, value: plannerText(value) }));
}
```

- [ ] **Step 4: Make the summary the default right panel**

Render one `<section class="stage-summary-card">` containing an `<h3>` and six `<dl>` rows before any editor. Do not render property keys such as `smallLoop`, `triggerType`, `regionIds`, or `componentStates` as visible text.

- [ ] **Step 5: Add compact responsive styling**

```css
.stage-summary-card { display: grid; gap: 12px; padding: 16px; border: 1px solid var(--line); border-radius: 16px; background: var(--surface); }
.stage-summary-row { display: grid; gap: 4px; }
.stage-summary-row dt { color: var(--muted); font-size: 12px; }
.stage-summary-row dd { margin: 0; line-height: 1.6; }
```

- [ ] **Step 6: Run focused tests and syntax check**

Run: `node --test tests/js/stage-review.test.js && node --check js/stage-review.js`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add js/stage-review.js css/review-workspace.css tests/js/stage-review.test.js
git commit -m "feat: add compact Chinese stage summary"
```

### Task 4: One on-demand component editor

**Files:**
- Modify: `js/stage-review.js`
- Test: `tests/js/stage-review.test.js`

**Interfaces:**
- Consumes: `workspace.selection`, stage-owned regions/components and the canonical component-state operation callbacks.
- Produces: `selectedComponent(model, stageId, selection) -> component | null` and exactly one mounted detail editor.

- [ ] **Step 1: Write selection tests**

```javascript
test("component detail opens only for the selected component or its numbered region", () => {
  const model = { components: [{ id: "CMP-1", stageId: "STG-1", regionId: "REG-1" }] };
  assert.equal(StageReview.selectedComponent(model, "STG-1", { type: "component", id: "CMP-1" }).id, "CMP-1");
  assert.equal(StageReview.selectedComponent(model, "STG-1", { type: "region", id: "REG-1" }).id, "CMP-1");
  assert.equal(StageReview.selectedComponent(model, "STG-2", { type: "component", id: "CMP-1" }), null);
  assert.equal(StageReview.selectedComponent(model, "STG-1", null), null);
});
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test tests/js/stage-review.test.js`

Expected: FAIL because `selectedComponent` is not defined.

- [ ] **Step 3: Implement selection resolution**

```javascript
function selectedComponent(model, stageId, selection) {
  if (!selection) return null;
  return (model.components || []).find((component) => component.stageId === stageId && (
    (selection.type === "component" && component.id === selection.id) ||
    (selection.type === "region" && component.regionId === selection.id)
  )) || null;
}
```

- [ ] **Step 4: Replace the all-components form wall**

Remove the unconditional `renderComponentStates(right, workspace, stage)` call. Render a compact list of component names/buttons; when `selectedComponent(...)` returns a component, pass only that component to a renamed `renderComponentEditor` function. Keep existing revisioned operations and field labels.

- [ ] **Step 5: Run stage and workspace tests**

Run: `node --test tests/js/stage-review.test.js tests/js/review-workspace.test.js tests/js/review-persistence.test.js`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add js/stage-review.js tests/js/stage-review.test.js
git commit -m "feat: show one component editor on demand"
```

### Task 5: Compatibility, regression, and browser acceptance

**Files:**
- Modify: `tests/test_review_workflow_integration.py`
- Modify: `tests/test_planning_model.py`
- Modify: `tests/js/review-workspace.test.js`
- Modify: `tools/review-workspace-live-browser-qa.js`
- Modify: `CURRENT_STATE.md`

**Interfaces:**
- Consumes: compact model output and unchanged `build_standard_prompt`, preview, planning, and Feishu render inputs.
- Produces: automated proof that compact review changes presentation/grouping without losing canonical export data.

- [ ] **Step 1: Add an export compatibility regression**

```python
def test_compact_review_preserves_gve16_export_entities_in_source_order():
    job = completed_compact_review_job()
    planning = build_planning_model(job)
    assert [item["frameId"] for item in planning["evidenceIndex"]] == job["orderedFrameIds"]
    assert planning["interaction"]["stages"]
    assert all(1 <= len(stage["representativeFrames"]) <= 3 for stage in job["reviewModel"]["stages"])
```

- [ ] **Step 2: Add browser assertions**

In `tools/review-workspace-live-browser-qa.js`, after opening stage review, assert:

```javascript
await expectStageCountBetween(page, 3, 7);
await clickStageTitle(page, 1);
await assertVisibleText(page, ["页面/环节名称", "当前目标", "如何进入", "关键组件"]);
await assertNoVisibleText(page, ["triggerType", "smallLoop", "componentStates"]);
await clickStageTitle(page, 2);
await assertSelectionResetToFirstRepresentative(page);
await clickFirstNumberedRegion(page);
await assertExactlyOneComponentEditor(page);
```

- [ ] **Step 3: Run all automated tests**

Run: `python -m pytest -q`

Expected: 490 or more passed, zero failures.

Run: `node --test tests/js/*.test.js`

Expected: 182 or more passed, zero failures.

- [ ] **Step 4: Run syntax and compile checks**

Run: `python -m compileall -q backend tests`

Expected: exit 0.

Run: `node --check js/review-workspace.js && node --check js/stage-review.js && node --check js/backend.js`

Expected: exit 0.

- [ ] **Step 5: Run real local browser QA without Feishu publication**

Run the existing live browser QA at 1440×900 and 390×844. Verify 3–7 titles, synchronized stage/frame/summary switching, no stale selection, one component editor, keyboard focus, and no horizontal overflow. Intercept `/feishu/publish`; no external document may be created.

- [ ] **Step 6: Update authoritative state**

Record exact Python/Node counts, browser viewport results, remaining warnings, and the resulting commit in `CURRENT_STATE.md`, `handoff_state.json`, `progress.md`, and `task_plan.md`.

- [ ] **Step 7: Commit**

```bash
git add tests tools CURRENT_STATE.md handoff_state.json progress.md task_plan.md
git commit -m "test: verify compact interaction review workflow"
```

## Self-Review

- Spec coverage: stage count, adjacency, ordering, representative-frame limits, unknown handling, selection reset, Chinese summary, one component editor, persisted-model safety, GVE16 compatibility, automated tests, and browser QA are each assigned to a task.
- Placeholder scan: every implementation and verification step contains concrete code or an exact command.
- Type consistency: `compact_generated_stages`, `selectStage`, `stageSummary`, and `selectedComponent` have one spelling and one responsibility throughout the plan.
