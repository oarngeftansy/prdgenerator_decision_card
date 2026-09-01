from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OwnerDecision:
    source_chapter_id: str
    source_object: str
    owner_object: str
    semantic_domain: str
    definition_mode: str
    reason: str


class OwnerResolutionPolicy:
    """Resolve semantic ownership after classification and before naming output."""

    def _text(self, chapter: dict[str, Any]) -> str:
        return "\n".join(
            str(item.get("text") or "")
            for item in chapter.get("sourceItems") or []
            if isinstance(item, dict)
        )

    def _semantic_domain(self, object_title: str, chapter: dict[str, Any]) -> str:
        text = self._text(chapter)
        chapter_type = chapter.get("chapterType")
        if chapter_type == "slot" and re.search(r"武器栏|武器槽|自选栏|默认武器栏", text):
            return "weapon_slot"
        if chapter_type == "level_flow" and re.search(r"胜负|触发胜利|触发失败|移交结算", text):
            return "battle_outcome"
        if chapter_type == "presentation" and re.search(r"显示.{0,12}(?:倒计时|当前等级)|(?:倒计时|当前等级).{0,12}显示", text):
            return "level_hud"
        if chapter_type == "settlement":
            return "settlement"
        return f"{object_title}:{chapter_type}:{chapter.get('title')}"

    def _definition_score(self, object_title: str, chapter: dict[str, Any]) -> tuple[int, int, int]:
        text = self._text(chapter)
        definition_markers = len(re.findall(r"数量|初始|为空|填充|写入|填满|每栏|承载", text))
        preferred_owner = 1 if object_title == "载具" else 0
        return preferred_owner, definition_markers, len(chapter.get("sourceItems") or [])

    def _infer_owner(self, legacy_object: str, chapter: dict[str, Any]) -> tuple[str, str]:
        text = self._text(chapter)
        domain = chapter.get("semanticDomain")
        chapter_type = chapter.get("chapterType")
        if domain == "level_hud":
            return "关卡", "HUD 倒计时/等级显示属于关卡表现"
        if domain == "battle_outcome":
            owner = legacy_object if legacy_object in {"关卡", "胜负"} else "关卡"
            return owner, "胜负判定按停止/判定/结算主行为归属"
        if chapter_type == "level_flow":
            if re.search(r"关卡|波次|首领阶段", text):
                return "关卡", "显式关卡/波次主语命中"
            if re.search(r"回合|行动方|行动点", text):
                return "回合", "显式回合流程主语命中"
        if chapter_type == "damage_death":
            for subject in ("载具", "怪物", "首领", "角色", "玩家"):
                if subject in text:
                    return subject, f"死亡定义的显式承载对象为{subject}"
        if legacy_object and legacy_object in text:
            return legacy_object, "正文主语支持旧 scope"
        explicit = [subject for subject in ("载具", "武器", "怪物", "关卡", "结算", "手牌", "回合", "胜负") if subject in text]
        if len(explicit) == 1:
            return explicit[0], "正文存在唯一显式业务对象"
        return legacy_object, "owner 证据不足，保留旧 scope 作为可审计 fallback"

    def resolve(self, tree: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        resolved = deepcopy(tree)
        decisions: list[OwnerDecision] = []

        for system in resolved:
            objects = system.get("objects") or []
            for obj in objects:
                for chapter in obj.get("chapters") or []:
                    chapter["semanticDomain"] = self._semantic_domain(obj["title"], chapter)
                    chapter["definitionMode"] = "primary"
                    chapter.setdefault("references", [])

            # Resolve owner from semantic role and explicit subject. Legacy scope is
            # only retained when corroborated or recorded as an evidence fallback.
            for obj in list(objects):
                for chapter in list(obj.get("chapters") or []):
                    owner, reason = self._infer_owner(obj["title"], chapter)
                    chapter["ownerResolutionReason"] = reason
                    if owner == obj["title"]:
                        continue
                    target = next((candidate for candidate in objects if candidate.get("title") == owner), None)
                    if target is None:
                        target = {"title": owner, "sourceChapterIds": [], "chapters": []}
                        objects.append(target)
                    obj["chapters"].remove(chapter)
                    target["chapters"].append(chapter)
                    chapter["semanticDomain"] = self._semantic_domain(owner, chapter)
                    for source_id in chapter.get("sourceChapterIds") or []:
                        decisions.append(OwnerDecision(
                            source_id, obj["title"], owner, chapter["semanticDomain"], "primary", reason,
                        ))

            # A HUD observation stored in the legacy monster scope belongs to the
            # level presentation domain, not to the monster entity lifecycle.
            level = next((obj for obj in objects if obj.get("title") == "关卡"), None)
            for obj in list(objects):
                for chapter in list(obj.get("chapters") or []):
                    if chapter.get("semanticDomain") != "level_hud" or obj.get("title") == "关卡":
                        continue
                    if level is None:
                        level = {"title": "关卡", "sourceChapterIds": [], "chapters": []}
                        objects.append(level)
                    obj["chapters"].remove(chapter)
                    level["chapters"].append(chapter)
                    for source_id in chapter.get("sourceChapterIds") or []:
                        decisions.append(OwnerDecision(
                            source_id, obj["title"], "关卡", "level_hud", "primary",
                            "HUD 倒计时/等级显示属于关卡表现；旧 scope 不作为最终 owner",
                        ))

            # Resolve one primary definition for each cross-scope semantic domain.
            slot_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for obj in objects:
                for chapter in obj.get("chapters") or []:
                    if chapter.get("semanticDomain") == "weapon_slot":
                        slot_candidates.append((obj, chapter))
            if slot_candidates:
                primary_obj, primary = max(
                    slot_candidates,
                    key=lambda pair: self._definition_score(pair[0]["title"], pair[1]),
                )
                for obj, chapter in slot_candidates:
                    if chapter is primary:
                        continue
                    obj["chapters"].remove(chapter)
                    for source_id in chapter.get("sourceChapterIds") or []:
                        reference = {"sourceChapterId": source_id, "sourceObject": obj["title"]}
                        if reference not in primary["references"]:
                            primary["references"].append(reference)
                        decisions.append(OwnerDecision(
                            source_id, obj["title"], primary_obj["title"], "weapon_slot", "reference",
                            "同一武器栏 semantic domain 已由信息更完整的章节定义",
                        ))

            # Parent objects carry an equivalent schema directly; a duplicate child
            # is removed even when other child categories remain.
            for obj in objects:
                for chapter in list(obj.get("chapters") or []):
                    same_semantic_title = chapter.get("title") == obj.get("title")
                    if not same_semantic_title:
                        continue
                    for key in (
                        "chapterType", "mechanicVariant", "matchedSchema", "classificationEvidence",
                        "namingReason", "semanticDomain", "definitionMode", "references", "sourceItems",
                        "ownerResolutionReason",
                    ):
                        obj[key] = deepcopy(chapter.get(key))
                    obj["chapters"].remove(chapter)

        return resolved, [decision.__dict__ for decision in decisions]


owner_resolution_policy = OwnerResolutionPolicy()
