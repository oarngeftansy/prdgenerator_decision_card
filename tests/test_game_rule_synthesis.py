import json
from pathlib import Path

from backend.game_rule_synthesis import (
    attach_approved_requirement_rules,
    normalize_ui_evidence,
    synthesize_game_rules,
    render_human_planning_preview,
)


def test_approved_requirement_rule_enters_synthesis_with_explicit_owner_and_lineage():
    report = {"gameRules": [], "filteredOut": [], "rejectedPlans": [], "metrics": {}}
    approved = [{
        "ruleId": "RULE-APPROVED", "mechanicId": "MECH-STATS", "valid": True,
        "ruleStatus": "approved_review", "text": "伤害统计以武器为统计单位。",
        "dimensionIds": ["statistics.attribution"],
        "satisfiesRequirementIds": ["REQ-STATS"],
    }]
    result = attach_approved_requirement_rules(
        report, approved,
        owner_by_mechanic={"MECH-STATS": {"ownerChapter": "战斗数据", "ruleGroup": "伤害统计"}},
    )
    rule = result["gameRules"][0]
    assert rule["ruleId"] == "SYN-REQ-APPROVED"
    assert rule["sourceRuleIds"] == ["RULE-APPROVED"]
    assert rule["sourceRequirementIds"] == ["REQ-STATS"]
    assert (rule["ownerChapter"], rule["ruleGroup"]) == ("战斗数据", "伤害统计")
    assert rule["statement"] == approved[0]["text"]


def test_requirement_publication_rejects_unapproved_invalid_or_ownerless_rules():
    rules = [
        {"ruleId": "RULE-CAND", "mechanicId": "M", "valid": True,
         "ruleStatus": "candidate_only", "text": "候选。"},
        {"ruleId": "RULE-INVALID", "mechanicId": "M", "valid": False,
         "ruleStatus": "approved_review", "text": "无效。"},
        {"ruleId": "RULE-OWNERLESS", "mechanicId": "OTHER", "valid": True,
         "ruleStatus": "approved_review", "text": "无归属。"},
    ]
    result = attach_approved_requirement_rules(
        {"gameRules": [], "filteredOut": [], "rejectedPlans": [], "metrics": {}},
        rules, owner_by_mechanic={"M": {"ownerChapter": "系统", "ruleGroup": "机制"}},
    )
    assert result["gameRules"] == []


def test_explicit_superseded_synthesis_identity_is_replaced_without_text_matching():
    report = {"gameRules": [{"ruleId": "SYN-OLD", "statement": "旧表达。"}], "metrics": {}}
    approved = [{"ruleId": "RULE-NEW", "mechanicId": "M", "valid": True,
                 "ruleStatus": "approved_review", "text": "新表达。",
                 "supersedesSynthesisRuleIds": ["SYN-OLD"]}]
    result = attach_approved_requirement_rules(
        report, approved, owner_by_mechanic={"M": {"ownerChapter": "系统", "ruleGroup": "机制"}})
    assert [rule["ruleId"] for rule in result["gameRules"]] == ["SYN-REQ-NEW"]


def _observation(key, text="observed", *, status="directly_observed"):
    return {"observationDimension": key, "observationStatus": status,
            "observedText": text, "mechanic": "test",
            "evidenceRefs": [{"evidenceId": "F0001", "sourcePath": "C:/evidence/F0001.jpg"}]}


def test_ui_remaining_count_does_not_invent_daily_lifecycle():
    result = normalize_ui_evidence({
        **_observation("refresh_ad_path", "当前剩余观看次数1/1"),
        "uiSemantic": {"displayType": "remaining", "label": "当前剩余观看次数", "value": "1/1"},
    })
    assert result["underlyingMechanic"] == "ad_refresh_limit"
    assert result["persistentRule"] == "广告刷新存在次数限制"
    assert "reset_period" in result["unresolvedSemantic"]
    assert result["lifecycle"] is None


def test_explicit_daily_label_can_ground_daily_cap():
    result = normalize_ui_evidence({
        **_observation("settlement_daily_count", "今日剩余次数3/3"),
        "uiSemantic": {"displayType": "remaining", "label": "今日剩余次数", "value": "3/3"},
    })
    assert result["underlyingMechanic"] == "daily_challenge_limit"
    assert result["persistentRule"] == "每日挑战次数上限为3次"
    assert result["lifecycle"] == "daily"


def test_synthesis_combines_multiple_observations_without_losing_concrete_effects():
    observations = [_observation("range"), _observation("damage"), _observation("cooldown")]
    plans = [{
        "ruleId": "GR-1", "ownerChapter": "词条", "ruleGroup": "词条效果",
        "statement": "词条可修改攻击范围、伤害和冷却。",
        "sourceDimensions": ["range", "damage", "cooldown"], "classification": "game_rule",
        "concreteSubrules": ["范围+30%。", "伤害+100%。", "冷却-20%。"],
    }]
    report = synthesize_game_rules(observations, plans)
    rule = report["gameRules"][0]
    assert rule["statement"] == "词条可修改攻击范围、伤害和冷却。"
    assert rule["concreteSubrules"] == ["范围+30%。", "伤害+100%。", "冷却-20%。"]
    assert len(rule["evidenceRefs"]) == 1  # stable evidence de-duplication


def test_synthesis_preserves_explicit_input_lineage_without_resolving_it_by_text():
    observations = [_observation("trigger", "升级触发候选。")]
    plans = [{
        "ruleId": "SYN-1", "ownerChapter": "成长", "ruleGroup": "候选",
        "statement": "升级触发候选。", "sourceDimensions": ["trigger"],
        "classification": "game_rule", "sourceLineIds": ["LINE-1", "LINE-2"],
    }]
    rule = synthesize_game_rules(observations, plans)["gameRules"][0]
    assert rule["sourceLineIds"] == ["LINE-1", "LINE-2"]


def test_interaction_and_presentation_are_filtered_from_core_rules():
    observations = [_observation("skip"), _observation("boss_banner")]
    plans = [
        {"ruleId": "I", "ownerChapter": "武器", "ruleGroup": "抽取", "statement": "点击空白跳过动画。",
         "sourceDimensions": ["skip"], "classification": "interaction"},
        {"ruleId": "P", "ownerChapter": "怪物", "ruleGroup": "首领", "statement": "显示首领来袭。",
         "sourceDimensions": ["boss_banner"], "classification": "presentation"},
    ]
    report = synthesize_game_rules(observations, plans)
    assert report["gameRules"] == []
    assert {item["classification"] for item in report["filteredOut"]} == {"interaction", "presentation"}


def test_ambiguous_evidence_cannot_ground_a_game_rule():
    observations = [_observation("frequency", status="ambiguous")]
    plans = [{"ruleId": "R", "ownerChapter": "武器", "ruleGroup": "攻击",
              "statement": "攻击间隔为1秒。", "sourceDimensions": ["frequency"],
              "classification": "gameplay_parameter"}]
    report = synthesize_game_rules(observations, plans)
    assert report["gameRules"] == []
    assert report["rejectedPlans"][0]["reason"] == "source_not_observable"


def test_human_preview_contains_no_audit_labels_or_internal_ids():
    report = {"gameRules": [{"ruleId": "GR-INTERNAL", "ownerChapter": "结算",
                              "ruleGroup": "伤害统计", "statement": "按武器统计伤害占比。",
                              "concreteSubrules": [], "classification": "game_rule"}]}
    markdown = render_human_planning_preview(report, [])
    assert "按武器统计伤害占比。" in markdown
    assert "GR-INTERNAL" not in markdown
    assert "候选" not in markdown
    assert "Evidence" not in markdown


def test_phase622_preview_resolves_observable_pending_and_filters_ui_interaction():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
    if not (artifact / "human-planning-preview.md").exists():
        return
    markdown = (artifact / "human-planning-preview.md").read_text(encoding="utf-8")
    assert "战斗中提供6个武器栏位。" in markdown
    assert "武器栏容量：待确认" not in markdown
    assert "刷新规则：待确认" not in markdown
    assert "关卡时限：待确认" not in markdown
    assert "点击空白处可跳过" not in markdown
    assert "结算页提供返回" not in markdown
    assert "挑战成功条件：待确认" not in markdown
    assert "【" not in markdown


def test_phase622_all_core_rules_have_observable_evidence_and_no_delivery_pollution():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
    if not (artifact / "game-rule-synthesis.json").exists():
        return
    report = json.loads((artifact / "game-rule-synthesis.json").read_text(encoding="utf-8"))
    assert all(rule["classification"] in {"game_rule", "gameplay_parameter"} for rule in report["gameRules"])
    assert all(rule["evidenceRefs"] for rule in report["gameRules"])
    assert all(rule["evidenceStatus"] in {"directly_observed", "strongly_supported"} for rule in report["gameRules"])
    gate = json.loads((artifact / "phase622-quality-gate.json").read_text(encoding="utf-8"))
    assert gate["pass"] is True


def test_phase622_ui_normalization_keeps_refresh_lifecycle_unresolved_but_daily_explicit():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
    if not (artifact / "ui-evidence-semantic-normalization.json").exists():
        return
    items = json.loads((artifact / "ui-evidence-semantic-normalization.json").read_text(encoding="utf-8"))
    by_key = {item["observationDimension"]: item for item in items}
    assert by_key["refresh_ad_path"]["lifecycle"] is None
    assert "reset_period" in by_key["refresh_ad_path"]["unresolvedSemantic"]
    assert by_key["settlement_daily_count"]["persistentRule"] == "每日挑战次数上限为3次"


def test_phase622_observation_fact_rule_layers_are_not_a_label_only_copy():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
    if not (artifact / "observation-fact-rule-synthesis.json").exists():
        return
    items = json.loads((artifact / "observation-fact-rule-synthesis.json").read_text(encoding="utf-8"))
    by_key = {item["observationDimension"]: item for item in items}
    refresh = by_key["refresh_ad_path"]
    assert refresh["synthesizedFact"] != refresh["observation"]
    assert refresh["synthesizedRuleIds"]
