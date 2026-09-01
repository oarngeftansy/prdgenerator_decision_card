from __future__ import annotations

import re
from typing import Any


POLICY_REF = "gameplay.flow_semantic_ownership_and_isolation"


_ROUTE_BY_TYPE = {
    "flow": "normalFlow",
    "interaction": "normalFlow",
    "logic": "keyRules",
    "presentation": "presentationRules",
    "numeric": "numericRules",
    "config": "configurationRules",
}

_STATIC_EVIDENCE = re.compile(
    r"(?:页面|界面|面板|弹窗|图标|按钮|画面|底部|顶部).*(?:显示|展示)|"
    r"(?:显示|展示).*(?:等级|收益|数值|图标|文本|公式)|"
    r"(?:公式|上限|下限|范围|倍率|当前值|每秒收益)(?:为|等于|是)",
)
_INITIATION = re.compile(r"(?:当|时|后|达到|进入|开始|点击|选择|确认|提交|拖动|输入|购买|升级|攻击|读取|消耗|关卡开始|玩家)")
_OUTCOME = re.compile(r"(?:系统|反馈|刷新|攻击|计算|扣除|提升|降低|增加|减少|更新|保存|生成|创建|获得|归零|击败|推进|变化|持续|生效|进入(?:结算|场景|页面))")
_EXIT = re.compile(r"(?:结算|结束|完成|返回|进入下一|进入初始|持续|直到|失败|成功|终点)")
_NUMERIC_EVIDENCE = re.compile(r"(?:公式|收益|等级|倍率|百分比|数值|当前值|每秒|上限|下限|范围|\d+(?:\.\d+)?%|[+×*/=])")


def _text(value: Any) -> str:
    return str(value or "").strip()


def route_structured_rules(rules: list[dict]) -> dict[str, list[str]]:
    """Route approved rule copy by semantic responsibility without rewriting it."""
    routed = {slot: [] for slot in (
        "normalFlow", "keyRules", "presentationRules", "numericRules", "configurationRules",
    )}
    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        behavior = _text(rule.get("behavior") or rule.get("text"))
        if not behavior:
            continue
        slot = _ROUTE_BY_TYPE.get(_text(rule.get("ruleType")).casefold(), "keyRules")
        if behavior not in routed[slot]:
            routed[slot].append(behavior)
    return routed


def _is_static_evidence(text: str) -> bool:
    return bool(_STATIC_EVIDENCE.search(text)) and not bool(re.search(
        r"(?:点击|选择|确认|提交|拖动|输入|购买|升级|攻击|扣除|提升|降低|增加|减少|更新|保存|生成|创建|获得|归零|击败|推进|进入结算)",
        text,
    ))


def _as_text_list(value: Any) -> list[str]:
    """Normalize legacy scalar/list slots without spreading strings into characters."""
    values = value if isinstance(value, list) else ([] if value is None else [value])
    return list(dict.fromkeys(_text(item) for item in values if _text(item)))


def repair_legacy_flow_ownership(chapter: dict) -> dict:
    """Move legacy screenshot and numeric observations out of gameplay flow."""
    if not isinstance(chapter.get("plannerSections"), dict):
        return chapter
    sections = chapter["plannerSections"]
    sections["normalFlow"] = _as_text_list(sections.get("normalFlow"))
    for slot in ("keyRules", "presentationRules", "numericRules", "configurationRules", "acceptanceExamples"):
        if slot in sections:
            sections[slot] = _as_text_list(sections.get(slot))
    if sections.get("normalFlowSource") == "planner":
        return chapter
    retained: list[str] = []
    for item in sections["normalFlow"]:
        if not _is_static_evidence(item):
            retained.append(item)
            continue
        target = "numericRules" if _NUMERIC_EVIDENCE.search(item) else "presentationRules"
        target_items = sections.setdefault(target, [])
        if item not in target_items:
            target_items.append(item)
    sections["normalFlow"] = retained
    return chapter


def flow_chain_report(chapter: dict) -> dict:
    """Validate declared gameplay flow independently of project identity or title."""
    sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    flow = [_text(item) for item in sections.get("normalFlow") or [] if _text(item)]
    if not flow:
        return {"passed": True, "declared": False, "errors": [], "roles": []}

    static_items = [item for item in flow if _is_static_evidence(item)]
    combined = "。".join(item for item in flow if item not in static_items)
    roles = []
    if _INITIATION.search(combined):
        roles.append("initiation")
    if _OUTCOME.search(combined):
        roles.append("outcome")
    if _EXIT.search(combined):
        roles.append("exit")

    errors = []
    if static_items:
        errors.append("STATIC_EVIDENCE_IS_NOT_FLOW")
    if not {"initiation", "outcome"}.issubset(roles):
        errors.append("FLOW_CHAIN_CAUSALITY_MISSING")
    return {
        "passed": not errors,
        "declared": True,
        "errors": errors,
        "roles": roles,
        "staticItems": static_items,
    }
