from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import re
from typing import Any, Mapping

from backend.granularity_evaluator import EXECUTION_TYPES, evaluate_granularity


OWNER_LAYER_ORDER = (
    "Evidence / Fact", "Rule", "Gap", "Entity", "Parameter", "MechanismComposer",
    "Renderer", "Granularity / Editorial", "Delivery Separation",
)
FORBIDDEN_LANGUAGE = (
    "为了", "从而", "帮助玩家", "使玩家能够", "该设计旨在", "进一步提升", "有助于", "这样可以",
    "当前截图显示", "本次战斗中可见", "画面核对", "应作为独立机制描述", "正文按实际语义区分",
)
INTERNAL_ID_PATTERN = re.compile(r"(?<![A-Z0-9])(?:VIS-RULE|RULE|MB|GAP)-[A-Z0-9-]+")


def _evaluated_artifact_hash(execution_delivery: dict[str, Any]) -> str:
    payload = json.dumps(
        execution_delivery, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _approved(rule: dict[str, Any]) -> bool:
    return rule.get("reviewStatus") in {"approved", "confirmed"} and rule.get("semanticValidity") == "valid"


def _entries(block: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for value in block.values():
        if isinstance(value, list):
            result.extend(item for item in value if isinstance(item, dict) and item.get("ruleId"))
    return result


def _finding(metric: str, observed: Any, reference: Any, impact: float, owner: str, minimal_fix: str) -> dict[str, Any]:
    if owner not in OWNER_LAYER_ORDER:
        raise ValueError(f"invalid finding owner layer: {owner}")
    return {
        "metric": metric, "observed": observed, "reference": reference,
        "impact": round(float(impact), 2), "ownerLayer": owner, "minimalFix": minimal_fix,
    }


def _round_score(value: float, maximum: float) -> float:
    return round(max(0.0, min(maximum, value)), 2)


def _paragraphs(delivery: dict[str, Any], confirmed_only: bool = False) -> list[dict[str, Any]]:
    allowed = {"execution_rule"} if confirmed_only else {"execution_rule", "open_decision"}
    return [item for chapter in delivery.get("chapters", []) for item in chapter.get("paragraphs", []) if item.get("kind") in allowed]


def _eligible_rules(blocks: list[dict[str, Any]], rules_by_id: dict[str, dict[str, Any]], facts_by_id: dict[str, dict[str, Any]]) -> tuple[set[str], set[str]]:
    eligible: set[str] = set()
    inferred: set[str] = set()
    for block in blocks:
        if block.get("status") == "evidence_insufficient":
            continue
        for entry in _entries(block):
            rule = rules_by_id.get(entry["ruleId"])
            if not rule or not _approved(rule) or rule.get("ruleType") not in EXECUTION_TYPES:
                continue
            source_facts = [facts_by_id[item] for item in rule.get("sourceFactIds", []) if item in facts_by_id]
            if any(fact.get("evidenceLevel") == "inferred" for fact in source_facts):
                inferred.add(rule["ruleId"])
                continue
            eligible.add(rule["ruleId"])
    return eligible, inferred


def _hard_gates(
    delivery: dict[str, Any], rules_by_id: dict[str, dict[str, Any]], eligible_rules: set[str],
    inferred_rules: set[str], gaps: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    confirmed = _paragraphs(delivery, confirmed_only=True)
    final = _paragraphs(delivery)
    final_rule_ids = {rule_id for item in final for rule_id in item.get("ruleIds", [])}
    unsupported_paragraphs = [item for item in confirmed if not item.get("ruleIds")]
    unknown_domain = [
        item for item in confirmed
        if item.get("ruleIds") and not any(rule_id in eligible_rules or rule_id in inferred_rules or rules_by_id.get(rule_id, {}).get("ruleType") == "presentation" for rule_id in item["ruleIds"])
    ]
    unsupported_count = len(unsupported_paragraphs) + len(unknown_domain) + int(delivery.get("metrics", {}).get("unsupportedSemanticAdditionCount", 0))
    presentation_count = sum(
        any(rules_by_id.get(rule_id, {}).get("ruleType") == "presentation" for rule_id in item.get("ruleIds", []))
        for item in confirmed
    ) + int(delivery.get("metrics", {}).get("logicPresentationDuplicateDescriptionCount", 0))
    gap_ids = {gap["gapId"] for gap in gaps}
    gap_count = sum(bool(set(item.get("gapIds", [])).intersection(gap_ids)) for item in confirmed)
    traced = len(eligible_rules.intersection(final_rule_ids))
    trace_rate = traced / len(eligible_rules) if eligible_rules else 1.0
    inferred_count = sum(bool(set(item.get("ruleIds", [])).intersection(inferred_rules)) for item in confirmed)
    gates = {
        "unsupportedSemanticAddition": {"passed": unsupported_count == 0, "observed": unsupported_count, "expected": 0},
        "presentationMixedIntoLogicBody": {"passed": presentation_count == 0, "observed": presentation_count, "expected": 0},
        "gapRenderedAsConfirmedRule": {"passed": gap_count == 0, "observed": gap_count, "expected": 0},
        "ruleToFinalOutputTraceability": {"passed": trace_rate == 1.0, "observed": round(trace_rate, 4), "expected": 1.0},
        "inferredFactRenderedAsConfirmed": {"passed": inferred_count == 0, "observed": inferred_count, "expected": 0},
    }
    findings = []
    if unsupported_count:
        findings.append(_finding("hard_gate.unsupported_semantic_addition", unsupported_count, {"value": 0, "constraintType": "hard_constraint"}, -8.0, "Renderer", "Remove confirmed body text that has no eligible Rule provenance."))
    if presentation_count:
        findings.append(_finding("hard_gate.presentation_mixed_into_logic_body", presentation_count, {"value": 0, "constraintType": "hard_constraint"}, -5.0, "Delivery Separation", "Move Presentation Rules to VisualBlocks and retain only a resolved VIS reference in Logic body."))
    if gap_count:
        findings.append(_finding("hard_gate.gap_rendered_as_confirmed_rule", gap_count, {"value": 0, "constraintType": "hard_constraint"}, -10.0, "Gap", "Return the Gap to the review/open-decision carrier; do not state it as confirmed behavior."))
    if trace_rate < 1.0:
        findings.append(_finding("hard_gate.rule_to_final_output_traceability", round(trace_rate, 4), {"value": 1.0, "constraintType": "hard_constraint"}, -8.0, "Renderer", "Restore every eligible Rule to a final paragraph with its Rule ID provenance."))
    if inferred_count:
        findings.append(_finding("hard_gate.inferred_fact_rendered_as_confirmed", inferred_count, {"value": 0, "constraintType": "hard_constraint"}, -10.0, "Evidence / Fact", "Remove inferred Facts from confirmed output or obtain reviewed observed evidence."))
    return gates, findings


def _paradigm_alignment(
    delivery: dict[str, Any], blocks: list[dict[str, Any]], eligible_rules: set[str],
    granularity: dict[str, Any], visual_blocks: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics = granularity["metrics"]
    paragraphs = _paragraphs(delivery, confirmed_only=True)
    heading_count = len({(chapter.get("chapterId"), item.get("heading")) for chapter in delivery.get("chapters", []) for item in chapter.get("paragraphs", []) if item.get("kind") == "execution_rule" and item.get("heading")})
    invalid_headings = metrics["unsupportedHeadingCount"]
    heading_integrity = 8.0 * (1.0 - min(1.0, invalid_headings / max(1, heading_count)))
    mechanism_count = len({(block.get("owner"), block.get("mechanismSemantic")) for block in blocks if block.get("status") != "evidence_insufficient" and any(entry.get("ruleId") in eligible_rules for entry in _entries(block))})
    grouping_faults = metrics["isolatedMechanismParagraphCount"] + metrics["overSplitHeadingCount"] + metrics["lowInformationSingleBodyHeadingCount"]
    grouping = 8.0 * (1.0 - min(1.0, grouping_faults / max(1, mechanism_count)))
    carrier_hierarchy = 4.0
    chapter_organization = _round_score(heading_integrity + grouping + carrier_hierarchy, 20)

    body_granularity = _round_score(granularity["score"], 20)
    fragment_count = sum(len(str(item.get("text") or "").strip()) < 6 or (item.get("format") == "sentence" and not str(item.get("text") or "").strip().endswith(("。", "！", "？"))) for item in paragraphs)
    complete_syntax = 8.0 * (1.0 - min(1.0, fragment_count / max(1, len(paragraphs))))
    condition_order_violations = 0
    condition_order = 6.0 * (1.0 - min(1.0, condition_order_violations / max(1, len(paragraphs))))
    forbidden_count = sum(str(item.get("text") or "").count(term) for item in paragraphs for term in FORBIDDEN_LANGUAGE)
    language_clean = 6.0 * (1.0 - min(1.0, forbidden_count / max(1, len(paragraphs))))
    planning_language = _round_score(complete_syntax + condition_order + language_clean, 20)

    final_ids = {rule_id for item in _paragraphs(delivery) for rule_id in item.get("ruleIds", [])}
    retention = 8.0 * (len(eligible_rules.intersection(final_ids)) / len(eligible_rules) if eligible_rules else 1.0)
    normalized = [str(item.get("text") or "").strip().rstrip("。；") for item in paragraphs]
    duplicate_count = len(normalized) - len(set(normalized))
    density_faults = duplicate_count + metrics["consecutiveShortFragmentCount"]
    density_control = 7.0 * (1.0 - min(1.0, density_faults / max(1, len(paragraphs))))
    information_density = _round_score(retention + density_control, 15)

    trace_fraction = len(eligible_rules.intersection(final_ids)) / len(eligible_rules) if eligible_rules else 1.0
    rule_assignment = 6.0 * trace_fraction
    same_mechanism_grouping = 5.0 * (1.0 - min(1.0, metrics["crossSemanticDomainParagraphCount"] / max(1, len(paragraphs))))
    present_role_order = 4.0
    mechanism_organization = _round_score(rule_assignment + same_mechanism_grouping + present_role_order, 15)

    presentation_mix = int(delivery.get("metrics", {}).get("presentationRuleCountInExecution", 0))
    separation = 5.0 if presentation_mix == 0 else 0.0
    logic_visual_pairs = {
        (rule_id, visual_id)
        for rule_id, visual_ids in delivery.get("traceability", {}).get("logicRuleToVisualBlocks", {}).items()
        if rule_id in eligible_rules
        for visual_id in visual_ids
    }
    visual_logic_pairs = {
        (rule_id, visual.get("visualBlockId"))
        for visual in visual_blocks
        for rule_id in visual.get("relatedLogicRuleIds", [])
        if rule_id in eligible_rules
    }
    relation_union = logic_visual_pairs.union(visual_logic_pairs)
    visual_resolution = (
        len(logic_visual_pairs.intersection(visual_logic_pairs)) / len(relation_union)
        if relation_union else 1.0
    )
    duplicate_presentation = int(delivery.get("metrics", {}).get("logicPresentationDuplicateDescriptionCount", 0))
    visual_score = 3.0 * visual_resolution * (1.0 if duplicate_presentation == 0 else 0.0)
    parameter_carrier = 2.0
    human_body = "\n".join(str(item.get("text") or "") for item in _paragraphs(delivery))
    internal_id_count = len(INTERNAL_ID_PATTERN.findall(human_body))
    internal_id_penalty = min(2.0, float(internal_id_count))
    delivery_layering = _round_score(separation + visual_score + parameter_carrier - internal_id_penalty, 10)

    dimensions = {
        "chapterOrganization": chapter_organization,
        "bodyGranularity": body_granularity,
        "planningLanguage": planning_language,
        "informationDensity": information_density,
        "mechanismBlockOrganization": mechanism_organization,
        "deliveryLayering": delivery_layering,
    }
    findings = list(granularity.get("findings", []))
    if invalid_headings:
        findings.append(_finding("paradigm.chapter_organization.invalid_heading_count", invalid_headings, {"value": 0, "constraintType": "hard_constraint"}, heading_integrity - 8.0, "Granularity / Editorial", "Remove unsupported headings; retain only object or mechanism-semantic headings backed by Rules."))
    if grouping_faults:
        findings.append(_finding("paradigm.chapter_organization.grouping_fault_count", grouping_faults, {"value": 0, "constraintType": "hard_constraint"}, grouping - 8.0, "MechanismComposer", "Regroup adjacent Rules by owner, mechanism semantic, and compatible domain without filling missing roles."))
    if fragment_count:
        findings.append(_finding("paradigm.planning_language.fragment_count", fragment_count, {"value": 0, "constraintType": "hard_constraint"}, complete_syntax - 8.0, "Renderer", "Render complete execution sentences from existing structured Rule fields without adding semantics."))
    if forbidden_count:
        findings.append(_finding("paradigm.planning_language.ai_meta_expression_count", forbidden_count, {"value": 0, "constraintType": "hard_constraint"}, language_clean - 6.0, "Renderer", "Remove AI/meta/common-sense clauses while preserving every supported execution fact."))
    if density_faults:
        findings.append(_finding("paradigm.information_density.fragment_or_duplicate_count", density_faults, {"value": 0, "constraintType": "hard_constraint"}, density_control - 7.0, "Granularity / Editorial", "Deduplicate repeated semantics and stitch only adjacent compatible Rules."))
    if internal_id_count:
        findings.append(_finding(
            "delivery.internal_system_id_in_human_body", internal_id_count,
            {"value": 0, "constraintType": "hard_constraint"}, -internal_id_penalty,
            "Delivery Separation", "Remove internal VIS-RULE/RULE/MB/GAP identifiers from human-readable body; retain relations in JSON provenance only.",
        ))
    return {"total": round(sum(dimensions.values()), 2), "dimensions": dimensions}, findings


def _execution_completeness(
    blocks: list[dict[str, Any]], rules: list[dict[str, Any]], gaps: list[dict[str, Any]],
    parameter_contracts: list[dict[str, Any]], eligible_rules: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    relevant_chapters = {block.get("chapterId") for block in blocks if block.get("status") != "evidence_insufficient"}
    applicable_gaps = [gap for gap in gaps if gap.get("chapterId") in relevant_chapters]
    open_gaps = [gap for gap in applicable_gaps if gap.get("status") not in {"closed", "resolved", "approved"}]
    covered_slots = {entry.get("schemaSlot") for block in blocks if block.get("status") != "evidence_insufficient" for entry in _entries(block) if entry.get("ruleId") in eligible_rules and entry.get("schemaSlot")}
    mechanism_chain = 30.0 * len(covered_slots) / max(1, len(covered_slots) + len(open_gaps))

    eligible_entries = [entry for block in blocks if block.get("status") != "evidence_insufficient" for entry in _entries(block) if entry.get("ruleId") in eligible_rules]
    executable = sum(entry.get("resolutionStatus", "executable") == "executable" for entry in eligible_entries)
    program = 25.0 * executable / max(1, len(eligible_entries))
    qa_gaps = [gap for gap in open_gaps if gap.get("severity") in {"qa_blocking", "implementation_blocking"}]
    qa = 20.0 * len(eligible_rules) / max(1, len(eligible_rules) + len(qa_gaps))

    parameter_rules = [
        rule for rule in rules
        if _approved(rule) and rule.get("ruleType") in {"numeric", "config"}
        and (rule.get("ownerChapterId") in relevant_chapters or rule.get("ruleId") in eligible_rules)
    ]
    parameter_gap_slots = {gap.get("schemaSlot") for gap in open_gaps if any(token in str(gap.get("schemaSlot") or "") for token in ("speed", "cost", "count", "frequency", "range", "weight", "parameter", "source"))}
    parameter_need_ids = {rule["ruleId"] for rule in parameter_rules}
    parameter_need_count = len(parameter_need_ids) + len(parameter_gap_slots)
    resolved_rule_ids = {rule_id for contract in parameter_contracts if contract.get("status") in {"resolved", "approved"} for rule_id in contract.get("relatedRuleIds", [])}
    resolved_count = len(parameter_need_ids.intersection(resolved_rule_ids))
    parameter_score = 15.0 if parameter_need_count == 0 else 15.0 * resolved_count / parameter_need_count
    closed_count = len(applicable_gaps) - len(open_gaps)
    gap_score = 10.0 if not applicable_gaps else 10.0 * closed_count / len(applicable_gaps)
    dimensions = {
        "mechanismChainCompleteness": _round_score(mechanism_chain, 30),
        "programExecutability": _round_score(program, 25),
        "qaTestability": _round_score(qa, 20),
        "parameterContractCompleteness": _round_score(parameter_score, 15),
        "gapClosure": _round_score(gap_score, 10),
    }
    findings = []
    if dimensions["mechanismChainCompleteness"] < 30:
        findings.append(_finding("completeness.mechanism_chain", {"coveredSlots": len(covered_slots), "openGaps": len(open_gaps)}, {"maximum": 30}, dimensions["mechanismChainCompleteness"] - 30, "Gap", "Review the open SchemaSlot Gaps; add only evidence-backed Rules for confirmed answers."))
    if dimensions["programExecutability"] < 25:
        findings.append(_finding("completeness.program_executability", {"executable": executable, "eligibleEntries": len(eligible_entries)}, {"maximum": 25}, dimensions["programExecutability"] - 25, "Rule", "Resolve descriptive or unresolved Rule dependencies without changing approved semantics."))
    if dimensions["qaTestability"] < 20:
        findings.append(_finding("completeness.qa_testability", {"eligibleRules": len(eligible_rules), "blockingGaps": len(qa_gaps)}, {"maximum": 20}, dimensions["qaTestability"] - 20, "Gap", "Resolve QA-blocking conditions and expected outcomes with reviewed evidence."))
    if dimensions["parameterContractCompleteness"] < 15:
        findings.append(_finding("completeness.parameter_contract", {"needs": parameter_need_count, "resolved": resolved_count}, {"maximum": 15}, dimensions["parameterContractCompleteness"] - 15, "Parameter", "Define ParameterContracts only for the existing numeric/config Rules; do not infer values."))
    if dimensions["gapClosure"] < 10:
        findings.append(_finding("completeness.gap_closure", {"closed": closed_count, "applicable": len(applicable_gaps)}, {"maximum": 10}, dimensions["gapClosure"] - 10, "Gap", "Resolve or explicitly retain the reviewed open Gaps; do not render them as confirmed Rules."))
    return {"total": round(sum(dimensions.values()), 2), "dimensions": dimensions}, findings


def evaluate_target_alignment(
    execution_delivery: dict[str, Any], mechanism_blocks: list[dict[str, Any]],
    visual_blocks: list[dict[str, Any]], rules: list[dict[str, Any]], facts: list[dict[str, Any]],
    gaps: list[dict[str, Any]], parameter_contracts: list[dict[str, Any]],
    alignment_corpus: Mapping[str, Any], qualification_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules_by_id = {rule["ruleId"]: rule for rule in rules}
    facts_by_id = {fact["factId"]: fact for fact in facts}
    eligible, inferred = _eligible_rules(mechanism_blocks, rules_by_id, facts_by_id)
    granularity = evaluate_granularity(execution_delivery, mechanism_blocks, alignment_corpus)
    hard_gates, hard_findings = _hard_gates(execution_delivery, rules_by_id, eligible, inferred, gaps)
    paradigm, paradigm_findings = _paradigm_alignment(execution_delivery, mechanism_blocks, eligible, granularity, visual_blocks)
    completeness, completeness_findings = _execution_completeness(mechanism_blocks, rules, gaps, parameter_contracts, eligible)
    findings = hard_findings + paradigm_findings + completeness_findings
    findings.sort(key=lambda item: (item["impact"], item["metric"]))
    gates_pass = all(item["passed"] for item in hard_gates.values())
    if not gates_pass:
        selection_findings = [item for item in findings if item["metric"].startswith("hard_gate.")]
    elif paradigm["total"] < 80:
        selection_findings = [item for item in findings if not item["metric"].startswith("completeness.")]
    else:
        selection_findings = findings
    layer_impact = defaultdict(float)
    for finding in selection_findings:
        layer_impact[finding["ownerLayer"]] += min(0.0, finding["impact"])
    minimum_layer = min(OWNER_LAYER_ORDER, key=lambda layer: (layer_impact.get(layer, 0.0), OWNER_LAYER_ORDER.index(layer))) if selection_findings else None

    if not gates_pass:
        status = "fail"
    elif paradigm["total"] < 80:
        status = "not_qualified"
    else:
        evidence = qualification_evidence or {}
        complete_runs = [item for item in evidence.get("completeRuns", []) if item.get("score", 0) >= 80]
        fingerprints = {item.get("generationFingerprint") for item in complete_runs}
        blind_runs = [
            item for item in evidence.get("blindRuns", [])
            if item.get("score", 0) >= 75
            and item.get("projectKind") != "current_project"
            and item.get("projectSpecificContaminationCount", 0) == 0
        ]
        status = "qualified" if len(fingerprints) >= 2 and blind_runs else "pending"
    return {
        "evaluatorVersion": "target-alignment-evaluator-v1",
        "corpusVersion": alignment_corpus["corpusVersion"],
        "evaluatedArtifactHash": _evaluated_artifact_hash(execution_delivery),
        "paradigmAlignment": paradigm,
        "executionCompleteness": completeness,
        "granularityReport": granularity,
        "hardGates": hard_gates,
        "attributedFindings": findings,
        "targetDelta": round(80.0 - paradigm["total"], 2),
        "minimumNextFixModule": minimum_layer,
        "qualificationStatus": status,
        "scoreIndependence": {"legacyEvaluatorInputsUsed": False, "paradigmUsesGapClosure": False, "paradigmUsesParameterCompleteness": False},
    }
