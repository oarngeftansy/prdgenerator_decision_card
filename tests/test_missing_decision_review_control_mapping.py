from backend.missing_decision_review_control_mapping import (
    evaluate_review_control_quality,
    map_missing_items_to_review_controls,
)


def _plan(owner, topic, missing=(), parameters=(), stops=()):
    return {"ownerChapter": owner, "ruleTopic": topic,
            "missingExecutionDetails": [{"semantic": semantic, "question": question,
                                          "sourceMissingIds": [source]}
                                         for semantic, question, source in missing],
            "gameplayParameters": [{"semantic": semantic, "label": label} for semantic, label in parameters],
            "stopReasons": list(stops)}


def test_routes_rules_to_p4_parameters_to_p6_and_defaults_to_suppress():
    plans = [
        _plan("RANDOM", "触发与选择", [("resume_combat", "选择后何时恢复战斗？", "M-RESUME")]),
        _plan("MONSTER", "接触伤害", [("contact_damage_mode", "接触伤害是单次还是持续？", "M-CONTACT")]),
        _plan("WEAPON", "攻击规则", parameters=[("damage", "伤害值或公式")]),
    ]
    placements = [{"parameterId": "P-SPEED", "ownerChapter": "VEHICLE", "ownerLayout": "L-MOVE",
                   "semantic": "movement_speed", "displayLabel": "移动速度",
                   "parameterClass": "unresolved_gameplay_parameter"}]
    decisions = map_missing_items_to_review_controls(plans, placements, [], [], {}, {})
    resume = next(item for item in decisions if item["sourceMissingId"] == "M-RESUME")
    assert resume["route"] == "Suppress"
    assert resume["disposition"] == "natural_default"
    contact = next(item for item in decisions if item["sourceMissingId"] == "M-CONTACT")
    assert contact["decisionClass"] == "rule_choice"
    assert contact["reviewStage"] == "P4"
    assert [option["label"] for option in contact["options"]] == ["接触时结算1次", "持续接触期间周期结算"]
    interval = next(item for item in decisions if item["decisionKey"] == "contact_damage_interval")
    assert interval["reviewStage"] == "P6"
    assert interval["dependency"]["decisionId"] == contact["decisionId"]
    speed = next(item for item in decisions if item["sourceMissingId"] == "P-SPEED")
    assert speed["decisionClass"] == "numeric_parameter"
    assert speed["reviewStage"] == "P6"


def test_damage_and_refresh_are_split_into_rule_form_and_dependent_parameters():
    plans = [_plan("WEAPON", "攻击规则", parameters=[("damage", "伤害值或公式")]),
             _plan("RANDOM", "刷新", parameters=[("refresh_cost", "刷新消耗")])]
    decisions = map_missing_items_to_review_controls(plans, [], [], [], {}, {})
    damage_model = next(item for item in decisions if item["decisionKey"] == "damage_model")
    assert damage_model["reviewStage"] == "P4"
    assert damage_model["decisionClass"] == "complex_rule"
    damage_values = [item for item in decisions if (item.get("dependency") or {}).get("decisionId") == damage_model["decisionId"]]
    assert damage_values and all(item["reviewStage"] == "P6" for item in damage_values)
    refresh_rule = next(item for item in decisions if item["decisionKey"] == "refresh_rule")
    assert refresh_rule["reviewStage"] == "P4"
    assert all(option["basis"] for option in refresh_rule["options"])
    refresh_amount = next(item for item in decisions if item["decisionKey"] == "refresh_cost_amount")
    assert refresh_amount["reviewStage"] == "P6"
    assert refresh_amount["dependency"]["decisionId"] == refresh_rule["decisionId"]


def test_observable_settlement_content_routes_to_evidence_recheck_and_recording_stays_suppressed():
    plans = [_plan("SETTLEMENT", "结算结果", [("displayed_data", "结算展示什么？", "M-DISPLAY")])]
    corrections = [{"chapterId": "SETTLEMENT", "scopeItem": "recorded_data", "correctedStatus": "unsupported"}]
    decisions = map_missing_items_to_review_controls(plans, [], corrections, [], {}, {})
    display = next(item for item in decisions if item["sourceMissingId"] == "M-DISPLAY")
    assert display["route"] == "Evidence Recheck"
    assert display["reviewStage"] == "Evidence"
    recorded = next(item for item in decisions if item["decisionKey"] == "recorded_data")
    assert recorded["route"] == "Suppress"
    assert recorded["approvalStatus"] == "not_applicable"


def test_growth_controls_do_not_promote_possible_corpus_patterns_to_project_options():
    plans = [_plan("LEVEL", "关卡成长", [("growth_accumulation", "成长如何累计？", "M-GROWTH")])]
    decisions = map_missing_items_to_review_controls(plans, [], [], [], {}, {})
    growth_source = next(item for item in decisions if item["decisionKey"] == "growth_source")
    upgrade_basis = next(item for item in decisions if item["decisionKey"] == "upgrade_basis")
    for decision in (growth_source, upgrade_basis):
        assert decision["decisionClass"] == "complex_rule"
        assert decision["uiControl"] == "structured_rule"
        assert decision["options"] == []
        assert decision["inputContract"]["fields"]


def test_quality_gate_rejects_stage_type_mismatch_internal_language_and_auto_approval():
    bad = [{"decisionId": "D", "decisionKey": "candidate_filter", "sourceMissingId": "RGAP-X",
            "ownerChapter": "C", "ruleTopic": "T", "decisionClass": "numeric_parameter",
            "reviewStage": "P4", "route": "P4", "question": "candidate_filter 怎么配置？",
            "options": [{"optionId": "O", "label": "A", "basis": ""}], "recommendedOption": "O",
            "recommendationOnly": False, "recommendationBasis": "AI", "allowCustom": False,
            "inputContract": {"control": "radio"}, "dependency": None, "approvalStatus": "approved",
            "disposition": "review"}]
    report = evaluate_review_control_quality(bad)
    assert report["qualityGate"] == "fail"
    assert report["numericAsRuleChoiceCount"] == 1
    assert report["unsupportedOptionCount"] == 1
    assert report["internalSemanticLeakCount"] > 0
    assert report["autoApprovedAiRecommendationCount"] == 1
