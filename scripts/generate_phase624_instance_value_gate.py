from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.instance_value_semantic_gate import (
    apply_gate_to_semantic_contracts,
    apply_instance_value_semantic_gate,
)
from backend.planning_model import validate_planning_model
from backend.rule_semantic_completion import render_semantically_completed_preview


P621 = ROOT / "artifacts" / "planning-content-phase6.2.1-evidence-saturation-2026-08-17"
P622 = ROOT / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
P623 = ROOT / "artifacts" / "planning-content-phase6.2.3-semantic-completion-2026-08-18"
OUT = ROOT / "artifacts" / "planning-content-phase6.2.4-instance-value-gate-2026-08-18"


UI_STATE_DIMENSIONS = {
    "vehicle_hp_display", "weapon_slot_visible_count", "weapon_draw_animation", "weapon_draw_skip",
    "weapon_damage_numbers", "three_choice_card_fields", "refresh_ad_path", "boss_counter_semantics",
    "level_display", "level_progress_bar", "settlement_double_reward", "settlement_return",
    "settlement_daily_count",
}
CURRENT_INSTANCE_DIMENSIONS = {
    "vehicle_damage_change", "weapon_draw_result", "ultimate_applied_in_combat",
    "boss_health_decrease", "victory_result", "settlement_reward_items",
    "settlement_weapon_damage", "settlement_total_damage",
}
EXAMPLE_VALUE_DIMENSIONS = {"hud_elapsed_time", "settlement_clear_time_record"}
GAMEPLAY_PARAMETER_DIMENSIONS = {
    "weapon_draw_cost", "weapon_attack_interval", "weapon_damage_formula",
    "three_choice_candidate_count", "three_choice_selection_count", "refresh_consumes_count",
    "ultimate_four_way_penalty", "affix_multi_explosion", "affix_poison_damage",
    "affix_thunder_cooldown",
}
PARAMETER_RULE_IDS = {"SYN-WEAPON-SLOTS", "SYN-SETTLEMENT-DAILY"}
FILTERED_RULE_TYPES = {
    "SYN-WEAPON-DRAW-SKIP": "ui_state",
    "SYN-DAMAGE-NUMBER": "ui_state",
    "SYN-CARD-FIELDS": "ui_state",
    "SYN-BOSS-BANNER": "ui_state",
    "SYN-BOSS-HP": "current_instance_state",
    "SYN-SETTLEMENT-RETURN": "ui_state",
}


def semantic_type_for_dimension(dimension: str) -> str:
    if dimension in UI_STATE_DIMENSIONS:
        return "ui_state"
    if dimension in CURRENT_INSTANCE_DIMENSIONS:
        return "current_instance_state"
    if dimension in EXAMPLE_VALUE_DIMENSIONS:
        return "example_value"
    if dimension in GAMEPLAY_PARAMETER_DIMENSIONS:
        return "gameplay_parameter"
    return "persistent_game_rule"


def fixed_basis(dimension: str) -> str | None:
    if dimension in {"ultimate_four_way_penalty", "affix_multi_explosion", "affix_poison_damage", "affix_thunder_cooldown"}:
        return "词条卡文案明确给出固定效果数值"
    if dimension in {"three_choice_candidate_count", "three_choice_selection_count"}:
        return "多张三选一画面稳定显示3项选1项"
    return None


def annotate_observations(matrix: list[dict]) -> list[dict]:
    result = []
    for item in matrix:
        dimension = item["observationDimension"]
        annotated = copy.deepcopy(item)
        annotated["recordId"] = f"OBS:{dimension}"
        annotated["sourceLayer"] = "observation"
        annotated["semanticType"] = semantic_type_for_dimension(dimension)
        annotated["fixedRuleBasis"] = fixed_basis(dimension)
        annotated["deliveryEligible"] = False
        result.append(annotated)
    return result


def annotate_facts(facts: list[dict]) -> list[dict]:
    result = []
    for item in facts:
        dimension = item["observationDimension"]
        annotated = copy.deepcopy(item)
        annotated["recordId"] = f"FACT:{dimension}"
        annotated["sourceLayer"] = "fact"
        annotated["semanticType"] = semantic_type_for_dimension(dimension)
        annotated["fixedRuleBasis"] = fixed_basis(dimension)
        annotated["deliveryEligible"] = False
        result.append(annotated)
    return result


def annotate_rules(synthesis: dict) -> list[dict]:
    result = []
    for rule in synthesis["gameRules"] + synthesis["filteredOut"]:
        annotated = copy.deepcopy(rule)
        rule_id = rule["ruleId"]
        semantic_type = FILTERED_RULE_TYPES.get(rule_id, "gameplay_parameter" if rule_id in PARAMETER_RULE_IDS else "persistent_game_rule")
        annotated["recordId"] = rule_id
        annotated["sourceLayer"] = "synthesized_rule"
        annotated["semanticType"] = semantic_type
        if rule_id == "SYN-WEAPON-SLOTS":
            annotated["fixedRuleBasis"] = "多个战斗与选择画面固定显示编号1至6的栏位"
        elif rule_id == "SYN-SETTLEMENT-DAILY":
            annotated["fixedRuleBasis"] = "UI明确标注今日剩余次数3/3"
        annotated["deliveryEligible"] = semantic_type in {"persistent_game_rule", "gameplay_parameter"}
        result.append(annotated)
    return result


def annotate_contracts(contracts: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    result = copy.deepcopy(contracts)
    subrule_annotations: dict[str, dict] = {}
    for contract in result:
        for dimension in contract["requiredRuleDimensions"]:
            dimension["semanticType"] = "gameplay_parameter" if dimension.get("kind") == "parameter" else "persistent_game_rule"
            if dimension.get("status") == "observed" and "value" in dimension and dimension["semanticType"] == "gameplay_parameter":
                if contract["ruleSemanticId"] == "RSC-WEAPON-SLOT":
                    dimension["fixedRuleBasis"] = "多个画面固定显示6个编号栏位"
                elif dimension["dimensionId"] == "double_reward":
                    dimension["fixedRuleBasis"] = "UI规则文案明确为双倍奖励"
                elif dimension["dimensionId"] == "daily_max_count":
                    dimension["fixedRuleBasis"] = "UI明确标注今日剩余次数3/3"
            for index, text in enumerate(dimension.get("subrules", [])):
                key = f"{contract['ruleSemanticId']}:{dimension['dimensionId']}:subrule:{index}"
                if contract["ruleSemanticId"] == "RSC-SETTLEMENT" and dimension["dimensionId"] == "damage_statistics":
                    semantic_type = "current_instance_state" if index == 0 else "example_value"
                    subrule_annotations[key] = {"semanticType": semantic_type}
                elif contract["ruleSemanticId"] == "RSC-AFFIX":
                    subrule_annotations[key] = {"semanticType": "gameplay_parameter",
                                                "fixedRuleBasis": "词条卡文案明确给出固定效果数值"}
                else:
                    subrule_annotations[key] = {"semanticType": "persistent_game_rule"}
    return result, subrule_annotations


def layer_gate_records(records: list[dict], text_field: str) -> dict:
    normalized = []
    for item in records:
        normalized.append({"recordId": item["recordId"], "text": item.get(text_field, ""),
                           "semanticType": item["semanticType"], "sourceLayer": item["sourceLayer"],
                           "fixedRuleBasis": item.get("fixedRuleBasis")})
    return apply_instance_value_semantic_gate(normalized)


def write_json(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def render_value_audit(specific_values: list[dict], contract_gate: dict) -> str:
    lines = ["# Instance Value → Rule Semantic Audit", "",
             "| Value | Semantic type | Core body | Derived rule / handling |", "|---|---|---:|---|"]
    for item in specific_values:
        lines.append(f"| {item['value']} | {item['semanticType']} | {'yes' if item['coreEligible'] else 'no'} | {item['handling']} |")
    lines += ["", "## Contract subvalues removed", ""]
    for item in contract_gate["excludedValues"]:
        lines.append(f"- {item['text']} → {item['semanticType']} → excluded from core body")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    matrix = json.loads((P621 / "evidence-coverage-matrix.json").read_text(encoding="utf-8"))["matrix"]
    facts = json.loads((P622 / "observation-fact-rule-synthesis.json").read_text(encoding="utf-8"))
    synthesis = json.loads((P622 / "game-rule-synthesis.json").read_text(encoding="utf-8"))
    contract_report = json.loads((P623 / "rule-semantic-contracts.json").read_text(encoding="utf-8"))

    observations = annotate_observations(matrix)
    annotated_facts = annotate_facts(facts)
    rules = annotate_rules(synthesis)
    observation_gate = layer_gate_records(observations, "observedText")
    fact_gate = layer_gate_records(annotated_facts, "synthesizedFact")
    rule_gate = layer_gate_records(rules, "statement")

    typed_contracts, annotations = annotate_contracts(contract_report["contracts"])
    contract_gate = apply_gate_to_semantic_contracts(typed_contracts, annotations)
    preview = render_semantically_completed_preview(contract_gate["contracts"])

    specific_values = [
        {"value": "05:14", "semanticType": "example_value", "coreEligible": False,
         "handling": "保留为本局通关时间证据；正文只写关卡记录经过时间并在结算展示"},
        {"value": "1/1", "semanticType": "ui_state", "coreEligible": False,
         "handling": "仅证明当前UI状态；次数上限和重置周期继续待确认"},
        {"value": "3/3", "semanticType": "ui_state", "coreEligible": False,
         "handling": "原值不渲染；UI明确的今日生命周期与总次数支持每日上限3次参数规则"},
        {"value": "88.9万", "semanticType": "current_instance_state", "coreEligible": False,
         "handling": "正文只保留结算统计本局总伤害"},
        {"value": "84.5% / 10.4% / 2.9% / 2.2%", "semanticType": "example_value", "coreEligible": False,
         "handling": "正文只保留按武器统计伤害占比"},
        {"value": "火焰范围+30%等词条数值", "semanticType": "gameplay_parameter", "coreEligible": True,
         "handling": "词条卡明确描述固定效果，作为规则常量保留"},
    ]
    all_annotated = observations + annotated_facts + rules
    missing_semantic_types = sum(item.get("semanticType") not in {
        "persistent_game_rule", "gameplay_parameter", "current_instance_state", "example_value", "ui_state"
    } for item in all_annotated)
    forbidden_values = ["05:14", "1/1", "3/3", "88.9万", "84.5%", "10.4%", "2.9%", "2.2%", "90.65%"]
    gate_reports = (observation_gate, fact_gate, rule_gate)
    ungrounded_parameters_in_core = sum(
        item.get("semanticType") == "gameplay_parameter" and not item.get("fixedRuleBasis")
        for report in gate_reports for item in report["coreEligible"]
    )
    quality = {
        "untypedObservationFactRule": missing_semantic_types,
        "instanceOrUiValueInCorePreview": sum(value in preview for value in forbidden_values),
        # Rejected values prove the gate worked; only an ungrounded value that
        # survived into core output is a quality failure.
        "ungroundedGameplayParameterInCore": ungrounded_parameters_in_core,
        "excludedInstanceSubvalueRetained": sum(item["text"] in preview for item in contract_gate["excludedValues"]),
        "fixedAffixValueLost": sum(value not in preview for value in ("火焰喷射范围+30%", "雷暴枪伤害+100%", "雷暴枪冷却时间-20%")),
        "approvedRuleWrites": 0,
        "approvedGapWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    type_distribution = {}
    for item in all_annotated:
        type_distribution[item["semanticType"]] = type_distribution.get(item["semanticType"], 0) + 1
    summary = {
        "observationCount": len(observations), "factCount": len(annotated_facts),
        "synthesizedRuleCount": len(rules), "semanticTypeDistribution": type_distribution,
        "coreContractCount": len(contract_gate["contracts"]),
        "retainedFixedSubvalueCount": contract_gate["metrics"]["retainedValueCount"],
        "excludedInstanceSubvalueCount": contract_gate["metrics"]["excludedValueCount"],
        "specificValueAuditCount": len(specific_values),
    }

    write_json("semantic-typed-observations.json", observations)
    write_json("semantic-typed-facts.json", annotated_facts)
    write_json("semantic-typed-synthesized-rules.json", rules)
    write_json("layer-gate-results.json", {"observations": observation_gate, "facts": fact_gate, "rules": rule_gate})
    write_json("gated-rule-semantic-contracts.json", contract_gate)
    write_json("specific-value-audit.json", specific_values)
    write_json("phase624-summary.json", summary)
    write_json("phase624-quality-gate.json", quality)
    (OUT / "specific-value-audit.md").write_text(render_value_audit(specific_values, contract_gate), encoding="utf-8")
    (OUT / "human-planning-preview.md").write_text(preview, encoding="utf-8")

    planning_model = json.loads((P623 / "gve16-planning-model.json").read_text(encoding="utf-8"))
    planning_model.setdefault("extensions", {}).update({
        "phase": "6.2.4",
        "instanceValueSemanticGateArtifact": "gated-rule-semantic-contracts.json",
        "semanticTypedRulesArtifact": "semantic-typed-synthesized-rules.json",
        "approvedWriteBack": False,
    })
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError(f"invalid GVE16 planning model: {errors}")
    write_json("gve16-planning-model.json", planning_model)
    write_json("provenance.json", {"phase621Source": str(P621.resolve()), "phase622Source": str(P622.resolve()),
               "phase623Source": str(P623.resolve()), "approvedRuleWrites": 0, "approvedGapWrites": 0,
               "historicalArtifactsMutated": False, "humanPreviewSource": "gated RuleSemanticContract"})


if __name__ == "__main__":
    main()
