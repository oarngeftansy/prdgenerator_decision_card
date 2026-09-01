# GVE16 Review Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the frame-form reviewer with a staged, full-width GVE16 review workspace that confirms flow, transitions, stage small loops, draggable annotations, and export readiness before Feishu publication.

**Architecture:** A new backend `review_model` module owns the canonical editable GVE16 draft, explicit operations, revision control, confirmation invalidation, undo/redo, and export gates. The browser loads that model and renders three phase-one views—flow, stage, and export preview—through focused JavaScript modules rather than extending the legacy frame renderer. Confirmed review data is compiled back into the existing planning/document/whiteboard pipeline, so Feishu output retains the approved `TVnd...` and `ZNWk...` contracts.

**Tech Stack:** Python 3.11, FastAPI, vanilla HTML/CSS/JavaScript, Pillow/OpenCV evidence already persisted by the screenshot pipeline, pytest, Node built-in test runner, existing Feishu CLI/renderers.

## Global Constraints

- Screenshot folders remain the primary input; one auxiliary video remains optional and non-blocking.
- A task accepts 2–30 first-level JPG, JPEG, PNG, or WebP screenshots in user-confirmed order.
- Planner-confirmed screenshot order establishes the default stage sequence and transition relationship; trigger type still comes from visual analysis or human review, so adjacency alone never turns every transition into a click.
- Phase one uses a full-width staged workspace, a left-to-right stage lane, and screenshot/rule split stage review.
- FlowDoc controls review behavior only; GVE16 controls final planning content.
- The canonical review model is the only editable planning source; views must not copy domain data.
- A stage may use 1–3 representative state frames; the lane shows one cover frame.
- Click transitions may have normalized anchors inside bound component boxes; automatic transitions never have click anchors.
- Core unresolved flow fields block export; non-core unresolved details remain visible without blocking export.
- Human edits and confirmed values must not be overwritten by later AI analysis.
- Feishu receives confirmed representative frames only; the document contains no duplicate evidence/reference-frame image section.
- Keep the existing Feishu order: create document → read board token → write structure → upload representative media → add image nodes → preview validation → raw validation.
- Add no runtime dependency.
- Preserve existing video-only and legacy frame-review APIs for compatibility while the new workspace becomes the default for completed interaction jobs.

---

### Task 1: Canonical review-model contract and validation

**Files:**
- Create: `backend/review_model.py`
- Create: `tests/test_review_model.py`
- Create: `tests/review_fixtures.py`

**Interfaces:**
- Consumes: completed job dictionaries containing `metadata`, `frames`, `scenes`, and `componentTracks`.
- Produces: `build_review_model(job: dict) -> dict`, `validate_review_model(model: dict) -> list[str]`, `review_gate(model: dict) -> dict`, and constants `TRIGGER_TYPES`, `RESULT_TYPES`, `FRAME_ROLES`.

- [ ] **Step 1: Write failing contract and gate tests**

```python
from backend.review_model import build_review_model, review_gate, validate_review_model
from tests.review_fixtures import make_image_job


def test_review_model_uses_stable_entities_and_screenshot_sources():
    model = build_review_model(make_image_job())
    assert model["schemaVersion"] == "2.0"
    assert [stage["id"] for stage in model["stages"]] == ["STG-001", "STG-002"]
    assert model["stages"][0]["representativeFrames"][0] == {"frameId": "F0001", "role": "entry"}
    assert model["sources"]["F0001"]["sourceType"] == "image_sequence"
    assert validate_review_model(model) == []


def test_core_unknown_blocks_but_non_core_unknown_does_not():
    model = build_review_model(make_image_job())
    model["reviewState"]["flowConfirmed"] = True
    for stage in model["stages"]:
        stage["confirmation"]["confirmed"] = True
    for transition in model["transitions"]:
        transition["triggerType"] = "tap" if transition["targetStageId"] else "system_event"
        transition["resultType"] = "navigate" if transition["targetStageId"] else "terminal"
    model["crossStateConstraints"].append({"id": "CST-001", "text": "弱网反馈待确认", "severity": "non_core", "status": "unknown"})
    gate = review_gate(model)
    assert gate["exportReady"] is True
    assert gate["warnings"] == ["CST-001"]
    model["transitions"][0]["targetStageId"] = None
    model["transitions"][0]["resultType"] = "unknown"
    gate = review_gate(model)
    assert gate["exportReady"] is False
    assert "TRN-001" in gate["blockers"]
```

Create `tests/review_fixtures.py` so every later task uses defined fixtures rather than private test-file state:

```python
from copy import deepcopy


def make_image_job():
    return {
        "id": "job-1",
        "metadata": {"mode": "interaction", "inputType": "image_sequence", "projectName": "武器流程"},
        "frames": [
            {"id": "F0001", "sequenceIndex": 1, "sceneId": 0, "sourceName": "01.png", "imageUrl": "/artifacts/job-1/frames/F0001.jpg", "analysis": {"what": "选择武器", "userAction": "点击卡片", "systemResponse": "卡片选中", "afterState": "选择完成", "beforeState": "进入关卡", "evidenceLevel": "明确展示", "confidence": "高"}},
            {"id": "F0002", "sequenceIndex": 2, "sceneId": 1, "sourceName": "02.png", "imageUrl": "/artifacts/job-1/frames/F0002.jpg", "analysis": {"what": "进入战斗", "userAction": "系统自动开始", "systemResponse": "战斗开始", "afterState": "战斗中", "beforeState": "选择完成", "evidenceLevel": "合理推断", "confidence": "中"}},
        ],
        "scenes": [
            {"id": 0, "frameIds": ["F0001"], "analysis": {"title": "选择武器", "objective": "确认武器", "entryCondition": "进入关卡", "exitCondition": "选择完成"}},
            {"id": 1, "frameIds": ["F0002"], "analysis": {"title": "战斗", "objective": "完成战斗", "entryCondition": "选择完成", "exitCondition": "战斗结束"}},
        ],
        "componentTracks": [],
    }


def make_confirmed_job():
    from backend.review_model import build_review_model
    job = deepcopy(make_image_job())
    model = build_review_model(job)
    model["reviewState"].update({"status": "preview", "flowConfirmed": True, "confirmedStageIds": [stage["id"] for stage in model["stages"]], "previewRevision": model["revision"]})
    for stage in model["stages"]:
        stage["confirmation"] = {"confirmed": True, "revision": model["revision"]}
        stage["smallLoop"] = {"display": stage["name"], "trigger": "已确认触发", "feedback": "已确认反馈", "result": stage["exitCondition"], "retry": "待确认"}
    for transition in model["transitions"]:
        transition["triggerType"] = "tap" if transition["targetStageId"] else "system_event"
        transition["resultType"] = "navigate" if transition["targetStageId"] else "terminal"
        transition["confirmation"] = {"confirmed": True, "revision": model["revision"]}
    for index, stage in enumerate(model["stages"], 1):
        region_count = 2 if index == 1 else 1
        for _ in range(region_count):
            region_id = f"REG-{len(model['regions']) + 1:04d}"
            model["regions"].append({"id": region_id, "stageId": stage["id"], "frameId": stage["representativeFrames"][0]["frameId"], "name": f"区域 {len(model['regions']) + 1}", "bounds": {"x": 0.1, "y": 0.1 + len(model["regions"]) * 0.1, "width": 0.3, "height": 0.1}, "displayOrder": len(model["regions"]) + 1, "displayNumber": len(model["regions"]) + 1, "sourceType": "human", "primary": True, "rule": {"display": "已确认内容", "condition": "已确认条件", "action": "已确认操作", "feedback": "已确认反馈", "result": "已确认结果", "exception": "待确认"}, "confirmation": {"confirmed": True}})
            stage["regionIds"].append(region_id)
    job["reviewModel"] = model
    return job
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_model.py -q
```

Expected: FAIL during collection because `backend.review_model` does not exist.

- [ ] **Step 3: Implement the minimal canonical contract**

Create `backend/review_model.py` with these public values and shapes:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

TRIGGER_TYPES = {"tap", "long_press", "swipe", "drag", "animation_end", "media_end", "timeout", "condition_met", "system_event", "unknown"}
RESULT_TYPES = {"navigate", "state_change", "open_overlay", "close_overlay", "return", "loop", "terminal", "unknown"}
FRAME_ROLES = {"entry", "change", "result"}


def _stage(index: int, scene: dict[str, Any]) -> dict[str, Any]:
    analysis = scene.get("analysis") or {}
    frame_ids = list(scene.get("frameIds") or [])
    representatives = [{"frameId": frame_id, "role": ("entry" if pos == 0 else "result")} for pos, frame_id in enumerate(frame_ids[:3])]
    return {
        "id": f"STG-{index:03d}", "sourceSceneId": scene.get("id"), "order": index,
        "name": analysis.get("title") or f"环节 {index}", "objective": analysis.get("objective") or "未知待确认",
        "entryCondition": analysis.get("entryCondition") or "未知待确认", "exitCondition": analysis.get("exitCondition") or "未知待确认",
        "terminal": False, "representativeFrames": representatives, "regionIds": [], "transitionIds": [],
        "smallLoop": {"display": "未知待确认", "trigger": "未知待确认", "feedback": "未知待确认", "result": "未知待确认", "retry": "未知待确认"},
        "confirmation": {"confirmed": False, "revision": None}, "unknowns": [],
    }


def build_review_model(job: dict[str, Any]) -> dict[str, Any]:
    stages = [_stage(index, scene) for index, scene in enumerate(job.get("scenes") or [], 1)]
    stage_by_scene = {stage["sourceSceneId"]: stage for stage in stages}
    transitions = []
    frame_by_id = {frame["id"]: frame for frame in job.get("frames") or []}
    for stage_index, stage in enumerate(stages):
        frame = frame_by_id.get(stage["representativeFrames"][0]["frameId"]) if stage["representativeFrames"] else None
        if not frame:
            continue
        analysis = frame.get("analysis") or {}
        target = stages[stage_index + 1]["id"] if stage_index + 1 < len(stages) else None
        transition = {
            "id": f"TRN-{len(transitions) + 1:03d}", "sourceStageId": stage["id"], "targetStageId": target,
            "triggerType": "tap" if analysis.get("userAction") not in (None, "", "unknown", "未知待确认") else "unknown",
            "triggerLabel": analysis.get("userAction") or "未知待确认", "componentId": None, "sourceFrameId": frame["id"], "anchor": None,
            "condition": analysis.get("beforeState") or "未知待确认", "response": analysis.get("systemResponse") or "未知待确认",
            "resultType": ("navigate" if target else "terminal"), "resultState": analysis.get("afterState") or "未知待确认",
            "trueBranchTargetId": target, "falseBranchTargetId": None, "primary": True, "included": True,
            "sourceLevel": analysis.get("evidenceLevel") or "未知待确认", "confidence": analysis.get("confidence") or "低",
            "confirmation": {"confirmed": False, "revision": None},
        }
        transitions.append(transition)
        stage["transitionIds"].append(transition["id"])
    sources = {frame["id"]: {"sourceType": job.get("metadata", {}).get("inputType", "video"), "sourceName": frame.get("sourceName"), "sequenceIndex": frame.get("sequenceIndex"), "imageUrl": frame.get("imageUrl")} for frame in job.get("frames") or []}
    return {
        "schemaVersion": "2.0", "standard": "GVE16", "revision": 1, "jobId": job.get("id"),
        "sources": sources, "stages": stages, "transitions": transitions, "regions": [], "components": [],
        "componentStates": [], "crossStateConstraints": [],
        "reviewState": {"status": "ai_draft", "flowConfirmed": False, "confirmedStageIds": [], "previewRevision": None},
        "editHistory": {"undo": [], "redo": []},
    }


def validate_review_model(model: dict[str, Any]) -> list[str]:
    errors = []
    stage_ids = {item.get("id") for item in model.get("stages") or []}
    component_ids = {item.get("id") for item in model.get("components") or []}
    for item in model.get("transitions") or []:
        if item.get("sourceStageId") not in stage_ids:
            errors.append(f"{item.get('id')}: invalid sourceStageId")
        if item.get("targetStageId") and item["targetStageId"] not in stage_ids:
            errors.append(f"{item.get('id')}: invalid targetStageId")
        if item.get("triggerType") not in TRIGGER_TYPES:
            errors.append(f"{item.get('id')}: invalid triggerType")
        if item.get("resultType") not in RESULT_TYPES:
            errors.append(f"{item.get('id')}: invalid resultType")
        if item.get("componentId") and item["componentId"] not in component_ids:
            errors.append(f"{item.get('id')}: invalid componentId")
        if item.get("triggerType") not in {"tap", "long_press"} and item.get("anchor") is not None:
            errors.append(f"{item.get('id')}: automatic transition cannot have anchor")
    return errors


def review_gate(model: dict[str, Any]) -> dict[str, Any]:
    blockers, warnings = [], []
    if not model.get("reviewState", {}).get("flowConfirmed"):
        blockers.append("FLOW_NOT_CONFIRMED")
    for stage in model.get("stages") or []:
        if not stage.get("confirmation", {}).get("confirmed"):
            blockers.append(stage["id"])
    for transition in model.get("transitions") or []:
        if transition.get("included") and (transition.get("triggerType") == "unknown" or transition.get("resultType") == "unknown"):
            blockers.append(transition["id"])
    warnings.extend(item["id"] for item in model.get("crossStateConstraints") or [] if item.get("severity") == "non_core" and item.get("status") == "unknown")
    return {"exportReady": not blockers, "blockers": list(dict.fromkeys(blockers)), "warnings": warnings}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command.

Expected: 2 tests PASS.

- [ ] **Step 5: Commit the model boundary**

```powershell
git add backend/review_model.py tests/test_review_model.py tests/review_fixtures.py
git commit -m "feat: add GVE16 review model"
```

---

### Task 2: Seed stages, representative frames, candidate transitions, and regions

**Files:**
- Modify: `backend/review_model.py`
- Modify: `backend/server.py:180-189`
- Create: `tests/test_review_model_seed.py`
- Modify: `tests/test_image_sequence_api.py`

**Interfaces:**
- Consumes: Task 1 `build_review_model(job)` and paid visual-model output persisted at `analysis-complete`.
- Produces: `ensure_review_model(job: dict) -> dict` and quality summary fields `qualified`, `blockers`, `candidateTransitionCount`, `stageCount`.

- [ ] **Step 1: Write failing seeding and quality tests**

```python
from backend.review_model import ensure_review_model
from tests.review_fixtures import make_image_job


def test_seed_does_not_treat_sequence_order_as_proven_navigation():
    job = make_image_job()
    model = ensure_review_model(job)
    first = model["transitions"][0]
    assert first["sourceStageId"] == "STG-001"
    assert first["targetStageId"] == "STG-002"
    assert first["targetBasis"] == "sequence_candidate"
    assert first["confirmation"]["confirmed"] is False


def test_unqualified_analysis_stays_out_of_review_workspace():
    job = make_image_job()
    for frame in job["frames"]:
        frame["analysis"] = {"what": "未知待确认", "userAction": "未知待确认", "systemResponse": "未知待确认", "afterState": "未知待确认"}
    model = ensure_review_model(job)
    assert model["quality"]["qualified"] is False
    assert "NO_QUALIFIED_STAGE" in model["quality"]["blockers"]


def test_seed_reuses_detected_boxes_as_editable_regions():
    job = make_image_job()
    job["frames"][0]["structure"] = {"width": 1000, "height": 2000, "elements": [{"id": "E001", "class": "button", "bbox": [100, 300, 400, 500]}]}
    model = ensure_review_model(job)
    region = model["regions"][0]
    assert region["bounds"] == {"x": 0.1, "y": 0.15, "width": 0.3, "height": 0.1}
    assert region["sourceType"] == "model"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_model_seed.py tests/test_image_sequence_api.py -q
```

Expected: FAIL because `ensure_review_model`, `targetBasis`, normalized regions, and quality output do not exist.

- [ ] **Step 3: Implement deterministic seeding and integrate the processing checkpoint**

Add these helpers to `backend/review_model.py`:

```python
def _meaningful(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and text != "unknown" and "未知待确认" not in text


def _normalized_bounds(element: dict[str, Any], width: float, height: float) -> dict[str, float]:
    left, top, right, bottom = element.get("bbox") or [0, 0, 0, 0]
    return {"x": left / width, "y": top / height, "width": (right - left) / width, "height": (bottom - top) / height}


def ensure_review_model(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("reviewModel"):
        return job["reviewModel"]
    model = build_review_model(job)
    for transition in model["transitions"]:
        transition["targetBasis"] = "sequence_candidate"
    for frame in job.get("frames") or []:
        structure = frame.get("structure") or {}
        width, height = float(structure.get("width") or 1), float(structure.get("height") or 1)
        stage = next((item for item in model["stages"] if item.get("sourceSceneId") == frame.get("sceneId")), None)
        if not stage:
            continue
        analysis = frame.get("analysis") or {}
        if frame["id"] == stage.get("representativeFrames", [{}])[0].get("frameId"):
            stage["smallLoop"] = {"display": analysis.get("what") or "未知待确认", "trigger": analysis.get("userAction") or "未知待确认", "feedback": analysis.get("systemResponse") or "未知待确认", "result": analysis.get("afterState") or "未知待确认", "retry": "未知待确认"}
        for element in (structure.get("elements") or [])[:40]:
            region_id = f"REG-{len(model['regions']) + 1:04d}"
            model["regions"].append({"id": region_id, "stageId": stage["id"], "frameId": frame["id"], "name": element.get("class") or "区域", "bounds": _normalized_bounds(element, width, height), "displayOrder": len(stage["regionIds"]) + 1, "displayNumber": None, "sourceType": "model", "primary": False, "rule": {"display": "未知待确认", "condition": "未知待确认", "action": "未知待确认", "feedback": "未知待确认", "result": "未知待确认", "exception": "未知待确认"}, "confirmation": {"confirmed": False}})
            stage["regionIds"].append(region_id)
    qualified_stages = sum(1 for stage in model["stages"] if _meaningful(stage["name"]) and any(_meaningful(value) for value in stage["smallLoop"].values()))
    model["quality"] = {"qualified": qualified_stages > 0, "blockers": ([] if qualified_stages > 0 else ["NO_QUALIFIED_STAGE"]), "candidateTransitionCount": len(model["transitions"]), "stageCount": len(model["stages"])}
    job["reviewModel"] = model
    return model
```

Update `backend/server.py` after `analysis-complete` persistence and before `generate_plan(job)`:

```python
from .review_model import ensure_review_model

# inside _process
job["reviewModel"] = ensure_review_model(job)
if not job["reviewModel"]["quality"]["qualified"]:
    raise RuntimeError("视觉模型未产出合格的 GVE16 审核草稿，请重新分析后再进入人工审核。")
```

- [ ] **Step 4: Run tests and verify GREEN**

Run the Step 2 command.

Expected: all focused tests PASS.

- [ ] **Step 5: Commit the seeded draft**

```powershell
git add backend/review_model.py backend/server.py tests/test_review_model_seed.py tests/test_image_sequence_api.py
git commit -m "feat: seed GVE16 review drafts"
```

---

### Task 3: Revisioned review operations, confirmation invalidation, and undo/redo API

**Files:**
- Create: `backend/review_service.py`
- Modify: `backend/server.py:449-479`
- Create: `tests/test_review_service.py`
- Create: `tests/test_review_api.py`

**Interfaces:**
- Consumes: Task 2 `job["reviewModel"]`.
- Produces: `apply_operations(model, operations, expected_revision)`, `undo(model, expected_revision)`, `redo(model, expected_revision)`, `confirm_flow(model)`, `confirm_stage(model, stage_id)`, and REST endpoints under `/api/jobs/{job_id}/review-model`.

- [ ] **Step 1: Write failing operation and API tests**

```python
from fastapi.testclient import TestClient

from backend import server
from backend.review_service import ReviewConflict, apply_operations, confirm_flow, undo
from backend.review_model import build_review_model
from tests.review_fixtures import make_image_job


def review_model():
    return build_review_model(make_image_job())


def test_stage_edit_invalidates_only_that_stage_and_preview():
    model = review_model()
    model["reviewState"].update({"flowConfirmed": True, "confirmedStageIds": ["STG-001", "STG-002"], "previewRevision": model["revision"]})
    for stage in model["stages"]:
        stage["confirmation"]["confirmed"] = True
    changed = apply_operations(model, [{"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "武器选择"}], model["revision"])
    assert changed["reviewState"]["flowConfirmed"] is True
    assert changed["reviewState"]["confirmedStageIds"] == ["STG-002"]
    assert changed["reviewState"]["previewRevision"] is None
    assert len(changed["editHistory"]["undo"]) == 1
    restored = undo(changed, changed["revision"])
    assert restored["stages"][0]["name"] != "武器选择"


def test_flow_edit_invalidates_all_downstream_confirmation():
    model = review_model()
    model["reviewState"].update({"flowConfirmed": True, "confirmedStageIds": ["STG-001"], "previewRevision": 1})
    changed = apply_operations(model, [{"type": "move_stage", "id": "STG-002", "toIndex": 0}], model["revision"])
    assert changed["reviewState"] == {"status": "flow_review", "flowConfirmed": False, "confirmedStageIds": [], "previewRevision": None}


def test_stale_revision_is_rejected():
    model = review_model()
    try:
        apply_operations(model, [], model["revision"] - 1)
    except ReviewConflict as exc:
        assert exc.current_revision == model["revision"]
    else:
        raise AssertionError("expected ReviewConflict")
```

API coverage must additionally assert:

```python
def test_review_operation_api_rejects_stale_revision(monkeypatch):
    job = make_image_job()
    job["reviewModel"] = build_review_model(job)
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server, "save_job", lambda value: store.__setitem__(value["id"], value))
    client = TestClient(server.app)
    response = client.post(f"/api/jobs/{job['id']}/review-model/operations", json={"expectedRevision": 1, "operations": [{"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "选择武器"}]})
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert client.post(f"/api/jobs/{job['id']}/review-model/operations", json={"expectedRevision": 1, "operations": []}).status_code == 409
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_service.py tests/test_review_api.py -q
```

Expected: FAIL because `backend.review_service` and the review-model endpoints do not exist.

- [ ] **Step 3: Implement explicit operations and focused endpoints**

Create `backend/review_service.py` with this public surface:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass
class ReviewConflict(Exception):
    current_revision: int


def _snapshot(model: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in model.items() if key != "editHistory"}


def _entity(model: dict[str, Any], kind: str, entity_id: str) -> dict[str, Any]:
    collection = {"stage": "stages", "transition": "transitions", "region": "regions", "component": "components", "constraint": "crossStateConstraints"}[kind]
    return next(item for item in model[collection] if item["id"] == entity_id)


def apply_operations(model: dict[str, Any], operations: list[dict[str, Any]], expected_revision: int) -> dict[str, Any]:
    if expected_revision != model["revision"]:
        raise ReviewConflict(model["revision"])
    result = deepcopy(model)
    before = _snapshot(result)
    flow_changed, changed_stage_ids = False, set()
    for operation in operations:
        if operation["type"] == "set":
            target = _entity(result, operation["entity"], operation["id"])
            target[operation["field"]] = deepcopy(operation["value"])
            flow_changed = flow_changed or operation["entity"] in {"transition", "constraint"}
            if operation["entity"] in {"stage", "region", "component"}:
                changed_stage_ids.add(target.get("stageId") or target.get("id"))
        elif operation["type"] == "move_stage":
            stages = result["stages"]
            index = next(index for index, stage in enumerate(stages) if stage["id"] == operation["id"])
            stage = stages.pop(index)
            stages.insert(max(0, min(operation["toIndex"], len(stages))), stage)
            for order, item in enumerate(stages, 1):
                item["order"] = order
            flow_changed = True
        else:
            raise ValueError(f"unsupported review operation: {operation['type']}")
    state = result["reviewState"]
    state["previewRevision"] = None
    if flow_changed:
        state.update(status="flow_review", flowConfirmed=False, confirmedStageIds=[])
        for stage in result["stages"]:
            stage["confirmation"] = {"confirmed": False, "revision": None}
    else:
        state["confirmedStageIds"] = [stage_id for stage_id in state.get("confirmedStageIds", []) if stage_id not in changed_stage_ids]
        for stage in result["stages"]:
            if stage["id"] in changed_stage_ids:
                stage["confirmation"] = {"confirmed": False, "revision": None}
    history = result.setdefault("editHistory", {"undo": [], "redo": []})
    history["undo"] = (history.get("undo", []) + [before])[-50:]
    history["redo"] = []
    result["revision"] += 1
    return result


def undo(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    if expected_revision != model["revision"]:
        raise ReviewConflict(model["revision"])
    result = deepcopy(model)
    before = result["editHistory"]["undo"].pop()
    current = _snapshot(result)
    history = result["editHistory"]
    history["redo"] = (history.get("redo", []) + [current])[-50:]
    result.update(deepcopy(before))
    result["editHistory"] = history
    result["revision"] = model["revision"] + 1
    return result


def redo(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    if expected_revision != model["revision"]:
        raise ReviewConflict(model["revision"])
    result = deepcopy(model)
    after = result["editHistory"]["redo"].pop()
    current = _snapshot(result)
    history = result["editHistory"]
    history["undo"] = (history.get("undo", []) + [current])[-50:]
    result.update(deepcopy(after))
    result["editHistory"] = history
    result["revision"] = model["revision"] + 1
    return result


def confirm_flow(model: dict[str, Any]) -> dict[str, Any]:
    invalid = [item["id"] for item in model["transitions"] if item.get("included") and (item.get("triggerType") == "unknown" or item.get("resultType") == "unknown")]
    if invalid:
        raise ValueError("无法确认完整流程：" + "、".join(invalid))
    result = deepcopy(model)
    result["revision"] += 1
    result["reviewState"].update(status="stage_review", flowConfirmed=True, confirmedStageIds=[], previewRevision=None)
    return result


def confirm_stage(model: dict[str, Any], stage_id: str) -> dict[str, Any]:
    result = deepcopy(model)
    stage = _entity(result, "stage", stage_id)
    if not 1 <= len(stage.get("representativeFrames") or []) <= 3:
        raise ValueError(f"{stage_id}: representative frames must contain 1-3 items")
    result["revision"] += 1
    stage["confirmation"] = {"confirmed": True, "revision": result["revision"]}
    state = result["reviewState"]
    state["confirmedStageIds"] = list(dict.fromkeys([*state.get("confirmedStageIds", []), stage_id]))
    state["status"] = "preview_ready" if len(state["confirmedStageIds"]) == len(result["stages"]) else "stage_review"
    state["previewRevision"] = None
    return result
```

Add `confirm_flow` and `confirm_stage` that validate required fields through `review_gate` subsets, set confirmation revisions, and clear `previewRevision`. Add GET, operations, undo, redo, confirm-flow, and confirm-stage endpoints in `backend/server.py`. Every mutating endpoint must reject archived jobs, convert `ReviewConflict` to HTTP 409 with `currentRevision`, save the job, and return `_public_job(job)["reviewModel"]`.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Step 2 command.

Expected: all review service and API tests PASS.

- [ ] **Step 5: Commit the review API**

```powershell
git add backend/review_service.py backend/server.py tests/test_review_service.py tests/test_review_api.py
git commit -m "feat: add revisioned review API"
```

---

### Task 4: Browser review client, selection model, and full-width workspace shell

**Files:**
- Create: `js/review-client.js`
- Create: `js/review-workspace.js`
- Create: `tests/js/review-workspace.test.js`
- Modify: `js/state.js`
- Modify: `js/backend.js:323-374`
- Modify: `index.html:158-197`
- Create: `css/review-workspace.css`
- Modify: `tests/test_screenshot_input_ui_contract.py`

**Interfaces:**
- Consumes: Task 3 review-model REST endpoints and completed backend jobs.
- Produces: `ReviewClient`, `ReviewWorkspace.initialState()`, `ReviewWorkspace.select()`, `ReviewWorkspace.routeForModel()`, `ReviewWorkspace.routeForJob()`, and DOM roots `#reviewWorkspace`, `#flowReviewView`, `#stageReviewView`, `#exportPreviewView`.

- [ ] **Step 1: Write failing pure-state and DOM contract tests**

```js
const test = require("node:test");
const assert = require("node:assert/strict");
const ReviewWorkspace = require("../../js/review-workspace.js");

test("completed interaction jobs enter full-flow review", () => {
  const state = ReviewWorkspace.initialState({ reviewState: { status: "ai_draft" }, stages: [{ id: "STG-001" }] });
  assert.equal(state.view, "flow");
  assert.equal(state.selectedStageId, "STG-001");
});

test("selection is one shared object across frame marker list and form", () => {
  const state = ReviewWorkspace.initialState({ reviewState: {}, stages: [{ id: "STG-001" }] });
  const selected = ReviewWorkspace.select(state, { type: "region", id: "REG-0002", stageId: "STG-001", frameId: "F0001" });
  assert.deepEqual(selected.selection, { type: "region", id: "REG-0002", stageId: "STG-001", frameId: "F0001" });
});
```

Extend the Python UI contract with:

```python
assert 'id="reviewWorkspace"' in html
assert 'id="flowReviewView"' in html
assert 'id="stageReviewView"' in html
assert 'id="exportPreviewView"' in html
assert "review-workspace.css" in html
assert "review-client.js" in html and "review-workspace.js" in html
assert ".workspace.has-review" in css
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
node --test tests/js/review-workspace.test.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_screenshot_input_ui_contract.py -q
```

Expected: FAIL because the modules and DOM roots do not exist.

- [ ] **Step 3: Implement the client and workspace shell**

`js/review-client.js` must export and expose in the browser:

```js
class ReviewClient {
  constructor(baseUrl, jobId) { this.baseUrl = baseUrl; this.jobId = jobId; }
  async request(path = "", options = {}) {
    const response = await fetch(`${this.baseUrl}/api/jobs/${this.jobId}/review-model${path}`, options);
    const body = await response.json();
    if (!response.ok) { const error = new Error(body.detail?.message || body.detail || "审核数据保存失败"); error.status = response.status; error.currentRevision = body.detail?.currentRevision; throw error; }
    return body;
  }
  load() { return this.request(); }
  operations(expectedRevision, operations) { return this.request("/operations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, operations }) }); }
  undo(expectedRevision) { return this.request("/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  redo(expectedRevision) { return this.request("/redo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
}
if (typeof module !== "undefined") module.exports = ReviewClient;
else window.ReviewClient = ReviewClient;
```

`js/review-workspace.js` must keep domain selection separate from the model:

```js
function initialState(model) {
  return { model, view: "flow", selectedStageId: model.stages?.[0]?.id || null, selectedTransitionId: null, selectedFrameId: null, selection: null, saveStatus: "saved", projectDrawerOpen: false };
}
function select(state, selection) { return { ...state, selection, selectedStageId: selection.stageId || state.selectedStageId, selectedFrameId: selection.frameId || state.selectedFrameId }; }
function routeForModel(model) { return model.quality?.qualified === false ? "analysis_failed" : model.reviewState?.previewRevision ? "preview" : model.reviewState?.flowConfirmed ? "stage" : "flow"; }
function routeForJob(job) { return job?.status === "completed" && job?.reviewModel ? "review_workspace" : "legacy_frames"; }
const api = { initialState, select, routeForModel, routeForJob };
if (typeof module !== "undefined") module.exports = api; else window.ReviewWorkspace = api;
```

Add a three-step top navigation, project drawer, three view roots, persistent save status, and undo/redo controls to `index.html`. Add `state.reviewWorkspace = null` and `state.reviewClient = null`. Update `syncBackendResult(job)` so completed interaction jobs with `reviewModel` add `.has-review`, initialize the client/state, and render the workspace instead of the legacy frame form. Preserve legacy rendering for old jobs without `reviewModel`.

Create `css/review-workspace.css` with a full-width grid, fixed step header, hidden inactive views, internal overflow only, 44px controls, focus-visible rules, and a `max-width: 700px` breakpoint that converts split review to tabs.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Step 2 commands plus:

```powershell
node --check js/review-client.js
node --check js/review-workspace.js
```

Expected: all focused tests and syntax checks PASS.

- [ ] **Step 5: Commit the shell**

```powershell
git add js/review-client.js js/review-workspace.js js/state.js js/backend.js index.html css/review-workspace.css tests/js/review-workspace.test.js tests/test_screenshot_input_ui_contract.py
git commit -m "feat: add staged review workspace shell"
```

---

### Task 5: Candidate-transition selection, detail review, anchors, and stage lane

**Files:**
- Create: `js/flow-review.js`
- Create: `tests/js/flow-review.test.js`
- Modify: `js/review-workspace.js`
- Modify: `js/app.js`
- Modify: `css/review-workspace.css`
- Modify: `backend/review_service.py`
- Modify: `tests/test_review_service.py`

**Interfaces:**
- Consumes: `reviewModel.transitions`, `reviewModel.stages`, `reviewModel.crossStateConstraints`, `ReviewClient.operations`, and shared workspace selection.
- Produces: `FlowReview.groupCandidates`, `FlowReview.visibleLane`, `FlowReview.anchorFromPointer`, `FlowReview.render`, and backend operations `set_transition_included`, `upsert_transition`, `delete_transition`, `merge_stages`, `set_anchor`, `upsert_constraint`, `delete_constraint`.

- [ ] **Step 1: Write failing flow selectors and geometry tests**

```js
const test = require("node:test");
const assert = require("node:assert/strict");
const FlowReview = require("../../js/flow-review.js");

test("candidate transitions group by source and retain automatic triggers", () => {
  const groups = FlowReview.groupCandidates([
    { id: "TRN-001", sourceStageId: "STG-001", triggerType: "tap", included: true },
    { id: "TRN-002", sourceStageId: "STG-001", triggerType: "animation_end", included: false },
  ]);
  assert.deepEqual(groups.map((group) => [group.stageId, group.items.length]), [["STG-001", 2]]);
});

test("click anchor clamps inside the normalized component box", () => {
  const anchor = FlowReview.anchorFromPointer({ x: 900, y: 50 }, { left: 0, top: 0, width: 1000, height: 2000 }, { x: 0.1, y: 0.2, width: 0.4, height: 0.3 });
  assert.deepEqual(anchor, { x: 0.5, y: 0.2 });
});

test("automatic transitions never render an anchor editor", () => {
  assert.equal(FlowReview.canEditAnchor({ triggerType: "animation_end" }), false);
  assert.equal(FlowReview.canEditAnchor({ triggerType: "tap", componentId: "CMP-001" }), true);
});
```

Add these Python operation tests:

```python
def test_transition_include_merge_and_anchor_rules():
    model = review_model()
    excluded = apply_operations(model, [{"type": "set_transition_included", "id": "TRN-001", "included": False}], model["revision"])
    assert next(item for item in excluded["transitions"] if item["id"] == "TRN-001")["included"] is False
    merged = apply_operations(model, [{"type": "merge_stages", "keepId": "STG-001", "mergeId": "STG-002"}], model["revision"])
    assert [stage["id"] for stage in merged["stages"]] == ["STG-001"]
    assert all(item.get("targetStageId") != "STG-002" for item in merged["transitions"])
    model["transitions"][0]["triggerType"] = "animation_end"
    try:
        apply_operations(model, [{"type": "set_anchor", "id": "TRN-001", "anchor": {"x": 0.2, "y": 0.3}}], model["revision"])
    except ValueError as exc:
        assert "anchor" in str(exc)
    else:
        raise AssertionError("expected automatic-transition anchor rejection")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
node --test tests/js/flow-review.test.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_service.py -q
```

Expected: FAIL because flow helpers and operations do not exist.

- [ ] **Step 3: Implement flow review and explicit transition operations**

Create `js/flow-review.js` with pure helpers:

```js
function groupCandidates(transitions) {
  const groups = new Map();
  for (const item of transitions || []) { if (!groups.has(item.sourceStageId)) groups.set(item.sourceStageId, []); groups.get(item.sourceStageId).push(item); }
  return Array.from(groups, ([stageId, items]) => ({ stageId, items }));
}
function visibleLane(model) { return [...(model.stages || [])].sort((a, b) => a.order - b.order).map((stage) => ({ ...stage, transitions: (model.transitions || []).filter((item) => item.included && item.sourceStageId === stage.id) })); }
function canEditAnchor(transition) { return ["tap", "long_press"].includes(transition.triggerType) && Boolean(transition.componentId); }
function anchorFromPointer(pointer, imageRect, bounds) {
  const rawX = (pointer.x - imageRect.left) / imageRect.width;
  const rawY = (pointer.y - imageRect.top) / imageRect.height;
  return { x: Math.max(bounds.x, Math.min(bounds.x + bounds.width, rawX)), y: Math.max(bounds.y, Math.min(bounds.y + bounds.height, rawY)) };
}
if (typeof module !== "undefined") module.exports = { groupCandidates, visibleLane, canEditAnchor, anchorFromPointer };
```

Implement `render(workspaceState)` in the browser branch to show candidate groups with include checkboxes, select-all/none, source→target, trigger chip, confidence, add/delete actions, and per-transition detail navigation. The lane uses stage cards, arrow labels, folded branches, drag sorting plus up/down buttons. Pointer movement for click anchors sends a `set_anchor` operation only on pointer-up. A separate cross-state constraint panel edits text, `core/non_core` severity, and `observed/inferred/unknown` status; these records later become yellow UE-board notes.

Extend `apply_operations` with explicit handlers. `set_anchor` must verify tap/long-press, resolve the bound component/region, clamp coordinates to its bounds, and invalidate flow confirmation. `merge_stages` must move frames/regions to the retained stage, rewrite every transition reference, remove the merged stage, and preserve candidate IDs.

- [ ] **Step 4: Run tests and verify GREEN**

Run Step 2 plus `node --check js/flow-review.js`.

Expected: all focused tests PASS.

- [ ] **Step 5: Commit flow review**

```powershell
git add js/flow-review.js js/review-workspace.js js/app.js css/review-workspace.css backend/review_service.py tests/js/flow-review.test.js tests/test_review_service.py
git commit -m "feat: review GVE16 flow transitions"
```

---

### Task 6: Stage small loops, representative frames, draggable boxes, and synchronized numbering

**Files:**
- Create: `js/stage-review.js`
- Create: `tests/js/stage-review.test.js`
- Modify: `js/review-workspace.js`
- Modify: `js/app.js`
- Modify: `css/review-workspace.css`
- Modify: `backend/review_service.py`
- Modify: `backend/review_model.py`
- Modify: `tests/test_review_service.py`

**Interfaces:**
- Consumes: stage, source, region, component, and component-state collections plus Task 3 operation API.
- Produces: `StageReview.clampBounds`, `StageReview.resizeBounds`, `StageReview.renumberRegions`, `StageReview.representativeFrames`, `StageReview.missingStateSlots`, `StageReview.render`, and backend operations `upsert_region`, `delete_region`, `set_region_bounds`, `reorder_region`, `set_representative_frames`, `set_small_loop`, `set_component_state`.

- [ ] **Step 1: Write failing box, numbering, and representative-frame tests**

```js
const test = require("node:test");
const assert = require("node:assert/strict");
const StageReview = require("../../js/stage-review.js");

test("moving and resizing boxes stays normalized and inside the screenshot", () => {
  assert.deepEqual(StageReview.clampBounds({ x: -0.2, y: 0.8, width: 0.5, height: 0.4 }), { x: 0, y: 0.6, width: 0.5, height: 0.4 });
  assert.deepEqual(StageReview.resizeBounds({ x: 0.2, y: 0.2, width: 0.3, height: 0.3 }, "se", { dx: 0.8, dy: 0.8 }), { x: 0.2, y: 0.2, width: 0.8, height: 0.8 });
});

test("display numbers change while stable ids remain", () => {
  const result = StageReview.renumberRegions([{ id: "REG-B", displayOrder: 2 }, { id: "REG-A", displayOrder: 1 }]);
  assert.deepEqual(result.map((item) => [item.id, item.displayNumber]), [["REG-A", 1], ["REG-B", 2]]);
});

test("one to three representative frames preserve explicit roles", () => {
  const selected = StageReview.representativeFrames([{ frameId: "F1", role: "entry" }, { frameId: "F2", role: "change" }, { frameId: "F3", role: "result" }]);
  assert.equal(selected.valid, true);
  assert.equal(StageReview.representativeFrames([]).valid, false);
  assert.equal(StageReview.representativeFrames([...selected.frames, { frameId: "F4", role: "result" }]).valid, false);
});

test("phase-one rules retain every GVE16 component state slot", () => {
  assert.deepEqual(StageReview.missingStateSlots({ default: "显示" }), ["pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet"]);
});
```

Add these backend cases to `tests/test_review_service.py`:

```python
def test_region_reference_conflict_and_stage_confirmation_requirements():
    model = review_model()
    model["regions"] = [{"id": "REG-0001", "stageId": "STG-001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
    model["transitions"][0]["componentId"] = "REG-0001"
    try:
        apply_operations(model, [{"type": "delete_region", "id": "REG-0001"}], model["revision"])
    except ValueError as exc:
        assert "TRN-001" in str(exc)
    else:
        raise AssertionError("expected referenced-region rejection")
    model["stages"][0]["representativeFrames"] = []
    try:
        confirm_stage(model, "STG-001")
    except ValueError as exc:
        assert "representative" in str(exc)
    else:
        raise AssertionError("expected representative-frame rejection")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
node --test tests/js/stage-review.test.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_service.py -q
```

Expected: FAIL because stage helpers and operations do not exist.

- [ ] **Step 3: Implement stage review and normalized geometry**

Create `js/stage-review.js` with these pure functions:

```js
const MIN_SIZE = 0.02;
const COMPONENT_STATE_KEYS = ["default", "pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet"];
function clampBounds(value) {
  const width = Math.max(MIN_SIZE, Math.min(1, Number(value.width)));
  const height = Math.max(MIN_SIZE, Math.min(1, Number(value.height)));
  return { x: Math.max(0, Math.min(1 - width, Number(value.x))), y: Math.max(0, Math.min(1 - height, Number(value.y))), width, height };
}
function resizeBounds(start, handle, delta) {
  const next = { ...start };
  if (handle.includes("e")) next.width += delta.dx;
  if (handle.includes("s")) next.height += delta.dy;
  if (handle.includes("w")) { next.x += delta.dx; next.width -= delta.dx; }
  if (handle.includes("n")) { next.y += delta.dy; next.height -= delta.dy; }
  return clampBounds(next);
}
function renumberRegions(regions) { return [...regions].sort((a, b) => a.displayOrder - b.displayOrder).map((item, index) => ({ ...item, displayNumber: index + 1 })); }
function representativeFrames(frames) { const copy = (frames || []).slice(0, 4); return { valid: copy.length >= 1 && copy.length <= 3 && copy.every((item) => ["entry", "change", "result"].includes(item.role)), frames: copy }; }
function missingStateSlots(states = {}) { return COMPONENT_STATE_KEYS.filter((key) => !Object.prototype.hasOwnProperty.call(states, key)); }
if (typeof module !== "undefined") module.exports = { clampBounds, resizeBounds, renumberRegions, representativeFrames, missingStateSlots };
```

The browser renderer must provide stage/frame navigation, representative-role controls, show-all screenshots without changing selection, image overlay boxes, red numbered markers, region chips, the current rule form, and a compact component-state section containing all nine slots. Box body drag moves; eight handles resize; empty-image drag creates; pointer-up sends one operation. Clicking a box, marker, chip, list item, or rule uses the shared selection object. Up/down controls provide non-drag ordering. Unseen component states remain explicit `unknown` values instead of disappearing.

Extend backend operations with server-side clamping, stable ID generation, reference conflict errors, region ordering, representative-frame validation, and small-loop field updates. `confirm_stage` must require 1–3 valid representatives and meaningful `display`, `trigger`, `feedback`, and `result` fields; `retry` may remain non-core unknown.

- [ ] **Step 4: Run tests and verify GREEN**

Run Step 2 plus `node --check js/stage-review.js`.

Expected: all focused tests PASS.

- [ ] **Step 5: Commit stage review**

```powershell
git add js/stage-review.js js/review-workspace.js js/app.js css/review-workspace.css backend/review_service.py backend/review_model.py tests/js/stage-review.test.js tests/test_review_service.py
git commit -m "feat: review GVE16 stage details"
```

---

### Task 7: Autosave states, conflicts, human-value protection, and history restoration

**Files:**
- Modify: `js/review-client.js`
- Modify: `js/review-workspace.js`
- Modify: `js/backend.js`
- Modify: `js/app.js`
- Create: `tests/js/review-persistence.test.js`
- Modify: `backend/review_service.py`
- Modify: `backend/server.py`
- Create: `tests/test_review_persistence.py`

**Interfaces:**
- Consumes: Task 3 revisioned operations and Task 4 workspace state.
- Produces: `createOperationQueue(options)`, `restoreUiState(model, saved)`, backend `sanitize_review_ui_state(model, saved)`, save-state rendering, conflict reload, persisted `reviewUiState`, and AI suggestions separate from human values.

- [ ] **Step 1: Write failing save, conflict, and restore tests**

```js
test("operation queue exposes saving saved and failed without losing edits", async () => {
  const statuses = [];
  const queue = createOperationQueue({
    send: async (revision, operations) => ({ revision: revision + 1, operations }),
    onStatus: (status) => statuses.push(status),
  });
  await queue.flush(4, [{ type: "set", entity: "stage", id: "STG-001", field: "name", value: "选择武器" }]);
  assert.deepEqual(statuses, ["saving", "saved"]);
});

test("restore uses server view and selection only when referenced ids still exist", () => {
  const restored = restoreUiState(model, { view: "stage", selectedStageId: "STG-002", selection: { type: "region", id: "REG-MISSING" } });
  assert.equal(restored.view, "stage");
  assert.equal(restored.selectedStageId, "STG-002");
  assert.equal(restored.selection, null);
});
```

Add these Python cases:

```python
def test_ui_state_and_suggestions_preserve_human_values(monkeypatch):
    job = make_image_job()
    job["reviewModel"] = build_review_model(job)
    stage = job["reviewModel"]["stages"][0]
    stage["name"] = "人工名称"
    stage["humanEditedFields"] = ["name"]
    stage["suggestions"] = {"name": "模型新名称"}
    job["reviewUiState"] = {"view": "stage", "selectedStageId": stage["id"], "selection": {"type": "region", "id": "missing"}}
    restored = sanitize_review_ui_state(job["reviewModel"], job["reviewUiState"])
    assert restored["view"] == "stage"
    assert restored["selection"] is None
    assert stage["name"] == "人工名称"
    assert stage["suggestions"]["name"] == "模型新名称"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
node --test tests/js/review-persistence.test.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_persistence.py -q
```

Expected: FAIL because the operation queue, UI-state persistence, and model-level suggestions do not exist.

- [ ] **Step 3: Implement durable save behavior and conflict recovery**

Add a 300ms debounced queue to `review-client.js`; drag/resize pointer-up bypasses debounce and flushes immediately. The queue keeps unsent operations after network failure, reports `saving/saved/failed/conflict`, and on 409 loads the current model before asking the user to choose server or local values for conflicting fields.

Use these public helpers:

```js
function createOperationQueue({ send, onStatus }) {
  let pending = [];
  return {
    push(operation) { pending.push(operation); },
    async flush(revision, operations = pending.splice(0)) {
      onStatus("saving");
      try { const result = await send(revision, operations); onStatus("saved"); return result; }
      catch (error) { pending = [...operations, ...pending]; onStatus(error.status === 409 ? "conflict" : "failed"); throw error; }
    },
    pending() { return [...pending]; },
  };
}
function restoreUiState(model, saved = {}) {
  const stageIds = new Set((model.stages || []).map((item) => item.id));
  const entityIds = new Set([...(model.regions || []), ...(model.components || []), ...(model.transitions || [])].map((item) => item.id));
  return { view: ["flow", "stage", "preview"].includes(saved.view) ? saved.view : "flow", selectedStageId: stageIds.has(saved.selectedStageId) ? saved.selectedStageId : model.stages?.[0]?.id || null, selection: saved.selection && entityIds.has(saved.selection.id) ? saved.selection : null, projectDrawerOpen: Boolean(saved.projectDrawerOpen) };
}
```

Persist this UI-only shape through `POST /review-model/ui-state`:

```json
{"view":"flow","selectedStageId":"STG-001","selectedTransitionId":null,"selectedFrameId":"F0001","selection":{"type":"region","id":"REG-0001"},"projectDrawerOpen":false}
```

Backend validation must discard selection IDs that do not exist, while preserving the requested view and valid stage. Add `humanEditedFields` and `suggestions` per entity. Reanalysis writes suggestions; accepting a suggestion becomes a normal `set` operation and records the field as human-edited. Returning to a task calls `ReviewClient.load()` and restores valid UI state.

Add this backend sanitizer to `backend/review_service.py`:

```python
def sanitize_review_ui_state(model: dict[str, Any], saved: dict[str, Any] | None) -> dict[str, Any]:
    value = saved or {}
    stage_order = [item["id"] for item in model.get("stages") or []]
    stage_ids = set(stage_order)
    entity_ids = {item["id"] for key in ("regions", "components", "transitions") for item in model.get(key) or []}
    selection = value.get("selection")
    return {
        "view": value.get("view") if value.get("view") in {"flow", "stage", "preview"} else "flow",
        "selectedStageId": value.get("selectedStageId") if value.get("selectedStageId") in stage_ids else (stage_order[0] if stage_order else None),
        "selectedTransitionId": value.get("selectedTransitionId") if value.get("selectedTransitionId") in entity_ids else None,
        "selectedFrameId": value.get("selectedFrameId") if value.get("selectedFrameId") in model.get("sources", {}) else None,
        "selection": selection if isinstance(selection, dict) and selection.get("id") in entity_ids else None,
        "projectDrawerOpen": bool(value.get("projectDrawerOpen")),
    }
```

- [ ] **Step 4: Run tests and verify GREEN**

Run the Step 2 commands and the existing history tests:

```powershell
node --test tests/js/archive-history.test.js tests/js/review-persistence.test.js
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_history_access.py tests/test_review_persistence.py -q
```

Expected: all focused tests PASS.

- [ ] **Step 5: Commit persistence behavior**

```powershell
git add js/review-client.js js/review-workspace.js js/backend.js js/app.js tests/js/review-persistence.test.js backend/review_service.py backend/server.py tests/test_review_persistence.py
git commit -m "feat: persist GVE16 review progress"
```

---

### Task 8: Export preview, confirmed planning compilation, and publication gate

**Files:**
- Modify: `backend/planning_model.py`
- Modify: `backend/planner.py`
- Modify: `backend/server.py:337-363`
- Create: `backend/review_preview.py`
- Create: `tests/test_review_preview.py`
- Modify: `tests/test_planning_model.py`
- Create: `js/export-preview.js`
- Create: `tests/js/export-preview.test.js`
- Modify: `js/review-workspace.js`
- Modify: `js/feishu-publish.js`

**Interfaces:**
- Consumes: confirmed `reviewModel`, Task 1 `review_gate`, and the existing local UE SVG renderer.
- Produces: `compile_confirmed_planning_model(job)`, `build_review_preview(job, job_dir=None)`, `POST /review-model/preview`, browser `ExportPreview.viewModel`, `ExportPreview.routeForIssue`, `ExportPreview.render`, a real `boardPreviewSvg`, and Feishu publish rejection when preview revision is stale.

- [ ] **Step 1: Write failing compilation and gate tests**

```python
from fastapi.testclient import TestClient

from backend import server
from backend.review_preview import build_review_preview
from tests.review_fixtures import make_confirmed_job


def test_preview_uses_confirmed_review_model_and_reports_warning_without_blocking(tmp_path):
    job = make_confirmed_job()
    job["reviewModel"]["crossStateConstraints"] = [{"id": "CST-001", "text": "弱网反馈待确认", "severity": "non_core", "status": "unknown"}]
    preview = build_review_preview(job, tmp_path)
    assert preview["exportReady"] is True
    assert preview["warningIds"] == ["CST-001"]
    assert preview["representativeFrameIds"] == ["F0001", "F0002"]
    assert preview["planningModel"]["standard"] == "GVE16"
    assert preview["planningModel"]["project"]["sourceType"] == "image_sequence"
    assert preview["boardPreviewSvg"].startswith("<svg")


def test_stale_preview_blocks_publish(monkeypatch):
    job = make_confirmed_job()
    job["reviewModel"]["reviewState"]["previewRevision"] = job["reviewModel"]["revision"] - 1
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    client = TestClient(server.app)
    response = client.post(f"/api/jobs/{job['id']}/feishu/publish", json={"requestId": "req-1", "mode": "reuse"})
    assert response.status_code == 409
    assert "重新生成导出预览" in response.json()["detail"]
```

Add these JavaScript cases:

```js
test("blockers navigate to their source while warnings keep export available", () => {
  const ready = ExportPreview.viewModel({ exportReady: true, blockerIds: [], warningIds: ["CST-001"], revision: 4 }, { revision: 4 });
  assert.equal(ready.exportDisabled, false);
  const blocked = ExportPreview.viewModel({ exportReady: false, blockerIds: ["STG-001"], warningIds: [], revision: 3 }, { revision: 4 });
  assert.equal(blocked.exportDisabled, true);
  assert.deepEqual(ExportPreview.routeForIssue("STG-001"), { view: "stage", stageId: "STG-001" });
});
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_preview.py tests/test_planning_model.py -q
node --test tests/js/export-preview.test.js
```

Expected: FAIL because confirmed compilation and preview modules do not exist.

- [ ] **Step 3: Compile confirmed review data and render preview**

Create `backend/review_preview.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from .planning_model import compile_confirmed_planning_model
from .review_model import review_gate


def build_review_preview(job: dict[str, Any], job_dir: Path | None = None) -> dict[str, Any]:
    model = job["reviewModel"]
    gate = review_gate(model)
    planning = compile_confirmed_planning_model(job)
    frame_ids = []
    for stage in sorted(model["stages"], key=lambda item: item["order"]):
        for item in stage["representativeFrames"]:
            if item["frameId"] not in frame_ids:
                frame_ids.append(item["frameId"])
    board_svg = ""
    if job_dir is not None:
        from .feishu_render import render_ue_board_svg
        board_svg, _ = render_ue_board_svg(job, job_dir)
    preview = {"revision": model["revision"], "exportReady": gate["exportReady"], "blockerIds": gate["blockers"], "warningIds": gate["warnings"], "representativeFrameIds": frame_ids, "planningModel": planning, "boardPreviewSvg": board_svg}
    if gate["exportReady"]:
        model["reviewState"]["previewRevision"] = model["revision"]
    job["planningModel"] = planning
    return preview
```

Add `compile_confirmed_planning_model(job)` to `backend/planning_model.py`. It must map `STG-*` to `SCN-*`, included confirmed transitions to `EVT-*`/`FLOW-*`, regions/components/states to `CMP-*`, representative frames to screenshot evidence with `sourceType=image_sequence`, and cross-state constraints to a dedicated extension consumed by renderers. Keep `build_planning_model` as the legacy fallback.

Add the preview endpoint; regenerate `job["plan"]` from the confirmed planning model. Update publish validation to require `review_gate(...).exportReady` and `previewRevision == revision` for jobs with a review model.

Create `js/export-preview.js` to render the directory, sanitized `boardPreviewSvg`, representative count, blockers, warnings, revision, and entity-return buttons. Feishu export remains explicit and is enabled only when the preview is current and export-ready.

Its pure boundary is:

```js
function viewModel(preview, model) { return { ...preview, exportDisabled: !preview.exportReady || preview.revision !== model.revision }; }
function routeForIssue(id) {
  if (id.startsWith("STG-")) return { view: "stage", stageId: id };
  if (id.startsWith("TRN-") || id === "FLOW_NOT_CONFIRMED") return { view: "flow", transitionId: id.startsWith("TRN-") ? id : null };
  return { view: "flow", issueId: id };
}
```

- [ ] **Step 4: Run tests and verify GREEN**

Run Step 2 plus existing publication UI/API contracts:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_review_preview.py tests/test_planning_model.py tests/test_feishu_publish_api.py -q
node --test tests/js/export-preview.test.js tests/js/feishu-publish.test.js
```

Expected: all focused tests PASS.

- [ ] **Step 5: Commit export gating**

```powershell
git add backend/planning_model.py backend/planner.py backend/server.py backend/review_preview.py tests/test_review_preview.py tests/test_planning_model.py js/export-preview.js js/review-workspace.js js/feishu-publish.js tests/js/export-preview.test.js
git commit -m "feat: gate GVE16 export on review"
```

---

### Task 9: GVE16 document and native UE-board mapping

**Files:**
- Modify: `backend/feishu_render.py`
- Modify: `backend/feishu_native_board.py`
- Modify: `backend/loop_hierarchy.py`
- Modify: `tests/test_feishu_render.py`
- Modify: `tests/test_gve16_native_whiteboard.py`
- Modify: `tests/test_feishu_sample_aligned_board.py`
- Modify: `tests/test_feishu_publish_contract.py`

**Interfaces:**
- Consumes: Task 8 confirmed `planningModel`, review extensions, representative-frame roles, region display numbers, transitions, and constraints.
- Produces: one `NativeWhiteboard`, document XML, deterministic media list, red marker/rule mapping, yellow notes, and solid/dashed straight connectors.

- [ ] **Step 1: Write failing sample-alignment tests**

```python
from backend.feishu_native_board import compile_gve16_whiteboard
from backend.feishu_render import render_feishu_document
from backend.review_preview import build_review_preview
from tests.review_fixtures import make_confirmed_job


def test_confirmed_review_board_uses_only_representatives_and_continuous_markers(tmp_path):
    job = make_confirmed_job()
    build_review_preview(job)
    board = compile_gve16_whiteboard(job)
    assert [image.frame_id for image in board.images] == ["F0001", "F0002"]
    nodes = [*board.structure["nodes"], *board.overlay["nodes"]]
    marker_nodes = [node for node in nodes if str(node.get("id", "")).startswith("marker-")]
    assert [node["text"]["text"] for node in marker_nodes] == ["1", "2", "3"]
    assert [node for node in nodes if node["type"] == "section"]


def test_transition_lines_use_semantic_styles():
    job = make_confirmed_job()
    job["reviewModel"]["transitions"] = [
        {**job["reviewModel"]["transitions"][0], "resultType": "navigate", "direction": "forward", "triggerLabel": "点击确认"},
        {**job["reviewModel"]["transitions"][1], "resultType": "return", "direction": "return", "triggerLabel": "关闭返回"},
    ]
    build_review_preview(job)
    board = compile_gve16_whiteboard(job)
    connectors = [node for node in board.overlay["nodes"] if node["type"] == "connector"]
    assert connectors[0]["connector"]["shape"] == "straight"
    assert connectors[0]["style"]["border_style"] == "solid"
    assert connectors[1]["style"]["border_style"] == "dash"


def test_document_does_not_repeat_board_screenshots(tmp_path):
    job = make_confirmed_job()
    build_review_preview(job)
    rendered = render_feishu_document(job, tmp_path)
    assert "参考画面" not in rendered.xml
    assert "证据帧" not in rendered.xml
    assert rendered.xml.count("<whiteboard") == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests/test_feishu_render.py tests/test_gve16_native_whiteboard.py tests/test_feishu_sample_aligned_board.py tests/test_feishu_publish_contract.py -q
```

Expected: FAIL because review-model representatives, marker numbering, constraints, and transition styles are not mapped.

- [ ] **Step 3: Map confirmed review entities without changing the publication protocol**

Update `loop_hierarchy.py` so confirmed stages become the large-loop stage list and each stage `smallLoop` becomes its internal loop. Update `feishu_native_board.py` to:

- select only unique `representativeFrames` in confirmed stage order;
- create real Section nodes for parent pages, overlays, and functional modules;
- place global continuous red markers from confirmed region `displayOrder` and matching numbered rule text;
- convert `crossStateConstraints` and non-core unknowns to `#fff3bf` notes;
- emit native straight connectors only, solid for forward/open and dashed for return/close;
- label automatic transitions with their trigger instead of creating click anchors;
- keep state changes inside their parent Section.

Update `feishu_render.py` so the existing `TVnd...` chapter order is unchanged, stage small loops and component-state tables come from confirmed review data, pending constraints appear in the approved pending section, and no screenshot block is added after the whiteboard.

Do not change media upload commands, checkpoint identifiers, overwrite-before-media sequencing, or preview/raw verification.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Step 2 command.

Expected: all Feishu and whiteboard contracts PASS.

- [ ] **Step 5: Commit GVE16 rendering**

```powershell
git add backend/feishu_render.py backend/feishu_native_board.py backend/loop_hierarchy.py tests/test_feishu_render.py tests/test_gve16_native_whiteboard.py tests/test_feishu_sample_aligned_board.py tests/test_feishu_publish_contract.py
git commit -m "feat: render confirmed GVE16 review"
```

---

### Task 10: Responsive browser QA, compatibility, and final verification

**Files:**
- Modify: `css/review-workspace.css`
- Modify: `index.html`
- Modify: `tests/test_screenshot_input_ui_contract.py`
- Create: `tests/test_review_workspace_ui_contract.py`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified desktop/mobile workflow, legacy-job fallback, clean source tree, and completed execution records.

- [ ] **Step 1: Add failing final UI contract assertions**

```python
def test_review_workspace_accessibility_and_responsive_contract():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")
    assert 'aria-label="审核步骤"' in html
    assert 'aria-live="polite"' in html
    assert "min-height: 44px" in css
    assert ":focus-visible" in css
    assert "overflow-x: auto" in css
    assert "max-width: 700px" in css
    assert "stage-mobile-tabs" in css
    assert "prefers-reduced-motion" in css
```

Add this JavaScript compatibility test:

```js
test("legacy completed jobs retain the frame reviewer fallback", () => {
  const route = ReviewWorkspace.routeForJob({ status: "completed", metadata: { mode: "interaction" }, frames: [{ id: "F0001" }] });
  assert.equal(route, "legacy_frames");
  assert.equal(ReviewWorkspace.routeForJob({ status: "completed", metadata: { mode: "interaction" }, reviewModel: { quality: { qualified: true } } }), "review_workspace");
});
```

- [ ] **Step 2: Run all project tests and capture any expected RED**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests -q
node --test tests/js/*.test.js
```

Expected before final polish: only newly added responsive/accessibility assertions may fail; existing tests must remain green.

- [ ] **Step 3: Complete responsive and accessibility polish**

Ensure:

- only the lane container scrolls horizontally on narrow screens;
- the page itself never overflows horizontally;
- stage review switches between picture and rule tabs under 700px;
- drag alternatives, keyboard focus, Delete handling, and 44px targets work;
- save/error/confirmation changes use `aria-live`;
- reduced-motion removes nonessential transitions;
- screenshot images reserve dimensions to prevent layout shift;
- old jobs retain the legacy reviewer, and all new interaction jobs use the staged workspace.

Use browser QA with 7 and 30 screenshot fixtures. Verify reorder, candidate filtering, flow confirmation, stage switching, component box movement, click anchor movement, auto-transition editing, save failure recovery, refresh restoration, preview blockers, and Feishu button gating at desktop and 390px width.

- [ ] **Step 4: Run fresh full verification**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages;$PWD"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests -q
node --test tests/js/*.test.js
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m compileall -q backend
Get-ChildItem js -Filter *.js | ForEach-Object { node --check $_.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
git diff --check
```

Expected: all project tests PASS; compilation and syntax checks produce no errors; `git diff --check` produces no output except configured line-ending warnings.

- [ ] **Step 5: Run focused simplification and requirement review**

Inspect `git diff` against this plan and the design specification. Confirm every completion criterion has a passing test, remove dead legacy branches that are no longer reachable for new jobs without removing the legacy fallback, avoid new dependencies, and keep responsibilities out of `frames-models.js` and `server.py` when they belong in the new focused modules. Re-run Step 4 after any simplification.

- [ ] **Step 6: Commit final QA and records**

```powershell
git add css/review-workspace.css index.html tests/test_screenshot_input_ui_contract.py tests/test_review_workspace_ui_contract.py progress.md task_plan.md
git commit -m "test: verify GVE16 review workspace"
```
