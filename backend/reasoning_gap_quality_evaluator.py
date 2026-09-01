from __future__ import annotations

from typing import Any

from backend.reasoning_gap_expander import GENERIC, LEADING, validate_reasoning_gap


def evaluate_reasoning_gap_quality(gaps: list[dict[str, Any]], graphs: list[dict[str, Any]],
                                   decision_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    graph_by_id = {graph["mechanicId"]: graph for graph in graphs}
    key_counts = {}
    decisions = {item["gapId"]: item for item in (decision_results or [])}
    for gap in gaps:
        key_counts[gap.get("semanticKey")] = key_counts.get(gap.get("semanticKey"), 0) + 1
    per = []
    for gap in gaps:
        graph = graph_by_id.get(gap.get("mechanicId"), {"mechanicId": gap.get("mechanicId"), "nodes": []})
        validation = validate_reasoning_gap(gap, graph)
        grounded = not any(item["code"] == "breakpoint_not_grounded" for item in validation["findings"])
        generic = bool(GENERIC.match(str(gap.get("question") or "").strip()))
        leading = bool(LEADING.search(str(gap.get("question") or "")))
        decision = decisions.get(gap.get("gapId"))
        status = decision.get("decisionWorthiness") if decision else "keep"
        criteria = set(decision.get("qualifyingCriteria", [])) if decision else {"program_branch", "qa_expectation"}
        dimensions = {
            "breakpointGrounding": 15 if grounded else 0,
            "specificity": 10 if not generic and len(str(gap.get("question") or "")) >= 18 else 0,
            "implementationUsefulness": 10 if gap.get("implementationImpact") else 0,
            "qaUsefulness": 10 if gap.get("qaImpact") else 0,
            "semanticUniqueness": 10 if key_counts.get(gap.get("semanticKey")) == 1 else 0,
            "noLeadingAnswer": 10 if not leading else 0,
            "decisionRelevance": 15 if status == "keep" else 5 if status == "defer" else 0,
            "nonTriviality": 10 if status in {"keep", "defer"} else 0,
            "gameplayConsequence": 10 if status == "keep" and bool(criteria & {"numeric_result", "state_transition", "rule_boundary", "program_branch"}) else 5 if status == "defer" else 0,
        }
        per.append({"gapId": gap.get("gapId"), "score": sum(dimensions.values()), "dimensions": dimensions,
                    "qualityGate": "pass" if validation["valid"] else "fail", "findings": validation["findings"]})
    return {"evaluatorVersion": "reasoning-gap-quality-v1", "total": round(sum(item["score"] for item in per) / len(per), 2) if per else 0.0,
            "gapCount": len(per), "passedCount": sum(item["qualityGate"] == "pass" for item in per),
            "failedCount": sum(item["qualityGate"] == "fail" for item in per), "perGap": per,
            "policy": "quality is averaged per unique grounded decision; gap count never adds score"}
