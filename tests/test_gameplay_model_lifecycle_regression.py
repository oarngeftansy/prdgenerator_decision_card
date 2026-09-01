from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend import server
from backend.gameplay_review_model import ensure_gameplay_review_model
from backend.review_model import build_review_model
from tests.review_fixtures import make_confirmed_job, make_image_job


def _store(monkeypatch, job):
    records = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: records[job_id])
    monkeypatch.setattr(
        server.storage,
        "mutate_job",
        lambda job_id, mutation: mutation(records[job_id]),
    )
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)
    return records


@pytest.mark.parametrize("input_type", ["image_sequence", "video"])
def test_missing_gameplay_model_get_is_read_only_and_returns_approved_flow_state_skeleton(monkeypatch, input_type):
    job = make_confirmed_job()
    job["metadata"]["inputType"] = input_type
    original = deepcopy(job)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(
        server.storage,
        "mutate_job",
        lambda *_args: (_ for _ in ()).throw(AssertionError("GET must not write the job")),
    )
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)

    response = TestClient(server.app).get(f"/api/jobs/{job['id']}/gameplay-review-model")

    assert response.status_code == 200
    model = response.json()
    assert model["jobId"] == job["id"]
    assert model["interactionRevision"] == job["reviewModel"]["revision"]
    assert model["lifecycleState"] == "generation_required"
    assert model["reviewState"]["status"] == "generation_required"
    assert model["directory"]["status"] == "pending_generation"
    assert model["chapters"] == []
    assert model["contentState"] == "pending"
    assert model["deterministicSkeleton"]["source"] == "approved_flow_state"
    assert [item["sourceStageId"] for item in model["deterministicSkeleton"]["stages"]] == [
        stage["id"] for stage in job["reviewModel"]["stages"]
    ]
    assert job == original


def test_existing_job_payload_includes_pending_container_without_writing(monkeypatch, tmp_path):
    job = make_image_job()
    job["reviewModel"] = build_review_model(job)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(
        server.storage,
        "mutate_job",
        lambda *_args: (_ for _ in ()).throw(AssertionError("GET must not write the job")),
    )
    monkeypatch.setattr(server, "job_path", lambda _job_id: tmp_path)

    response = TestClient(server.app).get(f"/api/jobs/{job['id']}")

    assert response.status_code == 200
    assert response.json()["gameplayReviewModel"]["lifecycleState"] == "generation_required"


@pytest.mark.parametrize("input_type", ["image_sequence", "video"])
def test_new_project_initializes_deterministic_gameplay_skeleton_for_every_input_type(input_type):
    job = make_confirmed_job()
    job["metadata"]["inputType"] = input_type

    model = ensure_gameplay_review_model(job)

    assert job["gameplayReviewModel"] is model
    assert model["lifecycleState"] == "generation_required"
    assert model["chapters"] == []
    assert model["directory"]["entries"] == []
    assert model["deterministicSkeleton"]["inputType"] == input_type
    assert len(model["deterministicSkeleton"]["stages"]) == len(job["reviewModel"]["stages"])


def test_deterministic_skeleton_uses_only_approved_flow_and_state_fields():
    job = make_confirmed_job()
    job["reviewModel"]["componentStates"] = [
        {"id": "CST-001", "componentId": "CMP-001", "states": [{"name": "选中", "result": "高亮"}]},
    ]

    first = ensure_gameplay_review_model(deepcopy(job))["deterministicSkeleton"]
    second = ensure_gameplay_review_model(deepcopy(job))["deterministicSkeleton"]

    assert first == second
    assert first["componentStates"] == [
        {"sourceStateId": "CST-001", "componentId": "CMP-001", "states": [{"name": "选中", "result": "高亮"}]},
    ]
    assert all("claims" not in stage and "rules" not in stage for stage in first["stages"])


def test_existing_drafts_initialize_a_ready_model_with_the_same_deterministic_basis():
    job = make_confirmed_job()
    job["gameplayChapterDrafts"] = [{
        "scope": "已确认玩法",
        "sourceFrameIds": ["F0001"],
        "claims": [{"text": "已确认内容", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
    }]

    model = ensure_gameplay_review_model(job)

    assert model["lifecycleState"] == "ready"
    assert model["contentState"] == "ready"
    assert model["deterministicSkeleton"]["stages"]


def test_failed_initial_generation_preserves_recoverable_gameplay_container(monkeypatch):
    job = make_confirmed_job()
    records = _store(monkeypatch, job)
    monkeypatch.setattr(
        server,
        "generate_gameplay_structure",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("system failure")),
    )

    server._generate_gameplay_review(job["id"], {})

    saved = records[job["id"]]
    assert saved["gameplayReviewGeneration"]["status"] == "failed"
    assert saved["gameplayReviewGeneration"]["failureKind"] == "system"
    assert saved["gameplayReviewModel"]["lifecycleState"] == "generation_failed"
    assert saved["gameplayReviewModel"]["contentState"] == "failed"
    assert saved["gameplayReviewModel"]["reviewState"]["status"] == "generation_required"
    assert saved["gameplayReviewModel"]["chapters"] == []
    assert saved["gameplayReviewModel"]["deterministicSkeleton"]["stages"]


def test_gameplay_generation_deadline_expires_without_late_result_overwriting_recovery(monkeypatch):
    job = make_confirmed_job()
    preserved = deepcopy(ensure_gameplay_review_model(job))
    job["gameplayReviewGeneration"] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued gameplay review generation.",
        "generationId": "GEN-001",
        "startedAt": "2026-08-25T06:10:36+00:00",
        "deadlineAt": "2026-08-25T06:15:36+00:00",
    }
    records = _store(monkeypatch, job)

    def late_model(*_args, **_kwargs):
        server._expire_gameplay_generation(job["id"], "GEN-001")
        return {"contentModelVersion": 1, "chapters": [{"id": "LATE"}]}

    monkeypatch.setattr(server, "generate_gameplay_structure", late_model)

    server._generate_gameplay_review(job["id"], {}, "GEN-001")

    saved = records[job["id"]]
    assert saved["gameplayReviewGeneration"]["status"] == "failed"
    assert saved["gameplayReviewGeneration"]["failureKind"] == "network"
    assert "超时" in saved["gameplayReviewGeneration"]["error"]
    assert saved["gameplayReviewGeneration"]["finishedAt"]
    assert saved["gameplayReviewModel"]["chapters"] == preserved["chapters"]
    assert saved["gameplayReviewModel"]["contentState"] == "failed"


def test_gameplay_generation_timeout_waits_until_the_latest_inactivity_deadline(monkeypatch):
    job = make_confirmed_job()
    ensure_gameplay_review_model(job)
    job["gameplayReviewGeneration"] = {
        "status": "running",
        "progress": 42,
        "message": "Generating gameplay review.",
        "generationId": "GEN-ACTIVE",
        "startedAt": "2026-08-25T06:10:36+00:00",
        "lastProgressAt": "2099-08-25T06:14:36+00:00",
        "deadlineAt": "2099-08-25T06:15:36+00:00",
    }
    records = _store(monkeypatch, job)
    scheduled = []
    monkeypatch.setattr(
        server,
        "_schedule_gameplay_generation_timeout",
        lambda job_id, generation_id, delay_seconds=None: scheduled.append((job_id, generation_id, delay_seconds)),
    )

    server._expire_gameplay_generation(job["id"], "GEN-ACTIVE")

    saved = records[job["id"]]
    assert saved["gameplayReviewGeneration"]["status"] == "running"
    assert saved["gameplayReviewModel"]["contentState"] != "failed"
    assert scheduled and scheduled[0][0:2] == (job["id"], "GEN-ACTIVE")
    assert scheduled[0][2] > 0


def test_generation_progress_refreshes_the_inactivity_deadline():
    previous = {
        "progress": 21,
        "lastProgressAt": "2026-08-25T06:10:36+00:00",
        "deadlineAt": "2026-08-25T06:15:36+00:00",
    }

    refreshed = server._refresh_gameplay_generation_activity(previous, 28, "已补全 4/13 个玩法机制")
    current = {
        **previous,
        **refreshed,
        "progress": 28,
        "logs": [{"progress": 28, "message": "已补全 4/13 个玩法机制"}],
    }
    unchanged = server._refresh_gameplay_generation_activity(current, 28, "已补全 4/13 个玩法机制")

    assert refreshed["lastProgressAt"] != previous["lastProgressAt"]
    assert refreshed["deadlineAt"] != previous["deadlineAt"]
    assert unchanged == {}


def test_public_running_generation_exposes_safe_timing_and_phase():
    public = server._public_gameplay_review_generation({
        "status": "running",
        "progress": 10,
        "message": "Generating gameplay review.",
        "phase": "requesting_model",
        "startedAt": "2026-08-25T06:10:36+00:00",
        "deadlineAt": "2026-08-25T06:15:36+00:00",
        "generationId": "PRIVATE-GENERATION-ID",
    })

    assert public["phase"] == "requesting_model"
    assert public["startedAt"] == "2026-08-25T06:10:36+00:00"
    assert public["deadlineAt"] == "2026-08-25T06:15:36+00:00"
    assert "generationId" not in public


@pytest.mark.parametrize(
    ("technical", "planner_issue"),
    [
        ("invalid detailed gameplay model: GCH-003:FLOW_CHAIN_CAUSALITY_MISSING", "详细玩法模型字段、引用或因果链不完整"),
        ("lead planner output audit failed: GCH-004:MECHANISM_CLOSURE", "主策完整性检查未通过"),
        ("gameplay detail generation changed the confirmed structure", "生成结果改动了已确认目录"),
    ],
)
def test_quality_failure_exposes_a_safe_actionable_reason_without_internal_codes(technical, planner_issue):
    exc = server.GameplayAnalysisQualityError(technical)

    issues = server._safe_gameplay_generation_quality_issues(exc)
    public = server._public_gameplay_review_generation({
        "status": "failed",
        "progress": 90,
        "message": "Gameplay review generation failed. Please retry.",
        "error": "视觉模型返回内容不符合玩法章节要求",
        "failureKind": "quality",
        "qualityIssues": issues,
    })

    assert public["qualityIssues"] == [planner_issue]
    assert "GCH-" not in public["qualityIssues"][0]


def test_lead_planner_failure_exposes_safe_chapter_level_reasons_without_internal_codes():
    exc = server.GameplayAnalysisQualityError(
        "lead planner output audit failed: "
        "GCH-004:LEAD_PLANNER_RULE_DEPTH_INSUFFICIENT; "
        "GCH-007:LANGUAGE_PRESENTATION_IN_PROSE; "
        "GCH-009:LANGUAGE_REVIEW_META"
    )

    issues = server._safe_gameplay_generation_quality_issues(exc)

    assert issues == [
        "主策完整性检查未通过",
        "第4章缺少可审核的规则正文或明确待确认选项",
        "第7章把纯画面表现写进了玩法正文",
        "第9章混入了审核过程或生成状态说明",
    ]
    assert all("GCH-" not in item for item in issues)
    assert all("LANGUAGE_" not in item for item in issues)


def test_gameplay_retry_rejects_missing_api_key_before_queueing(monkeypatch):
    job = make_confirmed_job()
    model = ensure_gameplay_review_model(job)
    model["lifecycleState"] = "generation_failed"
    model["contentState"] = "failed"
    job["gameplayReviewGeneration"] = {
        "status": "failed",
        "progress": 0,
        "message": "Gameplay review generation failed. Please retry.",
        "error": "玩法章节生成失败",
        "failureKind": "system",
    }
    original = deepcopy(job)
    _store(monkeypatch, job)
    monkeypatch.setattr(server, "_configured_value", lambda _key, _fallback: "")

    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review/generate",
        data={"api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen3.6-plus", "api_key": ""},
    )

    assert response.status_code == 400
    assert "API Key" in response.json()["detail"]
    assert job == original


def test_failed_regeneration_preserves_last_valid_gameplay_version(monkeypatch):
    job = make_confirmed_job()
    job["gameplayChapterDrafts"] = [{
        "scope": "已确认玩法",
        "sourceFrameIds": ["F0001"],
        "claims": [{"text": "已确认内容", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
    }]
    valid = ensure_gameplay_review_model(job)
    valid["lifecycleState"] = "ready"
    valid["contentState"] = "ready"
    preserved = deepcopy(valid)
    records = _store(monkeypatch, job)
    monkeypatch.setattr(
        server,
        "generate_gameplay_structure",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("system failure")),
    )

    server._generate_gameplay_review(job["id"], {})

    saved = records[job["id"]]["gameplayReviewModel"]
    assert saved["chapters"] == preserved["chapters"]
    assert saved["directory"] == preserved["directory"]
    assert saved["revision"] == preserved["revision"]
    assert saved["lifecycleState"] == "ready"
    assert saved["contentState"] == "failed"
    assert saved["lastValidRevision"] == preserved["revision"]


def test_existing_model_get_never_persists_lazy_migrations(monkeypatch):
    job = make_confirmed_job()
    job["gameplayReviewModel"] = {
        "schemaVersion": "1.0", "standard": "GVE16", "revision": 1,
        "jobId": job["id"], "interactionRevision": 1, "chapters": [],
    }
    original = deepcopy(job)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(
        server.storage,
        "mutate_job",
        lambda *_args: (_ for _ in ()).throw(AssertionError("GET must not persist lazy migrations")),
    )
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)

    response = TestClient(server.app).get(f"/api/jobs/{job['id']}/gameplay-review-model")

    assert response.status_code == 200
    assert response.json()["deterministicSkeleton"]["stages"]
    assert job == original


def test_gameplay_get_returns_recovery_skeleton_when_lazy_normalization_raises(monkeypatch):
    job = make_confirmed_job()
    original = deepcopy(job)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)
    monkeypatch.setattr(
        server,
        "ensure_gameplay_review_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("legacy normalization failed")),
    )

    response = TestClient(server.app).get(f"/api/jobs/{job['id']}/gameplay-review-model")

    assert response.status_code == 200
    assert response.json()["lifecycleState"] == "generation_required"
    assert response.json()["deterministicSkeleton"]["stages"]
    assert job == original


@pytest.mark.parametrize("archived", [False, True])
def test_aggregate_job_get_is_read_only_and_recovers_when_gameplay_normalization_raises(monkeypatch, archived):
    job = make_confirmed_job()
    job["archived"] = archived
    original = deepcopy(job)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)
    monkeypatch.setattr(server, "_refresh_reference_board_statuses", lambda *_args: False)
    monkeypatch.setattr(
        server.storage,
        "mutate_job",
        lambda *_args: (_ for _ in ()).throw(AssertionError("GET must not persist lazy migrations")),
    )
    monkeypatch.setattr(
        server,
        "ensure_gameplay_review_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("legacy normalization failed")),
    )

    response = TestClient(server.app).get(f"/api/jobs/{job['id']}")

    assert response.status_code == 200
    assert response.json()["gameplayReviewModel"]["deterministicSkeleton"]["stages"]
    assert job == original


def test_gameplay_get_fallback_survives_malformed_legacy_approval_metadata(monkeypatch):
    job = make_confirmed_job()
    job["reviewModel"]["reviewState"]["confirmedStageIds"] = []
    job["reviewModel"]["stages"][0]["confirmation"] = "legacy-bad-value"
    job["reviewModel"]["transitions"][0]["confirmation"] = "legacy-bad-value"
    job["gameplayReviewGeneration"] = "legacy-bad-value"
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "job_path", lambda _job_id: None)
    monkeypatch.setattr(
        server,
        "ensure_gameplay_review_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("legacy normalization failed")),
    )

    response = TestClient(server.app).get(f"/api/jobs/{job['id']}/gameplay-review-model")

    assert response.status_code == 200
    skeleton = response.json()["deterministicSkeleton"]
    assert [item["sourceStageId"] for item in skeleton["stages"]] == ["STG-002"]
    assert [item["sourceTransitionId"] for item in skeleton["transitions"]] == ["TRN-002"]


def test_interaction_finalize_binds_the_gameplay_container_before_generation():
    source = open(server.__file__, encoding="utf-8").read()
    finalize = source[source.index("def finalize(current"):source.index("storage.mutate_job(job_id, finalize)")]

    assert "ensure_gameplay_review_model(current)" in finalize


def test_failed_pending_container_can_retry_before_interaction_gate_is_ready(monkeypatch):
    job = make_image_job()
    job["reviewModel"] = build_review_model(job)
    job["gameplayReviewModel"] = ensure_gameplay_review_model(deepcopy(job))
    job["gameplayReviewGeneration"] = {
        "status": "failed",
        "progress": 0,
        "message": "Gameplay review generation failed. Please retry.",
        "error": "玩法章节生成失败",
    }
    records = _store(monkeypatch, job)
    submitted = []

    class CapturingExecutor:
        def submit(self, task, *args):
            submitted.append((task, args))

    monkeypatch.setattr(server, "executor", CapturingExecutor())

    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review/generate",
        data={"api_key": "test-key"},
    )

    assert response.status_code == 202
    assert records[job["id"]]["gameplayReviewGeneration"]["status"] == "queued"
    assert submitted[0][0] is server._generate_gameplay_review


def test_regeneration_marks_content_pending_without_discarding_last_valid_version(monkeypatch):
    job = make_confirmed_job()
    job["gameplayChapterDrafts"] = [{
        "scope": "已确认玩法",
        "sourceFrameIds": ["F0001"],
        "claims": [{"text": "已确认内容", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
    }]
    valid = ensure_gameplay_review_model(job)
    valid["lifecycleState"] = "ready"
    valid["contentState"] = "ready"
    preserved = deepcopy(valid["chapters"])
    records = _store(monkeypatch, job)
    monkeypatch.setattr(server, "review_gate", lambda _model: {"exportReady": True})
    monkeypatch.setattr(server.executor, "submit", lambda *_args: None)

    response = TestClient(server.app).post(
        f"/api/jobs/{job['id']}/gameplay-review/generate",
        data={"force": "true", "api_key": "test-key"},
    )

    assert response.status_code == 202
    model = records[job["id"]]["gameplayReviewModel"]
    assert model["contentState"] == "pending"
    assert model["lastValidRevision"] == valid["revision"]
    assert model["chapters"] == preserved
