from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.feishu_render import render_feishu_document


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOB = ROOT / "data/jobs/4180cd72eeaa4819be41db50bb4c5011/job.json"
DEFAULT_OUTPUT = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19/feishu-native-whiteboards"
PUBLICATION = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19"


def _accepted_job(job_path: Path) -> dict[str, Any]:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job["acceptedPublication"] = {
        "markdown": (PUBLICATION / "human-planning-preview.md").read_text(encoding="utf-8"),
        "p5Diagrams": json.loads((job_path.parent / "structures/p5-review-diagrams.json").read_text(encoding="utf-8"))["diagrams"],
        "p6Tables": json.loads((job_path.parent / "structures/p6-review-tables.json").read_text(encoding="utf-8"))["tables"],
        "nativeBoards": json.loads((PUBLICATION / "accepted-native-boards.json").read_text(encoding="utf-8")),
    }
    return job


def build(job_path: Path, output_dir: Path) -> dict[str, Any]:
    """Export and validate the sole Final presentation carrier: planning sketch."""
    rendered = render_feishu_document(_accepted_job(job_path), job_path.parent)
    if [(item.key, item.title) for item in rendered.native_boards] != [("planning", "策划草图")]:
        raise ValueError("Final must contain the planning sketch board only")
    previews = dict(rendered.preview_board_svgs)
    if list(previews) != ["planning"]:
        raise ValueError("Final preview must contain the planning sketch only")

    named = rendered.native_boards[0]
    board = named.board
    raw_nodes = [*board.structure.get("nodes", []), *board.overlay.get("nodes", [])]
    manifest = [{
        "key": named.key,
        "title": named.title,
        "structure": board.structure,
        "overlay": board.overlay,
        "images": [
            {"frameId": image.frame_id, "path": image.image_path, "node": image.node}
            for image in board.images
        ],
        "rawNodeCount": len(raw_nodes),
        "sectionCount": sum(node.get("type") == "section" for node in raw_nodes),
        "connectorCount": sum(node.get("type") == "connector" for node in raw_nodes),
    }]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "planning-preview.svg").write_text(previews["planning"], encoding="utf-8")
    (output_dir / "raw-board-manifest.json").write_text(json.dumps({
        "schemaVersion": "feishu-planning-only-delivery-v1",
        "contentFingerprint": rendered.content_fingerprint,
        "boards": manifest,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    acceptance = {
        "boardOrder": ["planning"],
        "planningScreenshotCount": len(board.images),
        "planningSectionCount": manifest[0]["sectionCount"],
        "planningConnectorCount": manifest[0]["connectorCount"],
        "forbiddenBoardCount": sum(item.key in {"ue", "competitor"} for item in rendered.native_boards),
        "previewExports": ["planning-preview.svg"],
        "remotePublicationState": "pending_final_publication",
    }
    (output_dir / "acceptance.json").write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return acceptance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, default=DEFAULT_JOB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.job, args.output)


if __name__ == "__main__":
    main()
