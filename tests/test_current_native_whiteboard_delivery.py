import json
from pathlib import Path

from scripts.build_current_native_whiteboard_delivery import DEFAULT_JOB, build


def test_current_native_whiteboard_delivery_is_planning_only(tmp_path: Path):
    acceptance = build(DEFAULT_JOB, tmp_path)
    manifest = json.loads((tmp_path / "raw-board-manifest.json").read_text(encoding="utf-8"))

    assert acceptance["boardOrder"] == ["planning"]
    assert acceptance["forbiddenBoardCount"] == 0
    assert acceptance["planningScreenshotCount"] > 0
    assert acceptance["planningSectionCount"] > 0
    assert acceptance["planningConnectorCount"] > 0
    assert acceptance["previewExports"] == ["planning-preview.svg"]
    assert [item["key"] for item in manifest["boards"]] == ["planning"]
    assert (tmp_path / "planning-preview.svg").is_file()
    assert not (tmp_path / "ue-preview.svg").exists()
    assert not (tmp_path / "competitor-preview.svg").exists()
