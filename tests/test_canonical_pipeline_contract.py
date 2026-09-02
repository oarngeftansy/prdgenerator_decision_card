from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from backend.canonical_pipeline import (
    PIPELINE_STAGE_ORDER,
    CanonicalPipelineError,
    assemble_validate_render,
    build_gameplay_understanding_model,
    build_interaction_model,
    build_p1_directory_projection,
    build_p2_interaction_projection,
    build_p5_diagram_projection,
    build_p6_parameter_projection,
    build_publication_input_snapshot,
)


EXPECTED_ORDER = (
    "gameplay_understanding",
    "interaction_model",
    "p1_directory_projection",
    "p2_interaction_projection",
    "p3_planning_snapshot",
    "execution_planning",
    "execution_rule_model",
    "p4_review",
    "p5_diagram_projection",
    "p6_parameter_projection",
    "publication_input_snapshot",
    "p7_assemble_validate_render",
)


def _execution_rule_model() -> dict:
    return {
        "version": "execution_rule_model_v1",
        "digest": "erm-digest",
        "chapters": [{
            "chapterId": "CH-MOVE",
            "system": "角色",
            "object": "移动",
            "title": "移动规则",
        }],
        "rules": [{
            "ruleId": "R-MOVE",
            "ownerChapterId": "CH-MOVE",
            "canonicalOwner": "CH-MOVE",
            "subject": "角色",
            "behavior": "收到方向输入后更新到下一个合法位置",
            "trigger": "方向输入变化",
            "conditions": ["目标位置可通行"],
            "result": "角色位置更新",
            "ruleType": "logic",
            "semanticValidity": "valid",
            "reviewStatus": "confirmed",
            "confirmationStatus": "confirmed",
            "publicationEligibility": "eligible",
            "publicationState": "confirmed",
        }],
        "ruleGroups": [],
        "mechanicFlows": [],
        "gaps": [],
        "finalPlanningGaps": [],
        "masterPlanner": {"status": "completed", "decisionCount": 0},
    }


def test_canonical_stage_order_is_frozen() -> None:
    assert PIPELINE_STAGE_ORDER == EXPECTED_ORDER
    assert PIPELINE_STAGE_ORDER.index("interaction_model") < PIPELINE_STAGE_ORDER.index("execution_planning")
    assert PIPELINE_STAGE_ORDER.index("execution_rule_model") < PIPELINE_STAGE_ORDER.index("p4_review")
    assert PIPELINE_STAGE_ORDER.index("p6_parameter_projection") < PIPELINE_STAGE_ORDER.index("publication_input_snapshot")
    assert PIPELINE_STAGE_ORDER[-1] == "p7_assemble_validate_render"


def test_understanding_and_interaction_are_first_class_pre_planning_models() -> None:
    gameplay = {
        "revision": 11,
        "directory": {
            "revision": 4,
            "understanding": {
                "Summary": "移动与场景探索",
                "CoreLoop": ["观察", "移动", "到达"],
                "Systems": [{"id": "SYS-MOVE", "name": "移动"}],
                "Mechanisms": [{"mechanicId": "MOVE"}],
            },
        },
        "chapters": [{"id": "GCH-001", "scope": "移动"}],
    }
    understanding = build_gameplay_understanding_model(gameplay)
    interaction = build_interaction_model(understanding, {
        "revision": 7,
        "stages": [{"id": "ST-1", "title": "移动输入"}],
        "transitions": [{"from": "idle", "to": "moving"}],
    })
    p1 = build_p1_directory_projection(understanding)
    p2 = build_p2_interaction_projection(interaction)

    assert understanding["version"] == "gameplay_understanding_model_v1_2"
    assert interaction["version"] == "interaction_model_v2"
    assert interaction["understandingDigest"] == understanding["digest"]
    assert p1["sourceDigest"] == understanding["digest"]
    assert p2["sourceDigest"] == interaction["digest"]
    assert p2["stages"][0]["id"] == "ST-1"


def test_p5_and_p6_are_read_only_projections_of_execution_rule_model() -> None:
    erm = _execution_rule_model()
    before = deepcopy(erm)
    gameplay = {
        "diagrams": [{"id": "D-1", "status": "reviewed"}],
        "diagramReview": {"revision": 2},
        "tables": [{"id": "T-1", "status": "reviewed"}],
        "chapters": [{
            "id": "GCH-001",
            "parameterSchema": [{"name": "移动速度", "type": "number"}],
            "formulae": [],
        }],
    }
    p5 = build_p5_diagram_projection(gameplay, erm)
    p6 = build_p6_parameter_projection(gameplay, erm)

    assert erm == before
    assert p5["executionRuleDigest"] == erm["digest"]
    assert p6["executionRuleDigest"] == erm["digest"]
    assert "rules" not in p5
    assert "rules" not in p6


def test_publication_snapshot_is_deep_copied_and_rejects_stale_projection() -> None:
    erm = _execution_rule_model()
    understanding = {"digest": "understanding-digest"}
    interaction = {"digest": "interaction-digest"}
    p4 = {
        "version": "p4_execution_review_v1",
        "executionRuleDigest": erm["digest"],
        "ready": True,
        "qualityJudge": {"ready": True},
        "planningSketch": {"version": "planning_sketch_v2", "contexts": []},
    }
    p5 = {"executionRuleDigest": erm["digest"], "diagrams": [], "digest": "p5"}
    p6 = {"executionRuleDigest": erm["digest"], "tables": [], "digest": "p6"}
    snapshot = build_publication_input_snapshot(understanding, interaction, erm, p4, p5, p6)

    erm["rules"][0]["behavior"] = "MUTATED AFTER SNAPSHOT"
    assert snapshot["executionRuleModel"]["rules"][0]["behavior"] != "MUTATED AFTER SNAPSHOT"
    assert snapshot["digest"]

    stale = {**p5, "executionRuleDigest": "different"}
    with pytest.raises(CanonicalPipelineError, match="P5 diagram projection is stale"):
        build_publication_input_snapshot(understanding, interaction, _execution_rule_model(), p4, stale, p6)


def test_p7_is_pure_snapshot_consumer_without_provider_or_transport_arguments() -> None:
    assert tuple(inspect.signature(assemble_validate_render).parameters) == ("snapshot",)
    erm = _execution_rule_model()
    snapshot = {
        "version": "publication_input_snapshot_v1",
        "digest": "snapshot-digest",
        "executionRuleModel": erm,
        "p4Review": {"ready": True, "qualityJudge": {"ready": True}},
        "p5DiagramProjection": {"executionRuleDigest": erm["digest"], "diagrams": []},
        "p6ParameterProjection": {"executionRuleDigest": erm["digest"], "tables": []},
        "planningSketch": {"version": "planning_sketch_v2", "contexts": []},
    }
    p7 = assemble_validate_render(snapshot)

    assert p7["publicationInputDigest"] == "snapshot-digest"
    assert p7["document"]["systems"]
    assert "收到方向输入后更新到下一个合法位置" in p7["markdown"]
    assert p7["previewHtml"]
    assert p7["feishuXml"]
