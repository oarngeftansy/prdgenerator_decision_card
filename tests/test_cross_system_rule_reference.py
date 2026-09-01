from backend.cross_system_rule_reference import (
    build_cross_system_chapter_previews,
    build_cross_system_reference_plans,
    evaluate_gve16_cross_system_references,
)


def _projection(rule, owner, role, refs=()):
    return {"sourceRuleId": rule, "primaryOwner": owner, "referenceOwners": list(refs),
            "ruleRole": role, "definitionMode": "full_definition"}


def _fixtures():
    projections = {"ruleProjections": [
        _projection("R-THREE", "C-THREE", "trigger_and_generation"),
        _projection("R-EFFECT", "C-AFFIX", "progression_effect", ("C-THREE", "C-WEAPON")),
        _projection("R-FAIL", "C-OUTCOME", "failure_rule", ("C-LEVEL",)),
        _projection("R-ATTACK", "C-WEAPON", "processing"),
    ], "systemChapterSkeletons": [
        {"chapterOwner": "C-LEVEL", "chapterTitle": "关卡 / 关卡流程"},
        {"chapterOwner": "C-THREE", "chapterTitle": "三选一 / 候选"},
        {"chapterOwner": "C-WEAPON", "chapterTitle": "武器 / 攻击"},
        {"chapterOwner": "C-AFFIX", "chapterTitle": "词条"},
        {"chapterOwner": "C-OUTCOME", "chapterTitle": "胜负判定"},
        {"chapterOwner": "C-SETTLEMENT", "chapterTitle": "结算"},
    ]}
    chains = [
        {"chainId": "CH-LEVEL", "title": "关卡战斗、成长与结算",
         "systemResponse": [{"semantic": "enter_three_choice", "ruleIds": ["R-THREE"]}],
         "progressionResult": [{"semantic": "apply_growth", "ruleIds": ["R-EFFECT"]}],
         "exitOrNext": [{"semantic": "failure_exit", "ruleIds": ["R-FAIL"]}]},
        {"chainId": "CH-RANDOM", "title": "三选一核心玩法", "entry": {"ruleIds": ["R-THREE"]},
         "progressionResult": [{"semantic": "apply_selected_effect", "ruleIds": ["R-EFFECT"]}]},
        {"chainId": "CH-WEAPON", "title": "武器获得、攻击与强化",
         "systemResponse": [{"semantic": "execute_attack", "ruleIds": ["R-ATTACK"]}],
         "progressionResult": [{"semantic": "apply_weapon_modifier", "ruleIds": ["R-EFFECT"]}]},
    ]
    scopes = [{"chapterId": "C-OUTCOME", "mechanicScopes": [
        {"scopeItem": "failure", "existenceStatus": "confirmed"},
        {"scopeItem": "victory", "existenceStatus": "possible"}]},
        {"chapterId": "C-SETTLEMENT", "mechanicScopes": [
            {"scopeItem": "failure_trigger", "existenceStatus": "unsupported"},
            {"scopeItem": "victory_trigger", "existenceStatus": "unsupported"}]}]
    rules = [{"ruleId": "R-THREE", "behavior": "升级时生成三张候选"},
             {"ruleId": "R-EFFECT", "behavior": "火焰喷射范围扩大30%"},
             {"ruleId": "R-FAIL", "behavior": "载具生命值归零后触发失败事件"},
             {"ruleId": "R-ATTACK", "behavior": "武器执行攻击"}]
    return projections, chains, scopes, rules


def test_builds_natural_short_references_and_suppresses_unsupported_settlement_relation():
    projections, chains, scopes, rules = _fixtures()
    plans = build_cross_system_reference_plans(projections, chains, [], [], [], scopes, rules)
    active = [plan for plan in plans if plan["referenceDepth"] != "no_reference_needed"]
    assert {plan["relationKey"] for plan in active} == {
        "level_to_three_choice", "three_choice_to_affix", "weapon_attack_to_affix", "level_to_outcome"}
    settlement = next(plan for plan in plans if plan["relationKey"] == "outcome_to_settlement")
    assert settlement["referenceDepth"] == "no_reference_needed"
    assert settlement["supportStatus"] == "unsupported"
    assert all("30%" not in plan.get("referenceText", "") for plan in active)
    assert all("详见" not in plan.get("referenceText", "") for plan in active)


def test_chapter_preview_keeps_one_full_definition_and_suppresses_cross_chapter_copies():
    projections, chains, scopes, rules = _fixtures()
    plans = build_cross_system_reference_plans(projections, chains, [], [], [], scopes, rules)
    previews = build_cross_system_chapter_previews(plans, projections, rules, [])
    full_rule_occurrences = {}
    for chapter in previews:
        for definition in chapter["fullDefinitions"]:
            full_rule_occurrences[definition["ruleId"]] = full_rule_occurrences.get(definition["ruleId"], 0) + 1
    assert all(count == 1 for count in full_rule_occurrences.values())
    level = next(chapter for chapter in previews if chapter["chapterId"] == "C-LEVEL")
    assert any("三选一" in item["text"] for item in level["shortCrossSystemReferences"])
    assert "R-THREE" in level["suppressedDuplicatedDefinitions"]


def test_cross_system_gate_rejects_duplicate_unsupported_mechanical_and_id_leaking_references():
    bad_plan = {"referenceId": "REF", "relationKey": "level_to_three_choice", "sourceChapter": "C",
                "targetChapter": "T", "sourceRule": "R", "targetRuleGroup": "G",
                "relationType": "triggers", "referencePurpose": "debug", "referenceDepth": "short_rule_reference",
                "referenceText": "详见 V2CH-009 RULE-X", "supportStatus": "unsupported"}
    preview = [{"chapterId": "C", "fullDefinitions": [{"ruleId": "R"}, {"ruleId": "R"}],
                "shortCrossSystemReferences": [{"text": bad_plan["referenceText"]}],
                "suppressedDuplicatedDefinitions": []}]
    report = evaluate_gve16_cross_system_references([bad_plan], preview)
    assert report["qualityGate"] == "fail"
    assert report["duplicateFullDefinitionCount"] == 1
    assert report["meaninglessReferenceCount"] == 1
    assert report["unsupportedRelationReferenceCount"] == 1
    assert report["internalIdLeakCount"] == 1
