"""Evidence-backed Phase 4 quality metrics over assembled sentence records."""

from __future__ import annotations

from typing import Any


DEFAULT_FILLER = ["为了", "从而", "帮助玩家", "使玩家能够", "该设计旨在", "有助于", "这样可以"]
DEFAULT_META = ["应作为独立机制描述", "正文按实际语义区分", "不扩写为", "本次截图显示", "当前截图显示", "画面核对", "本次战斗中可见"]


def _sentences(document: dict[str, Any]):
    for system in document.get("systems", []):
        for obj in system.get("objects", []):
            for chapter in obj.get("chapters", []):
                for group in chapter.get("groups", []):
                    yield from group.get("sentences", [])


def evaluate_document(document: dict[str, Any], approved_rules: list[dict[str, Any]], gaps: list[dict[str, Any]], style_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    sentences = list(_sentences(document))
    texts = [item["text"] for item in sentences]
    normalized = [text.rstrip("。；") for text in texts]
    approved_ids = {r["ruleId"] for r in approved_rules if r.get("reviewStatus") in {"approved", "confirmed"}}
    traced_ids = {rid for item in sentences for rid in item.get("sourceRuleIds", [])}
    gap_questions = {gap.get("question", "").rstrip("？") for gap in gaps}
    filler = DEFAULT_FILLER
    meta = DEFAULT_META
    return {
        "commonSenseFillerCount": sum(text.count(p) for text in texts for p in filler),
        "aiMetaLanguageCount": sum(text.count(p) for text in texts for p in meta),
        "duplicateRuleCount": len(normalized) - len(set(normalized)),
        "mixedLogicPresentationCount": sum(1 for item in sentences if "presentation" in item.get("ruleTypes", []) and len(set(item.get("ruleTypes", []))) > 1),
        "unsupportedBodySentenceCount": sum(1 for item in sentences if not item.get("sourceRuleIds")),
        "gapPromotedToConfirmedCount": sum(1 for text in normalized if text in gap_questions),
        "approvedRuleCount": len(approved_ids),
        "tracedApprovedRuleCount": len(approved_ids & traced_ids),
        "ruleToFinalSentenceTraceabilityRate": round(len(approved_ids & traced_ids) / len(approved_ids), 4) if approved_ids else 1.0,
        "finalSentenceCount": len(sentences),
    }
