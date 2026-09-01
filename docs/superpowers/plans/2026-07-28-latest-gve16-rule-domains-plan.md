# Latest GVE16 Rule Domains and Three Whiteboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing staged GVE16 review workspace so users can review narrative, guidance, and red-dot rules, optionally attach UX/competitor board assets, and publish one Feishu document containing three independent native whiteboards plus the three required chapters.

**Architecture:** Keep `reviewModel.schemaVersion` at `2.0` and add backward-compatible `ruleDomains` and `referenceBoards` defaults through `ensure_review_model`. Rule-domain edits remain revisioned operations; binary reference assets use focused multipart endpoints and persist metadata back into the same review model. Rendering returns an ordered tuple of named native boards, and the publisher checkpoints structure/media independently by board key while migrating legacy single-board records to the `planning` key.

**Tech Stack:** Python 3.11, FastAPI, Python stdlib filesystem/JSON, vanilla JavaScript modules, HTML/CSS, pytest, Node built-in test runner, installed `lark-cli.cmd` and `@larksuite/whiteboard-cli@^0.2.13`.

## Global Constraints

- Use TDD for every behavior: write the focused failing test, verify the expected failure, implement the minimum, then rerun focused and related suites.
- Add no dependency and do not change the built-in model/API configuration.
- Keep `schemaVersion: "2.0"`; existing history is upgraded additively by `ensure_review_model`.
- Narrative, guidance, and red-dot chapters always render. Empty domains use exactly `本次素材未展示，待确认` and do not block export.
- Rule-domain confirmation is mandatory before preview/export. Broken stage/frame/component references, broken guidance steps, and broken red-dot path references block export.
- UX and competitor assets are optional, never enter `frames`, `sources`, scenes, model analysis, representative-frame selection, or the planning board.
- The planning whiteboard continues to use confirmed representative frames only. UX and competitor boards use only their explicitly assigned assets.
- Feishu output contains three ordered native boards: `ux`, `planning`, `competitor`. Empty optional boards contain `待补充`.
- Preserve explicit user publish, Feishu user identity, fixed-folder reuse, revision conflict protection, idempotent retry, and preview/raw verification.
- Do not commit `artifacts/`, credentials, tokens, uploaded test media, or job runtime data.

---

### Task 1: Canonical rule-domain and reference-board model

**Files:**
- Modify: `backend/review_model.py:116-180,228-360,440-677`
- Modify: `tests/review_fixtures.py`
- Test: `tests/test_review_model.py`
- Test: `tests/test_review_model_seed.py`

**Interfaces:**
- Consumes: existing `build_review_model(job)`, `ensure_review_model(job)`, `validate_review_model(model)`, and `review_gate(model)`.
- Produces: `empty_rule_domains() -> dict[str, Any]`, `empty_reference_boards() -> dict[str, Any]`, additive model keys `ruleDomains` and `referenceBoards`, and validation/blocker IDs prefixed `RULE_DOMAIN_` or the damaged rule ID.

- [ ] **Step 1: Write failing default/backfill tests**

Add tests that assert both new and legacy models receive non-aliased defaults:

```python
def test_review_model_adds_empty_latest_gve16_domains_and_boards(sample_job):
    model = build_review_model(sample_job)
    assert model["ruleDomains"] == {
        "narrative": [], "guidance": [], "redDots": [],
        "reviewedDomains": [],
        "confirmation": {"confirmed": False, "revision": None},
    }
    assert model["referenceBoards"] == {
        "ux": {"assets": [], "status": "pending"},
        "planning": {"source": "confirmed_review_model", "status": "generated"},
        "competitor": {"assets": [], "status": "pending"},
    }

def test_legacy_review_model_is_backfilled_without_losing_confirmations(sample_job):
    legacy = build_review_model(sample_job)
    legacy.pop("ruleDomains")
    legacy.pop("referenceBoards")
    legacy["reviewState"]["flowConfirmed"] = True
    sample_job["reviewModel"] = legacy
    upgraded = ensure_review_model(sample_job)
    assert upgraded["reviewState"]["flowConfirmed"] is True
    assert upgraded["ruleDomains"]["narrative"] == []
    assert upgraded["referenceBoards"]["planning"]["source"] == "confirmed_review_model"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_model.py tests/test_review_model_seed.py -q
```

Expected: FAIL because `ruleDomains` and `referenceBoards` do not exist.

- [ ] **Step 3: Add model constructors and additive backfill**

Implement dependency-free constructors and call them from both build and ensure paths:

```python
RULE_DOMAIN_KEYS = ("narrative", "guidance", "redDots")
REFERENCE_BOARD_KEYS = ("ux", "planning", "competitor")

def empty_rule_domains() -> dict[str, Any]:
    return {
        "narrative": [], "guidance": [], "redDots": [],
        "reviewedDomains": [],
        "confirmation": {"confirmed": False, "revision": None},
    }

def empty_reference_boards() -> dict[str, Any]:
    return {
        "ux": {"assets": [], "status": "pending"},
        "planning": {"source": "confirmed_review_model", "status": "generated"},
        "competitor": {"assets": [], "status": "pending"},
    }
```

Use `deepcopy` when inserting defaults. Backfill missing nested keys without replacing existing lists, confirmations, or asset metadata.

- [ ] **Step 4: Write failing validation and gate tests**

Cover valid empty domains, missing rule confirmation, invalid bindings, and non-blocking empty content:

```python
def test_empty_reviewed_rule_domains_are_valid_but_require_confirmation(sample_job):
    model = build_review_model(sample_job)
    model["ruleDomains"]["reviewedDomains"] = ["narrative", "guidance", "redDots"]
    gate = review_gate(model)
    assert "RULE_DOMAINS_NOT_CONFIRMED" in gate["blockers"]
    assert not any("narrative" in item for item in gate["blockers"])

def test_rule_domain_reference_validation_rejects_unknown_component(confirmed_model):
    confirmed_model["ruleDomains"]["guidance"] = [{
        "id": "GDE-001", "title": "首次引导", "stageId": confirmed_model["stages"][0]["id"],
        "frameId": None, "scopeCount": "首次", "prerequisite": "进入页面",
        "steps": [{"id": "GDS-001", "action": "点击", "componentId": "CMP-MISSING", "prompt": "继续"}],
        "destination": "下一页", "sourceLevel": "unknown", "confidence": "低", "unknownReason": "待确认",
    }]
    assert any("GDE-001" in error and "CMP-MISSING" in error for error in validate_review_model(confirmed_model))
```

Also test narrative stage/frame references, red-dot ordered `path` references, asset IDs/paths/order uniqueness, and that empty UX/competitor assets are valid warnings rather than blockers.

- [ ] **Step 5: Implement validation and review gate rules**

Validate these exact shapes:

```python
NARRATIVE_FIELDS = ("title", "stageId", "triggerScene", "triggerNode", "presentation", "continuation")
GUIDANCE_FIELDS = ("title", "stageId", "scopeCount", "prerequisite", "steps", "destination")
RED_DOT_FIELDS = ("title", "stageId", "showCondition", "clearCondition", "path")
```

Require unique `NAR-*`, `GDE-*`, `RDT-*` IDs across the model. `stageId` must exist; optional `frameId` must be in `sources`; optional component IDs must exist and belong to the bound stage. Guidance `steps` and red-dot `path` must be lists of objects with stable nested IDs. Empty domains remain valid.

Extend `review_gate`:

```python
domains = model.get("ruleDomains") or {}
if not (domains.get("confirmation") or {}).get("confirmed"):
    blockers.append("RULE_DOMAINS_NOT_CONFIRMED")
for warning in ("UX_BOARD_PENDING", "COMPETITOR_BOARD_PENDING"):
    warnings.append(warning)
```

Only add the optional-board warnings when their asset lists are empty. Validation errors already become blockers.

- [ ] **Step 6: Run focused model tests**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/review_model.py tests/review_fixtures.py tests/test_review_model.py tests/test_review_model_seed.py
git commit -m "feat: add latest GVE16 review domains"
```

---

### Task 2: Revisioned rule operations and confirmation API

**Files:**
- Modify: `backend/review_service.py:1-690`
- Modify: `backend/server.py:598-689`
- Test: `tests/test_review_service.py`
- Test: `tests/test_review_api.py`
- Test: `tests/test_review_persistence.py`

**Interfaces:**
- Consumes: Task 1 model keys and validation.
- Produces operations `upsert_rule`, `delete_rule`, `reorder_rule`, `reorder_rule_nested`, `mark_rule_domain_reviewed`; function `confirm_rule_domains(model, expected_revision) -> dict`; endpoint `POST /api/jobs/{job_id}/review/confirm-rules`.

- [ ] **Step 1: Write failing service tests**

```python
def test_rule_operations_are_revisioned_and_invalidate_confirmation(confirmed_model):
    model = apply_operations(confirmed_model, [{
        "type": "upsert_rule", "domain": "narrative", "rule": {
            "title": "开场叙事", "stageId": confirmed_model["stages"][0]["id"],
            "frameId": None, "triggerScene": "进入关卡", "triggerNode": "开场",
            "presentation": "播放对白", "continuation": "开始操作",
            "sourceLevel": "observed", "confidence": "高", "unknownReason": "",
        },
    }], confirmed_model["revision"])
    assert model["ruleDomains"]["narrative"][0]["id"] == "NAR-001"
    assert model["ruleDomains"]["confirmation"]["confirmed"] is False
    assert model["reviewState"]["previewRevision"] is None

def test_confirm_rule_domains_requires_all_tabs_reviewed(confirmed_model):
    confirmed_model["ruleDomains"]["reviewedDomains"] = ["narrative", "guidance"]
    with pytest.raises(ValueError, match="redDots"):
        confirm_rule_domains(confirmed_model, confirmed_model["revision"])
```

Add delete/reorder, nested guidance step preservation, nested red-dot path preservation, undo/redo, human-edited field tracking, reanalysis suggestion protection, and flow/stage edits invalidating rule confirmation.

- [ ] **Step 2: Run service tests and verify RED**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_service.py tests/test_review_persistence.py -q
```

Expected: FAIL for unknown operation types and missing `confirm_rule_domains`.

- [ ] **Step 3: Implement minimal operations**

Add `rule` to entity metadata only when resolving existing rule IDs; keep domain routing explicit:

```python
RULE_COLLECTIONS = {"narrative": "NAR", "guidance": "GDE", "redDots": "RDT"}

def _rule_list(model: dict[str, Any], domain: Any) -> list[dict[str, Any]]:
    if domain not in RULE_COLLECTIONS:
        raise ValueError("unknown rule domain")
    return model["ruleDomains"][domain]
```

`upsert_rule` assigns the next stable ID, validates the full model before commit, marks supplied top-level fields human-edited, and preserves `suggestions`. `reorder_rule` rewrites integer `order` values. `mark_rule_domain_reviewed` adds one domain to `reviewedDomains` without fabricating rules.

Any content operation sets:

```python
result["ruleDomains"]["confirmation"] = {"confirmed": False, "revision": None}
result["reviewState"]["previewRevision"] = None
```

Flow- or stage-changing operations also clear `reviewedDomains`, because bindings and interpretation may have changed.

- [ ] **Step 4: Implement confirmation**

```python
def confirm_rule_domains(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    missing = [key for key in RULE_DOMAIN_KEYS if key not in model["ruleDomains"]["reviewedDomains"]]
    if missing:
        raise ValueError(f"rule domains not reviewed: {', '.join(missing)}")
    errors = validate_review_model(model)
    if errors:
        raise ValueError("; ".join(errors))
    result = deepcopy(model)
    result["revision"] += 1
    result["ruleDomains"]["confirmation"] = {"confirmed": True, "revision": result["revision"]}
    result["reviewState"].update(status="rules_confirmed", previewRevision=None)
    return result
```

Follow existing flow/stage confirmation revision semantics: confirmation itself persists atomically and returns the current canonical model.

- [ ] **Step 5: Write failing API tests**

```python
def test_confirm_rule_domains_endpoint_persists_model(client, completed_job):
    job_id = completed_job["id"]
    model = completed_job["reviewModel"]
    model["ruleDomains"]["reviewedDomains"] = ["narrative", "guidance", "redDots"]
    response = client.post(f"/api/jobs/{job_id}/review/confirm-rules", json={"expectedRevision": model["revision"]})
    assert response.status_code == 200
    assert response.json()["ruleDomains"]["confirmation"]["confirmed"] is True
```

Also assert 409 conflict and 422/400 validation behavior matches existing confirmation endpoints.

- [ ] **Step 6: Add endpoint and client-visible errors**

In `backend/server.py`, import `confirm_rule_domains` and add:

```python
@app.post("/api/jobs/{job_id}/review/confirm-rules")
def confirm_review_rules(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(job_id, payload, confirm_rule_domains)
```

- [ ] **Step 7: Run focused backend tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_service.py tests/test_review_persistence.py tests/test_review_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add backend/review_service.py backend/server.py tests/test_review_service.py tests/test_review_persistence.py tests/test_review_api.py
git commit -m "feat: review and confirm GVE16 rule domains"
```

---

### Task 3: Optional UX and competitor asset persistence

**Files:**
- Create: `backend/reference_board_assets.py`
- Modify: `backend/server.py:17,281-388,598-689`
- Test: `tests/test_reference_board_assets.py`
- Test: `tests/test_reference_board_api.py`

**Interfaces:**
- Consumes: `job_path(job_id)`, JSON job persistence, Task 1 `referenceBoards`.
- Produces: `persist_reference_assets(job: dict, job_dir: Path, board_key: str, uploads: list[UploadFile], manifest: str) -> list[dict]`, `delete_reference_asset(job: dict, job_dir: Path, board_key: str, asset_id: str) -> list[dict]`, `reorder_reference_assets(job: dict, board_key: str, asset_ids: list[str]) -> list[dict]`, `_require_review_revision(job: dict, expected: Any) -> None`, and `_finish_reference_board_mutation(job: dict, board_key: str) -> dict`; multipart/upload, delete, and order endpoints under `/api/jobs/{job_id}/review-model/reference-boards/{board_key}`.

- [ ] **Step 1: Write failing pure persistence tests**

Use in-memory `UploadFile` objects and a temporary job directory:

```python
def test_reference_assets_are_isolated_from_primary_frames(tmp_path, image_uploads, job):
    before_frames = deepcopy(job["frames"])
    assets = persist_reference_assets(job, tmp_path, "ux", image_uploads, '["ux_2.png","ux_10.png"]')
    assert [item["sourceName"] for item in assets] == ["ux_2.png", "ux_10.png"]
    assert all(item["relativePath"].startswith("reference_boards/ux/") for item in assets)
    assert job["frames"] == before_frames
    assert job["reviewModel"]["sources"].keys() == {frame["id"] for frame in before_frames}
```

Test allowed board keys (`ux`, `competitor` only), image content validation, natural filename order when no manifest is supplied, stable `UXA-*`/`CPA-*` IDs, explicit order, safe filenames, delete, and missing-file recovery status.

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_reference_board_assets.py -q
```

Expected: collection fails because `backend.reference_board_assets` does not exist.

- [ ] **Step 3: Implement filesystem boundary**

Use `Path.resolve()` containment checks and existing Pillow/OpenCV availability only for dimensions; do not add packages. Store files under `job_dir / "reference_boards" / board_key`. Return metadata:

```python
{
    "id": "UXA-001",
    "sourceName": "ux_2.png",
    "order": 1,
    "relativePath": "reference_boards/ux/UXA-001.png",
    "width": 1170,
    "height": 2532,
    "status": "ready",
}
```

Reject zero-byte, undecodable, non-image, duplicate manifest entries, traversal, and more than 30 assets per optional board. The cap reuses the existing primary screenshot maximum and is enforced independently per optional board.

Add these server-side mutation helpers next to the endpoints so all three calls share revision behavior without entering the text undo stack:

```python
def _require_review_revision(job: dict[str, Any], expected: Any) -> None:
    current = (job.get("reviewModel") or {}).get("revision")
    if type(expected) is not int or expected != current:
        raise ReviewConflict(current_revision=current or 0)

def _finish_reference_board_mutation(job: dict[str, Any], board_key: str) -> dict[str, Any]:
    model = job["reviewModel"]
    board = model["referenceBoards"][board_key]
    board["status"] = "ready" if board["assets"] else "pending"
    model["revision"] += 1
    model["reviewState"]["previewRevision"] = None
    errors = validate_review_model(model)
    if errors:
        raise ValueError("; ".join(errors))
    return model
```

- [ ] **Step 4: Write failing API tests**

```python
def test_upload_reference_board_assets_updates_only_requested_board(client, completed_job, png_files):
    response = client.post(
        f"/api/jobs/{completed_job['id']}/review-model/reference-boards/ux/assets",
        files=[("images", (path.name, path.read_bytes(), "image/png")) for path in png_files],
        data={"manifest": json.dumps([path.name for path in png_files]), "expectedRevision": str(completed_job["reviewModel"]["revision"])},
    )
    assert response.status_code == 200
    model = response.json()
    assert len(model["referenceBoards"]["ux"]["assets"]) == len(png_files)
    assert model["referenceBoards"]["competitor"]["assets"] == []
```

Test 409 revision conflicts, board-key rejection, delete, reorder, and public job paths without leaking absolute paths.

- [ ] **Step 5: Add focused endpoints**

Add endpoints with explicit user action only:

```python
@app.post("/api/jobs/{job_id}/review-model/reference-boards/{board_key}/assets")
def upload_reference_board_assets(
    job_id: str, board_key: str, images: list[UploadFile] = File(...),
    manifest: str = Form(""), expectedRevision: int = Form(...),
) -> dict[str, Any]:
    def mutation(job: dict[str, Any]) -> dict[str, Any]:
        _require_review_revision(job, expectedRevision)
        persist_reference_assets(job, job_path(job_id), board_key, images, manifest)
        return _finish_reference_board_mutation(job, board_key)
    return _mutate_review_job(job_id, mutation)

@app.delete("/api/jobs/{job_id}/review-model/reference-boards/{board_key}/assets/{asset_id}")
def remove_reference_board_asset(job_id: str, board_key: str, asset_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def mutation(job: dict[str, Any]) -> dict[str, Any]:
        _require_review_revision(job, payload.get("expectedRevision"))
        delete_reference_asset(job, job_path(job_id), board_key, asset_id)
        return _finish_reference_board_mutation(job, board_key)
    return _mutate_review_job(job_id, mutation)

@app.post("/api/jobs/{job_id}/review-model/reference-boards/{board_key}/order")
def order_reference_board_assets(job_id: str, board_key: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def mutation(job: dict[str, Any]) -> dict[str, Any]:
        _require_review_revision(job, payload.get("expectedRevision"))
        reorder_reference_assets(job, board_key, payload.get("assetIds"))
        return _finish_reference_board_mutation(job, board_key)
    return _mutate_review_job(job_id, mutation)
```

All mutations increment review revision, invalidate rule confirmation only if asset metadata becomes invalid, always invalidate preview, and persist the job once under the existing lock.

- [ ] **Step 6: Run focused asset/API tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_reference_board_assets.py tests/test_reference_board_api.py tests/test_image_sequence.py tests/test_image_sequence_api.py -q
```

Expected: PASS, proving the new pool is isolated from primary screenshots.

- [ ] **Step 7: Commit**

```powershell
git add backend/reference_board_assets.py backend/server.py tests/test_reference_board_assets.py tests/test_reference_board_api.py
git commit -m "feat: persist optional GVE16 board assets"
```

---

### Task 4: Rule-domain review frontend

**Files:**
- Create: `js/rule-domain-review.js`
- Create: `tests/js/rule-domain-review.test.js`
- Modify: `js/review-client.js:1-150`
- Modify: `js/review-workspace.js:1-90`
- Modify: `js/backend.js:329-675`
- Modify: `index.html` review workspace markup and script list
- Modify: `css/style.css`
- Test: `tests/test_review_workspace_ui_contract.py`

**Interfaces:**
- Consumes: Task 2 operations and `confirm-rules` endpoint.
- Produces: global/module `RuleDomainReview` with pure helpers and `render(workspace)`; workspace view `rules`; UI state `selectedRuleDomain`, `selectedRuleId`, `ruleMobilePane`.

- [ ] **Step 1: Write pure RED tests**

```javascript
test("empty domains remain empty and expose the approved pending copy", () => {
  const summary = RuleDomainReview.domainSummary({ narrative: [], guidance: [], redDots: [] }, "narrative");
  assert.deepEqual(summary, { count: 0, pending: 0, emptyText: "本次素材未展示，待确认" });
});

test("components are filtered by the selected stage", () => {
  const model = { components: [{ id: "CMP-1", stageId: "STG-1" }, { id: "CMP-2", stageId: "STG-2" }] };
  assert.deepEqual(RuleDomainReview.componentsForStage(model, "STG-1").map((item) => item.id), ["CMP-1"]);
});

test("guidance steps and red-dot paths produce stable reorder operations", () => {
  assert.deepEqual(RuleDomainReview.reorderNested("guidance", "GDE-1", "steps", 2, 0), {
    type: "reorder_rule_nested", domain: "guidance", id: "GDE-1", field: "steps", fromIndex: 2, toIndex: 0,
  });
});
```

- [ ] **Step 2: Run Node tests and verify RED**

```powershell
node --test tests/js/rule-domain-review.test.js
```

Expected: FAIL because `RuleDomainReview` does not exist.

- [ ] **Step 3: Implement pure helpers and accessible renderer**

Export/test these functions:

```javascript
const DOMAIN_KEYS = ["narrative", "guidance", "redDots"];
function domainSummary(ruleDomains, key) {
  const rules = ruleDomains?.[key] || [];
  return { count: rules.length, pending: rules.filter((item) => item.unknownReason).length, emptyText: rules.length ? "" : "本次素材未展示，待确认" };
}
function componentsForStage(model, stageId) { return (model.components || []).filter((item) => item.stageId === stageId); }
function newRuleDraft(domain, stageId) {
  const common = { title: "", stageId, frameId: null, sourceLevel: "unknown", confidence: "低", unknownReason: "待确认" };
  if (domain === "narrative") return { ...common, triggerScene: "", triggerNode: "", presentation: "", continuation: "" };
  if (domain === "guidance") return { ...common, scopeCount: "", prerequisite: "", steps: [], destination: "" };
  return { ...common, showCondition: "", clearCondition: "", path: [] };
}
function reorderNested(domain, id, field, fromIndex, toIndex) { return { type: "reorder_rule_nested", domain, id, field, fromIndex, toIndex }; }
function render(workspace) {
  const root = workspace.root;
  root.replaceChildren(buildRuleDomainTabs(workspace), buildRuleDomainEditor(workspace), buildReferenceBoardSection(workspace));
}
```

Render three `role="tab"` controls and one `role="tabpanel"`; a left rule list and one right editor; stage/frame/component selectors; add/delete/up/down buttons; nested guidance step cards; nested red-dot path cards; empty-state copy and add button. Each tab selection sends `mark_rule_domain_reviewed` once and persists UI state. Do not create empty placeholder rules.

- [ ] **Step 4: Extend review client/workspace routing**

Add:

```javascript
confirmRules(expectedRevision) {
  return this.request(`/api/jobs/${this.jobId}/review/confirm-rules`, {
    method: "POST", body: JSON.stringify({ expectedRevision }),
  });
}
```

`routeForModel` must return `rules` after flow and all stages are confirmed but rule domains are not confirmed; return `preview` only when `modelPreviewIsCurrent(model)` is true. `selectionExists` and conflict replay must resolve `narrative`, `guidance`, and `redDots` IDs through the explicit domain key carried in selection.

- [ ] **Step 5: Add markup, styles, and backend integration**

Add `rulesReviewView`, a `data-review-view="rules"` navigation button, and `reviewConfirmRulesBtn`. In `setReviewWorkspaceView`, allow `["flow", "stage", "rules", "preview", "analysis_failed"]`; show the rule confirmation button only in `rules`; disable preview until flow, all stages, and rule domains are confirmed.

After the final stage confirmation, route to `rules`, not preview. After rule confirmation, call `loadReviewPreview`.

CSS requirements:

```css
.rule-domain-layout { display:grid; grid-template-columns:minmax(220px, .8fr) minmax(0, 2fr); gap:16px; }
.rule-domain-action { min-height:44px; }
@media (max-width: 760px) { .rule-domain-layout { display:block; } }
@media (prefers-reduced-motion: reduce) { .rule-domain-review * { scroll-behavior:auto; transition:none; } }
```

Use existing color/focus tokens; no emoji icons, no hover-only controls, and no page-level horizontal scrolling.

- [ ] **Step 6: Add UI contract assertions**

Assert script order (`review-workspace.js`, `rule-domain-review.js`, then `backend.js`), the new view/button IDs, 44px controls, `aria-live`, mobile pane CSS, and no inline event handlers.

- [ ] **Step 7: Run frontend tests**

```powershell
node --test tests/js/rule-domain-review.test.js tests/js/review-workspace.test.js tests/js/review-client.test.js
node --check js/rule-domain-review.js
node --check js/review-client.js
node --check js/review-workspace.js
node --check js/backend.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_workspace_ui_contract.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add js/rule-domain-review.js js/review-client.js js/review-workspace.js js/backend.js index.html css/style.css tests/js/rule-domain-review.test.js tests/test_review_workspace_ui_contract.py
git commit -m "feat: review latest GVE16 rule domains"
```

---

### Task 5: Optional board asset UI and export preview counts

**Files:**
- Create: `js/reference-board-assets.js`
- Create: `tests/js/reference-board-assets.test.js`
- Modify: `js/review-client.js`
- Modify: `js/rule-domain-review.js`
- Modify: `js/export-preview.js`
- Modify: `js/backend.js`
- Modify: `css/style.css`
- Modify: `backend/review_preview.py`
- Test: `tests/test_review_preview.py`
- Test: `tests/js/export-preview.test.js`

**Interfaces:**
- Consumes: Task 3 asset endpoints and Task 4 rules view.
- Produces: `ReferenceBoardAssets` browser controller/helpers and preview fields `ruleDomainSummary`, `referenceBoardSummary`.

- [ ] **Step 1: Write RED helper and preview tests**

```javascript
test("board upload manifest preserves visible order", () => {
  const files = [{ name: "ux_10.png" }, { name: "ux_2.png" }];
  assert.equal(ReferenceBoardAssets.manifest(files), JSON.stringify(["ux_10.png", "ux_2.png"]));
});

test("planning board is read-only and optional boards expose pending state", () => {
  const summary = ReferenceBoardAssets.summaries({ ux: { assets: [] }, planning: { status: "generated" }, competitor: { assets: [] } });
  assert.deepEqual(summary.map((item) => [item.key, item.editable, item.label]), [
    ["ux", true, "待补充"], ["planning", false, "自动生成"], ["competitor", true, "待补充"],
  ]);
});
```

Python preview test:

```python
def test_review_preview_reports_three_boards_and_three_rule_domains(confirmed_job):
    preview = build_review_preview(confirmed_job)
    assert [item["key"] for item in preview["referenceBoardSummary"]] == ["ux", "planning", "competitor"]
    assert preview["ruleDomainSummary"]["narrative"]["emptyText"] == "本次素材未展示，待确认"
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
node --test tests/js/reference-board-assets.test.js tests/js/export-preview.test.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_review_preview.py -q
```

Expected: FAIL for missing helper and preview fields.

- [ ] **Step 3: Implement reference asset client/controller**

Add ReviewClient methods:

```javascript
uploadBoardAssets(boardKey, files, expectedRevision) {
  const body = new FormData();
  files.forEach((file) => body.append("images", file, file.name));
  body.append("manifest", JSON.stringify(files.map((file) => file.name)));
  body.append("expectedRevision", String(expectedRevision));
  return this.request(`/reference-boards/${boardKey}/assets`, { method: "POST", body });
}
deleteBoardAsset(boardKey, assetId, expectedRevision) {
  return this.request(`/reference-boards/${boardKey}/assets/${assetId}`, {
    method: "DELETE", body: JSON.stringify({ expectedRevision }),
  });
}
reorderBoardAssets(boardKey, assetIds, expectedRevision) {
  return this.request(`/reference-boards/${boardKey}/order`, {
    method: "POST", body: JSON.stringify({ expectedRevision, assetIds }),
  });
}
```

`ReferenceBoardAssets` must accept only multiple images, preserve selection order, expose pending/uploading/failed/ready states, render thumbnails with filename and order, support delete and up/down, and never append files to the primary screenshot input.

- [ ] **Step 4: Render “UE 三图准备” inside rules view**

UX and competitor cards include separate `<input type="file" multiple accept="image/*">`; planning is a read-only card showing representative count. Missing optional assets show `待补充`, not an error. Uploading/failed status disables rule confirmation and preview; an untouched empty card does not.

- [ ] **Step 5: Extend backend preview response and frontend preview**

In the existing preview builder/endpoint, return:

```python
"ruleDomainSummary": {
    key: {"count": len(domains[key]), "pendingCount": sum(bool(item.get("unknownReason")) for item in domains[key]), "emptyText": "本次素材未展示，待确认" if not domains[key] else ""}
    for key in RULE_DOMAIN_KEYS
},
"referenceBoardSummary": [
    {"key": "ux", "assetCount": len(boards["ux"]["assets"]), "status": boards["ux"]["status"]},
    {"key": "planning", "assetCount": len(native_board.images), "status": "generated"},
    {"key": "competitor", "assetCount": len(boards["competitor"]["assets"]), "status": boards["competitor"]["status"]},
],
```

`ExportPreview.render` shows all six counts/statuses and routes damaged rule IDs back to `rules` with the correct domain/ID selection.

- [ ] **Step 6: Run focused frontend/backend preview tests**

```powershell
node --test tests/js/reference-board-assets.test.js tests/js/export-preview.test.js tests/js/rule-domain-review.test.js
node --check js/reference-board-assets.js
node --check js/export-preview.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_reference_board_api.py tests/test_review_preview.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/review_preview.py js/reference-board-assets.js js/review-client.js js/rule-domain-review.js js/export-preview.js js/backend.js css/style.css tests/js/reference-board-assets.test.js tests/js/export-preview.test.js tests/test_review_preview.py
git commit -m "feat: prepare three GVE16 board sources"
```

---

### Task 6: Three required chapters and three native board render contracts

**Files:**
- Modify: `backend/feishu_native_board.py:1-320`
- Modify: `backend/feishu_render.py:1-365`
- Test: `tests/test_feishu_render.py`
- Test: `tests/test_gve16_native_whiteboard.py`
- Test: `tests/test_feishu_sample_aligned_board.py`

**Interfaces:**
- Consumes: Task 1 rule/reference model and existing `compile_gve16_whiteboard(job)` planning board.
- Produces dataclass `NamedWhiteboard(key: str, title: str, board: NativeWhiteboard)`; `compile_gve16_whiteboards(job) -> tuple[NamedWhiteboard, NamedWhiteboard, NamedWhiteboard]`; `RenderedFeishuDocument.native_boards` ordered `ux/planning/competitor` plus compatibility property `native_board` returning planning.

- [ ] **Step 1: Write RED rendering tests**

```python
def test_interaction_document_always_renders_latest_gve16_rule_chapters(confirmed_job, tmp_path):
    rendered = render_feishu_document(confirmed_job, tmp_path)
    for heading in ("9. 叙事", "11. 引导", "12. 红点提示"):
        assert f"<h1>{heading}</h1>" in rendered.xml
    assert rendered.xml.count("本次素材未展示，待确认") == 3
    assert [item.key for item in rendered.native_boards] == ["ux", "planning", "competitor"]
    assert rendered.xml.count("<whiteboard") == 3
```

Add populated narrative/guidance/red-dot assertions, nested step/path order, escaped user text, internal IDs hidden, UX/competitor asset isolation, empty optional board note, and planning board representative-only behavior.

- [ ] **Step 2: Run tests and verify RED**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_feishu_render.py tests/test_gve16_native_whiteboard.py tests/test_feishu_sample_aligned_board.py -q
```

Expected: FAIL because only one whiteboard and no three chapters exist.

- [ ] **Step 3: Compile reference boards without analysis leakage**

Add:

```python
@dataclass(frozen=True)
class NamedWhiteboard:
    key: str
    title: str
    board: NativeWhiteboard

def compile_reference_whiteboard(job: dict[str, Any], key: str, title: str) -> NativeWhiteboard:
    assets = ((job.get("reviewModel") or {}).get("referenceBoards") or {}).get(key, {}).get("assets") or []
    structure = {"nodes": [_section(f"section-{key}", title, 0, 560)]}
    images = []
    overlay_nodes = []
    if not assets:
        overlay_nodes.append(_note(f"note-{key}-pending", "待补充", 80, 140))
    for index, asset in enumerate(sorted(assets, key=lambda item: item["order"]), 1):
        node = {"id": f"image-{key}-{index}", "type": "image", "x": 80 + (index - 1) * 320, "y": 120, "width": 280, "height": 500}
        images.append(BoardImage(asset["id"], asset["relativePath"], node))
        overlay_nodes.append(_text_node(f"label-{key}-{index}", asset["sourceName"], node["x"], 640, 280))
    return NativeWhiteboard(structure, tuple(images), {"nodes": overlay_nodes})

def compile_gve16_whiteboards(job: dict[str, Any]) -> tuple[NamedWhiteboard, ...]:
    return (
        NamedWhiteboard("ux", "UX设计", compile_reference_whiteboard(job, "ux", "UX设计")),
        NamedWhiteboard("planning", "策划草图", compile_gve16_whiteboard(job)),
        NamedWhiteboard("competitor", "竞品参考", compile_reference_whiteboard(job, "competitor", "竞品参考")),
    )
```

Reference boards contain one real Section, ordered image nodes whose `image_path` comes only from `referenceBoards[key].assets`, and adjacent filenames. Empty boards contain a yellow `待补充` note and no images.

- [ ] **Step 4: Render rule chapters and ordered whiteboard blocks**

Create focused pure renderers:

```python
def _render_narrative(domains: dict[str, Any]) -> str:
    items = domains.get("narrative") or []
    return _PENDING_RULE_DOMAIN if not items else "".join(_render_narrative_item(item) for item in items)
def _render_guidance(domains: dict[str, Any], components: dict[str, dict[str, Any]]) -> str:
    items = domains.get("guidance") or []
    return _PENDING_RULE_DOMAIN if not items else "".join(_render_guidance_item(item, components) for item in items)
def _render_red_dots(domains: dict[str, Any], components: dict[str, dict[str, Any]]) -> str:
    items = domains.get("redDots") or []
    return _PENDING_RULE_DOMAIN if not items else "".join(_render_red_dot_item(item, components) for item in items)
```

Each empty renderer returns `<p>本次素材未展示，待确认</p>`. Populated guidance uses ordered `<ol>` steps; red dots show `显示条件`, `消去条件`, and `穿透路径` in order. Resolve component names for display and never emit stable IDs.

Replace the one whiteboard block with:

```python
parts.append("<h1>UE 流转图</h1>")
for named in native_boards:
    parts.extend([f"<h2>{escape(named.title)}</h2>", '<whiteboard type="raw"></whiteboard>'])
```

Keep a compatibility `native_board` property that returns the board whose key is `planning` so existing preview callers remain working until Task 7 completes.

- [ ] **Step 5: Run focused render/board tests**

Run Step 2 command. Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/feishu_native_board.py backend/feishu_render.py tests/test_feishu_render.py tests/test_gve16_native_whiteboard.py tests/test_feishu_sample_aligned_board.py
git commit -m "feat: render three latest GVE16 boards"
```

---

### Task 7: Resumable three-board Feishu publisher

**Files:**
- Modify: `backend/feishu_publish.py:1-295`
- Modify: `backend/server.py:114-200,421-475`
- Test: `tests/test_feishu_publish.py`
- Test: `tests/test_feishu_publish_api.py`
- Test: `tests/test_feishu_publish_contract.py`

**Interfaces:**
- Consumes: Task 6 `RenderedFeishuDocument.native_boards` and three ordered document tokens.
- Produces checkpoint maps `boardTokens`, `boardStructureRequestIds`, `boardMediaDone`, `boardVerified`; migrates legacy `boardToken`/flat media state to key `planning`.

- [ ] **Step 1: Write RED checkpoint and ordering tests**

```python
def test_publisher_writes_and_verifies_all_three_boards(fake_cli, confirmed_job, tmp_path):
    record = FeishuPublisher(fake_cli, tmp_path).publish(confirmed_job, request_id="req-3")
    saved = confirmed_job["feishuPublication"]
    assert list(saved["boardTokens"]) == ["ux", "planning", "competitor"]
    assert set(saved["boardVerified"]) == {"ux", "planning", "competitor"}
    assert all(saved["boardVerified"].values())

def test_partial_competitor_failure_resumes_without_rewriting_ux_or_planning(fake_cli, confirmed_job, tmp_path):
    fake_cli.fail_board_key_once = "competitor"
    publisher = FeishuPublisher(fake_cli, tmp_path)
    with pytest.raises(LarkCommandError):
        publisher.publish(confirmed_job, request_id="req-partial")
    first_structure_counts = fake_cli.structure_update_counts.copy()
    publisher.publish(confirmed_job, request_id="req-partial")
    assert fake_cli.document_create_count == 1
    assert fake_cli.structure_update_counts["ux"] == first_structure_counts["ux"]
    assert fake_cli.structure_update_counts["planning"] == first_structure_counts["planning"]
    assert fake_cli.structure_update_counts["competitor"] == first_structure_counts.get("competitor", 0) + 1
```

Test token-count mismatch, per-board image token maps, idempotent keys containing board key, empty-board verification, media isolation, old-record migration, and same-request retry.

- [ ] **Step 2: Run publisher tests and verify RED**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_feishu_publish.py tests/test_feishu_publish_contract.py -q
```

Expected: FAIL because publication uses only the first token and one flat board state.

- [ ] **Step 3: Add checkpoint migration and board loop**

Normalize once:

```python
def _board_checkpoint(record: dict[str, Any]) -> dict[str, Any]:
    tokens = dict(record.get("boardTokens") or {})
    if record.get("boardToken") and "planning" not in tokens:
        tokens["planning"] = record["boardToken"]
    return {
        "boardTokens": tokens,
        "boardStructureRequestIds": dict(record.get("boardStructureRequestIds") or {}),
        "boardMediaDone": dict(record.get("boardMediaDone") or {}),
        "boardVerified": dict(record.get("boardVerified") or {}),
    }
```

After document fetch, require exactly three whiteboard tokens and zip them with `rendered.native_boards` in document order. Persist the key/token map before any structure write.

For each named board:

1. Write structure once with `f"{request_id}-{key}-structure"`.
2. Upload only that board's images; store tokens under `boardMediaDone[key][image.frame_id]`.
3. Write overlays with `f"{request_id}-{key}-overlay"`.
4. Query raw and persist `boardVerified[key] = True`.

On retry, skip completed steps per key and never call document create when `documentToken` exists.

- [ ] **Step 4: Update public publication status safely**

Expose counts/statuses only:

```python
"boards": [
    {"key": key, "status": "verified" if verified.get(key) else "pending", "mediaCount": len(media.get(key) or {})}
    for key in ("ux", "planning", "competitor")
]
```

Do not return document tokens, board tokens, media tokens, absolute paths, CLI stdout, or credentials.

- [ ] **Step 5: Run publisher/API tests**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests/test_feishu_publish.py tests/test_feishu_publish_contract.py tests/test_feishu_publish_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/feishu_publish.py backend/server.py tests/test_feishu_publish.py tests/test_feishu_publish_contract.py tests/test_feishu_publish_api.py
git commit -m "feat: publish three GVE16 whiteboards"
```

---

### Task 8: End-to-end workflow, responsive QA, and completion records

**Files:**
- Modify: `backend/review_model.py`
- Modify: `backend/review_service.py`
- Modify: `backend/feishu_render.py`
- Modify: `backend/feishu_publish.py`
- Modify: `backend/server.py`
- Modify: `js/rule-domain-review.js`
- Modify: `js/reference-board-assets.js`
- Modify: `js/export-preview.js`
- Modify: `js/backend.js`
- Modify: `css/style.css`
- Modify: `index.html`
- Modify: `HANDOFF_NEXT_AGENT.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Test: `tests/test_review_workspace_ui_contract.py`
- Test: `tests/test_feishu_render.py`
- Test: `tests/test_feishu_publish.py`
- Test: `tests/js/*.test.js`

**Interfaces:**
- Consumes: Tasks 1-7 complete workflow.
- Produces: verified browser journey and durable handoff state; no new feature interface.

- [ ] **Step 1: Add one integration contract before manual QA**

Create or extend a test that builds a confirmed job, marks all rule domains reviewed, confirms them, adds one populated rule per domain, adds one UX and one competitor asset, creates preview, and runs fake publication. Assert:

```python
assert preview["exportReady"] is True
assert [board["key"] for board in preview["referenceBoardSummary"]] == ["ux", "planning", "competitor"]
assert rendered.xml.count("<whiteboard") == 3
assert publication.status == "published"
```

First run must fail if any cross-layer contract is incomplete; repair only the demonstrated gap and retain the test.

- [ ] **Step 2: Run full automated verification**

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
python -m pytest tests -q
node --test tests/js/*.test.js
python -m compileall backend
Get-ChildItem js -Filter *.js | ForEach-Object { node --check $_.FullName }
git diff --check
```

Expected: all Python and Node tests pass; compile/syntax/diff checks exit 0. Existing FastAPI/Starlette deprecation warnings may remain but no new warnings are accepted.

- [ ] **Step 3: Restart local service and run browser QA**

Use the existing `start.ps1`/project server path, then verify `/api/health` returns 200. In real Edge/Chromium, use a completed local interaction task and exercise:

1. Final stage confirmation routes to rules.
2. Visit all three tabs; empty copy is exact and does not create rules.
3. Add/edit/delete/reorder one narrative, two-step guidance, and three-level red-dot path.
4. Bind stage/component; verify filtered choices and damaged-reference feedback.
5. Upload two UX and two competitor images independently; reorder/delete; confirm primary frames/scenes are unchanged.
6. Refresh and reopen history; verify view, selected rule, values, order, assets, and confirmations recover.
7. Confirm rules; generate preview; verify six summaries and no blocker for empty optional assets.
8. Check desktop full-width and mobile 390px list/editor switching, 44px controls, keyboard navigation, focus visibility, no page horizontal overflow, and zero console errors.

Capture only local QA screenshots/logs under `artifacts/`; do not stage them.

- [ ] **Step 4: Run fake Feishu acceptance and optional authorized real dry run**

The automated fake-CLI test is mandatory. A real Feishu write requires the user's explicit publish action and current valid authorization. If authorized within the test task, publish one disposable test job and verify all three board previews/raw outputs; otherwise record real Feishu acceptance as pending without claiming it passed.

- [ ] **Step 5: Perform focused simplification and pain audit**

Use `ponytail-review` on the final diff. Delete duplicated routing/summary logic and avoid generic form abstractions with only one consumer. Then use `deep-user-pain-audit` on the actual workflow; fix immediate issues that prevent a planner from understanding, correcting, confirming, or exporting the rules. Re-run Step 2 after any fix.

- [ ] **Step 6: Update durable records**

Record exact test counts, browser viewport/results, service URL/port, real Feishu acceptance status, known warnings, and any residual risk in `progress.md`, `findings.md`, `task_plan.md`, and `HANDOFF_NEXT_AGENT.md`. Mark implementation complete only when all seven design completion criteria are evidenced.

- [ ] **Step 7: Final verification and commit**

Rerun Step 2 fresh and inspect `git status --short`. Then:

```powershell
git add backend js css index.html tests HANDOFF_NEXT_AGENT.md task_plan.md findings.md progress.md
git commit -m "test: verify latest GVE16 interaction workflow"
```

Do not add `artifacts/` or runtime job data.

---

## Plan Completion Checklist

- [ ] Task 1 model/defaults/validation/gate complete.
- [ ] Task 2 revisioned rule operations and confirmation complete.
- [ ] Task 3 optional asset persistence/API complete.
- [ ] Task 4 rule-domain review UI complete.
- [ ] Task 5 board asset UI and preview summaries complete.
- [ ] Task 6 three chapters and three native board renderers complete.
- [ ] Task 7 resumable three-board publisher complete.
- [ ] Task 8 automated/browser/Feishu acceptance and records complete.
