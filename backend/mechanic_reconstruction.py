"""Read-only reconstruction of grounded Rules into publishable mechanic flows."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .planning_language_renderer import render_rule


_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "planner_knowledge" / "mechanic-reconstruction-policies-v1.json"


def _policy() -> dict[str, Any]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return re.sub(r"[\s，。；：、,.!?！？‘’“”()（）]", "", str(value or "").casefold())


def _decompose_and_classify_clauses(rule: dict[str, Any], text: str) -> tuple[str, list[dict[str, str]], int]:
    raw_clauses = [item.strip() for item in re.split(r"[，,；;]", text) if item.strip()]
    classifications: list[dict[str, str]] = []
    retained: list[str] = []
    seen: set[str] = set()
    for clause in raw_clauses:
        normalized = _norm(clause)
        exception = bool(re.search(r"仍可|依然|例外|死亡动画期间", clause))
        target_consequence = bool(re.search(r"(?:不再|不能|无法).*(?:目标|被选择)|(?:移出|移除).*(?:目标|目标集合)", clause))
        if normalized in seen:
            value_class = "redundant"
        elif target_consequence and rule.get("intent") == "Death" and not exception:
            value_class = "derived_trivial"
        elif exception:
            value_class = "exception_relevant"
        elif rule.get("ruleType") == "presentation":
            value_class = "player_visible"
        else:
            value_class = "execution_relevant"
        classifications.append({"text": clause, "valueClass": value_class, "sourceRuleId": str(rule.get("ruleId") or "")})
        seen.add(normalized)
        if value_class not in {"derived_trivial", "redundant"}:
            retained.append(clause)
    return "，".join(retained), classifications, len(raw_clauses) - len(retained)


def _scope_matches(subject: str, scope: Any) -> bool:
    subject_norm = _norm(subject)
    values = scope if isinstance(scope, list) else [scope]
    return bool(subject_norm) and any(
        _norm(value) and (_norm(value) in subject_norm or subject_norm in _norm(value))
        for value in values
    )


def _recover_entity_owners(rules: list[dict[str, Any]], chapters: list[dict[str, Any]]) -> int:
    changed = 0
    scoped = [chapter for chapter in chapters if chapter.get("entityScope")]
    for rule in rules:
        current = next((chapter for chapter in chapters if chapter.get("chapterId") == rule.get("canonicalOwner")), None)
        if not current or not current.get("entityScope") or _scope_matches(rule.get("subject"), current["entityScope"]):
            continue
        candidates = [chapter for chapter in scoped if _scope_matches(rule.get("subject"), chapter.get("entityScope"))]
        if len(candidates) == 1:
            rule["canonicalOwner"] = candidates[0]["chapterId"]
            rule["ownerChapterId"] = candidates[0]["chapterId"]
            rule["ownerRecoveryBasis"] = "entity_scope"
            changed += 1
        else:
            rule["publicationEligibility"] = "blocked"
            rule.setdefault("guardReasons", []).append("entity_scope_unresolved")
    return changed


def _recover_cross_section_owners(rules: list[dict[str, Any]], chapters: list[dict[str, Any]], policy: dict[str, Any]) -> int:
    changed = 0
    chapter_by_id = {str(chapter.get("chapterId")): chapter for chapter in chapters}
    for family in policy.get("canonicalOwnerFamilies") or []:
        intents = set(family.get("intents") or [])
        anchors = set(family.get("anchorIntents") or [])
        family_rules = [rule for rule in rules if rule.get("intent") in intents]
        anchor_owners = {
            str(rule.get("canonicalOwner")) for rule in family_rules
            if rule.get("intent") in anchors and rule.get("canonicalOwner")
        }
        if len(anchor_owners) != 1:
            continue
        target = next(iter(anchor_owners))
        target_system = chapter_by_id.get(target, {}).get("system")
        for rule in family_rules:
            current = str(rule.get("canonicalOwner") or "")
            if current == target:
                continue
            if family.get("sameSystem") and target_system and chapter_by_id.get(current, {}).get("system") != target_system:
                continue
            if current:
                rule.setdefault("referenceOwnerChapterIds", []).append(current)
                rule["referenceOwnerChapterIds"] = list(dict.fromkeys(rule["referenceOwnerChapterIds"]))
            rule["canonicalOwner"] = target
            rule["definitionMode"] = "full_definition"
            rule["ownerRecoveryBasis"] = "cross_section_semantic_responsibility"
            changed += 1
    return changed


def _candidate_types(rules: list[dict[str, Any]], policy: dict[str, Any], lesson_registry) -> list[str]:
    if not any(rule.get("intent") == "CandidateGeneration" for rule in rules):
        return []
    binding = (policy.get("policyBindings") or {}).get("candidateTypeResolution") or {}
    if not lesson_registry.is_policy_enabled(
        str(binding.get("policyId") or ""), "mechanic_reconstruction"
    ):
        return []
    explicit = [
        str(candidate_type)
        for rule in rules
        for candidate_type in (
            list(rule.get("candidateTypes") or [])
            if isinstance(rule.get("candidateTypes"), list)
            else [rule.get("candidateType")]
        )
        if candidate_type
    ]
    if explicit:
        return list(dict.fromkeys(explicit))
    text = "\n".join(str(rule.get("behavior") or "") for rule in rules)
    return [
        item["candidateType"] for item in policy.get("candidateTypes") or []
        if any(re.search(pattern, text) for pattern in item.get("patterns") or [])
    ]


def _variant_for(rules: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any] | None:
    intents = {str(rule.get("intent")) for rule in rules}
    text = "\n".join(str(rule.get("behavior") or "") for rule in rules)
    return next((
        variant for variant in policy.get("mechanicVariants") or []
        if set(variant.get("requiredIntents") or []).issubset(intents)
        and all(re.search(pattern, text) for pattern in variant.get("evidencePatterns") or [])
    ), None)


def _decompose_compound_semantic_steps(steps: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    contracts = list(policy.get("compoundSemanticClauses") or [])
    for step in steps:
        contract = next((item for item in contracts if item.get("sourceGroup") == step.get("semanticGroup")), None)
        matched = None
        if contract:
            matched = next((
                (spec, re.search(str(spec.get("pattern") or ""), str(step.get("text") or "")))
                for spec in contract.get("patterns") or []
                if re.search(str(spec.get("pattern") or ""), str(step.get("text") or ""))
            ), None)
        if not matched:
            result.append(step)
            continue
        spec, match = matched
        source_rule_ids = list(step.get("sourceRuleIds") or ([step.get("ruleId")] if step.get("ruleId") else []))
        for index, capture in enumerate(spec.get("captures") or []):
            text = str(match.group(int(capture.get("group") or 0)) or "").strip()
            if capture.get("template"):
                text = str(capture["template"]).format(*match.groups()).strip()
            if not text:
                continue
            clause = deepcopy(step)
            clause["clauseId"] = f"{step.get('ruleId')}::semantic-{index + 1}"
            clause["text"] = text
            clause["semanticGroup"] = str(capture.get("semanticGroup") or step.get("semanticGroup"))
            clause["sourceRuleIds"] = source_rule_ids
            result.append(clause)
    return result


def _classify_final_gap(gap: dict[str, Any], policy: dict[str, Any]) -> str:
    contract = policy.get("finalGapRequirementPolicy") or {}
    explicit = str(gap.get("finalRequirementClass") or "")
    allowed = {*set(contract.get("publishableClasses") or []), "implicit_system_semantics"}
    if explicit in allowed:
        return explicit
    question = str(gap.get("question") or gap.get("proposal") or "")
    if any(re.search(pattern, question) for pattern in contract.get("specialProjectBehaviorPatterns") or []):
        return "special_project_behavior"
    if any(re.search(pattern, question) for pattern in contract.get("playerVisibleDecisionPatterns") or []):
        return "player_visible_design_decision"
    implicit_reference = str(gap.get("referenceKind") or "") in set(contract.get("implicitSystemReferenceKinds") or [])
    implicit_wording = any(re.search(pattern, question) for pattern in contract.get("implicitSystemPatterns") or [])
    if implicit_reference and implicit_wording:
        return "implicit_system_semantics"
    if gap.get("status") == "proposal_pending":
        return "planner_choice_required"
    return "planner_choice_required"


def _final_gaps(
    gaps: list[dict[str, Any]], flows: list[dict[str, Any]], policy: dict[str, Any], rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    suppressed = 0
    result = []
    classifications: list[dict[str, Any]] = []
    flow_by_chapter = {
        str(chapter_id): flow
        for flow in flows
        for chapter_id in (flow.get("sourceChapterIds") or [flow.get("chapterId")])
    }
    proposal_rules = {str(rule.get("proposalId")): rule for rule in rules if rule.get("proposalId")}
    generic = [re.compile(pattern) for pattern in policy.get("schemaQuestionPatterns") or []]
    technical = [re.compile(pattern) for pattern in policy.get("technicalQuestionPatterns") or []]
    seen_decisions: set[tuple[str, str]] = set()
    for source in gaps:
        gap = deepcopy(source)
        question = str(gap.get("question") or gap.get("proposal") or "")
        if gap.get("gapDomain") == "technical" or any(pattern.search(question) for pattern in technical):
            suppressed += 1
            continue
        flow = flow_by_chapter.get(str(gap.get("chapterId") or ""))
        variant = (flow or {}).get("mechanicVariant")
        variant_policy = next((item for item in policy.get("mechanicVariants") or [] if item.get("variantId") == variant), None)
        rewrite = next((
            item for item in (variant_policy or {}).get("gapRewrites") or []
            if str(gap.get("schemaSlot") or "") in set(item.get("sourceSlots") or [])
        ), None)
        if rewrite:
            gap["schemaSlot"] = rewrite["targetSlot"]
            gap["question"] = rewrite["question"]
            gap["specificity"] = "concrete_decision"
            question = gap["question"]
        if variant_policy and str(gap.get("schemaSlot") or "") in set(variant_policy.get("notApplicableSlots") or []):
            suppressed += 1
            continue
        requirement_class = _classify_final_gap(gap, policy)
        gap["finalRequirementClass"] = requirement_class
        gap["finalPublicationRequired"] = requirement_class in set(
            (policy.get("finalGapRequirementPolicy") or {}).get("publishableClasses") or []
        )
        classifications.append({
            "gapId": gap.get("gapId"),
            "finalRequirementClass": requirement_class,
            "finalPublicationRequired": gap["finalPublicationRequired"],
        })
        if not gap["finalPublicationRequired"]:
            suppressed += 1
            continue
        if any(pattern.search(question) for pattern in generic) and gap.get("specificity") != "concrete_decision":
            suppressed += 1
            continue
        specificity = next((
            item for item in policy.get("planningGapSpecificityRules") or []
            if str(gap.get("schemaSlot") or "") in set(item.get("sourceSlots") or [])
        ), None)
        if specificity:
            candidate_types = list((flow or {}).get("candidateTypes") or [])
            if specificity.get("requiresCandidateTypes") and not candidate_types:
                suppressed += 1
                continue
            labels = policy.get("candidateTypeLabels", {})
            template = specificity.get("singleTypeQuestionTemplate") if len(candidate_types) == 1 else None
            gap["question"] = str(template or specificity["questionTemplate"]).format(
                subject=str((flow or {}).get("subject") or "该机制"),
                candidateTypes="、".join(labels.get(item, item) for item in candidate_types),
            )
            gap["specificity"] = "concrete_decision"
            gap["decisionKey"] = specificity["decisionKey"]
            question = gap["question"]
        proposal = proposal_rules.get(str(gap.get("proposalId") or ""))
        if gap.get("status") == "proposal_pending" and proposal and not proposal.get("guardReasons"):
            gap["proposal"] = str(proposal.get("behavior") or "")
            gap["displayMode"] = "proposal"
            gap["specificity"] = "concrete_decision"
        if gap.get("specificity") != "concrete_decision" and gap.get("status") != "proposal_pending":
            suppressed += 1
            continue
        if gap.get("gapDomain", "planning") != "planning" or gap.get("applicabilityStatus", "applicable") != "applicable":
            continue
        if gap.get("status") not in {"open", "reviewed_open", "proposal_pending"}:
            continue
        if not question:
            continue
        decision_key = (str(gap.get("chapterId") or ""), str(gap.get("decisionKey") or gap.get("gapId") or ""))
        if decision_key in seen_decisions:
            suppressed += 1
            continue
        seen_decisions.add(decision_key)
        result.append(gap)
    return result, suppressed, classifications


def reconstruct_publication(
    *, rules: list[dict[str, Any]], chapters: list[dict[str, Any]], gaps: list[dict[str, Any]],
    lesson_registry=None,
) -> dict[str, Any]:
    if lesson_registry is None:
        from .system_lesson_registry import load_system_lesson_registry
        lesson_registry = load_system_lesson_registry()
    rule_value_enabled = lesson_registry.is_policy_enabled(
        "publication.rule_value", "mechanic_reconstruction"
    )
    run_specific_enabled = lesson_registry.is_policy_enabled(
        "authority.run_specific_observation", "mechanic_reconstruction"
    )
    ordering_enabled = lesson_registry.is_policy_enabled(
        "renderer.mechanic_narrative_order", "mechanic_reconstruction"
    )
    policy = _policy()
    rules = deepcopy(rules)
    recovered = _recover_cross_section_owners(rules, chapters, policy)
    reassignments = _recover_entity_owners(rules, chapters)
    excluded_types = set(policy.get("finalExcludedRuleTypes") or [])
    non_executable = [re.compile(pattern) for pattern in policy.get("nonExecutableRulePatterns") or []]
    trivial_derived = [
        rule for rule in rules
        if rule_value_enabled
        if rule.get("derivationKind") == "logical_consequence"
        and rule.get("finalValue") != "non_trivial"
        and not rule.get("exception")
    ]
    trivial_ids = {str(rule.get("ruleId")) for rule in trivial_derived}
    eligible = [
        rule for rule in rules
        if rule.get("publicationEligibility") == "eligible"
        and rule.get("confirmationStatus") == "confirmed"
        and rule.get("definitionMode") == "full_definition"
        and rule.get("ruleType") not in excluded_types
        and str(rule.get("ruleId")) not in trivial_ids
        and not any(pattern.search(str(rule.get("behavior") or "")) for pattern in non_executable)
    ]
    run_specific_suppressed = 0
    configured_retained = 0
    trivial_clause_suppressed = 0
    for rule in eligible:
        cleaned, classifications, removed = (
            _decompose_and_classify_clauses(rule, str(rule.get("behavior") or ""))
            if rule_value_enabled else (str(rule.get("behavior") or ""), [], 0)
        )
        rule["finalClauseClassifications"] = classifications
        if removed:
            rule["behavior"] = cleaned
            trivial_clause_suppressed += removed
        authority = str(rule.get("valueAuthority") or "")
        if authority == "observed_run_value" and run_specific_enabled:
            original = str(rule.get("behavior") or "")
            sanitized = re.sub(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", "", original)
            sanitized = sanitized.replace("固定发放", "发放").replace("基础货币", "货币")
            rule["behavior"] = sanitized
            rule["publicationValueMode"] = "mechanism_without_run_value"
            run_specific_suppressed += int(sanitized != original)
        elif authority in {"configured_value", "planner_confirmed_value"}:
            configured_retained += 1
    order = {intent: index for index, intent in enumerate(policy.get("intentOrder") or [])}
    slot_order = {slot: index for index, slot in enumerate(policy.get("slotOrder") or [])}
    chapter_by_id = {str(chapter.get("chapterId")): chapter for chapter in chapters}
    actor_subjects = {_norm(item) for item in policy.get("actorSubjects") or []}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rule in eligible:
        owner = str(rule.get("canonicalOwner") or "")
        chapter = chapter_by_id.get(owner, {})
        chapter_object = str(chapter.get("object") or "")
        chapter_title = str(chapter.get("title") or "")
        subject = str(rule.get("subjectEntityId") or rule.get("subject") or chapter_object or "系统")
        behavior = str(rule.get("behavior") or "")
        flow_subject = chapter_object if (
            rule.get("intent") == "CandidateGeneration"
            or
            chapter.get("chapterType") == "randomization"
            or
            _norm(subject) in actor_subjects
            or (chapter_object and (_norm(chapter_object) in _norm(subject) or _norm(chapter_object) in _norm(behavior)))
            or (chapter_title and _norm(chapter_title) in _norm(behavior))
        ) else subject
        key = (owner, flow_subject)
        grouped.setdefault(key, []).append(rule)
    flows = []
    candidate_resolved = 0
    for (chapter_id, subject), scoped in grouped.items():
        if ordering_enabled:
            scoped.sort(key=lambda rule: (order.get(str(rule.get("intent")), 999), slot_order.get(str(rule.get("schemaSlot")), 999), str(rule.get("ruleId"))))
        variant = _variant_for(scoped, policy)
        types = _candidate_types(scoped, policy, lesson_registry)
        if types:
            candidate_resolved += 1
        flows.append({
            "mechanicId": f"MECH-{chapter_id}-{hashlib.sha1(subject.encode('utf-8')).hexdigest()[:8].upper()}",
            "chapterId": chapter_id,
            "sourceChapterIds": [chapter_id],
            "system": chapter_by_id.get(chapter_id, {}).get("system"),
            "subject": subject,
            "mechanicVariant": (variant or {}).get("variantId"),
            "candidateTypes": types,
            "candidateTypeSummary": (
                "当前已观察到的候选内容包括："
                + "、".join(policy.get("candidateTypeLabels", {}).get(item, item) for item in types)
                + "。"
            ) if types else "",
            "steps": [{
                "ruleId": rule.get("ruleId"), "sourceRuleId": rule.get("ruleId"), "intent": rule.get("intent"),
                "schemaSlot": rule.get("schemaSlot"),
                "ruleType": rule.get("ruleType"), "subject": rule.get("subject"),
                "text": render_rule(rule).get("text") or rule.get("behavior"), "sourceFactIds": list(rule.get("sourceFactIds") or []),
                "evidenceIds": list(rule.get("evidenceIds") or []),
                "sourceRuleIds": [rule.get("ruleId")] if rule.get("ruleId") else [],
                "clauseClassifications": deepcopy(rule.get("finalClauseClassifications") or []),
            } for rule in scoped],
        })
    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for flow in flows:
        key = (str(flow.get("system") or ""), str(flow.get("subject") or ""))
        if key not in combined:
            combined[key] = deepcopy(flow)
            continue
        target = combined[key]
        target["sourceChapterIds"] = list(dict.fromkeys(target["sourceChapterIds"] + flow["sourceChapterIds"]))
        target["candidateTypes"] = list(dict.fromkeys(target["candidateTypes"] + flow["candidateTypes"]))
        target["steps"] = list({str(step.get("ruleId")): step for step in [*target["steps"], *flow["steps"]]}.values())
        if flow.get("mechanicVariant"):
            target["mechanicVariant"] = flow["mechanicVariant"]
    flows = list(combined.values())
    for flow in flows:
        candidate_context = any(step.get("intent") == "CandidateGeneration" for step in flow.get("steps") or [])
        semantic_group_by_slot = policy.get("semanticGroupBySlot", {})
        semantic_group_order = {group: index for index, group in enumerate(policy.get("semanticGroupOrder") or [])}
        if candidate_context and ordering_enabled:
            for step in flow["steps"]:
                step["semanticGroup"] = semantic_group_by_slot.get(str(step.get("schemaSlot")), "other")
            flow["steps"] = _decompose_compound_semantic_steps(flow["steps"], policy)
            inline_groups = set(policy.get("inlineInteractionGroups") or [])
            merged_steps = []
            consumed_rule_ids: set[str] = set()
            for step in flow["steps"]:
                if step.get("ruleId") in consumed_rule_ids or step.get("ruleType") == "interaction":
                    continue
                companions = [
                    other for other in flow["steps"]
                    if other.get("ruleType") == "interaction"
                    and other.get("schemaSlot") == step.get("schemaSlot")
                    and other.get("semanticGroup") == step.get("semanticGroup")
                    and other.get("semanticGroup") in inline_groups
                ]
                if companions:
                    action = companions[0]
                    action_text = str(action.get("text") or "").rstrip("。；，,")
                    result_text = str(step.get("text") or "").rstrip("。")
                    step["text"] = action_text + str(policy.get("interactionJoiner") or "后，") + result_text
                    step["sourceRuleIds"] = list(dict.fromkeys([
                        *(action.get("sourceRuleIds") or []), *(step.get("sourceRuleIds") or []),
                    ]))
                    step["sourceFactIds"] = list(dict.fromkeys([
                        *(action.get("sourceFactIds") or []), *(step.get("sourceFactIds") or []),
                    ]))
                    step["evidenceIds"] = list(dict.fromkeys([
                        *(action.get("evidenceIds") or []), *(step.get("evidenceIds") or []),
                    ]))
                    consumed_rule_ids.add(str(action.get("ruleId") or ""))
                merged_steps.append(step)
            for step in flow["steps"]:
                if step.get("ruleType") == "interaction" and step.get("ruleId") not in consumed_rule_ids:
                    merged_steps.append(step)
            flow["steps"] = merged_steps
        if ordering_enabled:
            flow["steps"].sort(key=lambda step: (
                semantic_group_order.get(str(step.get("semanticGroup")), 999) if candidate_context else order.get(str(step.get("intent")), 999),
                slot_order.get(str(step.get("schemaSlot")), 999),
                order.get(str(step.get("intent")), 999),
                str(step.get("ruleId")),
            ))
        flow["semanticGroups"] = []
        if candidate_context and ordering_enabled:
            for group_id in policy.get("semanticGroupOrder") or []:
                grouped_steps = [step for step in flow["steps"] if step.get("semanticGroup") == group_id]
                if grouped_steps:
                    flow["semanticGroups"].append({"groupId": group_id, "steps": grouped_steps})
        supporting_rules = [
            rule for rule in rules
            if str(rule.get("canonicalOwner") or "") in set(flow.get("sourceChapterIds") or [])
            and rule.get("confirmationStatus") == "confirmed"
        ]
        types = _candidate_types(supporting_rules, policy, lesson_registry) or (flow.get("candidateTypes") or [])
        flow["candidateTypes"] = types
        flow["candidateTypeSummary"] = (
            "当前已观察到的候选内容包括："
            + "、".join(policy.get("candidateTypeLabels", {}).get(item, item) for item in types)
            + "。"
        ) if types else ""
    final_gaps, suppressed, gap_classifications = _final_gaps(gaps, flows, policy, rules)
    remaining_scope_violations = sum(
        1 for rule in eligible
        for chapter in chapters
        if chapter.get("chapterId") == rule.get("canonicalOwner") and chapter.get("entityScope")
        and not _scope_matches(rule.get("subject"), chapter.get("entityScope"))
    )
    unsupported = sum(
        1 for rule in eligible
        if rule.get("guardReasons") or re.search(r"等概率|无放回|权重|保底", str(rule.get("behavior") or ""))
    )
    return {
        "rules": rules,
        "mechanicFlows": flows,
        "finalPlanningGaps": final_gaps,
        "gapClassifications": gap_classifications,
        "audit": {
            "reconstructedMechanismCount": len(flows),
            "crossSectionRecoveredRules": recovered,
            "schemaQuestionsSuppressed": suppressed,
            "genericCandidateAbstractionsResolved": candidate_resolved,
            "entityScopeReassignments": reassignments,
            "entityScopeViolations": remaining_scope_violations,
            "remainingPlanningGaps": len(final_gaps),
            "technicalGaps": sum(1 for gap in gaps if gap.get("gapDomain") == "technical"),
            "unsupportedInferenceCount": unsupported,
            "trivialDerivedRulesSuppressed": len(trivial_derived),
            "trivialDerivedClausesSuppressed": trivial_clause_suppressed,
            "runSpecificValuesSuppressed": run_specific_suppressed,
            "configuredValuesRetained": configured_retained,
            "implicitSystemSemanticGapsSuppressed": sum(
                item.get("finalRequirementClass") == "implicit_system_semantics"
                and not item.get("finalPublicationRequired")
                for item in gap_classifications
            ),
        },
    }
