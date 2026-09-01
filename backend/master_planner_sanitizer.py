from __future__ import annotations

import copy
from typing import Any

from .rule_status import normalize_rule_status


_STATUS_BY_SOURCE = {
    "material": "CONFIRMED",
    "reference_document": "CONFIRMED",
    "inference": "INFERRED",
    "inferred": "INFERRED",
    "planner": "PROPOSED",
    "proposal": "PROPOSED",
    "proposed": "PROPOSED",
    "pending": "PROPOSED",
}


def _status(item: dict[str, Any], default: str = "CONFIRMED") -> str:
    explicit = item.get("knowledgeStatus")
    if explicit:
        return normalize_rule_status(explicit, inference_level=item.get("inferenceLevel"), source_type=item.get("sourceType"))
    source = str(item.get("sourceType") or item.get("evidenceLevel") or "").strip().casefold()
    return _STATUS_BY_SOURCE.get(source, default)


def _stamp(value: Any, inherited: str = "CONFIRMED") -> Any:
    if isinstance(value, list):
        return [_stamp(item, inherited) for item in value]
    if not isinstance(value, dict):
        return value
    result = copy.deepcopy(value)
    own_status = _status(result, inherited)
    if any(key in result for key in ("text", "description", "value", "expression", "expected", "behavior", "plannerMeaning")):
        result["knowledgeStatus"] = own_status
    for key, child in list(result.items()):
        if isinstance(child, (dict, list)):
            result[key] = _stamp(child, own_status)
    return result


def sanitize_optional_modules_for_master_planner(chapter: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Keep explicit inference/proposals instead of deleting them for lack of direct evidence."""
    result = _stamp(chapter)
    for key in ("parameterSchema", "formulae", "workedExamples", "configurationSources"):
        if not result.get(key):
            result.pop(key, None)
    return result, []


def sanitize_semantics_for_master_planner(chapter: dict[str, Any]) -> dict[str, Any]:
    """Preserve generated business semantics and make provenance explicit.

    The previous sanitizer removed non-material claims and converted useful planning closure
    into decision cards. Master Planner keeps them as INFERRED/PROPOSED and lets the renderer
    show that status visually.
    """
    result = _stamp(chapter)
    claims = []
    for claim in result.get("claims") or []:
        if not isinstance(claim, dict) or not str(claim.get("text") or "").strip():
            continue
        claim.setdefault("knowledgeStatus", _status(claim))
        claims.append(claim)
    result["claims"] = claims
    result["evidenceSanitized"] = True
    result["knowledgePolicy"] = "no_hidden_inference"
    return result
