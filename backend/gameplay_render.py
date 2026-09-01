from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from html import escape
import re
from typing import Any
from xml.etree import ElementTree as ET

from .gameplay_directory import ensure_directory, legacy_directory
from .planning_content_policy import normalize_delivery_carriers


_SVG_NS = "http://www.w3.org/2000/svg"
_SVG_ELEMENTS = {"svg", "g", "rect", "text", "path", "line", "polyline", "polygon", "circle", "ellipse"}
_SVG_ATTRIBUTES = {
    "xmlns", "role", "aria-label", "viewBox", "id", "x", "y", "x1", "x2", "y1", "y2",
    "width", "height", "rx", "ry", "cx", "cy", "r", "fill", "stroke", "stroke-width",
    "stroke-dasharray", "font-size", "font-weight", "text-anchor", "d", "points", "transform", "opacity",
}

_PARAMETER_LABELS = {
    "playerGoal": "玩法目标", "trigger": "什么时候开始", "phaseOrder": "正常过程", "completion": "怎样算完成", "failure": "什么情况下失败", "reset": "结束后保留什么",
    "objects": "可操作对象", "legalRegion": "可放置区域", "matchRule": "匹配规则", "replacement": "替换规则", "failureReturn": "失败后返回", "bounds": "边界限制", "saveCondition": "保存条件",
    "spawn": "如何出现", "targeting": "攻击谁", "movement": "如何移动", "attack": "如何攻击", "cooldown": "攻击间隔", "hit": "命中后怎样", "death": "死亡后怎样",
    "inputs": "参与计算的数值", "units": "数值单位", "ranges": "可用范围", "formula": "计算公式", "stackOrder": "计算顺序", "rounding": "取整方式", "example": "计算示例", "configSource": "配置位置",
    "scope": "生效范围", "unlock": "解锁条件", "cost": "消耗", "levels": "等级内容", "cap": "上限", "effect": "生效结果",
    "eligibility": "可参与条件", "exclusions": "排除条件", "drawOrder": "抽取顺序", "replacementRule": "放回规则", "weightFormula": "权重计算", "emptyResult": "无结果处理", "temporaryResult": "临时结果", "confirm": "确认方式", "reroll": "重新抽取",
    "sources": "获得来源", "costs": "消耗项目", "settlement": "结算方式", "accumulation": "累计方式", "lifecycle": "保留周期",
    "entry": "进入条件", "distanceOrTime": "距离或时间", "spawns": "生成规则", "multipliers": "倍率", "experience": "经验获得", "reward": "奖励", "target": "作用目标", "parameters": "效果数值", "calculation": "计算方式", "stacks": "叠加规则", "duration": "持续时间", "removal": "移除方式",
    "win": "胜利条件", "rewardBoundary": "奖励边界", "statistics": "统计内容", "messages": "提示内容", "exit": "退出方式", "entryCost": "进入消耗", "costTiming": "扣除时机", "failureRefund": "失败返还", "sweep": "扫荡条件", "rewards": "奖励内容", "metric": "统计指标", "aggregation": "汇总方式", "refresh": "刷新方式", "sorting": "排序方式", "displayStates": "显示状态",
}


def _parameter_label(name: Any, metadata: dict[str, Any]) -> str:
    explicit = str(metadata.get("label") or "").strip()
    aliases = {
        "boss_name": "首领名称", "首领_name": "首领名称", "wave_time_trigger": "首领出现时间",
        "player_hp_current": "玩家当前生命值", "skill_resource_fire": "火焰技能资源",
        "damage_number_style": "伤害数字样式",
    }
    value = str(name)
    if explicit:
        return explicit
    if value in _PARAMETER_LABELS:
        return _PARAMETER_LABELS[value]
    if value in aliases:
        return aliases[value]
    return value if re.search(r"[\u4e00-\u9fff]", value) else "其他配置"


def _parameter_type(value: Any) -> str:
    return {"number": "数值", "text": "文本", "string": "文本", "boolean": "是或否"}.get(str(value or "").casefold(), _text(value, "待确认"))


def _parameter_unit(value: Any) -> str:
    return {
        "n/a": "无", "none": "无", "-": "无", "count": "个", "level": "级",
        "seconds": "秒", "second": "秒", "damage": "点伤害", "percent": "%", "hp": "点生命",
    }.get(str(value or "").casefold(), _text(value, "待确认"))


def _parameter_range(value: Any) -> str:
    return {"defined": "按配置填写", "fixed": "固定值"}.get(str(value or "").casefold(), _text(value, "待确认"))


def _parameter_source(value: Any) -> str:
    source = str(value or "").strip()
    if re.search(r"\bF\d{4}\b", source):
        return "素材截图"
    return {"planner": "策划填写", "material": "素材截图", "visual": "素材截图"}.get(source.casefold(), _text(source, "待确认"))


@dataclass(frozen=True)
class GameplayRenderResult:
    xml: str
    embedded_whiteboard_count: int
    order: tuple[dict[str, Any], ...]
    embedded_whiteboards: tuple[tuple[str, str], ...] = ()
    overview_xml: str = ""
    body_xml: str = ""
    overview_order: tuple[dict[str, Any], ...] = ()
    body_order: tuple[dict[str, Any], ...] = ()


class GameplayRenderError(ValueError):
    def __init__(self, blocker_ids: list[str]):
        self.blocker_ids = tuple(dict.fromkeys(blocker_ids))
        super().__init__(", ".join(self.blocker_ids))


def authoritative_gameplay_model(model: dict[str, Any]) -> dict[str, Any]:
    """Adapt a guarded PublicationProjection to the existing layout renderer."""
    projection = model.get("ruleIntelligenceProjection")
    if not isinstance(projection, dict) or projection.get("authorityMode") != "structured_rules":
        return model
    publication = projection.get("publication") or {}
    reconstructed_mode = bool(publication.get("mechanicFlows"))
    final_planning_gaps = list(publication.get("finalPlanningGaps") or [])
    flows_by_chapter: dict[str, list[dict[str, Any]]] = {}
    for flow in publication.get("mechanicFlows") or []:
        flows_by_chapter.setdefault(str(flow.get("chapterId") or ""), []).append(flow)
    chapters = []
    for source in publication.get("chapters") or []:
        if source.get("publicationEligibility") != "eligible":
            continue
        definitions = source.get("ruleDefinitions") or []
        references = source.get("references") or []
        visible = [*definitions, *references]
        source_flows = flows_by_chapter.get(str(source.get("chapterId") or ""), [])
        if reconstructed_mode and not source_flows:
            continue
        if not reconstructed_mode and not visible and not source.get("gaps"):
            continue
        chapter_id = str(source.get("chapterId") or "")
        reconstructed = []
        source_chapter_ids: set[str] = {chapter_id}
        for flow in source_flows:
            source_chapter_ids.update(str(item) for item in (flow.get("sourceChapterIds") or []) if item)
            if flow.get("candidateTypeSummary"):
                reconstructed.append({"ruleId": f"{flow.get('mechanicId')}-CANDIDATE-TYPES", "text": flow["candidateTypeSummary"]})
            reconstructed.extend(flow.get("steps") or [])
        flow_items = reconstructed or [
            {"ruleId": rule.get("ruleId"), "text": rule.get("behavior") or rule.get("text")}
            for rule in visible if rule.get("behavior") or rule.get("text")
        ]
        chapters.append({
            "id": chapter_id, "scope": source.get("title") or source.get("object") or "玩法规则",
            "sectionTitle": source.get("system") or "玩法规则",
            "subsectionTitle": source.get("object") or "规则",
            "status": "approved", "confirmation": {"confirmed": True},
            "plannerSections": {
                "summary": source.get("title") or source.get("object") or "玩法规则",
                "normalFlow": [{"id": item.get("ruleId"), "text": item.get("text")} for item in flow_items if item.get("text")],
                "keyRules": [], "specialCases": [], "acceptanceExamples": [],
            },
            "unknowns": [
                gap for gap in (final_planning_gaps if reconstructed_mode else source.get("gaps") or [])
                if gap.get("specificity") == "concrete_decision"
                and str(gap.get("chapterId") or "") in source_chapter_ids
            ],
            "parameters": {}, "claims": [], "sourceFrameIds": [],
        })
    if not chapters:
        raise GameplayRenderError(["STRUCTURED_PUBLICATION_EMPTY"])
    result = dict(model)
    result["chapters"] = chapters
    result["systems"] = []
    result["directory"] = legacy_directory(chapters)
    return result


def _text(value: Any, fallback: str = "待确认") -> str:
    if value in (None, ""):
        return fallback
    if isinstance(value, str):
        text = value
    else:
        text = str(value.get("value") or fallback) if isinstance(value, dict) else str(value)
    return re.sub(r"\b(?:SCN|EVT|GEV)-\d+\b", "", text).strip() or fallback


def _confirmed_chapters(model: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        chapter for chapter in model.get("chapters") or []
        if isinstance(chapter, dict)
        and chapter.get("status") in {"approved", "conditional"}
        and (chapter.get("confirmation") or {}).get("confirmed") is True
    ]


def _ordered_chapters(model: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = {item.get("id"): item for item in _confirmed_chapters(model)}
    directory = ensure_directory(model)
    if directory.get("status") != "confirmed":
        raise GameplayRenderError(["GAMEPLAY_DIRECTORY_NOT_CONFIRMED"])
    systems = model.get("systems") if isinstance(model.get("systems"), list) else []
    if systems:
        ordered: list[dict[str, Any]] = []
        for system in systems:
            if not isinstance(system, dict):
                continue
            for subsystem in system.get("subsystems") or []:
                if not isinstance(subsystem, dict):
                    continue
                for chapter_id in subsystem.get("chapterIds") or []:
                    chapter = chapters.get(chapter_id)
                    if chapter is None:
                        continue
                    item = dict(chapter)
                    item["sectionTitle"] = system.get("name") or ""
                    item["subsectionTitle"] = subsystem.get("name") or ""
                    ordered.append(item)
        return ordered
    ordered: list[dict[str, Any]] = []
    for entry in sorted(directory.get("entries") or [], key=lambda item: item.get("order", 0)):
        chapter = chapters.get(entry.get("chapterId"))
        if chapter is None:
            continue
        chapter = dict(chapter)
        chapter["scope"] = entry.get("title") or chapter.get("scope")
        chapter["sectionTitle"] = entry.get("sectionTitle") or ""
        ordered.append(chapter)
    return ordered


def _parameter_catalog(chapters: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for chapter in chapters:
        parameters = chapter.get("parameters") if isinstance(chapter.get("parameters"), dict) else {}
        for name, metadata in parameters.items():
            metadata = metadata if isinstance(metadata, dict) else {"value": metadata}
            rows.append(
                "<tr>"
                f"<td>{escape(_text(chapter.get('scope')))}</td><td>{escape(_parameter_label(name, metadata))}</td>"
                f"<td>{escape(_text(metadata.get('value')))}</td><td>{escape(_parameter_type(metadata.get('type')))}</td>"
                f"<td>{escape(_parameter_unit(metadata.get('unit')))}</td><td>{escape(_parameter_range(metadata.get('range')))}</td>"
                f"<td>{escape(_parameter_source(metadata.get('source')))}</td></tr>"
            )
    if not rows:
        return ""
    return (
        "<table><thead><tr><th>玩法</th><th>参数</th><th>数值</th><th>填写格式</th>"
        "<th>数值单位</th><th>可用范围</th><th>配置位置</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table>"
    )


def _safe_svg(value: Any) -> str:
    svg = str(value or "").strip()
    if not svg or re.search(r"<!DOCTYPE|<!ENTITY", svg, re.I):
        return ""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return ""
    root_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
    root_namespace = root.tag[1:].split("}", 1)[0] if isinstance(root.tag, str) and root.tag.startswith("{") else ""
    if root_name != "svg" or root_namespace not in {"", _SVG_NS}:
        return ""
    for node in root.iter():
        if not isinstance(node.tag, str):
            return ""
        namespace = node.tag[1:].split("}", 1)[0] if node.tag.startswith("{") else ""
        name = node.tag.rsplit("}", 1)[-1]
        if namespace not in {"", _SVG_NS} or name not in _SVG_ELEMENTS:
            return ""
        node.tag = name
        for attribute, raw in list(node.attrib.items()):
            attribute_name = attribute.rsplit("}", 1)[-1]
            value_text = str(raw).strip()
            if (
                attribute.startswith("{")
                or attribute_name not in _SVG_ATTRIBUTES
                or attribute_name.lower().startswith("on")
                or re.search(r"(?:url\s*\(|javascript:|data:|https?://|//)", value_text, re.I)
            ):
                return ""
            if attribute_name != attribute:
                return ""
        if node.tail and node.tail.strip():
            return ""
    root.set("xmlns", _SVG_NS)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def _diagram_xml(diagram: dict[str, Any], safe_svg: str) -> str:
    labels = {"state_flow": "玩法流程图", "probability": "随机算法流程图", "spatial": "空间关系图", "effect_chain": "效果链路图", "formula": "计算关系图"}
    title = _text(diagram.get("title") or labels.get(diagram.get("type")), "玩法图示")
    return (
        f"<h4>{escape(title)}</h4>"
        '<whiteboard type="blank"></whiteboard>'
    )


def _optional_modules_xml(chapter: dict[str, Any]) -> str:
    parts: list[str] = []
    # parameterSchema is retained for review/gating, not serialized as a
    # universal table. Formal delivery uses reviewed mechanism-specific tables.
    field_mappings = []
    for item in chapter.get("fieldDictionary") or []:
        if not isinstance(item, dict):
            continue
        planner_name = escape(_text(item.get("plannerName")))
        code_name = escape(_text(item.get("suggestedCodeName")))
        decision_state = _text(item.get("decisionStatus") or item.get("status"), "").strip().lower()
        adopted = item.get("confirmed") is True or decision_state in {"accepted", "confirmed", "adopted", "已采用", "已确认"}
        suggestion = "" if adopted else "（建议）"
        field_mappings.append(
            f"<li><b>{planner_name}：</b><code>{code_name}</code>{suggestion}</li>"
        )
    if field_mappings:
        parts.append(
            "<p><b>参数命名</b></p><ul>" + "".join(field_mappings) + "</ul>"
        )
    formulae = [item for item in chapter.get("formulae") or [] if isinstance(item, dict) and item.get("expression")]
    if formulae:
        for item in formulae:
            title = _text(item.get("title") or item.get("name"), "")
            expression = escape(_text(item.get("expression")))
            parts.append(f"<p><b>{escape(title)}：</b>{expression}</p>" if title else f"<p>{expression}</p>")
    examples = [item for item in chapter.get("workedExamples") or [] if isinstance(item, dict)]
    if examples:
        rows = []
        for item in examples:
            title = _text(item.get("title"), "计算示例")
            detail = _text(item.get("steps") or item.get("result") or item.get("description"))
            rows.append(f"<li>{escape(detail)}</li>" if title in {"计算示例", "示例", "算例"} else f"<li><b>{escape(title)}：</b>{escape(detail)}</li>")
        parts.append("<ul>" + "".join(rows) + "</ul>")
    sources = [item for item in chapter.get("configurationSources") or [] if isinstance(item, dict)]
    if sources:
        rows = []
        for item in sources:
            title = _text(item.get("title") or item.get("name"))
            field = _text(item.get("field"), "")
            rows.append(f"<li>{escape(title)}{(' · ' + escape(field)) if field else ''}</li>")
        parts.append("<ul>" + "".join(rows) + "</ul>")
    return "".join(parts)


def _reviewed_tables_xml(model: dict[str, Any], *, orphan_only: bool = False) -> tuple[str, int]:
    """Render reviewed gameplay tables from the same snapshot used by P7/export."""
    parts: list[str] = []
    count = 0
    for table in model.get("tables") or []:
        if not isinstance(table, dict) or table.get("status") in {"deleted", "open"}:
            continue
        if orphan_only and table.get("chapterIds"):
            continue
        columns = [_text(item, "") for item in table.get("columns") or []]
        rows = [item for item in table.get("rows") or [] if isinstance(item, list)]
        if not columns or not rows:
            continue
        field_index = columns.index("字段") if "字段" in columns else -1
        type_index = columns.index("类型") if "类型" in columns else -1
        suggested_index = columns.index("AI 建议值") if "AI 建议值" in columns else -1
        modified_index = columns.index("修改值") if "修改值" in columns else -1
        if field_index >= 0 and suggested_index >= 0 and modified_index >= 0:
            delivery_rows = []
            for row in rows:
                value = _text(row[modified_index] if modified_index < len(row) else "", "") or _text(row[suggested_index] if suggested_index < len(row) else "", "")
                field_type = _text(row[type_index] if 0 <= type_index < len(row) else "", "")
                unit_match = re.search(r"[（(]([^）)]+)[）)]", field_type)
                unit = unit_match.group(1) if unit_match else ""
                confirmed_value = f"{value}{unit}" if unit and value and not value.endswith(unit) else value
                delivery_rows.append([row[field_index] if field_index < len(row) else "", confirmed_value])
            columns, rows = ["参数", "确认值"], delivery_rows
        parts.append(f"<h3>{escape(_text(table.get('title'), '配置表'))}</h3>")
        parts.append(
            "<table><thead><tr>"
            + "".join(f"<th>{escape(column)}</th>" for column in columns)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{escape(_text(cell, ''))}</td>" for cell in row) + "</tr>"
                for row in rows
            )
            + "</tbody></table>"
        )
        count += 1
    return "".join(parts), count


def _chapter_is_sparse(chapter: dict[str, Any], *, has_diagram: bool = False) -> bool:
    if has_diagram:
        return False
    sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    normal_flow = [item for item in sections.get("normalFlow") or [] if _text(item, "")]
    groups = sum(bool(value) for value in (
        normal_flow,
        sections.get("keyRules") or chapter.get("claims") or chapter.get("evidenceClaims"),
        sections.get("specialCases") or chapter.get("edgeCases") or chapter.get("boundaries") or chapter.get("resetRules"),
        sections.get("attributeSections") or chapter.get("attributeSections"),
        chapter.get("parameters") or chapter.get("parameterSchema"),
        chapter.get("formulae") or chapter.get("workedExamples"),
        sections.get("acceptanceExamples") or chapter.get("acceptanceCases"),
        chapter.get("configurationSources") or chapter.get("dependencies"),
    ))
    return len(normal_flow) < 3 and groups <= 2


def _dedupe_similar_rules(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        normalized = re.sub(r"[，。；：、“”\s]", "", item)
        def duplicate(prior: str) -> bool:
            prior_normalized = re.sub(r"[，。；：、“”\s]", "", prior)
            shared_outcome = any(marker in item and marker in prior for marker in (
                "不要求玩家点击确认", "首领阶段仍属于同一局战斗", "显示首领名称、生命百分比和附加计数",
            ))
            return shared_outcome or SequenceMatcher(None, normalized, prior_normalized).ratio() >= .72
        duplicate_index = next((index for index, prior in enumerate(result) if duplicate(prior)), None)
        if duplicate_index is not None:
            # Later entries are the reviewed/refined copy.  Keep that exact
            # wording so deduplication removes repetition without discarding
            # the canonical delivery contract.
            result[duplicate_index] = item
            continue
        result.append(item)
    return result


def _semantic_rule_sections(chapter: dict[str, Any], key_rules: list[str], special_cases: list[str]) -> list[dict[str, Any]]:
    """Group only long rule lists into a few planner-facing business sections."""
    explicit = ((chapter.get("plannerSections") or {}).get("ruleSections") or [])
    if explicit:
        return [item for item in explicit if isinstance(item, dict) and item.get("items")]
    combined = _dedupe_similar_rules([*key_rules, *special_cases])
    if (len(key_rules) + len(special_cases) < 8
            or not any("首领" in item for item in combined)
            or not any(re.search(r"闪避|格挡|免疫", item) for item in combined)):
        return []
    buckets = [
        ("触发与战斗状态", re.compile(r"触发|达到.+条件|来袭|警告|切入|进入.+战|HUD|显示|继续(?:显示|累计)|同一局")),
        ("属性与承伤判定", re.compile(r"生命值等于|攻击力|倍率|闪避|格挡|免疫|伤害|承伤")),
        ("胜负结算", re.compile(r"生命值.*大于0|生命归零|成功|失败|胜负|结算|互斥")),
    ]
    sections = [{"heading": heading, "items": []} for heading, _ in buckets]
    remaining: list[str] = []
    for rule in combined:
        target = next((index for index, (_, pattern) in enumerate(buckets) if pattern.search(rule)), None)
        (sections[target]["items"] if target is not None else remaining).append(rule)
    if remaining:
        # Keep isolated facts with the closest first section instead of adding
        # a generic catch-all heading such as “其他规则”.
        sections[0]["items"].extend(remaining)
    return [section for section in sections if len(section["items"]) >= 1]


def _chapter_xml(chapter: dict[str, Any], *, merged: bool = False, diagrams: list[tuple[dict[str, Any], str]] | None = None,
                 frame_sources: dict[str, dict[str, Any]] | None = None,
                 linked_tables: list[dict[str, Any]] | None = None) -> str:
    claims = [item for item in chapter.get("evidenceClaims") or chapter.get("claims") or [] if isinstance(item, dict)]
    sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    acceptances = [item for item in sections.get("acceptanceExamples") or chapter.get("acceptanceCases") or [] if isinstance(item, dict)]
    parts: list[str] = []
    summary = _text(sections.get("summary") or chapter.get("plannerSummary"), "该玩法的核心机制还需要补充")
    normal_flow_records: list[tuple[str, str]] = []
    for index, item in enumerate(sections.get("normalFlow") or [], 1):
        if isinstance(item, dict):
            rule_id = _text(item.get("id") or item.get("ruleId"), f"R{index}")
            rule_text = _text(item.get("text") or item.get("value") or item.get("description"), "")
        else:
            rule_id = f"R{index}"
            rule_text = _text(item, "")
        if rule_text:
            normal_flow_records.append((rule_id, rule_text))
    normal_flow = [text for _, text in normal_flow_records]
    # Keep the complete reviewed execution sequence.  Truncating this list made
    # P7 and Feishu silently omit valid late steps (for example settlement and
    # refresh boundaries), which violates the shared delivery contract.
    deduped_flow_records: list[tuple[str, str]] = []
    seen_flow: set[str] = set()
    for rule_id, text in normal_flow_records:
        if text == summary or text in seen_flow:
            continue
        seen_flow.add(text)
        deduped_flow_records.append((rule_id, text))
    normal_flow_records = deduped_flow_records
    normal_flow = [text for _, text in normal_flow_records]
    key_rules = [_text(item, "") for item in sections.get("keyRules") or []]
    key_rules = [item for item in key_rules if item and item != summary]
    special_cases = [_text(item, "") for item in sections.get("specialCases") or []]
    special_cases = [item for item in special_cases if item and item != summary]
    rule_sections = _semantic_rule_sections(chapter, key_rules, special_cases)
    attribute_sections = sections.get("attributeSections") or chapter.get("attributeSections") or []
    attribute_sections = [item for item in attribute_sections if isinstance(item, dict)]
    attribute_heading = _text(sections.get("attributeHeading"), "")
    document_heading = attribute_heading or _text(chapter.get("scope"))
    optional_depth = sum(bool(chapter.get(key)) for key in (
        "parameterSchema", "formulae", "workedExamples", "configurationSources"
    ))
    content_groups = sum(bool(group) for group in (normal_flow, key_rules, special_cases, attribute_sections, acceptances)) + optional_depth
    deep_chapter = content_groups >= 3

    if merged:
        label = re.sub(r"(?:机制|状态管理)$", "", _text(chapter.get("scope"))) or _text(chapter.get("scope"))
        merged_copy = list(dict.fromkeys(item for item in [summary, *normal_flow, *key_rules, *special_cases] if item))
        parts.append(f"<p><b>{escape(label)}：</b>{escape('；'.join(item.rstrip('。；') for item in merged_copy) + '。')}</p>")
    else:
        parts.extend((f"<h3>{escape(document_heading)}</h3>", f"<p>{escape(summary)}</p>"))
    if normal_flow and not merged:
        if len(normal_flow) >= 3:
            flow_name = _text(chapter.get("flowHeading"), "") or ((re.sub(r"(?:机制|系统|规则)$", "", _text(chapter.get("scope"))) or "玩法") + "流程")
            parts.append(f"<h4>{escape(flow_name)}</h4>")
        anchored = sorted(diagrams or [], key=lambda item: int((item[0].get("placement") or {}).get("afterFlowIndex", 999)))
        inline_by_rule: dict[str, list[str]] = {}
        matched_inline_ids: set[int] = set()
        known_rule_ids = {rule_id for rule_id, _ in normal_flow_records}
        for figure_index, figure in enumerate(chapter.get("inlineFigures") or []):
            if not isinstance(figure, dict):
                continue
            after_rule_id = _text(figure.get("afterRuleId"), "")
            if not after_rule_id or after_rule_id not in known_rule_ids:
                continue
            source = (frame_sources or {}).get(_text(figure.get("frameId"), ""), {})
            image_url = _text(source.get("imageUrl") or source.get("previewUrl") or source.get("url"), "")
            if not image_url:
                continue
            frame_id = _text(figure.get("frameId"), "")
            label = _text(figure.get("caption"), "") or _text(chapter.get("scope"), "玩法说明图")
            inline_by_rule.setdefault(after_rule_id, []).append(
                f'<img name="inline-figure-{escape(frame_id, quote=True)}" caption="{escape(label, quote=True)}"/>'
            )
            matched_inline_ids.add(figure_index)
        if anchored:
            # A diagram illustrates the reviewed rule group; it must not split
            # one numbered sequence. Placement notes are editor metadata.
            parts.append("<ol>" + "".join(
                f'<li seq="auto">{escape(text)}{"".join(inline_by_rule.get(rule_id, []))}</li>'
                for rule_id, text in normal_flow_records
            ) + "</ol>")
            for diagram, safe_svg in anchored:
                parts.append(_diagram_xml(diagram, safe_svg))
        elif len(normal_flow) == 1:
            rule_id, text = normal_flow_records[0]
            parts.append(f"<p>{escape(text)}{''.join(inline_by_rule.get(rule_id, []))}</p>")
        else:
            parts.append("<ol>" + "".join(
                f"<li>{escape(text)}{''.join(inline_by_rule.get(rule_id, []))}</li>"
                for rule_id, text in normal_flow_records
            ) + "</ol>")
    else:
        matched_inline_ids = set()
    if not merged:
        for figure_index, figure in enumerate(chapter.get("inlineFigures") or []):
            if not isinstance(figure, dict):
                continue
            if figure_index in matched_inline_ids:
                continue
            source = (frame_sources or {}).get(_text(figure.get("frameId"), ""), {})
            image_url = _text(source.get("imageUrl") or source.get("previewUrl") or source.get("url"), "")
            if not image_url:
                continue
            caption = _text(figure.get("caption"), "")
            label = caption or _text(chapter.get("scope"), "玩法说明图")
            frame_id = _text(figure.get("frameId"), "")
            # A real image block is part of the shared delivery payload.  The
            # browser swaps this marker for the local artifact URL; Feishu
            # creates the block first and uploads the same file into it.
            parts.append(
                f'<img name="inline-figure-{escape(frame_id, quote=True)}" '
                f'caption="{escape(label, quote=True)}"/>'
            )
    if rule_sections and not merged:
        for group in rule_sections:
            parts.append(f"<h4>{escape(_text(group.get('heading')))}</h4>")
            parts.append("<ul>" + "".join(f"<li>{escape(item)}</li>" for item in group.get("items") or []) + "</ul>")
    elif key_rules and not merged:
        rule_heading = _text(chapter.get("ruleHeading"), "")
        if rule_heading:
            parts.append(f"<h4>{escape(rule_heading)}</h4>")
        parts.append("<ul>" + "".join(f"<li>{escape(item)}</li>" for item in key_rules if item) + "</ul>")
    if special_cases and not merged and not rule_sections:
        parts.append("<ul>" + "".join(f"<li>{escape(item)}</li>" for item in special_cases if item) + "</ul>")
    if attribute_sections and not merged:
        generic_attribute_headings = {"属性", "基础属性", "规则与边界", "玩法规则"}
        for group in attribute_sections:
            heading = _text(group.get("heading"), "")
            items = [_text(item, "") for item in group.get("items") or []]
            items = [item for item in items if item]
            if not items:
                continue
            if heading and heading not in generic_attribute_headings:
                parts.append(f"<h4>{escape(heading)}</h4>")
            parts.append("<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>")
    parts.append(_optional_modules_xml(chapter))
    if not merged and linked_tables:
        linked_xml, _ = _reviewed_tables_xml({"tables": linked_tables})
        parts.append(linked_xml.replace("<h3>", "<h4>").replace("</h3>", "</h4>"))
    return "".join(parts)


def _pending_items(job: dict[str, Any], chapters: list[dict[str, Any]]) -> list[str]:
    pending: list[str] = []
    for item in (job.get("reviewModel") or {}).get("crossStateConstraints") or []:
        if isinstance(item, dict) and item.get("status") == "unknown" and item.get("severity") != "core":
            pending.append(_text(item.get("text")))
    for chapter in chapters:
        for item in chapter.get("unknowns") or []:
            if not isinstance(item, dict) or item.get("blocking") is True:
                continue
            pending.append(_text(item.get("text") or item.get("description")))
    for item in (job.get("gameplayReviewModel") or {}).get("reviewState", {}).get("findings") or []:
        if isinstance(item, dict) and item.get("severity") != "blocker" and item.get("status") != "resolved":
            pending.append(_text(item.get("text") or item.get("message")))
    return list(dict.fromkeys(item for item in pending if item and item != "待确认"))


def render_gameplay_document_sections(job: dict[str, Any]) -> GameplayRenderResult:
    from .planning_gameplay_sync import sync_planning_gameplay_insights
    model = sync_planning_gameplay_insights(job, job.get("gameplayReviewModel") or {})
    model = authoritative_gameplay_model(model)
    model = normalize_delivery_carriers(model)
    chapters = _ordered_chapters(model)
    source_store = (job.get("reviewModel") or {}).get("sources") or {}
    if isinstance(source_store, list):
        frame_sources = {_text(item.get("frameId") or item.get("id"), ""): item for item in source_store if isinstance(item, dict)}
    else:
        frame_sources = source_store if isinstance(source_store, dict) else {}
    diagrams_by_chapter: dict[str, list[tuple[dict[str, Any], str]]] = {}
    invalid_diagrams: list[str] = []
    for diagram in model.get("diagrams") or []:
        if not isinstance(diagram, dict) or diagram.get("status") != "reviewed" or diagram.get("freshness") == "stale":
            continue
        placement = diagram.get("placement") if isinstance(diagram.get("placement"), dict) else {}
        first_chapter = _text(placement.get("chapterId"), "") or next((item for item in diagram.get("chapterIds") or [] if isinstance(item, str)), "")
        safe_svg = _safe_svg(diagram.get("svg"))
        if not safe_svg:
            invalid_diagrams.append(f"{_text(diagram.get('id'), 'DIAGRAM')}:DIAGRAM_RENDER_INVALID")
            continue
        if first_chapter and safe_svg:
            diagrams_by_chapter.setdefault(first_chapter, []).append((diagram, safe_svg))
    if invalid_diagrams:
        raise GameplayRenderError(invalid_diagrams)
    understanding = (model.get("directory") or {}).get("understanding") or {}
    overview_summary = _text(understanding.get("summary"), "请确认玩法概述")
    section_groups: dict[str, list[dict[str, Any]]] = {}
    for chapter in chapters:
        section_groups.setdefault(_text(chapter.get("sectionTitle"), ""), []).append(chapter)
    compact_sections = {
        title: bool(title) and all(_chapter_is_sparse(chapter, has_diagram=bool(diagrams_by_chapter.get(chapter.get("id")))) for chapter in items)
        for title, items in section_groups.items()
    }
    merge_overview = len(section_groups) == 1 and all(compact_sections.values())
    overview_paragraphs = [line.strip() for line in overview_summary.splitlines() if line.strip()]
    overview_html = [f"<p>{escape(line)}</p>" for line in overview_paragraphs]
    overview_parts = [] if merge_overview else ["<h1>玩法概述</h1>", *overview_html]
    overview_order: list[dict[str, Any]] = [] if merge_overview else [{"type": "gameplay_overview", "title": "玩法概述", "level": 1}]
    parts: list[str] = []
    order: list[dict[str, Any]] = []
    diagram_count = 0
    embedded_whiteboards: list[tuple[str, str]] = []
    current_section = ""
    current_subsection = ""
    for chapter in chapters:
        section = _text(chapter.get("sectionTitle"), "")
        if section and section != current_section:
            parts.append(f"<h1>{escape(section)}</h1>")
            order.append({"type": "gameplay_section", "title": section, "level": 1})
            if merge_overview:
                parts.extend(overview_html)
            current_section = section
            current_subsection = ""
        merged_section = compact_sections.get(section, False)
        subsection = _text(chapter.get("subsectionTitle"), "")
        if not merged_section and subsection and subsection != current_subsection:
            parts.append(f"<h2>{escape(subsection)}</h2>")
            order.append({"type": "gameplay_subsection", "title": subsection, "level": 2})
            current_subsection = subsection
        chapter_diagrams = diagrams_by_chapter.get(chapter.get("id"), [])
        linked_tables = [
            table for table in model.get("tables") or []
            if isinstance(table, dict)
            and table.get("status") not in {"deleted", "open"}
            and chapter.get("id") in (table.get("chapterIds") or [])
        ]
        parts.append(_chapter_xml(
            chapter, merged=merged_section, diagrams=chapter_diagrams,
            frame_sources=frame_sources, linked_tables=linked_tables,
        ))
        order.append({"type": "gameplay_chapter", "title": _text(chapter.get("scope")), "level": 2 if merged_section else 3})
        for diagram, safe_svg in chapter_diagrams:
            diagram_count += 1
            embedded_whiteboards.append((_text(diagram.get("title") or diagram.get("type"), "玩法图示"), safe_svg))
            order.append({"type": "gameplay_diagram", "title": _text(diagram.get("type"), "玩法图示"), "level": 4})
    reviewed_tables, reviewed_table_count = _reviewed_tables_xml(model, orphan_only=True)
    if reviewed_tables:
        parts.append("<h1>配置表</h1>" + reviewed_tables)
        order.append({"type": "reviewed_tables", "title": "配置表", "level": 1, "count": reviewed_table_count})
    pending = _pending_items(job, chapters)
    if pending:
        parts.append("<h1>待确认事项</h1><ul>" + "".join(f"<li>{escape(item)}</li>" for item in pending) + "</ul>")
        order.append({"type": "pending_list", "count": len(pending), "level": 1})
    overview_xml = "".join(overview_parts)
    body_xml = "".join(parts)
    return GameplayRenderResult(
        overview_xml + body_xml, diagram_count, tuple([*overview_order, *order]), tuple(embedded_whiteboards),
        overview_xml, body_xml, tuple(overview_order), tuple(order),
    )


def render_gameplay_sections(job: dict[str, Any]) -> str:
    return render_gameplay_document_sections(job).xml
