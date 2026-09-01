import json
from copy import deepcopy
from pathlib import Path
import re

import pytest

from backend.system_lesson_registry import SystemLessonRegistry, load_system_lesson_registry


ROOT = Path(__file__).resolve().parents[1]


def _payload(*, status: str = "approved") -> dict:
    return {
        "schemaVersion": "system-lessons-v1",
        "lessons": [
            {
                "lessonId": "LESSON-EVIDENCE-AUTHORITY",
                "sourceFeedbackIds": ["PF-GENERIC-01"],
                "lessonType": "evidence_authority",
                "problemPattern": "Observed sequences are promoted beyond their evidence authority.",
                "decisionLogic": "Keep observed values, patterns, configured values, and formulas distinct.",
                "applicableScope": ["gameplay_analysis"],
                "nonApplicableScope": ["explicit_formula_source"],
                "affectedPipelineStages": ["evidence_guard"],
                "policyRefs": ["guard.pattern_formula"],
                "testRefs": ["tests/test_system_lesson_registry.py::test_only_approved_lesson_enables_policy"],
                "status": status,
            }
        ],
    }


def test_only_approved_lesson_enables_policy():
    approved = SystemLessonRegistry.from_payload(_payload())
    candidate = SystemLessonRegistry.from_payload(_payload(status="candidate"))

    assert approved.is_policy_enabled("guard.pattern_formula", "evidence_guard") is True
    assert candidate.is_policy_enabled("guard.pattern_formula", "evidence_guard") is False


def test_stage_and_non_applicable_scope_limit_policy_activation():
    registry = SystemLessonRegistry.from_payload(_payload())

    assert registry.is_policy_enabled("guard.pattern_formula", "renderer") is False
    assert registry.is_policy_enabled(
        "guard.pattern_formula", "evidence_guard", scope="explicit_formula_source"
    ) is False


def test_lessons_are_project_independent_and_cover_all_recorded_feedback_items():
    registry = load_system_lesson_registry()
    serialized = json.dumps(registry.payload, ensure_ascii=False)

    assert len(registry.feedback_ids) == 16
    assert len(registry.lessons_by_id) == 15
    assert registry.is_policy_enabled(
        "interaction.evidence_modality_boundary", "interaction_analysis", scope="screenshot_sequence"
    ) is True
    assert "一路狂飙" not in serialized
    assert re.search(r"\bRULE-[0-9A-F]{8,}\b", serialized) is None


def test_feedback_policy_test_matrix_is_complete_for_every_approved_lesson():
    matrix = load_system_lesson_registry().feedback_policy_test_matrix()

    assert len(matrix) == 15
    assert all(row["sourceFeedbackIds"] for row in matrix)
    assert all(row["policyRefs"] for row in matrix)
    assert all(row["testRefs"] for row in matrix)
    assert all(row["status"] == "approved" for row in matrix)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload["lessons"].append(deepcopy(payload["lessons"][0])), "duplicate lessonId"),
        (lambda payload: payload["lessons"][0].update(status="active"), "invalid status"),
        (lambda payload: payload["lessons"][0].pop("decisionLogic"), "missing field"),
        (lambda payload: payload["lessons"][0].update(problemPattern="一路狂飙专用逻辑"), "project-specific"),
    ],
)
def test_invalid_lesson_payload_is_rejected(mutation, message):
    payload = _payload()
    mutation(payload)

    with pytest.raises(ValueError, match=message):
        SystemLessonRegistry.from_payload(payload)
