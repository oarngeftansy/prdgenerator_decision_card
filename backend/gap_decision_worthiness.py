from __future__ import annotations

from copy import deepcopy
from typing import Any


SUPPRESS_POLICIES = {
    "movement_input_composition": ("common_sense_deterministic", "自动前进负责纵向推进、横向输入负责横向微调；当前没有冲突证据，不需要策划确认位移向量的内部合成。"),
    "selection_commit": ("implementation_triviality", "一次点击只提交一次选择属于交互事件的基础防重处理，当前没有重复结算证据。"),
    "refresh_selection_exclusion": ("over_defensive_edge_case", "当前证据没有显示刷新与候选确认可在同一交互状态并发提交，不应为理论竞态增加策划问题。"),
    "refresh_candidate_pipeline": ("already_implied", "刷新后替换当前候选已经暗示重新执行当前三选一的候选生成；没有证据表明刷新使用另一套规则。"),
}
DEFER_POLICIES = {
    "contact_damage_interval": ("contact_damage_processing", "只有先确认接触伤害会持续重复结算，伤害间隔才成为适用参数。"),
    "contact_exit_condition": ("contact_damage_processing", "只有先确认存在持续接触伤害处理，脱离接触后的停止时点才需要定义。"),
}


def _criteria(gap: dict[str, Any]) -> list[str]:
    gap_type = gap.get("gapType")
    criteria = []
    if gap_type in {"processing", "ordering", "condition", "trigger", "dependency", "exception"}:
        criteria.append("program_branch")
    if gap_type in {"parameter", "aggregation", "result"}:
        criteria.append("numeric_result")
    if gap_type == "state_transition":
        criteria.append("state_transition")
    if gap_type in {"boundary", "exit_condition", "exception"}:
        criteria.append("rule_boundary")
    if gap.get("qaImpact"):
        criteria.append("qa_expectation")
    return sorted(set(criteria))


def _alternatives(gap: dict[str, Any]) -> list[str]:
    semantic = gap.get("missingNodeSemantic")
    explicit = {
        "contact_damage_processing": ["接触时仅造成一次伤害", "持续接触期间重复造成伤害"],
        "contact_damage_aggregation": ["每只怪物分别造成伤害", "同一时点只计算一次接触伤害"],
        "candidate_shortage_behavior": ["不足三项仍展示现有词条", "候选不足时不进入正常选择"],
        "movement_input_release": ["松开后保持当前位置", "松开后按规则回到路线基准位置"],
        "empty_target_behavior": ["没有目标时等待并继续检测", "没有目标时结束当前攻击循环"],
    }
    if semantic in explicit:
        return explicit[semantic]
    if gap.get("gapType") == "parameter":
        return ["使用独立配置", "读取现有相关配置"]
    return ["采用一种明确处理规则", "采用另一种会改变程序或 QA 预期的处理规则"]


def evaluate_gap_decision_worthiness(candidate_gap: dict[str, Any], grounded_graph: dict[str, Any],
                                      approved_rules: list[dict[str, Any]], evidence: Any) -> dict[str, Any]:
    del approved_rules, evidence
    gap = deepcopy(candidate_gap)
    semantic = gap.get("missingNodeSemantic")
    grounded_ids = {node["nodeId"] for node in grounded_graph.get("nodes", []) if node.get("status") in {"confirmed", "derived_structure"}}
    source_grounded = bool(gap.get("sourceNodeIds")) and set(gap.get("sourceNodeIds", [])) <= grounded_ids
    if not source_grounded:
        decision, reason_code = "suppress", "no_meaningful_branch"
        reason = "问题没有绑定当前机制的 grounded breakpoint，无法证明它会形成真实设计决策。"
        alternatives, criteria = [], []
    elif semantic in SUPPRESS_POLICIES:
        decision, (reason_code, reason) = "suppress", SUPPRESS_POLICIES[semantic]
        alternatives, criteria = ["当前规则的唯一自然解释"], []
    elif semantic in DEFER_POLICIES:
        decision, (depends_on, reason) = "defer", DEFER_POLICIES[semantic]
        reason_code, alternatives, criteria = "conditional_applicability", _alternatives(gap), _criteria(gap)
    else:
        criteria = _criteria(gap)
        if not criteria:
            decision, reason_code = "suppress", "no_meaningful_branch"
            reason, alternatives = "不同回答不会改变玩法结果、程序分支、数值、状态、边界或 QA 预期。", []
        else:
            decision, reason_code = "keep", "meaningful_design_decision"
            reason = "不同回答会改变至少一个玩法结果、程序分支、数值、状态转换、规则边界或 QA 预期。"
            alternatives = _alternatives(gap)
    return {
        "gapId": gap.get("gapId"), "mechanicId": gap.get("mechanicId"), "decisionWorthiness": decision,
        "reasonCode": reason_code, "reason": reason, "alternativeInterpretations": alternatives,
        "qualifyingCriteria": criteria, "gameplayImpact": "不同答案会改变玩家可见结果或玩法边界。" if decision == "keep" and any(item in criteria for item in ("numeric_result", "state_transition", "rule_boundary")) else "无新增玩法决策。" if decision == "suppress" else "取决于前置决策。",
        "implementationImpact": gap.get("implementationImpact"), "qaImpact": gap.get("qaImpact"),
        "dependsOnGapSemantic": DEFER_POLICIES.get(semantic, (None,))[0] if decision == "defer" else None,
        "sourceNodeIds": gap.get("sourceNodeIds", []), "internalQuestion": gap.get("question"),
    }


def filter_reasoning_gaps(candidate_gaps: list[dict[str, Any]], graphs: list[dict[str, Any]],
                          approved_rules: list[dict[str, Any]], evidence: Any) -> dict[str, Any]:
    graph_by_id = {graph["mechanicId"]: graph for graph in graphs}
    results = [evaluate_gap_decision_worthiness(gap, graph_by_id.get(gap.get("mechanicId"), {"nodes": []}), approved_rules, evidence)
               for gap in candidate_gaps]
    counts = {status: sum(result["decisionWorthiness"] == status for result in results) for status in ("keep", "suppress", "defer")}
    return {"candidateCount": len(candidate_gaps), "counts": counts, "results": results,
            "keptGapIds": [item["gapId"] for item in results if item["decisionWorthiness"] == "keep"],
            "suppressedGapIds": [item["gapId"] for item in results if item["decisionWorthiness"] == "suppress"],
            "deferredGapIds": [item["gapId"] for item in results if item["decisionWorthiness"] == "defer"],
            "plannerQuestionGeneratedCount": 0, "writesBackApprovedGap": False, "writesP4": False}
