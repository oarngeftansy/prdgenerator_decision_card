from __future__ import annotations

import copy
from typing import Any


SEMANTIC_TYPES = {
    "persistent_game_rule",
    "gameplay_parameter",
    "current_instance_state",
    "example_value",
    "ui_state",
}
CORE_TYPES = {"persistent_game_rule", "gameplay_parameter"}


def apply_instance_value_semantic_gate(records: list[dict[str, Any]]) -> dict[str, Any]:
    core: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in records:
        item = dict(raw)
        semantic_type = item.get("semanticType")
        if semantic_type not in SEMANTIC_TYPES:
            rejected.append({**item, "reason": "invalid_or_missing_semantic_type"})
            continue
        if semantic_type in {"current_instance_state", "example_value", "ui_state"}:
            excluded.append({**item, "coreEligible": False,
                             "exclusionReason": "instance_or_ui_value"})
            continue
        if semantic_type == "gameplay_parameter" and not item.get("fixedRuleBasis"):
            rejected.append({**item, "reason": "parameter_constant_not_grounded"})
            continue
        core.append({**item, "coreEligible": True})
    return {
        "coreEligible": core,
        "excluded": excluded,
        "rejected": rejected,
        "metrics": {"inputCount": len(records), "coreEligibleCount": len(core),
                    "excludedInstanceValueCount": len(excluded), "rejectedCount": len(rejected)},
    }


def apply_gate_to_semantic_contracts(contracts: list[dict[str, Any]],
                                     value_annotations: dict[str, str | dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(contracts)
    excluded: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    excluded_dimensions: list[dict[str, Any]] = []
    for contract in result:
        kept_dimensions = []
        for dimension in contract.get("requiredRuleDimensions", []):
            dimension_type = dimension.get("semanticType")
            if dimension_type not in SEMANTIC_TYPES:
                raise ValueError(f"invalid dimension semanticType: {dimension_type}")
            if dimension_type not in CORE_TYPES:
                excluded_dimensions.append({"ruleSemanticId": contract["ruleSemanticId"],
                                            "dimensionId": dimension["dimensionId"],
                                            "semanticType": dimension_type,
                                            "exclusionReason": "instance_or_ui_value"})
                continue
            if (dimension_type == "gameplay_parameter" and dimension.get("status") == "observed"
                    and "value" in dimension and not dimension.get("fixedRuleBasis")):
                excluded_dimensions.append({"ruleSemanticId": contract["ruleSemanticId"],
                                            "dimensionId": dimension["dimensionId"],
                                            "semanticType": dimension_type,
                                            "exclusionReason": "parameter_constant_not_grounded"})
                continue
            kept_subrules = []
            for index, text in enumerate(dimension.get("subrules", [])):
                key = f"{contract['ruleSemanticId']}:{dimension['dimensionId']}:subrule:{index}"
                raw_annotation = value_annotations.get(key)
                annotation = ({"semanticType": raw_annotation} if isinstance(raw_annotation, str)
                              else dict(raw_annotation or {}))
                semantic_type = annotation.get("semanticType")
                record = {"valueId": key, "text": text, "semanticType": semantic_type,
                          "ruleSemanticId": contract["ruleSemanticId"],
                          "dimensionId": dimension["dimensionId"]}
                if (semantic_type == "persistent_game_rule"
                        or (semantic_type == "gameplay_parameter" and annotation.get("fixedRuleBasis"))):
                    kept_subrules.append(text)
                    retained.append(record)
                else:
                    reason = ("parameter_constant_not_grounded" if semantic_type == "gameplay_parameter"
                              else "instance_or_ui_value")
                    excluded.append({**record, "exclusionReason": reason})
            dimension["subrules"] = kept_subrules
            kept_dimensions.append(dimension)
        contract["requiredRuleDimensions"] = kept_dimensions
    return {"contracts": result, "retainedValues": retained, "excludedValues": excluded,
            "excludedDimensions": excluded_dimensions,
            "metrics": {"retainedValueCount": len(retained), "excludedValueCount": len(excluded),
                        "excludedDimensionCount": len(excluded_dimensions)}}
