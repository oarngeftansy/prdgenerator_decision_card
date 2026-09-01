from backend.rule_expansion_depth import (
    calibrate_rule_expansion_depth,
    evaluate_expansion_stop_gate,
)


def _layout(layout_id, owner, title, rules=(), missing=(), params=()):
    return {"layoutId": layout_id, "ownerChapter": owner, "sectionTitle": title,
            "supportingRuleIds": list(rules), "referenceRuleIds": [],
            "missingRuleIds": list(missing), "parameterCarrierIds": list(params),
            "layoutPatternSource": "current > GVE16/ANON"}


def _scope(chapter, mechanic_type, statuses):
    return {"chapterId": chapter, "mechanicType": mechanic_type,
            "scopeItems": [{"scopeItem": key, "existenceStatus": value} for key, value in statuses.items()]}


def test_weapon_expands_gameplay_parameters_but_stops_implementation_details():
    layouts = [_layout("L-W", "W", "攻击规则", ("R-AUTO", "R-TARGET", "R-METHOD"),
                       ("M-DAMAGE",), ("P-RANGE", "P-INTERVAL", "P-DAMAGE"))]
    rules = [{"ruleId": "R-AUTO", "text": "武器无需玩家手动瞄准"},
             {"ruleId": "R-TARGET", "text": "武器选择射程内敌人作为攻击目标"},
             {"ruleId": "R-METHOD", "text": "武器向目标发射投射物或生成持续伤害区域"}]
    plans = calibrate_rule_expansion_depth(
        layouts, {}, [], [], [_scope("W", "attack", {"attack_method": "confirmed", "targeting": "confirmed"})],
        rules, {})
    plan = plans[0]
    assert {p["semantic"] for p in plan["gameplayParameters"]} == {"attack_range", "attack_interval", "damage"}
    assert {s["candidateDimension"] for s in plan["stopReasons"]} >= {
        "multi_target_internal_sorting", "no_target_polling_frequency", "internal_damage_event"}
    assert plan["depthVerdict"] == "under-expanded"


def test_three_choice_keeps_possible_dimensions_out_and_preserves_concrete_effects():
    layouts = [_layout("L-C", "C", "可获取词条", missing=("M-FILTER",)),
               _layout("L-R", "C", "选择结果", rules=("R-RANGE", "R-DAMAGE", "R-DIRECTION"))]
    rules = [{"ruleId": "R-RANGE", "text": "火焰喷射攻击范围扩大30%"},
             {"ruleId": "R-DAMAGE", "text": "雷暴枪伤害增加100%"},
             {"ruleId": "R-DIRECTION", "text": "终极词条将单方向喷射改为四面喷射"}]
    scopes = [_scope("C", "randomization", {"candidate_scope": "confirmed", "prerequisite": "possible",
                                               "max_level": "possible", "duplicate": "possible", "weight": "possible"})]
    plans = calibrate_rule_expansion_depth(layouts, {}, [], [], scopes, rules, {})
    candidate = next(p for p in plans if p["ruleTopic"] == "可获取词条")
    assert [m["semantic"] for m in candidate["missingExecutionDetails"]] == ["candidate_eligibility"]
    stopped = {s["candidateDimension"] for s in candidate["stopReasons"]}
    assert {"prerequisite", "max_level", "duplicate", "weight"} <= stopped
    result = next(p for p in plans if p["ruleTopic"] == "选择结果")
    assert {d["sourceRuleIds"][0] for d in result["confirmedDetails"]} == {"R-RANGE", "R-DAMAGE", "R-DIRECTION"}


def test_contact_damage_interval_remains_conditional_until_continuous_damage_is_confirmed():
    layouts = [_layout("L-M", "M", "接触伤害", ("R-CONTACT",), ("G-MODE",))]
    rules = [{"ruleId": "R-CONTACT", "text": "怪物接触载具后造成伤害"}]
    scopes = [_scope("M", "monster_attack", {"contact_effect": "confirmed", "damage_mode": "strongly_implied",
                                                "sustained_contact_damage": "possible"})]
    plan = calibrate_rule_expansion_depth(layouts, {}, [], [], scopes, rules, {})[0]
    assert [m["semantic"] for m in plan["missingExecutionDetails"]] == ["contact_damage_mode"]
    assert "contact_damage_interval" not in {p["semantic"] for p in plan["gameplayParameters"]}
    assert any(s["candidateDimension"] == "contact_damage_interval" for s in plan["stopReasons"])
    assert plan["depthStatus"] == "under-expanded"


def test_level_flow_does_not_instantiate_possible_victory_wave_or_reward():
    layouts = [_layout("L-L", "L", "关卡推进", missing=("M-LEVEL", "S-TIME"))]
    scopes = [_scope("L", "level_flow", {"player_level_up": "strongly_implied", "time_limit": "strongly_implied",
                                           "failure": "confirmed", "victory": "possible", "wave": "possible",
                                           "reward": "possible"})]
    plan = calibrate_rule_expansion_depth(layouts, {}, [], [], scopes, [], {})[0]
    semantics = {m["semantic"] for m in plan["missingExecutionDetails"]}
    assert semantics == {"growth_accumulation", "time_limit"}
    stopped = {s["candidateDimension"] for s in plan["stopReasons"]}
    assert {"victory", "wave", "reward"} <= stopped


def test_stop_gate_rejects_possible_scope_and_implementation_detail_expansion():
    report = evaluate_expansion_stop_gate([
        {"expansionId": "E", "missingExecutionDetails": [
            {"semantic": "weight", "scopeStatus": "possible", "detailKind": "game_rule"},
            {"semantic": "polling", "scopeStatus": "confirmed", "detailKind": "implementation"}],
         "stopReasons": []}
    ], [_scope("C", "randomization", {"weight": "possible"})])
    assert report["qualityGate"] == "fail"
    assert report["scopeViolationCount"] == 1
    assert report["implementationLeakCount"] == 1


def test_full_pass_covers_every_layout_and_reports_depth_status_counts():
    topics = ["移动规则", "获取与栏位", "攻击规则", "成长与词条", "可获取词条", "触发与选择",
              "刷新", "选择结果", "接触伤害", "关卡推进", "胜负衔接", "结算结果", "数据记录"]
    layouts = [_layout(f"L-{index}", f"C-{index}", topic) for index, topic in enumerate(topics)]
    scopes = [
        _scope("C-0", "movement", {"player_control": "confirmed"}),
        _scope("C-1", "attack", {"acquisition": "confirmed", "loadout_capacity": "strongly_implied"}),
        _scope("C-10", "level_flow", {"failure": "confirmed", "victory": "possible"}),
        _scope("C-11", "settlement", {"displayed_data": "strongly_implied"}),
        _scope("C-12", "settlement", {"recorded_data": "strongly_implied"}),
    ]
    plans = calibrate_rule_expansion_depth(layouts, {}, [], [], scopes, [], {})
    report = evaluate_expansion_stop_gate(plans, scopes)
    assert len(plans) == 13
    assert report["totalLayouts"] == 13
    assert report["appropriate"] + report["underExpanded"] + report["overExpanded"] == 13
    assert all(plan["depthStatus"] in {"appropriate", "under-expanded", "over-expanded"} for plan in plans)


def test_refresh_cost_depth_does_not_default_to_payment_timing_question():
    layout = _layout("L-R", "C", "刷新", rules=("R-COST",), params=("P-COST",))
    scopes = [_scope("C", "randomization", {"refresh": "confirmed", "refresh_cost": "confirmed",
                                               "refresh_count": "possible"})]
    rules = [{"ruleId": "R-COST", "text": "刷新操作存在消耗或替代条件"}]
    plan = calibrate_rule_expansion_depth([layout], {}, [], [], scopes, rules, {})[0]
    missing = {item["semantic"] for item in plan["missingExecutionDetails"]}
    assert "refresh_cost_or_condition" in missing
    assert "refresh_deduction_timing" not in missing
    assert any(item["candidateDimension"] == "payment_timing" for item in plan["stopReasons"])


def test_settlement_and_recording_expand_only_supported_delivery_rules():
    layouts = [_layout("L-S", "S", "结算结果", missing=("M-DISPLAY",)),
               _layout("L-R", "S", "数据记录", missing=("M-RECORD",))]
    scopes = [_scope("S", "settlement", {"displayed_data": "strongly_implied",
                                            "recorded_data": "strongly_implied",
                                            "reward_calculation": "unsupported", "run_data_clear": "unsupported"})]
    plans = calibrate_rule_expansion_depth(layouts, {}, [], [], scopes, [], {})
    settlement = next(plan for plan in plans if plan["ruleTopic"] == "结算结果")
    recording = next(plan for plan in plans if plan["ruleTopic"] == "数据记录")
    assert [item["semantic"] for item in settlement["missingExecutionDetails"]] == ["displayed_data"]
    assert [item["semantic"] for item in recording["missingExecutionDetails"]] == ["recorded_data"]
    assert {item["candidateDimension"] for item in settlement["stopReasons"]} >= {"reward_calculation"}
    assert {item["candidateDimension"] for item in recording["stopReasons"]} >= {"run_data_clear"}
