from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
JOB_ID = "8312a91c89e144e6a59f81b982f14c06"
JOB_DIR = ROOT / "data" / "jobs" / JOB_ID
JOB_PATH = JOB_DIR / "job.json"
SOURCE_PATH = JOB_DIR / "job.before-stage5-v2-20260812T050241Z.json"


def main() -> None:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    source_job = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    model = job["gameplayReviewModel"]
    source_model = source_job["gameplayReviewModel"]
    current_by_id = {item["id"]: item for item in model.get("diagrams") or []}
    source_by_id = {item["id"]: item for item in source_model.get("diagrams") or []}
    required = [f"GDI-{number}" for number in range(101, 107)]
    if set(required) - set(current_by_id) or set(required) - set(source_by_id):
        raise RuntimeError("curated diagram baseline is incomplete")

    restored = []
    for diagram_id in required:
        current = current_by_id[diagram_id]
        source = deepcopy(source_by_id[diagram_id])
        source["status"] = current.get("status", "open")
        source["revision"] = int(current.get("revision") or 1) + (0 if current.get("status") == "reviewed" else 1)
        source["feedback"] = deepcopy(current.get("feedback") or [])
        source["generationMode"] = "curated"
        source["freshness"] = "current"
        source["sourceRevision"] = model.get("revision")
        restored.append(source)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = JOB_DIR / f"job.before-curated-diagram-restore-{stamp}.json"
    shutil.copy2(JOB_PATH, backup)
    model["diagrams"] = restored
    model["revision"] = int(model.get("revision") or 0) + 1
    model.setdefault("reviewState", {})["previewRevision"] = None
    model["diagramReview"] = {
        "status": "ready",
        "noDiagramChapterIds": [],
        "exceptions": [],
        "sourceRevision": model["revision"],
    }
    job["gameplayFinalPreview"] = None
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()
    temporary = JOB_PATH.with_suffix(".curated-diagrams.tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(JOB_PATH)
    print(json.dumps({
        "jobId": JOB_ID,
        "backup": str(backup),
        "revision": model["revision"],
        "diagrams": [(item["id"], item["status"], item["revision"], item["title"]) for item in restored],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
