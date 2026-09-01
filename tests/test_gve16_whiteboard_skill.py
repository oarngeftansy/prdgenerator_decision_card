from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / ".codex" / "skills" / "gve16-feishu-whiteboard" / "SKILL.md"
RUNTIME = ROOT / "skills" / "gve16-feishu-whiteboard" / "SKILL.md"


def test_whiteboard_skill_preserves_native_render_and_verification_rules():
    skill_text = PROJECT.read_text(encoding="utf-8")

    for requirement in (
        "real Feishu `section`",
        "native `straight` connectors",
        "Export a preview and query raw nodes",
        "Overwrite structure before uploading images",
    ):
        assert requirement in skill_text


def test_project_and_runtime_whiteboard_skill_copies_match():
    assert PROJECT.read_bytes() == RUNTIME.read_bytes()
