from backend import server
from starlette.requests import Request


def test_runtime_ai_config_uses_built_in_key_without_publicly_exposing_it(monkeypatch, tmp_path):
    env_file = tmp_path / ".env.calibration"
    env_file.write_text(
        "VISION_API_BASE=https://example.test/v1\n"
        "VISION_MODEL=test-model\n"
        "VISION_API_KEY=secret-value\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "ROOT", tmp_path)
    server._vision_env_values.cache_clear()

    config = server._runtime_ai_config("", "", "")
    assert config == {
        "apiBase": "https://example.test/v1",
        "model": "test-model",
        "apiKey": "secret-value",
    }
    assert server._runtime_ai_config("", "", "guest-key")["apiKey"] == "guest-key"

    public = server.public_config()
    assert public == {
        "hasBuiltInApi": True,
        "apiBase": "https://example.test/v1",
        "model": "test-model",
    }
    assert "apiKey" not in public


def test_job_history_is_available_to_private_lan_clients(monkeypatch):
    monkeypatch.setattr(server, "list_jobs", lambda include_archived=False: [{"id": "private-job"}])
    request = Request({
        "type": "http", "method": "GET", "path": "/api/jobs", "headers": [],
        "query_string": b"", "client": ("192.168.50.88", 50000),
        "server": ("127.0.0.1", 8000), "scheme": "http", "http_version": "1.1",
    })

    assert server.get_jobs(request)[0]["id"] == "private-job"
