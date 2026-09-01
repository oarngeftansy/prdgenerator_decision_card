from backend.rule_semantic_completion import (
    build_rule_semantic_contracts,
    build_review_promotions,
    render_semantically_completed_preview,
)
import json
from pathlib import Path


def _rule(rule_id="R-REFRESH", statement="三选一支持观看广告刷新候选，广告刷新受次数限制。"):
    return {"ruleId": rule_id, "statement": statement, "ownerChapter": "三选一",
            "ruleGroup": "刷新", "evidenceStatus": "directly_observed",
            "evidenceRefs": [{"evidenceId": "F0002", "sourcePath": "C:/evidence/F0002.jpg"}]}


def _refresh_spec():
    return {
        "ruleSemanticId": "RSC-REFRESH", "mechanic": "广告刷新",
        "ownerChapter": "三选一", "ruleGroup": "刷新", "existenceStatus": "confirmed",
        "coreRuleIds": ["R-REFRESH"],
        "dimensions": [
            {"dimensionId": "refresh_action", "label": "刷新方式", "kind": "rule",
             "status": "observed", "displayText": "可观看广告刷新当前3项候选。"},
            {"dimensionId": "limit_exists", "label": "次数限制", "kind": "rule",
             "status": "observed", "displayText": "广告刷新存在次数限制。",
             "observedCurrentState": "1/1"},
            {"dimensionId": "max_count", "label": "刷新次数上限", "kind": "parameter",
             "status": "unresolved", "reviewRoute": "P6", "valueType": "integer"},
            {"dimensionId": "reset_scope", "label": "次数重置周期", "kind": "rule",
             "status": "unresolved", "reviewRoute": "P4",
             "options": ["每次三选一", "每局", "每日", "自定义"]},
        ],
    }


def test_confirmed_refresh_mechanic_expands_required_dimensions_without_using_1_1_as_max():
    report = build_rule_semantic_contracts([_rule()], [_refresh_spec()])
    contract = report["contracts"][0]
    assert contract["mechanic"] == "广告刷新"
    assert {item["dimensionId"] for item in contract["unresolvedRuleDimensions"]} == {"reset_scope"}
    assert {item["dimensionId"] for item in contract["unresolvedParameters"]} == {"max_count"}
    assert contract["observedValues"] == [{"dimensionId": "limit_exists", "currentObservedState": "1/1"}]
    assert all(item.get("value") != 1 for item in contract["unresolvedParameters"])
    assert contract["completionStatus"] == "semantically_under_expanded"


def test_possible_or_unsupported_mechanic_cannot_create_contract():
    spec = _refresh_spec()
    spec["existenceStatus"] = "possible"
    report = build_rule_semantic_contracts([_rule()], [spec])
    assert report["contracts"] == []
    assert report["rejectedSpecs"][0]["reason"] == "mechanic_not_confirmed"


def test_review_promotion_routes_rule_to_p4_and_number_to_p6_without_auto_approval():
    contracts = build_rule_semantic_contracts([_rule()], [_refresh_spec()])["contracts"]
    decisions = build_review_promotions(contracts)
    by_dimension = {item["dimensionId"]: item for item in decisions}
    assert by_dimension["reset_scope"]["reviewStage"] == "P4"
    assert by_dimension["max_count"]["reviewStage"] == "P6"
    assert by_dimension["max_count"]["inputContract"]["valueType"] == "integer"
    assert all(item["approvalStatus"] == "unreviewed" for item in decisions)
    assert all(item["recommendationOnly"] is True for item in decisions)


def test_gameplay_parameter_can_require_unit_without_guessing_unit_value():
    spec = _refresh_spec()
    spec["dimensions"][2]["unitRequired"] = True
    decision = next(item for item in build_review_promotions(
        build_rule_semantic_contracts([_rule()], [spec])["contracts"]
        ) if item["dimensionId"] == "max_count")
    assert decision["inputContract"]["control"] == "number_with_unit"
    assert decision["inputContract"]["unitRequired"] is True
    assert decision["inputContract"]["unit"] is None


def test_explicit_daily_3_3_resolves_value_but_unknown_daily_n_can_route_to_p6():
    explicit = {
        "ruleSemanticId": "RSC-DAILY", "mechanic": "每日挑战次数",
        "ownerChapter": "结算", "ruleGroup": "奖励与次数", "existenceStatus": "confirmed",
        "coreRuleIds": ["R-DAILY"], "dimensions": [
            {"dimensionId": "reset_scope", "label": "重置周期", "kind": "rule", "status": "observed",
             "value": "daily", "displayText": "挑战次数按日重置。"},
            {"dimensionId": "max_count", "label": "每日挑战次数上限", "kind": "parameter", "status": "observed",
             "value": 3, "displayText": "每日挑战次数上限为3次。"},
        ]}
    daily_rule = _rule("R-DAILY", "每日挑战次数上限为3次。")
    contract = build_rule_semantic_contracts([daily_rule], [explicit])["contracts"][0]
    assert build_review_promotions([contract]) == []
    unknown = {**explicit, "ruleSemanticId": "RSC-DAILY-N", "dimensions": [
        explicit["dimensions"][0],
        {"dimensionId": "max_count", "label": "每日挑战次数上限", "kind": "parameter",
         "status": "unresolved", "reviewRoute": "P6", "valueType": "integer"},
    ]}
    decision = build_review_promotions(build_rule_semantic_contracts([daily_rule], [unknown])["contracts"])[0]
    assert decision["question"] == "每日挑战次数上限是多少？"
    assert decision["reviewStage"] == "P6"


def test_suppressed_default_closures_never_promote_or_render():
    spec = _refresh_spec()
    spec["dimensions"].append({"dimensionId": "resume_combat", "label": "恢复战斗时点",
                               "kind": "rule", "status": "suppressed",
                               "suppressionReason": "natural_default_closure"})
    contract = build_rule_semantic_contracts([_rule()], [spec])["contracts"][0]
    assert all(item["dimensionId"] != "resume_combat" for item in build_review_promotions([contract]))
    preview = render_semantically_completed_preview([contract])
    assert "恢复战斗" not in preview


def test_human_preview_shows_complete_rule_frame_without_audit_vocabulary():
    contract = build_rule_semantic_contracts([_rule()], [_refresh_spec()])["contracts"][0]
    preview = render_semantically_completed_preview([contract])
    assert "可观看广告刷新当前3项候选。" in preview
    assert "广告刷新存在次数限制。" in preview
    assert "刷新次数上限：待确认。" in preview
    assert "次数重置周期：待确认。" in preview
    assert "1/1" not in preview
    for token in ("semantic", "evidence", "candidate", "P4", "P6", "RSC-", "R-REFRESH"):
        assert token not in preview


def test_phase623_reference_artifacts_match_completion_and_review_counts():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts" / "planning-content-phase6.2.3-semantic-completion-2026-08-18"
    if not (artifact / "semantic-completion-richness.json").exists():
        return
    metrics = json.loads((artifact / "semantic-completion-richness.json").read_text(encoding="utf-8"))
    assert metrics["confirmedMechanicCount"] == 14
    assert metrics["completedSemanticDimensionCount"] == 26
    assert metrics["actionableUnresolvedDimensionCount"] == 9
    assert metrics["p4PromotionCount"] == 6
    assert metrics["p6PromotionCount"] == 3
    assert metrics["observedParameterCount"] == 3


def test_phase623_human_preview_has_complete_refresh_frame_and_no_pseudo_pending():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts" / "planning-content-phase6.2.3-semantic-completion-2026-08-18"
    if not (artifact / "human-planning-preview.md").exists():
        return
    preview = (artifact / "human-planning-preview.md").read_text(encoding="utf-8")
    for text in ("可观看广告刷新当前3项候选。", "广告刷新存在次数限制。",
                 "刷新次数上限：待确认。", "次数重置周期：待确认。",
                 "战斗中提供6个武器栏位。", "每日挑战次数上限为3次。"):
        assert text in preview
    for text in ("武器栏容量：待确认", "关卡时限：待确认", "接触伤害方式：待确认",
                 "恢复战斗时点：待确认", "1/1"):
        assert text not in preview
    for token in ("semantic", "evidence", "candidate", "P4", "P6", "RSC-", "SYN-"):
        assert token not in preview


def test_phase623_quality_gate_and_gve16_model_validation_are_clean():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts" / "planning-content-phase6.2.3-semantic-completion-2026-08-18"
    if not (artifact / "phase623-quality-gate.json").exists():
        return
    gate = json.loads((artifact / "phase623-quality-gate.json").read_text(encoding="utf-8"))
    assert gate["pass"] is True
    model = json.loads((artifact / "gve16-planning-model.json").read_text(encoding="utf-8"))
    assert model["standard"] == "GVE16"
    assert model["mode"] == "gameplay"
    assert model["extensions"]["approvedWriteBack"] is False
