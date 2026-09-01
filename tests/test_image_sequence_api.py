import io
import json

from fastapi import UploadFile
from PIL import Image

from backend import image_sequence, server, storage


def image_upload(name: str) -> UploadFile:
    output = io.BytesIO()
    Image.new("RGB", (12, 20), (20, 50, 90)).save(output, format="PNG")
    return UploadFile(filename=name, file=io.BytesIO(output.getvalue()), headers={"content-type": "image/png"})


def video_upload(name: str = "source.mp4") -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(b"video"), headers={"content-type": "video/mp4"})


def manifest(names):
    return json.dumps([
        {"clientId": f"IMG{index:03d}", "originalName": name, "order": index}
        for index, name in enumerate(names, 1)
    ])


def create_args():
    return {
        "mode": "interaction", "project_name": "截图任务", "scope": "",
        "api_base": "", "model": "", "api_key": "",
        "transcription_api_base": "", "transcription_model": "whisper-1",
        "transcription_api_key": "", "standard_id": "",
    }


def configure_job_root(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    root.mkdir()
    monkeypatch.setattr(storage, "DATA_ROOT", root)
    monkeypatch.setattr(server, "DATA_ROOT", root)

    class FakeAdapter:
        def analyze(self, _path, _structures):
            return {"engine": "test", "elementCount": 0, "elements": [], "regionCounts": {}}

    monkeypatch.setattr(image_sequence, "ScreenCoderAdapter", FakeAdapter)


def test_create_image_job_preserves_manifest_order_and_dispatches(monkeypatch, tmp_path):
    configure_job_root(tmp_path, monkeypatch)
    submitted = []
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))

    job = server.create_job(
        video=None,
        images=[image_upload("10.png"), image_upload("2.png")],
        image_manifest=manifest(["2.png", "10.png"]),
        **create_args(),
    )

    assert job["metadata"]["inputType"] == "image_sequence"
    assert job["contentModelVersion"] == 2
    assert [frame["sourceName"] for frame in job["frames"]] == ["2.png", "10.png"]
    assert submitted[0][0] is server._process
    assert submitted[0][1][0] == job["id"]
    assert len(submitted[0][1]) == 2


def test_create_image_job_uses_recovery_model_when_empty_gameplay_initialization_fails(monkeypatch, tmp_path):
    configure_job_root(tmp_path, monkeypatch)
    submitted = []
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))
    monkeypatch.setattr(
        server,
        "ensure_gameplay_review_model",
        lambda _job: (_ for _ in ()).throw(RuntimeError("deployment modules are temporarily inconsistent")),
    )
    monkeypatch.setattr(
        server,
        "build_gameplay_recovery_model",
        lambda _job: {"schemaVersion": "gameplay-review-model-v2", "contentState": "pending"},
    )

    job = server.create_job(
        video=None,
        images=[image_upload("1.png"), image_upload("2.png")],
        image_manifest=manifest(["1.png", "2.png"]),
        **create_args(),
    )

    assert len(job["frames"]) == 2
    assert job["checkpoint"] == "frames-complete"
    assert job["gameplayReviewModel"]["contentState"] == "pending"
    assert submitted[0][0] is server._process


def test_image_processing_skips_video_extraction_and_can_retry(monkeypatch, tmp_path):
    configure_job_root(tmp_path, monkeypatch)
    submitted = []
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))
    job = server.create_job(
        video=None, images=[image_upload("1.png"), image_upload("2.png")],
        image_manifest=manifest(["1.png", "2.png"]), **create_args(),
    )
    monkeypatch.setattr(server, "inspect_video", lambda *_args: (_ for _ in ()).throw(AssertionError("video scan called")))
    def analyzed(_dir, frames, scenes, _config, _mode, _progress, input_type="video", **_kwargs):
        for frame in frames:
            frame["analysis"] = {
                "what": "Select item",
                "userAction": "tap card",
                "systemResponse": "card selected",
                "afterState": "selection complete",
            }
        return frames, scenes, {"inputType": input_type}

    monkeypatch.setattr(server, "analyze_video", analyzed)
    monkeypatch.setattr(server, "reconcile_and_audit", lambda _job: ([], [], {"score": 100}))
    monkeypatch.setattr(server, "generate_plan", lambda _job: "# plan")
    monkeypatch.setattr(server, "write_scene_specs", lambda *_args: [])

    server._process(job["id"], {})
    completed = storage.load_job(job["id"])
    assert completed["status"] == "completed"
    assert completed["analysisSummary"]["inputType"] == "image_sequence"

    server.retry_job(job["id"], "", "", "")
    assert submitted[-1][0] is server._process


def test_image_processing_stops_before_planning_for_unqualified_review_draft(monkeypatch, tmp_path):
    configure_job_root(tmp_path, monkeypatch)
    monkeypatch.setattr(server.executor, "submit", lambda *_args: None)
    job = server.create_job(
        video=None, images=[image_upload("1.png"), image_upload("2.png")],
        image_manifest=manifest(["1.png", "2.png"]), **create_args(),
    )
    monkeypatch.setattr(
        server,
        "analyze_video",
        lambda _dir, frames, scenes, _config, _mode, _progress, input_type="video", **_kwargs: (frames, scenes, {}),
    )
    planning_calls = []
    monkeypatch.setattr(server, "generate_plan", lambda _job: planning_calls.append(True))

    server._process(job["id"], {})

    failed = storage.load_job(job["id"])
    assert failed["status"] == "failed"
    assert "qualified GVE16 review draft" in failed["error"]
    assert planning_calls == []


def test_legacy_video_job_remains_supported(monkeypatch, tmp_path):
    configure_job_root(tmp_path, monkeypatch)
    submitted = []
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))

    job = server.create_job(video=video_upload(), images=None, image_manifest="", **create_args())

    assert job["metadata"]["inputType"] == "video"
    assert job["sourceUrl"].endswith("source.mp4")
    assert submitted[0][0] is server._process
