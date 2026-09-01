from __future__ import annotations

from typing import Any


WEIGHTS = {
    "actors": 10,
    "inputAndTrigger": 15,
    "processingChain": 20,
    "stateChange": 10,
    "result": 10,
    "exitAndBoundary": 10,
    "dependencies": 10,
    "gapNodeLocalization": 10,
    "systemAbstraction": 5,
}


def _has_role(nodes: list[dict[str, Any]], *roles: str) -> bool:
    return any(node.get("role") in roles and node.get("status") != "not_applicable" for node in nodes)


def _dimension_scores(model: dict[str, Any]) -> dict[str, float]:
    nodes = model.get("nodes", [])
    mapped_gaps = {gap_id for node in nodes for gap_id in node.get("supportingGapIds", [])}
    unmapped = set(model.get("unmappedGapIds", []))
    total_gaps = len(mapped_gaps.union(unmapped))
    gap_rate = len(mapped_gaps) / total_gaps if total_gaps else 1.0

    def structural_score(weight: int, roles: tuple[str, ...]) -> float:
        applicable = any(node.get("role") in roles for node in nodes)
        return float(weight) if not applicable or _has_role(nodes, *roles) else 0.0

    has_system_model = bool(model.get("supportingRuleIds")) and any(
        node.get("role") not in {"presentation"} for node in nodes
    )
    return {
        "actors": float(WEIGHTS["actors"] if model.get("actors") else 0),
        "inputAndTrigger": float(WEIGHTS["inputAndTrigger"] if _has_role(nodes, "input", "precondition", "trigger") else 0),
        "processingChain": structural_score(WEIGHTS["processingChain"], ("processing", "effect")),
        "stateChange": structural_score(WEIGHTS["stateChange"], ("state_before", "state_change")),
        "result": structural_score(WEIGHTS["result"], ("output",)),
        "exitAndBoundary": structural_score(WEIGHTS["exitAndBoundary"], ("exit_boundary", "failure_boundary")),
        "dependencies": structural_score(WEIGHTS["dependencies"], ("dependency",)),
        "gapNodeLocalization": round(WEIGHTS["gapNodeLocalization"] * gap_rate, 2),
        "systemAbstraction": float(WEIGHTS["systemAbstraction"] if has_system_model else 0),
    }


def evaluate_mechanic_depth(mechanic_models: list[dict[str, Any]]) -> dict[str, Any]:
    per_mechanic = []
    for model in mechanic_models:
        dimensions = _dimension_scores(model)
        per_mechanic.append({
            "mechanicId": model["mechanicId"],
            "name": model.get("name"),
            "score": round(sum(dimensions.values()), 2),
            "dimensions": dimensions,
            "observationOnlyWithoutSystemAbstraction": dimensions["systemAbstraction"] == 0,
        })
    dimensions = {
        name: round(sum(item["dimensions"][name] for item in per_mechanic) / len(per_mechanic), 2)
        if per_mechanic else float(weight)
        for name, weight in WEIGHTS.items()
    }
    contributions = [item for model in mechanic_models for item in model.get("ruleMechanicalInformationGain", [])]
    low = sorted(item["ruleId"] for item in contributions if item.get("classification") == "low_abstraction")
    average = round(sum(item.get("mechanicalInformationGain", 0) for item in contributions) / len(contributions), 2) if contributions else 0.0
    return {
        "evaluatorVersion": "mechanic-depth-evaluator-v1",
        "total": round(sum(dimensions.values()), 2),
        "dimensions": dimensions,
        "perMechanic": per_mechanic,
        "mechanicalInformationGain": {
            "averageSignalsPerRule": average,
            "lowAbstractionRuleIds": low,
            "lowAbstractionRuleCount": len(low),
            "fillerCount": 0,
        },
        "scoringPolicy": "structure recognition is scored independently from Gap closure",
    }
