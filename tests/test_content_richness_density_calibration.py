from backend.content_richness_density_calibration import (
    build_content_richness_preview,
    evaluate_content_richness,
)


def _expansion(layout, owner, topic, *, details=(), missing=(), parameters=(), stops=()):
    return {"layoutId": layout, "ownerChapter": owner, "ruleTopic": topic,
            "confirmedDetails": [{"detailId": f"D-{index}", "text": text,
                                  "sourceRuleIds": list(rule_ids), "evidenceStatus": "confirmed"}
                                 for index, (text, rule_ids) in enumerate(details)],
            "missingExecutionDetails": [{"semantic": semantic, "scopeStatus": status,
                                          "sourceMissingIds": [f"M-{semantic}"]}
                                         for semantic, status in missing],
            "gameplayParameters": [{"semantic": semantic, "label": label, "applicability": "active"}
                                   for semantic, label in parameters],
            "stopReasons": [{"candidateDimension": semantic, "scopeStatus": status,
                              "reasonType": "scope_not_active", "reason": "not active"}
                             for semantic, status in stops]}


def _decision(key, owner, topic, route):
    return {"decisionId": f"DEC-{key}", "decisionKey": key, "ownerChapter": owner,
            "ruleTopic": topic, "route": route, "approvalStatus": "unreviewed", "dependency": None}


def test_richness_uses_confirmed_and_review_sources_but_rejects_possible_dimensions():
    expansions = [_expansion("L1", "W", "攻击规则",
        details=[("武器无需玩家手动瞄准", ["R1"]), ("武器选择射程内敌人作为攻击目标", ["R2"])],
        missing=[("damage_resolution", "confirmed")],
        parameters=[("attack_range", "攻击范围")],
        stops=[("critical_hit", "possible")])]
    decisions = [_decision("damage_model", "W", "攻击规则", "P4"),
                 _decision("attack_range", "W", "攻击规则", "P6")]
    result = build_content_richness_preview(expansions, decisions, [], [], [])
    weapon = next(item for item in result["chapters"] if item["chapterTitle"] == "武器攻击")
    texts = [line["text"] for line in weapon["lines"]]
    assert "武器自动攻击射程内敌人，无需玩家手动瞄准。" in texts
    assert "伤害计算：待确认。" in texts
    assert "攻击范围：待确认。" in texts
    assert all("暴击" not in text for text in texts)
    audit = evaluate_content_richness(result, expansions, decisions, [])
    weapon_audit = next(item for item in audit["chapters"] if item["chapterTitle"] == "武器攻击")
    assert "critical_hit" in weapon_audit["correctlyRejectedDimensions"]
    assert weapon_audit["supportedButNotRenderedDimensions"] == []


def test_observed_values_remain_specific_and_are_not_replaced_by_abstract_summary():
    expansions = [_expansion("L", "T", "选择结果", details=[
        ("选择词条后改变已选武器的攻击方式", ["R-G"]),
        ("火焰喷射攻击范围扩大30%", ["R-F"]),
        ("雷暴枪伤害增加100%", ["R-T"]),
        ("终极词条将武器喷射方向由单方向改为四向喷射", ["R-U"]),
    ])]
    parameters = [
        {"ownerChapter": "T", "ownerLayout": "L", "semantic": "fire_range_modifier",
         "parameterClass": "observed_value", "observedValue": 30, "unit": "%", "sourceRuleIds": ["R-F"]},
        {"ownerChapter": "T", "ownerLayout": "L", "semantic": "thunder_damage_modifier",
         "parameterClass": "observed_value", "observedValue": 100, "unit": "%", "sourceRuleIds": ["R-T"]},
    ]
    result = build_content_richness_preview(expansions, [], parameters, [], [])
    affix = next(item for item in result["chapters"] if item["chapterTitle"] == "词条")
    texts = [line["text"] for line in affix["lines"]]
    assert texts == ["火焰喷射：攻击范围+30%。", "雷暴枪：伤害+100%。", "终极词条：喷射方向由单方向改为四向。"]
    assert all("R-G" in line["supportingRuleIds"] for line in affix["lines"])


def test_empty_scope_corrected_settlement_is_omitted_but_audited():
    expansions = [_expansion("L", "S", "结算结果", missing=[("displayed_data", "strongly_implied")]),
                  _expansion("L2", "S", "数据记录", missing=[("recorded_data", "strongly_implied")])]
    decisions = [_decision("displayed_data", "S", "结算结果", "Evidence Recheck"),
                 _decision("recorded_data", "S", "数据记录", "Suppress")]
    result = build_content_richness_preview(expansions, decisions, [], [], [])
    assert all(item["chapterTitle"] != "结算" for item in result["chapters"])
    assert result["omittedChapters"] == [{"chapterTitle": "结算", "reason": "evidence_recheck_or_scope_unsupported"}]


def test_effective_rule_density_counts_gameplay_information_not_words():
    expansions = [_expansion("L", "R", "触发与选择", details=[
        ("三选一升级触发时生成三张候选卡", ["R1"]),
        ("玩家从三张候选卡中选择一项", ["R2"]),
        ("系统升级触发时暂停游戏", ["R3"]),
    ])]
    result = build_content_richness_preview(expansions, [], [], [], [])
    report = evaluate_content_richness(result, expansions, [], [])
    density = report["effectiveRuleDensity"]
    assert density["effectiveGameplayRules"] >= 2
    assert density["concreteNumericRules"] >= 2
    assert density["fillerSentences"] == 0
    assert density["implementationSentences"] == 0


def test_player_input_is_rendered_without_redundant_player_through_phrase():
    expansions = [_expansion("L", "V", "移动规则", details=[
        ("玩家通过虚拟摇杆或按键横向微调载具", ["R-MOVE"])])]
    result = build_content_richness_preview(expansions, [], [], [], [])
    assert result["chapters"][0]["lines"][0]["text"] == "使用虚拟摇杆或按键横向微调载具。"
