from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_startup_uses_canonical_api_entrypoint() -> None:
    text = (ROOT / "start.ps1").read_text(encoding="utf-8")
    assert "uvicorn canonical_api_server:app" in text
    assert "uvicorn api_server:app" not in text
    assert "uvicorn backend.server:app" not in text
