from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any, Iterable


SECONDARY_FIELDS = (
    "objectStates",
    "runtimeResponsibilities",
    "presentationRules",
)

_PUNCTUATION = re.compile(r"[\s，。；：、,.!?！？（）()\-—]")


def _normalized(value: Any) -> str:
    return _PUNCTUATION.sub("", str(value or "")).casefold()


def _text_leaves(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        if value.strip():
            yield value
        return
    if isinstance(value, dict):
        for child in value.values():
            yield from _text_leaves(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from _text_leaves(child)


def _planner_fact_keys(chapter: dict[str, Any]) -> set[str]:
    planner = chapter.get("plannerSections")
    if not isinstance(planner, dict):
        return set()
    return {
        key
        for text in _text_leaves(planner)
        if (key := _normalized(text))
    }


def _secondary_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("text", "description", "rule", "content", "summary"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _fact_id(chapter_id: str, text: str) -> str:
    digest = hashlib.sha1(_normalized(text).encode("utf-8")).hexdigest()[:10]
    return f"FACT-{chapter_id}-{digest}"


def normalize_delivery_carriers(model: dict[str, Any]) -> dict[str, Any]:
    """Keep each publishable fact in one primary prose carrier.

    Planner prose owns facts intended for the final document. Identical copies in
    secondary review/runtime fields become stable references. Distinct secondary
    responsibilities remain untouched.
    """

    result = deepcopy(model)
    for chapter in result.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id") or "chapter")
        primary = _planner_fact_keys(chapter)
        refs = [item for item in chapter.get("carrierRefs") or [] if isinstance(item, dict)]
        existing_refs = {
            (str(item.get("field") or ""), str(item.get("factId") or ""))
            for item in refs
        }
        for field in SECONDARY_FIELDS:
            kept: list[Any] = []
            values = chapter.get(field)
            values = values if isinstance(values, list) else []
            for item in values:
                text = _secondary_text(item)
                fact_id = _fact_id(chapter_id, text) if text else ""
                if text and _normalized(text) in primary:
                    ref_key = (field, fact_id)
                    if ref_key not in existing_refs:
                        refs.append({"field": field, "factId": fact_id})
                        existing_refs.add(ref_key)
                else:
                    kept.append(item)
            chapter[field] = kept
        chapter["carrierRefs"] = refs
    return result


def carrier_policy_report(model: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        primary = _planner_fact_keys(chapter)
        for field in SECONDARY_FIELDS:
            values = chapter.get(field)
            values = values if isinstance(values, list) else []
            for item in values:
                text = _secondary_text(item)
                if text and _normalized(text) in primary:
                    findings.append(
                        {
                            "chapterId": chapter.get("id"),
                            "field": field,
                            "code": "CARRIER_DUPLICATE_PRIMARY_FACT",
                            "action": "保留一个正文主载体，其他字段改为 factId 引用。",
                        }
                    )
    return {"passed": not findings, "findings": findings}
