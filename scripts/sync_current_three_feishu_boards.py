from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.feishu_cli import LarkCli, LarkCommandError
from backend.feishu_publish import (
    _idempotent_token,
    _normalize_openapi_ids,
    _openapi_id_map,
    _raw_board_has_content,
    _raw_board_has_expected_images,
    _safe_media_arg,
    _structure_without_pending_images,
    _token,
    _token_backed_image_node,
)
from backend.feishu_render import render_feishu_document


ROOT = Path(__file__).resolve().parents[1]
JOB_DIR = ROOT / "data/jobs/4180cd72eeaa4819be41db50bb4c5011"
PUBLICATION = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19"
CHECKPOINT = PUBLICATION / "feishu-publication-checkpoint.json"
OUTPUT = PUBLICATION / "feishu-native-whiteboards/remote-sync-20260820-v7"
REQUEST_ID = "alignment-closure-20260820-v7-page-content-layer-repair"


def retry(operation, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except LarkCommandError as exc:
            last_error = exc
            if attempt + 1 == attempts:
                raise
            time.sleep(1 + attempt)
    raise last_error or RuntimeError("operation failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", default=os.environ.get("LARK_CLI_EXECUTABLE", "lark-cli.cmd"))
    parser.add_argument("--only", choices=("ue", "planning", "competitor"))
    args = parser.parse_args()
    cli = LarkCli(executable=args.cli, timeout=180)

    job = json.loads((JOB_DIR / "job.json").read_text(encoding="utf-8"))
    job["acceptedPublication"] = {
        "markdown": (PUBLICATION / "human-planning-preview.md").read_text(encoding="utf-8"),
        "p5Diagrams": json.loads((JOB_DIR / "structures/p5-review-diagrams.json").read_text(encoding="utf-8"))["diagrams"],
        "p6Tables": json.loads((JOB_DIR / "structures/p6-review-tables.json").read_text(encoding="utf-8"))["tables"],
        "nativeBoards": json.loads((PUBLICATION / "accepted-native-boards.json").read_text(encoding="utf-8")),
    }
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    document_token = str(checkpoint["documentToken"])
    board_tokens = checkpoint["boardTokens"]
    rendered = render_feishu_document(job, JOB_DIR)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "requestId": REQUEST_ID,
        "documentToken": document_token,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "boards": {},
    }
    for named in rendered.native_boards:
        key, board = named.key, named.board
        if args.only and key != args.only:
            continue
        token = str(board_tokens[key])
        id_map = _openapi_id_map(board.structure, board.overlay, [image.node for image in board.images])
        structure = _structure_without_pending_images(board.structure, id_map)
        retry(lambda: cli.run([
            "whiteboard", "+update", "--whiteboard-token", token,
            "--input_format", "raw", "--source", "-", "--overwrite",
            "--idempotent-token", _idempotent_token(REQUEST_ID, f"{key}-structure"),
            "--as", "user", "--json",
        ], stdin=json.dumps(structure, ensure_ascii=False)))

        uploaded: dict[str, str] = {}
        for index, image in enumerate(board.images, 1):
            media = retry(lambda image=image: cli.run([
                "docs", "+media-upload", "--parent-type", "whiteboard",
                "--parent-node", token, "--doc-id", document_token,
                "--file", _safe_media_arg(JOB_DIR / image.image_path),
                "--as", "user", "--json",
            ]).data)
            media_token = _token(media.get("file_token") or media.get("token"))
            if not media_token:
                raise RuntimeError(f"{key}: media upload returned no token for {image.frame_id}")
            image_node = _token_backed_image_node(image.node, media_token, id_map)
            retry(lambda image_node=image_node, index=index: cli.run([
                "whiteboard", "+update", "--whiteboard-token", token,
                "--input_format", "raw", "--source", "-",
                "--idempotent-token", _idempotent_token(REQUEST_ID, f"{key}-image-{index}"),
                "--as", "user", "--json",
            ], stdin=json.dumps({"nodes": [image_node]}, ensure_ascii=False)))
            uploaded[str(image.node.get("id") or image.frame_id)] = media_token

        overlay = _normalize_openapi_ids(board.overlay, id_map)
        if overlay.get("nodes") or overlay.get("connectors"):
            retry(lambda: cli.run([
                "whiteboard", "+update", "--whiteboard-token", token,
                "--input_format", "raw", "--source", "-",
                "--idempotent-token", _idempotent_token(REQUEST_ID, f"{key}-overlay"),
                "--as", "user", "--json",
            ], stdin=json.dumps(overlay, ensure_ascii=False)))

        remote = retry(lambda: cli.run([
            "whiteboard", "+query", "--whiteboard-token", token,
            "--output_as", "raw", "--as", "user", "--json",
        ]).data)
        if not _raw_board_has_content(remote):
            raise RuntimeError(f"{key}: remote board is empty after sync")
        if not _raw_board_has_expected_images(remote, len(board.images)):
            raise RuntimeError(f"{key}: remote board lost images after sync")
        (OUTPUT / f"{key}-raw.json").write_text(
            json.dumps(remote, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        report["boards"][key] = {
            "title": named.title,
            "token": token,
            "images": len(board.images),
            "uploadedNodes": len(uploaded),
            "verified": True,
        }
        print(json.dumps({"board": key, **report["boards"][key]}, ensure_ascii=False), flush=True)

    report["completedAt"] = datetime.now(timezone.utc).isoformat()
    (OUTPUT / "sync-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
