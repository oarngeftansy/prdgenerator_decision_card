from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import server
from backend.gameplay_review_model import build_gameplay_review_model
from tests.review_fixtures import make_image_job


def _context_job(tmp_path):
    job = make_image_job()
    trusted = server._runtime_ai_config("", "", "")
    job["runtimeProfile"] = {"apiBase": trusted["apiBase"], "model": trusted["model"]}
    job["gameplayReviewModel"] = build_gameplay_review_model(job, [{
        "scope": "combat", "claims": [{"text": "attack", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
        "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [],
        "unknowns": [], "sourceFrameIds": ["F0001"],
    }])
    (tmp_path / "frames").mkdir()
    (tmp_path / "auxiliary").mkdir()
    (tmp_path / "frames" / "F0001.jpg").write_bytes(b"screenshot")
    (tmp_path / "auxiliary" / "source.mp4").write_bytes(b"video")
    return job


def _client(monkeypatch, tmp_path):
    job = _context_job(tmp_path)
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server, "job_path", lambda _job_id: tmp_path)
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    return TestClient(server.app, raise_server_exceptions=False), job, store


def test_context_endpoint_persists_only_completed_context_and_stales_affected_chapter(monkeypatch, tmp_path):
    client, job, store = _client(monkeypatch, tmp_path)
    model = job["gameplayReviewModel"]
    model["chapters"][0].update(status="approved", confirmation={"confirmed": True, "revision": 1})
    model["diagrams"] = [{"id": "GDI-001", "chapterIds": ["GCH-001"], "status": "ready"}]
    before_interaction = deepcopy(job.get("reviewModel"))
    monkeypatch.setattr(server, "analyze_context_window", lambda **_kwargs: {
        "status": "completed", "matchedTime": 4.0, "radius": 2.0, "evidenceTimestamps": [2.0, 4.0, 6.0],
        "facts": {"trigger": {"closed": True, "observation": "tap attack"}}, "confidence": 0.9,
    })

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context", json={
        "expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["trigger"],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert set(body) == {
        "id", "chapterId", "anchorFrameId", "matchedTime", "radius", "evidenceTimestamps",
        "facts", "confidence", "status", "anchorAuthority", "observationAuthority",
    }
    assert body["anchorAuthority"] == "visual_match"
    assert body["observationAuthority"] == "observed_unreviewed"
    assert body["id"] == "GCW-001"
    assert store[job["id"]]["gameplayReviewModel"]["revision"] == 2
    assert store[job["id"]]["gameplayReviewModel"]["chapters"][0]["status"] == "chapter_review"
    assert store[job["id"]]["gameplayReviewModel"]["diagrams"][0]["status"] == "stale"
    assert store[job["id"]].get("reviewModel") == before_interaction


def test_context_endpoint_validates_revision_fields_and_anchor_ownership(monkeypatch, tmp_path):
    client, job, _ = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(server, "analyze_context_window", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")))
    url = f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context"

    assert client.post(url, json={"expectedRevision": 0, "anchorFrameId": "F0001", "missingFields": ["trigger"]}).status_code == 409
    assert client.post(url, json={"expectedRevision": 1, "anchorFrameId": "F0002", "missingFields": ["trigger"]}).status_code == 400
    assert client.post(url, json={"expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["unknown"]}).status_code == 400
    assert client.post(url, json={"expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": [{}]}).status_code == 400


def test_context_endpoint_uses_matching_trusted_server_profile(monkeypatch, tmp_path):
    client, job, store = _client(monkeypatch, tmp_path)
    job["runtimeProfile"] = {"apiBase": "https://trusted.example/v1", "model": "trusted-vision"}
    captured = {}
    monkeypatch.setattr(server, "_runtime_ai_config", lambda *_args: {
        "apiBase": "https://trusted.example/v1", "model": "trusted-vision", "apiKey": "server-secret",
    })
    monkeypatch.setattr(server, "analyze_context_window", lambda **kwargs: captured.update(kwargs) or {
        "status": "completed", "matchedTime": 4.0, "radius": 2.0, "evidenceTimestamps": [4.0],
        "facts": {"trigger": {"closed": True, "observation": "tap"}}, "confidence": 0.9,
    })

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context", json={
        "expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["trigger"],
    })

    assert response.status_code == 200
    assert captured["config"]["apiKey"] == "server-secret"
    assert "server-secret" not in response.text
    assert "server-secret" not in str(store[job["id"]])


@pytest.mark.parametrize("profile", [
    {"apiBase": "https://attacker.example/v1", "model": "trusted-vision"},
    {"apiBase": "https://trusted.example/v1", "model": "other-model"},
])
def test_context_endpoint_rejects_untrusted_profile_without_model_call_or_key_leak(monkeypatch, tmp_path, profile):
    client, job, store = _client(monkeypatch, tmp_path)
    job["runtimeProfile"] = profile
    monkeypatch.setattr(server, "_runtime_ai_config", lambda *_args: {
        "apiBase": "https://trusted.example/v1", "model": "trusted-vision", "apiKey": "server-secret",
    })
    called = []
    monkeypatch.setattr(server, "analyze_context_window", lambda **_kwargs: called.append(True))

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context", json={
        "expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["trigger"],
    })

    assert response.status_code == 400
    assert called == []
    assert "server-secret" not in response.text
    assert "server-secret" not in str(store[job["id"]])


def test_context_analysis_runs_outside_storage_mutation(monkeypatch, tmp_path):
    client, job, store = _client(monkeypatch, tmp_path)
    inside_mutation = False

    def mutate(job_id, mutation):
        nonlocal inside_mutation
        inside_mutation = True
        try:
            return mutation(store[job_id])
        finally:
            inside_mutation = False

    monkeypatch.setattr(server.storage, "mutate_job", mutate)
    monkeypatch.setattr(server, "analyze_context_window", lambda **_kwargs: {
        "status": "failed" if inside_mutation else "completed", "matchedTime": 4.0, "radius": 2.0,
        "evidenceTimestamps": [4.0], "facts": {"trigger": {"closed": True, "observation": "tap"}}, "confidence": 0.9,
    })

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context", json={
        "expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["trigger"],
    })

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_context_persistence_rechecks_revision_after_analysis(monkeypatch, tmp_path):
    client, job, store = _client(monkeypatch, tmp_path)

    def analyze(**_kwargs):
        store[job["id"]]["gameplayReviewModel"]["revision"] = 2
        return {
            "status": "completed", "matchedTime": 4.0, "radius": 2.0, "evidenceTimestamps": [4.0],
            "facts": {"trigger": {"closed": True, "observation": "tap"}}, "confidence": 0.9,
        }

    monkeypatch.setattr(server, "analyze_context_window", analyze)

    response = client.post(f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context", json={
        "expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["trigger"],
    })

    assert response.status_code == 409
    assert response.json()["detail"] == {"currentRevision": 2}
    assert store[job["id"]]["gameplayReviewModel"]["contextWindows"] == []


def test_context_success_is_an_independent_undo_boundary(monkeypatch, tmp_path):
    client, job, store = _client(monkeypatch, tmp_path)
    model = job["gameplayReviewModel"]
    model["editHistory"] = [{"undo": [], "redo": [{"old": "redo"}]}]
    monkeypatch.setattr(server, "analyze_context_window", lambda **_kwargs: {
        "status": "completed", "matchedTime": 4.0, "radius": 2.0, "evidenceTimestamps": [4.0],
        "facts": {"trigger": {"closed": True, "observation": "tap"}}, "confidence": 0.9,
    })

    created = client.post(f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context", json={
        "expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["trigger"],
    })
    redo_after_create = deepcopy(store[job["id"]]["gameplayReviewModel"]["editHistory"][0]["redo"])
    undone = client.post(f"/api/jobs/{job['id']}/gameplay-review-model/undo", json={"expectedRevision": 2})

    assert created.status_code == 200
    assert redo_after_create == []
    assert undone.status_code == 200
    assert undone.json()["revision"] == 3
    assert undone.json()["contextWindows"] == []


def test_context_endpoint_keeps_failed_or_unlocated_attempt_retryable(monkeypatch, tmp_path):
    client, job, store = _client(monkeypatch, tmp_path)
    url = f"/api/jobs/{job['id']}/gameplay-review/chapters/GCH-001/context"
    for result in ({"status": "needs_planner_location"}, {"status": "failed"}):
        monkeypatch.setattr(server, "analyze_context_window", lambda **_kwargs: result)
        response = client.post(url, json={"expectedRevision": 1, "anchorFrameId": "F0001", "missingFields": ["trigger"]})
        assert response.status_code == 200
        assert response.json() == {"status": result["status"]}
        assert store[job["id"]]["gameplayReviewModel"]["revision"] == 1
        assert store[job["id"]]["gameplayReviewModel"]["contextWindows"] == []


def test_analyze_context_uses_two_seconds_then_stops_when_requested_facts_close(monkeypatch, tmp_path):
    from backend import auxiliary_video

    calls = []
    monkeypatch.setattr(auxiliary_video, "match_screenshot_to_video", lambda *_args: {"status": "matched", "matchedTime": 12.0, "confidence": 0.9})
    monkeypatch.setattr(auxiliary_video, "_sample_context", lambda *_args, radius: calls.append(radius) or [{"timestamp": 12.0, "path": tmp_path / "x.jpg"}])
    monkeypatch.setattr(auxiliary_video, "_analyze_context_samples", lambda *_args: {"trigger": "tap"})

    result = auxiliary_video.analyze_context_window("GCH-001", "F0001", tmp_path / "shot.jpg", tmp_path / "source.mp4", ["trigger"], tmp_path, {})

    assert result["status"] == "completed"
    assert result["radius"] == 2.0
    assert calls == [2.0]


def test_analyze_context_expands_only_until_last_radius_and_never_calls_global_inspection(monkeypatch, tmp_path):
    from backend import auxiliary_video

    calls, model_calls = [], []
    monkeypatch.setattr(auxiliary_video, "inspect_video", lambda *_args: (_ for _ in ()).throw(AssertionError("global scan")), raising=False)
    monkeypatch.setattr(auxiliary_video, "match_screenshot_to_video", lambda *_args: {"status": "matched", "matchedTime": 3.0, "confidence": 0.8})
    monkeypatch.setattr(auxiliary_video, "_sample_context", lambda *_args, radius: calls.append(radius) or [{"timestamp": radius, "path": tmp_path / f"{radius}.jpg"}])
    monkeypatch.setattr(auxiliary_video, "_analyze_context_samples", lambda *_args: model_calls.append(1) or {})

    result = auxiliary_video.analyze_context_window("GCH-001", "F0001", tmp_path / "shot.jpg", tmp_path / "source.mp4", ["trigger"], tmp_path, {})

    assert result == {"status": "failed"}
    assert calls == [2.0, 5.0, 10.0]
    assert len(model_calls) == 3


def _schema_context(monkeypatch, tmp_path, answers, prompts=None):
    from backend import auxiliary_video

    calls = []
    monkeypatch.setattr(auxiliary_video, "match_screenshot_to_video", lambda *_args: {"status": "matched", "matchedTime": 3.0, "confidence": 0.8})
    monkeypatch.setattr(auxiliary_video, "_sample_context", lambda *_args, radius: calls.append(radius) or [{"timestamp": radius, "path": tmp_path / "x.jpg"}])
    monkeypatch.setattr(auxiliary_video, "_client", lambda _config: object())

    def call(_client, _model, prompt, _images, **_kwargs):
        if prompts is not None:
            prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(auxiliary_video, "_call", call)
    result = auxiliary_video.analyze_context_window("GCH-001", "F0001", Path("shot.jpg"), Path("video.mp4"), ["trigger"], tmp_path, {})
    return result, calls


@pytest.mark.parametrize("uncertain", ["insufficient evidence", "unable to determine"])
def test_closed_false_uncertainty_expands_from_two_to_five_seconds(monkeypatch, tmp_path, uncertain):
    answers = iter((
        {"trigger": {"closed": False, "observation": uncertain}},
        {"trigger": {"closed": True, "observation": "tap attack"}},
    ))

    result, calls = _schema_context(monkeypatch, tmp_path, answers)

    assert result["status"] == "completed"
    assert result["radius"] == 5.0
    assert result["facts"] == {"trigger": "tap attack"}
    assert calls == [2.0, 5.0]


def test_closed_true_specific_observation_is_accepted_and_persisted_as_string(monkeypatch, tmp_path):
    prompts = []
    result, calls = _schema_context(monkeypatch, tmp_path, iter((
        {"trigger": {"closed": True, "observation": "tap attack"}},
    )), prompts)

    assert result["status"] == "completed"
    assert result["facts"] == {"trigger": "tap attack"}
    assert calls == [2.0]
    assert "closed" in prompts[0] and "observation" in prompts[0]


@pytest.mark.parametrize("first", [
    {"trigger": "tap attack"},
    [{"trigger": {"closed": True, "observation": "tap attack"}}],
    {"trigger": {"closed": True, "observation": "tap attack", "uncertainty": "maybe"}},
    {"trigger": {"closed": True, "observation": ""}},
])
def test_legacy_or_nonconforming_schema_does_not_close_two_second_window(monkeypatch, tmp_path, first):
    result, calls = _schema_context(monkeypatch, tmp_path, iter((
        first,
        {"trigger": {"closed": True, "observation": "tap attack"}},
    )))

    assert result["status"] == "completed"
    assert result["radius"] == 5.0
    assert result["facts"] == {"trigger": "tap attack"}
    assert calls == [2.0, 5.0]


def test_failed_context_analysis_removes_attempt_samples(monkeypatch, tmp_path):
    from backend import auxiliary_video

    written = []
    monkeypatch.setattr(auxiliary_video, "match_screenshot_to_video", lambda *_args: {"status": "matched", "matchedTime": 3.0, "confidence": 0.8})

    def sample(_video_path, attempt_dir, _matched_time, *, radius):
        path = attempt_dir / f"{radius}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"sample")
        written.append(path)
        return [{"timestamp": radius, "path": path}]

    monkeypatch.setattr(auxiliary_video, "_sample_context", sample)
    monkeypatch.setattr(auxiliary_video, "_analyze_context_samples", lambda *_args: (_ for _ in ()).throw(TimeoutError("slow")))

    result = auxiliary_video.analyze_context_window("GCH-001", "F0001", Path("shot.jpg"), Path("video.mp4"), ["trigger"], tmp_path, {})

    assert result == {"status": "failed"}
    assert written and all(not path.exists() for path in written)


def test_low_score_context_match_needs_location_without_model_call(monkeypatch, tmp_path):
    from backend import auxiliary_video

    monkeypatch.setattr(auxiliary_video, "match_screenshot_to_video", lambda *_args: {"status": "needs_planner_location"})
    monkeypatch.setattr(auxiliary_video, "_analyze_context_samples", lambda *_args: (_ for _ in ()).throw(AssertionError("model must not run")))

    assert auxiliary_video.analyze_context_window("GCH-001", "F0001", Path("shot.jpg"), Path("video.mp4"), ["trigger"], tmp_path, {}) == {"status": "needs_planner_location"}
