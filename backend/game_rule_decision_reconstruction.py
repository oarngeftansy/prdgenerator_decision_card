from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, Mapping


ACTIVE_SCOPE = {"confirmed", "strongly_implied"}

# These are planner-facing decision groups. Slots are classification inputs, never headings.
GROUP_SPECS: dict[str, list[dict[str, Any]]] = {
    "movement": [
        {"title": "移动规则", "category": "usage_rule", "scopes": {"movement_action", "player_control", "movement_boundary"},
         "slots": {"movement_trigger", "movement_control", "movement_path", "movement_stop"},
         "semantics": {"movement_path_contract", "movement_stop"}, "parameters": {"movement_speed"}},
    ],
    "attack": [
        {"title": "获取与栏位", "category": "acquisition_rule", "scopes": {"acquisition", "loadout_capacity"},
         "slots": {"acquisition_rule", "random_trigger", "slot_count"}, "semantics": {"acquisition_rule", "loadout_capacity"}, "parameters": set()},
        {"title": "攻击规则", "category": "combat_rule", "scopes": {"attack_method", "targeting", "weapon_types"},
         "slots": {"attack_trigger", "attack_target", "attack_method"},
         "semantics": {"attack_method", "damage_output", "usage_rule", "combat_rule"},
         "parameters": {"next_attack_trigger", "attack_entry", "damage_output"}},
        {"title": "成长与词条", "category": "progression_rule", "scopes": {"progression", "modifier_application"},
         "slots": {"candidate_effect", "effect_parameter", "content_catalog_definition"},
         "semantics": {"progression_rule", "modifier_application"}, "parameters": set()},
    ],
    "randomization": [
        {"title": "可获取词条", "category": "randomization_rule", "scopes": {"candidate_scope", "owned_content_effect"},
         "slots": set(), "semantics": {"candidate_filter", "candidate_scope"}, "parameters": set()},
        {"title": "随机规则", "category": "randomization_rule", "scopes": {"trigger", "candidate_scope", "selection_count"},
         "slots": {"random_trigger", "candidate_selection", "selection_pause"},
         "semantics": {"randomization_rule", "selection_count"}, "parameters": {"candidate_weight_contract"}},
        {"title": "刷新规则", "category": "resource_rule", "scopes": {"refresh", "refresh_cost"},
         "slots": {"refresh_rule", "refresh_cost"}, "semantics": {"refresh", "refresh_cost"},
         "parameters": {"refresh_count", "refresh_cost_contract"}},
        {"title": "选择结果", "category": "progression_rule", "scopes": {"effect_application", "owned_content_effect"},
         "slots": {"candidate_effect", "effect_parameter"}, "semantics": {"effect_application", "progression_rule"}, "parameters": set()},
    ],
    "monster_attack": [
        {"title": "接触伤害", "category": "combat_rule", "scopes": {"attack_trigger", "contact_effect", "damage_mode", "target_system_relation"},
         "slots": {"attack_trigger", "attack_method", "damage_result"},
         "semantics": {"contact_damage_processing", "damage_mode"}, "parameters": {"contact_damage_interval"}},
    ],
    "level_flow": [
        {"title": "关卡推进", "category": "level_flow_rule", "scopes": {"entry", "stage_or_wave", "wave_progress", "spawn_timing", "player_level_up", "time_limit"},
         "slots": {"flow_trigger", "stage_transition", "spawn_source"},
         "semantics": {"level_flow_rule", "player_level_up", "time_limit"}, "parameters": {"time_limit"}},
        {"title": "胜负规则", "category": "victory_failure_rule", "scopes": {"victory", "failure"},
         "slots": {"victory_condition", "failure_condition"}, "semantics": {"victory_rule", "failure_rule"}, "parameters": set()},
    ],
    "settlement": [
        {"title": "结算结果", "category": "settlement_rule", "scopes": {"displayed_data", "victory_trigger", "failure_trigger"},
         "slots": {"settlement_trigger", "result_judgement", "settlement_presentation"},
         "semantics": {"displayed_data", "victory_rule", "failure_rule"}, "parameters": set()},
        {"title": "数据记录", "category": "lifecycle_rule", "scopes": {"recorded_data", "progress_settlement"},
         "slots": {"record_update", "statistics"}, "semantics": {"recorded_data", "lifecycle_rule"}, "parameters": set()},
    ],
}


def _id(mechanic_id: str, title: str) -> str:
    return "GRP-" + hashlib.sha1(f"{mechanic_id}:{title}".encode("utf-8")).hexdigest()[:12].upper()


def _matches_rule(item: Mapping[str, Any], spec: Mapping[str, Any]) -> bool:
    # Planner groups are selected by the rule's concrete schema slot. The broad
    # gameRuleType is deliberately insufficient because one type spans several decisions.
    return item.get("schemaSlot") in spec["slots"]


def _matches_missing(item: Mapping[str, Any], spec: Mapping[str, Any]) -> bool:
    # A scope proves the group may exist; it does not make every generic missing
    # dimension in that scope a planner rule. Missing rules require an explicit
    # planner semantic mapping.
    return item.get("semantic") in spec["semantics"]


def reconstruct_game_rule_groups(scoped_models: list[dict[str, Any]], approved_rules: list[dict[str, Any]],
                                 entity_graph: dict[str, Any], corpora: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build planner decision groups without promoting corpus candidates or changing source models."""
    del approved_rules, corpora  # scoped models already carry reviewed rule projections; corpora have no fact authority.
    groups: list[dict[str, Any]] = []
    for model in deepcopy(scoped_models):
        scopes = model.get("mechanicScopes", [])
        active = {item["scopeItem"]: item for item in scopes if item.get("existenceStatus") in ACTIVE_SCOPE}
        rejected = [{"scopeItem": item["scopeItem"], "existenceStatus": item["existenceStatus"]}
                    for item in scopes if item.get("existenceStatus") not in ACTIVE_SCOPE]
        specs = GROUP_SPECS.get(model.get("mechanicType"), [])
        mechanic_groups: list[dict[str, Any]] = []
        assigned_rules: set[str] = set()
        assigned_missing: set[str] = set()
        assigned_parameters: set[str] = set()
        for spec in specs:
            scope_basis = [active[name] for name in spec["scopes"] if name in active]
            known = [item for item in model.get("knownGameRules", [])
                     if item.get("ruleId") not in assigned_rules and _matches_rule(item, spec)]
            missing = [item for item in model.get("missingGameRules", [])
                       if item.get("sourceId") not in assigned_missing and _matches_missing(item, spec)
                       and item.get("scopeStatus") in ACTIVE_SCOPE]
            parameters = [item for item in model.get("gameplayParameters", [])
                          if item.get("sourceId") not in assigned_parameters and item.get("semantic") in spec["parameters"]]
            if not (known or missing or parameters):
                continue
            assigned_rules.update(item["ruleId"] for item in known)
            assigned_missing.update(item["sourceId"] for item in missing)
            assigned_parameters.update(item["sourceId"] for item in parameters)
            related = list(model.get("relatedSystems", []))
            for entity in entity_graph.get("entities", []):
                if model.get("chapterId") in ([entity.get("primaryDefinitionChapter")] + entity.get("referenceChapters", [])):
                    related.append(entity["entityId"])
            related = sorted(set(related))
            lifecycle = [item for item in known + missing if item.get("gameRuleType") == "lifecycle_rule"]
            group = {"groupId": _id(model["mechanicId"], spec["title"]), "mechanicId": model["mechanicId"],
                     "mechanicName": model.get("name"), "title": spec["title"], "ruleCategory": spec["category"],
                     "scopeBasis": scope_basis, "knownRules": known, "missingRules": missing,
                     "gameplayParameters": parameters, "relatedSystems": related, "lifecycleRules": lifecycle,
                     "evidenceStatus": "partial" if known and missing else "confirmed" if known else "unresolved",
                     "rejectedDimensions": []}
            mechanic_groups.append(group)
        if mechanic_groups:
            mechanic_groups[0]["rejectedDimensions"] = rejected
        groups.extend(mechanic_groups)
    return groups


def evaluate_rule_group_granularity(groups: list[dict[str, Any]], scoped_models: list[dict[str, Any]]) -> dict[str, Any]:
    scope_status = {(item["mechanicId"], scope["scopeItem"]): scope["existenceStatus"]
                    for item in scoped_models for scope in item.get("mechanicScopes", [])}
    unsupported = []
    one_gap_headings = []
    implementation = []
    parameter_headings = []
    duplicate_siblings = []
    non_gameplay_titles = []
    seen_groups: set[tuple[str, str]] = set()
    internal_terms = {"breakpoint", "node", "edge", "contract", "pipeline", "target_set_build", "atomic commit", "event ordering"}
    for group in groups:
        sibling_key = (group["mechanicId"], group["title"])
        if sibling_key in seen_groups:
            duplicate_siblings.append(group["groupId"])
        seen_groups.add(sibling_key)
        for basis in group.get("scopeBasis", []):
            if scope_status.get((group["mechanicId"], basis["scopeItem"])) not in ACTIVE_SCOPE:
                unsupported.append(group["groupId"])
        text = f"{group.get('title','')} {group.get('knownRules',[])} {group.get('missingRules',[])}".lower()
        if any(term in text for term in internal_terms):
            implementation.append(group["groupId"])
        if not group.get("title") or any(term in group["title"].lower() for term in internal_terms):
            non_gameplay_titles.append(group["groupId"])
        if not group.get("knownRules") and len(group.get("missingRules", [])) == 1 and not group.get("gameplayParameters"):
            # A single gap is acceptable only when it is grouped under a stable planner topic, never its semantic label.
            if group["title"] == group["missingRules"][0].get("semantic"):
                one_gap_headings.append(group["groupId"])
        if len(group.get("gameplayParameters", [])) == 1 and not group.get("knownRules") and not group.get("missingRules"):
            parameter_headings.append(group["groupId"])
    findings = unsupported + implementation + one_gap_headings + parameter_headings + duplicate_siblings + non_gameplay_titles
    return {"qualityGate": "pass" if not findings else "fail", "groupCount": len(groups),
            "unsupportedScopeGroupCount": len(set(unsupported)),
            "implementationDetailPollutionCount": len(set(implementation)),
            "oneGapOneHeadingCount": len(set(one_gap_headings)),
            "parameterPromotedToGroupCount": len(set(parameter_headings)),
            "duplicateSiblingGroupCount": len(set(duplicate_siblings)),
            "nonGameplayThemeTitleCount": len(set(non_gameplay_titles)),
            "findings": sorted(set(findings))}
