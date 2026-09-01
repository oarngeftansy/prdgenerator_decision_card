from backend.rule_semantic_grounding import decompose_rule_semantics, ground_mechanic_graphs
from backend.graph_semantic_validator import validate_graph_semantics
from backend.graph_grounding_quality_evaluator import (
    evaluate_effective_reconstruction_depth,
    evaluate_graph_grounding_quality,
)


def _rule(rule_id="R1", behavior="载具沿预设路线自动行进", subject="载具", slot="movement_trigger", chapter="C1"):
    return {"ruleId": rule_id, "ownerChapterId": chapter, "ruleType": "logic", "schemaSlot": slot,
            "subject": subject, "behavior": behavior, "reviewStatus": "approved", "semanticValidity": "valid",
            "evidenceIds": [f"E-{rule_id}"], "sourceFactIds": []}


def _model(mechanic_type="movement", nodes=(), rules=("R1",)):
    return {"mechanicId": "M1", "chapterId": "C1", "chapterIds": ["C1"], "mechanicType": mechanic_type,
            "name": "测试机制", "supportingRuleIds": list(rules), "nodes": list(nodes)}


def test_rule_explicit_object_path_and_action_ground_three_nodes():
    rule = _rule()
    decomposition = decompose_rule_semantics(rule)
    roles = {(item["semanticRole"], item["nodeSemantic"]) for item in decomposition["components"]}
    assert ("object", "moving_object") in roles
    assert ("input_constraint", "movement_path") in roles
    assert ("action", "position_update") in roles
    graph = ground_mechanic_graphs([_model()], [rule], [], {"patterns": ()})[0]
    nodes = {node["semantic"]: node for node in graph["nodes"]}
    assert nodes["moving_object"]["status"] == "confirmed"
    assert nodes["movement_path"]["status"] == "confirmed"


def test_contact_damage_rule_grounds_both_condition_and_damage_result():
    rule = _rule(behavior="怪物接触载具后造成伤害", subject="怪物", slot="attack_trigger")
    decomposition = decompose_rule_semantics(rule)
    roles = {item["semanticRole"] for item in decomposition["components"]}
    assert {"condition", "result"} <= roles
    graph = ground_mechanic_graphs([_model("attack")], [rule], [], {"patterns": ()})[0]
    nodes = {node["semantic"]: node for node in graph["nodes"]}
    assert nodes["attack_trigger"]["status"] == "confirmed"
    assert nodes["damage_output"]["status"] == "confirmed"
    assert nodes["damage_output"]["supportingRuleIds"] == ["R1"]


def test_derived_without_complete_provenance_is_downgraded():
    model = _model(nodes=[{"nodeId": "OLD", "mechanismNode": "bridge", "axis": "processing",
                          "reasoningStatus": "derived_structure", "supportingRuleIds": [],
                          "supportingEvidenceIds": [], "gapLocations": []}], rules=())
    graph = ground_mechanic_graphs([model], [], [], {"patterns": ()})[0]
    assert graph["nodes"][0]["status"] == "hypothesis"
    assert graph["nodes"][0]["derivationType"] is None


def test_transient_persists_until_does_not_activate_lifecycle_persistence():
    graph = {"mechanicId": "M1", "nodes": [
        {"nodeId": "S", "semantic": "selection_state", "nodeType": "state", "status": "confirmed", "supportingRuleIds": ["R1"]},
        {"nodeId": "E", "semantic": "selection_end", "nodeType": "condition", "status": "confirmed", "supportingRuleIds": ["R2"]},
    ], "edges": [{"fromNodeId": "S", "toNodeId": "E", "relationType": "persists_until", "conditionRef": "E", "evidenceStatus": "confirmed", "durationKind": "transientStateDuration"}],
             "supportingRuleIds": ["R1", "R2"], "lifecycle": {"status": "not_applicable", "doesMechanicOwnPersistentState": False}}
    assert validate_graph_semantics(graph, [])["lifecyclePersistenceEdgeCount"] == 0


def test_reversed_edge_lowers_quality_and_result_mislabeled_as_trigger_is_found():
    decompositions = [{"ruleId": "R1", "components": [
        {"semanticRole": "condition", "nodeSemantic": "contact", "text": "接触载具"},
        {"semanticRole": "result", "nodeSemantic": "damage", "text": "造成伤害"},
    ]}]
    nodes = [
        {"nodeId": "C", "semantic": "contact", "nodeType": "condition", "status": "confirmed", "supportingRuleIds": ["R1"]},
        {"nodeId": "D", "semantic": "damage", "nodeType": "result", "status": "confirmed", "supportingRuleIds": ["R1"]},
    ]
    good = {"mechanicId": "GOOD", "nodes": nodes, "edges": [{"fromNodeId": "C", "toNodeId": "D", "relationType": "produces", "conditionRef": "C", "evidenceStatus": "confirmed"}], "supportingRuleIds": ["R1"]}
    bad_nodes = [dict(nodes[0]), {**nodes[1], "nodeType": "trigger"}]
    bad = {"mechanicId": "BAD", "nodes": bad_nodes, "edges": [{"fromNodeId": "D", "toNodeId": "C", "relationType": "produces", "conditionRef": None, "evidenceStatus": "confirmed"}], "supportingRuleIds": ["R1"]}
    quality = evaluate_graph_grounding_quality([good, bad], decompositions)
    assert quality["perMechanic"][0]["score"] > quality["perMechanic"][1]["score"]
    findings = validate_graph_semantics(bad, decompositions)["findings"]
    assert {item["code"] for item in findings} >= {"edge_direction_invalid", "result_mislabeled_as_trigger"}


def test_effective_depth_multiplies_coverage_by_grounding_quality():
    report = evaluate_effective_reconstruction_depth(
        {"perMechanic": [{"mechanicId": "M1", "score": 80}]},
        {"perMechanic": [{"mechanicId": "M1", "score": 50}]},
    )
    assert report["perMechanic"][0]["effectiveReconstructionDepth"] == 40


def test_reversed_branch_direction_is_rejected():
    graph = {"mechanicId": "M1", "nodes": [
        {"nodeId": "A", "semantic": "action", "nodeType": "processing", "status": "confirmed", "supportingRuleIds": ["R1"]},
        {"nodeId": "C", "semantic": "choice", "nodeType": "condition", "status": "confirmed", "supportingRuleIds": ["R1"]},
    ], "edges": [{"fromNodeId": "A", "toNodeId": "C", "relationType": "branches_to", "conditionRef": None, "evidenceStatus": "confirmed"}],
             "supportingRuleIds": ["R1"]}
    assert "edge_direction_invalid" in {item["code"] for item in validate_graph_semantics(graph, [])["findings"]}
