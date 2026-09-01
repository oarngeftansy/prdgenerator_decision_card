from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
SKILLS = {
    "screencoder-video-ui-analyzer",
    "visual-reference-decomposer",
    "gve16-planning-schema",
    "ultra-high-standard-game-prd",
    "planning-to-design-handoff",
    "video-to-gve16-planner",
    "gve16-feishu-whiteboard",
}


def _metadata(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, frontmatter, _ = text.split("---", 2)
    return yaml.safe_load(frontmatter)


def test_complete_skills_are_deployed_to_runtime_and_codex_trees():
    for root in (ROOT / "skills", ROOT / ".codex" / "skills"):
        for name in SKILLS:
            package = root / name
            metadata = _metadata(package / "SKILL.md")
            assert metadata["name"] == name
            assert metadata["description"]
            interface = yaml.safe_load((package / "agents" / "openai.yaml").read_text(encoding="utf-8"))
            assert interface["interface"]["display_name"]
            assert interface["interface"]["default_prompt"]


def test_codex_copy_matches_runtime_copy():
    for name in SKILLS:
        runtime_files = {
            path.relative_to(ROOT / "skills" / name): path.read_bytes()
            for path in (ROOT / "skills" / name).rglob("*") if path.is_file()
        }
        codex_files = {
            path.relative_to(ROOT / ".codex" / "skills" / name): path.read_bytes()
            for path in (ROOT / ".codex" / "skills" / name).rglob("*") if path.is_file()
        }
        assert runtime_files == codex_files


def test_orchestrator_declares_full_video_to_gve16_chain():
    text = (ROOT / "skills" / "video-to-gve16-planner" / "SKILL.md").read_text(encoding="utf-8")
    for dependency in (
        "$video-evidence-extractor",
        "$screencoder-video-ui-analyzer",
        "$temporal-event-reconciler",
        "$planning-sample-calibrator",
        "$gve16-planning-schema",
        "$planning-quality-auditor",
        "$gve16-feishu-whiteboard",
    ):
        assert dependency in text
    assert "玩法" in text and "交互" in text and "GVE16" in text


def test_handoff_documents_connector_boundary():
    text = (ROOT / "skills" / "planning-to-design-handoff" / "SKILL.md").read_text(encoding="utf-8")
    assert "schema-ready" in text
    assert "不得声称" in text
    assert (ROOT / "skills" / "planning-to-design-handoff" / "references" / "handoff-schema.md").is_file()


def test_whiteboard_skill_encodes_the_approved_visual_contract():
    text = (ROOT / "skills" / "gve16-feishu-whiteboard" / "SKILL.md").read_text(encoding="utf-8")
    for rule in ("section", "screenshot", "straight", "#fff3bf", "90%"):
        assert rule in text
