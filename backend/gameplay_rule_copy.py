from __future__ import annotations

import copy
import re
from typing import Any

from .feishu_language_quality import rule_carrier, split_rule_carriers
from .gameplay_copy import chapter_gameplay_summary
from .gameplay_flow_semantics import flow_chain_report


_OPTIONAL_MODULES = ("parameterSchema", "formulae", "workedExamples", "configurationSources")
_EVIDENCE_LEVELS = {"material", "reference_document", "inference", "planner", "pending"}
_CHINESE_VISUAL_TERMS = (
    "屏幕", "界面", "页面", "弹窗", "按钮", "图标", "边框", "背景", "颜色",
    "高亮", "特效", "飘字", "左上", "右上", "左侧", "右侧", "上方", "下方", "中央", "显示", "展示",
)
_BUSINESS_RULE_TERMS = (
    "生成", "筛选", "排除", "扣除", "返还", "计算", "重置", "清空", "保存",
    "解锁", "排序", "填充", "移动", "攻击", "获得", "选择", "确认", "结算",
)


def _has_evidence(item: Any) -> bool:
    if not isinstance(item, dict) or item.get("evidenceLevel") not in _EVIDENCE_LEVELS:
        return False
    frame_ids = item.get("sourceFrameIds")
    return bool(
        (isinstance(frame_ids, list) and any(isinstance(value, str) and value for value in frame_ids))
        or (isinstance(item.get("referenceSource"), str) and item["referenceSource"].strip())
    )


def normalize_optional_modules(chapter: dict[str, Any]) -> dict[str, Any]:
    """Keep useful planner modules and reject unsupported formula/config claims."""
    result = copy.deepcopy(chapter)
    for key in _OPTIONAL_MODULES:
        if not result.get(key):
            result.pop(key, None)
    for formula in result.get("formulae") or []:
        variables = formula.get("variables") if isinstance(formula, dict) else None
        if not _has_evidence(formula) or not isinstance(variables, list) or not variables or any(not _has_evidence(item) for item in variables):
            raise ValueError("formula evidence is required for the expression and every variable")
    for row in result.get("parameterSchema") or []:
        if not _has_evidence(row):
            raise ValueError("parameter evidence is required for every configuration field")
    return result


def sanitize_generated_optional_modules(chapter: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Discard unsupported model-generated values while preserving the usable chapter."""
    result = copy.deepcopy(chapter)
    warnings: list[str] = []
    existing_cards = [card for card in result.get("decisionCards") or [] if isinstance(card, dict)]

    def next_card_id() -> str:
        used = {str(card.get("id") or "") for card in existing_cards}
        index = 1
        while f"GDC-{index:03d}" in used:
            index += 1
        return f"GDC-{index:03d}"

    def add_gap_card(kind: str, names: list[str]) -> None:
        labels = "、".join(list(dict.fromkeys(name for name in names if name))) or ("相关参数" if kind == "parameter" else "相关公式")
        if kind == "parameter":
            question = f"截图未提供{labels}的可靠数值，这些配置项如何处理？"
            options = [
                {"id": "configure", "label": "保留配置项并由策划补齐数值"},
                {"id": "omit", "label": "确认本机制不配置这些数值"},
            ]
            impacts = ["参数表", "玩法正文", "验收用例", "最终文档"]
        else:
            question = f"截图不足以证明{labels}的计算关系，这些公式如何处理？"
            options = [
                {"id": "configure", "label": "保留公式并由策划补齐计算规则"},
                {"id": "omit", "label": "确认本机制不使用这些公式"},
            ]
            impacts = ["计算公式", "参数表", "玩法正文", "验收用例", "最终文档"]
        if any(card.get("question") == question for card in existing_cards):
            return
        existing_cards.append({
            "id": next_card_id(),
            "question": question,
            "selectionMode": "single",
            "options": options,
            "recommendedOptionId": "omit",
            "recommendationReason": "当前截图没有提供足以确认该数值或计算关系的依据，先不写入确定规则更安全。",
            "allowCustom": True,
            "evidence": [{"reference": "当前项目截图未提供可核验的配置值或完整计算关系"}],
            "impacts": impacts,
            "status": "pending",
        })

    rows = result.get("parameterSchema")
    if isinstance(rows, list):
        supported = [row for row in rows if _has_evidence(row)]
        unsupported = [row for row in rows if row not in supported]
        removed = len(rows) - len(supported)
        if supported:
            result["parameterSchema"] = supported
        else:
            result.pop("parameterSchema", None)
        if removed:
            warnings.append(f"已移除{removed}项缺少依据的数值字段")
            add_gap_card("parameter", [str(row.get("name") or "").strip() for row in unsupported if isinstance(row, dict)])
    formulae = result.get("formulae")
    if isinstance(formulae, list):
        supported = []
        for formula in formulae:
            variables = formula.get("variables") if isinstance(formula, dict) else None
            if _has_evidence(formula) and isinstance(variables, list) and variables and all(_has_evidence(item) for item in variables):
                supported.append(formula)
        unsupported = [formula for formula in formulae if formula not in supported]
        removed = len(formulae) - len(supported)
        if supported:
            result["formulae"] = supported
        else:
            result.pop("formulae", None)
        if removed:
            warnings.append(f"已移除{removed}条缺少依据的计算公式")
            add_gap_card("formula", [str(row.get("name") or row.get("expression") or "").strip() for row in unsupported if isinstance(row, dict)])
    if existing_cards:
        result["decisionCards"] = existing_cards
    return result, warnings


def sanitize_generated_semantics(chapter: dict[str, Any]) -> dict[str, Any]:
    """Publish only evidence-backed generated facts; route unsupported prose to review."""
    result = copy.deepcopy(chapter)
    frame_ids = {
        str(value).strip() for value in result.get("sourceFrameIds") or []
        if str(value).strip()
    }
    grounded_claims = [
        item for item in result.get("claims") or []
        if isinstance(item, dict)
        and item.get("sourceType") in {"material", "reference_document"}
        and any(str(value).strip() in frame_ids for value in item.get("sourceFrameIds") or [])
    ]
    evidence_text = "\n".join(str(item.get("text") or "") for item in grounded_claims)

    def normalized(value: Any) -> str:
        return re.sub(r"[\s，。；：、,.!?%％（）()\-_—]", "", str(value or "")).casefold()

    supported_parameters: dict[str, Any] = {}
    unsupported_parameter_names: list[str] = []
    for name, raw in (result.get("parameters") or {}).items():
        metadata = raw if isinstance(raw, dict) else {"value": raw}
        value = metadata.get("value")
        source = str(metadata.get("source") or "").strip()
        value_token = normalized(value)
        value_supported = bool(
            value_token
            and value_token not in {"待确认", "未知", "unknown", "pending"}
            and value_token in normalized(evidence_text)
        )
        source_supported = not source or source in frame_ids
        if value_supported and source_supported:
            supported_parameters[str(name)] = copy.deepcopy(raw)
        else:
            unsupported_parameter_names.append(str(name))
    result["parameters"] = supported_parameters

    supported_schema = []
    for row in result.get("parameterSchema") or []:
        if (isinstance(row, dict)
                and row.get("evidenceLevel") in {"reference_document", "planner"}
                and str(row.get("referenceSource") or "").strip()):
            supported_schema.append(copy.deepcopy(row))
        elif isinstance(row, dict):
            unsupported_parameter_names.append(str(row.get("name") or "相关参数"))
    if supported_schema:
        result["parameterSchema"] = supported_schema
    else:
        result.pop("parameterSchema", None)

    supported_formulae = []
    unsupported_formula_names: list[str] = []
    for row in result.get("formulae") or []:
        if (isinstance(row, dict)
                and row.get("evidenceLevel") in {"reference_document", "planner"}
                and str(row.get("referenceSource") or "").strip()):
            supported_formulae.append(copy.deepcopy(row))
        elif isinstance(row, dict):
            unsupported_formula_names.append(str(row.get("name") or row.get("expression") or "相关公式"))
    if supported_formulae:
        result["formulae"] = supported_formulae
    else:
        result.pop("formulae", None)

    mechanism_type = str((result.get("mechanism") or {}).get("type") or result.get("mechanismType") or "custom")
    result["mechanism"] = {"type": mechanism_type}

    removed_acceptance = [
        item for item in result.get("acceptanceCases") or []
        if not _has_evidence(item)
    ]
    result["acceptanceCases"] = [
        copy.deepcopy(item) for item in result.get("acceptanceCases") or []
        if _has_evidence(item)
    ]
    for field in ("workedExamples", "configurationSources", "attributeSections"):
        supported = [
            copy.deepcopy(item) for item in result.get(field) or []
            if _has_evidence(item)
        ]
        if supported:
            result[field] = supported
        else:
            result.pop(field, None)

    cards = [copy.deepcopy(card) for card in result.get("decisionCards") or [] if isinstance(card, dict)]

    def append_card(question: str, options: list[dict[str, str]], impacts: list[str]) -> None:
        if any(str(card.get("question") or "").strip() == question for card in cards):
            return
        used = {str(card.get("id") or "") for card in cards}
        index = 1
        while f"GDC-{index:03d}" in used:
            index += 1
        cards.append({
            "id": f"GDC-{index:03d}",
            "question": question,
            "selectionMode": "single",
            "options": options,
            "recommendedOptionId": options[-1]["id"],
            "recommendationReason": "当前素材不足以把该内容写成已确认规则。",
            "allowCustom": True,
            "evidence": ([{"frameId": value, "label": "当前章节参考画面"} for value in sorted(frame_ids)]
                         or [{"reference": "当前章节缺少可核对依据"}]),
            "impacts": impacts,
            "status": "pending",
        })

    scope = _text(result.get("scope") or result.get("title")) or "本机制"
    if unsupported_parameter_names:
        labels = "、".join(dict.fromkeys(unsupported_parameter_names))
        append_card(
            f"当前素材无法核对“{scope}”的{labels}，这些数值如何处理？",
            [{"id": "configure", "label": "由策划补齐并标明来源"}, {"id": "omit", "label": "本章暂不发布这些数值"}],
            ["参数表", "玩法正文", "验收用例", "最终文档"],
        )
    if unsupported_formula_names:
        labels = "、".join(dict.fromkeys(unsupported_formula_names))
        append_card(
            f"当前素材无法证明“{scope}”的{labels}计算关系，该公式如何处理？",
            [{"id": "configure", "label": "由策划补齐公式与变量来源"}, {"id": "omit", "label": "本章暂不发布该公式"}],
            ["计算公式", "参数表", "玩法正文", "验收用例", "最终文档"],
        )
    if removed_acceptance or not result["acceptanceCases"]:
        append_card(
            f"“{scope}”的玩家操作、系统反馈、结果状态和出口应如何定义？",
            [{"id": "complete", "label": "按已确认交互补齐完整链路"}, {"id": "rule_only", "label": "本章只保留已证实规则事实"}],
            ["玩法流程", "验收用例", "图解", "最终文档"],
        )
    result["decisionCards"] = cards
    result["evidenceSanitized"] = True
    return result


def optional_module_errors(chapter: dict[str, Any]) -> list[str]:
    try:
        normalize_optional_modules(chapter)
    except ValueError as exc:
        return [str(exc)]
    return []


def _is_visual_only(text: str) -> bool:
    has_visual_term = any(term in text for term in _CHINESE_VISUAL_TERMS) or bool(_VISUAL_ONLY.search(text))
    return has_visual_term and not any(term in text for term in _BUSINESS_RULE_TERMS)


_VISUAL_ONLY = re.compile(
    r"(?:屏幕|界面|页面|弹窗|按钮|图标|边框|背景|颜色|高亮|特效|飘字|左上|右上|左侧|右侧|上方|下方|中央|显示|展示)",
    re.I,
)

_SUMMARY_BY_TYPE = {
    "core_loop": "玩家持续完成核心操作并推进目标，直到达成胜利或进入失败结算。",
    "entity_behavior": "场上单位按照既定规则出现、移动、攻击并处理受击与死亡。",
    "formula": "战斗结果由参与计算的属性、加成顺序和边界规则共同决定。",
    "progression": "玩家投入成长资源提升能力，达到上限前持续获得对应增益。",
    "random_pool": "玩家在局内成长时选择一项强化，使本局能力发生变化。",
    "economy_reward": "玩家通过指定玩法获得并结算资源，奖励按照完成进度累计。",
    "level_wave": "玩家依次完成关卡中的各个阶段，并按推进结果获得对应奖励。",
    "buff_chain": "强化效果作用于指定能力，并按照持续、叠加和移除规则改变战斗结果。",
    "settlement": "系统根据本次挑战结果、完成进度和统计数据进行结算。",
    "external_entry": "玩家满足解锁和消耗条件后进入玩法，并按照挑战结果获得奖励。",
    "statistics_feedback": "系统持续汇总本次玩法数据，供玩家查看当前表现和结果。",
}

_FLOW_FIELDS = {
    "core_loop": ("trigger", "phaseOrder", "completion"),
    "entity_behavior": ("spawn", "movement", "attack", "hit", "death"),
    "formula": ("inputs", "formula", "stackOrder", "rounding", "example"),
    "progression": ("unlock", "cost", "levels", "effect"),
    "random_pool": ("eligibility", "drawOrder", "temporaryResult", "confirm", "reroll", "reset"),
    "economy_reward": ("sources", "costs", "accumulation", "settlement"),
    "level_wave": ("entry", "phaseOrder", "movement", "spawns", "completion", "reward"),
    "buff_chain": ("trigger", "target", "calculation", "stacks", "duration", "removal"),
    "settlement": ("win", "failure", "rewardBoundary", "statistics", "exit"),
    "external_entry": ("unlock", "eligibility", "entryCost", "costTiming", "sweep", "rewards"),
    "statistics_feedback": ("metric", "aggregation", "refresh", "sorting", "reset"),
}

_SPECIAL_FIELDS = {
    "core_loop": ("failure", "reset"),
    "entity_behavior": ("targeting", "cooldown"),
    "formula": ("ranges", "rounding"),
    "progression": ("cap", "reset"),
    "random_pool": ("exclusions", "replacementRule", "emptyResult", "cost", "reset"),
    "economy_reward": ("failure", "lifecycle"),
    "level_wave": ("multipliers",),
    "buff_chain": ("replacement", "removal"),
    "settlement": ("failure", "messages"),
    "external_entry": ("failureRefund",),
    "statistics_feedback": ("displayStates", "reset"),
}

_UNIT_LABELS = {
    "count": "个", "level": "级", "seconds": "秒", "second": "秒", "damage": "点",
    "percent": "%", "hp": "点", "string": "", "text": "", "n/a": "", "-": "",
}


def _planner_language(value: str) -> str:
    replacements = (
        (r"局内随机成长局内成长系统", "局内随机成长系统"),
        (r"进入词条库", "加入强化内容库"), (r"终极词条", "终极强化"),
        (r"词条库", "强化内容库"), (r"词条", "强化效果"),
        (r"随机数生成", "随机抽取"),
        (r"Roguelike\s*式?", "局内随机成长"), (r"Buff", "强化效果"),
        (r"Build", "能力组合"), (r"Boss", "首领"), (r"RNG", "随机机制"),
        (r"Roll", "刷新"),
    )
    text = value
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text


def _text(value: Any) -> str:
    if isinstance(value, str):
        return _planner_language(value.strip())
    if isinstance(value, dict):
        for key in ("text", "description", "value", "rule", "expected"):
            if isinstance(value.get(key), str) and value[key].strip():
                return _planner_language(value[key].strip())
    if value in (None, "", [], {}):
        return ""
    return str(value).strip()


def _abstract_claim(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    if "选择后" in text and "武器栏" in text:
        return "玩家选择新武器后，该武器加入本局可用武器，并使攻击方式发生变化。"
    if "刷新" in text and any(term in text for term in ("三个选项", "三项", "重置当前")):
        return "玩家满足刷新条件后，可将当前三项候选强化替换为新候选。"
    text = re.sub(r"(?:屏幕|页面|界面)(?:左上角|右上角|左侧|右侧|上方|下方|中央|底部)?", "", text)
    text = re.sub(r"弹出[^，。]*(?:界面|弹窗)[，,]?", "", text)
    text = re.sub(r"(?:左上角|右上角|左侧|右侧|上方|下方|中央|底部)", "", text)
    text = re.sub(r"(?:图标|边框|背景|颜色|特效)", "", text)
    text = re.sub(r"[‘’'\"]", "", text)
    text = re.sub(r"\s+", "", text).strip("，,；;。")
    gameplay_verbs = ("触发", "选择", "提供", "获得", "攻击", "击杀", "推进", "升级", "强化", "刷新", "结算", "解锁", "进入", "暂停", "继续", "消耗", "掉落")
    if not text or not any(verb in text for verb in gameplay_verbs):
        return ""
    return text + "。"


def _parameter_rules(parameters: Any) -> list[str]:
    if not isinstance(parameters, dict):
        return []
    result = []
    for name, raw in parameters.items():
        metadata = raw if isinstance(raw, dict) else {"value": raw}
        value = _text(metadata.get("value"))
        if not value or value in {"待确认", "未知"}:
            continue
        unit_raw = _text(metadata.get("unit")).casefold()
        unit = _UNIT_LABELS.get(unit_raw, _text(metadata.get("unit")))
        if unit and value.endswith(unit):
            unit = ""
        sentence = f"{_planner_language(str(name))}为{value}{unit}。"
        if sentence not in result:
            result.append(sentence)
    return result


def _sentences(mechanism: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for field in fields:
        value = mechanism.get(field)
        values = value if isinstance(value, list) else [value]
        for item in values:
            text = _text(item)
            if text and not _is_visual_only(text) and text not in result:
                result.append(text.rstrip("；。") + "。")
    return result


def planner_sections(chapter: dict[str, Any]) -> dict[str, Any]:
    mechanism = chapter.get("mechanism") if isinstance(chapter.get("mechanism"), dict) else {}
    mechanism_type = str(mechanism.get("type") or chapter.get("mechanismType") or "")
    description = _text(mechanism.get("description"))
    summary = description.rstrip("；。") + "。" if description and not _is_visual_only(description) else _SUMMARY_BY_TYPE.get(mechanism_type)
    if not summary:
        summary = chapter_gameplay_summary(chapter).rstrip("；。") + "。"
    normal_flow = _sentences(mechanism, _FLOW_FIELDS.get(mechanism_type, ()))
    if not normal_flow:
        description = _text(mechanism.get("description"))
        if description and not _is_visual_only(description):
            normal_flow = [description.rstrip("；。") + "。"]
    if chapter.get("executionSequence"):
        normal_flow = [item.rstrip("；。") + "。" for item in (_text(value) for value in chapter.get("executionSequence") or []) if item]
    for claim in chapter.get("claims") or []:
        abstracted = _abstract_claim(claim.get("text") if isinstance(claim, dict) else claim)
        if abstracted and abstracted not in normal_flow:
            normal_flow.append(abstracted)
    normal_flow = normal_flow[:4]
    key_rules = _sentences(mechanism, tuple(
        key for key in mechanism
        if key not in {"type", "description"}
        and key not in _SPECIAL_FIELDS.get(mechanism_type, ())
        and key not in _FLOW_FIELDS.get(mechanism_type, ())
    ))
    special_cases = _sentences(mechanism, _SPECIAL_FIELDS.get(mechanism_type, ()))
    if chapter.get("boundaryRules"):
        special_cases = [item.rstrip("；。") + "。" for item in (_text(value) for value in chapter.get("boundaryRules") or []) if item]
    structured_rules = []
    for field in ("contentInventory", "lifecycle", "lifecycleRules", "runtimeResponsibilities", "responsibilitySequence", "presentationRules", "carrierContract"):
        values = chapter.get(field) if isinstance(chapter.get(field), list) else [chapter.get(field)]
        for value in values:
            text = _text(value)
            if text and text not in structured_rules:
                structured_rules.append(text.rstrip("；。") + "。")
    if structured_rules:
        key_rules = list(dict.fromkeys([*key_rules, *structured_rules]))
    acceptance = []
    for item in chapter.get("acceptanceCases") or []:
        if isinstance(item, dict):
            premise = _text(item.get("scene") or item.get("title") or item.get("case")) + _text(item.get("action") or item.get("when") or item.get("input"))
            if any(word in premise for word in ("或", "可能", "推测", "待确认", "无法确认")):
                continue
            acceptance.append({
                "scene": _text(item.get("scene") or item.get("title") or item.get("case")),
                "action": _text(item.get("action") or item.get("when") or item.get("input")),
                "expected": _text(item.get("expected") or item.get("result")),
            })
    raw_attribute_sections = chapter.get("attributeSections")
    if not isinstance(raw_attribute_sections, list):
        existing_sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        raw_attribute_sections = existing_sections.get("attributeSections") or []
    attribute_sections = []
    for group in raw_attribute_sections:
        if not isinstance(group, dict):
            continue
        heading = _text(group.get("heading"))
        items = list(dict.fromkeys(
            text for text in (_text(item) for item in group.get("items") or []) if text
        ))
        if heading and items:
            attribute_sections.append({"heading": heading, "items": items})
    return {
        "summary": summary,
        "normalFlow": normal_flow,
        "keyRules": key_rules,
        "specialCases": special_cases,
        "attributeHeading": _text(chapter.get("attributeHeading") or (
            (chapter.get("plannerSections") or {}).get("attributeHeading")
            if isinstance(chapter.get("plannerSections"), dict) else ""
        )),
        "attributeSections": attribute_sections,
        "acceptanceExamples": acceptance,
    }


def _route_generated_planner_carriers(sections: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Keep generated gameplay prose semantic while moving visual clauses to P5."""
    routed = copy.deepcopy(sections)
    presentation: list[str] = []

    def sentence(value: str) -> str:
        return value.strip(" ；。") + "。"

    def route_text(value: Any) -> str:
        text = _text(value)
        if not text:
            return ""
        logic, visual = split_rule_carriers(text)
        if visual:
            presentation.append(sentence(visual))
        return sentence(logic) if logic else ""

    for field in ("normalFlow", "keyRules", "specialCases"):
        logic_items: list[str] = []
        for raw in routed.get(field) or []:
            if logic := route_text(raw):
                logic_items.append(logic)
        routed[field] = list(dict.fromkeys(logic_items))

    summary = _text(routed.get("summary"))
    if summary and rule_carrier(summary) != "logic":
        routed["summary"] = route_text(summary)

    routed_attribute_heading = route_text(routed.get("attributeHeading"))
    routed["attributeHeading"] = routed_attribute_heading.rstrip("。")

    attribute_sections: list[dict[str, Any]] = []
    for group in routed.get("attributeSections") or []:
        if not isinstance(group, dict):
            continue
        heading = route_text(group.get("heading") or group.get("title"))
        items = list(dict.fromkeys(
            logic for raw in group.get("items") or [] if (logic := route_text(raw))
        ))
        if heading and items:
            attribute_sections.append({"heading": heading.rstrip("。"), "items": items})
    routed["attributeSections"] = attribute_sections

    acceptance_examples: list[dict[str, str]] = []
    for item in routed.get("acceptanceExamples") or []:
        if not isinstance(item, dict):
            continue
        candidate = {
            field: route_text(item.get(field))
            for field in ("scene", "action", "expected")
        }
        if all(candidate.values()):
            acceptance_examples.append(candidate)
    routed["acceptanceExamples"] = acceptance_examples
    return routed, list(dict.fromkeys(presentation))


def _evidence_first_planner_sections(chapter: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Build review copy from cited claims instead of unverified model prose."""
    flow: list[str] = []
    key_rules: list[str] = []
    presentation: list[str] = []
    for claim in chapter.get("claims") or []:
        if not isinstance(claim, dict) or claim.get("sourceType") not in {"material", "reference_document"}:
            continue
        text = _text(claim.get("text"))
        if not text:
            continue
        if abstracted := _abstract_claim(text):
            flow.append(abstracted)
            continue
        logic, visual = split_rule_carriers(text)
        if logic:
            key_rules.append(logic.strip(" ；。") + "。")
        if visual:
            presentation.append(visual.strip(" ；。") + "。")
    scope = _text(chapter.get("scope") or chapter.get("title")) or "当前机制"
    summary_source = flow or key_rules
    summary = "".join(summary_source[:2]) if summary_source else (
        f"当前素材已确认“{scope}”的可见信息；具体操作、反馈和边界需通过决策卡确认。"
    )
    return ({
        "summary": summary,
        "normalFlow": list(dict.fromkeys(flow)),
        "keyRules": list(dict.fromkeys(key_rules)),
        "specialCases": [],
        "attributeHeading": "",
        "attributeSections": [],
        "acceptanceExamples": [],
    }, list(dict.fromkeys(presentation)))


def _route_incomplete_flow_to_planner_decision(chapter: dict[str, Any]) -> dict[str, Any]:
    """Keep a grounded rule fact without pretending it is a complete player flow."""
    report = flow_chain_report(chapter)
    if not report.get("declared") or report.get("passed"):
        return chapter
    sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    incomplete_flow = [str(item).strip() for item in sections.get("normalFlow") or [] if str(item).strip()]
    sections["normalFlow"] = []
    sections["keyRules"] = list(dict.fromkeys([
        *[str(item).strip() for item in sections.get("keyRules") or [] if str(item).strip()],
        *incomplete_flow,
    ]))

    scope = _text(chapter.get("scope") or chapter.get("title")) or "本机制"
    question = f"现有素材不足以闭合“{scope}”的触发、玩家操作、系统反馈和结果出口，应如何定义？"
    cards = [card for card in chapter.get("decisionCards") or [] if isinstance(card, dict)]
    if not any(str(card.get("question") or "").strip() == question for card in cards):
        used = {str(card.get("id") or "") for card in cards}
        index = 1
        while f"GDC-{index:03d}" in used:
            index += 1
        frame_ids = [str(item).strip() for item in chapter.get("sourceFrameIds") or [] if str(item).strip()]
        cards.append({
            "id": f"GDC-{index:03d}",
            "question": question,
            "selectionMode": "single",
            "options": [
                {"id": "complete_flow", "label": "按已确认交互补齐完整操作链"},
                {"id": "rule_only", "label": "本章仅保留规则事实，不设独立操作流程"},
            ],
            "recommendedOptionId": "rule_only",
            "recommendationReason": "当前素材只证明了规则结果，尚不足以确定完整操作链。",
            "allowCustom": True,
            "evidence": ([{"frameId": item, "label": "当前章节参考画面"} for item in frame_ids]
                         or [{"reference": "当前章节素材未提供完整操作链"}]),
            "impacts": ["玩法流程", "验收用例", "图解", "最终文档"],
            "status": "pending",
        })
    chapter["decisionCards"] = cards
    return chapter


def enrich_gameplay_draft(draft: dict[str, Any]) -> dict[str, Any]:
    enriched = normalize_optional_modules(draft)
    claims = [item for item in enriched.get("claims") or [] if isinstance(item, dict)]
    enriched["evidenceClaims"] = copy.deepcopy(claims)
    raw_presentation: list[str] = []
    mechanism = enriched.get("mechanism") if isinstance(enriched.get("mechanism"), dict) else {}
    for key, raw in mechanism.items():
        if key == "type":
            continue
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            text = _text(value)
            if not text:
                continue
            _logic, visual = split_rule_carriers(text)
            if visual:
                raw_presentation.append(visual.strip(" ；。") + "。")
    if enriched.get("evidenceSanitized") is True:
        sections, presentation = _evidence_first_planner_sections(enriched)
    else:
        sections, presentation = _route_generated_planner_carriers(planner_sections(enriched))
    enriched["plannerSections"] = sections
    if presentation or raw_presentation:
        enriched["presentationRules"] = list(dict.fromkeys([
            *[str(item).strip() for item in enriched.get("presentationRules") or [] if str(item).strip()],
            *raw_presentation,
            *presentation,
        ]))
    return _route_incomplete_flow_to_planner_decision(enriched)


def legacy_planner_sections_adapter(chapter: dict[str, Any]) -> dict[str, Any]:
    """The sole compatibility entrance for v1 prose-based gameplay copy."""
    sections = chapter.get("plannerSections")
    return copy.deepcopy(sections) if isinstance(sections, dict) else planner_sections(chapter)


def migrate_gameplay_rule_copy(job: dict[str, Any]) -> dict[str, Any]:
    model = job.get("gameplayReviewModel")
    if not isinstance(model, dict):
        return job
    if model.get("contentModelVersion") == 2:
        for chapter in model.get("chapters") or []:
            if isinstance(chapter, dict):
                chapter.pop("plannerSections", None)
        model["ruleCopyVersion"] = 5
        return job
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter.setdefault("evidenceClaims", copy.deepcopy(chapter.get("claims") or []))
        confirmation = chapter.get("confirmation")
        explicitly_unconfirmed = isinstance(confirmation, dict) and confirmation.get("confirmed") is False
        sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        old_summary = _text(sections.get("summary"))
        auto_generated_or_visual = (
            not old_summary or _is_visual_only(old_summary) or old_summary.endswith("的玩法规则。")
        )
        if explicitly_unconfirmed or auto_generated_or_visual:
            chapter["plannerSections"] = planner_sections(chapter)
    model["ruleCopyVersion"] = 4
    return job
