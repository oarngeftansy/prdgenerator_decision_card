import pytest

from backend.mechanic_design_synthesis import (
    accept_mechanic_design,
    build_mechanic_review_view,
    synthesize_mechanic_design,
)


def _proposal(pid, rid, dimension, text, proposal_type="design_inference"):
    return {
        "proposalId": pid, "originRequirementId": rid,
        "executionDimensionId": dimension, "proposalText": text,
        "proposalType": proposal_type, "knownContextRefs": [f"E-{rid}"],
    }


def test_synthesizes_stable_review_only_design_items():
    proposals = [
        _proposal("P1", "R1", "movement.state", "怪物向载具移动。"),
        _proposal("P2", "R2", "attack.entry", "接触后停止移动并造成伤害。"),
    ]
    spec = {
        "mechanicDesignId": "MDES-MONSTER", "mechanicId": "M1",
        "planningTitle": "普通怪物行为", "ownerPath": ["怪物", "普通怪物", "行为逻辑"],
        "items": [
            {"sequence": 1, "text": "怪物向载具移动。", "role": "entry", "proposalIds": ["P1"]},
            {"sequence": 2, "text": "接触后停止移动并造成伤害。", "role": "core_processing", "proposalIds": ["P2"]},
        ],
    }
    result = synthesize_mechanic_design(mechanic_spec=spec, proposals=proposals)
    assert [item["sequence"] for item in result["recommendedDesign"]] == [1, 2]
    assert all(item["designItemId"].startswith("MDI-") for item in result["recommendedDesign"])
    assert all(set(("sequence", "text", "knowledgeClass", "sourceProposalIds",
                        "requirementIds", "parameterRefs", "approvalState")) <= item.keys()
               for item in result["recommendedDesign"])
    assert result["reviewEligibility"] == "ready"
    assert result["confirmed"] is False
    assert result["resolved"] is False
    assert result["publicationEligible"] is False
    again = synthesize_mechanic_design(mechanic_spec=spec, proposals=proposals)
    assert [i["designItemId"] for i in result["recommendedDesign"]] == [
        i["designItemId"] for i in again["recommendedDesign"]]


def test_completeness_is_separate_from_coherence_and_references_prevent_duplication():
    proposals = [_proposal("P1", "R1", "draw.result_commitment", "确认3项结果。")]
    spec = {
        "mechanicDesignId": "MDES-DRAW", "mechanicId": "M2", "planningTitle": "独立抽取",
        "ownerPath": ["局内成长", "独立抽取"],
        "applicableRoles": ["entry", "core_processing", "exit", "next_state"],
        "items": [{"sequence": 1, "text": "确认3项结果。", "role": "core_processing", "proposalIds": ["P1"]}],
    }
    result = synthesize_mechanic_design(
        mechanic_spec=spec, proposals=proposals,
        rule_references=[{"referenceId": "REF-1", "primaryMechanicId": "M-WEAPON",
                          "consumerMechanicId": "M2", "relation": "uses_result_processing"}],
    )
    assert result["coherenceFindings"] == []
    assert result["executionCompleteness"]["score"] == 25.0
    assert set(result["unclosedLifecycleSlots"]) == {"entry", "exit", "next_state"}
    assert result["ruleReferences"][0]["primaryMechanicId"] == "M-WEAPON"


def test_conflict_and_parameter_without_consumer_block_ready():
    proposal = _proposal("P1", "R1", "attack.entry", "接触后造成伤害。")
    spec = {
        "mechanicDesignId": "MDES-M", "mechanicId": "M1", "planningTitle": "普通怪物行为",
        "ownerPath": ["怪物", "行为逻辑"],
        "items": [{"sequence": 1, "text": "接触后造成伤害。", "role": "entry",
                   "proposalIds": ["P1"], "conflictingConfirmedRefs": ["RULE-X"]}],
    }
    result = synthesize_mechanic_design(
        mechanic_spec=spec, proposals=[proposal],
        parameter_placeholders=[{"parameterId": "PAR-1", "text": "攻击间隔", "consumerMechanicId": ""}],
    )
    assert result["reviewEligibility"] == "needs_design_decision"
    assert result["compatibilityFindings"]
    assert any(f["type"] == "parameter_consumer_missing" for f in result["coherenceFindings"])


def test_review_view_hides_lineage_until_expanded_and_never_grants_publication():
    proposal = _proposal("P1", "R1", "attack.entry", "接触后造成伤害。")
    spec = {"mechanicDesignId": "MDES-M", "mechanicId": "M1", "planningTitle": "普通怪物行为",
            "ownerPath": ["怪物", "普通怪物", "行为逻辑"],
            "items": [{"sequence": 1, "text": "接触后造成伤害。", "role": "entry", "proposalIds": ["P1"]}]}
    synthesis = synthesize_mechanic_design(mechanic_spec=spec, proposals=[proposal])
    default = build_mechanic_review_view(synthesis)
    rendered = str(default)
    assert "attack.entry" not in rendered and "P1" not in rendered and "R1" not in rendered
    assert default["actions"] == ["accept_mechanic", "edit", "reject", "expand_evidence"]
    assert default["approvalGranularity"] == "design_item"
    assert default["acceptMechanicEffect"] == "batch_review_decisions_not_rule_merge"
    assert default["publicationEligible"] is False
    expanded = build_mechanic_review_view(synthesis, expand_lineage=True)
    assert expanded["lineage"]["proposalIds"] == ["P1"]
    assert expanded["lineage"]["requirementIds"] == ["R1"]


def test_duplicate_atomic_primary_owner_is_rejected():
    proposal = _proposal("P1", "R1", "weapon.slot_activation", "新武器进入空栏。")
    spec = {"mechanicDesignId": "MDES-W", "mechanicId": "M1", "planningTitle": "武器处理",
            "ownerPath": ["武器", "结果处理"],
            "items": [{"sequence": 1, "text": "新武器进入空栏。", "role": "core_processing", "proposalIds": ["P1"]}]}
    with pytest.raises(ValueError, match="primary owner"):
        synthesize_mechanic_design(mechanic_spec=spec, proposals=[proposal],
                                   atomic_primary_owners={"P1": ["M1", "M2"]})


def test_accept_mechanic_creates_one_approved_rule_per_design_item_with_requirement_lineage():
    synthesis = {
        "mechanicDesignId": "MDES-W", "reviewEligibility": "ready",
        "recommendedDesign": [
            {"designItemId": "D1", "text": "新武器进入空栏。", "sourceProposalIds": ["P1"],
             "requirementIds": ["R1"], "approvalState": "pending_review"},
            {"designItemId": "D2", "text": "命中时造成伤害；具体时点仍需确认。", "sourceProposalIds": ["P2"],
             "requirementIds": ["R2"], "approvalState": "pending_review"},
        ],
    }
    result = accept_mechanic_design(
        synthesis,
        accepted_text_by_design_item={"D2": "投射物命中或持续区域结算时产生伤害。"},
    )
    assert len(result["approvedRules"]) == 2
    assert result["approvedRules"][0]["satisfiesRequirementIds"] == ["R1"]
    assert result["approvedRules"][1]["satisfiesRequirementIds"] == ["R2"]
    assert {rule["sourceDesignItemId"] for rule in result["approvedRules"]} == {"D1", "D2"}
    assert all(rule["approvalAction"] == "accept_mechanic" for rule in result["approvedRules"])
    assert all("待确认" not in rule["text"] and "仍需确认" not in rule["text"]
               for rule in result["approvedRules"])
    assert result["requirementClosureOverlay"] == {"R1": "resolved", "R2": "resolved"}
    assert all(item["approvalState"] == "approved" for item in result["updatedSynthesis"]["recommendedDesign"])
