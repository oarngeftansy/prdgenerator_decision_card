from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

from backend.feishu_native_board import compile_gve16_whiteboard
from backend.feishu_render import render_feishu_document, render_ue_board_svg
from backend.loop_hierarchy import build_loop_hierarchy
from backend.planning_board_model import build_planning_board_model
from backend.review_preview import build_review_preview
from tests.review_fixtures import make_confirmed_job


def test_page_spec_uses_confirmed_regions_as_layout_elements_with_function_details():
    job = make_confirmed_job()
    first_stage = job["reviewModel"]["stages"][0]
    regions = [
        region for region in job["reviewModel"]["regions"]
        if region["stageId"] == first_stage["id"]
    ]
    regions[0].update({
        "name": "关卡进度",
        "bounds": {"x": 0.08, "y": 0.04, "width": 0.42, "height": 0.08},
        "rule": {
            "display": "显示当前关卡进度和剩余时间",
            "condition": "战斗期间持续显示",
            "action": "",
            "feedback": "显示当前关卡进度和剩余时间",
            "result": "",
            "exception": "待确认",
        },
    })
    regions[1].update({
        "name": "强化选项",
        "bounds": {"x": 0.18, "y": 0.34, "width": 0.64, "height": 0.28},
        "rule": {
            "display": "三张强化卡片横向排列",
            "condition": "达到升级条件时显示",
            "action": "点击一张卡片完成选择",
            "feedback": "所选卡片高亮",
            "result": "强化立即生效",
            "exception": "待确认",
        },
    })

    board = build_planning_board_model(job)
    page = next(page for page in board["pages"] if page["id"] == first_stage["id"])

    assert [group["title"] for group in page["groups"]] == ["页面信息", "顶部区域（从左到右）", "主要内容区（从上到下）", "武器与强化属性", "功能说明"]
    top_item = page["groups"][1]["items"][0]
    main_item = page["groups"][2]["items"][0]
    assert top_item["text"] == "关卡进度"
    assert [child["text"] for child in top_item["children"]] == ["显示当前关卡进度和剩余时间", "战斗期间持续显示"]
    assert main_item["text"] == "强化选项"
    assert [child["text"] for child in main_item["children"]] == [
        "三张强化卡片横向排列", "达到升级条件时显示", "点击一张卡片完成选择", "所选卡片高亮", "强化立即生效",
    ]
    visible_copy = " ".join(
        text
        for group in page["groups"] for item in group["items"]
        for text in [group["title"], item["text"], *(child["text"] for child in item["children"])]
    )
    assert visible_copy.count("显示当前关卡进度和剩余时间") == 1
    assert "已确认触发" not in visible_copy
    assert "已确认反馈" not in visible_copy


def test_page_spec_falls_back_to_visual_page_structure_when_saved_regions_are_placeholders():
    job = make_confirmed_job()
    first_stage = job["reviewModel"]["stages"][0]
    frame_id = first_stage["representativeFrames"][0]["frameId"]
    frame = next(frame for frame in job["frames"] if frame["id"] == frame_id)
    frame["analysis"]["regionStructure"] = {
        "header": "顶部区域，包含暂停按钮、关卡名称、倒计时",
        "main-playfield": "主要战斗区域，显示敌人、玩家载具和爆炸反馈",
        "control-bar-bottom": "底部操作区，包含三个技能按钮",
    }
    for region in job["reviewModel"]["regions"]:
        if region["stageId"] == first_stage["id"]:
            region["name"] = "component"
            region["rule"] = {field: "덤횅훰" for field in ("display", "condition", "action", "feedback", "result", "exception")}

    board = build_planning_board_model(job)
    page = next(page for page in board["pages"] if page["id"] == first_stage["id"])
    visible_copy = str(page["groups"])

    assert [group["title"] for group in page["groups"]] == [
        "页面信息", "顶部区域（从左到右）", "主要内容区（从上到下）", "底部区域（从左到右）", "武器与强化属性", "功能说明",
    ]
    assert "暂停按钮" in visible_copy
    assert "敌人" in visible_copy
    assert "三个技能按钮" in visible_copy
    assert "页面元素" not in visible_copy
    assert "component" not in visible_copy
    assert "덤횅훰" not in visible_copy


def test_action_word_stage_title_is_replaced_by_the_actual_page_name():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["name"] = "查看战斗状态"
    frame_id = stage["representativeFrames"][0]["frameId"]
    frame = next(frame for frame in job["frames"] if frame["id"] == frame_id)
    frame["analysis"]["what"] = "游戏战斗主界面，玩家操控车辆对抗敌人潮"

    board = build_planning_board_model(job)

    assert board["pages"][0]["title"] == "战斗主界面"


def test_complex_page_exposes_bound_detail_crops_and_an_internal_state_flow():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["representativeFrames"].append({"frameId": "F0002", "role": "result"})
    first_id, second_id = [item["frameId"] for item in stage["representativeFrames"]]
    frames = {frame["id"]: frame for frame in job["frames"]}
    frames[first_id]["analysis"]["what"] = "扫荡设置页面"
    frames[second_id]["analysis"]["what"] = "扫荡奖励页面"
    region = next(region for region in job["reviewModel"]["regions"] if region["stageId"] == stage["id"])
    region.update({
        "name": "战斗伤害反馈",
        "frameId": first_id,
        "bounds": {"x": 0.58, "y": 0.32, "width": 0.28, "height": 0.22},
        "rule": {
            "display": "显示伤害数字和增减益箭头", "condition": "命中目标时显示",
            "action": "", "feedback": "伤害数字短暂浮现", "result": "", "exception": "",
        },
    })

    page = build_planning_board_model(job)["pages"][0]

    assert page["subflow"] == {
        "states": [
            {"id": f"{page['id']}-state-1", "frameId": first_id, "title": "扫荡设置页面", "order": 1},
            {"id": f"{page['id']}-state-2", "frameId": second_id, "title": "扫荡奖励页面", "order": 2},
        ],
        "steps": [{
            "id": f"{page['id']}-step-1", "sourceStateId": f"{page['id']}-state-1",
            "targetStateId": f"{page['id']}-state-2", "label": "已确认触发",
        }],
    }
    assert page["detailCrops"] == [{
        "id": region["id"], "frameId": first_id, "title": "战斗伤害反馈",
        "description": "显示伤害数字和增减益箭头；命中目标时显示；伤害数字短暂浮现",
        "bounds": region["bounds"], "groupTitle": "主要内容区（从上到下）",
        "sourceWidth": 0, "sourceHeight": 0,
    }]
    crop_item = next(
        item for group in page["groups"] for item in group["items"]
        if item["text"] == "战斗伤害反馈"
    )
    assert crop_item["cropIds"] == [region["id"]]


def test_shared_page_model_marks_confirmed_one_to_many_navigation_as_a_tree_branch():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"], second["name"] = "玩法主页", "扫荡页面"
    third = deepcopy(second)
    third.update({"id": "STG-003", "order": 3, "name": "载具页面", "regionIds": [], "transitionIds": []})
    third["confirmation"] = {"confirmed": True, "revision": job["reviewModel"]["revision"]}
    job["reviewModel"]["stages"].append(third)
    branch = {
        "id": "TRN-BRANCH", "sourceStageId": first["id"], "targetStageId": third["id"],
        "included": True, "triggerType": "tap", "triggerLabel": "点击载具入口",
        "resultType": "navigate", "confirmation": {"confirmed": True},
    }
    job["reviewModel"]["transitions"].append(branch)

    pages = build_planning_board_model(job)["pages"]
    topology = {page["id"]: page["topology"] for page in pages}

    assert topology[first["id"]]["depth"] == 0
    assert topology[second["id"]]["parentPageId"] == first["id"]
    assert topology[third["id"]]["parentPageId"] == first["id"]
    assert topology[second["id"]]["depth"] == topology[third["id"]]["depth"] == 1
    assert topology[second["id"]]["column"] != topology[third["id"]]["column"]
    assert topology[first["id"]]["branching"] is True


def test_multiple_confirmed_entry_pages_are_laid_out_as_parallel_tree_roots():
    job = make_confirmed_job()
    job["reviewModel"]["transitions"] = []

    pages = build_planning_board_model(job)["pages"]

    assert len(pages) == 2
    assert all(page["topology"]["branching"] is True for page in pages)
    assert pages[0]["topology"]["column"] != pages[1]["topology"]["column"]


def test_native_board_uses_shared_page_model_without_legacy_section_tree(monkeypatch):
    """The native board must consume the same page contract as the web preview."""
    board_model = {
        "pages": [{
            "id": "PAGE-A",
            "title": "选择强化页面",
            "screenshots": [{
                "frameId": "FRAME-A", "imageUrl": "data:image/png;base64,aGVsbG8=",
                "sourceWidth": 200, "sourceHeight": 400,
            }],
            "groups": [{"title": "强化选择", "items": [{
                "text": "选择一项强化", "children": [{"text": "确认后立即生效", "children": []}],
            }]}],
            "notes": [{"text": "需要确认返回后是否保留选择"}],
            "sourceRefs": [],
        }],
        "relations": [], "notes": [], "showUeMarkers": False,
        # Poison legacy keys: any native read of these would be a contract breach.
        "stages": None, "systems": None, "modules": None,
    }
    monkeypatch.setattr("backend.planning_board_model.build_planning_board_model", lambda job: board_model)

    board = compile_gve16_whiteboard({"id": "shared-only", "frames": []})
    nodes = [*board.structure["nodes"], *board.overlay["nodes"]]

    sections = [node for node in nodes if str(node.get("id", "")).startswith("section-page-")]
    assert len(sections) == 1
    assert sections[0]["locked"] is False and sections[0]["children"]
    assert [image.frame_id for image in board.images] == ["FRAME-A"]
    assert any(node.get("id") == "page-title-PAGE-A" for node in nodes)
    assert any(node.get("id") == "page-copy-PAGE-A" for node in nodes)
    assert any(node.get("id") == "page-note-PAGE-A-1" for node in nodes)


def test_native_board_reuses_shared_page_copy_notes_screenshots_and_relations(monkeypatch):
    board_model = {
        "pages": [
            {
                "id": "PAGE-A", "title": "选择强化", "sourceRefs": [],
                "screenshots": [
                    {"frameId": "FRAME-1", "imageUrl": "data:image/png;base64,aGVsbG8=", "sourceWidth": 200, "sourceHeight": 400},
                    {"frameId": "FRAME-2", "imageUrl": "data:image/png;base64,aGVsbG8=", "sourceWidth": 0, "sourceHeight": 0},
                ],
                "groups": [{"title": "强化说明", "items": [{
                    "text": "选择一项强化", "children": [{"text": "确认后立即生效", "children": []}],
                }]}],
                "notes": [{"text": "确认返回后是否保留选择"}],
            },
            {"id": "PAGE-B", "title": "返回战斗", "screenshots": [], "groups": [], "notes": [], "sourceRefs": []},
        ],
        "relations": [{
            "id": "REL-AB", "sourcePageId": "PAGE-A", "targetPageId": "PAGE-B",
            "label": "确认后进入战斗", "lineStyle": "solid",
        }],
        "notes": [], "showUeMarkers": False,
    }
    monkeypatch.setattr("backend.planning_board_model.build_planning_board_model", lambda job: board_model)

    board = compile_gve16_whiteboard({"id": "shared-alignment", "frames": []})
    nodes = {node["id"]: node for node in [*board.structure["nodes"], *board.overlay["nodes"]]}

    assert [nodes[f"page-title-{page['id']}"]["text"]["text"] for page in board_model["pages"]] == [
        page["title"] for page in board_model["pages"]
    ]
    assert nodes["page-copy-PAGE-A"]["text"]["text"] == "强化说明\n• 选择一项强化\n  • 确认后立即生效"
    assert nodes["page-note-PAGE-A-1"]["text"]["text"] == "确认返回后是否保留选择"
    assert [image.frame_id for image in board.images] == ["FRAME-1", "FRAME-2"]
    assert board.images[0].node["width"] * 400 == board.images[0].node["height"] * 200
    assert (board.images[1].node["width"], board.images[1].node["height"]) == (270, 500)
    assert nodes["page-relation-label-REL-AB"]["text"]["text"] == "确认后进入战斗"
    segments = [nodes[f"page-relation-REL-AB-{index}"] for index in range(1, 4)]
    assert all(segment["connector"]["shape"] == "straight" for segment in segments)
    assert segments[0]["connector"]["end"]["position"] == segments[1]["connector"]["start"]["position"]
    assert segments[1]["connector"]["end"]["position"] == segments[2]["connector"]["start"]["position"]
    assert segments[1]["connector"]["start"]["position"]["x"] < nodes["page-title-PAGE-A"]["x"]


def test_confirmed_review_board_uses_representatives_without_future_ue_markers():
    job = make_confirmed_job()
    build_review_preview(job)

    board = compile_gve16_whiteboard(job)
    nodes = [*board.structure["nodes"], *board.overlay["nodes"]]
    marker_nodes = [node for node in nodes if str(node.get("id", "")).startswith("marker-")]

    assert [image.frame_id for image in board.images] == ["F0001", "F0002"]
    assert marker_nodes == []
    assert [node for node in nodes if str(node.get("id", "")).startswith("page-title-")]
    sections = [node for node in nodes if str(node.get("id", "")).startswith("section-page-")]
    assert len(sections) == 2
    assert all(node["locked"] is False and node["children"] for node in sections)


def test_confirmed_review_transition_styles_and_automatic_labels_are_semantic():
    job = make_confirmed_job()
    first, second = job["reviewModel"]["transitions"]
    first.update({"resultType": "navigate", "direction": "forward", "triggerLabel": "确认选择"})
    second.update({
        "targetStageId": job["reviewModel"]["stages"][0]["id"],
        "resultType": "return",
        "direction": "return",
        "triggerType": "system_event",
        "triggerLabel": "自动返回",
    })
    build_review_preview(job)

    board = compile_gve16_whiteboard(job)
    connectors = {node["id"]: node for node in board.overlay["nodes"] if node["type"] == "connector"}
    labels = [node["text"]["text"] for node in board.overlay["nodes"] if node["type"] == "text_shape"]
    first_segments = [connectors[f"page-relation-{first['id']}-{index}"] for index in range(1, 4)]
    second_segments = [connectors[f"page-relation-{second['id']}-{index}"] for index in range(1, 4)]

    assert all(segment["connector"]["shape"] == "straight" for segment in [*first_segments, *second_segments])
    assert all(segment["style"]["border_style"] == "solid" for segment in first_segments)
    assert all(segment["style"]["border_style"] == "dash" for segment in second_segments)
    assert first_segments[1]["connector"]["start"]["position"]["x"] != second_segments[1]["connector"]["start"]["position"]["x"]
    assert "自动返回" in labels


def test_native_three_relations_use_distinct_page_anchors_and_avoid_the_notes_column(monkeypatch):
    pages = [
        {
            "id": page_id, "title": page_id, "screenshots": [], "groups": [], "sourceRefs": [],
            "notes": [{"text": "需要确认跨页面保留规则"}] if page_id == "PAGE-A" else [],
        }
        for page_id in ("PAGE-A", "PAGE-B", "PAGE-C")
    ]
    relations = [
        {"id": "R-AB", "sourcePageId": "PAGE-A", "targetPageId": "PAGE-B", "label": "前往乙", "lineStyle": "solid"},
        {"id": "R-AC", "sourcePageId": "PAGE-A", "targetPageId": "PAGE-C", "label": "前往丙", "lineStyle": "solid"},
        {"id": "R-BA", "sourcePageId": "PAGE-B", "targetPageId": "PAGE-A", "label": "返回甲", "lineStyle": "dashed"},
    ]
    monkeypatch.setattr(
        "backend.planning_board_model.build_planning_board_model",
        lambda job: {"pages": pages, "relations": relations, "notes": [], "showUeMarkers": False},
    )

    board = compile_gve16_whiteboard({"frames": []})
    nodes = {node["id"]: node for node in [*board.structure["nodes"], *board.overlay["nodes"]]}
    connectors = [node for node in board.overlay["nodes"] if node["type"] == "connector"]
    page_a_anchors = {
        nodes["page-relation-R-AB-1"]["connector"]["start"]["position"]["y"],
        nodes["page-relation-R-AC-1"]["connector"]["start"]["position"]["y"],
        nodes["page-relation-R-BA-3"]["connector"]["end"]["position"]["y"],
    }
    lane_xs = {
        nodes[f"page-relation-{relation['id']}-2"]["connector"]["start"]["position"]["x"]
        for relation in relations
    }
    content_rectangles = [
        (node["id"], node["x"], node["y"], node["x"] + node["width"], node["y"] + node["height"])
        for node in board.structure["nodes"]
        if node["type"] in {"text_shape", "composite_shape", "image"}
    ]

    def crosses_rectangle_interior(connector, rectangle):
        _, left, top, right, bottom = rectangle
        start = connector["connector"]["start"]["position"]
        end = connector["connector"]["end"]["position"]
        if start["y"] == end["y"]:
            segment_left, segment_right = sorted((start["x"], end["x"]))
            return top < start["y"] < bottom and max(segment_left, left) < min(segment_right, right)
        if start["x"] == end["x"]:
            segment_top, segment_bottom = sorted((start["y"], end["y"]))
            return left < start["x"] < right and max(segment_top, top) < min(segment_bottom, bottom)
        raise AssertionError("native relation segment must remain horizontal or vertical")

    assert len(connectors) == 9
    assert all(node["connector"]["shape"] == "straight" for node in connectors)
    assert len(page_a_anchors) == 3
    assert len(lane_xs) == 3
    assert all(lane_x < nodes["page-title-PAGE-A"]["x"] for lane_x in lane_xs)
    assert not [
        (connector["id"], rectangle[0])
        for connector in connectors
        for rectangle in content_rectangles
        if crosses_rectangle_interior(connector, rectangle)
    ]


def test_confirmed_review_hierarchy_and_document_use_review_loops_without_screenshots(tmp_path: Path):
    job = make_confirmed_job()
    job["reviewModel"]["stages"][0]["smallLoop"]["display"] = "reviewed selection loop"
    job["reviewModel"]["crossStateConstraints"] = [
        {"id": "CNS-001", "text": "keep selection on return", "severity": "non_core", "status": "unknown"}
    ]
    build_review_preview(job)

    hierarchy = build_loop_hierarchy(job)
    rendered = render_feishu_document(job, tmp_path)

    assert [stage["title"] for stage in hierarchy["largeLoops"][0]["stages"]] == [
        stage["name"] for stage in job["reviewModel"]["stages"]
    ]
    assert "reviewed selection loop" in rendered.xml
    assert "keep selection on return" in rendered.xml
    assert rendered.evidence_images == ()
    assert rendered.xml.count("<whiteboard") == 1
    assert [board.key for board in rendered.native_boards] == ["planning"]
    assert "UE 流转图" not in rendered.xml and "竞品参考" not in rendered.xml


def test_targetless_state_and_close_transitions_stay_in_their_page_sections():
    job = make_confirmed_job()
    state_change, close_overlay = job["reviewModel"]["transitions"]
    state_change.update({"targetStageId": None, "resultType": "state_change", "resultState": "selected in place"})
    close_overlay.update({"targetStageId": None, "resultType": "close_overlay", "resultState": "back to page"})
    build_review_preview(job)

    board = compile_gve16_whiteboard(job)
    connectors = [node for node in board.overlay["nodes"] if node["type"] == "connector"]

    assert connectors == []
    assert len([node for node in board.structure["nodes"] if str(node.get("id", "")).startswith("section-page-")]) == 2


def test_confirmed_component_and_constraint_unknowns_are_yellow_notes():
    job = make_confirmed_job()
    stage_id = job["reviewModel"]["stages"][0]["id"]
    job["reviewModel"]["components"] = [{
        "id": "CMP-UNKNOWN", "stageId": stage_id, "name": "selection control",
        "confirmation": {"confirmed": True}, "unknowns": ["确认组件状态"],
    }]
    job["reviewModel"]["crossStateConstraints"] = [{
        "id": "CNS-UNKNOWN", "stageId": stage_id, "text": "selection persists", "status": "unknown",
        "severity": "non_core", "unknowns": ["确认返回规则"],
    }]
    build_review_preview(job)

    board = compile_gve16_whiteboard(job)
    notes = [node for node in board.structure["nodes"] if node.get("style", {}).get("fill_color") == "#fff3bf"]
    note_texts = [node["text"]["text"] for node in notes]

    assert "确认组件状态" in note_texts
    assert "确认返回规则" in note_texts


def test_global_cross_state_constraint_is_visible_in_web_and_native_boards(tmp_path: Path):
    job = make_confirmed_job()
    text = "所有页面返回后都保留本局选择"
    job["reviewModel"]["crossStateConstraints"] = [{"id": "CNS-GLOBAL", "text": text}]

    svg, _ = render_ue_board_svg(job, tmp_path)
    board = compile_gve16_whiteboard(job)
    native_notes = [
        node for node in board.structure["nodes"]
        if str(node.get("id") or "").startswith("board-note-")
    ]

    assert 'data-node-kind="board-note"' in svg
    assert text in "".join(ET.fromstring(svg).itertext())
    assert [node["text"]["text"] for node in native_notes] == [text]
    assert all(node["style"]["fill_color"] == "#fff3bf" for node in native_notes)


def test_shared_representatives_keep_rule_order_without_number_prefixes():
    job = make_confirmed_job()
    first_stage, second_stage = job["reviewModel"]["stages"]
    second_stage["representativeFrames"] = [{"frameId": "F0001", "role": "entry"}]
    second_regions = [region for region in job["reviewModel"]["regions"] if region["stageId"] == second_stage["id"]]
    second_regions[0]["frameId"] = "F0001"
    first_regions = [region for region in job["reviewModel"]["regions"] if region["stageId"] == first_stage["id"]]
    first_regions[0]["displayOrder"], first_regions[1]["displayOrder"] = 2, 1
    build_review_preview(job)

    board = compile_gve16_whiteboard(job)
    markers = {node["id"]: node for node in board.overlay["nodes"] if str(node.get("id", "")).startswith("marker-")}

    assert [item.frame_id for item in board.images] == ["F0001", "F0001"]
    assert markers == {}


def test_web_preview_consumes_shared_page_relation_structure(tmp_path: Path):
    from backend.feishu_render import render_ue_board_svg
    job = make_confirmed_job()
    first, second = job["reviewModel"]["transitions"]
    first.update(direction="forward", resultType="navigate")
    second.update(direction="return", resultType="return", targetStageId=job["reviewModel"]["stages"][0]["id"])
    job["reviewModel"]["crossStateConstraints"] = [{"text": "返回后保留选择"}]
    svg, _ = render_ue_board_svg(job, tmp_path)
    for page_id in ("STG-001", "STG-002"):
        assert f'data-page-id="{page_id}"' in svg
    assert 'data-line-style="solid"' in svg
    assert 'data-line-style="dashed"' in svg
    assert '#FFF3BF' in svg
    assert 'data-marker-number=' not in svg


def test_web_preview_returns_safe_empty_board_without_a_legacy_planning_model(tmp_path: Path):
    svg, images = render_ue_board_svg({"id": "empty", "frames": []}, tmp_path)
    visible_text = "".join(ET.fromstring(svg).itertext())

    assert images == ()
    assert 'data-node-kind="empty-page-board"' in svg
    assert "暂无已确认页面" in visible_text
    assert 'data-node-kind="stage-section"' not in svg


def test_web_preview_renders_full_page_notes_and_grows_the_page_unit(tmp_path: Path):
    job = make_confirmed_job()
    long_note = "需要策划确认返回页面后是否保留此前选择状态以及再次进入时是否继续沿用"
    job["reviewModel"]["stages"][0]["unknowns"] = [long_note * 4]

    svg, _ = render_ue_board_svg(job, tmp_path)
    root = ET.fromstring(svg)
    note_groups = [node for node in root.iter() if node.attrib.get("data-node-kind") == "page-note"]
    first_page = next(node for node in root.iter() if node.attrib.get("data-page-id") == "STG-001")
    page_rect = next(node for node in first_page if node.tag.endswith("rect"))

    assert note_groups
    assert long_note in "".join(root.itertext())
    assert len([node for node in note_groups[0].iter() if node.tag.endswith("tspan")]) >= 4
    assert int(page_rect.attrib["height"]) > 430


def test_web_preview_accounts_for_long_page_and_group_title_lines(monkeypatch, tmp_path: Path):
    long_page_title = "页面标题需要完整展示并且每一行都会推动下方内容继续向下排列" * 5
    long_group_title = "说明分组标题同样需要完整换行并为正文留下足够空间" * 5
    board = {
        "pages": [
            {"id": "PAGE-A", "title": long_page_title, "screenshots": [], "notes": [], "sourceRefs": [],
             "groups": [{"title": long_group_title, "items": [{"text": "正文内容", "children": []}]}]},
            {"id": "PAGE-B", "title": "下一页面", "screenshots": [], "notes": [], "sourceRefs": [], "groups": []},
        ],
        "relations": [], "notes": [], "showUeMarkers": False,
    }
    monkeypatch.setattr("backend.planning_board_model.build_planning_board_model", lambda job: board)

    svg, _ = render_ue_board_svg({"id": "long-title", "frames": []}, tmp_path)
    root = ET.fromstring(svg)
    first_page = next(node for node in root.iter() if node.attrib.get("data-page-id") == "PAGE-A")
    second_page = next(node for node in root.iter() if node.attrib.get("data-page-id") == "PAGE-B")
    first_rect = next(node for node in first_page if node.tag.endswith("rect"))
    second_rect = next(node for node in second_page if node.tag.endswith("rect"))
    group = next(node for node in first_page.iter() if node.attrib.get("data-node-kind") == "page-group")

    assert len([node for node in first_page.iter() if node.tag.endswith("tspan") and node.text in long_page_title]) >= 5
    assert len([node for node in group.iter() if node.tag.endswith("tspan")]) >= 4
    assert int(first_rect.attrib["height"]) > int(second_rect.attrib["height"])
    assert int(second_rect.attrib["y"]) == int(first_rect.attrib["y"])
    assert int(second_rect.attrib["x"]) > int(first_rect.attrib["x"]) + int(first_rect.attrib["width"])


def test_web_preview_preserves_nested_group_items_with_depth_and_bullets(monkeypatch, tmp_path: Path):
    board = {
        "pages": [{
            "id": "PAGE-A", "title": "嵌套说明", "screenshots": [], "notes": [], "sourceRefs": [],
            "groups": [{"title": "操作层级", "items": [{
                "text": "第一层", "children": [{"text": "第二层", "children": [{"text": "第三层", "children": []}]}],
            }]}],
        }],
        "relations": [], "notes": [], "showUeMarkers": False,
    }
    monkeypatch.setattr("backend.planning_board_model.build_planning_board_model", lambda job: board)

    svg, _ = render_ue_board_svg({"id": "nested", "frames": []}, tmp_path)
    root = ET.fromstring(svg)
    items = [node for node in root.iter() if node.attrib.get("data-node-kind") == "page-copy-item"]

    assert [node.attrib["data-depth"] for node in items] == ["0", "1", "2"]
    assert [next(node.itertext()).startswith("• ") for node in items] == [True, True, True]
    item_text_nodes = [next(child for child in node.iter() if child.tag.endswith("text")) for node in items]
    assert len({node.attrib["x"] for node in item_text_nodes}) == 3


def test_web_and_native_boards_render_internal_subflow_and_bound_detail_crop(monkeypatch, tmp_path: Path):
    screenshot = {
        "frameId": "FRAME-A", "imageUrl": "data:image/png;base64,aGVsbG8=",
        "sourceWidth": 400, "sourceHeight": 800,
    }
    crop = {
        "id": "CROP-A", "frameId": "FRAME-A", "title": "伤害反馈",
        "bounds": {"x": 0.5, "y": 0.25, "width": 0.25, "height": 0.2},
        "groupTitle": "主要内容区（从上到下）", "sourceWidth": 400, "sourceHeight": 800,
    }
    board_model = {
        "pages": [{
            "id": "PAGE-A", "title": "扫荡", "screenshots": [
                screenshot,
                {"frameId": "FRAME-B", "imageUrl": "data:image/png;base64,aGVsbG8=", "sourceWidth": 400, "sourceHeight": 800},
            ],
            "groups": [{"title": "主要内容区（从上到下）", "items": [{
                "text": "伤害反馈", "children": [{"text": "显示伤害数字", "children": []}], "cropIds": ["CROP-A"],
            }]}],
            "detailCrops": [crop], "notes": [], "sourceRefs": [],
            "subflow": {
                "states": [
                    {"id": "STATE-A", "frameId": "FRAME-A", "title": "扫荡设置页面", "order": 1},
                    {"id": "STATE-B", "frameId": "FRAME-B", "title": "奖励结果页面", "order": 2},
                ],
                "steps": [{"id": "STEP-A", "sourceStateId": "STATE-A", "targetStateId": "STATE-B", "label": "点击扫荡"}],
            },
        }],
        "relations": [], "notes": [], "showUeMarkers": False,
    }
    monkeypatch.setattr("backend.planning_board_model.build_planning_board_model", lambda job: board_model)

    svg, _ = render_ue_board_svg({"id": "layered", "frames": []}, tmp_path)
    root = ET.fromstring(svg)
    crop_node = next(node for node in root.iter() if node.attrib.get("data-node-kind") == "page-detail-crop")
    subflow_edge = next(node for node in root.iter() if node.attrib.get("data-edge-kind") == "page-subflow-step")

    assert crop_node.attrib["data-crop-id"] == "CROP-A"
    assert crop_node.attrib["data-source-frame-id"] == "FRAME-A"
    assert crop_node.attrib["data-source-view-box"] == "200 200 100 160"
    assert subflow_edge.attrib["data-step-id"] == "STEP-A"
    assert "点击扫荡" in "".join(subflow_edge.itertext())

    native = compile_gve16_whiteboard({"id": "layered", "frames": []})
    native_nodes = [*native.structure["nodes"], *native.overlay["nodes"]]
    native_crop = next(node for node in native_nodes if node.get("id") == "page-detail-crop-PAGE-A-CROP-A")
    assert native_crop["crop"] == crop["bounds"]
    assert any(str(node.get("id", "")).startswith("page-subflow-STEP-A") for node in native_nodes)


def test_web_and_native_boards_place_confirmed_siblings_as_a_tree_branch(monkeypatch, tmp_path: Path):
    pages = [
        {"id": "ROOT", "title": "玩法主页", "screenshots": [], "groups": [], "notes": [], "sourceRefs": [],
         "topology": {"parentPageId": "", "depth": 0, "column": 0.5, "branching": True}},
        {"id": "LEFT", "title": "扫荡", "screenshots": [], "groups": [], "notes": [], "sourceRefs": [],
         "topology": {"parentPageId": "ROOT", "depth": 1, "column": 0.0, "branching": False}},
        {"id": "RIGHT", "title": "载具养成", "screenshots": [], "groups": [], "notes": [], "sourceRefs": [],
         "topology": {"parentPageId": "ROOT", "depth": 1, "column": 1.0, "branching": False}},
    ]
    relations = [
        {"id": "ROOT-LEFT", "sourcePageId": "ROOT", "targetPageId": "LEFT", "label": "点击扫荡", "lineStyle": "solid"},
        {"id": "ROOT-RIGHT", "sourcePageId": "ROOT", "targetPageId": "RIGHT", "label": "点击载具", "lineStyle": "solid"},
    ]
    monkeypatch.setattr(
        "backend.planning_board_model.build_planning_board_model",
        lambda job: {"pages": pages, "relations": relations, "notes": [], "showUeMarkers": False},
    )

    svg, _ = render_ue_board_svg({"id": "tree", "frames": []}, tmp_path)
    root = ET.fromstring(svg)
    page_nodes = {node.attrib["data-page-id"]: node for node in root.iter() if node.attrib.get("data-node-kind") == "page-spec"}
    rects = {page_id: next(child for child in node if child.tag.endswith("rect")) for page_id, node in page_nodes.items()}
    assert rects["LEFT"].attrib["y"] == rects["RIGHT"].attrib["y"]
    assert rects["LEFT"].attrib["x"] != rects["RIGHT"].attrib["x"]
    assert int(rects["ROOT"].attrib["y"]) < int(rects["LEFT"].attrib["y"])
    assert len([
        node for node in root.iter()
        if node.attrib.get("data-edge-kind") == "page-relation" and node.attrib.get("data-route") == "tree-branch"
    ]) == 2

    native = compile_gve16_whiteboard({"id": "tree", "frames": []})
    native_titles = {node["id"]: node for node in native.structure["nodes"] if str(node.get("id", "")).startswith("page-title-")}
    assert native_titles["page-title-LEFT"]["y"] == native_titles["page-title-RIGHT"]["y"]
    assert native_titles["page-title-LEFT"]["x"] != native_titles["page-title-RIGHT"]["x"]
    assert any(node.get("treeRelation") is True for node in native.overlay["nodes"])


def test_web_preview_assigns_bidirectional_and_branch_relations_independent_lanes(monkeypatch, tmp_path: Path):
    pages = [
        {"id": page_id, "title": page_id, "screenshots": [], "notes": [], "sourceRefs": [], "groups": []}
        for page_id in ("PAGE-A", "PAGE-B", "PAGE-C")
    ]
    relations = [
        {"id": "R-AB", "sourcePageId": "PAGE-A", "targetPageId": "PAGE-B", "label": "前往乙页面", "lineStyle": "solid"},
        {"id": "R-BA", "sourcePageId": "PAGE-B", "targetPageId": "PAGE-A", "label": "返回甲页面并在完成确认后继续保留所有已经选择的内容" * 4, "lineStyle": "dashed"},
        {"id": "R-AC", "sourcePageId": "PAGE-A", "targetPageId": "PAGE-C", "label": "前往丙页面", "lineStyle": "solid"},
        {"id": "R-CA", "sourcePageId": "PAGE-C", "targetPageId": "PAGE-A", "label": "返回起始页面并在完成确认后继续保留所有已经选择的内容" * 4, "lineStyle": "dashed"},
    ]
    board = {"pages": pages, "relations": relations, "notes": [], "showUeMarkers": False}
    monkeypatch.setattr("backend.planning_board_model.build_planning_board_model", lambda job: board)

    svg, _ = render_ue_board_svg({"id": "relations", "frames": []}, tmp_path)
    root = ET.fromstring(svg)
    edges = [node for node in root.iter() if node.attrib.get("data-edge-kind") == "page-relation"]
    paths = [next(node for node in edge.iter() if node.tag.endswith("path")) for edge in edges]
    labels = [next(node for node in edge.iter() if node.tag.endswith("text")) for edge in edges]
    viewbox_width = int(root.attrib["viewBox"].split()[2])

    def conservative_line_width(text: str) -> float:
        return sum(12 if ord(character) > 127 else 7.2 for character in text)

    assert [edge.attrib["data-lane-index"] for edge in edges] == ["0", "1", "2", "3"]
    assert {edge.attrib["data-route-side"] for edge in edges} == {"left", "right"}
    assert len({edge.attrib["data-lane-x"] for edge in edges}) == 4
    assert all(int(edge.attrib["data-label-x"]) >= 0 for edge in edges)
    for label in labels:
        label_x = int(label.attrib["x"])
        line_width = max(conservative_line_width(tspan.text or "") for tspan in label if tspan.tag.endswith("tspan"))
        assert label_x + line_width <= viewbox_width
    for side in ("left", "right"):
        regions = []
        side_edges = [edge for edge in edges if edge.attrib["data-route-side"] == side]
        for edge in side_edges:
            label = next(node for node in edge.iter() if node.tag.endswith("text"))
            label_x = int(label.attrib["x"])
            label_width = max(conservative_line_width(tspan.text or "") for tspan in label if tspan.tag.endswith("tspan"))
            regions.append((label_x, label_x + label_width, int(edge.attrib["data-lane-x"])))
        for (_, current_right, _), (next_left, _, _) in zip(sorted(regions), sorted(regions)[1:]):
            assert next_left - current_right >= 24
        for left, right, own_lane in regions:
            for _, _, other_lane in regions:
                if other_lane == own_lane:
                    continue
                distance = left - other_lane if other_lane < left else other_lane - right
                assert distance >= 24
    assert all(len([path for path in edge.iter() if path.attrib.get("data-route-layer") == "gap"]) == 1 for edge in edges)
    assert all(len([path for path in edge.iter() if path.attrib.get("data-route-layer") == "line"]) == 1 for edge in edges)
    assert len({path.attrib["d"] for path in paths}) == 4
    assert len({label.attrib["x"] for label in labels}) == 4


def test_web_preview_uses_shared_data_image_or_a_visible_unavailable_placeholder(monkeypatch, tmp_path: Path):
    screenshot = {
        "frameId": "FRAME-NOT-IN-JOB", "imageUrl": "data:image/png;base64,aGVsbG8=",
        "sourceWidth": 200, "sourceHeight": 100,
    }
    board = {
        "pages": [{"id": "PAGE-A", "title": "截图来源", "screenshots": [screenshot], "groups": [], "notes": [], "sourceRefs": []}],
        "relations": [], "notes": [], "showUeMarkers": False,
    }
    monkeypatch.setattr("backend.planning_board_model.build_planning_board_model", lambda job: board)

    svg, _ = render_ue_board_svg({"id": "shared-image", "frames": []}, tmp_path)
    root = ET.fromstring(svg)
    image = next(node for node in root.iter() if node.tag.endswith("image"))
    assert image.attrib["href"] == screenshot["imageUrl"]
    assert 'data-image-state="unavailable"' not in svg
    assert 'href=""' not in svg

    screenshot["imageUrl"] = "https://unsafe.example/screenshot.png"
    svg, _ = render_ue_board_svg({"id": "shared-image", "frames": []}, tmp_path)
    assert 'data-image-state="unavailable"' in svg
    assert "截图暂不可用" in "".join(ET.fromstring(svg).itertext())
    assert 'href=""' not in svg


def test_web_preview_renders_shared_pages_as_screenshot_and_copy_cards(tmp_path: Path):
    """The web board keeps the page model visible without rebuilding a system tree."""
    job = make_confirmed_job()
    for frame in job["frames"]:
        frame["imageUrl"] = "data:image/png;base64,aGVsbG8="

    svg, _ = render_ue_board_svg(job, tmp_path)

    assert 'data-node-kind="page-spec"' in svg
    assert 'data-node-kind="page-screenshot"' in svg
    assert 'data-node-kind="page-copy"' in svg
    assert 'data-edge-kind="page-relation"' in svg
    assert 'data-route="page-gutter"' in svg
    assert 'preserveAspectRatio="xMidYMid meet"' in svg
    assert 'preserveAspectRatio="xMidYMid slice"' not in svg
    assert "…" not in svg
    assert 'data-system-id=' not in svg
    assert 'data-module-id=' not in svg


def test_web_preview_draws_vertical_page_specs_without_a_system_tree(tmp_path: Path):
    job = make_confirmed_job()
    job["reviewModel"]["stages"][0]["name"] = "持续战斗并击退敌人"
    job["reviewModel"]["stages"][1]["name"] = "查看升级选项"
    svg, _ = render_ue_board_svg(job, tmp_path)
    assert svg.count('data-node-kind="page-spec"') == 2
    assert 'data-system-id=' not in svg
    assert 'data-module-id=' not in svg
    assert svg.index('data-page-id="STG-001"') < svg.index('data-page-id="STG-002"')


def test_web_preview_routes_arrows_through_empty_gutters_instead_of_cards(tmp_path: Path):
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = "持续战斗并击退敌人"
    second["name"] = "查看升级选项"

    svg, _ = render_ue_board_svg(job, tmp_path)

    assert 'data-route="page-gutter"' in svg
    assert 'data-edge-kind="page-relation"' in svg


def test_web_preview_renders_shared_group_copy_as_separate_lines(tmp_path: Path):
    job = make_confirmed_job()
    stage_id = job["reviewModel"]["stages"][0]["id"]
    regions = [region for region in job["reviewModel"]["regions"] if region["stageId"] == stage_id]
    regions[0]["name"] = "战斗区域"
    regions[0]["rule"].update({
        "display": "敌人进入战斗区域",
        "condition": "玩家控制载具移动，武器自动攻击",
        "feedback": "命中后显示伤害数字和爆炸效果",
        "result": "敌人生命值降低",
    })

    svg, _ = render_ue_board_svg(job, tmp_path)
    visible_text = "".join(ET.fromstring(svg).itertext())

    assert 'data-node-kind="page-copy"' in svg
    assert "敌人进入战斗区域" in visible_text
    assert "玩家控制载具移动，武器自动攻击" in visible_text
    assert "命中后显示伤害数字和爆炸效果" in visible_text
    assert "敌人生命值降低" in visible_text


def test_web_preview_wraps_group_copy_without_ellipsis(tmp_path: Path):
    job = make_confirmed_job()
    job["reviewModel"]["stages"][0]["smallLoop"]["feedback"] = (
        "玩家完成选择后系统立即应用强化效果并恢复战斗，同时刷新当前武器表现和剩余选择次数"
    )

    svg, _ = render_ue_board_svg(job, tmp_path)
    root = ET.fromstring(svg)
    copy_groups = [node for node in root.iter() if node.attrib.get("data-node-kind") == "page-copy"]
    lines = [node.text or "" for group in copy_groups for node in group.iter() if node.tag.endswith("tspan")]

    assert lines
    assert max(map(len, lines)) <= 42
    assert all("…" not in line for line in lines)


def test_native_board_text_nodes_expand_for_wrapped_rule_copy():
    job = make_confirmed_job()
    job["reviewModel"]["stages"][0]["smallLoop"]["feedback"] = "确认后立即应用强化效果并恢复战斗，同时刷新当前武器表现和剩余选择次数" * 3
    board = compile_gve16_whiteboard(job)
    rule_nodes = [node for node in board.structure["nodes"] if str(node.get("id", "")).startswith("page-copy-")]

    assert rule_nodes
    assert all(node["height"] >= 80 for node in rule_nodes)


def test_web_preview_does_not_invent_an_arrow_between_unconnected_pages(tmp_path: Path):
    job = make_confirmed_job()
    for stage, name in zip(job["reviewModel"]["stages"], ("持续战斗并击退敌人", "查看战斗状态")):
        stage["name"] = name
    job["reviewModel"]["transitions"] = []

    svg, _ = render_ue_board_svg(job, tmp_path)

    assert 'data-edge-kind="page-relation"' not in svg


def test_native_and_web_boards_preserve_portrait_source_aspect_ratio(tmp_path: Path):
    job = make_confirmed_job()
    for frame in job["frames"]:
        frame["structure"] = {"width": 494, "height": 924}
        frame["imagePath"] = f"frames/{frame['id']}.jpg"
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    for frame in job["frames"]:
        (frame_dir / f"{frame['id']}.jpg").write_bytes(b"source-file")

    board = compile_gve16_whiteboard(job)
    assert board.images
    for image in board.images:
        assert image.node["width"] * 924 == image.node["height"] * 494
        assert (image.node["width"], image.node["height"]) == (247, 462)

    from backend.feishu_render import render_ue_board_svg
    svg, _ = render_ue_board_svg(job, tmp_path)
    assert 'data-source-width="494"' in svg
    assert 'data-source-height="924"' in svg
    assert 'preserveAspectRatio="xMidYMid meet"' in svg
    assert 'preserveAspectRatio="xMidYMid slice"' not in svg


def test_large_coprime_screenshots_stay_bounded_and_nearly_exact_in_native_and_web(tmp_path: Path):
    job = make_confirmed_job()
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    for frame in job["frames"]:
        frame["structure"] = {"width": 853, "height": 1280}
        frame["imagePath"] = f"frames/{frame['id']}.jpg"
        (frame_dir / f"{frame['id']}.jpg").write_bytes(b"source-file")

    board = compile_gve16_whiteboard(job)
    native_images = sorted(board.images, key=lambda image: image.node["y"])
    for image in native_images:
        width, height = image.node["width"], image.node["height"]
        assert width <= 360 and height <= 500
        assert abs(width / height - 853 / 1280) < 1e-9
    assert all(
        current.node["y"] + current.node["height"] < following.node["y"]
        for current, following in zip(native_images, native_images[1:])
    )

    svg, _ = render_ue_board_svg(job, tmp_path)
    root = ET.fromstring(svg)
    web_images = [node for node in root.iter() if node.tag.endswith("image")]
    assert web_images
    for image in web_images:
        width, height = float(image.attrib["width"]), float(image.attrib["height"])
        assert width <= 370 and height <= 300
        assert abs(width / height - 853 / 1280) < 1e-9


def test_confirmed_region_never_falls_back_to_a_different_representative_image():
    job = make_confirmed_job()
    first_stage = job["reviewModel"]["stages"][0]
    first_region = next(region for region in job["reviewModel"]["regions"] if region["stageId"] == first_stage["id"])
    first_region["frameId"] = "F0002"

    board = compile_gve16_whiteboard(job)

    assert [image.frame_id for image in board.images] == ["F0001", "F0002"]


def test_ue_board_is_screenshot_first_and_hierarchically_grouped(tmp_path: Path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    (frame_dir / "F0001.jpg").write_bytes(b"first-image")
    (frame_dir / "F0002.jpg").write_bytes(b"second-image")
    job = {
        "id": "sample-board",
        "metadata": {"mode": "interaction", "projectName": "示例"},
        "frames": [
            {"id": "F0001", "timestamp": 1, "imagePath": "frames/F0001.jpg"},
            {"id": "F0002", "timestamp": 3, "imagePath": "frames/F0002.jpg"},
        ],
        "planningModel": {
            "mode": "interaction",
            "project": {"name": "示例", "scope": "还原交互"},
            "loopHierarchy": {
                "largeLoops": [{
                    "id": "LOOP-001", "title": "完成一次任务", "entryCondition": "进入首页",
                    "repeatCondition": "再次发起任务", "exitCondition": "返回首页",
                    "stages": [{
                        "id": "STAGE-01", "title": "选择目标", "smallLoops": [{
                            "id": "SMALL-01", "title": "选择并确认", "entryCondition": "目标列表已显示",
                            "repeatCondition": "更换目标", "exitCondition": "确认目标",
                            "steps": [
                                {"id": "STEP-01", "title": "打开列表", "userAction": "点击目标入口", "systemResponse": "显示目标列表", "evidence": [{"sourceId": "F0001"}]},
                                {"id": "STEP-02", "title": "确认目标", "userAction": "点击确认", "systemResponse": "关闭弹窗并刷新首页", "evidence": [{"sourceId": "F0002"}]},
                            ],
                        }],
                    }],
                }],
            },
            "designHandoff": {"flowEdges": []},
        },
    }

    rendered = render_feishu_document(job, tmp_path)

    assert rendered.board_format == "svg"
    assert 'data-node-kind="empty-page-board"' not in rendered.board_svg
    assert rendered.board_svg.count('data-node-kind="page-spec"') == 2
    assert rendered.board_svg.count('data-node-kind="page-screenshot"') == 2
    assert "flowchart LR" not in rendered.board_svg
    assert rendered.evidence_images == ()
    assert [image.frame_id for image in rendered.native_board.images] == ["F0001", "F0002"]
    assert "<h1>参考画面</h1>" not in rendered.xml
    sections = [node for node in rendered.native_board.structure["nodes"] if node["type"] == "section"]
    assert len(sections) == 2
    assert all(node["locked"] is False and node["children"] for node in sections)
