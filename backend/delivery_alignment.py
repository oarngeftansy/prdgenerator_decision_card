from __future__ import annotations

import hashlib
import json
from html import escape
from typing import Any

from .gameplay_render import (
    GameplayRenderError,
    _dedupe_similar_rules,
    authoritative_gameplay_model,
    render_gameplay_document_sections,
)
from .planning_gameplay_sync import planning_gameplay_sync_report


def _text(value: Any) -> str:
    return str(value or "").strip()


def _section_text(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("text"))
    return _text(value)


def _digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _remediation(carrier: str, issue: str, action: str) -> dict[str, str]:
    return {
        "basis": f"P7 与飞书必须读取同一发布快照；当前{carrier}未通过同源核对。",
        "action": action,
        "carrier": carrier,
        "impact": "阻止最终预览与飞书导出，避免不同载体发布互相矛盾的规则。",
        "retest": f"重新生成 P7 与飞书后，再次核对{carrier}指纹及可见内容。",
    }


def _contract_payload(model: dict[str, Any]) -> dict[str, Any]:
    model = authoritative_gameplay_model(model)
    chapters = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        chapters.append({
            "id": _text(chapter.get("id")),
            "title": _text(chapter.get("scope") or chapter.get("title")),
            "summary": _text(sections.get("summary")),
            "normalFlow": [_section_text(item) for item in sections.get("normalFlow") or [] if _section_text(item)],
            "keyRules": _dedupe_similar_rules([_section_text(item) for item in sections.get("keyRules") or [] if _section_text(item)]),
            "specialCases": _dedupe_similar_rules([_section_text(item) for item in sections.get("specialCases") or [] if _section_text(item)]),
            "formulae": [{
                "name": _text(item.get("name") or item.get("title")),
                "expression": _text(item.get("expression")),
                "calculationOrder": _text(item.get("calculationOrder")),
                "rounding": _text(item.get("rounding")),
                "example": _text(item.get("example")),
                "variables": item.get("variables") or [],
            } for item in chapter.get("formulae") or [] if isinstance(item, dict)],
        })
    tables = []
    for table in model.get("tables") or []:
        if not isinstance(table, dict) or table.get("status") == "deleted":
            continue
        tables.append({
            "id": _text(table.get("id")),
            "chapterIds": [_text(item) for item in table.get("chapterIds") or []],
            "columns": [_text(item) for item in table.get("columns") or []],
            "rows": [[_text(cell) for cell in row] for row in table.get("rows") or [] if isinstance(row, list)],
        })
    interaction = {
        "revision": model.get("interactionRevision"),
        "frameIds": sorted({_text(item.get("frameId")) for item in model.get("evidenceAnchors") or []
                            if isinstance(item, dict) and _text(item.get("frameId"))}),
    }
    return {"revision": model.get("revision"), "interaction": interaction, "chapters": chapters, "tables": tables}


def canonical_delivery_contract(model: dict[str, Any]) -> dict[str, Any]:
    payload = _contract_payload(model)
    prose = [{key: value for key, value in chapter.items() if key != "formulae"} for chapter in payload["chapters"]]
    formulae = [{"chapterId": chapter["id"], "formulae": chapter["formulae"]} for chapter in payload["chapters"]]
    return {
        **payload,
        "carrierFingerprints": {
            "prose": _digest(prose), "tables": _digest(payload["tables"]),
            "formulae": _digest(formulae), "planningBoard": _digest(payload["interaction"]),
        },
        "fingerprint": _digest(payload),
    }


def delivery_alignment_report(job: dict[str, Any]) -> dict[str, Any]:
    model = job.get("gameplayReviewModel") if isinstance(job.get("gameplayReviewModel"), dict) else {}
    contract = canonical_delivery_contract(model)
    try:
        rendered = render_gameplay_document_sections(job)
    except GameplayRenderError as exc:
        return {
            "passed": False, "fingerprint": contract["fingerprint"], "revision": contract["revision"],
            "expectedChapterOrder": [item["title"] for item in contract["chapters"]],
            "renderedChapterOrder": [], "missingCopy": [], "tableCount": len(contract["tables"]),
            "renderErrors": list(exc.blocker_ids), "differences": [{
                "carrier": "飞书正文", "issue": "渲染被审核门禁阻断",
                "remediation": _remediation("飞书正文", "渲染被审核门禁阻断", "先处理阻断项，再从同一发布快照重新生成。"),
            }],
        }
    missing_copy = []
    for chapter in contract["chapters"]:
        for value in [chapter["summary"], *chapter["normalFlow"], *chapter["keyRules"], *chapter["specialCases"]]:
            if value and escape(value) not in rendered.xml and escape(value.rstrip("。；")) not in rendered.xml:
                missing_copy.append({"chapterId": chapter["id"], "text": value})
        for formula in chapter["formulae"]:
            expression = formula["expression"]
            if expression and escape(expression) not in rendered.xml:
                missing_copy.append({"chapterId": chapter["id"], "carrier": "公式", "text": expression})
    for table in contract["tables"]:
        # Column captions may be normalized by the Feishu renderer; business values may not disappear.
        for value in [cell for row in table["rows"] for cell in row]:
            if value and escape(value) not in rendered.xml:
                missing_copy.append({"tableId": table["id"], "carrier": "配置表", "text": value})
    rendered_titles = [item.get("title") for item in rendered.order if item.get("type") == "gameplay_chapter"]
    expected_titles = [item["title"] for item in contract["chapters"]]
    interaction_revision = job.get("reviewModel", {}).get("revision")
    known_frames = {str(item.get("id")) for item in job.get("frames") or [] if isinstance(item, dict)}
    interaction_ok = contract["interaction"]["revision"] == interaction_revision and all(
        frame_id in known_frames for frame_id in contract["interaction"]["frameIds"]
    )
    differences = []
    planning_sync = planning_gameplay_sync_report(job, model)
    if not planning_sync["passed"]:
        differences.append({"carrier": "策划草图 → 玩法正文", "issue": "存在尚未进入玩法载体的草图解读", "remediation": _remediation(
            "策划草图 → 玩法正文", "存在尚未进入玩法载体的草图解读", "按问题中的目标章节与承载位置重新同步，再生成 P7 和飞书正文。")})
    if missing_copy:
        carriers = sorted({item.get("carrier", "正文") for item in missing_copy})
        for carrier in carriers:
            differences.append({"carrier": carrier, "issue": f"{carrier}内容未进入飞书输出", "remediation": _remediation(
                carrier, f"{carrier}内容未进入飞书输出", f"检查{carrier}渲染映射，并从当前发布快照重新生成飞书正文。")})
    if rendered_titles != expected_titles:
        differences.append({"carrier": "章节目录", "issue": "P7 与飞书章节顺序不一致", "remediation": _remediation(
            "章节目录", "P7 与飞书章节顺序不一致", "移除独立排序数据源，统一读取发布快照中的章节顺序。")})
    if not interaction_ok:
        differences.append({"carrier": "策划草图", "issue": "草图引用的交互版本或截图锚点已失配", "remediation": _remediation(
            "策划草图", "草图引用的交互版本或截图锚点已失配", "按当前交互版本重建草图引用，并删除不存在的截图锚点。")})
    return {
        "passed": not differences,
        "fingerprint": contract["fingerprint"],
        "revision": contract["revision"],
        "expectedChapterOrder": expected_titles,
        "renderedChapterOrder": rendered_titles,
        "missingCopy": missing_copy,
        "tableCount": len(contract["tables"]),
        "formulaCount": sum(len(item["formulae"]) for item in contract["chapters"]),
        "interactionBinding": contract["interaction"],
        "carrierFingerprints": contract["carrierFingerprints"],
        "planningGameplaySync": planning_sync,
        "differences": differences,
    }
