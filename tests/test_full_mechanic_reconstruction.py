from __future__ import annotations

import pytest

from backend.full_mechanic_reconstruction import (
    apply_planner_value_gate,
    evaluate_core_design_depth,
    load_reconstruction_profile,
    reconstruct_mechanic_model,
    validate_reconstruction,
)


def test_planner_value_gate_requires_a_game_design_consequence():
    high_value = apply_planner_value_gate({
        "responsibilityId": "choice.pool_shortage",
        "plannerValueSignals": ["changes_random_or_result"],
        "detailType": "game_rule",
    })
    supporting = apply_planner_value_gate({
        "responsibilityId": "choice.candidate_stability",
        "plannerValueSignals": [],
        "detailType": "supporting_execution",
    })
    implementation = apply_planner_value_gate({
        "responsibilityId": "weapon.instance_identity",
        "plannerValueSignals": ["changes_state_lifecycle"],
        "detailType": "addressable_instance_model",
    })
    assert high_value["plannerValueClass"] == "high_value"
    assert supporting["plannerValueClass"] == "supporting_execution"
    assert implementation["plannerValueClass"] == "implementation_only"
    assert implementation["countsTowardCoreDepth"] is False


def test_profiles_keep_non_high_value_details_out_of_core_depth_denominator():
    for mechanic_id in ("MDES-CHOICE", "MDES-WEAPON", "MDES-MONSTER"):
        profile = load_reconstruction_profile(mechanic_id)
        assert any(item["plannerValueClass"] != "high_value" for item in profile["responsibilities"])
        assert all(item["countsTowardCoreDepth"] == (item["plannerValueClass"] == "high_value")
                   for item in profile["responsibilities"])


def test_core_depth_excludes_non_core_carriers_and_failed_items():
    contract = {
        "responsibilities": [
            {"responsibilityId": "state", "weight": 1, "requiredSemantics": ["state_model"]},
            {"responsibilityId": "repeat", "weight": 1, "requiredSemantics": ["repeat_model"]},
            {"responsibilityId": "flow", "weight": 1, "requiredSemantics": ["data_flow"]},
            {"responsibilityId": "branch", "weight": 1, "requiredSemantics": ["branch_model"]},
        ]
    }
    model = {
        "designItems": [
            {"designItemId": "D1", "knowledgeClass": "design_inference", "gateStatus": "pass",
             "semanticResponsibilities": ["state_model"]},
            {"designItemId": "D2", "knowledgeClass": "qa", "gateStatus": "pass",
             "semanticResponsibilities": ["repeat_model"]},
            {"designItemId": "D3", "knowledgeClass": "placeholder", "gateStatus": "pass",
             "semanticResponsibilities": ["data_flow"]},
            {"designItemId": "D4", "knowledgeClass": "design_inference", "gateStatus": "fail",
             "semanticResponsibilities": ["branch_model"]},
        ]
    }

    result = evaluate_core_design_depth(model, contract)

    assert result["coveredResponsibilityIds"] == ["state"]
    assert result["missingResponsibilityIds"] == ["repeat", "flow", "branch"]
    assert result["coverage"] == 25.0


def test_parameter_counts_only_with_core_responsibility_and_consumer():
    contract = {"responsibilities": [
        {"responsibilityId": "timing", "weight": 1, "requiredSemantics": ["attack_timing"]},
    ]}
    auxiliary = {"designItems": [{
        "designItemId": "P1", "knowledgeClass": "parameter", "gateStatus": "pass",
        "semanticResponsibilities": ["attack_timing"], "coreMechanicResponsibility": False,
        "consumerDesignItemIds": [],
    }]}
    core = {"designItems": [{
        "designItemId": "P2", "knowledgeClass": "parameter", "gateStatus": "pass",
        "semanticResponsibilities": ["attack_timing"], "coreMechanicResponsibility": True,
        "consumerDesignItemIds": ["ATTACK-CYCLE"],
    }]}

    assert evaluate_core_design_depth(auxiliary, contract)["coverage"] == 0.0
    assert evaluate_core_design_depth(core, contract)["coverage"] == 100.0


def test_validation_rejects_broken_lifecycle_and_generic_information():
    model = {
        "designItems": [{"designItemId": "D1", "text": "满足条件后执行", "gateStatus": "pass",
                         "knowledgeClass": "design_inference", "semanticResponsibilities": ["state"]}],
        "relations": [],
        "parameterContracts": [],
    }
    result = validate_reconstruction(model, {"requiredLifecycleRoles": ["entry", "running", "exit"]})
    assert result["pass"] is False
    assert result["gates"]["informationGain"] is False
    assert result["gates"]["lifecycleClosure"] is False


def test_reconstruction_requires_stable_profile_responsibilities():
    with pytest.raises(ValueError, match="responsibilityId"):
        reconstruct_mechanic_model({
            "mechanicDesignId": "MDES-X",
            "profile": {"responsibilities": [{"family": "state"}]},
            "sourceItems": [],
        })


@pytest.mark.parametrize(("mechanic_id", "required_ids"), [
    ("MDES-CHOICE", {"choice.candidate_pool", "choice.eligibility", "choice.pool_shortage",
                     "choice.refresh_invalidation", "choice.commit_boundary", "choice.cleanup"}),
    ("MDES-WEAPON", {"weapon.instance_identity", "weapon.result_classification", "weapon.slot_branches",
                     "weapon.activation", "weapon.attack_cycle", "weapon.damage_handoff", "weapon.cleanup"}),
    ("MDES-MONSTER", {"monster.target", "monster.contact_evaluation", "monster.first_damage",
                      "monster.movement_lock", "monster.exit_resume", "monster.pending_damage"}),
])
def test_profiles_discover_high_value_second_order_responsibilities(mechanic_id, required_ids):
    profile = load_reconstruction_profile(mechanic_id)
    ids = {item["responsibilityId"] for item in profile["responsibilities"]}
    assert required_ids <= ids
    assert all("answer" not in item for item in profile["responsibilities"])


def test_conditional_children_remain_dormant_without_existence_signals():
    choice = load_reconstruction_profile("MDES-CHOICE", existence_signals=set())
    weapon = load_reconstruction_profile("MDES-WEAPON", existence_signals=set())
    conditional = {
        item["responsibilityId"]: item["applicability"]
        for profile in (choice, weapon)
        for item in profile["responsibilities"]
        if item["role"] == "conditional"
    }
    assert conditional["choice.consecutive_level"] == "dormant_optional"
    assert conditional["weapon.full_slot"] == "dormant_optional"


def test_profile_granularity_has_unique_questions_and_stable_ids():
    for mechanic_id in ("MDES-CHOICE", "MDES-WEAPON", "MDES-MONSTER"):
        profile = load_reconstruction_profile(mechanic_id)
        ids = [item["responsibilityId"] for item in profile["responsibilities"]]
        questions = [item["executionQuestion"] for item in profile["responsibilities"]]
        assert len(ids) == len(set(ids))
        assert len(questions) == len(set(questions))
