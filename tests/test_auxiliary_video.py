from backend import server
from tests.review_fixtures import make_image_job


def test_initial_screenshot_processing_passes_auxiliary_video_as_fallback_context(monkeypatch, tmp_path):
    job = make_image_job()
    job.update(checkpoint="frames-complete", status="queued")
    (tmp_path / "auxiliary").mkdir()
    (tmp_path / "auxiliary" / "source.mp4").write_bytes(b"video")
    job["auxiliaryVideo"] = {"filename": "source.mp4", "sourceUrl": "/artifacts/job-1/auxiliary/source.mp4"}
    captured = {}
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "job_path", lambda _job_id: tmp_path)
    monkeypatch.setattr(server, "update_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server.storage, "mutate_job", lambda _job_id, mutation: mutation(job))
    def analyze(*_args, **kwargs):
        captured.update(kwargs)
        return job["frames"], job["scenes"], {}
    monkeypatch.setattr(server, "analyze_video", analyze)
    monkeypatch.setattr(server, "ensure_review_model", lambda _job: {"quality": {"qualified": True}})
    monkeypatch.setattr(server, "_refresh_outputs", lambda _job: None)
    monkeypatch.setattr(server, "write_scene_specs", lambda *_args: {})

    server._process(job["id"], {})

    assert captured["auxiliary_video_path"] == tmp_path / "auxiliary" / "source.mp4"


def test_context_module_does_not_import_global_video_inspection():
    from backend import auxiliary_video

    assert "inspect_video" not in auxiliary_video.__dict__


def test_manual_timestamp_confirms_location_without_confirming_observation(monkeypatch, tmp_path):
    from backend import auxiliary_video

    monkeypatch.setattr(auxiliary_video, "_sample_context", lambda *_args, **_kwargs: [{"timestamp": 60.0, "path": tmp_path / "frame.jpg"}])
    monkeypatch.setattr(auxiliary_video, "_analyze_context_samples", lambda *_args, **_kwargs: {"process": "对象位置发生变化"})

    result = auxiliary_video.analyze_context_window(
        "C1", "F1", tmp_path / "anchor.jpg", tmp_path / "video.mp4", ["process"], tmp_path, {},
        manual_timestamp=60.0,
    )

    assert result["status"] == "completed"
    assert result["anchorAuthority"] == "planner_confirmed_location"
    assert result["observationAuthority"] == "observed_unreviewed"


def test_context_window_observation_enters_temporal_fact_chain():
    from backend.rule_intelligence_pipeline import build_rule_intelligence_projection

    result = build_rule_intelligence_projection(
        approved_data={"facts": [], "rules": [], "gaps": []}, chapters=[], context_windows=[{
            "id": "GCW-001", "chapterId": "C1", "anchorFrameId": "F1",
            "matchedTime": 10.0, "radius": 2.0, "evidenceTimestamps": [8.0, 10.0, 12.0],
            "facts": {"process": "对象位置发生变化"}, "confidence": .8,
            "anchorAuthority": "planner_confirmed_location",
        }],
    )

    fact = result["facts"][0]
    assert fact["sourceKind"] == "auxiliary_video"
    assert fact["observationMode"] == "temporal_context"
    assert fact["inferenceLevel"] == "observed"
    assert fact["reviewStatus"] == "unreviewed"
