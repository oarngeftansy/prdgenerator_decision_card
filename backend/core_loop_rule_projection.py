from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any


CORE_OWNER = "CORE-GAMEPLAY-LOOP"


def _id(prefix: str, *parts: str) -> str:
    raw = ":".join(parts)
    return f"{prefix}-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def _model_maps(models: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_mechanic = {m["mechanicId"]: m for m in models}
    return by_mechanic, {m["mechanicId"]: m["chapterId"] for m in models}


def _rule_groups(groups: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        for rule in group.get("knownRules", []):
            result.setdefault(rule["ruleId"], []).append({"group": group, "rule": rule})
    return result


def _content_item_owner(rule_id: str, entity_graph: dict[str, Any]) -> str | None:
    fallback = None
    for entity in entity_graph.get("entities", []):
        if entity.get("entityType") != "content_item":
            continue
        fallback = fallback or entity.get("primaryDefinitionChapter")
        if rule_id in entity.get("relatedRuleIds", []):
            return entity.get("primaryDefinitionChapter")
    return fallback


def _primary_owner(rule_id: str, memberships: list[dict[str, Any]], chapter_by_mechanic: dict[str, str],
                   entity_graph: dict[str, Any], approved_owner: str | None = None) -> tuple[str, str]:
    slots = {item["rule"].get("schemaSlot") for item in memberships}
    if slots & {"candidate_effect", "effect_parameter", "content_catalog_definition"}:
        entity_owner = _content_item_owner(rule_id, entity_graph)
        if entity_owner:
            return entity_owner, "强化效果由内容项主定义章节集中定义。"
        weapon = next((item for item in memberships if item["group"].get("title") == "成长与词条"), None)
        if weapon:
            return chapter_by_mechanic[weapon["group"]["mechanicId"]], "强化效果归武器成长与词条规则组主定义。"
    if approved_owner:
        return approved_owner, "沿用已审核 Rule 的原始主定义章节。"
    selected = memberships[0]
    return chapter_by_mechanic[selected["group"]["mechanicId"]], "规则由其所属玩法规则组的系统章节主定义。"


def _rule_role(slot: str | None) -> str:
    roles = {
        "movement_control": "player_control", "movement_trigger": "movement",
        "acquisition_rule": "acquisition", "random_trigger": "entry_trigger",
        "selection_pause": "state_change", "candidate_selection": "player_choice",
        "refresh_rule": "refresh", "refresh_cost": "resource_condition",
        "attack_trigger": "input_constraint", "attack_target": "target_selection",
        "attack_method": "processing", "candidate_effect": "progression_effect",
        "effect_parameter": "progression_parameter", "failure_condition": "failure_rule",
    }
    return roles.get(slot, "game_rule")


def _role_from_chains(rule_id: str, chains: list[dict[str, Any]], fallback: str) -> str:
    semantic_roles = {
        "automatic_targeting_mode": "input_constraint", "select_target": "target_selection",
        "execute_attack": "processing", "generate_candidates": "trigger_and_generation",
        "acquire_weapon": "acquisition",
        "upgrade_trigger": "trigger_and_generation", "select_candidate": "player_choice",
        "refresh_candidates": "refresh", "replace_candidates": "refresh_result",
        "refresh_requirement": "resource_condition", "apply_selected_effect": "progression_effect",
        "apply_weapon_modifier": "progression_effect", "vehicle_control": "player_control",
        "monster_contact_damage": "damage_effect", "failure_exit": "failure_rule",
    }
    local = [c for c in chains if len(c.get("mechanicIds", [])) == 1] + [c for c in chains if len(c.get("mechanicIds", [])) > 1]
    found = []
    for chain in local:
        entry = [chain["entry"]] if chain.get("entry") else []
        steps = entry + [step for field in ("playerAction", "systemResponse", "stateChange", "progressionResult", "exitOrNext")
                         for step in chain.get(field, [])]
        for step in steps:
            if rule_id in step.get("ruleIds", []):
                found.append(semantic_roles.get(step.get("semantic"), fallback))
    priority = ("processing", "target_selection", "trigger_and_generation", "progression_effect", "damage_effect",
                "resource_condition", "refresh_result", "refresh", "player_choice", "state_change", "input_constraint")
    return next((role for role in priority if role in found), found[0] if found else fallback)


def _source_chain(rule_id: str, chains: list[dict[str, Any]], primary_mechanic_ids: set[str]) -> tuple[str, list[str]]:
    candidates = [chain for chain in chains if rule_id in chain.get("supportingRuleIds", [])]
    if not candidates:
        return "", []
    local = next((chain for chain in candidates if len(chain.get("mechanicIds", [])) == 1
                  and set(chain.get("mechanicIds", [])) & primary_mechanic_ids), None)
    chosen = local or candidates[0]
    return chosen["chainId"], [chain["chainId"] for chain in candidates]


def _missing_owner(semantic: str, model_by_type: dict[str, dict[str, Any]], groups: list[dict[str, Any]],
                   entity_graph: dict[str, Any]) -> tuple[str | None, str]:
    type_map = {
        "candidate_filter": "randomization", "resume_combat": "randomization",
        "loadout_capacity": "attack", "damage_resolution": "attack",
        "player_level_up": "level_flow", "victory_path": "level_flow",
        "displayed_data": "settlement",
    }
    mechanic_type = type_map.get(semantic)
    if semantic == "loadout_capacity":
        slot = next((e for e in entity_graph.get("entities", []) if e.get("entityType") == "container"
                     and e.get("semanticKey") == "weapon_slot"), None)
        if slot and slot.get("primaryDefinitionChapter"):
            return slot["primaryDefinitionChapter"], "武器栏缺口归容器的主定义章节。"
    if semantic == "victory_path":
        level = next((e for e in entity_graph.get("entities", []) if e.get("entityType") == "runtime_context"), None)
        if level and level.get("primaryDefinitionChapter"):
            return level["primaryDefinitionChapter"], "胜负出口归关卡主定义章节。"
    model = model_by_type.get(mechanic_type or "")
    if model:
        return model["chapterId"], f"断点归 {mechanic_type} 系统章节处理。"
    return None, "没有已确认的系统 owner。"


def project_core_loop_rules(chains: list[dict[str, Any]], game_rule_groups: list[dict[str, Any]],
                            scoped_models: list[dict[str, Any]], entity_graph: dict[str, Any],
                            approved_rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    model_by_mechanic, chapter_by_mechanic = _model_maps(scoped_models)
    model_by_type = {m["mechanicType"]: m for m in scoped_models}
    memberships = _rule_groups(game_rule_groups)
    approved_owner_by_rule = {rule["ruleId"]: rule.get("ownerChapterId") for rule in (approved_rules or [])}
    projections = []
    for rule_id, items in memberships.items():
        owner, reason = _primary_owner(rule_id, items, chapter_by_mechanic, entity_graph, approved_owner_by_rule.get(rule_id))
        candidate_owners = {chapter_by_mechanic[item["group"]["mechanicId"]] for item in items}
        owner_mechanics = {item["group"]["mechanicId"] for item in items
                           if chapter_by_mechanic[item["group"]["mechanicId"]] == owner}
        source_chain, source_chains = _source_chain(rule_id, chains, owner_mechanics)
        slot = items[0]["rule"].get("schemaSlot")
        rule_role = _role_from_chains(rule_id, chains, _rule_role(slot))
        projections.append({"projectionId": _id("PROJ", rule_id), "sourceChainId": source_chain,
                            "sourceChainIds": source_chains, "sourceRuleId": rule_id, "primaryOwner": owner,
                            "referenceOwners": sorted(({CORE_OWNER} | candidate_owners) - {owner}),
                            "ruleRole": rule_role, "definitionMode": "full_definition", "rationale": reason})

    missing_projections = []
    seen_missing: set[tuple[str, str]] = set()
    for chain in chains:
        for link in chain.get("missingLinks", []):
            key = (link["semanticKey"], link["question"])
            if key in seen_missing:
                continue
            seen_missing.add(key)
            owner, reason = _missing_owner(link["semanticKey"], model_by_type, game_rule_groups, entity_graph)
            missing_projections.append({"projectionId": _id("MISS", chain["chainId"], link["semanticKey"]),
                                        "sourceChainId": chain["chainId"], "semanticKey": link["semanticKey"],
                                        "question": link["question"], "primaryOwner": owner,
                                        "referenceOwners": [CORE_OWNER], "rationale": reason})

    parameter_projections = []
    seen_parameters: set[str] = set()
    group_by_id = {g["groupId"]: g for g in game_rule_groups}
    for chain in chains:
        for parameter in chain.get("gameplayParameters", []):
            parameter_id = parameter.get("sourceId") or parameter.get("semantic")
            if parameter_id in seen_parameters:
                continue
            seen_parameters.add(parameter_id)
            group = group_by_id.get(parameter.get("sourceGroupId"))
            owner = chapter_by_mechanic.get(group["mechanicId"]) if group else None
            parameter_projections.append({"projectionId": _id("PARAMPROJ", str(parameter_id)),
                                          "sourceChainId": chain["chainId"], "sourceRuleId": None,
                                          "sourceParameterId": parameter_id, "primaryOwner": owner,
                                          "referenceOwners": [CORE_OWNER], "ruleRole": "gameplay_parameter",
                                          "definitionMode": "parameter_carrier",
                                          "rationale": "玩法参数随影响它的系统规则组承载，值与配置来源留待 ParameterResolver。"})

    skeletons = []
    entity_by_owner = {e.get("primaryDefinitionChapter"): e for e in entity_graph.get("entities", [])
                       if e.get("primaryDefinitionChapter")}
    entity_group_title = {"container": "栏位规则", "content_item": "词条规则",
                          "runtime_context": "胜负规则", "process": "结算规则", "report": "统计规则"}
    role_group_title = {"acquisition": "获取规则", "refresh": "刷新规则", "refresh_result": "刷新规则",
                        "trigger_and_generation": "触发与候选生成", "failure_rule": "胜负规则"}
    role_chapter_title = {"acquisition": "武器获取", "refresh": "三选一 / 刷新",
                          "refresh_result": "三选一 / 刷新", "failure_rule": "胜负判定"}
    owners = sorted({p["primaryOwner"] for p in projections + parameter_projections if p.get("primaryOwner")}
                    | {m["primaryOwner"] for m in missing_projections if m.get("primaryOwner")})
    for owner in owners:
        owner_models = [m for m in scoped_models if m["chapterId"] == owner]
        owner_groups = [g for g in game_rule_groups if chapter_by_mechanic.get(g["mechanicId"]) == owner]
        owner_entity = entity_by_owner.get(owner)
        owner_roles = [p["ruleRole"] for p in projections if p["primaryOwner"] == owner]
        chapter_title = (owner_models[0].get("name", owner) if owner_models else
                         owner_entity.get("name", owner) if owner_entity else
                         role_chapter_title.get(owner_roles[0], owner) if owner_roles else owner)
        skeleton_groups = [{"groupId": g["groupId"], "title": g["title"]} for g in owner_groups]
        if not skeleton_groups and owner_entity:
            skeleton_groups = [{"groupId": _id("OWNGRP", owner),
                                "title": entity_group_title.get(owner_entity.get("entityType"), f"{owner_entity.get('name', '')}规则")}]
        if not skeleton_groups:
            title = role_group_title.get(owner_roles[0], "系统规则") if owner_roles else "系统规则"
            skeleton_groups = [{"groupId": _id("OWNGRP", owner), "title": title}]
        source_chain_ids = ({p["sourceChainId"] for p in projections if p["primaryOwner"] == owner}
                            | {m["sourceChainId"] for m in missing_projections if m["primaryOwner"] == owner}
                            | {p["sourceChainId"] for p in parameter_projections if p["primaryOwner"] == owner})
        skeletons.append({"chapterOwner": owner, "chapterTitle": chapter_title,
                          "ruleGroups": skeleton_groups,
                          "fullDefinitionRuleIds": [p["sourceRuleId"] for p in projections if p["primaryOwner"] == owner],
                          "shortReferenceRuleIds": [p["sourceRuleId"] for p in projections if owner in p["referenceOwners"]],
                          "missingLinkProjectionIds": [m["projectionId"] for m in missing_projections if m["primaryOwner"] == owner],
                          "parameterProjectionIds": [p["projectionId"] for p in parameter_projections if p["primaryOwner"] == owner],
                          "sourceChainIds": sorted(source_chain_ids)})

    core = {"loopId": CORE_OWNER, "title": "Core Gameplay Loop", "definitionMode": "overview_only",
            "steps": ["战斗", "成长", "三选一", "强化", "继续战斗", "胜负", "结算"],
            "sourceChainIds": [c["chainId"] for c in chains],
            "referenceProjectionIds": [p["projectionId"] for p in projections]}
    return {"coreGameplayLoop": core, "ruleProjections": projections,
            "missingLinkProjections": missing_projections, "parameterProjections": parameter_projections,
            "systemChapterSkeletons": skeletons}


def evaluate_projection_integrity(projection_set: dict[str, Any]) -> dict[str, Any]:
    projections = projection_set.get("ruleProjections", [])
    full_counts = Counter(p["sourceRuleId"] for p in projections if p["definitionMode"] == "full_definition")
    duplicate = sorted(rule_id for rule_id, count in full_counts.items() if count > 1)
    missing_owner = [m["projectionId"] for m in projection_set.get("missingLinkProjections", []) if not m.get("primaryOwner")]
    core_full = 1 if "fullRuleDefinitions" in projection_set.get("coreGameplayLoop", {}) else 0
    projected_chains = {cid for p in projections for cid in p.get("sourceChainIds", [])}
    expected_chains = set(projection_set.get("coreGameplayLoop", {}).get("sourceChainIds", []))
    untracked = sorted(expected_chains - projected_chains)
    findings = duplicate + missing_owner + (["core_loop_contains_full_definitions"] if core_full else []) + untracked
    return {"qualityGate": "pass" if not findings else "fail",
            "duplicateFullDefinitionCount": len(duplicate), "duplicateRuleIds": duplicate,
            "missingLinkWithoutOwnerCount": len(missing_owner), "coreLoopFullDefinitionCount": core_full,
            "untrackedSourceChainCount": len(untracked), "untrackedSourceChainIds": untracked,
            "ruleProjectionTraceabilityRate": 1.0 if all(p.get("sourceChainId") for p in projections) else 0.0,
            "findings": findings}
