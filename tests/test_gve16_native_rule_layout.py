from backend.gve16_native_rule_layout import evaluate_layout_quality, reconstruct_native_rule_layouts


def _projection(rule_id, owner, role, refs=()):
    return {"projectionId": f"P-{rule_id}", "sourceRuleId": rule_id, "primaryOwner": owner,
            "referenceOwners": list(refs), "ruleRole": role, "definitionMode": "full_definition"}


def _group(group_id, owner_mechanic, title, rules):
    return {"groupId": group_id, "mechanicId": owner_mechanic, "title": title,
            "knownRules": [{"ruleId": rid, "text": rid, "schemaSlot": slot} for rid, slot in rules],
            "missingRules": [], "gameplayParameters": []}


def test_weapon_attack_uses_mechanic_native_order_and_embeds_parameters():
    projection_set = {
        "ruleProjections": [_projection("R-AUTO", "C-WEAPON", "input_constraint"),
                            _projection("R-TARGET", "C-WEAPON", "target_selection"),
                            _projection("R-METHOD", "C-WEAPON", "processing")],
        "missingLinkProjections": [{"projectionId": "M-DAMAGE", "semanticKey": "damage_resolution",
                                    "question": "伤害如何结算？", "primaryOwner": "C-WEAPON"}],
        "parameterProjections": [
            {"projectionId": "PP-RANGE", "sourceParameterId": "P-RANGE", "primaryOwner": "C-WEAPON"},
            {"projectionId": "PP-INTERVAL", "sourceParameterId": "P-INTERVAL", "primaryOwner": "C-WEAPON"},
            {"projectionId": "PP-DAMAGE", "sourceParameterId": "P-DAMAGE", "primaryOwner": "C-WEAPON"}],
        "systemChapterSkeletons": [{"chapterOwner": "C-WEAPON", "chapterTitle": "武器 / 攻击"}]}
    groups = [_group("G-ATTACK", "M-WEAPON", "攻击规则",
                     [("R-AUTO", "attack_trigger"), ("R-TARGET", "attack_target"), ("R-METHOD", "attack_method")])]
    chains = [{"chainId": "CW", "gameplayParameters": [
        {"sourceId": "P-RANGE", "semantic": "attack_entry", "sourceGroupId": "G-ATTACK"},
        {"sourceId": "P-INTERVAL", "semantic": "next_attack_trigger", "sourceGroupId": "G-ATTACK"},
        {"sourceId": "P-DAMAGE", "semantic": "damage_output", "sourceGroupId": "G-ATTACK"}]}]
    plans = reconstruct_native_rule_layouts(projection_set, groups, chains, {})
    plan = plans[0]
    assert plan["subsectionOrder"] == ["自动攻击", "攻击方式", "伤害结算"]
    automatic = plan["subsections"][0]
    assert automatic["supportingRuleIds"] == ["R-AUTO", "R-TARGET"]
    assert set(automatic["parameterCarrierIds"]) == {"PP-RANGE", "PP-INTERVAL"}
    assert plan["subsections"][2]["missingRuleIds"] == ["M-DAMAGE"]
    assert "参数" not in plan["subsectionOrder"]


def test_three_choice_places_missing_and_refresh_content_in_natural_sections():
    projection_set = {
        "ruleProjections": [_projection("R-TRIGGER", "C-RANDOM", "trigger_and_generation"),
                            _projection("R-SELECT", "C-RANDOM", "player_choice"),
                            _projection("R-REFRESH", "C-REFRESH", "refresh", ["C-RANDOM"]),
                            _projection("R-EFFECT", "C-AFFIX", "progression_effect", ["C-RANDOM"])],
        "missingLinkProjections": [
            {"projectionId": "M-FILTER", "semanticKey": "candidate_filter", "question": "哪些词条可以出现？", "primaryOwner": "C-RANDOM"},
            {"projectionId": "M-RESUME", "semanticKey": "resume_combat", "question": "何时恢复战斗？", "primaryOwner": "C-RANDOM"}],
        "parameterProjections": [{"projectionId": "PP-COUNT", "sourceParameterId": "P-COUNT", "primaryOwner": "C-RANDOM"}],
        "systemChapterSkeletons": [{"chapterOwner": "C-RANDOM", "chapterTitle": "三选一"}]}
    groups = [
        _group("G-CANDIDATE", "M-RANDOM", "可获取词条", []),
        _group("G-RANDOM", "M-RANDOM", "随机规则", [("R-TRIGGER", "random_trigger"), ("R-SELECT", "candidate_selection")]),
        _group("G-REFRESH", "M-RANDOM", "刷新规则", [("R-REFRESH", "refresh_rule")]),
        _group("G-RESULT", "M-RANDOM", "选择结果", [("R-EFFECT", "candidate_effect")])]
    chains = [{"chainId": "CR", "gameplayParameters": [{"sourceId": "P-COUNT", "semantic": "refresh_count", "sourceGroupId": "G-REFRESH"}]}]
    plans = reconstruct_native_rule_layouts(projection_set, groups, chains, {})
    assert [p["sectionTitle"] for p in plans] == ["可获取词条", "触发与选择", "刷新", "选择结果"]
    candidate = plans[0]
    assert candidate["missingRuleIds"] == ["M-FILTER"]
    selection = plans[1]
    assert "玩家选择" in selection["subsectionOrder"]
    assert "M-RESUME" in next(s for s in selection["subsections"] if s["title"] == "玩家选择")["missingRuleIds"]
    refresh = plans[2]
    assert refresh["referenceRuleIds"] == ["R-REFRESH"]
    assert refresh["parameterCarrierIds"] == ["PP-COUNT"]


def test_low_content_monster_attack_stays_direct_bullets_without_empty_subheadings():
    projection_set = {"ruleProjections": [_projection("R-CONTACT", "C-MONSTER", "damage_effect")],
                      "missingLinkProjections": [], "parameterProjections": [],
                      "systemChapterSkeletons": [{"chapterOwner": "C-MONSTER", "chapterTitle": "怪物 / 攻击"}]}
    groups = [_group("G-CONTACT", "M-MONSTER", "接触伤害", [("R-CONTACT", "attack_trigger")])]
    plan = reconstruct_native_rule_layouts(projection_set, groups, [], {})[0]
    assert plan["sectionTitle"] == "接触伤害"
    assert plan["layoutMode"] == "direct_bullets"
    assert plan["subsectionOrder"] == []
    assert plan["supportingRuleIds"] == ["R-CONTACT"]
    assert evaluate_layout_quality([plan])["qualityGate"] == "pass"


def test_layout_gate_rejects_empty_internal_and_uniform_schema_headings():
    bad = {"layoutId": "L1", "ownerChapter": "C", "ruleGroupId": "G", "sectionTitle": "trigger",
           "layoutMode": "subsections", "subsectionOrder": ["条件", "processing"], "subsectionPurpose": ["", ""],
           "supportingRuleIds": [], "referenceRuleIds": [], "missingRuleIds": [], "parameterCarrierIds": [],
           "layoutPatternSource": "template", "subsections": [
               {"title": "条件", "supportingRuleIds": [], "referenceRuleIds": [], "missingRuleIds": [], "parameterCarrierIds": []},
               {"title": "processing", "supportingRuleIds": [], "referenceRuleIds": [], "missingRuleIds": [], "parameterCarrierIds": []}]}
    report = evaluate_layout_quality([bad])
    assert report["qualityGate"] == "fail"
    assert report["emptyHeadingCount"] == 2
    assert report["internalSemanticHeadingCount"] > 0
    assert report["uniformSchemaTraceCount"] > 0
