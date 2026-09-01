from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_JOB_ID = "4180cd72eeaa4819be41db50bb4c5011"
DEFAULT_SOURCE_JOB_ID = "8312a91c89e144e6a59f81b982f14c06"
ACCEPTED_DIRECTORY_TITLES = [
    "载具",
    "武器",
    "局内强化",
    "终极强化",
    "武器抽取",
    "怪物",
    "关卡",
    "结算",
]


def repair_payload(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    source_model = source.get("gameplayReviewModel")
    if not isinstance(source_model, dict):
        raise ValueError("accepted source is missing gameplayReviewModel")
    titles = [
        item.get("title")
        for item in (source_model.get("directory") or {}).get("entries") or []
        if isinstance(item, dict)
    ]
    if titles != ACCEPTED_DIRECTORY_TITLES:
        raise ValueError(f"accepted source directory drifted: {titles!r}")

    repaired = copy.deepcopy(target)
    repaired["gameplayReviewModel"] = copy.deepcopy(source_model)
    repaired.setdefault("metadata", {})["projectName"] = "一路狂飙交互与玩法策划案"
    repaired["updatedAt"] = datetime.now(timezone.utc).isoformat()
    repaired["workbenchRepair"] = {
        "reason": "restore accepted eight-owner gameplay directory after stale 18-chapter model writeback",
        "sourceJobId": source.get("id") or DEFAULT_SOURCE_JOB_ID,
        "restoredDirectoryTitles": ACCEPTED_DIRECTORY_TITLES,
        "restoredAt": repaired["updatedAt"],
    }
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-job-id", default=DEFAULT_TARGET_JOB_ID)
    parser.add_argument("--source-job-id", default=DEFAULT_SOURCE_JOB_ID)
    args = parser.parse_args()

    target_path = ROOT / "data" / "jobs" / args.target_job_id / "job.json"
    source_path = ROOT / "data" / "jobs" / args.source_job_id / "job.json"
    target = json.loads(target_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))
    repaired = repair_payload(target, source)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = target_path.with_name(f"job.before-workbench-repair-{timestamp}.json")
    backup_path.write_text(json.dumps(target, ensure_ascii=False, indent=2), encoding="utf-8")

    temporary_path = target_path.with_suffix(".json.repairing")
    temporary_path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(target_path)
    print(json.dumps({
        "target": str(target_path),
        "backup": str(backup_path),
        "directoryTitles": ACCEPTED_DIRECTORY_TITLES,
        "revision": repaired["gameplayReviewModel"].get("revision"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
