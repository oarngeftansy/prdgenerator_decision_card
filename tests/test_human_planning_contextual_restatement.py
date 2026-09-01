import copy

from backend.human_planning_contextual_restatement import (
    build_human_planning_restatements,
    evaluate_human_planning_readability,
)


def _fixtures():
    plans = [
        {"referenceId": "X1", "relationKey": "level_to_three_choice", "sourceChapter": "LEVEL",
         "targetChapter": "THREE", "sourceRule": "R-THREE", "referenceDepth": "short_rule_reference",
         "supportingRuleIds": ["R-THREE"]},
        {"referenceId": "X2", "relationKey": "three_choice_to_affix", "sourceChapter": "THREE",
         "targetChapter": "AFFIX", "sourceRule": "R-EFFECT", "referenceDepth": "short_rule_reference",
         "supportingRuleIds": ["R-EFFECT", "R-RANGE", "R-DAMAGE"]},
        {"referenceId": "X3", "relationKey": "weapon_attack_to_affix", "sourceChapter": "WEAPON",
         "targetChapter": "AFFIX", "sourceRule": "R-EFFECT", "referenceDepth": "short_rule_reference",
         "supportingRuleIds": ["R-EFFECT", "R-RANGE", "R-DAMAGE"]},
        {"referenceId": "X4", "relationKey": "level_to_outcome", "sourceChapter": "LEVEL",
         "targetChapter": "OUTCOME", "sourceRule": "R-FAIL", "referenceDepth": "inline_reference",
         "supportingRuleIds": ["R-FAIL"]},
        {"referenceId": "X5", "relationKey": "outcome_to_settlement", "sourceChapter": "OUTCOME",
         "targetChapter": "SETTLEMENT", "sourceRule": "R-FAIL", "referenceDepth": "no_reference_needed",
         "supportingRuleIds": ["R-FAIL"]},
    ]
    previews = [
        {"chapterId": "LEVEL", "chapterTitle": "关卡流程", "fullDefinitions": []},
        {"chapterId": "THREE", "chapterTitle": "三选一", "fullDefinitions": [
            {"ruleId": "R-THREE", "text": "三选一升级触发时生成三张候选卡"},
            {"ruleId": "R-SELECT", "text": "玩家从三张候选卡中选择一项"},
            {"ruleId": "R-PAUSE", "text": "系统升级触发时暂停游戏"},
            {"ruleId": "R-REFRESH", "text": "玩家点击刷新按钮"},
            {"ruleId": "R-REPLACE", "text": "三选一刷新后替换当前三项候选"}]},
        {"chapterId": "WEAPON", "chapterTitle": "武器攻击", "fullDefinitions": [
            {"ruleId": "R-AUTO", "text": "武器无需玩家手动瞄准"},
            {"ruleId": "R-TARGET", "text": "武器选择射程内敌人作为攻击目标"},
            {"ruleId": "R-METHOD", "text": "武器向目标发射投射物或生成持续伤害区域"}]},
        {"chapterId": "AFFIX", "chapterTitle": "词条", "fullDefinitions": [
            {"ruleId": "R-EFFECT", "text": "已选武器选择后改变攻击方式"},
            {"ruleId": "R-RANGE", "text": "火焰喷射攻击范围扩大30%"},
            {"ruleId": "R-DAMAGE", "text": "雷暴枪伤害增加100%"},
            {"ruleId": "R-DIRECTION", "text": "终极词条将喷射方向由单方向改为四向喷射"}]},
        {"chapterId": "OUTCOME", "chapterTitle": "胜负判定", "fullDefinitions": [
            {"ruleId": "R-FAIL", "text": "载具生命值归零后触发失败事件"}]},
    ]
    return plans, previews


def test_restates_relationships_as_direct_game_rules_without_owner_reference_language():
    plans, previews = _fixtures()
    original = copy.deepcopy(plans)
    chapters = build_human_planning_restatements(plans, previews, [], [], [])
    assert plans == original
    level = next(chapter for chapter in chapters if chapter["chapterId"] == "LEVEL")
    assert [item["text"] for item in level["statements"]] == [
        "战斗等级达到升级条件时触发三选一。", "载具生命值归零时关卡失败。"]
    three = next(chapter for chapter in chapters if chapter["chapterId"] == "THREE")
    assert any(item["text"] == "玩家选择1项后获得该项强化。" for item in three["statements"])
    weapon = next(chapter for chapter in chapters if chapter["chapterId"] == "WEAPON")
    assert any(item["text"] == "词条生效后，可改变武器的攻击方式、攻击范围或伤害。"
               for item in weapon["statements"])
    text = "\n".join(item["text"] for chapter in chapters for item in chapter["statements"])
    assert all(term not in text for term in ("owner", "reference", "详见", "对应词条效果生效", "进入失败判定"))


def test_short_contextual_restatement_can_repeat_core_rule_without_duplicate_full_block():
    plans, previews = _fixtures()
    chapters = build_human_planning_restatements(plans, previews, [], [], [])
    report = evaluate_human_planning_readability(chapters)
    assert report["qualityGate"] == "pass"
    assert report["duplicatedFullRuleBlockCount"] == 0
    assert report["contextualRestatementCount"] == 4
    fail_occurrences = [(chapter["chapterId"], item["mode"]) for chapter in chapters
                        for item in chapter["statements"] if "关卡失败" in item["text"]]
    assert fail_occurrences == [("LEVEL", "contextual_restatement"), ("OUTCOME", "full_definition")]


def test_readability_gate_rejects_audit_headings_relation_jargon_and_internal_ids():
    bad = [{"chapterId": "C", "chapterTitle": "Full definitions", "statements": [
        {"statementId": "S", "text": "详见 V2CH-009，由 target owner 负责定义。",
         "mode": "contextual_restatement", "supportingRuleIds": ["R"]}]}]
    report = evaluate_human_planning_readability(bad)
    assert report["qualityGate"] == "fail"
    assert report["auditStructureLeakCount"] == 1
    assert report["ownerReferenceLanguageCount"] > 0
    assert report["relationTranslationToneCount"] > 0
    assert report["internalIdLeakCount"] == 1
