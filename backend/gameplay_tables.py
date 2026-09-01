from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .gameplay_review_service import GameplayReviewConflict


def _require_revision(model: dict[str, Any], expected_revision: int) -> None:
    if type(expected_revision) is not int or expected_revision != model.get("revision"):
        raise GameplayReviewConflict(model.get("revision", 0))


def _finish(model: dict[str, Any]) -> dict[str, Any]:
    model["revision"] += 1
    model.setdefault("reviewState", {})["previewRevision"] = None
    return model


def _text(value: Any, fallback: str = "") -> str:
    value = str(value or "").strip()
    return value if value and value not in {"待确认", "未知", "undefined", "null"} else fallback


def _schema_items(chapter: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    schema = chapter.get("parameterSchema") or chapter.get("parameters") or []
    if isinstance(schema, dict):
        return [(str(name), value if isinstance(value, dict) else {"value": value}) for name, value in schema.items()]
    if isinstance(schema, list):
        return [(_text(item.get("name") or item.get("title")), item) for item in schema if isinstance(item, dict) and _text(item.get("name") or item.get("title"))]
    return []


def _explicit(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return ""


def _concrete(value: str) -> bool:
    return bool(value and value not in {"—", "数值", "按实际配置", "需要策划决定", "待确认"})


def _qualified_parameter(data: dict[str, Any]) -> bool:
    source = _explicit(data, "configurationSource", "deliverySource", "source")
    if source.startswith(("需要结合", "需要策划", "待补充")):
        source = ""
    evidence = _explicit(data, "evidenceLevel")
    concrete_fields = [_explicit(data, key) for key in ("type", "unit", "value", "defaultValue", "default")]
    is_supported = source or any(marker in evidence for marker in ("素材明确", "参考文档明确", "策划人工"))
    return bool(is_supported and any(_concrete(value) for value in concrete_fields))


def _qualified_attribute(data: dict[str, Any]) -> bool:
    category = _explicit(data, "category", "attributeCategory")
    source = _explicit(data, "deliverySource", "configurationSource", "source")
    return bool(category and source)


def _formula_source(data: dict[str, Any]) -> str:
    source = _explicit(data, "configurationSource", "source")
    if source:
        return source
    evidence = _explicit(data, "evidenceLevel")
    return evidence if any(marker in evidence for marker in ("素材明确", "参考文档明确", "策划人工")) else ""


def _rows(chapter: dict[str, Any]) -> tuple[list[list[str]], list[dict[str, str]]]:
    rows: list[list[str]] = []
    details: list[dict[str, str]] = []
    for name, data in _schema_items(chapter):
        if not _qualified_parameter(data):
            continue
        value = _text(data.get("value") or data.get("defaultValue") or data.get("default"), "—")
        value_type = _text(data.get("type"), "数值")
        unit = _text(data.get("unit"))
        source = _text(data.get("configurationSource") or data.get("deliverySource") or data.get("source") or data.get("evidenceLevel"), "需要策划补充来源")
        meaning = _text(data.get("plannerMeaning") or data.get("meaning") or data.get("description"), name)
        rows.append([name, f"{value_type}（{unit}）" if unit else value_type, value, value, "待确认", "确认"])
        details.append({"field": name, "purpose": meaning, "basis": source, "source": source,
                        "formula": _text(data.get("formula") or data.get("calculation"))})
    for index, formula in enumerate(chapter.get("formulae") or [], 1):
        data = formula if isinstance(formula, dict) else {"expression": formula}
        expression = _text(data.get("formula") or data.get("expression"))
        source = _formula_source(data)
        if expression and source:
            field = _text(data.get("name"), f"计算公式{index}")
            rows.append([field, "公式", expression, expression, "待确认", "确认"])
            details.append({"field": field, "purpose": _text(data.get("meaning"), "计算关系"),
                            "basis": source, "source": source, "formula": expression})
    return rows, details


def _chapter_category(model: dict[str, Any], chapter: dict[str, Any]) -> str:
    chapter_id = chapter.get("id")
    for system in model.get("systems") or []:
        for subsystem in system.get("subsystems") or []:
            if chapter_id in (subsystem.get("chapterIds") or []):
                return _text(subsystem.get("name") or system.get("name"), _text(chapter.get("scope"), "玩法属性"))
    return _text(chapter.get("subsystemName") or chapter.get("systemName") or chapter.get("scope"), "玩法属性")


def _attribute_catalog(model: dict[str, Any], chapters: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for chapter in chapters:
        for name, data in _schema_items(chapter):
            if not _qualified_attribute(data):
                continue
            category = _explicit(data, "category", "attributeCategory")
            if (category, name) in seen:
                continue
            seen.add((category, name))
            rows.append([category, name, _text(data.get("plannerMeaning") or data.get("meaning") or data.get("description"), name),
                         _explicit(data, "deliverySource", "configurationSource", "source")])
    return rows


def _calculation_legend(chapters: list[dict[str, Any]]) -> list[list[str]]:
    expressions: list[str] = []
    for chapter in chapters:
        for formula in chapter.get("formulae") or []:
            data = formula if isinstance(formula, dict) else {"expression": formula}
            expression = _text(data.get("formula") or data.get("expression"))
            source = _formula_source(data)
            if expression and source:
                expressions.append(expression)
    rows: list[list[str]] = []
    if expressions:
        rows.append(["计算关系", "属性之间的计算顺序或换算方式", "；".join(dict.fromkeys(expressions))])
    return rows


def _next_id(tables: list[dict[str, Any]]) -> str:
    used = {item.get("id") for item in tables}
    number = 1
    while f"GTB-{number:03d}" in used:
        number += 1
    return f"GTB-{number:03d}"


def auto_generate_tables(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result = deepcopy(model)
    tables = result.setdefault("tables", [])
    confirmed = [chapter for chapter in result.get("chapters") or [] if isinstance(chapter, dict) and (chapter.get("confirmation") or {}).get("confirmed")]
    generated_by_chapter = {chapter.get("id"): _rows(chapter) for chapter in confirmed}
    qualified_by_chapter = {chapter_id: value[0] for chapter_id, value in generated_by_chapter.items()}
    generated_kinds = {"chapter_parameters", "attribute_catalog", "calculation_legend"}
    for item in tables:
        if not isinstance(item, dict) or item.get("status") == "deleted":
            continue
        kind = item.get("kind")
        chapter_ids = item.get("chapterIds") or []
        is_generated_chapter_table = kind == "chapter_parameters" or (not kind and len(chapter_ids) == 1 and str(item.get("title") or "").endswith("参数表"))
        if is_generated_chapter_table and not qualified_by_chapter.get(chapter_ids[0] if chapter_ids else None):
            item["status"] = "deleted"
        elif kind in {"attribute_catalog", "calculation_legend"}:
            item["status"] = "deleted"
    existing = {tuple(item.get("chapterIds") or []): item for item in tables
                if isinstance(item, dict) and item.get("status") != "deleted" and item.get("kind") not in {"attribute_catalog", "calculation_legend"}}
    no_table: list[str] = []
    for chapter in confirmed:
        chapter_id = chapter.get("id")
        rows = qualified_by_chapter.get(chapter_id) or []
        row_details = (generated_by_chapter.get(chapter_id) or ([], []))[1]
        if not rows:
            no_table.append(chapter_id)
            continue
        if (chapter_id,) in existing:
            current = existing[(chapter_id,)]
            if current.get("rows") != rows:
                current.update({"kind": "chapter_parameters", "title": f"{chapter.get('scope') or '玩法章节'}参数表",
                                "columns": ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"],
                                "rows": rows, "rowDetails": row_details, "status": "open", "revision": current.get("revision", 1) + 1})
            continue
        tables.append({"id": _next_id(tables), "kind": "chapter_parameters", "title": f"{chapter.get('scope') or '玩法章节'}参数表",
                       "chapterIds": [chapter_id], "columns": ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"],
                       "rows": rows, "rowDetails": row_details, "status": "open", "revision": 1, "optional": True, "feedback": []})
    chapter_ids = [chapter.get("id") for chapter in confirmed if chapter.get("id")]
    specs = [("attribute_catalog", "属性分类与投放来源", ["属性分类", "属性", "属性说明", "投放来源"], _attribute_catalog(result, confirmed)),
             ("calculation_legend", "属性与计算关系图例", ["图例", "表示内容", "当前素材中的对应项"], _calculation_legend(confirmed))]
    for kind, title, columns, rows in specs:
        if not rows:
            continue
        previous = next((item for item in tables if item.get("kind") == kind and item.get("status") != "deleted"), None)
        if previous:
            if previous.get("status") != "reviewed":
                previous.update({"title": title, "columns": columns, "rows": rows, "chapterIds": chapter_ids})
            continue
        tables.append({"id": _next_id(tables), "kind": kind, "title": title, "chapterIds": chapter_ids, "columns": columns, "rows": rows,
                       "status": "open", "revision": 1, "optional": False, "feedback": []})
    result["tableReview"] = {"status": "ready", "noTableChapterIds": no_table, "sourceRevision": model.get("revision")}
    return _finish(result)


def table_action(model: dict[str, Any], table_id: str, action: str, expected_revision: int, feedback: str = "") -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result = deepcopy(model)
    table = next((item for item in result.get("tables") or [] if isinstance(item, dict) and item.get("id") == table_id), None)
    if not table:
        raise ValueError(f"unknown table: {table_id}")
    if action == "approve":
        columns = table.get("columns") or []
        rows = table.get("rows") or []
        requires_row_review = table.get("kind") == "chapter_parameters" or "状态" in columns
        confirmed_rows = {index for index, row in enumerate(rows) if len(row) > 4 and row[4] == "已确认"}
        confirmed_rows.update({int(item.get("rowIndex")) for item in table.get("rowReviews") or [] if item.get("confirmed") and str(item.get("rowIndex", "")).isdigit()})
        if requires_row_review and (not rows or len(confirmed_rows) != len(rows)):
            raise ValueError("all table rows must be confirmed before approval")
        table["status"] = "reviewed"
    elif action == "delete":
        table["status"] = "deleted"
    elif action == "regenerate":
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("feedback is required")
        table.setdefault("feedback", []).append({"text": feedback.strip(), "tableRevision": table.get("revision", 1)})
        table["revision"] = table.get("revision", 1) + 1
        table["status"] = "open"
    elif action == "confirm_row":
        try:
            payload = json.loads(feedback)
            row_index = int(payload["rowIndex"])
            value = str(payload.get("value", "")).strip()
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise ValueError("row confirmation is invalid") from error
        if row_index < 0 or row_index >= len(table.get("rows") or []):
            raise ValueError("row confirmation is out of range")
        reviews = table.setdefault("rowReviews", [])
        reviews[:] = [item for item in reviews if item.get("rowIndex") != row_index]
        reviews.append({"rowIndex": row_index, "value": value, "confirmed": True})
        table["status"] = "open"
    else:
        raise ValueError("unsupported table action")
    return _finish(result)
