import pytest

from backend.mechanic_execution_depth import assess_proposal_gates, evaluate_depth_profile


def profile(dimensions):
    return {"mechanicDesignId": "MDES-X", "structuralCompleteness": 100,
            "dimensions": dimensions}


def dimension(dimension_id="DEPTH-X-LOGIC", **overrides):
    value = {
        "depthDimensionId": dimension_id,
        "dimensionFamily": "data_flow",
        "dimensionRole": "core",
        "executionQuestion": "统计结果按什么业务对象归属？",
        "logicClass": "logic",
        "applicability": {"status": "active", "signals": ["statistics_exists"]},
        "satisfactionContract": {
            "requiredSemantics": ["statistics_attribution"],
            "requiredInformation": ["统计单位", "归属对象"],
            "insufficientPatterns": ["按规则统计"],
        },
        "completionRoute": "existing_rule",
    }
    value.update(overrides)
    return value


def test_logic_depth_rejects_presentation_and_accepts_matching_approved_rule():
    presentation = {"ruleId": "P", "valid": True, "ruleStatus": "approved_review",
                    "ruleType": "presentation", "semanticResponsibilities": ["statistics_attribution"]}
    approved = {"ruleId": "R", "valid": True, "ruleStatus": "approved_review",
                "ruleType": "game_rule", "semanticResponsibilities": ["statistics_attribution"]}
    assert evaluate_depth_profile(profile([dimension()]), [presentation], [])["currentCoverage"] == 0
    result = evaluate_depth_profile(profile([dimension()]), [approved], [])
    assert result["currentCoverage"] == 100
    assert result["dimensions"][0]["coverage"]["supportingRuleIds"] == ["R"]


def test_projection_tiers_and_depth_ready_are_not_conflated():
    dims = [
        dimension("DEPTH-CONS", executionQuestion="统计归属如何定义？", completionRoute="conservative_proposal"),
        dimension("DEPTH-DESIGN", dimensionFamily="branch", completionRoute="design_inference",
                  executionQuestion="统计分支如何处理？",
                  satisfactionContract={"requiredSemantics": ["branch_result"], "requiredInformation": ["分支结果"], "insufficientPatterns": []}),
        dimension("DEPTH-HUMAN", dimensionFamily="calculation_algorithm", completionRoute="human_decision",
                  executionQuestion="精确统计权重如何配置？",
                  satisfactionContract={"requiredSemantics": ["exact_weight"], "requiredInformation": ["权重"], "insufficientPatterns": []}),
    ]
    proposals = [
        {"proposalId": "PC", "depthDimensionIds": ["DEPTH-CONS"], "proposalType": "conservative_proposal",
         "qualityGatePassed": True, "compatibilityPassed": True, "coherencePassed": True},
        {"proposalId": "PD", "depthDimensionIds": ["DEPTH-DESIGN"], "proposalType": "design_inference",
         "qualityGatePassed": True, "compatibilityPassed": True, "coherencePassed": True},
    ]
    result = evaluate_depth_profile(profile(dims), [], proposals)
    assert result["currentCoverage"] == 0
    assert result["projectedConservativeCoverage"] == pytest.approx(100 / 3)
    assert result["projectedDesignCoverage"] == pytest.approx(200 / 3)
    assert result["projectedCoverage"] == result["projectedDesignCoverage"]
    assert result["depthReady"] is False


def test_projected_one_hundred_does_not_make_unapproved_core_depth_ready():
    dim = dimension("DEPTH-CORE", executionQuestion="攻击退出后进入什么状态？",
                    completionRoute="design_inference")
    proposal = {"proposalId": "P", "depthDimensionIds": ["DEPTH-CORE"],
                "proposalType": "design_inference", "qualityGatePassed": True,
                "compatibilityPassed": True, "coherencePassed": True}
    result = evaluate_depth_profile(profile([dim]), [], [proposal])
    assert result["projectedCoverage"] == 100
    assert result["depthReady"] is False


def test_parent_gate_and_granularity_gate_prevent_denominator_inflation():
    parent = dimension("DEPTH-REPEAT-EXISTS", dimensionRole="conditional",
                       applicability={"status": "dormant_optional", "signals": []})
    child = dimension("DEPTH-REPEAT-INTERVAL", dimensionRole="conditional",
                      parentDepthDimensionId="DEPTH-REPEAT-EXISTS",
                      applicability={"status": "active", "signals": []})
    with pytest.raises(ValueError, match="parent existence"):
        evaluate_depth_profile(profile([parent, child]), [], [])

    duplicate = dimension("DEPTH-DUPLICATE", executionQuestion=parent["executionQuestion"],
                          applicability={"status": "active", "signals": ["repeat"]})
    active_parent = {**parent, "applicability": {"status": "active", "signals": ["repeat"]}}
    with pytest.raises(ValueError, match="granularity"):
        evaluate_depth_profile(profile([active_parent, duplicate]), [], [])


def test_proposal_gate_rejects_low_information_conflict_and_coherence_issue():
    proposal = {"proposalText": "满足条件后执行。", "depthDimensionIds": ["D"],
                "informationGainTypes": [], "conflictingRuleIds": ["R"],
                "coherenceIssues": ["missing exit"]}
    assert assess_proposal_gates(proposal) == {
        "informationGain": False, "compatibility": False, "coherence": False,
    }
