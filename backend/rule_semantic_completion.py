from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any


_CONFIRMED_EXISTENCE = {"confirmed", "strongly_supported"}
_VALID_STATUS = {"observed", "unresolved", "suppressed", "not_applicable"}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def build_rule_semantic_contracts(game_rules: list[dict[str, Any]],
                                  completion_specs: list[dict[str, Any]]) -> dict[str, Any]:
    """Complete only evidence-confirmed mechanics; unresolved dimensions remain review inputs."""
    rule_by_id = {item["ruleId"]: item for item in game_rules}
    contracts: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for spec in completion_specs:
        if spec.get("existenceStatus") not in _CONFIRMED_EXISTENCE:
            rejected.append({"ruleSemanticId": spec.get("ruleSemanticId"),
                             "mechanic": spec.get("mechanic"), "reason": "mechanic_not_confirmed"})
            continue
        core_ids = spec.get("coreRuleIds", [])
        core_rules = [rule_by_id.get(rule_id) for rule_id in core_ids]
        if not core_ids or any(item is None for item in core_rules):
            rejected.append({"ruleSemanticId": spec.get("ruleSemanticId"),
                             "mechanic": spec.get("mechanic"), "reason": "confirmed_core_rule_missing"})
            continue
        dimensions = []
        observed_values = []
        unresolved_rules = []
        unresolved_parameters = []
        review_route = []
        suppressed = []
        for raw in spec.get("dimensions", []):
            item = dict(raw)
            status = item.get("status")
            if status not in _VALID_STATUS:
                raise ValueError(f"invalid semantic dimension status: {status}")
            if status == "suppressed":
                suppressed.append(item)
                continue
            if status == "not_applicable":
                continue
            dimensions.append(item)
            if status == "observed":
                if "observedCurrentState" in item:
                    observed_values.append({"dimensionId": item["dimensionId"],
                                            "currentObservedState": item["observedCurrentState"]})
                elif "value" in item:
                    observed_values.append({"dimensionId": item["dimensionId"], "value": item["value"]})
            elif item.get("kind") == "parameter":
                unresolved_parameters.append(item)
                review_route.append({"dimensionId": item["dimensionId"], "reviewStage": "P6"})
            else:
                unresolved_rules.append(item)
                review_route.append({"dimensionId": item["dimensionId"], "reviewStage": "P4"})
        unresolved_count = len(unresolved_rules) + len(unresolved_parameters)
        evidence_refs = []
        seen = set()
        for rule in core_rules:
            for evidence in rule.get("evidenceRefs", []):
                key = (evidence.get("evidenceId"), evidence.get("sourcePath"))
                if key not in seen:
                    seen.add(key)
                    evidence_refs.append(evidence)
        contracts.append({
            "ruleSemanticId": spec["ruleSemanticId"],
            "mechanic": spec["mechanic"],
            "ownerChapter": spec["ownerChapter"],
            "ruleGroup": spec["ruleGroup"],
            "existenceStatus": spec["existenceStatus"],
            "confirmedCoreRule": [{"ruleId": rule["ruleId"], "statement": rule["statement"]}
                                  for rule in core_rules],
            "requiredRuleDimensions": dimensions,
            "observedValues": observed_values,
            "unresolvedRuleDimensions": unresolved_rules,
            "unresolvedParameters": unresolved_parameters,
            "reviewRoute": review_route,
            "suppressedDimensions": suppressed,
            "sourceEvidenceRefs": evidence_refs,
            "completionStatus": "semantically_under_expanded" if unresolved_count else "complete",
            "approvalStatus": "candidate_only",
        })
    metrics = {
        "confirmedMechanicCount": len(contracts),
        "completedSemanticDimensionCount": sum(
            item.get("status") == "observed" for contract in contracts
            for item in contract["requiredRuleDimensions"]),
        "actionableUnresolvedDimensionCount": sum(
            len(contract["unresolvedRuleDimensions"]) + len(contract["unresolvedParameters"])
            for contract in contracts),
        "semanticallyUnderExpandedCount": sum(
            contract["completionStatus"] == "semantically_under_expanded" for contract in contracts),
        "concreteSubruleCount": sum(
            len(item.get("subrules", [])) for contract in contracts
            for item in contract["requiredRuleDimensions"]),
        "observedParameterCount": sum(
            item.get("status") == "observed" and item.get("kind") == "parameter" and "value" in item
            for contract in contracts for item in contract["requiredRuleDimensions"]),
    }
    return {"contracts": contracts, "rejectedSpecs": rejected, "metrics": metrics}


def build_review_promotions(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for contract in contracts:
        unresolved = contract.get("unresolvedRuleDimensions", []) + contract.get("unresolvedParameters", [])
        for item in unresolved:
            stage = "P6" if item.get("kind") == "parameter" else "P4"
            label = item["label"]
            question = item.get("question") or (f"{label}是多少？" if stage == "P6" else f"{label}如何确定？")
            input_contract = (
                {"control": "number_with_unit" if item.get("unitRequired") else "number",
                 "valueType": item.get("valueType", "number"),
                 "unit": item.get("unit"), "unitRequired": bool(item.get("unitRequired")),
                 "allowCustomUnit": bool(item.get("unitRequired"))}
                if stage == "P6" else
                {"control": "radio" if item.get("options") else "structured_rule",
                 "options": item.get("options", []), "allowCustom": True}
            )
            decisions.append({
                "decisionId": _stable_id("DEC", contract["ruleSemanticId"], item["dimensionId"]),
                "sourceRuleSemanticId": contract["ruleSemanticId"],
                "mechanic": contract["mechanic"],
                "ownerChapter": contract["ownerChapter"],
                "ruleGroup": contract["ruleGroup"],
                "dimensionId": item["dimensionId"],
                "decisionClass": "numeric_parameter" if stage == "P6" else item.get("decisionClass", "rule_choice"),
                "reviewStage": stage,
                "question": question,
                "options": item.get("options", []),
                "inputContract": input_contract,
                "recommendationOnly": True,
                "approvalStatus": "unreviewed",
            })
    return decisions


def render_semantically_completed_preview(contracts: list[dict[str, Any]]) -> str:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    chapter_order: list[str] = []
    for contract in contracts:
        chapter = contract["ownerChapter"]
        if chapter not in chapter_order:
            chapter_order.append(chapter)
        grouped[chapter][contract["ruleGroup"]].append(contract)
    lines = ["# Human Planning Preview", ""]
    seen_lines: set[tuple[str, str, str]] = set()
    for chapter in chapter_order:
        lines.extend([f"## {chapter}", ""])
        groups = grouped[chapter]
        for group, group_contracts in groups.items():
            if len(groups) > 1:
                lines.extend([f"### {group}", ""])
            for contract in group_contracts:
                for item in contract["requiredRuleDimensions"]:
                    if item["status"] == "observed":
                        text = item.get("displayText")
                    elif item["status"] == "unresolved":
                        text = f"{item['label']}：待确认。"
                    else:
                        text = None
                    if not text:
                        continue
                    key = (chapter, group, text)
                    if key in seen_lines:
                        continue
                    seen_lines.add(key)
                    lines.append(f"- {text}")
                    for subrule in item.get("subrules", []):
                        lines.append(f"  - {subrule}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
