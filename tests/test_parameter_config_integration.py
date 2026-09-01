from backend.parameter_config_integration import (
    build_parameter_placement_plans,
    evaluate_gve16_parameter_integration,
    prepare_phase60_inputs,
)


def test_parameter_unknown_does_not_make_rule_depth_under_expanded():
    plan = {"expansionId": "E1", "ownerChapter": "C", "layoutId": "L", "ruleTopic": "移动规则",
            "confirmedDetails": [{"sourceRuleIds": ["R1"], "text": "玩家控制载具横向移动"}],
            "missingExecutionDetails": [],
            "gameplayParameters": [{"semantic": "movement_speed", "label": "移动速度"}],
            "stopReasons": [], "depthStatus": "under-expanded"}
    result = prepare_phase60_inputs([plan], [], [])
    corrected = result["expansionPlans"][0]
    assert corrected["depthStatus"] == "appropriate"
    assert corrected["parameterCompletenessStatus"] == "incomplete"


def test_recorded_data_is_downgraded_when_only_settlement_display_evidence_exists():
    scopes = [{"chapterId": "SETTLEMENT", "mechanicScopes": [{
        "scopeItem": "displayed_data", "existenceStatus": "strongly_implied", "uiBasis": ["R-VISUAL"]}, {
        "scopeItem": "recorded_data", "existenceStatus": "strongly_implied", "uiBasis": ["R-VISUAL"],
        "evidenceBasis": [], "ruleBasis": [], "relationshipBasis": []}]}]
    rules = [{"ruleId": "R-VISUAL", "ruleType": "presentation", "behavior": "结算界面显示通关时间"}]
    plan = {"expansionId": "E", "ownerChapter": "SETTLEMENT", "layoutId": "L", "ruleTopic": "数据记录",
            "confirmedDetails": [], "missingExecutionDetails": [{"semantic": "recorded_data"}],
            "gameplayParameters": [], "stopReasons": [], "depthStatus": "under-expanded"}
    result = prepare_phase60_inputs([plan], scopes, rules)
    correction = result["scopeCorrections"][0]
    assert correction["scopeItem"] == "recorded_data"
    assert correction["correctedStatus"] == "unsupported"
    corrected_plan = result["expansionPlans"][0]
    assert corrected_plan["missingExecutionDetails"] == []
    assert corrected_plan["depthStatus"] == "over-expanded"


def test_parameter_placement_preserves_observed_values_and_rejects_inactive_dimensions():
    plans = [
        {"expansionId": "E-A", "ownerChapter": "WEAPON", "layoutId": "L-A", "ruleTopic": "攻击规则",
         "gameplayParameters": [{"semantic": "attack_range", "label": "攻击范围"},
                                {"semantic": "attack_interval", "label": "攻击间隔"},
                                {"semantic": "damage", "label": "伤害值或公式"}]},
        {"expansionId": "E-R", "ownerChapter": "RANDOM", "layoutId": "L-R", "ruleTopic": "刷新",
         "gameplayParameters": [{"semantic": "refresh_cost", "label": "刷新消耗"}]},
        {"expansionId": "E-T", "ownerChapter": "RANDOM", "layoutId": "L-T", "ruleTopic": "触发与选择",
         "gameplayParameters": []},
        {"expansionId": "E-E", "ownerChapter": "RANDOM", "layoutId": "L-E", "ruleTopic": "选择结果",
         "gameplayParameters": []},
    ]
    rules = [
        {"ruleId": "R-COUNT", "ownerChapterId": "RANDOM", "schemaSlot": "random_trigger",
         "behavior": "三选一升级触发时生成三张候选卡", "evidenceIds": ["EV-1"]},
        {"ruleId": "R-SELECT", "ownerChapterId": "RANDOM", "schemaSlot": "candidate_selection",
         "behavior": "玩家从三张候选卡中选择一项", "evidenceIds": ["EV-2"]},
        {"ruleId": "R-RANGE", "ownerChapterId": "RANDOM", "schemaSlot": "effect_parameter",
         "behavior": "火焰喷射攻击范围扩大30%", "evidenceIds": ["EV-3"]},
        {"ruleId": "R-DAMAGE", "ownerChapterId": "RANDOM", "schemaSlot": "effect_parameter",
         "behavior": "雷暴枪伤害增加100%", "evidenceIds": ["EV-4"]},
        {"ruleId": "R-DIRECTION", "ownerChapterId": "AFFIX", "schemaSlot": "content_catalog_definition",
         "behavior": "终极词条将武器喷射方向由单方向改为四向喷射", "evidenceIds": ["EV-5"]},
    ]
    placements = build_parameter_placement_plans(plans, [], [], rules, [])
    observed = {item["displayLabel"]: item["observedValue"] for item in placements
                if item["parameterClass"] == "observed_value"}
    assert observed == {"候选数量": 3, "选择数量": 1, "火焰喷射攻击范围": 30,
                        "雷暴枪伤害": 100, "终极词条喷射方向": "单方向→四向"}
    semantics = {item["semantic"] for item in placements}
    assert {"attack_range", "attack_interval", "damage", "refresh_cost"} <= semantics
    assert "refresh_count" not in semantics
    assert "contact_damage_interval" not in semantics
    assert all(item["configReferenceStatus"] == "no_confirmed_reference" for item in placements)


def test_parameter_integration_gate_rejects_fake_formula_config_and_table():
    bad = [{"parameterId": "P", "ownerChapter": "C", "ownerLayout": "L", "semantic": "damage",
            "naturalPlacement": "attribute_table", "displayLabel": "Weapon.damageFormulaRef",
            "parameterClass": "unresolved_gameplay_parameter", "valueStatus": "unresolved",
            "observedValue": None, "unit": None, "formulaStatus": "invented",
            "configReferenceStatus": "invented", "sourceEvidence": []}]
    report = evaluate_gve16_parameter_integration(bad, [])
    assert report["qualityGate"] == "fail"
    assert report["internalFieldLabelCount"] == 1
    assert report["unsupportedFormulaCount"] == 1
    assert report["unsupportedConfigReferenceCount"] == 1
    assert report["unnecessaryTableCount"] == 1
