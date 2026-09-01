from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any


ENTITY_TYPES = frozenset({
    "runtime_object", "container", "content_item", "candidate_set",
    "runtime_context", "process", "report",
})
CORE_RULE_TYPES = frozenset({"logic", "flow", "numeric", "config", "interaction"})
SOURCE_TARGET_PATTERNS = (
    re.compile(r"选择.+作为.+目标"),
    re.compile(r"接触.+(?:造成|触发)"),
    re.compile(r"改变.+(?:方式|方向|状态)"),
    re.compile(r"获得.+"),
)


def _approved(rule: dict[str, Any]) -> bool:
    return rule.get("reviewStatus") in {"approved", "confirmed"} and rule.get("semanticValidity") == "valid"


def _matches(text: str, aliases: list[str]) -> bool:
    return any(alias and alias in text for alias in sorted(aliases, key=len, reverse=True))


def build_entity_graph(
    chapters: list[dict[str, Any]],
    approved_rules: list[dict[str, Any]],
    reviewed_gaps: list[dict[str, Any]],
    entity_declarations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic Logic/Data graph; presentation is reference-only."""
    chapters = deepcopy(chapters)
    rules = deepcopy(approved_rules)
    gaps = deepcopy(reviewed_gaps)
    declarations = deepcopy(entity_declarations)
    chapter_ids = {c.get("chapterId") for c in chapters}

    for declaration in declarations:
        if declaration.get("entityType") not in ENTITY_TYPES:
            raise ValueError(f"unsupported EntityType: {declaration.get('entityType')}")

    aliases = {
        d["entityId"]: list(dict.fromkeys([d["name"], *d.get("aliases", [])]))
        for d in declarations
    }
    by_id = {d["entityId"]: d for d in declarations}
    core_rules = [r for r in rules if _approved(r) and r.get("ruleType") in CORE_RULE_TYPES]
    presentation_rules = [r for r in rules if _approved(r) and r.get("ruleType") == "presentation"]

    entities: list[dict[str, Any]] = []
    for declaration in declarations:
        entity_id = declaration["entityId"]
        related_rules = [
            r["ruleId"] for r in core_rules
            if _matches(" ".join(str(r.get(k) or "") for k in ("subject", "behavior", "result", "stateChange")), aliases[entity_id])
        ]
        candidate_chapters = [
            r["ownerChapterId"] for r in core_rules
            if r["ruleId"] in related_rules and r.get("ownerChapterId") in chapter_ids
        ]
        nominated = declaration.get("primaryChapterId")
        primary = nominated if nominated in chapter_ids else (candidate_chapters[0] if candidate_chapters else None)
        references = sorted({*candidate_chapters, *declaration.get("referenceChapterIds", [])} - ({primary} if primary else set()))
        related_gaps = [
            gap["gapId"] for gap in gaps
            if gap.get("chapterId") == primary or gap.get("chapterId") in references
        ]
        definition_status = "confirmed" if related_rules else "evidence_insufficient"
        entities.append({
            "entityId": entity_id,
            "name": declaration["name"],
            "entityType": declaration["entityType"],
            "semanticKey": declaration["semanticKey"],
            "ownerEntityId": declaration.get("ownerEntityId"),
            "parentEntityId": declaration.get("parentEntityId"),
            "childEntityIds": [],
            "primaryDefinitionChapter": primary,
            "referenceChapters": references,
            "relatedRuleIds": sorted(set(related_rules)),
            "relatedGapIds": sorted(set(related_gaps)),
            "definitionStatus": definition_status,
            "declarationEvidence": declaration.get("declarationEvidence", "approved domain declaration"),
        })

    entity_map = {e["entityId"]: e for e in entities}
    relationships: list[dict[str, Any]] = []
    for declaration in declarations:
        child_id = declaration["entityId"]
        reason = declaration.get("relationReason", "approved domain declaration")
        owner_id = declaration.get("ownerEntityId")
        if owner_id:
            if owner_id not in entity_map:
                raise ValueError(f"unknown owner entity: {owner_id}")
            relationships.append({"relationType": "owner", "sourceEntityId": owner_id, "targetEntityId": child_id, "evidenceRuleIds": [], "reason": reason})
        parent_id = declaration.get("parentEntityId")
        if parent_id:
            if parent_id not in entity_map:
                raise ValueError(f"unknown parent entity: {parent_id}")
            entity_map[parent_id]["childEntityIds"].append(child_id)
            relationships.append({"relationType": "parent_child", "sourceEntityId": parent_id, "targetEntityId": child_id, "evidenceRuleIds": [], "reason": reason})

    seen_source_target: set[tuple[str, str]] = set()
    for rule in core_rules:
        subject_text = str(rule.get("subject") or "")
        remainder = " ".join(str(rule.get(k) or "") for k in ("behavior", "result", "stateChange"))
        source_ids = [entity_id for entity_id, names in aliases.items() if _matches(subject_text, names)]
        target_ids = [entity_id for entity_id, names in aliases.items() if _matches(remainder, names)]
        if not any(pattern.search(remainder) for pattern in SOURCE_TARGET_PATTERNS):
            continue
        for source_id in source_ids:
            for target_id in target_ids:
                if source_id == target_id or (source_id, target_id) in seen_source_target:
                    continue
                seen_source_target.add((source_id, target_id))
                relationships.append({
                    "relationType": "source_target", "sourceEntityId": source_id,
                    "targetEntityId": target_id, "evidenceRuleIds": [rule["ruleId"]],
                    "reason": "approved non-presentation rule",
                })

    presentation_refs = []
    for rule in presentation_rules:
        text = " ".join(str(rule.get(k) or "") for k in ("subject", "behavior", "result", "stateChange"))
        related = {
            entity_id for entity_id, names in aliases.items() if _matches(text, names)
        }
        owner_chapter = rule.get("ownerChapterId")
        related.update(
            entity["entityId"] for entity in entities
            if owner_chapter == entity["primaryDefinitionChapter"] or owner_chapter in entity["referenceChapters"]
        )
        related = sorted(related)
        presentation_refs.append({"ruleId": rule["ruleId"], "relatedEntityIds": related})

    presentation_ids = {r["ruleId"] for r in presentation_rules}
    backflow = sum(bool(presentation_ids.intersection(edge["evidenceRuleIds"])) for edge in relationships)
    for entity in entities:
        entity["childEntityIds"] = sorted(set(entity["childEntityIds"]))
    entities.sort(key=lambda e: e["entityId"])
    relationships.sort(key=lambda e: (e["relationType"], e["sourceEntityId"], e["targetEntityId"]))

    distribution = dict(sorted(Counter(e["entityType"] for e in entities).items()))
    return {
        "graphVersion": "entity-graph-v1",
        "entities": entities,
        "relationships": relationships,
        "entityTypeDistribution": distribution,
        "presentationRuleReferences": presentation_refs,
        "pollutionAudit": {
            "presentationCreatedEntityCount": 0,
            "presentationBackflowCount": backflow,
            "presentationSupportedCoreRelationshipCount": backflow,
            "directoryHeadingPromotedEntityCount": 0,
            "passed": backflow == 0,
        },
    }
