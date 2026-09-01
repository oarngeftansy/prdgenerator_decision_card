import json
from copy import deepcopy

from backend.planning_model import build_planning_model, build_standard_prompt, compile_confirmed_planning_model, validate_planning_model
from tests.review_fixtures import make_confirmed_job, make_image_job


def _job(mode: str) -> dict:
    return {
        "id": "job-1",
        "metadata": {"mode": mode, "projectName": "示例项目", "scope": "复刻样例颗粒度"},
        "video": {"filename": "demo.mp4", "duration": 42.5, "width": 1920, "height": 1080},
        "frames": [
            {
                "id": "F0001",
                "sceneId": 0,
                "timestamp": 1.25,
                "structure": {
                    "engine": "ScreenCoder-UIED",
                    "elements": [
                        {"trackId": "T0001", "class": "button", "bbox": [10, 20, 110, 70]},
                    ],
                },
                "analysis": {
                    "what": "开始界面",
                    "eventType": "tap",
                    "beforeState": {"screen": "idle"},
                    "userAction": "点击开始按钮",
                    "systemResponse": "进入关卡",
                    "afterState": {"screen": "level"},
                    "evidenceLevel": "明确展示",
                    "confidence": "高",
                    "unknowns": [],
                },
            }
        ],
        "scenes": [
            {
                "id": 0,
                "start": 0.0,
                "end": 4.0,
                "frameIds": ["F0001"],
                "analysis": {
                    "title": "开始",
                    "sceneType": "关卡入口" if mode == "gameplay" else "首页",
                    "objective": "进入下一状态",
                    "entryCondition": "视频开始",
                    "exitCondition": "点击开始",
                    "visibleRules": ["点击后进入下一状态"],
                    "stateChanges": ["idle -> level"],
                    "evidenceLevel": "明确展示",
                    "confidence": "高",
                },
            }
        ],
        "componentTracks": [
            {"id": "T0001", "class": "button", "observations": [{"frameId": "F0001", "timestamp": 1.25}]},
        ],
        "qualityReport": {"score": 88, "checks": ["evidence-confidence"]},
    }


def test_builds_stable_evidence_backed_gameplay_model():
    first = build_planning_model(_job("gameplay"))
    second = build_planning_model(_job("gameplay"))

    assert first == second
    assert first["standard"] == "GVE16"
    assert first["mode"] == "gameplay"
    assert first["scenes"][0]["id"] == "SCN-001"
    assert first["events"][0]["id"] == "EVT-001"
    assert first["events"][0]["beforeState"] == {"screen": "idle"}
    assert first["events"][0]["evidence"][0]["locator"] == "00:01.250"
    assert first["gameplay"]["coreLoop"]
    assert first["interaction"] is None
    assert validate_planning_model(first) == []
    json.dumps(first, ensure_ascii=False)


def test_builds_interaction_handoff_without_claiming_figma_execution():
    model = build_planning_model(_job("interaction"))

    assert model["interaction"]["taskFlow"][0]["from"] == {"screen": "idle"}
    assert model["gameplay"] is None
    assert model["components"][0]["id"] == "CMP-001"
    assert model["designHandoff"]["status"] == "schema-ready"
    assert model["designHandoff"]["generatedArtifacts"] == []
    assert model["designHandoff"]["flowEdges"][0]["eventId"] == "EVT-001"
    assert validate_planning_model(model) == []


def test_planning_model_drops_single_observation_generic_detector_noise():
    job = _job("interaction")
    job["componentTracks"] = [
        {"id": f"T{index:04d}", "class": "component", "observations": [{"frameId": "F0001"}]}
        for index in range(1, 1301)
    ] + [{"id": "T-button", "class": "button", "observations": [{"frameId": "F0001"}]}]

    model = build_planning_model(job)

    assert [component["sourceTrackId"] for component in model["components"]] == ["T-button"]
    assert validate_planning_model(model) == []


def test_interaction_events_use_detail_frames_when_available():
    job = _job("interaction")
    first = job["frames"][0]
    first["analysis"]["isDetailFrame"] = True
    job["frames"].append({
        **first,
        "id": "F0002",
        "timestamp": 2.0,
        "analysis": {**first["analysis"], "isDetailFrame": False, "userAction": "非代表帧动作"},
    })
    job["scenes"][0]["frameIds"].append("F0002")

    model = build_planning_model(job)

    assert [event["evidence"][0]["sourceId"] for event in model["events"]] == ["F0001"]
    assert len(model["interaction"]["taskFlow"]) == 1


def test_legacy_image_sequence_fallback_emits_matching_evidence_source_type():
    model = build_planning_model(make_image_job())

    assert model["project"]["sourceType"] == "image_sequence"
    assert model["events"][0]["evidence"][0]["sourceType"] == "image_sequence"
    assert model["events"][0]["evidence"][0]["locator"] == "1"
    assert validate_planning_model(model) == []


def test_validator_rejects_broken_evidence_reference():
    model = build_planning_model(_job("gameplay"))
    model["events"][0]["evidence"] = []

    assert validate_planning_model(model) == ["events[0].evidence must be a non-empty list"]


def test_gve16_prompt_is_always_enabled_and_example_is_additive():
    gameplay = build_standard_prompt("gameplay")
    interaction = build_standard_prompt("interaction", "# 已批准交互样例")

    assert "GVE16" in gameplay and "核心循环" in gameplay
    assert "GVE16" in interaction and "组件层级" in interaction
    assert "# 已批准交互样例" in interaction


def test_confirmed_review_compilation_uses_only_confirmed_entities_and_stable_gve16_ids():
    job = make_confirmed_job()
    job["reviewModel"]["transitions"][1]["included"] = False
    job["reviewModel"]["regions"][0]["confirmation"] = {"confirmed": False}

    model = compile_confirmed_planning_model(job)

    assert [scene["id"] for scene in model["scenes"]] == ["SCN-001", "SCN-002"]
    assert [event["id"] for event in model["events"]] == ["EVT-001"]
    assert [flow["id"] for flow in model["interaction"]["taskFlow"]] == ["FLOW-001"]
    assert [component["id"] for component in model["components"]] == ["CMP-001", "CMP-002"]
    assert all(item["sourceType"] == "image_sequence" for item in model["evidence"])
    assert validate_planning_model(model) == []


def test_confirmed_review_compilation_keeps_internal_roles_and_model_annotations_out_of_preview_copy():
    job = make_confirmed_job()
    stage = job["reviewModel"]["stages"][0]
    stage["name"] = "首领战"
    stage["smallLoop"]["feedback"] = "Boss受到攻击（inferred from damage numbers）"

    model = compile_confirmed_planning_model(job)
    loop = model["loopHierarchy"]["largeLoops"][0]
    steps = loop["stages"][0]["smallLoops"][0]["steps"]

    assert loop["title"] == "玩家操作流程"
    assert [step["title"] for step in steps] == ["操作前"]
    assert all(step["systemResponse"] == "首领受到攻击（根据伤害数字推测）" for step in steps)
    assert not any(word in str([step["title"] for step in steps]).lower() for word in ("entry", "change", "result"))


def test_unconfirmed_included_transitions_are_excluded_from_confirmed_compilation():
    job = make_confirmed_job()
    for transition in job["reviewModel"]["transitions"]:
        transition["confirmation"] = {"confirmed": False}

    model = compile_confirmed_planning_model(job)

    assert model["events"] == []


def test_gate_and_compiler_agree_that_unconfirmed_included_transition_is_not_exportable():
    from backend.review_model import review_gate

    job = make_confirmed_job()
    transition = job["reviewModel"]["transitions"][0]
    transition["confirmation"] = {"confirmed": False, "revision": None}

    assert transition["id"] in review_gate(job["reviewModel"])["blockers"]
    planning = compile_confirmed_planning_model(job)
    assert transition["id"] not in {event["sourceTransitionId"] for event in planning["events"]}


def test_validator_rejects_invalid_and_duplicate_entity_ids():
    model = compile_confirmed_planning_model(make_confirmed_job())
    model["scenes"][1]["id"] = model["scenes"][0]["id"]
    model["events"][0]["id"] = "EVENT-1"
    model["components"].append(deepcopy(model["components"][0]))
    model["interaction"]["taskFlow"].append(deepcopy(model["interaction"]["taskFlow"][0]))

    errors = validate_planning_model(model)

    assert "scenes[1].id must be a unique SCN-### id" in errors
    assert "events[0].id must be a unique EVT-### id" in errors
    assert "components[3].id must be a unique CMP-### id" in errors
    assert "interaction.taskFlow[2].id must be a unique FLOW-### id" in errors


def test_validator_rejects_broken_flow_component_and_representative_references():
    model = compile_confirmed_planning_model(make_confirmed_job())
    flow = model["interaction"]["taskFlow"][0]
    flow.update(eventId="EVT-999", sourceStageId="SCN-999", resultType="state_change", targetStageId="SCN-999", resultState="changed")
    model["interaction"]["componentStates"] = [{"componentId": "CMP-999", "states": {"default": "visible"}}]
    model["scenes"][0]["evidence"][0]["sceneId"] = "SCN-999"
    model["loopHierarchy"]["largeLoops"][0]["stages"][0]["smallLoops"][0]["steps"][0]["evidence"][0]["sceneId"] = "SCN-999"

    errors = validate_planning_model(model)

    assert "interaction.taskFlow[0].eventId must reference an event" in errors
    assert "interaction.taskFlow[0].sourceStageId must reference a scene" in errors
    assert "interaction.taskFlow[0].targetStageId must reference a scene" in errors
    assert "interaction.componentStates[0].componentId must reference a component" in errors
    assert "scenes[0].evidence[0].sceneId must equal SCN-001" in errors
    assert "loopHierarchy.largeLoops[0].stages[0].smallLoops[0].steps[0].evidence[0].sceneId must equal SCN-001" in errors


def test_validator_requires_complete_event_evidence_and_json_serializable_values():
    model = compile_confirmed_planning_model(make_confirmed_job())
    evidence = model["events"][0]["evidence"][0]
    evidence.pop("locator")
    evidence["sourceType"] = "web"
    model["quality"] = {"bad": {"not-json"}}

    errors = validate_planning_model(model)

    assert "events[0].evidence[0].locator is required" in errors
    assert "events[0].evidence[0].sourceType must be video or image_sequence" in errors
    assert "model must be JSON serializable" in errors


def test_validator_rejects_structured_evidence_scalars_without_crashing():
    model = compile_confirmed_planning_model(make_confirmed_job())
    model["events"][0]["evidence"][0]["confidence"] = {"level": "high"}
    model["events"][0]["evidence"][0]["sourceType"] = "video"

    errors = validate_planning_model(model)

    assert "events[0].evidence[0].confidence must be a non-empty scalar" in errors
    assert "events[0].evidence[0].sourceType must match project sourceType" in errors


def test_validator_reports_malformed_required_collections_without_crashing():
    model = compile_confirmed_planning_model(make_confirmed_job())
    model["scenes"] = 42
    model["interaction"] = ["bad"]

    errors = validate_planning_model(model)

    assert "scenes must be a list" in errors
    assert "interaction.taskFlow must be a list" in errors


def test_compiler_emits_explicit_transition_result_semantics():
    model = compile_confirmed_planning_model(make_confirmed_job())
    first, last = model["events"]
    first_flow, last_flow = model["interaction"]["taskFlow"]

    assert (first["resultType"], first["targetStageId"]) == ("navigate", "SCN-002")
    assert (last["resultType"], last["targetStageId"]) == ("terminal", None)
    assert (first_flow["resultType"], first_flow["targetStageId"]) == ("navigate", "SCN-002")
    assert (last_flow["resultType"], last_flow["targetStageId"]) == ("terminal", None)


def test_validator_enforces_transition_targets_and_internal_result_state():
    base = compile_confirmed_planning_model(make_confirmed_job())
    missing_target = deepcopy(base)
    missing_target["events"][0].update(resultType="navigate", targetStageId=None)
    terminal_target = deepcopy(base)
    terminal_target["events"][-1].update(resultType="terminal", targetStageId="SCN-001")
    missing_state = deepcopy(base)
    missing_state["events"][0].update(resultType="state_change", targetStageId=None, resultState=None)

    assert "events[0].targetStageId is required for navigate" in validate_planning_model(missing_target)
    assert "events[1].targetStageId must be null for terminal" in validate_planning_model(terminal_target)
    assert "events[0].resultState is required for state_change" in validate_planning_model(missing_state)
