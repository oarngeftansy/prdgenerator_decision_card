"""Canonical interaction-planning projection for Master Planner v2.

The planning sketch is derived from the canonical rule model. It is deliberately
mechanic-agnostic: a rule may describe a UI surface, a gameplay context, or a
system-only context. We never invent a fake screen merely to make a board.

`inferred` and `proposed` are provenance/display states, not blockers. The review
only blocks structural defects such as rules that disappeared from the sketch or
interactions that no longer point to canonical rules.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
from typing import Any


_UI_TERMS = (
    "页面", "界面", "按钮", "点击", "选择", "弹窗", "列表", "入口", "关闭", "返回", "提示",
    "panel", "button", "click", "tap", "modal", "screen", "ui",
)
_GAMEPLAY_TERMS = (
    "移动", "攻击", "战斗", "目标", "碰撞", "死亡", "生成", "刷新", "技能", "单位", "回合",
    "关卡", "波次", "资源", "奖励", "结算", "伤害", "速度", "位置", "范围", "状态",
)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)
    return str(value or "")


def _stable_id(prefix: str, *parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return f"{prefix}-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12].upper()


def _context_type(rule: dict[str, Any]) -> str:
    text = _text(rule).casefold()
    if any(term.casefold() in text for term in _UI_TERMS):
        return "ui_surface"
    if any(term.casefold() in text for term in _GAMEPLAY_TERMS):
        return "gameplay_context"
    return "system_context"


def _owner_id(rule: dict[str, Any]) -> str:
    return str(
        rule.get("ownerMechanicId")
        or rule.get("canonicalOwner")
        or rule.get("ownerChapterId")
        or rule.get("system")
        or "UNSCOPED"
    )


def _context_title(owner: str, context_type: str, chapter_by_id: dict[str, dict[str, Any]]) -> str:
    chapter = chapter_by_id.get(owner) or {}
    for key in ("title", "mechanism", "subsystem", "system", "object"):
        value = str(chapter.get(key) or "").strip()
        if value:
            return value
    return {
        "ui_surface": "交互界面",
        "gameplay_context": "玩法交互",
        "system_context": "系统行为",
    }[context_type]


def _state_change(rule: dict[str, Any]) -> str:
    explicit = str(
        rule.get("stateChange")
        or rule.get("resultState")
        or rule.get("afterState")
        or ""
    ).strip()
    if explicit:
        return explicit
    return str(rule.get("result") or "").strip()


def build_planning_sketch(publication: dict[str, Any]) -> dict[str, Any]:
    """Project canonical rules into a reviewable, mechanic-agnostic sketch."""
    rules = [deepcopy(rule) for rule in publication.get("rules") or [] if isinstance(rule, dict)]
    chapters = [chapter for chapter in publication.get("chapters") or [] if isinstance(chapter, dict)]
    chapter_by_id = {str(chapter.get("chapterId") or ""): chapter for chapter in chapters}

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rule in rules:
        if rule.get("publicationEligibility", "eligible") != "eligible":
            continue
        owner = _owner_id(rule)
        context_type = _context_type(rule)
        grouped.setdefault((owner, context_type), []).append(rule)

    contexts: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    for (owner, context_type), owned_rules in grouped.items():
        context_id = _stable_id("CTX", owner, context_type)
        interactions: list[dict[str, Any]] = []
        state_nodes: list[dict[str, Any]] = []
        for rule in owned_rules:
            rule_id = str(rule.get("ruleId") or _stable_id("RULE", owner, _text(rule)))
            interaction_id = _stable_id("INT", context_id, rule_id)
            publication_state = str(rule.get("publicationState") or rule.get("reviewStatus") or "confirmed")
            interaction = {
                "interactionId": interaction_id,
                "ruleRefs": [rule_id],
                "publicationState": publication_state,
                "intent": str(rule.get("intent") or "").strip(),
                "trigger": str(rule.get("trigger") or "").strip(),
                "preconditions": [str(item) for item in (rule.get("conditions") or []) if str(item).strip()],
                "action": str(rule.get("behavior") or "").strip(),
                "result": str(rule.get("result") or "").strip(),
                "stateChange": _state_change(rule),
                "exception": str(rule.get("exception") or "").strip(),
                "persistence": str(rule.get("persistence") or "").strip(),
                "reset": str(rule.get("reset") or "").strip(),
                "dependencies": [str(item) for item in (rule.get("dependencies") or []) if str(item).strip()],
                "acceptanceCases": deepcopy(rule.get("acceptanceCases") or []),
            }
            interactions.append(interaction)
            if interaction["stateChange"]:
                state_nodes.append({
                    "stateId": _stable_id("STATE", interaction_id, interaction["stateChange"]),
                    "label": interaction["stateChange"],
                    "publicationState": publication_state,
                    "ruleRefs": [rule_id],
                })
            if interaction["trigger"] or interaction["result"]:
                all_edges.append({
                    "edgeId": _stable_id("EDGE", interaction_id),
                    "contextId": context_id,
                    "interactionId": interaction_id,
                    "from": interaction["trigger"] or "context_active",
                    "to": interaction["result"] or interaction["stateChange"] or "context_updated",
                    "publicationState": publication_state,
                    "ruleRefs": [rule_id],
                })

        contexts.append({
            "contextId": context_id,
            "ownerId": owner,
            "title": _context_title(owner, context_type, chapter_by_id),
            "contextType": context_type,
            "ruleRefs": [str(rule.get("ruleId") or "") for rule in owned_rules if str(rule.get("ruleId") or "")],
            "states": state_nodes,
            "interactions": interactions,
        })

    return {
        "version": "planning_sketch_v2",
        "authority": "canonical_rule_projection",
        "contexts": contexts,
        "edges": all_edges,
        "ruleCount": len(rules),
        "contextCount": len(contexts),
    }


def audit_planning_sketch(sketch: dict[str, Any], publication: dict[str, Any]) -> dict[str, Any]:
    """Check traceability/closure without treating inference as an error."""
    eligible_rule_ids = {
        str(rule.get("ruleId") or "")
        for rule in publication.get("rules") or []
        if isinstance(rule, dict)
        and rule.get("publicationEligibility", "eligible") == "eligible"
        and str(rule.get("ruleId") or "")
    }
    covered: set[str] = set()
    orphan_interactions: list[str] = []
    states = Counter()
    interaction_count = 0
    for context in sketch.get("contexts") or []:
        if not isinstance(context, dict):
            continue
        for interaction in context.get("interactions") or []:
            if not isinstance(interaction, dict):
                continue
            interaction_count += 1
            refs = {str(item) for item in (interaction.get("ruleRefs") or []) if str(item)}
            covered.update(refs & eligible_rule_ids)
            if not refs or refs.isdisjoint(eligible_rule_ids):
                orphan_interactions.append(str(interaction.get("interactionId") or ""))
            states[str(interaction.get("publicationState") or "confirmed")] += 1

    uncovered = sorted(eligible_rule_ids - covered)
    critical: list[str] = []
    if uncovered:
        critical.append("planning_sketch_rule_coverage_incomplete")
    if orphan_interactions:
        critical.append("planning_sketch_orphan_interactions")
    return {
        "version": "interaction_review_v2",
        "ready": not critical,
        "criticalIssues": critical,
        "uncoveredRuleIds": uncovered,
        "orphanInteractionIds": orphan_interactions,
        "interactionCount": interaction_count,
        "publicationStateCounts": dict(states),
        "policy": "inferred_and_proposed_are_reviewable_non_blocking_states",
    }


def planning_sketch_to_markdown(sketch: dict[str, Any]) -> str:
    """Render the canonical sketch without leaking provenance labels into copy."""
    lines = ["## 策划草图", ""]
    for context in sketch.get("contexts") or []:
        if not isinstance(context, dict):
            continue
        title = str(context.get("title") or "玩法上下文").strip()
        lines.extend([f"### {title}", ""])
        for interaction in context.get("interactions") or []:
            if not isinstance(interaction, dict):
                continue
            action = str(interaction.get("action") or "").strip()
            if action:
                lines.append(f"- {action.rstrip('。；')}。")
            trigger = str(interaction.get("trigger") or "").strip()
            result = str(interaction.get("result") or interaction.get("stateChange") or "").strip()
            if trigger or result:
                transition = " → ".join(value for value in (trigger, result) if value)
                lines.append(f"  - 流转：{transition}")
            conditions = [str(value).strip() for value in interaction.get("preconditions") or [] if str(value).strip()]
            if conditions:
                lines.append("  - 条件：" + "；".join(conditions))
            exception = str(interaction.get("exception") or "").strip()
            if exception:
                lines.append(f"  - 异常：{exception}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def project_and_review_interactions(publication: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    sketch = build_planning_sketch(publication)
    return sketch, audit_planning_sketch(sketch, publication)
