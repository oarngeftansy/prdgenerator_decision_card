from copy import deepcopy

from backend import server, storage
from backend.gameplay_review_model import ensure_gameplay_review_model, gameplay_model_has_reviewable_detail
from backend.review_model import build_review_model, ensure_review_model
from tests.review_fixtures import make_confirmed_job, make_image_job


# Regression: the formal grocery project kept the exact legacy action text
# "无操作（静态展示）" instead of asking the planner to choose the real action.
# Found by /qa on 2026-08-26.
def test_exact_legacy_static_action_becomes_one_planner_decision_for_every_project():
    for project_name in ("一路狂飙", "杂货铺游戏厅", "角色创建", "全新项目"):
        job = make_image_job()
        job["metadata"]["projectName"] = project_name
        model = build_review_model(job)
        transition = model["transitions"][0]
        source = model["sources"][transition["sourceFrameId"]]
        stage = next(item for item in model["stages"] if item["id"] == transition["sourceStageId"])
        transition.update({"triggerType": "unknown", "triggerLabel": "无操作（静态展示）"})
        stage["smallLoop"]["trigger"] = "无操作（静态展示）"
        source["pageInfo"]["action"] = "无操作（静态展示）"
        job["frames"][0]["analysis"]["userAction"] = "无操作（静态展示）"
        model["interactionDecisionCards"] = []
        job["reviewModel"] = model

        migrated = ensure_review_model(job)
        cards = [
            item for item in migrated["interactionDecisionCards"]
            if item["transitionId"] == transition["id"] and item["status"] == "pending"
        ]

        assert migrated["transitions"][0]["triggerLabel"] == "待确认"
        assert stage["smallLoop"]["trigger"] == "待确认"
        assert source["pageInfo"]["action"] == "待确认"
        assert len(cards) == 1


def test_human_confirmed_static_action_is_not_rewritten_by_legacy_migration():
    job = make_image_job()
    model = build_review_model(job)
    transition = model["transitions"][0]
    source = model["sources"][transition["sourceFrameId"]]
    transition.update({
        "triggerType": "system_event",
        "triggerLabel": "无操作（静态展示）",
        "humanEditedFields": ["triggerLabel"],
    })
    source["pageInfo"]["action"] = "无操作（静态展示）"
    source["humanEditedFields"] = ["pageInfo.action"]
    job["reviewModel"] = model

    migrated = ensure_review_model(job)

    assert migrated["transitions"][0]["triggerLabel"] == "无操作（静态展示）"
    assert migrated["sources"][transition["sourceFrameId"]]["pageInfo"]["action"] == "无操作（静态展示）"


# Regression: a failed regeneration could replace an accepted Gameplay Model
# with an empty skeleton because only lastValidRevision, not the model, was saved.
# Found by /qa on 2026-08-26.
def test_storage_preserves_and_read_path_restores_the_last_valid_gameplay_model(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    job = make_confirmed_job()
    (tmp_path / job["id"]).mkdir()
    valid = ensure_gameplay_review_model(job)
    valid["chapters"] = [{
        "id": "GCH-001",
        "title": "已批准章节",
        "plannerSections": {"normalFlow": ["玩家触发入口，系统反馈并进入下一状态。"]},
    }]
    valid["revision"] = 37
    valid["lifecycleState"] = "ready"
    valid["contentState"] = "ready"
    valid.setdefault("reviewState", {})["status"] = "chapter_review"
    storage.save_job(job)

    failed = storage.load_job(job["id"])
    failed["gameplayReviewModel"] = {
        "schemaVersion": "1.0",
        "standard": "GVE16",
        "revision": 1,
        "jobId": job["id"],
        "chapters": [],
    }
    failed["gameplayReviewGeneration"] = {"status": "failed"}
    storage.save_job(failed)

    persisted = storage.load_job(job["id"])
    assert persisted["gameplayReviewLastValidModel"]["revision"] == 37
    restored = ensure_gameplay_review_model(deepcopy(persisted))
    assert restored["revision"] == 37
    assert [(item["id"], item["title"]) for item in restored["chapters"]] == [
        ("GCH-001", "已批准章节")
    ]
    assert restored["lifecycleState"] == "ready"
    assert restored["contentState"] == "failed"


def test_structure_only_chapters_never_replace_or_hide_the_last_valid_detail_model(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    job = make_confirmed_job()
    (tmp_path / job["id"]).mkdir()
    valid = ensure_gameplay_review_model(job)
    valid.update({
        "revision": 37,
        "chapters": [{
            "id": "GCH-001",
            "title": "已批准章节",
            "plannerSections": {"normalFlow": ["玩家触发入口，系统反馈并进入下一状态。"]},
        }],
        "lifecycleState": "ready",
        "contentState": "ready",
    })
    valid.setdefault("reviewState", {})["status"] = "chapter_review"
    storage.save_job(job)

    pending = storage.load_job(job["id"])
    pending["gameplayReviewModel"] = {
        "schemaVersion": "1.0",
        "standard": "GVE16",
        "revision": 38,
        "jobId": job["id"],
        "chapters": [{"id": "GCH-STRUCTURE", "title": "只有目录骨架"}],
        "reviewState": {"status": "detail_generation_pending"},
        "contentState": "pending",
    }
    pending["gameplayReviewGeneration"] = {"status": "failed"}
    storage.save_job(pending)

    persisted = storage.load_job(job["id"])
    assert persisted["gameplayReviewLastValidModel"]["revision"] == 37
    restored = ensure_gameplay_review_model(deepcopy(persisted))
    assert restored["revision"] == 37
    assert restored["chapters"][0]["title"] == "已批准章节"


def test_pending_structure_displays_the_last_valid_detail_instead_of_hiding_it():
    job = make_confirmed_job()
    job["gameplayReviewLastValidModel"] = {
        "jobId": job["id"],
        "revision": 37,
        "reviewState": {"status": "chapter_review"},
        "chapters": [{
            "id": "GCH-001",
            "title": "已批准章节",
            "plannerSections": {"normalFlow": ["玩家触发入口，系统反馈并进入下一状态。"]},
        }],
    }
    job["gameplayReviewModel"] = {
        "jobId": job["id"],
        "revision": 38,
        "reviewState": {"status": "detail_generation_pending"},
        "contentState": "pending",
        "chapters": [{"id": "GCH-STRUCTURE", "title": "只有目录骨架"}],
    }
    job["gameplayReviewGeneration"] = {"status": "running"}

    restored = ensure_gameplay_review_model(job)

    assert restored["revision"] == 37
    assert restored["contentState"] == "pending"


def test_detail_validity_requires_real_reviewable_content_and_exact_job_ownership():
    skeleton = {
        "jobId": "job-1",
        "reviewState": {"status": "chapter_review"},
        "chapters": [{"id": "GCH-001", "title": "只有标题"}],
    }
    detailed = deepcopy(skeleton)
    detailed["chapters"][0]["plannerSections"] = {
        "normalFlow": ["玩家触发入口，系统反馈并进入下一状态。"]
    }

    assert gameplay_model_has_reviewable_detail(skeleton, expected_job_id="job-1") is False
    assert gameplay_model_has_reviewable_detail(detailed, expected_job_id="job-1") is True
    assert gameplay_model_has_reviewable_detail(detailed, expected_job_id="job-2") is False
    detailed.pop("jobId")
    assert gameplay_model_has_reviewable_detail(detailed, expected_job_id="job-1") is False

    metadata_only = deepcopy(skeleton)
    metadata_only["chapters"][0].update({
        "claims": [{"id": "CLM-001", "sourceType": "material"}],
        "mechanism": {"type": "core_loop"},
    })
    assert gameplay_model_has_reviewable_detail(metadata_only, expected_job_id="job-1") is False
    metadata_only["chapters"][0]["claims"][0]["text"] = "玩家点击入口后进入下一状态。"
    assert gameplay_model_has_reviewable_detail(metadata_only, expected_job_id="job-1") is True


def test_storage_never_captures_a_detailed_model_owned_by_another_job(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    job = make_confirmed_job()
    (tmp_path / job["id"]).mkdir()
    job["gameplayReviewModel"] = {
        "jobId": "another-job",
        "reviewState": {"status": "chapter_review"},
        "chapters": [{
            "id": "GCH-001",
            "plannerSections": {"normalFlow": ["foreign detail"]},
        }],
    }

    storage.save_job(job)

    assert "gameplayReviewLastValidModel" not in storage.load_job(job["id"])


def test_last_valid_gameplay_snapshot_is_private():
    job = make_confirmed_job()
    job["gameplayReviewLastValidModel"] = {"chapters": [{"id": "GCH-001"}]}

    assert "gameplayReviewLastValidModel" not in server._public_job(job)


def test_public_running_generation_never_falls_back_to_a_failure_message():
    public = server._public_gameplay_review_generation({
        "status": "running",
        "progress": 28,
        "phase": "validating",
        "message": "Generating gameplay details from the confirmed structure.",
    })

    assert public["status"] == "running"
    assert public["message"] == "Generating gameplay details from the confirmed structure."


def test_generation_display_progress_never_moves_backwards_during_the_single_quality_repair():
    assert server._monotonic_generation_progress({"progress": 90}, 55) == 90
    assert server._monotonic_generation_progress({"progress": 90}, 5) == 90
    assert server._monotonic_generation_progress({"progress": 90}, 100) == 100


def test_current_gameplay_model_without_job_ownership_is_isolated():
    job = make_confirmed_job()
    job["gameplayReviewModel"] = {
        "revision": 99,
        "reviewState": {"status": "chapter_review"},
        "chapters": [{
            "id": "FOREIGN",
            "plannerSections": {"normalFlow": ["foreign content"]},
        }],
    }

    isolated = ensure_gameplay_review_model(job)

    assert isolated["jobId"] == job["id"]
    assert isolated["chapters"] == []
