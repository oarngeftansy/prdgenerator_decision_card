import copy
from pathlib import Path

from backend.mechanic_knowledge_graph import load_mechanic_graph
from backend.mechanic_pipeline_adapter import build_mechanic_intelligence_projection


def test_adapter_is_read_only_and_keeps_candidates_out_of_approved_and_final_data():
    graph = load_mechanic_graph(Path("data/planner_knowledge/mechanic-knowledge-graph-v1.json"))
    pipeline = {
        "evidence": [{"evidenceId": "E1", "signalIds": ["signal.commodity_list"], "entityIds": ["shop-1"]}],
        "facts": [{"factId": "F1", "evidenceIds": ["E1"], "existenceSignalIds": ["signal.purchase_action"]}],
        "rules": [{"ruleId": "R1", "reviewStatus": "approved", "satisfiesResponsibilityIds": ["responsibility.price"]}],
        "relations": [{"from": "shop-1", "to": "currency-1", "type": "consumes"}],
        "review": {"proposals": []},
        "planning": {"chapters": []},
        "final": {"rules": ["R1"], "body": []},
    }
    before = copy.deepcopy(pipeline)
    projection = build_mechanic_intelligence_projection(graph, **pipeline)

    assert pipeline == before
    assert [item["mechanicType"] for item in projection["detectedMechanics"]] == ["shop"]
    assert projection["missingRequirements"] == []
    assert projection["approvedRules"] == []
    assert projection["finalPublication"] == []
    assert projection["integrity"]["candidateRulePromotionCount"] == 0
    assert projection["integrity"]["finalPublicationMutationCount"] == 0


def test_adapter_routes_unsatisfied_active_responsibility_to_review_and_planning_hints_only():
    graph = load_mechanic_graph(Path("data/planner_knowledge/mechanic-knowledge-graph-v1.json"))
    projection = build_mechanic_intelligence_projection(
        graph,
        evidence=[{"evidenceId": "E2", "signalIds": ["signal.refresh_action", "signal.commodity_list_changes"]}],
        facts=[],
        rules=[],
        relations=[],
        review={},
        planning={},
        final={},
    )
    assert [item["responsibilityId"] for item in projection["missingRequirements"]] == [
        "responsibility.refresh_result"
    ]
    assert projection["reviewCandidates"][0]["authority"] == "candidate_only"
    assert projection["planningHints"][0]["contentAuthority"] == "none"
    assert projection["finalPublication"] == []


def test_adapter_does_not_activate_from_genre_or_unapproved_review_content():
    graph = load_mechanic_graph(Path("data/planner_knowledge/mechanic-knowledge-graph-v1.json"))
    projection = build_mechanic_intelligence_projection(
        graph,
        evidence=[],
        facts=[],
        rules=[],
        relations=[],
        review={"genre": "tower defense", "proposals": [{"signalIds": ["signal.enemy_wave_spawn", "signal.path_to_objective"]}]},
        planning={},
        final={},
    )
    assert projection["detectedMechanics"] == []
    assert projection["reviewCandidates"] == []
