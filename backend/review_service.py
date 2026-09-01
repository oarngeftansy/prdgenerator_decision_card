from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
import re
from typing import Any

from .review_model import COMPONENT_STATE_KEYS, RESULT_TYPES, RULE_DOMAIN_KEYS, TRIGGER_TYPES, representative_frames_for_ids, review_gate, validate_representative_frames, validate_review_model


_COLLECTIONS = {
    "stage": "stages",
    "transition": "transitions",
    "region": "regions",
    "component": "components",
    "constraint": "crossStateConstraints",
}
RULE_COLLECTIONS = {"narrative": "NAR", "guidance": "GDE", "redDots": "RDT"}
RULE_OPERATION_TYPES = frozenset({"upsert_rule", "delete_rule", "reorder_rule", "reorder_rule_nested", "mark_rule_domain_reviewed"})
_HISTORY_LIMIT = 50
_EDITABLE_FIELDS = {
    "stage": {"name", "objective", "entryCondition", "exitCondition", "smallLoop", "unknowns"},
    "transition": {"triggerType", "triggerLabel", "condition", "response", "resultType", "resultState", "primary", "included", "sourceLevel", "confidence"},
    "region": {"name", "bounds", "displayNumber", "sourceType", "primary", "rule"},
    "component": {"name", "label", "type", "role", "description", "states", "properties", "rule", "confidence", "unknowns"},
    "constraint": {"text", "status", "severity", "rule", "details", "unknowns"},
}
_ANCHOR_TRIGGERS = {"tap", "long_press"}
_CONSTRAINT_SEVERITIES = {"core", "non_core"}
_CONSTRAINT_STATUSES = {"observed", "inferred", "unknown"}
_RESULT_TYPES_REQUIRING_TARGET = {"navigate", "open_overlay", "return", "loop"}
_TRANSITION_FIELDS = {
    "sourceStageId", "targetStageId", "triggerType", "triggerLabel", "componentId", "regionId", "sourceFrameId",
    "anchor", "condition", "response", "resultType", "resultState", "trueBranchTargetId", "falseBranchTargetId",
    "primary", "included", "sourceLevel", "confidence",
}
_CONSTRAINT_FIELDS = {"text", "status", "severity", "rule", "details", "unknowns"}
_MIN_REGION_SIZE = 0.02


@dataclass
class ReviewConflict(Exception):
    current_revision: int


def ensure_review_entity_metadata(model: dict[str, Any]) -> dict[str, Any]:
    for collection in _COLLECTIONS.values():
        for entity in model.get(collection) or []:
            entity["humanEditedFields"] = sorted({field for field in entity.get("humanEditedFields", []) if isinstance(field, str)})
            entity["suggestions"] = dict(entity.get("suggestions") or {})
    return model


def sanitize_review_ui_state(model: dict[str, Any], saved: dict[str, Any] | None) -> dict[str, Any]:
    ensure_review_entity_metadata(model)
    value = saved or {}
    stage_order = [item["id"] for item in model.get("stages") or []]
    stage_ids = set(stage_order)
    ids_by_type = {
        "stage": stage_ids,
        "transition": {item["id"] for item in model.get("transitions") or []},
        "region": {item["id"] for item in model.get("regions") or []},
        "component": {item["id"] for item in model.get("components") or []},
        "constraint": {item["id"] for item in model.get("crossStateConstraints") or []},
    }
    selection = value.get("selection")
    return {
        "view": value.get("view") if value.get("view") in {"gameplay_directory", "flow", "stage", "preview", "interaction_preview", "gameplay", "diagrams", "tables", "final_preview"} else "flow",
        "selectedStageId": value.get("selectedStageId") if value.get("selectedStageId") in stage_ids else (stage_order[0] if stage_order else None),
        "selectedTransitionId": value.get("selectedTransitionId") if value.get("selectedTransitionId") in ids_by_type["transition"] else None,
        "selectedFrameId": value.get("selectedFrameId") if value.get("selectedFrameId") in model.get("sources", {}) else None,
        "selection": selection if isinstance(selection, dict) and selection.get("id") in ids_by_type.get(selection.get("type"), set()) else None,
        "projectDrawerOpen": bool(value.get("projectDrawerOpen")),
    }


def record_reanalysis_suggestions(model: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(model)
    ensure_review_entity_metadata(result)
    for entity, collection in _COLLECTIONS.items():
        candidate_by_id = {item.get("id"): item for item in candidate.get(collection) or []}
        for current in result.get(collection) or []:
            fresh = candidate_by_id.get(current.get("id"))
            if not fresh:
                continue
            for field in _EDITABLE_FIELDS[entity]:
                if field in fresh and fresh.get(field) != current.get(field):
                    current["suggestions"][field] = deepcopy(fresh[field])
    domains, candidate_domains = result.get("ruleDomains"), candidate.get("ruleDomains")
    if not isinstance(domains, dict) or not isinstance(candidate_domains, dict) or not all(
        isinstance(domains.get(domain), list)
        and isinstance(candidate_domains.get(domain), list)
        for domain in RULE_DOMAIN_KEYS
    ):
        return result
    for domain in RULE_DOMAIN_KEYS:
        candidate_by_id = {item.get("id"): item for item in _rule_list(candidate, domain)}
        for current in _rule_list(result, domain):
            fresh = candidate_by_id.get(current.get("id"))
            if not fresh:
                continue
            _ensure_rule_metadata(current)
            for field, value in fresh.items():
                if field not in {"id", "order", "humanEditedFields", "suggestions"} and value != current.get(field):
                    current["suggestions"][field] = deepcopy(value)
    return result


def _snapshot(model: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in model.items() if key != "editHistory"}


def _content_snapshot(model: dict[str, Any]) -> dict[str, Any]:
    snapshot = _snapshot(model)
    for collection in _COLLECTIONS.values():
        for entity in snapshot.get(collection) or []:
            entity.pop("suggestions", None)
            entity.pop("humanEditedFields", None)
    domains = snapshot.get("ruleDomains")
    if isinstance(domains, dict):
        domains.pop("reviewedDomains", None)
        domains.pop("confirmation", None)
        for domain in RULE_DOMAIN_KEYS:
            for rule in domains.get(domain) or []:
                if isinstance(rule, dict):
                    rule.pop("suggestions", None)
                    rule.pop("humanEditedFields", None)
    return snapshot


def _entity(model: dict[str, Any], kind: str, entity_id: str) -> dict[str, Any]:
    try:
        collection = _COLLECTIONS[kind]
        return next(item for item in model[collection] if item["id"] == entity_id)
    except (KeyError, StopIteration) as exc:
        raise ValueError(f"unknown {kind}: {entity_id}") from exc


def _rule_list(model: dict[str, Any], domain: Any) -> list[dict[str, Any]]:
    if domain not in RULE_COLLECTIONS:
        raise ValueError("unknown rule domain")
    rules = model.get("ruleDomains", {}).get(domain)
    if not isinstance(rules, list):
        raise ValueError(f"rule domain {domain} must be a list")
    return rules


def _ensure_rule_metadata(rule: dict[str, Any]) -> None:
    rule["humanEditedFields"] = sorted({field for field in rule.get("humanEditedFields", []) if isinstance(field, str)})
    rule["suggestions"] = dict(rule.get("suggestions") or {})


def _rule(model: dict[str, Any], domain: Any, rule_id: Any) -> dict[str, Any]:
    if not isinstance(rule_id, str) or not rule_id:
        raise ValueError("rule id is required")
    for rule in _rule_list(model, domain):
        if rule.get("id") == rule_id:
            _ensure_rule_metadata(rule)
            return rule
    raise ValueError(f"unknown rule: {rule_id}")


def _rule_payload_fields(payload: dict[str, Any]) -> set[str]:
    return set(payload) - {"id", "order", "humanEditedFields", "suggestions"}


def _renumber_rules(rules: list[dict[str, Any]]) -> None:
    for order, rule in enumerate(rules, 1):
        rule["order"] = order


def _ensure_next_rule_number(model: dict[str, Any], domain: str, rules: list[dict[str, Any]]) -> dict[str, int]:
    counters = model["ruleDomains"].setdefault("nextRuleNumbers", {})
    if not isinstance(counters, dict):
        raise ValueError("rule nextRuleNumbers must be an object")
    prefix = RULE_COLLECTIONS[domain]
    numbers = [int(rule_id[len(prefix) + 1:]) for rule in rules if isinstance(rule_id := rule.get("id"), str) and rule_id.startswith(f"{prefix}-") and rule_id[len(prefix) + 1:].isdigit()]
    next_number = counters.get(domain, 1)
    if type(next_number) is not int or next_number < 1:
        next_number = 1
    counters[domain] = max(next_number, max(numbers, default=0) + 1)
    return counters


def _next_rule_id(model: dict[str, Any], domain: str, rules: list[dict[str, Any]]) -> str:
    counters = _ensure_next_rule_number(model, domain, rules)
    number = counters[domain]
    counters[domain] = number + 1
    prefix = RULE_COLLECTIONS[domain]
    return f"{prefix}-{number:03d}"


def _rule_index(value: Any, operation: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{operation} requires integer indexes")
    return value


def _require_revision(model: dict[str, Any], expected_revision: Any) -> None:
    if type(expected_revision) is not int:
        raise ValueError("expectedRevision must be an integer")
    if expected_revision != model["revision"]:
        raise ReviewConflict(model["revision"])


def _remember(history: dict[str, list[dict[str, Any]]], key: str, snapshot: dict[str, Any]) -> None:
    history[key] = (history.get(key, []) + [snapshot])[-_HISTORY_LIMIT:]


def _mark_human(entity: dict[str, Any], *fields: str) -> None:
    entity["humanEditedFields"] = sorted(set(entity.get("humanEditedFields", [])) | set(fields))
    suggestions = entity.setdefault("suggestions", {})
    for field in fields:
        suggestions.pop(field, None)


def _mark_changed_human_fields(entity: dict[str, Any], before: dict[str, Any], payload: dict[str, Any], editable_fields: set[str]) -> None:
    changed = [field for field in payload if field in editable_fields and before.get(field) != entity.get(field)]
    if changed:
        _mark_human(entity, *changed)


def _new_or_updated(model: dict[str, Any], collection: str, before_ids: set[str], entity_id: Any = None) -> dict[str, Any] | None:
    items = model.get(collection) or []
    if entity_id:
        return next((item for item in items if item.get("id") == entity_id), None)
    return next((item for item in items if item.get("id") not in before_ids), None)


def _next_id(items: list[dict[str, Any]], prefix: str) -> str:
    ids = {item.get("id") for item in items}
    number = 1
    width = 4 if prefix == "REG" else 3
    while f"{prefix}-{number:0{width}d}" in ids:
        number += 1
    return f"{prefix}-{number:0{width}d}"


def _region_bounds(bounds: Any) -> dict[str, float]:
    if not isinstance(bounds, dict):
        raise ValueError("region requires normalized bounds")
    try:
        x, y, width, height = (float(bounds[key]) for key in ("x", "y", "width", "height"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("region requires normalized bounds") from exc
    if not all(isfinite(value) for value in (x, y, width, height)):
        raise ValueError("region requires finite bounds")
    width, height = max(_MIN_REGION_SIZE, min(1.0, width)), max(_MIN_REGION_SIZE, min(1.0, height))
    return {"x": max(0.0, min(1.0 - width, x)), "y": max(0.0, min(1.0 - height, y)), "width": width, "height": height}


def _stage_id(model: dict[str, Any], stage_id: Any, field: str, optional: bool = False) -> str | None:
    if stage_id is None and optional:
        return None
    if not isinstance(stage_id, str) or not stage_id or not any(stage.get("id") == stage_id for stage in model.get("stages", [])):
        raise ValueError(f"invalid {field}")
    return stage_id


def _representative_frame_ids(model: dict[str, Any], stage_id: str) -> set[str]:
    stage = _entity(model, "stage", stage_id)
    return {str(item.get("frameId")) for item in stage.get("representativeFrames") or [] if item.get("frameId")}


def _validate_region_ownership(model: dict[str, Any], region: dict[str, Any]) -> None:
    stage_id, frame_id = region.get("stageId"), region.get("frameId")
    _stage_id(model, stage_id, "stageId")
    if frame_id not in _representative_frame_ids(model, stage_id):
        raise ValueError("region frameId must be a representative frame of its owning stage")


def _normalized_bounds(bounds: Any) -> dict[str, float]:
    if not isinstance(bounds, dict):
        raise ValueError("anchor requires a bound component or region")
    try:
        result = {key: float(bounds[key]) for key in ("x", "y", "width", "height")}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("anchor requires normalized bounds") from exc
    if not all(isfinite(value) for value in result.values()) or result["width"] <= 0 or result["height"] <= 0:
        raise ValueError("anchor requires normalized bounds")
    return result


def _anchor_bounds(model: dict[str, Any], transition: dict[str, Any]) -> dict[str, float]:
    component_id, region_id = transition.get("componentId"), transition.get("regionId")
    component = next((item for item in model.get("components", []) if item.get("id") == component_id), None) if component_id else None
    if component:
        _validate_anchor_binding(component, transition)
    if not region_id and component:
        region_id = component.get("regionId")
    region = next((item for item in model.get("regions", []) if item.get("id") == region_id), None) if region_id else None
    if region:
        _validate_anchor_binding(region, transition)
    if component and component.get("bounds"):
        return _normalized_bounds(component["bounds"])
    if not region:
        raise ValueError("anchor requires a bound component or region")
    return _normalized_bounds(region.get("bounds"))


def _validate_anchor_binding(binding: dict[str, Any], transition: dict[str, Any]) -> None:
    if binding.get("stageId") != transition.get("sourceStageId"):
        raise ValueError("anchor binding must match transition source stage")
    if binding.get("frameId") and transition.get("sourceFrameId") and binding["frameId"] != transition["sourceFrameId"]:
        raise ValueError("anchor binding must match transition source frame")


def _clamped_anchor(model: dict[str, Any], transition: dict[str, Any], anchor: Any) -> dict[str, float]:
    if not isinstance(anchor, dict):
        raise ValueError("anchor must be an object")
    bounds = _anchor_bounds(model, transition)
    try:
        x, y = float(anchor["x"]), float(anchor["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("anchor requires x and y") from exc
    if not isfinite(x) or not isfinite(y):
        raise ValueError("anchor requires finite coordinates")
    return {
        "x": max(bounds["x"], min(bounds["x"] + bounds["width"], x)),
        "y": max(bounds["y"], min(bounds["y"] + bounds["height"], y)),
    }


def _transition_defaults(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _next_id(model["transitions"], "TRN"), "sourceStageId": None, "targetStageId": None,
        "triggerType": "unknown", "triggerLabel": "", "componentId": None, "regionId": None,
        "sourceFrameId": "", "anchor": None, "condition": "", "response": "", "resultType": "unknown",
        "resultState": "", "trueBranchTargetId": None, "falseBranchTargetId": None, "primary": False,
        "included": False, "sourceLevel": "", "confidence": "", "confirmation": {"confirmed": False, "revision": None},
    }


def _validate_transition(model: dict[str, Any], transition: dict[str, Any]) -> None:
    _stage_id(model, transition.get("sourceStageId"), "sourceStageId")
    for field in ("targetStageId", "trueBranchTargetId", "falseBranchTargetId"):
        _stage_id(model, transition.get(field), field, optional=True)
    if transition.get("sourceFrameId") not in (model.get("sources") or {}):
        raise ValueError("invalid sourceFrameId")
    if transition.get("triggerType") not in TRIGGER_TYPES:
        raise ValueError("invalid triggerType")
    if transition.get("resultType") not in RESULT_TYPES:
        raise ValueError("invalid resultType")
    if transition.get("resultType") in _RESULT_TYPES_REQUIRING_TARGET and not transition.get("targetStageId"):
        raise ValueError("targetStageId is required for this resultType")
    component_id, region_id = transition.get("componentId"), transition.get("regionId")
    if component_id and not any(item.get("id") == component_id for item in model.get("components", [])):
        raise ValueError("invalid componentId")
    if region_id and not any(item.get("id") == region_id for item in model.get("regions", [])):
        raise ValueError("invalid regionId")
    if component_id or region_id:
        _anchor_bounds(model, transition)
    if transition.get("anchor") is not None:
        if transition.get("triggerType") not in _ANCHOR_TRIGGERS:
            raise ValueError("automatic transition cannot have an anchor")
        transition["anchor"] = _clamped_anchor(model, transition, transition["anchor"])


def _sync_stage_relationships(model: dict[str, Any]) -> None:
    transitions = model.get("transitions", [])
    regions = model.get("regions", [])
    for stage in model.get("stages", []):
        stage["transitionIds"] = [item["id"] for item in transitions if item.get("sourceStageId") == stage.get("id")]
        stage["regionIds"] = [item["id"] for item in regions if item.get("stageId") == stage.get("id")]


def _renumber_regions(model: dict[str, Any], stage_id: str) -> None:
    regions = [item for item in model.get("regions", []) if item.get("stageId") == stage_id]
    order = {id(item): index for index, item in enumerate(model.get("regions", []))}
    regions.sort(key=lambda item: (item.get("displayOrder", 0), order[id(item)]))
    for index, region in enumerate(regions, 1):
        region["displayOrder"] = index
        region["displayNumber"] = index
    _sync_stage_relationships(model)


def _upsert_region(model: dict[str, Any], operation: dict[str, Any]) -> str:
    payload = operation.get("region")
    if not isinstance(payload, dict):
        raise ValueError("upsert_region requires a region object")
    region_id = payload.get("id")
    existing = next((item for item in model.get("regions", []) if item.get("id") == region_id), None) if region_id else None
    if region_id and not existing:
        raise ValueError(f"unknown region: {region_id}")
    if existing:
        candidate = deepcopy(existing)
        for field in ("name", "bounds", "sourceType", "primary", "rule"):
            if field in payload:
                candidate[field] = deepcopy(payload[field])
        if "stageId" in payload and payload["stageId"] != candidate.get("stageId") or "frameId" in payload and payload["frameId"] != candidate.get("frameId"):
            raise ValueError("region ownership is not editable")
    else:
        stage_id, frame_id = _stage_id(model, payload.get("stageId"), "stageId"), payload.get("frameId")
        candidate = {"id": _next_id(model["regions"], "REG"), "stageId": stage_id, "frameId": frame_id, "name": "region", "sourceType": "human", "primary": False, "rule": {}, "displayOrder": len([item for item in model["regions"] if item.get("stageId") == stage_id]) + 1, "displayNumber": None}
        candidate.update({key: deepcopy(value) for key, value in payload.items() if key in {"name", "bounds", "sourceType", "primary", "rule"}})
    candidate["bounds"] = _region_bounds(candidate.get("bounds"))
    _validate_region_ownership(model, candidate)
    if existing:
        existing.update(candidate)
    else:
        model["regions"].append(candidate)
    _renumber_regions(model, candidate["stageId"])
    return candidate["stageId"]


def _delete_region(model: dict[str, Any], region_id: Any) -> str:
    region = _entity(model, "region", region_id)
    if region.get("primary"):
        raise ValueError("primary region cannot be deleted")
    references = [item.get("id") for item in model.get("transitions", []) if item.get("regionId") == region_id or item.get("componentId") == region_id]
    if references:
        raise ValueError("region is referenced by " + ", ".join(references))
    if any(item.get("regionId") == region_id for item in model.get("components", [])):
        raise ValueError("region is referenced by a component")
    stage_id = region["stageId"]
    model["regions"].remove(region)
    _renumber_regions(model, stage_id)
    return stage_id


def _set_representative_frames(model: dict[str, Any], operation: dict[str, Any]) -> str:
    stage = _entity(model, "stage", operation.get("id", "")); frames = operation.get("frames")
    if error := validate_representative_frames(frames, model.get("sources") or {}):
        raise ValueError(error)
    frame_ids = {item["frameId"] for item in frames}
    if any(region.get("stageId") == stage["id"] and region.get("frameId") not in frame_ids for region in model.get("regions") or []):
        raise ValueError("representative frame change would orphan a stage region; use replace_representative_frame")
    stage["representativeFrames"] = deepcopy(frames)
    return stage["id"]


def _replace_representative_frame(model: dict[str, Any], operation: dict[str, Any]) -> str:
    stage = _entity(model, "stage", operation.get("id", ""))
    old_frame_id, replacement = operation.get("oldFrameId"), operation.get("frame")
    if not isinstance(replacement, dict) or not any(item.get("frameId") == old_frame_id for item in stage.get("representativeFrames") or []):
        raise ValueError("replace_representative_frame requires an existing oldFrameId and replacement frame")
    frames = [deepcopy(item) for item in stage.get("representativeFrames") or [] if item.get("frameId") != old_frame_id]
    frames.append(deepcopy(replacement))
    frames.sort(key=lambda item: ("entry", "change", "result").index(item.get("role")) if item.get("role") in {"entry", "change", "result"} else 99)
    if error := validate_representative_frames(frames, model.get("sources") or {}):
        raise ValueError(error)
    new_frame_id = replacement.get("frameId")
    stage["representativeFrames"] = frames
    source = (model.get("sources") or {}).get(new_frame_id)
    if isinstance(source, dict):
        previous_stage_id = source.get("stageId")
        if previous_stage_id and previous_stage_id != stage["id"]:
            previous_stage = next((item for item in model.get("stages") or [] if item.get("id") == previous_stage_id), None)
            if previous_stage:
                previous_stage["sourceFrameIds"] = [frame_id for frame_id in previous_stage.get("sourceFrameIds", []) if frame_id != new_frame_id]
        source["stageId"] = stage["id"]
        source.setdefault("materialRole", "supplemental")
        if new_frame_id not in stage.setdefault("sourceFrameIds", []):
            stage["sourceFrameIds"].append(new_frame_id)
    for collection in ("regions", "components"):
        for item in model.get(collection) or []:
            if item.get("stageId") == stage["id"] and item.get("frameId") == old_frame_id:
                item["frameId"] = new_frame_id
    for transition in model.get("transitions") or []:
        if transition.get("sourceStageId") == stage["id"] and transition.get("sourceFrameId") == old_frame_id:
            transition["sourceFrameId"] = new_frame_id
    return stage["id"]


def _set_component_state(model: dict[str, Any], operation: dict[str, Any]) -> str:
    component = _entity(model, "component", operation.get("componentId", "")); states = operation.get("states")
    if not isinstance(states, dict):
        raise ValueError("set_component_state requires states")
    normalized = {key: str(states.get(key) or "unknown") for key in COMPONENT_STATE_KEYS}
    existing = next((item for item in model.get("componentStates", []) if item.get("componentId") == component["id"]), None)
    if existing: existing["states"] = normalized
    else: model.setdefault("componentStates", []).append({"id": _next_id(model["componentStates"], "CST"), "componentId": component["id"], "states": normalized})
    return component.get("stageId")


def _upsert_transition(model: dict[str, Any], operation: dict[str, Any]) -> None:
    payload = operation.get("transition")
    if not isinstance(payload, dict):
        raise ValueError("upsert_transition requires a transition object")
    transition_id = payload.get("id")
    existing = next((item for item in model["transitions"] if item.get("id") == transition_id), None) if transition_id else None
    if transition_id and not existing:
        raise ValueError(f"unknown transition: {transition_id}")
    candidate = deepcopy(existing) if existing else _transition_defaults(model)
    for field in _TRANSITION_FIELDS:
        if field in payload:
            candidate[field] = deepcopy(payload[field])
    _validate_transition(model, candidate)
    if existing:
        existing.update(candidate)
    else:
        model["transitions"].append(candidate)
    _sync_stage_relationships(model)


def _upsert_constraint(model: dict[str, Any], operation: dict[str, Any]) -> None:
    payload = operation.get("constraint")
    if not isinstance(payload, dict):
        raise ValueError("upsert_constraint requires a constraint object")
    constraint_id = payload.get("id")
    existing = next((item for item in model["crossStateConstraints"] if item.get("id") == constraint_id), None) if constraint_id else None
    if constraint_id and not existing:
        raise ValueError(f"unknown constraint: {constraint_id}")
    candidate = deepcopy(existing) if existing else {"id": _next_id(model["crossStateConstraints"], "CNS"), "text": "", "severity": "non_core", "status": "unknown"}
    for field in _CONSTRAINT_FIELDS:
        if field in payload:
            candidate[field] = deepcopy(payload[field])
    _validate_constraint(candidate)
    if existing:
        existing.update(candidate)
    else:
        model["crossStateConstraints"].append(candidate)


def _resolve_interaction_decision_card(model: dict[str, Any], operation: dict[str, Any]) -> str:
    card_id = operation.get("cardId")
    card = next((item for item in model.get("interactionDecisionCards") or [] if item.get("id") == card_id), None)
    if not card:
        raise ValueError("unknown interaction decision card")
    transition = _entity(model, "transition", card.get("transitionId", ""))
    option_id = str(operation.get("optionId") or "").strip()
    custom = str(operation.get("customText") or "").strip()
    option = next((item for item in card.get("options") or [] if item.get("id") == option_id), None)
    if bool(option) == bool(custom):
        raise ValueError("choose exactly one interaction operation or custom text")
    if option:
        trigger_type = option.get("triggerType")
        label = str(option.get("label") or "").strip()
    else:
        trigger_type = next((kind for kind, tokens in (
            ("long_press", ("长按",)), ("swipe", ("滑动",)), ("drag", ("拖动", "拖拽")),
            ("tap", ("点击", "点按")), ("system_event", ("自动", "系统")),
        ) if any(token in custom for token in tokens)), "unknown")
        label = custom
    transition["triggerType"] = trigger_type
    transition["triggerLabel"] = label
    _mark_human(transition, "triggerType", "triggerLabel")
    stage = _entity(model, "stage", transition.get("sourceStageId", ""))
    loop = stage.setdefault("smallLoop", {})
    loop["trigger"] = label
    _mark_human(stage, "smallLoop")
    source = (model.get("sources") or {}).get(transition.get("sourceFrameId"))
    if isinstance(source, dict):
        source.setdefault("pageInfo", {})["action"] = label
        edited = source.setdefault("humanEditedFields", [])
        if "pageInfo.action" not in edited:
            edited.append("pageInfo.action")
    card.update({"status": "resolved", "selectedOptionId": option_id or None, "resolvedText": label})
    return stage["id"]


def _validate_constraint(constraint: dict[str, Any]) -> None:
    if constraint.get("severity") not in _CONSTRAINT_SEVERITIES or constraint.get("status") not in _CONSTRAINT_STATUSES:
        raise ValueError("invalid constraint severity or status")


def _upsert_rule(model: dict[str, Any], operation: dict[str, Any]) -> None:
    domain = operation.get("domain")
    payload = operation.get("rule")
    if not isinstance(payload, dict):
        raise ValueError("upsert_rule requires a rule object")
    rules = _rule_list(model, domain)
    rule_id = payload.get("id")
    existing = next((item for item in rules if item.get("id") == rule_id), None) if rule_id else None
    if rule_id and existing is None:
        raise ValueError(f"unknown rule: {rule_id}")
    fields = _rule_payload_fields(payload)
    if existing is None:
        candidate = {field: deepcopy(payload[field]) for field in fields}
        candidate["id"] = _next_rule_id(model, domain, rules)
        candidate["order"] = len(rules) + 1
        _ensure_rule_metadata(candidate)
        _mark_human(candidate, *fields)
        rules.append(candidate)
        return
    _ensure_rule_metadata(existing)
    before = deepcopy(existing)
    candidate = deepcopy(existing)
    candidate.update({field: deepcopy(payload[field]) for field in fields})
    existing.update(candidate)
    _mark_changed_human_fields(existing, before, payload, fields)


def _reorder_rule(model: dict[str, Any], operation: dict[str, Any]) -> None:
    rules = _rule_list(model, operation.get("domain"))
    rule = _rule(model, operation.get("domain"), operation.get("id"))
    destination = max(0, min(_rule_index(operation.get("toIndex"), "reorder_rule"), len(rules) - 1))
    rules.pop(rules.index(rule))
    rules.insert(destination, rule)
    _renumber_rules(rules)
    _mark_human(rule, "order")


def _reorder_rule_nested(model: dict[str, Any], operation: dict[str, Any]) -> None:
    domain, field = operation.get("domain"), operation.get("field")
    expected_field = {"guidance": "steps", "redDots": "path"}.get(domain)
    if field != expected_field:
        raise ValueError("invalid nested rule field")
    rule = _rule(model, domain, operation.get("id"))
    items = rule.get(field)
    if not isinstance(items, list):
        raise ValueError(f"{field} must be a list")
    source = _rule_index(operation.get("fromIndex"), "reorder_rule_nested")
    destination = max(0, min(_rule_index(operation.get("toIndex"), "reorder_rule_nested"), len(items) - 1))
    try:
        item = items.pop(source)
    except IndexError as exc:
        raise ValueError("invalid nested rule reorder") from exc
    items.insert(destination, item)
    _mark_human(rule, field)


def apply_operations(model: dict[str, Any], operations: Any, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    if not isinstance(operations, list) or not all(isinstance(operation, dict) for operation in operations):
        raise ValueError("operations must be a list of objects")
    if not operations:
        return deepcopy(model)
    result = deepcopy(model)
    before = _snapshot(result)
    before_content = _content_snapshot(result)
    flow_changed, changed_stage_ids, legacy_rule_operation = False, set(), False
    for operation in operations:
        operation_type = operation.get("type")
        legacy_rule_operation = legacy_rule_operation or operation_type in RULE_OPERATION_TYPES
        if operation_type == "set":
            target = _entity(result, operation.get("entity", ""), operation.get("id", ""))
            field = operation.get("field")
            if not isinstance(field, str) or not field:
                raise ValueError("set operation requires field")
            if field not in _EDITABLE_FIELDS.get(operation["entity"], set()):
                raise ValueError(f"{operation['entity']}.{field} is not editable")
            value = operation.get("value")
            if field in target and target[field] == value:
                continue
            candidate = deepcopy(target)
            candidate[field] = deepcopy(value)
            if operation["entity"] == "transition":
                _validate_transition(result, candidate)
            elif operation["entity"] == "constraint":
                _validate_constraint(candidate)
            elif operation["entity"] == "region" and field == "bounds":
                candidate[field] = _region_bounds(candidate[field])
            if operation["entity"] == "region":
                _validate_region_ownership(result, candidate)
            target.update(candidate)
            _mark_human(target, field)
            flow_changed = flow_changed or operation["entity"] == "transition"
            if operation["entity"] in {"stage", "region", "component"} and field != "unknowns":
                changed_stage_ids.add(target.get("stageId") or target.get("id"))
            if operation["entity"] == "region":
                _renumber_regions(result, target["stageId"])
        elif operation_type == "upsert_region":
            before_ids = {item.get("id") for item in result["regions"]}
            payload = operation.get("region") or {}
            existing = next((item for item in result["regions"] if item.get("id") == payload.get("id")), None)
            before_region = deepcopy(existing) if existing else {}
            changed_stage_ids.add(_upsert_region(result, operation))
            if region := _new_or_updated(result, "regions", before_ids, payload.get("id")):
                _mark_changed_human_fields(region, before_region, payload, _EDITABLE_FIELDS["region"])
        elif operation_type == "delete_region":
            changed_stage_ids.add(_delete_region(result, operation.get("id", "")))
        elif operation_type == "set_region_bounds":
            region = _entity(result, "region", operation.get("id", "")); _validate_region_ownership(result, region); region["bounds"] = _region_bounds(operation.get("bounds")); _mark_human(region, "bounds"); changed_stage_ids.add(region["stageId"])
        elif operation_type == "reorder_region":
            region = _entity(result, "region", operation.get("id", "")); _validate_region_ownership(result, region); siblings = sorted([item for item in result["regions"] if item.get("stageId") == region["stageId"]], key=lambda item: item.get("displayOrder", 0)); destination = max(0, min(int(operation.get("toIndex")), len(siblings) - 1)); siblings.pop(siblings.index(region)); siblings.insert(destination, region)
            for index, item in enumerate(siblings, 1): item["displayOrder"] = index
            _renumber_regions(result, region["stageId"]); _mark_human(region, "displayOrder"); changed_stage_ids.add(region["stageId"])
        elif operation_type == "set_representative_frames":
            changed_stage_ids.add(_set_representative_frames(result, operation)); _mark_human(_entity(result, "stage", operation.get("id", "")), "representativeFrames")
        elif operation_type == "replace_representative_frame":
            changed_stage_ids.add(_replace_representative_frame(result, operation)); _mark_human(_entity(result, "stage", operation.get("id", "")), "representativeFrames")
        elif operation_type == "set_small_loop":
            stage = _entity(result, "stage", operation.get("id", "")); loop = operation.get("smallLoop")
            if not isinstance(loop, dict): raise ValueError("set_small_loop requires smallLoop")
            stage["smallLoop"] = {key: str(loop.get(key) or "unknown") for key in ("display", "trigger", "feedback", "result", "retry")}; _mark_human(stage, "smallLoop"); changed_stage_ids.add(stage["id"])
        elif operation_type == "set_component_state":
            changed_stage_ids.add(_set_component_state(result, operation)); _mark_human(_entity(result, "component", operation.get("componentId", "")), "states")
        elif operation_type == "move_stage":
            stages = result["stages"]
            try:
                index = next(index for index, stage in enumerate(stages) if stage["id"] == operation["id"])
                to_index = int(operation["toIndex"])
            except (KeyError, StopIteration, TypeError, ValueError) as exc:
                raise ValueError("invalid move_stage operation") from exc
            destination = max(0, min(to_index, len(stages) - 1))
            if index == destination:
                continue
            stage = stages.pop(index)
            stages.insert(destination, stage)
            for order, item in enumerate(stages, 1):
                item["order"] = order; _mark_human(item, "order")
            flow_changed = True
        elif operation_type == "set_transition_included":
            transition = _entity(result, "transition", operation.get("id", ""))
            included = operation.get("included")
            if type(included) is not bool:
                raise ValueError("set_transition_included requires a boolean")
            transition["included"] = included; _mark_human(transition, "included")
            flow_changed = True
        elif operation_type == "upsert_transition":
            payload = operation.get("transition") or {}
            before_ids = {item.get("id") for item in result["transitions"]}
            existing = next((item for item in result["transitions"] if item.get("id") == payload.get("id")), None)
            before_transition = deepcopy(existing) if existing else {}
            _upsert_transition(result, operation)
            if transition := _new_or_updated(result, "transitions", before_ids, payload.get("id")):
                _mark_changed_human_fields(transition, before_transition, payload, _EDITABLE_FIELDS["transition"])
            flow_changed = True
        elif operation_type == "resolve_interaction_decision_card":
            changed_stage_ids.add(_resolve_interaction_decision_card(result, operation))
            flow_changed = True
        elif operation_type == "skip_interaction_decision_card":
            card = next((item for item in result.get("interactionDecisionCards") or [] if item.get("id") == operation.get("cardId")), None)
            if not card:
                raise ValueError("unknown interaction decision card")
            card["status"] = "skipped"
        elif operation_type == "delete_transition":
            transition = _entity(result, "transition", operation.get("id", ""))
            result["transitions"].remove(transition)
            _sync_stage_relationships(result)
            flow_changed = True
        elif operation_type == "merge_stages":
            keep = _entity(result, "stage", operation.get("keepId", ""))
            merged = _entity(result, "stage", operation.get("mergeId", ""))
            if keep["id"] == merged["id"]:
                raise ValueError("merge_stages requires two stages")
            representative_frames, seen_frame_ids = [], set()
            for frame in [*keep.get("representativeFrames", []), *merged.get("representativeFrames", [])]:
                frame_id = frame.get("frameId")
                if frame_id in seen_frame_ids:
                    continue
                seen_frame_ids.add(frame_id)
                representative_frames.append(frame)
            if len(representative_frames) > 3:
                raise ValueError("merge_stages requires at most 3 representative frames; reselect representative frames first")
            rebuilt_representative_frames = representative_frames_for_ids([frame["frameId"] for frame in representative_frames])
            if error := validate_representative_frames(rebuilt_representative_frames, result.get("sources") or {}):
                raise ValueError(error)
            keep["representativeFrames"] = rebuilt_representative_frames
            merged_source_ids = [
                frame_id for frame_id, source in (result.get("sources") or {}).items()
                if isinstance(source, dict) and source.get("stageId") == merged["id"]
            ]
            representative_source_ids = [frame.get("frameId") for frame in representative_frames if frame.get("frameId")]
            keep["sourceFrameIds"] = list(dict.fromkeys([
                *keep.get("sourceFrameIds", []),
                *merged.get("sourceFrameIds", []),
                *merged_source_ids,
                *representative_source_ids,
            ]))
            for frame_id in keep["sourceFrameIds"]:
                source = (result.get("sources") or {}).get(frame_id)
                if isinstance(source, dict) and source.get("stageId") == merged["id"]:
                    source["stageId"] = keep["id"]
            _mark_human(keep, "representativeFrames", "merge")
            for collection in ("regions", "components"):
                for item in result.get(collection, []):
                    if item.get("stageId") == merged["id"]:
                        item["stageId"] = keep["id"]
            for transition in result["transitions"]:
                for field in ("sourceStageId", "targetStageId", "trueBranchTargetId", "falseBranchTargetId"):
                    if transition.get(field) == merged["id"]:
                        transition[field] = keep["id"]
            result["stages"].remove(merged)
            for order, stage in enumerate(result["stages"], 1):
                stage["order"] = order
            _renumber_regions(result, keep["id"])
            flow_changed = True
        elif operation_type == "set_anchor":
            transition = _entity(result, "transition", operation.get("id", ""))
            if transition.get("triggerType") not in _ANCHOR_TRIGGERS:
                raise ValueError("automatic transition cannot have an anchor")
            transition["anchor"] = _clamped_anchor(result, transition, operation.get("anchor")); _mark_human(transition, "anchor")
            flow_changed = True
        elif operation_type == "upsert_constraint":
            payload = operation.get("constraint") or {}
            before_ids = {item.get("id") for item in result["crossStateConstraints"]}
            existing = next((item for item in result["crossStateConstraints"] if item.get("id") == payload.get("id")), None)
            before_constraint = deepcopy(existing) if existing else {}
            _upsert_constraint(result, operation)
            if constraint := _new_or_updated(result, "crossStateConstraints", before_ids, payload.get("id")):
                _mark_changed_human_fields(constraint, before_constraint, payload, _EDITABLE_FIELDS["constraint"])
        elif operation_type == "delete_constraint":
            constraint = _entity(result, "constraint", operation.get("id", ""))
            result["crossStateConstraints"].remove(constraint)
        elif operation_type == "upsert_rule":
            _upsert_rule(result, operation)
        elif operation_type == "delete_rule":
            rules = _rule_list(result, operation.get("domain"))
            rule = _rule(result, operation.get("domain"), operation.get("id"))
            _ensure_next_rule_number(result, operation["domain"], rules)
            rules.remove(rule)
            _renumber_rules(rules)
        elif operation_type == "reorder_rule":
            _reorder_rule(result, operation)
        elif operation_type == "reorder_rule_nested":
            _reorder_rule_nested(result, operation)
        elif operation_type == "mark_rule_domain_reviewed":
            domain = operation.get("domain")
            _rule_list(result, domain)
            reviewed = result["ruleDomains"].setdefault("reviewedDomains", [])
            if domain not in reviewed:
                reviewed.append(domain)
        elif operation_type == "reject_suggestion":
            target = _entity(result, operation.get("entity", ""), operation.get("id", ""))
            field = operation.get("field")
            if not isinstance(field, str) or field not in target.get("suggestions", {}):
                raise ValueError("suggestion not found")
            target["suggestions"].pop(field)
        else:
            raise ValueError(f"unsupported review operation: {operation_type}")
    if errors := validate_review_model(result, include_legacy=legacy_rule_operation):
        raise ValueError("; ".join(errors))
    if result == model:
        return deepcopy(model)
    state = result["reviewState"]
    content_changed = _content_snapshot(result) != before_content
    if content_changed:
        state["previewRevision"] = None
    if legacy_rule_operation and isinstance(result.get("ruleDomains"), dict):
        result["ruleDomains"].setdefault("confirmation", {}).update(confirmed=False, revision=None)
    if flow_changed:
        state.update(status="flow_review", flowConfirmed=False, confirmedStageIds=[])
        for stage in result["stages"]:
            stage["confirmation"] = {"confirmed": False, "revision": None}
        for transition in result["transitions"]:
            transition["confirmation"] = {"confirmed": False, "revision": None}
    else:
        state["confirmedStageIds"] = [stage_id for stage_id in state.get("confirmedStageIds", []) if stage_id not in changed_stage_ids]
        for stage in result["stages"]:
            if stage["id"] in changed_stage_ids:
                stage["confirmation"] = {"confirmed": False, "revision": None}
    history = result.setdefault("editHistory", {"undo": [], "redo": []})
    _remember(history, "undo", before)
    history["redo"] = []
    result["revision"] += 1
    if not content_changed and state.get("previewRevision") == model["revision"]:
        state["previewRevision"] = result["revision"]
    return result


def undo(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result = deepcopy(model)
    history = result.setdefault("editHistory", {"undo": [], "redo": []})
    if not history.get("undo"):
        raise ValueError("nothing to undo")
    before = history["undo"].pop()
    _remember(history, "redo", _snapshot(result))
    result.update(deepcopy(before))
    result["editHistory"] = history
    result["revision"] = model["revision"] + 1
    return result


def redo(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result = deepcopy(model)
    history = result.setdefault("editHistory", {"undo": [], "redo": []})
    if not history.get("redo"):
        raise ValueError("nothing to redo")
    after = history["redo"].pop()
    _remember(history, "undo", _snapshot(result))
    result.update(deepcopy(after))
    result["editHistory"] = history
    result["revision"] = model["revision"] + 1
    return result


def _flow_blockers(model: dict[str, Any]) -> list[str]:
    probe = deepcopy(model)
    probe["reviewState"]["flowConfirmed"] = True
    for stage in probe.get("stages", []):
        stage["confirmation"] = {"confirmed": True, "revision": probe["revision"]}
    for transition in probe.get("transitions", []):
        if transition.get("included"):
            transition["confirmation"] = {"confirmed": True, "revision": probe["revision"]}
    stage_ids = {stage.get("id") for stage in probe.get("stages", [])}
    transition_ids = {transition.get("id") for transition in probe.get("transitions", []) if transition.get("included")}
    return [
        blocker
        for blocker in review_gate(probe)["blockers"]
        if blocker not in stage_ids and blocker not in transition_ids and blocker != "RULE_DOMAINS_NOT_CONFIRMED"
    ]


def _stage_is_confirmable(model: dict[str, Any], stage_id: str) -> bool:
    stage = _entity(model, "stage", stage_id)
    if not 1 <= len(stage.get("representativeFrames") or []) <= 3:
        return False
    probe = deepcopy(model)
    probe["reviewState"]["flowConfirmed"] = True
    for item in probe.get("stages", []):
        item["confirmation"] = {"confirmed": True, "revision": probe["revision"]}
    for transition in probe.get("transitions", []):
        transition["included"] = False
    return stage_id not in review_gate(probe)["blockers"]


def _stage_evidence_blocker(model: dict[str, Any], stage: dict[str, Any]) -> str:
    """Return a planner-facing reason when a stage lacks confirmable evidence."""
    frame_ids = [str(item.get("frameId") or "") for item in stage.get("representativeFrames") or []]
    sources = model.get("sources") or {}
    if not frame_ids or any(not str((sources.get(frame_id) or {}).get("imageUrl") or "").strip() for frame_id in frame_ids):
        return "stage evidence is missing a corresponding image"

    uncertain = re.compile(r"待确认|未知|无明确(?:点击|操作)|可能|推测|猜测|unknown|inferred", re.I)
    observed_actions = []
    for frame_id in frame_ids:
        action = str(((sources.get(frame_id) or {}).get("pageInfo") or {}).get("action") or "").strip()
        if action and not uncertain.search(action):
            observed_actions.append(action)
    for transition in model.get("transitions") or []:
        if transition.get("sourceStageId") != stage.get("id") or not transition.get("included"):
            continue
        label = str(transition.get("triggerLabel") or "").strip()
        source_level = str(transition.get("sourceLevel") or "").strip()
        if transition.get("triggerType") != "unknown" and label and not uncertain.search(label) and source_level not in {"推测", "inferred"}:
            observed_actions.append(label)
    trigger = str((stage.get("smallLoop") or {}).get("trigger") or "").strip()
    if trigger and not uncertain.search(trigger):
        observed_actions.append(trigger)
    return "" if observed_actions else "stage evidence has no explicit observed action"


def confirm_flow(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    if blockers := _flow_blockers(model):
        raise ValueError("cannot confirm flow: " + ", ".join(blockers))
    result = deepcopy(model)
    result["revision"] += 1
    result["reviewState"].update(status="stage_review", flowConfirmed=True, confirmedStageIds=[], previewRevision=None)
    for key in ("ueFlowConfirmed", "ueFlowFingerprint", "ueFlowApprovedFingerprint"):
        result["reviewState"].pop(key, None)
    for stage in result["stages"]:
        stage["confirmation"] = {"confirmed": False, "revision": None}
    for transition in result["transitions"]:
        transition["confirmation"] = {"confirmed": bool(transition.get("included")), "revision": result["revision"] if transition.get("included") else None}
    return result


def confirm_rule_domains(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    domains = model.get("ruleDomains")
    if not isinstance(domains, dict):
        raise ValueError("rule domains must be an object")
    reviewed = domains.get("reviewedDomains")
    if not isinstance(reviewed, list):
        raise ValueError("rule domains reviewedDomains must be a list")
    missing = [domain for domain in RULE_DOMAIN_KEYS if domain not in reviewed]
    if missing:
        raise ValueError(f"rule domains not reviewed: {', '.join(missing)}")
    if errors := validate_review_model(model, include_legacy=True):
        raise ValueError("; ".join(errors))
    result = deepcopy(model)
    result["revision"] += 1
    result["ruleDomains"]["confirmation"] = {"confirmed": True, "revision": result["revision"]}
    result["reviewState"].update(status="rules_confirmed", previewRevision=None)
    return result


def confirm_stage(model: dict[str, Any], stage_id: str, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    stage = _entity(model, "stage", stage_id)
    if error := validate_representative_frames(stage.get("representativeFrames"), model.get("sources") or {}):
        raise ValueError(error)
    for region in model.get("regions") or []:
        if region.get("stageId") == stage_id:
            _validate_region_ownership(model, region)
    if not model.get("reviewState", {}).get("flowConfirmed"):
        raise ValueError("flow must be confirmed before confirming a stage")
    if blocker := _stage_evidence_blocker(model, stage):
        raise ValueError(blocker)
    result = deepcopy(model)
    stage = _entity(result, "stage", stage_id)
    result["revision"] += 1
    stage["confirmation"] = {"confirmed": True, "revision": result["revision"]}
    for region in result.get("regions") or []:
        if region.get("stageId") == stage_id:
            region["confirmation"] = {"confirmed": True, "revision": result["revision"]}
    component_ids = set()
    for component in result.get("components") or []:
        if component.get("stageId") == stage_id:
            component["confirmation"] = {"confirmed": True, "revision": result["revision"]}
            component_ids.add(component.get("id"))
    for item in result.get("componentStates") or []:
        if item.get("componentId") in component_ids:
            item["confirmation"] = {"confirmed": True, "revision": result["revision"]}
    state = result["reviewState"]
    state["confirmedStageIds"] = list(dict.fromkeys([*state.get("confirmedStageIds", []), stage_id]))
    all_confirmed = len(state["confirmedStageIds"]) == len(result["stages"])
    state["status"] = "preview_pending" if all_confirmed else "stage_review"
    if all_confirmed:
        state.pop("ueFlowConfirmed", None)
        state.pop("ueFlowFingerprint", None)
        state.pop("ueFlowApprovedFingerprint", None)
    state["previewRevision"] = None
    return result


def _ue_flow_fingerprint(model: dict[str, Any]) -> str:
    import hashlib
    import json
    stages = []
    for stage in sorted(model.get("stages") or [], key=lambda item: (item.get("order", 0), item.get("id", ""))):
        stages.append({
            "id": stage.get("id"), "order": stage.get("order"), "name": stage.get("name"),
            "entryCondition": stage.get("entryCondition"), "exitCondition": stage.get("exitCondition"),
            "representativeFrames": stage.get("representativeFrames") or [],
        })
    transitions = [{key: item.get(key) for key in (
        "id", "sourceStageId", "targetStageId", "triggerLabel", "triggerType", "sourceFrameId", "included"
    )} for item in sorted(model.get("transitions") or [], key=lambda item: item.get("id", ""))]
    encoded = json.dumps({"stages": stages, "transitions": transitions}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def confirm_ue_flow(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    if not model.get("stages") or not all(stage.get("confirmation", {}).get("confirmed") for stage in model["stages"]):
        raise ValueError("all stages must be confirmed before confirming UE flow")
    current = _ue_flow_fingerprint(model)
    recorded = model.get("reviewState", {}).get("ueFlowFingerprint")
    if recorded != current:
        raise ValueError("UE flow is stale and must be regenerated")
    result = deepcopy(model)
    result["revision"] += 1
    result["reviewState"].update(
        status="preview_ready", ueFlowConfirmed=True,
        ueFlowApprovedFingerprint=current, previewRevision=result["revision"],
    )
    return result
