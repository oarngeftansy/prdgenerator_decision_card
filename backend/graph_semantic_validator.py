from __future__ import annotations

from typing import Any


ROLE_TYPES = {
    "object": {"object"}, "condition": {"condition", "entry_condition", "precondition"}, "trigger": {"trigger"},
    "input_constraint": {"input_constraint"}, "target_selection": {"target_selection", "processing"},
    "action": {"processing"}, "state_change": {"state_transition"}, "result": {"result", "output", "effect"},
    "boundary": {"boundary", "exit_condition"}, "numeric": {"parameter"},
}


def validate_graph_semantics(graph: dict[str, Any], decompositions: list[dict[str, Any]]) -> dict[str, Any]:
    findings = []
    nodes = {node["nodeId"]: node for node in graph.get("nodes", [])}
    expected = {(item["ruleId"], component["nodeSemantic"]): component["semanticRole"]
                for item in decompositions for component in item.get("components", [])}
    for node in nodes.values():
        if node.get("status") == "derived_structure" and not all((node.get("derivationType"), node.get("sourceNodeIds"), node.get("sourceRuleIds"), node.get("derivationReason"))):
            findings.append({"code": "derived_provenance_missing", "nodeId": node["nodeId"], "severity": "error"})
        for rule_id in node.get("supportingRuleIds", []):
            role = expected.get((rule_id, node["semantic"]))
            if role and node.get("nodeType") not in ROLE_TYPES[role]:
                if role == "result" and node.get("nodeType") == "trigger":
                    code = "result_mislabeled_as_trigger"
                elif role == "condition" and node.get("nodeType") == "trigger":
                    code = "condition_trigger_confusion"
                elif role == "state_change" and node.get("nodeType") == "state":
                    code = "state_transition_confusion"
                elif role == "result" and node.get("nodeType") in {"upstream_dependency", "downstream_dependency"}:
                    code = "output_dependency_confusion"
                else:
                    code = "node_role_mismatch"
                findings.append({"code": code, "nodeId": node["nodeId"], "ruleId": rule_id, "expectedRole": role, "severity": "error"})
    for edge in graph.get("edges", []):
        start, end = nodes.get(edge["fromNodeId"]), nodes.get(edge["toNodeId"])
        if not start or not end:
            findings.append({"code": "edge_endpoint_missing", "edge": edge, "severity": "error"})
            continue
        relation = edge["relationType"]
        direction_ok = True
        if relation == "produces":
            direction_ok = start.get("nodeType") not in {"result", "output", "effect"} and end.get("nodeType") in {"result", "output", "effect", "processing", "state_transition", "target_selection"}
        elif relation == "triggers":
            direction_ok = start.get("nodeType") in {"condition", "trigger", "entry_condition", "precondition", "target_selection"}
        elif relation == "transitions_to":
            direction_ok = end.get("nodeType") == "state_transition"
        elif relation == "requires":
            direction_ok = start.get("nodeType") in {"processing", "target_selection", "state_transition", "result", "output"} and end.get("nodeType") in {"input_constraint", "parameter", "precondition", "object"}
        elif relation == "depends_on":
            direction_ok = start.get("nodeType") in {"processing", "state_transition", "result", "output"} and end.get("nodeType") in {"parameter", "upstream_dependency", "downstream_dependency"}
        elif relation == "persists_until":
            direction_ok = start.get("nodeType") in {"state", "state_transition"} and end.get("nodeType") in {"condition", "trigger", "exit_condition", "processing"}
        elif relation == "branches_to":
            direction_ok = start.get("nodeType") in {"condition", "state", "state_transition", "result", "output"} and end.get("nodeType") in {"processing", "state_transition", "result", "output"}
        if not direction_ok:
            findings.append({"code": "edge_direction_invalid", "fromNodeId": start["nodeId"], "toNodeId": end["nodeId"], "relationType": relation, "severity": "error"})
        if relation == "triggers" and start.get("nodeType") == "condition" and not edge.get("conditionRef"):
            findings.append({"code": "condition_ref_missing", "fromNodeId": start["nodeId"], "toNodeId": end["nodeId"], "severity": "error"})
    edges = graph.get("edges", [])
    for node in nodes.values():
        if node.get("status") != "derived_structure":
            continue
        incoming = [edge for edge in edges if edge["toNodeId"] == node["nodeId"]]
        outgoing = [edge for edge in edges if edge["fromNodeId"] == node["nodeId"]]
        if len(incoming) == len(outgoing) == 1 and any(edge["fromNodeId"] == incoming[0]["fromNodeId"] and edge["toNodeId"] == outgoing[0]["toNodeId"] for edge in edges):
            findings.append({"code": "redundant_intermediate_node", "nodeId": node["nodeId"], "severity": "warning"})
    return {"mechanicId": graph["mechanicId"], "findingCount": len(findings), "findings": findings,
            "transientStateDurationEdgeCount": sum(edge.get("durationKind") == "transientStateDuration" for edge in graph.get("edges", [])),
            "lifecyclePersistenceEdgeCount": sum(edge.get("durationKind") == "lifecyclePersistence" for edge in graph.get("edges", []))}
