"""Create a disposable, fully unlocked workbench fixture from a real job."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "data" / "jobs"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = JOBS / args.source / "job.json"
    job = copy.deepcopy(json.loads(source.read_text(encoding="utf-8")))
    fixture_id = f"qa-web-buttons-{uuid.uuid4().hex[:12]}"
    job["id"] = fixture_id
    job.setdefault("metadata", {})["projectName"] = "网页按钮隔离验收"

    gameplay = job["gameplayReviewModel"]
    gameplay["jobId"] = fixture_id
    gameplay["directory"]["status"] = "confirmed"
    gameplay["directory"]["confirmedAtRevision"] = gameplay["directory"].get("revision")
    gameplay["reviewState"]["interactionHandoffConfirmed"] = True
    for chapter in gameplay.get("chapters", []):
        chapter["status"] = "approved"
        chapter.setdefault("confirmation", {})["confirmed"] = True
        chapter["confirmation"]["revision"] = gameplay.get("revision")
    for diagram in gameplay.get("diagrams", []):
        diagram["status"] = "reviewed"
    for table in gameplay.get("tables", []):
        table["status"] = "reviewed"
    gameplay.setdefault("diagramReview", {})["status"] = "ready"
    gameplay.setdefault("tableReview", {})["status"] = "ready"

    review = job["reviewModel"]
    review["jobId"] = fixture_id
    confirmed_ids = []
    for stage in review.get("stages", []):
        stage.setdefault("confirmation", {})["confirmed"] = True
        stage["confirmation"]["revision"] = review.get("revision")
        confirmed_ids.append(stage["id"])
    review["reviewState"]["flowConfirmed"] = True
    review["reviewState"]["ueFlowConfirmed"] = True
    review["reviewState"]["confirmedStageIds"] = confirmed_ids
    review["reviewState"]["previewRevision"] = review.get("revision")

    target = JOBS / fixture_id
    target.mkdir(parents=True, exist_ok=False)
    for directory_name in ("frames", "uploads", "structures"):
        source_directory = source.parent / directory_name
        if source_directory.is_dir():
            shutil.copytree(source_directory, target / directory_name)
    (target / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    print(fixture_id)


if __name__ == "__main__":
    main()
