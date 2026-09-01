from backend.core_loop_rule_projection import evaluate_projection_integrity, project_core_loop_rules


def _group(group_id, mechanic_id, title, rule_ids):
    return {"groupId": group_id, "mechanicId": mechanic_id, "title": title,
            "knownRules": [{"ruleId": rid, "schemaSlot": "candidate_effect", "text": "规则"} for rid in rule_ids],
            "missingRules": [], "gameplayParameters": [], "relatedSystems": []}


def test_same_rule_across_local_and_cross_chain_has_one_full_definition():
    groups = [_group("G-RANDOM", "M-RANDOM", "选择结果", ["R-EFFECT"]),
              _group("G-WEAPON", "M-WEAPON", "成长与词条", ["R-EFFECT"])]
    models = [{"mechanicId": "M-RANDOM", "chapterId": "C-RANDOM", "mechanicType": "randomization"},
              {"mechanicId": "M-WEAPON", "chapterId": "C-WEAPON", "mechanicType": "attack"}]
    chains = [
        {"chainId": "CHAIN-LOCAL", "chainType": "three_choice_core", "mechanicIds": ["M-RANDOM"],
         "supportingRuleIds": ["R-EFFECT"], "missingLinks": [], "gameplayParameters": []},
        {"chainId": "CHAIN-CROSS", "chainType": "level_combat_growth_settlement", "mechanicIds": ["M-RANDOM", "M-WEAPON"],
         "supportingRuleIds": ["R-EFFECT"], "missingLinks": [], "gameplayParameters": []},
    ]
    result = project_core_loop_rules(chains, groups, models, {})
    projections = [p for p in result["ruleProjections"] if p["sourceRuleId"] == "R-EFFECT"]
    assert len(projections) == 1
    assert projections[0]["definitionMode"] == "full_definition"
    assert projections[0]["primaryOwner"] == "C-WEAPON"
    assert "CORE-GAMEPLAY-LOOP" in projections[0]["referenceOwners"]


def test_missing_links_receive_specific_system_owners():
    groups = [_group("G-RANDOM", "M-RANDOM", "可获取词条", []),
              _group("G-LEVEL", "M-LEVEL", "关卡推进", []),
              _group("G-WEAPON", "M-WEAPON", "攻击规则", [])]
    models = [{"mechanicId": "M-RANDOM", "chapterId": "C-RANDOM", "mechanicType": "randomization"},
              {"mechanicId": "M-LEVEL", "chapterId": "C-LEVEL", "mechanicType": "level_flow"},
              {"mechanicId": "M-WEAPON", "chapterId": "C-WEAPON", "mechanicType": "attack"}]
    chains = [{"chainId": "CROSS", "chainType": "level_combat_growth_settlement",
               "mechanicIds": ["M-RANDOM", "M-LEVEL", "M-WEAPON"], "supportingRuleIds": [], "gameplayParameters": [],
               "missingLinks": [
                   {"semanticKey": "candidate_filter", "question": "哪些词条可以出现？"},
                   {"semanticKey": "player_level_up", "question": "经验如何触发升级？"},
                   {"semanticKey": "damage_resolution", "question": "如何结算伤害？"}]}]
    result = project_core_loop_rules(chains, groups, models, {})
    owners = {item["semanticKey"]: item["primaryOwner"] for item in result["missingLinkProjections"]}
    assert owners == {"candidate_filter": "C-RANDOM", "player_level_up": "C-LEVEL", "damage_resolution": "C-WEAPON"}
    assert evaluate_projection_integrity(result)["missingLinkWithoutOwnerCount"] == 0


def test_core_loop_is_overview_only_and_system_skeleton_carries_definitions():
    groups = [_group("G-MOVE", "M-MOVE", "移动规则", ["R-MOVE"])]
    models = [{"mechanicId": "M-MOVE", "chapterId": "C-MOVE", "mechanicType": "movement"}]
    chains = [{"chainId": "CHAIN-CROSS", "chainType": "level_combat_growth_settlement", "mechanicIds": ["M-MOVE"],
               "supportingRuleIds": ["R-MOVE"], "missingLinks": [], "gameplayParameters": []}]
    result = project_core_loop_rules(chains, groups, models, {})
    assert result["coreGameplayLoop"]["definitionMode"] == "overview_only"
    assert "fullRuleDefinitions" not in result["coreGameplayLoop"]
    assert result["systemChapterSkeletons"][0]["fullDefinitionRuleIds"] == ["R-MOVE"]
    report = evaluate_projection_integrity(result)
    assert report["duplicateFullDefinitionCount"] == 0
    assert report["coreLoopFullDefinitionCount"] == 0
    assert report["qualityGate"] == "pass"


def test_entity_ownership_routes_weapon_slot_and_affix_without_duplicate_definitions():
    groups = [_group("G-WEAPON", "M-WEAPON", "成长与词条", ["R-EFFECT"])]
    groups[0]["knownRules"][0]["schemaSlot"] = "candidate_effect"
    models = [{"mechanicId": "M-WEAPON", "chapterId": "C-WEAPON", "mechanicType": "attack"}]
    chains = [{"chainId": "C1", "chainType": "weapon_acquire_attack_upgrade", "mechanicIds": ["M-WEAPON"],
               "supportingRuleIds": ["R-EFFECT"], "gameplayParameters": [],
               "missingLinks": [{"semanticKey": "loadout_capacity", "question": "武器栏数量未知"}]}]
    entity = {"entities": [
        {"entityId": "E-AFFIX", "name": "词条", "entityType": "content_item", "primaryDefinitionChapter": "C-AFFIX", "relatedRuleIds": []},
        {"entityId": "E-SLOT", "name": "武器栏", "entityType": "container", "semanticKey": "weapon_slot",
         "primaryDefinitionChapter": "C-SLOT", "relatedRuleIds": []}]}
    result = project_core_loop_rules(chains, groups, models, entity)
    assert result["ruleProjections"][0]["primaryOwner"] == "C-AFFIX"
    assert result["missingLinkProjections"][0]["primaryOwner"] == "C-SLOT"
