from backend.game_rule_reconstruction import build_game_rule_models, evaluate_game_mechanic_depth, load_game_rule_corpus
from scripts.generate_phase543_game_rule_reconstruction import generate_phase543_game_rules


CORPUS = {
    "templates": {
        "attack": {"gameRuleDimensions": ["usage_rule", "combat_rule", "progression_rule", "limitation_rule"]},
        "randomization": {"gameRuleDimensions": ["randomization_rule", "resource_rule", "state_rule", "lifecycle_rule"]},
    }
}


def _chapter(chapter_id="C1", chapter_type="attack"):
    return {"chapterId": chapter_id, "chapterType": chapter_type, "title": "攻击", "object": "武器"}


def _rule(rule_id="R1", slot="attack_method", behavior="武器向目标发射投射物"):
    return {"ruleId": rule_id, "ownerChapterId": "C1", "schemaSlot": slot, "ruleType": "logic",
            "behavior": behavior, "reviewStatus": "approved", "semanticValidity": "valid"}


def test_game_rules_and_implementation_details_are_structurally_separate():
    reasoning = [
        {"gapId": "G1", "mechanicId": "C1", "missingNodeSemantic": "target_priority", "question": "多目标怎么排序？"},
        {"gapId": "G2", "mechanicId": "C1", "missingNodeSemantic": "weapon_acquisition", "question": "武器怎么获得？"},
    ]
    model = build_game_rule_models([_chapter()], [_rule()], reasoning, CORPUS)[0]
    assert [item["sourceId"] for item in model["implementationDetails"]] == ["G1"]
    assert "G1" not in [item["sourceId"] for item in model["missingGameRules"]]
    assert "G2" in [item["sourceId"] for item in model["missingGameRules"]]


def test_approved_weapon_rule_is_kept_as_confirmed_game_rule():
    model = build_game_rule_models([_chapter()], [_rule()], [], CORPUS)[0]
    assert model["confirmedRules"] == ["R1"]
    assert model["usageRules"][0]["ruleId"] == "R1"
    assert model["gameplayPurpose"] == "定义武器如何被玩家使用并产生战斗结果。"


def test_randomization_template_prioritizes_player_facing_random_and_resource_rules():
    chapter = _chapter("C2", "randomization")
    rule = {**_rule("R2", "random_trigger", "升级时生成三张候选"), "ownerChapterId": "C2"}
    model = build_game_rule_models([chapter], [rule], [], CORPUS)[0]
    assert model["randomRules"][0]["ruleId"] == "R2"
    assert {item["gameRuleType"] for item in model["missingGameRules"]} >= {"resource_rule", "lifecycle_rule"}


def test_technical_questions_do_not_raise_game_mechanic_depth():
    base = build_game_rule_models([_chapter()], [_rule()], [], CORPUS)[0]
    technical = [{"gapId": f"G{i}", "mechanicId": "C1", "missingNodeSemantic": "target_priority",
                  "question": "内部排序？"} for i in range(30)]
    noisy = build_game_rule_models([_chapter()], [_rule()], technical, CORPUS)[0]
    assert len(noisy["implementationDetails"]) == 30
    assert evaluate_game_mechanic_depth([noisy])["total"] == evaluate_game_mechanic_depth([base])["total"]


def test_model_without_confirmed_game_rules_remains_low_depth_even_with_full_template():
    model = build_game_rule_models([_chapter()], [], [], CORPUS)[0]
    report = evaluate_game_mechanic_depth([model])
    assert report["total"] <= 25
    assert report["dimensions"]["gameRuleCoverage"] == 0


def test_runtime_corpus_contains_only_provisional_rule_dimensions():
    corpus = load_game_rule_corpus("data/calibration/gve16/game-rule-corpus.json")
    assert corpus["provisional"] is True
    assert corpus["contentAuthority"] == "none"
    assert "gameRuleDimensions" in corpus["templates"]["randomization"]
    assert "project answers" in corpus["forbidden"]


def test_upstream_conflict_removes_disputed_route_rule_from_confirmed_game_rules():
    route_rule = _rule("R-PATH", "movement_trigger", "载具沿预设路线自动行进")
    chapter = _chapter("C1", "movement")
    conflict = [{"gapId": "G-PATH", "mechanicId": "C1", "missingNodeSemantic": "movement_path_contract",
                 "gapDisposition": "upstream_conflict"}]
    corpus = {"templates": {"movement": {"gameRuleDimensions": ["usage_rule"]}}}
    model = build_game_rule_models([chapter], [route_rule], conflict, corpus)[0]
    assert "R-PATH" not in model["confirmedRules"]
    assert model["rulesUnderReview"][0]["ruleId"] == "R-PATH"


def test_phase543_six_chapter_run_is_read_only_and_implementation_does_not_score(tmp_path):
    summary = generate_phase543_game_rules(tmp_path)
    assert summary["modelCount"] == 6
    assert summary["gameMechanicDepth"] < 30
    assert summary["implementationDetailCount"] > 0
    assert summary["implementationDetailsAffectScore"] is False
    assert summary["finalDocumentGenerated"] is False
    assert summary["modifiedApprovedGapCount"] == 0
    assert summary["p4WriteCount"] == 0
    assert summary["parameterResolverInvoked"] is False
    import json
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
