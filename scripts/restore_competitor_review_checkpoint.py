from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
ACCEPTED_REVIEW_REVISION = 45


def main() -> None:
    job = json.loads(JOB.read_text(encoding="utf-8"))
    review = job["reviewModel"]
    assets = review["referenceBoards"]["competitor"]["assets"]
    if len(assets) != 15 or any(item.get("status") != "ready" for item in assets):
        raise SystemExit("expected the 15 previously accepted competitor assets")
    if review.get("revision") != ACCEPTED_REVIEW_REVISION + 1:
        raise SystemExit("review revision is not the recovery-only revision")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = JOB.with_name(f"job.before-competitor-checkpoint-restore-{stamp}.json")
    shutil.copy2(JOB, backup)
    review["revision"] = ACCEPTED_REVIEW_REVISION
    review.setdefault("reviewState", {})["previewRevision"] = ACCEPTED_REVIEW_REVISION
    JOB.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"backup": str(backup), "assets": len(assets), "reviewRevision": ACCEPTED_REVIEW_REVISION}, ensure_ascii=False))


if __name__ == "__main__":
    main()
