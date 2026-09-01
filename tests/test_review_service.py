from copy import deepcopy

import pytest

from backend.review_model import build_review_model, empty_rule_domains, review_gate
from backend.review_service import ReviewConflict, apply_operations, confirm_flow, confirm_rule_domains, confirm_stage, confirm_ue_flow, record_reanalysis_suggestions, redo, undo


def test_last_stage_routes_directly_to_planning_preview(confirmed_model):
    model = confirm_flow(confirmed_model, confirmed_model["revision"])
    for stage in model["stages"]:
        model = confirm_stage(model, stage["id"], model["revision"])
    assert model["reviewState"]["status"] == "preview_pending"
    assert "ueFlowConfirmed" not in model["reviewState"]
from tests.review_fixtures import make_image_job


def review_model():
    model = build_review_model(make_image_job())
    model["ruleDomains"] = empty_rule_domains()
    return model


@pytest.fixture
def confirmed_model():
    model = review_model()
    model["ruleDomains"].update(
        reviewedDomains=["narrative", "guidance", "redDots"],
        confirmation={"confirmed": True, "revision": model["revision"]},
    )
    model["reviewState"]["previewRevision"] = model["revision"]
    return model


def _narrative_rule(model, title="开场叙事"):
    return {
        "title": title, "stageId": model["stages"][0]["id"], "frameId": None,
        "triggerScene": "进入关卡", "triggerNode": "开场", "presentation": "播放对白", "continuation": "开始操作",
        "sourceLevel": "observed", "confidence": "高", "unknownReason": "",
    }


def _guidance_rule(model):
    return {
        "title": "操作引导", "stageId": model["stages"][0]["id"], "frameId": None,
        "scopeCount": "一次", "prerequisite": "进入关卡",
        "steps": [{"id": "GDE-001-step-1", "text": "点击开始"}, {"id": "GDE-001-step-2", "text": "确认选择"}],
        "destination": "战斗",
    }


def _red_dot_rule(model):
    return {
        "title": "奖励红点", "stageId": model["stages"][0]["id"], "frameId": None,
        "showCondition": "有可领取奖励", "clearCondition": "领取后",
        "path": [{"id": "RDT-001-path-1", "text": "大厅"}, {"id": "RDT-001-path-2", "text": "奖励"}],
    }


def test_rule_operations_are_revisioned_and_invalidate_confirmation(confirmed_model):
    changed = apply_operations(confirmed_model, [{"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(confirmed_model)}], confirmed_model["revision"])

    assert changed["revision"] == confirmed_model["revision"] + 1
    assert changed["ruleDomains"]["narrative"][0]["id"] == "NAR-001"
    assert changed["ruleDomains"]["narrative"][0]["humanEditedFields"] == sorted(_narrative_rule(confirmed_model))
    assert changed["ruleDomains"]["confirmation"] == {"confirmed": False, "revision": None}
    assert changed["reviewState"]["previewRevision"] is None
    assert len(changed["editHistory"]["undo"]) == 1


def test_rule_delete_reorder_and_nested_reorder_preserve_rule_content(confirmed_model):
    model = apply_operations(confirmed_model, [
        {"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(confirmed_model, "first")},
        {"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(confirmed_model, "second")},
        {"type": "upsert_rule", "domain": "guidance", "rule": _guidance_rule(confirmed_model)},
        {"type": "upsert_rule", "domain": "redDots", "rule": _red_dot_rule(confirmed_model)},
    ], confirmed_model["revision"])

    reordered = apply_operations(model, [
        {"type": "reorder_rule", "domain": "narrative", "id": "NAR-002", "toIndex": 0},
        {"type": "reorder_rule_nested", "domain": "guidance", "id": "GDE-001", "field": "steps", "fromIndex": 1, "toIndex": 0},
        {"type": "reorder_rule_nested", "domain": "redDots", "id": "RDT-001", "field": "path", "fromIndex": 1, "toIndex": 0},
    ], model["revision"])

    assert [(item["id"], item["order"]) for item in reordered["ruleDomains"]["narrative"]] == [("NAR-002", 1), ("NAR-001", 2)]
    assert [step["id"] for step in reordered["ruleDomains"]["guidance"][0]["steps"]] == ["GDE-001-step-2", "GDE-001-step-1"]
    assert [step["id"] for step in reordered["ruleDomains"]["redDots"][0]["path"]] == ["RDT-001-path-2", "RDT-001-path-1"]

    deleted = apply_operations(reordered, [{"type": "delete_rule", "domain": "narrative", "id": "NAR-002"}], reordered["revision"])
    restored = undo(deleted, deleted["revision"])
    redone = redo(restored, restored["revision"])

    assert [item["id"] for item in redone["ruleDomains"]["narrative"]] == ["NAR-001"]
    assert redone["ruleDomains"]["guidance"][0]["steps"][0]["text"] == "确认选择"
    assert redone["ruleDomains"]["redDots"][0]["path"][0]["text"] == "奖励"


def test_rule_edits_preserve_unrelated_suggestions_and_reanalysis_respects_human_values(confirmed_model):
    model = apply_operations(confirmed_model, [{"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(confirmed_model)}], confirmed_model["revision"])
    model["ruleDomains"]["narrative"][0]["suggestions"] = {"title": "模型标题", "presentation": "模型表现"}

    changed = apply_operations(model, [{"type": "upsert_rule", "domain": "narrative", "rule": {"id": "NAR-001", "title": "人工标题"}}], model["revision"])
    candidate = deepcopy(changed)
    candidate["ruleDomains"]["narrative"][0]["title"] = "重分析标题"
    suggested = record_reanalysis_suggestions(changed, candidate)

    assert changed["ruleDomains"]["narrative"][0]["humanEditedFields"] == sorted(_narrative_rule(confirmed_model))
    assert changed["ruleDomains"]["narrative"][0]["suggestions"] == {"presentation": "模型表现"}
    assert suggested["ruleDomains"]["narrative"][0]["title"] == "人工标题"
    assert suggested["ruleDomains"]["narrative"][0]["suggestions"] == {"presentation": "模型表现", "title": "重分析标题"}


def test_active_flow_and_stage_edits_preserve_legacy_rule_data(confirmed_model):
    confirmed_model["ruleDomains"] = {"confirmation": {"confirmed": True, "revision": 4}, "custom": [1, 2]}
    before = deepcopy(confirmed_model["ruleDomains"])

    stage_edited = apply_operations(confirmed_model, [{
        "type": "set", "entity": "stage", "id": "STG-001", "field": "unknowns", "value": ["copy pending"],
    }], confirmed_model["revision"])
    flow_edited = apply_operations(stage_edited, [{
        "type": "move_stage", "id": "STG-002", "toIndex": 0,
    }], stage_edited["revision"])

    assert stage_edited["ruleDomains"] == before
    assert flow_edited["ruleDomains"] == before


def test_confirm_rule_domains_requires_all_tabs_reviewed_and_advances_once(confirmed_model):
    confirmed_model["ruleDomains"]["reviewedDomains"] = ["narrative", "guidance"]
    with pytest.raises(ValueError, match="redDots"):
        confirm_rule_domains(confirmed_model, confirmed_model["revision"])

    confirmed_model["ruleDomains"]["reviewedDomains"].append("redDots")
    result = confirm_rule_domains(confirmed_model, confirmed_model["revision"])

    assert result["revision"] == confirmed_model["revision"] + 1
    assert result["ruleDomains"]["confirmation"] == {"confirmed": True, "revision": result["revision"]}
    assert result["reviewState"]["status"] == "rules_confirmed"
    assert result["reviewState"]["previewRevision"] is None


def test_marking_rule_domain_reviewed_does_not_fabricate_rules():
    model = review_model()
    changed = apply_operations(model, [{"type": "mark_rule_domain_reviewed", "domain": "guidance"}], model["revision"])

    assert changed["ruleDomains"]["guidance"] == []
    assert changed["ruleDomains"]["reviewedDomains"] == ["guidance"]


def test_active_non_rule_edits_preserve_legacy_rule_domains(confirmed_model):
    before = deepcopy(confirmed_model["ruleDomains"])
    constrained = apply_operations(confirmed_model, [{
        "type": "upsert_constraint", "constraint": {"text": "preserve selection", "severity": "non_core", "status": "observed"},
    }], confirmed_model["revision"])
    noted = apply_operations(confirmed_model, [{
        "type": "set", "entity": "stage", "id": "STG-001", "field": "unknowns", "value": ["copy pending"],
    }], confirmed_model["revision"])

    assert constrained["ruleDomains"] == before
    assert noted["ruleDomains"] == before


def test_read_only_or_unchanged_operations_do_not_invalidate_rule_confirmation(confirmed_model):
    confirmed_model["stages"][0]["unknowns"] = ["copy pending"]

    read_only = apply_operations(confirmed_model, [], confirmed_model["revision"])
    unchanged = apply_operations(confirmed_model, [{
        "type": "set", "entity": "stage", "id": "STG-001", "field": "unknowns", "value": ["copy pending"],
    }], confirmed_model["revision"])

    assert read_only["ruleDomains"]["confirmation"] == confirmed_model["ruleDomains"]["confirmation"]
    assert unchanged["ruleDomains"]["confirmation"] == confirmed_model["ruleDomains"]["confirmation"]


def test_deleted_rule_ids_are_not_reused_in_any_domain(confirmed_model):
    created = apply_operations(confirmed_model, [
        {"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(confirmed_model)},
        {"type": "upsert_rule", "domain": "guidance", "rule": _guidance_rule(confirmed_model)},
        {"type": "upsert_rule", "domain": "redDots", "rule": _red_dot_rule(confirmed_model)},
    ], confirmed_model["revision"])
    deleted = apply_operations(created, [
        {"type": "delete_rule", "domain": "narrative", "id": "NAR-001"},
        {"type": "delete_rule", "domain": "guidance", "id": "GDE-001"},
        {"type": "delete_rule", "domain": "redDots", "id": "RDT-001"},
    ], created["revision"])
    recreated = apply_operations(deleted, [
        {"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(deleted)},
        {"type": "upsert_rule", "domain": "guidance", "rule": _guidance_rule(deleted)},
        {"type": "upsert_rule", "domain": "redDots", "rule": _red_dot_rule(deleted)},
    ], deleted["revision"])

    assert [item["id"] for item in recreated["ruleDomains"]["narrative"]] == ["NAR-002"]
    assert [item["id"] for item in recreated["ruleDomains"]["guidance"]] == ["GDE-002"]
    assert [item["id"] for item in recreated["ruleDomains"]["redDots"]] == ["RDT-002"]


@pytest.mark.parametrize("value", [True, "0", 0.0])
def test_rule_reorder_requires_strict_integer_indexes(confirmed_model, value):
    model = apply_operations(confirmed_model, [
        {"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(confirmed_model, "first")},
        {"type": "upsert_rule", "domain": "narrative", "rule": _narrative_rule(confirmed_model, "second")},
        {"type": "upsert_rule", "domain": "guidance", "rule": _guidance_rule(confirmed_model)},
    ], confirmed_model["revision"])

    with pytest.raises(ValueError, match="integer"):
        apply_operations(model, [{"type": "reorder_rule", "domain": "narrative", "id": "NAR-002", "toIndex": value}], model["revision"])
    with pytest.raises(ValueError, match="integer"):
        apply_operations(model, [{"type": "reorder_rule_nested", "domain": "guidance", "id": "GDE-001", "field": "steps", "fromIndex": 0, "toIndex": value}], model["revision"])
    with pytest.raises(ValueError, match="integer"):
        apply_operations(model, [{"type": "reorder_rule_nested", "domain": "guidance", "id": "GDE-001", "field": "steps", "fromIndex": value, "toIndex": 0}], model["revision"])


def test_stage_edit_invalidates_only_that_stage_and_preview():
    model = review_model()
    model["reviewState"].update({"flowConfirmed": True, "confirmedStageIds": ["STG-001", "STG-002"], "previewRevision": model["revision"]})
    for stage in model["stages"]:
        stage["confirmation"]["confirmed"] = True

    changed = apply_operations(model, [{"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "武器选择"}], model["revision"])

    assert changed["reviewState"]["flowConfirmed"] is True
    assert changed["reviewState"]["confirmedStageIds"] == ["STG-002"]
    assert changed["reviewState"]["previewRevision"] is None
    assert len(changed["editHistory"]["undo"]) == 1
    restored = undo(changed, changed["revision"])
    assert restored["stages"][0]["name"] != "武器选择"


def test_flow_edit_invalidates_all_downstream_confirmation():
    model = review_model()
    model["reviewState"].update({"flowConfirmed": True, "confirmedStageIds": ["STG-001"], "previewRevision": 1})

    changed = apply_operations(model, [{"type": "move_stage", "id": "STG-002", "toIndex": 0}], model["revision"])

    assert changed["reviewState"] == {"status": "flow_review", "flowConfirmed": False, "confirmedStageIds": [], "previewRevision": None}
    assert all(stage["confirmation"] == {"confirmed": False, "revision": None} for stage in changed["stages"])


def test_stale_revision_is_rejected():
    model = review_model()

    with pytest.raises(ReviewConflict) as error:
        apply_operations(model, [], model["revision"] - 1)

    assert error.value.current_revision == model["revision"]


def test_undo_and_redo_are_revisioned_and_limited_to_available_history():
    model = review_model()
    changed = apply_operations(model, [{"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "编辑后"}], 1)
    restored = undo(changed, 2)
    redone = redo(restored, 3)

    assert redone["stages"][0]["name"] == "编辑后"
    with pytest.raises(ValueError, match="nothing to undo"):
        undo(model, 1)


def test_confirm_flow_allows_unknown_trigger_type_for_planner_confirmation():
    model = review_model()
    model["transitions"][0]["triggerType"] = "unknown"

    confirmed = confirm_flow(model, model["revision"])

    assert confirmed["revision"] == 2
    assert confirmed["reviewState"] == {"status": "stage_review", "flowConfirmed": True, "confirmedStageIds": [], "previewRevision": None}
    assert all(item["confirmation"] == {"confirmed": True, "revision": 2} for item in confirmed["transitions"] if item["included"])


def test_confirm_stage_defers_unresolved_details_and_records_confirmation_revision():
    model = review_model()
    model["reviewState"]["flowConfirmed"] = True
    deferred = confirm_stage(model, "STG-001", model["revision"])
    assert deferred["stages"][0]["confirmation"] == {"confirmed": True, "revision": 2}
    assert "STG-001" not in review_gate(deferred)["blockers"]
    assert "STG-001_PENDING_DETAILS" in review_gate(deferred)["warnings"]

    valid = review_model()
    valid["reviewState"]["flowConfirmed"] = True
    for stage in valid["stages"]:
        stage["smallLoop"] = {"display": "display", "trigger": "tap", "feedback": "feedback", "result": "result", "retry": ""}
    confirmed = confirm_stage(valid, "STG-001", valid["revision"])

    assert confirmed["revision"] == 2
    assert confirmed["stages"][0]["confirmation"] == {"confirmed": True, "revision": 2}
    assert confirmed["reviewState"]["confirmedStageIds"] == ["STG-001"]


@pytest.mark.parametrize("failure", ["missing_image", "missing_action", "inferred_action"])
def test_confirm_stage_rejects_evidence_that_cannot_support_a_planner_confirmation(failure):
    model = review_model()
    model["reviewState"]["flowConfirmed"] = True
    stage = model["stages"][0]
    frame_id = stage["representativeFrames"][0]["frameId"]
    transition = next(item for item in model["transitions"] if item["sourceStageId"] == stage["id"])
    if failure == "missing_image":
        model["sources"][frame_id]["imageUrl"] = ""
    elif failure == "missing_action":
        model["sources"][frame_id]["pageInfo"]["action"] = "无明确操作"
        stage["smallLoop"]["trigger"] = "待确认"
        transition["triggerType"] = "unknown"
        transition["triggerLabel"] = ""
    else:
        model["sources"][frame_id]["pageInfo"]["action"] = "推测玩家点击按钮"
        stage["smallLoop"]["trigger"] = "待确认"
        transition["triggerLabel"] = "可能点击按钮"
        transition["sourceLevel"] = "推测"

    with pytest.raises(ValueError, match="stage evidence"):
        confirm_stage(model, stage["id"], model["revision"])
    assert stage["confirmation"]["confirmed"] is False
    assert model["reviewState"]["status"] != "preview_ready"


def test_flow_change_clears_transition_confirmations_and_stage_confirmation_confirms_owned_entities():
    model = review_model()
    for stage in model["stages"]:
        stage["smallLoop"] = {"display": "display", "trigger": "tap", "feedback": "feedback", "result": "result", "retry": ""}
    model["regions"] = [{"id": "REG-001", "stageId": "STG-001", "frameId": "F0001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}, "confirmation": {"confirmed": False, "revision": None}}]
    model["stages"][0]["regionIds"] = ["REG-001"]
    model["components"] = [{"id": "CMP-0001", "stageId": "STG-001", "frameId": "F0001", "regionId": "REG-001", "confirmation": {"confirmed": False, "revision": None}}]
    model["componentStates"] = [{"id": "CST-001", "componentId": "CMP-0001", "states": {key: "visible" for key in ("default", "pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet")}, "confirmation": {"confirmed": False, "revision": None}}]
    model = confirm_flow(model, model["revision"])
    confirmed = confirm_stage(model, "STG-001", model["revision"])

    assert confirmed["regions"][0]["confirmation"] == {"confirmed": True, "revision": 3}
    assert confirmed["components"][0]["confirmation"] == {"confirmed": True, "revision": 3}
    assert confirmed["componentStates"][0]["confirmation"] == {"confirmed": True, "revision": 3}

    invalidated = apply_operations(confirmed, [{"type": "set_transition_included", "id": "TRN-001", "included": False}], confirmed["revision"])
    assert all(item["confirmation"] == {"confirmed": False, "revision": None} for item in invalidated["transitions"])


def test_region_reference_conflict_and_stage_confirmation_requirements():
    model = review_model()
    model["regions"] = [{"id": "REG-0001", "stageId": "STG-001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
    model["transitions"][0]["componentId"] = "REG-0001"
    try:
        apply_operations(model, [{"type": "delete_region", "id": "REG-0001"}], model["revision"])
    except ValueError as exc:
        assert "TRN-001" in str(exc)
    else:
        raise AssertionError("expected referenced-region rejection")
    model["stages"][0]["representativeFrames"] = []
    try:
        confirm_stage(model, "STG-001", model["revision"])
    except ValueError as exc:
        assert "representative" in str(exc)
    else:
        raise AssertionError("expected representative-frame rejection")


def test_representative_frame_operations_use_the_shared_validation_rules():
    model = review_model()
    valid = [{"frameId": "F0001", "role": "entry"}]
    changed = apply_operations(model, [{"type": "set_representative_frames", "id": "STG-001", "frames": valid}], model["revision"])
    assert changed["stages"][0]["representativeFrames"] == valid
    for invalid in [
        [{"frameId": "F0001", "role": "entry"}, {"frameId": "F0001", "role": "result"}],
        [{"frameId": "F0001", "role": "entry"}, {"frameId": "F0002", "role": "entry"}],
        [{"frameId": "F0001", "role": "entry"}, {"frameId": "F0002", "role": "change"}],
        [{"frameId": "F9999", "role": "entry"}],
    ]:
        with pytest.raises(ValueError, match="representative"):
            apply_operations(model, [{"type": "set_representative_frames", "id": "STG-001", "frames": invalid}], model["revision"])


def test_stage_operations_clamp_and_renumber_regions_atomically():
    model = review_model()
    changed = apply_operations(model, [
        {"type": "upsert_region", "region": {"stageId": "STG-001", "frameId": "F0001", "bounds": {"x": -1, "y": 0.8, "width": 0.5, "height": 0.4}}},
        {"type": "upsert_region", "region": {"stageId": "STG-001", "frameId": "F0001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}},
    ], model["revision"])
    assert changed["revision"] == model["revision"] + 1
    assert [region["displayNumber"] for region in changed["regions"]] == [1, 2]
    assert changed["regions"][0]["bounds"] == {"x": 0.0, "y": 0.6, "width": 0.5, "height": 0.4}
    original = deepcopy(changed)
    with pytest.raises(ValueError, match="primary"):
        apply_operations(changed, [{"type": "set", "entity": "region", "id": changed["regions"][0]["id"], "field": "primary", "value": True}, {"type": "delete_region", "id": changed["regions"][0]["id"]}], changed["revision"])
    assert changed == original


def test_reconfirming_flow_resets_existing_stage_confirmations():
    model = review_model()
    model["ruleDomains"]["confirmation"] = {"confirmed": True, "revision": model["revision"]}
    for stage in model["stages"]:
        stage["smallLoop"] = {"display": "display", "trigger": "tap", "feedback": "feedback", "result": "result", "retry": ""}
    model = confirm_flow(model, model["revision"])
    for stage in model["stages"]:
        model = confirm_stage(model, stage["id"], model["revision"])
    assert review_gate(model)["exportReady"] is True

    reconfirmed = confirm_flow(model, model["revision"])

    assert reconfirmed["reviewState"] == {"status": "stage_review", "flowConfirmed": True, "confirmedStageIds": [], "previewRevision": None}
    assert all(stage["confirmation"] == {"confirmed": False, "revision": None} for stage in reconfirmed["stages"])
    assert review_gate(reconfirmed)["exportReady"] is False


def test_confirmations_require_non_boolean_integer_revisions():
    model = review_model()

    with pytest.raises(ValueError, match="expectedRevision"):
        confirm_flow(model, None)
    with pytest.raises(ValueError, match="expectedRevision"):
        confirm_stage(model, "STG-001", True)


@pytest.mark.parametrize("operation", [
    {"type": "set", "entity": "stage", "id": "STG-001", "field": "order", "value": 2},
    {"type": "set", "entity": "region", "id": "REG-001", "field": "stageId", "value": "STG-002"},
    {"type": "set", "entity": "stage", "id": "STG-001", "field": "id", "value": "STG-999"},
])
def test_generic_set_rejects_identity_and_ownership_fields(operation):
    model = review_model()
    model["regions"] = [{"id": "REG-001", "stageId": "STG-001"}]

    with pytest.raises(ValueError, match="not editable"):
        apply_operations(model, [operation], model["revision"])


def test_empty_operation_batch_is_a_true_noop():
    model = review_model()
    model["reviewState"]["previewRevision"] = model["revision"]
    model["editHistory"]["redo"] = [{"revision": 0}]

    result = apply_operations(model, [], model["revision"])

    assert result == model
    assert result is not model


def test_content_equivalent_operations_are_a_true_noop():
    model = review_model()
    model["reviewState"].update({"flowConfirmed": True, "confirmedStageIds": ["STG-001", "STG-002"], "previewRevision": model["revision"]})
    for stage in model["stages"]:
        stage["confirmation"] = {"confirmed": True, "revision": model["revision"]}
    model["editHistory"]["redo"] = [{"revision": 0}]

    result = apply_operations(model, [
        {"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": model["stages"][0]["name"]},
        {"type": "move_stage", "id": "STG-001", "toIndex": 0},
    ], model["revision"])

    assert result == model
    assert result is not model


def test_mixed_operation_batch_applies_only_real_changes():
    model = review_model()
    model["reviewState"].update({"flowConfirmed": True, "confirmedStageIds": ["STG-001", "STG-002"], "previewRevision": model["revision"]})
    for stage in model["stages"]:
        stage["confirmation"] = {"confirmed": True, "revision": model["revision"]}

    result = apply_operations(model, [
        {"type": "move_stage", "id": "STG-001", "toIndex": 0},
        {"type": "set", "entity": "stage", "id": "STG-001", "field": "name", "value": "renamed"},
    ], model["revision"])

    assert result["revision"] == model["revision"] + 1
    assert result["reviewState"]["confirmedStageIds"] == ["STG-002"]
    assert result["reviewState"]["previewRevision"] is None
    assert result["stages"][0]["confirmation"] == {"confirmed": False, "revision": None}


@pytest.mark.parametrize("operations", [None, {"type": "set"}, [None]])
def test_operations_must_be_a_list_of_objects(operations):
    model = review_model()

    with pytest.raises(ValueError, match="operations"):
        apply_operations(model, operations, model["revision"])


def test_transition_include_merge_and_anchor_rules():
    model = review_model()
    excluded = apply_operations(model, [{"type": "set_transition_included", "id": "TRN-001", "included": False}], model["revision"])
    assert next(item for item in excluded["transitions"] if item["id"] == "TRN-001")["included"] is False

    merged = apply_operations(model, [{"type": "merge_stages", "keepId": "STG-001", "mergeId": "STG-002"}], model["revision"])
    assert [stage["id"] for stage in merged["stages"]] == ["STG-001"]
    assert all(item.get("targetStageId") != "STG-002" for item in merged["transitions"])

    model["transitions"][0]["triggerType"] = "animation_end"
    with pytest.raises(ValueError, match="anchor"):
        apply_operations(model, [{"type": "set_anchor", "id": "TRN-001", "anchor": {"x": 0.2, "y": 0.3}}], model["revision"])


def test_stage_merge_rehomes_regions_and_representative_frames():
    model = review_model()
    model["regions"] = [{"id": "REG-001", "stageId": "STG-002", "frameId": "F0002", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
    model["stages"][1]["regionIds"] = ["REG-001"]

    merged = apply_operations(model, [{"type": "merge_stages", "keepId": "STG-001", "mergeId": "STG-002"}], model["revision"])

    assert merged["regions"][0]["stageId"] == "STG-001"
    assert merged["stages"][0]["regionIds"] == ["REG-001"]
    assert [frame["frameId"] for frame in merged["stages"][0]["representativeFrames"]] == ["F0001", "F0002"]
    assert [frame["role"] for frame in merged["stages"][0]["representativeFrames"]] == ["entry", "result"]


def test_stage_merge_renumbers_regions_across_both_stages():
    model = review_model()
    model["regions"] = [
        {"id": "REG-001", "stageId": "STG-001", "frameId": "F0001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}, "displayOrder": 1, "displayNumber": 1},
        {"id": "REG-002", "stageId": "STG-002", "frameId": "F0002", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}, "displayOrder": 1, "displayNumber": 1},
    ]
    model["stages"][0]["regionIds"] = ["REG-001"]
    model["stages"][1]["regionIds"] = ["REG-002"]

    merged = apply_operations(model, [{"type": "merge_stages", "keepId": "STG-001", "mergeId": "STG-002"}], model["revision"])

    assert [(region["id"], region["displayOrder"], region["displayNumber"]) for region in merged["regions"]] == [
        ("REG-001", 1, 1),
        ("REG-002", 2, 2),
    ]


def test_stage_merge_rejects_invalid_representative_source_without_mutating_input():
    model = review_model()
    model["stages"][1]["representativeFrames"] = [{"frameId": "F9999", "role": "entry"}]
    original = deepcopy(model)

    with pytest.raises(ValueError, match="representative"):
        apply_operations(model, [{"type": "merge_stages", "keepId": "STG-001", "mergeId": "STG-002"}], model["revision"])

    assert model == original


def test_stage_merge_deduplicates_frames_in_stable_order_and_rejects_more_than_three():
    model = review_model()
    model["sources"]["F0003"] = deepcopy(model["sources"]["F0002"])
    model["stages"][0]["representativeFrames"] = [{"frameId": "F0001"}, {"frameId": "F0002"}]
    model["stages"][1]["representativeFrames"] = [{"frameId": "F0002"}, {"frameId": "F0003"}]

    merged = apply_operations(model, [{"type": "merge_stages", "keepId": "STG-001", "mergeId": "STG-002"}], model["revision"])
    assert [item["frameId"] for item in merged["stages"][0]["representativeFrames"]] == ["F0001", "F0002", "F0003"]

    model["stages"][1]["representativeFrames"].append({"frameId": "F0004"})
    with pytest.raises(ValueError, match="representative"):
        apply_operations(model, [{"type": "merge_stages", "keepId": "STG-001", "mergeId": "STG-002"}], model["revision"])


@pytest.mark.parametrize("result_type", ["navigate", "open_overlay", "return", "loop"])
def test_transition_requires_target_for_navigation_but_allows_terminal_without_one(result_type):
    model = review_model()
    payload = {"sourceStageId": "STG-001", "targetStageId": None, "sourceFrameId": "F0001", "triggerType": "system_event", "triggerLabel": "auto", "resultType": result_type}
    with pytest.raises(ValueError, match="targetStageId"):
        apply_operations(model, [{"type": "upsert_transition", "transition": payload}], model["revision"])

    terminal = apply_operations(model, [{"type": "upsert_transition", "transition": {**payload, "resultType": "terminal"}}], model["revision"])
    assert terminal["transitions"][-1]["targetStageId"] is None
    assert terminal["transitions"][-1]["resultType"] == "terminal"


def test_generic_transition_edits_cannot_break_target_semantics():
    model = review_model()
    model["transitions"][0].update({"targetStageId": None, "resultType": "terminal"})
    with pytest.raises(ValueError, match="targetStageId"):
        apply_operations(model, [{"type": "set", "entity": "transition", "id": "TRN-001", "field": "resultType", "value": "navigate"}], model["revision"])


@pytest.mark.parametrize("binding", [
    {"id": "REG-001", "stageId": "STG-002", "frameId": "F0001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
    {"id": "REG-001", "stageId": "STG-001", "frameId": "F0002", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
])
def test_anchor_binding_must_match_transition_source_stage_and_frame(binding):
    model = review_model()
    model["regions"] = [binding]
    model["transitions"][0].update({"triggerType": "tap", "regionId": "REG-001"})
    with pytest.raises(ValueError, match="anchor"):
        apply_operations(model, [{"type": "set_anchor", "id": "TRN-001", "anchor": {"x": 0.2, "y": 0.2}}], model["revision"])
    with pytest.raises(ValueError, match="anchor"):
        apply_operations(model, [{"type": "upsert_transition", "transition": model["transitions"][0]}], model["revision"])


@pytest.mark.parametrize("region", [
    {"stageId": "STG-002", "frameId": "F0001"},
    {"stageId": "STG-001", "frameId": "F0002"},
])
@pytest.mark.parametrize("operation_type", ["set_anchor", "upsert_transition"])
def test_explicit_component_and_region_bindings_are_both_validated(region, operation_type):
    model = review_model()
    model["components"] = [{"id": "CMP-001", "stageId": "STG-001", "frameId": "F0001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
    model["regions"] = [{"id": "REG-001", **region, "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
    model["transitions"][0].update({"triggerType": "tap", "componentId": "CMP-001", "regionId": "REG-001"})
    operation = {"type": "set_anchor", "id": "TRN-001", "anchor": {"x": 0.2, "y": 0.2}} if operation_type == "set_anchor" else {"type": "upsert_transition", "transition": model["transitions"][0]}
    with pytest.raises(ValueError, match="anchor"):
        apply_operations(model, [operation], model["revision"])


def test_constraint_text_is_the_canonical_editable_text_field():
    model = review_model()
    model["crossStateConstraints"] = [{"id": "CNS-001", "text": "old", "severity": "non_core", "status": "unknown"}]
    updated = apply_operations(model, [{"type": "upsert_constraint", "constraint": {"id": "CNS-001", "text": "new", "severity": "core", "status": "observed"}}], model["revision"])
    assert updated["crossStateConstraints"] == [{"id": "CNS-001", "text": "new", "severity": "core", "status": "observed", "humanEditedFields": ["severity", "status", "text"], "suggestions": {}}]


def test_explicit_transition_and_constraint_operations_preserve_review_invalidation():
    model = review_model()
    created = apply_operations(model, [{
        "type": "upsert_transition",
        "transition": {
            "sourceStageId": "STG-001", "targetStageId": "STG-002", "sourceFrameId": "F0001",
            "triggerType": "system_event", "triggerLabel": "自动开始", "resultType": "navigate", "included": True,
        },
    }], model["revision"])
    candidate = next(item for item in created["transitions"] if item["id"] != "TRN-001")
    assert candidate["id"].startswith("TRN-")
    assert created["reviewState"]["flowConfirmed"] is False

    constrained = apply_operations(created, [{
        "type": "upsert_constraint",
        "constraint": {"text": "同一状态不能同时展示", "severity": "core", "status": "observed"},
    }], created["revision"])
    constraint = constrained["crossStateConstraints"][0]
    assert constraint["id"].startswith("CNS-")

    deleted = apply_operations(constrained, [{"type": "delete_constraint", "id": constraint["id"]}], constrained["revision"])
    assert deleted["crossStateConstraints"] == []


@pytest.mark.parametrize("frame_id", ["F0002", "F0003"])
def test_region_mutation_rejects_frames_outside_the_owning_stage_representatives(frame_id):
    model = review_model()
    model["sources"]["F0003"] = deepcopy(model["sources"]["F0001"])

    with pytest.raises(ValueError, match="representative frame"):
        apply_operations(model, [{
            "type": "upsert_region",
            "region": {"stageId": "STG-001", "frameId": frame_id, "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
        }], model["revision"])


def test_stage_confirmation_rejects_legacy_regions_on_non_representative_frames():
    model = review_model()
    model["reviewState"]["flowConfirmed"] = True
    model["stages"][0]["smallLoop"] = {"display": "display", "trigger": "tap", "feedback": "feedback", "result": "result", "retry": ""}
    model["regions"] = [{"id": "REG-001", "stageId": "STG-001", "frameId": "F0002", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]

    with pytest.raises(ValueError, match="representative frame"):
        confirm_stage(model, "STG-001", model["revision"])


def test_representative_replacement_atomically_rehomes_owned_annotations_and_transition_sources():
    model = review_model()
    model["sources"]["F0003"] = deepcopy(model["sources"]["F0001"])
    model["regions"] = [{"id": "REG-001", "stageId": "STG-001", "frameId": "F0001", "bounds": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
    model["components"] = [{"id": "CMP-001", "stageId": "STG-001", "frameId": "F0001", "regionId": "REG-001"}]
    model["stages"][0]["regionIds"] = ["REG-001"]
    model["componentStates"] = [{"id": "CST-001", "componentId": "CMP-001", "states": {key: "visible" for key in ("default", "pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet")}}]

    result = apply_operations(model, [{"type": "replace_representative_frame", "id": "STG-001", "oldFrameId": "F0001", "frame": {"frameId": "F0003", "role": "entry"}}], model["revision"])

    assert result["stages"][0]["representativeFrames"] == [{"frameId": "F0003", "role": "entry"}]
    assert result["regions"][0]["frameId"] == "F0003"
    assert result["components"][0]["frameId"] == "F0003"
    assert result["transitions"][0]["sourceFrameId"] == "F0003"


def test_non_structural_constraints_and_notes_keep_confirmations_but_invalidate_preview():
    model = review_model()
    model["reviewState"].update({"status": "preview_ready", "flowConfirmed": True, "confirmedStageIds": [stage["id"] for stage in model["stages"]], "previewRevision": model["revision"]})
    for stage in model["stages"]:
        stage["confirmation"] = {"confirmed": True, "revision": model["revision"]}

    constrained = apply_operations(model, [{"type": "upsert_constraint", "constraint": {"text": "keep", "severity": "non_core", "status": "observed"}}], model["revision"])
    noted = apply_operations(constrained, [{"type": "set", "entity": "stage", "id": "STG-001", "field": "unknowns", "value": ["copy pending"]}], constrained["revision"])

    assert noted["reviewState"]["flowConfirmed"] is True
    assert noted["reviewState"]["confirmedStageIds"] == [stage["id"] for stage in model["stages"]]
    assert all(stage["confirmation"]["confirmed"] for stage in noted["stages"])
    assert noted["reviewState"]["previewRevision"] is None


def test_rejecting_a_suggestion_preserves_a_current_preview_when_content_does_not_change():
    model = review_model()
    model["reviewState"].update({"status": "preview_ready", "flowConfirmed": True, "confirmedStageIds": [stage["id"] for stage in model["stages"]], "previewRevision": model["revision"]})
    for stage in model["stages"]:
        stage["confirmation"] = {"confirmed": True, "revision": model["revision"]}
    model["stages"][0]["suggestions"] = {"name": "new name"}

    result = apply_operations(model, [{"type": "reject_suggestion", "entity": "stage", "id": "STG-001", "field": "name"}], model["revision"])

    assert result["revision"] == model["revision"] + 1
    assert result["reviewState"]["previewRevision"] == result["revision"]
    assert result["reviewState"]["confirmedStageIds"] == model["reviewState"]["confirmedStageIds"]
    assert result["stages"][0]["confirmation"] == model["stages"][0]["confirmation"]


def test_resolving_interaction_decision_card_updates_transition_stage_and_source_atomically():
    model = review_model()
    transition = model["transitions"][0]
    transition.update({"triggerType": "unknown", "triggerLabel": "待确认"})
    model["interactionDecisionCards"] = [{
        "id": "IDC-001", "transitionId": transition["id"], "status": "pending",
        "options": [{"id": "tap", "label": "点击当前页面中的按钮或入口", "triggerType": "tap"}],
    }]

    result = apply_operations(model, [{"type": "resolve_interaction_decision_card", "cardId": "IDC-001", "optionId": "tap"}], model["revision"])

    updated = result["transitions"][0]
    assert updated["triggerType"] == "tap"
    assert updated["triggerLabel"] == "点击当前页面中的按钮或入口"
    assert result["stages"][0]["smallLoop"]["trigger"] == updated["triggerLabel"]
    assert result["sources"][updated["sourceFrameId"]]["pageInfo"]["action"] == updated["triggerLabel"]
    assert "pageInfo.action" in result["sources"][updated["sourceFrameId"]]["humanEditedFields"]
    assert result["interactionDecisionCards"][0]["status"] == "resolved"
