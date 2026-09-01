import json
from pathlib import Path

from backend.instance_value_semantic_gate import (
    apply_instance_value_semantic_gate,
    apply_gate_to_semantic_contracts,
)


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.2.4-instance-value-gate-2026-08-18"


def test_current_run_damage_value_is_kept_for_audit_but_not_core_body():
    report = apply_instance_value_semantic_gate([{
        "recordId": "VALUE-TOTAL-DAMAGE", "text": "本局总伤害88.9万。",
        "semanticType": "current_instance_state", "sourceLayer": "rule_subvalue",
    }])
    assert report["coreEligible"] == []
    assert report["excluded"][0]["text"] == "本局总伤害88.9万。"
    assert report["excluded"][0]["exclusionReason"] == "instance_or_ui_value"


def test_fixed_affix_modifier_is_gameplay_parameter_and_remains_in_core_body():
    report = apply_instance_value_semantic_gate([{
        "recordId": "VALUE-AFFIX", "text": "火焰扩张：攻击范围+30%。",
        "semanticType": "gameplay_parameter", "sourceLayer": "rule_subvalue",
        "fixedRuleBasis": "词条卡明确描述固定效果",
    }])
    assert [item["text"] for item in report["coreEligible"]] == ["火焰扩张：攻击范围+30%。"]


def test_ui_state_3_3_can_support_a_separate_daily_parameter_but_is_not_itself_rendered():
    records = [{
        "recordId": "UI-DAILY", "text": "今日剩余次数3/3",
        "semanticType": "ui_state", "sourceLayer": "observation",
    }, {
        "recordId": "RULE-DAILY-MAX", "text": "每日挑战次数上限为3次。",
        "semanticType": "gameplay_parameter", "sourceLayer": "synthesized_rule",
        "fixedRuleBasis": "UI标签明确给出今日生命周期与剩余/总次数",
        "derivedFromRecordIds": ["UI-DAILY"],
    }]
    report = apply_instance_value_semantic_gate(records)
    assert [item["recordId"] for item in report["coreEligible"]] == ["RULE-DAILY-MAX"]
    assert [item["recordId"] for item in report["excluded"]] == ["UI-DAILY"]


def test_gameplay_parameter_without_fixed_rule_basis_is_rejected():
    report = apply_instance_value_semantic_gate([{
        "recordId": "BAD", "text": "攻击间隔0.2秒。",
        "semanticType": "gameplay_parameter", "sourceLayer": "example_value",
    }])
    assert report["coreEligible"] == []
    assert report["rejected"][0]["reason"] == "parameter_constant_not_grounded"


def test_contract_gate_strips_instance_subrules_but_keeps_persistent_summary():
    contracts = [{
        "ruleSemanticId": "RSC-SETTLEMENT", "mechanic": "结算",
        "requiredRuleDimensions": [{
            "dimensionId": "damage_statistics", "status": "observed", "kind": "rule",
            "displayText": "结算展示本局总伤害，并按武器统计伤害占比。",
            "semanticType": "persistent_game_rule",
            "subrules": ["本局总伤害：88.9万。", "火焰喷射器84.5%；毒液炮10.4%。"],
        }],
    }]
    annotations = {
        "RSC-SETTLEMENT:damage_statistics:subrule:0": "current_instance_state",
        "RSC-SETTLEMENT:damage_statistics:subrule:1": "example_value",
    }
    result = apply_gate_to_semantic_contracts(contracts, annotations)
    dimension = result["contracts"][0]["requiredRuleDimensions"][0]
    assert dimension["displayText"] == "结算展示本局总伤害，并按武器统计伤害占比。"
    assert dimension["subrules"] == []
    assert len(result["excludedValues"]) == 2


def test_contract_gate_keeps_fixed_affix_subrules():
    contracts = [{
        "ruleSemanticId": "RSC-AFFIX", "mechanic": "词条",
        "requiredRuleDimensions": [{
            "dimensionId": "modifier", "status": "observed", "kind": "rule",
            "displayText": "词条可修改武器属性。", "semanticType": "persistent_game_rule",
            "subrules": ["火焰扩张：攻击范围+30%。"],
        }],
    }]
    annotations = {"RSC-AFFIX:modifier:subrule:0": {
        "semanticType": "gameplay_parameter", "fixedRuleBasis": "词条卡明确描述固定效果"}}
    result = apply_gate_to_semantic_contracts(contracts, annotations)
    assert result["contracts"][0]["requiredRuleDimensions"][0]["subrules"] == ["火焰扩张：攻击范围+30%。"]


def test_contract_gate_rejects_parameter_subrule_without_constant_basis():
    contracts = [{
        "ruleSemanticId": "RSC-AFFIX", "mechanic": "词条",
        "requiredRuleDimensions": [{
            "dimensionId": "modifier", "status": "observed", "kind": "rule",
            "displayText": "词条可修改武器属性。", "semanticType": "persistent_game_rule",
            "subrules": ["攻击范围+30%。"],
        }],
    }]
    annotations = {"RSC-AFFIX:modifier:subrule:0": "gameplay_parameter"}
    result = apply_gate_to_semantic_contracts(contracts, annotations)
    assert result["contracts"][0]["requiredRuleDimensions"][0]["subrules"] == []
    assert result["excludedValues"][0]["exclusionReason"] == "parameter_constant_not_grounded"


def test_phase624_artifacts_gate_instance_values_from_human_preview():
    preview = (ARTIFACT_DIR / "human-planning-preview.md").read_text(encoding="utf-8")
    for instance_value in ("05:14", "1/1", "3/3", "88.9万", "84.5%", "10.4%", "2.9%", "2.2%", "90.65%"):
        assert instance_value not in preview
    assert "结算展示本局总伤害，并按武器统计伤害占比。" in preview
    assert "火焰扩张：火焰喷射范围+30%。" in preview
    assert "每日挑战次数上限为3次。" in preview


def test_phase624_artifacts_are_fully_typed_and_quality_gate_passes():
    valid_types = {
        "persistent_game_rule", "gameplay_parameter", "current_instance_state",
        "example_value", "ui_state",
    }
    for filename in (
        "semantic-typed-observations.json",
        "semantic-typed-facts.json",
        "semantic-typed-synthesized-rules.json",
    ):
        records = json.loads((ARTIFACT_DIR / filename).read_text(encoding="utf-8"))
        assert records
        assert all(record["semanticType"] in valid_types for record in records)
    quality = json.loads((ARTIFACT_DIR / "phase624-quality-gate.json").read_text(encoding="utf-8"))
    assert quality["ungroundedGameplayParameterInCore"] == 0
    assert quality["fixedAffixValueLost"] == 0
    assert quality["pass"] is True


def test_phase624_planning_model_keeps_gve16_contract_and_no_writeback():
    model = json.loads((ARTIFACT_DIR / "gve16-planning-model.json").read_text(encoding="utf-8"))
    assert model["standard"] == "GVE16"
    assert model["mode"] == "gameplay"
    assert model["extensions"]["phase"] == "6.2.4"
    assert model["extensions"]["approvedWriteBack"] is False
