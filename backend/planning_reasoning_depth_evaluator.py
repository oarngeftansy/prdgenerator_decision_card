from __future__ import annotations

from typing import Any


WEIGHTS = {
    "mechanicAbstraction": 15, "stateModel": 15, "conditionAndTransition": 15,
    "processingChain": 15, "boundaryAndException": 10, "crossSystemDependency": 10,
    "lifecycle": 10, "parameterConfigAwareness": 5, "gapLocalization": 5,
}


def _scores(model: dict[str, Any]) -> dict[str, float]:
    localized = {item["gapId"] for node in model.get("nodes", []) for item in node.get("gapLocations", [])}
    unmapped = set(model.get("unmappedGapIds", []))
    gap_total = len(localized | unmapped)
    gap_rate = len(localized) / gap_total if gap_total else 1.0
    lifecycle = model.get("lifecycle", {})
    return {
        "mechanicAbstraction": 15.0 if model.get("actors") and model.get("objects") else 0.0,
        "stateModel": 15.0 if model.get("states") else 0.0,
        "conditionAndTransition": 15.0 if (model.get("entryConditions") or model.get("triggers") or model.get("preconditions")) and model.get("stateTransitions") else 0.0,
        "processingChain": 15.0 if model.get("processingStages") and model.get("outputs") else 0.0,
        "boundaryAndException": 10.0 if model.get("exitConditions") and (model.get("exceptions") or model.get("boundaries")) else 0.0,
        "crossSystemDependency": 10.0 if model.get("upstreamMechanics") or model.get("downstreamMechanics") else 0.0,
        "lifecycle": 10.0 if all(lifecycle.get(key) for key in ("initialize", "persist", "reset")) else 0.0,
        "parameterConfigAwareness": 5.0 if model.get("parameters") and model.get("configSources") else 0.0,
        "gapLocalization": round(5.0 * gap_rate, 2),
    }


def evaluate_planning_reasoning_depth(models: list[dict[str, Any]]) -> dict[str, Any]:
    per_mechanic = []
    for model in models:
        dimensions = _scores(model)
        per_mechanic.append({"mechanicId": model["mechanicId"], "name": model.get("name"), "score": sum(dimensions.values()), "dimensions": dimensions})
    dimensions = {
        name: round(sum(item["dimensions"][name] for item in per_mechanic) / len(per_mechanic), 2) if per_mechanic else float(weight)
        for name, weight in WEIGHTS.items()
    }
    statuses = {
        status: sum(node.get("reasoningStatus") == status for model in models for node in model.get("nodes", []))
        for status in ("confirmed", "derived_structure", "hypothesis", "unresolved")
    }
    return {
        "evaluatorVersion": "planning-reasoning-depth-v1", "total": round(sum(dimensions.values()), 2),
        "dimensions": dimensions, "perMechanic": per_mechanic, "nodeStatusCounts": statuses,
        "executionCompletenessContribution": 0,
        "policy": "derived_structure, hypothesis and unresolved prove reasoning coverage only; they never close execution gaps",
    }
