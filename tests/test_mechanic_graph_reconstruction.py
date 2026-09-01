from copy import deepcopy
from pathlib import Path

from backend.mechanic_graph_corpus import load_gve16_mechanic_structure_corpus
from backend.mechanic_graph_reconstruction import reconstruct_mechanic_graphs
from backend.mechanic_reconstruction_depth_evaluator import evaluate_mechanic_reconstruction_depth


ROOT = Path(__file__).resolve().parents[1]
CORPUS = load_gve16_mechanic_structure_corpus(ROOT / "data/quality/gve16-mechanic-structure-corpus-v2.json")


def _node(index, status="confirmed", justified=False, rule=True, node_type="processing"):
    return {
        "nodeId": f"N{index}", "semantic": f"node_{index}", "nodeType": node_type,
        "status": status, "supportingRuleIds": [f"R{index}"] if rule else [],
        "supportingGapIds": [], "supportingEvidenceIds": [f"E{index}"] if rule else [],
        "derivationJustified": justified,
    }


def _graph(nodes, edges=(), rules=True, lifecycle=None):
    return {
        "mechanicId": "M1", "mechanicType": "attack", "nodes": nodes, "edges": list(edges),
        "supportingRuleIds": ["R1"] if rules else [],
        "lifecycle": lifecycle or {"status": "not_applicable", "doesMechanicOwnPersistentState": False,
                                     "lifecycleApplicabilityReason": "没有已确认的持续状态。"},
    }


def _edge(a, b, relation="triggers", evidence="confirmed"):
    return {"fromNodeId": a, "toNodeId": b, "relationType": relation,
            "conditionRef": None, "evidenceStatus": evidence}


def test_corpus_is_anonymous_provisional_and_relation_rich():
    assert CORPUS["contentAuthority"] == "none"
    assert CORPUS["provisional"] is True
    assert all(pattern["evidenceSourceRef"].startswith("GVE16/ANON-") for pattern in CORPUS["patterns"])
    assert all(pattern["nodeTypes"] and pattern["edgePatterns"] for pattern in CORPUS["patterns"])
    assert "rawText" not in str(CORPUS)


def test_twenty_template_nodes_without_edges_score_below_five_node_causal_chain():
    template_only = _graph([_node(i, "hypothesis", rule=False) for i in range(20)], rules=False)
    chain_nodes = [_node(i) for i in range(5)]
    chain = _graph(chain_nodes, [_edge(f"N{i}", f"N{i+1}", "transitions_to") for i in range(4)])
    report = evaluate_mechanic_reconstruction_depth([template_only, chain])
    scores = [item["score"] for item in report["perMechanic"]]
    assert scores[0] < scores[1]
    assert scores[0] <= 15


def test_template_inflation_renaming_and_unsupported_lifecycle_cannot_raise_depth():
    base = _graph([_node(1)])
    inflated = deepcopy(base)
    inflated["nodes"] += [_node(i, "derived_structure", justified=False, rule=False) for i in range(2, 12)]
    inflated["lifecycle"] = {"status": "applicable", "doesMechanicOwnPersistentState": True,
                             "lifecycleApplicabilityReason": "template says so"}
    inflated["nodes"] += [_node(12, "derived_structure", False, False, "lifecycle_initialize")]
    report = evaluate_mechanic_reconstruction_depth([base, inflated])
    assert report["perMechanic"][1]["score"] == report["perMechanic"][0]["score"]


def test_deleting_edges_lowers_depth_and_branch_transition_beats_relationless_model():
    nodes = [_node(i) for i in range(5)]
    relationless = _graph(deepcopy(nodes))
    related = _graph(deepcopy(nodes), [
        _edge("N0", "N1", "triggers"), _edge("N1", "N2", "transitions_to"),
        _edge("N1", "N3", "branches_to"), _edge("N3", "N4", "produces"),
    ])
    scores = evaluate_mechanic_reconstruction_depth([relationless, related])["perMechanic"]
    assert scores[1]["score"] > scores[0]["score"]


def test_no_approved_rule_model_cannot_get_high_depth_even_with_complete_template():
    nodes = [_node(i, "derived_structure", justified=True, rule=False) for i in range(8)]
    graph = _graph(nodes, [_edge(f"N{i}", f"N{i+1}", evidence="justified_derived") for i in range(7)], rules=False)
    assert evaluate_mechanic_reconstruction_depth([graph])["total"] <= 20


def test_reconstruction_tightens_derived_and_lifecycle_without_mutating_inputs():
    model = {
        "mechanicId": "M1", "chapterId": "C1", "mechanicType": "attack", "name": "武器 / 攻击",
        "supportingRuleIds": ["R1", "R2"],
        "nodes": [
            {"nodeId": "OLD1", "mechanismNode": "target_selection", "axis": "processing", "reasoningStatus": "confirmed", "supportingRuleIds": ["R1"], "supportingEvidenceIds": ["E1"], "gapLocations": []},
            {"nodeId": "OLD2", "mechanismNode": "target_set_build", "axis": "processing", "reasoningStatus": "derived_structure", "supportingRuleIds": [], "supportingEvidenceIds": [], "gapLocations": []},
            {"nodeId": "OLD3", "mechanismNode": "attack_execution", "axis": "processing", "reasoningStatus": "confirmed", "supportingRuleIds": ["R2"], "supportingEvidenceIds": ["E2"], "gapLocations": []},
            {"nodeId": "OLD4", "mechanismNode": "attack_reset", "axis": "lifecycle_reset", "reasoningStatus": "derived_structure", "supportingRuleIds": [], "supportingEvidenceIds": [], "gapLocations": []},
        ],
    }
    before = deepcopy(model)
    graph = reconstruct_mechanic_graphs([model], [], [], CORPUS)[0]
    indexed = {node["semantic"]: node for node in graph["nodes"]}
    assert model == before
    assert indexed["target_set_build"]["status"] == "derived_structure"
    assert indexed["target_set_build"]["derivationJustified"] is True
    assert indexed["attack_reset"]["status"] == "hypothesis"
    assert graph["lifecycle"]["status"] == "not_applicable"
    assert any(edge["fromNodeId"] == indexed["target_set_build"]["nodeId"] for edge in graph["edges"])
