from __future__ import annotations

from typing import Any, Iterable, Mapping

from backend.mechanic_knowledge_graph import MechanicKnowledgeGraph


def _authoritative_signal_records(
    evidence: Iterable[Mapping[str, Any]],
    facts: Iterable[Mapping[str, Any]],
    rules: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records = [
        {
            "evidenceId": str(item.get("evidenceId") or ""),
            "signalIds": list(item.get("signalIds") or []),
            "entityIds": list(item.get("entityIds") or []),
        }
        for item in evidence
    ]
    records.extend({
        "evidenceId": str(item.get("factId") or ""),
        "signalIds": list(item.get("existenceSignalIds") or []),
        "entityIds": list(item.get("entityIds") or []),
    } for item in facts)
    records.extend({
        "evidenceId": str(item.get("ruleId") or ""),
        "signalIds": list(item.get("existenceSignalIds") or []),
        "entityIds": list(item.get("entityIds") or []),
    } for item in rules if item.get("reviewStatus") == "approved")
    return [item for item in records if item["signalIds"]]


def build_mechanic_intelligence_projection(
    graph: MechanicKnowledgeGraph,
    *,
    evidence: Iterable[Mapping[str, Any]],
    facts: Iterable[Mapping[str, Any]],
    rules: Iterable[Mapping[str, Any]],
    relations: Iterable[Mapping[str, Any]],
    review: Mapping[str, Any],
    planning: Mapping[str, Any],
    final: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a candidate-only projection without mutating authoritative pipeline data."""
    evidence = list(evidence)
    facts = list(facts)
    rules = list(rules)
    relations = [dict(item) for item in relations]
    signal_records = _authoritative_signal_records(evidence, facts, rules)
    detected = graph.detect_mechanics(signal_records)
    active = graph.activate_responsibilities(
        detected,
        evidence=signal_records,
        rules=rules,
        relations=relations,
    )
    missing = graph.discover_missing_requirements(active, rules=rules)
    entity_ids = sorted({
        str(entity_id)
        for item in signal_records
        for entity_id in item.get("entityIds") or []
        if str(entity_id)
    })
    project_graph = graph.compose_project_graph(
        detected,
        project_nodes=[{"id": entity_id, "kind": "Entity"} for entity_id in entity_ids],
        relations=relations,
    )
    review_candidates = [{
        **item,
        "authority": "candidate_only",
        "publicationEligible": False,
    } for item in missing]
    planning_hints = [{
        "patternId": item["patternId"],
        "responsibilityId": item["responsibilityId"],
        "contentAuthority": "none",
        "mayCreateChapter": False,
    } for item in missing]
    return {
        "detectedMechanics": detected,
        "activeResponsibilities": active,
        "projectMechanicGraph": project_graph,
        "missingRequirements": missing,
        "reviewCandidates": review_candidates,
        "planningHints": planning_hints,
        "approvedRules": [],
        "finalPublication": [],
        "integrity": {
            "candidateRulePromotionCount": 0,
            "planningMutationCount": 0,
            "finalPublicationMutationCount": 0,
            "reviewInputConsumedForActivation": False,
            "planningInputConsumedForActivation": False,
            "finalInputConsumedForActivation": False,
        },
    }
