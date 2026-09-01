from __future__ import annotations

from copy import deepcopy
from typing import Any


_PUBLISHABLE_RULE_STATUSES = {"existing_valid", "approved_review", "evidence_derived_valid"}
_LOGIC_RULE_TYPES = {"game_rule", "gameplay_parameter", "logic", "numeric", "config"}
_PROJECTED_TYPES = {"conservative_proposal", "design_inference", "alternative_design", "parameter"}


def assess_proposal_gates(proposal: dict[str, Any]) -> dict[str, bool]:
    explicit = all(field in proposal for field in (
        "qualityGatePassed", "compatibilityPassed", "coherencePassed"
    ))
    if explicit:
        return {"informationGain": proposal["qualityGatePassed"] is True,
                "compatibility": proposal["compatibilityPassed"] is True,
                "coherence": proposal["coherencePassed"] is True}
    text = " ".join(str(proposal.get("proposalText", "")).split())
    invalid = {"开始时开始统计。", "满足条件后执行。", "满足攻击条件后攻击。", "按规则计算伤害。"}
    return {
        "informationGain": bool(proposal.get("informationGainTypes")) and text not in invalid,
        "compatibility": not proposal.get("conflictingEvidence") and not proposal.get("conflictingRuleIds"),
        "coherence": bool(proposal.get("depthDimensionIds")) and not proposal.get("coherenceIssues"),
    }


def _proposal_passes(proposal: dict[str, Any]) -> bool:
    return all(assess_proposal_gates(proposal).values())


def _matching_rules(dimension: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = set(dimension["satisfactionContract"].get("requiredSemantics", []))
    logic_class = dimension.get("logicClass", "logic")
    result = []
    for rule in rules:
        if not rule.get("valid") or rule.get("ruleStatus") not in _PUBLISHABLE_RULE_STATUSES:
            continue
        if logic_class == "logic" and rule.get("ruleType", "game_rule") not in _LOGIC_RULE_TYPES:
            continue
        if required <= set(rule.get("semanticResponsibilities", [])):
            result.append(rule)
    return result


def _validate_dimensions(dimensions: list[dict[str, Any]]) -> None:
    by_id = {item["depthDimensionId"]: item for item in dimensions}
    if len(by_id) != len(dimensions):
        raise ValueError("depth granularity violation: duplicate stable id")
    active_questions: set[str] = set()
    for item in dimensions:
        if item.get("applicability", {}).get("status") != "active":
            continue
        question = " ".join(item.get("executionQuestion", "").split()).casefold()
        if question in active_questions:
            raise ValueError("depth granularity violation: synonymous execution question")
        active_questions.add(question)
        parent_id = item.get("parentDepthDimensionId")
        if parent_id:
            parent = by_id.get(parent_id)
            if not parent or parent.get("applicability", {}).get("status") != "active":
                raise ValueError("parent existence signal is not active")


def evaluate_depth_profile(
    profile: dict[str, Any],
    rules: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate one review-only depth profile without changing source state."""
    result = deepcopy(profile)
    dimensions = result.get("dimensions", [])
    _validate_dimensions(dimensions)
    active = [item for item in dimensions if item.get("applicability", {}).get("status") == "active"]
    covered = conservative = design = 0
    failed_active = False
    human_decision = False
    unresolved_core = False
    for item in dimensions:
        matches = _matching_rules(item, rules) if item in active else []
        item["coverage"] = {
            "currentStatus": "covered" if matches else "missing",
            "supportingRuleIds": [rule["ruleId"] for rule in matches],
        }
        if item not in active:
            continue
        current = bool(matches)
        relevant = [proposal for proposal in proposals
                    if item["depthDimensionId"] in proposal.get("depthDimensionIds", [])]
        passing = [proposal for proposal in relevant if _proposal_passes(proposal)]
        has_conservative = any(p.get("proposalType") == "conservative_proposal" for p in passing)
        has_design = any(p.get("proposalType") in _PROJECTED_TYPES for p in passing)
        covered += int(current)
        conservative += int(current or has_conservative)
        design += int(current or has_design)
        human_decision |= item.get("completionRoute") == "human_decision"
        # Projected proposals improve review coverage but do not resolve a Core
        # dimension until they become Existing/Approved Rules.
        unresolved_core |= item.get("dimensionRole") == "core" and not current
        failed_active |= bool(relevant) and not bool(passing)
        failed_active |= not current and item.get("completionRoute") not in {
            "evidence_probe", "conservative_proposal", "design_inference",
            "alternative_design", "parameter", "human_decision",
        }
    denominator = len(active)
    percent = lambda count: count / denominator * 100 if denominator else 100.0
    result.update({
        "activeDimensionCount": denominator,
        "currentCoveredCount": covered,
        "currentCoverage": percent(covered),
        "projectedConservativeCoverage": percent(conservative),
        "projectedDesignCoverage": percent(design),
        "projectedCoverage": percent(design),
        "depthReady": not (unresolved_core or human_decision or failed_active),
    })
    return result


def evaluate_depth_benchmark(
    profiles: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluated = [evaluate_depth_profile(profile, rules, proposals) for profile in profiles]
    total = sum(item["activeDimensionCount"] for item in evaluated)
    weighted = lambda key: (sum(item[key] * item["activeDimensionCount"] for item in evaluated) / total
                            if total else 100.0)
    return {
        "profiles": evaluated,
        "metrics": {
            "activeDimensionCount": total,
            "currentCoverage": weighted("currentCoverage"),
            "projectedConservativeCoverage": weighted("projectedConservativeCoverage"),
            "projectedDesignCoverage": weighted("projectedDesignCoverage"),
            "projectedCoverage": weighted("projectedCoverage"),
            "depthReadyMechanicCount": sum(item["depthReady"] for item in evaluated),
        },
    }
