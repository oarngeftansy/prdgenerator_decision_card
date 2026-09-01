# GVE16 Two-Board Interaction Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Narrow new interaction tasks to a confirmed planning-sketch board plus an optional competitor-reference board while preserving legacy task data without exposing or exporting legacy UX/rule-domain features.

**Architecture:** Keep `reviewModel.schemaVersion` at `2.0`, but introduce an explicit active interaction contract that ignores legacy `ruleDomains` and `referenceBoards.ux` for navigation, mutation, validation, preview, and export. Reuse the existing confirmed flow/stage/component model for the planning board and the hardened competitor asset pool for the reference board. Render and publish exactly two ordered native whiteboards with per-board resumable checkpoints.

**Tech Stack:** Python 3.11, FastAPI, vanilla browser JavaScript, Node test runner, pytest, Feishu Docx/Whiteboard CLI contracts.

## Global Constraints

- New interaction flow is exactly: material import → flow review → stage/component review → two-board preview → Feishu export.
- Active board order is exactly `planning`, `competitor`, with titles `策划草图`, `竞品参考`.
- `planning` is generated only from confirmed representative frames, components, states, transitions, constraints, and unresolved notes.
- `competitor` uses only `referenceBoards.competitor.assets`; an empty pool is valid and renders a yellow `待补充` note with zero images.
- `ruleDomains`, `referenceBoards.ux`, and old `ux` publication checkpoints are legacy data: preserve them byte-for-byte where practical, but never display, mutate, validate as an active gate, or export them for new interaction tasks.
- Do not emit narrative, guidance, or red-dot chapters in an interaction delivery.
- Keep `reviewModel.schemaVersion == "2.0"`; use additive/tolerant reads, not a destructive migration.
- Never add all frames/evidence frames to Feishu. The planning board uses confirmed representative frames only.
- Do not add dependencies. Preserve the existing built-in runtime and hardened asset filesystem boundary.
- Do not stage or commit `artifacts/`.

---

### Task 1: Active two-board model contract and export gate

**Files:**
- Modify: `backend/review_model.py:27-75,180-205,318-345,542-675,857-915`
- Modify: `tests/test_review_model.py`
- Modify: `tests/test_review_model_seed.py`
- Modify: `tests/review_fixtures.py`

**Interfaces:**
- Consumes: existing schema `2.0`, flow/stage/component validators, legacy job dictionaries.
- Produces: `ACTIVE_REFERENCE_BOARD_KEYS = ("planning", "competitor")`, `active_reference_boards() -> dict[str, Any]`, `validate_review_model(model, *, include_legacy: bool = True) -> list[str]`, and an export gate without `RULE_DOMAINS_NOT_CONFIRMED` or UX/competitor-empty blockers.

- [ ] **Step 1: Write failing fresh-model and legacy-preservation tests**

```python
def test_new_interaction_model_contains_only_active_reference_boards(analysis_job):
    model = build_review_model(analysis_job)
    assert model["schemaVersion"] == "2.0"
    assert "ruleDomains" not in model
    assert model["referenceBoards"] == {
        "planning": {"source": "confirmed_review_model", "status": "generated"},
        "competitor": {"assets": [], "status": "pending"},
    }


def test_ensure_preserves_legacy_fields_without_backfilling_them(analysis_job):
    legacy = build_review_model(analysis_job)
    legacy["ruleDomains"] = {"legacy": {"keep": True}}
    legacy["referenceBoards"]["ux"] = {"assets": [{"id": "UXA-001"}], "status": "ready"}
    ensured = ensure_review_model({"reviewModel": legacy}, analysis_job)
    assert ensured["ruleDomains"] == {"legacy": {"keep": True}}
    assert ensured["referenceBoards"]["ux"] == {"assets": [{"id": "UXA-001"}], "status": "ready"}
```

- [ ] **Step 2: Write failing gate tests**

```python
def test_active_gate_ignores_legacy_rule_and_ux_damage(confirmed_model):
    confirmed_model["ruleDomains"] = ["damaged legacy value"]
    confirmed_model["referenceBoards"]["ux"] = {"assets": [None], "status": "ready"}
    gate = review_gate(confirmed_model)
    assert "RULE_DOMAINS_NOT_CONFIRMED" not in gate["blockers"]
    assert "UX_BOARD_PENDING" not in gate["warnings"]
    assert gate["exportReady"] is True


def test_empty_competitor_is_a_non_blocking_pending_summary(confirmed_model):
    confirmed_model["referenceBoards"]["competitor"] = {"assets": [], "status": "pending"}
    gate = review_gate(confirmed_model)
    assert gate["exportReady"] is True
    assert gate["warnings"] == ["COMPETITOR_BOARD_PENDING"]
```

- [ ] **Step 3: Run RED tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_model.py tests/test_review_model_seed.py -q
```

Expected: failures show fresh models still contain rule domains/UX and the gate still adds `RULE_DOMAINS_NOT_CONFIRMED`.

- [ ] **Step 4: Implement the active contract without deleting legacy values**

```python
ACTIVE_REFERENCE_BOARD_KEYS = ("planning", "competitor")


def active_reference_boards() -> dict[str, Any]:
    return {
        "planning": {"source": "confirmed_review_model", "status": "generated"},
        "competitor": {"assets": [], "status": "pending"},
    }
```

Use `active_reference_boards()` when building a new review model. In `ensure_review_model`, add missing `planning` and `competitor` values but never add, replace, or remove `ruleDomains`/`ux`. Add an `include_legacy` keyword to `validate_review_model`: core flow/stage/component and competitor validation always runs; rule-domain and UX validation runs only when `include_legacy=True` and the corresponding legacy field exists. Call `validate_review_model(model, include_legacy=False)` from `review_gate`; retain full validation for legacy rule APIs. Remove the rule confirmation blocker and UX warning from `review_gate`; retain the non-blocking competitor warning.

- [ ] **Step 5: Run Task 1 tests and the review-service regression suite**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_model.py tests/test_review_model_seed.py tests/test_review_service.py tests/test_review_preview.py -q
```

Expected: PASS; legacy values survive and active flow/stage/component validation remains strict.

- [ ] **Step 6: Commit**

```powershell
git add backend/review_model.py tests/test_review_model.py tests/test_review_model_seed.py tests/review_fixtures.py
git commit -m "refactor: activate two-board interaction contract"
```

---

### Task 2: Remove legacy rules from the active confirmation path

**Files:**
- Modify: `backend/review_service.py:100-125,540-590,630-760,810-870`
- Modify: `backend/server.py:590-710,800-840`
- Modify: `tests/test_review_service.py`
- Modify: `tests/test_review_api.py`
- Modify: `tests/test_review_persistence.py`

**Interfaces:**
- Consumes: Task 1 active gate and existing revisioned flow/stage confirmation APIs.
- Produces: final stage confirmation with `reviewState.status == "preview_ready"`; active edits that do not alter legacy rule confirmation; active mutations validated with `include_legacy=False`; legacy `POST /confirm-rules` retained only for old clients and fully validated with `include_legacy=True`.

- [ ] **Step 1: Write failing final-stage and preservation tests**

```python
def test_confirming_last_stage_advances_directly_to_preview(model):
    model["ruleDomains"] = {"confirmation": {"confirmed": True, "revision": 7}, "legacy": "keep"}
    before = deepcopy(model["ruleDomains"])
    result = confirm_stage(model, model["stages"][-1]["id"], model["revision"])
    assert result["reviewState"]["status"] == "preview_ready"
    assert result["ruleDomains"] == before


def test_active_flow_edit_does_not_mutate_legacy_rule_data(confirmed_model):
    confirmed_model["ruleDomains"] = {"confirmation": {"confirmed": True, "revision": 4}, "custom": [1, 2]}
    result = apply_operations(confirmed_model, [{"type": "set", "entity": "stage", "id": "STG-001", "field": "unknowns", "value": ["待确认"]}])
    assert result["ruleDomains"] == confirmed_model["ruleDomains"]
```

- [ ] **Step 2: Run RED tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_service.py tests/test_review_api.py tests/test_review_persistence.py -q
```

Expected: at least one preservation assertion fails because active mutations currently invalidate rule confirmation.

- [ ] **Step 3: Stop active mutations from touching rule domains**

Remove rule-confirmation invalidation from the shared flow/stage/component mutation path. Keep invalidation local to legacy rule operations only:

```python
if operation.get("type") in RULE_OPERATION_TYPES and isinstance(result.get("ruleDomains"), dict):
    result["ruleDomains"].setdefault("confirmation", {}).update(confirmed=False, revision=None)
```

Keep `confirm_rule_domains` and its server endpoint for old clients, but do not call it from active code and do not let its status affect active preview/export.
Route active flow/stage/component/reference-asset completion through `validate_review_model(..., include_legacy=False)`. Route legacy rule operations and `confirm_rule_domains` through `validate_review_model(..., include_legacy=True)`.

- [ ] **Step 4: Add API regression proving final-stage response is preview-ready**

```python
def test_last_stage_confirmation_returns_preview_ready_canonical_model(client, completed_job):
    model = completed_job["reviewModel"]
    response = client.post(
        f"/api/jobs/{completed_job['id']}/review/confirm-stage/{model['stages'][-1]['id']}",
        json={"expectedRevision": model["revision"]},
    )
    assert response.status_code == 200
    assert response.json()["reviewState"]["status"] == "preview_ready"
```

- [ ] **Step 5: Run service/API/persistence tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_service.py tests/test_review_api.py tests/test_review_persistence.py -q
```

Expected: PASS with stale-revision 409 behavior unchanged.

- [ ] **Step 6: Commit**

```powershell
git add backend/review_service.py backend/server.py tests/test_review_service.py tests/test_review_api.py tests/test_review_persistence.py
git commit -m "refactor: bypass legacy rule confirmation"
```

---

### Task 3: Two-board browser workflow and competitor-only asset controls

**Files:**
- Modify: `index.html:165-215,260-272`
- Modify: `js/review-workspace.js:1-95`
- Modify: `js/backend.js:480-780`
- Modify: `js/reference-board-assets.js`
- Modify: `js/review-client.js`
- Modify: `js/export-preview.js`
- Modify: `css/style.css`
- Modify: `css/review-workspace.css`
- Test: `tests/js/review-workspace.test.js`
- Test: `tests/js/screenshot-backend.test.js`
- Test: `tests/js/reference-board-assets.test.js`
- Test: `tests/js/export-preview.test.js`
- Test: `tests/test_review_workspace_ui_contract.py`

**Interfaces:**
- Consumes: final-stage `preview_ready`, Task 1 `planning`/`competitor` board data, Task 3 hardened competitor endpoints.
- Produces: active views `flow`, `stage`, `preview`; `ReferenceBoardAssets.summaries()` returning exactly planning and competitor; preview screen containing read-only planning status plus competitor controls.

- [ ] **Step 1: Write failing navigation tests**

```javascript
test("confirmed stages route directly to preview", () => {
  const model = fixture({ flowConfirmed: true, allStagesConfirmed: true, previewRevision: null });
  assert.equal(ReviewWorkspace.routeForModel(model), "preview");
});

test("legacy saved rules view migrates to preview", () => {
  const model = fixture({ flowConfirmed: true, allStagesConfirmed: true });
  const rebuilt = ReviewWorkspace.rebuild(model, "saved", { view: "rules", model });
  assert.equal(rebuilt.view, "preview");
});
```

- [ ] **Step 2: Write failing two-board summary and UI-contract tests**

```javascript
test("board summaries expose planning and competitor only", () => {
  const result = ReferenceBoardAssets.summaries({
    ux: { assets: [{ id: "legacy" }], status: "ready" },
    planning: { status: "generated" },
    competitor: { assets: [], status: "pending" },
  }, 4);
  assert.deepEqual(result.map(({ key, editable, label }) => [key, editable, label]), [
    ["planning", false, "自动生成"],
    ["competitor", true, "待补充"],
  ]);
});
```

```python
def test_review_workspace_exposes_only_flow_stage_preview(index_html):
    assert 'data-review-view="rules"' not in index_html
    assert 'id="rulesReviewView"' not in index_html
    assert "rule-domain-review.js" not in index_html
    assert index_html.count("data-review-view=") == 3
```

- [ ] **Step 3: Run RED frontend tests**

```powershell
node --test tests/js/review-workspace.test.js tests/js/screenshot-backend.test.js tests/js/reference-board-assets.test.js tests/js/export-preview.test.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_workspace_ui_contract.py -q
```

Expected: failures show the rules route/nav and UX card still exist.

- [ ] **Step 4: Implement the active route and remove rules markup/script**

Use only these active views:

```javascript
const ACTIVE_VIEWS = ["flow", "stage", "preview"];

function routeForModel(model) {
  const stages = model.stages || [];
  const allConfirmed = Boolean(model.reviewState?.flowConfirmed)
    && stages.every((stage) => stage.confirmation?.confirmed);
  if (model.quality?.qualified === false) return "analysis_failed";
  if (allConfirmed) return "preview";
  return model.reviewState?.flowConfirmed ? "stage" : "flow";
}
```

When restoring UI state, map `rules` to `preview`. Remove the rules nav button, rules section, confirmation button binding, and `rule-domain-review.js` script tag. Keep the legacy JavaScript file in the repository for historical reference; it must not be loaded.

- [ ] **Step 5: Render planning plus competitor controls in preview**

Change board summaries to:

```javascript
function summaries(boards, planningCount = 0) {
  const competitor = boards?.competitor || { assets: [], status: "pending" };
  return [
    { key: "planning", title: "策划草图", editable: false, label: "自动生成", count: planningCount, status: "generated" },
    { key: "competitor", title: "竞品参考", editable: true, label: competitor.assets?.length ? "已添加" : "待补充", count: competitor.assets?.length || 0, status: competitor.status || "pending" },
  ];
}
```

Mount the existing competitor uploader/list/retry controller above the preview result. Reject `ux` in browser controller calls. Planning remains read-only. Empty competitor must not set an uploading/failed gate.

- [ ] **Step 6: Verify loading, failure, 409, rapid-click, and 44px controls**

Extend existing tests to assert:

```javascript
assert.equal(context.state.reviewWorkspace.referenceBoardStates.ux, undefined);
assert.equal(context.canConfirmPreviewWithEmptyCompetitor(), true);
assert.equal(context.secondRapidCompetitorRequestCount, 0);
```

Retain the atomic missing replacement path, persistent failed/retry state, canonical 409 reload, and 44px minimum touch target.

- [ ] **Step 7: Run all JavaScript and UI-contract tests**

```powershell
node --test tests/js/*.test.js
node --check js/review-workspace.js
node --check js/backend.js
node --check js/reference-board-assets.js
node --check js/export-preview.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_workspace_ui_contract.py -q
```

Expected: PASS; no rules tab, UX upload input, duplicate listener, or vertical text regression.

- [ ] **Step 8: Commit**

```powershell
git add index.html js/review-workspace.js js/backend.js js/reference-board-assets.js js/review-client.js js/export-preview.js css/style.css css/review-workspace.css tests/js/review-workspace.test.js tests/js/screenshot-backend.test.js tests/js/reference-board-assets.test.js tests/js/export-preview.test.js tests/test_review_workspace_ui_contract.py
git commit -m "refactor: show two-board interaction preview"
```

---

### Task 4: Two-board preview response and interaction document renderer

**Files:**
- Modify: `backend/review_preview.py`
- Modify: `backend/feishu_native_board.py:195-210`
- Modify: `backend/feishu_render.py:300-465`
- Modify: `tests/test_review_preview.py`
- Modify: `tests/test_feishu_render.py`
- Modify: `tests/test_gve16_native_whiteboard.py`
- Modify: `tests/test_feishu_sample_aligned_board.py`

**Interfaces:**
- Consumes: confirmed review model, planning native board compiler, competitor asset compiler.
- Produces: preview `referenceBoardSummary` with exactly two items; `compile_gve16_whiteboards(...) -> tuple[NamedWhiteboard, NamedWhiteboard]`; interaction XML with exactly two whiteboard blocks and no legacy rule chapters.

- [ ] **Step 1: Write failing preview and renderer tests**

```python
def test_preview_reports_planning_and_competitor_only(confirmed_job):
    preview = build_review_preview(confirmed_job)
    assert [item["key"] for item in preview["referenceBoardSummary"]] == ["planning", "competitor"]
    assert "ruleDomainSummary" not in preview
    assert preview["exportReady"] is True


def test_interaction_document_contains_exactly_two_ue_boards(confirmed_job, tmp_path):
    confirmed_job["reviewModel"]["ruleDomains"] = {"narrative": [{"title": "legacy"}]}
    rendered = render_feishu_document(confirmed_job, tmp_path)
    assert [board.key for board in rendered.native_boards] == ["planning", "competitor"]
    assert [board.title for board in rendered.native_boards] == ["策划草图", "竞品参考"]
    assert rendered.xml.count('<whiteboard type="raw"></whiteboard>') == 2
    assert "UX设计" not in rendered.xml
    assert "9. 叙事" not in rendered.xml
    assert "11. 引导" not in rendered.xml
    assert "12. 红点提示" not in rendered.xml
```

- [ ] **Step 2: Run RED renderer tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_preview.py tests/test_feishu_render.py tests/test_gve16_native_whiteboard.py tests/test_feishu_sample_aligned_board.py -q
```

Expected: failures show six summaries, three native boards, and legacy rule chapters.

- [ ] **Step 3: Compile exactly two boards**

```python
def compile_gve16_whiteboards(
    job: dict[str, Any], job_dir: Path | None = None,
) -> tuple[NamedWhiteboard, NamedWhiteboard]:
    return (
        NamedWhiteboard("planning", "策划草图", compile_gve16_whiteboard(job)),
        NamedWhiteboard("competitor", "竞品参考", compile_reference_whiteboard(job, "competitor", "竞品参考", job_dir)),
    )
```

Keep `RenderedFeishuDocument.native_board` returning the board whose key is `planning`.

- [ ] **Step 4: Remove interaction rule chapters from XML**

For interaction mode, append only:

```python
parts.append("<h1>UE流转图</h1>")
for named in native_boards:
    parts.extend([f"<h2>{escape(named.title)}</h2>", '<whiteboard type="raw"></whiteboard>'])
```

Delete `_PENDING_RULE_DOMAIN`, `_render_narrative`, `_render_guidance`, `_render_red_dots`, and their interaction-only tests; no active module imports these helpers. Future gameplay planning must introduce its own evidence-specific renderer rather than reviving interaction legacy fields.

- [ ] **Step 5: Keep planning and competitor source isolation tests**

Assert planning images are exactly confirmed representative frame IDs, competitor images are exactly ready competitor asset IDs, and empty competitor contains a yellow `待补充` note with no images. Include damaged legacy UX/rules values and prove rendering does not inspect them.

- [ ] **Step 6: Run renderer tests and compile checks**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_preview.py tests/test_feishu_render.py tests/test_gve16_native_whiteboard.py tests/test_feishu_sample_aligned_board.py -q
python -m compileall -q backend/review_preview.py backend/feishu_native_board.py backend/feishu_render.py
```

Expected: PASS with two ordered boards and no interaction rule chapters.

- [ ] **Step 7: Commit**

```powershell
git add backend/review_preview.py backend/feishu_native_board.py backend/feishu_render.py tests/test_review_preview.py tests/test_feishu_render.py tests/test_gve16_native_whiteboard.py tests/test_feishu_sample_aligned_board.py
git commit -m "refactor: render two interaction whiteboards"
```

---

### Task 5: Resumable two-board Feishu publisher and legacy checkpoint migration

**Files:**
- Modify: `backend/feishu_publish.py:40-130,180-430`
- Modify: `backend/server.py:430-475,850-910` publication status sanitizer and public response tests
- Modify: `tests/test_feishu_publish.py`
- Modify: `tests/test_feishu_publish_api.py`

**Interfaces:**
- Consumes: Task 4 ordered `(planning, competitor)` native boards and existing publication record.
- Produces: active checkpoint views containing only `planning`/`competitor`; persisted checkpoint dictionaries retain any legacy `ux` entries unchanged but exclude them from completion/retry decisions; exactly two distinct whiteboard tokens.

- [ ] **Step 1: Write failing token-count and resume tests**

```python
def test_publisher_requires_two_distinct_whiteboard_tokens(fake_cli, confirmed_job, tmp_path):
    fake_cli.fetch_whiteboards = ["planning-token", "competitor-token"]
    record = FeishuPublisher(fake_cli, tmp_path).publish(confirmed_job, request_id="req-two")
    assert record.status == "published"
    assert fake_cli.updated_board_keys == ["planning", "competitor"]


def test_competitor_failure_resumes_without_rewriting_planning(fake_cli, confirmed_job, tmp_path):
    fake_cli.fail_board_once = "competitor"
    publisher = FeishuPublisher(fake_cli, tmp_path)
    with pytest.raises(LarkCommandError):
        publisher.publish(confirmed_job, request_id="req-resume")
    planning_writes = fake_cli.structure_writes["planning"]
    publisher.publish(confirmed_job, request_id="req-resume")
    assert fake_cli.structure_writes["planning"] == planning_writes
    assert confirmed_job["feishuPublication"]["boardVerified"] == {"planning": True, "competitor": True}
```

- [ ] **Step 2: Write failing legacy migration tests**

```python
def test_legacy_three_board_checkpoint_ignores_ux_for_new_completion(confirmed_job):
    confirmed_job["feishuPublication"] = {
        "requestId": "req-old",
        "status": "partial",
        "boardVerified": {"ux": False, "planning": True, "competitor": False},
        "boardStructureRequestIds": {"ux": "old", "planning": "req-old"},
        "boardMediaDone": {"ux": {"legacy": "token"}, "planning": {}},
    }
    checkpoint = _board_checkpoint(confirmed_job["feishuPublication"])
    assert checkpoint["boardVerified"] == {"planning": True, "competitor": False}
    assert "ux" not in checkpoint["boardTokens"]
```

- [ ] **Step 3: Run RED publisher tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_feishu_publish.py tests/test_feishu_publish_api.py -q
```

Expected: failures show the publisher still requires three tokens/boards and carries UX checkpoints.

- [ ] **Step 4: Normalize active checkpoint dictionaries**

```python
ACTIVE_BOARD_KEYS = ("planning", "competitor")


def _active_map(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {key: source[key] for key in ACTIVE_BOARD_KEYS if key in source}
```

Use `_active_map` only to calculate active work, completion, retry, and token mapping for `boardTokens`, `boardStructureRequestIds`, `boardMediaDone`, and `boardVerified`. When persisting updated dictionaries, merge active values back into the original dictionaries so any legacy `ux` entry remains byte-for-byte unchanged. Continue migrating old single-board `boardStructureRequestId` to `planning`. Never delete or rewrite persisted UX checkpoint data.

- [ ] **Step 5: Require exactly two ordered document whiteboards**

```python
if len(tokens) != len(boards) or len(tokens) != 2 or len(set(tokens)) != 2:
    raise LarkCommandError("command_failed", "Feishu document must contain exactly two distinct UE flow whiteboards")
```

Map tokens with `zip(boards, tokens)` and preserve per-board structure/media/verify idempotency. A planning success plus competitor failure must resume competitor only.

- [ ] **Step 6: Verify redaction and idempotency**

Ensure API responses still contain only `status`, `documentUrl`, and user-facing message. Add a recursive assertion that no key/value exposes document tokens, board tokens, media tokens, absolute paths, CLI stdout, or credentials.

- [ ] **Step 7: Run publisher/API tests and compile checks**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_feishu_publish.py tests/test_feishu_publish_api.py -q
python -m compileall -q backend/feishu_publish.py backend/server.py
```

Expected: PASS; partial resume never rewrites verified planning and UX is not part of active completion.

- [ ] **Step 8: Commit**

```powershell
git add backend/feishu_publish.py backend/server.py tests/test_feishu_publish.py tests/test_feishu_publish_api.py
git commit -m "refactor: publish two interaction whiteboards"
```

---

### Task 6: Update GVE16 skills and delivery contracts

**Files:**
- Modify: `.codex/skills/gve16-feishu-delivery/SKILL.md`
- Modify: `.codex/skills/gve16-feishu-delivery/references/delivery-contract.md`
- Modify: `.codex/skills/gve16-feishu-delivery/references/flowdoc-review-contract.md`
- Modify: `.codex/skills/gve16-feishu-whiteboard/SKILL.md`
- Modify: `skills/gve16-feishu-delivery/SKILL.md`
- Modify: `skills/gve16-feishu-delivery/references/delivery-contract.md`
- Modify: `skills/gve16-feishu-delivery/references/flowdoc-review-contract.md`
- Modify: `skills/gve16-feishu-whiteboard/SKILL.md`
- Modify: `tests/test_gve16_delivery_skill.py`
- Modify: `tests/test_gve16_whiteboard_skill.py`
- Modify: `findings.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: approved design spec and verified Wiki revision 40 reference.
- Produces: identical project/runtime Skill copies documenting two-board interaction delivery and separating future gameplay planning from the interaction contract.

- [ ] **Step 1: Write failing Skill-contract tests**

```python
def test_interaction_skill_names_only_two_active_ue_boards(skill_text):
    assert "策划草图" in skill_text
    assert "竞品参考" in skill_text
    assert "交互阶段不生成 UX设计" in skill_text
    assert "交互阶段不输出叙事、引导、红点提示章节" in skill_text
    assert "planning → competitor" in skill_text


def test_project_and_runtime_skill_copies_match(project_skill, runtime_skill):
    assert project_skill.read_text(encoding="utf-8") == runtime_skill.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run RED Skill tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_gve16_delivery_skill.py tests/test_gve16_whiteboard_skill.py -q
```

Expected: failures show the current Skill still mandates three boards and three rule chapters.

- [ ] **Step 3: Rewrite the active interaction contract**

Document these exact rules in both Skill trees:

```text
交互阶段的 UE 流转图只包含两个原生画板，顺序为 planning → competitor：
1. 策划草图：确认后的代表截图、组件编号、规则说明、straight 跳转/返回线和黄色待确认注记。
2. 竞品参考：仅用户上传的竞品截图和文件名；为空时显示黄色“待补充”。
交互阶段不生成 UX设计，也不输出叙事、引导、红点提示章节。
```

State that future gameplay planning uses a separate evidence-specific contract and must not be inferred from this interaction-only rule.

- [ ] **Step 4: Record durable findings and progress**

Add the Wiki document ID/revision, node counts (planning 146: 58 image/54 composite/30 connector/4 sticky; competitor 26 image), approved compatibility strategy A, and active two-board order to `findings.md`/`progress.md`. Do not store whiteboard tokens or credentials.

- [ ] **Step 5: Run Skill tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_gve16_delivery_skill.py tests/test_gve16_whiteboard_skill.py -q
```

Expected: PASS and byte-identical Skill copies.

- [ ] **Step 6: Commit**

```powershell
git add .codex/skills/gve16-feishu-delivery .codex/skills/gve16-feishu-whiteboard skills/gve16-feishu-delivery skills/gve16-feishu-whiteboard tests/test_gve16_delivery_skill.py tests/test_gve16_whiteboard_skill.py findings.md progress.md
git commit -m "docs: align GVE16 interaction to two boards"
```

---

### Task 7: End-to-end migration, browser QA, and completion records

**Files:**
- Modify: `tests/test_review_workflow_integration.py`
- Modify: `tools/review-workspace-browser-qa.js`
- Modify: `tests/test_review_workspace_browser_qa_contract.py`
- Modify: `task_plan.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: Tasks 1-6 active workflow, renderer, publisher, and Skill contract.
- Produces: one automated end-to-end regression, one real-browser QA journey, full-suite evidence, and updated completion records.

- [ ] **Step 1: Write failing end-to-end migration test**

```python
def test_legacy_three_board_job_completes_new_two_board_workflow(client, legacy_three_board_job):
    job_id = legacy_three_board_job["id"]
    model = client.get(f"/api/jobs/{job_id}").json()["reviewModel"]
    assert model["ruleDomains"] == legacy_three_board_job["reviewModel"]["ruleDomains"]
    assert model["referenceBoards"]["ux"] == legacy_three_board_job["reviewModel"]["referenceBoards"]["ux"]
    assert review_gate(model)["exportReady"] is True
    preview = client.get(f"/api/jobs/{job_id}/review/preview").json()
    assert [item["key"] for item in preview["referenceBoardSummary"]] == ["planning", "competitor"]
```

- [ ] **Step 2: Update browser QA journey**

Make the browser script exercise:

```text
flow confirmation
→ each stage/component confirmation
→ preview opens directly (no rules tab)
→ planning card is read-only
→ competitor empty state says 待补充 and does not block
→ upload/reorder/delete/retry competitor assets
→ export button enables from the current preview revision
```

Assert there is no rules nav, rules panel, UX upload input, or vertical text layout.

- [ ] **Step 3: Run focused workflow and browser-contract tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_workflow_integration.py tests/test_review_workspace_browser_qa_contract.py -q
node --test tests/js/*.test.js
```

Expected: PASS.

- [ ] **Step 4: Run the full project-owned suites**

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests -q
node --test tests/js/*.test.js
python -m compileall -q backend
Get-ChildItem js -Filter *.js | ForEach-Object { node --check $_.FullName }
git diff --check
```

Expected: all project-owned Python/JavaScript tests pass. If vendored packages are collected by an unscoped command, report them separately and do not treat them as project failures.

- [ ] **Step 5: Run real browser QA**

Start the existing project server, verify `/api/health == 200`, then run `tools/review-workspace-browser-qa.js` with the configured Edge/Chromium and fixture paths. Capture the final mobile screenshot and confirm the journey above. Do not publish a real Feishu document in this task.

- [ ] **Step 6: Update completion records**

Mark the obsolete three-board/rule-domain plan as superseded in `task_plan.md` and record the two-board test/browser results in `progress.md`. Preserve prior history; do not rewrite it as though it never happened.

- [ ] **Step 7: Commit**

```powershell
git add tests/test_review_workflow_integration.py tools/review-workspace-browser-qa.js tests/test_review_workspace_browser_qa_contract.py task_plan.md progress.md
git commit -m "test: verify two-board interaction workflow"
```

---

## Plan Completion Checklist

- [ ] Fresh tasks contain only active planning/competitor board defaults.
- [ ] Legacy rule/UX data survives reads and active saves unchanged.
- [ ] Rules confirmation and UX/competitor emptiness do not block active export.
- [ ] Component confirmation routes directly to preview.
- [ ] Browser has no rules view or UX upload entry.
- [ ] Preview contains read-only planning plus competitor controls and exactly two summaries.
- [ ] Interaction XML contains exactly two whiteboard blocks and no rule-domain chapters.
- [ ] Publisher verifies/resumes planning and competitor independently and ignores legacy UX completion.
- [ ] Skills and durable records describe the revision-40 two-board standard.
- [ ] Python, JavaScript, syntax, compile, browser, and diff checks pass.
