from copy import deepcopy
import json

from backend.gameplay_copy import consolidate_gameplay_chapters, migrate_gameplay_presentation
from scripts import migrate_current_gameplay_task


def migration_job():
    return {
        "id": "job-migrate",
        "gameplayReviewModel": {
            "revision": 7,
            "interactionRevision": 3,
            "reviewState": {},
            "editHistory": [{"undo": [{"legacy": "变化前生命值"}], "redo": []}],
            "chapters": [{
                "id": "GCH-001", "scope": "生命值状态管理", "systemName": "战斗系统",
                "mechanism": {"type": "custom", "description": "载具受击后扣减生命值。"},
                "confirmation": {"confirmed": True},
                "parameterSchema": [
                    {"name": "生命", "type": "整数", "unit": "点", "defaultValue": 100,
                     "plannerMeaning": "可承受的伤害总量", "deliverySource": "策划人工确认"},
                    {"name": "变化前生命值", "plannerMeaning": "参与生命值状态管理计算的数值", "evidenceLevel": "根据素材推断"},
                    {"name": "攻击修正", "plannerMeaning": "额外伤害变化", "evidenceLevel": "根据素材推断"},
                ],
                "formulae": [{"expression": "变化后生命值 = 变化前生命值 - 本次承受伤害", "evidenceLevel": "根据素材推断"}],
            }],
            "directory": {
                "presentationVersion": 10, "understandingSource": "planner",
                "understanding": {"summary": "策划手写概述"},
                "entries": [{"chapterId": "GCH-001", "title": "生命值状态管理", "summary": "策划手写摘要", "summarySource": "planner"}],
            },
            "systems": [],
            "tables": [{
                "id": "GTB-009", "kind": "chapter_parameters", "title": "旧参数表", "chapterIds": ["GCH-001"],
                "rows": [["生命", "整数（点）", "100", "120", "已确认", "确认"]], "status": "reviewed",
                "rowReviews": [{"rowIndex": 0, "value": "120", "confirmed": True}],
            }],
            "diagrams": [],
        },
    }


def test_dry_run_is_read_only_and_reports_cleanup_and_rebuild():
    job = migration_job()
    before = deepcopy(job)

    report = migrate_gameplay_presentation(job, dry_run=True)

    assert job == before
    assert report["dryRun"] is True
    assert report["removed"] == {"inferredParameters": 2, "inferredFormulae": 1, "historySnapshots": 1}
    assert report["plannerContentPreserved"] is True
    assert report["rebuilt"]["tables"] == 1


def test_apply_preserves_planner_copy_and_reviewed_table_value_but_clears_history():
    job = migration_job()

    migrate_gameplay_presentation(job, rebuild_derived=True)

    model = job["gameplayReviewModel"]
    assert model["directory"]["understanding"]["summary"] == "策划手写概述"
    assert model["directory"]["entries"][0]["summary"] == "策划手写摘要"
    assert model["chapters"][0]["parameterSchema"] == [{
        "name": "生命", "type": "整数", "unit": "点", "defaultValue": 100,
        "plannerMeaning": "可承受的伤害总量", "deliverySource": "策划人工确认",
    }]
    assert model["chapters"][0]["formulae"] == []
    assert model["editHistory"] == []
    assert model["tables"][0]["rows"][0][3:5] == ["120", "已确认"]
    assert model["tables"][0]["status"] == "reviewed"
    assert job["gameplayMigration"]["plannerContentPreserved"] is True


def test_rebuild_never_overwrites_curated_diagram_svg():
    job = migration_job()
    curated = {
        "id": "GDI-101", "type": "state_flow", "chapterIds": ["GCH-001"],
        "title": "人工验收图", "svg": "<svg><path d='M0 0L10 10'/></svg>",
        "status": "reviewed", "freshness": "current", "generationMode": "curated",
    }
    job["gameplayReviewModel"]["diagrams"] = [deepcopy(curated)]

    migrate_gameplay_presentation(job, rebuild_derived=True)

    restored = next(item for item in job["gameplayReviewModel"]["diagrams"] if item["id"] == "GDI-101")
    assert restored == curated


def test_default_display_compatibility_does_not_rebuild_or_increment_revision():
    job = migration_job()
    revision = job["gameplayReviewModel"]["revision"]
    original_tables = deepcopy(job["gameplayReviewModel"]["tables"])

    migrate_gameplay_presentation(job)

    assert job["gameplayReviewModel"]["revision"] == revision
    assert job["gameplayReviewModel"]["tables"] == original_tables
    assert "gameplayMigration" not in job


def test_chapter_consolidation_preserves_facts_and_rewrites_artifact_links():
    model = {
        "revision": 4,
        "reviewState": {"previewRevision": 4},
        "chapters": [
            {"id": "GCH-001", "scope": "移动", "claims": [{"text": "事实A"}], "sourceFrameIds": ["F1"], "plannerSections": {"keyRules": ["规则A"]}, "inlineEvidence": [], "parameters": {}, "confirmation": {"confirmed": True}},
            {"id": "GCH-002", "scope": "生命", "claims": [{"text": "事实B"}], "sourceFrameIds": ["F2"], "plannerSections": {"keyRules": ["规则B"]}, "inlineEvidence": [], "parameters": {}, "confirmation": {"confirmed": True}},
        ],
        "directory": {"revision": 2, "entries": [{"id": "GDE-001", "chapterId": "GCH-001"}, {"id": "GDE-002", "chapterId": "GCH-002"}]},
        "tables": [{"chapterIds": ["GCH-002"]}], "diagrams": [],
    }

    consolidate_gameplay_chapters(model, [{"chapterIds": ["GCH-001", "GCH-002"], "title": "移动与生存", "summary": "合并摘要"}])

    assert len(model["chapters"]) == 1
    assert [item["text"] for item in model["chapters"][0]["claims"]] == ["事实A", "事实B"]
    assert model["chapters"][0]["sourceFrameIds"] == ["F1", "F2"]
    assert model["chapters"][0]["plannerSections"]["keyRules"] == ["规则A", "规则B"]
    assert model["directory"]["entries"][0]["title"] == "移动与生存"
    assert model["tables"][0]["chapterIds"] == ["GCH-001"]
    assert model["revision"] == 5
    assert model["reviewState"]["previewRevision"] is None


def test_script_creates_readable_backup_and_atomic_current_job(tmp_path, monkeypatch):
    path = tmp_path / "job.json"
    path.write_text(json.dumps(migration_job(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(migrate_current_gameplay_task, "build_final_review_preview", lambda job, _path: {
        "gameplayRevision": job["gameplayReviewModel"]["revision"], "exportReady": False, "blockerIds": ["REVIEW_REQUIRED"]
    })

    result = migrate_current_gameplay_task.execute(path, apply=True)

    backup = result["backup"]
    restored = json.loads(path.read_text(encoding="utf-8"))
    assert json.loads(open(backup, encoding="utf-8").read())["id"] == "job-migrate"
    assert restored["id"] == "job-migrate"
    assert restored["gameplayFinalPreview"]["gameplayRevision"] == restored["gameplayReviewModel"]["revision"]
    assert result["beforeHash"] != result["afterHash"]


def test_script_restores_backup_when_preview_rebuild_fails(tmp_path, monkeypatch):
    path = tmp_path / "job.json"
    path.write_text(json.dumps(migration_job(), ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(
        migrate_current_gameplay_task,
        "build_final_review_preview",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("preview failed")),
    )

    try:
        migrate_current_gameplay_task.execute(path, apply=True)
    except RuntimeError as error:
        assert str(error) == "preview failed"
    else:
        raise AssertionError("migration failure should propagate")

    assert path.read_bytes() == before
