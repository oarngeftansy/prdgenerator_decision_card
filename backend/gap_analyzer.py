from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from .chapter_schema_library import SCHEMA_VERSION, chapter_schema_library
from .planning_content_models import ApplicabilityPredicate, Gap


_TAG_PATTERNS = {
    "three_choice": r"三选一|三张候选|候选卡", "roulette": r"老虎机|滚动|随机定格",
    "refresh": r"刷新", "weight": r"权重|概率", "candidate": r"候选|选项",
    "duplicate": r"允许重复|重复项", "replacement": r"放回|不放回|无放回",
    "max_level": r"最大等级|满级|等级上限", "prerequisite": r"前置条件|前置关系",
    "candidate_ui": r"候选卡|选择界面", "range": r"射程|攻击范围|攻击距离",
    "ranged": r"投射物|子弹|喷射", "damage": r"伤害", "repeat": r"连续|频率|冷却|源源不断",
    "continuous": r"连续|源源不断", "multiple_enemies": r"大量|多个|种类", "wave": r"波次",
    "manual_control": r"摇杆|按键|手动|微调", "steering": r"横向微调",
    "directional": r"向下|方向", "follow": r"跟随|向目标", "targeted": r"目标",
    "pathfinding": r"寻路", "waypoint": r"路线|路径", "bounded_path": r"预设路线",
    "collision": r"碰撞", "obstacle": r"障碍", "stage": r"阶段|波次",
    "countdown": r"倒计时", "boss": r"首领|Boss", "reward": r"奖励|金币|经验|道具",
    "persistence": r"落库|保存|记录更新", "settlement_ui": r"结算界面|挑战成功",
    "slot_ui": r"栏位.*显示|武器图标", "attack_vfx": r"攻击形态|攻击特效",
    "attack_sfx": r"攻击音效", "movement_animation": r"移动动画", "movement_vfx": r"移动特效",
}


def _tags(chapter: dict[str, Any], facts: list[dict], rules: list[dict]) -> set[str]:
    text = " ".join([
        str(chapter.get("mechanicVariant") or ""),
        *(str(fact.get("sourceText") or "") for fact in facts), *(str(rule.get("behavior") or "") for rule in rules),
    ])
    tags = {tag for tag, pattern in _TAG_PATTERNS.items() if re.search(pattern, text, re.I)}
    if chapter.get("mechanicVariant"):
        variant = str(chapter["mechanicVariant"])
        tags.difference_update({"three_choice", "roulette"} - {variant})
        tags.add(variant)
    return tags


def _chapter_owns_slot(chapter: dict[str, Any], slot_id: str) -> bool:
    title = str(chapter.get("title") or "")
    if chapter.get("chapterType") == "randomization" and chapter.get("mechanicVariant") == "three_choice":
        refresh_slots = {"refresh_rule", "refresh_count", "refresh_cost"}
        return slot_id in refresh_slots if title == "刷新" else slot_id not in refresh_slots
    if chapter.get("chapterType") == "level_flow":
        result_slots = {"victory_condition", "failure_condition"}
        return slot_id in result_slots if title == "胜负判定" else slot_id not in result_slots
    if chapter.get("chapterType") == "settlement" and title == "伤害统计":
        return slot_id == "settlement_presentation"
    return True


def _predicate_matches(predicate: ApplicabilityPredicate | None, tags: set[str]) -> bool:
    if predicate is None: return False
    if predicate.operator == "evidence_tag": return bool(predicate.operands and predicate.operands[0] in tags)
    values = [_predicate_matches(item, tags) if isinstance(item, ApplicabilityPredicate) else item in tags for item in predicate.operands]
    if predicate.operator == "any": return any(values)
    if predicate.operator == "all": return all(values)
    if predicate.operator == "not": return not any(values)
    return False


def _gap_id(chapter_id: str, slot_id: str) -> str:
    return "GAP-" + hashlib.sha1(f"{chapter_id}:{slot_id}".encode("utf-8")).hexdigest()[:12].upper()


def _question(template: str, chapter: dict[str, Any]) -> str:
    return template.replace("{object}", str(chapter.get("object") or chapter.get("title") or "该对象"))


def _rule_proves_slot(rule: dict[str, Any]) -> bool:
    if rule.get("schemaSlot") == "refresh_cost" and re.search(r"消耗或替代条件|资源或广告", str(rule.get("behavior") or "")):
        return False
    return True


def _fact_proves_slot(slot_id: str, fact: dict[str, Any]) -> bool:
    if slot_id == "refresh_cost" and re.search(r"消耗或替代条件|资源或广告", str(fact.get("sourceText") or "")):
        return False
    return True


def analyze_gaps(approved_data: dict[str, Any]) -> dict[str, Any]:
    """Deterministically compare applicable schema slots with observed, valid coverage."""
    facts_by_id = {fact["factId"]: fact for fact in approved_data.get("facts") or []}
    slots_by_chapter: dict[str, dict[str, dict]] = {}
    for state in approved_data.get("slots") or []:
        slots_by_chapter.setdefault(state["chapterId"], {})[state["slotId"]] = state
    rules_by_chapter: dict[str, list[dict]] = {}
    for rule in approved_data.get("rules") or []:
        rules_by_chapter.setdefault(rule["ownerChapterId"], []).append(rule)

    gaps, chapter_coverage, applicable_total, covered_total = [], [], 0, 0
    inferred_closures = 0
    for chapter in approved_data.get("chapters") or []:
        chapter_id = chapter["chapterId"]
        schema = chapter_schema_library.resolve(chapter["chapterType"], chapter.get("mechanicVariant"), SCHEMA_VERSION)
        chapter_rules = rules_by_chapter.get(chapter_id, [])
        chapter_fact_ids = {fact_id for state in slots_by_chapter.get(chapter_id, {}).values() for fact_id in state.get("factIds") or []}
        chapter_facts = [facts_by_id[fact_id] for fact_id in chapter_fact_ids if fact_id in facts_by_id]
        tags = _tags(chapter, chapter_facts, chapter_rules)
        required = covered = 0
        open_slots = []
        covered_slots = []
        coverage_by_slot = {
            rule["schemaSlot"] for rule in chapter_rules
            if rule.get("semanticValidity", "valid") == "valid" and rule.get("reviewStatus") != "needs_revision"
            and _rule_proves_slot(rule)
            and any(facts_by_id.get(fid, {}).get("evidenceLevel") == "observed" for fid in rule.get("sourceFactIds") or [])
        }
        coverage_by_slot.update(
            slot_id for slot_id, state in slots_by_chapter.get(chapter_id, {}).items()
            if state.get("status") in {"confirmed", "reviewed"}
            and any(
                facts_by_id.get(fid, {}).get("evidenceLevel") == "observed"
                and facts_by_id.get(fid, {}).get("semanticValidity", "valid") == "valid"
                and _fact_proves_slot(slot_id, facts_by_id.get(fid, {}))
                for fid in state.get("factIds") or []
            )
        )
        for slot in schema.slots:
            if not _chapter_owns_slot(chapter, slot.slot_id):
                continue
            applicable = slot.applicability == "core"
            if slot.applicability in {"conditional", "presentation_only"}:
                applicable = _predicate_matches(slot.applicable_when, tags)
            if slot.applicability == "derived":
                applicable = all(source in coverage_by_slot for source in (slot.derivation.source_slots if slot.derivation else ()))
                if applicable: coverage_by_slot.add(slot.slot_id)
            if slot.applicability == "optional" or not applicable:
                continue
            required += 1
            applicable_total += 1
            if slot.slot_id in coverage_by_slot:
                covered += 1
                covered_total += 1
                covered_slots.append(slot.slot_id)
                continue
            state = slots_by_chapter.get(chapter_id, {}).get(slot.slot_id, {})
            if any(facts_by_id.get(fid, {}).get("evidenceLevel") == "inferred" for fid in state.get("factIds") or []):
                inferred_closures += 0
            if slot.gap_policy:
                gap = Gap(
                    _gap_id(chapter_id, slot.slot_id), chapter_id, slot.slot_id,
                    slot.gap_policy.severity, _question(slot.gap_policy.question, chapter),
                    gap_domain=slot.gap_policy.gap_domain,
                    inference_permission=slot.gap_policy.inference_permission,
                )
                payload = gap.to_dict()
                context = chapter.get("temporalProbeContext")
                if slot.gap_policy.probe_type and isinstance(context, dict):
                    required_fields = ("subjectEntityId", "anchor", "searchWindow", "sourceEvidenceRevision")
                    if all(context.get(field) is not None for field in required_fields):
                        payload.update({
                            "probeEligible": True,
                            "probeType": slot.gap_policy.probe_type,
                            "targetProperty": slot.gap_policy.target_property,
                            "evidenceQuestion": payload["question"],
                            **{field: context[field] for field in required_fields},
                        })
                gaps.append(payload)
                open_slots.append(slot.slot_id)
        context = chapter.get("temporalProbeContext")
        movement_observed = any(
            slot_id.startswith("movement_") and slot_id not in {"movement_speed_source", "movement_rate_change"}
            for slot_id in coverage_by_slot
        )
        if chapter.get("chapterType") == "movement" and movement_observed and isinstance(context, dict):
            required_fields = ("subjectEntityId", "anchor", "searchWindow", "sourceEvidenceRevision")
            if all(context.get(field) is not None for field in required_fields) and "movement_rate_change" not in coverage_by_slot:
                rate_gap = {
                    "gapId": _gap_id(chapter_id, "movement_rate_change"),
                    "chapterId": chapter_id, "schemaSlot": "movement_rate_change",
                    "severity": "qa_blocking",
                    "question": f"{chapter.get('object') or chapter.get('title') or '该对象'}的移动速率是否会随过程发生变化？",
                    "status": "open", "gapKind": "missing_temporal_responsibility",
                    "subjectEntityId": context["subjectEntityId"], "intent": "Movement",
                    "blockingScope": "review_only", "gapDomain": "planning",
                    "inferencePermission": "evidence_required", "applicabilityStatus": "applicable",
                    "probeEligible": True, "probeType": "PersistentStateProbe",
                    "targetProperty": "movement_rate",
                    "evidenceQuestion": "该对象在不同时间窗中的移动速率是否发生明显变化？",
                    **{field: context[field] for field in required_fields},
                }
                gaps.append(rate_gap)
                open_slots.append("movement_rate_change")
        chapter_coverage.append({
            "chapterId": chapter_id, "title": chapter["title"], "chapterType": chapter["chapterType"],
            "mechanicVariant": chapter.get("mechanicVariant"), "required": required, "covered": covered,
            "openGap": len(open_slots), "coveredSlots": covered_slots, "openSlots": open_slots,
        })
    keys = [(gap["chapterId"], gap["schemaSlot"]) for gap in gaps]
    severity = Counter(gap["severity"] for gap in gaps)
    return {
        **approved_data, "gaps": gaps, "chapterCoverage": chapter_coverage,
        "metrics": {
            "gapCount": len(gaps), "implementationBlocking": severity["implementation_blocking"],
            "qaBlocking": severity["qa_blocking"], "documentationGap": severity["documentation_gap"],
            "applicableSlotCount": applicable_total, "coveredSlotCount": covered_total,
            "inferredFactsClosingGaps": inferred_closures, "duplicateGapCount": len(keys) - len(set(keys)),
        },
    }
