from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


GAME_RULE_TYPES = (
    "acquisition_rule", "usage_rule", "unlock_rule", "progression_rule", "randomization_rule",
    "combat_rule", "reward_rule", "failure_rule", "victory_rule", "level_flow_rule", "resource_rule",
    "state_rule", "limitation_rule", "lifecycle_rule", "system_dependency",
)
GAME_EXECUTION_RULE_TYPES = {"logic", "flow", "numeric", "config", "interaction"}

FIELD_BY_TYPE = {
    "acquisition_rule": "acquisitionRules", "usage_rule": "usageRules", "unlock_rule": "unlockRules",
    "progression_rule": "progressionRules", "randomization_rule": "randomRules", "combat_rule": "usageRules",
    "reward_rule": "rewardRules", "failure_rule": "victoryFailureRules", "victory_rule": "victoryFailureRules",
    "level_flow_rule": "stateRules", "resource_rule": "resourceRules", "state_rule": "stateRules",
    "limitation_rule": "limitationRules", "lifecycle_rule": "lifecycleRules",
    "system_dependency": "relatedSystems",
}

IMPLEMENTATION_SEMANTICS = {
    "target_priority", "empty_target_behavior", "movement_input_composition", "movement_input_release",
    "selection_commit", "refresh_selection_exclusion", "contact_damage_aggregation", "internal_state_cleanup",
    "polling", "event_ordering", "atomic_commit", "vector_composition", "technical_fallback", "selection_state_exit",
}
CONFIGURATION_VALIDATION_SEMANTICS = {"empty_candidate", "candidate_shortage_behavior"}

SEMANTIC_GAME_TYPES = {
    "weapon_acquisition": "acquisition_rule", "weapon_unlock": "unlock_rule",
    "candidate_filter": "randomization_rule", "candidate_constraints": "randomization_rule",
    "candidate_weight_contract": "randomization_rule", "empty_candidate": "randomization_rule",
    "candidate_shortage_behavior": "randomization_rule", "selection_state_exit": "state_rule",
    "contact_damage_processing": "combat_rule", "contact_damage_interval": "combat_rule",
    "movement_speed": "usage_rule", "movement_stop": "state_rule", "movement_path_contract": "usage_rule",
    "refresh_count": "resource_rule", "refresh_cost_contract": "resource_rule",
}

SLOT_GAME_TYPES = {
    "movement_trigger": "usage_rule", "movement_control": "usage_rule",
    "attack_trigger": "combat_rule", "attack_target": "combat_rule", "attack_method": "combat_rule",
    "random_trigger": "randomization_rule", "selection_pause": "state_rule",
    "candidate_selection": "randomization_rule", "candidate_effect": "progression_rule",
    "effect_parameter": "progression_rule", "refresh_rule": "randomization_rule", "refresh_cost": "resource_rule",
    "spawn_trigger": "level_flow_rule", "victory_condition": "victory_rule", "failure_condition": "failure_rule",
    "settlement_trigger": "level_flow_rule", "reward_rule": "reward_rule", "record_update": "lifecycle_rule",
}

PURPOSES = {
    "movement": "定义玩家如何控制移动，以及移动如何影响关卡推进。",
    "attack": "定义武器如何被玩家使用并产生战斗结果。",
    "monster_attack": "定义怪物如何对玩家对象产生战斗影响。",
    "randomization": "定义随机成长何时发生、可获得什么以及选择如何生效。",
    "spawn": "定义战斗对象如何进入关卡并参与关卡推进。",
    "level_flow": "定义关卡如何进入、推进、结束并衔接成长与结算。",
    "settlement": "定义胜负结果、奖励、记录与局内状态收尾。",
}

CHECK_SLOTS = {
    "movement_action": {"movement_trigger"}, "player_control": {"movement_control"},
    "attack_method": {"attack_method", "attack_target"}, "targeting": {"attack_target", "attack_trigger"},
    "trigger": {"random_trigger"}, "selection_count": {"candidate_selection"},
    "effect_application": {"candidate_effect", "effect_parameter"}, "refresh": {"refresh_rule"},
    "refresh_cost": {"refresh_cost"}, "contact_effect": {"attack_trigger"},
    "victory": {"victory_condition"}, "failure": {"failure_condition"},
    "reward_basis": {"reward_rule"}, "recorded_data": {"record_update"},
}


def load_game_rule_corpus(path: str | Path) -> dict[str, Any]:
    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    if corpus.get("contentAuthority") != "none" or not corpus.get("provisional"):
        raise ValueError("Game Rule Corpus must remain provisional and cannot be content authority")
    return corpus


def _approved(rule: dict[str, Any]) -> bool:
    return rule.get("reviewStatus") in {"approved", "confirmed", "unreviewed"} and rule.get("semanticValidity") == "valid"


def _mechanic_id(chapter: dict[str, Any]) -> str:
    digest = hashlib.sha1(f"game-rule:{chapter['chapterId']}".encode("utf-8")).hexdigest()[:12].upper()
    return f"GRM-{digest}"


def _empty_model(chapter: dict[str, Any]) -> dict[str, Any]:
    name_parts = list(dict.fromkeys(filter(None, (chapter.get("object"), chapter.get("title")))))
    return {"mechanicId": chapter.get("mechanicId") or _mechanic_id(chapter), "chapterId": chapter["chapterId"],
            "mechanicType": chapter.get("chapterType"), "name": " / ".join(name_parts),
            "gameplayPurpose": PURPOSES.get(chapter.get("chapterType"), "定义该系统面向玩家的玩法规则与系统关系。"),
            "playerEntry": [], "acquisitionRules": [], "usageRules": [], "unlockRules": [],
            "progressionRules": [], "randomRules": [], "stateRules": [], "limitationRules": [],
            "resourceRules": [], "rewardRules": [], "victoryFailureRules": [], "lifecycleRules": [],
            "relatedSystems": [], "parameterNeeds": [], "entityAttributeNeeds": [], "confirmedRules": [], "missingGameRules": [],
            "implementationDetails": [], "rulesUnderReview": []}


def build_game_rule_models(chapters: list[dict[str, Any]], approved_rules: list[dict[str, Any]],
                           reasoning_items: list[dict[str, Any]], corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    models = []
    for chapter in deepcopy(chapters):
        model = _empty_model(chapter)
        related = [item for item in reasoning_items if item.get("mechanicId") in {chapter["chapterId"], model["mechanicId"]}]
        route_path_conflict = any(item.get("gapDisposition") == "upstream_conflict" and
                                  item.get("missingNodeSemantic") == "movement_path_contract" for item in related)
        supporting_ids = set(chapter.get("supportingRuleIds", []))
        chapter_rules = [deepcopy(rule) for rule in approved_rules if (rule.get("ownerChapterId") == chapter["chapterId"] or
                         rule.get("ruleId") in supporting_ids) and
                         rule.get("ruleType") in GAME_EXECUTION_RULE_TYPES and _approved(rule)]
        confirmed_types = set()
        for rule in chapter_rules:
            if route_path_conflict and rule.get("schemaSlot") == "movement_trigger" and "预设路线" in str(rule.get("behavior")):
                model["rulesUnderReview"].append({"ruleId": rule["ruleId"], "reason": "上游静态证据不足以证明自动沿预设路线移动。"})
                continue
            game_type = SLOT_GAME_TYPES.get(rule.get("schemaSlot"), "usage_rule")
            if chapter.get("chapterType") == "attack" and rule.get("schemaSlot") == "attack_trigger" and "无需玩家手动瞄准" in str(rule.get("behavior")):
                game_type = "usage_rule"
            if chapter.get("chapterType") == "attack" and "获得武器" in str(rule.get("behavior")):
                game_type = "acquisition_rule"
            item = {"ruleId": rule["ruleId"], "gameRuleType": game_type, "text": rule.get("behavior"),
                    "schemaSlot": rule.get("schemaSlot")}
            model[FIELD_BY_TYPE[game_type]].append(item)
            if rule.get("schemaSlot") in {"movement_trigger", "attack_trigger", "random_trigger", "spawn_trigger", "settlement_trigger"}:
                model["playerEntry"].append(item)
            model["confirmedRules"].append(rule["ruleId"])
            confirmed_types.add(game_type)
        for item in related:
            semantic = item.get("missingNodeSemantic")
            source_id = item.get("gapId") or item.get("sourceId")
            disposition = item.get("gapDisposition")
            if disposition == "parameter_need":
                model["parameterNeeds"].append({"sourceId": source_id, "semantic": semantic,
                                                "contract": item.get("reducedContract")})
            elif disposition == "entity_attribute":
                model["entityAttributeNeeds"].append({"sourceId": source_id, "semantic": semantic,
                                                      "attribute": item.get("reducedContract")})
            elif semantic in CONFIGURATION_VALIDATION_SEMANTICS:
                model["implementationDetails"].append({"sourceId": source_id, "semantic": semantic,
                                                       "detailType": "configuration_validation",
                                                       "reason": "正常配置完整性与异常兜底校验，不作为当前主玩法规则决策。"})
            elif disposition in {"implementation_default", "already_answered_by_evidence", "defer"} or semantic in IMPLEMENTATION_SEMANTICS:
                model["implementationDetails"].append({"sourceId": source_id, "semantic": semantic,
                                                       "detailType": "implementation_detail",
                                                       "reason": "只影响内部实现，不改变当前可证明的玩家玩法规则。"})
            elif semantic in SEMANTIC_GAME_TYPES:
                game_type = SEMANTIC_GAME_TYPES[semantic]
                model["missingGameRules"].append({"sourceId": source_id, "gameRuleType": game_type,
                                                  "semantic": semantic, "status": "unresolved"})
        template = corpus.get("templates", {}).get(chapter.get("chapterType"), {})
        existing_missing = {item["gameRuleType"] for item in model["missingGameRules"]}
        for game_type in template.get("gameRuleDimensions", []):
            if game_type not in confirmed_types and game_type not in existing_missing:
                model["missingGameRules"].append({"sourceId": f"TEMPLATE:{chapter['chapterId']}:{game_type}",
                                                  "gameRuleType": game_type, "semantic": game_type,
                                                  "status": "unresolved", "plannerReviewEligible": False})
        deduped: dict[tuple[str, str], dict[str, Any]] = {}
        for item in model["missingGameRules"]:
            key = (item["gameRuleType"], item["semantic"])
            if key not in deduped:
                deduped[key] = {**item, "sourceIds": [item["sourceId"]]}
            elif item["sourceId"] not in deduped[key]["sourceIds"]:
                deduped[key]["sourceIds"].append(item["sourceId"])
        model["missingGameRules"] = list(deduped.values())
        model["gameMechanicSkeleton"] = [
            {"gameRuleType": game_type, "status": "partially_confirmed" if game_type in confirmed_types else "unresolved"}
            for game_type in template.get("gameRuleDimensions", [])
        ]
        model["gameRuleChecks"] = []
        for check in template.get("ruleChecks", []):
            supporting = [rule["ruleId"] for rule in chapter_rules if rule["ruleId"] in model["confirmedRules"] and
                          rule.get("schemaSlot") in CHECK_SLOTS.get(check, set())]
            model["gameRuleChecks"].append({"semantic": check, "status": "confirmed" if supporting else "unresolved",
                                           "supportingRuleIds": supporting})
        models.append(model)
    return models


def evaluate_game_mechanic_depth(models: list[dict[str, Any]]) -> dict[str, Any]:
    if not models:
        return {"total": 0.0, "dimensions": {}}
    totals = {"gameRuleCoverage": 0.0, "playerBehaviorChain": 0.0, "growthResourceChain": 0.0,
              "ruleLimitations": 0.0, "systemRelationships": 0.0, "victoryReward": 0.0,
              "lifecycle": 0.0}
    for model in models:
        confirmed = set()
        for field in FIELD_BY_TYPE.values():
            for item in model.get(field, []):
                if isinstance(item, dict) and item.get("gameRuleType"):
                    confirmed.add(item["gameRuleType"])
        applicable = confirmed | {item["gameRuleType"] for item in model["missingGameRules"]}
        totals["gameRuleCoverage"] += 25 * len(confirmed) / max(1, len(applicable))
        totals["playerBehaviorChain"] += 20 * min(1, len(confirmed & {"acquisition_rule", "usage_rule", "combat_rule", "state_rule"}) / 2)
        totals["growthResourceChain"] += 15 * min(1, len(confirmed & {"progression_rule", "resource_rule", "randomization_rule"}) / 2)
        totals["ruleLimitations"] += 10 if "limitation_rule" in confirmed else 0
        totals["systemRelationships"] += 10 if "system_dependency" in confirmed else 0
        totals["victoryReward"] += 10 * min(1, len(confirmed & {"victory_rule", "failure_rule", "reward_rule"}) / 2)
        totals["lifecycle"] += 10 if "lifecycle_rule" in confirmed else 0
    dimensions = {key: round(value / len(models), 2) for key, value in totals.items()}
    return {"total": round(sum(dimensions.values()), 2), "dimensions": dimensions,
            "implementationDetailCount": sum(len(model["implementationDetails"]) for model in models),
            "implementationDetailsAffectScore": False,
            "policy": "only confirmed player-facing game rules increase depth; implementation detail count contributes zero"}
