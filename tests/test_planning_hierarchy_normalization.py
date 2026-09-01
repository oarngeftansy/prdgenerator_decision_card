from backend.planning_hierarchy_normalization import (
    evaluate_planning_title_quality,
    normalize_planning_hierarchy,
)


def test_title_quality_combines_composite_and_single_responsibility_checks():
    composite = evaluate_planning_title_quality({
        "title": "获取、栏位与攻击", "responsibilityKinds": ["acquire", "slot", "attack"],
        "parentResponsibility": "武器", "responsibility": "mixed_peer_mechanics",
    })
    assert composite["allowed"] is False
    assert composite["compositeCheck"]["matchedSeparators"] == ["、", "与"]
    assert composite["singleResponsibilityCheck"]["singleResponsibility"] is False

    generic = evaluate_planning_title_quality({
        "title": "综合规则", "responsibilityKinds": ["weapon", "settlement"],
        "parentResponsibility": "核心战斗", "responsibility": "generic_container",
    })
    assert generic["allowed"] is False
    assert "generic_container" in generic["singleResponsibilityCheck"]["findings"]

    real_concept = evaluate_planning_title_quality({
        "title": "合作与对抗", "responsibilityKinds": ["mode"],
        "parentResponsibility": "玩法模式", "responsibility": "mode",
        "businessConceptEvidenceRefs": ["RULE-MODE-1"],
    })
    assert real_concept["allowed"] is True
    assert real_concept["compositeCheck"]["businessConceptExempted"] is True


def test_normalization_projects_explicit_owners_and_only_reports_owner_structure_risk():
    review_units = [{
        "mechanicDesignId": "MDES-MONSTER", "planningTitle": "普通怪物行为",
        "recommendedDesign": [
            {"designItemId": "D1", "text": "怪物向载具移动。", "confirmedRuleIds": ["R1"]},
            {"designItemId": "D2", "text": "接触载具后造成伤害。", "confirmedRuleIds": ["R2"]},
        ],
    }]
    assignments = [
        {"designItemId": "D1", "ownerPath": ["关卡推进", "怪物行为", "普通怪物", "移动"],
         "ownerEvidenceRefs": ["HIER-AUDIT"],
         "ownerSignals": [{"ownerType": "entity", "ownerPath": ["怪物", "普通怪物"]},
                          {"ownerType": "flow", "ownerPath": ["关卡推进", "怪物行为"]}]},
        {"designItemId": "D2", "ownerPath": ["关卡推进", "怪物行为", "普通怪物", "攻击"],
         "ownerEvidenceRefs": ["HIER-AUDIT"]},
    ]
    result = normalize_planning_hierarchy(review_units, assignments)
    assert result["metrics"]["assignmentRate"] == 100.0
    assert result["metrics"]["duplicatePrimaryPlanningNodeCount"] == 0
    assert result["assignments"]["D1"]["ownerPath"] == assignments[0]["ownerPath"]
    assert result["assignments"]["D1"]["planningNodeId"].startswith("PNODE-")
    assert result["assignments"]["D1"]["planningNodeId"] != result["assignments"]["D2"]["planningNodeId"]
    assert result["ownerStructureFindings"][0]["type"] == "mixed_owner_responsibilities"
    assert result["ownerStructureFindings"][0]["ownerChanged"] is False
    assert result["unmappedDesignItemIds"] == []
    leaf_titles = {node["title"] for node in result["planningNodes"] if node["nodeRole"] == "mechanic_responsibility"}
    assert {"移动", "攻击"} <= leaf_titles


def test_missing_explicit_owner_stays_unmapped_instead_of_guessing_from_text():
    result = normalize_planning_hierarchy([{
        "mechanicDesignId": "M1", "planningTitle": "攻击",
        "recommendedDesign": [{"designItemId": "D1", "text": "怪物攻击载具。"}],
    }], [])
    assert result["unmappedDesignItemIds"] == ["D1"]
    assert result["metrics"]["gatePassed"] is False
    assert result["planningNodes"] == []
