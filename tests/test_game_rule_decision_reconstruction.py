from backend.game_rule_decision_reconstruction import (
    evaluate_rule_group_granularity,
    reconstruct_game_rule_groups,
)


def _model(mechanic_type="randomization"):
    return {
        "mechanicId": "M1", "mechanicType": mechanic_type, "name": "三选一",
        "mechanicScopes": [
            {"scopeItem": "candidate_scope", "existenceStatus": "confirmed", "ruleBasis": ["R1"]},
            {"scopeItem": "refresh", "existenceStatus": "confirmed", "ruleBasis": ["R2"]},
            {"scopeItem": "duplicate", "existenceStatus": "possible", "ruleBasis": []},
            {"scopeItem": "run_reset", "existenceStatus": "unsupported", "ruleBasis": []},
        ],
        "knownGameRules": [
            {"ruleId": "R1", "schemaSlot": "candidate_selection", "gameRuleType": "randomization_rule", "text": "玩家从三个词条中选择一个。"},
            {"ruleId": "R2", "schemaSlot": "refresh_rule", "gameRuleType": "randomization_rule", "text": "刷新后替换当前三个选项。"},
            {"ruleId": "R3", "schemaSlot": "random_trigger", "gameRuleType": "randomization_rule", "text": "升级时触发三选一。"},
        ],
        "missingGameRules": [
            {"sourceId": "G1", "semantic": "candidate_filter", "scopeItem": "candidate_scope", "scopeStatus": "confirmed"},
        ],
        "gameplayParameters": [
            {"sourceId": "P1", "semantic": "refresh_count", "contract": "Randomization.refreshCount"},
        ],
        "implementationDetails": [{"semantic": "atomic_commit"}],
        "explorationCandidates": [{"scopeItem": "duplicate", "existenceStatus": "possible"}],
    }


def test_randomization_rules_are_grouped_by_planner_decision_not_gap():
    groups = reconstruct_game_rule_groups([_model()], approved_rules=[], entity_graph={}, corpora={})
    assert [group["title"] for group in groups] == ["可获取词条", "随机规则", "刷新规则"]
    candidate = groups[0]
    assert candidate["knownRules"] == []
    assert [item["sourceId"] for item in candidate["missingRules"]] == ["G1"]
    assert {item["ruleId"] for item in groups[1]["knownRules"]} == {"R1", "R3"}
    assert groups[2]["gameplayParameters"][0]["semantic"] == "refresh_count"


def test_possible_or_unsupported_scope_never_creates_rule_group():
    groups = reconstruct_game_rule_groups([_model()], approved_rules=[], entity_graph={}, corpora={})
    assert "重复规则" not in {group["title"] for group in groups}
    assert "状态继承与重置" not in {group["title"] for group in groups}
    rejected = {item["scopeItem"] for group in groups for item in group["rejectedDimensions"]}
    assert rejected == {"duplicate", "run_reset"}


def test_parameter_stays_inside_its_game_rule_group_and_implementation_is_excluded():
    groups = reconstruct_game_rule_groups([_model()], approved_rules=[], entity_graph={}, corpora={})
    assert all(group["title"] != "刷新次数" for group in groups)
    assert all("atomic_commit" not in str(group) for group in groups)
    report = evaluate_rule_group_granularity(groups, [_model()])
    assert report["qualityGate"] == "pass"
    assert report["implementationDetailPollutionCount"] == 0
    assert report["unsupportedScopeGroupCount"] == 0


def test_single_gap_does_not_become_a_heading_and_external_corpus_cannot_create_scope():
    model = _model("attack")
    model.update({"name": "武器 / 攻击", "mechanicScopes": [
        {"scopeItem": "attack_method", "existenceStatus": "confirmed", "ruleBasis": ["R1"]},
        {"scopeItem": "unlock", "existenceStatus": "unsupported", "ruleBasis": []}],
        "knownGameRules": [{"ruleId": "R1", "schemaSlot": "attack_method", "gameRuleType": "combat_rule", "text": "武器发射投射物。"}],
        "missingGameRules": [{"sourceId": "G1", "semantic": "damage_output", "scopeItem": "attack_method", "scopeStatus": "confirmed"}],
        "gameplayParameters": [{"sourceId": "P1", "semantic": "damage_output", "contract": "Weapon.damage"}],
        "explorationCandidates": [{"scopeItem": "unlock", "existenceStatus": "unsupported"}]})
    external = {"patterns": [{"category": "progression_pattern", "pattern": "possible unlock", "permission": "exploration_only"}]}
    groups = reconstruct_game_rule_groups([model], [], {}, {"external": external})
    assert [group["title"] for group in groups] == ["攻击规则"]
    assert groups[0]["missingRules"][0]["sourceId"] == "G1"
    assert groups[0]["gameplayParameters"][0]["semantic"] == "damage_output"
