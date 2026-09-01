from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.gameplay_diagrams import (
    approve_diagram,
    auto_generate_diagrams,
    build_diagram,
    delete_diagram,
    generate_diagram,
    regenerate_diagram,
)
from backend.gameplay_review_model import gameplay_gate
from backend.gameplay_review_service import apply_gameplay_operations


def _parameter(value, unit="次", range_="0-100", source="截图"):
    return {"type": "number", "unit": unit, "range": range_, "source": source, "value": value}


@pytest.fixture
def model():
    return {
        "schemaVersion": "1.0", "standard": "GVE16", "jobId": "job-diagrams", "revision": 4,
        "interactionRevision": 3, "evidenceAnchors": [], "contextWindows": [], "editHistory": [],
        "reviewState": {"status": "diagram_review", "findings": []}, "diagrams": [],
        "chapters": [
            {
                "id": "GCH-001", "scope": "随机三选一", "claims": [], "dependencies": [],
                "acceptanceCases": [], "unknowns": [], "sourceFrameIds": [], "status": "approved",
                "confirmation": {"confirmed": True, "revision": 4},
                "mechanism": {"type": "random_pool"},
                "parameters": {
                    "eligibility": _parameter("进入候选池"), "exclusions": _parameter("已持有排除"),
                    "drawOrder": _parameter("按权重抽取"), "replacementRule": _parameter("不放回"),
                    "weightFormula": _parameter("weight/sum(weight)", "%"), "emptyResult": _parameter("显示空槽"),
                    "temporaryResult": _parameter("暂存三项"), "confirm": _parameter("选择一项"),
                    "reroll": _parameter("整组刷新"), "cost": _parameter("1", "次数"), "reset": _parameter("章节结束"),
                },
            },
            {
                "id": "GCH-002", "scope": "伤害结算", "claims": [], "dependencies": ["GCH-001"],
                "acceptanceCases": [], "unknowns": [], "sourceFrameIds": [], "status": "approved",
                "confirmation": {"confirmed": True, "revision": 4},
                "mechanism": {"type": "formula"},
                "parameters": {
                    "inputs": _parameter("attack=120, defense=20", "点"), "units": _parameter("点"),
                    "ranges": _parameter("attack>=0"), "formula": _parameter("attack - defense", "点"),
                    "stackOrder": _parameter("先加成后减防"), "rounding": _parameter("向下取整"),
                    "example": _parameter("120 - 20 = 100", "点"), "configSource": _parameter("战斗表"),
                },
            },
        ],
    }


def test_probability_diagram_retains_source_ids_and_is_deterministic(model):
    first = build_diagram(model, ["GCH-001"], "probability")
    second = build_diagram(model, ["GCH-001"], "probability")
    assert first == second
    assert first["chapterIds"] == ["GCH-001"]
    assert all(node["sourceIds"] for node in first["nodes"])
    assert all(edge["sourceIds"] for edge in first["edges"])
    assert first["nodes"][0]["id"].startswith("GDI-N-")


@pytest.mark.parametrize("diagram_type", ["spatial", "state_flow", "probability", "effect_chain", "formula"])
def test_all_supported_types_return_safe_canonical_svg(model, diagram_type):
    chapter_id = "GCH-002" if diagram_type == "formula" else "GCH-001"
    diagram = build_diagram(model, [chapter_id], diagram_type)
    assert diagram["type"] == diagram_type
    assert diagram["svg"].startswith("<svg")
    assert "<script" not in diagram["svg"].lower()
    assert diagram["mermaid"]


def test_labels_are_escaped_in_svg_and_mermaid(model):
    model["chapters"][0]["scope"] = '<script>alert("x")</script>]'
    diagram = build_diagram(model, ["GCH-001"], "state_flow")
    assert "<script" not in diagram["svg"].lower()
    assert "<script" not in diagram["mermaid"].lower()
    assert "&lt;script&gt;" in diagram["svg"]


def test_formula_includes_formula_parameter_table_and_worked_example(model):
    diagram = build_diagram(model, ["GCH-002"], "formula")
    assert "attack - defense" in diagram["svg"]
    assert "参数" in diagram["svg"]
    assert "120 - 20 = 100" in diagram["svg"]


def test_formula_uses_chapter_formulae_and_omits_empty_parameter_and_example_placeholders(model):
    chapter = model["chapters"][1]
    chapter["parameters"] = {}
    chapter["formulae"] = {
        "name": "生命值变化", "expression": "变化后生命值 = 变化前生命值 - 本次伤害 + 恢复量",
        "rounding": "需要策划决定",
    }

    diagram = build_diagram(model, ["GCH-002"], "formula")

    assert "变化后生命值 = 变化前生命值 - 本次伤害 + 恢复量" in diagram["svg"]
    assert "参数：" not in diagram["svg"]
    assert "算例：" not in diagram["svg"]
    assert "scope:" not in diagram["svg"]
    assert "待确认" not in diagram["svg"]


def test_feedback_is_per_diagram_and_regeneration_creates_revision(model):
    generated = generate_diagram(model, ["GCH-001"], "probability", model["revision"])
    original = deepcopy(generated["diagrams"][0])
    revised = regenerate_diagram(generated, original["id"], "补充空槽分支", generated["revision"])
    diagram = revised["diagrams"][0]
    assert diagram["revision"] == 2
    assert diagram["feedback"][-1]["text"] == "补充空槽分支"
    assert diagram["status"] == "open"
    assert original["feedback"] == []


def test_approve_and_optional_delete_have_distinct_terminal_states(model):
    generated = generate_diagram(model, ["GCH-001"], "probability", 4)
    diagram_id = generated["diagrams"][0]["id"]
    approved = approve_diagram(generated, diagram_id, generated["revision"])
    assert approved["diagrams"][0]["status"] == "reviewed"
    deleted = delete_diagram(approved, diagram_id, approved["revision"])
    assert deleted["diagrams"][0]["status"] == "deleted"
    assert deleted["diagrams"][0]["optional"] is True


def test_generation_rejects_unhelpful_type_for_simple_chapter(model):
    model["chapters"][0]["mechanism"] = {"type": "economy_reward"}
    with pytest.raises(ValueError, match="not helpful"):
        generate_diagram(model, ["GCH-001"], "spatial", 4)


def test_generation_rejects_formula_because_formula_belongs_in_gameplay_text(model):
    with pytest.raises(ValueError, match="text instead of a diagram"):
        generate_diagram(model, ["GCH-002"], "formula", 4)


def test_auto_generation_selects_helpful_diagrams_and_records_completion(model):
    generated = auto_generate_diagrams(model, 4)
    assert [(item["chapterIds"], item["type"]) for item in generated["diagrams"]] == [
        (["GCH-001"], "probability"),
    ]
    assert generated["diagramReview"]["status"] == "ready"
    assert generated["diagramReview"]["noDiagramChapterIds"] == ["GCH-002"]


def test_auto_generation_rebuilds_existing_stale_diagram_from_latest_chapter(model):
    generated = generate_diagram(model, ["GCH-001"], "probability", 4)
    stale = apply_gameplay_operations(
        generated,
        [{"type": "set_chapter_field", "chapterId": "GCH-001", "field": "scope", "value": "新版随机三选一"}],
        generated["revision"],
    )
    before = deepcopy(stale["diagrams"][0])
    assert before["status"] == "stale"

    refreshed = auto_generate_diagrams(stale, stale["revision"])

    diagram = refreshed["diagrams"][0]
    assert diagram["id"] == before["id"]
    assert diagram["revision"] == before["revision"] + 1
    assert diagram["status"] == "open"
    assert diagram["freshness"] == "current"
    assert diagram["sourceRevision"] == stale["revision"]
    assert "新版随机三选一" in diagram["svg"]


def test_auto_generation_does_not_duplicate_chapter_already_covered_by_multi_chapter_diagram(model):
    model["diagrams"] = [{
        "id": "GDI-101", "type": "state_flow", "chapterIds": ["GCH-001", "GCH-002"],
        "status": "stale", "freshness": "current", "revision": 1, "optional": False,
        "feedback": [],
    }]

    generated = auto_generate_diagrams(model, model["revision"])

    active = [item for item in generated["diagrams"] if item.get("status") != "deleted"]
    assert [item["id"] for item in active] == ["GDI-101"]
    assert active[0]["status"] == "open"


def test_auto_generation_never_replaces_visual_flow_with_text_boxes_only(model):
    visual_svg = '<svg><rect/><text>旧流程</text><line/><polygon/></svg>'
    model["chapters"][0]["mechanism"] = {"type": "core_loop"}
    model["chapters"][0]["parameters"] = {
        "trigger": _parameter("进入关卡"),
        "phaseOrder": _parameter("准备、战斗、结算"),
        "completion": _parameter("击败首领"),
    }
    model["diagrams"] = [{
        "id": "GDI-101", "type": "state_flow", "chapterIds": ["GCH-001"],
        "status": "stale", "freshness": "current", "revision": 1, "optional": False,
        "feedback": [], "svg": visual_svg, "generationMode": "curated",
    }]

    generated = auto_generate_diagrams(model, model["revision"])

    diagram = generated["diagrams"][0]
    assert diagram["svg"] == visual_svg
    assert diagram["status"] == "open"
    assert diagram["revision"] == 2
    assert diagram["sourceRevision"] == model["revision"]


def test_auto_generation_deletes_legacy_formula_diagram_and_keeps_formula_as_text(model):
    model["diagrams"] = [{
        "id": "GDI-001", "type": "formula", "chapterIds": ["GCH-002"],
        "status": "reviewed", "optional": True,
    }]

    generated = auto_generate_diagrams(model, 4)

    assert generated["diagrams"][0]["status"] == "deleted"
    assert generated["diagramReview"]["noDiagramChapterIds"] == ["GCH-002"]


def test_auto_generation_records_no_diagram_for_unhelpful_chapters(model):
    model["chapters"][0]["mechanism"] = {"type": "plain_description"}
    model["chapters"][1]["confirmation"]["confirmed"] = False
    generated = auto_generate_diagrams(model, 4)
    assert generated["diagrams"] == []
    assert generated["diagramReview"] == {
        "status": "ready",
        "noDiagramChapterIds": ["GCH-001"],
        "sourceRevision": 4,
    }


def test_status_mechanism_without_formula_never_renders_placeholder_formula_or_internal_scope(model):
    model["chapters"] = [{
        "id": "GCH-001", "scope": "生命值状态管理", "plannerSummary": "受击时扣减生命值，归零时本局失败。",
        "claims": [], "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": [],
        "status": "approved", "confirmation": {"confirmed": True, "revision": 4},
        "mechanism": {"type": "buff_chain"}, "parameters": {},
    }]

    generated = auto_generate_diagrams(model, 4)

    assert generated["diagrams"] == []
    assert generated["diagramReview"]["noDiagramChapterIds"] == ["GCH-001"]


def test_regeneration_reclassifies_a_legacy_formula_diagram_from_current_planner_semantics(model):
    chapter = model["chapters"][0]
    chapter.update({
        "scope": "生命值状态管理",
        "plannerSummary": "受击时扣减生命值，生命值归零时本局失败。",
        "mechanism": {"type": "custom"},
        "parameters": {},
        "formulae": {"expression": "变化后生命值 = 变化前生命值 - 本次伤害"},
    })
    model["diagrams"] = [{
        "id": "GDI-001", "type": "formula", "chapterIds": ["GCH-001"], "status": "open",
        "revision": 1, "optional": True, "feedback": [],
    }]

    regenerated = regenerate_diagram(model, "GDI-001", "按当前策划语义重建", 4)

    diagram = regenerated["diagrams"][0]
    assert diagram["type"] == "effect_chain"
    assert diagram["interactionRevision"] == model["interactionRevision"]
    assert "scope:" not in diagram["svg"]
    assert "待确认" not in diagram["svg"]


def test_auto_generation_recovers_helpful_diagram_from_planner_copy_when_model_left_type_custom(model):
    model["chapters"] = [{
        "id": "GCH-001", "scope": "随机武器抽取", "plannerSummary": "玩家从候选池随机抽取一种武器。",
        "claims": [], "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": [],
        "status": "approved", "confirmation": {"confirmed": True, "revision": 4},
        "mechanism": {"type": "custom"}, "parameters": {},
    }]

    generated = auto_generate_diagrams(model, 4)

    assert generated["diagrams"] == []
    assert generated["diagramReview"]["noDiagramChapterIds"] == ["GCH-001"]


@pytest.mark.parametrize("status", ["open", "stale", "revising"])
def test_unsettled_diagram_states_block_export(model, status):
    model["diagrams"] = [{"id": "GDI-001", "type": "probability", "chapterIds": ["GCH-001"], "status": status, "optional": True, "interactionRevision": 3}]
    assert "GDI-001" in gameplay_gate(model, {"revision": 3})["blockers"]


def test_deleted_optional_diagram_does_not_block_export(model):
    model["diagrams"] = [{"id": "GDI-001", "type": "probability", "chapterIds": ["GCH-001"], "status": "deleted", "optional": True, "interactionRevision": 3}]
    assert "GDI-001" not in gameplay_gate(model, {"revision": 3})["blockers"]


def test_diagram_api_persists_generate_regenerate_and_approve(monkeypatch, model):
    from backend import server

    job = {"id": "job-diagrams", "archived": False, "gameplayReviewModel": model}
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    client = TestClient(server.app)

    response = client.post("/api/jobs/job-diagrams/gameplay-review-model/diagrams", json={"expectedRevision": 4, "chapterIds": ["GCH-001"], "diagramType": "probability"})
    assert response.status_code == 200
    diagram_id = response.json()["diagrams"][0]["id"]
    response = client.post(f"/api/jobs/job-diagrams/gameplay-review-model/diagrams/{diagram_id}/regenerate", json={"expectedRevision": 5, "feedback": "补空槽"})
    assert response.json()["diagrams"][0]["revision"] == 2
    response = client.post(f"/api/jobs/job-diagrams/gameplay-review-model/diagrams/{diagram_id}/approve", json={"expectedRevision": 6})
    assert response.json()["diagrams"][0]["status"] == "reviewed"


def test_generate_rejects_missing_chapter_ids_as_validation_error(model):
    with pytest.raises(ValueError, match="chapterIds"):
        generate_diagram(model, None, "probability", 4)


def test_deleted_optional_diagram_stays_deleted_after_source_chapter_edit(model):
    generated = generate_diagram(model, ["GCH-001"], "probability", 4)
    deleted = delete_diagram(generated, "GDI-001", 5)
    edited = apply_gameplay_operations(deleted, [{"type": "set_chapter_field", "chapterId": "GCH-001", "field": "scope", "value": "新范围"}], 6)
    assert edited["diagrams"][0]["status"] == "deleted"
    assert "GDI-001" not in gameplay_gate(edited, {"revision": 3})["blockers"]


def test_node_and_edge_ids_stay_bound_to_sources_across_reorder_and_insertion(model):
    forward = build_diagram(model, ["GCH-001", "GCH-002"], "state_flow")
    reverse = build_diagram(model, ["GCH-002", "GCH-001"], "state_flow")
    single = build_diagram(model, ["GCH-002"], "state_flow")

    def by_sources(items):
        return {tuple(item["sourceIds"]): item["id"] for item in items}

    assert by_sources(forward["nodes"]) == by_sources(reverse["nodes"])
    assert set(by_sources(single["nodes"]).items()) <= set(by_sources(forward["nodes"]).items())
    assert by_sources(forward["edges"]) == by_sources(reverse["edges"])


@pytest.mark.parametrize("operation", [
    {"type": "delete_chapter", "chapterId": "GCH-001"},
    {"type": "merge_chapters", "keepId": "GCH-002", "mergeId": "GCH-001"},
])
def test_deleted_optional_diagram_stays_terminal_when_source_chapter_is_removed(model, operation):
    generated = generate_diagram(model, ["GCH-001"], "probability", 4)
    deleted = delete_diagram(generated, "GDI-001", 5)
    changed = apply_gameplay_operations(deleted, [operation], 6)
    assert changed["diagrams"][0]["status"] == "deleted"
    assert "GDI-001" not in gameplay_gate(changed, {"revision": 3})["blockers"]
