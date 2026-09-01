from backend import server
from backend.review_preview import build_review_preview
from tests.review_fixtures import make_confirmed_job


def test_completed_paid_analysis_is_reused_after_downstream_failure():
    job = {
        "checkpoint": "analysis-complete",
        "analysisSummary": {"modelEnabled": True, "qualifiedDetailFrameCount": 12},
        "frames": [{"analysis": {"what": "关卡页面"}}],
    }

    assert server._has_reusable_analysis(job) is True


def test_interrupted_job_resume_rehydrates_built_in_model_config(monkeypatch, tmp_path):
    job_dir = tmp_path / "job-1"
    job_dir.mkdir()
    (job_dir / "job.json").write_text("{}", encoding="utf-8")
    job = {
        "id": "job-1", "status": "processing", "checkpoint": "frames-complete",
        "cancelRequested": False, "metadata": {"inputType": "image_sequence"}, "frames": [{"id": "F1"}],
        "runtimeProfile": {"model": "qwen3.6-plus"},
    }
    submitted = []
    trusted = {"apiBase": "https://trusted.example/v1", "model": "qwen3.6-plus", "apiKey": "rehydrated"}
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "update_job", lambda *_args, **_kwargs: job)
    monkeypatch.setattr(server, "_runtime_ai_config", lambda *_args: trusted)
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))

    server.resume_interrupted_jobs()

    assert submitted == [(server._process, ("job-1", trusted))]


def test_directory_pending_image_job_is_submitted_without_a_source_video(monkeypatch, tmp_path):
    job_dir = tmp_path / "job-directory"
    job_dir.mkdir()
    (job_dir / "job.json").write_text("{}", encoding="utf-8")
    job = {
        "id": "job-directory", "status": "processing", "checkpoint": "directory-pending",
        "cancelRequested": False, "metadata": {"inputType": "image_sequence"},
        "frames": [{"id": "F0001", "analysis": {"title": "已识别"}}],
        "runtimeProfile": {"model": "qwen3.6-plus"},
    }
    submitted = []
    trusted = {"apiBase": "https://trusted.example/v1", "model": "qwen3.6-plus", "apiKey": "rehydrated"}
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "update_job", lambda *_args, **_kwargs: job)
    monkeypatch.setattr(server, "_runtime_ai_config", lambda *_args: trusted)
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))

    server.resume_interrupted_jobs()

    assert submitted == [(server._process, ("job-directory", trusted))]


def test_interrupted_image_import_recovers_persisted_frames_before_resuming(monkeypatch, tmp_path):
    job_dir = tmp_path / "job-recover"
    job_dir.mkdir()
    (job_dir / "job.json").write_text("{}", encoding="utf-8")
    job = {
        "id": "job-recover", "status": "queued", "checkpoint": None,
        "cancelRequested": False, "metadata": {"inputType": "image_sequence"}, "frames": [],
        "runtimeProfile": {"model": "qwen3.6-plus"},
    }
    recovered = ([{"id": "F0001"}, {"id": "F0002"}], [{"id": 0}, {"id": 1}], [{"id": "T1"}])
    submitted = []
    updates = []
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "recover_persisted_image_sequence", lambda _path: recovered)
    monkeypatch.setattr(server.storage, "mutate_job", lambda _job_id, mutation: mutation(job))
    monkeypatch.setattr(server, "update_job", lambda _job_id, **values: updates.append(values) or job.update(values) or job)
    monkeypatch.setattr(server, "_runtime_ai_config", lambda *_args: {"apiKey": "key", "model": "model", "apiBase": "base"})
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))

    server.resume_interrupted_jobs()

    assert job["frames"] == recovered[0]
    assert job["scenes"] == recovered[1]
    assert job["componentTracks"] == recovered[2]
    assert job["checkpoint"] == "frames-complete"
    assert submitted and submitted[0][0] is server._process


def test_interrupted_image_import_without_recoverable_files_becomes_actionable_failure(monkeypatch, tmp_path):
    job_dir = tmp_path / "job-empty"
    job_dir.mkdir()
    (job_dir / "job.json").write_text("{}", encoding="utf-8")
    job = {
        "id": "job-empty", "status": "queued", "checkpoint": None,
        "cancelRequested": False, "metadata": {"inputType": "image_sequence"}, "frames": [],
    }
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "recover_persisted_image_sequence", lambda _path: None)
    monkeypatch.setattr(server, "update_job", lambda _job_id, **values: job.update(values) or job)

    server.resume_interrupted_jobs()

    assert job["status"] == "failed"
    assert job["stage"] == "截图导入被服务重启中断"
    assert "重新选择原截图文件夹" in job["error"]


def test_recovered_images_wait_for_browser_api_key_instead_of_failing_again(monkeypatch, tmp_path):
    job_dir = tmp_path / "job-key"
    job_dir.mkdir()
    (job_dir / "job.json").write_text("{}", encoding="utf-8")
    job = {
        "id": "job-key", "status": "queued", "checkpoint": None,
        "cancelRequested": False, "metadata": {"inputType": "image_sequence"}, "frames": [],
        "runtimeProfile": {"model": "qwen3.6-plus"},
    }
    recovered = ([{"id": "F0001"}, {"id": "F0002"}], [{"id": 0}, {"id": 1}], [])
    submitted = []
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "recover_persisted_image_sequence", lambda _path: recovered)
    monkeypatch.setattr(server.storage, "mutate_job", lambda _job_id, mutation: mutation(job))
    monkeypatch.setattr(server, "update_job", lambda _job_id, **values: job.update(values) or job)
    monkeypatch.setattr(server, "_runtime_ai_config", lambda *_args: {"apiKey": "", "model": "model", "apiBase": "base"})
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))

    server.resume_interrupted_jobs()

    assert job["status"] == "failed"
    assert job["stage"] == "素材已恢复，等待重新分析"
    assert "已恢复 2 张截图" in job["error"]
    assert "API Key" in job["error"]
    assert submitted == []


def test_restored_confirmed_job_keeps_pages_when_frames_only_have_image_paths(tmp_path):
    job = make_confirmed_job()
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    for frame in job["frames"]:
        frame.pop("imageUrl", None)
        frame["imagePath"] = f"frames/{frame['id']}.jpg"
        (frame_dir / f"{frame['id']}.jpg").write_bytes(b"restored-frame")

    preview = build_review_preview(job, tmp_path)

    assert preview["boardPreviewSvg"].count('data-node-kind="page-screenshot"') == 2
    assert 'data-image-state="unavailable"' not in preview["boardPreviewSvg"]
