from fastapi import HTTPException
from starlette.requests import Request

from backend import server
from tests.test_gameplay_render import complete_job


def _request(host: str) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/jobs",
        "raw_path": b"/api/jobs",
        "query_string": b"",
        "headers": [],
        "client": (host, 50000),
        "server": ("127.0.0.1", 8000),
    })


def test_loopback_can_list_and_archive_history(monkeypatch):
    monkeypatch.setattr(server, "list_jobs", lambda include_archived=False: [{
        "id": "job-1", "status": "completed", "frames": [{"id": "F0001"}],
        "planningModel": {"events": [1]}, "metadata": {"projectName": "Demo"},
        "qualityReport": {"score": 91, "details": ["large"]},
    }])
    monkeypatch.setattr(server, "update_job", lambda job_id, **changes: {"id": job_id, **changes})

    local = server.get_jobs(_request("127.0.0.1"), False)[0]
    assert local["id"] == "job-1"
    assert local["qualityReport"] == {"score": 91}
    assert "frames" not in local
    assert "planningModel" not in local
    assert server.get_jobs(_request("::1"), False)[0]["id"] == "job-1"
    assert server.archive_job("job-1", _request("127.0.0.2"), True)["archived"] is True


def test_private_lan_client_can_list_and_archive_history(monkeypatch):
    monkeypatch.setattr(server, "list_jobs", lambda include_archived=False: [{
        "id": "job-lan", "status": "failed", "metadata": {"projectName": "局域网任务"}
    }])
    monkeypatch.setattr(server, "update_job", lambda job_id, **changes: {"id": job_id, **changes})

    jobs = server.get_jobs(_request("192.168.50.88"), False)
    assert jobs[0]["id"] == "job-lan"
    assert server.archive_job("job-lan", _request("192.168.50.88"), True)["archived"] is True


def test_public_remote_client_cannot_list_history():
    with __import__("pytest").raises(HTTPException) as listing:
        server.get_jobs(_request("8.8.8.8"), False)
    assert listing.value.status_code == 403


def test_local_history_returns_safe_restorable_gameplay_state(monkeypatch):
    job = complete_job()
    job["gameplayReviewModel"]["reviewState"]["previewRevision"] = 3
    job["gameplayReviewGeneration"] = {
        "status": "completed", "progress": 100, "message": "Gameplay review generated.",
        "technicalError": "provider timeout", "apiKey": "sk-secret",
    }
    job["runtimeProfile"] = {
        "apiBase": "https://provider.invalid/v1", "apiKey": "sk-secret",
        "videoPath": r"C:\Users\planner\private.mp4",
    }
    job["gameplayReviewModel"]["contextWindows"] = [{
        "chapterId": "GCH-001", "status": "completed", "matchedTime": 12.5,
        "radius": 5, "evidenceTimestamps": [11.0, 13.0],
        "technicalError": "matching trace", "localPath": r"D:\jobs\job-1\frames",
        "genericNested": "/home/planner/private.mp4", "assetPath": "/tmp/job/frame.png",
    }]
    monkeypatch.setattr(server, "list_jobs", lambda include_archived=False: [job])

    payload = server.get_jobs(_request("127.0.0.1"), False)[0]
    serialized = __import__("json").dumps(payload)

    assert payload["gameplayReviewGeneration"]["status"] == "completed"
    assert payload["gameplayReviewModel"]["chapters"][0]["id"] == "GCH-001"
    assert payload["gameplayReviewModel"]["diagrams"][0]["status"] == "reviewed"
    assert payload["gameplayReviewModel"]["reviewState"]["previewRevision"] == 3
    for forbidden in ("technicalError", "apiKey", "apiBase", "matchedTime", "evidenceTimestamps", "C:\\", "D:\\", "/home/", "/tmp/", "sk-secret"):
        assert forbidden not in serialized


def test_public_job_strips_posix_paths_under_generic_and_path_keys():
    job = complete_job()
    job["nested"] = {
        "generic": "/var/private/gameplay.mp4",
        "framePath": "/Users/planner/frame.png",
        "safeUrl": "/artifacts/job-1/frames/F0001.jpg",
    }

    public = server._public_job(job)

    assert public["nested"]["generic"] == ""
    assert "framePath" not in public["nested"]
    assert public["nested"]["safeUrl"] == "/artifacts/job-1/frames/F0001.jpg"
