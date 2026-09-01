from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend import server, storage
from backend.review_model import build_review_model, empty_rule_domains
from backend.review_service import apply_operations, record_reanalysis_suggestions, sanitize_review_ui_state
from tests.review_fixtures import make_image_job


def test_final_document_view_survives_server_ui_state_sanitizing():
    model = build_review_model(make_image_job())

    restored = sanitize_review_ui_state(model, {"view": "final_preview"})

    assert restored["view"] == "final_preview"


def test_ui_state_and_suggestions_preserve_human_values():
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


def test_normal_set_marks_human_field_and_removes_its_suggestion():
    model = build_review_model(make_image_job())
    stage = model["stages"][0]
    stage["suggestions"] = {"name": "模型新名称"}

    changed = apply_operations(model, [{"type": "set", "entity": "stage", "id": stage["id"], "field": "name", "value": "人工名称"}], model["revision"])

    assert changed["stages"][0]["humanEditedFields"] == ["name"]
    assert changed["stages"][0]["suggestions"] == {}


def test_reanalysis_records_suggestions_without_overwriting_human_or_confirmed_values():
    model = build_review_model(make_image_job())
    model["ruleDomains"] = {"legacy": "keep"}
    stage = model["stages"][0]
    stage["name"] = "人工名称"
    stage["humanEditedFields"] = ["name"]
    stage["confirmation"] = {"confirmed": True, "revision": 1}
    candidate = build_review_model(make_image_job())
    candidate["ruleDomains"] = {"legacy": "keep"}
    candidate["stages"][0]["name"] = "模型新名称"

    updated = record_reanalysis_suggestions(model, candidate)

    assert updated["stages"][0]["name"] == "人工名称"
    assert updated["stages"][0]["humanEditedFields"] == ["name"]
    assert updated["stages"][0]["suggestions"]["name"] == "模型新名称"


def test_reanalysis_records_rule_suggestions_without_overwriting_human_rule_values():
    model = build_review_model(make_image_job())
    model["ruleDomains"] = empty_rule_domains()
    model["ruleDomains"]["narrative"] = [{
        "id": "NAR-001", "title": "人工规则", "humanEditedFields": ["title"], "suggestions": {"presentation": "保留建议"},
    }]
    candidate = deepcopy(model)
    candidate["ruleDomains"]["narrative"][0]["title"] = "模型规则"

    updated = record_reanalysis_suggestions(model, candidate)

    assert updated["ruleDomains"]["narrative"][0]["title"] == "人工规则"
    assert updated["ruleDomains"]["narrative"][0]["suggestions"] == {"presentation": "保留建议", "title": "模型规则"}


def test_ui_state_endpoint_sanitizes_and_rejects_archived_jobs(monkeypatch):
    job = make_image_job()
    job["reviewModel"] = build_review_model(job)
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server, "save_job", lambda value: store.__setitem__(value["id"], value))
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    client = TestClient(server.app)

    response = client.post(f"/api/jobs/{job['id']}/review-model/ui-state", json={"view": "preview", "selectedStageId": "missing", "selection": {"type": "region", "id": "missing"}})

    assert response.status_code == 200
    assert response.json()["view"] == "preview"
    assert response.json()["selectedStageId"] == "STG-001"
    assert response.json()["selection"] is None
    job["archived"] = True
    assert client.post(f"/api/jobs/{job['id']}/review-model/ui-state", json={}).status_code == 409


def test_ui_state_rejects_cross_type_ids_and_explicit_operations_mark_humans():
    model = build_review_model(make_image_job())
    stage, transition = model["stages"][0], model["transitions"][0]
    model["regions"] = [{"id": "REG-0001", "stageId": stage["id"], "frameId": "F0001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}, "displayOrder": 1, "displayNumber": 1}]
    stage["regionIds"] = ["REG-0001"]
    restored = sanitize_review_ui_state(model, {"selectedTransitionId": "REG-0001", "selection": {"type": "transition", "id": "REG-0001"}})
    assert restored["selectedTransitionId"] is None
    assert restored["selection"] is None

    changed = apply_operations(model, [{"type": "set_region_bounds", "id": "REG-0001", "bounds": {"x": 0.2, "y": 0.2, "width": 0.2, "height": 0.2}}, {"type": "set_transition_included", "id": transition["id"], "included": False}, {"type": "set_small_loop", "id": stage["id"], "smallLoop": {"display": "human"}}], model["revision"])
    assert "bounds" in changed["regions"][0]["humanEditedFields"]
    assert "included" in changed["transitions"][0]["humanEditedFields"]
    assert "smallLoop" in changed["stages"][0]["humanEditedFields"]


@pytest.mark.parametrize("endpoint, extra", [
    (server.reanalyze_job, ()),
    (server.reanalyze_scene, (0,)),
])
def test_archived_whole_job_and_scene_reanalysis_never_write_or_enqueue(monkeypatch, endpoint, extra):
    job = make_image_job()
    job["archived"] = True
    writes, submissions = [], []
    monkeypatch.setattr(server, "load_job", lambda job_id: job)
    monkeypatch.setattr(server, "save_job", lambda value: writes.append(value))
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(job))
    monkeypatch.setattr(server.executor, "submit", lambda *args: submissions.append(args))

    with pytest.raises(server.HTTPException) as error:
        endpoint(job["id"], *extra, "", "", "")

    assert error.value.status_code == 409
    assert writes == []
    assert submissions == []


def test_full_form_upserts_only_mark_actual_supported_human_changes():
    model = build_review_model(make_image_job())
    transition = model["transitions"][0]
    transition["suggestions"] = {"triggerLabel": "model", "response": "keep"}
    untouched = apply_operations(model, [{"type": "upsert_transition", "transition": {"id": transition["id"], "triggerLabel": transition["triggerLabel"]}}], model["revision"])
    assert untouched["transitions"][0]["suggestions"] == transition["suggestions"]
    assert untouched["transitions"][0].get("humanEditedFields", []) == []

    changed = apply_operations(model, [{"type": "upsert_transition", "transition": {"id": transition["id"], "triggerLabel": "human"}}], model["revision"])
    assert changed["transitions"][0]["humanEditedFields"] == ["triggerLabel"]
    assert changed["transitions"][0]["suggestions"] == {"response": "keep"}

    constraint_model = deepcopy(model)
    constraint_model["crossStateConstraints"] = [{"id": "CNS-001", "text": "old", "severity": "core", "status": "observed", "suggestions": {"text": "model", "details": "keep"}}]
    no_op = apply_operations(constraint_model, [{"type": "upsert_constraint", "constraint": {"id": "CNS-001", "text": "old"}}], constraint_model["revision"])
    assert no_op["crossStateConstraints"][0]["suggestions"] == {"text": "model", "details": "keep"}
    assert no_op["crossStateConstraints"][0].get("humanEditedFields", []) == []

    edited = apply_operations(constraint_model, [{"type": "upsert_constraint", "constraint": {"id": "CNS-001", "text": "human"}}], constraint_model["revision"])
    assert edited["crossStateConstraints"][0]["humanEditedFields"] == ["text"]
    assert edited["crossStateConstraints"][0]["suggestions"] == {"details": "keep"}

    region_model = deepcopy(model)
    region_model["regions"] = [{"id": "REG-0001", "stageId": "STG-001", "frameId": "F0001", "name": "old", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}, "sourceType": "human", "primary": False, "rule": {}, "displayOrder": 1, "displayNumber": 1, "suggestions": {"name": "model", "rule": {"keep": True}}}]
    region_no_op = apply_operations(region_model, [{"type": "upsert_region", "region": {"id": "REG-0001", "name": "old"}}], region_model["revision"])
    assert region_no_op["regions"][0]["suggestions"] == {"name": "model", "rule": {"keep": True}}
    assert region_no_op["regions"][0].get("humanEditedFields", []) == []

    region_edited = apply_operations(region_model, [{"type": "upsert_region", "region": {"id": "REG-0001", "name": "human"}}], region_model["revision"])
    assert region_edited["regions"][0]["humanEditedFields"] == ["name"]
    assert region_edited["regions"][0]["suggestions"] == {"rule": {"keep": True}}


def test_legacy_rule_id_counter_survives_delete_persist_reload_before_recreate(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    job = storage.new_job({"mode": "interaction", "projectName": "Demo", "scope": ""})
    model = build_review_model(make_image_job())
    model["ruleDomains"] = empty_rule_domains()
    rule = {
        "title": "开场叙事", "stageId": "STG-001", "frameId": None,
        "triggerScene": "进入关卡", "triggerNode": "开场", "presentation": "播放对白", "continuation": "开始操作",
    }
    seeded = apply_operations(model, [{"type": "upsert_rule", "domain": "narrative", "rule": rule}], model["revision"])
    seeded["ruleDomains"].pop("nextRuleNumbers")
    job["reviewModel"] = seeded
    storage.save_job(job)

    deleted_job = storage.load_job(job["id"])
    deleted_job["reviewModel"] = apply_operations(
        deleted_job["reviewModel"], [{"type": "delete_rule", "domain": "narrative", "id": "NAR-001"}], deleted_job["reviewModel"]["revision"],
    )
    storage.save_job(deleted_job)
    reloaded = storage.load_job(job["id"])
    recreated = apply_operations(reloaded["reviewModel"], [{"type": "upsert_rule", "domain": "narrative", "rule": rule}], reloaded["reviewModel"]["revision"])

    assert recreated["ruleDomains"]["narrative"][0]["id"] == "NAR-002"
