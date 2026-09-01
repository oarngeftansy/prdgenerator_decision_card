from __future__ import annotations

import re
from typing import Any

from .granularity_audit import granularity_audit_report
from .feishu_language_quality import language_quality_report
from .planning_content_policy import carrier_policy_report
from .gameplay_domain_policy import provenance_scope_report


_SCREEN_CAPTION = re.compile(
    r"(?:^|[。；])\s*(?:从|根据)?(?:画面|屏幕|截图)(?:中|上)?(?:可以看到|可见|显示|展示|出现)",
    re.I,
)
_INTERNAL_LANGUAGE = re.compile(
    r"(?:\b(?:unknown|component|entry|result|connected|pending|mechanismType)\b|(?:SCN|EVT|TRN|CMP|GCH|GDE)-\d+|undefined)",
    re.I,
)
_GENERIC_SUMMARY = re.compile(r"^(?:待确认|.+的玩法规则[。.]?|请确认.+|本章将说明.+)$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def lead_planner_preflight(job: dict[str, Any], phase: str, structure_model: dict[str, Any] | None = None) -> list[str]:
    """Checks the evidence and confirmed structure before any model generation call."""
    errors: list[str] = []
    frames = [item for item in job.get("frames") or [] if isinstance(item, dict) and _text(item.get("id"))]
    if not frames:
        errors.append("LEAD_PLANNER_INPUT_HAS_NO_EVIDENCE")
    if phase == "details":
        model = structure_model or {}
        directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
        if directory.get("status") != "confirmed":
            errors.append("LEAD_PLANNER_DIRECTORY_NOT_CONFIRMED")
        chapters = [item for item in model.get("chapters") or [] if isinstance(item, dict)]
        if not chapters:
            errors.append("LEAD_PLANNER_STRUCTURE_EMPTY")
        for chapter in chapters:
            if not _text(chapter.get("systemName")) or not _text(chapter.get("subsystemName")) or not _text(chapter.get("scope")):
                errors.append("LEAD_PLANNER_STRUCTURE_LEVEL_MISSING")
                break
    return list(dict.fromkeys(errors))


def lead_planner_output_audit(
    model: dict[str, Any],
    phase: str,
    *,
    allow_pending_decisions: bool = False,
) -> list[str]:
    """Audits planner-visible copy; evidence captions are intentionally excluded."""
    errors: list[str] = []
    directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
    understanding = directory.get("understanding") if isinstance(directory.get("understanding"), dict) else {}
    visible_texts: list[tuple[str, str]] = [("directory.overview", _text(understanding.get("summary")))]
    for entry in directory.get("entries") or []:
        if isinstance(entry, dict):
            visible_texts.append((f"directory.{_text(entry.get('id'))}", _text(entry.get("summary"))))
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = _text(chapter.get("id")) or "chapter"
        visible_texts.append((f"{chapter_id}.plannerSummary", _text(chapter.get("plannerSummary"))))
        sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        visible_texts.append((f"{chapter_id}.summary", _text(sections.get("summary"))))
        for section_name in ("normalFlow", "keyRules", "specialCases"):
            for index, item in enumerate(sections.get(section_name) or []):
                visible_texts.append((f"{chapter_id}.{section_name}[{index}]", _text(item)))
        for group_index, group in enumerate(sections.get("attributeSections") or []):
            if not isinstance(group, dict):
                continue
            visible_texts.append((f"{chapter_id}.attributeSections[{group_index}].heading", _text(group.get("heading") or group.get("title"))))
            for item_index, item in enumerate(group.get("items") or []):
                visible_texts.append((f"{chapter_id}.attributeSections[{group_index}].items[{item_index}]", _text(item)))

    for location, text in visible_texts:
        if not text:
            continue
        if _INTERNAL_LANGUAGE.search(text):
            errors.append(f"{location}:LEAD_PLANNER_INTERNAL_LANGUAGE")
        if _SCREEN_CAPTION.search(text):
            errors.append(f"{location}:LEAD_PLANNER_SCREEN_CAPTION_AS_RULE")
        if _GENERIC_SUMMARY.fullmatch(text):
            errors.append(f"{location}:LEAD_PLANNER_RULE_TOO_SHALLOW")

    chapters = [item for item in model.get("chapters") or [] if isinstance(item, dict)]
    if chapters and not model.get("systems"):
        errors.append("LEAD_PLANNER_SYSTEM_HIERARCHY_MISSING")
    if phase == "details":
        for chapter in chapters:
            sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
            depth_categories = sum(bool(sections.get(key)) for key in ("normalFlow", "keyRules", "specialCases", "attributeSections", "acceptanceExamples"))
            depth_categories += int(bool(chapter.get("parameterSchema") or chapter.get("parameters")))
            depth_categories += int(bool(chapter.get("formulae") or chapter.get("workedExamples")))
            if allow_pending_decisions:
                reviewable_cards = [
                    card for card in chapter.get("decisionCards") or []
                    if isinstance(card, dict)
                    and card.get("status") == "pending"
                    and str(card.get("question") or "").strip()
                    and len([option for option in card.get("options") or [] if isinstance(option, dict)]) >= 2
                ]
                depth_categories += int(bool(reviewable_cards))
            if depth_categories < 2:
                errors.append(f"{_text(chapter.get('id'))}:LEAD_PLANNER_RULE_DEPTH_INSUFFICIENT")
    if phase == "details":
        errors.extend(
            f"{item['chapterId']}:{item['code']}"
            for item in granularity_audit_report(model)["findings"]
        )
        errors.extend(
            f"{item['chapterId']}:{item['code']}"
            for item in language_quality_report(model)["findings"]
        )
        errors.extend(
            f"{item['chapterId']}:{item['code']}"
            for item in carrier_policy_report(model)["findings"]
        )
        errors.extend(
            f"{item['chapterId']}:{item['code']}"
            for item in provenance_scope_report(model)["findings"]
        )
    return list(dict.fromkeys(errors))


def assert_lead_planner_ready(job: dict[str, Any], phase: str, structure_model: dict[str, Any] | None = None) -> None:
    errors = lead_planner_preflight(job, phase, structure_model)
    if errors:
        raise ValueError("; ".join(errors))


def assert_lead_planner_output(model: dict[str, Any], phase: str) -> None:
    errors = lead_planner_output_audit(model, phase)
    if errors:
        raise ValueError("; ".join(errors[:20]))
