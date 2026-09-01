from copy import deepcopy

from backend.review_model import COMPONENT_STATE_KEYS, build_review_model, empty_rule_domains, ensure_review_model
from backend.review_service import apply_operations
from tests.review_fixtures import make_confirmed_job, make_image_job


def job_with_scene_titles(titles):
    template = make_image_job()
    frame_template = template["frames"][0]
    scene_template = template["scenes"][0]
    job = deepcopy(template)
    job["frames"] = []
    job["scenes"] = []
    for index, title in enumerate(titles, 1):
        frame = deepcopy(frame_template)
        frame["id"] = f"F{index:04d}"
        frame["sceneId"] = index - 1
        frame["sequenceIndex"] = index
        frame["sourceName"] = f"{index:02d}.png"
        frame["imageUrl"] = f"/artifacts/job-1/frames/F{index:04d}.jpg"
        scene = deepcopy(scene_template)
        scene["id"] = index - 1
        scene["frameIds"] = [frame["id"]]
        scene["analysis"]["title"] = title
        job["frames"].append(frame)
        job["scenes"].append(scene)
    return job


def test_generated_review_compacts_adjacent_functional_stages_to_seven():
    model = build_review_model(job_with_scene_titles([
        "普通战斗-开始", "普通战斗-持续", "武器选择-展开", "武器选择-结果",
        "技能选择", "Boss预警", "Boss战斗", "Boss战斗-持续", "胜利结算",
    ]))

    assert 3 <= len(model["stages"]) <= 7
    assert list(model["sources"]) == [f"F{index:04d}" for index in range(1, 10)]
    assert all(1 <= len(stage["representativeFrames"]) <= 3 for stage in model["stages"])


def test_generated_review_never_merges_non_adjacent_matching_titles():
    model = build_review_model(job_with_scene_titles(["普通战斗", "武器选择", "普通战斗"]))

    names = [stage["name"] for stage in model["stages"]]
    assert len(names) == 3
    assert names[0] == names[2]
    assert names[1] != names[0]


def test_seed_does_not_treat_sequence_order_as_proven_navigation():
    model = ensure_review_model(make_image_job())

    first = model["transitions"][0]
    assert first["sourceStageId"] == "STG-001"
    assert first["targetStageId"] == "STG-002"
    assert first["targetBasis"] == "sequence_candidate"
    assert first["confirmation"]["confirmed"] is False


def test_terminal_transition_is_not_a_sequence_candidate():
    model = ensure_review_model(make_image_job())

    terminal = model["transitions"][-1]
    assert terminal["targetStageId"] is None
    assert terminal["targetBasis"] == "sequence_end"
    assert model["quality"]["candidateTransitionCount"] == 1


def test_existing_transition_without_an_adjacent_target_is_not_backfilled_as_sequence_candidate():
    job = make_confirmed_job()
    transition = job["reviewModel"]["transitions"][0]
    transition["targetStageId"] = "STG-999"

    model = ensure_review_model(job)

    assert transition["targetBasis"] == "visual"
    assert model["quality"]["candidateTransitionCount"] == 0


def test_existing_review_model_preserves_human_values_and_backfills_quality():
    job = make_confirmed_job()
    legacy = job["reviewModel"]
    legacy.pop("quality", None)
    original_confirmation = legacy["stages"][0]["confirmation"].copy()
    original_small_loop = legacy["stages"][0]["smallLoop"].copy()

    model = ensure_review_model(job)

    assert model is legacy
    assert model["stages"][0]["confirmation"] == original_confirmation
    assert model["stages"][0]["smallLoop"] == original_small_loop
    assert model["quality"]["qualified"] is True


def test_confirmed_page_review_stays_qualified_when_legacy_small_loop_is_pending():
    job = make_confirmed_job()
    for stage in job["reviewModel"]["stages"]:
        stage["smallLoop"] = {key: "未知待确认" for key in ("display", "trigger", "feedback", "result", "retry")}
        stage["objective"] = "玩家在当前页面完成对应操作并进入下一环节。"
        stage["representativeFrames"] = [{"frameId": "F0001", "role": "entry"}]

    model = ensure_review_model(job)

    assert all(stage["confirmation"]["confirmed"] for stage in model["stages"])
    assert model["quality"] == {
        "qualified": True,
        "blockers": [],
        "candidateTransitionCount": model["quality"]["candidateTransitionCount"],
        "stageCount": len(model["stages"]),
    }


def test_legacy_review_model_is_backfilled_without_losing_confirmations():
    job = make_image_job()
    legacy = build_review_model(job)
    guidance = [{"id": "GDE-001", "title": "existing guidance"}]
    asset = {"id": "UX-001", "relativePath": "reference_boards/ux/existing.png", "order": 1, "kind": "wireframe"}
    legacy["ruleDomains"] = {
        "guidance": guidance,
        "confirmation": {"confirmed": True, "revision": 7},
    }
    legacy["referenceBoards"] = {"ux": {"assets": [asset]}}
    legacy["reviewState"]["flowConfirmed"] = True
    job["reviewModel"] = legacy

    upgraded = ensure_review_model(job)

    assert upgraded["reviewState"]["flowConfirmed"] is True
    assert upgraded["ruleDomains"] == {"guidance": guidance, "confirmation": {"confirmed": True, "revision": 7}}
    assert upgraded["ruleDomains"]["confirmation"] == {"confirmed": True, "revision": 7}
    assert upgraded["referenceBoards"]["ux"]["assets"] == [asset]
    assert upgraded["referenceBoards"]["ux"]["assets"][0]["kind"] == "wireframe"
    assert upgraded["referenceBoards"]["planning"]["source"] == "confirmed_review_model"


def test_active_board_backfill_defaults_are_not_aliased_between_models():
    jobs = [make_image_job(), make_image_job()]
    for job in jobs:
        legacy = build_review_model(job)
        legacy.pop("ruleDomains", None)
        legacy.pop("referenceBoards")
        job["reviewModel"] = legacy

    first, second = (ensure_review_model(job) for job in jobs)
    first["referenceBoards"]["competitor"]["assets"].append({"id": "CPA-001"})

    assert "ruleDomains" not in first
    assert "ruleDomains" not in second
    assert second["referenceBoards"]["competitor"]["assets"] == []


def test_ensure_preserves_legacy_fields_without_backfilling_them():
    job = make_image_job()
    legacy = build_review_model(job)
    legacy["ruleDomains"] = {"legacy": {"keep": True}}
    legacy["referenceBoards"]["ux"] = {"assets": [{"id": "UXA-001"}], "status": "ready"}

    job["reviewModel"] = legacy
    ensured = ensure_review_model(job)

    assert ensured["ruleDomains"] == {"legacy": {"keep": True}}
    assert ensured["referenceBoards"]["ux"] == {"assets": [{"id": "UXA-001"}], "status": "ready"}


def test_unqualified_analysis_stays_out_of_review_workspace():
    job = make_image_job()
    pending = "\u672a\u77e5\u5f85\u786e\u8ba4"
    for frame in job["frames"]:
        frame["analysis"] = {
            "what": pending,
            "userAction": pending,
            "systemResponse": pending,
            "afterState": pending,
        }

    model = ensure_review_model(job)

    assert model["quality"]["qualified"] is False
    assert "NO_QUALIFIED_STAGE" in model["quality"]["blockers"]


def test_seed_reuses_detected_boxes_as_editable_regions():
    job = make_image_job()
    job["frames"][0]["structure"] = {
        "width": 1000,
        "height": 2000,
        "elements": [{"id": "E001", "class": "button", "bbox": [100, 300, 400, 500]}],
    }

    model = ensure_review_model(job)

    region = model["regions"][0]
    assert region["bounds"] == {"x": 0.1, "y": 0.15, "width": 0.3, "height": 0.1}
    assert region["sourceType"] == "model"


def test_seeded_meaningful_regions_create_editable_components_and_all_state_slots():
    job = make_image_job()
    job["frames"][0]["structure"] = {"width": 100, "height": 100, "elements": [{"id": "E001", "class": "button", "bbox": [10, 10, 40, 40]}]}
    model = ensure_review_model(job)
    model["ruleDomains"] = empty_rule_domains()

    component = model["components"][0]
    assert component["id"] == "CMP-0001"
    assert component["regionId"] == model["regions"][0]["id"]
    assert component["bounds"] == model["regions"][0]["bounds"]
    assert model["componentStates"][0]["states"] == {key: "unknown" for key in COMPONENT_STATE_KEYS}

    changed = apply_operations(model, [{"type": "set_component_state", "componentId": component["id"], "states": {"selected": "shown"}}], model["revision"])
    assert changed["componentStates"][0]["states"]["selected"] == "shown"
    assert set(changed["componentStates"][0]["states"]) == set(COMPONENT_STATE_KEYS)


def test_seed_limits_generic_detector_boxes_to_salient_component_candidates():
    job = make_image_job()
    job["frames"] = job["frames"][:1]
    job["scenes"] = job["scenes"][:1]
    job["scenes"][0]["frameIds"] = [job["frames"][0]["id"]]
    job["frames"][0]["structure"] = {
        "width": 100, "height": 100,
        "elements": [
            *({"class": "component", "bbox": [index, index, index + 10, index + 10]} for index in range(20)),
            {"class": "component", "bbox": [0, 0, 1, 1]},
        ],
    }

    model = ensure_review_model(job)

    assert len(model["regions"]) == 12
    assert len(model["components"]) == 12


def test_seeded_region_numbers_are_canonical_per_stage_across_frames():
    job = make_image_job()
    job["frames"][0]["structure"] = {"width": 100, "height": 100, "elements": [{"class": "first", "bbox": [0, 0, 10, 10]}]}
    job["frames"][1]["structure"] = {"width": 100, "height": 100, "elements": [{"class": "second", "bbox": [0, 0, 10, 10]}]}
    job["frames"][1]["sceneId"] = job["frames"][0]["sceneId"]

    regions = ensure_review_model(job)["regions"]
    assert [(region["frameId"], region["displayOrder"], region["displayNumber"]) for region in regions] == [("F0001", 1, 1), ("F0002", 2, 2)]


def test_seed_clamps_valid_boxes_and_discards_malformed_boxes():
    job = make_image_job()
    job["frames"][0]["structure"] = {
        "width": 100,
        "height": 100,
        "elements": [
            {"class": "panel", "bbox": [-20, -10, 120, 140]},
            {"class": "inverted", "bbox": [80, 10, 20, 30]},
            {"class": "flat", "bbox": [10, 10, 10, 30]},
            {"class": "infinite", "bbox": [0, 0, float("inf"), 20]},
            {"class": "invalid", "bbox": [0, 0, "right", 20]},
        ],
    }

    model = ensure_review_model(job)

    assert [region["name"] for region in model["regions"]] == ["panel"]
    bounds = model["regions"][0]["bounds"]
    assert bounds == {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
    assert all(0 <= value <= 1 for value in bounds.values())
    assert bounds["x"] + bounds["width"] <= 1
    assert bounds["y"] + bounds["height"] <= 1


def test_seed_discards_regions_when_source_dimensions_are_invalid():
    job = make_image_job()
    job["frames"][0]["structure"] = {
        "width": 0,
        "height": float("nan"),
        "elements": [{"class": "button", "bbox": [10, 10, 30, 30]}],
    }

    assert ensure_review_model(job)["regions"] == []
def test_unknown_screenshot_action_becomes_a_planner_decision_card_for_every_project():
    for project_name in ("一路狂飙", "杂货铺游戏厅", "角色创建", "全新项目"):
        job = make_image_job()
        job["metadata"]["projectName"] = project_name
        job["frames"][0]["analysis"]["userAction"] = "未捕捉点击或滑动操作（当前帧为静态展示）"
        model = build_review_model(job)
        transition = model["transitions"][0]
        card = next(item for item in model["interactionDecisionCards"] if item["transitionId"] == transition["id"])
        assert transition["triggerType"] == "unknown"
        assert transition["triggerLabel"] == "待确认"
        assert card["status"] == "pending"
        assert [item["id"] for item in card["options"]] == ["tap", "swipe", "drag", "system_event"]
        assert project_name not in card["question"]


def test_resolved_interaction_operation_survives_model_backfill_from_original_frame_analysis():
    job = make_image_job()
    model = build_review_model(job)
    transition = model["transitions"][0]
    source = model["sources"][transition["sourceFrameId"]]
    transition.update({"triggerType": "tap", "triggerLabel": "点击经营入口"})
    source["pageInfo"]["action"] = "点击经营入口"
    source["humanEditedFields"] = ["pageInfo.action"]
    job["reviewModel"] = model

    reloaded = ensure_review_model(job)

    assert reloaded["sources"][transition["sourceFrameId"]]["pageInfo"]["action"] == "点击经营入口"
