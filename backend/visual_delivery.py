from __future__ import annotations

from copy import deepcopy
from typing import Any


LOGIC_RULE_TYPES = frozenset({"logic", "flow", "numeric", "config", "interaction"})
DERIVED_LINK_FAMILIES = frozenset({"movement", "damage_death", "randomization", "content_catalog", "settlement"})


def _approved(rule: dict[str, Any]) -> bool:
    return rule.get("reviewStatus") in {"approved", "confirmed"} and rule.get("semanticValidity") == "valid"


def _semantic_family(slot: str) -> str | None:
    if slot.startswith("movement_"):
        return "movement"
    if slot.startswith("attack_"):
        return "attack"
    if slot.startswith("damage_death_"):
        return "damage_death"
    if slot.startswith("random_") or slot in {"selection_pause", "candidate_selection", "candidate_effect", "refresh_rule", "refresh_count", "refresh_cost", "candidate_pool_source", "pool_entry_condition", "pool_exit_condition", "duplicate_rule", "replacement_rule", "weight_rule", "empty_result_rule", "max_level_rule", "prerequisite_rule", "roulette_stop"}:
        return "randomization"
    if slot.startswith("settlement_") or slot in {"result_determination", "reward_rule", "persistence_timing", "exit_path"}:
        return "settlement"
    if slot.startswith("content_catalog_"):
        return "content_catalog"
    return None


def _logic_entities(entity_graph: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for entity in entity_graph.get("entities", []):
        for rule_id in entity.get("relatedRuleIds", []):
            result.setdefault(rule_id, set()).add(entity["entityId"])
    return result


def _screenshot_projection(rule: dict[str, Any], evidence_index: dict[str, Any]) -> tuple[list[str], str, str]:
    screenshot_registry = evidence_index.get("screenshots", {})
    screenshot_ids: list[str] = []
    screen = ""
    state = ""
    for evidence_id in rule.get("evidenceIds", []):
        evidence = evidence_index.get(evidence_id, {})
        for screenshot_id in evidence.get("screenshotIds", []):
            record = screenshot_registry.get(screenshot_id)
            if not record or record.get("kind") != "screenshot":
                raise ValueError(f"sourceScreenshotIds contains a non-screenshot index: {screenshot_id}")
            if screenshot_id not in screenshot_ids:
                screenshot_ids.append(screenshot_id)
            screen = screen or str(record.get("screen") or "")
            state = state or str(record.get("state") or "")
    return screenshot_ids, screen, state


def build_visual_blocks(
    presentation_rules: list[dict[str, Any]],
    logic_rules: list[dict[str, Any]],
    entity_graph: dict[str, Any],
    evidence_index: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create one VisualBlock per Presentation Rule without changing Logic or Entity data."""
    presentations = deepcopy(presentation_rules)
    logic = deepcopy(logic_rules)
    graph = deepcopy(entity_graph)
    evidence = deepcopy(evidence_index)
    audited = {item["ruleId"]: list(item.get("relatedEntityIds", [])) for item in graph.get("presentationRuleReferences", [])}
    entity_ids = {item["entityId"] for item in graph.get("entities", [])}
    logic_by_id = {rule["ruleId"]: rule for rule in logic if _approved(rule) and rule.get("ruleType") in LOGIC_RULE_TYPES}
    entities_by_logic_rule = _logic_entities(graph)
    blocks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for rule in presentations:
        if rule.get("ruleType") != "presentation" or not _approved(rule):
            raise ValueError(f"VisualBlock requires an approved Presentation Rule: {rule.get('ruleId')}")
        rule_id = rule["ruleId"]
        related_entities = audited.get(rule_id)
        if not related_entities or not set(related_entities).issubset(entity_ids):
            raise ValueError(f"audited Entity reference is missing or invalid for {rule_id}")
        visual_id = f"VIS-{rule_id}"
        if visual_id in seen_ids:
            raise ValueError(f"duplicate VisualBlock ID: {visual_id}")
        seen_ids.add(visual_id)

        explicit_ids = list(rule.get("relatedLogicRuleIds") or [])
        if explicit_ids:
            invalid = [item for item in explicit_ids if item not in logic_by_id]
            if invalid:
                raise ValueError(f"explicit Logic Rule reference is invalid: {', '.join(invalid)}")
            related_logic_ids = list(dict.fromkeys(explicit_ids))
            link_reasons = {item: "explicit_rule_id" for item in related_logic_ids}
        else:
            presentation_family = _semantic_family(str(rule.get("schemaSlot") or ""))
            presentation_evidence = set(rule.get("evidenceIds") or [])
            related_logic_ids = []
            link_reasons = {}
            for logic_id, logic_rule in logic_by_id.items():
                shared_entity = bool(set(related_entities).intersection(entities_by_logic_rule.get(logic_id, set())))
                compatible = (
                    presentation_family in DERIVED_LINK_FAMILIES
                    and presentation_family == _semantic_family(str(logic_rule.get("schemaSlot") or ""))
                    and rule.get("ownerChapterId") == logic_rule.get("ownerChapterId")
                )
                evidence_match = bool(presentation_evidence.intersection(logic_rule.get("evidenceIds") or []))
                if shared_entity and compatible and evidence_match:
                    related_logic_ids.append(logic_id)
                    link_reasons[logic_id] = "shared_entity+compatible_mechanism_semantic+evidence_chain_intersection"

        screenshot_ids, screen, state = _screenshot_projection(rule, evidence)
        blocks.append({
            "visualBlockId": visual_id,
            "relatedEntityIds": related_entities,
            "relatedRuleIds": [rule_id],
            "relatedLogicRuleIds": related_logic_ids,
            "logicLinkReasons": link_reasons,
            "evidenceIds": list(rule.get("evidenceIds") or []),
            "screen": str(rule.get("screen") or screen),
            "state": str(rule.get("state") or state),
            "visualElement": str(rule.get("visualElement") or rule.get("subject") or ""),
            "triggerReference": str(rule.get("triggerReference") or ""),
            "presentationDescription": str(rule.get("behavior") or ""),
            "interactionAnchor": str(rule.get("interactionAnchor") or ""),
            "sourceScreenshotIds": screenshot_ids,
        })
    return blocks
