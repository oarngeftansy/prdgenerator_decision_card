# 玩法文案与策划草图对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将玩法结论与交互证据彻底分层，并让网页预览和飞书原生白板使用同一套符合用户最新飞书样例的主线、阶段、分支、方向连线和黄色注记结构。

**Architecture:** 新增纯函数模块 `backend/gameplay_copy.py`，从章节机制生成策划可读的玩法摘要，并把截图声明保留为证据而不是规则正文。新增 `backend/planning_board_model.py` 作为网页 SVG 与飞书原生白板的共享中间结构，两个渲染器只负责表现，不再各自推导流程。

**Tech Stack:** Python 3.12、FastAPI、原生 JavaScript、SVG、飞书原生白板节点、pytest、Node test runner。

## Global Constraints

- 目录摘要只陈述素材已经支持的玩法结论。
- “需要在本节定义”“请策划确认”“后续需要补充”只允许出现在待确认事项中。
- 页面、按钮、弹窗、屏幕位置、颜色、边框和特效属于交互或视觉证据，不作为玩法概述。
- 专有名词首次使用“通用名称（素材中称‘原名’）”，后续使用通用名称；引用界面原文时保留原名。
- 网页预览与飞书白板必须具有相同的阶段顺序、截图、规则文字和连线方向。
- 前进/进入/打开使用实线；返回/关闭/回环使用虚线；待确认事项使用 `#fff3bf`。
- 红色数字编号属于后续 UE 流转图；本版本默认关闭，不作为预览或飞书策划白板的验收条件，但保留已有编译代码和可选扩展字段。
- 不重新调用视觉模型，不删除现有九个章节或十五张证据图。

---

### Task 1: 玩法文案分层与术语规范

**Files:**
- Create: `backend/gameplay_copy.py`
- Modify: `backend/gameplay_directory.py`
- Test: `tests/test_gameplay_copy.py`
- Test: `tests/test_gameplay_directory.py`

**Interfaces:**
- Consumes: gameplay chapter dictionaries containing `scope`, `mechanism`, `claims`, `unknowns`, and `parameters`.
- Produces: `normalize_game_term(text: str, *, first_use: bool) -> str`, `chapter_gameplay_summary(chapter: dict, *, first_use: bool = False) -> str`, `build_gameplay_overview(chapters: list[dict]) -> str`, `refresh_directory_copy(model: dict) -> dict`, and `migrate_gameplay_presentation(job: dict) -> dict`.

- [ ] **Step 1: Write failing terminology and evidence-separation tests**

```python
def test_chapter_summary_uses_mechanism_instead_of_interface_claims():
    chapter = {
        "scope": "终极词条入库与概率获取机制",
        "mechanism": {"type": "random_pool", "description": "终极词条属于高稀有度成长内容，获取后加入词条库。"},
        "claims": [{"text": "界面使用金色边框，点击后显示进入词条库。"}],
        "unknowns": ["后续抽取概率待确认"],
    }
    assert chapter_gameplay_summary(chapter, first_use=True) == (
        "终极强化（素材中称‘终极词条’）属于高稀有度成长内容，获取后加入强化库。"
    )

def test_directory_refresh_does_not_mutate_evidence_claims():
    before = deepcopy(model["chapters"][0]["claims"])
    refresh_directory_copy(model)
    assert model["chapters"][0]["claims"] == before
    assert "界面" not in model["directory"]["entries"][0]["summary"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/test_gameplay_copy.py tests/test_gameplay_directory.py -q`

Expected: FAIL because `backend.gameplay_copy` and the new functions do not exist.

- [ ] **Step 3: Implement deterministic gameplay copy**

```python
TERM_RULES = (
    ("终极词条", "终极强化", "终极词条"),
    ("词条库", "强化库", "词条库"),
    ("词条", "强化效果", "词条"),
    ("Boss", "首领", "Boss"),
)

INTERACTION_ONLY = re.compile(
    r"(?:屏幕(?:上方|下方|左侧|右侧)|左上角|右上角|界面底部|弹窗|按钮|边框|背景|特效|UI|HUD)",
    re.I,
)

def chapter_gameplay_summary(chapter: dict, *, first_use: bool = False) -> str:
    description = str((chapter.get("mechanism") or {}).get("description") or "").strip()
    if not description or INTERACTION_ONLY.search(description):
        description = str(chapter.get("scope") or "该玩法").strip()
    return normalize_game_term(description, first_use=first_use)

def refresh_directory_copy(model: dict) -> dict:
    directory = model.get("directory") or {}
    chapters = {item.get("id"): item for item in model.get("chapters") or []}
    for index, entry in enumerate(directory.get("entries") or []):
        chapter = chapters.get(entry.get("chapterId"))
        if chapter:
            entry["summary"] = chapter_gameplay_summary(chapter, first_use=index == 0)
    directory.setdefault("understanding", {})["summary"] = build_gameplay_overview(
        [chapters.get(item.get("chapterId")) for item in directory.get("entries") or []]
    )
    directory["presentationVersion"] = 2
    return model

def migrate_gameplay_presentation(job: dict) -> dict:
    model = job.get("gameplayReviewModel")
    if isinstance(model, dict) and (model.get("directory") or {}).get("presentationVersion", 0) < 2:
        refresh_directory_copy(model)
    return job
```

`build_gameplay_overview` takes at most the first three non-empty `plannerSummary` values, removes duplicate sentences, and returns at most four sentences. It never reads `claims`; unknown rules remain in chapter `unknowns`.

- [ ] **Step 4: Change directory synthesis to call the shared copy layer**

In `synthesize_directory`, keep title grouping and ownership intact, then construct the model and call `refresh_directory_copy`. Do not use `_claim_texts(draft)[:2]` as `entry.summary` or `understanding.summary`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_gameplay_copy.py tests/test_gameplay_directory.py -q`

Expected: PASS; evidence claims are byte-for-byte unchanged.

- [ ] **Step 6: Commit**

```bash
git add backend/gameplay_copy.py backend/gameplay_directory.py tests/test_gameplay_copy.py tests/test_gameplay_directory.py
git commit -m "feat: separate gameplay summaries from interaction evidence"
```

### Task 2: 工作台和最终飞书正文使用玩法摘要

**Files:**
- Modify: `js/gameplay-review.js`
- Modify: `js/gameplay-directory.js`
- Modify: `backend/gameplay_render.py`
- Modify: `backend/gameplay_review_model.py`
- Test: `tests/js/gameplay-review.test.js`
- Test: `tests/js/gameplay-directory.test.js`
- Test: `tests/test_gameplay_render.py`
- Test: `tests/test_gameplay_review_model.py`

**Interfaces:**
- Consumes: Task 1 `chapter_gameplay_summary` and `refresh_directory_copy`.
- Produces: chapter JSON field `plannerSummary`; workbench and Feishu renderers use it for gameplay conclusions while retaining `claims` as evidence.

- [ ] **Step 1: Write failing workbench and final-output tests**

```javascript
test("chapter summary does not present interface evidence as gameplay", () => {
  const item = chapter({
    plannerSummary: "局内成长触发后，玩家从三项候选强化效果中选择一项。",
    claims: [{ text: "弹出选择武器界面，底部显示刷新按钮。", sourceType: "material", sourceFrameIds: ["F0001"] }],
  });
  assert.equal(GameplayReview.chapterSummary(item), item.plannerSummary);
});
```

```python
def test_final_gameplay_rule_uses_planner_summary_and_keeps_claim_as_evidence():
    xml = render_gameplay_document_sections(job).xml
    assert "<b>玩法规则：</b>局内成长触发后" in xml
    assert "<b>素材证据：</b>弹出选择武器界面" in xml
    assert "<b>规则说明：</b>弹出选择武器界面" not in xml
```

- [ ] **Step 2: Run tests and verify RED**

Run: `node --test tests/js/gameplay-review.test.js tests/js/gameplay-directory.test.js`

Run: `python -m pytest tests/test_gameplay_render.py tests/test_gameplay_review_model.py -q`

Expected: FAIL because `plannerSummary` is neither populated nor rendered.

- [ ] **Step 3: Populate `plannerSummary` without altering claims**

In `refresh_directory_copy`, set `chapter["plannerSummary"] = chapter_gameplay_summary(chapter, first_use=index == 0)`. In `ensure_gameplay_review_model`, call the refresh only when `presentationVersion < 2`; preserve titles, order, confirmations and claims.

- [ ] **Step 4: Update planner-facing renderers**

```javascript
function chapterSummary(chapter) {
  return text(chapter?.plannerSummary).trim() || "这部分玩法还需要补充明确的机制结论。";
}
```

Change the directory prefix from `本章将说明：` to `玩法范围：`. Rename the expanded claim group from `本章规则` to `素材依据`, and its editor label from `规则说明` to `素材中看到的内容`.

In `_chapter_xml`, render `plannerSummary` under `玩法规则` and render claims in a separate `素材证据` paragraph. Unknowns remain under the existing pending section and are not appended to the summary.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `node --test tests/js/gameplay-review.test.js tests/js/gameplay-directory.test.js`

Run: `python -m pytest tests/test_gameplay_render.py tests/test_gameplay_review_model.py -q`

Expected: PASS with no interaction evidence labelled as a gameplay rule.

- [ ] **Step 6: Commit**

```bash
git add js/gameplay-review.js js/gameplay-directory.js backend/gameplay_render.py backend/gameplay_review_model.py tests/js/gameplay-review.test.js tests/js/gameplay-directory.test.js tests/test_gameplay_render.py tests/test_gameplay_review_model.py
git commit -m "feat: render gameplay conclusions separately from evidence"
```

### Task 3: Shared planning-board model

**Files:**
- Create: `backend/planning_board_model.py`
- Modify: `backend/feishu_native_board.py`
- Modify: `backend/feishu_render.py`
- Test: `tests/test_planning_board_model.py`
- Test: `tests/test_feishu_sample_aligned_board.py`

**Interfaces:**
- Consumes: confirmed `reviewModel.stages`, `regions`, `transitions`, `crossStateConstraints`, and representative frames.
- Produces: `build_planning_board_model(job: dict) -> dict` with `stages`, `edges`, `notes`, and dormant `numberedAnnotations` for future UE flow use.

- [ ] **Step 1: Write a failing shared-model contract test**

```python
def test_board_model_preserves_hierarchy_direction_and_notes():
    board = build_planning_board_model(confirmed_job)
    assert [item["id"] for item in board["stages"]] == ["STG-001", "STG-002"]
    assert board["edges"][0]["lineStyle"] == "solid"
    assert board["edges"][1]["lineStyle"] == "dashed"
    assert all(item["fill"] == "#fff3bf" for item in board["notes"])
    assert board["style"]["showNumberedAnnotations"] is False
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest tests/test_planning_board_model.py -q`

Expected: FAIL because the shared builder does not exist.

- [ ] **Step 3: Implement the intermediate model**

```python
def build_planning_board_model(job: dict) -> dict:
    review = job.get("reviewModel") or {}
    stages = sorted(
        [item for item in review.get("stages") or [] if (item.get("confirmation") or {}).get("confirmed")],
        key=lambda item: (item.get("order", 0), item.get("id", "")),
    )
    stage_order = {stage["id"]: index for index, stage in enumerate(stages)}
    regions = sorted(
        [item for item in review.get("regions") or [] if (item.get("confirmation") or {}).get("confirmed") and item.get("stageId") in stage_order],
        key=lambda item: (stage_order[item["stageId"]], item.get("displayOrder", 0), item.get("id", "")),
    )
    numbered_annotations = [{
        "number": number, "stageId": item["stageId"], "frameId": item.get("frameId"),
        "x": float((item.get("bounds") or {}).get("x") or 0),
        "y": float((item.get("bounds") or {}).get("y") or 0),
        "text": str((item.get("rule") or {}).get("action") or (item.get("rule") or {}).get("display") or item.get("name") or "待确认"),
    } for number, item in enumerate(regions, 1)]
    transitions = [item for item in review.get("transitions") or [] if item.get("included") and (item.get("confirmation") or {}).get("confirmed")]
    edges = [{
        "id": item.get("id"), "sourceStageId": item.get("sourceStageId"), "targetStageId": item.get("targetStageId"),
        "label": item.get("triggerLabel") or item.get("triggerType") or "待确认",
        "direction": item.get("direction") or ("return" if item.get("resultType") in {"return", "close_overlay", "loop"} else "forward"),
        "lineStyle": "dashed" if item.get("resultType") in {"return", "close_overlay", "loop"} or item.get("direction") == "return" else "solid",
    } for item in transitions]
    return {
        "stages": [stage_record(stage, job) for stage in stages],
        "numberedAnnotations": numbered_annotations,
        "edges": edges,
        "notes": yellow_notes(review),
        "style": {"showNumberedAnnotations": False},
    }
```

`stage_record` returns the stage id, name and confirmed representative frame ids. `yellow_notes` flattens cross-state constraints and stage/component unknowns to records with `stageId`, `text`, and `fill: "#fff3bf"`; empty strings are discarded.

- [ ] **Step 4: Make the native compiler consume the shared model**

Replace direct iteration over `reviewModel.regions` and `reviewModel.transitions` in `_compile_confirmed_review_board` with `board = build_planning_board_model(job)`. Keep native node creation in `feishu_native_board.py`; do not move Feishu token or media behavior into the shared model.

- [ ] **Step 5: Verify model and native compiler tests**

Run: `python -m pytest tests/test_planning_board_model.py tests/test_feishu_sample_aligned_board.py tests/test_gve16_native_whiteboard.py -q`

Expected: PASS; all connectors remain native `straight`, forward lines are solid, return lines are dashed, and numbered annotations remain disabled by default.

- [ ] **Step 6: Commit**

```bash
git add backend/planning_board_model.py backend/feishu_native_board.py tests/test_planning_board_model.py tests/test_feishu_sample_aligned_board.py
git commit -m "feat: share one planning board model across outputs"
```

### Task 4: Align webpage board preview with the Feishu sample

**Files:**
- Modify: `backend/feishu_render.py`
- Modify: `backend/review_preview.py`
- Modify: `js/export-preview.js`
- Test: `tests/test_feishu_sample_aligned_board.py`
- Test: `tests/test_review_api.py`
- Test: `tests/js/export-preview.test.js`

**Interfaces:**
- Consumes: Task 3 `build_planning_board_model(job)`.
- Produces: SVG preview with global flow, stage sections, local branches, solid/dashed connectors, and yellow notes matching the latest Feishu planning-board sample.

- [ ] **Step 1: Write failing SVG parity tests**

```python
def test_preview_matches_native_stage_and_edge_structure(job, tmp_path):
    model = build_planning_board_model(job)
    svg, _ = render_ue_board_svg(job, tmp_path)
    for stage in model["stages"]:
        assert f'data-stage-id="{stage["id"]}"' in svg
    assert 'data-line-style="solid"' in svg
    assert 'data-line-style="dashed"' in svg
    assert '#fff3bf' in svg
    assert 'data-marker-number=' not in svg
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_feishu_sample_aligned_board.py tests/test_review_api.py -q`

Expected: FAIL because the current SVG flattens stages into card rows and does not share the native board hierarchy.

- [ ] **Step 3: Render the sample-aligned hierarchy**

Update `render_ue_board_svg` to:

1. Draw one top row for the complete main flow.
2. Draw each stage in order with representative screenshots.
3. Expand stage-local screenshots and rule text beneath their owning stage without numbered annotations.
4. Draw solid forward edges and dashed return edges from the shared model.
5. Place notes below their owning stage with `fill="#fff3bf"`.

All SVG nodes receive stable attributes: `data-stage-id`, `data-frame-id`, `data-edge-id`, and `data-line-style`. The dormant numbered-annotation data remains in the shared model but is not rendered unless a future UE-flow style explicitly enables it.

- [ ] **Step 4: Keep the webpage preview on the real generated SVG**

In `review_preview.py`, continue returning `boardPreviewSvg` from `render_ue_board_svg`. In `export-preview.js`, do not recreate cards client-side; render the SVG and expose a concise legend: “实线为前进，虚线为返回；黄色为异常或待确认”。

- [ ] **Step 5: Run focused parity tests and full suites**

Run: `python -m pytest tests/test_planning_board_model.py tests/test_feishu_sample_aligned_board.py tests/test_gve16_native_whiteboard.py tests/test_review_api.py -q`

Run: `node --test tests/js/export-preview.test.js tests/js/screenshot-backend.test.js`

Run: `python -m pytest -q`

Run: `node --test tests/js/*.test.js`

Expected: all tests pass; no preview/native stage, hierarchy or edge mismatch.

- [ ] **Step 6: Commit**

```bash
git add backend/feishu_render.py backend/review_preview.py js/export-preview.js tests/test_feishu_sample_aligned_board.py tests/test_review_api.py tests/js/export-preview.test.js
git commit -m "feat: align planning preview with GVE16 whiteboard"
```

### Task 5: Migrate and verify the current nine-chapter task

**Files:**
- Modify: `data/jobs/183261b4137e40a59596b3afcaad4f18/job.json` through the storage API only
- Test: `tests/test_history_access.py`

**Interfaces:**
- Consumes: Task 1 `refresh_directory_copy` and Task 3 `build_planning_board_model`.
- Produces: current saved task with `presentationVersion: 2`, rewritten summaries, unchanged claims/evidence, and a preview based on the shared board model.

- [ ] **Step 1: Add a migration regression test**

```python
def test_presentation_migration_preserves_review_content():
    before_claims = deepcopy(job["gameplayReviewModel"]["chapters"])
    migrate_gameplay_presentation(job)
    assert [item["claims"] for item in job["gameplayReviewModel"]["chapters"]] == [item["claims"] for item in before_claims]
    assert len(job["gameplayReviewModel"]["chapters"]) == 9
    assert len(job["gameplayReviewModel"]["evidenceAnchors"]) == 15
```

- [ ] **Step 2: Run the migration test and verify RED**

Run: `python -m pytest tests/test_history_access.py -q`

Expected: FAIL before migration wiring exists.

- [ ] **Step 3: Apply migration atomically through `storage.mutate_job`**

Load the current task, deep-copy chapters and evidence anchors, call `refresh_directory_copy`, verify counts and claim equality, then persist. Do not edit `job.json` with string replacement and do not invoke the visual model.

- [ ] **Step 4: Verify the real task and preview**

Query:

```powershell
$job = Invoke-RestMethod 'http://127.0.0.1:8000/api/jobs/183261b4137e40a59596b3afcaad4f18'
$job.gameplayReviewModel.chapters.Count
$job.gameplayReviewModel.evidenceAnchors.Count
$job.gameplayReviewModel.directory.presentationVersion
```

Expected: `9`, `15`, `2`. Generate the interaction preview and verify that stage order, local branches and edge styles match the native board model, numbered annotations are absent, and the page remains on the directory after refresh.

- [ ] **Step 5: Run all suites and restart the LAN service**

Run: `python -m pytest -q`

Run: `node --test tests/js/*.test.js`

Expected: all tests pass. Restart Uvicorn on `0.0.0.0:8000`, then verify the LAN job URL returns HTTP 200.

- [ ] **Step 6: Commit only source and tests**

The current task data is runtime state and must not be committed. Commit any remaining source/test changes only after `git status --short` confirms unrelated user files remain untouched.
