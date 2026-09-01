import re

import pytest

from backend.planning_board_model import _stage_record, build_planning_board_model, planner_board_text, _semantic_frame_ids
from backend.feishu_render import _page_copy_lines
from backend.review_service import apply_operations, confirm_flow, confirm_stage
from tests.review_fixtures import make_confirmed_job


def _page_text(page: dict) -> str:
    return " ".join(
        str(value)
        for group in page["groups"]
        for item in group["items"]
        for value in (item.get("text", ""), *item.get("children", []))
    )


def test_board_model_exports_only_the_shared_page_spec_contract():
    board = build_planning_board_model(make_confirmed_job())

    assert set(board) == {"pages", "relations", "notes", "showUeMarkers"}
    assert board["showUeMarkers"] is False
    assert board["pages"]
    assert set(board["pages"][0]) == {
        "id", "title", "screenshots", "groups", "notes", "sourceRefs",
        "detailCrops", "screenshotDetails", "topology",
    }


def test_page_description_matches_sample_granularity_for_nested_visual_structure():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["objective"] = "供玩家查看关卡状态并控制战斗"
    stage["entryCondition"] = "进入关卡后显示"
    stage["smallLoop"].update({
        "trigger": "点击暂停按钮",
        "feedback": "系统暂停当前战斗并显示暂停状态",
        "result": "页面停留在战斗界面，等待玩家继续",
    })
    job["reviewModel"]["regions"] = []
    stage["regionIds"] = []
    job["frames"][0]["analysis"]["regionStructure"] = {
        "header": {
            "description": "顶部状态栏",
            "elements": ["暂停按钮", "关卡名称", "倒计时", "关卡进度条"],
        },
        "main": {
            "playfield": "中央区域显示玩家、敌人、攻击特效和伤害数字",
        },
    }

    page = build_planning_board_model(job)["pages"][0]
    groups = {group["title"]: group["items"] for group in page["groups"]}
    visible = _page_text(page)

    assert [item["text"] for item in groups["页面信息"]] == ["页面用途：供玩家查看关卡状态并控制战斗"]
    assert [item["text"] for item in groups["顶部区域（从左到右）"]] == [
        "暂停按钮", "关卡名称", "倒计时", "关卡进度条",
    ]
    assert [item["text"] for item in groups["功能说明"]][:4] == [
        "显示时机：进入关卡后显示",
        "可进行的操作：点击暂停按钮",
        "操作后的变化：系统暂停当前战斗并显示暂停状态",
        "完成后的状态：页面停留在战斗界面，等待玩家继续",
    ]


def test_page_spec_abstracts_literal_values_and_desktop_observation_without_breaking_parentheses():
    job = make_confirmed_job()
    job["frames"][0]["analysis"]["regionStructure"] = {
        "top": "顶部信息栏，关卡名'2.沙漠雪径'、倒计时'02:36'、资源计数(火焰11、蓝色1)",
        "center": "中央战斗区，屏幕中央偏下有鼠标光标；三个技能选项（火焰扩张、爆炸扩张、雷暴增幅）",
    }

    model = build_planning_board_model(job)
    visible = " ".join(
        [item["text"], *[child["text"] for child in item.get("children") or []]][part]
        for group in model["pages"][0]["groups"]
        for item in group["items"]
        for part in range(1 + len(item.get("children") or []))
    )

    assert "鼠标" not in visible
    assert "02:36" not in visible
    assert "2.沙漠雪径" not in visible
    assert "资源计数" in visible
    assert "火焰11" not in visible
    assert not any(mark in visible for mark in "（）()")
    assert not any(token in visible for token in ("{'", "':", "elements", "description", "playfield"))


def test_page_spec_flattens_half_open_parentheses_and_literal_titles():
    job = make_confirmed_job()
    job["frames"][0]["analysis"]["regionStructure"] = {
        "left": ["小地图（显示路径", "统计按钮（柱状图图标"],
        "center": ["玩家车辆（黄色工程车", "标题为“广域喷射”", "Roguelike机制"],
    }

    page = build_planning_board_model(job)["pages"][0]
    visible = _page_text(page)

    assert "小地图 显示路径" in visible
    assert "统计按钮 柱状图图标" in visible
    assert "玩家车辆 黄色工程车" in visible
    assert "广域喷射" not in visible
    assert "随机成长机制" in visible
    assert not any(mark in visible for mark in "（）()")


def test_stale_visual_model_configuration_message_never_becomes_page_copy():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["objective"] = "需要配置视觉模型后识别"
    stage["name"] = "查看升级选项"

    page = build_planning_board_model(job)["pages"][0]
    visible = _page_text(page)

    assert "需要配置视觉模型" not in visible
    assert f"页面用途：供玩家查看{page['title']}" in visible


def test_mostly_english_visual_analysis_does_not_leave_punctuation_fragments_in_page_copy():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["entryCondition"] = "未知待确认"
    stage["exitCondition"] = "未知待确认"
    stage["smallLoop"] = {
        "trigger": "待确认", "feedback": "待确认", "result": "待确认", "retry": "待确认",
    }
    frame = job["frames"][0]
    for candidate in job["frames"]:
        candidate["analysis"]["regionStructure"] = {}
        candidate["analysis"].update({"userAction": "", "systemResponse": "", "afterState": "", "beforeState": ""})
    job["reviewModel"]["regions"] = []
    stage["regionIds"] = []
    frame["analysis"].update({
        "userAction": "The player reaches a checkpoint and the game pauses automatically.",
        "systemResponse": "A modal titled '选择武器' appears with '火焰扩张', '爆炸扩张', and '雷暴增幅'.",
        "afterState": "The menu remains open and waits for the player to press '刷新'.",
    })

    frames = {candidate["id"]: candidate for candidate in job["frames"]}
    record = _stage_record(stage, frames)
    assert not record["trigger"]
    assert not record["feedback"]
    assert not record["result"]

    page = build_planning_board_model(job)["pages"][0]
    assert not any(group["title"].startswith(("弹窗", "刷新")) for group in page["groups"])
    assert not any("操作后的变化：弹窗" in item["text"] for group in page["groups"] for item in group["items"])


def test_legacy_events_are_migrated_to_page_specs_with_image_evidence():
    job = {
        "frames": [{"id": "F0001", "imagePath": "frames/F0001.jpg"}],
        "planningModel": {
            "events": [{
                "id": "EVT-001", "action": "点击开始", "response": "进入战斗",
                "beforeState": "主菜单", "afterState": "战斗页面",
                "evidence": [{"sourceId": "F0001"}],
            }],
        },
    }

    board = build_planning_board_model(job)

    assert set(board) == {"pages", "relations", "notes", "showUeMarkers"}
    assert [page["id"] for page in board["pages"]] == ["legacy-EVT-001"]
    assert board["pages"][0]["screenshots"] == [{
        "frameId": "F0001", "imageUrl": "frames/F0001.jpg", "sequenceIndex": None,
        "sourceWidth": 0, "sourceHeight": 0,
    }]
    assert board["relations"] == []


def test_unconfirmed_modern_stages_do_not_fall_back_to_legacy_planning_events():
    job = {
        "frames": [{"id": "F0001", "imagePath": "frames/F0001.jpg"}],
        "reviewModel": {"stages": [{"id": "STG-001", "confirmation": {"confirmed": False}}]},
        "planningModel": {"events": [{"id": "EVT-001", "action": "旧事件", "evidence": [{"sourceId": "F0001"}]}]},
    }

    board = build_planning_board_model(job)

    assert board["pages"] == []
    assert board["relations"] == []


@pytest.mark.parametrize("loop_hierarchy", [None, [], "damaged", {"largeLoops": None}, {"largeLoops": [{}]}])
def test_malformed_legacy_loop_hierarchy_safely_returns_an_empty_page_board(loop_hierarchy):
    job = {
        "frames": [{"id": "F0001", "imagePath": "frames/F0001.jpg"}],
        "planningModel": {"events": [], "loopHierarchy": loop_hierarchy},
    }

    board = build_planning_board_model(job)

    assert board["pages"] == []
    assert board["relations"] == []


def test_legacy_events_without_explicit_relation_evidence_keep_pages_but_do_not_invent_edges():
    job = {
        "frames": [
            {"id": "F0001", "imagePath": "frames/F0001.jpg"},
            {"id": "F0003", "imagePath": "frames/F0003.jpg"},
        ],
        "planningModel": {"events": [
            {"id": "EVT-001", "action": "打开选项", "evidence": [{"sourceId": "F0001"}]},
            {"id": "EVT-002", "action": "无图中间步骤", "evidence": [{"sourceId": "F0002"}]},
            {"id": "EVT-003", "action": "确认结算", "evidence": [{"sourceId": "F0003"}]},
        ]},
    }

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == ["legacy-EVT-001", "legacy-EVT-003"]
    assert board["relations"] == []


def test_legacy_confirmed_transition_target_can_create_an_explicit_relation():
    job = {
        "frames": [
            {"id": "F0001", "imagePath": "frames/F0001.jpg"},
            {"id": "F0002", "imagePath": "frames/F0002.jpg"},
        ],
        "planningModel": {"events": [
            {
                "id": "EVT-001", "sceneId": "SCN-001", "action": "点击开始",
                "sourceTransitionId": "TRN-001", "targetStageId": "SCN-002", "resultType": "navigate",
                "evidence": [{"sourceId": "F0001"}],
            },
            {"id": "EVT-002", "sceneId": "SCN-002", "action": "进入战斗", "evidence": [{"sourceId": "F0002"}]},
        ]},
    }

    board = build_planning_board_model(job)

    assert board["relations"] == [{
        "id": "legacy-relation-TRN-001",
        "sourcePageId": "legacy-EVT-001",
        "targetPageId": "legacy-EVT-002",
        "label": "点击开始",
        "lineStyle": "solid",
    }]


@pytest.mark.parametrize(
    ("planning", "expected_ids"),
    [
        ({"events": {"id": "EVT-BAD"}}, []),
        ({"events": "bad"}, []),
        ({"events": [{"id": "EVT-001", "action": "无效证据", "evidence": {"sourceId": "F0001"}}]}, []),
        ({"events": [None, "bad", {"id": "EVT-001", "action": "有效事件", "evidence": [None, "bad", {"sourceId": "F0001"}]}]}, ["legacy-EVT-001"]),
        ({"loopHierarchy": {"largeLoops": [{"stages": 42}]}}, []),
        ({"loopHierarchy": {"largeLoops": [{"stages": [{"smallLoops": "bad"}]}]}}, []),
        ({"loopHierarchy": {"largeLoops": [{"stages": [{"smallLoops": [{"steps": None}]}]}]}}, []),
        ({"loopHierarchy": {"largeLoops": [None, {"stages": ["bad", {"smallLoops": [None, {"steps": ["bad", {"title": "有效步骤", "userAction": "确认", "evidence": [{"sourceId": "F0001"}]}]}]}]}]}}, ["legacy-STEP-001"]),
    ],
)
def test_legacy_nested_collections_only_accept_lists_of_mapping_items(planning, expected_ids):
    job = {
        "frames": [{"id": "F0001", "imagePath": "frames/F0001.jpg"}],
        "planningModel": planning,
    }

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == expected_ids


def test_continuous_evidence_for_one_page_is_merged_without_losing_screenshots():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = second["name"] = "载具养成"
    first["objective"] = second["objective"] = "提升载具能力"
    first["smallLoop"].update({"trigger": "点击升级按钮", "feedback": "展示当前等级"})
    second["smallLoop"].update({"trigger": "选择升级项目", "result": "升级后攻击力提高"})

    board = build_planning_board_model(job)

    assert [page["title"] for page in board["pages"]] == ["载具养成"]
    assert [shot["frameId"] for shot in board["pages"][0]["screenshots"]] == ["F0001", "F0002"]
    assert {ref["frameId"] for ref in board["pages"][0]["sourceRefs"]} == {"F0001", "F0002"}
    assert board["relations"] == []


def test_page_groups_are_generated_from_the_page_evidence_not_a_fixed_template():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = "载具养成"
    first["entryCondition"] = "从玩法主页进入载具养成"
    first["exitCondition"] = "点击返回战斗"
    first["smallLoop"].update({
        "trigger": "点击升级按钮",
        "feedback": "展示当前等级和升级消耗",
        "result": "升级后攻击力提高",
    })
    second["name"] = "奖励选择"
    second["entryCondition"] = "战斗结束后进入奖励选择"
    second["smallLoop"].update({"trigger": "选择一个奖励", "feedback": "展示可选内容"})

    pages = build_planning_board_model(job)["pages"]
    first_groups = [group["title"] for group in pages[0]["groups"]]
    second_groups = [group["title"] for group in pages[1]["groups"]]

    assert first_groups[:6] == ["页面信息", "进入载具养成", "升级操作", "当前等级和升级消耗", "攻击力提高", "返回战斗"]
    assert second_groups[:5] == ["页面信息", "进入奖励选择", "选择奖励", "可选内容", "战斗结束"]
    assert "武器与强化属性" in first_groups
    assert first_groups != second_groups
    assert not set(first_groups + second_groups).intersection({"进入页面", "主要操作", "展示内容", "操作结果"})
    assert "点击返回战斗" in _page_text(pages[0])


def test_only_confirmed_relations_with_two_visible_page_endpoints_are_exported():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = "玩法主页"
    second["name"] = "载具养成"
    transition = job["reviewModel"]["transitions"][0]
    transition.update(triggerLabel="点击载具入口", triggerType="tap", resultType="navigate")

    board = build_planning_board_model(job)

    assert board["relations"] == [{
        "id": transition["id"],
        "sourcePageId": first["id"],
        "targetPageId": second["id"],
        "label": "点击载具入口",
        "lineStyle": "solid",
    }]

    transition["confirmation"]["confirmed"] = False
    assert build_planning_board_model(job)["relations"] == []


def test_page_notes_keep_real_cross_state_questions_but_not_technical_failures():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    job["reviewModel"]["crossStateConstraints"] = [{
        "stageId": stage["id"],
        "text": "返回后保留选择",
        "unknowns": ["保留时长待确认"],
    }]
    stage["unknowns"] = ["逐帧请求解析失败", "未知待确认", "可能是按钮", "是否保留升级效果待确认"]

    board = build_planning_board_model(job)

    assert board["pages"][0]["notes"] == [
        {"text": "返回后保留选择"},
        {"text": "保留时长待确认"},
        {"text": "是否保留升级效果待确认"},
    ]
    assert [note["text"] for note in board["notes"]] == [
        "返回后保留选择", "保留时长待确认", "是否保留升级效果待确认",
    ]
    assert not any(note["text"] in {"未知待确认", "可能是按钮"} for note in board["notes"])


def test_cross_state_constraints_without_a_stage_are_retained_as_board_notes():
    job = make_confirmed_job()
    job["reviewModel"]["crossStateConstraints"] = [{
        "id": "CNS-GLOBAL",
        "text": "所有页面返回后都保留本局选择",
        "unknowns": ["退出本局后是否清空需要确认"],
    }]

    board = build_planning_board_model(job)

    assert [note["text"] for note in board["notes"]] == [
        "所有页面返回后都保留本局选择",
        "退出本局后是否清空需要确认",
    ]
    assert all(not page["notes"] for page in board["pages"])


def test_same_title_with_different_page_purpose_or_state_is_not_merged():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = second["name"] = "载具养成"
    first["objective"] = "查看当前载具属性"
    second["objective"] = "选择升级奖励"

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == [first["id"], second["id"]]
    assert [shot["frameId"] for page in board["pages"] for shot in page["screenshots"]] == ["F0001", "F0002"]


def test_same_title_and_purpose_with_different_explicit_state_is_not_merged():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = second["name"] = "载具养成"
    first["objective"] = second["objective"] = "提升载具能力"
    first["pageState"] = "升级前"
    second["pageState"] = "升级完成"

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == [first["id"], second["id"]]


def test_missing_screenshot_excludes_its_page_and_any_relation_endpoint():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["representativeFrames"] = [{"frameId": "F-MISSING", "role": "entry"}]
    first["name"] = "玩法主页"
    second["name"] = "载具养成"
    job["reviewModel"]["transitions"][0]["triggerLabel"] = "点击载具入口"

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == [second["id"]]
    assert board["relations"] == []


def test_empty_screenshot_url_excludes_its_page_and_any_relation_endpoint():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    job["frames"][0]["imageUrl"] = ""
    first["name"] = "玩法主页"
    second["name"] = "载具养成"
    job["reviewModel"]["transitions"][0]["triggerLabel"] = "点击载具入口"

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == [second["id"]]
    assert board["relations"] == []


def test_same_title_without_page_purpose_or_state_evidence_is_not_merged():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = second["name"] = "载具养成"
    first["objective"] = second["objective"] = ""
    first.pop("pageState", None)
    second.pop("pageState", None)

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == [first["id"], second["id"]]


def test_merged_page_accumulates_known_states_before_merging_a_third_segment():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = second["name"] = "载具养成"
    first["objective"] = second["objective"] = "提升载具能力"
    first.pop("pageState", None)
    second["pageState"] = "升级中"
    third = {
        **second,
        "id": "STG-003",
        "order": 3,
        "pageState": "升级完成",
        "representativeFrames": [{"frameId": "F0003", "role": "entry"}],
    }
    job["reviewModel"]["stages"].append(third)
    job["frames"].append({
        **job["frames"][1],
        "id": "F0003",
        "sequenceIndex": 3,
        "imageUrl": "/artifacts/job-1/frames/F0003.jpg",
    })

    board = build_planning_board_model(job)

    assert [page["id"] for page in board["pages"]] == [first["id"], third["id"]]
    assert [shot["frameId"] for shot in board["pages"][0]["screenshots"]] == ["F0001", "F0002"]
    assert [shot["frameId"] for shot in board["pages"][1]["screenshots"]] == ["F0003"]


def test_source_file_names_remain_trace_data_and_never_enter_visible_page_copy():
    job = make_confirmed_job()
    job["frames"][0]["sourceName"] = "mouse_hover_result.png"

    page = build_planning_board_model(job)["pages"][0]
    visible_text = f"{page['title']} {_page_text(page)}"

    assert "sourceName" not in page["screenshots"][0]
    assert "sourceName" not in page["sourceRefs"][0]
    assert "mouse_hover_result" not in visible_text.lower()


def test_screenshots_preserve_source_dimensions_with_frame_dimension_fallback():
    job = make_confirmed_job()
    job["frames"][0]["structure"] = {"width": 494, "height": 924}
    job["frames"][1].update(width=1280, height=720)

    screenshots = [
        screenshot
        for page in build_planning_board_model(job)["pages"]
        for screenshot in page["screenshots"]
    ]

    assert screenshots[0]["sourceWidth"] == 494
    assert screenshots[0]["sourceHeight"] == 924
    assert screenshots[1]["sourceWidth"] == 1280
    assert screenshots[1]["sourceHeight"] == 720


@pytest.mark.parametrize(
    ("source_width", "expected_width"),
    [
        (494, 494),
        ("494", 0),
        (0, 0),
        (-1, 0),
        (True, 0),
        (494.5, 0),
        ("494.5", 0),
        ("invalid", 0),
        (None, 0),
    ],
)
def test_screenshot_dimensions_accept_only_strict_positive_integers(source_width, expected_width):
    job = make_confirmed_job()
    job["frames"][0].update(sourceWidth=source_width, sourceHeight="924")

    screenshot = build_planning_board_model(job)["pages"][0]["screenshots"][0]

    assert screenshot["sourceWidth"] == expected_width
    assert screenshot["sourceHeight"] == 0


@pytest.mark.parametrize("invalid", [0, -1, True, 494.5, "494", None])
def test_screenshot_structure_dimensions_reject_non_positive_or_non_integer_values(invalid):
    job = make_confirmed_job()
    job["frames"][0]["structure"] = {"width": invalid, "height": invalid}

    screenshot = build_planning_board_model(job)["pages"][0]["screenshots"][0]

    assert screenshot["sourceWidth"] == 0
    assert screenshot["sourceHeight"] == 0


def test_page_copy_is_complete_and_never_exposes_internal_or_desktop_terms():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["name"] = "entry result component unknown"
    stage["smallLoop"].update({
        "trigger": "鼠标指针停留在按钮上，点击升级按钮",
        "feedback": "展示可选内容...并显示HUD",
        "result": "升级完成……返回战斗",
    })

    page = build_planning_board_model(job)["pages"][0]
    text = f"{page['title']} {_page_text(page)}"

    assert page["title"] not in {"场景 1", "确认第 3 步操作"}
    assert not any(token in text.lower() for token in ("mouse", "entry", "result", "component", "unknown", "hud"))
    assert "鼠标" not in text and "光标" not in text
    assert "..." not in text and "……" not in text
    assert "点击升级按钮" in text and "返回战斗" in text


def test_mechanical_stage_titles_fall_back_to_the_visible_page_name():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["name"] = "场景 1"
    job["frames"][0]["analysis"]["what"] = "载具养成界面"

    page = build_planning_board_model(job)["pages"][0]

    assert page["title"] == "载具养成"


def test_speculative_or_desktop_titles_fall_back_to_visible_page_copy():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["name"] = "mouse cursor hover：可能是升级选择界面"
    stage["smallLoop"]["trigger"] = "mouse + keyboard hover 组合输入；点击升级按钮"
    job["frames"][0]["analysis"]["what"] = "载具养成界面"

    page = build_planning_board_model(job)["pages"][0]
    visible_text = f"{page['title']} {_page_text(page)}"

    assert page["title"] == "载具养成"
    assert "点击升级按钮" in visible_text
    assert not any(term in visible_text.lower() for term in ("mouse", "cursor", "hover", "keyboard"))


def test_generic_program_tokens_are_removed_without_losing_chinese_copy_or_numbers():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["name"] = "载具养成 frameId=F0001；stageId=STG-001；sequenceIndex=7"
    stage["smallLoop"].update({
        "trigger": "点击升级按钮，frameId=F0001，获得30金币",
        "feedback": "stageId:STG-001；造成120点伤害",
    })

    page = build_planning_board_model(job)["pages"][0]
    visible_text = f"{page['title']} {_page_text(page)}"

    assert page["title"] == "载具养成"
    assert "点击升级按钮" in visible_text and "30金币" in visible_text and "120点伤害" in visible_text
    assert not any(token in visible_text.lower() for token in ("frameid", "stageid", "sequenceindex", "f0001", "stg-001"))
    assert not any(punctuation * 2 in visible_text for punctuation in ("，", "；", ",", ";"))


def test_planner_board_text_is_the_shared_chinese_cleaning_entry_point():
    cleaned = planner_board_text("鼠标点击entry按钮，result为unknown；HUD显示……...…")

    assert cleaned == "点击页面按钮，结果为待确认"
    assert planner_board_text("武器升级选择弹窗（Level Up Modal）") == "武器升级选择弹窗"


def test_planner_board_text_flattens_structured_visual_values_without_python_garbage():
    cleaned = planner_board_text({
        "type": "Passive / None",
        "description": "系统根据时间自动触发首领警告",
        "details": ["Red Vignette", {"description": "显示首领来袭提示"}],
    })

    assert cleaned == "系统根据时间自动触发首领警告；显示首领来袭提示"
    assert not any(token in cleaned for token in ("{", "}", "[", "]", "Passive", "Vignette"))


def test_planner_board_text_drops_punctuation_only_visual_model_garbage():
    assert planner_board_text("', .") == ""
    assert planner_board_text("'' : '', '', ''. '' .") == ""
    assert planner_board_text("??????") == ""


def test_planner_board_text_drops_non_actions_and_truncated_bottom_bar_fragments():
    assert planner_board_text("未发生点击动作") == ""
    assert planner_board_text("底部有一排数字快捷键提示 到 / 以及入口") == ""
    assert _page_copy_lines("• 可进行的操作：未发生点击动作", 40) == []
    assert _page_copy_lines("• 底部有一排数字快捷键提示 到 / 以及入口", 40) == []


def test_representative_frame_must_match_the_page_semantics():
    record = {"title": "武器升级选择弹窗", "frameIds": ["F1", "F2"]}
    frames = {
        "F1": {"imageUrl": "F1.png", "analysis": {"what": "战斗进行中画面"}},
        "F2": {"imageUrl": "F2.png", "analysis": {"pageName": "武器升级选择弹窗"}},
    }
    assert _semantic_frame_ids(record, frames) == ["F2"]
    assert _semantic_frame_ids({"title": "结算页面", "frameIds": ["F1"]}, frames) == ["F1"]
    assert _semantic_frame_ids({"title": "人工命名页面", "frameIds": ["F1"], "humanEdited": True}, frames) == ["F1"]
    assert _semantic_frame_ids({"title": "普通页面", "frameIds": ["F1"]}, {"F1": {"imageUrl": "F1.png"}}) == ["F1"]


def test_simple_confirmed_sequence_uses_board_grid_instead_of_forcing_a_tree_column():
    job = make_confirmed_job()

    pages = build_planning_board_model(job)["pages"]

    assert len(pages) == 2
    assert all(page["topology"]["branching"] is False for page in pages)


def test_page_spec_extracts_explicit_gameplay_attributes_from_frame_analysis_and_sources():
    job = make_confirmed_job()
    frame = job["frames"][0]
    frame["analysis"]["components"] = [{
        "type": "ModalContainer", "children": [
            {"type": "OptionCard", "title": "迅猛喷射", "description": "火焰喷射器伤害频率提高20%"},
            {"type": "OptionCard", "title": "火焰扩张", "description": "火焰喷射范围扩大30%"},
        ],
    }, {"type": "HUD_Element", "content": "时间：02:37"}]
    frame["analysis"]["rules"] = ["刷新次数为1/1", "弹出选择界面时暂停战斗"]
    frame["analysis"]["gameMechanics"] = "选择一项强化后立即生效"
    job["reviewModel"]["sources"][frame["id"]]["secondaryInformation"] = ["生命：4472", "关卡进度：03:08"]

    page = build_planning_board_model(job)["pages"][0]
    groups = {group["title"]: [item["text"] for item in group["items"]] for group in page["groups"]}

    assert "迅猛喷射 - 火焰喷射器伤害频率提高20%" in groups["武器与强化属性"]
    assert "火焰扩张 - 火焰喷射范围扩大30%" in groups["武器与强化属性"]
    assert "生命：4472" in groups["生存属性"]
    assert "关卡进度：03:08" in groups["关卡状态与资源"]
    assert "刷新次数为1/1" in groups["规则信息"]
    assert str(page["groups"]).count("迅猛喷射") == 1
    assert str(page["groups"]).count("火焰扩张") == 1


def test_function_description_does_not_repeat_identical_dynamic_group_copy():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["regionIds"] = []
    job["reviewModel"]["regions"] = [
        item for item in job["reviewModel"]["regions"] if item["stageId"] != stage["id"]
    ]
    stage["entryCondition"] = "进入强化选择"
    stage["smallLoop"].update({
        "trigger": "选择一项强化",
        "feedback": "强化立即生效",
        "result": "返回战斗",
    })

    page = build_planning_board_model(job)["pages"][0]
    visible_items = [item["text"] for group in page["groups"] for item in group["items"]]

    assert sum(text.endswith("进入强化选择") for text in visible_items) == 1
    assert sum(text.endswith("选择一项强化") for text in visible_items) == 1
    assert sum(text.endswith("强化立即生效") for text in visible_items) == 1
    assert sum(text.endswith("返回战斗") for text in visible_items) == 1


def test_punctuation_and_generic_transition_labels_do_not_create_false_page_edges():
    job = make_confirmed_job()
    transition = job["reviewModel"]["transitions"][0]
    transition["triggerLabel"] = "', ."

    assert build_planning_board_model(job)["relations"] == []

    transition["triggerLabel"] = "无明确操作"
    assert build_planning_board_model(job)["relations"] == []

    transition["triggerLabel"] = "用户未进行显式点击操作，系统根据游戏逻辑自动触发事件"
    assert build_planning_board_model(job)["relations"] == []


def test_visual_structure_drops_punctuation_fragments_left_by_english_cleanup():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["regionIds"] = []
    job["reviewModel"]["regions"] = [item for item in job["reviewModel"]["regions"] if item["stageId"] != stage["id"]]
    job["frames"][0]["analysis"]["regionStructure"] = {
        "top": ["Boss HP / LV.1", "||", "/", "顶部信息-", "暂停按钮"],
    }

    visible = _page_text(build_planning_board_model(job)["pages"][0])

    assert "暂停按钮" in visible
    assert "||" not in visible
    assert "顶部信息-" not in visible


def test_complex_modal_frame_gets_an_automatic_local_explanation_crop():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["regionIds"] = []
    job["reviewModel"]["regions"] = [item for item in job["reviewModel"]["regions"] if item["stageId"] != stage["id"]]
    frame = job["frames"][0]
    frame["structure"] = {
        "width": 500,
        "height": 1000,
        "elementCount": 12,
        "elements": [
            {"class": "component", "bbox": [80, 220, 420, 700]},
            {"class": "component", "bbox": [100, 260, 200, 360]},
        ],
    }
    frame["analysis"]["regionStructure"] = {
        "modal": {"title": "抽取武器", "content": "九宫格武器候选区", "footer": "刷新按钮"},
    }

    crop = build_planning_board_model(job)["pages"][0]["detailCrops"][0]

    assert crop["frameId"] == frame["id"]
    assert crop["title"] == "抽取武器局部说明"
    assert crop["bounds"]["width"] < 1
    assert crop["bounds"]["height"] < 1
    assert crop["description"]


def test_page_spec_exposes_complete_planner_reading_fields_without_placeholder_fragments():
    job = make_confirmed_job()
    page = build_planning_board_model(job)["pages"][0]
    visible = _page_text(page)
    for label in ("页面用途：", "进入条件：", "区域与元素：", "玩家操作：", "系统反馈：", "状态保留：", "离开方式："):
        assert label in visible
    assert not re.search(r"(?:^|[：；])\s*[-—_'\"]+\s*(?:$|[；。])", visible)


def test_every_stage_source_frame_is_retained_and_gets_its_own_information_card():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["sourceFrameIds"] = ["F0001", "F0003"]
    job["frames"].append({
        **job["frames"][0],
        "id": "F0003",
        "imageUrl": "/artifacts/job-1/frames/F0003.jpg",
        "analysis": {
            **job["frames"][0]["analysis"],
            "what": "武器槽局部画面",
            "regionStructure": {"right": "武器槽：武器图标、等级、冷却状态"},
        },
    })

    page = build_planning_board_model(job)["pages"][0]

    assert [shot["frameId"] for shot in page["screenshots"]] == ["F0001", "F0003"]
    assert [detail["frameId"] for detail in page["screenshotDetails"]] == ["F0001", "F0003"]
    assert page["screenshotDetails"][1]["title"] == "武器槽局部画面"
    assert "武器槽" in str(page["screenshotDetails"][1]["groups"])


def test_planner_edits_persist_verbatim_into_page_order_copy_and_relation_destination():
    job = make_confirmed_job()
    model = job["reviewModel"]
    first, second = model["stages"]
    transition = next(item for item in model["transitions"] if item.get("targetStageId") == second["id"])
    edited_transition = {**transition, "triggerLabel": "人工确认后前往奖励页", "targetStageId": second["id"]}
    model = apply_operations(model, [
        {"type": "move_stage", "id": second["id"], "toIndex": 0},
        {"type": "set", "entity": "stage", "id": first["id"], "field": "name", "value": "人工页面标题"},
        {"type": "set", "entity": "stage", "id": first["id"], "field": "entryCondition", "value": "人工操作前"},
        {
            "type": "set_small_loop", "id": first["id"],
            "smallLoop": {
                "display": "人工页面概述", "trigger": "人工玩家操作", "feedback": "人工系统反馈",
                "result": "人工操作结果", "retry": "人工重试说明",
            },
        },
        {"type": "upsert_transition", "transition": edited_transition},
    ], model["revision"])
    model = confirm_flow(model, model["revision"])
    for stage in model["stages"]:
        model = confirm_stage(model, stage["id"], model["revision"])
    job["reviewModel"] = model

    board = build_planning_board_model(job)
    edited_page = next(page for page in board["pages"] if page["id"] == first["id"])
    item_texts = [item["text"] for group in edited_page["groups"] for item in group["items"]]

    assert [page["id"] for page in board["pages"]] == [second["id"], first["id"]]
    assert edited_page["title"] == "人工页面标题"
    assert all(text in item_texts for text in ["人工操作前", "人工玩家操作", "人工系统反馈", "人工操作结果"])
    assert board["relations"] == [{
        "id": transition["id"], "sourcePageId": first["id"], "targetPageId": second["id"],
        "label": "人工确认后前往奖励页", "lineStyle": "solid",
    }]
