from __future__ import annotations

from enum import Enum
from typing import Any


class RuleKnowledgeStatus(str, Enum):
    """Planner-facing knowledge state. Status is metadata, never prose."""

    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    PROPOSED = "PROPOSED"
    CONFLICT = "CONFLICT"


_YELLOW = {RuleKnowledgeStatus.INFERRED.value, RuleKnowledgeStatus.PROPOSED.value}


def normalize_rule_status(value: Any, *, inference_level: Any = None, source_type: Any = None) -> str:
    raw = str(value or "").strip().upper()
    if raw in {item.value for item in RuleKnowledgeStatus}:
        return raw

    inference = str(inference_level or "").strip().casefold()
    source = str(source_type or "").strip().casefold()
    if inference in {"conflict", "contradiction", "contradicted"}:
        return RuleKnowledgeStatus.CONFLICT.value
    if source in {"proposal", "proposed", "planner_proposal"} or inference in {"proposal", "proposed"}:
        return RuleKnowledgeStatus.PROPOSED.value
    if source in {"inference", "inferred"} or inference in {
        "inference", "inferred", "derived_inference", "reasonable_inference", "hypothesis"
    }:
        return RuleKnowledgeStatus.INFERRED.value
    return RuleKnowledgeStatus.CONFIRMED.value


def status_visual_tone(status: Any) -> str:
    normalized = normalize_rule_status(status)
    if normalized in _YELLOW:
        return "inference"
    if normalized == RuleKnowledgeStatus.CONFLICT.value:
        return "conflict"
    return "confirmed"


def publication_allowed(status: Any) -> bool:
    """Inference is publishable; only unresolved conflict is a distinct review concern."""
    return normalize_rule_status(status) != RuleKnowledgeStatus.CONFLICT.value


def strip_status_caveat(text: Any) -> str:
    """Remove legacy audit prefixes while preserving the actual planner conclusion."""
    value = str(text or "").strip()
    prefixes = (
        "【黄色：推断】", "【推断】", "【AI推断】", "【建议】", "【待确认】",
        "黄色：推断：", "推断：", "AI推断：", "建议：",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if value.startswith(prefix):
                value = value[len(prefix):].lstrip(" ：:")
                changed = True
    return value
