from copy import deepcopy

from backend.gameplay_copy import chapter_gameplay_summary, migrate_gameplay_presentation, refresh_directory_copy


def test_chapter_summary_uses_mechanism_instead_of_interface_claims():
    chapter = {
        "id": "GCH-001",
        "scope": "终极词条入库与概率获取机制",
        "mechanism": {"type": "random_pool", "description": "终极词条属于高稀有度成长内容，获取后加入词条库。"},
        "claims": [{"text": "界面使用金色边框，点击后显示进入词条库。"}],
        "unknowns": ["后续抽取概率待确认"],
    }
    assert chapter_gameplay_summary(chapter, first_use=True) == "终极强化（素材中称‘终极词条’）属于高稀有度成长内容，获取后加入强化库。"


def test_directory_refresh_does_not_mutate_evidence_claims():
    chapter = {
        "id": "GCH-001", "scope": "局内升级", "mechanism": {"type": "progression", "description": "玩家升级后从三项强化效果中选择一项。"},
        "claims": [{"id": "GCL-001", "text": "屏幕中央弹出选择武器界面。"}],
    }
    model = {"chapters": [chapter], "directory": {"entries": [{"chapterId": "GCH-001", "summary": "旧文案"}], "understanding": {}}}
    before = deepcopy(chapter["claims"])
    refresh_directory_copy(model)
    assert chapter["claims"] == before
    assert "界面" not in model["directory"]["entries"][0]["summary"]
    assert model["directory"]["presentationVersion"] == 13


def test_structure_only_visual_observations_become_gameplay_rules_not_screen_captions():
    movement = {
        "scope": "载具移动机制",
        "mechanism": {"type": "custom", "description": "画面显示载具沿预设路线（小地图黄线）自动行进，玩家通过虚拟摇杆或按键进行横向微调以规避或瞄准。"},
    }
    health = {
        "scope": "生命值状态管理",
        "mechanism": {"type": "custom", "description": "载具底部显示绿色血条及具体数值（如4472/4460），受击时数值减少，归零则失败。"},
    }

    movement_summary = chapter_gameplay_summary(movement)
    health_summary = chapter_gameplay_summary(health)

    assert movement_summary == "载具沿预设路线自动前进；玩家可控制载具横向移动，以调整行进位置、规避敌人或对准攻击目标。"
    assert health_summary == "载具拥有独立生命值；受到伤害时扣减生命值，生命值归零时本局失败。"
    assert all(word not in movement_summary + health_summary for word in ("画面", "小地图", "虚拟摇杆", "按键", "显示", "4472"))


def test_directory_understanding_is_built_from_gameplay_abstractions_and_identifies_current_family():
    chapters = [
        {"id": "GCH-001", "scope": "载具移动机制", "systemName": "核心战斗系统", "subsystemName": "角色与载具控制", "mechanism": {"type": "custom", "description": "画面显示载具沿预设路线自动行进。"}},
        {"id": "GCH-002", "scope": "三选一强化池", "systemName": "局内成长系统", "subsystemName": "升级选择", "mechanism": {"type": "custom", "description": "升级时暂停游戏，弹出三个卡片供玩家选择。"}},
    ]
    model = {"chapters": chapters, "directory": {"entries": [
        {"chapterId": "GCH-001", "title": "载具移动机制", "summary": "旧文案"},
        {"chapterId": "GCH-002", "title": "三选一强化池", "summary": "旧文案"},
    ], "understanding": {"primaryFamily": "待策划确认", "supportingMechanics": [], "uncertainties": ["主玩法类型还不能仅凭当前素材确定"]}}}

    refresh_directory_copy(model)

    understanding = model["directory"]["understanding"]
    assert understanding["primaryFamily"] == "战斗推进与局内成长"
    assert understanding["supportingMechanics"] == ["核心战斗系统", "局内成长系统"]
    assert understanding["uncertainties"] == []
    assert "画面显示" not in understanding["summary"]
    assert model["directory"]["presentationVersion"] == 13


def test_directory_understanding_summarizes_the_game_from_the_players_viewpoint():
    chapters = [
        {"id": "GCH-001", "scope": "载具移动机制", "systemName": "核心战斗系统", "mechanism": {"description": "载具沿预设路线自动前进；玩家可控制载具横向移动，以调整行进位置、规避敌人或对准攻击目标。"}},
        {"id": "GCH-002", "scope": "自动索敌与攻击", "systemName": "核心战斗系统", "mechanism": {"description": "武器自动攻击射程内敌人。"}},
        {"id": "GCH-003", "scope": "三选一强化池", "systemName": "局内成长系统", "mechanism": {"description": "玩家升级后从三项强化中选择一项。"}},
        {"id": "GCH-004", "scope": "胜利条件判定", "systemName": "关卡系统", "mechanism": {"description": "击败首领后胜利，生命值归零时失败。"}},
    ]
    model = {"chapters": chapters, "directory": {"entries": [
        {"chapterId": item["id"], "title": item["scope"], "summary": "旧文案"} for item in chapters
    ], "understanding": {}}}

    refresh_directory_copy(model)

    summary = model["directory"]["understanding"]["summary"]
    assert all(label not in summary for label in ("核心目标：", "基础操作：", "核心循环：", "胜败条件："))
    assert "玩家可控制载具横向移动" in summary
    assert "武器自动攻击射程内敌人" in summary
    assert "玩家升级后从三项强化中选择一项" in summary
    assert len([item for item in summary.split("\n\n") if item]) <= 4


def test_legacy_static_and_numeric_observations_are_removed_from_gameplay_flow_without_losing_copy():
    chapter = {
        "id": "GCH-001", "scope": "店铺等级与收益公式",
        "plannerSections": {"normalFlow": [
            "F0001/F0002底部面板显示当前等级（2767级）、每秒收益（4.9万/秒）及计算公式。",
            "玩家确认升级后，系统扣除钞票并提升店铺等级。",
        ]},
    }
    model = {"chapters": [chapter], "directory": {"presentationVersion": 12, "entries": [{"chapterId": chapter["id"]}], "understanding": {}}}
    refresh_directory_copy(model)
    sections = chapter["plannerSections"]
    assert sections["normalFlow"] == ["玩家确认升级后，系统扣除钞票并提升店铺等级。"]
    assert sections["numericRules"] == ["F0001/F0002底部面板显示当前等级（2767级）、每秒收益（4.9万/秒）及计算公式。"]


def test_directory_refresh_preserves_a_distinct_planner_written_overview():
    chapter = {"id": "GCH-001", "scope": "移动", "mechanism": {"description": "玩家左右移动。"}}
    model = {"chapters": [chapter], "directory": {
        "understandingSource": "planner",
        "understanding": {"summary": "这是策划手工确认的玩法概述。"},
        "entries": [{"chapterId": "GCH-001", "title": "移动", "summary": "玩家左右移动。"}],
    }}
    refresh_directory_copy(model)
    assert model["directory"]["understanding"]["summary"] == "这是策划手工确认的玩法概述。"


def test_structure_phase_understanding_uses_only_the_current_project_systems_without_combat_templates():
    chapters = [
        {"id": "GCH-001", "scope": "建筑收购条件", "systemName": "城市收购", "subsystemName": "建筑交易", "mechanism": {"description": "满足条件后收购目标建筑。"}},
        {"id": "GCH-002", "scope": "收购进度累计", "systemName": "城市收购", "subsystemName": "建筑交易", "mechanism": {"description": "完成收购后累计城市进度。"}},
    ]
    model = {
        "chapters": chapters,
        "reviewState": {"structurePhase": "mechanisms", "status": "mechanism_directory_review"},
        "directory": {"entries": [
            {"chapterId": item["id"], "title": item["scope"], "summary": "旧文案"} for item in chapters
        ], "understanding": {}},
    }

    refresh_directory_copy(model)

    understanding = model["directory"]["understanding"]
    assert understanding["primaryFamily"] == "城市收购"
    assert understanding["supportingMechanics"] == []
    assert "建筑收购条件" in understanding["summary"]
    assert all(term not in understanding["summary"] for term in ("战斗与关卡", "三选一", "胜败条件", "当前素材尚未明确玩家"))


def test_unconfirmed_legacy_bad_directory_is_routed_to_regeneration_without_overwriting_evidence():
    chapters = [
        {"id": "GCH-001", "scope": "建筑", "systemName": "城市收购", "subsystemName": "全部规则", "mechanism": {"description": "建筑信息"}},
        {"id": "GCH-002", "scope": "建筑", "systemName": "城市收购", "subsystemName": "全部规则", "mechanism": {"description": "建筑信息"}},
        {"id": "GCH-003", "scope": "收购信息面板", "systemName": "城市收购", "subsystemName": "全部规则", "mechanism": {"description": "显示收购信息"}},
    ]
    job = {"gameplayReviewModel": {
        "lifecycleState": "ready", "contentState": "ready", "chapters": deepcopy(chapters),
        "systems": [{"name": "城市收购", "subsystems": [{"name": "全部规则", "chapterIds": [item["id"] for item in chapters]}]}],
        "reviewState": {"status": "mechanism_directory_review", "structurePhase": "mechanisms"},
        "directory": {"status": "draft", "presentationVersion": 12, "entries": [
            {"chapterId": item["id"], "title": item["scope"]} for item in chapters
        ], "understanding": {}},
    }}

    migrate_gameplay_presentation(job)

    model = job["gameplayReviewModel"]
    assert model["reviewState"]["status"] == "generation_required"
    assert model["contentState"] == "pending"
    assert any("重复机制" in item for item in model["reviewState"]["structureQualityErrors"])
    assert [(item["scope"], item["mechanism"]) for item in model["chapters"]] == [
        (item["scope"], item["mechanism"]) for item in chapters
    ]


def test_planner_confirmed_directory_is_never_silently_invalidated_by_shape_audit():
    chapter = {"id": "GCH-001", "scope": "收购信息面板", "systemName": "城市收购", "subsystemName": "城市收购"}
    job = {"gameplayReviewModel": {
        "lifecycleState": "ready", "contentState": "ready", "chapters": [chapter],
        "systems": [{"name": "城市收购", "subsystems": [{"name": "城市收购", "chapterIds": ["GCH-001"]}]}],
        "reviewState": {"status": "chapter_review", "structurePhase": "detailed"},
        "directory": {"status": "confirmed", "presentationVersion": 12, "entries": [{"chapterId": "GCH-001", "title": "收购信息面板"}], "understanding": {}},
    }}

    migrate_gameplay_presentation(job)

    assert job["gameplayReviewModel"]["reviewState"]["status"] == "chapter_review"
    assert job["gameplayReviewModel"]["contentState"] == "ready"
    assert job["gameplayReviewModel"]["directory"]["status"] == "confirmed"
    assert job["gameplayReviewModel"]["reviewState"]["structureQualityErrors"]
