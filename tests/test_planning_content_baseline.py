from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.freeze_planning_content_baseline import freeze_baseline
from tests.test_gameplay_render import complete_job


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_freeze_baseline_is_read_only_and_reproducible(tmp_path: Path) -> None:
    job = complete_job()
    job["id"] = "baseline-job"
    job["gameplayReviewModel"]["jobId"] = "baseline-job"
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    source_digest = _sha256(job_path)

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = freeze_baseline(job_path, first_dir)
    second = freeze_baseline(job_path, second_dir)

    assert _sha256(job_path) == source_digest
    assert first == second
    assert (first_dir / "baseline_metrics.json").read_bytes() == (second_dir / "baseline_metrics.json").read_bytes()
    assert (first_dir / "gameplay_directory.json").read_bytes() == (second_dir / "gameplay_directory.json").read_bytes()
    assert (first_dir / "p4_gameplay_review_model.json").read_bytes() == (second_dir / "p4_gameplay_review_model.json").read_bytes()
    assert (first_dir / "p7_body.xml").read_bytes() == (second_dir / "p7_body.xml").read_bytes()
    assert first["jobId"] == "baseline-job"
    assert first["chapterCount"] == 1
    assert first["bodySentenceCount"] > 0
    assert first["ruleCandidateCount"] == 4
    manifest = json.loads((first_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sourceJobSha256Before"] == manifest["sourceJobSha256After"] == source_digest


def test_freeze_baseline_records_in_memory_gate_override_without_mutating_source(tmp_path: Path) -> None:
    job = complete_job()
    job["gameplayReviewModel"]["directory"]["status"] = "draft"
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    source_digest = _sha256(job_path)

    metrics = freeze_baseline(job_path, tmp_path / "baseline")
    manifest = json.loads((tmp_path / "baseline" / "manifest.json").read_text(encoding="utf-8"))

    assert _sha256(job_path) == source_digest
    assert metrics["chapterCount"] == 1
    assert manifest["p7SnapshotMode"] == "in_memory_directory_gate_override"
    assert manifest["sourceJobSha256Before"] == manifest["sourceJobSha256After"] == source_digest
    assert manifest["anomalies"] == ["GAMEPLAY_DIRECTORY_NOT_CONFIRMED"]
