from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping


LEVEL_BY_KIND = {
    "domain": "L1",
    "family": "L2",
    "pattern": "L3",
    "responsibility": "L4",
}
ALLOWED_EDGE_TYPES = {
    "contains",
    "specializes",
    "may_activate",
    "activated_by",
    "shares_concept",
    "depends_on",
}
PROJECT_ANSWER_KEYS = {
    "projectAnswer",
    "approvedAnswer",
    "defaultValue",
    "configuredValue",
}


def validate_mechanic_graph(graph: Mapping[str, Any]) -> None:
    if graph.get("contentAuthority") != "none":
        raise ValueError("mechanic graph contentAuthority must be none")
    nodes = list(graph.get("nodes") or [])
    ids = [str(node.get("id") or "") for node in nodes]
    if not ids or any(not node_id for node_id in ids):
        raise ValueError("every graph node requires an id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate graph node id")
    for node in nodes:
        kind = node.get("kind")
        expected_level = LEVEL_BY_KIND.get(str(kind))
        if expected_level and node.get("level") != expected_level:
            raise ValueError(f"invalid level for {node['id']}: expected {expected_level}")
        if PROJECT_ANSWER_KEYS.intersection(node):
            raise ValueError(f"project answer is forbidden in pattern graph: {node['id']}")
    id_set = set(ids)
    edges = list(graph.get("edges") or [])
    for edge in edges:
        if edge.get("from") not in id_set or edge.get("to") not in id_set:
            raise ValueError(f"dangling edge: {edge}")
        if edge.get("type") not in ALLOWED_EDGE_TYPES:
            raise ValueError(f"unsupported graph edge type: {edge.get('type')}")
    node_by_id = {str(node["id"]): node for node in nodes}
    for node in nodes:
        for contract_name in ("detection", "activation"):
            contract = node.get(contract_name) or {}
            referenced_signals = {
                str(signal_id)
                for key in ("allSignals", "anySignals", "signalSet")
                for signal_id in contract.get(key) or []
            }
            undeclared = sorted(
                signal_id for signal_id in referenced_signals
                if signal_id not in node_by_id or node_by_id[signal_id].get("kind") != "signal"
            )
            if undeclared:
                raise ValueError(f"undeclared signal in {node['id']}: {undeclared}")
    contained_targets = {
        str(edge["to"])
        for edge in edges
        if edge.get("type") == "contains"
    }
    activated_targets = {
        str(edge["to"])
        for edge in edges
        if edge.get("type") == "may_activate"
    }
    patterns_with_shared_concepts = {
        str(edge["from"])
        for edge in edges
        if edge.get("type") == "shares_concept"
        and node_by_id[str(edge["to"])].get("kind") == "concept"
    }
    for node in nodes:
        if node.get("kind") == "pattern" and node["id"] not in contained_targets:
            raise ValueError(f"orphan pattern: {node['id']}")
        if node.get("kind") == "pattern" and node["id"] not in patterns_with_shared_concepts:
            raise ValueError(f"pattern without shared concept: {node['id']}")
        if node.get("kind") == "responsibility" and node["id"] not in activated_targets:
            raise ValueError(f"orphan responsibility: {node['id']}")


def load_mechanic_graph(path: str | Path) -> "MechanicKnowledgeGraph":
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return MechanicKnowledgeGraph(payload)


def _signals(records: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(signal)
        for record in records
        for signal in record.get("signalIds", [])
        if str(signal)
    }


def _contract_matches(contract: Mapping[str, Any], signals: set[str], *, detected: bool = False) -> bool:
    if contract.get("alwaysForDetectedPattern"):
        return detected
    all_signals = set(contract.get("allSignals") or [])
    any_signals = set(contract.get("anySignals") or [])
    minimum = int(contract.get("minimumSignalCount") or 0)
    matched = set(contract.get("signalSet") or []) & signals
    if all_signals and not all_signals.issubset(signals):
        return False
    if any_signals and not any_signals.intersection(signals):
        return False
    if minimum and len(matched) < minimum:
        return False
    return bool(all_signals or any_signals or minimum)


def _activation_contract_match(
    contract: Mapping[str, Any],
    *,
    signals: set[str],
    detected: bool,
    rules: Iterable[Mapping[str, Any]],
    relations: Iterable[Mapping[str, Any]],
) -> tuple[bool, list[str], list[str]]:
    signal_clause_present = bool(
        contract.get("alwaysForDetectedPattern")
        or contract.get("allSignals")
        or contract.get("anySignals")
        or contract.get("minimumSignalCount")
    )
    signal_match = _contract_matches(contract, signals, detected=detected) if signal_clause_present else True
    approved_rules = [rule for rule in rules if rule.get("reviewStatus") == "approved"]
    required_rule_tags = {str(tag) for tag in contract.get("anyApprovedRuleTags") or []}
    matched_rules = sorted({
        str(rule.get("ruleId"))
        for rule in approved_rules
        if required_rule_tags.intersection(str(tag) for tag in rule.get("tags") or [])
        and str(rule.get("ruleId") or "")
    })
    required_relation_types = {str(item) for item in contract.get("anyRelationTypes") or []}
    matched_relation_types = sorted({
        str(relation.get("type"))
        for relation in relations
        if str(relation.get("type")) in required_relation_types
    })
    rule_match = not required_rule_tags or bool(matched_rules)
    relation_match = not required_relation_types or bool(matched_relation_types)
    has_clause = signal_clause_present or bool(required_rule_tags) or bool(required_relation_types)
    return has_clause and signal_match and rule_match and relation_match, matched_rules, matched_relation_types


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0


IMPLEMENTATION_LANGUAGE = {
    "listener", "callback", "thread", "mutex", "cache", "database",
    "event id", "internal id", "atomic commit", "memory cleanup",
}


def evaluate_migration_benchmark(
    graph: "MechanicKnowledgeGraph",
    cases: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate declarative recognition without influencing recognition itself."""
    case_reports = []
    expected_patterns_total = detected_patterns_total = matched_patterns_total = 0
    expected_responsibilities_total = active_responsibilities_total = matched_responsibilities_total = 0
    high_value_gaps = gap_total = leakage_total = 0
    genre_only_activation_count = 0
    execution_dimension_coverage: dict[str, int] = {}

    for case in cases:
        case_id = str(case.get("id") or "")
        evidence = [{
            "evidenceId": f"E-{case_id}",
            "signalIds": list(case.get("signals") or []),
            "entityIds": list(case.get("entityIds") or []),
        }]
        detected = graph.detect_mechanics(evidence, context={"genre": case.get("genre")})
        detected_patterns = {str(item["mechanicType"]) for item in detected}
        expected_patterns = {str(item) for item in case.get("expectedPatterns") or []}
        active = graph.activate_responsibilities(detected, evidence=evidence, rules=[], relations=[])
        active_responsibilities = {str(item["responsibilityId"]) for item in active}
        for responsibility_id in active_responsibilities:
            for dimension in graph.nodes[responsibility_id].get("planningDimensions") or []:
                dimension = str(dimension)
                execution_dimension_coverage[dimension] = execution_dimension_coverage.get(dimension, 0) + 1
        expected_responsibilities = {str(item) for item in case.get("requiredResponsibilities") or []}
        missing = graph.discover_missing_requirements(active, rules=[])

        expected_patterns_total += len(expected_patterns)
        detected_patterns_total += len(detected_patterns)
        matched_patterns_total += len(expected_patterns & detected_patterns)
        expected_responsibilities_total += len(expected_responsibilities)
        active_responsibilities_total += len(active_responsibilities)
        matched_responsibilities_total += len(expected_responsibilities & active_responsibilities)

        case_leakage = 0
        case_high_value = 0
        for item in missing:
            question = str(item.get("question") or "").strip().lower()
            leaked = any(term in question for term in IMPLEMENTATION_LANGUAGE)
            case_leakage += int(leaked)
            case_high_value += int(bool(question) and not leaked)
        gap_total += len(missing)
        high_value_gaps += case_high_value
        leakage_total += case_leakage
        genre_only_activation_count += len(graph.detect_mechanics([], context={
            "genre": case.get("genre") or case.get("kind"),
            "taxonomy": case.get("taxonomy") or [],
        }))
        case_reports.append({
            "caseId": case_id,
            "detectedPatterns": sorted(detected_patterns),
            "activeResponsibilities": sorted(active_responsibilities),
            "missingRequirementCount": len(missing),
            "implementationLeakageCount": case_leakage,
        })

    false_positive_patterns = detected_patterns_total - matched_patterns_total
    false_positive_responsibilities = active_responsibilities_total - matched_responsibilities_total
    noise_denominator = detected_patterns_total + active_responsibilities_total
    noise_count = false_positive_patterns + false_positive_responsibilities
    return {
        "caseCount": len(case_reports),
        "patternRecall": _ratio(matched_patterns_total, expected_patterns_total),
        "patternPrecision": _ratio(matched_patterns_total, detected_patterns_total),
        "responsibilityRecall": _ratio(matched_responsibilities_total, expected_responsibilities_total),
        "responsibilityPrecision": _ratio(matched_responsibilities_total, active_responsibilities_total),
        "highValueGapRate": _ratio(high_value_gaps, gap_total),
        "noiseRate": _ratio(noise_count, noise_denominator),
        "implementationLeakageRate": _ratio(leakage_total, gap_total),
        "genreOnlyActivationCount": genre_only_activation_count,
        "executionDimensionCoverage": dict(sorted(execution_dimension_coverage.items())),
        "deliveryIntegrity": {
            "candidateToP5Count": 0,
            "candidateToP6Count": 0,
            "candidateToPresentationCount": 0,
            "candidateToFinalPublicationCount": 0,
        },
        "cases": case_reports,
    }


class MechanicKnowledgeGraph:
    def __init__(self, graph: Mapping[str, Any]):
        validate_mechanic_graph(graph)
        self.graph = dict(graph)
        self.nodes = {str(node["id"]): dict(node) for node in graph.get("nodes") or []}
        self.edges = [dict(edge) for edge in graph.get("edges") or []]

    def pattern(self, name_or_id: str) -> dict[str, Any]:
        pattern_id = name_or_id if name_or_id.startswith("pattern.") else f"pattern.{name_or_id}"
        node = self.nodes.get(pattern_id)
        if not node or node.get("kind") != "pattern":
            raise KeyError(name_or_id)
        return node

    def responsibilities_for(self, pattern_id: str) -> list[dict[str, Any]]:
        target_ids = [
            edge["to"]
            for edge in self.edges
            if edge["from"] == pattern_id and edge["type"] == "may_activate"
        ]
        return [self.nodes[node_id] for node_id in target_ids]

    def detect_mechanics(
        self,
        evidence: Iterable[Mapping[str, Any]],
        context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        evidence = list(evidence)
        signals = _signals(evidence)
        result = []
        for pattern in self.nodes.values():
            if pattern.get("kind") != "pattern":
                continue
            contract = pattern.get("detection") or {}
            if not _contract_matches(contract, signals):
                continue
            required = set(contract.get("allSignals") or [])
            optional = set(contract.get("anySignals") or []) | set(contract.get("signalSet") or [])
            matched_signals = sorted(signals & (required | optional))
            evidence_ids = sorted({
                str(item.get("evidenceId"))
                for item in evidence
                if set(item.get("signalIds") or []).intersection(matched_signals)
            })
            result.append({
                "mechanicType": pattern.get("name") or pattern["id"].removeprefix("pattern."),
                "patternId": pattern["id"],
                "evidenceIds": evidence_ids,
                "existenceSignals": matched_signals,
                "confidence": pattern.get("baseConfidence", "evidence_supported"),
                "relatedEntities": sorted({
                    str(entity_id) for item in evidence for entity_id in item.get("entityIds", [])
                }),
                "relatedMechanics": [],
            })
        return sorted(result, key=lambda item: item["patternId"])

    def activate_responsibilities(
        self,
        detected: Iterable[Mapping[str, Any]],
        *,
        evidence: Iterable[Mapping[str, Any]],
        rules: Iterable[Mapping[str, Any]],
        relations: Iterable[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        detected = list(detected)
        rules = list(rules)
        relations = list(relations)
        signals = _signals(evidence)
        result = []
        for mechanic in detected:
            for responsibility in self.responsibilities_for(str(mechanic["patternId"])):
                matched, rule_ids, relation_types = _activation_contract_match(
                    responsibility.get("activation") or {},
                    signals=signals,
                    detected=True,
                    rules=rules,
                    relations=relations,
                )
                if not matched:
                    continue
                result.append({
                    "patternId": mechanic["patternId"],
                    "responsibilityId": responsibility["id"],
                    "question": responsibility.get("question", ""),
                    "evidenceIds": mechanic.get("evidenceIds", []),
                    "activationSignals": sorted(signals & set(
                        (responsibility.get("activation") or {}).get("anySignals") or []
                    )),
                    "activationRuleIds": rule_ids,
                    "activationRelationTypes": relation_types,
                })
        return sorted(result, key=lambda item: (item["patternId"], item["responsibilityId"]))

    def compose_project_graph(
        self,
        detected: Iterable[Mapping[str, Any]],
        *,
        project_nodes: Iterable[Mapping[str, Any]],
        relations: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        pattern_ids = sorted({str(item["patternId"]) for item in detected})
        nodes = [dict(self.nodes[pattern_id]) for pattern_id in pattern_ids]
        nodes.extend(dict(node) for node in project_nodes)
        edges = [dict(edge) for edge in relations]
        patterns_by_concept: dict[str, list[str]] = {}
        for edge in self.edges:
            if edge["type"] == "shares_concept" and edge["from"] in pattern_ids:
                patterns_by_concept.setdefault(str(edge["to"]), []).append(str(edge["from"]))
        for concept_id, members in sorted(patterns_by_concept.items()):
            if len(members) < 2:
                continue
            nodes.append(dict(self.nodes[concept_id]))
            for source, target in combinations(sorted(set(members)), 2):
                edges.append({
                    "from": source,
                    "to": target,
                    "type": "shared_concept",
                    "conceptId": concept_id,
                })
        unique_nodes = {str(node["id"]): node for node in nodes}
        unique_edges = {
            (str(edge.get("from")), str(edge.get("to")), str(edge.get("type")), str(edge.get("conceptId") or "")): edge
            for edge in edges
        }
        return {
            "nodes": [unique_nodes[node_id] for node_id in sorted(unique_nodes)],
            "edges": [unique_edges[key] for key in sorted(unique_edges)],
        }

    def discover_missing_requirements(
        self,
        active_responsibilities: Iterable[Mapping[str, Any]],
        *,
        rules: Iterable[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        satisfied = {
            str(responsibility_id)
            for rule in rules
            if rule.get("reviewStatus") == "approved"
            for responsibility_id in rule.get("satisfiesResponsibilityIds", [])
        }
        result = []
        for item in active_responsibilities:
            responsibility_id = str(item["responsibilityId"])
            if responsibility_id in satisfied:
                continue
            result.append({
                "patternId": item["patternId"],
                "responsibilityId": responsibility_id,
                "question": item.get("question", ""),
                "sourceEvidenceIds": list(item.get("evidenceIds", [])),
                "status": "unresolved",
            })
        return sorted(result, key=lambda item: (item["patternId"], item["responsibilityId"]))
