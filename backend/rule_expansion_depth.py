from __future__ import annotations

import hashlib
from typing import Any, Mapping


ACTIVE_SCOPE = {"confirmed", "strongly_implied"}
IMPLEMENTATION_DIMENSIONS = {
    "multi_target_internal_sorting", "no_target_polling_frequency", "internal_damage_event",
    "same_frame_competition", "event_ordering", "cache", "input_vector_composition",
}
TARGET_DEPTH_BY_TOPIC = {
    "移动规则": "control_and_gameplay_speed",
    "获取与栏位": "acquisition_result_and_loadout_capacity",
    "攻击规则": "targeting_method_and_damage_parameters",
    "成长与词条": "confirmed_modifier_effects",
    "可获取词条": "candidate_eligibility",
    "触发与选择": "trigger_pause_choice_and_resume",
    "刷新": "availability_cost_and_candidate_replacement",
    "选择结果": "effect_specificity",
    "接触伤害": "contact_damage_mode",
    "关卡推进": "growth_trigger_and_time_boundary",
    "胜负衔接": "failure_condition_and_flow_transition",
    "结算结果": "settlement_result_content",
    "数据记录": "recorded_data_scope",
}


def _stable_id(layout_id: str, topic: str) -> str:
    value = hashlib.sha1(f"{layout_id}:{topic}".encode("utf-8")).hexdigest()[:12].upper()
    return f"EXP-{value}"


def _scope_index(scoped_models: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for model in scoped_models:
        items = model.get("mechanicScopes") or model.get("scopeItems", [])
        result[model["chapterId"]] = {
            item["scopeItem"]: item["existenceStatus"] for item in items
        }
    return result


def _rule_index(approved_rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {rule.get("ruleId") or rule.get("id"): rule for rule in approved_rules}


def _detail(rule_id: str, rule_map: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    rule = rule_map.get(rule_id, {})
    text = rule.get("text") or rule.get("behavior") or rule.get("statement") or rule_id
    return {"detailId": f"DETAIL:{rule_id}", "text": text, "sourceRuleIds": [rule_id],
            "evidenceStatus": "confirmed"}


def _missing(semantic: str, question: str, scope_status: str, impact: str,
             source_ids: list[str] | None = None) -> dict[str, Any]:
    return {"semantic": semantic, "question": question, "scopeStatus": scope_status,
            "detailKind": "game_rule", "gameplayImpact": impact, "sourceMissingIds": source_ids or []}


def _parameter(semantic: str, label: str, source_ids: list[str] | None = None,
               applicability: str = "active") -> dict[str, Any]:
    return {"semantic": semantic, "label": label, "sourceParameterCarrierIds": source_ids or [],
            "applicability": applicability}


def _stop(dimension: str, reason_type: str, reason: str, scope_status: str = "not_applicable") -> dict[str, Any]:
    return {"candidateDimension": dimension, "reasonType": reason_type, "reason": reason,
            "scopeStatus": scope_status}


def _base_plan(layout: dict[str, Any], rule_map: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    rule_ids = [*layout.get("supportingRuleIds", []), *layout.get("referenceRuleIds", [])]
    confirmed = [_detail(rule_id, rule_map) for rule_id in rule_ids if rule_id in rule_map]
    topic = layout["sectionTitle"]
    return {
        "expansionId": _stable_id(layout["layoutId"], topic), "layoutId": layout["layoutId"],
        "ownerChapter": layout["ownerChapter"], "ruleTopic": topic,
        "currentKnownDepth": {"confirmedDetailCount": len(confirmed),
                              "missingDetailCount": len(layout.get("missingRuleIds", [])),
                              "parameterCarrierCount": len(layout.get("parameterCarrierIds", []))},
        "targetDepth": TARGET_DEPTH_BY_TOPIC.get(topic, "current_confirmed_game_rule_depth"),
        "confirmedDetails": confirmed,
        "missingExecutionDetails": [], "gameplayParameters": [], "stopReasons": [],
        "gvePatternBasis": [{"source": layout.get("layoutPatternSource", "GVE16/ANON"),
                             "dimension": "execution_granularity", "contentAuthority": "none"}],
        "depthVerdict": "appropriate", "depthStatus": "appropriate",
    }


def calibrate_rule_expansion_depth(layouts: list[dict[str, Any]], projections: Any,
                                   groups: list[dict[str, Any]], chains: list[dict[str, Any]],
                                   scoped_models: list[dict[str, Any]], approved_rules: list[dict[str, Any]],
                                   corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Calibrate execution depth without creating scope, rules, gaps, values, or prose."""
    scopes = _scope_index(scoped_models)
    rules = _rule_index(approved_rules)
    plans: list[dict[str, Any]] = []
    for layout in layouts:
        plan = _base_plan(layout, rules)
        topic = plan["ruleTopic"]
        scope = scopes.get(plan["ownerChapter"], {})
        missing_ids = layout.get("missingRuleIds", [])
        param_ids = layout.get("parameterCarrierIds", [])

        if topic == "移动规则":
            plan["gameplayParameters"] = [_parameter("movement_speed", "移动速度", param_ids)]
            plan["stopReasons"] += [
                _stop("input_vector_composition", "implementation_only", "输入向量合成属于内部实现。"),
                _stop("movement_path", "scope_not_active", "当前上游证据未确认自动沿预设路线移动。",
                      scope.get("movement_action", "contradicted")),
            ]
            plan["depthVerdict"] = "under-expanded"

        elif topic == "获取与栏位":
            if scope.get("loadout_capacity") in ACTIVE_SCOPE:
                plan["missingExecutionDetails"] = [_missing(
                    "loadout_capacity", "武器栏可以容纳多少个武器或技能？",
                    scope["loadout_capacity"], "改变玩家可持有内容和战斗构筑", missing_ids)]
            for dimension in ("unlock", "duplicate_acquisition", "replacement"):
                status = scope.get(dimension, "unsupported")
                if status not in ACTIVE_SCOPE:
                    plan["stopReasons"].append(_stop(dimension, "scope_not_active",
                        "当前证据未证明该获取或栏位规则存在。", status))
            plan["depthVerdict"] = "under-expanded" if plan["missingExecutionDetails"] else "appropriate"

        elif topic == "攻击规则":
            plan["gameplayParameters"] = [
                _parameter("attack_range", "攻击范围", param_ids),
                _parameter("attack_interval", "攻击间隔", param_ids),
                _parameter("damage", "伤害值或公式", param_ids),
            ]
            plan["missingExecutionDetails"] = [
                _missing("damage_resolution", "武器攻击造成的伤害值或计算公式是什么？",
                         scope.get("attack_method", "confirmed"), "改变战斗数值结果", missing_ids)
            ]
            plan["stopReasons"] += [
                _stop("multi_target_internal_sorting", "implementation_only", "同优先级目标的内部排序不改变已确认玩法规则。"),
                _stop("no_target_polling_frequency", "implementation_only", "无目标检测频率属于内部轮询。"),
                _stop("internal_damage_event", "implementation_only", "内部伤害事件不属于玩法执行颗粒度。"),
            ]
            plan["depthVerdict"] = "under-expanded"

        elif topic == "可获取词条":
            plan["missingExecutionDetails"] = [
                _missing("candidate_eligibility", "哪些内容有资格进入本轮三选一？",
                         scope.get("candidate_scope", "unsupported"), "改变随机结果", missing_ids)
            ]
            for dimension in ("prerequisite", "max_level", "duplicate", "weight"):
                status = scope.get(dimension, "unsupported")
                if status not in ACTIVE_SCOPE:
                    plan["stopReasons"].append(_stop(dimension, "scope_not_active",
                        "当前证据尚未证明该随机维度存在，不按 GVE16 模板实例化。", status))
            plan["depthVerdict"] = "under-expanded"

        elif topic == "触发与选择":
            plan["missingExecutionDetails"] = [
                _missing("resume_combat", "完成选择后，战斗在什么时点恢复？", "confirmed",
                         "改变暂停状态与后续玩法衔接", missing_ids)
            ]
            plan["stopReasons"].append(_stop("same_frame_competition", "implementation_only",
                                              "刷新与选择的同帧竞争属于内部事件处理。"))
            plan["depthVerdict"] = "under-expanded"

        elif topic == "刷新":
            # Existing carriers are preserved; no value or contract is invented here.
            if param_ids:
                plan["gameplayParameters"].append(_parameter("refresh_cost", "刷新消耗", param_ids))
            refresh_count_status = scope.get("refresh_count", "unsupported")
            if refresh_count_status in ACTIVE_SCOPE:
                plan["gameplayParameters"].append(_parameter("refresh_count", "刷新次数", param_ids))
            else:
                plan["stopReasons"].append(_stop("refresh_count", "scope_not_active",
                    "刷新存在，但当前证据尚未证明次数限制存在。", refresh_count_status))
            if scope.get("refresh_cost") in ACTIVE_SCOPE:
                plan["missingExecutionDetails"].append(_missing(
                    "refresh_cost_or_condition", "刷新需要消耗什么，或满足什么条件时可以使用？",
                    scope["refresh_cost"], "改变资源消耗和刷新可用条件", []))
            plan["stopReasons"].append(_stop(
                "payment_timing", "decision_not_gameplay_material",
                "当前没有证据表明扣除时点会改变玩家可感知结果或资源规则，因此不默认提升。",
                "not_elevated"))
            plan["depthVerdict"] = "under-expanded"

        elif topic == "选择结果":
            existing_ids = {rule_id for detail in plan["confirmedDetails"] for rule_id in detail["sourceRuleIds"]}
            for rule_id, rule in rules.items():
                behavior = rule.get("behavior") or rule.get("text") or ""
                is_choice_effect = rule.get("schemaSlot") in {"candidate_effect", "effect_parameter"}
                is_affix_attack_change = (rule.get("schemaSlot") == "content_catalog_definition"
                                          and "词条" in behavior and "攻击" in behavior)
                if rule_id not in existing_ids and (is_choice_effect or is_affix_attack_change):
                    plan["confirmedDetails"].append(_detail(rule_id, rules))
            plan["depthVerdict"] = "appropriate" if plan["confirmedDetails"] else "under-expanded"

        elif topic == "接触伤害":
            damage_mode = scope.get("damage_mode", "unsupported")
            if damage_mode in ACTIVE_SCOPE:
                plan["missingExecutionDetails"] = [_missing(
                    "contact_damage_mode", "怪物接触载具时，伤害是只结算一次还是持续结算？",
                    damage_mode, "改变载具受到的伤害结果", missing_ids)]
            sustained = scope.get("sustained_contact_damage", "unsupported")
            if sustained not in ACTIVE_SCOPE:
                plan["stopReasons"].append(_stop("contact_damage_interval", "conditional_scope_inactive",
                    "只有持续接触伤害被确认后，才需要定义伤害间隔。", sustained))
            plan["depthVerdict"] = "under-expanded" if plan["missingExecutionDetails"] else "appropriate"

        elif topic == "关卡推进":
            if scope.get("player_level_up") in ACTIVE_SCOPE:
                plan["missingExecutionDetails"].append(_missing(
                    "growth_accumulation", "关卡内成长如何累计并达到升级条件？",
                    scope["player_level_up"], "改变成长节奏与三选一触发", missing_ids))
            if scope.get("time_limit") in ACTIVE_SCOPE:
                plan["missingExecutionDetails"].append(_missing(
                    "time_limit", "关卡时限是多少？", scope["time_limit"], "改变关卡结束边界", missing_ids))
                plan["gameplayParameters"].append(_parameter("time_limit", "关卡时限"))
            for dimension, scope_key in (("victory", "victory"), ("wave", "stage_or_wave"),
                                         ("reward", "reward_basis")):
                status = scope.get(scope_key, "unsupported")
                if status not in ACTIVE_SCOPE:
                    plan["stopReasons"].append(_stop(dimension, "scope_not_active",
                        "当前证据尚未证明该关卡子机制存在。", status))
            plan["depthVerdict"] = "under-expanded"

        elif topic == "胜负衔接":
            if scope.get("failure") in ACTIVE_SCOPE:
                plan["missingExecutionDetails"] = [_missing(
                    "failure_result", "触发失败后，关卡进入什么结束或结算状态？",
                    scope["failure"], "改变关卡状态与后续流程", missing_ids)]
            victory_status = scope.get("victory", "unsupported")
            if victory_status not in ACTIVE_SCOPE:
                plan["stopReasons"].append(_stop("victory", "scope_not_active",
                    "当前证据只确认失败条件，未证明胜利规则。", victory_status))
            plan["depthVerdict"] = "under-expanded" if plan["missingExecutionDetails"] else "appropriate"

        elif topic == "结算结果":
            displayed = scope.get("displayed_data", "unsupported")
            if displayed in ACTIVE_SCOPE:
                plan["missingExecutionDetails"] = [_missing(
                    "displayed_data", "结算时需要展示哪些已产生的战斗结果数据？",
                    displayed, "改变玩家看到的结算结果", missing_ids)]
            for dimension in ("reward_calculation", "progress_settlement"):
                status = scope.get(dimension, "unsupported")
                if status not in ACTIVE_SCOPE:
                    plan["stopReasons"].append(_stop(dimension, "scope_not_active",
                        "当前证据未证明该结算子机制存在。", status))
            plan["depthVerdict"] = "under-expanded" if plan["missingExecutionDetails"] else "appropriate"

        elif topic == "数据记录":
            recorded = scope.get("recorded_data", "unsupported")
            if recorded in ACTIVE_SCOPE:
                plan["missingExecutionDetails"] = [_missing(
                    "recorded_data", "结算后需要保存哪些已确认存在的战斗结果数据？",
                    recorded, "改变跨局记录结果", missing_ids)]
            clear_status = scope.get("run_data_clear", "unsupported")
            if clear_status not in ACTIVE_SCOPE:
                plan["stopReasons"].append(_stop("run_data_clear", "scope_not_active",
                    "当前证据未证明局内数据清理规则存在。", clear_status))
            plan["depthVerdict"] = "under-expanded" if plan["missingExecutionDetails"] else "appropriate"

        plan["depthStatus"] = plan["depthVerdict"]
        plans.append(plan)
    return plans


def evaluate_expansion_stop_gate(plans: list[dict[str, Any]], scopes: list[dict[str, Any]]) -> dict[str, Any]:
    scope_violations = []
    implementation_leaks = []
    ungrounded = []
    for plan in plans:
        for detail in plan.get("missingExecutionDetails", []):
            if detail.get("scopeStatus") not in ACTIVE_SCOPE:
                scope_violations.append(f"{plan['expansionId']}:{detail.get('semantic')}")
            if detail.get("detailKind") == "implementation" or detail.get("semantic") in IMPLEMENTATION_DIMENSIONS:
                implementation_leaks.append(f"{plan['expansionId']}:{detail.get('semantic')}")
            if not detail.get("gameplayImpact"):
                ungrounded.append(f"{plan['expansionId']}:{detail.get('semantic')}")
    findings = scope_violations + implementation_leaks + ungrounded
    appropriate = sum(plan.get("depthStatus", plan.get("depthVerdict")) == "appropriate" for plan in plans)
    under = sum(plan.get("depthStatus", plan.get("depthVerdict")) == "under-expanded" for plan in plans)
    over = sum(plan.get("depthStatus", plan.get("depthVerdict")) == "over-expanded" for plan in plans)
    required_missing = [{"expansionId": plan["expansionId"], "ruleTopic": plan.get("ruleTopic"), **detail}
                        for plan in plans for detail in plan.get("missingExecutionDetails", [])]
    low_value = [{"expansionId": plan["expansionId"], "ruleTopic": plan.get("ruleTopic"), **item}
                 for plan in plans for item in plan.get("stopReasons", [])
                 if item.get("reasonType") in {"implementation_only", "decision_not_gameplay_material"}]
    return {"qualityGate": "pass" if not findings else "fail",
            "planCount": len(plans), "totalLayouts": len(plans), "appropriate": appropriate,
            "underExpanded": under, "overExpanded": over,
            "scopeViolationCount": len(scope_violations),
            "implementationLeakCount": len(implementation_leaks),
            "missingGameplayImpactCount": len(ungrounded),
            "gve16RequiredMissingExecutionRules": required_missing,
            "lowValueDetailsStopped": low_value, "findings": findings}
