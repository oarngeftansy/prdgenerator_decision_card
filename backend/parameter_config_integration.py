from __future__ import annotations

import copy
import hashlib
import re
from typing import Any


PARAMETER_ONLY_MISSING = {
    "loadout_capacity": ("weapon_slot_capacity", "武器栏容量"),
    "damage_resolution": ("damage", "伤害值或公式"),
    "refresh_cost_or_condition": ("refresh_cost", "刷新消耗或可用条件"),
    "time_limit": ("time_limit", "关卡时限"),
}
PLACEMENT = {
    "movement_speed": "nested_bullet", "weapon_slot_capacity": "nested_bullet",
    "attack_range": "nested_bullet", "attack_interval": "nested_bullet", "damage": "nested_bullet",
    "refresh_cost": "nested_bullet", "time_limit": "nested_bullet",
}


def _id(owner: str, layout: str, semantic: str, source: str = "") -> str:
    digest = hashlib.sha1(f"{owner}:{layout}:{semantic}:{source}".encode("utf-8")).hexdigest()[:12].upper()
    return f"PARAM-{digest}"


def _rule_map(rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {rule.get("ruleId") or rule.get("id"): rule for rule in rules}


def _recorded_data_has_persistence_evidence(scope: dict[str, Any], rules: dict[str, dict[str, Any]]) -> bool:
    # Presentation of a result/new-record badge proves display, not cross-run persistence.
    supporting = [*scope.get("ruleBasis", []), *scope.get("evidenceBasis", []),
                  *scope.get("relationshipBasis", [])]
    for source in supporting:
        rule = rules.get(source)
        if not rule or rule.get("ruleType") == "presentation":
            continue
        text = rule.get("behavior") or rule.get("text") or ""
        if any(term in text for term in ("保存", "持久", "历史记录", "战绩", "排行榜", "跨局", "写入记录")):
            return True
    return False


def prepare_phase60_inputs(expansion_plans: list[dict[str, Any]], scoped_models: list[dict[str, Any]],
                           approved_rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply read-only preflight corrections without mutating historical artifacts."""
    plans = copy.deepcopy(expansion_plans)
    rules = _rule_map(approved_rules)
    corrections: list[dict[str, Any]] = []
    recorded_owners: set[str] = set()
    for model in scoped_models:
        for scope in model.get("mechanicScopes", model.get("scopeItems", [])):
            if scope.get("scopeItem") != "recorded_data":
                continue
            if scope.get("existenceStatus") in {"confirmed", "strongly_implied"} and not _recorded_data_has_persistence_evidence(scope, rules):
                recorded_owners.add(model["chapterId"])
                corrections.append({"chapterId": model["chapterId"], "scopeItem": "recorded_data",
                                    "previousStatus": scope.get("existenceStatus"), "correctedStatus": "unsupported",
                                    "reason": "结算展示证据不能证明结算后跨局保存；未发现历史记录、战绩、排行榜或持久化逻辑证据。",
                                    "historicalScopeArtifactModified": False})

    for plan in plans:
        moved: list[dict[str, Any]] = []
        retained: list[dict[str, Any]] = []
        for detail in plan.get("missingExecutionDetails", []):
            semantic = detail.get("semantic")
            if semantic in PARAMETER_ONLY_MISSING:
                parameter_semantic, label = PARAMETER_ONLY_MISSING[semantic]
                if not any(item.get("semantic") == parameter_semantic for item in plan.get("gameplayParameters", [])):
                    moved.append({"semantic": parameter_semantic, "label": label, "applicability": "active",
                                  "sourceParameterCarrierIds": detail.get("sourceMissingIds", [])})
            else:
                retained.append(detail)
        plan["missingExecutionDetails"] = retained
        plan.setdefault("gameplayParameters", []).extend(moved)

        if plan.get("ownerChapter") in recorded_owners and plan.get("ruleTopic") == "数据记录":
            plan["missingExecutionDetails"] = [item for item in plan.get("missingExecutionDetails", [])
                                               if item.get("semantic") != "recorded_data"]
            plan.setdefault("stopReasons", []).append({"candidateDimension": "recorded_data",
                "reasonType": "scope_downgraded", "scopeStatus": "unsupported",
                "reason": "当前只有结算展示证据，不能建立跨局保存规则。"})
            plan["depthStatus"] = plan["depthVerdict"] = "over-expanded"
            plan["parameterCompletenessStatus"] = "not_applicable"
            continue

        plan["depthStatus"] = plan["depthVerdict"] = (
            "under-expanded" if plan.get("missingExecutionDetails") else "appropriate"
        )
        plan["parameterCompletenessStatus"] = (
            "incomplete" if plan.get("gameplayParameters") else "complete"
        )
    return {"expansionPlans": plans, "scopeCorrections": corrections}


def _placement(owner: str, layout: str, semantic: str, label: str, source_evidence: list[str],
               parameter_class: str, observed_value: Any = None, unit: str | None = None,
               source_rule_ids: list[str] | None = None) -> dict[str, Any]:
    formula = "unresolved" if semantic == "damage" and parameter_class == "unresolved_gameplay_parameter" else "not_applicable"
    return {"parameterId": _id(owner, layout, semantic, ",".join(source_rule_ids or [])),
            "ownerChapter": owner, "ownerLayout": layout, "semantic": semantic,
            "naturalPlacement": "inline_rule" if parameter_class == "observed_value" else PLACEMENT.get(semantic, "nested_bullet"),
            "displayLabel": label, "parameterClass": parameter_class,
            "valueStatus": "observed" if parameter_class == "observed_value" else "unresolved",
            "observedValue": observed_value, "unit": unit, "formulaStatus": formula,
            "configReferenceStatus": "no_confirmed_reference", "sourceEvidence": sorted(set(source_evidence)),
            "sourceRuleIds": source_rule_ids or []}


def _layout_for(plans: list[dict[str, Any]], owner: str, topic: str) -> dict[str, Any] | None:
    return next((plan for plan in plans if plan.get("ownerChapter") == owner and plan.get("ruleTopic") == topic), None)


def build_parameter_placement_plans(expansion_plans: list[dict[str, Any]], layouts: list[dict[str, Any]],
                                    groups: list[dict[str, Any]], approved_rules: list[dict[str, Any]],
                                    scoped_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = _rule_map(approved_rules)
    placements: list[dict[str, Any]] = []
    for plan in expansion_plans:
        evidence = []
        for detail in plan.get("confirmedDetails", []):
            for rule_id in detail.get("sourceRuleIds", []):
                evidence.extend(rules.get(rule_id, {}).get("evidenceIds", []))
        for parameter in plan.get("gameplayParameters", []):
            placements.append(_placement(plan["ownerChapter"], plan["layoutId"], parameter["semantic"],
                                         parameter["label"], evidence, "unresolved_gameplay_parameter"))

    # Observed values remain attached to the natural three-choice rule layouts.
    random_owners = {rule.get("ownerChapterId") for rule in approved_rules
                     if rule.get("schemaSlot") in {"random_trigger", "candidate_selection", "effect_parameter"}}
    random_owner = next((owner for owner in random_owners if _layout_for(expansion_plans, owner, "触发与选择")), None)
    trigger_layout = _layout_for(expansion_plans, random_owner, "触发与选择") if random_owner else None
    result_layout = _layout_for(expansion_plans, random_owner, "选择结果") if random_owner else None
    for rule in approved_rules:
        rule_id = rule.get("ruleId") or rule.get("id")
        text = rule.get("behavior") or rule.get("text") or ""
        evidence = rule.get("evidenceIds", [])
        spec = None
        target = None
        if rule.get("schemaSlot") == "random_trigger" and "三张" in text:
            spec, target = ("candidate_count", "候选数量", 3, "张"), trigger_layout
        elif rule.get("schemaSlot") == "candidate_selection" and "一项" in text:
            spec, target = ("selection_count", "选择数量", 1, "项"), trigger_layout
        elif rule.get("schemaSlot") == "effect_parameter" and "范围" in text:
            match = re.search(r"(\d+)%", text)
            if match:
                spec, target = ("fire_range_modifier", "火焰喷射攻击范围", int(match.group(1)), "%"), result_layout
        elif rule.get("schemaSlot") == "effect_parameter" and "伤害" in text:
            match = re.search(r"(\d+)%", text)
            if match:
                spec, target = ("thunder_damage_modifier", "雷暴枪伤害", int(match.group(1)), "%"), result_layout
        elif rule.get("schemaSlot") == "content_catalog_definition" and "单方向" in text and "四向" in text:
            spec, target = ("ultimate_direction_change", "终极词条喷射方向", "单方向→四向", "方向"), result_layout
        if spec and target:
            semantic, label, value, unit = spec
            placements.append(_placement(target["ownerChapter"], target["layoutId"], semantic, label, evidence,
                                         "observed_value", value, unit, [rule_id]))
    return placements


def evaluate_gve16_parameter_integration(placements: list[dict[str, Any]], approved_rules: list[dict[str, Any]]) -> dict[str, Any]:
    orphan = [item["parameterId"] for item in placements if not item.get("ownerChapter") or not item.get("ownerLayout")]
    internal = [item["parameterId"] for item in placements
                if re.search(r"[A-Za-z_]+[._][A-Za-z_]", item.get("displayLabel", ""))]
    bad_configs = [item["parameterId"] for item in placements
                   if item.get("configReferenceStatus") not in {"no_confirmed_reference", "confirmed"}]
    bad_formula = [item["parameterId"] for item in placements
                   if item.get("formulaStatus") not in {"not_applicable", "unresolved", "confirmed"}]
    unnecessary_tables = [item["parameterId"] for item in placements if item.get("naturalPlacement") == "attribute_table"
                          and item.get("tableJustification", {}).get("sharedFieldObjectCount", 0) < 2]
    required_observed = {rule.get("ruleId") for rule in approved_rules if (
        (rule.get("schemaSlot") in {"random_trigger", "candidate_selection"} and
         any(token in (rule.get("behavior") or rule.get("text") or "") for token in ("三张", "一项"))) or
        rule.get("schemaSlot") == "effect_parameter" or
        (rule.get("schemaSlot") == "content_catalog_definition" and "四向" in (rule.get("behavior") or ""))
    )}
    placed_observed = {rule_id for item in placements if item.get("parameterClass") == "observed_value"
                       for rule_id in item.get("sourceRuleIds", [])}
    lost_observed = sorted(required_observed - placed_observed)
    findings = orphan + internal + bad_configs + bad_formula + unnecessary_tables + lost_observed
    unresolved = sum(item.get("parameterClass") == "unresolved_gameplay_parameter" for item in placements)
    return {"qualityGate": "pass" if not findings else "fail", "parameterCount": len(placements),
            "orphanParameterCount": len(orphan), "internalFieldLabelCount": len(internal),
            "unsupportedConfigReferenceCount": len(bad_configs), "unsupportedFormulaCount": len(bad_formula),
            "lostObservedValueCount": len(lost_observed), "unnecessaryTableCount": len(unnecessary_tables),
            "unresolvedParameterCount": unresolved, "findings": findings}
