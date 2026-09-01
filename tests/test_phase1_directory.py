from backend.phase1_directory import build_phase1_directory


def test_directory_builds_object_then_stable_rule_categories_without_slot_headings():
    model = {"chapters": [{
        "id": "OLD-1", "scope": "武器解锁、攻击与词条成长", "systemName": "核心战斗",
        "claims": [
            {"text": "武器进入射程后自动攻击目标并发射投射物。"},
            {"text": "武器在局外消耗材料升级，完成指定关卡后解锁。"},
            {"text": "词条达到最大等级后移出随机池。"},
        ],
    }]}
    result = build_phase1_directory(model)
    children = result["tree"][0]["objects"][0]["chapters"]
    assert [item["title"] for item in children] == ["攻击", "解锁与养成", "词条"]
    assert all(item["title"] not in {"攻击触发", "攻击目标", "攻击退出"} for item in children)
    assert result["qualityReport"]["customCount"] == 0


def test_blind_card_game_does_not_invent_vehicle_weapon_or_reference_sections():
    model = {"chapters": [
        {"id": "C1", "scope": "手牌", "systemName": "卡牌对局", "claims": [{"text": "回合开始时从牌库随机抽取卡牌加入手牌栏位。"}]},
        {"id": "C2", "scope": "回合结算", "systemName": "卡牌对局", "claims": [{"text": "行动点耗尽后结束回合并结算持续效果。"}]},
    ]}
    result = build_phase1_directory(model)
    titles = result["humanReadableTree"]
    assert "载具" not in titles and "武器" not in titles and "GVE16" not in titles
    assert "卡牌对局" in titles and "手牌" in titles


def test_context_keeps_terminal_affix_as_one_chapter_and_hud_entry_out_of_damage_statistics():
    model = {"chapters": [
        {
            "id": "C1", "scope": "终极强化", "systemName": "局内成长",
            "claims": [
                {"text": "终极词条进入候选范围后以金色边框显示。"},
                {"text": "确认后攻击方向变化并同时应用伤害修正。"},
            ],
        },
        {
            "id": "C2", "scope": "载具", "systemName": "核心战斗",
            "claims": [{"text": "暂停、倍速和伤害统计是战斗 HUD 的独立操作入口。"}],
        },
    ]}
    result = build_phase1_directory(model)
    terminal_object = result["tree"][0]["objects"][0]
    terminal = terminal_object["chapters"]
    vehicle = result["tree"][1]["objects"][0]["chapters"]
    assert terminal == []
    assert terminal_object["chapterType"] == "content_catalog"
    assert all(chapter["title"] != "伤害统计" for chapter in vehicle)


def test_three_choice_groups_slots_into_candidate_and_refresh_chapters_only():
    model = {"chapters": [{
        "id": "C1", "scope": "局内强化", "systemName": "局内成长",
        "claims": [
            {"text": "升级后展示三张候选卡，玩家确认一项后生效。"},
            {"text": "已解锁内容按权重随机抽取。"},
            {"text": "刷新会整体替换当前三项候选。"},
        ],
    }]}
    result = build_phase1_directory(model)
    chapters = result["tree"][0]["objects"][0]["chapters"]
    assert [chapter["title"] for chapter in chapters] == ["候选", "刷新"]
