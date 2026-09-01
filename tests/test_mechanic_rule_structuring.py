import json
from pathlib import Path

from backend.mechanic_rule_structuring import (
    build_mechanic_rule_hierarchy,
    render_mechanic_rule_preview,
)


def test_requirement_discovery_is_attached_as_non_publication_registry():
    from backend.mechanic_rule_structuring import build_mechanic_requirement_registry

    registry = build_mechanic_requirement_registry([{
        "mechanicId": "MECH-MONSTER",
        "mechanicType": "monster_movement_attack",
        "ownerPath": {"system": "战斗", "subsystem": "怪物", "mechanic": "怪物行为"},
        "existenceSignals": [],
    }], [])
    assert registry["publicationEligible"] is False
    assert registry["requirements"]
    assert all(item["status"] != "dormant_optional" or item["dimensionRole"] != "core"
               for item in registry["requirements"])


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.2.5-mechanic-rule-structuring-2026-08-18"


def _contract(rule_id="RULE-A", dimensions=None):
    return {
        "ruleSemanticId": "RSC-TEST", "mechanic": "测试机制",
        "ownerChapter": "测试系统", "ruleGroup": "使用规则",
        "confirmedCoreRule": [{"ruleId": rule_id, "statement": "规则A。"}],
        "requiredRuleDimensions": dimensions or [{
            "dimensionId": "rule_a", "status": "observed", "kind": "rule",
            "semanticType": "persistent_game_rule", "displayText": "规则A。", "subrules": [],
        }],
    }


def test_hierarchy_preserves_rule_and_dimension_provenance():
    result = build_mechanic_rule_hierarchy([_contract()], [])
    group = result["chapters"][0]["ruleGroups"][0]
    item = group["items"][0]
    assert group["title"] == "使用规则"
    assert item["text"] == "规则A。"
    assert item["supportingRuleIds"] == ["RULE-A"]
    assert item["sourceDimensionIds"] == ["rule_a"]
    assert result["qualityGate"]["unsupportedHierarchyNodeCount"] == 0


def test_single_rule_does_not_create_mechanical_subheading():
    result = build_mechanic_rule_hierarchy([_contract()], [])
    group = result["chapters"][0]["ruleGroups"][0]
    assert group["subgroups"] == []
    preview = render_mechanic_rule_preview(result)
    assert "####" not in preview


def test_affix_rules_form_supported_numeric_shape_and_tradeoff_structure():
    contract = {
        **_contract("RULE-AFFIX"), "mechanic": "武器词条", "ownerChapter": "词条",
        "ruleGroup": "词条效果", "ruleSemanticId": "RSC-AFFIX",
        "requiredRuleDimensions": [{
            "dimensionId": "modifier_dimensions", "status": "observed", "kind": "rule",
            "semanticType": "persistent_game_rule",
            "displayText": "词条可修改武器的攻击范围、伤害、冷却、攻击次数和攻击方向。",
            "subrules": ["火焰扩张：火焰喷射范围+30%。", "广域喷射：改为四向喷射，伤害-20%。"],
        }, {
            "dimensionId": "tradeoff", "status": "observed", "kind": "rule",
            "semanticType": "persistent_game_rule",
            "displayText": "部分词条在强化攻击效果的同时降低伤害。", "subrules": [],
        }],
    }
    result = build_mechanic_rule_hierarchy([contract], [])
    group = result["chapters"][0]["ruleGroups"][0]
    assert [item["title"] for item in group["subgroups"]] == ["数值强化", "攻击形态", "复合效果"]
    assert group["synthesisLevel"] == "mechanic_rule"
    assert all(item["supportingRuleIds"] == ["RULE-AFFIX"] for item in group["subgroups"])


def test_preview_hides_internal_synthesis_vocabulary():
    hierarchy = build_mechanic_rule_hierarchy([_contract()], [])
    preview = render_mechanic_rule_preview(hierarchy)
    for forbidden in ("atomic_rule", "composite_rule", "mechanic_rule", "semantic contract", "evidence", "relation type"):
        assert forbidden not in preview


def test_default_damage_semantics_are_suppressed_from_preview_but_kept_in_audit():
    contract = _contract("RULE-HP", [{
        "dimensionId": "damage_reduces_health", "status": "observed", "kind": "rule",
        "semanticType": "persistent_game_rule", "displayText": "载具受伤后扣除当前生命值。", "subrules": [],
    }])
    hierarchy = build_mechanic_rule_hierarchy([contract], [])
    item = hierarchy["chapters"][0]["ruleGroups"][0]["items"][0]
    assert item["publishWorthiness"] == "suppress_common_sense"
    assert item["worthinessReason"] == "default_damage_semantics_without_special_rule"
    assert "载具受伤后扣除当前生命值。" not in render_mechanic_rule_preview(hierarchy)
    assert hierarchy["worthinessAudit"]["suppressedCommonSenseRules"][0]["supportingRuleIds"] == ["RULE-HP"]


def test_basic_rule_that_defines_failure_condition_is_retained():
    contract = _contract("RULE-FAIL", [{
        "dimensionId": "failure_condition", "status": "observed", "kind": "rule",
        "semanticType": "persistent_game_rule", "displayText": "载具生命值归零时关卡失败。", "subrules": [],
    }])
    hierarchy = build_mechanic_rule_hierarchy([contract], [])
    item = hierarchy["chapters"][0]["ruleGroups"][0]["items"][0]
    assert item["publishWorthiness"] == "retain_meaningful"
    assert item["worthinessReason"] == "defines_gameplay_outcome_or_transition"
    assert "载具生命值归零时关卡失败。" in render_mechanic_rule_preview(hierarchy)


def test_dimension_relation_metadata_survives_mechanic_structuring():
    contract = _contract("RULE-CHAIN", [{
        "dimensionId": "entry", "status": "observed", "kind": "rule",
        "semanticType": "persistent_game_rule", "displayText": "进入战区后开始移动。",
        "relationType": "sequence", "precedes": ["contact"], "subrules": [],
    }, {
        "dimensionId": "contact", "status": "observed", "kind": "rule",
        "semanticType": "persistent_game_rule", "displayText": "接触载具后造成伤害。",
        "relationType": "state_transition", "dependsOn": ["entry"], "subrules": [],
    }])
    hierarchy = build_mechanic_rule_hierarchy([contract], [])
    items = hierarchy["chapters"][0]["ruleGroups"][0]["items"]
    assert items[0]["relations"] == [{"type": "sequence", "targetDimensionId": "contact"}]
    assert items[1]["relations"] == [{"type": "dependency", "sourceDimensionId": "entry"}]
    assert hierarchy["metrics"]["groundedRuleRelationCount"] == 2


def test_contact_damage_and_counted_choice_remain_meaningful_rules():
    contracts = [
        _contract("RULE-CONTACT", [{
            "dimensionId": "contact_damage", "status": "observed", "kind": "rule",
            "semanticType": "persistent_game_rule", "displayText": "怪物接触载具后造成伤害。", "subrules": [],
        }]),
        {**_contract("RULE-CHOICE", [{
            "dimensionId": "selection_result", "status": "observed", "kind": "rule",
            "semanticType": "persistent_game_rule", "displayText": "玩家从3项中选择1项并获得对应强化。", "subrules": [],
        }]), "ruleSemanticId": "RSC-CHOICE", "ownerChapter": "三选一", "ruleGroup": "选择"},
    ]
    hierarchy = build_mechanic_rule_hierarchy(contracts, [])
    retained = hierarchy["worthinessAudit"]["retainedBasicButMeaningfulRules"]
    retained_text = {item["text"] for item in retained}
    assert "怪物接触载具后造成伤害。" in retained_text
    assert "玩家从3项中选择1项并获得对应强化。" in retained_text


def test_phase625_artifact_has_no_unsupported_content_and_preview_is_structured():
    quality = json.loads((ARTIFACT_DIR / "phase625-quality-gate.json").read_text(encoding="utf-8"))
    preview = (ARTIFACT_DIR / "human-planning-preview.md").read_text(encoding="utf-8")
    assert quality["unsupportedHierarchyNodeCount"] == 0
    assert quality["internalVocabularyLeakCount"] == 0
    assert quality["untraceablePreviewRuleCount"] == 0
    assert quality["suppressedCommonSenseRuleInPreview"] == 0
    assert quality["pass"] is True
    assert "载具受伤后扣除当前生命值。" not in preview
    audit = json.loads((ARTIFACT_DIR / "core-rule-worthiness-audit.json").read_text(encoding="utf-8"))
    assert audit["suppressedCommonSenseRules"][0]["text"] == "载具受伤后扣除当前生命值。"
    assert "### 词条效果" in preview
    assert "#### 数值强化" in preview
    assert "### 伤害统计" in preview
    assert "### 挑战次数" in preview
