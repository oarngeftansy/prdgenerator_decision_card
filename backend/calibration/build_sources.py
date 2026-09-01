from __future__ import annotations

import argparse
import json
from pathlib import Path

from .document_parser import parse_document
from .whiteboard_parser import parse_whiteboard


BOARDS = {
    "ux": "01-ux.json",
    "planning": "02-plan.json",
    "reference": "03-reference.json",
}


def build(document_fetch: Path, boards_dir: Path, output_dir: Path) -> None:
    fetch = json.loads(document_fetch.read_text(encoding="utf-8-sig"))
    document = fetch["data"]["document"]
    normalized_document = parse_document(document["content"])
    normalized_document["metadata"] = {
        "documentId": document["document_id"],
        "revisionId": document["revision_id"],
    }
    boards = {}
    for board_id, filename in BOARDS.items():
        raw = json.loads((boards_dir / filename).read_text(encoding="utf-8"))
        boards[board_id] = parse_whiteboard(raw["nodes"], board_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "document.json").write_text(
        json.dumps(normalized_document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "whiteboards.json").write_text(
        json.dumps(boards, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-fetch", type=Path, required=True)
    parser.add_argument("--boards-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.document_fetch, args.boards_dir, args.output_dir)


if __name__ == "__main__":
    main()
