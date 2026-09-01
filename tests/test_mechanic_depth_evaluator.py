from backend.mechanic_depth_evaluator import evaluate_mechanic_depth


def _model():
    nodes = [
        {"nodeId": "N1", "role": "input", "status": "confirmed", "supportingGapIds": []},
        {"nodeId": "N2", "role": "trigger", "status": "confirmed", "supportingGapIds": []},
        {"nodeId": "N3", "role": "processing", "status": "inferred_structure", "supportingGapIds": []},
        {"nodeId": "N4", "role": "state_change", "status": "unresolved", "supportingGapIds": ["G1"]},
        {"nodeId": "N5", "role": "output", "status": "unresolved", "supportingGapIds": ["G2"]},
        {"nodeId": "N6", "role": "exit_boundary", "status": "unresolved", "supportingGapIds": ["G3"]},
        {"nodeId": "N7", "role": "dependency", "status": "inferred_structure", "supportingGapIds": []},
    ]
    return {
        "mechanicId": "M1", "name": "测试机制", "actors": ["对象"], "nodes": nodes,
        "unmappedGapIds": [], "supportingRuleIds": ["R1", "R2"],
        "ruleMechanicalInformationGain": [
            {"ruleId": "R1", "signals": ["input"], "mechanicalInformationGain": 1, "classification": "low_abstraction"},
            {"ruleId": "R2", "signals": ["processing", "result"], "mechanicalInformationGain": 2, "classification": "mechanically_dense"},
        ],
    }


def test_depth_rewards_identified_structure_even_when_answers_remain_unresolved():
    report = evaluate_mechanic_depth([_model()])
    assert report["total"] == 100
    assert report["dimensions"] == {
        "actors": 10, "inputAndTrigger": 15, "processingChain": 20, "stateChange": 10,
        "result": 10, "exitAndBoundary": 10, "dependencies": 10,
        "gapNodeLocalization": 10, "systemAbstraction": 5,
    }


def test_information_gain_identifies_low_abstraction_without_calling_it_filler():
    report = evaluate_mechanic_depth([_model()])
    gain = report["mechanicalInformationGain"]
    assert gain["lowAbstractionRuleIds"] == ["R1"]
    assert gain["averageSignalsPerRule"] == 1.5
    assert gain["fillerCount"] == 0
