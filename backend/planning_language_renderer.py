"""Deterministic planning-language renderer.

The renderer changes syntax only. Provenance is carried as structured metadata so
user-visible copy never needs labels such as “推断/待确认”.
"""

from __future__ import annotations

import re
from typing import Any

from .publication_state import decorate_publication_item, normalize_publication_state


APPROVED_STATUSES = {"approved", "confirmed", "inferred", "proposed"}


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


def render_rule(rule: dict[str, Any], style_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render one publishable rule without changing its business semantics."""
    publication_state = normalize_publication_state(rule)
    base = {
        "sentenceId": f"S-{rule.get('ruleId', 'UNKNOWN')}",
        "sourceRuleIds": list(dict.fromkeys(([rule.get("ruleId")] if rule.get("ruleId") else []) + list(rule.get("mergedSourceRuleIds") or []))),
        "sourceFactIds": list(dict.fromkeys(list(rule.get("sourceFactIds") or []) + list(rule.get("mergedSourceFactIds") or []))),
        "evidenceIds": list(rule.get("evidenceIds") or []),
        "ruleTypes": [rule.get("ruleType")] if rule.get("ruleType") else [],
        "schemaSlots": [rule.get("schemaSlot")] if rule.get("schemaSlot") else [],
        "publicationState": publication_state,
    }
    review_status = str(rule.get("reviewStatus") or "").lower()
    # Inferred/proposed rules are intentionally publishable. Their uncertainty is
    # exposed through publicationState/visual metadata rather than hedged prose.
    if review_status not in APPROVED_STATUSES and publication_state not in {"inferred", "proposed", "conflict"}:
        return decorate_publication_item({**base, "status": "rejected", "reason": "rule_not_publishable", "text": ""})
    if rule.get("semanticValidity") not in {None, "valid"} or not rule.get("behavior"):
        return decorate_publication_item({**base, "status": "rejected", "reason": "invalid_semantics", "text": ""})

    parts: list[str] = []
    trigger = str(rule.get("trigger") or "").strip()
    conditions = [str(item).strip() for item in (rule.get("conditions") or []) if str(item).strip()]
    behavior = _controlled_variant(str(rule["behavior"]).strip().rstrip("。；"))
    result = str(rule.get("result") or "").strip().rstrip("。；")
    exit_condition = str(rule.get("exitCondition") or "").strip().rstrip("。；")
    exception = str(rule.get("exception") or "").strip().rstrip("。；")

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
    return decorate_publication_item({**base, "status": "rendered", "text": _complete(text), "lintViolations": violations})
