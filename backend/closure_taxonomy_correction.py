from __future__ import annotations

import copy
from typing import Any


_CORRECTION_STATUSES = {"evidence_unknown", "dormant_optional", "not_applicable",
                        "review_required", "evidence_probe"}
_STRONG_EXCLUSION_BASES = {"contradiction", "mutual_exclusion", "wrong_mechanic_type"}


def apply_closure_taxonomy_corrections(report: dict[str, Any],
                                       corrections: list[dict[str, Any]]) -> dict[str, Any]:
    """Replace legacy not-applicable records with the corrected six-state taxonomy."""
    result = copy.deepcopy(report)
    correction_by_legacy: dict[str, list[dict[str, Any]]] = {}
    for raw in corrections:
        item = copy.deepcopy(raw)
        status = item.get("newStatus")
        if status not in _CORRECTION_STATUSES:
            raise ValueError(f"invalid closure correction status: {status}")
        if status == "not_applicable" and item.get("exclusionBasisType") not in _STRONG_EXCLUSION_BASES:
            raise ValueError("not_applicable requires a strong exclusion basis")
        if status == "review_required" and not item.get("displayText"):
            raise ValueError("review_required correction requires display text")
        correction_by_legacy.setdefault(item["legacyDimensionId"], []).append(item)

    covered: set[str] = set()
    for mechanic in result.get("mechanics", []):
        legacy_items = mechanic.pop("notApplicableDimensions", [])
        mechanic["resolvedDimensions"] = copy.deepcopy(mechanic.get("confirmedRuleDimensions", []))
        mechanic["evidenceUnknownDimensions"] = []
        mechanic["dormantOptionalDimensions"] = []
        mechanic["evidenceProbeDimensions"] = []
        mechanic["notApplicableDimensions"] = []
        for legacy in legacy_items:
            legacy_id = legacy["dimensionId"]
            replacements = correction_by_legacy.get(legacy_id)
            if not replacements:
                raise ValueError(f"legacy not_applicable record lacks correction: {legacy_id}")
            covered.add(legacy_id)
            for replacement in replacements:
                replacement["previousStatus"] = "not_applicable"
                replacement["legacyReason"] = legacy.get("reason")
                replacement["ruleSemanticId"] = mechanic.get("ruleSemanticId")
                if replacement["newStatus"] == "review_required":
                    replacement.setdefault("options", [])
                    replacement.setdefault("controlType", "structured_custom")
                    replacement["approvalStatus"] = "unreviewed"
                    mechanic["reviewRequiredGaps"].append(replacement)
                else:
                    target = {
                        "evidence_unknown": "evidenceUnknownDimensions",
                        "dormant_optional": "dormantOptionalDimensions",
                        "evidence_probe": "evidenceProbeDimensions",
                        "not_applicable": "notApplicableDimensions",
                    }[replacement["newStatus"]]
                    mechanic[target].append(replacement)
        _set_mechanic_closure(mechanic)

    unused = set(correction_by_legacy) - covered
    if unused:
        raise ValueError(f"corrections reference unknown legacy records: {sorted(unused)}")
    result["metrics"] = calculate_active_closure_metrics(result)
    result["taxonomy"] = ["resolved", "evidence_resolvable", "review_required",
                          "evidence_unknown", "dormant_optional", "not_applicable"]
    result["auxiliaryAuditTracks"] = ["evidence_probe"]
    return result


def calculate_active_closure_metrics(report: dict[str, Any]) -> dict[str, Any]:
    resolved = sum(len(item.get("resolvedDimensions", item.get("confirmedRuleDimensions", [])))
                   for item in report.get("mechanics", []))
    evidence_resolvable = sum(len(item.get("evidenceResolvableGaps", []))
                              for item in report.get("mechanics", []))
    review_required = sum(len(item.get("reviewRequiredGaps", []))
                          for item in report.get("mechanics", []))
    evidence_unknown = sum(len(item.get("evidenceUnknownDimensions", []))
                           for item in report.get("mechanics", []))
    dormant_optional = sum(len(item.get("dormantOptionalDimensions", []))
                           for item in report.get("mechanics", []))
    true_not_applicable = sum(len(item.get("notApplicableDimensions", []))
                              for item in report.get("mechanics", []))
    evidence_probe = sum(len(item.get("evidenceProbeDimensions", []))
                         for item in report.get("mechanics", []))
    active = resolved + evidence_resolvable + review_required
    return {
        "activeExecutionDimensions": active,
        "resolved": resolved,
        "evidenceResolvable": evidence_resolvable,
        "reviewRequired": review_required,
        "evidenceUnknown": evidence_unknown,
        "dormantOptional": dormant_optional,
        "trueNotApplicable": true_not_applicable,
        "evidenceProbe": evidence_probe,
        "unknownMechanicDetailCount": evidence_unknown,
        "activeClosureRate": round(100 * resolved / active, 2) if active else 0.0,
    }


def _set_mechanic_closure(mechanic: dict[str, Any]) -> None:
    resolved = len(mechanic.get("resolvedDimensions", []))
    open_active = len(mechanic.get("evidenceResolvableGaps", [])) + len(mechanic.get("reviewRequiredGaps", []))
    active = resolved + open_active
    score = round(100 * resolved / active, 2) if active else 0.0
    mechanic["closureScore"] = score
    mechanic["closureStatus"] = "closed" if open_active == 0 else (
        "open" if score < 50 else "partially_closed")
