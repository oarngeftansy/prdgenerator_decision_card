from __future__ import annotations

from typing import Any


_REVIEWABLE_DETAIL_STATUSES = {
    "chapter_review",
    "diagram_review",
    "table_review",
    "preview",
    "preview_ready",
}
_CHAPTER_DETAIL_FIELDS = {
    "claims",
    "evidenceClaims",
    "mechanism",
    "parameters",
    "formulae",
    "dependencies",
    "acceptanceCases",
    "executionSequence",
    "objectStates",
    "interactionFeedback",
    "runtimeResponsibilities",
    "presentationRules",
    "lifecycleRules",
    "domainStates",
    "requiredResponsibilities",
}
_PLANNER_SECTION_FIELDS = {
    "summary",
    "normalFlow",
    "keyRules",
    "specialCases",
    "attributeSections",
    "acceptanceExamples",
}
_STRUCTURAL_METADATA_KEYS = {
    "id",
    "status",
    "type",
    "sourceType",
    "schemaVersion",
    "revision",
    "order",
    "frameId",
    "chapterId",
    "systemId",
    "subsystemId",
    "sourceFrameIds",
}


def _has_meaningful_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return any(
            _has_meaningful_value(item)
            for key, item in value.items()
            if key not in _STRUCTURAL_METADATA_KEYS
        )
    return value is not None


def _chapter_has_reviewable_detail(chapter: Any) -> bool:
    if not isinstance(chapter, dict):
        return False
    if any(_has_meaningful_value(chapter.get(field)) for field in _CHAPTER_DETAIL_FIELDS):
        return True
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    return any(_has_meaningful_value(planner.get(field)) for field in _PLANNER_SECTION_FIELDS)


def gameplay_model_has_reviewable_detail(model: Any, *, expected_job_id: str | None = None) -> bool:
    if not isinstance(model, dict):
        return False
    model_job_id = model.get("jobId")
    if not isinstance(model_job_id, str) or not model_job_id.strip():
        return False
    if expected_job_id is not None and model_job_id != expected_job_id:
        return False
    review_state = model.get("reviewState") if isinstance(model.get("reviewState"), dict) else {}
    if review_state.get("status") not in _REVIEWABLE_DETAIL_STATUSES:
        return False
    return any(_chapter_has_reviewable_detail(chapter) for chapter in model.get("chapters") or [])
