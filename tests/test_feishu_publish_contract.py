from pathlib import Path

from backend.feishu_cli import _ALLOWED_PREFIXES
from backend.feishu_publish import FOLDER_NAME, _safe_media_arg


ROOT = Path(__file__).resolve().parents[1]


def test_publication_uses_fixed_folder_and_user_identity_contract():
    source = (ROOT / "backend" / "feishu_publish.py").read_text(encoding="utf-8")
    assert FOLDER_NAME == "视频策划案生成中心"
    assert '"--as", "user"' in source
    assert '"--as", "bot"' not in source


def test_cli_allowlist_has_no_delete_or_arbitrary_shell_commands():
    flattened = {" ".join(prefix) for prefix in _ALLOWED_PREFIXES}
    assert not any("delete" in command for command in flattened)
    assert not any(command.startswith(("cmd", "powershell", "bash", "sh ")) for command in flattened)


def test_media_paths_cannot_escape_project(tmp_path):
    outside = ROOT.parent / "outside-project-media.jpg"
    try:
        _safe_media_arg(outside.resolve())
    except ValueError as error:
        assert "inside the project" in str(error)
    else:
        raise AssertionError("outside media path was accepted")


def test_publication_api_uses_an_allowlist_instead_of_raw_state():
    source = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
    assert "_PUBLICATION_FIELDS" in source
    assert "_public_feishu_publication" in source
    assert '"access_token"' not in source
    assert '"refresh_token"' not in source


def test_frontend_contains_no_feishu_credential_input():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    source = (ROOT / "js" / "feishu-publish.js").read_text(encoding="utf-8")
    assert "feishuToken" not in html
    assert "access_token" not in source
    assert "refresh_token" not in source
