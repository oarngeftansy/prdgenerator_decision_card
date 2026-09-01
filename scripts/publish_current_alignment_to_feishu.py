from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from backend.feishu_cli import LarkCli
from backend.feishu_publish import FeishuPublisher


ROOT = Path(__file__).resolve().parents[1]
JOB_DIR = ROOT / "data/jobs/4180cd72eeaa4819be41db50bb4c5011"
PUBLICATION = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19"
CHECKPOINT = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19/feishu-publication-checkpoint.json"
DEFAULT_CLI = Path(os.environ.get("LARK_CLI_EXECUTABLE", "lark-cli.cmd"))
REQUEST_ID = "alignment-closure-20260820-v4-three-board-gve16-realign"


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, default=DEFAULT_CLI)
    args = parser.parse_args()
    job = json.loads((JOB_DIR / "job.json").read_text(encoding="utf-8"))
    job["acceptedPublication"] = {
        "markdown": (PUBLICATION / "human-planning-preview.md").read_text(encoding="utf-8"),
        "p5Diagrams": json.loads((JOB_DIR / "structures/p5-review-diagrams.json").read_text(encoding="utf-8"))["diagrams"],
        "p6Tables": json.loads((JOB_DIR / "structures/p6-review-tables.json").read_text(encoding="utf-8"))["tables"],
        "nativeBoards": json.loads((PUBLICATION / "accepted-native-boards.json").read_text(encoding="utf-8")),
    }
    if CHECKPOINT.exists():
        job["feishuPublication"] = json.loads(CHECKPOINT.read_text(encoding="utf-8"))

    def save(publication: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        _write(CHECKPOINT, publication)
        return publication

    result = FeishuPublisher(
        LarkCli(executable=str(args.cli), timeout=180),
        JOB_DIR,
        save=save,
    ).publish(job, REQUEST_ID, "update")
    print(json.dumps({
        "status": result.status,
        "documentToken": result.document_token,
        "documentUrl": result.document_url,
        "checkpoint": str(CHECKPOINT.relative_to(ROOT)).replace("\\", "/"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
