"""Phase-1 structured Rule authority pipeline.

This module never treats chapter titles, planner prose, or knowledge patterns as
project answers.  It projects already structured facts/rules through intent,
ownership, evidence and closure contracts before publication.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any


INTENT_BY_SLOT = {
    "attack_target": "TargetSelection",
    "attack_direction": "AttackDirection",
    "attack_method": "AttackMode",
    "attack_trigger": "AttackTrigger",
    "attack_frequency": "AttackInterval",
    "attack_range": "Range",
    "damage_reference": "Damage",
    "damage": "Damage",
    "spawn_trigger": "Spawn",
    "spawn_source": "Spawn",
    "spawn_composition": "Spawn",
    "spawn_interval": "Spawn",
    "spawn_stop_condition": "Spawn",
    "movement_trigger": "Movement",
    "movement_direction": "Movement",
    "movement_control": "Movement",
    "movement_speed_source": "Movement",
    "movement_path": "Movement",
    "movement_stop_condition": "Movement",
    "random_trigger": "CandidateGeneration",
    "candidate_pool_source": "CandidateGeneration",
    "pool_entry_condition": "CandidateGeneration",
    "candidate_selection": "CandidateGeneration",
    "candidate_effect": "CandidateGeneration",
    "selection_pause": "CandidateGeneration",
    "refresh_rule": "CandidateGeneration",
    "refresh_cost": "CandidateGeneration",
    "victory_condition": "VictoryCondition",
    "failure_condition": "FailureCondition",
    "level_end_timing": "ResultTransition",
    "result_transition": "ResultTransition",
}

FALLBACK_INTENTS = (
    ("VictoryCondition", re.compile(r"胜利|挑战成功|通关")),
    ("FailureCondition", re.compile(r"失败|挑战失败")),
    ("ResultTransition", re.compile(r"进入(?:结算|结果)|结束检查")),
    ("TargetSelection", re.compile(r"(?:选择|锁定|寻找).{0,8}目标|目标.{0,8}(?:选择|锁定)")),
    ("AttackInterval", re.compile(r"每\s*\d|攻击间隔|攻击频率|冷却")),
    ("Range", re.compile(r"射程|攻击范围|攻击距离")),
    ("AttackDirection", re.compile(r"朝|方向|转向|旋转")),
    ("Damage", re.compile(r"伤害|扣除生命")),
    ("Spawn", re.compile(r"生成|刷新|出现")),
    ("Movement", re.compile(r"移动|前进|行进")),
    ("CandidateGeneration", re.compile(r"候选|抽取|随机")),
    ("AttackTrigger", re.compile(r"开始攻击|触发攻击")),
    ("AttackMode", re.compile(r"攻击|发射|喷射")),
)

RESPONSIBILITY_INTENTS = {
    "victory_condition": "VictoryCondition",
    "failure_condition": "FailureCondition",
    "result_transition": "ResultTransition",
    "candidate_generation": "CandidateGeneration",
    "spawn": "Spawn",
    "movement": "Movement",
    "attack": "AttackTrigger",
}

_INFERENCE_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "planner_knowledge" / "planning-inference-policies-v1.json"
_NARRATIVE_RECOVERY_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "planner_knowledge" / "approved-narrative-recovery-policies-v1.json"


def _inference_policies() -> list[dict[str, Any]]:
    payload = json.loads(_INFERENCE_POLICY_PATH.read_text(encoding="utf-8"))
    return list(payload.get("closureInferencePolicies") or [])


def _confirmed_for_inference(rule: dict[str, Any]) -> bool:
    return (
        rule.get("reviewStatus") in {"approved", "confirmed"}
        and rule.get("semanticValidity", "valid") == "valid"
        and not rule.get("guardReasons")
    )


def _apply_closure_inference_policies(
    rules: list[dict[str, Any]], lesson_registry,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inferred: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    confirmed = [rule for rule in rules if _confirmed_for_inference(rule)]
    for policy in _inference_policies():
        permission = str(policy.get("inferencePermission") or "evidence_required")
        risk = str(policy.get("riskClass") or "high")
        if permission == "infer_and_publish" and risk != "low":
            continue
        if permission == "infer_with_review" and risk not in {"low", "medium"}:
            continue
        grouped: dict[str, list[dict[str, Any]]] = {}
        for rule in confirmed:
            owner = str(rule.get("canonicalOwner") or rule.get("ownerChapterId") or "")
            grouped.setdefault(owner, []).append(rule)
        for scoped_rules in grouped.values():
            matched: list[dict[str, Any]] = []
            for field, requirements in (("intent", policy.get("requiredIntents") or []), ("schemaSlot", policy.get("requiredSlots") or [])):
                for requirement in requirements:
                    source = next((rule for rule in scoped_rules if rule.get(field) == requirement), None)
                    if source is None:
                        matched = []
                        break
                    matched.append(source)
                if requirements and not matched:
                    break
            matched = list({str(rule.get("ruleId")): rule for rule in matched}.values())
            if not matched:
                continue
            output = dict(policy.get("output") or {})
            primary = matched[0]
            behavior = str(output.get("behaviorTemplate") or "").format(primarySubject=str(primary.get("subject") or "系统"))
            source_rule_ids = [str(rule.get("ruleId")) for rule in matched]
            source_fact_ids = list(dict.fromkeys(str(fid) for rule in matched for fid in (rule.get("sourceFactIds") or [])))
            evidence_ids = list(dict.fromkeys(str(eid) for rule in matched for eid in (rule.get("evidenceIds") or [])))
            rule_id = "RULE-INF-" + hashlib.sha1(f"{policy.get('policyId')}|{'|'.join(sorted(source_rule_ids))}".encode("utf-8")).hexdigest()[:12].upper()
            candidate = {
                "ruleId": rule_id, "subject": primary.get("subject") or "系统", "behavior": behavior,
                "intent": output.get("intent") or "Unknown", "intentBasis": "declarative_closure_policy",
                "schemaSlot": output.get("schemaSlot") or "", "ruleType": output.get("ruleType") or "logic",
                "ownerChapterId": primary.get("canonicalOwner") or primary.get("ownerChapterId"),
                "canonicalOwner": primary.get("canonicalOwner") or primary.get("ownerChapterId"),
                "definitionMode": "full_definition", "semanticValidity": "valid",
                "reviewStatus": "approved" if permission == "infer_and_publish" else "unreviewed",
                "confirmationStatus": "confirmed" if permission == "infer_and_publish" else "unreviewed",
                "inferenceLevel": "planner_inference", "inferencePermission": permission,
                "inferencePolicy": policy.get("policyId"), "sourceRuleIds": source_rule_ids,
                "sourceFactIds": source_fact_ids, "evidenceIds": evidence_ids, "guardReasons": [],
                "publicationEligibility": "eligible" if permission == "infer_and_publish" else "review_required",
            }
            candidate["guardReasons"] = _guard_rule(candidate, lesson_registry)
            if candidate["guardReasons"]:
                candidate["publicationEligibility"] = "blocked"
            if any(_normalized(rule.get("behavior")) == _normalized(behavior) for rule in rules + inferred):
                continue
            if permission == "infer_and_publish":
                inferred.append(candidate)
            elif permission == "infer_with_review":
                proposal_id = "PROPOSAL-" + rule_id.removeprefix("RULE-INF-")
                candidate["proposalId"] = proposal_id
                proposals.append({
                    "proposalId": proposal_id, "inferencePermission": permission, "reviewStatus": "unreviewed",
                    "evidenceLineage": {"sourceRuleIds": source_rule_ids, "sourceFactIds": source_fact_ids, "evidenceIds": evidence_ids},
                    "addressesGapSlots": list(policy.get("addressesGapSlots") or []), "proposedRule": candidate,
                })
    return inferred, proposals


def _normalized(value: Any) -> str:
    text = str(value or "").casefold()
    return re.sub(r"[\s，。；：、,.!?！？‘’“”()（）]", "", text)


def _intent(rule: dict[str, Any], lesson_registry) -> tuple[str, str]:
    explicit = str(rule.get("intent") or rule.get("intentHint") or "")
    slot = str(rule.get("schemaSlot") or "")
    # A broad carrier slot cannot erase a narrower semantic in the Rule itself.
    # This is a fallback refinement, never a chapter-title classification.
    behavior = str(rule.get("behavior") or "")
    if explicit and rule.get("intentAuthority") == "planner_confirmed_feedback":
        return explicit, "planner_confirmed_feedback"
    intent_policy = json.loads(_NARRATIVE_RECOVERY_POLICY_PATH.read_text(encoding="utf-8"))
    correction = next((
        item for item in intent_policy.get("intentCorrections") or []
        if lesson_registry.is_policy_enabled(
            str(item.get("policyId") or ""), "rule_intelligence"
        )
        if explicit in set(item.get("sourceIntents") or [])
        and any(re.search(pattern, behavior) for pattern in item.get("patterns") or [])
    ), None)
    if correction:
        return str(correction["intent"]), "declarative_semantic_correction"
    if slot == "attack_method" and re.search(r"朝|方向|转向|旋转", behavior):
        return "AttackDirection", "behavior_fallback"
    if explicit and slot in INTENT_BY_SLOT and explicit != INTENT_BY_SLOT[slot]:
        return INTENT_BY_SLOT[slot], "schema_slot_correction"
    if explicit:
        return explicit, "structured_intent"
    if slot in INTENT_BY_SLOT:
        return INTENT_BY_SLOT[slot], "schema_slot"
    predicate = str(rule.get("predicate") or "")
    action = " ".join(str(rule.get(key) or "") for key in ("action", "result", "stateChange"))
    structured = f"{predicate} {action}".strip()
    if structured:
        for intent, pattern in FALLBACK_INTENTS:
            if pattern.search(structured):
                return intent, "structured_semantics"
    for intent, pattern in FALLBACK_INTENTS:
        if pattern.search(behavior):
            return intent, "behavior_fallback"
    return "Unknown", "unresolved"


def _slot_after_semantic_correction(rule: dict[str, Any], intent: str, basis: str) -> str:
    slot = str(rule.get("schemaSlot") or "")
    if basis != "declarative_semantic_correction":
        return slot
    policy = json.loads(_NARRATIVE_RECOVERY_POLICY_PATH.read_text(encoding="utf-8"))
    correction = next((
        item for item in policy.get("intentCorrections") or []
        if item.get("intent") == intent and item.get("schemaSlot")
    ), None)
    return str((correction or {}).get("schemaSlot") or slot)


def _condition(rule: dict[str, Any]) -> str:
    values = rule.get("conditions")
    if isinstance(values, list):
        return " && ".join(str(value) for value in values)
    return str(rule.get("condition") or rule.get("trigger") or "")


def _fingerprint(rule: dict[str, Any], intent: str) -> str:
    identity = {
        "subject": _normalized(rule.get("subject")),
        "intent": intent,
        "trigger": _normalized(rule.get("trigger")),
        "condition": _normalized(_condition(rule)),
        "result": _normalized(rule.get("result") or rule.get("stateChange")),
    }
    # Legacy structured rules often carry the complete result in behavior.
    if not identity["result"]:
        identity["result"] = _normalized(rule.get("behavior"))
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _similarity_group(rule: dict[str, Any], intent: str) -> str:
    identity = {
        "subject": _normalized(rule.get("subject")),
        "intent": intent,
        "result": _normalized(rule.get("result")) or _normalized(rule.get("behavior"))[-8:],
    }
    return hashlib.sha1(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _owner_for(rule: dict[str, Any], intent: str, chapters: list[dict[str, Any]], lesson_registry) -> str | None:
    current = str(rule.get("canonicalOwner") or rule.get("ownerChapterId") or "")
    if not lesson_registry.is_policy_enabled(
        "ownership.canonical_global_recovery", "rule_intelligence"
    ):
        return current or None
    required = {
        "VictoryCondition": "victory_condition",
        "FailureCondition": "failure_condition",
        "ResultTransition": "result_transition",
    }.get(intent)
    if required:
        owners = [
            str(chapter.get("chapterId")) for chapter in chapters
            if required in set(chapter.get("schemaResponsibilities") or [])
            or any(str(gap.get("schemaSlot") or "") == required for gap in chapter.get("gaps") or [])
        ]
        if len(owners) == 1:
            return owners[0]
    return current or None


def _guard_rule(rule: dict[str, Any], lesson_registry) -> list[str]:
    text = str(rule.get("behavior") or "")
    reasons = []
    authority = str(rule.get("authorityStatus") or rule.get("inferenceLevel") or "observed")
    if re.search(r"等概率|无放回|权重|优先级|保底", text) and authority not in {"confirmed", "explicit", "planner_confirmed"}:
        reasons.append(
            "unsupported_random_mechanic"
            if lesson_registry.is_policy_enabled("guard.random_strength", "evidence_guard")
            else "random_strength_policy_unavailable"
        )
    if (rule.get("formulaExpression") or "公式" in text) and str(rule.get("parameterSource") or "") != "explicit_formula":
        reasons.append("unsupported_formula")
    return reasons


def _parameters(items: list[dict[str, Any]], lesson_registry) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result, formulae = [], []
    for source in items:
        item = deepcopy(source)
        values = item.get("observedValues")
        if (
            lesson_registry.is_policy_enabled("guard.pattern_formula", "evidence_guard")
            and item.get("sourceKind") == "observed_value"
            and isinstance(values, list)
            and len(values) >= 3
        ):
            deltas = [right - left for left, right in zip(values, values[1:]) if isinstance(left, (int, float)) and isinstance(right, (int, float))]
            if len(deltas) == len(values) - 1 and len(set(deltas)) == 1:
                item["sourceKind"] = "inferred_pattern"
                item["inferredPattern"] = {"kind": "constant_delta", "delta": deltas[0]}
                item.pop("formulaExpression", None)
        if item.get("sourceKind") == "explicit_formula" and item.get("formulaExpression"):
            formulae.append(deepcopy(item))
        result.append(item)
    return result, formulae


def _closure(chapter: dict[str, Any], rules: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    responsibilities = set(chapter.get("schemaResponsibilities") or [])
    if chapter.get("chapterType") == "randomization":
        responsibilities.add("candidate_generation")
    if not responsibilities:
        return None, []
    intents = {
        rule["intent"] for rule in rules
        if rule.get("confirmationStatus") == "confirmed"
        and (rule.get("canonicalOwner") == chapter.get("chapterId") or rule.get("ownerChapterId") == chapter.get("chapterId"))
    }
    slots: dict[str, str] = {}
    gaps = []
    required = []
    for responsibility in responsibilities:
        intent = RESPONSIBILITY_INTENTS.get(responsibility)
        if not intent:
            continue
        label = intent
        state = "confirmed" if intent in intents else "unresolved"
        slots[label] = state
        required.append(label)
        if state != "confirmed":
            gaps.append({
                "gapId": f"GAP-{chapter.get('chapterId')}-{label}", "chapterId": chapter.get("chapterId"),
                "schemaSlot": label, "intent": intent, "gapKind": "missing_schema_slot",
                "status": "unresolved", "blockingScope": "chapter" if intent == "VictoryCondition" else "rule",
                "gapDomain": "planning", "inferencePermission": "evidence_required",
                "applicabilityStatus": "applicable",
                "severity": "implementation_blocking" if intent == "VictoryCondition" else "qa_blocking",
            })
    if "CandidateGeneration" in intents or "candidate_generation" in responsibilities:
        for label in ("CandidateType", "Eligibility", "SamplingRule"):
            slots.setdefault(label, "unresolved")
        for label in ("WeightRule", "PriorityRule", "GuaranteeRule", "DuplicateRule"):
            slots.setdefault(label, "not_observed")
    status = "complete" if required and all(slots.get(label) == "confirmed" for label in required) else "incomplete"
    return {"chapterId": chapter.get("chapterId"), "status": status, "slots": slots, "requiredSlots": required}, gaps


def _entity_lifecycle(entities: list[dict[str, Any]], rules: list[dict[str, Any]], lesson_registry) -> list[dict[str, Any]]:
    if not lesson_registry.is_policy_enabled(
        "closure.lifecycle_evidence_bound", "schema_closure"
    ):
        return []
    gaps = []
    for entity in entities:
        if entity.get("entityType") != "combat_entity" or entity.get("existenceStatus") != "confirmed":
            continue
        name = _normalized(entity.get("name"))
        intents = {
            rule["intent"] for rule in rules
            if rule.get("confirmationStatus") == "confirmed" and name and name in _normalized(rule.get("subject"))
        }
        for intent in ("Spawn", "Movement", "AttackTrigger"):
            if intent in intents:
                continue
            gaps.append({
                "gapId": f"GAP-{entity.get('entityId')}-{intent}", "subjectEntityId": entity.get("entityId"),
                "intent": "Attack" if intent == "AttackTrigger" else intent, "schemaSlot": intent,
                "gapKind": "missing_lifecycle_node", "status": "unresolved", "blockingScope": "rule",
            })
    return gaps


def build_rule_intelligence_projection(
    *, approved_data: dict[str, Any], chapters: list[dict[str, Any]],
    entity_declarations: list[dict[str, Any]] | None = None,
    context_windows: list[dict[str, Any]] | None = None,
    temporal_observations: list[dict[str, Any]] | None = None,
    temporal_facts: list[dict[str, Any]] | None = None,
    temporal_rule_candidates: list[dict[str, Any]] | None = None,
    temporal_evidence_gaps: list[dict[str, Any]] | None = None,
    component_tracks: list[dict[str, Any]] | None = None,
    legacy_mode: bool = False,
    lesson_registry=None,
) -> dict[str, Any]:
    del component_tracks
    if lesson_registry is None:
        from .system_lesson_registry import load_system_lesson_registry
        lesson_registry = load_system_lesson_registry()
    from .planner_feedback_assimilation import assimilate_planner_feedback
    feedback_assimilation = assimilate_planner_feedback(approved_data)
    approved_data = feedback_assimilation["effectiveApprovedData"]
    from .approved_information_recovery import recover_approved_information
    information_recovery = recover_approved_information(
        approved_data, chapters, lesson_registry=lesson_registry
    )
    from .recovered_rule_dependency_closure import close_recovered_rule_dependencies
    dependency_closure = close_recovered_rule_dependencies(
        approved_data=approved_data,
        chapters=chapters,
        rules=[*list(approved_data.get("rules") or []), *information_recovery["rules"]],
        lesson_registry=lesson_registry,
    )
    chapters = dependency_closure["chapters"]
    facts = [*deepcopy(approved_data.get("facts") or []), *deepcopy(temporal_facts or [])]
    for window in context_windows or []:
        timestamps = [float(value) for value in window.get("evidenceTimestamps") or [] if isinstance(value, (int, float))]
        for field, observation in (window.get("facts") or {}).items():
            if not isinstance(observation, str) or not observation.strip():
                continue
            fact_id = "FACT-TEMP-" + hashlib.sha1(f"{window.get('id')}|{field}|{observation}".encode()).hexdigest()[:12].upper()
            facts.append({
                "factId": fact_id, "subject": window.get("subjectEntity") or "待解析对象",
                "entityId": window.get("subjectEntityId"), "predicate": field, "object": observation.strip(),
                "sourceText": observation.strip(), "evidenceIds": [window.get("anchorFrameId")],
                "evidenceTimestamps": timestamps, "timeRange": [min(timestamps), max(timestamps)] if timestamps else None,
                "confidence": float(window.get("confidence") or 0), "evidenceLevel": "observed",
                "sourceKind": "auxiliary_video", "observationMode": "temporal_context",
                "inferenceLevel": "observed", "reviewStatus": "unreviewed",
                "anchorAuthority": window.get("anchorAuthority") or "visual_match",
            })
    rules = []
    exact_groups: dict[str, list[dict[str, Any]]] = {}
    similarity_groups: dict[str, list[dict[str, Any]]] = {}
    authoritative_sources = [
        *list(approved_data.get("rules") or []),
        *information_recovery["rules"],
        *dependency_closure["rules"],
    ]
    approved_rule_ids = {str(item.get("ruleId")) for item in authoritative_sources}
    for source in [*authoritative_sources, *list(temporal_rule_candidates or [])]:
        rule = deepcopy(source)
        intent, basis = _intent(rule, lesson_registry)
        rule["schemaSlot"] = _slot_after_semantic_correction(rule, intent, basis)
        exact = _fingerprint(rule, intent)
        similar = _similarity_group(rule, intent)
        owner = _owner_for(rule, intent, chapters, lesson_registry)
        reasons = _guard_rule(rule, lesson_registry)
        rule.update({
            "intent": intent, "intentBasis": basis, "canonicalOwner": owner,
            "exactSemanticFingerprint": exact, "similarityGroup": similar,
            "definitionMode": "full_definition", "guardReasons": reasons,
            "publicationEligibility": "blocked" if reasons or not owner or intent == "Unknown" else "eligible",
        })
        if str(rule.get("ruleId")) not in approved_rule_ids:
            rule["candidateKind"] = str(rule.get("candidateKind") or "temporal_rule_candidate")
            rule["publicationEligibility"] = "review_required"
        confirmation = rule.get("confirmationFingerprint")
        rule["confirmationStatus"] = "stale" if confirmation and confirmation != exact else ("confirmed" if rule.get("reviewStatus") in {"approved", "confirmed"} else "unreviewed")
        if rule["confirmationStatus"] == "stale":
            rule["publicationEligibility"] = "review_required"
        rules.append(rule)
        exact_groups.setdefault(exact, []).append(rule)
        similarity_groups.setdefault(similar, []).append(rule)

    # A legacy chapter snapshot may omit schemaResponsibilities even though its
    # already-approved outcome rules establish one unambiguous canonical owner.
    # Recover only when the whole result family points to exactly one owner.
    outcome_owners = {
        str(rule.get("canonicalOwner")) for rule in rules
        if rule.get("canonicalOwner") and (
            rule.get("intent") in {"VictoryCondition", "FailureCondition"}
            or rule.get("schemaSlot") == "result_transition"
        )
    }
    if (
        lesson_registry.is_policy_enabled(
            "ownership.canonical_global_recovery", "rule_intelligence"
        )
        and len(outcome_owners) == 1
    ):
        outcome_owner = next(iter(outcome_owners))
        for rule in rules:
            if rule.get("intent") != "ResultTransition" or rule.get("canonicalOwner"):
                continue
            rule["canonicalOwner"] = outcome_owner
            rule["ownerRecoveryBasis"] = "unique_approved_result_family_owner"
            if not rule.get("guardReasons"):
                rule["publicationEligibility"] = "eligible"

    for group in exact_groups.values():
        if len(group) < 2:
            continue
        canonical = _owner_for(group[0], group[0]["intent"], chapters, lesson_registry)
        full = next((rule for rule in group if rule.get("ownerChapterId") == canonical), group[0])
        for rule in group:
            rule["canonicalOwner"] = canonical or full.get("ownerChapterId")
            rule["definitionMode"] = "full_definition" if rule is full else "reference"

    possible_duplicates = []
    for group_id, group in similarity_groups.items():
        distinct = {rule["exactSemanticFingerprint"] for rule in group}
        if len(distinct) <= 1:
            continue
        possible_duplicates.append({"similarityGroup": group_id, "ruleIds": [rule.get("ruleId") for rule in group], "status": "review_required"})
        for rule in group:
            rule["publicationEligibility"] = "review_required"

    planner_inferences, review_proposals = _apply_closure_inference_policies(
        rules, lesson_registry
    )
    rules.extend(planner_inferences)
    rules.extend(deepcopy(item["proposedRule"]) for item in review_proposals)

    observations = deepcopy(temporal_observations or [])
    movement_candidates, temporal_gaps = [], []
    for observation in observations:
        if observation.get("observationType") != "VisualPositionChange" or len(observation.get("samples") or []) < 2:
            continue
        movement_candidates.append({
            "candidateId": f"MOVE-{observation.get('observationId')}", "entityId": observation.get("entityId"),
            "sourceObservationId": observation.get("observationId"), "status": "candidate",
        })
        gap_kind = "coordinate_frame_unknown" if observation.get("coordinateFrame") in {None, "", "unknown"} else "movement_driver_unknown"
        temporal_gaps.append({
            "gapId": f"GAP-{observation.get('observationId')}", "subjectEntityId": observation.get("entityId"),
            "intent": "Movement", "gapKind": gap_kind, "status": "unresolved", "blockingScope": "review_only",
        })

    closures, closure_gaps = [], []
    for chapter in chapters:
        item, gaps = _closure(chapter, rules)
        if item:
            closures.append(item)
            closure_gaps.extend(gaps)
    confirmed_recovered_slots = {
        (str(rule.get("canonicalOwner") or ""), str(rule.get("schemaSlot") or ""), str(rule.get("intent") or ""))
        for rule in rules
        if rule.get("confirmationStatus") == "confirmed" and rule.get("inferenceLevel") == "approved_information_recovery"
    }
    source_gaps = []
    resolved_by_recovery = []
    for source_gap in deepcopy(approved_data.get("gaps") or []):
        key = (str(source_gap.get("chapterId") or ""), str(source_gap.get("schemaSlot") or ""), str(source_gap.get("intent") or ""))
        slot_only_match = any(owner == key[0] and slot == key[1] for owner, slot, _intent in confirmed_recovered_slots if slot and key[1])
        intent_only_match = any(owner == key[0] and intent == key[2] for owner, _slot, intent in confirmed_recovered_slots if intent and key[2])
        if key in confirmed_recovered_slots or slot_only_match or intent_only_match:
            source_gap.update({"status": "resolved", "resolution": "global_approved_information_recovery"})
            resolved_by_recovery.append(source_gap)
            continue
        source_gaps.append(source_gap)
    information_recovery["resolvedGapIds"] = [gap.get("gapId") for gap in resolved_by_recovery]
    gaps = [
        *source_gaps, *deepcopy(temporal_evidence_gaps or []),
        *_entity_lifecycle(entity_declarations or [], rules, lesson_registry), *closure_gaps,
        *deepcopy(dependency_closure["gaps"]), *temporal_gaps,
    ]
    proposal_slots = {
        (str(proposal["proposedRule"].get("canonicalOwner") or ""), str(slot)): proposal
        for proposal in review_proposals
        for slot in proposal.get("addressesGapSlots") or []
    }
    for gap in gaps:
        gap.setdefault("gapDomain", "planning")
        gap.setdefault("inferencePermission", "evidence_required")
        gap.setdefault("applicabilityStatus", "applicable")
        proposal = proposal_slots.get((str(gap.get("chapterId") or ""), str(gap.get("schemaSlot") or "")))
        if proposal and gap.get("status") not in {"resolved", "not_applicable"}:
            gap["status"] = "proposal_pending"
            gap["inferencePermission"] = "infer_with_review"
            gap["proposalId"] = proposal["proposalId"]
    parameters, formulae = _parameters(approved_data.get("parameters") or [], lesson_registry)
    from .mechanic_reconstruction import reconstruct_publication
    reconstruction = reconstruct_publication(
        rules=rules, chapters=chapters, gaps=gaps, lesson_registry=lesson_registry
    )
    gap_classification_by_id = {
        str(item.get("gapId")): item for item in reconstruction.get("gapClassifications") or []
        if item.get("gapId")
    }
    for gap in gaps:
        classification = gap_classification_by_id.get(str(gap.get("gapId") or ""))
        if classification:
            gap.update(deepcopy(classification))
    rules = reconstruction["rules"]
    reconstructed_rule_ids = {
        str(step.get("ruleId"))
        for flow in reconstruction["mechanicFlows"]
        for step in flow.get("steps") or []
        if step.get("ruleId")
    }
    publication_rules = [
        deepcopy(rule) for rule in rules
        if rule.get("publicationEligibility") == "eligible"
        and rule.get("confirmationStatus") == "confirmed"
        and str(rule.get("ruleId")) in reconstructed_rule_ids
    ]
    rule_candidates = [deepcopy(rule) for rule in rules if rule.get("candidateKind") == "temporal_rule_candidate"]
    chapter_map = {str(chapter.get("chapterId")): deepcopy(chapter) for chapter in chapters if chapter.get("chapterId")}
    review_chapters, publication_chapters = [], []
    for chapter_id, chapter in chapter_map.items():
        review_definitions = [deepcopy(rule) for rule in rules if rule.get("canonicalOwner") == chapter_id and rule.get("definitionMode") == "full_definition"]
        review_references = [deepcopy(rule) for rule in rules if (rule.get("ownerChapterId") == chapter_id and rule.get("definitionMode") != "full_definition") or chapter_id in (rule.get("referenceOwnerChapterIds") or [])]
        definitions = [deepcopy(rule) for rule in publication_rules if rule.get("canonicalOwner") == chapter_id and rule.get("definitionMode") == "full_definition"]
        references = [deepcopy(rule) for rule in publication_rules if (rule.get("ownerChapterId") == chapter_id and rule.get("definitionMode") != "full_definition") or chapter_id in (rule.get("referenceOwnerChapterIds") or [])]
        chapter_gaps = [deepcopy(gap) for gap in gaps if gap.get("chapterId") == chapter_id]
        publication_gaps = [deepcopy(gap) for gap in reconstruction["finalPlanningGaps"] if gap.get("chapterId") == chapter_id]
        chapter_blocked = any(gap.get("blockingScope") in {"chapter", "document"} and gap.get("status") not in {"resolved", "not_applicable"} for gap in chapter_gaps)
        shared = {
            **chapter, "closureStatus": next((item["status"] for item in closures if item["chapterId"] == chapter_id), "not_assessed"),
            "publicationEligibility": "blocked" if chapter_blocked else "eligible",
            "gaps": chapter_gaps,
        }
        review_chapters.append({**shared, "ruleDefinitions": review_definitions, "references": review_references})
        publication_chapters.append({**shared, "publicationEligibility": "eligible", "gaps": publication_gaps, "ruleDefinitions": definitions, "references": references})
    duplicate_full = [fingerprint for fingerprint, group in exact_groups.items() if sum(rule["definitionMode"] == "full_definition" for rule in group) > 1]
    blocked = [rule.get("ruleId") for rule in rules if rule.get("publicationEligibility") != "eligible" or rule.get("confirmationStatus") != "confirmed"]
    return {
        "projectionVersion": "rule-intelligence-phase1-v1",
        "authorityMode": "legacy_approved_snapshot" if legacy_mode else "structured_rules",
        "facts": facts, "rules": rules,
        "parameters": parameters, "gaps": gaps, "closures": closures,
        "movementCandidates": movement_candidates, "ruleCandidates": rule_candidates, "possibleDuplicates": possible_duplicates,
        "plannerInferences": deepcopy(planner_inferences), "reviewProposals": deepcopy(review_proposals),
        "feedbackAssimilation": {
            "proposedOperations": deepcopy(feedback_assimilation["proposedOperations"]),
            "appliedOperations": deepcopy(feedback_assimilation["appliedOperations"]),
            "architectureImprovementCandidates": deepcopy(feedback_assimilation["architectureImprovementCandidates"]),
            "lineage": deepcopy(feedback_assimilation["lineage"]),
            "feedbackRevision": approved_data.get("feedbackRevision", 0),
        },
        "approvedInformationRecovery": deepcopy(information_recovery),
        "dependencyClosure": {
            "references": deepcopy(dependency_closure["references"]),
            "unresolvedMechanicReferences": deepcopy(dependency_closure["unresolvedMechanicReferences"]),
            "undefinedReferencedEntities": deepcopy(dependency_closure["undefinedReferencedEntities"]),
            "orphanRuleIds": sorted(
                {str(rule.get("ruleId")) for rule in publication_rules}.difference(reconstructed_rule_ids)
            ),
        },
        "reviewProjection": {"rules": deepcopy(rules), "chapters": review_chapters,
                             "parameters": deepcopy(parameters), "gaps": deepcopy(gaps)},
        "publication": {"rules": publication_rules, "chapters": publication_chapters,
                        "formulae": formulae, "gaps": deepcopy(reconstruction["finalPlanningGaps"]),
                        "finalPlanningGaps": deepcopy(reconstruction["finalPlanningGaps"]),
                        "mechanicFlows": deepcopy(reconstruction["mechanicFlows"])},
        "reconstructionAudit": deepcopy(reconstruction["audit"]),
        "guard": {"passed": not blocked and not duplicate_full, "blockedRuleIds": blocked,
                  "duplicateFullDefinitionFingerprints": duplicate_full},
    }
