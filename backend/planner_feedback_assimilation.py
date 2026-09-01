"""Revisioned Planner Feedback operations over structured ApprovedData.

Feedback text is never treated as project evidence.  Only reviewed, typed
project operations may alter the derived ApprovedData used by publication.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PROJECT_SCOPE = "project_feedback"
SYSTEM_SCOPE = "system_feedback"
SUPPORTED_OPERATIONS = {
    "patch_rule_intent", "move_rule_schema_slot", "set_canonical_owner",
    "upsert_gap", "resolve_gap", "patch_parameter", "mark_evidence_required",
}
VERIFICATION_STATUSES = {
    "fully_reflected", "partially_reflected", "system_only", "project_only",
    "registered_only", "regressed", "not_reflected", "not_applicable",
}


def build_feedback_trace(records: list[dict[str, Any]], *, last_verified_revision: int) -> dict[str, Any]:
    """Build a lightweight audit trace without reading or mutating Rule authority."""
    normalized = []
    for source in deepcopy(records):
        feedback_id = str(source.get("feedbackId") or "")
        status = str(source.get("verificationStatus") or "")
        if not feedback_id or status not in VERIFICATION_STATUSES:
            raise ValueError("feedback trace requires feedbackId and valid verificationStatus")
        affected = source.get("affected") or {}
        normalized.append({
            "feedbackId": feedback_id,
            "affected": {
                "policyIds": list(affected.get("policyIds") or []),
                "ruleIds": list(affected.get("ruleIds") or []),
                "gapIds": list(affected.get("gapIds") or []),
                "testIds": list(affected.get("testIds") or []),
                "finalAnchors": list(affected.get("finalAnchors") or []),
            },
            "verificationStatus": status,
            "lastVerifiedRevision": int(last_verified_revision),
        })
    return {"schemaVersion": "feedback-trace-v1", "records": normalized}


def _find(items: list[dict[str, Any]], key: str, value: Any, label: str) -> dict[str, Any]:
    item = next((candidate for candidate in items if candidate.get(key) == value), None)
    if item is None:
        raise ValueError(f"feedback target {label} does not exist: {value}")
    return item


def _operation_status(feedback: dict[str, Any], operation: dict[str, Any]) -> str:
    status = str(operation.get("status") or "proposed")
    if feedback.get("reviewStatus") not in {"approved", "confirmed"}:
        return "proposed"
    return status


def _lineage(
    feedback: dict[str, Any], operation: dict[str, Any], before: dict[str, Any], after: dict[str, Any], revision: int,
) -> dict[str, Any]:
    return {
        "feedbackId": feedback["feedbackId"],
        "operationId": operation["operationId"],
        "operation": operation["operationType"],
        "targetRuleId": operation.get("targetRuleId"),
        "schemaResponsibility": operation.get("schemaResponsibility"),
        "before": before, "after": after,
        "sourceRevision": feedback.get("sourceRevision"),
        "appliedRevision": revision,
    }


def _apply_operation(
    data: dict[str, Any], feedback: dict[str, Any], operation: dict[str, Any], revision: int,
) -> dict[str, Any]:
    kind = operation.get("operationType")
    if kind not in SUPPORTED_OPERATIONS:
        raise ValueError(f"unsupported feedback operation: {kind}")
    after = deepcopy(operation.get("after") or {})
    if kind in {"patch_rule_intent", "move_rule_schema_slot", "set_canonical_owner"}:
        rule = _find(data.setdefault("rules", []), "ruleId", operation.get("targetRuleId"), "rule")
        fields = {
            "patch_rule_intent": ("intent",),
            "move_rule_schema_slot": ("schemaSlot",),
            "set_canonical_owner": ("canonicalOwner",),
        }[kind]
        before = {field: deepcopy(rule.get(field)) for field in fields}
        for field in fields:
            if field not in after:
                raise ValueError(f"feedback operation {kind} requires {field}")
            rule[field] = deepcopy(after[field])
        if kind == "patch_rule_intent":
            rule["intentAuthority"] = "planner_confirmed_feedback"
            rule["intentFeedbackId"] = feedback.get("feedbackId")
            rule["intentFeedbackOperationId"] = operation.get("operationId")
        normalized_after = {field: deepcopy(rule.get(field)) for field in fields}
    elif kind == "patch_parameter":
        parameter = _find(data.setdefault("parameters", []), "parameterId", operation.get("targetParameterId"), "parameter")
        before = {field: deepcopy(parameter.get(field)) for field in after}
        parameter.update(deepcopy(after)); normalized_after = {field: deepcopy(parameter.get(field)) for field in after}
    elif kind == "resolve_gap":
        gap = _find(data.setdefault("gaps", []), "gapId", operation.get("targetGapId"), "gap")
        after = after or {"status": "resolved"}
        before = {field: deepcopy(gap.get(field)) for field in after}
        gap.update(deepcopy(after)); normalized_after = {field: deepcopy(gap.get(field)) for field in after}
    else:
        gap = deepcopy(after)
        if not gap.get("gapId"):
            raise ValueError(f"feedback operation {kind} requires gapId")
        existing = next((item for item in data.setdefault("gaps", []) if item.get("gapId") == gap["gapId"]), None)
        before = deepcopy(existing) if existing else {}
        gap.setdefault("status", "open")
        gap.setdefault("gapDomain", "planning")
        gap.setdefault("inferencePermission", "evidence_required")
        gap.setdefault("feedbackId", feedback["feedbackId"])
        if existing is None:
            data["gaps"].append(gap)
        else:
            existing.update(gap)
        normalized_after = deepcopy(gap)
    return _lineage(feedback, operation, before, normalized_after, revision)


def assimilate_planner_feedback(approved_data: dict[str, Any]) -> dict[str, Any]:
    effective = deepcopy(approved_data)
    feedbacks = [item for item in effective.get("plannerFeedback") or [] if isinstance(item, dict)]
    proposed: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    existing_lineage = list(effective.get("feedbackLineage") or [])
    applied_ids = {str(item.get("operationId")) for item in existing_lineage}
    pending_apply: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for feedback in feedbacks:
        feedback_id = feedback.get("feedbackId")
        scope = feedback.get("scope")
        if not feedback_id or scope not in {PROJECT_SCOPE, SYSTEM_SCOPE}:
            raise ValueError("planner feedback requires feedbackId and valid scope")
        operations = [deepcopy(item) for item in feedback.get("requestedOperations") or [] if isinstance(item, dict)]
        if scope == SYSTEM_SCOPE:
            candidates.append({
                "candidateId": f"ARCH-{feedback_id}", "feedbackId": feedback_id,
                "status": "review_required", "text": feedback.get("text"),
                "suggestedOperations": operations, "sourceRevision": feedback.get("sourceRevision"),
            })
            continue
        for operation in operations:
            if not operation.get("operationId") or not operation.get("operationType"):
                raise ValueError("feedback operation requires operationId and operationType")
            operation.update({"feedbackId": feedback_id, "scope": scope, "status": _operation_status(feedback, operation)})
            if operation["status"] in {"approved", "confirmed"} and operation["operationId"] not in applied_ids:
                pending_apply.append((feedback, operation))
            elif operation["status"] == "proposed":
                proposed.append(operation)
    revision = int(effective.get("feedbackRevision") or 0) + (1 if pending_apply else 0)
    for feedback, operation in pending_apply:
        lineage = _apply_operation(effective, feedback, operation, revision)
        existing_lineage.append(lineage)
        applied.append({**operation, "lineage": deepcopy(lineage)})
    effective["feedbackRevision"] = revision
    effective["feedbackLineage"] = existing_lineage
    return {
        "effectiveApprovedData": effective,
        "proposedOperations": proposed,
        "appliedOperations": applied,
        "architectureImprovementCandidates": candidates,
        "lineage": existing_lineage,
    }
