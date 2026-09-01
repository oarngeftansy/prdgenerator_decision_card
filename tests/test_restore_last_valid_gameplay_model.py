import json
import hashlib

import pytest


# Regression: the accepted 一路狂飙 model had already been replaced by an
# empty skeleton before the persistence guard existed, so deployment needs a
# generic, backup-first recovery path rather than a project-name patch.
# Found by /qa on 2026-08-26.
def test_restore_last_valid_model_is_backup_first_and_preserves_other_job_data(tmp_path):
    from scripts.restore_last_valid_gameplay_model import restore_last_valid_model

    job_path = tmp_path / "job.json"
    snapshot_path = tmp_path / "snapshot.json"
    job = {
        "id": "job-1",
        "reviewModel": {"revision": 42},
        "gameplayReviewGeneration": {"status": "failed", "error": "old failure"},
        "gameplayReviewModel": {"jobId": "job-1", "revision": 1, "chapters": []},
    }
    snapshot = {
        "jobId": "job-1",
        "revision": 370,
        "chapters": [{
            "id": "GCH-001",
            "scope": "已批准章节",
            "plannerSections": {"normalFlow": ["玩家触发入口，系统反馈并进入下一状态。"]},
        }],
        "lifecycleState": "ready",
        "contentState": "ready",
        "reviewState": {"status": "chapter_review"},
    }
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    result = restore_last_valid_model(
        job_path,
        snapshot_path,
        expected_revision=370,
        expected_scopes=("已批准章节",),
        expected_sha256=digest,
        offline_confirmed=True,
    )
    restored = json.loads(job_path.read_text(encoding="utf-8"))

    assert result["restoredRevision"] == 370
    assert restored["reviewModel"] == {"revision": 42}
    assert restored["gameplayReviewGeneration"] == {"status": "failed", "error": "old failure"}
    assert restored["gameplayReviewModel"]["revision"] == 370
    assert restored["gameplayReviewModel"]["contentState"] == "failed"
    assert restored["gameplayReviewLastValidModel"]["revision"] == 370
    assert len(list(tmp_path.glob("job.before-last-valid-restore-*.json"))) == 1


def test_restore_last_valid_model_rejects_cross_project_or_nonempty_overwrite(tmp_path):
    from scripts.restore_last_valid_gameplay_model import restore_last_valid_model

    job_path = tmp_path / "job.json"
    snapshot_path = tmp_path / "snapshot.json"
    job_path.write_text(json.dumps({
        "id": "job-1",
        "gameplayReviewModel": {
            "jobId": "job-1",
            "reviewState": {"status": "chapter_review"},
            "chapters": [{
                "id": "CURRENT",
                "plannerSections": {"normalFlow": ["current detail"]},
            }],
        },
    }), encoding="utf-8")
    snapshot_path.write_text(json.dumps({
        "jobId": "job-2",
        "revision": 2,
        "chapters": [{"id": "OTHER"}],
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="job id"):
        restore_last_valid_model(
            job_path,
            snapshot_path,
            expected_revision=2,
            expected_scopes=("OTHER",),
            expected_sha256=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
            offline_confirmed=True,
        )

    matching = {
        "jobId": "job-1",
        "revision": 2,
        "chapters": [{
            "id": "OTHER",
            "scope": "Other",
            "plannerSections": {"normalFlow": ["real detail"]},
        }],
        "reviewState": {"status": "chapter_review"},
    }
    snapshot_path.write_text(json.dumps(matching), encoding="utf-8")
    with pytest.raises(ValueError, match="already has durable content"):
        restore_last_valid_model(
            job_path,
            snapshot_path,
            expected_revision=2,
            expected_scopes=("Other",),
            expected_sha256=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
            offline_confirmed=True,
        )


def test_restore_requires_offline_confirmation_and_exact_snapshot_contract(tmp_path):
    from scripts.restore_last_valid_gameplay_model import restore_last_valid_model

    job_path = tmp_path / "job.json"
    snapshot_path = tmp_path / "snapshot.json"
    job_path.write_text(json.dumps({"id": "job-1", "gameplayReviewModel": {"chapters": []}}), encoding="utf-8")
    snapshot = {
        "jobId": "job-1",
        "revision": 370,
        "reviewState": {"status": "chapter_review"},
        "chapters": [{
            "id": "GCH-001",
            "scope": "载具",
            "plannerSections": {"normalFlow": ["real detail"]},
        }],
    }
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="offline"):
        restore_last_valid_model(
            job_path, snapshot_path, expected_revision=370,
            expected_scopes=("载具",), expected_sha256=digest,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        restore_last_valid_model(
            job_path, snapshot_path, expected_revision=370,
            expected_scopes=("载具",), expected_sha256="0" * 64,
            offline_confirmed=True,
        )
    with pytest.raises(ValueError, match="chapter scopes"):
        restore_last_valid_model(
            job_path, snapshot_path, expected_revision=370,
            expected_scopes=("武器",), expected_sha256=digest,
            offline_confirmed=True,
        )
