from copy import deepcopy
import threading
import json

import pytest
from fastapi.testclient import TestClient

from backend import server, storage
from backend.review_model import build_review_model, empty_rule_domains
from backend.gameplay_review_model import build_gameplay_review_model, required_parameter_fields
from tests.review_fixtures import make_confirmed_job, make_image_job


def test_gameplay_response_merges_p6_sidecar_without_mutating_job_json(tmp_path, monkeypatch):
    job = {"id": "job-p6-sidecar", "gameplayReviewModel": {"revision": 7, "tables": [{"id": "OLD", "status": "reviewed"}]}}
    structures = tmp_path / "structures"
    structures.mkdir()
    (structures / "p6-review-tables.json").write_text(json.dumps({
        "schemaVersion": "p6-review-tables-v1",
        "tables": [{"id": "P6-CHOICE", "title": "三选一配置", "status": "reviewed", "rows": [["候选数量", "3", "已确认"]]}],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(server, "job_path", lambda _job_id: tmp_path)

    response = server._gameplay_model_response(job)

    assert response["tables"] == [{"id": "OLD", "status": "reviewed"}, {"id": "P6-CHOICE", "title": "三选一配置", "status": "reviewed", "rows": [["候选数量", "3", "已确认"]]}]
    assert response["p6Sidecar"] == {"schemaVersion": "p6-review-tables-v1", "tableCount": 1}
    assert job["gameplayReviewModel"]["tables"] == [{"id": "OLD", "status": "reviewed"}]


def test_gameplay_response_merges_p5_sidecar_without_mutating_job_json(tmp_path, monkeypatch):
    job = {"id": "job-p5-sidecar", "gameplayReviewModel": {"revision": 7, "diagrams": [{"id": "OLD", "status": "deleted"}]}}
    structures = tmp_path / "structures"
    structures.mkdir()
    (structures / "p5-review-diagrams.json").write_text(json.dumps({
        "schemaVersion": "p5-review-diagrams-v1",
        "diagrams": [{"id": "P5-CHOICE-FLOW", "type": "state_flow", "chapterIds": ["GCH-012"], "status": "reviewed", "svg": "<svg><path d='M0 0L1 1'/></svg>"}],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(server, "job_path", lambda _job_id: tmp_path)

    response = server._gameplay_model_response(job)

    assert response["diagrams"][-1]["id"] == "P5-CHOICE-FLOW"
    assert response["p5Sidecar"] == {"schemaVersion": "p5-review-diagrams-v1", "diagramCount": 1}
    assert job["gameplayReviewModel"]["diagrams"] == [{"id": "OLD", "status": "deleted"}]


def _client_with_job(monkeypatch, archived=False):
    job = make_image_job()
    job["archived"] = archived
    job["reviewModel"] = build_review_model(job)
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server, "save_job", lambda value: store.__setitem__(value["id"], value))
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    return TestClient(server.app), job, store


def _persist_confirmed_job(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    seed = storage.new_job({"mode": "interaction", "projectName": "Demo", "scope": ""})
    job = make_confirmed_job()
    job.update(
        id=seed["id"], status="completed", plan="# Demo",
        planningModel={"standard": "GVE16", "mode": "interaction"},
    )
    storage.save_job(job)
    return job


def test_review_operation_api_rejects_stale_revision(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)
    job["reviewModel"]["stages"][0]["name"] = "before"

    response = client.post(f"/api/jobs/{job['id']}/review-model/operations", json={"expectedRevision": 1, "operations": [{"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "选择武器"}]})

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    stale = client.post(f"/api/jobs/{job['id']}/review-model/operations", json={"expectedRevision": 1, "operations": []})
    assert stale.status_code == 409
    assert stale.json()["detail"]["currentRevision"] == 2


def test_review_api_loads_saves_and_rejects_archived_mutations(monkeypatch):
    client, job, store = _client_with_job(monkeypatch)

    assert client.get(f"/api/jobs/{job['id']}/review-model").json()["revision"] == 1
    assert client.post(f"/api/jobs/{job['id']}/review-model/undo", json={"expectedRevision": 1}).status_code == 400
    assert client.post(f"/api/jobs/{job['id']}/review-model/operations", json={"expectedRevision": 1, "operations": []}).json()["revision"] == 1
    assert store[job["id"]]["reviewModel"]["revision"] == 1

    archived_client, archived, _ = _client_with_job(monkeypatch, archived=True)
    assert archived_client.post(f"/api/jobs/{archived['id']}/review-model/redo", json={"expectedRevision": 1}).status_code == 409


def test_confirm_stage_api_requires_current_revision(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)

    response = client.post(f"/api/jobs/{job['id']}/review-model/confirm-stage", json={"stageId": "STG-001", "expectedRevision": 0})

    assert response.status_code == 409
    assert response.json()["detail"] == {"currentRevision": 1}


def test_confirm_stage_api_does_not_unlock_preview_for_a_stage_without_evidence(monkeypatch):
    client, job, store = _client_with_job(monkeypatch)
    model = job["reviewModel"]
    flow = client.post(f"/api/jobs/{job['id']}/review-model/confirm-flow", json={"expectedRevision": model["revision"]})
    assert flow.status_code == 200
    stage = flow.json()["stages"][0]
    frame_id = stage["representativeFrames"][0]["frameId"]
    store[job["id"]]["reviewModel"]["sources"][frame_id]["imageUrl"] = ""

    response = client.post(
        f"/api/jobs/{job['id']}/review-model/confirm-stage",
        json={"stageId": stage["id"], "expectedRevision": flow.json()["revision"]},
    )

    assert response.status_code == 400
    assert "stage evidence" in response.json()["detail"]
    saved = store[job["id"]]["reviewModel"]
    assert saved["stages"][0]["confirmation"]["confirmed"] is False
    assert saved["reviewState"]["status"] == "stage_review"


def test_last_stage_confirmation_goes_directly_to_preview_pending(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)
    model = job["reviewModel"]
    model["ruleDomains"] = {"confirmation": {"confirmed": True, "revision": 7}, "legacy": "keep"}
    before_rules = deepcopy(model["ruleDomains"])
    for stage in model["stages"]:
        stage["smallLoop"] = {
            "display": stage["name"], "trigger": "confirmed trigger", "feedback": "confirmed feedback",
            "result": stage["exitCondition"], "retry": "",
        }

    response = client.post(f"/api/jobs/{job['id']}/review-model/confirm-flow", json={"expectedRevision": model["revision"]})
    assert response.status_code == 200
    for stage in model["stages"]:
        response = client.post(
            f"/api/jobs/{job['id']}/review-model/confirm-stage",
            json={"stageId": stage["id"], "expectedRevision": response.json()["revision"]},
        )

    assert response.status_code == 200
    assert response.json()["reviewState"]["status"] == "preview_pending"
    assert "ueFlowConfirmed" not in response.json()["reviewState"]
    assert response.json()["ruleDomains"] == before_rules


def test_active_reference_board_mutation_preserves_legacy_data(monkeypatch):
    _, job, _ = _client_with_job(monkeypatch)
    model = job["reviewModel"]
    model["ruleDomains"] = {"legacy": "keep"}
    model["referenceBoards"]["ux"] = {"assets": "legacy"}
    before_rules = deepcopy(model["ruleDomains"])
    before_ux = deepcopy(model["referenceBoards"]["ux"])

    server._finish_reference_board_mutation(job, "competitor")

    assert model["ruleDomains"] == before_rules
    assert model["referenceBoards"]["ux"] == before_ux


def test_confirm_rule_domains_endpoint_persists_canonical_model_and_errors(monkeypatch):
    client, job, store = _client_with_job(monkeypatch)
    model = job["reviewModel"]
    model["ruleDomains"] = empty_rule_domains()
    model["ruleDomains"]["reviewedDomains"] = ["narrative", "guidance", "redDots"]

    response = client.post(f"/api/jobs/{job['id']}/review/confirm-rules", json={"expectedRevision": model["revision"]})

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["ruleDomains"]["confirmation"] == {"confirmed": True, "revision": 2}
    canonical = response.json()
    canonical.pop("reviewUiState")
    assert store[job["id"]]["reviewModel"] == canonical
    stale = client.post(f"/api/jobs/{job['id']}/review/confirm-rules", json={"expectedRevision": 1})
    assert stale.status_code == 409
    assert stale.json()["detail"] == {"currentRevision": 2}
    assert client.post(f"/api/jobs/{job['id']}/review/confirm-rules", json={}).status_code == 400
    assert client.post(f"/api/jobs/{job['id']}/review/confirm-rules", json=[]).status_code == 422


def test_confirm_rule_domains_endpoint_rejects_invalid_rule_model(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)
    model = job["reviewModel"]
    model["ruleDomains"] = empty_rule_domains()
    model["ruleDomains"].update(
        narrative=[{"id": "NAR-001"}],
        reviewedDomains=["narrative", "guidance", "redDots"],
    )

    response = client.post(f"/api/jobs/{job['id']}/review/confirm-rules", json={"expectedRevision": model["revision"]})

    assert response.status_code == 400
    assert "NAR-001" in response.json()["detail"]


def test_confirmation_api_rejects_missing_expected_revision(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)

    assert client.post(f"/api/jobs/{job['id']}/review-model/confirm-flow", json={}).status_code == 400
    assert client.post(f"/api/jobs/{job['id']}/review-model/confirm-stage", json={"stageId": "STG-001"}).status_code == 400


def test_operations_api_rejects_invalid_payload_shapes(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)

    for operations in (None, {"type": "set"}, [None]):
        response = client.post(f"/api/jobs/{job['id']}/review-model/operations", json={"expectedRevision": 1, "operations": operations})
        assert response.status_code == 400


def test_archived_legacy_review_model_get_is_not_saved(monkeypatch):
    job = make_image_job()
    job["archived"] = True
    store = {job["id"]: job}
    saved = []
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server, "save_job", lambda value: saved.append(value))
    client = TestClient(server.app)

    response = client.get(f"/api/jobs/{job['id']}/review-model")

    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert saved == []


def test_existing_review_model_get_backfills_and_persists_screenshot_coverage(monkeypatch):
    client, job, store = _client_with_job(monkeypatch)
    for source in job["reviewModel"]["sources"].values():
        source.pop("materialRole", None)
        source.pop("stageId", None)
    for stage in job["reviewModel"]["stages"]:
        stage.pop("sourceFrameIds", None)

    response = client.get(f"/api/jobs/{job['id']}/review-model")

    assert response.status_code == 200
    model = response.json()
    assert all(source.get("materialRole") for source in model["sources"].values())
    assert {frame_id for stage in model["stages"] for frame_id in stage["sourceFrameIds"]} == set(model["sources"])
    assert store[job["id"]]["reviewModel"]["sources"]["F0001"]["materialRole"] == "independent_page"


def test_review_operation_lock_prevents_stale_save_from_deleting_publication(tmp_path, monkeypatch):
    job = _persist_confirmed_job(tmp_path, monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    pin_done = threading.Event()
    errors = []
    original_apply = server.apply_operations

    def blocked_apply(*args):
        entered.set()
        if not release.wait(2):
            raise TimeoutError("review operation barrier timed out")
        return original_apply(*args)

    monkeypatch.setattr(server, "apply_operations", blocked_apply)

    def mutate_review():
        try:
            server.apply_review_operations(job["id"], {
                "expectedRevision": 1,
                "operations": [{"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "edited"}],
            })
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    review_thread = threading.Thread(target=mutate_review)
    review_thread.start()
    assert entered.wait(2)

    def pin_publication():
        storage.mutate_job(job["id"], lambda current: current.__setitem__(
            "feishuPublication", {"status": "checking_auth", "requestId": "req-atomic-review-1"}
        ))
        pin_done.set()

    pin_thread = threading.Thread(target=pin_publication)
    pin_thread.start()
    assert not pin_done.wait(0.2)
    release.set()
    review_thread.join(2)
    pin_thread.join(2)

    current = storage.load_job(job["id"])
    assert errors == []
    assert current["reviewModel"]["revision"] == 2
    assert current["feishuPublication"]["requestId"] == "req-atomic-review-1"


def test_publication_pin_preserves_concurrent_review_revision(tmp_path, monkeypatch):
    job = _persist_confirmed_job(tmp_path, monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    review_done = threading.Event()
    original_gate = server.review_gate
    monkeypatch.setattr(server, "executor", type("Deferred", (), {"submit": lambda self, *args: None})())

    def blocked_gate(model):
        entered.set()
        if not release.wait(2):
            raise TimeoutError("publication barrier timed out")
        return original_gate(model)

    monkeypatch.setattr(server, "review_gate", blocked_gate)
    publication_thread = threading.Thread(
        target=lambda: server.publish_job_to_feishu(job["id"], {"requestId": "req-atomic-pin-01", "mode": "update"})
    )
    publication_thread.start()
    assert entered.wait(2)

    def mutate_review():
        server.apply_review_operations(job["id"], {
            "expectedRevision": 1,
            "operations": [{"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "revision 2"}],
        })
        review_done.set()

    review_thread = threading.Thread(target=mutate_review)
    review_thread.start()
    assert not review_done.wait(0.2)
    release.set()
    publication_thread.join(2)
    review_thread.join(2)

    current = storage.load_job(job["id"])
    assert current["reviewModel"]["revision"] == 2
    assert current["feishuPublication"]["requestId"] == "req-atomic-pin-01"
    assert current["feishuPublication"]["approvedReviewRevision"] == 1


def test_ui_state_merge_preserves_publication_record(tmp_path, monkeypatch):
    job = _persist_confirmed_job(tmp_path, monkeypatch)
    publication = {
        "status": "published", "requestId": "req-ui-merge-0001",
        "documentToken": "doc-1", "approvedReviewRevision": 1,
    }
    entered = threading.Event()
    release = threading.Event()
    pin_done = threading.Event()
    original_sanitize = server.sanitize_review_ui_state

    def blocked_sanitize(*args):
        entered.set()
        if not release.wait(2):
            raise TimeoutError("UI-state barrier timed out")
        return original_sanitize(*args)

    monkeypatch.setattr(server, "sanitize_review_ui_state", blocked_sanitize)
    saved = []
    ui_thread = threading.Thread(target=lambda: saved.append(
        server.save_review_ui_state(job["id"], {"view": "preview", "selectedStageId": "STG-001"})
    ))
    ui_thread.start()
    assert entered.wait(2)

    def pin_publication():
        storage.mutate_job(job["id"], lambda current: current.__setitem__("feishuPublication", publication.copy()))
        pin_done.set()

    pin_thread = threading.Thread(target=pin_publication)
    pin_thread.start()
    assert not pin_done.wait(0.2)
    release.set()
    ui_thread.join(2)
    pin_thread.join(2)

    current = storage.load_job(job["id"])
    assert saved[0]["view"] == "preview"
    assert current["feishuPublication"] == publication


def test_gameplay_review_generation_rejects_interaction_gate_not_ready(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/generate", data={"api_key": "configured-key"})

    assert response.status_code == 409


def test_failed_initial_gameplay_structure_can_retry_before_interaction_review_is_complete(monkeypatch):
    client, job, store = _client_with_job(monkeypatch)
    job["gameplayReviewGeneration"] = {
        "status": "failed", "progress": 0,
        "message": "Gameplay review generation failed. Please retry.",
        "error": "玩法章节生成失败",
    }
    submitted = []

    class CapturingExecutor:
        def submit(self, task, *args):
            submitted.append((task, args))

    monkeypatch.setattr(server, "executor", CapturingExecutor())

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/generate", data={"api_key": "configured-key"})

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert submitted[0][0] is server._generate_gameplay_review
    assert store[job["id"]]["gameplayReviewGeneration"]["status"] == "queued"


def test_gameplay_review_generation_rejects_stale_interaction_preview(monkeypatch):
    job = make_confirmed_job()
    job["reviewModel"]["reviewState"]["previewRevision"] = job["reviewModel"]["revision"] - 1
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    client = TestClient(server.app)

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/generate", data={"api_key": "configured-key"})

    assert response.status_code == 409
    assert "gameplayReviewGeneration" not in store[job["id"]]


def test_gameplay_review_generation_creates_structure_without_mutating_interaction(monkeypatch):
    job = make_confirmed_job()
    job["metadata"]["mode"] = "gameplay"
    store = {job["id"]: job}
    before = deepcopy(job["reviewModel"])
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "job_path", lambda job_id: None)
    monkeypatch.setattr(server, "generate_gameplay_structure", lambda current, _path, _config, _progress: {
        "chapters": [{"id": "GCH-001"}],
        "reviewState": {"status": "system_directory_review", "structurePhase": "systems"},
    })

    class Immediate:
        def submit(self, task, *args):
            task(*args)

    monkeypatch.setattr(server, "executor", Immediate())
    client = TestClient(server.app)

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/generate", data={"api_key": "configured-key"})

    assert response.status_code == 202
    generation = store[job["id"]]["gameplayReviewGeneration"]
    assert generation["status"] == "completed"
    assert generation["progress"] == 100
    assert generation["message"] == "Gameplay structure ready for review."
    assert generation["phase"] == "finalizing"
    assert generation["startedAt"]
    assert generation["deadlineAt"]
    assert generation["finishedAt"]
    assert generation["generationId"]
    assert store[job["id"]]["gameplayReviewModel"]["reviewState"]["structurePhase"] == "systems"
    assert store[job["id"]]["reviewModel"] == before


def test_gameplay_review_generation_force_rebuilds_a_confirmed_legacy_model(monkeypatch):
    job = make_confirmed_job()
    job["metadata"]["mode"] = "gameplay"
    job["gameplayReviewModel"] = {"directory": {"status": "confirmed"}, "reviewState": {"structurePhase": "detailed"}}
    store = {job["id"]: job}
    calls = []
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "job_path", lambda job_id: None)
    monkeypatch.setattr(server, "generate_gameplay_structure", lambda *_args: calls.append("rebuilt") or {
        "chapters": [{"id": "GCH-001"}], "reviewState": {"status": "system_directory_review", "structurePhase": "systems"},
    })

    class Immediate:
        def submit(self, task, *args):
            task(*args)

    monkeypatch.setattr(server, "executor", Immediate())
    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review/generate",
        data={"force": "true", "api_key": "configured-key"},
    )

    assert response.status_code == 202
    assert calls == ["rebuilt"]
    assert store[job["id"]]["gameplayReviewModel"]["reviewState"]["structurePhase"] == "systems"


def test_gameplay_review_generation_resumes_confirmed_pending_details(monkeypatch):
    job = make_confirmed_job()
    job["gameplayReviewModel"] = {
        "revision": 5, "directory": {"status": "confirmed"},
        "reviewState": {"status": "detail_generation_pending", "structurePhase": "confirmed"},
        "chapters": [{"id": "GCH-001"}],
    }
    store = {job["id"]: job}
    submitted = []
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))

    class CapturingExecutor:
        def submit(self, task, *args): submitted.append((task, args))

    monkeypatch.setattr(server, "executor", CapturingExecutor())
    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review/generate",
        data={"api_base": "https://vision.example/v1", "model": "vision-model", "api_key": "configured-key"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert submitted[0][0] is server._generate_confirmed_gameplay_details
    assert submitted[0][1][1] == {"apiBase": "https://vision.example/v1", "model": "vision-model", "apiKey": "configured-key"}


def test_gameplay_review_generation_persists_safe_failure(monkeypatch):
    job = make_confirmed_job()
    job["metadata"]["mode"] = "gameplay"
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "job_path", lambda job_id: None)
    monkeypatch.setattr(server, "generate_gameplay_structure", lambda *_args: (_ for _ in ()).throw(RuntimeError("private network token")))

    class Immediate:
        def submit(self, task, *args):
            task(*args)

    monkeypatch.setattr(server, "executor", Immediate())
    client = TestClient(server.app)

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/generate", data={"api_key": "configured-key"})

    assert response.status_code == 202
    generation = store[job["id"]]["gameplayReviewGeneration"]
    assert generation["status"] == "failed"
    assert generation["progress"] == 0
    assert generation["message"] == "Gameplay review generation failed. Please retry."
    assert generation["error"] == "玩法章节生成失败"
    assert generation["failureKind"] == "system"
    assert generation["startedAt"]
    assert generation["deadlineAt"]
    assert generation["finishedAt"]
    assert generation["generationId"]
    assert "private network token" not in str(store[job["id"]])


def test_gameplay_review_generation_explains_missing_vision_configuration(monkeypatch):
    job = make_confirmed_job()
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "job_path", lambda job_id: None)
    monkeypatch.setattr(server, "generate_gameplay_structure", lambda *_args: (_ for _ in ()).throw(
        server.GameplayAnalysisQualityError("gameplay vision model is unavailable")
    ))

    class Immediate:
        def submit(self, task, *args):
            task(*args)

    monkeypatch.setattr(server, "executor", Immediate())
    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review/generate",
        data={"api_key": "configured-key"},
    )

    assert response.status_code == 202
    assert store[job["id"]]["gameplayReviewGeneration"]["error"] == "视觉模型未配置"


def test_gameplay_review_generation_marks_submit_failure_as_retryable(monkeypatch):
    job = make_confirmed_job()
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))

    class Rejecting:
        def submit(self, *_args):
            raise RuntimeError("executor stopped")

    monkeypatch.setattr(server, "executor", Rejecting())
    client = TestClient(server.app)

    with pytest.raises(RuntimeError, match="executor stopped"):
        client.post(f"/api/jobs/{job['id']}/gameplay-review/generate", data={"api_key": "configured-key"})

    assert store[job["id"]]["gameplayReviewGeneration"] == {
        "status": "failed", "progress": 0, "message": "Gameplay review generation failed. Please retry.",
    }


def test_startup_marks_interrupted_gameplay_generation_as_retryable(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    job = storage.new_job({"mode": "interaction", "projectName": "Demo", "scope": ""})
    job.update(status="completed", progress=100)
    job["gameplayReviewGeneration"] = {
        "status": "running", "progress": 15, "message": "Generating gameplay review.",
    }
    storage.save_job(job)

    server.resume_interrupted_jobs()

    current = storage.load_job(job["id"])
    assert current["status"] == "completed"
    assert current["gameplayReviewGeneration"] == {
        "status": "failed",
        "progress": 15,
        "message": "Gameplay review generation failed. Please retry.",
        "error": "任务因服务重启暂停，请点击重新生成继续；现有审核结果已保留",
    }


def test_public_gameplay_generation_exposes_only_safe_planner_logs():
    public = server._public_gameplay_review_generation({
        "status": "running", "progress": 25, "message": "Generating gameplay review.",
        "logs": [
            {"progress": 5, "message": "开始读取已确认目录", "level": "info", "private": "secret"},
            {"progress": 25, "message": "已完成5/18个玩法机制", "level": "info"},
        ],
    })

    assert public["logs"] == [
        {"progress": 5, "message": "开始读取已确认目录", "level": "info"},
        {"progress": 25, "message": "已完成5/18个玩法机制", "level": "info"},
    ]


def test_quality_failure_is_publicly_marked_for_automatic_repair():
    public = server._public_gameplay_review_generation({
        "status": "failed", "progress": 80,
        "message": "Gameplay review generation failed. Please retry.",
        "failureKind": "quality",
    })

    assert public["failureKind"] == "quality"


def test_legacy_generic_gameplay_failure_is_publicly_classified_as_system():
    public = server._public_gameplay_review_generation({
        "status": "failed", "progress": 0,
        "message": "Gameplay review generation failed. Please retry.",
        "error": "玩法章节生成失败",
    })

    assert public["failureKind"] == "system"


def test_final_preview_blocks_confirmed_directory_skeleton_until_details_exist(monkeypatch):
    job = make_confirmed_job()
    job["gameplayReviewModel"] = {
        "revision": 41,
        "chapters": [{
            "id": "GCH-001", "scope": "载具移动机制", "status": "approved",
            "confirmation": {"confirmed": True, "revision": 10},
            "sourceFrameIds": ["F0001"],
        }],
        "reviewState": {"status": "detail_generation_pending", "previewRevision": None},
    }
    store = {job["id"]: job}
    submitted = []
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "job_path", lambda job_id: None)
    monkeypatch.setattr(server, "build_final_review_preview", lambda current, _path: {
        "interactionRevision": current["reviewModel"]["revision"],
        "gameplayRevision": 41,
        "directoryRevision": 1,
        "exportReady": False,
        "blockerIds": [
            "GCH-001:GAMEPLAY_DEPTH_INSUFFICIENT",
            "GCH-001:RULES_MISSING",
            "GCH-001:VERIFICATION_MISSING",
        ],
        "warningIds": [],
        "documentOrder": [],
    })

    class CapturingExecutor:
        def submit(self, task, *args):
            submitted.append((task, args))

    monkeypatch.setattr(server, "executor", CapturingExecutor())
    client = TestClient(server.app)

    first = client.post(
        f"/api/jobs/{job['id']}/gameplay-review-model/final-preview",
        json={"expectedRevision": 41, "apiBase": "https://vision.example/v1", "model": "vision-model", "apiKey": "configured-key"},
    )
    second = client.post(
        f"/api/jobs/{job['id']}/gameplay-review-model/final-preview",
        json={"expectedRevision": 41},
    )

    assert first.status_code == 409
    assert second.status_code == 409
    assert "详细规则" in first.json()["detail"]
    assert submitted == []
    assert "gameplayReviewGeneration" not in store[job["id"]]
    assert store[job["id"]]["gameplayReviewModel"]["chapters"][0]["confirmation"] == {
        "confirmed": True, "revision": 10,
    }


def test_final_preview_never_uses_pending_detail_generation_as_document_body(monkeypatch):
    job = make_confirmed_job()
    job["gameplayReviewModel"] = {
        "revision": 8,
        "chapters": [{"id": "GCH-001", "status": "draft", "confirmation": {"confirmed": False}}],
        "reviewState": {"status": "detail_generation_pending", "previewRevision": None},
    }
    store = {job["id"]: job}
    submitted = []
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "build_final_review_preview", lambda *_args: {
        "exportReady": False, "blockerIds": ["GCH-001:RULES_MISSING"], "warningIds": [], "documentOrder": [],
    })
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)

    class CapturingExecutor:
        def submit(self, task, *args): submitted.append((task, args))

    monkeypatch.setattr(server, "executor", CapturingExecutor())
    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review-model/final-preview",
        json={"expectedRevision": 8, "apiBase": "https://vision.example/v1", "model": "vision-model", "apiKey": "configured-key"},
    )

    assert response.status_code == 409
    assert "详细规则" in response.json()["detail"]
    assert submitted == []


def test_final_preview_queues_confirmed_language_and_granularity_repairs(monkeypatch):
    job = make_confirmed_job()
    job["gameplayReviewModel"] = {
        "revision": 17,
        "chapters": [{
            "id": "GCH-001", "scope": "店铺收益", "status": "approved",
            "confirmation": {"confirmed": True, "revision": 17},
        }],
        "reviewState": {"status": "ready", "previewRevision": None},
    }
    store = {job["id"]: job}
    submitted = []
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)
    monkeypatch.setattr(server, "build_final_review_preview", lambda *_args: {
        "exportReady": False,
        "blockerIds": ["LANGUAGE_FILLER", "GRANULARITY_ATTRIBUTENARRATIVE_MISSING"],
        "warningIds": [], "documentOrder": [],
    })

    class CapturingExecutor:
        def submit(self, task, *args):
            submitted.append((task, args))

    monkeypatch.setattr(server, "executor", CapturingExecutor())
    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review-model/final-preview",
        json={"expectedRevision": 17, "apiBase": "https://vision.example/v1", "model": "vision-model", "apiKey": "configured-key"},
    )

    assert response.status_code == 200
    assert response.json()["autoCompletion"]["status"] == "queued"
    assert submitted[0][0] is server._generate_confirmed_gameplay_details
    assert store[job["id"]]["gameplayReviewGeneration"]["status"] == "queued"


def test_gameplay_model_routes_return_canonical_model_and_leave_interaction_unchanged(monkeypatch):
    client, job, store = _client_with_job(monkeypatch)
    job["gameplayReviewModel"] = build_gameplay_review_model(job, [{
        "scope": "combat", "claims": [{"text": "Attack", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
        "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"],
    }])
    before_interaction = deepcopy(job["reviewModel"])

    response = client.get(f"/api/jobs/{job['id']}/gameplay-review-model")
    changed = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/operations", json={
        "expectedRevision": 1, "operations": [{"type": "set_chapter_field", "chapterId": "GCH-001", "field": "scope", "value": "combat loop"}],
    })

    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert changed.status_code == 200
    assert changed.json()["revision"] == 2
    assert store[job["id"]]["reviewModel"] == before_interaction


def test_second_structure_confirmation_queues_detail_generation(monkeypatch):
    client, job, store = _client_with_job(monkeypatch)
    model = build_gameplay_review_model(job, [{
        "scope": "光点连线", "systemName": "光路编织", "subsystemName": "连接规则",
        "claims": [{"text": "拖动光点", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
        "mechanism": {"type": "custom"}, "parameters": {}, "dependencies": [],
        "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"],
    }])
    model["reviewState"].update({"structurePhase": "mechanisms", "status": "mechanism_directory_review", "depthContractVersion": 1})
    job["gameplayReviewModel"] = model
    monkeypatch.setattr(server, "job_path", lambda job_id: None)
    runtime_args = []
    monkeypatch.setattr(server, "_runtime_ai_config", lambda *args: runtime_args.append(args) or {"apiBase": "local", "model": "vision", "apiKey": "key"})
    monkeypatch.setattr(server, "generate_gameplay_details", lambda current, confirmed, _path, _config, _progress: {
        **confirmed, "reviewState": {**confirmed["reviewState"], "status": "chapter_review", "structurePhase": "detailed"},
    })

    class Immediate:
        def submit(self, task, *args):
            task(*args)

    monkeypatch.setattr(server, "executor", Immediate())

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/confirm-directory", json={
        "expectedRevision": model["revision"], "apiBase": "https://vision.example/v1", "model": "vision-pro", "apiKey": "secret",
    })

    assert response.status_code == 200
    assert store[job["id"]]["gameplayReviewModel"]["reviewState"]["status"] == "chapter_review"
    assert store[job["id"]]["gameplayReviewGeneration"]["status"] == "completed"
    assert runtime_args == [("https://vision.example/v1", "vision-pro", "secret")]
    stale = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/undo", json={"expectedRevision": 1})
    assert stale.status_code == 409
    assert stale.json()["detail"] == {"currentRevision": 2}
    assert client.post(f"/api/jobs/{job['id']}/gameplay-review-model/operations", json={"expectedRevision": 2, "operations": [{"type": "nope"}]}).status_code == 400


def test_gameplay_model_api_reopen_is_idempotent_and_rejects_nested_ids(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)
    job["gameplayReviewModel"] = build_gameplay_review_model(job, [{
        "scope": "combat", "claims": [{"id": "GCL-001", "text": "Attack", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
        "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"],
    }])
    model = job["gameplayReviewModel"]
    model["chapters"][0].update(status="chapter_review", confirmation={"confirmed": False, "revision": None})
    model["reviewState"]["previewRevision"] = None
    model["editHistory"] = [{"undo": [], "redo": [{"kept": True}]}]

    reopened = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/reopen-chapter", json={"chapterId": "GCH-001", "expectedRevision": 1})
    malformed = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/operations", json={
        "expectedRevision": 1, "operations": [{"type": "upsert_claim", "chapterId": "GCH-001", "claim": {"id": "bad", "text": "bad", "sourceType": "material", "sourceFrameIds": ["F0001"]}}],
    })
    duplicate = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/operations", json={
        "expectedRevision": 1, "operations": [{"type": "add_chapter", "chapter": {"scope": "new", "claims": [{"id": "GCL-001", "text": "duplicate", "sourceType": "material", "sourceFrameIds": ["F0001"]}], "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"]}}],
    })

    assert reopened.status_code == 200
    assert reopened.json()["revision"] == 1
    assert reopened.json()["editHistory"][0]["redo"] == [{"kept": True}]
    assert malformed.status_code == 400
    assert duplicate.status_code == 400


def test_gameplay_confirm_api_persists_a_conditional_decision(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)
    job["gameplayReviewModel"] = build_gameplay_review_model(job, [{
        "scope": "combat", "claims": [{"text": "Attack", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
        "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": ["动画待确认"], "sourceFrameIds": ["F0001"],
    }])
    job["gameplayReviewModel"]["chapters"][0]["parameters"] = {
        field: {"type": "text", "unit": "n/a", "range": "one", "source": "F0001"}
        for field in required_parameter_fields("core_loop")
    }

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/confirm-chapter", json={"chapterId": "GCH-001", "expectedRevision": 1, "decision": "conditional"})

    assert response.status_code == 200
    assert response.json()["chapters"][0]["confirmation"]["decision"] == "conditional"


def test_gameplay_confirm_api_persists_rejected_decision_for_incomplete_chapter(monkeypatch):
    client, job, _ = _client_with_job(monkeypatch)
    job["gameplayReviewModel"] = build_gameplay_review_model(job, [{
        "scope": "combat", "claims": [], "mechanism": {"type": "core_loop"}, "parameters": {},
        "dependencies": [], "acceptanceCases": [], "unknowns": ["need evidence"], "sourceFrameIds": ["F0001"],
    }])

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/confirm-chapter", json={"chapterId": "GCH-001", "expectedRevision": 1, "decision": "rejected"})

    assert response.status_code == 200
    assert response.json()["chapters"][0]["status"] == "rejected"
    assert response.json()["chapters"][0]["confirmation"]["decision"] == "rejected"
