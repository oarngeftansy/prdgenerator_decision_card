from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


ACTIVE_STATUSES = {"confirmed", "strongly_implied"}

CHECK_RULE_SLOTS = {
    "movement_action": {"movement_trigger"}, "player_control": {"movement_control"},
    "acquisition": {"acquisition_rule", "random_trigger"}, "unlock": {"unlock_rule"},
    "loadout_capacity": {"slot_count"}, "duplicate_acquisition": {"duplicate_rule"},
    "replacement": {"replacement_rule"}, "weapon_types": {"attack_method", "attack_target", "effect_parameter"},
    "attack_method": {"attack_method", "attack_target"}, "targeting": {"attack_target", "attack_trigger"},
    "progression": {"candidate_effect", "effect_parameter"}, "modifier_application": {"candidate_effect", "effect_parameter", "content_catalog_definition"},
    "trigger": {"random_trigger"}, "candidate_scope": {"random_trigger", "candidate_selection"},
    "owned_content_effect": {"candidate_effect"}, "selection_count": {"candidate_selection"},
    "refresh": {"refresh_rule"}, "refresh_cost": {"refresh_cost"}, "effect_application": {"candidate_effect", "effect_parameter"},
    "attack_trigger": {"attack_trigger"}, "contact_effect": {"attack_trigger"}, "target_system_relation": {"attack_trigger"},
    "spawn_timing": {"spawn_source"}, "failure": {"failure_condition"},
    "displayed_data": {"settlement_presentation"}, "recorded_data": {"settlement_presentation", "record_update"},
}

UNSUPPORTED_WITHOUT_DIRECT = {"unlock", "replacement"}
PARAMETER_PARENT = {
    "movement_speed": "player_control", "next_attack_trigger": "attack_method",
    "attack_entry": "attack_method", "damage_output": "attack_method",
    "candidate_weight_contract": "weight", "refresh_count": "refresh",
    "refresh_cost_contract": "refresh_cost", "contact_damage_interval": "sustained_contact_damage",
}
PARAMETER_CONTRACT = {"contact_damage_interval": "Monster.contactDamageInterval"}
SEMANTIC_SCOPE = {
    "acquisition_rule": "acquisition", "unlock_rule": "unlock", "usage_rule": "attack_method",
    "combat_rule": "attack_method", "progression_rule": "progression", "limitation_rule": "combat_limit",
    "system_dependency": "target_system_relation", "randomization_rule": "candidate_scope",
    "resource_rule": "refresh_cost", "state_rule": "effect_application", "lifecycle_rule": "run_reset",
    "level_flow_rule": "wave_progress", "victory_rule": "victory", "failure_rule": "failure",
    "reward_rule": "reward_basis", "candidate_filter": "candidate_scope",
    "candidate_constraints": "duplicate", "contact_damage_processing": "damage_mode",
    "movement_path_contract": "movement_action", "movement_stop": "movement_boundary",
}
SCOPE_GAME_TYPE = {"loadout_capacity": "limitation_rule", "player_level_up": "progression_rule",
                   "time_limit": "limitation_rule", "displayed_data": "state_rule", "recorded_data": "lifecycle_rule",
                   "damage_mode": "combat_rule"}


def _valid_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [rule for rule in rules if rule.get("semanticValidity") == "valid"]


def infer_mechanic_scopes(chapters: list[dict[str, Any]], rules: list[dict[str, Any]], ui_structure: list[dict[str, Any]],
                          entity_graph: dict[str, Any], corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    valid = _valid_rules(rules)
    ui_items = list(ui_structure or [])
    scopes = []
    for chapter in chapters:
        mechanic_id, mechanic_type = chapter["mechanicId"], chapter["chapterType"]
        checks = corpus.get("templates", {}).get(mechanic_type, {}).get("ruleChecks", [])
        supporting_ids = set(chapter.get("supportingRuleIds", []))
        chapter_rules = [rule for rule in valid if rule.get("ownerChapterId") == chapter["chapterId"] or rule.get("ruleId") in supporting_ids]
        cross_rules = [rule for rule in valid if str(chapter.get("object") or "") in str(rule.get("behavior") or "")]
        all_rules = {rule["ruleId"]: rule for rule in chapter_rules + cross_rules}
        presentation = [rule for rule in all_rules.values() if rule.get("ruleType") == "presentation"]
        logic = [rule for rule in all_rules.values() if rule.get("ruleType") != "presentation"]
        entities = entity_graph.get("entities", [])
        has_weapon_slot = mechanic_type == "attack" and any(entity.get("entityType") == "container" and "武器" in str(entity.get("name")) for entity in entities)
        has_candidate_set = mechanic_type == "randomization" and any(entity.get("entityType") == "candidate_set" for entity in entities)
        route_contradiction = any(item.get("mechanicId") == mechanic_id and item.get("gapDisposition") == "upstream_conflict" for item in ui_items)
        for check in checks:
            matched = [rule for rule in logic if rule.get("schemaSlot") in CHECK_RULE_SLOTS.get(check, set())]
            ui_matched = [rule for rule in presentation if rule.get("schemaSlot") in CHECK_RULE_SLOTS.get(check, set())]
            if check == "time_limit":
                ui_matched += [rule for rule in presentation if "倒计时" in str(rule.get("behavior"))]
            if check == "player_level_up":
                ui_matched += [rule for rule in presentation if "当前等级" in str(rule.get("behavior"))]
            if check == "displayed_data":
                ui_matched += [rule for rule in presentation if "结算界面" in str(rule.get("behavior"))]
            if check == "recorded_data":
                ui_matched += [rule for rule in presentation if "纪录" in str(rule.get("behavior"))]
            ui_matched = list({rule["ruleId"]: rule for rule in ui_matched}.values())
            relationship = []
            if check == "loadout_capacity" and has_weapon_slot:
                relationship = [entity["entityId"] for entity in entities if entity.get("entityType") == "container" and "武器" in str(entity.get("name"))]
            if check == "candidate_scope" and has_candidate_set:
                relationship = [entity["entityId"] for entity in entities if entity.get("entityType") == "candidate_set"]
            if route_contradiction and check == "movement_action":
                status, reason = "contradicted", "上游证据无法确认自动沿预设路线移动，且存在相反玩法解释。"
            elif matched:
                status, reason = "confirmed", "存在已审核逻辑/数据 Rule 直接支持该子机制。"
            elif relationship:
                status, reason = "strongly_implied", "已审计 Entity/relationship 证明该子机制载体存在，但具体规则未知。"
            elif ui_matched:
                status, reason = "strongly_implied", "UI/表现结构稳定呈现该玩法对象，但具体逻辑规则未知。"
            elif check == "damage_mode" and any(rule.get("schemaSlot") == "attack_trigger" for rule in logic):
                status, reason = "strongly_implied", "接触伤害已经确认存在，单次或持续的伤害方式必然需要确定，但当前答案未知。"
            elif check in UNSUPPORTED_WITHOUT_DIRECT:
                status, reason = "unsupported", "仅存在于类型模板，当前 Evidence/Rule/UI/relationship 均未证明。"
            elif logic:
                status, reason = "possible", "父机制存在，但当前证据未证明该子机制在本项目中成立。"
            else:
                status, reason = "unsupported", "当前项目没有证据证明该子机制存在。"
            scopes.append({"mechanicId": mechanic_id, "mechanicType": mechanic_type, "scopeItem": check,
                           "existenceStatus": status,
                           "evidenceBasis": sorted({e for rule in matched for e in rule.get("evidenceIds", [])}),
                           "ruleBasis": [rule["ruleId"] for rule in matched], "uiBasis": [rule["ruleId"] for rule in ui_matched],
                           "relationshipBasis": relationship, "applicabilityReason": reason})
    return scopes


def apply_mechanic_scope(models: list[dict[str, Any]], scopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_mechanic: dict[str, list[dict[str, Any]]] = {}
    for scope in scopes:
        by_mechanic.setdefault(scope["mechanicId"], []).append(scope)
    result = []
    for raw in deepcopy(models):
        model_scopes = by_mechanic.get(raw["mechanicId"], [])
        scope_by_item = {item["scopeItem"]: item for item in model_scopes}
        kept, exploration = [], [item for item in model_scopes if item["existenceStatus"] not in ACTIVE_STATUSES]
        for missing in raw.get("missingGameRules", []):
            scope_item = SEMANTIC_SCOPE.get(missing.get("semantic"), missing.get("semantic"))
            scope = scope_by_item.get(scope_item)
            if scope and scope["existenceStatus"] in ACTIVE_STATUSES:
                kept.append({**missing, "scopeItem": scope_item, "scopeStatus": scope["existenceStatus"]})
        raw["missingGameRules"] = kept
        existing_scope_items = {item.get("scopeItem") for item in kept}
        for scope in model_scopes:
            if scope["existenceStatus"] == "strongly_implied" and scope["scopeItem"] not in existing_scope_items:
                raw["missingGameRules"].append({"sourceId": f"SCOPE:{raw['mechanicId']}:{scope['scopeItem']}",
                                                "gameRuleType": SCOPE_GAME_TYPE.get(scope["scopeItem"], "state_rule"),
                                                "semantic": scope["scopeItem"], "status": "unresolved",
                                                "scopeItem": scope["scopeItem"], "scopeStatus": "strongly_implied"})
        raw["explorationCandidates"] = exploration
        gameplay, conditional = [], []
        implementation = []
        parameter_items = list(raw.get("parameterNeeds", []))
        for detail in raw.get("implementationDetails", []):
            if detail.get("semantic") == "contact_damage_interval":
                parameter_items.append({"sourceId": detail.get("sourceId"), "semantic": "contact_damage_interval",
                                        "contract": PARAMETER_CONTRACT["contact_damage_interval"]})
            else:
                implementation.append(detail)
        for parameter in parameter_items:
            parent = PARAMETER_PARENT.get(parameter.get("semantic"))
            parent_scope = scope_by_item.get(parent)
            if parameter.get("semantic") == "contact_damage_interval" and not (parent_scope and parent_scope["existenceStatus"] == "confirmed"):
                conditional.append({**parameter, "applicability": "defer_until_sustained_contact_damage_confirmed"})
            elif parent_scope and parent_scope["existenceStatus"] in ACTIVE_STATUSES:
                gameplay.append({**parameter, "parameterRole": "gameplay_parameter"})
            else:
                exploration.append({"mechanicId": raw["mechanicId"], "scopeItem": parent or parameter.get("semantic"),
                                    "existenceStatus": "possible", "applicabilityReason": "对应参数载体尚未证明适用。"})
        raw["gameplayParameters"] = gameplay
        raw["conditionalGameplayParameters"] = conditional
        raw["implementationDetails"] = implementation
        raw["mechanicScopes"] = model_scopes
        fields = ("acquisitionRules", "usageRules", "unlockRules", "progressionRules", "randomRules", "stateRules",
                  "limitationRules", "resourceRules", "rewardRules", "victoryFailureRules", "lifecycleRules")
        raw["knownGameRules"] = [item for field in fields for item in raw.get(field, [])]
        result.append(raw)
    return result


def evaluate_scope_precision(scopes: list[dict[str, Any]], models: list[dict[str, Any]]) -> dict[str, Any]:
    scope_index = {(item["mechanicId"], item["scopeItem"]): item for item in scopes}
    unsupported = []
    instantiated = 0
    for model in models:
        for item in model.get("missingGameRules", []):
            instantiated += 1
            scope_item = item.get("scopeItem") or SEMANTIC_SCOPE.get(item.get("semantic"), item.get("semantic"))
            scope = scope_index.get((model["mechanicId"], scope_item))
            if scope and scope["existenceStatus"] not in ACTIVE_STATUSES:
                unsupported.append({"mechanicId": model["mechanicId"], "scopeItem": scope_item, "status": scope["existenceStatus"]})
    supported_count = sum(item["existenceStatus"] in ACTIVE_STATUSES for item in scopes)
    return {"qualityGate": "pass" if not unsupported else "fail",
            "unsupportedInstantiatedCount": len(unsupported), "templateOnlyInstantiatedCount": len(unsupported),
            "currentEvidenceSupportedScopeRatio": round(supported_count / len(scopes), 4) if scopes else 0.0,
            "instantiatedMissingGameRuleCount": instantiated, "findings": unsupported,
            "policy": "precision rewards evidence-supported scope; possible/unsupported items stay exploratory"}
