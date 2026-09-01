from __future__ import annotations

from typing import Any

from backend.graph_semantic_validator import validate_graph_semantics


def evaluate_graph_grounding_quality(graphs: list[dict[str, Any]], decompositions: list[dict[str, Any]]) -> dict[str, Any]:
    per = []
    for graph in graphs:
        local = graph.get("ruleDecompositions") or [item for item in decompositions if item["ruleId"] in graph.get("supportingRuleIds", [])]
        validation = validate_graph_semantics(graph, local)
        expected = {(item["ruleId"], component["nodeSemantic"]) for item in local for component in item.get("components", [])}
        actual = {(rule_id, node["semantic"]) for node in graph.get("nodes", []) if node.get("status") == "confirmed" for rule_id in node.get("supportingRuleIds", [])}
        if not expected:
            per.append({"mechanicId": graph["mechanicId"], "name": graph.get("name"), "score": 0.0,
                        "assessmentStatus": "not_assessable", "ruleSemanticRetention": None,
                        "findingCount": 0, "findings": []})
            continue
        retention = len(expected & actual) / len(expected)
        findings = validation["findings"]
        node_errors = sum(item["code"] in {"result_mislabeled_as_trigger", "condition_trigger_confusion", "state_transition_confusion", "output_dependency_confusion", "node_role_mismatch"} for item in findings)
        edge_errors = sum(item["code"] in {"edge_direction_invalid", "condition_ref_missing", "edge_endpoint_missing"} for item in findings)
        derivation_errors = sum(item["code"] in {"derived_provenance_missing", "redundant_intermediate_node"} for item in findings)
        node_accuracy = max(0.0, 1.0 - node_errors / max(1, len(actual)))
        edge_accuracy = max(0.0, 1.0 - edge_errors / max(1, len(graph.get("edges", []))))
        upgrade_accuracy = max(0.0, 1.0 - derivation_errors / max(1, sum(node.get("status") == "derived_structure" for node in graph.get("nodes", []))))
        dimensions = {"ruleInformationRetention": round(30 * retention, 2), "confirmedNodeSemanticAccuracy": round(25 * node_accuracy, 2),
                      "edgeDirectionAndRelation": round(35 * edge_accuracy, 2), "upgradeDowngradeCorrectness": round(10 * upgrade_accuracy, 2)}
        score = round(sum(dimensions.values()), 2)
        per.append({"mechanicId": graph["mechanicId"], "name": graph.get("name"), "score": score, "assessmentStatus": "assessed",
                    "dimensions": dimensions, "ruleSemanticRetention": round(100 * retention, 2), "findingCount": len(findings), "findings": findings})
    assessed = [item for item in per if item["assessmentStatus"] == "assessed"]
    return {"evaluatorVersion": "graph-grounding-quality-v1", "total": round(sum(item["score"] for item in assessed) / len(assessed), 2) if assessed else 0.0,
            "perMechanic": per}


def evaluate_effective_reconstruction_depth(coverage_report: dict[str, Any], quality_report: dict[str, Any]) -> dict[str, Any]:
    quality = {item["mechanicId"]: item["score"] for item in quality_report.get("perMechanic", [])}
    per = []
    for item in coverage_report.get("perMechanic", []):
        graph_quality = quality.get(item["mechanicId"], 0.0)
        per.append({"mechanicId": item["mechanicId"], "reconstructionCoverage": item["score"],
                    "graphGroundingQuality": graph_quality,
                    "effectiveReconstructionDepth": round(item["score"] * graph_quality / 100, 2)})
    return {"evaluatorVersion": "effective-reconstruction-depth-v1",
            "formula": "Reconstruction Coverage × Graph Grounding Quality",
            "total": round(sum(item["effectiveReconstructionDepth"] for item in per) / len(per), 2) if per else 0.0,
            "perMechanic": per}
