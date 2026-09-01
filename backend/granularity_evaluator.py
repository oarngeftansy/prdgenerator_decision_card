from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping


EXECUTION_TYPES = frozenset({"logic", "flow", "numeric", "config", "interaction"})


def _family(slot: str) -> str:
    for prefix in ("movement", "attack", "damage_death", "random", "settlement", "content_catalog", "spawn", "level"):
        if slot.startswith(prefix):
            return prefix
    if slot in {"selection_pause", "candidate_selection", "candidate_effect", "refresh_rule", "refresh_count", "refresh_cost"}:
        return "random"
    return slot or "unknown"


def _block_index(blocks: list[dict[str, Any]]) -> tuple[dict[str, tuple[str, str, str]], set[str], set[str]]:
    domains: dict[str, tuple[str, str, str]] = {}
    eligible: set[str] = set()
    headings: set[str] = set()
    for block in blocks:
        if block.get("status") == "evidence_insufficient":
            continue
        owner = str(block.get("owner") or block.get("chapterId") or "")
        semantic = str(block.get("mechanismSemantic") or "")
        headings.add(semantic)
        for value in block.values():
            if not isinstance(value, list):
                continue
            for entry in value:
                if not isinstance(entry, dict) or entry.get("ruleType") not in EXECUTION_TYPES or not entry.get("ruleId"):
                    continue
                rule_id = entry["ruleId"]
                eligible.add(rule_id)
                domains[rule_id] = (owner, semantic, _family(str(entry.get("schemaSlot") or "")))
    return domains, eligible, headings


def _execution_paragraphs(delivery: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (chapter.get("chapterId", ""), paragraph)
        for chapter in delivery.get("chapters", [])
        for paragraph in chapter.get("paragraphs", [])
        if paragraph.get("kind") in {"execution_rule", "open_decision"}
    ]


def _finding(metric: str, observed: Any, reference: Any, impact: float, minimal_fix: str) -> dict[str, Any]:
    return {
        "metric": metric, "observed": observed, "reference": reference,
        "impact": round(impact, 2), "ownerLayer": "Granularity / Editorial",
        "minimalFix": minimal_fix,
    }


def _distribution_fit(paragraphs: list[dict[str, Any]], corpus: Mapping[str, Any], one_rule_sentence_ratio: float, average_rules: float) -> float:
    if not paragraphs:
        return 4.0
    refs = corpus["provisionalReferences"]
    lengths = [len(str(item.get("text") or "").replace("- ", "").strip()) for item in paragraphs]
    average_length = sum(lengths) / len(lengths)
    sentence_ref = refs["sentenceLength"]
    if sentence_ref["median"] <= average_length <= sentence_ref["p75"]:
        length_fit = 1.0
    else:
        boundary = sentence_ref["median"] if average_length < sentence_ref["median"] else sentence_ref["p75"]
        length_fit = max(0.0, 1.0 - abs(average_length - boundary) / max(1.0, sentence_ref["max"] - sentence_ref["min"]))
    dist = refs["rulesPerGroup"]["distribution"]
    count = refs["rulesPerGroup"]["count"]
    expected_rules = (dist["1"] + 2 * dist["2"] + 3 * dist["3+"]) / count
    rules_fit = max(0.0, 1.0 - abs(average_rules - expected_rules) / 2.0)
    expected_one = dist["1"] / count
    one_fit = max(0.0, 1.0 - abs(one_rule_sentence_ratio - expected_one))
    return round(4.0 * (length_fit + rules_fit + one_fit) / 3.0, 2)


def evaluate_granularity(
    execution_delivery: dict[str, Any],
    mechanism_blocks: list[dict[str, Any]],
    alignment_corpus: Mapping[str, Any],
) -> dict[str, Any]:
    domains, eligible_rules, supported_headings = _block_index(mechanism_blocks)
    chapter_paragraphs = _execution_paragraphs(execution_delivery)
    paragraphs = [item for _, item in chapter_paragraphs]
    final_rule_ids = {rule_id for item in paragraphs for rule_id in item.get("ruleIds", [])}
    lost_rules = sorted(eligible_rules - final_rule_ids)

    sentence_paragraphs = [item for item in paragraphs if item.get("format") == "sentence"]
    one_rule_sentences = sum(len(item.get("ruleIds", [])) == 1 for item in sentence_paragraphs)
    one_rule_ratio = one_rule_sentences / len(sentence_paragraphs) if sentence_paragraphs else 0.0
    average_rules = sum(len(set(item.get("ruleIds", []))) for item in paragraphs) / len(paragraphs) if paragraphs else 0.0
    average_length = sum(len(str(item.get("text") or "").replace("- ", "").strip()) for item in paragraphs) / len(paragraphs) if paragraphs else 0.0
    carriers = Counter()
    for item in paragraphs:
        carriers[{"sentence": "prose", "bullets": "bullet", "numbered": "numbered", "table": "table"}.get(item.get("format"), "prose")] += 1
    carrier_distribution = {key: carriers.get(key, 0) for key in ("prose", "bullet", "numbered", "table")}

    cross_domain = 0
    paragraph_domains: dict[str, set[tuple[str, str, str]]] = {}
    for item in paragraphs:
        item_domains = {domains[rule_id] for rule_id in item.get("ruleIds", []) if rule_id in domains}
        paragraph_domains[item.get("paragraphId", "")] = item_domains
        if len(item_domains) > 1:
            cross_domain += 1

    headings: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for chapter_id, item in chapter_paragraphs:
        headings[(chapter_id, str(item.get("heading") or ""))].append(item)
    unsupported_headings = sum(bool(heading and heading not in supported_headings and heading != "开放决策") for _, heading in headings)
    low_info = sum(
        len(items) == 1 and len(items[0].get("ruleIds", [])) == 1 and len(str(items[0].get("text") or "").strip()) < 16
        for items in headings.values()
    )
    single_rule_headings = sum(len(items) == 1 and len(items[0].get("ruleIds", [])) == 1 for items in headings.values())
    single_heading_ratio = single_rule_headings / len(headings) if headings else 0.0

    by_mechanism: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in paragraphs:
        item_domains = paragraph_domains.get(item.get("paragraphId", ""), set())
        if len(item_domains) == 1:
            by_mechanism[next(iter(item_domains))].append(item)
    isolated = sum(len(items) > 1 and all(len(item.get("ruleIds", [])) == 1 for item in items) for items in by_mechanism.values())
    over_split = sum(max(0, len({str(item.get("heading") or "") for item in items}) - 1) for items in by_mechanism.values())

    consecutive_short = 0
    for chapter in execution_delivery.get("chapters", []):
        body = [item for item in chapter.get("paragraphs", []) if item.get("kind") in {"execution_rule", "open_decision"}]
        for left, right in zip(body, body[1:]):
            consecutive_short += int(len(str(left.get("text") or "").strip()) < 16 and len(str(right.get("text") or "").strip()) < 16)
    stitched = [item for item in paragraphs if len(item.get("ruleIds", [])) > 1]
    semicolon_ratio = sum("；" in str(item.get("text") or "") for item in stitched) / len(stitched) if stitched else 0.0

    denominator = max(1, len(paragraphs))
    semantic_score = round(8.0 * (1.0 - min(1.0, cross_domain / denominator)), 2)
    cohesion_faults = len(lost_rules) + low_info + unsupported_headings + over_split + isolated
    cohesion_denominator = max(1, len(eligible_rules) + len(by_mechanism))
    cohesion_score = round(8.0 * (1.0 - min(1.0, cohesion_faults / cohesion_denominator)), 2)
    distribution_score = _distribution_fit(paragraphs, alignment_corpus, one_rule_ratio, average_rules)
    score = round(semantic_score + cohesion_score + distribution_score, 2)

    findings = []
    if cross_domain:
        findings.append(_finding(
            "granularity.cross_semantic_domain_paragraph_count", cross_domain,
            {"value": 0, "constraintType": "hard_constraint"}, semantic_score - 8.0,
            "Split the paragraph at the semantic-domain boundary; keep only Rules with the same owner and mechanism semantic together.",
        ))
    if lost_rules:
        findings.append(_finding(
            "granularity.lost_eligible_rule_count", len(lost_rules), {"value": 0, "constraintType": "hard_constraint"},
            -8.0 * len(lost_rules) / cohesion_denominator,
            "Restore every eligible Rule to a traceable final carrier before optimizing paragraph length.",
        ))
    if unsupported_headings:
        findings.append(_finding(
            "granularity.unsupported_heading_count", unsupported_headings, {"value": 0, "constraintType": "hard_constraint"},
            -8.0 * unsupported_headings / cohesion_denominator,
            "Remove headings that are not backed by an existing mechanism semantic.",
        ))
    if low_info:
        findings.append(_finding(
            "granularity.low_information_single_body_heading_count", low_info,
            {"distributionId": "rulesPerGroup", "provisional": True}, -8.0 * low_info / cohesion_denominator,
            "Inline the low-information Rule under its supported mechanism heading.",
        ))
    findings.sort(key=lambda item: (item["impact"], item["metric"]))
    metrics = {
        "oneRuleOneSentenceRatio": round(one_rule_ratio, 4),
        "singleRuleIndependentHeadingRatio": round(single_heading_ratio, 4),
        "averageRulesPerParagraph": round(average_rules, 4),
        "averageParagraphLength": round(average_length, 2),
        "carrierDistribution": carrier_distribution,
        "semicolonStitchingRatio": round(semicolon_ratio, 4),
        "consecutiveShortFragmentCount": consecutive_short,
        "isolatedMechanismParagraphCount": isolated,
        "crossSemanticDomainParagraphCount": cross_domain,
        "lowInformationSingleBodyHeadingCount": low_info,
        "overSplitHeadingCount": over_split,
        "forcedMultiRuleMergeCount": cross_domain,
        "lostEligibleRuleCount": len(lost_rules),
        "unsupportedHeadingCount": unsupported_headings,
        "eligibleRuleCount": len(eligible_rules),
        "finalParagraphCount": len(paragraphs),
    }
    return {
        "evaluatorVersion": "granularity-evaluator-v1",
        "score": score,
        "scoreComponents": {
            "semanticDomainIsolation": semantic_score,
            "mechanismCohesion": cohesion_score,
            "provisionalDistributionFit": distribution_score,
        },
        "metrics": metrics,
        "findings": findings,
        "referencePolicy": {"hardConstraints": "non_provisional", "distributionRanges": "provisional"},
    }
