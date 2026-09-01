from __future__ import annotations

import json
import os
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .gameplay_lifecycle import gameplay_model_has_reviewable_detail

def _configured_root(name: str, fallback: Path) -> Path:
    configured = os.environ.get(name)
    return Path(configured).expanduser().resolve() if configured else fallback.resolve()


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = _configured_root("PRD_JOBS_ROOT", ROOT / "data" / "jobs")
DATA_ROOT.mkdir(parents=True, exist_ok=True)
STANDARDS_ROOT = _configured_root("PRD_STANDARDS_ROOT", ROOT / "data" / "standards")
STANDARDS_ROOT.mkdir(parents=True, exist_ok=True)
_LOCK = threading.RLock()
_LAST_VALID_GAMEPLAY_KEY = "gameplayReviewLastValidModel"


def _preserve_last_valid_gameplay_model(job: dict[str, Any], persisted: dict[str, Any] | None) -> None:
    current = job.get("gameplayReviewModel")
    job_id = job.get("id")
    if gameplay_model_has_reviewable_detail(current, expected_job_id=job_id):
        job[_LAST_VALID_GAMEPLAY_KEY] = deepcopy(current)
        return
    if gameplay_model_has_reviewable_detail(job.get(_LAST_VALID_GAMEPLAY_KEY), expected_job_id=job_id):
        return
    if not isinstance(persisted, dict):
        return
    previous = persisted.get("gameplayReviewModel")
    if not gameplay_model_has_reviewable_detail(previous, expected_job_id=job_id):
        previous = persisted.get(_LAST_VALID_GAMEPLAY_KEY)
    if gameplay_model_has_reviewable_detail(previous, expected_job_id=job_id):
        job[_LAST_VALID_GAMEPLAY_KEY] = deepcopy(previous)


def _load_job_unlocked(job_id: str) -> dict[str, Any]:
    return json.loads((job_path(job_id) / "job.json").read_text(encoding="utf-8"))


def _save_job_unlocked(job: dict[str, Any]) -> None:
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()
    target = job_path(job["id"]) / "job.json"
    persisted = None
    if target.exists():
        try:
            persisted = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            persisted = None
    _preserve_last_valid_gameplay_model(job, persisted)
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        for attempt in range(5):
            try:
                temp.replace(target)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                # Windows indexers and virus scanners can briefly retain a handle
                # after reading a large job file. Keep the atomic replacement but
                # retry the transient sharing violation instead of losing the save.
                time.sleep(0.05 * (attempt + 1))
    finally:
        temp.unlink(missing_ok=True)


def new_job(metadata: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    job_dir = DATA_ROOT / job_id
    (job_dir / "frames").mkdir(parents=True)
    (job_dir / "structures").mkdir()
    (job_dir / "assets").mkdir()
    (job_dir / "specs").mkdir()
    (job_dir / "source_images").mkdir()
    (job_dir / "auxiliary").mkdir()
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "id": job_id,
        "status": "queued",
        "stage": "等待处理",
        "progress": 0,
        "createdAt": now,
        "updatedAt": now,
        "error": None,
        "metadata": metadata,
        "video": None,
        "scenes": [],
        "frames": [],
        "plan": "",
    }
    save_job(job)
    return job


def job_path(job_id: str) -> Path:
    path = (DATA_ROOT / job_id).resolve()
    if DATA_ROOT.resolve() not in path.parents:
        raise ValueError("invalid job id")
    return path


def load_job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        return _load_job_unlocked(job_id)


def save_job(job: dict[str, Any]) -> None:
    with _LOCK:
        _save_job_unlocked(job)


def mutate_job(job_id: str, mutation: Callable[[dict[str, Any]], Any]) -> Any:
    """Atomically reload, validate/mutate, and persist one job."""
    with _LOCK:
        job = _load_job_unlocked(job_id)
        result = mutation(job)
        _save_job_unlocked(job)
        return result


def update_job(job_id: str, **changes: Any) -> dict[str, Any]:
    def update(job: dict[str, Any]) -> dict[str, Any]:
        job.update(changes)
        return job

    return mutate_job(job_id, update)


def list_jobs(include_archived: bool = False) -> list[dict[str, Any]]:
    jobs = []
    for record in DATA_ROOT.glob("*/job.json"):
        try:
            job = json.loads(record.read_text(encoding="utf-8"))
            if job.get("archived") and not include_archived:
                continue
            jobs.append(job)
        except (OSError, json.JSONDecodeError):
            continue
    jobs.sort(key=lambda item: item.get("updatedAt", ""), reverse=True)
    return jobs


def list_standards() -> list[dict[str, Any]]:
    records = []
    for path in STANDARDS_ROOT.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            name = str(record.get("name") or "").strip()
            # Keep corrupted or test-generated placeholder records on disk for
            # diagnosis, but never expose them as selectable planning standards.
            if not name or not any(character not in "?？�" and not character.isspace() for character in name):
                continue
            records.append(record)
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(records, key=lambda item: item.get("createdAt", ""), reverse=True)


def save_standard(record: dict[str, Any]) -> dict[str, Any]:
    (STANDARDS_ROOT / f"{record['id']}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record
