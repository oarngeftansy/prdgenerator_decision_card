from backend.gameplay_rule_chain_reconstruction import (
    evaluate_chain_coherence,
    reconstruct_gameplay_rule_chains,
)


def test_rule_chain_requirement_reassessment_preserves_exact_dimension():
    from backend.gameplay_rule_chain_reconstruction import reassess_chain_requirements

    requirements = [{
        "requirementId": "REQ-1", "mechanicId": "MECH-1",
        "executionDimensionId": "attack.exit", "status": "review_required",
    }]
    rules = [{
        "ruleId": "RULE-1", "mechanicId": "MECH-1", "valid": True,
        "satisfiesRequirementIds": ["REQ-1"], "dimensionIds": ["attack.entry"],
    }]
    assert reassess_chain_requirements(requirements, rules)[0]["status"] == "review_required"
    rules[0]["dimensionIds"] = ["attack.exit"]
    assert reassess_chain_requirements(requirements, rules)[0]["status"] == "resolved"


def test_approved_requirement_rules_form_business_chains_without_event_architecture():
    from backend.gameplay_rule_chain_reconstruction import attach_approved_requirement_rules

    rules = [{
        "ruleId": "R-STATS", "mechanicId": "M-STATS", "valid": True,
        "text": "伤害统计以本局武器伤害为统计对象，并以武器为统计单位。",
        "dimensionIds": ["statistics.attribution"], "originRequirementIds": ["REQ-1"],
    }, {
        "ruleId": "R-NEXT", "mechanicId": "M-LEVEL", "valid": True,
        "satisfiesMechanicIds": ["M-LEVEL", "M-SETTLE"],
        "text": "关卡完成后进入成功结算。",
        "dimensionIds": ["battle.next_state", "settlement.entry"],
        "originRequirementIds": ["REQ-2"],
    }]
    chains = attach_approved_requirement_rules([], rules)
    assert {chain["chainType"] for chain in chains} == {"damage_statistics", "boss_completion_settlement"}
    text = str(chains)
    assert "DamageEvent" not in text
    assert "监听" not in text
    assert {rid for chain in chains for rid in chain["supportingRuleIds"]} == {"R-STATS", "R-NEXT"}


def _group(group_id, mechanic_id, title, rules=(), missing=(), parameters=()):
    return {"groupId": group_id, "mechanicId": mechanic_id, "title": title,
            "knownRules": list(rules), "missingRules": list(missing),
            "gameplayParameters": list(parameters), "relatedSystems": []}


def _rule(rule_id, slot, text):
    return {"ruleId": rule_id, "schemaSlot": slot, "text": text}


def test_three_choice_is_reconstructed_as_one_player_loop_with_grounded_breaks():
    groups = [
        _group("G1", "M-RANDOM", "可获取词条", missing=[{"sourceId": "X1", "semantic": "candidate_filter"}]),
        _group("G2", "M-RANDOM", "随机规则", rules=[
            _rule("R1", "random_trigger", "升级时生成三张候选卡"),
            _rule("R2", "selection_pause", "生成候选时暂停游戏"),
            _rule("R3", "candidate_selection", "玩家从三张候选卡中选择一项")]),
        _group("G3", "M-RANDOM", "刷新规则", rules=[
            _rule("R4", "refresh_rule", "玩家可以刷新候选"),
            _rule("R5", "refresh_rule", "刷新后替换当前候选")],
            parameters=[{"sourceId": "P1", "semantic": "refresh_count", "contract": "Randomization.refreshCount"}]),
        _group("G4", "M-RANDOM", "选择结果", rules=[_rule("R6", "candidate_effect", "选择后改变武器效果")]),
    ]
    models = [{"mechanicId": "M-RANDOM", "mechanicType": "randomization", "name": "三选一 / 候选"}]
    chains = reconstruct_gameplay_rule_chains(groups, models, {})
    chain = next(item for item in chains if item["chainType"] == "three_choice_core")
    assert chain["entry"]["ruleIds"] == ["R1"]
    assert {item["ruleIds"][0] for item in chain["playerAction"]} == {"R3", "R4"}
    assert [item["ruleIds"] for item in chain["systemResponse"]] == [["R2"], ["R1"], ["R5"]]
    assert chain["progressionResult"][0]["ruleIds"] == ["R6"]
    assert chain["gameplayParameters"][0]["attachedTo"] == "刷新"
    questions = {item["question"] for item in chain["missingLinks"]}
    assert "目前还不知道哪些词条有资格出现在三选一里。" in questions
    assert "目前还不知道玩家完成选择后何时恢复战斗。" in questions


def test_weapon_rules_form_acquire_attack_and_upgrade_chain_without_unsupported_unlock():
    groups = [
        _group("W1", "M-WEAPON", "获取与栏位", rules=[_rule("W-R1", "acquisition_rule", "抽取后获得武器")],
               missing=[{"sourceId": "WG1", "semantic": "loadout_capacity"}]),
        _group("W2", "M-WEAPON", "攻击规则", rules=[
            _rule("W-R2", "attack_trigger", "武器无需手动瞄准"),
            _rule("W-R3", "attack_target", "武器选择射程内敌人"),
            _rule("W-R4", "attack_method", "武器向目标发动攻击")],
            parameters=[{"sourceId": "WP1", "semantic": "attack_entry", "contract": "Weapon.attackRange"},
                        {"sourceId": "WP2", "semantic": "damage_output", "contract": "Weapon.damage"}]),
        _group("W3", "M-WEAPON", "成长与词条", rules=[_rule("W-R5", "candidate_effect", "词条改变武器攻击方式")]),
    ]
    models = [{"mechanicId": "M-WEAPON", "mechanicType": "attack", "name": "武器 / 攻击",
               "mechanicScopes": [{"scopeItem": "unlock", "existenceStatus": "unsupported"}]}]
    chain = next(item for item in reconstruct_gameplay_rule_chains(groups, models, {}) if item["chainType"] == "weapon_acquire_attack_upgrade")
    assert [item["ruleIds"] for item in chain["systemResponse"]] == [["W-R2"], ["W-R3"], ["W-R4"]]
    assert chain["progressionResult"][0]["ruleIds"] == ["W-R5"]
    assert all("解锁" not in item["question"] for item in chain["missingLinks"])
    assert {p["attachedTo"] for p in chain["gameplayParameters"]} == {"自动攻击"}


def test_cross_system_chain_exposes_missing_gameplay_links_and_excludes_implementation_details():
    groups = [
        _group("M1", "M-MONSTER", "接触伤害", rules=[_rule("MR1", "attack_trigger", "怪物接触载具后造成伤害")]),
        _group("L1", "M-LEVEL", "关卡推进", missing=[{"sourceId": "LG1", "semantic": "player_level_up"}]),
        _group("L2", "M-LEVEL", "胜负规则", rules=[_rule("LR1", "failure_condition", "载具生命归零后失败")]),
        _group("S1", "M-SETTLE", "结算结果", missing=[{"sourceId": "SG1", "semantic": "displayed_data"}]),
    ]
    models = [
        {"mechanicId": "M-MONSTER", "mechanicType": "monster_attack", "name": "怪物 / 攻击", "implementationDetails": [{"semantic": "event_ordering"}]},
        {"mechanicId": "M-LEVEL", "mechanicType": "level_flow", "name": "关卡 / 流程"},
        {"mechanicId": "M-SETTLE", "mechanicType": "settlement", "name": "结算"},
    ]
    chain = next(item for item in reconstruct_gameplay_rule_chains(groups, models, {}) if item["chainType"] == "level_combat_growth_settlement")
    assert set(chain["mechanicIds"]) == {"M-MONSTER", "M-LEVEL", "M-SETTLE"}
    questions = {item["question"] for item in chain["missingLinks"]}
    assert "目前还不知道关卡内经验如何累计并触发升级。" in questions
    assert all("event_ordering" not in str(item) for item in chain.values())
    report = evaluate_chain_coherence([chain], groups)
    assert report["implementationDetailPollutionCount"] == 0


def test_monster_movement_and_contact_damage_form_a_grounded_chain_without_range_invention():
    groups = [_group("MON", "M-MONSTER", "怪物行为", rules=[
        _rule("MON-MOVE", "movement_trigger", "怪物进入战区后向载具移动"),
        _rule("MON-HIT", "attack_trigger", "怪物接触载具后造成伤害"),
    ])]
    models = [{"mechanicId": "M-MONSTER", "mechanicType": "monster_attack", "name": "怪物行为"}]
    chain = next(item for item in reconstruct_gameplay_rule_chains(groups, models, {})
                 if item["chainType"] == "monster_movement_contact")
    assert chain["entry"]["ruleIds"] == ["MON-MOVE"]
    assert chain["systemResponse"][0]["ruleIds"] == ["MON-HIT"]
    assert chain["relationTypes"] == ["sequence", "state_transition"]
    assert all("攻击距离" not in str(value) for value in chain.values())


def test_damage_statistics_and_outcome_settlement_use_only_existing_rules():
    groups = [
        _group("STAT", "M-SETTLE", "伤害统计", rules=[
            _rule("STAT-TOTAL", "statistics_total", "统计本局总伤害"),
            _rule("STAT-SHARE", "statistics_attribution", "按武器统计伤害占比"),
        ], missing=[{"sourceId": "STAT-FORMULA", "semantic": "damage_share_formula"}]),
        _group("END", "M-SETTLE", "结算", rules=[
            _rule("END-FAIL", "failure_condition", "载具生命值归零时关卡失败"),
            _rule("END-RESULT", "settlement_result", "结算展示本局结果"),
        ]),
    ]
    models = [{"mechanicId": "M-SETTLE", "mechanicType": "settlement", "name": "关卡结束"}]
    chains = reconstruct_gameplay_rule_chains(groups, models, {})
    statistics = next(item for item in chains if item["chainType"] == "damage_statistics")
    outcome = next(item for item in chains if item["chainType"] == "outcome_settlement")
    assert [step["ruleIds"] for step in statistics["systemResponse"]] == [["STAT-TOTAL"], ["STAT-SHARE"]]
    assert statistics["missingLinks"][0]["semanticKey"] == "damage_share_formula"
    assert outcome["entry"]["ruleIds"] == ["END-FAIL"]
    assert outcome["exitOrNext"][0]["ruleIds"] == ["END-RESULT"]
    assert set(statistics["supportingRuleIds"] + outcome["supportingRuleIds"]) == {
        "STAT-TOTAL", "STAT-SHARE", "END-FAIL", "END-RESULT"}
