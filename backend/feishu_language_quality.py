from __future__ import annotations

import re
from typing import Any


_FILLER = re.compile(r"(?:本节主要(?:介绍|说明)|该机制(?:具有|起到).{0,10}(?:作用|意义)|玩家可以进行相关操作|需要注意的是)")
_ABSTRACT = re.compile(r"(?:候选刷新|状态隔离|生命周期管理|进行相关操作|相关内容|有关机制|闭环|收口)")
_FIXED_HEADINGS = {"正常怎么玩", "关键规则", "特殊情况", "怎么验证", "配置来源", "计算公式", "计算示例"}
_REVIEW_META = re.compile(r"(?:流程图只(?:确定|说明)|素材只证明|仍由决策卡确认|不从流程图推断|图中的.{0,24}由后续章节|本节继续说明|留待(?:阶段|策划|决策卡).{0,8}(?:确认|验证)|需由(?:策划)?决策.{0,8}(?:固化|确认))")
_TEMPLATE_TITLE = re.compile(
    r"^.{1,10}[、，].{1,10}(?:与|和).{1,12}(?:归集|联动|反馈|状态|机制|管理|处理|使用|承接)$"
)
_AUDIT_VOICE = re.compile(
    r"(?:当前项目应|本文档应|本次(?:输出|生成)应|应逐项保留|不能概括处理|不得笼统描述|需要补齐|尚未覆盖|对齐样例)"
)
_EMPTY_ABSTRACTION = re.compile(
    r"^(?:本节|本部分|该部分)?(?:主要)?用于(?:承接|说明|介绍|覆盖)(?:后续|相关)?(?:玩法|业务|机制|内容|规则)*(?:内容|规则)?[。.]?$"
)
_REPEATED_CADENCE_SUBJECT = re.compile(r"^(?:玩家|系统).+并.+")
_LOGIC_CUE = re.compile(
    r"(?:进入|达到|满足|命中|离开|确认|选择|消耗|扣除|写入|生成|重置|停止|恢复|自动前进|开始攻击|不可|上限|归零)"
)
_PRESENTATION_CUE = re.compile(
    r"(?:(?:画面|屏幕|截图|界面|页面)(?:中|上)?(?:显示|展示|可见|出现)|"
    r"(?:上方|下方|左侧|右侧|顶部|底部|红色|蓝色|挂载|常驻显示|图标位置|按钮位置|播放动画|闪烁|描边|字号|颜色).{0,12}(?:显示|生命条|图标|按钮|动画|特效)?)"
)
_COMMON_KNOWLEDGE = re.compile(
    r"^(?:玩家可以通过操作(?:来)?(?:控制|进行|完成).+|界面(?:会|将)?显示相关内容|系统(?:会|将)?进行相应处理|该功能用于提供相关功能)[。]?$"
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return "\n".join(filter(None, (_text(item) for item in value.values())))
    if isinstance(value, (list, tuple)):
        return "\n".join(filter(None, (_text(item) for item in value)))
    return ""


def _normalized(value: Any) -> str:
    return re.sub(r"[\s，。；：、,.!?！？（）()\-—]", "", _text(value)).casefold()


def rule_carrier(text: str) -> str:
    has_logic = bool(_LOGIC_CUE.search(text or ""))
    has_presentation = bool(_PRESENTATION_CUE.search(text or ""))
    if has_logic and has_presentation:
        return "mixed"
    if has_presentation:
        return "presentation"
    return "logic"


def split_rule_carriers(text: str) -> tuple[str, str]:
    """Split complete clauses without inventing a missing gameplay transition."""
    logic: list[str] = []
    presentation: list[str] = []
    for clause in [item.strip(" ，；。") for item in re.split(r"[，；]", text or "") if item.strip(" ，；。")]:
        carrier = rule_carrier(clause)
        if carrier == "presentation":
            presentation.append(clause)
        elif carrier == "logic":
            logic.append(clause)
        else:
            presentation.append(clause)
    return "；".join(logic), "；".join(presentation)


def _language_remediation(code: str, message: str) -> dict[str, str]:
    actions = {
        "LANGUAGE_FILLER": "删除无信息开场或总结，直接写条件、对象、动作和结果。",
        "LANGUAGE_ABSTRACT_TERM": "将抽象术语改写为具体对象、动作和结果。",
        "LANGUAGE_FIXED_HEADING": "删除固定模板标题，按当前机制的信息量合并或改为业务标题。",
        "LANGUAGE_CARRIER_DUPLICATION": "保留表格中的字段和值，正文删除复述，只保留因果、约束和边界。",
        "LANGUAGE_CROSS_CHAPTER_DUPLICATION": "选择一个主章节保留完整说明，其他章节删除重复段落并改为短引用。",
        "LANGUAGE_REVIEW_META": "从正式正文和图解说明中删除审核过程、证据能力与决策卡状态，只保留玩家条件、系统动作、结果和边界。",
        "LANGUAGE_TEMPLATE_TITLE": "将编辑式复合标题改为机制对象或策划常用业务名；确有多个独立机制时拆成章节。",
        "LANGUAGE_AUDIT_VOICE": "删除检查报告式措辞，直接写当前项目已经成立的玩法条件、动作、结果或边界。",
        "LANGUAGE_REPEATED_CADENCE": "合并同一动作链中的短句，并交替使用条件句、结果句和必要的分点，避免连续同句式罗列。",
        "LANGUAGE_EMPTY_ABSTRACTION": "删除只承担过渡作用的句子，直接从该机制的触发条件或核心规则开始。",
        "LANGUAGE_LOGIC_PRESENTATION_MIXED": "拆成逻辑规则与表现规则；正文保留触发、状态和结果，位置、颜色、挂载和动画移入策划草图。",
        "LANGUAGE_PRESENTATION_IN_PROSE": "将纯布局、颜色、挂载或动画要求移入策划草图；正文只保留会影响实现和测试的反馈语义。",
        "LANGUAGE_COMMON_KNOWLEDGE": "删除没有新增操作、状态、配置、边界或测试条件的常识句，直接写项目特有规则。",
    }
    return {
        "basis": message,
        "action": actions.get(code, "按问题说明修改对应句子。"),
        "carrier": "玩法正文",
        "impact": "同步更新审核页、P7 预览和飞书正文；修复前保持导出阻断。",
        "retest": "保存后重新运行语言检查，确认原问题消失且业务事实没有丢失。",
    }


def language_quality_report(model: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    chapters: list[dict[str, Any]] = []
    chapter_bodies: list[tuple[str, str, str]] = []
    top_level_tables = [item for item in model.get("tables") or [] if isinstance(item, dict) and item.get("status") != "deleted"]
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id") or "chapter")
        title = str(chapter.get("scope") or chapter.get("title") or "当前章节")
        planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        # Evidence claims remain traceable but are not published as gameplay copy.
        # Carrier duplication must therefore inspect the actual published carrier,
        # not flag a screenshot caption that never enters P7/Feishu正文.
        # Diagram placement/followUp is also editor metadata and is deliberately
        # excluded by the renderer; invisible legacy notes must not block export.
        body = _text([chapter.get("bodyText"), planner, chapter.get("rules")])
        chapter_bodies.append((chapter_id, title, _normalized(body)))
        if _FILLER.search(body):
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_FILLER", "message": f"《{title}》存在没有新增业务信息的开场或总结句。"})
        if _REVIEW_META.search(body):
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_REVIEW_META", "message": f"《{title}》混入了审核过程、证据能力或决策卡状态说明；这些内容不属于正式玩法规则。"})
        if _TEMPLATE_TITLE.fullmatch(title):
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_TEMPLATE_TITLE", "message": f"《{title}》使用了编辑式复合标题，没有直接对应单一玩法对象或机制。"})
        if _AUDIT_VOICE.search(body):
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_AUDIT_VOICE", "message": f"《{title}》使用了审核报告或生成指令语气，没有直接陈述玩法事实。"})
        sentences = [item.strip() for item in re.split(r"[。！？!?\n]+", body) if item.strip()]
        for sentence in sentences:
            carrier = rule_carrier(sentence)
            if carrier == "mixed":
                findings.append({"chapterId": chapter_id, "code": "LANGUAGE_LOGIC_PRESENTATION_MIXED", "message": f"《{title}》把逻辑状态与位置、颜色、挂载或动画表现写在了同一条规则中。"})
            elif carrier == "presentation":
                findings.append({"chapterId": chapter_id, "code": "LANGUAGE_PRESENTATION_IN_PROSE", "message": f"《{title}》正文包含只属于策划草图的纯表现说明。"})
            if _COMMON_KNOWLEDGE.fullmatch(sentence):
                findings.append({"chapterId": chapter_id, "code": "LANGUAGE_COMMON_KNOWLEDGE", "message": f"《{title}》包含没有新增实现或测试约束的常识句：{sentence}。"})
        if sum(bool(_REPEATED_CADENCE_SUBJECT.match(item)) for item in sentences) >= 3:
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_REPEATED_CADENCE", "message": f"《{title}》连续使用相同的“玩家/系统 + 动作 + 并”句式，阅读节奏机械。"})
        if any(_EMPTY_ABSTRACTION.fullmatch(item) for item in sentences):
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_EMPTY_ABSTRACTION", "message": f"《{title}》包含只用于过渡、没有新增玩法信息的抽象句。"})
        for term in dict.fromkeys(_ABSTRACT.findall(body)):
            findings.append({
                "chapterId": chapter_id,
                "code": "LANGUAGE_ABSTRACT_TERM",
                "message": f"《{title}》使用了没有直接说明业务事实的词语“{term}”，请改写为具体对象、动作和结果。",
            })
        headings = {_text(item) for item in chapter.get("publishedHeadings") or []}
        if headings & _FIXED_HEADINGS:
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_FIXED_HEADING", "message": f"《{title}》仍在使用固定模板标题。"})

        # Attribute prose intentionally repeats the business value needed to
        # explain behavior; the table remains the compact lookup carrier.
        # Other published prose must still avoid copying a table payload.
        duplication_planner = {key: value for key, value in planner.items() if key != "attributeSections"}
        duplication_body = _text([chapter.get("bodyText"), duplication_planner, [] if planner else chapter.get("rules")])
        body_normalized = _normalized(duplication_body)
        duplicated: list[str] = []
        related_tables = list(chapter.get("tables") or [])
        related_tables.extend(table for table in top_level_tables if chapter_id in (table.get("chapterIds") or []))
        for table in related_tables:
            if not isinstance(table, dict):
                continue
            for row in table.get("rows") or []:
                # The first cell is normally the business field/attribute name.
                # Repeating that name in nearby prose is required for readable
                # behavior-to-configuration mapping; only duplicated values and
                # explanatory payload are considered carrier duplication.
                for cell in (row[1:] if isinstance(row, list) else []):
                    cell_text = _text(cell)
                    normalized = _normalized(cell_text)
                    # Short enum labels/IDs (BOSS, PVP, item_id) legitimately
                    # appear in both prose and lookup tables. They are not a
                    # duplicated explanation and must not block publishing.
                    meaningful_payload = len(normalized) >= 8 or (bool(re.search(r"\d", normalized)) and len(normalized) >= 4)
                    if meaningful_payload and normalized in body_normalized:
                        duplicated.append(cell_text)
        if duplicated:
            findings.append({
                "chapterId": chapter_id,
                "code": "LANGUAGE_CARRIER_DUPLICATION",
                "message": f"《{title}》正文重复了表格已经承载的内容：{duplicated[0]}。",
            })
        chapters.append({"chapterId": chapter_id, "findingCount": 0})
    for index, (chapter_id, title, body) in enumerate(chapter_bodies):
        if len(body) < 16:
            continue
        for other_id, other_title, other_body in chapter_bodies[index + 1:]:
            if body != other_body:
                continue
            message = f"《{title}》与《{other_title}》重复了同一段业务正文；请保留一个主要说明位置，其他章节改用短引用。"
            findings.append({"chapterId": chapter_id, "code": "LANGUAGE_CROSS_CHAPTER_DUPLICATION", "message": message})
            findings.append({"chapterId": other_id, "code": "LANGUAGE_CROSS_CHAPTER_DUPLICATION", "message": message})
    for chapter in chapters:
        chapter["findingCount"] = sum(item["chapterId"] == chapter["chapterId"] for item in findings)
    for item in findings:
        item["remediation"] = _language_remediation(item["code"], item["message"])
    return {"passed": not findings, "findings": findings, "chapters": chapters}


def three_reader_report(model: dict[str, Any]) -> dict[str, Any]:
    """Check whether the draft gives planner intent, implementation behavior and test boundaries."""
    body = _text([
        chapter.get("plannerSections")
        for chapter in model.get("chapters") or []
        if isinstance(chapter, dict)
    ])
    planner = bool(re.search(r"(?:达到|满足|进入|选择|确认|目标|条件|结果)", body))
    programmer = bool(re.search(r"(?:生成|写入|扣除|读取|更新|重置|停止|恢复|计算|立即)", body))
    tester = bool(re.search(r"(?:为空|不足|无效|重复|上限|失败|归零|否则|离开|不可|未满足|异常)", body))
    missing = []
    if not planner:
        missing.append("design_intent")
    if not programmer:
        missing.append("implementation_behavior")
    if not tester:
        missing.append("test_boundary")
    return {"passed": not missing, "planner": planner, "programmer": programmer, "tester": tester, "missing": missing}


def handwritten_gap_report(
    *,
    handwritten_roles: set[str],
    generated_roles: set[str],
    supported_roles: set[str],
) -> dict[str, Any]:
    """Compare information roles, not wording, against a planner-written reference."""
    required = set(handwritten_roles) & set(supported_roles)
    missing = sorted(required - set(generated_roles))
    excess = sorted(set(generated_roles) - set(supported_roles))
    return {"passed": not missing and not excess, "missing": missing, "excess": excess}


HANDWRITTEN_DELTA_DIMENSIONS = (
    "机制拆分",
    "规则深度",
    "属性解释",
    "配置映射",
    "执行顺序",
    "异常边界",
    "生命周期",
    "图文关系",
    "语言与排布",
)


def handwritten_delta_matrix(comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build a traceable, actionable comparison against planner-written references."""
    rows: list[dict[str, Any]] = []
    missing_dimensions: list[str] = []
    blocking_dimensions: list[str] = []
    untraced_dimensions: list[str] = []
    unremediated_dimensions: list[str] = []

    for dimension in HANDWRITTEN_DELTA_DIMENSIONS:
        item = comparisons.get(dimension)
        if item is None:
            missing_dimensions.append(dimension)
            continue

        handwritten = list(item.get("handwritten") or [])
        current = list(item.get("current") or [])
        missing = list(item.get("missing") or [])
        excess = list(item.get("excess") or [])
        remediation = list(item.get("remediation") or [])
        handwritten_refs = list(item.get("handwritten_refs") or [])
        current_refs = list(item.get("current_refs") or [])

        if missing or excess:
            blocking_dimensions.append(dimension)
        if (handwritten or missing) and not handwritten_refs or (current or excess) and not current_refs:
            untraced_dimensions.append(dimension)
        if (missing or excess) and not remediation:
            unremediated_dimensions.append(dimension)

        rows.append({
            "维度": dimension,
            "手写文档有": handwritten,
            "当前输出有": current,
            "缺失": missing,
            "多余或错误": excess,
            "改善方式": remediation,
            "手写依据": handwritten_refs,
            "当前依据": current_refs,
        })

    passed = not (
        missing_dimensions
        or blocking_dimensions
        or untraced_dimensions
        or unremediated_dimensions
    )
    return {
        "passed": passed,
        "rows": rows,
        "missingDimensions": missing_dimensions,
        "blockingDimensions": blocking_dimensions,
        "untracedDimensions": untraced_dimensions,
        "unremediatedDimensions": unremediated_dimensions,
    }
