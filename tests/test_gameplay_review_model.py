from copy import deepcopy

from backend.gameplay_review_model import (
    MECHANISM_SCHEMAS,
    build_gameplay_review_model,
    ensure_gameplay_review_model,
    gameplay_gate,
    normalize_gameplay_structure,
    required_parameter_fields,
    validate_gameplay_review_model,
)


def _job() -> dict:
    return {
        "id": "job-gameplay-1",
        "interactionModel": {"revision": 7},
        "frames": [
            {"id": "F0001", "timestamp": 1.0, "sourceName": "combat.png", "imageUrl": "/artifacts/job-gameplay-1/frames/F0001.jpg", "sequenceIndex": 1},
            {"id": "F0002", "timestamp": 2.0},
        ],
    }


def _draft() -> dict:
    return {
        "scope": "combat loop",
        "claims": [{"text": "Player attacks", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
        "mechanism": {"type": "core_loop", "name": "Attack"},
        "parameters": {},
        "dependencies": [],
        "acceptanceCases": [],
        "unknowns": [],
        "sourceFrameIds": ["F0001"],
    }


def test_normalize_structure_groups_only_observed_chapters_and_preserves_ids():
    first = _draft()
    first.update({"scope": "持续战斗", "systemName": "战斗与关卡", "subsystemName": "核心战斗"})
    second = _draft()
    second.update({"scope": "升级选择", "systemName": "局内成长", "subsystemName": "升级选择", "sourceFrameIds": ["F0002"]})

    normalized = normalize_gameplay_structure(build_gameplay_review_model(_job(), [first, second]))

    assert [item["name"] for item in normalized["systems"]] == ["战斗与关卡", "局内成长"]
    assert normalized["chapters"][0]["id"] == "GCH-001"
    assert normalized["chapters"][0]["systemId"] == normalized["systems"][0]["id"]
    assert normalized["systems"][0]["subsystems"][0]["chapterIds"] == ["GCH-001"]


def test_builds_frozen_evidence_only_chapters_from_drafts():
    job = _job()
    model = build_gameplay_review_model(job, [_draft()])

    assert model["interactionRevision"] == 7
    assert model["evidenceAnchors"] == [{
        "id": "GEV-001", "frameId": "F0001", "imageUrl": "/artifacts/job-gameplay-1/frames/F0001.jpg",
        "source": {"name": "combat.png", "timestamp": 1.0, "sequenceIndex": 1},
    }]
    assert model["chapters"][0]["id"] == "GCH-001"
    assert model["chapters"][0]["sourceFrameIds"] == ["F0001"]
    assert model["chapters"][0]["claims"][0]["sourceType"] == "material"
    assert model["chapters"][0]["status"] == "draft"
    assert model["reviewState"]["status"] == "chapter_review"
    assert validate_gameplay_review_model(model) == []


def test_build_preserves_presentation_rules_routed_out_of_generated_planner_copy():
    draft = _draft()
    draft["presentationRules"] = ["底部播放升级动画。"]

    chapter = build_gameplay_review_model(_job(), [draft])["chapters"][0]

    assert chapter["presentationRules"] == ["底部播放升级动画。"]


def test_explicit_v2_model_uses_structured_approved_data_without_planner_prose():
    job = _job()
    job["contentModelVersion"] = 2
    draft = _draft()
    draft.update(scope="武器", systemName="核心战斗", claims=[{
        "text": "目标进入射程后，武器自动攻击目标。", "sourceType": "material", "sourceFrameIds": ["F0001"],
    }])
    model = build_gameplay_review_model(job, [draft])
    assert model["contentModelVersion"] == 2
    assert model["approvedData"]["rules"]
    assert all("plannerSections" not in chapter for chapter in model["chapters"])


def test_planned_mechanism_type_does_not_invent_parameters_or_formulae_without_evidence():
    model = build_gameplay_review_model(_job(), [{
        "title": "随机奖励抽取",
        "mechanismType": "random_pool",
        "sourceFrameIds": ["F0001"],
    }])

    chapter = model["chapters"][0]
    assert chapter["id"] == "GCH-001"
    assert chapter["scope"] == "随机奖励抽取"
    assert chapter["mechanism"] == {"type": "random_pool"}
    assert chapter["plannerSummary"] == "系统从当前可用内容池中随机产生候选结果；抽取范围、消耗和刷新规则由本机制定义。"
    assert chapter["inlineEvidence"][0]["caption"] == "支持判断：玩家在局内成长时选择一项强化，使本局能力发生变化。"
    assert not chapter.get("parameterSchema")
    assert not chapter.get("formulae")
    assert validate_gameplay_review_model(model) == []


def test_chapter_inline_evidence_preserves_distinct_frames_dimensions_and_rule_captions():
    job = _job()
    job["frames"] = [{
        "id": f"F000{index}", "imageUrl": f"/artifacts/job-gameplay-1/frames/F000{index}.jpg",
        "structure": {"width": 494, "height": 924},
    } for index in range(1, 5)]
    draft = _draft()
    draft["sourceFrameIds"] = ["F0001", "F0002", "F0003", "F0004", "F0002"]
    draft["claims"] = [{
        "text": f"第{index}张图支持规则{index}", "sourceType": "material", "sourceFrameIds": [f"F000{index}"],
    } for index in range(1, 5)]

    chapter = build_gameplay_review_model(job, [draft])["chapters"][0]

    assert [item["frameId"] for item in chapter["inlineEvidence"]] == ["F0001", "F0002", "F0003", "F0004"]
    assert all((item["width"], item["height"]) == (494, 924) for item in chapter["inlineEvidence"])
    assert chapter["inlineEvidence"][0]["caption"] == "支持判断：第1张图支持规则1"


def test_requires_mechanism_specific_parameter_fields_and_rejects_unknown_types():
    assert set(MECHANISM_SCHEMAS) == {
        "custom", "core_loop", "spatial_drag", "entity_behavior", "formula", "progression", "random_pool",
        "economy_reward", "level_wave", "buff_chain", "settlement", "external_entry", "statistics_feedback",
    }
    assert required_parameter_fields("economy_reward") == ("sources", "costs", "settlement", "accumulation", "failure", "lifecycle")
    assert required_parameter_fields("unknown") == ()

    model = build_gameplay_review_model(_job(), [_draft()])
    model["chapters"][0]["mechanism"]["type"] = "unknown"

    assert "GCH-001: unknown mechanism type 'unknown'" in validate_gameplay_review_model(model)


def test_validator_rejects_bad_claim_and_evidence_references():
    model = build_gameplay_review_model(_job(), [_draft()])
    model["chapters"][0]["claims"][0]["sourceType"] = "unsupported"
    model["chapters"][0]["sourceFrameIds"] = ["F9999"]

    errors = validate_gameplay_review_model(model)

    assert "GCH-001.claims[0].sourceType: invalid source type" in errors
    assert "GCH-001.sourceFrameIds[0]: unknown evidence F9999" in errors


def test_validator_rejects_malformed_and_duplicate_nested_entity_ids():
    model = build_gameplay_review_model(_job(), [_draft()])
    model["chapters"][0]["claims"] = [
        {"id": "GCL-001", "text": "first", "sourceType": "material", "sourceFrameIds": ["F0001"]},
        {"id": "GCL-001", "text": "second", "sourceType": "material", "sourceFrameIds": ["F0001"]},
    ]
    model["chapters"][0]["acceptanceCases"] = [{"id": "bad", "text": "invalid"}]

    errors = validate_gameplay_review_model(model)

    assert any("claims[1].id" in error for error in errors)
    assert any("acceptanceCases[0].id" in error for error in errors)


def test_validator_rejects_unknown_chapter_dependencies():
    model = build_gameplay_review_model(_job(), [_draft()])
    model["chapters"][0]["dependencies"] = ["GCH-999"]

    assert "GCH-001.dependencies: unknown chapter GCH-999" in validate_gameplay_review_model(model)


def test_gate_blocks_stale_unreviewed_incomplete_and_stale_diagrams():
    model = build_gameplay_review_model(_job(), [_draft()])
    chapter = model["chapters"][0]
    chapter["status"] = "reviewed"
    chapter["confirmation"] = {"confirmed": True, "revision": 1}
    chapter["parameters"] = {
        field: {"type": "number", "unit": "points", "range": "0-10", "source": "F0001"}
        for field in required_parameter_fields("core_loop")
    }
    model["diagrams"] = [{"id": "GDI-001", "revision": 1, "status": "open", "chapterIds": ["GCH-001"]}]

    result = gameplay_gate(model, {"revision": 8})

    assert result["exportReady"] is False
    assert "INTERACTION_REVISION_STALE" in result["blockers"]
    assert "GDI-001" in result["blockers"]


def test_gate_blocks_explicitly_failed_detail_semantic_quality():
    model = build_gameplay_review_model(_job(), [_draft()])
    model["detailQuality"] = {
        "passed": False,
        "errors": ["GCH-001:FLOW_CHAIN_STATIC_EVIDENCE_IS_NOT_FLOW"],
    }

    result = gameplay_gate(model, {"revision": 7, "frames": _job()["frames"]})

    assert "DETAIL_QUALITY_FAILED" in result["blockers"]
    assert "GCH-001:FLOW_CHAIN_STATIC_EVIDENCE_IS_NOT_FLOW" in result["blockers"]


def test_gate_blocks_reviewed_diagram_without_frozen_interaction_revision():
    model = build_gameplay_review_model(_job(), [_draft()])
    chapter = model["chapters"][0]
    chapter["status"] = "reviewed"
    chapter["confirmation"] = {"confirmed": True, "revision": 1}
    chapter["parameters"] = {
        field: {"type": "number", "unit": "points", "range": "0-10", "source": "F0001"}
        for field in required_parameter_fields("core_loop")
    }
    model["diagrams"] = [{"id": "GDI-001", "revision": 1, "status": "reviewed", "chapterIds": ["GCH-001"]}]

    assert "GDI-001" in gameplay_gate(model, {"revision": 7})["blockers"]


def test_gate_reports_the_chapter_id_for_invalid_evidence_references():
    model = build_gameplay_review_model(_job(), [_draft()])
    chapter = model["chapters"][0]
    chapter["status"] = "reviewed"
    chapter["confirmation"] = {"confirmed": True, "revision": 1}
    chapter["parameters"] = {
        field: {"type": "number", "unit": "points", "range": "0-10", "source": "F0001"}
        for field in required_parameter_fields("core_loop")
    }
    chapter["sourceFrameIds"] = ["F9999"]

    result = gameplay_gate(model, {"revision": 7, "frames": _job()["frames"]})

    assert "GCH-001" in result["blockers"]


def test_gate_rejects_unknown_gameplay_that_stops_at_title_and_visual_description():
    model = build_gameplay_review_model(_job(), [{
        **_draft(),
        "scope": "光路编织",
        "mechanism": {"type": "custom", "description": "画面中出现多个发光节点"},
        "confirmation": {"confirmed": True, "revision": 1, "decision": "approved"},
        "status": "approved",
    }])
    model["directory"]["status"] = "confirmed"
    model["reviewState"]["depthContractVersion"] = 1

    result = gameplay_gate(model, {"revision": 7, "frames": _job()["frames"]})

    assert "GCH-001:GAMEPLAY_DEPTH_INSUFFICIENT" in result["blockers"]


def test_depth_contract_requires_formula_for_formula_mechanism():
    draft = _draft()
    draft["mechanism"] = {"type": "formula", "inputs": "攻击属性与倍率", "rounding": "向下取整"}
    draft["parameters"] = {"攻击属性": {"value": 100, "type": "number", "unit": "点", "range": "0-9999", "source": "F0001"}}
    draft["acceptanceCases"] = [{"scene": "正常计算", "action": "造成伤害", "expected": "输出取整后的伤害"}]
    draft.update(status="approved", confirmation={"confirmed": True})
    model = build_gameplay_review_model(_job(), [draft])
    model["directory"]["status"] = "confirmed"
    model["reviewState"]["depthContractVersion"] = 1

    result = gameplay_gate(model, {"revision": 7, "frames": _job()["frames"]})

    assert "GCH-001:FORMULA_DEFINITION_MISSING" in result["blockers"]


def test_depth_contract_rejects_formula_module_without_evidence():
    draft = _draft()
    draft["mechanism"] = {"type": "custom", "goal": "完成连接", "rules": "相邻目标才能连接"}
    draft["parameters"] = {"连接上限": {"value": 3, "type": "number", "unit": "个", "range": "1-10", "source": "F0001"}}
    draft["acceptanceCases"] = [{"scene": "正常连接", "action": "连接目标", "expected": "路径生效"}]
    draft.update(status="approved", confirmation={"confirmed": True})
    model = build_gameplay_review_model(_job(), [draft])
    model["chapters"][0]["formulae"] = [{"expression": "结果=A×B", "variables": [{"name": "A"}]}]
    model["directory"]["status"] = "confirmed"
    model["reviewState"]["depthContractVersion"] = 1

    result = gameplay_gate(model, {"revision": 7, "frames": _job()["frames"]})

    assert "GCH-001:OPTIONAL_MODULE_EVIDENCE_INVALID" in result["blockers"]


def test_ensure_returns_existing_model_and_initializes_missing_one():
    job = _job()
    first = ensure_gameplay_review_model(job)
    second = ensure_gameplay_review_model(job)

    assert first is second
    assert job["gameplayReviewModel"] is first


def test_ensure_rejects_a_gameplay_model_copied_from_another_job():
    job = _job()
    model = build_gameplay_review_model(job, [_draft()])
    model["jobId"] = "old-job"
    model["evidenceAnchors"][0]["imageUrl"] = "/artifacts/old-job/frames/F0001.jpg"
    model["chapters"][0]["inlineEvidence"][0]["imageUrl"] = "/artifacts/old-job/frames/F0001.jpg"
    job["gameplayReviewModel"] = model

    refreshed = ensure_gameplay_review_model(job)

    assert refreshed["jobId"] == "job-gameplay-1"
    assert refreshed["chapters"] == []
    assert refreshed["evidenceAnchors"] == []
    assert refreshed["reviewState"]["status"] == "generation_required"
    assert job["gameplayReviewModel"] is refreshed


def test_new_chapter_keeps_phase1_schema_classification_metadata():
    draft = _draft()
    draft["scope"] = "武器"
    draft["claims"] = [{"id": "GCL-001", "text": "进入射程后自动索敌并发射投射物。", "sourceType": "material", "sourceFrameIds": ["F0001"]}]
    chapter = build_gameplay_review_model(_job(), [draft])["chapters"][0]
    assert chapter["chapterType"] == "attack"
    assert chapter["mechanicVariant"] == "ranged"
    assert chapter["matchedSchema"].endswith(":attack:ranged")
