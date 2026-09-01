from __future__ import annotations

from typing import Any

from .feishu_language_quality import language_quality_report
from .granularity_audit import AXES, granularity_audit_report


SAMPLE_METHODS = {
    "overviewTraceability": "同类样例的玩法介绍是后文索引，每个核心循环、成长、资源和胜负结论都有详细落点。",
    "contentInventory": "同类样例在对象确有差异时逐项列出，不使用“存在多种内容”概括。",
    "objectState": "同类样例区分对象、状态、关系以及局内/局外或临时/永久生命周期。",
    "attributeNarrative": "同类样例先在对象行为附近逐项解释属性含义、计算或判断作用、时机与边界，再用表格集中查配。",
    "configuration": "同类样例由正文解释行为含义，表格承担字段、单位、范围和值。",
    "executionSequence": "同类样例仅在顺序影响结果时展开步骤，短序列保持紧凑。",
    "formula": "同类样例先定义变量，再给表达式、顺序、取整和有完整数值依据的算例。",
    "boundary": "同类样例把失败、空结果、重复或容量边界贴近受影响规则。",
    "lifecycle": "同类样例明确区分暂存、保存、中断恢复和结束重置的实际范围。",
    "interactionFeedback": "同类样例按触发或操作、系统反馈、结果的因果顺序表达。",
    "runtimeResponsibility": "同类样例在职责影响实现时明确执行方、同步节点和校验时机。",
    "presentationContract": "同类样例把动画、显示、排序或样式验收与隐藏玩法逻辑分开。",
    "scopeStatus": "同类样例保留取消、延期和历史规则的可追溯状态，但不让它们进入当前正式流程。",
}


def _applicable(spec: Any) -> bool:
    if spec is True:
        return True
    return isinstance(spec, dict) and bool(spec.get("applicable") or spec.get("sourceIds") or spec.get("sources"))


def sample_alignment_report(model: dict[str, Any]) -> dict[str, Any]:
    granularity = granularity_audit_report(model)
    language = language_quality_report(model)
    audit_by_chapter = {item["chapterId"]: item for item in granularity.get("chapters") or []}
    missing_by_chapter = {
        (item["chapterId"], item["axis"])
        for item in granularity["findings"]
        if item["axis"] in AXES
    }
    language_by_chapter: dict[str, list[dict[str, str]]] = {}
    for item in language["findings"]:
        language_by_chapter.setdefault(item["chapterId"], []).append(item)
    chapters: list[dict[str, Any]] = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id") or "chapter")
        evidence = chapter.get("granularityEvidence") if isinstance(chapter.get("granularityEvidence"), dict) else {}
        audited_axes = (audit_by_chapter.get(chapter_id) or {}).get("axes") or {}
        rows = []
        for axis, (label, _fields) in AXES.items():
            spec = evidence.get(axis)
            applicable = _applicable(spec)
            status = "not_applicable"
            if applicable:
                status = "missing" if (chapter_id, axis) in missing_by_chapter else "satisfied"
            audit_axis = audited_axes.get(axis) or {}
            source_ids = list(audit_axis.get("sourceIds") or [])
            required_facts = list(audit_axis.get("requiredFacts") or [])
            covered_facts = list(audit_axis.get("coveredFacts") or [])
            missing_facts = list(audit_axis.get("missingFacts") or [])
            if status == "not_applicable":
                explicit_reason = spec.get("notApplicableReason") if isinstance(spec, dict) else ""
                basis = explicit_reason or f"当前素材没有提供可支持{label}的事实，因此不要求生成该部分。"
            elif status == "missing":
                basis = f"来源 {', '.join(source_ids) or '尚未标明'} 已要求说明{label}"
                if missing_facts:
                    basis += f"，正文仍缺少：{'；'.join(missing_facts)}。"
                else:
                    basis += "，但正文尚未承载对应内容。"
            else:
                basis = f"来源 {', '.join(source_ids) or '已登记素材'} 要求的{label}事实均已写入正文。"
            rows.append({
                "axis": axis,
                "label": label,
                "sampleMethod": SAMPLE_METHODS[axis],
                "evidenceApplicable": applicable,
                "status": status,
                "sourceIds": source_ids,
                "requiredFacts": required_facts,
                "coveredFacts": covered_facts,
                "missingFacts": missing_facts,
                "basis": basis,
            })
        chapters.append({
            "chapterId": chapter_id,
            "title": chapter.get("scope") or chapter.get("title") or "当前章节",
            "mechanismType": (chapter.get("mechanism") or {}).get("type") if isinstance(chapter.get("mechanism"), dict) else "custom",
            "granularity": rows,
            "language": {
                "sampleMethod": "按制作价值选择事实，以明确主语组织条件—动作—结果—边界，并按载体去重。",
                "findings": language_by_chapter.get(chapter_id, []),
                "status": "satisfied" if not language_by_chapter.get(chapter_id) else "missing",
            },
        })
    return {
        "passed": granularity["passed"] and language["passed"],
        "chapters": chapters,
        "summary": {
            "missing": sum(row["status"] == "missing" for chapter in chapters for row in chapter["granularity"])
            + sum(chapter["language"]["status"] == "missing" for chapter in chapters),
            "satisfied": sum(row["status"] == "satisfied" for chapter in chapters for row in chapter["granularity"]),
            "notApplicable": sum(row["status"] == "not_applicable" for chapter in chapters for row in chapter["granularity"]),
        },
    }
