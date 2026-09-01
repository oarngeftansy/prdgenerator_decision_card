import json
from pathlib import Path

from backend.gve16_hierarchy_flattening import (
    flatten_mechanic_rule_hierarchy,
    render_flattened_mechanic_preview,
)


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.2.6-hierarchy-flattening-2026-08-18"


def _item(text, dimension):
    return {
        "text": text, "supportingRuleIds": [f"RULE-{dimension}"],
        "sourceDimensionIds": [dimension], "publishWorthiness": "retain_meaningful",
        "subrules": [], "itemType": "coreRule", "synthesisLevel": "atomic_rule",
    }


def test_single_rule_subgroups_flatten_into_parent_section_without_losing_rules():
    hierarchy = {"chapters": [{"title": "武器", "ruleGroups": [{
        "groupId": "ATTACK", "title": "攻击", "items": [], "supportingRuleIds": ["RULE-A", "RULE-B"],
        "sourceDimensionIds": ["a", "b"], "subgroups": [
            {"title": "自动攻击", "items": [_item("自动攻击规则。", "a")]},
            {"title": "伤害结算", "items": [_item("伤害计算：待确认。", "b")]},
        ],
    }]}]}
    flattened = flatten_mechanic_rule_hierarchy(hierarchy)
    section = flattened["chapters"][0]["sections"][0]
    assert section["title"] == "攻击"
    assert [item["text"] for item in section["items"]] == ["自动攻击规则。", "伤害计算：待确认。"]
    preview = render_flattened_mechanic_preview(flattened)
    assert "####" not in preview
    assert "#### 自动攻击" not in preview


def test_independent_settlement_submechanisms_may_remain_sections():
    hierarchy = {"chapters": [{"title": "结算", "ruleGroups": [{
        "groupId": "SETTLEMENT", "title": "结算结果", "items": [], "supportingRuleIds": ["RULE-T", "RULE-D"],
        "sourceDimensionIds": ["time", "damage"], "subgroups": [
            {"title": "战斗结果", "items": [_item("结算记录通关时间。", "time")]},
            {"title": "伤害统计", "items": [_item("结算统计伤害。", "damage")]},
        ],
    }]}]}
    flattened = flatten_mechanic_rule_hierarchy(hierarchy)
    assert [item["title"] for item in flattened["chapters"][0]["sections"]] == ["战斗结果", "伤害统计"]
    assert all(item["headingRetentionReason"] == "independent_submechanic" for item in flattened["chapters"][0]["sections"])


def test_success_semantic_model_language_is_stitched_into_planning_language():
    hierarchy = {"chapters": [{"title": "关卡", "ruleGroups": [{
        "groupId": "SUCCESS", "title": "胜负结果", "items": [
            _item("关卡存在挑战成功结果。", "success_result"),
            {**_item("挑战成功条件：待确认。", "success_condition"), "itemType": "pending"},
        ], "supportingRuleIds": ["RULE-success_result", "RULE-success_condition"],
        "sourceDimensionIds": ["success_result", "success_condition"], "subgroups": [],
    }]}]}
    flattened = flatten_mechanic_rule_hierarchy(hierarchy)
    item = flattened["chapters"][0]["sections"][0]["items"][0]
    assert item["text"] == "关卡可正常通关，通关条件：待确认。"
    assert set(item["sourceDimensionIds"]) == {"success_result", "success_condition"}


def test_phase626_artifact_reduces_hierarchy_without_rule_loss():
    metrics = json.loads((ARTIFACT_DIR / "hierarchy-comparison.json").read_text(encoding="utf-8"))
    quality = json.loads((ARTIFACT_DIR / "phase626-quality-gate.json").read_text(encoding="utf-8"))
    preview = (ARTIFACT_DIR / "human-planning-preview.md").read_text(encoding="utf-8")
    assert metrics["after"]["headingCount"] < metrics["before"]["headingCount"]
    assert metrics["before"]["maxNestingDepth"] == 4
    assert metrics["after"]["maxNestingDepth"] == 3
    assert metrics["after"]["singleRuleHeadingCount"] <= metrics["before"]["singleRuleHeadingCount"]
    assert metrics["after"]["duplicatedConcreteRuleCount"] == 0
    assert quality["lostRuleSemanticCount"] == 0
    assert quality["unjustifiedSingleRuleHeadingCount"] == 0
    assert quality["pass"] is True
    assert "####" not in preview
    assert "关卡存在挑战成功结果" not in preview
    assert "关卡可正常通关，通关条件：待确认。" in preview

