from __future__ import annotations

import re
from typing import Any, Iterable


DOMAIN_TAGS: dict[str, frozenset[str]] = {
    "movement": frozenset({"movement", "path", "position", "speed", "navigation"}),
    "placement": frozenset({"placement", "placement_grid", "grid", "occupancy", "building_slot"}),
    "random": frozenset({"random", "random_choice", "weights", "replacement", "reroll", "pool"}),
    "combat": frozenset({"combat", "health", "damage", "attack", "defence", "targeting"}),
    "growth": frozenset({"growth", "level_up", "upgrade", "experience", "progression"}),
    "buff": frozenset({"buff", "buff_duration", "status_effect", "stack", "immunity"}),
    "inventory": frozenset({"inventory", "inventory_slot", "item", "stack_limit", "capacity"}),
    "level": frozenset({"level", "wave", "stage", "checkpoint", "victory", "failure"}),
    "sweep": frozenset({"sweep", "skip_battle", "offline_reward", "sweep_cost"}),
}

DOMAIN_UNRESOLVED: dict[str, frozenset[str]] = {
    "movement": frozenset({"movement_boundary", "reset_position", "path_branch"}),
    "placement": frozenset({"overlap", "placement_failure", "relocation"}),
    "random": frozenset({"weights", "replacement", "duplicate_policy", "reroll_cost", "pool_scope"}),
    "combat": frozenset({"damage_order", "target_priority", "death_timing"}),
    "growth": frozenset({"upgrade_cost", "max_level", "reset_scope"}),
    "buff": frozenset({"stack_rule", "refresh_rule", "dispel_rule"}),
    "inventory": frozenset({"capacity", "overflow", "stack_limit"}),
    "level": frozenset({"victory_condition", "failure_condition", "checkpoint_reset"}),
    "sweep": frozenset({"sweep_cost", "sweep_limit", "reward_basis"}),
}

VALID_SOURCE_SCOPES = frozenset(
    {
        "current_material",
        "current_reference",
        "current_configuration",
        "planner_decision",
        "sample_reserve",
    }
)

_PUNCTUATION = re.compile(r"[\s，。；：、,.!?！？（）()\-—]")


def _normalized(value: Any) -> str:
    return _PUNCTUATION.sub("", str(value or "")).casefold()


def _text_leaves(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        if value.strip():
            yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _text_leaves(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _text_leaves(child)


def classify_domain_modules(evidence_tags: set[str], unresolved: set[str]) -> dict[str, str]:
    """Activate only gameplay domains supported by current-project evidence."""

    evidence = {str(item).strip().casefold() for item in evidence_tags if str(item).strip()}
    pending = {str(item).strip().casefold() for item in unresolved if str(item).strip()}
    states: dict[str, str] = {}
    for domain, tags in DOMAIN_TAGS.items():
        if not evidence.intersection(tags):
            states[domain] = "not_applicable"
        elif pending.intersection(DOMAIN_UNRESOLVED[domain]):
            states[domain] = "decision_required"
        else:
            states[domain] = "applicable"
    return states


def provenance_scope_report(model: dict[str, Any]) -> dict[str, Any]:
    """Prevent reusable examples from silently becoming current-project facts."""

    findings: list[dict[str, Any]] = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        published = {
            _normalized(text)
            for text in _text_leaves(chapter.get("plannerSections") or {})
            if _normalized(text)
        }
        for claim in chapter.get("provenanceClaims") or []:
            if not isinstance(claim, dict):
                continue
            if str(claim.get("sourceScope") or "") != "sample_reserve":
                continue
            text = str(claim.get("text") or "").strip()
            is_published = bool(claim.get("publicationAllowed") is True)
            is_published = is_published or bool(text and _normalized(text) in published)
            if is_published:
                findings.append(
                    {
                        "chapterId": chapter.get("id"),
                        "code": "SAMPLE_RESERVE_PUBLISHED_AS_FACT",
                        "text": text,
                        "action": "样例只用于补充检查维度或生成决策问题；结论必须由当前素材、配置或策划选择支持。",
                    }
                )
    return {"passed": not findings, "findings": findings}
