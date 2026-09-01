from __future__ import annotations

from copy import deepcopy
from html import escape
import re
from typing import Any

from .gameplay_review_service import GameplayReviewConflict


SUPPORTED_TYPES = {"spatial", "state_flow", "probability", "effect_chain", "formula"}
HELPFUL_FOR = {
    "spatial": {"spatial_drag", "entity_behavior", "level_wave"},
    "state_flow": {"core_loop", "level_wave", "settlement", "external_entry", "statistics_feedback"},
    "probability": {"random_pool"},
    "effect_chain": {"entity_behavior", "buff_chain", "economy_reward", "progression"},
    "formula": {"formula"},
}
AUTO_TYPE_ORDER = ("formula", "probability", "spatial", "state_flow", "effect_chain")


def _planner_inferred_diagram_type(chapter: dict[str, Any]) -> str | None:
    """Recover a useful diagram choice when the model kept the generic custom type."""
    sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    text = "；".join(str(value) for value in (
        chapter.get("scope"), chapter.get("plannerSummary"), sections.get("summary"),
        sections.get("normalFlow"), sections.get("keyRules"),
    ) if value)
    if re.search(r"随机|抽取|概率|权重|候选池|刷新候选", text):
        return "probability"
    if re.search(r"移动|拖动|摆放|空间|位置|范围|边界", text):
        return "spatial"
    if re.search(r"强化|效果|状态|生命值|增益|减益|持续时间", text):
        return "effect_chain"
    if re.search(r"阶段|关卡|流程|登场|胜利|失败|结算|退出|重进", text):
        return "state_flow"
    if chapter.get("formulae") or re.search(r"公式|计算顺序|取整|伤害计算", text):
        return "formula"
    return None


def _chapter(model: dict[str, Any], chapter_id: str) -> dict[str, Any]:
    chapter = next((item for item in model.get("chapters") or [] if isinstance(item, dict) and item.get("id") == chapter_id), None)
    if not chapter:
        raise ValueError(f"unknown chapter: {chapter_id}")
    return chapter


def _value(parameter: Any) -> str:
    if not isinstance(parameter, dict):
        return str(parameter or "")
    value = parameter.get("value")
    return str(value if value not in (None, "") else "")


_FIELD_LABELS = {
    "objects": "操作对象", "legalRegion": "可活动区域", "matchRule": "判定规则",
    "bounds": "边界", "failureReturn": "失败后的处理", "trigger": "何时发生",
    "phaseOrder": "阶段顺序", "completion": "完成条件", "failure": "失败条件",
    "reset": "重置方式", "entry": "进入条件", "exit": "结束去向", "eligibility": "可进入候选的内容",
    "exclusions": "排除条件", "weightFormula": "抽取权重", "drawOrder": "抽取顺序",
    "emptyResult": "无结果时的处理", "confirm": "确认后的结果", "reroll": "刷新规则",
    "target": "作用目标", "calculation": "效果计算", "stacks": "叠加规则",
    "duration": "持续时间", "replacement": "替换规则", "removal": "移除条件", "effect": "实际效果",
    "formula": "计算公式", "inputs": "参与计算的数值", "units": "单位", "ranges": "取值范围",
    "stackOrder": "计算顺序", "rounding": "取整方式", "example": "计算示例", "configSource": "配置来源",
}


def _safe_label(value: Any) -> str:
    return str(value or "待确认").replace("<", "‹").replace(">", "›").replace('"', "'").replace("[", "（").replace("]", "）").replace("\n", " ")


def _fields(chapter: dict[str, Any], diagram_type: str) -> list[tuple[str, str]]:
    parameters = chapter.get("parameters") or {}
    preferred = {
        "spatial": ("objects", "legalRegion", "matchRule", "bounds", "failureReturn"),
        "state_flow": ("trigger", "phaseOrder", "completion", "failure", "reset", "entry", "exit"),
        "probability": ("eligibility", "exclusions", "weightFormula", "drawOrder", "emptyResult", "confirm", "reroll"),
        "effect_chain": ("target", "trigger", "calculation", "stacks", "duration", "replacement", "removal", "effect"),
        "formula": ("formula", "inputs", "units", "ranges", "stackOrder", "rounding", "example", "configSource"),
    }[diagram_type]
    values = [(_FIELD_LABELS.get(name, name), _value(parameters[name])) for name in preferred if name in parameters and _value(parameters[name])]
    if values:
        return values
    fallback = [(str(name), _value(value)) for name, value in list(parameters.items())[:7] if _value(value)]
    if fallback:
        return fallback
    summary = str(chapter.get("plannerSummary") or "").strip()
    return [("玩法说明", summary)] if summary and diagram_type != "formula" else []


def _has_visual_structure(chapters: list[dict[str, Any]], diagram_type: str) -> bool:
    """Only keep diagrams that communicate a relationship better than plain text."""
    if diagram_type == "formula":
        return False
    field_count = sum(len(_fields(chapter, diagram_type)) for chapter in chapters)
    chapter_ids = {chapter.get("id") for chapter in chapters}
    has_cross_chapter_relation = any(
        dependency in chapter_ids
        for chapter in chapters
        for dependency in (chapter.get("dependencies") or [])
    )
    return field_count >= 2 or has_cross_chapter_relation


def _svg_has_relationship(svg: Any) -> bool:
    value = str(svg or "")
    return bool(re.search(r"<(?:line|path|polyline|polygon)\b", value, re.IGNORECASE))


def _id_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")


def _node_id(source_id: str) -> str:
    return f"GDI-N-{_id_part(source_id)}"


def _edge_id(source_id: str, target_id: str, role: str) -> str:
    return f"GDI-E-{_id_part(source_id)}--{_id_part(role)}--{_id_part(target_id)}"


def _canonical_graph(chapters: list[dict[str, Any]], diagram_type: str) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []
    edges: list[dict] = []
    chapter_ids = {chapter["id"] for chapter in chapters}
    for chapter in chapters:
        source = chapter["id"]
        root_id = _node_id(source)
        nodes.append({"id": root_id, "label": chapter.get("scope") or source, "sourceIds": [source]})
        previous = root_id
        for field, value in _fields(chapter, diagram_type):
            source_id = f"{source}.parameters.{field}"
            node_id = _node_id(source_id)
            nodes.append({"id": node_id, "label": f"{field}: {value}", "sourceIds": [source_id]})
            edge_id = _edge_id(previous, node_id, "sequence")
            edges.append({"id": edge_id, "from": previous, "to": node_id, "label": "", "sourceIds": [source_id]})
            previous = node_id
        for dependency in chapter.get("dependencies") or []:
            if dependency in chapter_ids:
                start, end = _node_id(dependency), root_id
                edges.append({"id": _edge_id(start, end, "dependency"), "from": start, "to": end, "label": "依赖", "sourceIds": [dependency, source, "dependency"]})
    return nodes, edges


def _mermaid(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["flowchart TD"]
    lines.extend(f'  {node["id"].replace("-", "_")}["{_safe_label(node["label"])}"]' for node in nodes)
    for edge in edges:
        label = f'|{_safe_label(edge["label"])}|' if edge["label"] else ""
        lines.append(f'  {edge["from"].replace("-", "_")} -->{label} {edge["to"].replace("-", "_")}')
    return "\n".join(lines)


def _svg(nodes: list[dict], edges: list[dict], diagram_type: str, chapters: list[dict[str, Any]]) -> str:
    node_indexes = {node["id"]: index for index, node in enumerate(nodes)}
    connectors = []
    for edge in edges:
        if edge.get("from") not in node_indexes or edge.get("to") not in node_indexes:
            continue
        start_y = 50 + node_indexes[edge["from"]] * 42
        end_y = 16 + node_indexes[edge["to"]] * 42
        direction = 1 if end_y >= start_y else -1
        arrow_y = end_y
        points = f"374,{arrow_y - 7 * direction} 386,{arrow_y - 7 * direction} 380,{arrow_y}"
        connectors.append(
            f'<g id="{escape(edge["id"], quote=True)}">'
            f'<line x1="380" y1="{start_y}" x2="380" y2="{end_y - 7 * direction}" stroke="#94a3b8" stroke-width="2"/>'
            f'<polygon points="{points}" fill="#64748b"/>'
            f'</g>'
        )
    rows = []
    for index, node in enumerate(nodes):
        y = 40 + index * 42
        rows.append(f'<g id="{escape(node["id"], quote=True)}"><rect x="16" y="{y - 24}" width="728" height="34" rx="8" fill="#f5f3ff" stroke="#7c3aed"/><text x="28" y="{y - 2}" font-size="14" fill="#201a2e">{escape(str(node["label"]))}</text></g>')
    extra = ""
    if diagram_type == "formula":
        chapter = chapters[0]
        parameters = chapter.get("parameters") or {}
        raw_formulae = chapter.get("formulae") or {}
        if isinstance(raw_formulae, list):
            formulae = next((item for item in raw_formulae if isinstance(item, dict)), {})
        else:
            formulae = raw_formulae if isinstance(raw_formulae, dict) else {}
        formula = _value(parameters.get("formula")) or str(formulae.get("expression") or formulae.get("formula") or "").strip()
        example = _value(parameters.get("example")) or str(formulae.get("example") or "").strip()
        y = 58 + len(nodes) * 42
        parameter_rows = "；".join(
            f"{escape(_FIELD_LABELS.get(name, name))}={escape(_value(value))}"
            for name, value in parameters.items()
            if name not in {"formula", "example"} and _value(value)
        )
        lines = []
        if formula:
            lines.append((15, 700, f"公式：{formula}"))
        if parameter_rows:
            lines.append((13, 400, f"参数：{parameter_rows}"))
        if example:
            lines.append((13, 400, f"算例：{example}"))
        extra = "".join(
            f'<text x="16" y="{y + index * 28}" font-size="{size}" font-weight="{weight}">{escape(text)}</text>'
            for index, (size, weight, text) in enumerate(lines)
        )
    height = max(120, 90 + len(nodes) * 42 + (28 * len(re.findall(r"<text ", extra)) if extra else 0))
    return f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(diagram_type, quote=True)}" viewBox="0 0 760 {height}">{"".join(connectors)}{"".join(rows)}{extra}</svg>'


def build_diagram(model: dict[str, Any], chapter_ids: list[str], diagram_type: str) -> dict[str, Any]:
    if diagram_type not in SUPPORTED_TYPES:
        raise ValueError("unsupported diagram type")
    if not isinstance(chapter_ids, list) or not chapter_ids or any(not isinstance(item, str) for item in chapter_ids) or len(chapter_ids) != len(set(chapter_ids)):
        raise ValueError("chapterIds must contain unique chapters")
    chapters = [_chapter(model, chapter_id) for chapter_id in chapter_ids]
    nodes, edges = _canonical_graph(chapters, diagram_type)
    return {
        "type": diagram_type, "chapterIds": list(chapter_ids), "nodes": nodes, "edges": edges,
        "mermaid": _mermaid(nodes, edges), "svg": _svg(nodes, edges, diagram_type, chapters),
    }


def _require_revision(model: dict[str, Any], expected_revision: int) -> None:
    if type(expected_revision) is not int or expected_revision != model.get("revision"):
        raise GameplayReviewConflict(model.get("revision", 0))


def _next_id(model: dict[str, Any]) -> str:
    used = {item.get("id") for item in model.get("diagrams") or [] if isinstance(item, dict)}
    number = 1
    while f"GDI-{number:03d}" in used:
        number += 1
    return f"GDI-{number:03d}"


def _finish(model: dict[str, Any]) -> dict[str, Any]:
    model["revision"] += 1
    model.setdefault("reviewState", {})["previewRevision"] = None
    return model


def generate_diagram(model: dict[str, Any], chapter_ids: list[str], diagram_type: str, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    if not isinstance(chapter_ids, list) or not chapter_ids:
        raise ValueError("chapterIds are required")
    chapters = [_chapter(model, chapter_id) for chapter_id in chapter_ids]
    if diagram_type == "formula":
        raise ValueError("formula should be shown as text instead of a diagram")
    if not any((chapter.get("mechanism") or {}).get("type") in HELPFUL_FOR.get(diagram_type, set()) for chapter in chapters):
        raise ValueError(f"{diagram_type} diagram is not helpful for selected chapters")
    if not _has_visual_structure(chapters, diagram_type):
        raise ValueError("selected chapters do not contain a visual relationship")
    result = deepcopy(model)
    diagram = build_diagram(result, chapter_ids, diagram_type)
    diagram.update({
        "id": _next_id(result), "revision": 1, "status": "open", "freshness": "current", "optional": True,
        "interactionRevision": result.get("interactionRevision"), "sourceRevision": result.get("revision"), "feedback": [],
    })
    result.setdefault("diagrams", []).append(diagram)
    return _finish(result)


def auto_generate_diagrams(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    """Automatically decide which confirmed chapters benefit from a structure diagram."""
    _require_revision(model, expected_revision)
    result = deepcopy(model)
    chapters_by_id = {
        chapter.get("id"): chapter
        for chapter in result.get("chapters") or []
        if isinstance(chapter, dict)
    }
    for diagram in result.get("diagrams") or []:
        if not isinstance(diagram, dict) or diagram.get("status") == "deleted":
            continue
        chapters = [chapters_by_id[item] for item in diagram.get("chapterIds") or [] if item in chapters_by_id]
        if diagram.get("type") == "formula" or not _has_visual_structure(chapters, diagram.get("type")):
            diagram.update({"status": "deleted", "optional": True, "freshness": "current"})
            continue
        if diagram.get("status") == "stale":
            canonical = build_diagram(result, diagram.get("chapterIds") or [], diagram.get("type"))
            if diagram.get("generationMode") != "curated" and (_svg_has_relationship(canonical.get("svg")) or not _svg_has_relationship(diagram.get("svg"))):
                diagram.update(canonical)
            diagram.update({
                "revision": int(diagram.get("revision") or 1) + 1,
                "status": "open",
                "freshness": "current",
                "sourceRevision": model.get("revision"),
            })
    active_keys = {
        (tuple(item.get("chapterIds") or []), item.get("type"))
        for item in result.get("diagrams") or []
        if isinstance(item, dict) and item.get("status") != "deleted"
    }
    active_chapter_ids = {
        chapter_id
        for item in result.get("diagrams") or []
        if isinstance(item, dict) and item.get("status") != "deleted"
        for chapter_id in item.get("chapterIds") or []
    }
    no_diagram: list[str] = []
    for chapter in result.get("chapters") or []:
        if not isinstance(chapter, dict) or not (chapter.get("confirmation") or {}).get("confirmed"):
            continue
        chapter_id = chapter.get("id")
        mechanism_type = (chapter.get("mechanism") or {}).get("type")
        diagram_type = next((kind for kind in AUTO_TYPE_ORDER if mechanism_type in HELPFUL_FOR[kind]), None)
        if diagram_type is None and mechanism_type == "custom":
            diagram_type = _planner_inferred_diagram_type(chapter)
        if not diagram_type or not _has_visual_structure([chapter], diagram_type):
            no_diagram.append(chapter_id)
            continue
        if chapter_id in active_chapter_ids:
            continue
        if ((chapter_id,), diagram_type) in active_keys:
            continue
        diagram = build_diagram(result, [chapter_id], diagram_type)
        diagram.update({
            "id": _next_id(result), "revision": 1, "status": "open", "freshness": "current",
            "optional": True, "interactionRevision": result.get("interactionRevision"),
            "sourceRevision": result.get("revision"), "feedback": [],
        })
        result.setdefault("diagrams", []).append(diagram)
        active_keys.add(((chapter_id,), diagram_type))
        active_chapter_ids.add(chapter_id)
    result["diagramReview"] = {
        "status": "ready",
        "noDiagramChapterIds": no_diagram,
        "sourceRevision": model.get("revision"),
    }
    return _finish(result)


def _diagram(model: dict[str, Any], diagram_id: str) -> dict[str, Any]:
    diagram = next((item for item in model.get("diagrams") or [] if isinstance(item, dict) and item.get("id") == diagram_id), None)
    if not diagram:
        raise ValueError(f"unknown diagram: {diagram_id}")
    return diagram


def add_diagram_feedback(model: dict[str, Any], diagram_id: str, text: str, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("feedback is required")
    result = deepcopy(model)
    diagram = _diagram(result, diagram_id)
    diagram.setdefault("feedback", []).append({"text": text.strip(), "diagramRevision": diagram.get("revision", 1)})
    return _finish(result)


def regenerate_diagram(model: dict[str, Any], diagram_id: str, feedback: str, expected_revision: int) -> dict[str, Any]:
    result = add_diagram_feedback(model, diagram_id, feedback, expected_revision)
    diagram = _diagram(result, diagram_id)
    chapters = [_chapter(result, chapter_id) for chapter_id in diagram["chapterIds"]]
    regenerated_type = diagram["type"]
    if len(chapters) == 1 and (chapters[0].get("mechanism") or {}).get("type") == "custom":
        regenerated_type = _planner_inferred_diagram_type(chapters[0]) or regenerated_type
    canonical = build_diagram(result, diagram["chapterIds"], regenerated_type)
    diagram.update(canonical)
    diagram.update({
        "revision": diagram.get("revision", 1) + 1,
        "status": "open",
        "freshness": "current",
        "sourceRevision": result["revision"],
        "interactionRevision": result.get("interactionRevision"),
    })
    return result


def approve_diagram(model: dict[str, Any], diagram_id: str, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result = deepcopy(model)
    diagram = _diagram(result, diagram_id)
    if diagram.get("status") in {"stale", "revising", "deleted"}:
        raise ValueError("diagram is not ready for approval")
    diagram.update({
        "status": "reviewed", "freshness": "current",
        # Approval always binds the exact diagram the planner just reviewed to
        # the current interaction snapshot. Without this, the UI can report
        # success while the P7 gate continues to reject an older revision.
        "interactionRevision": result.get("interactionRevision"),
    })
    return _finish(result)


def delete_diagram(model: dict[str, Any], diagram_id: str, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result = deepcopy(model)
    diagram = _diagram(result, diagram_id)
    if not diagram.get("optional", True):
        raise ValueError("required diagram cannot be deleted")
    diagram["status"] = "deleted"
    return _finish(result)
