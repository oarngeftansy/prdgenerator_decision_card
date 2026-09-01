from backend.hidden_rule_review_integration import build_hidden_rule_review_package


def _gap(key, stage):
    return {"dimensionId": key, "reviewStage": stage, "approvalStatus": "unreviewed",
            "displayText": f"{key}：待确认。", "ruleSemanticId": f"RSC:{key}"}


def test_review_package_routes_rules_to_p4_and_values_to_p6_without_approving():
    package = build_hidden_rule_review_package([
        _gap("damage_model", "P4"),
        _gap("attack_range", "P6"),
        _gap("refresh_reset_scope", "P4"),
        _gap("refresh_max_count", "P6"),
    ])

    assert [item["dimensionId"] for item in package["p4Decisions"]] == [
        "damage_model", "refresh_reset_scope"]
    assert [item["dimensionId"] for item in package["p6Parameters"]] == [
        "attack_range", "refresh_max_count"]
    assert all(item["approvalStatus"] == "unreviewed" for item in
               package["p4Decisions"] + package["p6Parameters"])
    assert package["qualityGate"]["autoApproved"] == 0


def test_hidden_review_uses_planner_language_and_does_not_publish_diagnostic_answers():
    package = build_hidden_rule_review_package([
        _gap("candidate_eligibility", "P4"),
        _gap("acquisition_to_slot_relation", "P4"),
    ])
    visible = " ".join(item["question"] for item in package["p4Decisions"])

    assert "三选一中，哪些武器强化或词条可以出现？" in visible
    assert "获得新武器后，武器栏如何处理？" in visible
    assert "优先填入空武器栏" not in visible
    assert all(item["control"]["type"] == "structured_rule" for item in package["p4Decisions"])
    assert package["qualityGate"]["diagnosticOverrideLeak"] == 0


def test_current_closure_dimensions_produce_eight_p4_and_three_p6_controls():
    keys = [
        ("acquisition_to_slot_relation", "P4"), ("attack_range", "P6"),
        ("attack_interval", "P6"), ("damage_model", "P4"),
        ("candidate_eligibility", "P4"), ("refresh_max_count", "P6"),
        ("refresh_reset_scope", "P4"), ("boss_stage_trigger", "P4"),
        ("growth_source", "P4"), ("upgrade_rule", "P4"),
        ("success_condition", "P4"),
    ]
    package = build_hidden_rule_review_package([_gap(key, stage) for key, stage in keys])

    assert len(package["p4Decisions"]) == 8
    assert len(package["p6Parameters"]) == 3
    assert package["qualityGate"]["pass"] is True
