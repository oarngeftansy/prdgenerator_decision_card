from __future__ import annotations

from typing import Any


GROUNDED = frozenset({"confirmed", "derived_structure"})
GROUNDED_EVIDENCE = frozenset({"confirmed", "justified_derived"})


def _score(graph: dict[str, Any]) -> tuple[float, dict[str, float]]:
    rules = set(graph.get("supportingRuleIds", []))
    nodes = [node for node in graph.get("nodes", []) if node.get("status") == "confirmed" or
             (node.get("status") == "derived_structure" and node.get("derivationJustified"))]
    edges = [edge for edge in graph.get("edges", []) if edge.get("evidenceStatus") in GROUNDED_EVIDENCE]
    dimensions = {
        "groundedNodes": min(20.0, len(nodes) * 4.0),
        "meaningfulDirectedEdges": min(25.0, len(edges) * 6.25),
        "stateTransitions": min(15.0, sum(edge["relationType"] in {"transitions_to", "resets"} for edge in edges) * 7.5),
        "branchesAndRepeats": min(10.0, sum(edge["relationType"] in {"branches_to", "repeats_to"} for edge in edges) * 5.0),
        "boundaryRelations": min(10.0, sum(node.get("nodeType") in {"boundary", "exit_condition", "exception"} for node in nodes) * 5.0),
        "lifecycleRelations": min(10.0, sum(edge.get("durationKind") == "lifecyclePersistence" or edge["relationType"] == "resets" for edge in edges) * 5.0),
        "crossSystemDependencies": min(10.0, sum(edge["relationType"] == "depends_on" for edge in edges) * 5.0),
    }
    total = round(sum(dimensions.values()), 2)
    if not rules:
        total = min(total, 20.0)
    return total, dimensions


def evaluate_mechanic_reconstruction_depth(graphs: list[dict[str, Any]]) -> dict[str, Any]:
    per = []
    for graph in graphs:
        score, dimensions = _score(graph)
        per.append({"mechanicId": graph["mechanicId"], "name": graph.get("name"), "score": score, "dimensions": dimensions,
                    "confirmedEdgeCount": sum(edge.get("evidenceStatus") == "confirmed" for edge in graph.get("edges", [])),
                    "justifiedDerivedEdgeCount": sum(edge.get("evidenceStatus") == "justified_derived" for edge in graph.get("edges", []))})
    return {
        "evaluatorVersion": "mechanic-reconstruction-depth-v2", "total": round(sum(item["score"] for item in per) / len(per), 2) if per else 0.0,
        "perMechanic": per, "templateReasoningCoverageScore": 95,
        "legacyScoreDisposition": "Template / Reasoning Coverage Score; not a reconstruction-depth result",
        "executionCompletenessContribution": 0,
    }
