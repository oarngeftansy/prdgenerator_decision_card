from backend.phase1_directory import build_phase1_directory
from scripts.generate_phase11_owner_audit import _acceptance


def _object(result, title):
    return next(
        obj
        for system in result["tree"]
        for obj in system["objects"]
        if obj["title"] == title
    )


def _titles(obj):
    return [chapter["title"] for chapter in obj["chapters"]]


def test_end_condition_is_owned_by_level_flow_not_damage_death():
    result = build_phase1_directory({"chapters": [{
        "id": "LEVEL", "scope": "关卡", "systemName": "关卡推进",
        "claims": [{"text": "击败首领时触发胜利并移交结算；载具生命值归零时触发失败并移交结算。"}],
    }]})

    level = _object(result, "关卡")
    assert "受击及死亡" not in _titles(level)
    assert "胜负判定" in _titles(level)
    assert next(chapter for chapter in level["chapters"] if chapter["title"] == "胜负判定")["chapterType"] == "level_flow"


def test_vehicle_life_zero_event_definition_remains_with_vehicle_death_chapter():
    result = build_phase1_directory({"chapters": [{
        "id": "VEHICLE", "scope": "载具", "systemName": "核心战斗",
        "claims": [{"text": "载具生命值归零时停止战斗并进入失败分支。"}],
    }]})

    vehicle = _object(result, "载具")
    assert _titles(vehicle) == ["受击及死亡"]
    assert vehicle["chapters"][0]["chapterType"] == "damage_death"


def test_parent_directly_carries_same_settlement_schema():
    result = build_phase1_directory({"chapters": [{
        "id": "SETTLEMENT", "scope": "结算", "systemName": "关卡推进",
        "claims": [
            {"text": "收到胜利结果后进入结算并发放奖励。"},
            {"text": "结算界面展示伤害统计。"},
        ],
    }]})

    settlement = _object(result, "结算")
    assert settlement["chapterType"] == "settlement"
    assert settlement["matchedSchema"] == "chapter-schema-v2:settlement:base"
    assert _titles(settlement) == ["伤害统计"]


def test_win_loss_condition_does_not_trigger_damage_death_in_blind_game():
    result = build_phase1_directory({"chapters": [{
        "id": "RESULT", "scope": "胜负", "systemName": "卡牌对局",
        "claims": [{"text": "任一方生命值归零时停止对局并判定胜负，随后进入胜负结算。"}],
    }]})

    outcome = _object(result, "胜负")
    assert "受击及死亡" not in _titles(outcome)
    assert _titles(outcome) == ["胜负判定"]
    assert any(chapter["chapterType"] in {"level_flow", "settlement"} for chapter in outcome["chapters"])


def test_weapon_slot_has_one_primary_owner_and_other_evidence_is_reference():
    result = build_phase1_directory({"chapters": [
        {
            "id": "VEHICLE", "scope": "载具", "systemName": "核心战斗",
            "claims": [
                {"text": "载具承载 1 个默认武器栏和 4 个自选武器栏，自选栏初始为空。"},
                {"text": "获得新武器后写入空栏，栏位填满后不再获得新武器类型。"},
            ],
        },
        {
            "id": "WEAPON", "scope": "武器", "systemName": "核心战斗",
            "claims": [{"text": "屏幕底部按钮对应武器槽位。"}],
        },
    ]})

    vehicle = _object(result, "载具")
    weapon = _object(result, "武器")
    slot = next(chapter for chapter in vehicle["chapters"] if chapter["title"] == "栏位")
    assert "栏位" not in _titles(weapon)
    assert slot["definitionMode"] == "primary"
    assert slot["semanticDomain"] == "weapon_slot"
    assert slot["references"] == [{"sourceChapterId": "WEAPON", "sourceObject": "武器"}]


def test_monster_hud_timer_moves_to_level_presentation_not_monster_flow():
    result = build_phase1_directory({"chapters": [
        {
            "id": "MONSTER", "scope": "怪物", "systemName": "关卡推进",
            "claims": [{"text": "顶部中央显示倒计时，左上角显示当前等级。"}],
        },
        {
            "id": "LEVEL", "scope": "关卡", "systemName": "关卡推进",
            "claims": [{"text": "进入关卡后按顺序推进波次。"}],
        },
    ]})

    monster = _object(result, "怪物")
    level = _object(result, "关卡")
    assert "关卡流程" not in _titles(monster)
    assert "战斗表现" in _titles(level)


def test_legacy_scope_is_not_owner_when_explicit_subject_defines_another_system():
    result = build_phase1_directory({"chapters": [{
        "id": "LEGACY", "scope": "怪物", "systemName": "关卡推进",
        "claims": [{"text": "关卡按顺序推进波次，达到首领阶段条件后切换阶段。"}],
    }]})

    monster = _object(result, "怪物")
    level = _object(result, "关卡")
    assert "关卡流程" not in _titles(monster)
    assert "关卡流程" in _titles(level)
    assert any(
        decision["source_chapter_id"] == "LEGACY"
        and decision["owner_object"] == "关卡"
        for decision in result["ownershipDecisions"]
    )


def test_phase11_acceptance_contract_covers_all_owner_regressions():
    main = build_phase1_directory({"chapters": [
        {"id": "VEHICLE", "scope": "载具", "systemName": "核心战斗", "claims": [
            {"text": "载具承载 1 个默认武器栏和 4 个自选武器栏，自选栏初始为空。"},
            {"text": "载具生命值归零时停止战斗并进入失败分支。"},
        ]},
        {"id": "WEAPON", "scope": "武器", "systemName": "核心战斗", "claims": [{"text": "屏幕底部按钮对应武器槽位。"}]},
        {"id": "MONSTER", "scope": "怪物", "systemName": "关卡推进", "claims": [
            {"text": "顶部中央显示倒计时，左上角显示当前等级。"},
            {"text": "怪物生命值归零后进入死亡处理并移除实体。"},
        ]},
        {"id": "LEVEL", "scope": "关卡", "systemName": "关卡推进", "claims": [
            {"text": "击败首领时触发胜利并移交结算；载具生命值归零时触发失败并移交结算。"},
        ]},
        {"id": "SETTLEMENT", "scope": "结算", "systemName": "关卡推进", "claims": [
            {"text": "收到胜利结果后进入结算并发放奖励。"},
            {"text": "结算界面展示伤害统计。"},
        ]},
    ]})
    blind = build_phase1_directory({"chapters": [{
        "id": "RESULT", "scope": "胜负", "systemName": "卡牌对局",
        "claims": [{"text": "任一方生命值归零时停止对局并判定胜负，随后进入胜负结算。"}],
    }]})

    assert all(_acceptance(main, blind).values())
