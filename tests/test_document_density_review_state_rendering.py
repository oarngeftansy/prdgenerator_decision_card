from backend.document_density_review_state_rendering import (
    build_review_state_density_preview,
    evaluate_document_density_gate,
)


def _chapter(chapter_id, title, statements):
    return {"chapterId": chapter_id, "chapterTitle": title, "statements": statements}


def _statement(semantic, text, *rule_ids):
    return {"statementId": f"S-{semantic}", "semantic": semantic, "text": text,
            "supportingRuleIds": list(rule_ids)}


def _decision(key, owner, route, topic, *, dependency=None):
    return {"decisionId": f"D-{key}", "decisionKey": key, "ownerChapter": owner,
            "ruleTopic": topic, "route": route, "reviewStage": route,
            "approvalStatus": "pending_evidence" if route == "Evidence Recheck" else "unreviewed",
            "dependency": dependency, "options": [{"label": "不得进入正文"}]}


def test_approved_rules_are_condensed_without_losing_rule_provenance():
    chapters = [_chapter("WEAPON", "武器攻击", [
        _statement("automatic_targeting", "武器无需玩家手动瞄准，自动选择射程内的敌人发起攻击。", "R-A", "R-B"),
        _statement("attack_method", "攻击时，武器向目标发射投射物或生成持续伤害区域。", "R-C"),
    ])]
    result = build_review_state_density_preview(chapters, [], [])
    weapon = result["chapters"][0]
    assert weapon["lines"][0]["text"] == "武器自动攻击射程内敌人，无需玩家手动瞄准。"
    assert weapon["lines"][0]["supportingRuleIds"] == ["R-A", "R-B"]
    assert weapon["lines"][1]["text"] == "武器攻击时，向目标发射投射物或生成持续伤害区域。"


def test_pending_review_states_render_as_short_items_and_hidden_states_do_not_leak():
    chapters = [_chapter("LEVEL", "关卡流程", [
        _statement("vehicle_zero_hp_failure", "载具生命值归零时关卡失败。", "R-FAIL")])]
    decisions = [
        _decision("growth_source", "LEVEL", "P4", "关卡推进"),
        _decision("upgrade_basis", "LEVEL", "P4", "关卡推进"),
        _decision("time_limit", "LEVEL", "P6", "关卡推进"),
        _decision("failure_result", "LEVEL", "Evidence Recheck", "胜负衔接"),
        _decision("resume_combat", "LEVEL", "Suppress", "关卡推进"),
    ]
    result = build_review_state_density_preview(chapters, decisions, [])
    texts = [line["text"] for line in result["chapters"][0]["lines"]]
    assert texts == ["载具生命值归零时关卡失败。", "成长规则：待确认。", "关卡时限：待确认。"]
    assert all("不得进入正文" not in text for text in texts)
    assert {item["decisionKey"] for item in result["audit"]["evidenceRecheckSuppressed"]} == {"failure_result"}
    assert {item["decisionKey"] for item in result["audit"]["suppressedItemsRemoved"]} == {"resume_combat"}


def test_dependent_parameters_stay_hidden_until_parent_rule_is_approved():
    chapters = [_chapter("WEAPON", "武器攻击", [])]
    decisions = [
        _decision("damage_model", "WEAPON", "P4", "攻击规则"),
        _decision("damage_fixed_value", "WEAPON", "P6", "攻击规则",
                  dependency={"decisionId": "D-damage_model", "whenOption": "fixed"}),
        _decision("attack_range", "WEAPON", "P6", "攻击规则"),
    ]
    result = build_review_state_density_preview(chapters, decisions, [])
    texts = [line["text"] for line in result["chapters"][0]["lines"]]
    assert texts == ["伤害计算：待确认。", "攻击范围：待确认。"]


def test_same_owner_parameter_from_another_rule_topic_does_not_pollute_attack_chapter():
    chapters = [_chapter("WEAPON", "武器攻击", [])]
    decisions = [
        _decision("weapon_slot_capacity", "WEAPON", "P6", "获取与栏位"),
        _decision("attack_interval", "WEAPON", "P6", "攻击规则"),
    ]
    result = build_review_state_density_preview(chapters, decisions, [])
    assert [line["text"] for line in result["chapters"][0]["lines"]] == ["攻击间隔：待确认。"]


def test_specific_affix_rules_suppress_the_redundant_abstract_summary():
    chapters = [_chapter("AFFIX", "词条", [
        _statement("affix_attack_change", "玩家选择词条后，已选武器的攻击方式发生改变。", "R-SUM"),
        _statement("fire_range", "火焰喷射：攻击范围提高30%。", "R-FIRE"),
        _statement("thunder_damage", "雷暴枪：伤害提高100%。", "R-THUNDER"),
        _statement("ultimate_direction", "终极词条：喷射方向由单方向改为四向。", "R-ULT"),
    ])]
    result = build_review_state_density_preview(chapters, [], [])
    texts = [line["text"] for line in result["chapters"][0]["lines"]]
    assert texts == ["火焰喷射：攻击范围+30%。", "雷暴枪：伤害+100%。", "终极词条：喷射方向由单方向改为四向。"]
    assert all("R-SUM" in line["supportingRuleIds"] for line in result["chapters"][0]["lines"])
    assert result["audit"]["deletedItems"][0]["reason"] == "abstract_summary_over_specific_rule"


def test_density_gate_catches_review_leaks_and_over_compression():
    bad = {"chapters": [{"chapterTitle": "武器攻击", "lines": [
        {"text": "怪物接触载具后如何结算？接触一次或持续接触。", "supportingRuleIds": []},
        {"text": "攻击。", "supportingRuleIds": ["R-A"]},
        {"text": "失败后界面：待确认。", "supportingRuleIds": [], "state": "pending_evidence"},
    ]}], "audit": {"evidenceRecheckSuppressed": [], "suppressedItemsRemoved": []}}
    report = evaluate_document_density_gate(bad)
    assert report["qualityGate"] == "fail"
    assert report["reviewQuestionLeakCount"] > 0
    assert report["reviewOptionLeakCount"] > 0
    assert report["evidenceRecheckAsRuleCount"] > 0
    assert report["ambiguousSubjectCount"] > 0
