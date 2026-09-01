from pathlib import Path

from backend.storage import _configured_root


def test_configured_root_uses_explicit_existing_task_directory(tmp_path, monkeypatch):
    configured = tmp_path / "shared-jobs"
    monkeypatch.setenv("PRD_JOBS_ROOT", str(configured))

    result = _configured_root("PRD_JOBS_ROOT", Path("fallback"))

    assert result == configured.resolve()
