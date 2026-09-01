import hashlib
import copy
import json
from pathlib import Path

from backend.acceptance_evidence import validate_stage3_evidence
from backend.delivery_alignment import canonical_delivery_contract, delivery_alignment_report
from backend.gameplay_render import authoritative_gameplay_model, render_gameplay_document_sections
from backend.stage3_quality_gate import stage3_quality_gate_report
from tests.test_gameplay_render import complete_job


ROOT = Path(__file__).resolve().parents[1]
MECHANISM_CASES = json.loads((ROOT / "data/calibration/gve16/stage3-mechanism-cases.json").read_text(encoding="utf-8"))["cases"]


def test_tc28_p7_and_feishu_share_one_canonical_delivery_contract():
    job = complete_job()
    model = job["gameplayReviewModel"]

    contract = canonical_delivery_contract(model)
    report = delivery_alignment_report(job)

    assert report["passed"]
    assert report["fingerprint"] == contract["fingerprint"]
    assert report["revision"] == model["revision"]
    assert report["expectedChapterOrder"] == report["renderedChapterOrder"]


def test_tc28_contract_fingerprint_changes_when_published_copy_changes():
    job = complete_job()
    before = canonical_delivery_contract(job["gameplayReviewModel"])["fingerprint"]
    job["gameplayReviewModel"]["chapters"][0]["plannerSections"]["summary"] = "修改后的确认正文。"
    after = canonical_delivery_contract(job["gameplayReviewModel"])["fingerprint"]

    assert before != after


def test_structured_contract_ignores_legacy_cache_and_tracks_publication_rules():
    job = complete_job()
    model = job["gameplayReviewModel"]
    model["contentModelVersion"] = 2
    model["ruleIntelligenceProjection"] = {
        "authorityMode": "structured_rules",
        "publication": {"chapters": [{
            "chapterId": "GCH-001", "title": "攻击规则", "publicationEligibility": "eligible",
            "ruleDefinitions": [{"ruleId": "R-1", "behavior": "每 1 秒执行一次攻击。"}],
            "references": [], "gaps": [],
        }]},
    }
    before = canonical_delivery_contract(model)
    model["chapters"][0]["plannerSections"]["normalFlow"] = ["不得进入发布的旧缓存。"]
    cache_changed = canonical_delivery_contract(model)
    model["ruleIntelligenceProjection"]["publication"]["chapters"][0]["ruleDefinitions"][0]["behavior"] = "每 2 秒执行一次攻击。"
    rule_changed = canonical_delivery_contract(model)

    assert cache_changed["fingerprint"] == before["fingerprint"]
    assert rule_changed["fingerprint"] != before["fingerprint"]


def test_web_and_feishu_use_the_same_publication_projection_without_final_pollution():
    job = complete_job()
    model = job["gameplayReviewModel"]
    model["contentModelVersion"] = 2
    model["chapters"][0]["plannerSections"]["normalFlow"] = ["仅存在于 plannerSections 的污染。"]
    model["presentationEvidence"] = [{"text": "仅表现证据。"}]
    model["ruleIntelligenceProjection"] = {
        "authorityMode": "structured_rules",
        "possibleDuplicates": [{"ruleIds": ["R-DEBUG"]}],
        "publication": {"chapters": [{
            "chapterId": "GCH-001", "title": "攻击规则", "publicationEligibility": "eligible",
            "ruleDefinitions": [{"ruleId": "R-PUBLIC", "behavior": "每 1 秒执行一次攻击。"}],
            "references": [], "gaps": [],
        }]},
        "guard": {"passed": True, "blockedRuleIds": []},
    }

    web_model = authoritative_gameplay_model(model)
    contract = canonical_delivery_contract(model)
    rendered = render_gameplay_document_sections(job).xml
    web_lines = [item["text"] for item in web_model["chapters"][0]["plannerSections"]["normalFlow"]]

    assert web_lines == contract["chapters"][0]["normalFlow"] == ["每 1 秒执行一次攻击。"]
    assert "每 1 秒执行一次攻击" in rendered
    for forbidden in ("仅存在于 plannerSections 的污染", "仅表现证据", "R-PUBLIC", "R-DEBUG"):
        assert forbidden not in rendered


def test_tc28_contract_deduplicates_rephrased_rules_using_reviewed_wording():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSections"]["keyRules"] = [
        "首领来袭是自动阶段反馈，不要求玩家点击确认。",
        "达到首领阶段条件后自动播放“首领来袭”警告，不要求玩家点击确认。",
    ]

    contract = canonical_delivery_contract(job["gameplayReviewModel"])

    assert contract["chapters"][0]["keyRules"] == [
        "达到首领阶段条件后自动播放“首领来袭”警告，不要求玩家点击确认。"
    ]


def test_tc28_contract_tracks_formula_table_and_planning_board_independently():
    job = complete_job()
    model = job["gameplayReviewModel"]
    model["chapters"][0]["formulae"] = [{"name": "结算", "expression": "结果=A×B"}]
    model["tables"] = [{"id": "T1", "chapterIds": ["GCH-001"], "status": "reviewed", "columns": ["字段", "值"], "rows": [["倍率", "2"]]}]
    before = canonical_delivery_contract(model)["carrierFingerprints"]

    formula_changed = copy.deepcopy(model)
    formula_changed["chapters"][0]["formulae"][0]["expression"] = "结果=A+B"
    assert canonical_delivery_contract(formula_changed)["carrierFingerprints"]["formulae"] != before["formulae"]

    table_changed = copy.deepcopy(model)
    table_changed["tables"][0]["rows"][0][1] = "3"
    assert canonical_delivery_contract(table_changed)["carrierFingerprints"]["tables"] != before["tables"]

    board_changed = copy.deepcopy(model)
    board_changed["interactionRevision"] += 1
    assert canonical_delivery_contract(board_changed)["carrierFingerprints"]["planningBoard"] != before["planningBoard"]


def test_tc28_wrong_interaction_binding_fails_with_actionable_remediation():
    job = complete_job()
    job["gameplayReviewModel"]["interactionRevision"] += 1

    report = delivery_alignment_report(job)

    assert not report["passed"]
    finding = next(item for item in report["differences"] if item["carrier"] == "策划草图")
    assert set(finding["remediation"]) == {"basis", "action", "carrier", "impact", "retest"}


def test_tc28_nonempty_formula_and_configuration_table_reach_feishu_output():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["parameterSchema"] = [{"name": "基础倍率", "type": "number", "unit": "倍", "defaultValue": "2"}]
    chapter["formulae"] = [{"name": "最终结果", "expression": "最终结果=基础值×基础倍率"}]
    job["gameplayReviewModel"]["tables"] = [{
        "id": "T1", "chapterIds": [chapter["id"]], "status": "reviewed",
        "columns": ["字段", "类型", "单位", "默认值"], "rows": [["基础倍率", "number", "倍", "2"]],
    }]

    report = delivery_alignment_report(job)

    assert report["passed"]
    assert report["formulaCount"] == 1
    assert report["tableCount"] == 1
    assert report["missingCopy"] == []


def test_p7_keeps_every_reviewed_execution_step_instead_of_truncating_after_four():
    job = complete_job()
    flow = [f"执行步骤 {index}" for index in range(1, 7)]
    job["gameplayReviewModel"]["chapters"][0]["plannerSections"]["normalFlow"] = flow

    rendered = render_gameplay_document_sections(job).xml

    assert all(step in rendered for step in flow)
    assert delivery_alignment_report(job)["passed"]


def test_parameter_names_are_concise_and_adopted_names_drop_suggestion_copy():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["fieldDictionary"] = [{
        "plannerName": "载具当前生命值", "suggestedCodeName": "vehicleCurrentHp",
        "type": "整数", "unit": "点", "source": "竞品截图可见信息",
        "status": "建议命名，待程序或配置表确认",
    }, {
        "plannerName": "武器名称", "suggestedCodeName": "weaponName",
        "type": "文本", "source": "策划采用", "status": "confirmed", "decisionStatus": "accepted",
    }]

    rendered = render_gameplay_document_sections(job).xml

    assert "参数命名" in rendered
    assert "载具当前生命值" in rendered
    assert "vehicleCurrentHp" in rendered
    assert "建议" in rendered
    assert "待程序或配置表确认" not in rendered
    assert "整数" not in rendered
    assert "竞品截图可见信息" not in rendered
    assert "<b>武器名称：</b><code>weaponName</code>" in rendered
    assert "策划字段名" not in rendered


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _entries():
    return [{
        "caseId": f"S3-TC{index:02d}", "visibleCaseId": f"S3-TC{index:02d}",
        "inputHash": _hash(f"input-{index}"), "bodyHash": _hash(f"body-{index}"),
        "screenshotHash": _hash(f"shot-{index}"), "humanInspected": True,
    } for index in range(1, 31)]


def test_tc30_accepts_only_thirty_unique_correctly_bound_and_inspected_evidence_items():
    report = validate_stage3_evidence(_entries(), official_before="job-hash", official_after="job-hash")

    assert report == {"passed": True, "findings": [], "caseCount": 30, "officialJobUnchanged": True}


def test_tc30_rejects_duplicate_screenshot_wrong_identity_and_changed_official_job():
    entries = _entries()
    entries[1]["screenshotHash"] = entries[0]["screenshotHash"]
    entries[2]["visibleCaseId"] = "S3-TC02"
    entries[3]["humanInspected"] = False

    report = validate_stage3_evidence(entries, official_before="before", official_after="after")
    messages = "\n".join(report["findings"])

    assert not report["passed"]
    assert "重复截图哈希" in messages
    assert "截图身份" in messages
    assert "人工目检" in messages
    assert "正式任务执行前后哈希不一致" in messages


def test_tc29_real_gate_distinguishes_pass_granularity_failure_and_language_failure():
    complete = copy.deepcopy(next(item["model"] for item in MECHANISM_CASES if item["id"] == "S3-TC12"))
    shallow = copy.deepcopy(next(item["model"] for item in MECHANISM_CASES if item["id"] == "S3-TC13"))
    degraded = copy.deepcopy(complete)
    degraded["chapters"][0]["plannerSections"]["summary"] = "本节主要介绍奖励候选机制，并通过状态隔离形成闭环。"

    passed = stage3_quality_gate_report(complete)
    granularity_failed = stage3_quality_gate_report(shallow)
    language_failed = stage3_quality_gate_report(degraded)

    assert passed["passed"]
    assert not granularity_failed["passed"] and granularity_failed["granularityAudit"]["findings"]
    assert not language_failed["passed"] and language_failed["languageAudit"]["findings"]
    assert granularity_failed["languageAudit"]["passed"]
    assert language_failed["granularityAudit"]["passed"]
