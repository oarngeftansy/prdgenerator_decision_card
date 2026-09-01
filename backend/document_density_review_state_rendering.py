from __future__ import annotations

import hashlib
import re
from typing import Any


_PENDING_LABELS = {
    "candidate_eligibility": "可获取词条范围",
    "growth_source": "成长规则",
    "upgrade_basis": "成长规则",
    "damage_model": "伤害计算",
    "refresh_rule": "刷新规则",
    "contact_damage_mode": "接触伤害方式",
    "movement_speed": "移动速度",
    "weapon_slot_capacity": "武器栏容量",
    "attack_range": "攻击范围",
    "attack_interval": "攻击间隔",
    "time_limit": "关卡时限",
}

_DENSE_TEXT = {
    "automatic_targeting": "武器自动攻击射程内敌人，无需玩家手动瞄准。",
    "attack_method": "武器攻击时，向目标发射投射物或生成持续伤害区域。",
    "three_choice_trigger": "战斗等级提升时暂停战斗，并生成3张候选。",
    "three_choice_result": "玩家从3项中选择1项，获得对应强化。",
    "refresh_candidates": "点击刷新后替换当前3项候选。",
    "fire_range": "火焰喷射：攻击范围+30%。",
    "thunder_damage": "雷暴枪：伤害+100%。",
}


def _topic_belongs_to_chapter(chapter_title: str, decision: dict[str, Any]) -> bool:
    topic = decision.get("ruleTopic", "")
    if chapter_title == "武器攻击":
        return topic == "攻击规则"
    return True


def _line_id(chapter_id: str, semantic: str, state: str) -> str:
    digest = hashlib.sha1(f"{chapter_id}:{semantic}:{state}".encode("utf-8")).hexdigest()[:12].upper()
    return f"DLINE-{digest}"


def _pending_line(chapter_id: str, decision: dict[str, Any]) -> dict[str, Any] | None:
    key = decision.get("decisionKey", "")
    label = _PENDING_LABELS.get(key)
    if not label:
        return None
    state = "p4_pending" if decision.get("route") == "P4" else "p6_pending"
    return {"lineId": _line_id(chapter_id, key, state), "semantic": key,
            "text": f"{label}：待确认。", "state": state, "supportingRuleIds": [],
            "sourceDecisionIds": [decision["decisionId"]], "sourceText": ""}


def _approved_line(chapter_id: str, statement: dict[str, Any]) -> dict[str, Any]:
    semantic = statement["semantic"]
    text = _DENSE_TEXT.get(semantic, statement["text"])
    return {"lineId": _line_id(chapter_id, semantic, "approved"), "semantic": semantic,
            "text": text, "state": "approved",
            "supportingRuleIds": list(statement.get("supportingRuleIds", [])),
            "sourceStatementIds": [statement.get("statementId")], "sourceText": statement["text"]}


def build_review_state_density_preview(chapters: list[dict[str, Any]],
                                       review_decisions: list[dict[str, Any]],
                                       parameter_placements: list[dict[str, Any]]) -> dict[str, Any]:
    del parameter_placements  # Decisions are the audited P4/P6 state authority for this preview.
    audit: dict[str, list[dict[str, Any]]] = {
        "deletedItems": [], "mergedItems": [], "pendingRendered": [],
        "evidenceRecheckSuppressed": [
            {"decisionId": item["decisionId"], "decisionKey": item["decisionKey"],
             "ownerChapter": item.get("ownerChapter"), "renderState": "pending_evidence"}
            for item in review_decisions if item.get("route") == "Evidence Recheck"],
        "suppressedItemsRemoved": [
            {"decisionId": item["decisionId"], "decisionKey": item["decisionKey"],
             "ownerChapter": item.get("ownerChapter")}
            for item in review_decisions if item.get("route") == "Suppress"]}
    output_chapters: list[dict[str, Any]] = []

    decisions_by_owner: dict[str, list[dict[str, Any]]] = {}
    for decision in review_decisions:
        decisions_by_owner.setdefault(decision.get("ownerChapter", ""), []).append(decision)

    for chapter in chapters:
        chapter_id = chapter["chapterId"]
        statements = chapter.get("statements", [])
        specific_affix = {item.get("semantic") for item in statements} >= {
            "fire_range", "thunder_damage", "ultimate_direction"}
        absorbed_summary_rule_ids = [rule_id for item in statements
            if item.get("semantic") == "affix_attack_change" and specific_affix
            for rule_id in item.get("supportingRuleIds", [])]
        lines: list[dict[str, Any]] = []
        for statement in statements:
            if statement.get("semantic") == "affix_attack_change" and specific_affix:
                audit["deletedItems"].append({"chapterTitle": chapter["chapterTitle"],
                    "semantic": statement["semantic"], "text": statement["text"],
                    "supportingRuleIds": statement.get("supportingRuleIds", []),
                    "reason": "abstract_summary_over_specific_rule"})
                continue
            line = _approved_line(chapter_id, statement)
            if statement.get("semantic") in {"fire_range", "thunder_damage", "ultimate_direction"}:
                line["supportingRuleIds"] = list(dict.fromkeys(
                    line["supportingRuleIds"] + absorbed_summary_rule_ids))
            lines.append(line)
            if line["text"] != statement["text"]:
                audit["mergedItems"].append({"chapterTitle": chapter["chapterTitle"],
                    "semantic": statement["semantic"], "before": statement["text"],
                    "after": line["text"], "supportingRuleIds": line["supportingRuleIds"]})

        pending_labels: set[str] = set()
        for decision in decisions_by_owner.get(chapter_id, []):
            if not _topic_belongs_to_chapter(chapter["chapterTitle"], decision):
                continue
            route = decision.get("route")
            if route == "Evidence Recheck":
                continue
            if route == "Suppress":
                continue
            if route not in {"P4", "P6"} or decision.get("approvalStatus") == "approved":
                continue
            # Conditional P6 inputs are inactive until their parent P4 choice is approved.
            if route == "P6" and decision.get("dependency"):
                continue
            pending = _pending_line(chapter_id, decision)
            if not pending or pending["text"] in pending_labels:
                continue
            pending_labels.add(pending["text"])
            lines.append(pending)
            audit["pendingRendered"].append({"chapterTitle": chapter["chapterTitle"],
                "decisionId": decision["decisionId"], "decisionKey": decision["decisionKey"],
                "state": pending["state"], "text": pending["text"]})

        output_chapters.append({"chapterId": chapter_id, "chapterTitle": chapter["chapterTitle"],
                                "lines": lines})
    return {"chapters": output_chapters, "audit": audit}


def evaluate_document_density_gate(preview: dict[str, Any]) -> dict[str, Any]:
    counts = {key: 0 for key in (
        "redundantSubject", "redundantTransition", "commonSenseExplanation",
        "abstractSummaryOverSpecificRule", "duplicatedMeaning", "reviewQuestionLeak",
        "reviewOptionLeak", "evidenceRecheckAsRule", "suppressedItemLeak",
        "lostCondition", "lostResult", "lostNumber", "lostLimit", "ambiguousSubject")}
    findings: list[dict[str, Any]] = []
    for chapter in preview.get("chapters", []):
        seen: set[str] = set()
        for line in chapter.get("lines", []):
            text = line.get("text", "")
            source = line.get("sourceText", "")
            checks = {
                "redundantSubject": bool(re.search(r"^(玩家|系统|武器|怪物)\1", text)),
                "redundantTransition": bool(re.search(r"对应.+(?:生效|产生影响)|进行实现|产生影响", text)),
                "commonSenseExplanation": any(term in text for term in ("为了", "从而", "帮助玩家", "该设计旨在")),
                "abstractSummaryOverSpecificRule": line.get("semantic") == "affix_attack_change" and any(
                    other.get("semantic") in {"fire_range", "thunder_damage", "ultimate_direction"}
                    for other in chapter.get("lines", [])),
                "duplicatedMeaning": text in seen,
                "reviewQuestionLeak": "？" in text,
                "reviewOptionLeak": "？" in text and any(term in text for term in ("或", "接触一次", "持续接触")),
                "evidenceRecheckAsRule": line.get("state") == "pending_evidence",
                "suppressedItemLeak": line.get("state") == "suppressed",
                "lostCondition": any(term in source for term in ("时", "后", "达到")) and not any(
                    term in text for term in ("时", "后", "达到", "提升")) and not (
                        line.get("semantic") == "three_choice_result" and "选择" in text and "获得" in text),
                "lostResult": any(term in source for term in ("失败", "获得", "伤害", "改变")) and not any(
                    term in text for term in ("失败", "获得", "伤害", "改变", "+", "改为")),
                "lostNumber": bool(re.search(r"\d", source)) and not bool(re.search(r"\d", text)),
                "lostLimit": any(term in source for term in ("无需", "仅", "最多", "不")) and not any(
                    term in text for term in ("无需", "仅", "最多", "不")),
                "ambiguousSubject": len(re.sub(r"[，。；：\s]", "", text)) <= 4 and line.get("state", "approved") == "approved",
            }
            seen.add(text)
            for metric, failed in checks.items():
                if failed:
                    counts[metric] += 1
                    findings.append({"metric": metric, "chapterTitle": chapter.get("chapterTitle"),
                                     "lineId": line.get("lineId"), "text": text})
    report = {f"{key[0].lower() + key[1:]}Count": value for key, value in counts.items()}
    report["findings"] = findings
    report["qualityGate"] = "pass" if not any(counts.values()) else "fail"
    return report
