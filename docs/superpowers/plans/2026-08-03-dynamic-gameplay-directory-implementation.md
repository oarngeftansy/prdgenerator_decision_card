# Dynamic Gameplay Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirm AI's overall gameplay understanding and evidence-based directory before detailed review, present interaction and gameplay as concise planning statements with exception-first questions, and publish the confirmed directory in the same Feishu document as the approved interaction boards.

**Architecture:** Add a focused directory classifier and versioned directory state to the existing `gameplayReviewModel`; keep raw evidence facts separate from planner-facing chapters. Route the browser through a new directory-confirmation view before the existing chapter reviewer, then render Feishu only from the confirmed directory and approved chapters. Preserve existing interaction review and two-board publication contracts.

**Tech Stack:** Python 3.12, FastAPI, pytest, vanilla JavaScript, Node `node:test`, Playwright browser QA, existing Feishu XML/native-whiteboard publisher.

## Global Constraints

- Only gameplay modules evidenced by source material or explicitly added by a planner appear in the directory; no empty fixed combat chapters.
- Interaction and gameplay publish to one Feishu document.
- Interaction keeps exactly the approved `策划草图` and `竞品参考` native boards.
- Planner-facing copy does not expose `规则来源`, `关联章节`, `规则参数`, `跨页面规则`, `必须处理`, `补充规则与验收`, internal IDs, or English enum values.
- Knowledge sources suggest what to inspect but never prove that a mechanic exists.
- Final rendering treats both user-provided Feishu samples as binding: Maze revision 61 governs cross-genre gameplay structure and parameter detail; GVE16 document revision 41 and two-board revision 40 govern interaction boards and matching gameplay expression. Never claim a newer revision without reading it.
- AI understanding and directory confirmation occur before detailed interaction and gameplay review.
- Directory edits invalidate the final preview; only chapters affected by content ownership changes lose confirmation.
- Final gameplay document order is `玩法概述` → confirmed dynamic gameplay chapters → non-empty `配置与参数` → non-empty `待确认事项`.
- Existing history jobs remain readable through additive model defaults; do not destructively migrate legacy data.

---

## File Structure

- Create `backend/gameplay_directory.py`: fact classification, cross-batch merging, dynamic title proposals, directory validation, and impact calculation.
- Create `js/gameplay-directory.js`: planner-facing AI understanding and directory confirmation view with rename, reorder, add, delete, merge, split, and content assignment controls.
- Create `tests/test_gameplay_directory.py`: backend classification and mutation-impact contracts.
- Create `tests/js/gameplay-directory.test.js`: accessible directory view and operation payload contracts.
- Modify `backend/gameplay_analysis.py`: request evidence facts and run whole-video directory synthesis after batch analysis.
- Modify `backend/gameplay_review_model.py`: persist directory version/status/order/type assessment and validate ownership.
- Modify `backend/gameplay_review_service.py`: apply directory operations and targeted confirmation invalidation.
- Modify `backend/gameplay_render.py`: render overview, confirmed dynamic chapters, consolidated parameters, and pending items in confirmed order.
- Modify `backend/server.py`: add directory-confirmation endpoint and enforce directory gate.
- Modify `js/gameplay-review-client.js`: expose directory confirmation request.
- Modify `js/gameplay-workspace.js`, `js/review-workspace.js`, and `js/backend.js`: route and persist directory UI state.
- Modify `js/gameplay-review.js` and `js/gameplay-mechanism-forms.js`: replace generic system fields with concrete result/config/edge-case/question sections.
- Modify `index.html` and `css/gameplay-review.css`: mount and style the new directory stage.
- Modify gameplay Python/JavaScript tests and `tools/run_gameplay_review_browser_qa.js`: cover the complete route and Feishu consistency.

---

### Task 1: Evidence-Based Gameplay Type and Directory Synthesis

**Files:**
- Create: `backend/gameplay_directory.py`
- Modify: `backend/gameplay_analysis.py`
- Modify: `backend/server.py`
- Test: `tests/test_gameplay_directory.py`
- Test: `tests/test_gameplay_analysis.py`
- Test: `tests/test_review_workflow_integration.py`

**Interfaces:**
- Consumes: validated chapter drafts with `title`, `mechanismType`, `claims`, `sourceFrameIds`, `parameters`, `unknowns`.
- Produces: `synthesize_directory(drafts: list[dict]) -> dict` with `typeAssessment`, `entries`, and `unassignedClaimIds`; `directory_entry(...) -> dict` with stable `GDE-*` IDs.

- [ ] **Step 1: Write failing synthesis tests**

```python
def test_synthesis_uses_mechanics_not_combat_template():
    drafts = [draft("拖动不同形状拼入背包", "spatial_container", "拖动形状占据合法格子")]
    result = synthesize_directory(drafts)
    assert [item["title"] for item in result["entries"]] == ["背包拼接"]
    assert "武器系统" not in str(result)
    assert "敌人及首领" not in str(result)

def test_synthesis_separates_fast_combat_from_slow_upgrade_choice():
    drafts = [
        draft("自动攻击敌群", "combat", "角色持续自动攻击"),
        draft("升级三选一", "random_choice", "升级时暂停并选择一个效果"),
    ]
    result = synthesize_directory(drafts)
    assert [item["title"] for item in result["entries"]] == ["核心循环", "局内升级"]
    assert result["typeAssessment"]["primaryFamily"] == "自动战斗生存"
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/test_gameplay_directory.py tests/test_gameplay_analysis.py -q`

Expected: FAIL because `backend.gameplay_directory` and whole-video synthesis do not exist.

- [ ] **Step 3: Implement deterministic synthesis boundaries**

```python
@dataclass(frozen=True)
class DirectoryCandidate:
    title: str
    mechanism_types: tuple[str, ...]
    claim_ids: tuple[str, ...]
    source_frame_ids: tuple[str, ...]

def synthesize_directory(drafts: list[dict[str, Any]]) -> dict[str, Any]:
    facts = collect_facts(drafts)
    families = classify_families(facts)
    candidates = merge_related_facts(facts)
    return {
        "typeAssessment": families,
        "entries": [directory_entry(index + 1, item) for index, item in enumerate(candidates)],
        "unassignedClaimIds": unassigned_claim_ids(facts, candidates),
    }
```

Use explicit feature rules for observable actions, state transitions, time structure, entities, resources, growth, failure/re-entry, and cognitive-mode switches. Theme words never decide the family without matching player behavior.

- [ ] **Step 4: Change analysis to synthesize once after all batches and persist it before review**

Keep batch calls evidence-focused, merge all validated drafts, then call `synthesize_directory(candidates)` exactly once. Add the returned proposal to `build_gameplay_review_model(job, candidates, directory_proposal=proposal)`. In the completed-analysis processing path, create and persist this draft gameplay model immediately after the interaction review draft, before the browser enters detailed review. A generation failure persists an explicit retry/manual-directory state and never invents chapters.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_gameplay_directory.py tests/test_gameplay_analysis.py tests/test_review_workflow_integration.py -q`

Expected: PASS.

```powershell
git add backend/gameplay_directory.py backend/gameplay_analysis.py backend/server.py tests/test_gameplay_directory.py tests/test_gameplay_analysis.py tests/test_review_workflow_integration.py
git commit -m "feat: synthesize evidence-based gameplay directories"
```

---

### Task 2: Versioned Directory Model and Compatibility Defaults

**Files:**
- Modify: `backend/gameplay_review_model.py`
- Modify: `backend/gameplay_directory.py`
- Test: `tests/test_gameplay_review_model.py`
- Test: `tests/test_history_access.py`

**Interfaces:**
- Consumes: `directory_proposal` from Task 1 and existing chapter drafts.
- Produces: model fields `directory: {revision, status, entries, typeAssessment, unassignedClaimIds, confirmedAtRevision}` and `directory_gate(model) -> list[str]`.

- [ ] **Step 1: Write failing model and legacy tests**

```python
def test_new_model_requires_confirmed_directory_before_chapter_review():
    model = build_gameplay_review_model(job(), drafts(), directory_proposal=proposal())
    assert model["directory"]["status"] == "draft"
    assert directory_gate(model) == ["GAMEPLAY_DIRECTORY_NOT_CONFIRMED"]

def test_legacy_model_gets_confirmed_directory_in_existing_chapter_order():
    model = ensure_gameplay_review_model(legacy_job())
    assert model["directory"]["status"] == "confirmed"
    assert [item["chapterId"] for item in model["directory"]["entries"]] == ["GCH-001"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_gameplay_review_model.py tests/test_history_access.py -q`

Expected: FAIL because the directory state is absent.

- [ ] **Step 3: Add additive directory schema and validation**

Each entry stores `id`, `chapterId`, `title`, `claimIds`, `summary`, and `order`. Validate unique entry/chapter/claim ownership, consecutive order, valid references, non-empty planner titles, and no unassigned claims at confirmation.

- [ ] **Step 4: Add legacy defaults without rewriting stored jobs**

At read time, derive a confirmed directory from existing chapter order when `directory` is missing. Do not increment the gameplay revision merely for reading a legacy job.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_gameplay_review_model.py tests/test_history_access.py -q`

Expected: PASS.

```powershell
git add backend/gameplay_review_model.py backend/gameplay_directory.py tests/test_gameplay_review_model.py tests/test_history_access.py
git commit -m "feat: persist versioned gameplay directories"
```

---

### Task 3: Directory Editing, Confirmation, and Targeted Invalidation

**Files:**
- Modify: `backend/gameplay_directory.py`
- Modify: `backend/gameplay_review_service.py`
- Modify: `backend/server.py`
- Test: `tests/test_gameplay_directory.py`
- Test: `tests/test_gameplay_review_service.py`
- Test: `tests/test_review_api.py`

**Interfaces:**
- Produces: `apply_directory_operations(model, operations, expected_revision) -> dict`; `confirm_gameplay_directory(model, expected_revision) -> dict`; endpoint `POST /api/jobs/{job_id}/gameplay-review-model/confirm-directory`.

- [ ] **Step 1: Write failing operation-impact tests**

```python
def test_rename_and_reorder_preserve_confirmation():
    result = apply_directory_operations(confirmed_model(), [rename("GDE-001"), reorder(["GDE-002", "GDE-001"])], 4)
    assert all(chapter["confirmation"]["confirmed"] for chapter in result["chapters"])

def test_move_claim_reopens_only_source_and_target_chapters():
    result = apply_directory_operations(three_chapter_model(), [move_claim("GCL-002", "GDE-001", "GDE-002")], 7)
    assert confirmation_map(result) == {"GCH-001": False, "GCH-002": False, "GCH-003": True}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_gameplay_directory.py tests/test_gameplay_review_service.py tests/test_review_api.py -q`

Expected: FAIL because directory operations and confirmation endpoint are absent.

- [ ] **Step 3: Implement explicit operations**

Support `rename_directory_entry`, `reorder_directory_entries`, `add_directory_entry`, `delete_directory_entry`, `merge_directory_entries`, `split_directory_entry`, and `move_claim_between_entries`. Return a set of affected chapter IDs from content ownership changes; reuse the existing chapter reopen helper only for those IDs.

- [ ] **Step 4: Implement confirmation and preview invalidation**

Confirmation rejects empty titles, duplicate ownership, or unassigned claims. Every directory edit clears `reviewState.previewRevision`; rename/order edits retain chapter confirmations, while ownership edits reopen affected chapters.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_gameplay_directory.py tests/test_gameplay_review_service.py tests/test_review_api.py -q`

Expected: PASS.

```powershell
git add backend/gameplay_directory.py backend/gameplay_review_service.py backend/server.py tests/test_gameplay_directory.py tests/test_gameplay_review_service.py tests/test_review_api.py
git commit -m "feat: edit and confirm gameplay directories"
```

---

### Task 4: AI Understanding and Directory Confirmation Workspace

**Files:**
- Create: `js/gameplay-directory.js`
- Create: `tests/js/gameplay-directory.test.js`
- Modify: `js/gameplay-review-client.js`
- Modify: `js/gameplay-workspace.js`
- Modify: `js/review-workspace.js`
- Modify: `js/backend.js`
- Modify: `index.html`
- Modify: `css/gameplay-review.css`
- Test: `tests/js/gameplay-workspace.test.js`
- Test: `tests/js/review-workspace.test.js`

**Interfaces:**
- Consumes: `model.directory` and operation queue.
- Produces: `GameplayDirectory.render(workspace)` and route name `gameplay_directory`; client methods `updateUnderstanding(expectedRevision, understanding)` and `confirmDirectory(expectedRevision)`.

- [ ] **Step 1: Write failing route and renderer tests**

```javascript
test("draft directory routes before gameplay chapters", () => {
  assert.equal(routeForModel(model({ directory: { status: "draft" } })), "gameplay_directory");
});

test("draft directory routes before unconfirmed interaction", () => {
  const model = combinedModel({ interactionConfirmed: false, directoryStatus: "draft" });
  assert.equal(routeForModel(model), "gameplay_directory");
});

test("directory cards expose planner actions and concrete summaries", () => {
  const root = renderDirectory(directoryModel());
  assert.match(root.textContent, /AI对这个玩法的理解/);
  assert.match(root.textContent, /确认玩法目录/);
  assert.match(root.textContent, /本章将说明/);
  assert.doesNotMatch(root.textContent, /claimId|mechanismType|规则来源|关联章节/);
});
```

- [ ] **Step 2: Run tests and verify failure**

Run: `node --test tests/js/gameplay-directory.test.js tests/js/gameplay-workspace.test.js tests/js/review-workspace.test.js`

Expected: FAIL because the route and renderer do not exist.

- [ ] **Step 3: Build accessible directory controls**

Render a compact understanding card first: one to four planning sentences, primary gameplay, up to three supporting mechanics, and explicit uncertainties. Render ordered directory cards below it with editable chapter title, concrete content summary, unresolved-question count, move up/down, merge, split, delete, and add controls. Use confirmation dialog text that includes the number of confirmed items before destructive deletion. All buttons have `type="button"`, visible focus, and disabled saving states.

- [ ] **Step 4: Wire operations and confirmation**

Send understanding and directory edits through the existing revisioned operation queue. `确认理解和目录，开始审核` flushes pending edits, calls `confirmDirectory`, rebuilds canonical state, and routes to detailed interaction review first. The post-interaction action reuses the already confirmed gameplay model and directory instead of calling gameplay generation again or creating new chapter titles.

- [ ] **Step 5: Run tests and commit**

Run: `node --test tests/js/gameplay-directory.test.js tests/js/gameplay-workspace.test.js tests/js/review-workspace.test.js`

Expected: PASS.

```powershell
git add js/gameplay-directory.js js/gameplay-review-client.js js/gameplay-workspace.js js/review-workspace.js js/backend.js index.html css/gameplay-review.css tests/js/gameplay-directory.test.js tests/js/gameplay-workspace.test.js tests/js/review-workspace.test.js
git commit -m "feat: add gameplay directory confirmation workspace"
```

---

### Task 5: Concise Planner-Facing Interaction and Chapter Review

**Files:**
- Modify: `js/gameplay-review.js`
- Modify: `js/gameplay-mechanism-forms.js`
- Modify: `js/stage-review.js`
- Modify: `js/flow-review.js`
- Modify: `css/gameplay-review.css`
- Test: `tests/js/gameplay-review.test.js`

**Interfaces:**
- Produces a concise `玩法说明`, concrete questions, and on-demand detail sections; interaction cards use the same summary-first rule.

- [ ] **Step 1: Write failing copy and information-hierarchy tests**

```javascript
test("chapter review leads with one planning statement and hides internal fields", () => {
  const root = renderChapter(combatChapter());
  assert.match(root.textContent, /玩法说明/);
  assert.match(root.textContent, /需要你确认的问题/);
  assert.match(root.textContent, /展开详细规则/);
  assert.doesNotMatch(root.textContent, /规则来源|关联章节|规则参数|跨页面规则|必须处理|补充规则与验收|sourceType|dependency/);
});
```

- [ ] **Step 2: Run test and verify failure**

Run: `node --test tests/js/gameplay-review.test.js`

Expected: FAIL against the current generic groups.

- [ ] **Step 3: Render concrete rule sentences and mechanism-specific fields**

Compile claims into one to three complete planning sentences. Keep player goal, trigger, input, feedback, state change, result, and exceptions as hidden detail fields until `展开详细规则` is activated. Render only fields defined by the selected mechanism schema; labels must ask concrete questions such as `升级时提供几个选项？` and `返回战斗前是否必须选择？`.

- [ ] **Step 4: Convert uncertainty and conflicts into answerable questions**

Apply the same summary-first rule to interaction stages and transitions: default to a sentence such as `点击升级选项后，效果立即生效并返回战斗`; expose the existing four-step and eight-field editors only when incomplete or explicitly expanded. Hide source metadata by default behind `查看判断依据`. Render each unknown/conflict as a full question with its affected rule named. Auto-generate acceptance checks and keep them collapsed under `检查方法`.

- [ ] **Step 5: Run tests and commit**

Run: `node --test tests/js/gameplay-review.test.js`

Expected: PASS.

```powershell
git add js/gameplay-review.js js/gameplay-mechanism-forms.js js/stage-review.js js/flow-review.js css/gameplay-review.css tests/js/gameplay-review.test.js
git commit -m "feat: present gameplay review in planner language"
```

---

### Task 6: Confirmed Directory Gates and Final Feishu Rendering

**Files:**
- Modify: `backend/gameplay_review_model.py`
- Modify: `backend/gameplay_render.py`
- Modify: `backend/server.py`
- Modify: `js/backend.js`
- Test: `tests/test_gameplay_render.py`
- Test: `tests/test_review_api.py`

**Interfaces:**
- Consumes: confirmed directory order, approved chapters, existing interaction render result.
- Produces: `GameplayRenderResult` ordered as overview, dynamic chapters, optional parameter section, optional pending section.

- [ ] **Step 1: Write failing rendering contracts**

```python
def test_render_uses_confirmed_directory_order_and_document_sections():
    result = render_gameplay_document_sections(job_with_directory(["局内升级", "核心循环"]))
    assert result.xml.index("玩法概述") < result.xml.index("局内升级") < result.xml.index("核心循环")
    assert result.xml.index("核心循环") < result.xml.index("配置与参数") < result.xml.index("待确认事项")

def test_render_omits_empty_fixed_sections_and_rejects_draft_directory():
    assert "武器系统" not in render_gameplay_document_sections(puzzle_job()).xml
    with pytest.raises(GameplayRenderError) as error:
        render_gameplay_document_sections(draft_directory_job())
    assert "GAMEPLAY_DIRECTORY_NOT_CONFIRMED" in error.value.blocker_ids
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_gameplay_render.py tests/test_review_api.py -q`

Expected: FAIL because rendering currently loops chapter scope directly.

- [ ] **Step 3: Render from confirmed directory only**

Create `overview_xml(chapters)`, `chapter_xml(entry, chapter)`, `parameter_catalog_xml(chapters)`, and `pending_xml(job, chapters)`. The renderer never renames or reorders entries. Omit the parameter or pending section when empty.

- [ ] **Step 4: Bind preview to all three revisions**

Final preview returns `interactionRevision`, `directoryRevision`, and `gameplayRevision`. Publication rejects any mismatch and directs the user back to the changed stage.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_gameplay_render.py tests/test_review_api.py -q`

Expected: PASS.

```powershell
git add backend/gameplay_review_model.py backend/gameplay_render.py backend/server.py js/backend.js tests/test_gameplay_render.py tests/test_review_api.py
git commit -m "feat: render confirmed gameplay directory to Feishu"
```

---

### Task 7: Browser Workflow and Regression QA

**Files:**
- Modify: `tools/run_gameplay_review_browser_qa.js`
- Modify: `tests/test_review_workspace_browser_qa_contract.py`
- Modify: `tests/js/review-browser-globals.test.js`
- Modify: `index.html`

**Interfaces:**
- Verifies: AI understanding and directory confirmation → interaction review/preview → chapter review → diagrams → final preview → mocked Feishu publication.

- [ ] **Step 1: Extend the browser QA contract test**

Require markers for directory rename, reorder, merge/split invalidation, directory confirmation, preserved unrelated chapter confirmation, and matching three revisions.

- [ ] **Step 2: Run the contract test and verify failure**

Run: `python -m pytest tests/test_review_workspace_browser_qa_contract.py -q`

Expected: FAIL because the QA script lacks directory actions.

- [ ] **Step 3: Extend the Playwright scenario**

Mock a non-combat understanding and directory and assert no combat-only chapter appears. Correct the primary gameplay, rename and reorder entries, confirm before entering interaction review, complete one chapter, return to split another, assert only affected chapters reopen, then finish and verify the final preview order. Scan visible copy for the forbidden terms in Global Constraints and English enum values.

- [ ] **Step 4: Run all JavaScript tests and browser QA**

Run: `node --test tests/js/*.test.js`

Expected: all tests PASS.

Run: `node tools/run_gameplay_review_browser_qa.js --base http://127.0.0.1:8000 --playwright C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright`

Expected: PASS with desktop and mobile screenshots and no console errors.

- [ ] **Step 5: Commit**

```powershell
git add tools/run_gameplay_review_browser_qa.js tests/test_review_workspace_browser_qa_contract.py tests/js/review-browser-globals.test.js index.html
git commit -m "test: verify dynamic gameplay directory workflow"
```

---

### Task 8: Feishu Sample Alignment and Full Verification

**Files:**
- Modify: `tests/test_gameplay_render.py`
- Modify: `tests/test_review_workflow_integration.py`
- Modify: `docs/research/2026-07-28-gameplay-reference-documents.md` only if a newer Feishu revision is actually read.

**Interfaces:**
- Verifies: saved Maze revision 61, GVE16 document revision 41, and GVE16 two-board revision 40 contracts against one combined document.

- [ ] **Step 1: Add sample-derived structural fixtures**

Create one Maze-like non-combat job and one GVE16-like combat job. Assert mechanism-specific directory names, rule-first chapter content, consolidated parameter tables, optional diagrams, and exactly two interaction boards.

- [ ] **Step 2: Run integration tests and verify initial failure or coverage gap**

Run: `python -m pytest tests/test_gameplay_render.py tests/test_review_workflow_integration.py -q`

Expected: FAIL until the combined-order and sample-alignment assertions are satisfied.

- [ ] **Step 3: Fix only contract mismatches found by the fixtures**

Do not add generic GDD sections. Preserve natural-language rules, real row/column data as tables, optional diagrams only for spatial/stage/probability/multi-entity relationships, and interaction board order `策划草图` then `竞品参考`.

- [ ] **Step 4: Run the full verification suite**

Run: `python -m pytest -q`

Expected: all Python tests PASS.

Run: `node --test tests/js/*.test.js`

Expected: all JavaScript tests PASS.

Run both existing browser QA scripts against the local service.

Expected: both PASS, no console errors, no forbidden copy, and final preview directory equals confirmed directory.

- [ ] **Step 5: Commit final alignment tests**

```powershell
git add tests/test_gameplay_render.py tests/test_review_workflow_integration.py
git commit -m "test: enforce Feishu gameplay sample alignment"
```

---

## Self-Review Result

- Spec coverage: dynamic recognition, mixed genres, early AI-understanding/directory confirmation, summary-first planner copy, targeted invalidation, final document structure, two-board interaction preservation, legacy compatibility, error handling, and three-layer revision gates each map to a task.
- Placeholder scan: no deferred implementation placeholders remain; the current bundled Playwright path is written explicitly in Task 7.
- Type consistency: `directory`, `typeAssessment`, `entries`, `directoryRevision`, `confirmDirectory`, and `gameplay_directory` use the same names across backend, browser, preview, and tests.
