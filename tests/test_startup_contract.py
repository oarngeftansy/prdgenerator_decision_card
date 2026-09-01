from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_script_defaults_to_lan_and_accepts_host_and_port_overrides():
    script = (ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "param(" in script
    assert '[string]$HostAddress = "0.0.0.0"' in script
    assert "[int]$Port = 8000" in script
    assert "dependencies\\node\\bin" in script
    assert "飞书机器人（jojo）\\node_modules\\.bin\\lark-cli.CMD" in script
    assert "--host $HostAddress --port $Port" in script


def test_start_script_launches_master_planner_api_without_incompatible_calibration_fallback():
    script = (ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "api_server:app" in script
    assert "uvicorn backend.server:app" not in script
    assert ".runtime312" in script
    assert "runtime_packages" in script
