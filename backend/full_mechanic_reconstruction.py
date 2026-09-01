from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


COUNTED_KNOWLEDGE_CLASSES = {
    "confirmed",
    "conservative_proposal",
    "design_inference",
    "recommended_alternative",
    "parameter",
}
LOW_INFORMATION_PATTERNS = ("满足条件后执行", "按规则处理", "按规则生成", "开始时开始", "结束时结束")
DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "planner_knowledge" / "full_mechanic_reconstruction_profiles_v1.json"
IMPLEMENTATION_DETAIL_TYPES = {
    "addressable_instance_model", "confirmation_lock", "listener_event_model",
    "reference_cleanup", "internal_timer_cleanup", "internal_pending_processing",
}
SUPPORTING_DETAIL_TYPES = {"supporting_execution", "temporary_state_cleanup", "qa_procedure"}
FAMILY_VALUE_SIGNALS = {
    "state": "changes_state_lifecycle", "lifecycle": "changes_state_lifecycle",
    "reset": "changes_state_lifecycle", "interrupt": "changes_state_lifecycle",
    "condition": "changes_strategy_or_result", "repeat": "changes_strategy_or_result",
    "branch": "multiple_valid_outcomes", "algorithm": "changes_random_or_result",
    "parameter": "changes_resource_numeric_or_stats", "data_flow": "changes_cross_system_flow",
    "dependency": "changes_cross_system_flow",
}


def apply_planner_value_gate(responsibility: dict[str, Any]) -> dict[str, Any]:
    detail_type = responsibility.get("detailType", "game_rule")
    signals = list(responsibility.get("plannerValueSignals", []))
    if detail_type in IMPLEMENTATION_DETAIL_TYPES:
        value_class = "implementation_only"
        reason = "Only determines internal implementation or cleanup behavior."
    elif detail_type in SUPPORTING_DETAIL_TYPES or not signals:
        value_class = "supporting_execution"
        reason = "Supports execution clarity but has no independent gameplay design consequence."
    else:
        value_class = "high_value"
        reason = "Changes gameplay, lifecycle, numeric outcome, ownership, or a real design branch."
    return {
        **responsibility,
        "plannerValueClass": value_class,
        "plannerValueReason": reason,
        "countsTowardCoreDepth": value_class == "high_value",
    }


def load_reconstruction_profile(
    mechanic_design_id: str,
    path: Path = DEFAULT_PROFILE_PATH,
    existence_signals: set[str] | None = None,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload["profiles"][mechanic_design_id]
    detail_overrides = payload.get("detailTypeOverrides", {})
    lever_by_responsibility = {}
    for lever_id, lever_question, member_ids in payload.get("designLevers", {}).get(mechanic_design_id, []):
        for member_id in member_ids:
            lever_by_responsibility[member_id] = (lever_id, lever_question)
    signals = existence_signals
    responsibilities = []
    for responsibility_id, family, role, question, semantic, required_signal in source["responsibilities"]:
        active = role == "core" or (required_signal is not None and (signals is None or required_signal in signals))
        detail_type = detail_overrides.get(responsibility_id, "game_rule")
        value_signal = FAMILY_VALUE_SIGNALS.get(family)
        responsibility = {
            "responsibilityId": responsibility_id,
            "family": family,
            "role": role,
            "executionQuestion": question,
            "requiredSemantics": [semantic],
            "requiredExistenceSignals": [required_signal] if required_signal else [],
            "applicability": "active" if active else "dormant_optional",
            "satisfactionCriteria": [semantic],
            "insufficientPatterns": list(LOW_INFORMATION_PATTERNS),
            "detailType": detail_type,
            "plannerValueSignals": [] if detail_type != "game_rule" else ([value_signal] if value_signal else []),
            "designLeverId": lever_by_responsibility.get(responsibility_id, (None, None))[0],
            "designLeverQuestion": lever_by_responsibility.get(responsibility_id, (None, None))[1],
        }
        responsibilities.append(apply_planner_value_gate(responsibility))
    return {
        "mechanicDesignId": mechanic_design_id,
        "modelType": source["modelType"],
        "contentAuthority": payload["contentAuthority"],
        "responsibilities": responsibilities,
    }


def _item_counts(item: dict[str, Any]) -> bool:
    if item.get("gateStatus") != "pass":
        return False
    knowledge_class = item.get("knowledgeClass")
    if knowledge_class not in COUNTED_KNOWLEDGE_CLASSES:
        return False
    if knowledge_class == "parameter":
        return bool(item.get("coreMechanicResponsibility") and item.get("consumerDesignItemIds"))
    return True


def evaluate_core_design_depth(model: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    responsibilities = contract.get("responsibilities", [])
    counted_items = [item for item in model.get("designItems", []) if _item_counts(item)]
    covered: list[str] = []
    missing: list[str] = []
    covered_weight = 0.0
    total_weight = 0.0

    for responsibility in responsibilities:
        responsibility_id = responsibility["responsibilityId"]
        weight = float(responsibility.get("weight", 1))
        total_weight += weight
        required = set(responsibility.get("requiredSemantics", []))
        available_semantics = {semantic for item in counted_items
                               for semantic in item.get("semanticResponsibilities", [])}
        matched = bool(required and required.issubset(available_semantics))
        if matched:
            covered.append(responsibility_id)
            covered_weight += weight
        else:
            missing.append(responsibility_id)

    coverage = round(100.0 * covered_weight / total_weight, 1) if total_weight else 0.0
    return {
        "coverage": coverage,
        "coveredResponsibilityIds": covered,
        "missingResponsibilityIds": missing,
        "failedResponsibilityIds": [],
    }


def validate_reconstruction(model: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    items = model.get("designItems", [])
    relations = model.get("relations", [])
    texts = [item.get("text", "") for item in items]
    information_gain = all(text and not any(pattern in text for pattern in LOW_INFORMATION_PATTERNS)
                           for text in texts)
    roles = {item.get("lifecycleRole") for item in items}
    required_roles = set(contract.get("requiredLifecycleRoles", []))
    lifecycle = required_roles.issubset(roles) and bool(relations or len(required_roles) < 2)
    ids = [item.get("designItemId") for item in items]
    stable_ids = all(ids) and len(ids) == len(set(ids))
    duplicate_text = len(texts) != len(set(texts))
    parameters_valid = all(parameter.get("consumerDesignItemIds")
                           for parameter in model.get("parameterContracts", []))
    gates = {
        "lifecycleClosure": lifecycle,
        "branchClosure": not model.get("unclosedBranchIds"),
        "repeatClosure": not model.get("unclosedRepeatIds"),
        "dataFlowClosure": not model.get("unconsumedOutputIds"),
        "ruleReuse": not model.get("duplicatePrimaryRuleIds"),
        "informationGain": information_gain,
        "compatibility": not model.get("compatibilityIssues"),
        "coherence": not model.get("coherenceIssues"),
        "granularity": stable_ids and not duplicate_text,
        "plannerRelevance": all(item.get("plannerRelevant", True) for item in items),
        "parameterConsumers": parameters_valid,
    }
    return {"pass": all(gates.values()), "gates": gates}


def reconstruct_mechanic_model(reconstruction_input: dict[str, Any]) -> dict[str, Any]:
    profile = reconstruction_input.get("profile", {})
    responsibilities = profile.get("responsibilities", [])
    for responsibility in responsibilities:
        if not responsibility.get("responsibilityId"):
            raise ValueError("responsibilityId is required")
    duplicate_ids = [item for item, count in Counter(
        responsibility["responsibilityId"] for responsibility in responsibilities
    ).items() if count > 1]
    if duplicate_ids:
        raise ValueError(f"duplicate responsibilityId: {duplicate_ids}")
    return {
        "mechanicDesignId": reconstruction_input["mechanicDesignId"],
        "designItems": list(reconstruction_input.get("sourceItems", [])),
        "relations": list(reconstruction_input.get("sourceRelations", [])),
        "parameterContracts": list(reconstruction_input.get("parameterContracts", [])),
    }
