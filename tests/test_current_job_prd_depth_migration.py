from copy import deepcopy
import json
from pathlib import Path

from backend.feishu_language_quality import language_quality_report
from backend.gameplay_domain_policy import provenance_scope_report
from backend.planning_content_policy import carrier_policy_report
from backend.granularity_audit import mechanism_closure_report
from scripts.migrate_current_job_prd_depth import migrate_job


ROOT = Path(__file__).resolve().parents[1]
CURRENT_JOB = ROOT / "data" / "jobs" / "8312a91c89e144e6a59f81b982f14c06" / "job.json"


def current_job_fixture():
    duplicate = "武器命中目标后扣除生命值。"
    sample_only = "进入关卡时包含1个默认武器栏和4个自选栏。"
    return {
        "id": "fixture-job",
        "gameplayReviewModel": {
            "revision": 7,
            "chapters": [
                {
                    "id": "C1",
                    "scope": "命中、反馈与伤害归集",
                    "plannerSections": {
                        "attributeHeading": "武器",
                        "summary": "武器自动攻击进入范围的目标。",
                        "normalFlow": [duplicate],
                        "keyRules": [
                            sample_only,
                            "奖励区包含多类奖励，当前项目应逐项保留而不是概括处理。",
                        ],
                    },
                    "objectStates": [duplicate],
                    "runtimeResponsibilities": [duplicate],
                    "presentationRules": [duplicate],
                    "provenanceClaims": [
                        {
                            "text": sample_only,
                            "sourceScope": "sample_reserve",
                            "publicationAllowed": True,
                        }
                    ],
                    "contentInventory": ["武器", "目标", "伤害"],
                    "sourceFrameIds": ["F0001"],
                },
                {
                    "id": "C2",
                    "scope": "局内升级与三选一强化",
                    "plannerSections": {
                        "summary": "升级后展示三个候选。",
                        "normalFlow": ["玩家确认一项强化后恢复战斗。"],
                    },
                    "unresolvedResponsibilities": ["weights", "replacement"],
                    "contentInventory": ["候选", "选择", "刷新"],
                    "sourceFrameIds": ["F0002"],
                },
            ],
            "reviewState": {"previewRevision": 7},
        },
    }


def test_migration_removes_duplicate_secondary_carriers_and_audit_voice():
    migrated = migrate_job(current_job_fixture())
    model = migrated["gameplayReviewModel"]
    weapon = model["chapters"][0]

    assert weapon["scope"] == "武器"
    assert weapon["objectStates"] == []
    assert weapon["runtimeResponsibilities"] == []
    assert weapon["presentationRules"] == []
    assert len(weapon["carrierRefs"]) == 3
    assert language_quality_report(model)["passed"] is True
    assert carrier_policy_report(model)["passed"] is True


def test_migration_demotes_sample_only_current_facts():
    migrated = migrate_job(current_job_fixture())
    model = migrated["gameplayReviewModel"]
    weapon = model["chapters"][0]
    published = str(weapon["plannerSections"])

    assert "1个默认武器栏和4个自选栏" not in published
    assert weapon["provenanceClaims"][0]["publicationAllowed"] is False
    assert weapon["provenanceClaims"][0]["usage"] == "decision_question"
    assert provenance_scope_report(model)["passed"] is True


def test_migration_activates_only_evidenced_domains_and_records_gve16_roles():
    migrated = migrate_job(current_job_fixture())
    weapon, random_choice = migrated["gameplayReviewModel"]["chapters"]

    assert weapon["domainStates"]["combat"] == "applicable"
    assert weapon["domainStates"]["inventory"] == "not_applicable"
    assert random_choice["domainStates"]["random"] == "decision_required"
    assert random_choice["domainStates"]["sweep"] == "not_applicable"
    assert set(random_choice["sampleAlignment"]) >= {
        "content_inventory",
        "execution_sequence",
        "boundary_and_lifecycle",
        "decision_coverage",
    }


def test_migration_keeps_unknown_algorithms_as_actionable_decisions():
    migrated = migrate_job(current_job_fixture())
    random_choice = migrated["gameplayReviewModel"]["chapters"][1]
    cards = random_choice["decisionCards"]

    covered = {
        responsibility
        for card in cards
        for responsibility in (
            card.get("responsibilities") or [card.get("responsibility")]
        )
        if responsibility
    }
    assert {"weights", "replacement", "filter", "duplicate", "empty", "reset"} <= covered
    assert all(len(card["options"]) >= 2 for card in cards)
    assert all(card["allowCustom"] and card["allowSkip"] for card in cards)
    assert all(card["impacts"] for card in cards)


def test_migration_is_pure_and_increments_revision_once():
    source = current_job_fixture()
    original = deepcopy(source)

    migrated = migrate_job(source)

    assert source == original
    assert migrated["gameplayReviewModel"]["revision"] == 8
    assert "previewRevision" not in migrated["gameplayReviewModel"]["reviewState"]


def test_migration_promotes_explicit_lifecycle_facts_and_has_no_false_green_gap():
    source = current_job_fixture()
    source["gameplayReviewModel"]["chapters"][0]["plannerSections"]["specialCases"] = [
        "武器类型选定后本局内不可更换，战斗结束后清空栏位状态。"
    ]

    model = migrate_job(source)["gameplayReviewModel"]
    weapon = model["chapters"][0]

    assert weapon["lifecycleRules"] == [
        "武器类型选定后本局内不可更换，战斗结束后清空栏位状态。"
    ]
    assert all(
        state != "missing"
        for chapter in model["chapters"]
        for state in chapter["sampleAlignment"].values()
    )
    assert mechanism_closure_report(model)["passed"] is True


def test_migration_keeps_directory_titles_summaries_and_understanding_semantically_aligned():
    source = current_job_fixture()
    source["gameplayReviewModel"]["directory"] = {
        "understanding": {"summary": "旧的重复描述"},
        "entries": [
            {"chapterId": "C1", "title": "旧武器标题", "summary": "载具移动描述"},
            {"chapterId": "C2", "title": "旧强化标题", "summary": "武器自动攻击描述"},
        ],
    }

    model = migrate_job(source)["gameplayReviewModel"]
    entries = model["directory"]["entries"]

    assert entries[0]["title"] == "武器"
    assert "索敌范围" in entries[0]["summary"]
    assert entries[1]["title"] == "局内强化"
    assert "生成强化候选" in entries[1]["summary"]
    assert model["directory"]["understanding"]["coreLoop"].startswith("载具推进")


def test_migration_is_idempotent_for_generated_decision_cards():
    once = migrate_job(current_job_fixture())
    twice = migrate_job(once)

    once_cards = [
        card["id"]
        for chapter in once["gameplayReviewModel"]["chapters"]
        for card in chapter.get("decisionCards") or []
    ]
    twice_cards = [
        card["id"]
        for chapter in twice["gameplayReviewModel"]["chapters"]
        for card in chapter.get("decisionCards") or []
    ]

    assert twice_cards == once_cards


def test_migration_routes_pure_presentation_to_planning_trace_and_keeps_logic_in_prose():
    source = current_job_fixture()
    source["gameplayReviewModel"]["chapters"][0]["plannerSections"]["normalFlow"] = [
        "载具沿道路自动前进，同时在载具上方显示生命条。",
        "顶部显示本局计时。",
    ]
    source["gameplayReviewModel"]["planningGameplayTrace"] = []

    model = migrate_job(source)["gameplayReviewModel"]
    weapon = model["chapters"][0]
    prose = "\n".join(weapon["plannerSections"]["normalFlow"])
    board_copy = "\n".join(
        item["text"] for item in model["planningGameplayTrace"] if item["status"] == "board_only"
    )

    assert "载具沿道路自动前进" in prose
    assert "上方显示生命条" not in prose
    assert "顶部显示本局计时" not in prose
    assert "上方显示生命条" in board_copy
    assert "顶部显示本局计时" in board_copy


def test_current_job_p1_migration_separates_level_monster_and_settlement_responsibilities():
    source = json.loads(CURRENT_JOB.read_text(encoding="utf-8"))

    model = migrate_job(source)["gameplayReviewModel"]
    chapters = {chapter["scope"]: chapter for chapter in model["chapters"]}

    assert set(chapters) == {
        "载具", "武器", "局内强化", "终极强化", "武器抽取", "怪物", "关卡", "结算"
    }
    assert [entry["title"] for entry in model["directory"]["entries"]] == [
        chapter["scope"] for chapter in model["chapters"]
    ]
    assert all(entry.get("id") for entry in model["directory"]["entries"])
    assert next(entry for entry in model["directory"]["entries"] if entry["title"] == "关卡")["sectionTitle"] == "关卡推进"

    monster_text = json.dumps(chapters["怪物"]["plannerSections"], ensure_ascii=False)
    assert all(term not in monster_text for term in ("首领阶段", "整局时间", "胜利结算"))

    level_text = json.dumps(chapters["关卡"]["plannerSections"], ensure_ascii=False)
    assert all(term in level_text for term in ("波次", "首领阶段", "时间", "胜利", "失败"))

    settlement_text = json.dumps(chapters["结算"]["plannerSections"], ensure_ascii=False)
    assert all(term in settlement_text for term in ("成功结算", "失败结算", "中断", "奖励", "重复领取"))


def test_current_job_p1_migration_exposes_fields_formula_status_lifecycle_and_fresh_bindings():
    source = json.loads(CURRENT_JOB.read_text(encoding="utf-8"))

    model = migrate_job(source)["gameplayReviewModel"]
    chapters = {chapter["scope"]: chapter for chapter in model["chapters"]}

    assert all(chapter.get("fieldDictionary") for chapter in chapters.values())
    assert all(chapter.get("formulaStatus") in {"supported", "decision_required", "not_applicable"} for chapter in chapters.values())
    assert all(chapter.get("lifecycleRules") for chapter in chapters.values())
    assert chapters["怪物"]["formulaStatus"] == "supported"
    assert chapters["怪物"]["formulae"]
    assert chapters["结算"]["formulaStatus"] == "supported"

    level_id = chapters["关卡"]["id"]
    level_diagrams = [diagram for diagram in model["diagrams"] if level_id in diagram.get("chapterIds", [])]
    assert level_diagrams
    assert all(diagram["status"] == "stale" for diagram in level_diagrams)
