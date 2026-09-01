"""Project-independent planner lessons that activate declarative runtime policies."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_SYSTEM_LESSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "planner_knowledge"
    / "system-lessons-v1.json"
)

_REQUIRED_FIELDS = {
    "lessonId",
    "sourceFeedbackIds",
    "lessonType",
    "problemPattern",
    "decisionLogic",
    "applicableScope",
    "nonApplicableScope",
    "affectedPipelineStages",
    "policyRefs",
    "testRefs",
    "status",
}
_STATUSES = {"candidate", "approved", "deprecated"}
_PROJECT_SPECIFIC_MARKERS = ("一路狂飙", "V2CH-", "GAP-YILU")
_PROJECT_RULE_ID = re.compile(r"\bRULE-[0-9A-F]{8,}\b")


def _non_empty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


@dataclass(frozen=True)
class SystemLessonRegistry:
    payload: dict[str, Any]
    lessons_by_id: dict[str, dict[str, Any]]
    policy_to_lessons: dict[str, tuple[str, ...]]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SystemLessonRegistry":
        if payload.get("schemaVersion") != "system-lessons-v1":
            raise ValueError("invalid schemaVersion")
        lessons = payload.get("lessons")
        if not isinstance(lessons, list):
            raise ValueError("lessons must be a list")

        lessons_by_id: dict[str, dict[str, Any]] = {}
        policy_to_lessons: dict[str, list[str]] = {}
        for index, lesson in enumerate(lessons):
            if not isinstance(lesson, dict):
                raise ValueError(f"lesson {index} must be an object")
            missing = sorted(field for field in _REQUIRED_FIELDS if not _non_empty(lesson.get(field)))
            if missing:
                raise ValueError(f"missing field: {', '.join(missing)}")
            lesson_id = str(lesson["lessonId"])
            if lesson_id in lessons_by_id:
                raise ValueError(f"duplicate lessonId: {lesson_id}")
            if lesson.get("status") not in _STATUSES:
                raise ValueError(f"invalid status: {lesson.get('status')}")
            serialized = json.dumps(lesson, ensure_ascii=False)
            if any(marker in serialized for marker in _PROJECT_SPECIFIC_MARKERS) or _PROJECT_RULE_ID.search(serialized):
                raise ValueError(f"project-specific content in {lesson_id}")
            for field in (
                "sourceFeedbackIds",
                "applicableScope",
                "nonApplicableScope",
                "affectedPipelineStages",
                "policyRefs",
                "testRefs",
            ):
                if not isinstance(lesson.get(field), list):
                    raise ValueError(f"{field} must be a list in {lesson_id}")
            lessons_by_id[lesson_id] = lesson
            for policy_ref in lesson["policyRefs"]:
                policy_to_lessons.setdefault(str(policy_ref), []).append(lesson_id)

        return cls(
            payload=payload,
            lessons_by_id=lessons_by_id,
            policy_to_lessons={key: tuple(value) for key, value in policy_to_lessons.items()},
        )

    @property
    def feedback_ids(self) -> frozenset[str]:
        return frozenset(
            str(feedback_id)
            for lesson in self.lessons_by_id.values()
            for feedback_id in lesson.get("sourceFeedbackIds", [])
        )

    def is_policy_enabled(self, policy_ref: str, stage: str, scope: str | None = None) -> bool:
        for lesson_id in self.policy_to_lessons.get(policy_ref, ()):
            lesson = self.lessons_by_id[lesson_id]
            if lesson.get("status") != "approved":
                continue
            if stage not in lesson.get("affectedPipelineStages", []):
                continue
            if scope and scope in lesson.get("nonApplicableScope", []):
                continue
            return True
        return False

    def feedback_policy_test_matrix(self) -> list[dict[str, Any]]:
        return [
            {
                "lessonId": lesson_id,
                "sourceFeedbackIds": list(lesson["sourceFeedbackIds"]),
                "lessonType": lesson["lessonType"],
                "policyRefs": list(lesson["policyRefs"]),
                "testRefs": list(lesson["testRefs"]),
                "status": lesson["status"],
            }
            for lesson_id, lesson in self.lessons_by_id.items()
        ]


def load_system_lesson_registry(path: Path | str | None = None) -> SystemLessonRegistry:
    source = Path(path) if path is not None else DEFAULT_SYSTEM_LESSON_PATH
    return SystemLessonRegistry.from_payload(json.loads(source.read_text(encoding="utf-8")))
