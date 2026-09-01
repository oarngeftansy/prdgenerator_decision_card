from __future__ import annotations

import hashlib
from typing import Any


_OBSERVABLE = {"directly_observed", "strongly_supported"}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _validate_observation(item: dict[str, Any]) -> None:
    status = item.get("observationStatus")
    if status not in _OBSERVABLE | {"ambiguous", "not_observable"}:
        raise ValueError(f"invalid observationStatus: {status}")
    if status in _OBSERVABLE:
        refs = item.get("evidenceRefs", [])
        if not refs:
            raise ValueError("observable dimension requires evidenceRefs")
        for ref in refs:
            if not ref.get("evidenceId"):
                raise ValueError("evidenceRef requires evidenceId")
            if not ref.get("sourcePath"):
                raise ValueError("evidenceRef requires sourcePath")


def build_evidence_coverage_matrix(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a read-only coverage report; this function never promotes a Fact or Rule."""
    matrix: list[dict[str, Any]] = []
    fact_candidates: list[dict[str, Any]] = []
    rule_candidates: list[dict[str, Any]] = []
    for raw in observations:
        _validate_observation(raw)
        item = dict(raw)
        status = item["observationStatus"]
        observable = status in _OBSERVABLE
        extracted = bool(item.get("alreadyExtracted"))
        item["observable"] = observable
        item["newlyExtracted"] = observable and not extracted
        matrix.append(item)
        if item["newlyExtracted"]:
            base = {
                "candidateId": _stable_id("EVCAND", item["observationDimension"]),
                "observationDimension": item["observationDimension"],
                "mechanic": item.get("mechanic"),
                "candidateText": item.get("observedText", ""),
                "evidenceStatus": status,
                "evidenceRefs": item["evidenceRefs"],
                "approvalStatus": "candidate_only",
            }
            fact_candidates.append({**base, "candidateType": "fact"})
            if item.get("ruleCandidateText"):
                rule_candidates.append({
                    **base,
                    "candidateId": _stable_id("RLCAND", item["observationDimension"]),
                    "candidateType": "rule",
                    "candidateText": item["ruleCandidateText"],
                })

    observable = [item for item in matrix if item["observable"]]
    extracted = [item for item in observable if item.get("alreadyExtracted")]
    missed = [item for item in observable if not item.get("alreadyExtracted")]
    metrics = {
        "observableDimensions": len(observable),
        "extractedObservableDimensions": len(extracted),
        "missedObservableDimensions": len(missed),
        "ambiguousDimensions": sum(item["observationStatus"] == "ambiguous" for item in matrix),
        "unobservableDimensions": sum(item["observationStatus"] == "not_observable" for item in matrix),
        "observableExtractionCoverage": round(len(extracted) / len(observable), 4) if observable else 1.0,
    }
    return {"matrix": matrix, "metrics": metrics,
            "newFactCandidates": fact_candidates, "newRuleCandidates": rule_candidates}


_NATURAL_CLOSURES = {
    "resume_combat": "natural_gameplay_closure",
    "contact_damage_mode": "confirmed_rule_already_determines_player_visible_result",
    "contact_damage_interval": "parent_mechanic_not_evidenced",
}
_KEEP_PARAMETERS = {"movement_speed", "attack_range", "attack_interval", "damage_model",
                    "growth_source", "upgrade_basis", "candidate_eligibility"}


def evaluate_default_closure(
    review_decisions: list[dict[str, Any]],
    evidence_resolutions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Route pending decisions without treating unknown or theoretical variability as a gap."""
    items: list[dict[str, Any]] = []
    for decision in review_decisions:
        key = decision.get("decisionKey", "")
        disposition = "defer"
        reason = "no_material_player_facing_branch_proven"
        if key in _NATURAL_CLOSURES:
            disposition, reason = "suppress", _NATURAL_CLOSURES[key]
        elif key == "weapon_slot_capacity" and key in evidence_resolutions:
            disposition, reason = "evidence_candidate", "visible_slot_count_resolves_numeric_pending"
        elif key == "displayed_data" and key in evidence_resolutions:
            disposition, reason = "evidence_candidate", "settlement_screen_directly_lists_results"
        elif key == "time_limit" and "elapsed_time_not_limit" in evidence_resolutions:
            disposition, reason = "upstream_conflict", "hud_value_matches_clear_time_not_time_limit"
        elif key == "refresh_rule" and "refresh_rule" in evidence_resolutions:
            disposition, reason = "evidence_candidate", "visible_ad_refresh_path_replaces_unsupported_resource_claim"
        elif key in {"refresh_resource_type", "refresh_cost_amount"} and "refresh_rule" in evidence_resolutions:
            disposition, reason = "suppress", "resource_payment_path_not_evidenced"
        elif key in _KEEP_PARAMETERS:
            disposition, reason = "keep", "material_gameplay_rule_or_parameter_remains_unresolved"
        elif decision.get("route") == "Suppress":
            disposition, reason = "suppress", "already_suppressed"
        elif decision.get("route") == "Evidence Recheck":
            disposition, reason = "evidence_recheck", "observable_outcome_should_be_rechecked_before_planner_review"
        elif decision.get("dependency"):
            disposition, reason = "suppress", "parent_mechanic_not_evidenced"
        items.append({
            "decisionId": decision.get("decisionId"),
            "decisionKey": key,
            "existingRoute": decision.get("route"),
            "disposition": disposition,
            "gateReason": reason,
        })
    counts: dict[str, int] = {}
    for item in items:
        counts[item["disposition"]] = counts.get(item["disposition"], 0) + 1
    return {"items": items, "counts": counts}
