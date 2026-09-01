from backend.planner_gap_routing import (
    evaluate_planner_signal_to_noise,
    evaluate_planner_routing_quality,
    route_candidate_gaps,
    route_gap_for_planner_significance,
)
from scripts.generate_phase542_planner_gap_routing import generate_phase542


def _gap(semantic, gap_type="processing"):
    return {
        "gapId": f"G-{semantic}", "mechanicId": "M1", "sourceNodeIds": ["N1"],
        "missingNodeSemantic": semantic, "gapType": gap_type, "question": f"{semantic}?",
        "implementationImpact": "会影响实现。", "qaImpact": "会影响验收。",
    }


def _graph():
    return {"mechanicId": "M1", "nodes": [{"nodeId": "N1", "status": "confirmed"}]}


def test_implementation_details_do_not_become_planner_decisions():
    for semantic in ("target_priority", "empty_target_behavior", "movement_input_composition", "movement_input_release"):
        result = route_gap_for_planner_significance(_gap(semantic), _graph(), [], {})
        assert result["gapDisposition"] == "implementation_default"
        assert result["routeTarget"] == "Implementation Default"
        assert result["plannerReviewEligible"] is False
        assert result["createsApprovedRule"] is False


def test_complex_questions_are_reduced_to_parameter_or_entity_contracts():
    cooldown = route_gap_for_planner_significance(_gap("next_attack_trigger", "trigger"), _graph(), [], {})
    attack_type = route_gap_for_planner_significance(_gap("attack_method_selection"), _graph(), [], {})
    assert cooldown["gapDisposition"] == "parameter_need"
    assert cooldown["routeTarget"] == "ParameterResolver"
    assert "attackInterval" in cooldown["reducedContract"]
    assert attack_type["gapDisposition"] == "entity_attribute"
    assert attack_type["routeTarget"] == "Entity Model"
    assert attack_type["reducedContract"] == "Weapon.attackType"


def test_disputed_preset_route_is_routed_upstream_instead_of_extended():
    audit = {"movementRouteRule": {"status": "conflict", "reason": "静态帧不足以证明自动沿预设路线移动。"}}
    result = route_gap_for_planner_significance(_gap("movement_path_contract"), _graph(), [], audit)
    assert result["gapDisposition"] == "upstream_conflict"
    assert result["routeTarget"] == "Rule Review"
    assert result["plannerReviewEligible"] is False


def test_only_gameplay_significant_choices_reach_planner_review():
    contact = route_gap_for_planner_significance(_gap("contact_damage_processing"), _graph(), [], {})
    duplicate = route_gap_for_planner_significance(_gap("candidate_constraints", "boundary"), _graph(), [], {})
    aggregation = route_gap_for_planner_significance(_gap("contact_damage_aggregation", "aggregation"), _graph(), [], {})
    assert contact["gapDisposition"] == duplicate["gapDisposition"] == "real_design_decision"
    assert contact["plannerSalience"] == "high"
    assert aggregation["gapDisposition"] == "implementation_default"


def test_batch_routes_every_candidate_and_signal_to_noise_counts_no_leaked_noise():
    gaps = [_gap("contact_damage_processing"), _gap("target_priority"), _gap("next_attack_trigger", "parameter")]
    report = route_candidate_gaps(gaps, [_graph()], [], {})
    assert report["candidateCount"] == 3
    assert report["dispositionCounts"] == {
        "real_design_decision": 1, "parameter_need": 1, "entity_attribute": 0,
        "implementation_default": 1, "visual_detail": 0, "already_answered_by_evidence": 0,
        "upstream_conflict": 0, "defer": 0,
    }
    signal = evaluate_planner_signal_to_noise(report)
    assert signal["plannerReviewCount"] == 1
    assert signal["plannerReviewNoiseCount"] == 0
    assert signal["plannerSignalToNoiseRatio"] == 1.0
    assert signal["candidateSignalRate"] == 1 / 3
    assert report["plannerQuestionGeneratedCount"] == 0
    quality = evaluate_planner_routing_quality(report)
    assert quality["score"] == 100.0
    assert quality["dimensions"] == {"decisionRelevance": 100.0, "nonTriviality": 100.0, "gameplayConsequence": 100.0}


def test_phase542_real_run_routes_32_without_mutating_sources(tmp_path):
    summary = generate_phase542(tmp_path)
    assert summary["candidateCount"] == 32
    assert summary["dispositionCounts"]["real_design_decision"] == 10
    assert summary["dispositionCounts"]["upstream_conflict"] == 2
    assert summary["plannerSignalToNoise"]["plannerReviewNoiseCount"] == 0
    assert summary["plannerQuestionGeneratedCount"] == 0
    assert summary["modifiedApprovedGapCount"] == 0
    assert summary["parameterResolverInvoked"] is False
    import json
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
