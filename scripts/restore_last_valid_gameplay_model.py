from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gameplay_lifecycle import gameplay_model_has_reviewable_detail


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def restore_last_valid_model(
    job_path: Path,
    snapshot_path: Path,
    *,
    expected_revision: int,
    expected_scopes: tuple[str, ...],
    expected_sha256: str,
    offline_confirmed: bool = False,
) -> dict[str, Any]:
    if not offline_confirmed:
        raise ValueError("offline confirmation is required before restoring a job file")
    job_path = job_path.resolve()
    snapshot_path = snapshot_path.resolve()
    original_job_bytes = job_path.read_bytes()
    job = json.loads(original_job_bytes.decode("utf-8"))
    if not isinstance(job, dict):
        raise ValueError(f"expected JSON object: {job_path}")
    snapshot_bytes = snapshot_path.read_bytes()
    if hashlib.sha256(snapshot_bytes).hexdigest().lower() != expected_sha256.lower():
        raise ValueError("snapshot SHA-256 does not match the expected value")
    snapshot = _read_object(snapshot_path)
    job_id = str(job.get("id") or "").strip()
    snapshot_job_id = str(snapshot.get("jobId") or "").strip()
    if not job_id or snapshot_job_id != job_id:
        raise ValueError("snapshot job id does not match target job id")
    if snapshot.get("revision") != expected_revision:
        raise ValueError("snapshot revision does not match the expected revision")
    actual_scopes = tuple(
        str(item.get("scope") or item.get("title") or "").strip()
        for item in snapshot.get("chapters") or []
        if isinstance(item, dict)
    )
    if actual_scopes != expected_scopes:
        raise ValueError("snapshot chapter scopes do not match the expected chapter scopes")
    if not gameplay_model_has_reviewable_detail(snapshot, expected_job_id=job_id):
        raise ValueError("snapshot does not contain durable reviewable gameplay detail")
    if gameplay_model_has_reviewable_detail(job.get("gameplayReviewModel"), expected_job_id=job_id):
        raise ValueError("target job already has durable content; refusing to overwrite it")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = job_path.with_name(f"job.before-last-valid-restore-{timestamp}.json")
    if backup.exists():
        backup = job_path.with_name(f"job.before-last-valid-restore-{timestamp}-{uuid.uuid4().hex[:8]}.json")
    shutil.copy2(job_path, backup)

    last_valid = deepcopy(snapshot)
    restored = deepcopy(snapshot)
    restored["lifecycleState"] = "ready"
    generation = job.get("gameplayReviewGeneration")
    if isinstance(generation, dict) and generation.get("status") == "failed":
        restored["contentState"] = "failed"
    else:
        restored.setdefault("contentState", "ready")
    restored["lastValidRevision"] = restored.get("revision")
    job["gameplayReviewLastValidModel"] = last_valid
    job["gameplayReviewModel"] = restored
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()

    temp = job_path.with_name(f".{job_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        if job_path.read_bytes() != original_job_bytes:
            raise RuntimeError("target job changed during offline recovery; refusing to overwrite concurrent changes")
        os.replace(temp, job_path)
    finally:
        temp.unlink(missing_ok=True)

    verified = _read_object(job_path)
    if not gameplay_model_has_reviewable_detail(verified.get("gameplayReviewModel"), expected_job_id=job_id):
        raise RuntimeError("restored job verification failed")
    return {
        "jobId": job_id,
        "restoredRevision": restored.get("revision"),
        "chapterCount": len(restored.get("chapters") or []),
        "backup": str(backup),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a verified last-valid Gameplay Model without overwriting a non-empty model.")
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--expected-revision", type=int, required=True)
    parser.add_argument("--expected-scope", action="append", dest="expected_scopes", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--offline-confirmed", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(restore_last_valid_model(
        args.job,
        args.snapshot,
        expected_revision=args.expected_revision,
        expected_scopes=tuple(args.expected_scopes),
        expected_sha256=args.expected_sha256,
        offline_confirmed=args.offline_confirmed,
    ), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
