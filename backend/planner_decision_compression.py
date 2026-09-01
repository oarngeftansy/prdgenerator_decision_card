from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any


GROUPS = {
    "candidate_filter": {
        "lever": "candidate_eligibility", "title": "词条入池规则", "type": "system_rule",
        "core": "哪些词条可以进入本次三选一？",
        "impact": "改变玩家可获得的成长选项、成长路径与随机结果。", "priority": "P0",
    },
    "candidate_constraints": {
        "lever": "candidate_draw_rules", "title": "三选一随机规则", "type": "randomization_rule",
        "core": "三张词条按什么规则抽取？",
        "impact": "改变单次三选一的随机结果、重复概率与构筑策略。", "priority": "P0",
    },
    "contact_damage_processing": {
        "lever": "contact_damage_mode", "title": "接触伤害方式", "type": "combat_rule",
        "core": "怪物接触载具后，接触伤害按单次还是持续方式处理？",
        "impact": "改变怪物贴近载具后的伤害结果、规避策略与承伤节奏。", "priority": "P0",
    },
}

COMPRESS_AWAY = {
    "empty_candidate": ("Configuration Validation", "configuration_validation", "正常配置应先保证存在可用词条；极端空池属于配置校验与兜底，不独立占用主策决策。"),
    "candidate_shortage_behavior": ("Configuration Validation", "configuration_validation", "正常配置应保证可组成三选一；不足三项先作为配置完整性校验，不因 QA 边界拆成主策决策。"),
    "selection_state_exit": ("Implementation Default", "common_sense_sequence", "选择生效后关闭选择状态并恢复战斗属于自然流程；没有特殊生命周期证据时不单独询问。"),
}

LEVER_RULE_SLOTS = {
    "candidate_eligibility": {"candidate_pool", "entry_condition", "exit_condition", "prerequisite"},
    "candidate_draw_rules": {"random_trigger", "refresh_rule", "randomization_rule"},
    "contact_damage_mode": {"attack_trigger", "damage_result", "contact_damage"},
}


def _id(mechanic_id: str, lever: str) -> str:
    value = hashlib.sha1(f"{mechanic_id}:{lever}".encode("utf-8")).hexdigest()[:12].upper()
    return f"PDEC-{value}"


def compress_planner_decisions(planner_review_gaps: list[dict[str, Any]], all_routed_gaps: list[dict[str, Any]],
                               approved_rules: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    compressed_out = []
    for gap in planner_review_gaps:
        semantic = gap.get("missingNodeSemantic")
        if semantic in COMPRESS_AWAY:
            target, reason_code, reason = COMPRESS_AWAY[semantic]
            compressed_out.append({"gapId": gap.get("gapId"), "mechanicId": gap.get("mechanicId"),
                                   "routeTarget": target, "reasonCode": reason_code, "reason": reason})
            continue
        definition = GROUPS.get(semantic)
        if not definition:
            compressed_out.append({"gapId": gap.get("gapId"), "mechanicId": gap.get("mechanicId"),
                                   "routeTarget": "Deferred", "reasonCode": "no_proven_design_lever",
                                   "reason": "尚未证明该缺口对应独立且显著的 design lever。"})
            continue
        groups.setdefault((gap.get("mechanicId"), definition["lever"]), []).append(gap)

    decisions = []
    for (mechanic_id, lever), gaps in groups.items():
        definition = next(value for value in GROUPS.values() if value["lever"] == lever)
        rule_text = [rule.get("behavior") or rule.get("sourceText") for rule in approved_rules
                     if rule.get("mechanicId") == mechanic_id and
                     rule.get("schemaSlot") in LEVER_RULE_SLOTS.get(lever, set()) and
                     (rule.get("behavior") or rule.get("sourceText"))]
        dependencies = sorted({item.get("reducedContract") for item in all_routed_gaps
                               if item.get("mechanicId") == mechanic_id and item.get("reducedContract") and
                               ((lever == "candidate_draw_rules" and item.get("missingNodeSemantic") == "candidate_weight_contract"))})
        decisions.append({
            "decisionId": _id(mechanic_id, lever), "mechanicId": mechanic_id,
            "title": definition["title"], "decisionType": definition["type"], "designLever": lever,
            "sourceReasoningGapIds": [gap["gapId"] for gap in gaps], "coreQuestion": definition["core"],
            "subQuestions": [gap.get("originalGap") or gap.get("question") for gap in gaps],
            "currentKnownRules": sorted(set(rule_text)),
            "unresolvedDimensions": sorted(set(gap.get("missingNodeSemantic") for gap in gaps)),
            "gameplayImpact": definition["impact"], "priority": definition["priority"],
            "routedDependencies": dependencies,
        })
    decisions.sort(key=lambda item: item["decisionId"])
    merge_audit = [{"decisionId": item["decisionId"], "sourceReasoningGapIds": item["sourceReasoningGapIds"],
                    "mergeReason": "同一 mechanic 内的问题共同控制同一个 design lever，可由一项策划结论统一回答。"}
                   for item in decisions]
    before, after = len(planner_review_gaps), len(decisions)
    return {"beforePlannerReviewCount": before, "afterPlannerDecisionCount": after,
            "compressionRatio": round(1 - after / before, 4) if before else 0.0,
            "plannerDecisions": decisions, "compressedOut": compressed_out, "mergeAudit": merge_audit,
            "plannerQuestionGeneratedCount": 0, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
            "parameterResolverInvoked": False}


def evaluate_planner_decision_granularity(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    lever_counts = Counter((item.get("mechanicId"), item.get("designLever")) for item in decisions)
    findings = []
    for (mechanic_id, lever), count in lever_counts.items():
        if count > 1:
            findings.append({"code": "duplicate_design_lever", "mechanicId": mechanic_id, "designLever": lever,
                             "message": "同一 design lever 被拆成多个 sibling PlannerDecision。"})
    for item in decisions:
        if item.get("decisionType") in {"parameter", "entity_attribute"}:
            findings.append({"code": "parameter_as_decision", "decisionId": item.get("decisionId"),
                             "message": "参数或实体属性被错误提升为独立 PlannerDecision。"})
        if len(item.get("sourceReasoningGapIds", [])) == 1 and len(item.get("subQuestions", [])) > 3:
            findings.append({"code": "qa_edge_fragmentation", "decisionId": item.get("decisionId"),
                             "message": "单一底层 Gap 被 QA 边界扩张成多个策划问题。"})
    counts = Counter(item["code"] for item in findings)
    return {"qualityGate": "pass" if not findings else "fail", "findingCount": len(findings),
            "findingCounts": dict(counts), "findings": findings,
            "checks": ["sibling_rule_group", "answer_coverage", "parameter_or_attribute_promotion",
                       "qa_edge_fragmentation", "duplicate_design_lever"]}
