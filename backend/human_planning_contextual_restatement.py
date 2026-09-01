from __future__ import annotations

import hashlib
import re
from typing import Any


AUDIT_HEADINGS = {"Full definitions", "Short cross-system references", "Suppressed duplicated definitions"}
OWNER_REFERENCE_TERMS = ("sourceChapter", "targetChapter", "primaryOwner", "referenceOwner", "owner", "reference",
                         "负责定义", "主定义", "短引用", "完整定义")
RELATION_TRANSLATION_PATTERNS = (
    r"详见", r"参见", r"对应.{0,8}生效", r"进入.{0,8}判定", r"产生关联", r"产生影响", r"对.{0,8}产生影响",
)


def _sid(chapter: str, semantic: str, rule_ids: list[str]) -> str:
    digest = hashlib.sha1(f"{chapter}:{semantic}:{','.join(rule_ids)}".encode("utf-8")).hexdigest()[:12].upper()
    return f"HSTMT-{digest}"


def _statement(chapter: str, semantic: str, text: str, mode: str, rule_ids: list[str],
               reference_ids: list[str] | None = None) -> dict[str, Any]:
    return {"statementId": _sid(chapter, semantic, rule_ids), "semantic": semantic, "text": text,
            "mode": mode, "supportingRuleIds": rule_ids, "sourceReferenceIds": reference_ids or []}


def _definitions(chapter: dict[str, Any]) -> list[dict[str, Any]]:
    return chapter.get("fullDefinitions", [])


def _find(definitions: list[dict[str, Any]], token: str) -> list[dict[str, Any]]:
    return [item for item in definitions if token in item.get("text", "")]


def _rules(items: list[dict[str, Any]]) -> list[str]:
    return [item["ruleId"] for item in items]


def build_human_planning_restatements(reference_plans: list[dict[str, Any]],
                                       chapter_previews: list[dict[str, Any]],
                                       approved_rules: list[dict[str, Any]],
                                       expansion_plans: list[dict[str, Any]],
                                       parameter_placements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build human-readable chapter context while leaving machine reference plans untouched."""
    active_by_source: dict[str, list[dict[str, Any]]] = {}
    for plan in reference_plans:
        if plan.get("referenceDepth") != "no_reference_needed":
            active_by_source.setdefault(plan["sourceChapter"], []).append(plan)
    chapters = []
    for preview in chapter_previews:
        chapter_id = preview["chapterId"]
        title = preview["chapterTitle"]
        defs = _definitions(preview)
        refs = {plan["relationKey"]: plan for plan in active_by_source.get(chapter_id, [])}
        statements: list[dict[str, Any]] = []

        if title == "关卡流程":
            if "level_to_three_choice" in refs:
                plan = refs["level_to_three_choice"]
                statements.append(_statement(chapter_id, "level_up_to_three_choice",
                    "战斗等级达到升级条件时触发三选一。", "contextual_restatement",
                    plan.get("supportingRuleIds", []), [plan["referenceId"]]))
            if "level_to_outcome" in refs:
                plan = refs["level_to_outcome"]
                statements.append(_statement(chapter_id, "vehicle_zero_hp_failure",
                    "载具生命值归零时关卡失败。", "contextual_restatement",
                    plan.get("supportingRuleIds", []), [plan["referenceId"]]))

        elif title == "三选一":
            trigger = _find(defs, "三张候选")
            pause = _find(defs, "暂停")
            if trigger or pause:
                statements.append(_statement(chapter_id, "three_choice_trigger",
                    "战斗等级提升时，暂停战斗并生成3张候选卡。", "full_definition",
                    _rules([*trigger, *pause])))
            choice = _find(defs, "选择一项")
            effect_plan = refs.get("three_choice_to_affix")
            if choice and effect_plan:
                statements.append(_statement(chapter_id, "three_choice_result",
                    "玩家选择1项后获得该项强化。", "contextual_restatement",
                    [*_rules(choice), *effect_plan.get("supportingRuleIds", [])], [effect_plan["referenceId"]]))
            refresh = [item for item in defs if "刷新" in item.get("text", "")]
            if refresh:
                has_cost = any("消耗" in item.get("text", "") or "替代条件" in item.get("text", "") for item in refresh)
                text = "玩家可刷新当前3项候选。"
                if has_cost:
                    text = "玩家可刷新当前3项候选；刷新存在消耗或替代条件。"
                statements.append(_statement(chapter_id, "refresh_candidates", text, "full_definition", _rules(refresh)))

        elif title == "武器攻击":
            auto = _find(defs, "无需玩家手动瞄准")
            target = _find(defs, "射程内敌人")
            if auto or target:
                statements.append(_statement(chapter_id, "automatic_targeting",
                    "武器无需玩家手动瞄准，自动选择射程内的敌人发起攻击。", "full_definition",
                    _rules([*auto, *target])))
            method = [item for item in defs if "投射物" in item.get("text", "") or "持续伤害区域" in item.get("text", "")]
            if method:
                statements.append(_statement(chapter_id, "attack_method",
                    "攻击时，武器向目标发射投射物或生成持续伤害区域。", "full_definition", _rules(method)))
            modifier_plan = refs.get("weapon_attack_to_affix")
            if modifier_plan:
                statements.append(_statement(chapter_id, "affix_changes_attack",
                    "词条生效后，可改变武器的攻击方式、攻击范围或伤害。", "contextual_restatement",
                    modifier_plan.get("supportingRuleIds", []), [modifier_plan["referenceId"]]))

        elif title == "词条":
            generic = _find(defs, "改变攻击方式")
            if generic:
                statements.append(_statement(chapter_id, "affix_attack_change",
                    "玩家选择词条后，已选武器的攻击方式发生改变。", "full_definition", _rules(generic)))
            for token, semantic, text in (
                ("范围扩大30%", "fire_range", "火焰喷射：攻击范围提高30%。"),
                ("伤害增加100%", "thunder_damage", "雷暴枪：伤害提高100%。"),
                ("四向喷射", "ultimate_direction", "终极词条：喷射方向由单方向改为四向。"),
            ):
                matched = _find(defs, token)
                if matched:
                    statements.append(_statement(chapter_id, semantic, text, "full_definition", _rules(matched)))

        elif title == "胜负判定":
            failure = [item for item in defs if "生命值归零" in item.get("text", "") and "失败" in item.get("text", "")]
            if failure:
                statements.append(_statement(chapter_id, "vehicle_zero_hp_failure",
                    "载具生命值归零时关卡失败。", "full_definition", _rules(failure)))

        else:
            for definition in defs:
                text = definition.get("text", "").rstrip("。") + "。"
                statements.append(_statement(chapter_id, "direct_rule", text, "full_definition", [definition["ruleId"]]))
        chapters.append({"chapterId": chapter_id, "chapterTitle": title, "statements": statements})
    return chapters


def evaluate_human_planning_readability(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    audit_leaks = [chapter.get("chapterId") for chapter in chapters if chapter.get("chapterTitle") in AUDIT_HEADINGS]
    owner_language = []
    relation_tone = []
    id_leaks = []
    unreadable = []
    implausible = []
    full_blocks: dict[tuple[str, ...], int] = {}
    contextual_count = 0
    id_pattern = re.compile(r"\b(?:V2CH|RULE|ENT|XREF|HSTMT)-[A-Z0-9-]+\b")
    for chapter in chapters:
        statements = chapter.get("statements", [])
        if not statements:
            unreadable.append(chapter.get("chapterId"))
        for statement in statements:
            text = statement.get("text", "")
            if any(term in text for term in OWNER_REFERENCE_TERMS):
                owner_language.append(statement.get("statementId"))
            if any(re.search(pattern, text) for pattern in RELATION_TRANSLATION_PATTERNS):
                relation_tone.append(statement.get("statementId"))
            if id_pattern.search(text):
                id_leaks.append(statement.get("statementId"))
            if not text.endswith(("。", "？", "！")) or len(text) < 8:
                implausible.append(statement.get("statementId"))
            if statement.get("mode") == "contextual_restatement":
                contextual_count += 1
            elif statement.get("mode") == "full_definition":
                key = tuple(sorted(statement.get("supportingRuleIds", [])))
                if key:
                    full_blocks[key] = full_blocks.get(key, 0) + 1
    duplicate_full = sum(max(0, count - 1) for count in full_blocks.values())
    findings = audit_leaks + owner_language + relation_tone + id_leaks + unreadable + implausible
    if duplicate_full:
        findings.append(f"duplicated_full_rule_block:{duplicate_full}")
    return {"qualityGate": "pass" if not findings else "fail",
            "chapterCount": len(chapters), "statementCount": sum(len(c.get("statements", [])) for c in chapters),
            "contextualRestatementCount": contextual_count,
            "duplicatedFullRuleBlockCount": duplicate_full,
            "auditStructureLeakCount": len(audit_leaks),
            "ownerReferenceLanguageCount": len(owner_language),
            "relationTranslationToneCount": len(relation_tone),
            "internalIdLeakCount": len(id_leaks),
            "standaloneReadabilityFailureCount": len(unreadable),
            "plannerPlausibilityFailureCount": len(implausible), "findings": findings}
