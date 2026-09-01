from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, Iterable


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16].upper()}"


def synthesize_mechanic_design(*, mechanic_spec: dict[str, Any],
                               proposals: Iterable[dict[str, Any]],
                               confirmed_rules: Iterable[dict[str, Any]] = (),
                               parameter_placeholders: Iterable[dict[str, Any]] = (),
                               rule_references: Iterable[dict[str, Any]] = (),
                               atomic_primary_owners: dict[str, list[str]] | None = None) -> dict[str, Any]:
    proposals = list(proposals)
    proposal_by_id = {item["proposalId"]: item for item in proposals}
    mechanic_id = mechanic_spec["mechanicId"]
    for proposal_id, owners in (atomic_primary_owners or {}).items():
        if len(set(owners)) != 1 or owners[0] != mechanic_id:
            raise ValueError(f"atomic proposal {proposal_id} must have exactly one primary owner")

    design_items = []
    compatibility = []
    for raw in sorted(mechanic_spec.get("items", []), key=lambda item: item["sequence"]):
        source_ids = list(raw.get("proposalIds", []))
        sources = [proposal_by_id[item] for item in source_ids]
        requirement_ids = list(dict.fromkeys(
            requirement_id for source in sources
            if (requirement_id := source.get("originRequirementId"))))
        knowledge_class = raw.get("knowledgeClass") or (
            "confirmed" if raw.get("confirmedRuleIds") else
            "alternative_design" if any(source.get("proposalType") == "alternative_design" for source in sources)
            else "design_inference"
        )
        conflicts = list(raw.get("conflictingConfirmedRefs", []))
        if conflicts:
            compatibility.append({"type": "confirmed_content_conflict",
                                  "designItemSequence": raw["sequence"], "conflictingRefs": conflicts})
        design_items.append({
            "designItemId": _stable_id("MDI", mechanic_id, raw["sequence"], *source_ids),
            "sequence": raw["sequence"], "text": raw["text"], "role": raw.get("role"),
            "completenessRoles": list(raw.get("completenessRoles") or ([raw["role"]] if raw.get("role") else [])),
            "knowledgeClass": knowledge_class, "sourceProposalIds": source_ids,
            "requirementIds": requirement_ids,
            "parameterRefs": list(raw.get("parameterRefs", [])), "approvalState": "pending_review",
            "confirmedRuleIds": list(raw.get("confirmedRuleIds", [])),
            "publicationEligible": False,
        })

    parameters = list(parameter_placeholders)
    coherence = []
    for parameter in parameters:
        if not parameter.get("consumerMechanicId"):
            coherence.append({"type": "parameter_consumer_missing", "parameterId": parameter.get("parameterId")})
    roles = {role for item in design_items for role in item["completenessRoles"]}
    applicable = list(mechanic_spec.get("applicableRoles", []))
    missing = [role for role in applicable if role not in roles]
    completeness = round((len(applicable) - len(missing)) / len(applicable) * 100, 1) if applicable else 100.0
    eligibility = "needs_design_decision" if compatibility or coherence else "ready"
    proposal_ids = list(dict.fromkeys(pid for item in design_items for pid in item["sourceProposalIds"]))
    requirement_ids = list(dict.fromkeys(rid for item in design_items for rid in item["requirementIds"]))
    evidence_refs = list(dict.fromkeys(ref for proposal in proposals for ref in proposal.get("knownContextRefs", [])))
    return {
        "mechanicDesignId": mechanic_spec["mechanicDesignId"], "mechanicId": mechanic_id,
        "planningTitle": mechanic_spec["planningTitle"],
        "reviewTitle": mechanic_spec.get("reviewTitle", mechanic_spec["planningTitle"]),
        "ownerPath": list(mechanic_spec["ownerPath"]),
        "confirmedRules": list(confirmed_rules), "recommendedDesign": design_items,
        "designInferences": [item for item in design_items if item["knowledgeClass"] == "design_inference"],
        "parameterPlaceholders": parameters, "designDecisions": list(mechanic_spec.get("designDecisions", [])),
        "ruleReferences": list(rule_references), "atomicProposalIds": proposal_ids,
        "requirementIds": requirement_ids, "evidenceRefs": evidence_refs,
        "coherenceFindings": coherence, "compatibilityFindings": compatibility,
        "unclosedLifecycleSlots": missing,
        "executionCompleteness": {"applicableRoleCount": len(applicable),
                                  "satisfiedRoleCount": len(applicable) - len(missing),
                                  "score": completeness},
        "reviewEligibility": eligibility, "confirmed": False, "resolved": False,
        "publicationEligible": False,
    }


def build_mechanic_review_view(synthesis: dict[str, Any], *, expand_lineage: bool = False) -> dict[str, Any]:
    view = {
        "mechanicDesignId": synthesis["mechanicDesignId"],
        "title": synthesis.get("reviewTitle", synthesis["planningTitle"]), "ownerPath": synthesis["ownerPath"],
        "confirmedRules": synthesis["confirmedRules"],
        "recommendedDesign": [{key: item[key] for key in
                               ("designItemId", "sequence", "text", "knowledgeClass", "approvalState")}
                              for item in synthesis["recommendedDesign"]],
        "designInferences": [item["designItemId"] for item in synthesis["designInferences"]],
        "parameterPlaceholders": synthesis["parameterPlaceholders"],
        "designDecisions": synthesis["designDecisions"],
        "reviewEligibility": synthesis["reviewEligibility"],
        "executionCompleteness": synthesis["executionCompleteness"],
        "actions": ["accept_mechanic", "edit", "reject", "expand_evidence"],
        "approvalGranularity": "design_item",
        "acceptMechanicEffect": "batch_review_decisions_not_rule_merge",
        "publicationEligible": False,
    }
    if expand_lineage:
        view["lineage"] = {
            "proposalIds": synthesis["atomicProposalIds"],
            "requirementIds": synthesis["requirementIds"],
            "evidenceRefs": synthesis["evidenceRefs"],
            "items": [{"designItemId": item["designItemId"],
                       "proposalIds": item["sourceProposalIds"],
                       "requirementIds": item["requirementIds"]}
                      for item in synthesis["recommendedDesign"]],
        }
    return view


def accept_mechanic_design(
    synthesis: dict[str, Any], *,
    accepted_text_by_design_item: dict[str, str] | None = None,
    dimension_by_requirement: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Batch-accept a review unit while preserving one Rule per design item."""
    if synthesis.get("reviewEligibility") != "ready":
        raise ValueError("mechanic design is not ready for review acceptance")
    accepted_text_by_design_item = accepted_text_by_design_item or {}
    dimension_by_requirement = dimension_by_requirement or {}
    updated = deepcopy(synthesis)
    rules = []
    closure = {}
    forbidden_review_language = ("待确认", "仍需确认", "AI建议", "AI推演", "推荐方案")
    for item in updated.get("recommendedDesign", []):
        text = accepted_text_by_design_item.get(item["designItemId"], item["text"]).strip()
        if any(term in text for term in forbidden_review_language):
            raise ValueError(f"approved rule contains review language: {item['designItemId']}")
        requirement_ids = list(item.get("requirementIds", []))
        digest = hashlib.sha256(
            f"{item['designItemId']}:accept_mechanic:{text}".encode("utf-8")
        ).hexdigest()[:12].upper()
        rules.append({
            "ruleId": f"RULE-{digest}",
            "mechanicId": synthesis.get("mechanicId", synthesis["mechanicDesignId"]),
            "valid": True, "ruleStatus": "approved_review",
            "sourceType": "planner_approved_mechanic_design",
            "sourceDesignItemId": item["designItemId"],
            "sourceProposalIds": list(item.get("sourceProposalIds", [])),
            "text": text,
            "dimensionIds": [dimension_by_requirement[requirement_id]
                             for requirement_id in requirement_ids
                             if requirement_id in dimension_by_requirement],
            "originRequirementIds": requirement_ids,
            "satisfiesRequirementIds": requirement_ids,
            "approvalAction": "accept_mechanic",
            "planningNodeId": item.get("planningNodeId"),
            "planningOwnerPath": list(item.get("planningOwnerPath", [])),
        })
        item["approvalState"] = "approved"
        item["approvedRuleId"] = rules[-1]["ruleId"]
        for requirement_id in requirement_ids:
            closure[requirement_id] = "resolved"
    return {"mechanicDesignId": synthesis["mechanicDesignId"],
            "approvalAction": "accept_mechanic", "approvedRules": rules,
            "requirementClosureOverlay": closure, "updatedSynthesis": updated,
            "publicationEligible": False}
