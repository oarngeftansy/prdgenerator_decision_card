from backend.gap_decision_worthiness import evaluate_gap_decision_worthiness, filter_reasoning_gaps
from backend.reasoning_gap_quality_evaluator import evaluate_reasoning_gap_quality


def _gap(semantic, question="需要确认吗？", gap_type="processing"):
    return {"gapId": f"G-{semantic}", "mechanicId": "M1", "sourceNodeIds": ["N1"],
            "missingNodeSemantic": semantic, "missingRelation": "requires", "gapType": gap_type,
            "question": question, "implementationImpact": "会影响实现。", "qaImpact": "会影响验收。",
            "blockingLevel": "P0 implementation_blocking", "evidenceBasis": ["R1"],
            "derivationReason": "存在机制断点。", "ownerLayer": "Gap", "semanticKey": f"M1:{semantic}"}


def _graph():
    return {"mechanicId": "M1", "nodes": [{"nodeId": "N1", "semantic": "position_update", "nodeType": "processing",
             "status": "confirmed", "supportingRuleIds": ["R1"]}], "edges": [], "supportingRuleIds": ["R1"]}


def test_common_sense_movement_composition_is_suppressed():
    result = evaluate_gap_decision_worthiness(_gap("movement_input_composition"), _graph(), [], {})
    assert result["decisionWorthiness"] == "suppress"
    assert result["reasonCode"] == "common_sense_deterministic"
    assert result["qualifyingCriteria"] == []


def test_trivial_atomicity_and_over_defensive_same_frame_race_are_suppressed():
    atomicity = evaluate_gap_decision_worthiness(_gap("selection_commit"), _graph(), [], {})
    race = evaluate_gap_decision_worthiness(_gap("refresh_selection_exclusion"), _graph(), [], {})
    assert atomicity["reasonCode"] == "implementation_triviality"
    assert race["reasonCode"] == "over_defensive_edge_case"
    assert atomicity["decisionWorthiness"] == race["decisionWorthiness"] == "suppress"


def test_already_implied_refresh_pipeline_is_suppressed():
    result = evaluate_gap_decision_worthiness(_gap("refresh_candidate_pipeline"), _graph(), [], {})
    assert result["decisionWorthiness"] == "suppress"
    assert result["reasonCode"] == "already_implied"


def test_parameter_and_contact_damage_branch_are_kept_for_real_consequences():
    parameter = evaluate_gap_decision_worthiness(_gap("movement_speed", gap_type="parameter"), _graph(), [], {})
    contact = evaluate_gap_decision_worthiness(_gap("contact_damage_processing"), _graph(), [], {})
    assert parameter["decisionWorthiness"] == contact["decisionWorthiness"] == "keep"
    assert "numeric_result" in parameter["qualifyingCriteria"]
    assert "program_branch" in contact["qualifyingCriteria"]
    assert len(contact["alternativeInterpretations"]) >= 2


def test_conditional_followup_is_deferred_until_parent_decision():
    interval = evaluate_gap_decision_worthiness(_gap("contact_damage_interval", gap_type="parameter"), _graph(), [], {})
    exit_gap = evaluate_gap_decision_worthiness(_gap("contact_exit_condition", gap_type="exit_condition"), _graph(), [], {})
    assert interval["decisionWorthiness"] == exit_gap["decisionWorthiness"] == "defer"
    assert interval["dependsOnGapSemantic"] == "contact_damage_processing"


def test_filter_partitions_every_candidate_once_and_quality_penalizes_trivial_retention():
    candidates = [_gap("movement_speed", gap_type="parameter"), _gap("movement_input_composition"), _gap("selection_commit")]
    report = filter_reasoning_gaps(candidates, [_graph()], [], {})
    assert report["candidateCount"] == 3
    assert report["counts"] == {"keep": 1, "suppress": 2, "defer": 0}
    assert len(report["results"]) == 3
    quality = evaluate_reasoning_gap_quality(candidates, [_graph()], decision_results=report["results"])
    by_id = {item["gapId"]: item for item in quality["perGap"]}
    assert by_id["G-movement_speed"]["dimensions"]["decisionRelevance"] > 0
    assert by_id["G-movement_input_composition"]["dimensions"]["nonTriviality"] == 0
    assert by_id["G-selection_commit"]["score"] < by_id["G-movement_speed"]["score"]
