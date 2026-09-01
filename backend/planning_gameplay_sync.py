from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
import re
from typing import Any


_CARRIERS = {"normalFlow", "keyRules", "specialCases", "attributeSections"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _derived_board_insights(job: dict[str, Any], chapters: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn screenshot-backed option-card facts into weapon prose candidates.

    Generic detections such as “画面包含等级信息” and layout descriptions stay on
    the board.  Only named option facts with an explicit effect are eligible.
    """
    weapon = next((chapter for chapter in chapters.values()
                   if _text((chapter.get("plannerSections") or {}).get("attributeHeading")) == "武器"), None)
    if weapon is None:
        return []
    from .planning_board_model import build_planning_board_model

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in build_planning_board_model(job).get("pages") or []:
        frame_ids = [_text(item.get("frameId")) for item in page.get("sourceRefs") or []
                     if isinstance(item, dict) and _text(item.get("frameId"))]
        for group in page.get("groups") or []:
            if _text(group.get("title")) != "武器与强化属性":
                continue
            for item in group.get("items") or []:
                raw = _text(item.get("text") if isinstance(item, dict) else item)
                if " - " not in raw:
                    continue
                name, effect = (_text(part) for part in raw.split(" - ", 1))
                if not name or not effect or raw in seen:
                    continue
                seen.add(raw)
                prose = (f"{name}：本次截图显示，{effect.rstrip('。')}。"
                         if re.search(r"\d", effect) else f"{name}：{effect.rstrip('。')}。")
                digest = sha1((raw + "|" + "|".join(frame_ids)).encode("utf-8")).hexdigest()[:12]
                result.append({
                    "id": f"PGB-{digest}", "text": prose, "targetChapterId": _text(weapon.get("id")),
                    "carrier": "attributeSections", "attributeHeading": "局内强化与效果",
                    "sourceFrameIds": frame_ids, "origin": "planning_board",
                })
    return result


def sync_planning_gameplay_insights(job: dict[str, Any], gameplay_model: dict[str, Any]) -> dict[str, Any]:
    """Copy explicitly classified, gameplay-relevant board interpretations into gameplay copy."""
    result = deepcopy(gameplay_model)
    chapters = {str(item.get("id")): item for item in result.get("chapters") or [] if isinstance(item, dict)}
    chapters_by_scope = {str(item.get("scope")): item for item in chapters.values() if _text(item.get("scope"))}
    trace: list[dict[str, Any]] = []
    stages = ((job.get("reviewModel") or {}).get("stages") or [])
    stage_records = [(stage, stage.get("gameplayInsights") or []) for stage in stages if isinstance(stage, dict)]
    stage_records.append(({"id": "PLANNING-BOARD", "name": "策划草图业务解读"},
                          _derived_board_insights(job, chapters)))
    for stage, insights in stage_records:
        for insight in insights:
            if not isinstance(insight, dict) or not _text(insight.get("text")):
                continue
            record = {
                "insightId": _text(insight.get("id")), "stageId": _text(stage.get("id")),
                "stageName": _text(stage.get("name") or stage.get("title")),
                "targetChapterId": _text(insight.get("targetChapterId")),
                "carrier": _text(insight.get("carrier") or "keyRules"), "text": _text(insight.get("text")),
                "sourceFrameIds": [str(item) for item in insight.get("sourceFrameIds") or [] if _text(item)],
            }
            if _text(insight.get("carrier")) == "attributeSections":
                record["attributeHeading"] = _text(insight.get("attributeHeading"))
            if insight.get("gameplayRelevant") is False:
                trace.append({**record, "status": "board_only", "reason": _text(insight.get("reason"))})
                continue
            chapter = chapters.get(record["targetChapterId"]) or chapters_by_scope.get(_text(insight.get("targetScope")))
            if chapter is None:
                trace.append({**record, "status": "missing_target"})
                continue
            record["targetChapterId"] = _text(chapter.get("id"))
            carrier = record["carrier"] if record["carrier"] in _CARRIERS else "keyRules"
            record["carrier"] = carrier
            sections = chapter.setdefault("plannerSections", {})
            if carrier == "attributeSections":
                heading = record["attributeHeading"]
                if not heading:
                    trace.append({**record, "status": "missing_attribute_heading"})
                    continue
                groups = sections.setdefault("attributeSections", [])
                group = next((item for item in groups if _text(item.get("heading")) == heading), None)
                if group is None:
                    group = {"heading": heading, "items": []}
                    groups.append(group)
                values = group.setdefault("items", [])
            else:
                values = sections.setdefault(carrier, [])
            if record["text"] not in values:
                values.append(record["text"])
            trace.append({**record, "status": "delivered"})
    result["planningGameplayTrace"] = trace
    return result


def planning_gameplay_sync_report(job: dict[str, Any], gameplay_model: dict[str, Any]) -> dict[str, Any]:
    if not (gameplay_model.get("planningGameplayTrace") or []):
        gameplay_model = sync_planning_gameplay_insights(job, gameplay_model)
    chapters = {str(item.get("id")): item for item in gameplay_model.get("chapters") or [] if isinstance(item, dict)}
    findings = []
    trace = gameplay_model.get("planningGameplayTrace") or []
    for item in trace:
        if not isinstance(item, dict) or item.get("status") == "board_only":
            continue
        chapter = chapters.get(str(item.get("targetChapterId") or ""))
        carrier = str(item.get("carrier") or "keyRules")
        sections = ((chapter or {}).get("plannerSections") or {})
        if carrier == "attributeSections":
            heading = _text(item.get("attributeHeading"))
            group = next((entry for entry in sections.get("attributeSections") or []
                          if _text(entry.get("heading")) == heading), None)
            values = (group or {}).get("items") or []
        else:
            values = sections.get(carrier) or []
        if item.get("status") != "delivered" or item.get("text") not in values:
            findings.append({
                "insightId": item.get("insightId"), "stageId": item.get("stageId"),
                "targetChapterId": item.get("targetChapterId"), "text": item.get("text"),
                "issue": "策划草图中的玩法解读尚未进入目标玩法载体",
                "improvementPath": "确认目标玩法章节与承载位置，重新同步正文后再生成 P7 和飞书文档。",
            })
    delivered = sum(1 for item in trace if isinstance(item, dict) and item.get("status") == "delivered")
    board_only = sum(1 for item in trace if isinstance(item, dict) and item.get("status") == "board_only")
    return {"passed": not findings, "insightCount": len(trace), "deliveredCount": delivered,
            "boardOnlyCount": board_only, "missingCount": len(findings), "findings": findings}
