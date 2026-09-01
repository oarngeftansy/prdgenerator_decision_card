from backend.planner_decision_compression import (
    compress_planner_decisions,
    evaluate_planner_decision_granularity,
)
from scripts.generate_phase543_planner_decision_compression import generate_phase543


def _gap(gap_id, semantic, mechanic="M-RANDOM", question=None):
    return {"gapId": gap_id, "mechanicId": mechanic, "missingNodeSemantic": semantic,
            "originalGap": question or semantic, "gapDisposition": "real_design_decision",
            "plannerReviewEligible": True, "routeTarget": "Planner Review"}


def test_candidate_eligibility_siblings_become_one_design_decision():
    gaps = [_gap("G1", "candidate_filter", question="哪些可以进入？"),
            _gap("G2", "candidate_filter", question="哪些需要移出？"),
            _gap("G3", "candidate_filter", question="满级后怎么处理？"),
            _gap("G4", "candidate_filter", question="前置条件怎么判断？")]
    report = compress_planner_decisions(gaps, [], [])
    assert report["beforePlannerReviewCount"] == 4
    assert report["afterPlannerDecisionCount"] == 1
    decision = report["plannerDecisions"][0]
    assert decision["title"] == "词条入池规则"
    assert decision["designLever"] == "candidate_eligibility"
    assert decision["sourceReasoningGapIds"] == ["G1", "G2", "G3", "G4"]
    assert len(decision["subQuestions"]) == 4


def test_random_constraints_merge_while_weight_stays_a_dependency_not_a_decision():
    planner = [_gap("G1", "candidate_constraints"), _gap("G2", "candidate_constraints")]
    routed = [{"gapId": "GP", "mechanicId": "M-RANDOM", "gapDisposition": "parameter_need",
               "missingNodeSemantic": "candidate_weight_contract", "reducedContract": "CandidateItem.weight"}]
    rules = [{"mechanicId": "M-RANDOM", "schemaSlot": "random_trigger", "behavior": "生成三张候选"},
             {"mechanicId": "M-RANDOM", "schemaSlot": "candidate_selection", "behavior": "玩家点击一项"}]
    decision = compress_planner_decisions(planner, routed, rules)["plannerDecisions"][0]
    assert decision["title"] == "三选一随机规则"
    assert decision["sourceReasoningGapIds"] == ["G1", "G2"]
    assert decision["routedDependencies"] == ["CandidateItem.weight"]
    assert decision["currentKnownRules"] == ["生成三张候选"]


def test_common_sense_and_configuration_fallbacks_are_routed_away_after_compression():
    gaps = [_gap("G1", "empty_candidate"), _gap("G2", "candidate_shortage_behavior"),
            _gap("G3", "selection_state_exit")]
    report = compress_planner_decisions(gaps, [], [])
    assert report["afterPlannerDecisionCount"] == 0
    disposition = {item["gapId"]: item["routeTarget"] for item in report["compressedOut"]}
    assert disposition == {"G1": "Configuration Validation", "G2": "Configuration Validation",
                           "G3": "Implementation Default"}


def test_contact_damage_mode_remains_a_real_design_lever():
    report = compress_planner_decisions([_gap("G1", "contact_damage_processing", "M-ATTACK")], [], [])
    decision = report["plannerDecisions"][0]
    assert decision["title"] == "接触伤害方式"
    assert decision["designLever"] == "contact_damage_mode"
    assert decision["gameplayImpact"]


def test_granularity_gate_detects_duplicate_levers_and_parameter_decisions():
    duplicate = {"decisionId": "D1", "mechanicId": "M", "designLever": "pool", "decisionType": "system_rule",
                 "sourceReasoningGapIds": ["G1"], "subQuestions": ["a"]}
    duplicate2 = dict(duplicate, decisionId="D2", sourceReasoningGapIds=["G2"])
    parameter = dict(duplicate, decisionId="D3", designLever="speed", decisionType="parameter")
    result = evaluate_planner_decision_granularity([duplicate, duplicate2, parameter])
    assert result["qualityGate"] == "fail"
    assert result["findingCounts"]["duplicate_design_lever"] == 1
    assert result["findingCounts"]["parameter_as_decision"] == 1


def test_phase543_real_run_compresses_ten_to_three_without_writes(tmp_path):
    summary = generate_phase543(tmp_path)
    assert summary["beforePlannerReviewCount"] == 10
    assert summary["afterPlannerDecisionCount"] == 3
    assert summary["compressionRatio"] == 0.7
    assert summary["granularityGate"] == "pass"
    assert summary["plannerQuestionGeneratedCount"] == 0
    assert summary["modifiedApprovedGapCount"] == 0
    assert summary["p4WriteCount"] == 0
    assert summary["parameterResolverInvoked"] is False
    import json
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
