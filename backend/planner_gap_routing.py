from __future__ import annotations

from copy import deepcopy
from typing import Any


DISPOSITIONS = (
    "real_design_decision", "parameter_need", "entity_attribute", "implementation_default",
    "visual_detail", "already_answered_by_evidence", "upstream_conflict", "defer",
)

PARAMETER_CONTRACTS = {
    "movement_speed": "Vehicle.movementSpeed + unit",
    "next_attack_trigger": "Weapon.attackInterval / cooldown",
    "attack_entry": "Weapon.attackRange + distanceOrigin",
    "damage_output": "Weapon.damageFormulaRef + damageTarget",
    "candidate_weight_contract": "CandidateItem.weight",
    "refresh_count": "Randomization.refreshCount",
    "refresh_cost_contract": "Randomization.refreshCost + paymentTiming",
    "contact_damage_interval": "Monster.contactDamageInterval",
}
ENTITY_CONTRACTS = {
    "attack_method_selection": "Weapon.attackType",
    "candidate_set": "CandidateSet.source",
}
IMPLEMENTATION_DEFAULTS = {
    "movement_input_composition": "正交输入同时生效；没有反例证据时无需策划定义内部向量合成。",
    "movement_input_release": "输入停止后不再产生该输入对应的变化；默认行为不写成确认规则。",
    "target_priority": "普通自动索敌采用稳定实现排序即可；当前没有特殊索敌或策略证据。",
    "empty_target_behavior": "无目标时不攻击并等待后续检测；该默认仅用于抑制问题。",
    "exit_condition": "目标失效后终止对该目标的处理并继续常规检测；没有特殊玩法证据。",
    "selection_commit": "单次点击单次响应属于交互防重的自然实现。",
    "refresh_selection_exclusion": "当前没有真实并发交互风险证据，不为理论同帧竞态发问。",
    "contact_damage_aggregation": "各攻击来源按各自命中处理属于自然对象语义；没有合并伤害证据。",
}
ALREADY_ANSWERED = {"refresh_candidate_pipeline": "现有刷新 Rule 已说明刷新会替换当前候选，不再重复提问。"}
DEFERRED = {
    "contact_damage_interval": "先确认接触伤害是单次还是持续，间隔参数才适用。",
    "contact_exit_condition": "先确认是否存在持续接触伤害，脱离后的停止处理才适用。",
}
HIGH_SALIENCE = {
    "candidate_filter", "candidate_constraints", "empty_candidate", "candidate_shortage_behavior",
    "selection_state_exit", "contact_damage_processing",
}


def _grounded(candidate_gap: dict[str, Any], graph: dict[str, Any]) -> bool:
    grounded = {node.get("nodeId") for node in graph.get("nodes", []) if node.get("status") in {"confirmed", "derived_structure"}}
    sources = set(candidate_gap.get("sourceNodeIds", []))
    return bool(sources) and sources <= grounded


def route_gap_for_planner_significance(candidate_gap: dict[str, Any], grounded_graph: dict[str, Any],
                                        approved_rules: list[dict[str, Any]], evidence: Any) -> dict[str, Any]:
    del approved_rules
    gap = deepcopy(candidate_gap)
    semantic = gap.get("missingNodeSemantic")
    disposition, target, salience, reason, contract = "defer", "Deferred", "none", "缺少足够依据进行稳定分流。", None
    route_audit = evidence if isinstance(evidence, dict) else {}
    route_conflict = route_audit.get("movementRouteRule", {}).get("status") == "conflict"

    if not _grounded(gap, grounded_graph):
        reason = "候选未绑定 grounded graph breakpoint，不能升级为策划决策。"
    elif semantic in {"movement_path_contract", "movement_stop"} and route_conflict:
        disposition, target, salience = "upstream_conflict", "Rule Review", "high"
        reason = route_audit["movementRouteRule"].get("reason", "移动前提存在上游证据冲突。")
    elif semantic in DEFERRED:
        disposition, target, reason = "defer", "Deferred", DEFERRED[semantic]
    elif semantic in PARAMETER_CONTRACTS:
        disposition, target, salience, contract = "parameter_need", "ParameterResolver", "medium", PARAMETER_CONTRACTS[semantic]
        reason = "该问题可降维为参数或配置契约，不占用主策机制决策队列。"
    elif semantic in ENTITY_CONTRACTS:
        disposition, target, salience, contract = "entity_attribute", "Entity Model", "medium", ENTITY_CONTRACTS[semantic]
        reason = "该问题可降维为对象属性或映射关系。"
    elif semantic in IMPLEMENTATION_DEFAULTS:
        disposition, target, reason = "implementation_default", "Implementation Default", IMPLEMENTATION_DEFAULTS[semantic]
    elif semantic in ALREADY_ANSWERED:
        disposition, target, reason = "already_answered_by_evidence", "Deferred", ALREADY_ANSWERED[semantic]
    elif semantic in HIGH_SALIENCE:
        disposition, target, salience = "real_design_decision", "Planner Review", "high"
        reason = "不同答案会改变玩法结果、重要状态或玩家选择，属于主策应明确的规则。"
    else:
        disposition, target = "implementation_default", "Implementation Default"
        reason = "目前只证明实现细节未定义，尚不足以证明存在值得主策停下来决定的玩法分支。"

    return {
        "gapId": gap.get("gapId"), "mechanicId": gap.get("mechanicId"),
        "originalGap": gap.get("question"), "gapDisposition": disposition,
        "plannerSalience": salience, "routeTarget": target, "reason": reason,
        "reducedContract": contract, "plannerReviewEligible": disposition == "real_design_decision",
        "createsApprovedRule": False, "sourceNodeIds": gap.get("sourceNodeIds", []),
        "missingNodeSemantic": semantic, "implementationImpact": gap.get("implementationImpact"),
        "qaImpact": gap.get("qaImpact"), "plannerQuestion": None,
    }


def route_candidate_gaps(candidate_gaps: list[dict[str, Any]], graphs: list[dict[str, Any]],
                         approved_rules: list[dict[str, Any]], evidence: Any) -> dict[str, Any]:
    graph_by_id = {graph["mechanicId"]: graph for graph in graphs}
    results = [route_gap_for_planner_significance(gap, graph_by_id.get(gap.get("mechanicId"), {"nodes": []}),
                                                  approved_rules, evidence) for gap in candidate_gaps]
    counts = {item: sum(result["gapDisposition"] == item for result in results) for item in DISPOSITIONS}
    return {"candidateCount": len(results), "dispositionCounts": counts, "results": results,
            "plannerReviewGapIds": [item["gapId"] for item in results if item["plannerReviewEligible"]],
            "plannerQuestionGeneratedCount": 0, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
            "parameterResolverInvoked": False}


def evaluate_planner_signal_to_noise(routing_report: dict[str, Any]) -> dict[str, Any]:
    review = [item for item in routing_report["results"] if item.get("routeTarget") == "Planner Review"]
    signal = [item for item in review if item.get("gapDisposition") == "real_design_decision"]
    noise = len(review) - len(signal)
    return {"candidateCount": routing_report["candidateCount"], "plannerReviewCount": len(review),
            "plannerReviewSignalCount": len(signal), "plannerReviewNoiseCount": noise,
            "plannerSignalToNoiseRatio": round(len(signal) / len(review), 4) if review else 1.0,
            "candidateSignalRate": len(signal) / routing_report["candidateCount"] if routing_report["candidateCount"] else 0.0}


def evaluate_planner_routing_quality(routing_report: dict[str, Any]) -> dict[str, Any]:
    results = routing_report["results"]
    planner = [item for item in results if item["routeTarget"] == "Planner Review"]
    noise = [item for item in planner if item["gapDisposition"] != "real_design_decision"]
    low_salience = [item for item in planner if item["plannerSalience"] != "high"]
    leaked_defaults = [item for item in planner if item["missingNodeSemantic"] in IMPLEMENTATION_DEFAULTS]
    dimensions = {
        "decisionRelevance": round(100 * (1 - len(noise) / max(1, len(planner))), 2),
        "nonTriviality": round(100 * (1 - (len(low_salience) + len(leaked_defaults)) / max(1, len(planner))), 2),
        "gameplayConsequence": round(100 * sum(item["plannerSalience"] == "high" for item in planner) / max(1, len(planner)), 2),
    }
    return {"score": round(sum(dimensions.values()) / len(dimensions), 2), "dimensions": dimensions,
            "plannerNoiseGapIds": [item["gapId"] for item in noise],
            "policy": "quality rewards relevant non-trivial gameplay decisions; candidate count never adds score"}
