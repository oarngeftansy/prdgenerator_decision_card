from __future__ import annotations

import copy
from typing import Any


_DISPOSITIONS = {"evidence_resolvable", "review_required", "not_applicable"}


def audit_execution_rule_closure(contracts: list[dict[str, Any]],
                                 closure_specs: list[dict[str, Any]]) -> dict[str, Any]:
    specs = {item["ruleSemanticId"]: item for item in closure_specs}
    mechanics: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for contract in contracts:
        mechanic_spec = specs.get(contract["ruleSemanticId"], {})
        confirmed_rules = [dict(item) for item in contract.get("confirmedCoreRule", [])]
        confirmed_dimensions = [dict(item) for item in contract.get("requiredRuleDimensions", [])
                                if item.get("status") == "observed"]
        evidence_resolvable = []
        review_required = []
        not_applicable = []
        for raw in mechanic_spec.get("dimensions", []):
            item = copy.deepcopy(raw)
            disposition = item.get("disposition")
            if disposition not in _DISPOSITIONS:
                rejected.append({**item, "ruleSemanticId": contract["ruleSemanticId"],
                                 "reason": "invalid_gap_disposition"})
                continue
            item["ruleSemanticId"] = contract["ruleSemanticId"]
            if disposition == "evidence_resolvable":
                if not item.get("basis") or not item.get("candidateRule"):
                    rejected.append({**item, "reason": "evidence_candidate_without_concrete_basis"})
                    continue
                item["candidateOnly"] = True
                item["approvalStatus"] = "candidate_only"
                evidence_resolvable.append(item)
            elif disposition == "review_required":
                if not item.get("mechanicExistenceBasis"):
                    rejected.append({**item, "reason": "review_gap_without_confirmed_mechanic_basis"})
                    continue
                item["displayText"] = item.get("displayText") or item.get("question")
                item["approvalStatus"] = "unreviewed"
                review_required.append(item)
            else:
                not_applicable.append(item)
        open_count = len(evidence_resolvable) + len(review_required)
        relevant_count = len(confirmed_dimensions) + open_count
        closure_score = round(100 * len(confirmed_dimensions) / relevant_count, 2) if relevant_count else 0.0
        status = "closed" if open_count == 0 else (
            "open" if closure_score < 50 else "partially_closed")
        mechanics.append({
            "ruleSemanticId": contract["ruleSemanticId"],
            "mechanic": contract["mechanic"],
            "ownerChapter": contract["ownerChapter"],
            "displaySection": mechanic_spec.get("displaySection"),
            "confirmedRules": confirmed_rules,
            "confirmedRuleDimensions": confirmed_dimensions,
            "evidenceResolvableGaps": evidence_resolvable,
            "reviewRequiredGaps": review_required,
            "notApplicableDimensions": not_applicable,
            "closureStatus": status,
            "closureScore": closure_score,
        })
    return {
        "mechanics": mechanics,
        "rejectedDimensions": rejected,
        "metrics": {
            "confirmedMechanicCount": len(mechanics),
            "closedCount": sum(item["closureStatus"] == "closed" for item in mechanics),
            "partiallyClosedCount": sum(item["closureStatus"] == "partially_closed" for item in mechanics),
            "openCount": sum(item["closureStatus"] == "open" for item in mechanics),
            "evidenceResolvableGapCount": sum(len(item["evidenceResolvableGaps"]) for item in mechanics),
            "reviewRequiredGapCount": sum(len(item["reviewRequiredGaps"]) for item in mechanics),
            "notApplicableDimensionCount": sum(len(item["notApplicableDimensions"]) for item in mechanics),
        },
        "approvedRuleWrites": 0,
        "approvedGapWrites": 0,
    }


def render_execution_closure_preview(native_result: dict[str, Any], report: dict[str, Any]) -> str:
    chapters = copy.deepcopy(native_result.get("chapters", []))
    chapter_by_title = {item["title"]: item for item in chapters}
    for mechanic in report.get("mechanics", []):
        additions = []
        for gap in mechanic.get("evidenceResolvableGaps", []):
            additions.append(gap["candidateRule"])
        for gap in mechanic.get("reviewRequiredGaps", []):
            additions.append(gap["displayText"])
        if not additions:
            continue
        chapter = chapter_by_title.get(mechanic["ownerChapter"])
        if chapter is None:
            continue
        preferred = next((section for section in chapter["sections"]
                          if section["title"] == mechanic.get("displaySection")), None)
        section = preferred or chapter["sections"][0]
        existing = {item["text"] for item in section["items"]}
        for text in additions:
            if text not in existing:
                section["items"].append({"text": text})
                existing.add(text)
    lines = ["# Human Planning Preview", ""]
    for chapter in chapters:
        lines.extend([f"## {chapter['title']}", ""])
        for section in chapter["sections"]:
            lines.extend([f"### {section['title']}", ""])
            lines.extend(f"- {item['text']}" for item in section["items"])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
