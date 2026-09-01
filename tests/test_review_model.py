import re

import pytest

from backend.review_model import _planner_stage_name, build_review_model, compact_generated_stages, empty_rule_domains, review_gate, sanitize_review_planner_copy, validate_representative_frames, validate_review_model
from tests.review_fixtures import make_confirmed_job, make_image_job


def test_planner_copy_replaces_punctuation_only_analysis_with_a_chinese_pending_label():
    model = {
        "stages": [{"name": "', .", "objective": "????", "smallLoop": {"trigger": "'' : ."}}],
        "transitions": [{"triggerLabel": "', .", "confidence": "Low"}],
    }

    cleaned = sanitize_review_planner_copy(model)

    assert cleaned["stages"][0]["name"] == "待确认"
    assert cleaned["stages"][0]["objective"] == "待确认"
    assert cleaned["stages"][0]["smallLoop"]["trigger"] == "待确认"
    assert cleaned["transitions"][0]["triggerLabel"] == "待确认"


def _region(stage_id="STG-001", frame_id="F0001", **overrides):
    return {
        "id": "REG-0001",
        "stageId": stage_id,
        "frameId": frame_id,
        "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
        **overrides,
    }


def _component(**overrides):
    return {
        "id": "CMP-0001",
        "stageId": "STG-001",
        "frameId": "F0001",
        "regionId": "REG-0001",
        "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
        **overrides,
    }


def test_stage_name_fallback_is_a_short_player_action_instead_of_a_numbered_step():
    name = _planner_stage_name(3, {
        "title": "场景 3", "objective": "需要配置视觉模型后识别",
        "userAction": "待确认", "systemResponse": "待确认", "afterState": "待确认",
    })

    assert name == "查看当前状态并继续操作"
    assert "第 3 步" not in name


def test_stage_name_summarizes_long_battle_copy():
    name = _planner_stage_name(7, {
        "title": "Boss战进行中：玩家操控角色（下方小坦克/机器人）攻击Boss僵尸博士，Boss正在释放闪电攻击。",
        "userAction": "玩家操控角色移动并攻击Boss",
        "systemResponse": "Boss释放闪电攻击",
    })

    assert len(name) <= 18
    assert name == "操控角色攻击首领"


def test_compaction_prefers_a_specific_page_name_over_generic_fallback_copy():
    stages = [
        {"id": "STG-001", "name": "查看当前状态并继续操作", "representativeFrames": [{"frameId": "F0001", "role": "entry"}]},
        {"id": "STG-002", "name": "选择武器强化", "representativeFrames": [{"frameId": "F0002", "role": "entry"}]},
    ]

    compacted = compact_generated_stages(stages, minimum=1, maximum=1)

    assert compacted[0]["name"] == "选择武器强化"


def test_compaction_merges_adjacent_duplicate_generic_stages_even_below_maximum():
    stages = [
        {"id": "STG-001", "name": "查看当前状态并继续操作", "representativeFrames": [{"frameId": "F0001", "role": "entry"}]},
        {"id": "STG-002", "name": "查看当前状态并继续操作", "representativeFrames": [{"frameId": "F0002", "role": "entry"}]},
        {"id": "STG-003", "name": "关卡结算页面", "representativeFrames": [{"frameId": "F0003", "role": "entry"}]},
    ]

    compacted = compact_generated_stages(stages, maximum=7)

    assert [item["name"] for item in compacted] == ["查看当前状态并继续操作", "关卡结算页面"]


def test_generated_planner_fields_flatten_model_objects_and_remove_english_copy():
    job = make_image_job()
    frame = job["frames"][0]
    frame["analysis"].update({
        "what": "Boss Warning UI",
        "beforeState": {"description": "Normal Battle State"},
        "userAction": {"type": "Passive / None", "description": "系统自动触发事件"},
        "systemResponse": {"action": "Trigger Boss Warning Overlay", "details": ["Red Vignette", "显示首领来袭提示"]},
        "afterState": {"description": "进入Boss战预警状态", "status": "Warning Active"},
        "evidenceLevel": "High",
        "confidence": "High",
    })
    job["scenes"][0]["analysis"] = frame["analysis"]

    model = build_review_model(job)
    visible = " ".join(str(value) for value in (
        model["stages"][0]["name"], model["stages"][0]["objective"],
        model["transitions"][0]["triggerLabel"], model["transitions"][0]["condition"],
        model["transitions"][0]["response"], model["transitions"][0]["resultState"],
        model["transitions"][0]["sourceLevel"], model["transitions"][0]["confidence"],
    ))

    assert "{" not in str(model["transitions"][0]["response"])
    assert not re.search(r"\b(?:Boss|Warning|UI|Passive|None|Trigger|Overlay|High)\b", visible, re.I)


def _component_state(**overrides):
    return {
        "id": "CST-0001",
        "componentId": "CMP-0001",
        "states": {
            "default": "visible",
            "pressed": "unknown",
            "selected": "unknown",
            "disabled": "unknown",
            "loading": "unknown",
            "success": "unknown",
            "error": "unknown",
            "exhausted": "unknown",
            "condition_unmet": "unknown",
        },
        **overrides,
    }


def test_review_model_uses_stable_entities_and_screenshot_sources():
    model = build_review_model(make_image_job())

    assert model["schemaVersion"] == "2.0"
    assert [stage["id"] for stage in model["stages"]] == ["STG-001", "STG-002"]
    assert model["stages"][0]["representativeFrames"][0] == {
        "frameId": "F0001",
        "role": "entry",
    }
    assert model["sources"]["F0001"]["sourceType"] == "image_sequence"
    assert validate_review_model(model) == []


def test_every_uploaded_frame_has_an_explicit_page_role_and_stage_owner():
    job = make_image_job()
    model = build_review_model(job)

    assert set(model["sources"]) == {frame["id"] for frame in job["frames"]}
    assert all(source["materialRole"] in {"independent_page", "supplemental", "duplicate"} for source in model["sources"].values())
    assert all(source["stageId"] for source in model["sources"].values())
    covered = [frame_id for stage in model["stages"] for frame_id in stage["sourceFrameIds"]]
    assert sorted(covered) == sorted(model["sources"])


def test_exact_duplicate_frames_are_kept_and_marked_instead_of_silently_omitted():
    job = make_image_job()
    job["frames"][1]["imageUrl"] = job["frames"][0]["imageUrl"]

    model = build_review_model(job)

    assert model["sources"]["F0001"]["materialRole"] == "independent_page"
    assert model["sources"]["F0002"]["materialRole"] == "duplicate"
    assert model["sources"]["F0002"]["duplicateOf"] == "F0001"


def test_generated_duplicate_transitions_are_excluded_and_alternatives_share_one_choice_group():
    model = build_review_model(make_image_job())
    first = model["transitions"][0]
    duplicate = {**first, "id": "TRN-999", "included": True}
    alternative = {**first, "id": "TRN-998", "targetStageId": model["stages"][0]["id"], "included": False}
    model["transitions"].extend([duplicate, alternative])
    from backend.review_model import _backfill_review_metadata
    _backfill_review_metadata(model)

    assert duplicate["included"] is False
    assert duplicate["duplicateOf"] == first["id"]
    assert first["choiceMode"] == alternative["choiceMode"] == "exclusive"
    assert first["choiceGroupId"] == alternative["choiceGroupId"]


def test_secondary_page_information_keeps_level_weapon_resource_and_status_regions():
    job = make_image_job()
    job["frames"][0]["structure"] = {"width": 500, "height": 1000, "elements": [
        {"class": "level", "text": "LV.1", "bbox": [10, 10, 60, 35]},
        {"class": "weapon-slot", "text": "武器槽 1", "bbox": [430, 350, 490, 410]},
        {"class": "resource", "text": "金币 300", "bbox": [400, 10, 490, 35]},
        {"class": "status", "text": "生命 4472", "bbox": [170, 930, 330, 970]},
    ]}

    model = build_review_model(job)

    details = " ".join(model["sources"]["F0001"]["secondaryInformation"])
    assert all(value in details for value in ("LV.1", "武器槽 1", "金币 300", "生命 4472"))


def test_new_interaction_model_contains_only_active_reference_boards():
    model = build_review_model(make_image_job())

    assert model["schemaVersion"] == "2.0"
    assert "ruleDomains" not in model
    assert model["referenceBoards"] == {
        "planning": {"source": "confirmed_review_model", "status": "generated"},
        "competitor": {"assets": [], "status": "pending"},
    }


def test_active_gate_ignores_legacy_rule_and_ux_damage():
    model = make_confirmed_job()["reviewModel"]
    model["ruleDomains"] = ["damaged legacy value"]
    model["referenceBoards"]["ux"] = {"assets": [None], "status": "ready"}

    gate = review_gate(model)

    assert "RULE_DOMAINS_NOT_CONFIRMED" not in gate["blockers"]
    assert "UX_BOARD_PENDING" not in gate["warnings"]
    assert gate["exportReady"] is True


def test_empty_competitor_is_a_non_blocking_pending_summary():
    model = make_confirmed_job()["reviewModel"]
    model["referenceBoards"]["competitor"] = {"assets": [], "status": "pending"}

    gate = review_gate(model)

    assert gate["exportReady"] is True
    assert gate["warnings"] == []


def test_rule_domain_reference_validation_rejects_unknown_component():
    model = make_confirmed_job()["reviewModel"]
    model["ruleDomains"] = empty_rule_domains()
    model["ruleDomains"]["guidance"] = [{
        "id": "GDE-001",
        "title": "首次引导",
        "stageId": model["stages"][0]["id"],
        "frameId": None,
        "scopeCount": "首次",
        "prerequisite": "进入页面",
        "steps": [{"id": "GDS-001", "action": "点击", "componentId": "CMP-MISSING", "prompt": "继续"}],
        "destination": "下一页",
    }]

    assert any("GDE-001" in error and "CMP-MISSING" in error for error in validate_review_model(model))


def test_rule_domain_validation_rejects_non_string_references_without_throwing():
    model = make_confirmed_job()["reviewModel"]
    model["ruleDomains"] = empty_rule_domains()
    model["ruleDomains"]["guidance"] = [{
        "id": "GDE-001",
        "title": "first guide",
        "stageId": [],
        "frameId": {},
        "scopeCount": "first",
        "prerequisite": "open page",
        "steps": [{"id": "GDS-001", "componentId": []}],
        "destination": "next page",
    }]

    errors = validate_review_model(model)

    assert "GDE-001: expected string stageId" in errors
    assert "GDE-001: expected string frameId" in errors
    assert "GDE-001: expected string componentId" in errors


def test_rule_domain_validation_rejects_unknown_narrative_frame_and_red_dot_path_component():
    model = make_confirmed_job()["reviewModel"]
    model["ruleDomains"] = empty_rule_domains()
    model["ruleDomains"]["narrative"] = [{
        "id": "NAR-001",
        "title": "开场",
        "stageId": model["stages"][0]["id"],
        "frameId": "F-MISSING",
        "triggerScene": "进入",
        "triggerNode": "页面",
        "presentation": "动画",
        "continuation": "继续",
    }]
    model["ruleDomains"]["redDots"] = [{
        "id": "RDT-001",
        "title": "功能红点",
        "stageId": model["stages"][0]["id"],
        "showCondition": "有奖励",
        "clearCondition": "已查看",
        "path": [{"id": "RDP-001", "componentId": "CMP-MISSING"}],
    }]

    errors = validate_review_model(model)
    assert any("NAR-001" in error and "F-MISSING" in error for error in errors)
    assert any("RDT-001" in error and "CMP-MISSING" in error for error in errors)


def test_reference_board_assets_require_unique_ids_paths_and_orders():
    model = make_confirmed_job()["reviewModel"]
    model["referenceBoards"]["ux"] = {"assets": [], "status": "pending"}
    model["referenceBoards"]["ux"]["assets"] = [
        {"id": "UX-001", "relativePath": "reference_boards/ux/a.png", "order": 1},
        {"id": "UX-001", "relativePath": "reference_boards/ux/a.png", "order": 1},
    ]

    errors = validate_review_model(model)
    assert any("referenceBoards.ux.assets" in error and "duplicate id" in error for error in errors)
    assert any("referenceBoards.ux.assets" in error and "duplicate relativePath" in error for error in errors)
    assert any("referenceBoards.ux.assets" in error and "duplicate order" in error for error in errors)


def test_empty_optional_reference_boards_warn_without_blocking():
    gate = review_gate(make_confirmed_job()["reviewModel"])

    assert gate["exportReady"] is True
    assert "COMPETITOR_BOARD_PENDING" not in gate["warnings"]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("schemaVersion", "1.0", "schemaVersion: expected '2.0'"),
        ("standard", "OTHER", "standard: expected 'GVE16'"),
        ("revision", 0, "revision: expected a positive integer"),
        ("jobId", "", "jobId: expected a non-empty string"),
    ],
)
def test_validator_rejects_invalid_canonical_model_identity(field, value, error):
    model = build_review_model(make_image_job())
    model[field] = value

    assert error in validate_review_model(model)


def test_validator_rejects_duplicate_entity_ids_with_collection_paths():
    model = build_review_model(make_image_job())
    model["regions"] = [_region()]
    model["stages"][0]["regionIds"] = ["REG-0001"]
    model["components"] = [_component(id="REG-0001")]

    assert "components[0].id: duplicates regions[0].id 'REG-0001'" in validate_review_model(model)


@pytest.mark.parametrize(
    ("region", "error"),
    [
        (_region(bounds={"x": 0.1, "y": 0.1, "width": float("inf"), "height": 0.2}), "regions[0].bounds.width: expected a finite normalized value"),
        (_region(bounds={"x": 0.9, "y": 0.1, "width": 0.2, "height": 0.2}), "regions[0].bounds: must stay within normalized bounds"),
        (_region(stage_id="STG-999"), "regions[0].stageId: unknown stage 'STG-999'"),
        (_region(frame_id="F0002"), "regions[0].frameId: does not belong to stage 'STG-001'"),
    ],
)
def test_validator_rejects_malformed_region_ownership_and_bounds(region, error):
    model = build_review_model(make_image_job())
    model["regions"] = [region]
    model["stages"][0]["regionIds"] = [region["id"]]

    assert error in validate_review_model(model)


def test_validator_rejects_component_and_state_ownership_gaps():
    model = build_review_model(make_image_job())
    model["regions"] = [_region()]
    model["stages"][0]["regionIds"] = ["REG-0001"]
    model["components"] = [_component()]
    model["componentStates"] = [_component_state(states={"default": "visible"})]

    errors = validate_review_model(model)

    assert "componentStates[0].states: missing required slots pressed, selected, disabled, loading, success, error, exhausted, condition_unmet" in errors


def test_validator_rejects_component_region_and_frame_mismatches():
    model = build_review_model(make_image_job())
    model["regions"] = [_region()]
    model["stages"][0]["regionIds"] = ["REG-0001"]
    model["components"] = [_component(stageId="STG-002", frameId="F0002")]
    model["componentStates"] = [_component_state()]

    errors = validate_review_model(model)

    assert "components[0].stageId: does not match region 'REG-0001'" in errors
    assert "components[0].frameId: does not match region 'REG-0001'" in errors


def test_validator_requires_component_states_for_every_component_and_valid_references():
    model = build_review_model(make_image_job())
    model["regions"] = [_region()]
    model["stages"][0]["regionIds"] = ["REG-0001"]
    model["components"] = [_component()]
    model["componentStates"] = [_component_state(componentId="CMP-999")]

    errors = validate_review_model(model)

    assert "componentStates[0].componentId: unknown component 'CMP-999'" in errors
    assert "components[0].componentState: missing state slots" in errors


def test_validator_rejects_transition_branch_and_anchor_reference_mismatches():
    model = build_review_model(make_image_job())
    model["regions"] = [_region()]
    model["stages"][0]["regionIds"] = ["REG-0001"]
    model["transitions"][0].update(
        {
            "regionId": "REG-0001",
            "sourceFrameId": "F0002",
            "trueBranchTargetId": "STG-999",
            "anchor": {"x": float("nan"), "y": 0.2},
        }
    )

    errors = validate_review_model(model)

    assert "transitions[0].sourceFrameId: does not belong to stage 'STG-001'" in errors
    assert "transitions[0].trueBranchTargetId: unknown stage 'STG-999'" in errors
    assert "transitions[0].regionId: frame does not match sourceFrameId" in errors
    assert "transitions[0].anchor.x: expected a finite normalized value" in errors


def test_validator_accepts_a_normalized_anchor_bound_to_its_source_region():
    model = build_review_model(make_image_job())
    model["regions"] = [_region()]
    model["stages"][0]["regionIds"] = ["REG-0001"]
    model["transitions"][0].update({"regionId": "REG-0001", "anchor": {"x": 0.2, "y": 0.2}})

    assert validate_review_model(model) == []


def test_review_model_carries_frame_structure_dimensions_to_sources():
    job = make_image_job()
    job["frames"][0]["structure"] = {"width": 528, "height": 986}

    model = build_review_model(job)

    assert model["sources"]["F0001"]["width"] == 528
    assert model["sources"]["F0001"]["height"] == 986


def test_representative_frames_have_one_canonical_validator_and_strict_roles():
    sources = {"F1": {}, "F2": {}, "F3": {}}
    assert validate_representative_frames([{"frameId": "F1", "role": "entry"}], sources) is None
    assert validate_representative_frames([{"frameId": "F1", "role": "entry"}, {"frameId": "F2", "role": "result"}], sources) is None
    assert validate_representative_frames([{"frameId": "F1", "role": "entry"}, {"frameId": "F2", "role": "change"}, {"frameId": "F3", "role": "result"}], sources) is None
    for invalid in [
        [{"frameId": "F1", "role": "entry"}, {"frameId": "F1", "role": "result"}],
        [{"frameId": "F1", "role": "entry"}, {"frameId": "F2", "role": "entry"}],
        [{"frameId": "F1", "role": "entry"}, {"frameId": "F2", "role": "change"}],
        [{"frameId": "F9", "role": "entry"}],
    ]:
        assert validate_representative_frames(invalid, sources)


def test_seed_uses_entry_change_result_for_three_representative_frames():
    job = make_image_job()
    job["frames"].append({"id": "F0003", "sequenceIndex": 3, "sceneId": 0, "analysis": {}})
    job["scenes"][0]["frameIds"] = ["F0001", "F0002", "F0003"]

    assert build_review_model(job)["stages"][0]["representativeFrames"] == [
        {"frameId": "F0001", "role": "entry"}, {"frameId": "F0002", "role": "change"}, {"frameId": "F0003", "role": "result"},
    ]


def test_core_unknown_blocks_but_non_core_unknown_does_not():
    model = build_review_model(make_image_job())
    model["reviewState"]["flowConfirmed"] = True
    for stage in model["stages"]:
        stage["confirmation"]["confirmed"] = True
        stage["smallLoop"].update(
            {
                "display": stage["name"],
                "trigger": "已确认触发",
                "feedback": "已确认反馈",
                "result": stage["exitCondition"],
            }
        )
    for transition in model["transitions"]:
        transition["triggerType"] = "tap" if transition["targetStageId"] else "system_event"
        transition["resultType"] = "navigate" if transition["targetStageId"] else "terminal"
        transition["confirmation"] = {"confirmed": True, "revision": model["revision"]}
    model["crossStateConstraints"].append(
        {
            "id": "CST-001",
            "text": "弱网反馈待确认",
            "severity": "non_core",
            "status": "unknown",
        }
    )

    gate = review_gate(model)
    assert gate["exportReady"] is True
    assert gate["warnings"] == ["CST-001"]

    model["transitions"][0]["targetStageId"] = None
    model["transitions"][0]["resultType"] = "unknown"
    gate = review_gate(model)
    assert gate["exportReady"] is False
    assert "TRN-001" in gate["blockers"]


@pytest.mark.parametrize(
    ("action", "trigger_type"),
    [
        ("系统自动开始", "system_event"),
        ("动画结束", "animation_end"),
        ("media end", "media_end"),
        ("等待 3 秒后", "timeout"),
        ("after 3 seconds", "timeout"),
        ("after 1 second", "timeout"),
        ("wait 1 second", "timeout"),
        ("条件满足", "condition_met"),
        ("condition met", "condition_met"),
        ("点击卡片", "tap"),
        ("无法判断", "unknown"),
    ],
)
def test_explicit_action_semantics_use_the_matching_trigger_type(action, trigger_type):
    job = make_image_job()
    job["frames"][1]["analysis"]["userAction"] = action
    model = build_review_model(job)

    assert model["transitions"][0]["triggerType"] == "tap"
    assert model["transitions"][1]["triggerType"] == trigger_type


def test_review_gate_blocks_structural_and_core_unknowns_but_warns_non_core_unknowns():
    model = build_review_model(make_image_job())
    model["reviewState"]["flowConfirmed"] = True
    for stage in model["stages"]:
        stage["confirmation"]["confirmed"] = True
    for transition in model["transitions"]:
        transition["triggerType"] = "tap" if transition["targetStageId"] else "system_event"
        transition["resultType"] = "navigate" if transition["targetStageId"] else "terminal"

    model["stages"][0]["representativeFrames"] = []
    model["stages"][1]["entryCondition"] = "待确认"
    model["stages"][1]["exitCondition"] = None
    model["transitions"][0]["targetStageId"] = "STG-999"
    model["transitions"][1]["condition"] = "unknown"
    model["crossStateConstraints"].extend(
        [
            {"id": "CST-CORE", "severity": "core", "status": "unknown"},
            {"id": "CST-NON-CORE", "severity": "non_core", "status": "unknown"},
        ]
    )

    gate = review_gate(model)

    assert gate["exportReady"] is False
    assert "STG-001" in gate["blockers"]
    assert "STG-002_PENDING_DETAILS" in gate["warnings"]
    assert "TRN-001: invalid targetStageId" in gate["blockers"]
    assert "TRN-002" in gate["blockers"]
    assert "CST-CORE" in gate["blockers"]
    assert gate["warnings"] == ["STG-002_PENDING_DETAILS", "CST-NON-CORE"]


def test_validation_and_gate_reject_invalid_stage_order_and_missing_navigation_target():
    invalid_order = build_review_model(make_image_job())
    invalid_order["stages"][0]["order"] = 0
    assert "STG-001: invalid order" in validate_review_model(invalid_order)

    duplicate_order = build_review_model(make_image_job())
    duplicate_order["stages"][1]["order"] = 1
    assert "STG-002: duplicate order" in validate_review_model(duplicate_order)
    assert review_gate(duplicate_order)["exportReady"] is False

    missing_target = build_review_model(make_image_job())
    missing_target["transitions"][0]["targetStageId"] = None
    assert "TRN-001: missing targetStageId" in validate_review_model(missing_target)
    assert review_gate(missing_target)["exportReady"] is False


def test_confirmed_small_loop_unknown_is_deferred_as_a_warning():
    model = make_confirmed_job()["reviewModel"]

    assert review_gate(model)["exportReady"] is True
    model["stages"][0]["smallLoop"]["feedback"] = "待确认"
    assert review_gate(model)["exportReady"] is True
    assert "STG-001_PENDING_DETAILS" in review_gate(model)["warnings"]

    model["stages"][0]["smallLoop"]["feedback"] = "已确认反馈"
    assert review_gate(model)["exportReady"] is True


def test_confirmed_transition_unknown_details_are_deferred_as_a_warning():
    model = make_confirmed_job()["reviewModel"]
    transition = model["transitions"][0]
    transition["triggerLabel"] = "待确认"
    transition["condition"] = "待确认"

    gate = review_gate(model)

    assert gate["exportReady"] is True
    assert transition["id"] not in gate["blockers"]
    assert f'{transition["id"]}_PENDING_DETAILS' in gate["warnings"]


def test_included_transition_requires_explicit_confirmation_even_for_legacy_flow_flag():
    model = make_confirmed_job()["reviewModel"]
    transition = model["transitions"][0]
    transition["confirmation"] = {"confirmed": False, "revision": None}
    model["reviewState"]["flowConfirmed"] = True

    gate = review_gate(model)

    assert gate["exportReady"] is False
    assert transition["id"] in gate["blockers"]
def test_generic_scene_title_is_replaced_with_planner_facing_task_name():
    job = make_image_job()
    job["scenes"][0]["analysis"].update(
        title="Scene 1",
        objective="Choose one weapon upgrade after leveling up",
        summary="A Select Weapon menu offers Poison Cannon, Rapid Fire, and Flame Expansion.",
    )

    assert build_review_model(job)["stages"][0]["name"] == "选择武器强化"


def test_gameplay_model_extracts_visible_weapon_parameters_without_inventing_damage_formula():
    from backend.gameplay_review_model import build_gameplay_review_model

    job = {"id": "job", "frames": [{"id": "F0001", "imageUrl": "/frame.jpg"}]}
    drafts = [
        {"scope": "现有武器数值强化", "sourceFrameIds": ["F0001"], "claims": [{"text": "火焰喷射范围扩大30%，雷暴枪伤害增加100%。", "sourceFrameIds": ["F0001"], "sourceType": "material"}]},
        {"scope": "伤害数字表现", "sourceFrameIds": ["F0001"], "claims": [{"text": "敌人受击出现85、91、172伤害数字。", "sourceFrameIds": ["F0001"], "sourceType": "material"}]},
    ]

    model = build_gameplay_review_model(job, drafts)
    weapon, damage = model["chapters"]

    parameter_by_name = {item["name"]: item for item in weapon["parameterSchema"]}
    assert {"火焰喷射范围", "雷暴枪伤害"}.issubset(parameter_by_name)
    assert [parameter_by_name[name]["defaultValue"] for name in ("火焰喷射范围", "雷暴枪伤害")] == ["30", "100"]
    assert not damage.get("formulae")
    assert not damage.get("parameterSchema")
    assert "85、91、172" in damage["workedExamples"][0]["steps"]


def test_gameplay_model_does_not_invent_formula_frameworks_from_chapter_names():
    from backend.gameplay_review_model import build_gameplay_review_model

    job = {"id": "job", "frames": [{"id": "F0001", "imageUrl": "/frame.jpg"}]}
    scopes = ["生命值状态管理", "现有武器数值强化", "强化效果刷新功能", "随机武器抽取", "战后资源结算"]
    drafts = [{
        "scope": scope,
        "sourceFrameIds": ["F0001"],
        "claims": [{"text": "素材展示了对应数值变化。", "sourceFrameIds": ["F0001"], "sourceType": "material"}],
    } for scope in scopes]

    model = build_gameplay_review_model(job, drafts)

    assert all(not chapter.get("formulae") for chapter in model["chapters"])
    assert all(not chapter.get("parameterSchema") for chapter in model["chapters"])


def test_damage_numbers_do_not_invent_an_unobserved_damage_formula():
    from backend.gameplay_review_model import build_gameplay_review_model

    job = {"id": "job", "frames": [{"id": "F0001", "imageUrl": "/frame.jpg"}]}
    model = build_gameplay_review_model(job, [{
        "scope": "伤害数字表现",
        "sourceFrameIds": ["F0001"],
        "claims": [{"text": "敌人受击出现85、91、172伤害数字。", "sourceFrameIds": ["F0001"], "sourceType": "material"}],
    }])

    chapter = model["chapters"][0]
    assert not chapter.get("formulae")
    assert not chapter.get("parameterSchema")
    assert "85、91、172" in chapter["workedExamples"][0]["steps"]


def test_enemy_spawn_word_refresh_does_not_become_candidate_reroll_formula():
    from backend.gameplay_review_model import build_gameplay_review_model

    job = {"id": "job", "frames": [{"id": "F0001", "imageUrl": "/frame.jpg"}]}
    model = build_gameplay_review_model(job, [{
        "scope": "常规怪物刷新",
        "sourceFrameIds": ["F0001"],
        "claims": [{"text": "怪物持续从屏幕上方出现。", "sourceFrameIds": ["F0001"], "sourceType": "material"}],
    }])

    assert not model["chapters"][0].get("formulae")
