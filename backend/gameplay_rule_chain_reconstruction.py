from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

from backend.mechanic_requirement_discovery import reassess_requirement


INTERNAL_TERMS = {"breakpoint", "node", "edge", "contract", "pipeline", "atomic", "event_ordering", "target_set"}


def reassess_chain_requirements(
    requirements: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Close only requirements explicitly satisfied by valid rules at the same dimension."""
    return [reassess_requirement(requirement, rules) for requirement in requirements]


def attach_approved_requirement_rules(
    chains: list[dict[str, Any]],
    approved_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach already-approved business rules without reconstructing their content."""
    result = deepcopy(chains)
    valid = [rule for rule in approved_rules if rule.get("valid") is True]

    def rules_for(prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
        return [rule for rule in valid
                if any(dimension.startswith(prefixes) for dimension in rule.get("dimensionIds", []))]

    statistics = rules_for(("statistics.",))
    if statistics:
        mechanic_ids = sorted({mid for rule in statistics
                               for mid in ([rule.get("mechanicId")] + rule.get("satisfiesMechanicIds", [])) if mid})
        result.append({
            "chainId": _chain_id("damage_statistics_business_contract", mechanic_ids),
            "chainType": "damage_statistics",
            "mechanicId": statistics[0]["mechanicId"],
            "mechanicIds": mechanic_ids,
            "title": "伤害统计",
            "entry": None,
            "playerAction": [],
            "systemResponse": [
                _step(rule["text"], [rule], [], "statistics_business_rule") for rule in statistics
            ],
            "stateChange": [], "progressionResult": [], "exitOrNext": [],
            "supportingRuleIds": [rule["ruleId"] for rule in statistics],
            "missingLinks": [], "gameplayParameters": [],
            "relationTypes": ["attribution", "aggregation"],
            "sourceRequirementIds": sorted({rid for rule in statistics
                                             for rid in rule.get("originRequirementIds", [])}),
        })

    stage_rules = [rule for rule in valid if any(
        dimension in {"stage.completion_after_boss", "battle.next_state", "outcome.success_trigger", "settlement.entry"}
        for dimension in rule.get("dimensionIds", [])
    )]
    if stage_rules:
        cleanup = [rule for rule in stage_rules if "stage.completion_after_boss" in rule.get("dimensionIds", [])]
        outcome = [rule for rule in stage_rules if set(rule.get("dimensionIds", [])) & {
            "battle.next_state", "outcome.success_trigger", "settlement.entry"
        }]
        mechanic_ids = sorted({mid for rule in stage_rules
                               for mid in ([rule.get("mechanicId")] + rule.get("satisfiesMechanicIds", [])) if mid})
        result.append({
            "chainId": _chain_id("boss_completion_settlement", mechanic_ids),
            "chainType": "boss_completion_settlement",
            "mechanicId": mechanic_ids[0], "mechanicIds": mechanic_ids,
            "title": "Boss 击败、关卡完成与结算",
            "entry": None, "playerAction": [],
            "systemResponse": [_step(rule["text"], [rule], [], "post_boss_cleanup") for rule in cleanup],
            "stateChange": [], "progressionResult": [],
            "exitOrNext": [_step(rule["text"], [rule], [], "enter_success_settlement") for rule in outcome],
            "supportingRuleIds": [rule["ruleId"] for rule in stage_rules],
            "missingLinks": [], "gameplayParameters": [],
            "relationTypes": ["sequence", "state_transition"],
            "sourceRequirementIds": sorted({rid for rule in stage_rules
                                             for rid in rule.get("originRequirementIds", [])}),
        })

    attached_rule_ids = {
        rule_id for chain in result for rule_id in chain.get("supportingRuleIds", [])
    }
    remaining_by_mechanic: dict[str, list[dict[str, Any]]] = {}
    for rule in valid:
        if rule.get("ruleId") not in attached_rule_ids:
            remaining_by_mechanic.setdefault(rule.get("mechanicId", ""), []).append(rule)
    for mechanic_id, rules in remaining_by_mechanic.items():
        if not mechanic_id:
            continue
        steps = [_step(rule["text"], [rule], [], rule.get("dimensionIds", ["approved_rule"])[0])
                 for rule in rules]
        owner_paths = [rule.get("planningOwnerPath", []) for rule in rules if rule.get("planningOwnerPath")]
        result.append({
            "chainId": _chain_id("approved_mechanic", [mechanic_id]),
            "chainType": "approved_mechanic",
            "mechanicId": mechanic_id,
            "mechanicIds": [mechanic_id],
            "title": owner_paths[0][-1] if owner_paths else "已批准机制执行链",
            "entry": steps[0] if steps else None,
            "playerAction": [],
            "systemResponse": steps[1:-1] if len(steps) > 2 else [],
            "stateChange": [],
            "progressionResult": [],
            "exitOrNext": steps[-1:] if len(steps) > 1 else [],
            "supportingRuleIds": [rule["ruleId"] for rule in rules],
            "missingLinks": [],
            "gameplayParameters": [],
            "relationTypes": ["sequence"] + (["state_transition"] if len(rules) > 1 else []),
            "sourceRequirementIds": sorted({rid for rule in rules
                                             for rid in rule.get("originRequirementIds", [])}),
        })
    return result


def _chain_id(chain_type: str, mechanic_ids: list[str]) -> str:
    raw = f"{chain_type}:{':'.join(mechanic_ids)}"
    return "CHAIN-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def _step(text: str, rules: list[dict[str, Any]], groups: list[dict[str, Any]], semantic: str) -> dict[str, Any]:
    return {"semantic": semantic, "text": text, "ruleIds": [r["ruleId"] for r in rules],
            "sourceGroupIds": sorted({g["groupId"] for g in groups})}


def _rules(groups: list[dict[str, Any]], *slots: str) -> list[dict[str, Any]]:
    wanted = set(slots)
    return [rule for group in groups for rule in group.get("knownRules", []) if rule.get("schemaSlot") in wanted]


def _unique_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list({rule["ruleId"]: rule for rule in rules}.values())


def _attack_parts(groups: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = _rules(groups, "attack_target", "attack_method")
    target = [rule for rule in candidates if "选择" in str(rule.get("text"))
              and any(noun in str(rule.get("text")) for noun in ("目标", "敌人", "怪物"))]
    processing = [rule for rule in candidates if rule["ruleId"] not in {item["ruleId"] for item in target}]
    return _unique_rules(target), _unique_rules(processing)


def _groups_for(all_groups: list[dict[str, Any]], mechanic_id: str) -> list[dict[str, Any]]:
    return [group for group in all_groups if group["mechanicId"] == mechanic_id]


def _missing(groups: list[dict[str, Any]], semantic: str, question: str, after: str) -> dict[str, Any] | None:
    matches = [item for group in groups for item in group.get("missingRules", []) if item.get("semantic") == semantic]
    if not matches:
        return None
    return {"semanticKey": semantic, "question": question, "afterStep": after,
            "supportingGapIds": [item["sourceId"] for item in matches]}


def _parameters(groups: list[dict[str, Any]], attachment: dict[str, str]) -> list[dict[str, Any]]:
    result = []
    for group in groups:
        for parameter in group.get("gameplayParameters", []):
            semantic = parameter.get("semantic")
            result.append({**parameter, "attachedTo": attachment.get(semantic, group["title"]),
                           "sourceGroupId": group["groupId"]})
    return result


def _three_choice(groups: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    trigger = _rules(groups, "random_trigger")
    pause = _rules(groups, "selection_pause")
    select = _rules(groups, "candidate_selection")
    refresh = _rules(groups, "refresh_rule")
    refresh_cost = _rules(groups, "refresh_cost")
    refresh_action, refresh_result = refresh[:1], refresh[1:]
    effects = _rules(groups, "candidate_effect", "effect_parameter")
    missing = []
    candidate_gap = _missing(groups, "candidate_filter", "目前还不知道哪些词条有资格出现在三选一里。", "生成候选前")
    if candidate_gap:
        missing.append(candidate_gap)
    if pause and select:
        missing.append({"semanticKey": "resume_combat", "question": "目前还不知道玩家完成选择后何时恢复战斗。",
                        "afterStep": "选择结果", "supportingGapIds": []})
    chain_rules = trigger + pause + select + refresh + refresh_cost + effects
    return {"chainId": _chain_id("three_choice_core", [model["mechanicId"]]), "chainType": "three_choice_core",
            "mechanicId": model["mechanicId"], "mechanicIds": [model["mechanicId"]], "title": "三选一核心玩法",
            "entry": _step("升级触发三选一", trigger, groups, "upgrade_trigger") if trigger else None,
            "playerAction": [item for item in (
                _step("选择一项候选", select, groups, "select_candidate") if select else None,
                _step("刷新当前候选", refresh_action, groups, "refresh_candidates") if refresh_action else None) if item],
            "systemResponse": [item for item in (
                _step("暂停当前战斗", pause, groups, "pause_combat") if pause else None,
                _step("生成三张候选", trigger, groups, "generate_candidates") if trigger else None,
                _step("刷新存在消耗或替代条件", refresh_cost, groups, "refresh_requirement") if refresh_cost else None,
                _step("替换当前候选", refresh_result, groups, "replace_candidates") if refresh_result else None) if item],
            "stateChange": [],
            "progressionResult": [_step("所选内容改变武器效果", effects, groups, "apply_selected_effect")] if effects else [],
            "exitOrNext": [], "supportingRuleIds": [r["ruleId"] for r in chain_rules], "missingLinks": missing,
            "gameplayParameters": _parameters(groups, {"refresh_count": "刷新", "refresh_cost_contract": "刷新"})}


def _weapon(groups: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    acquire = _rules(groups, "acquisition_rule", "random_trigger")
    targeting_mode = _rules(groups, "attack_trigger")
    target, attack = _attack_parts(groups)
    effects = _rules(groups, "candidate_effect", "effect_parameter", "content_catalog_definition")
    missing = []
    loadout = _missing(groups, "loadout_capacity", "目前还不知道获得武器后可使用的武器栏数量。", "获得武器后")
    if loadout:
        missing.append(loadout)
    if attack and any(p.get("semantic") == "damage_output" for g in groups for p in g.get("gameplayParameters", [])):
        missing.append({"semanticKey": "damage_resolution", "question": "目前还不知道武器攻击命中后如何结算伤害。",
                        "afterStep": "发动攻击", "supportingGapIds": []})
    chain_rules = acquire + targeting_mode + target + attack + effects
    responses = []
    if targeting_mode:
        responses.append(_step("进入自动攻击模式", targeting_mode, groups, "automatic_targeting_mode"))
    if target:
        responses.append(_step("选择射程内目标", target, groups, "select_target"))
    if attack:
        responses.append(_step("执行武器攻击", attack, groups, "execute_attack"))
    return {"chainId": _chain_id("weapon_acquire_attack_upgrade", [model["mechanicId"]]),
            "chainType": "weapon_acquire_attack_upgrade", "mechanicId": model["mechanicId"],
            "mechanicIds": [model["mechanicId"]], "title": "武器获得、攻击与强化",
            "entry": _step("获得武器", acquire, groups, "acquire_weapon") if acquire else None,
            "playerAction": [], "systemResponse": responses, "stateChange": [],
            "progressionResult": [_step("词条改变攻击方式或攻击参数", effects, groups, "apply_weapon_modifier")] if effects else [],
            "exitOrNext": [], "supportingRuleIds": [r["ruleId"] for r in chain_rules], "missingLinks": missing,
            "gameplayParameters": _parameters(groups, {"attack_entry": "自动攻击", "next_attack_trigger": "自动攻击", "damage_output": "自动攻击"})}


def _monster(groups: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    movement = _rules(groups, "movement_trigger", "movement_control")
    contact = _rules(groups, "attack_trigger", "contact_damage")
    supporting = _unique_rules(movement + contact)
    return {
        "chainId": _chain_id("monster_movement_contact", [model["mechanicId"]]),
        "chainType": "monster_movement_contact", "mechanicId": model["mechanicId"],
        "mechanicIds": [model["mechanicId"]], "title": "怪物移动与接触伤害",
        "entry": _step("怪物进入战区并开始移动", movement, groups, "enter_and_move") if movement else None,
        "playerAction": [],
        "systemResponse": [_step("接触载具后造成伤害", contact, groups, "contact_damage")] if contact else [],
        "stateChange": [], "progressionResult": [], "exitOrNext": [],
        "supportingRuleIds": [rule["ruleId"] for rule in supporting], "missingLinks": [],
        "gameplayParameters": _parameters(groups, {}),
        "relationTypes": [value for value, present in (
            ("sequence", bool(movement and contact)), ("state_transition", bool(movement and contact))) if present],
    }


def _settlement_chains(groups: list[dict[str, Any]], model: dict[str, Any]) -> list[dict[str, Any]]:
    total = _rules(groups, "statistics_total", "damage_statistics")
    attribution = _rules(groups, "statistics_attribution", "damage_attribution")
    formula_gap = _missing(groups, "damage_share_formula", "目前还不知道武器伤害占比如何计算。", "伤害归属后")
    statistics_rules = _unique_rules(total + attribution)
    statistics = {
        "chainId": _chain_id("damage_statistics", [model["mechanicId"]]),
        "chainType": "damage_statistics", "mechanicId": model["mechanicId"],
        "mechanicIds": [model["mechanicId"]], "title": "伤害统计",
        "entry": None, "playerAction": [],
        "systemResponse": [item for item in (
            _step("累计本局伤害", total, groups, "aggregate_damage") if total else None,
            _step("按武器归属伤害", attribution, groups, "attribute_damage") if attribution else None,
        ) if item],
        "stateChange": [], "progressionResult": [], "exitOrNext": [],
        "supportingRuleIds": [rule["ruleId"] for rule in statistics_rules],
        "missingLinks": [formula_gap] if formula_gap else [],
        "gameplayParameters": _parameters(groups, {}),
        "relationTypes": ["sequence", "attribution"] if total and attribution else [],
    }
    failure = _rules(groups, "failure_condition", "victory_condition", "success_condition")
    result = _rules(groups, "settlement_result", "reward_rule", "displayed_data")
    outcome_rules = _unique_rules(failure + result)
    outcome = {
        "chainId": _chain_id("outcome_settlement", [model["mechanicId"]]),
        "chainType": "outcome_settlement", "mechanicId": model["mechanicId"],
        "mechanicIds": [model["mechanicId"]], "title": "胜负与结算",
        "entry": _step("满足关卡结束条件", failure, groups, "battle_end_condition") if failure else None,
        "playerAction": [], "systemResponse": [], "stateChange": [], "progressionResult": [],
        "exitOrNext": [_step("进入结算并展示结果", result, groups, "publish_settlement_result")] if result else [],
        "supportingRuleIds": [rule["ruleId"] for rule in outcome_rules], "missingLinks": [],
        "gameplayParameters": _parameters(groups, {}),
        "relationTypes": ["sequence", "state_transition"] if failure and result else [],
    }
    return [chain for chain in (statistics, outcome) if chain["supportingRuleIds"]]


def _cross_system(all_groups: list[dict[str, Any]], models: list[dict[str, Any]]) -> dict[str, Any] | None:
    types = {m["mechanicType"]: m for m in models}
    if "level_flow" not in types:
        return None
    selected_types = ("movement", "monster_attack", "randomization", "attack", "level_flow", "settlement")
    selected_models = [types[t] for t in selected_types if t in types]
    mechanic_ids = [m["mechanicId"] for m in selected_models]
    groups = [g for g in all_groups if g["mechanicId"] in mechanic_ids]
    movement_groups = _groups_for(groups, types["movement"]["mechanicId"]) if "movement" in types else []
    monster_groups = _groups_for(groups, types["monster_attack"]["mechanicId"]) if "monster_attack" in types else []
    weapon_groups = _groups_for(groups, types["attack"]["mechanicId"]) if "attack" in types else []
    random_groups = _groups_for(groups, types["randomization"]["mechanicId"]) if "randomization" in types else []
    weapon_target, weapon_processing = _attack_parts(weapon_groups)
    weapon_mode = _rules(weapon_groups, "attack_trigger")
    monster_combat = _rules(monster_groups, "attack_trigger", "attack_method")
    combat = _unique_rules(weapon_mode + weapon_target + weapon_processing + monster_combat)
    failure = _rules(groups, "failure_condition")
    random_trigger = _rules(random_groups, "random_trigger")
    progression = _unique_rules(_rules(random_groups + weapon_groups, "candidate_effect", "effect_parameter"))
    movement = _rules(movement_groups, "movement_control", "movement_trigger")
    missing = []
    level_groups = _groups_for(groups, types["level_flow"]["mechanicId"])
    level_up = _missing(level_groups, "player_level_up", "目前还不知道关卡内经验如何累计并触发升级。", "战斗成长")
    if level_up:
        missing.append(level_up)
    if not any(r.get("schemaSlot") == "victory_condition" for r in failure):
        missing.append({"semanticKey": "victory_path", "question": "当前证据尚未确认关卡如何达成胜利并进入结算。",
                        "afterStep": "持续战斗", "supportingGapIds": []})
    if "settlement" in types:
        settle_groups = _groups_for(groups, types["settlement"]["mechanicId"])
        displayed = _missing(settle_groups, "displayed_data", "目前还不知道结算时需要展示哪些战斗结果。", "关卡结束后")
        if displayed:
            missing.append(displayed)
    supporting = movement + combat + random_trigger + progression + failure
    system_response = []
    if movement:
        system_response.append(_step("玩家横向控制载具", movement, movement_groups, "vehicle_control"))
    if weapon_mode or weapon_target or weapon_processing:
        system_response.append(_step("武器自动选择目标并执行攻击", _unique_rules(weapon_mode + weapon_target + weapon_processing),
                                     weapon_groups, "weapon_combat"))
    if monster_combat:
        system_response.append(_step("怪物接触载具后造成伤害", monster_combat, monster_groups, "monster_contact_damage"))
    if random_trigger:
        system_response.append(_step("升级触发三选一", random_trigger, random_groups, "enter_three_choice"))
    return {"chainId": _chain_id("level_combat_growth_settlement", mechanic_ids),
            "chainType": "level_combat_growth_settlement", "mechanicId": "CROSS-SYSTEM", "mechanicIds": mechanic_ids,
            "title": "关卡战斗、成长与结算", "entry": None, "playerAction": [], "systemResponse": system_response,
            "stateChange": [], "progressionResult": [_step("选择结果改变武器效果", progression, groups, "apply_growth")]
            if progression else [], "exitOrNext": [_step("载具生命归零后进入失败流程", failure, groups, "failure_exit")]
            if failure else [], "supportingRuleIds": [r["ruleId"] for r in supporting], "missingLinks": missing,
            "gameplayParameters": _parameters(groups, {})}


def reconstruct_gameplay_rule_chains(game_rule_groups: list[dict[str, Any]], scoped_models: list[dict[str, Any]],
                                     entity_graph: dict[str, Any]) -> list[dict[str, Any]]:
    del entity_graph  # Entity relationships are already projected as relatedSystems on the groups.
    chains = []
    for model in scoped_models:
        groups = _groups_for(game_rule_groups, model["mechanicId"])
        if model["mechanicType"] == "randomization" and groups:
            chains.append(_three_choice(groups, model))
        elif model["mechanicType"] == "attack" and groups:
            chains.append(_weapon(groups, model))
        elif model["mechanicType"] == "monster_attack" and groups:
            chains.append(_monster(groups, model))
        elif model["mechanicType"] == "settlement" and groups:
            chains.extend(_settlement_chains(groups, model))
    cross = _cross_system(game_rule_groups, scoped_models)
    if cross:
        chains.append(cross)
    return chains


def evaluate_chain_coherence(chains: list[dict[str, Any]], game_rule_groups: list[dict[str, Any]]) -> dict[str, Any]:
    group_rules = {r["ruleId"] for g in game_rule_groups for r in g.get("knownRules", [])}
    chain_rules = {rid for chain in chains for rid in chain.get("supportingRuleIds", [])}
    uncovered = sorted(group_rules - chain_rules)
    implementation = []
    unreadable = []
    classification_only = []
    for chain in chains:
        human_text = " ".join([str(chain.get("title", "")), str(chain.get("entry", {}).get("text", "") if chain.get("entry") else "")]
                              + [step.get("text", "") for field in ("playerAction", "systemResponse", "stateChange", "progressionResult", "exitOrNext")
                                 for step in chain.get(field, [])]
                              + [link.get("question", "") for link in chain.get("missingLinks", [])]).lower()
        if any(term in human_text for term in INTERNAL_TERMS):
            implementation.append(chain["chainId"])
        if not any((chain.get("playerAction"), chain.get("systemResponse"), chain.get("progressionResult"), chain.get("exitOrNext"))):
            classification_only.append(chain["chainId"])
        for link in chain.get("missingLinks", []):
            question = link.get("question", "")
            if not question.startswith(("目前", "当前")) or any(term in question.lower() for term in INTERNAL_TERMS):
                unreadable.append(link.get("semanticKey"))
    # A rule may belong to a non-core group outside the three requested chains; report it without failing this scoped audit.
    hard_findings = implementation + unreadable + classification_only
    return {"qualityGate": "pass" if not hard_findings else "fail", "chainCount": len(chains),
            "classificationOnlyChainCount": len(classification_only), "uncoveredKnownRuleIds": uncovered,
            "knownRulePlacementRate": round((len(group_rules) - len(uncovered)) / len(group_rules), 4) if group_rules else 1.0,
            "implementationDetailPollutionCount": len(set(implementation)),
            "unreadableMissingLinkCount": len(set(unreadable)),
            "crossSystemChainCount": sum(len(c.get("mechanicIds", [])) > 1 for c in chains),
            "findings": sorted(set(hard_findings))}
