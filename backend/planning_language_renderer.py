"""Deterministic Phase 4 renderer over canonical structured rules.

The renderer may reorganize approved semantics, but never invent business rules. Knowledge
status is carried as metadata and mapped to visual tone; it must never leak into prose.
"""

from __future__ import annotations

import re
from typing import Any

from .rule_status import normalize_rule_status, status_visual_tone, strip_status_caveat


APPROVED_STATUSES = {"approved", "confirmed"}


def _complete(text: str) -> str:
    text = re.sub(r"\s+", "", str(text or "").strip())
    if text and text[-1] not in "。！？；":
        text += "。"
    return text


def _controlled_variant(text: str) -> str:
    """Apply syntax-only variants whose output is a semantic paraphrase."""
    text = re.sub(r"^(.+?)改变攻击方向将(.+?)由(.+?)改为(.+)$", r"\1将\2由\3改为\4", text)
    text = re.sub(r"^已选(.+?)选择后改变(.+)$", r"玩家选择\1后，改变所选\1的\2", text)
    text = text.replace("移出武器合法目标集合", "不再作为武器攻击目标")
    text = text.replace("剩余合法目标", "剩余可攻击目标")
    return text


def _clean_business_text(value: Any) -> str:
    """Keep planner prose decisive while removing legacy provenance/audit prefixes."""
    return strip_status_caveat(value).strip().rstrip("。；")


def render_rule(rule: dict[str, Any], style_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render one canonical rule without changing its business semantics.

    CONFIRMED renders normally. INFERRED and PROPOSED render normally in prose but carry
    ``visualTone=inference`` so web/Feishu can highlight them yellow. CONFLICT carries a
    conflict tone. The knowledge status is never verbalized inside ``text``.
    """
    knowledge_status = normalize_rule_status(
        rule.get("knowledgeStatus"),
        inference_level=rule.get("inferenceLevel"),
        source_type=rule.get("sourceType"),
    )
    base = {
        "sentenceId": f"S-{rule.get('ruleId', 'UNKNOWN')}",
        "sourceRuleIds": list(dict.fromkeys(([rule.get("ruleId")] if rule.get("ruleId") else []) + list(rule.get("mergedSourceRuleIds") or []))),
        "sourceFactIds": list(dict.fromkeys(list(rule.get("sourceFactIds") or []) + list(rule.get("mergedSourceFactIds") or []))),
        "evidenceIds": list(rule.get("evidenceIds") or []),
        "ruleTypes": [rule.get("ruleType")] if rule.get("ruleType") else [],
        "schemaSlots": [rule.get("schemaSlot")] if rule.get("schemaSlot") else [],
        "semanticKey": str(rule.get("semanticKey") or ""),
        "knowledgeStatus": knowledge_status,
        "visualTone": status_visual_tone(knowledge_status),
    }
    if rule.get("reviewStatus") not in APPROVED_STATUSES:
        return {**base, "status": "rejected", "reason": "rule_not_approved", "text": ""}
    if rule.get("semanticValidity") != "valid" or not rule.get("behavior"):
        return {**base, "status": "rejected", "reason": "invalid_semantics", "text": ""}

    parts: list[str] = []
    trigger = _clean_business_text(rule.get("trigger"))
    conditions = [_clean_business_text(item) for item in (rule.get("conditions") or [])]
    conditions = [item for item in conditions if item]
    behavior = _controlled_variant(_clean_business_text(rule["behavior"]))
    result = _clean_business_text(rule.get("result"))
    exit_condition = _clean_business_text(rule.get("exitCondition"))
    exception = _clean_business_text(rule.get("exception"))

    prefix = trigger or ("且".join(conditions) if conditions else "")
    if prefix and prefix not in behavior:
        parts.append(f"当{prefix}时，{behavior}")
    else:
        parts.append(behavior)
    if result and result not in behavior:
        parts.append(result)
    if exit_condition:
        parts.append(f"当{exit_condition}时，退出当前状态")
    if exception:
        parts.append(f"例外：{exception}")

    text = "；".join(part for part in parts if part)
    forbidden = (style_profile or {}).get("forbidden_expressions", [])
    violations = [phrase for phrase in forbidden if phrase and phrase in text]
    return {**base, "status": "rendered", "text": _complete(text), "lintViolations": violations}
