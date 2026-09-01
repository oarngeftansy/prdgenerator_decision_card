from pathlib import Path

import pytest
from fastapi import HTTPException

from backend import server, storage


def _make_job(tmp_path: Path, monkeypatch, archived=False):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    job = storage.new_job({"mode": "gameplay", "projectName": "局部分析", "scope": ""})
    (storage.job_path(job["id"]) / "source.mp4").write_bytes(b"video")
    job.update(
        archived=archived,
        status="completed",
        video={"duration": 10.0, "filename": "source.mp4"},
        frames=[
            {
                "id": "F0001", "timestamp": 2.0, "sceneId": 0, "confirmed": False,
                "structure": {"regionCounts": {}, "elements": []},
                "analysis": {"what": "旧结论", "userAction": "旧操作", "confidence": "低"},
                "lastModelAnalysis": {"what": "旧结论", "userAction": "旧操作", "confidence": "低"},
            },
            {
                "id": "F0002", "timestamp": 5.0, "sceneId": 0, "confirmed": False,
                "structure": {"regionCounts": {}, "elements": []},
                "analysis": {"what": "不应改变", "userAction": "等待", "confidence": "高"},
            },
        ],
        scenes=[{
            "id": 0, "start": 0.0, "end": 10.0, "frameIds": ["F0001", "F0002"],
            "analysis": {"title": "场景", "summary": "摘要", "entryCondition": "进入", "exitCondition": "退出"},
        }],
        componentTracks=[],
        analysisSummary={"modelEnabled": True},
    )
    storage.save_job(job)
    return job


def test_review_marks_only_changed_model_fields_as_human_edits(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)

    server.save_review(job["id"], {"frames": {"F0001": {
        "confirmed": False,
        "analysis": {"what": "策划修正", "userAction": "旧操作", "confidence": "低"},
    }}})

    frame = storage.load_job(job["id"])["frames"][0]
    assert frame["humanEditedFields"] == ["what"]


def test_review_uses_explicit_browser_edit_list_without_guessing(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)

    server.save_review(job["id"], {"frames": {"F0001": {
        "confirmed": False,
        "humanEditedFields": ["userAction"],
        "analysis": {"what": "前端格式化的旧结论", "userAction": "策划点击", "confidence": "低"},
    }}})

    frame = storage.load_job(job["id"])["frames"][0]
    assert frame["humanEditedFields"] == ["userAction"]


def test_public_job_does_not_expose_local_technical_errors():
    job = {"frames": [{"supplementalEvidence": {"status": "failed", "message": "可重试", "technicalError": "secret stack"}}]}
    public = server._public_job(job)
    assert public["frames"][0]["supplementalEvidence"] == {"status": "failed", "message": "可重试"}


def test_local_worker_changes_only_target_and_preserves_human_field(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)
    original_scene = job["scenes"]
    original_other = job["frames"][1]
    job["frames"][0]["humanEditedFields"] = ["userAction"]
    storage.save_job(job)
    monkeypatch.setattr(server, "extract_supplemental", lambda *args: [{"timestamp": 1.0, "imageUrl": "/a.jpg"}, {"timestamp": 2.0, "imageUrl": "/b.jpg"}])
    monkeypatch.setattr(server, "analyze_local_evidence", lambda *args: {
        "what": "新结论", "userAction": "新操作", "confidence": "高", "attentionSignals": []
    })

    server._reanalyze_frame(job["id"], "F0001", {"apiBase": "local", "model": "vision", "apiKey": "key"})

    result = storage.load_job(job["id"])
    target = result["frames"][0]
    assert len(result["frames"]) == 2
    assert result["frames"][1] == original_other
    assert result["scenes"] == original_scene
    assert target["analysis"]["what"] == "新结论"
    assert target["analysis"]["userAction"] == "旧操作"
    assert target["analysisSuggestion"] == {"userAction": "新操作"}
    assert target["supplementalEvidence"]["status"] == "ready"


def test_accept_and_reject_suggestions_are_persisted(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)
    job["frames"][0]["analysisSuggestion"] = {"what": "建议结论", "userAction": "建议操作"}
    storage.save_job(job)

    server.accept_frame_suggestion(job["id"], "F0001", "what")
    server.reject_frame_suggestion(job["id"], "F0001", "userAction")

    frame = storage.load_job(job["id"])["frames"][0]
    assert frame["analysis"]["what"] == "建议结论"
    assert frame["humanEditedFields"] == ["what"]
    assert frame["analysisSuggestion"] == {}


def test_start_rejects_archived_and_duplicate_frame_jobs(tmp_path, monkeypatch):
    archived = _make_job(tmp_path, monkeypatch, archived=True)
    with pytest.raises(HTTPException) as archived_error:
        server.supplement_and_reanalyze_frame(archived["id"], "F0001")
    assert archived_error.value.status_code == 409

    active = storage.load_job(archived["id"])
    active["archived"] = False
    active["frames"][0]["supplementalEvidence"] = {"status": "analyzing"}
    storage.save_job(active)
    with pytest.raises(HTTPException) as duplicate_error:
        server.supplement_and_reanalyze_frame(active["id"], "F0001")
    assert duplicate_error.value.status_code == 409


def test_archived_jobs_reject_all_legacy_review_and_suggestion_writes(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch, archived=True)
    job["frames"][0]["analysisSuggestion"] = {"what": "建议"}
    storage.save_job(job)

    with pytest.raises(HTTPException) as review_error:
        server.save_review(job["id"], {"frames": {}})
    with pytest.raises(HTTPException) as suggestion_error:
        server.accept_frame_suggestion(job["id"], "F0001", "what")

    assert review_error.value.status_code == 409
    assert suggestion_error.value.status_code == 409
