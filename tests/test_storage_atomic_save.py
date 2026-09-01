from pathlib import Path

from backend import storage


def test_atomic_save_retries_transient_windows_permission_error(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    job_dir = tmp_path / "retry-job"
    job_dir.mkdir()
    (job_dir / "job.json").write_text('{"id":"retry-job"}', encoding="utf-8")

    original_replace = Path.replace
    attempts = []

    def flaky_replace(source, target):
        attempts.append((source, target))
        if len(attempts) < 3:
            raise PermissionError("transient sharing violation")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr(storage.time, "sleep", lambda _seconds: None)

    storage.save_job({"id": "retry-job", "status": "completed"})

    assert len(attempts) == 3
    assert storage.load_job("retry-job")["status"] == "completed"
    assert not list(job_dir.glob(".*.tmp"))
