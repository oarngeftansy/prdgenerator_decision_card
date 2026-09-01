from __future__ import annotations

import hashlib
from typing import Any, Iterable


SEPARATORS = ("、", "/", "与", "和", "+", "&")
GENERIC_CONTAINER_TITLES = frozenset({"综合规则", "综合系统", "其他规则", "通用规则", "功能集合"})


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16].upper()}"


def evaluate_composite_title(title: str, *,
                             business_concept_evidence_refs: Iterable[str] = ()) -> dict[str, Any]:
    refs = list(business_concept_evidence_refs)
    matched = [separator for separator in SEPARATORS if separator in title]
    exempted = bool(matched and refs)
    return {
        "allowed": not matched or exempted,
        "matchedSeparators": matched,
        "businessConceptExempted": exempted,
        "businessConceptEvidenceRefs": refs,
        "reason": ("confirmed_business_concept" if exempted else
                   "composite_peer_title" if matched else "single_title"),
    }


def evaluate_single_responsibility(node: dict[str, Any]) -> dict[str, Any]:
    findings = []
    kinds = list(dict.fromkeys(node.get("responsibilityKinds", [])))
    responsibility = node.get("responsibility")
    if len(kinds) > 1 or responsibility == "mixed_peer_mechanics":
        findings.append("mixed_peer_responsibilities")
    if responsibility == "generic_container" or node.get("title") in GENERIC_CONTAINER_TITLES:
        findings.append("generic_container")
    if node.get("parentChildValid") is False:
        findings.append("invalid_parent_child_responsibility")
    if not responsibility and not kinds:
        findings.append("responsibility_undefined")
    return {"singleResponsibility": not findings, "findings": findings,
            "responsibilityKinds": kinds}


def evaluate_planning_title_quality(node: dict[str, Any]) -> dict[str, Any]:
    composite = evaluate_composite_title(
        str(node["title"]),
        business_concept_evidence_refs=node.get("businessConceptEvidenceRefs", ()),
    )
    responsibility = evaluate_single_responsibility(node)
    return {"allowed": composite["allowed"] and responsibility["singleResponsibility"],
            "compositeCheck": composite, "singleResponsibilityCheck": responsibility}


def normalize_planning_hierarchy(review_units: Iterable[dict[str, Any]],
                                 owner_assignments: Iterable[dict[str, Any]]) -> dict[str, Any]:
    review_units = list(review_units)
    assignments_input = list(owner_assignments)
    by_item: dict[str, list[dict[str, Any]]] = {}
    for assignment in assignments_input:
        if assignment.get("designItemId"):
            by_item.setdefault(assignment["designItemId"], []).append(assignment)

    item_context = {}
    for unit in review_units:
        for item in unit.get("recommendedDesign", []):
            item_context[item["designItemId"]] = (unit, item)

    duplicate_count = sum(len(items) - 1 for items in by_item.values() if len(items) > 1)
    mapped = {}
    unmapped = []
    node_by_path: dict[tuple[str, ...], dict[str, Any]] = {}
    title_findings = []
    owner_findings = []
    for design_item_id, (unit, item) in item_context.items():
        candidates = by_item.get(design_item_id, [])
        if len(candidates) != 1:
            unmapped.append(design_item_id)
            continue
        assignment = candidates[0]
        path = tuple(assignment.get("ownerPath", []))
        if not path:
            unmapped.append(design_item_id)
            continue
        for depth in range(1, len(path) + 1):
            partial = path[:depth]
            title = partial[-1]
            quality = evaluate_planning_title_quality({
                "title": title, "responsibilityKinds": ["owner_node"],
                "responsibility": "owner_node",
                "businessConceptEvidenceRefs": assignment.get("businessConceptEvidenceRefs", []),
            })
            if not quality["allowed"]:
                title_findings.append({"ownerPath": list(partial), "title": title, **quality})
            node = node_by_path.setdefault(partial, {
                "planningNodeId": _stable_id("PNODE", *partial), "title": title,
                "ownerPath": list(partial),
                "nodeRole": ("system" if depth == 1 else "subsystem" if depth < len(path)
                             else "mechanic_responsibility"),
                "sourceDesignItemIds": [], "sourceRuleIds": [],
                "sourceReviewUnitIds": [], "ownerEvidenceRefs": [], "designItemSummaries": [],
                "planningOrder": assignment.get("planningOrder", 1000),
            })
            if depth == len(path):
                node["sourceDesignItemIds"].append(design_item_id)
                node["sourceRuleIds"].extend(item.get("confirmedRuleIds", []))
                node["sourceReviewUnitIds"].append(unit["mechanicDesignId"])
                node["ownerEvidenceRefs"].extend(assignment.get("ownerEvidenceRefs", []))
                node["designItemSummaries"].append(item["text"])
                node["planningOrder"] = min(node["planningOrder"], assignment.get("planningOrder", 1000))
        leaf = node_by_path[path]
        mapped[design_item_id] = {
            "planningNodeId": leaf["planningNodeId"], "ownerPath": list(path),
            "ownerEvidenceRefs": list(assignment.get("ownerEvidenceRefs", [])),
        }
        signals = assignment.get("ownerSignals", [])
        signal_paths = {tuple(signal.get("ownerPath", [])) for signal in signals if signal.get("ownerPath")}
        signal_types = {signal.get("ownerType") for signal in signals}
        if len(signal_paths) > 1 and len(signal_types) > 1:
            owner_findings.append({
                "type": "mixed_owner_responsibilities", "designItemId": design_item_id,
                "assignedOwnerPath": list(path), "ownerSignals": signals, "ownerChanged": False,
                "recommendation": "revisit_in_future_hierarchy_audit",
            })

    for assignment in [item for item in assignments_input if not item.get("designItemId")]:
        path = tuple(assignment.get("ownerPath", []))
        if not path:
            continue
        for depth in range(1, len(path) + 1):
            partial = path[:depth]
            node = node_by_path.setdefault(partial, {
                "planningNodeId": _stable_id("PNODE", *partial), "title": partial[-1],
                "ownerPath": list(partial),
                "nodeRole": ("system" if depth == 1 else "subsystem" if depth < len(path)
                             else "mechanic_responsibility"),
                "sourceDesignItemIds": [], "sourceRuleIds": [], "sourceReviewUnitIds": [],
                "ownerEvidenceRefs": [], "designItemSummaries": [],
                "planningOrder": assignment.get("planningOrder", 1000),
            })
            if depth == len(path):
                node["sourceRuleIds"].extend(assignment.get("sourceRuleIds", []))
                if assignment.get("sourceReviewUnitId"):
                    node["sourceReviewUnitIds"].append(assignment["sourceReviewUnitId"])
                node["ownerEvidenceRefs"].extend(assignment.get("ownerEvidenceRefs", []))
                if assignment.get("contentSummary"):
                    node["designItemSummaries"].append(assignment["contentSummary"])
                node["planningOrder"] = min(node["planningOrder"], assignment.get("planningOrder", 1000))

    for node in node_by_path.values():
        for key in ("sourceDesignItemIds", "sourceRuleIds", "sourceReviewUnitIds", "ownerEvidenceRefs"):
            node[key] = list(dict.fromkeys(node[key]))
    total = len(item_context)
    assignment_rate = round(len(mapped) / total * 100, 1) if total else 100.0
    return {
        "reviewHierarchy": [{"reviewUnitId": unit["mechanicDesignId"],
                             "reviewTitle": unit.get("reviewTitle", unit["planningTitle"]),
                             "designItemIds": [item["designItemId"] for item in unit.get("recommendedDesign", [])]}
                            for unit in review_units],
        "planningNodes": sorted(node_by_path.values(), key=lambda node: (len(node["ownerPath"]), node["ownerPath"])),
        "assignments": mapped, "compositeTitleFindings": title_findings,
        "ownerStructureFindings": owner_findings, "unmappedDesignItemIds": sorted(unmapped),
        "metrics": {"designItemCount": total, "assignedDesignItemCount": len(mapped),
                    "assignmentRate": assignment_rate,
                    "duplicatePrimaryPlanningNodeCount": duplicate_count,
                    "compositePlanningTitleCount": len(title_findings),
                    "ownerStructureFindingCount": len(owner_findings),
                    "gatePassed": not unmapped and not duplicate_count and not title_findings},
    }
