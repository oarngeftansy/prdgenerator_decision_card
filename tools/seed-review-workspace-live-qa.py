from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.storage import job_path, save_job
from tests.review_fixtures import make_confirmed_job


def seed(job_id: str, image_path: Path) -> dict:
    if not image_path.is_file():
        raise FileNotFoundError(image_path)
    job = make_confirmed_job()
    job["id"] = job_id
    job["status"] = "completed"
    job["stage"] = "策划案生成完成"
    job["progress"] = 100
    job["plan"] = "# Live backend QA"
    model = job["reviewModel"]
    model["jobId"] = job_id
    model["reviewState"] = {
        "status": "flow_review", "flowConfirmed": False,
        "confirmedStageIds": [], "previewRevision": None,
    }
    model["referenceBoards"]["ux"] = {"assets": [], "status": "pending"}
    for stage in model["stages"]:
        stage["confirmation"] = {"confirmed": False, "revision": None}
    for transition in model["transitions"]:
        transition["confirmation"] = {"confirmed": False, "revision": None}

    directory = job_path(job_id)
    (directory / "frames").mkdir(parents=True, exist_ok=True)
    for frame in job["frames"]:
        relative = Path("frames") / f"{frame['id']}.jpg"
        (directory / relative).write_bytes(image_path.read_bytes())
        frame["imagePath"] = relative.as_posix()
        frame["imageUrl"] = f"/artifacts/{job_id}/{relative.as_posix()}"
        model["sources"][frame["id"]]["imageUrl"] = frame["imageUrl"]
    save_job(job)
    return {"jobId": job_id, "jobDir": str(directory), "revision": model["revision"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a deterministic live-backend review workspace QA job.")
    parser.add_argument("--job-id", default="final-review-live-qa")
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(seed(args.job_id, args.image.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
