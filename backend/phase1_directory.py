from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from .chapter_classifier import ChapterClassification, classify_text
from .chapter_schema_library import SCHEMA_VERSION, chapter_schema_library
from .chapter_naming_policy import ChapterNamingInput, chapter_naming_policy
from .owner_resolution_policy import owner_resolution_policy


CHAPTER_TYPE_ORDER = (
    "attribute", "movement", "spawn", "attack", "damage_death", "slot",
    "unlock_progression", "content_catalog", "randomization", "combat_calculation",
    "state_machine", "interaction", "presentation", "level_flow", "settlement", "unknown",
)
_OBJECT_TERMS = (
    "载具", "武器", "怪物", "首领", "关卡", "结算", "词条", "技能", "手牌", "牌库",
    "卡牌", "建筑", "角色", "棋子", "宠物", "装备", "三选一", "武器抽取", "终极词条",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _content_items(chapter: dict[str, Any]) -> list[dict[str, str]]:
    items = []
    for index, claim in enumerate(chapter.get("claims") or [], 1):
        if isinstance(claim, dict) and _text(claim.get("text")):
            items.append({"source": f"claim:{claim.get('id') or index}", "text": _text(claim.get("text"))})
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    for field in ("normalFlow", "keyRules", "specialCases"):
        for index, item in enumerate(planner.get(field) or [], 1):
            if isinstance(item, str) and item.strip():
                items.append({"source": f"planner:{field}:{index}", "text": item.strip()})
    return items


def _object_name(chapter: dict[str, Any], all_text: str) -> str:
    scope = _text(chapter.get("scope") or chapter.get("title"))
    if scope == "局内强化" and re.search(r"三选一|三张候选", all_text):
        return "三选一"
    if scope == "终极强化" and "终极词条" in all_text:
        return "终极词条"
    if scope and len(scope) <= 8 and not re.search(r"[、，]|与|及", scope):
        return scope
    for term in sorted(_OBJECT_TERMS, key=len, reverse=True):
        if term in scope or term in all_text:
            return term
    return scope or "待确认对象"


def _concept_title(text: str, classification: ChapterClassification) -> str | None:
    if classification.chapter_type == "level_flow" and re.search(r"判定胜负|触发胜利|触发失败|胜负触发|移交结算|生命值归零.{0,20}(?:停止对局|进入.{0,6}结算)", text):
        return "胜负判定"
    if classification.chapter_type == "content_catalog" and "词条" in text:
        return "词条"
    if classification.chapter_type == "randomization" and "刷新" in text and not re.search(r"三选一|候选池|随机池|抽取", text):
        return "刷新"
    if classification.chapter_type == "randomization" and classification.mechanic_variant == "three_choice" and "候选" in text:
        return "候选"
    if re.search(r"跳字|伤害数字|飘出.{0,12}数字", text):
        return "跳字"
    if classification.chapter_type in {"settlement", "combat_calculation", "presentation"} and re.search(r"伤害统计|伤害归集|总伤害|秒伤", text):
        return "伤害统计"
    return None


def _user_visible_variant(object_name: str, classification: ChapterClassification, text: str) -> str | None:
    if classification.mechanic_variant == "three_choice" and object_name == "三选一" and re.search(r"三选一|三张候选", text):
        return "三选一"
    return None


def _classification_for_item(item: dict[str, str]) -> ChapterClassification:
    result = classify_text("", [item["text"]])
    if re.search(r"词条组|前置词条|最大等级|随机池|词条库|终极词条", item["text"]):
        schema = chapter_schema_library.resolve("content_catalog", None, SCHEMA_VERSION)
        return ChapterClassification("content_catalog", None, schema.schema_key, tuple([*result.classification_evidence, "稳定业务对象命中“词条”"]), max(result.confidence, 0.8))
    if re.search(r"跳字|伤害数字|飘出.{0,12}数字", item["text"]):
        schema = chapter_schema_library.resolve("presentation", None, SCHEMA_VERSION)
        return ChapterClassification("presentation", None, schema.schema_key, tuple([*result.classification_evidence, "稳定表现类别命中“跳字/伤害数字”"]), max(result.confidence, 0.8))
    return result


def _contextual_classification(object_name: str, text: str, result: ChapterClassification) -> ChapterClassification:
    if object_name == "三选一" and result.chapter_type in {"attack", "unlock_progression", "interaction", "presentation", "randomization"}:
        schema = chapter_schema_library.resolve("randomization", "three_choice", SCHEMA_VERSION)
        return ChapterClassification("randomization", "three_choice", schema.schema_key, tuple([*result.classification_evidence, "对象上下文：三选一规则"]), max(result.confidence, 0.85))
    if object_name == "武器抽取":
        schema = chapter_schema_library.resolve("randomization", "roulette", SCHEMA_VERSION)
        return ChapterClassification("randomization", "roulette", schema.schema_key, tuple([*result.classification_evidence, "对象上下文：滚动抽取规则"]), max(result.confidence, 0.85))
    if object_name == "终极词条":
        schema = chapter_schema_library.resolve("content_catalog", None, SCHEMA_VERSION)
        return ChapterClassification("content_catalog", None, schema.schema_key, tuple([*result.classification_evidence, "对象上下文：终极词条"]), max(result.confidence, 0.85))
    if re.search(r"生命值归零|失败分支", text) and result.chapter_type == "settlement":
        schema = chapter_schema_library.resolve("damage_death", None, SCHEMA_VERSION)
        return ChapterClassification("damage_death", None, schema.schema_key, tuple([*result.classification_evidence, "失败结果由受击及死亡章节承载"]), max(result.confidence, 0.85))
    return result


def _tree_text(tree: list[dict[str, Any]]) -> str:
    lines = []
    for system in tree:
        lines.append(system["title"])
        for object_index, obj in enumerate(system["objects"]):
            last_object = object_index == len(system["objects"]) - 1
            object_prefix = "└─" if last_object else "├─"
            chapters = obj["chapters"]
            if len(chapters) == 1 and chapters[0]["title"] == obj["title"]:
                lines.append(f"{object_prefix} {obj['title']}")
                continue
            lines.append(f"{object_prefix} {obj['title']}")
            branch = "   " if last_object else "│  "
            for chapter_index, chapter in enumerate(chapters):
                leaf = "└─" if chapter_index == len(chapters) - 1 else "├─"
                lines.append(f"{branch}{leaf} {chapter['title']}")
    return "\n".join(lines)


def _quality_report(tree: list[dict[str, Any]], unknown: int, custom: int) -> dict[str, Any]:
    titles = []
    child_rows = []
    for system in tree:
        titles.append(system["title"])
        for obj in system["objects"]:
            titles.append(obj["title"])
            for child in obj["chapters"]:
                titles.append(child["title"])
                child_rows.append(child)
    whitelist = {"解锁与养成", "受击及死亡"}
    issues = [issue for child in child_rows for issue in child.get("titleQualityIssues") or []]
    return {
        "totalTitleCount": len(titles),
        "averageTitleLength": round(sum(map(len, titles)) / len(titles), 2) if titles else 0,
        "twelveOrMoreTitleCount": sum(len(title) >= 12 for title in titles),
        "dunhaoTitleCount": sum("、" in title for title in titles),
        "andOrJiTitleCount": sum("与" in title or "及" in title for title in titles),
        "whitelistedCombinationCount": sum(title in whitelist for title in titles),
        "multipleActionsCount": issues.count("multiple_actions"),
        "sentenceLikeCount": issues.count("sentence_like"),
        "containsResultCount": issues.count("contains_result"),
        "chapterTypeMismatchCount": issues.count("chapter_type_mismatch"),
        "unknownCount": unknown,
        "customCount": custom,
    }


def build_phase1_directory(model: dict[str, Any]) -> dict[str, Any]:
    systems: OrderedDict[str, OrderedDict[str, dict[str, Any]]] = OrderedDict()
    comparisons = []
    unknown_count = 0
    for chapter_index, chapter in enumerate(model.get("chapters") or [], 1):
        if not isinstance(chapter, dict):
            continue
        old_title = _text(chapter.get("scope") or chapter.get("title")) or f"旧章节{chapter_index}"
        directory_entry = next((entry for entry in (model.get("directory") or {}).get("entries") or [] if isinstance(entry, dict) and entry.get("chapterId") == chapter.get("id")), {})
        system_name = _text(chapter.get("systemName") or directory_entry.get("sectionTitle")) or "其他玩法"
        items = _content_items(chapter)
        all_text = "\n".join(item["text"] for item in items)
        object_name = _object_name(chapter, all_text)
        grouped: OrderedDict[tuple[str, str | None], dict[str, Any]] = OrderedDict()
        unresolved = []
        for item in items:
            classification = _classification_for_item(item)
            classification = _contextual_classification(object_name, item["text"], classification)
            if classification.chapter_type == "unknown":
                unresolved.append(item)
                continue
            concept = _concept_title(item["text"], classification)
            if object_name == "三选一" and classification.chapter_type == "randomization":
                concept = "刷新" if "刷新" in item["text"] and not re.search(r"三选一|候选池|随机池|抽取", item["text"]) else "候选"
            if object_name == "终极词条":
                concept = object_name
            key = (classification.chapter_type, concept)
            bucket = grouped.setdefault(key, {"classification": classification, "items": [], "evidence": []})
            if bucket["classification"].mechanic_variant is None and classification.mechanic_variant is not None:
                bucket["classification"] = classification
            bucket["items"].append(item)
            for marker in classification.classification_evidence:
                if marker not in bucket["evidence"]:
                    bucket["evidence"].append(marker)
        if not grouped:
            classification = classify_text(old_title, [all_text] if all_text else [])
            key = (classification.chapter_type, None)
            grouped[key] = {"classification": classification, "items": unresolved, "evidence": list(classification.classification_evidence)}
            unresolved = []
        if unresolved:
            next(iter(grouped.values()))["items"].extend(unresolved)
        weak_keys = [
            key for key, bucket in grouped.items()
            if key[0] in {"state_machine", "interaction", "presentation"}
            and len(bucket["items"]) == 1
            and _concept_title(bucket["items"][0]["text"], bucket["classification"]) is None
        ]
        for key in weak_keys:
            weak = grouped.pop(key)
            if grouped:
                next(iter(grouped.values()))["items"].extend(weak["items"])
            else:
                grouped[key] = weak
        object_node = systems.setdefault(system_name, OrderedDict()).setdefault(object_name, {"title": object_name, "sourceChapterIds": [], "chapters": []})
        source_id = _text(chapter.get("id")) or f"OLD-{chapter_index:03d}"
        object_node["sourceChapterIds"].append(source_id)
        group_rows = []
        for (chapter_type, concept), bucket in grouped.items():
            classification = bucket["classification"]
            mechanic_variant = classification.mechanic_variant
            visible = _user_visible_variant(object_name, classification, "\n".join(item["text"] for item in bucket["items"]))
            naming = chapter_naming_policy.name(ChapterNamingInput(
                level=3, system_name=system_name, object_name=object_name, chapter_type=chapter_type,
                mechanic_variant=mechanic_variant, user_visible_variant_name=visible, legacy_title=old_title,
            ))
            title = concept or naming.title
            quality = chapter_naming_policy.inspect(title, chapter_type) if concept is None else ()
            row = {
                "title": title,
                "chapterType": chapter_type,
                "mechanicVariant": mechanic_variant,
                "matchedSchema": classification.matched_schema,
                "classificationEvidence": bucket["evidence"],
                "namingReason": f"{naming.naming_reason}" + (f"；素材稳定概念为“{concept}”" if concept else ""),
                "titleSplit": len(grouped) > 1 or old_title != title,
                "titleQualityIssues": list(quality),
                "sourceChapterIds": [source_id],
                "sourceItems": bucket["items"],
            }
            if chapter_type == "unknown":
                unknown_count += 1
            group_rows.append(row)
        order = {kind: index for index, kind in enumerate(CHAPTER_TYPE_ORDER)}
        group_rows.sort(key=lambda row: (order.get(row["chapterType"], 999), row["title"]))
        object_node["chapters"].extend(group_rows)
        comparisons.append({
            "sourceChapterId": source_id,
            "oldTitle": old_title,
            "objectTitle": object_name,
            "splitInto": [row["title"] for row in group_rows],
            "titleSplit": len(group_rows) > 1 or any(row["title"] != old_title for row in group_rows),
            "newNodes": group_rows,
        })
    tree = [{"title": system, "objects": list(objects.values())} for system, objects in systems.items()]
    tree, ownership_decisions = owner_resolution_policy.resolve(tree)
    return {
        "schemaVersion": "phase1-directory-v1",
        "tree": tree,
        "comparisons": comparisons,
        "humanReadableTree": _tree_text(tree),
        "qualityReport": _quality_report(tree, unknown_count, 0),
        "ownershipDecisions": ownership_decisions,
    }
