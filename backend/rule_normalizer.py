from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import re
from typing import Any

from .atomic_fact_normalizer import normalize_claims
from .chapter_schema_library import SCHEMA_VERSION, chapter_schema_library
from .phase1_directory import build_phase1_directory
from .planning_content_models import ApprovedData, AtomicFact, Rule, SchemaSlotState
from .rule_separator import separate_atomic_fact


def _nodes(directory: dict[str, Any]):
    for system in directory.get("tree") or []:
        for obj in system.get("objects") or []:
            if obj.get("chapterType"):
                yield system, obj, obj
            for child in obj.get("chapters") or []:
                yield system, obj, child


def _slot_for_fact(schema: Any, fact: AtomicFact) -> str:
    text, kind = fact.source_text, fact.semantic_type
    slot_ids = {slot.slot_id for slot in schema.slots}
    if len(schema.slots) == 1:
        return schema.slots[0].slot_id
    if kind == "presentation":
        explicit = next((slot.slot_id for slot in schema.slots if "presentation" in slot.slot_id), None)
        if explicit: return explicit
    if schema.chapter_type == "randomization":
        if "暂停" in text and "selection_pause" in slot_ids:
            return "selection_pause"
        if "刷新" in text:
            return "refresh_cost" if kind in {"numeric", "config"} and "refresh_cost" in slot_ids else "refresh_rule"
        if "权重" in text:
            return "weight_rule"
        if kind in {"numeric", "config"} and "effect_parameter" in slot_ids:
            return "effect_parameter"
        if kind == "logic" and re.search(r"效果|范围|伤害|攻击方式", text) and "candidate_effect" in slot_ids:
            return "candidate_effect"
        if kind == "interaction" and "candidate_selection" in slot_ids:
            return "candidate_selection"
        return "random_trigger"
    if schema.chapter_type == "spawn":
        if re.search(r"从.*(?:生成|出现)|区域|点位", text): return "spawn_source"
        if re.search(r"间隔|频率|连续", text): return "spawn_interval"
        if re.search(r"停止|结束", text): return "spawn_stop_condition"
        return "spawn_trigger"
    if schema.chapter_type == "level_flow":
        if "胜利" in text: return "victory_condition"
        if "失败" in text: return "failure_condition"
        if re.search(r"阶段.*(?:切换|进入)", text): return "stage_transition"
        if re.search(r"结束|停止|进入结算", text): return "level_end_timing"
        return "level_start_condition"
    keyword_slots = (
        ("exit", ("退出", "停止", "结束")), ("trigger", ("触发", "开始", "进入", "暂停")),
        ("target", ("目标",)), ("frequency", ("频率", "冷却")),
        ("range", ("距离", "射程")), ("refresh", ("刷新", "替换")),
        ("result", ("结果", "胜负", "判定")), ("count", ("数量", "个栏位")),
    )
    for marker, words in keyword_slots:
        if any(word in text for word in words):
            match = next((slot.slot_id for slot in schema.slots if marker in slot.slot_id and kind in slot.allowed_rule_types), None)
            if match: return match
    compatible = [slot.slot_id for slot in schema.slots if kind in slot.allowed_rule_types]
    return compatible[0] if compatible else schema.slots[0].slot_id


def _semantic_errors(rule: Rule, schema: Any) -> tuple[str, ...]:
    errors = list(rule.validation_errors)
    slot = next((item for item in schema.slots if item.slot_id == rule.schema_slot), None)
    if slot is None:
        errors.append("unknown_schema_slot")
    elif rule.rule_type not in slot.allowed_rule_types:
        errors.append("rule_type_slot_mismatch")
    text = rule.behavior
    if rule.schema_slot == "weight_rule" and "权重" not in text:
        errors.append("schema_semantic_mismatch")
    if rule.schema_slot == "attack_range" and not re.search(r"射程|攻击距离", text):
        errors.append("schema_semantic_mismatch")
    if "presentation" in rule.schema_slot and rule.rule_type != "presentation":
        errors.append("schema_semantic_mismatch")
    return tuple(dict.fromkeys(errors))


def _target_chapter_type(fact: AtomicFact, current_type: str) -> str:
    text = fact.source_text
    if fact.predicate in {"移动", "行进"} or re.search(r"生成后.*移动", text):
        return "movement"
    if fact.predicate == "触发伤害" or re.search(r"接触.*(?:造成|触发).*伤害", text):
        return "attack"
    if fact.subject == "关卡" and fact.semantic_type == "flow":
        return "level_flow"
    return current_type


def build_approved_data_v2(model: dict[str, Any]) -> dict[str, Any]:
    """Build the v2 source of truth from evidence claims only; planner prose is ignored."""
    directory = build_phase1_directory(model)
    claims = {
        str(claim.get("id")): claim
        for chapter in model.get("chapters") or [] if isinstance(chapter, dict)
        for claim in chapter.get("claims") or [] if isinstance(claim, dict) and claim.get("id")
    }
    chapters, facts, rules, slots = [], [], [], []
    entries = []
    for chapter_number, (system, obj, node) in enumerate(_nodes(directory), 1):
        chapter_id = f"V2CH-{chapter_number:03d}"
        chapter_type = node.get("chapterType")
        variant = node.get("mechanicVariant")
        schema = chapter_schema_library.resolve(chapter_type, variant, SCHEMA_VERSION)
        chapter = {
            "chapterId": chapter_id, "system": system["title"], "object": obj["title"],
            "title": node["title"], "chapterType": chapter_type, "mechanicVariant": variant,
            "matchedSchema": schema.schema_key, "classificationEvidence": list(node.get("classificationEvidence") or []),
        }
        contexts = model.get("temporalProbeContexts") or []
        context = next((item for item in contexts if isinstance(item, dict) and item.get("scope") in {node["title"], obj["title"]}), None)
        if context:
            chapter["temporalProbeContext"] = dict(context)
        chapters.append(chapter)
        entries.append({"system": system, "object": obj, "node": node, "chapter": chapter, "schema": schema})
    facts_by_chapter_slot: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        system, obj, node = entry["system"], entry["object"], entry["node"]
        chapter, schema = entry["chapter"], entry["schema"]
        chapter_id, chapter_type = chapter["chapterId"], chapter["chapterType"]
        for source in node.get("sourceItems") or []:
            source_name = str(source.get("source") or "")
            if not source_name.startswith("claim:"):
                continue
            raw = claims.get(source_name.split(":", 1)[1])
            if raw is None:
                # Phase-1 also supports legacy claims without IDs; retain their text but never planner copy.
                raw = {"text": source.get("text"), "sourceFrameIds": []}
            if raw.get("sourceType") in {"planner", "pending"}:
                continue
            for fact in normalize_claims(raw, obj["title"]):
                facts.append(fact)
                target_type = _target_chapter_type(fact, chapter_type)
                target = entry
                if target_type != chapter_type:
                    candidates = [candidate for candidate in entries if candidate["system"]["title"] == system["title"] and candidate["chapter"]["chapterType"] == target_type]
                    if not candidates and target_type == "level_flow":
                        candidates = [candidate for candidate in entries if candidate["chapter"]["chapterType"] == target_type]
                    target = next((candidate for candidate in candidates if candidate["object"]["title"] == obj["title"]), None)
                    if target is None and re.search(r"胜利|失败", fact.source_text):
                        target = next((candidate for candidate in candidates if candidate["chapter"]["title"] == "胜负判定"), None)
                    if target is None and len(candidates) == 1:
                        target = candidates[0]
                    target = target or entry
                target_chapter_id, target_schema = target["chapter"]["chapterId"], target["schema"]
                slot_id = _slot_for_fact(target_schema, fact)
                if fact.evidence_level == "inferred":
                    if fact.fact_id not in facts_by_chapter_slot[target_chapter_id][slot_id]:
                        facts_by_chapter_slot[target_chapter_id][slot_id].append(fact.fact_id)
                    continue
                separated = separate_atomic_fact(fact, target_chapter_id, slot_id)
                for rule in separated:
                    errors = _semantic_errors(rule, target_schema)
                    gated = replace(
                        rule, review_status="needs_revision" if errors or rule.review_status == "needs_revision" else "unreviewed",
                        semantic_validity="invalid" if errors else rule.semantic_validity,
                        validation_errors=errors,
                    )
                    if fact.fact_id not in facts_by_chapter_slot[target_chapter_id][slot_id]:
                        facts_by_chapter_slot[target_chapter_id][slot_id].append(fact.fact_id)
                    rules.append(gated)
    for entry in entries:
        chapter, schema = entry["chapter"], entry["schema"]
        chapter_id = chapter["chapterId"]
        for slot in schema.slots:
            fact_ids = tuple(facts_by_chapter_slot[chapter_id].get(slot.slot_id, []))
            status = "confirmed" if fact_ids else ("not_applicable" if slot.applicability in {"optional", "presentation_only", "derived", "conditional"} else "missing")
            slots.append(SchemaSlotState(chapter_id, slot.slot_id, fact_ids, status))
    approved = ApprovedData(SCHEMA_VERSION, tuple(chapters), tuple(facts), tuple(slots), tuple(rules)).to_dict()
    from .gap_analyzer import analyze_gaps
    return analyze_gaps(approved)


def build_rule_intelligence_v1(model: dict[str, Any], approved_data: dict[str, Any]) -> dict[str, Any]:
    """Project structured content into the Phase-1 publication authority chain."""
    from .rule_intelligence_pipeline import build_rule_intelligence_projection

    temporal = model.get("temporalEvidence") if isinstance(model.get("temporalEvidence"), dict) else {}
    return build_rule_intelligence_projection(
        approved_data=approved_data,
        chapters=list(approved_data.get("chapters") or []),
        entity_declarations=list(model.get("entityDeclarations") or []),
        context_windows=list(model.get("contextWindows") or []),
        temporal_facts=list(temporal.get("facts") or []),
        temporal_rule_candidates=list(temporal.get("ruleCandidates") or []),
        temporal_observations=list(temporal.get("observations") or []),
        temporal_evidence_gaps=list(temporal.get("gaps") or []),
        component_tracks=list(model.get("componentTracks") or []),
    )
