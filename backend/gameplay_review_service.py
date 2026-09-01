from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any

from .gameplay_review_model import MECHANISM_SCHEMAS, configured_parameter_items, gameplay_gate, normalize_gameplay_structure, validate_gameplay_review_model
from .gameplay_directory import directory_errors, ensure_directory
from .chapter_schema_library import chapter_schema_library


_HISTORY_LIMIT = 50
_CHAPTER_FIELDS = {"scope", "claims", "parameters", "dependencies", "acceptanceCases", "unknowns", "decisionCards", "plannerSections", "sourceFrameIds"}
_METADATA_FIELDS = ("type", "unit", "range", "source")
_RULE_TYPES = {"logic", "presentation", "interaction", "flow", "numeric", "config"}
_RULE_DECISIONS = {"approved", "rejected", "needs_revision", "unreviewed"}


@dataclass
class GameplayReviewConflict(Exception):
    current_revision: int


def _require_revision(model: dict[str, Any], expected_revision: Any) -> None:
    current = model.get("revision")
    if type(expected_revision) is not int or expected_revision != current:
        raise GameplayReviewConflict(current_revision=current if type(current) is int else 0)


def _snapshot(model: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in model.items() if key not in {"revision", "editHistory"}}


def _restore(model: dict[str, Any], snapshot: dict[str, Any]) -> None:
    for key in list(model):
        if key not in {"revision", "editHistory"}:
            model.pop(key)
    model.update(deepcopy(snapshot))


def _history(model: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    history = model.get("editHistory")
    if not isinstance(history, list):
        history = []
        model["editHistory"] = history
    if not history or not isinstance(history[0], dict) or not all(isinstance(history[0].get(key), list) for key in ("undo", "redo")):
        history[:] = [{"undo": [], "redo": []}]
    return history[0]


def _remember(history: dict[str, list[dict[str, Any]]], direction: str, snapshot: dict[str, Any]) -> None:
    history[direction].append(deepcopy(snapshot))
    del history[direction][:-_HISTORY_LIMIT]


def _chapter(model: dict[str, Any], chapter_id: Any) -> dict[str, Any]:
    if not isinstance(chapter_id, str):
        raise ValueError("chapter id is required")
    for chapter in model.get("chapters") or []:
        if chapter.get("id") == chapter_id:
            return chapter
    raise ValueError(f"unknown chapter: {chapter_id}")


def _chapter_id(operation: dict[str, Any]) -> Any:
    return operation.get("chapterId", operation.get("id"))


def _next_chapter_id(model: dict[str, Any]) -> str:
    used = {chapter.get("id") for chapter in model.get("chapters") or []}
    number = 1
    while f"GCH-{number:03d}" in used:
        number += 1
    return f"GCH-{number:03d}"


def _next_directory_entry_id(directory: dict[str, Any]) -> str:
    used = {item.get("id") for item in directory.get("entries") or [] if isinstance(item, dict)}
    number = 1
    while f"GDE-{number:03d}" in used:
        number += 1
    return f"GDE-{number:03d}"


def _touch_directory(directory: dict[str, Any]) -> None:
    directory["status"] = "draft"
    directory["confirmedAtRevision"] = None
    directory["revision"] = int(directory.get("revision") or 0) + 1
    for index, entry in enumerate(directory.get("entries") or [], 1):
        entry["order"] = index


def _new_chapter(model: dict[str, Any], payload: Any, base: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("chapter must be an object")
    source = deepcopy(base) if base else {}
    source.update(deepcopy(payload))
    return {
        "id": _next_chapter_id(model),
        "scope": source.get("scope") or "pending",
        "claims": deepcopy(source.get("claims") or []),
        "mechanism": deepcopy(source.get("mechanism") or {"type": "core_loop"}),
        "parameters": deepcopy(source.get("parameters") or {}),
        "dependencies": deepcopy(source.get("dependencies") or []),
        "acceptanceCases": deepcopy(source.get("acceptanceCases") or []),
        "unknowns": deepcopy(source.get("unknowns") or []),
        "decisionCards": deepcopy(source.get("decisionCards") or []),
        "sourceFrameIds": deepcopy(source.get("sourceFrameIds") or []),
        "status": "chapter_review",
        "confirmation": {"confirmed": False, "revision": None},
    }


def _item_id(items: list[Any], prefix: str) -> str:
    used = {item.get("id") for item in items if isinstance(item, dict)}
    number = 1
    while f"{prefix}-{number:03d}" in used:
        number += 1
    return f"{prefix}-{number:03d}"


def _upsert_item(items: list[Any], payload: Any, prefix: str, all_items: list[Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("item must be an object")
    item = deepcopy(payload)
    item_id = item.get("id") or _item_id(all_items, prefix)
    if not isinstance(item_id, str) or not re.fullmatch(rf"{prefix}-\d{{3}}", item_id):
        raise ValueError(f"item id must be a {prefix}-### id")
    item["id"] = item_id
    for index, current in enumerate(items):
        if isinstance(current, dict) and current.get("id") == item_id:
            items[index] = item
            return
    items.append(item)


def _delete_item(items: list[Any], item_id: Any, label: str) -> None:
    if not isinstance(item_id, str) or not item_id:
        raise ValueError(f"{label} id is required")
    for item in list(items):
        if isinstance(item, dict) and item.get("id") == item_id:
            items.remove(item)
            return
    raise ValueError(f"unknown {label}: {item_id}")


def _mark_changed(model: dict[str, Any], chapter_ids: set[str]) -> None:
    for chapter_id in chapter_ids:
        try:
            chapter = _chapter(model, chapter_id)
        except ValueError:
            continue
        chapter["status"] = "chapter_review"
        chapter["confirmation"] = {"confirmed": False, "revision": None}
    for diagram in model.get("diagrams") or []:
        if isinstance(diagram, dict) and chapter_ids.intersection(diagram.get("chapterIds") or []):
            _mark_diagram_stale(diagram)
    for table in model.get("tables") or []:
        if isinstance(table, dict) and chapter_ids.intersection(table.get("chapterIds") or []) and table.get("status") != "deleted":
            table["status"] = "stale"
    model.setdefault("reviewState", {})["previewRevision"] = None


def _mark_diagram_stale(diagram: dict[str, Any]) -> None:
    if diagram.get("status") != "deleted" or not diagram.get("optional", True):
        diagram["status"] = "stale"


def _apply_operation(model: dict[str, Any], operation: dict[str, Any]) -> set[str]:
    operation_type = operation.get("type")
    if not isinstance(operation_type, str):
        raise ValueError("operation type is required")
    if operation_type == "register_planner_feedback":
        approved = model.get("approvedData")
        if model.get("contentModelVersion") != 2 or not isinstance(approved, dict):
            raise ValueError("planner feedback requires content model v2")
        feedback = deepcopy(operation.get("feedback"))
        if not isinstance(feedback, dict) or not feedback.get("feedbackId"):
            raise ValueError("planner feedback requires feedbackId")
        if feedback.get("scope") not in {"project_feedback", "system_feedback"}:
            raise ValueError("planner feedback scope is invalid")
        records = approved.setdefault("plannerFeedback", [])
        if any(item.get("feedbackId") == feedback["feedbackId"] for item in records if isinstance(item, dict)):
            raise ValueError("planner feedback id already exists")
        feedback.setdefault("sourceRevision", approved.get("approvalRevision"))
        feedback["reviewStatus"] = "unreviewed"
        for requested in feedback.get("requestedOperations") or []:
            if isinstance(requested, dict):
                requested["status"] = "proposed"
        records.append(feedback)
        return set()
    if operation_type == "review_planner_feedback_operation":
        approved = model.get("approvedData")
        if model.get("contentModelVersion") != 2 or not isinstance(approved, dict):
            raise ValueError("planner feedback requires content model v2")
        feedback = next((item for item in approved.get("plannerFeedback") or [] if item.get("feedbackId") == operation.get("feedbackId")), None)
        if feedback is None:
            raise ValueError("unknown planner feedback")
        requested = next((item for item in feedback.get("requestedOperations") or [] if item.get("operationId") == operation.get("operationId")), None)
        if requested is None:
            raise ValueError("unknown planner feedback operation")
        decision = operation.get("decision")
        if decision not in {"approved", "rejected"}:
            raise ValueError("planner feedback operation decision is invalid")
        requested["status"] = decision
        statuses = {item.get("status") for item in feedback.get("requestedOperations") or [] if isinstance(item, dict)}
        feedback["reviewStatus"] = "approved" if "approved" in statuses else ("rejected" if statuses == {"rejected"} else "unreviewed")
        feedback["reviewedAtRevision"] = int(model.get("revision") or 0) + 1
        return set()
    if operation_type == "review_rule":
        approved = model.get("approvedData")
        if model.get("contentModelVersion") != 2 or not isinstance(approved, dict):
            raise ValueError("review_rule requires content model v2")
        rule_id = operation.get("ruleId")
        rule = next((item for item in approved.get("rules") or [] if isinstance(item, dict) and item.get("ruleId") == rule_id), None)
        promoted_temporal_candidate = rule is None
        if promoted_temporal_candidate:
            projected = (model.get("ruleIntelligenceProjection") or {}).get("ruleCandidates") or []
            source_candidate = next((item for item in projected if isinstance(item, dict) and item.get("ruleId") == rule_id), None)
            rule = deepcopy(source_candidate) if source_candidate is not None else None
        if rule is None:
            raise ValueError(f"unknown rule: {rule_id}")
        patch = operation.get("patch") or {}
        if not isinstance(patch, dict):
            raise ValueError("rule patch must be an object")
        immutable = {key: deepcopy(rule.get(key)) for key in ("semanticKey", "ownerChapterId", "evidenceIds")}
        candidate = {**rule, **deepcopy(patch)}
        if candidate.get("ruleType") not in _RULE_TYPES:
            raise ValueError("unknown ruleType")
        if not isinstance(candidate.get("behavior"), str) or not candidate["behavior"].strip():
            raise ValueError("rule behavior is required")
        valid_slots = {
            item.get("slotId") for item in approved.get("slots") or []
            if isinstance(item, dict) and item.get("chapterId") == candidate.get("ownerChapterId")
        }
        if candidate.get("schemaSlot") not in valid_slots:
            raise ValueError("unknown schemaSlot for owner chapter")
        owner = next((item for item in approved.get("chapters") or [] if isinstance(item, dict) and item.get("chapterId") == candidate.get("ownerChapterId")), {})
        schema_key = str(owner.get("matchedSchema") or "")
        parts = schema_key.split(":", 2)
        if len(parts) == 3:
            schema = chapter_schema_library.resolve(parts[1], None if parts[2] == "base" else parts[2], parts[0])
            slot = next((item for item in schema.slots if item.slot_id == candidate.get("schemaSlot")), None)
            if slot and candidate.get("ruleType") not in slot.allowed_rule_types:
                raise ValueError("ruleType is not allowed by schemaSlot")
        decision = operation.get("decision")
        if decision not in _RULE_DECISIONS:
            raise ValueError("invalid rule review decision")
        if decision == "approved" and (candidate.get("semanticValidity", "valid") != "valid" or candidate.get("validationErrors")):
            raise ValueError("rule semantic validity gate rejected approval")
        previous_status = rule.get("reviewStatus")
        rule.update(candidate)
        rule.update(immutable)
        rule["reviewStatus"] = decision
        if promoted_temporal_candidate:
            if decision != "approved":
                raise ValueError("temporal candidate must be approved to enter authoritative rules")
            rule.pop("guardReasons", None)
            rule.pop("confirmationStatus", None)
            rule.pop("publicationEligibility", None)
            approved.setdefault("rules", []).append(rule)
            source_fact_id_list = list(dict.fromkeys(str(item) for item in rule.get("sourceFactIds") or []))
            source_fact_ids = set(source_fact_id_list)
            temporal_facts = (model.get("temporalEvidence") or {}).get("facts") or []
            approved_facts = approved.setdefault("facts", [])
            existing_fact_ids = {str(item.get("factId")) for item in approved_facts if isinstance(item, dict)}
            for temporal_fact in temporal_facts:
                if str(temporal_fact.get("factId")) not in source_fact_ids or str(temporal_fact.get("factId")) in existing_fact_ids:
                    continue
                promoted_fact = deepcopy(temporal_fact)
                promoted_fact["reviewStatus"] = "approved"
                promoted_fact["approvalSourceRuleId"] = rule_id
                approved_facts.append(promoted_fact)
                existing_fact_ids.add(str(promoted_fact.get("factId")))
            slot_state = next((
                item for item in approved.get("slots") or []
                if item.get("chapterId") == rule.get("ownerChapterId") and item.get("slotId") == rule.get("schemaSlot")
            ), None)
            if slot_state is not None:
                slot_state["factIds"] = list(dict.fromkeys([*(slot_state.get("factIds") or []), *source_fact_id_list]))
                slot_state["status"] = "confirmed"
        approved.setdefault("reviewHistory", []).append({
            "ruleId": rule_id, "revision": int(model.get("revision") or 0) + 1,
            "previousStatus": previous_status, "decision": decision,
            "behavior": rule["behavior"], "evidenceIds": deepcopy(rule["evidenceIds"]),
        })
        approved["approvalRevision"] = int(approved.get("approvalRevision") or 0) + 1
        return set()
    if operation_type == "update_gameplay_understanding":
        value = operation.get("understanding")
        if not isinstance(value, dict): raise ValueError("understanding must be an object")
        summary = str(value.get("summary") or "").strip()
        if len([item for item in re.split(r"[。！？!?]+", summary) if item.strip()]) > 4: raise ValueError("gameplay summary must contain no more than four sentences")
        directory = ensure_directory(model); directory["understanding"] = deepcopy(value); directory["understandingSource"] = "planner"; directory["status"] = "draft"; directory["confirmedAtRevision"] = None; directory["revision"] = int(directory.get("revision") or 0) + 1
        return set()
    if operation_type == "rename_directory_entry":
        directory = ensure_directory(model); entry_id, title = operation.get("entryId"), str(operation.get("title") or "").strip()
        if not title: raise ValueError("directory title is required")
        entry = next((item for item in directory["entries"] if item.get("id") == entry_id), None)
        if not entry: raise ValueError("unknown directory entry")
        entry["title"] = title; _chapter(model, entry["chapterId"])["scope"] = title
        directory["status"] = "draft"; directory["confirmedAtRevision"] = None; directory["revision"] = int(directory.get("revision") or 0) + 1
        return set()
    if operation_type == "update_directory_entry_summary":
        directory = ensure_directory(model); entry_id = operation.get("entryId"); summary = str(operation.get("summary") or "").strip()
        if not summary: raise ValueError("directory summary is required")
        entry = next((item for item in directory["entries"] if item.get("id") == entry_id), None)
        if not entry: raise ValueError("unknown directory entry")
        entry["summary"] = summary; entry["summarySource"] = "planner"
        directory["status"] = "draft"; directory["confirmedAtRevision"] = None; directory["revision"] = int(directory.get("revision") or 0) + 1
        return {entry["chapterId"]}
    if operation_type == "reorder_directory_entries":
        directory = ensure_directory(model); order = operation.get("entryIds")
        entries = directory.get("entries") or []
        if not isinstance(order, list) or len(order) != len(entries) or set(order) != {item.get("id") for item in entries}: raise ValueError("entryIds must contain every directory entry exactly once")
        by_id = {item["id"]: item for item in entries}; directory["entries"] = [by_id[item] for item in order]
        for index, item in enumerate(directory["entries"], 1): item["order"] = index
        directory["status"] = "draft"; directory["confirmedAtRevision"] = None; directory["revision"] = int(directory.get("revision") or 0) + 1
        return set()
    if operation_type == "move_directory_entry_to_system":
        directory = ensure_directory(model); entry_id = operation.get("entryId"); system_name = str(operation.get("systemName") or "").strip()
        entry = next((item for item in directory["entries"] if item.get("id") == entry_id), None)
        valid_names = {str(item.get("name") or "").strip() for item in model.get("systems") or []}
        if not entry: raise ValueError("unknown directory entry")
        if not system_name or system_name not in valid_names: raise ValueError("unknown gameplay system")
        entry["sectionTitle"] = system_name
        directory["status"] = "draft"; directory["confirmedAtRevision"] = None; directory["revision"] = int(directory.get("revision") or 0) + 1
        return {entry["chapterId"]}
    if operation_type == "add_gameplay_system":
        name = str(operation.get("name") or "").strip()
        if not name: raise ValueError("gameplay system name is required")
        systems = model.setdefault("systems", [])
        if any(str(item.get("name") or "").strip() == name for item in systems): raise ValueError("gameplay system name already exists")
        used = {str(item.get("id") or "") for item in systems}
        index = 1
        while f"GSY-{index:03d}" in used: index += 1
        systems.append({"id": f"GSY-{index:03d}", "name": name, "subsystems": []})
        directory = ensure_directory(model); directory["status"] = "draft"; directory["confirmedAtRevision"] = None; directory["revision"] = int(directory.get("revision") or 0) + 1
        return set()
    if operation_type == "add_directory_entry":
        directory = ensure_directory(model); title = str(operation.get("title") or "待命名玩法").strip()
        chapter = _new_chapter(model, {"scope": title, "mechanism": {"type": operation.get("mechanismType") or "core_loop"}})
        model.setdefault("chapters", []).append(chapter)
        directory.setdefault("entries", []).append({"id": _next_directory_entry_id(directory), "chapterId": chapter["id"], "title": title, "summary": "请填写这一部分要说明的玩法", "claimIds": [], "order": len(directory.get("entries") or []) + 1})
        _touch_directory(directory); return {chapter["id"]}
    if operation_type == "delete_directory_entry":
        directory = ensure_directory(model); entry = next((item for item in directory.get("entries") or [] if item.get("id") == operation.get("entryId")), None)
        if not entry: raise ValueError("unknown directory entry")
        if entry.get("claimIds"): raise ValueError("move or merge this chapter content before deleting it")
        directory["entries"].remove(entry); model["chapters"] = [item for item in model.get("chapters") or [] if item.get("id") != entry.get("chapterId")]
        _touch_directory(directory); return set()
    if operation_type == "merge_directory_entries":
        directory = ensure_directory(model); source_id, target_id = operation.get("sourceEntryId"), operation.get("targetEntryId")
        source = next((item for item in directory.get("entries") or [] if item.get("id") == source_id), None); target = next((item for item in directory.get("entries") or [] if item.get("id") == target_id), None)
        if not source or not target or source is target: raise ValueError("two different directory entries are required")
        source_chapter, target_chapter = _chapter(model, source["chapterId"]), _chapter(model, target["chapterId"])
        target_chapter["claims"].extend(source_chapter.get("claims") or []); target["claimIds"] = [*target.get("claimIds", []), *source.get("claimIds", [])]
        for name, parameter in (source_chapter.get("parameters") or {}).items(): target_chapter.setdefault("parameters", {}).setdefault(name, parameter)
        for field in ("dependencies", "acceptanceCases", "unknowns", "sourceFrameIds"):
            target_chapter[field] = list(dict.fromkeys([*(target_chapter.get(field) or []), *(source_chapter.get(field) or [])])) if field in {"dependencies", "sourceFrameIds"} else [*(target_chapter.get(field) or []), *(source_chapter.get(field) or [])]
        target_chapter["dependencies"] = [item for item in target_chapter["dependencies"] if item not in {source_chapter["id"], target_chapter["id"]}]
        for chapter in model.get("chapters") or []:
            chapter["dependencies"] = [target_chapter["id"] if item == source_chapter["id"] else item for item in chapter.get("dependencies") or []]
        for diagram in model.get("diagrams") or []:
            diagram["chapterIds"] = list(dict.fromkeys(target_chapter["id"] if item == source_chapter["id"] else item for item in diagram.get("chapterIds") or []))
        target["summary"] = "；".join(filter(None, [target.get("summary"), source.get("summary")]))
        directory["entries"].remove(source); model["chapters"].remove(source_chapter); _touch_directory(directory); return {target_chapter["id"]}
    if operation_type == "split_directory_entry":
        directory = ensure_directory(model); source = next((item for item in directory.get("entries") or [] if item.get("id") == operation.get("entryId")), None)
        claim_ids = list(dict.fromkeys(operation.get("claimIds") or [])); title = str(operation.get("title") or "拆分后的玩法").strip()
        if not source or not claim_ids or any(item not in (source.get("claimIds") or []) for item in claim_ids): raise ValueError("valid source entry and claimIds are required")
        source_chapter = _chapter(model, source["chapterId"]); selected = [item for item in source_chapter.get("claims") or [] if item.get("id") in claim_ids]
        new_chapter = _new_chapter(model, {**source_chapter, "scope": title, "claims": selected})
        source_chapter["claims"] = [item for item in source_chapter.get("claims") or [] if item.get("id") not in claim_ids]; source["claimIds"] = [item for item in source.get("claimIds") or [] if item not in claim_ids]
        model["chapters"].append(new_chapter); directory["entries"].insert(directory["entries"].index(source) + 1, {"id": _next_directory_entry_id(directory), "chapterId": new_chapter["id"], "title": title, "summary": "；".join(str(item.get("text") or "") for item in selected[:2]), "claimIds": claim_ids, "order": 0})
        _touch_directory(directory); return {source_chapter["id"], new_chapter["id"]}
    if operation_type == "move_claim_between_entries":
        directory = ensure_directory(model); claim_id = operation.get("claimId")
        source = next((item for item in directory["entries"] if claim_id in (item.get("claimIds") or [])), None)
        target = next((item for item in directory["entries"] if item.get("id") == operation.get("targetEntryId")), None)
        if not source or not target or source is target: raise ValueError("valid source claim and target entry are required")
        source["claimIds"].remove(claim_id); target.setdefault("claimIds", []).append(claim_id)
        claim = next((item for item in _chapter(model, source["chapterId"])["claims"] if item.get("id") == claim_id), None)
        if claim: _chapter(model, source["chapterId"])["claims"].remove(claim); _chapter(model, target["chapterId"])["claims"].append(claim)
        directory["status"] = "draft"; directory["confirmedAtRevision"] = None; directory["revision"] = int(directory.get("revision") or 0) + 1
        return {source["chapterId"], target["chapterId"]}
    if operation_type == "set_chapter_field":
        chapter = _chapter(model, _chapter_id(operation)); field = operation.get("field")
        if field not in _CHAPTER_FIELDS:
            raise ValueError("chapter field is not editable")
        if field == "decisionCards":
            published = {str(card.get("publishedText") or "").strip() for card in chapter.get("decisionCards") or [] if isinstance(card, dict)} - {""}
            resolved = {str(card.get("resolvedText") or "").strip() for card in chapter.get("decisionCards") or [] if isinstance(card, dict)} - {""}
            planner_sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
            if published and isinstance(planner_sections.get("keyRules"), list):
                planner_sections["keyRules"] = [item for item in planner_sections["keyRules"] if str(item).strip() not in published]
            if resolved:
                chapter["claims"] = [claim for claim in chapter.get("claims") or [] if not (isinstance(claim, dict) and claim.get("sourceType") == "planner" and str(claim.get("text") or "").strip() in resolved)]
        chapter[field] = deepcopy(operation.get("value")); return {chapter["id"]}
    if operation_type in {"resolve_decision_card", "skip_decision_card"}:
        chapter = _chapter(model, _chapter_id(operation))
        requested_card_id = operation.get("cardId")
        card = next((
            item for item in chapter.get("decisionCards") or []
            if item.get("id") == requested_card_id or requested_card_id in (item.get("legacyIds") or [])
        ), None)
        if not card:
            raise ValueError("unknown decision card")
        if operation_type == "skip_decision_card":
            card["status"] = "skipped"
            return {chapter["id"]}
        option_ids = operation.get("selectedOptionIds") or []
        custom_value = str(operation.get("customValue") or "").strip()
        if not isinstance(option_ids, list) or any(not isinstance(item, str) for item in option_ids):
            raise ValueError("selectedOptionIds must be a list of strings")
        if card.get("selectionMode", "single") == "single" and len(option_ids) + bool(custom_value) != 1:
            raise ValueError("single decision card requires exactly one choice")
        if card.get("selectionMode") == "multiple" and not option_ids and not custom_value:
            raise ValueError("multiple decision card requires at least one choice")
        options = {item.get("id"): item for item in card.get("options") or [] if isinstance(item, dict)}
        if any(item not in options for item in option_ids):
            raise ValueError("unknown decision option")
        if custom_value and not card.get("allowCustom", True):
            raise ValueError("custom choice is not allowed")
        selected = [str(options[item].get("label") or "").strip() for item in option_ids]
        resolved_text = "；".join(item for item in [*selected, custom_value] if item)
        if not resolved_text:
            raise ValueError("decision result is empty")
        card.update({"status": "resolved", "selectedOptionIds": option_ids, "customValue": custom_value, "resolvedText": resolved_text})
        question = str(card.get("question") or "").strip()
        chapter["unknowns"] = [item for item in chapter.get("unknowns") or [] if str(item).strip() != question]
        target = card.get("target") if isinstance(card.get("target"), dict) else {}
        if target.get("type") == "field_dictionary":
            planner_name = str(target.get("plannerName") or "").strip()
            mappings = chapter.setdefault("fieldDictionary", [])
            mapping = next((item for item in mappings if isinstance(item, dict) and str(item.get("plannerName") or "").strip() == planner_name), None)
            if mapping is None:
                mapping = {"plannerName": planner_name}
                mappings.append(mapping)
            mapping.update({
                "suggestedCodeName": resolved_text,
                "status": "confirmed",
                "decisionStatus": "accepted",
                "decisionCardId": card.get("id"),
            })
            return {chapter["id"]}
        all_claims = [claim for item in model.get("chapters") or [] for claim in item.get("claims") or []]
        _upsert_item(chapter["claims"], {"text": resolved_text, "sourceType": "planner", "sourceFrameIds": []}, "GCL", all_claims)
        decision_rule = f"{question.rstrip('？?')}：{resolved_text}" if question else resolved_text
        planner_sections = chapter.setdefault("plannerSections", {})
        key_rules = planner_sections.get("keyRules")
        if not isinstance(key_rules, list):
            key_rules = [str(key_rules).strip()] if str(key_rules or "").strip() else []
        prior_rule = str(card.get("publishedText") or "").strip()
        if prior_rule:
            key_rules = [item for item in key_rules if str(item).strip() != prior_rule]
        if decision_rule not in key_rules:
            key_rules.append(decision_rule)
        planner_sections["keyRules"] = key_rules
        card["publishedText"] = decision_rule
        return {chapter["id"]}
    if operation_type == "move_chapter":
        chapter = _chapter(model, _chapter_id(operation))
        system_id, subsystem_id = operation.get("systemId"), operation.get("subsystemId")
        system = next((item for item in model.get("systems") or [] if item.get("id") == system_id), None)
        subsystem = next((item for item in (system or {}).get("subsystems") or [] if item.get("id") == subsystem_id), None)
        if not system or not subsystem:
            raise ValueError("unknown gameplay system or subsystem")
        chapter["systemName"], chapter["subsystemName"] = system["name"], subsystem["name"]
        rebuilt = normalize_gameplay_structure(model)
        model["systems"] = rebuilt["systems"]
        by_id = {item["id"]: item for item in rebuilt["chapters"]}
        for item in model.get("chapters") or []:
            item["systemId"] = by_id[item["id"]]["systemId"]
            item["subsystemId"] = by_id[item["id"]]["subsystemId"]
        return {chapter["id"]}
    if operation_type == "set_mechanism_field":
        chapter = _chapter(model, _chapter_id(operation)); field = operation.get("field")
        if not isinstance(field, str) or field == "id":
            raise ValueError("mechanism field is not editable")
        chapter["mechanism"][field] = deepcopy(operation.get("value")); return {chapter["id"]}
    if operation_type in {"upsert_claim", "delete_claim", "upsert_parameter", "delete_parameter", "upsert_dependency", "delete_dependency", "upsert_acceptance", "delete_acceptance"}:
        chapter = _chapter(model, _chapter_id(operation))
        if operation_type == "upsert_claim": _upsert_item(chapter["claims"], operation.get("claim"), "GCL", [claim for chapter_item in model["chapters"] for claim in chapter_item["claims"]])
        elif operation_type == "delete_claim": _delete_item(chapter["claims"], operation.get("claimId", operation.get("id")), "claim")
        elif operation_type == "upsert_parameter":
            name, parameter = operation.get("name", operation.get("parameterName")), operation.get("parameter")
            if not isinstance(name, str) or not name or not isinstance(parameter, dict): raise ValueError("parameter name and object are required")
            chapter["parameters"][name] = deepcopy(parameter)
        elif operation_type == "delete_parameter":
            name = operation.get("name", operation.get("parameterName"))
            if not isinstance(name, str) or name not in chapter["parameters"]: raise ValueError("unknown parameter")
            chapter["parameters"].pop(name)
        elif operation_type == "upsert_dependency":
            dependency_id = operation.get("dependencyId", operation.get("dependency")); _chapter(model, dependency_id)
            if dependency_id == chapter["id"]: raise ValueError("chapter cannot depend on itself")
            if dependency_id not in chapter["dependencies"]: chapter["dependencies"].append(dependency_id)
        elif operation_type == "delete_dependency":
            dependency_id = operation.get("dependencyId", operation.get("dependency"))
            if dependency_id not in chapter["dependencies"]: raise ValueError("unknown dependency")
            chapter["dependencies"].remove(dependency_id)
        elif operation_type == "upsert_acceptance":
            acceptance, legacy_index = operation.get("acceptance"), operation.get("acceptanceIndex")
            if isinstance(legacy_index, int) and 0 <= legacy_index < len(chapter["acceptanceCases"]) and not chapter["acceptanceCases"][legacy_index].get("id"):
                if not isinstance(acceptance, dict): raise ValueError("item must be an object")
                all_acceptances = [item for chapter_item in model["chapters"] for item in chapter_item["acceptanceCases"]]
                replacement = deepcopy(acceptance); replacement["id"] = _item_id(all_acceptances, "GAC")
                chapter["acceptanceCases"][legacy_index] = replacement
            else:
                _upsert_item(chapter["acceptanceCases"], acceptance, "GAC", [acceptance for chapter_item in model["chapters"] for acceptance in chapter_item["acceptanceCases"]])
        else:
            acceptance_id, legacy_index = operation.get("acceptanceId", operation.get("id")), operation.get("acceptanceIndex")
            if not acceptance_id and isinstance(legacy_index, int) and 0 <= legacy_index < len(chapter["acceptanceCases"]): chapter["acceptanceCases"].pop(legacy_index)
            else: _delete_item(chapter["acceptanceCases"], acceptance_id, "acceptance")
        return {chapter["id"]}
    if operation_type == "add_chapter":
        chapter = _new_chapter(model, operation.get("chapter")); model["chapters"].append(chapter); return {chapter["id"]}
    if operation_type == "delete_chapter":
        chapter = _chapter(model, _chapter_id(operation)); chapter_id = chapter["id"]
        model["chapters"].remove(chapter); affected = {chapter_id}
        for other in model["chapters"]:
            if chapter_id in other.get("dependencies", []): other["dependencies"].remove(chapter_id); affected.add(other["id"])
        for diagram in model.get("diagrams") or []:
            if chapter_id in diagram.get("chapterIds", []): diagram["chapterIds"] = [item for item in diagram["chapterIds"] if item != chapter_id]; _mark_diagram_stale(diagram)
        return affected - {chapter_id}
    if operation_type == "merge_chapters":
        keep = _chapter(model, operation.get("keepId")); merged = _chapter(model, operation.get("mergeId"))
        if keep is merged: raise ValueError("chapters must differ")
        keep["claims"] += [item for item in deepcopy(merged["claims"]) if item not in keep["claims"]]
        keep["acceptanceCases"] += [item for item in deepcopy(merged["acceptanceCases"]) if item not in keep["acceptanceCases"]]
        keep["unknowns"] += [item for item in deepcopy(merged["unknowns"]) if item not in keep["unknowns"]]
        keep["sourceFrameIds"] = list(dict.fromkeys(keep["sourceFrameIds"] + merged["sourceFrameIds"]))
        keep["parameters"] = {**deepcopy(merged["parameters"]), **keep["parameters"]}
        keep["dependencies"] = list(dict.fromkeys(item for item in keep["dependencies"] + merged["dependencies"] if item not in {keep["id"], merged["id"]}))
        merged_id = merged["id"]; model["chapters"].remove(merged)
        affected = {keep["id"]}
        for chapter in model["chapters"]:
            before_dependencies = chapter["dependencies"]
            chapter["dependencies"] = list(dict.fromkeys(keep["id"] if item == merged_id else item for item in chapter["dependencies"] if item != chapter["id"]))
            if chapter["dependencies"] != before_dependencies:
                affected.add(chapter["id"])
        for diagram in model.get("diagrams") or []:
            if merged_id in diagram.get("chapterIds", []): diagram["chapterIds"] = list(dict.fromkeys(keep["id"] if item == merged_id else item for item in diagram["chapterIds"])); _mark_diagram_stale(diagram)
        return affected
    if operation_type == "split_chapter":
        chapter = _chapter(model, _chapter_id(operation)); split = _new_chapter(model, operation.get("chapter"), chapter); model["chapters"].insert(model["chapters"].index(chapter) + 1, split); return {chapter["id"], split["id"]}
    if operation_type == "reorder_chapters":
        order = operation.get("chapterIds")
        if not isinstance(order, list) or set(order) != {chapter.get("id") for chapter in model.get("chapters") or []} or len(order) != len(model["chapters"]): raise ValueError("chapterIds must contain every chapter exactly once")
        by_id = {chapter["id"]: chapter for chapter in model["chapters"]}; model["chapters"] = [by_id[chapter_id] for chapter_id in order]; return set(order)
    if operation_type == "set_finding_resolution":
        finding_id, resolution = operation.get("findingId", operation.get("id")), operation.get("resolution", operation.get("status"))
        if not isinstance(finding_id, str) or not isinstance(resolution, str) or not resolution: raise ValueError("finding id and resolution are required")
        for finding in model.setdefault("reviewState", {}).setdefault("findings", []):
            if isinstance(finding, dict) and finding.get("id") == finding_id: finding["status"] = resolution; return set()
        raise ValueError(f"unknown finding: {finding_id}")
    raise ValueError(f"unsupported gameplay operation: {operation_type}")


def _validate(model: dict[str, Any]) -> None:
    if errors := validate_gameplay_review_model(model):
        raise ValueError("; ".join(errors))


def _normalize_historical_chapters_for_edit(model: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Upgrade persisted pre-schema chapters before an interactive mutation.

    Historical jobs can contain presentation-complete chapters that predate the
    strict editor fields or use descriptive decision-card ids.  The browser must
    not expose an enabled save/continue button that can only return HTTP 400.
    Preserve authored content while filling editor-only containers and assigning
    deterministic schema ids to legacy cards.
    """
    decision_id_aliases: dict[tuple[str, str], str] = {}
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter.setdefault("claims", [])
        chapter.setdefault("mechanism", {"type": "custom"})
        chapter.setdefault("parameters", {})
        chapter.setdefault("dependencies", [])
        chapter.setdefault("acceptanceCases", [])
        chapter.setdefault("unknowns", [])
        chapter.setdefault("decisionCards", [])
        chapter.setdefault("sourceFrameIds", [])
        chapter.setdefault("status", "chapter_review")
        chapter.setdefault("confirmation", {"confirmed": False, "revision": None})
        cards = chapter.get("decisionCards")
        if not isinstance(cards, list):
            chapter["decisionCards"] = []
            continue
        used: set[str] = set()
        next_number = 1
        for card in cards:
            if not isinstance(card, dict):
                continue
            card_id = card.get("id")
            if isinstance(card_id, str) and re.fullmatch(r"GDC-\d{3}", card_id) and card_id not in used:
                used.add(card_id)
                continue
            while f"GDC-{next_number:03d}" in used:
                next_number += 1
            next_id = f"GDC-{next_number:03d}"
            if isinstance(card_id, str) and card_id:
                decision_id_aliases[(str(chapter.get("id") or ""), card_id)] = next_id
                card["legacyIds"] = list(dict.fromkeys([*(card.get("legacyIds") or []), card_id]))
            card["id"] = next_id
            used.add(card["id"])
            next_number += 1
    return decision_id_aliases


def apply_gameplay_operations(model: dict[str, Any], operations: Any, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    if not isinstance(operations, list) or any(not isinstance(operation, dict) for operation in operations):
        raise ValueError("operations must be a list of objects")
    result = deepcopy(model)
    # Models created before decision cards existed omit the field entirely.
    # Normalize them before applying the first new operation so a historical
    # task can be edited and validated without a destructive regeneration.
    for chapter in result.get("chapters") or []:
        if isinstance(chapter, dict):
            chapter.setdefault("decisionCards", [])
    result.setdefault("temporalProbeRequests", [])
    result.setdefault("temporalEvidence", {"facts": [], "observations": [], "ruleCandidates": [], "gaps": []})
    decision_id_aliases = _normalize_historical_chapters_for_edit(result)
    before = _snapshot(result)
    changed_chapters: set[str] = set()
    for original_operation in operations:
        operation = deepcopy(original_operation)
        if operation.get("type") in {"resolve_decision_card", "skip_decision_card"}:
            alias = decision_id_aliases.get((str(operation.get("chapterId") or ""), str(operation.get("cardId") or "")))
            if alias:
                operation["cardId"] = alias
        operation_before = deepcopy(result)
        affected = _apply_operation(result, operation)
        if result != operation_before:
            changed_chapters.update(affected)
    _validate(result)
    if _snapshot(result) == before:
        return deepcopy(model)
    _mark_changed(result, changed_chapters)
    if result.get("contentModelVersion") == 2 and isinstance(result.get("approvedData"), dict):
        from .rule_normalizer import build_rule_intelligence_v1
        result["ruleIntelligenceProjection"] = build_rule_intelligence_v1(result, result["approvedData"])
    history = _history(result); _remember(history, "undo", before); history["redo"] = []
    result["revision"] = model["revision"] + 1
    _validate(result)
    return result


def confirm_gameplay_directory(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result, before = deepcopy(model), _snapshot(model)
    _normalize_historical_chapters_for_edit(result)
    directory = ensure_directory(result)
    errors = directory_errors(result)
    if errors: raise ValueError("cannot confirm directory: " + "; ".join(errors))
    result["revision"] = model["revision"] + 1
    review_state = result.setdefault("reviewState", {})
    structure_phase = review_state.get("structurePhase")
    if structure_phase == "systems":
        # The first decision only locks the broad gameplay-system split.  Keep
        # the directory editable while the planner checks its mechanisms.
        directory["status"] = "draft"
        directory.pop("confirmedAtRevision", None)
        review_state["structurePhase"] = "mechanisms"
        review_state["status"] = "mechanism_directory_review"
        review_state["systemsConfirmedAtRevision"] = result["revision"]
    else:
        directory["status"] = "confirmed"
        directory["confirmedAtRevision"] = result["revision"]
        if structure_phase == "mechanisms":
            review_state["structurePhase"] = "confirmed"
            review_state["status"] = "detail_generation_pending"
            review_state["mechanismsConfirmedAtRevision"] = result["revision"]
    review_state["previewRevision"] = None
    review_state["interactionHandoffConfirmed"] = False
    history = _history(result); _remember(history, "undo", before); history["redo"] = []
    _validate(result)
    return result


def add_gameplay_context(model: dict[str, Any], chapter_id: str, context: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result, before = deepcopy(model), _snapshot(model)
    chapter = _chapter(result, chapter_id)
    windows = result.setdefault("contextWindows", [])
    used = {item.get("id") for item in windows if isinstance(item, dict)}
    number = 1
    while f"GCW-{number:03d}" in used:
        number += 1
    windows.append({"id": f"GCW-{number:03d}", **deepcopy(context)})
    _mark_changed(result, {chapter["id"]})
    history = _history(result); _remember(history, "undo", before); history["redo"] = []
    result["revision"] = model["revision"] + 1
    if result.get("contentModelVersion") == 2 and isinstance(result.get("approvedData"), dict):
        from .rule_normalizer import build_rule_intelligence_v1
        result["ruleIntelligenceProjection"] = build_rule_intelligence_v1(result, result["approvedData"])
    _validate(result)
    return result


def add_targeted_temporal_probe_result(
    model: dict[str, Any], probe_result: dict[str, Any], expected_revision: int,
    *, rebuild_projection: bool = True,
) -> dict[str, Any]:
    """Persist a probe as undoable review evidence without approving its facts or candidates."""
    _require_revision(model, expected_revision)
    request = probe_result.get("request")
    if not isinstance(request, dict) or request.get("status") not in {"completed", "exhausted"}:
        raise ValueError("completed or exhausted probe request is required")
    result, before = deepcopy(model), _snapshot(model)
    requests = result.setdefault("temporalProbeRequests", [])
    requests[:] = [item for item in requests if item.get("probeRequestId") != request.get("probeRequestId")]
    requests.append(deepcopy(request))
    evidence = result.setdefault("temporalEvidence", {"facts": [], "observations": [], "ruleCandidates": [], "gaps": []})
    for key in ("facts", "observations", "ruleCandidates", "gaps"):
        incoming_key = "temporalFacts" if key == "facts" else key
        existing = evidence.setdefault(key, [])
        incoming = probe_result.get(incoming_key) or []
        id_key = {"facts": "factId", "observations": "observationId", "ruleCandidates": "ruleId", "gaps": "gapId"}[key]
        incoming_ids = {item.get(id_key) for item in incoming if isinstance(item, dict)}
        existing[:] = [item for item in existing if item.get(id_key) not in incoming_ids]
        existing.extend(deepcopy(incoming))
    result["revision"] = int(model.get("revision") or 0) + 1
    history = _history(result); _remember(history, "undo", before); history["redo"] = []
    if rebuild_projection and result.get("contentModelVersion") == 2 and isinstance(result.get("approvedData"), dict):
        from .rule_normalizer import build_rule_intelligence_v1
        result["ruleIntelligenceProjection"] = build_rule_intelligence_v1(result, result["approvedData"])
    _validate(result)
    return result


def _move_history(model: dict[str, Any], expected_revision: int, source: str, target: str) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    result = deepcopy(model); history = _history(result)
    if not history[source]: raise ValueError(f"nothing to {source}")
    snapshot = history[source].pop(); _remember(history, target, _snapshot(result)); _restore(result, snapshot)
    result["revision"] = model["revision"] + 1
    _validate(result)
    return result


def undo_gameplay(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    return _move_history(model, expected_revision, "undo", "redo")


def redo_gameplay(model: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    return _move_history(model, expected_revision, "redo", "undo")


def _confirmation_blockers(model: dict[str, Any], chapter_id: str) -> list[str]:
    chapter = _chapter(model, chapter_id); blockers: list[str] = []
    mechanism = chapter.get("mechanism") or {}
    if mechanism.get("type") not in MECHANISM_SCHEMAS: blockers.append("mechanism type is required")
    for field, metadata in configured_parameter_items(chapter):
        if not isinstance(metadata, dict) or any(not metadata.get(key) or (isinstance(metadata.get(key), str) and metadata[key].strip().lower() == "unknown") for key in _METADATA_FIELDS): blockers.append(f"parameter {field} is incomplete")
    if not any(isinstance(claim, dict) and claim.get("sourceType") != "pending" and claim.get("sourceFrameIds") for claim in chapter.get("claims") or []): blockers.append("source-backed claim is required")
    if any(isinstance(finding, dict) and finding.get("severity") == "blocker" and finding.get("status") != "resolved" for finding in (model.get("reviewState") or {}).get("findings") or []): blockers.append("blocking findings remain")
    probe = deepcopy(model)
    probe_chapter = _chapter(probe, chapter_id)
    probe_chapter["status"] = "conditional"
    probe_chapter["confirmation"] = {"confirmed": True, "revision": probe["revision"], "decision": "conditional"}
    if chapter_id in gameplay_gate(probe, {"revision": probe.get("interactionRevision")})["blockers"]:
        blockers.append(f"{chapter_id}: gameplay gate is not satisfied")
    try: _validate(model)
    except ValueError as exc: blockers.append(str(exc))
    return blockers


def confirm_gameplay_chapter(model: dict[str, Any], chapter_id: str, expected_revision: int, decision: str = "approved") -> dict[str, Any]:
    _require_revision(model, expected_revision)
    if decision not in {"approved", "conditional", "rejected", "not_applicable"}: raise ValueError("confirmation decision is invalid")
    if decision not in {"rejected", "not_applicable"} and (blockers := _confirmation_blockers(model, chapter_id)): raise ValueError("cannot confirm chapter: " + "; ".join(blockers))
    result, before = deepcopy(model), _snapshot(model); chapter = _chapter(result, chapter_id)
    chapter["status"] = decision; result["revision"] = model["revision"] + 1
    chapter["confirmation"] = {"confirmed": decision != "rejected", "revision": result["revision"], **({"decision": decision} if decision != "approved" else {})}
    if result.get("contentModelVersion") == 2 and isinstance(result.get("approvedData"), dict):
        selected_ids = set(chapter.get("structuredRuleIds") or [])
        projected_rules = {rule.get("ruleId"): rule for rule in (result.get("ruleIntelligenceProjection") or {}).get("rules") or []}
        for rule in result["approvedData"].get("rules") or []:
            if rule.get("ruleId") not in selected_ids:
                continue
            rule["reviewStatus"] = "approved" if decision in {"approved", "conditional"} else "rejected"
            rule["confirmationFingerprint"] = projected_rules.get(rule.get("ruleId"), {}).get("exactSemanticFingerprint")
        from .rule_normalizer import build_rule_intelligence_v1
        result["ruleIntelligenceProjection"] = build_rule_intelligence_v1(result, result["approvedData"])
    result.setdefault("reviewState", {})["previewRevision"] = None
    history = _history(result); _remember(history, "undo", before); history["redo"] = []
    _validate(result)
    return result


def reopen_gameplay_chapter(model: dict[str, Any], chapter_id: str, expected_revision: int) -> dict[str, Any]:
    _require_revision(model, expected_revision)
    _chapter(model, chapter_id)
    result, before = deepcopy(model), _snapshot(model); _mark_changed(result, {chapter_id})
    if _snapshot(result) == before:
        return deepcopy(model)
    history = _history(result); _remember(history, "undo", before); history["redo"] = []
    result["revision"] = model["revision"] + 1
    _validate(result)
    return result
