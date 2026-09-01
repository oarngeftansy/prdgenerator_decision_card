from __future__ import annotations

from copy import deepcopy
from typing import Any

from .chapter_classifier import classify_text
from .phase1_directory import build_phase1_directory

TITLE_BY_MECHANISM = {
    "core_loop": "核心循环",
    "spatial_drag": "空间与摆放规则",
    "entity_behavior": "实体行为",
    "formula": "战斗与数值计算",
    "progression": "成长与解锁",
    "random_pool": "随机选择与刷新",
    "economy_reward": "资源与奖励",
    "level_wave": "关卡与阶段推进",
    "buff_chain": "Buff与效果",
    "settlement": "结算与退出",
    "external_entry": "进入条件与扫荡",
    "statistics_feedback": "统计与反馈",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _claim_texts(draft: dict[str, Any]) -> list[str]:
    return [
        _text(item.get("text")) for item in draft.get("claims") or []
        if isinstance(item, dict) and _text(item.get("text"))
    ]


def _title(draft: dict[str, Any]) -> str:
    proposed = _text(draft.get("title") or draft.get("scope"))
    mechanism = _text(draft.get("mechanismType") or (draft.get("mechanism") or {}).get("type"))
    generic = proposed.lower().startswith(("scene", "frame", "场景", "页面", "截图"))
    return TITLE_BY_MECHANISM.get(mechanism, proposed or "待命名玩法") if generic or not proposed else proposed


def _type_assessment(drafts: list[dict[str, Any]]) -> dict[str, Any]:
    mechanisms = {
        _text(item.get("mechanismType") or (item.get("mechanism") or {}).get("type"))
        for item in drafts if isinstance(item, dict)
    }
    if "level_wave" in mechanisms and ("progression" in mechanisms or "random_pool" in mechanisms):
        primary = "关卡推进与成长"
    elif "spatial_drag" in mechanisms:
        primary = "空间摆放与组合"
    elif "entity_behavior" in mechanisms or "formula" in mechanisms:
        primary = "战斗玩法"
    elif "economy_reward" in mechanisms:
        primary = "经营与资源循环"
    else:
        primary = "待策划确认"
    supporting = [TITLE_BY_MECHANISM[item] for item in TITLE_BY_MECHANISM if item in mechanisms][:3]
    uncertainties = [] if primary != "待策划确认" else ["主玩法类型还不能仅凭当前素材确定"]
    return {"primaryFamily": primary, "supportingMechanics": supporting, "uncertainties": uncertainties}


def synthesize_directory(drafts: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [deepcopy(item) for item in drafts if isinstance(item, dict)]
    groups: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, draft in enumerate(valid, 1):
        mechanism = _text(draft.get("mechanismType") or (draft.get("mechanism") or {}).get("type"))
        title = _title(draft)
        key = (mechanism, title.casefold())
        if key not in by_key:
            entry = {
                "id": f"GDE-{len(groups) + 1:03d}",
                "chapterId": f"GCH-{index:03d}",
                "title": title,
                "summary": "；".join(_claim_texts(draft)[:2]) or "请确认本章准备说明的玩法内容",
                "claimIds": [item.get("id") for item in draft.get("claims") or [] if isinstance(item, dict) and item.get("id")],
                "order": len(groups) + 1,
            }
            groups.append(entry)
            by_key[key] = entry
        else:
            entry = by_key[key]
            more = _claim_texts(draft)
            if more:
                entry["summary"] = "；".join(filter(None, [entry["summary"], *more[:2]]))
    assessment = _type_assessment(valid)
    sentences = []
    for draft in valid:
        sentences.extend(_claim_texts(draft))
        if len(sentences) >= 4:
            break
    directory = {
        "revision": 1,
        "status": "draft",
        "understanding": {
            "summary": "。".join(item.rstrip("。") for item in sentences[:4]) + ("。" if sentences else ""),
            **assessment,
        },
        "entries": groups,
        "unassignedClaimIds": [],
        "confirmedAtRevision": None,
    }
    phase1 = build_phase1_directory({"chapters": valid})
    directory.update({
        "contentModelVersion": 2,
        "classifiedTree": phase1["tree"],
        "humanReadableTree": phase1["humanReadableTree"],
        "titleQualityReport": phase1["qualityReport"],
    })
    comparisons = phase1.get("comparisons") or []
    for index, entry in enumerate(directory["entries"]):
        draft = valid[index] if index < len(valid) else {}
        texts = _claim_texts(draft)
        classification = classify_text(_text(draft.get("title") or draft.get("scope")), texts)
        comparison = comparisons[index] if index < len(comparisons) else {}
        new_nodes = comparison.get("newNodes") or []
        old_title = entry["title"]
        object_title = comparison.get("objectTitle") or old_title
        entry.update({
            "legacyTitle": old_title,
            "title": object_title,
            "chapterType": classification.chapter_type,
            "mechanicVariant": classification.mechanic_variant,
            "matchedSchema": classification.matched_schema,
            "classificationEvidence": list(classification.classification_evidence),
            "namingReason": (new_nodes[0].get("namingReason") if new_nodes else "按稳定对象与规则类别命名"),
            "titleSplit": bool(comparison.get("titleSplit")),
        })
    # Drafts do not have stable chapter ids until the review model is built.
    # Keep the proposed structure; the shared copy layer refreshes it afterwards.
    return directory


def legacy_directory(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [{
        "id": f"GDE-{index:03d}", "chapterId": chapter.get("id"),
        "title": _text(chapter.get("scope")) or "待命名玩法",
        "summary": "；".join(_claim_texts(chapter)[:2]) or "已按历史章节保留",
        "claimIds": [item.get("id") for item in chapter.get("claims") or [] if isinstance(item, dict) and item.get("id")],
        "order": index,
    } for index, chapter in enumerate(chapters, 1) if isinstance(chapter, dict)]
    return {
        "revision": 1, "status": "confirmed",
        "understanding": {"summary": "", "primaryFamily": "历史任务", "supportingMechanics": [], "uncertainties": []},
        "entries": entries, "unassignedClaimIds": [], "confirmedAtRevision": 1, "legacyDerived": True,
    }


def ensure_directory(model: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(model.get("directory"), dict):
        model["directory"] = legacy_directory(model.get("chapters") or [])
    elif model["directory"].get("legacyDerived") is True:
        current_ids = [item.get("id") for item in model.get("chapters") or [] if isinstance(item, dict)]
        directory_ids = [item.get("chapterId") for item in model["directory"].get("entries") or [] if isinstance(item, dict)]
        if current_ids != directory_ids:
            model["directory"] = legacy_directory(model.get("chapters") or [])
    directory = model["directory"]
    chapters = {
        item.get("id"): item
        for item in model.get("chapters") or []
        if isinstance(item, dict) and item.get("id")
    }
    assigned_claim_ids: set[str] = set()
    for entry in directory.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        chapter = chapters.get(entry.get("chapterId"))
        if not isinstance(chapter, dict):
            continue
        canonical_claim_ids = [
            item.get("id")
            for item in chapter.get("claims") or []
            if isinstance(item, dict) and item.get("id")
        ]
        if entry.get("claimIds") != canonical_claim_ids:
            entry["claimIds"] = canonical_claim_ids
        assigned_claim_ids.update(canonical_claim_ids)
    all_claim_ids = [
        claim.get("id")
        for chapter in chapters.values()
        for claim in chapter.get("claims") or []
        if isinstance(claim, dict) and claim.get("id")
    ]
    directory["unassignedClaimIds"] = [claim_id for claim_id in all_claim_ids if claim_id not in assigned_claim_ids]
    return directory


def directory_errors(model: dict[str, Any], require_confirmed: bool = False) -> list[str]:
    directory = model.get("directory")
    if not isinstance(directory, dict):
        return ["directory: expected an object"]
    errors: list[str] = []
    if require_confirmed and directory.get("status") != "confirmed":
        errors.append("GAMEPLAY_DIRECTORY_NOT_CONFIRMED")
    entries = directory.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("directory.entries: expected at least one entry")
        return errors
    chapter_ids = {item.get("id") for item in model.get("chapters") or [] if isinstance(item, dict)}
    seen_entries, seen_chapters, seen_claims = set(), set(), set()
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            errors.append(f"directory.entries[{index - 1}]: expected an object")
            continue
        if entry.get("id") in seen_entries or not _text(entry.get("id")).startswith("GDE-"):
            errors.append("directory entry id must be unique")
        seen_entries.add(entry.get("id"))
        if entry.get("chapterId") not in chapter_ids or entry.get("chapterId") in seen_chapters:
            errors.append("directory chapter ownership must be unique and valid")
        seen_chapters.add(entry.get("chapterId"))
        if not _text(entry.get("title")):
            errors.append("directory title is required")
        if entry.get("order") != index:
            errors.append("directory order must be consecutive")
        for claim_id in entry.get("claimIds") or []:
            if claim_id in seen_claims:
                errors.append("directory claim ownership must be unique")
            seen_claims.add(claim_id)
    if directory.get("unassignedClaimIds"):
        errors.append("directory has unassigned content")
    return errors
