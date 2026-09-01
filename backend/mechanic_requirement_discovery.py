from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


CLOSURE_STATUSES = frozenset({
    "resolved",
    "evidence_probe",
    "evidence_resolvable",
    "evidence_unknown",
    "review_required",
    "dormant_optional",
    "not_applicable",
})


def _contract(*criteria: str, insufficient: Iterable[str] = ()) -> dict[str, list[str]]:
    return {"criteria": list(criteria), "insufficientPatterns": list(insufficient)}


def _dimension(
    dimension_id: str,
    role: str,
    *criteria: str,
    existence_signals: Iterable[str] = (),
    modes: Iterable[str] = ("hidden_behavior",),
    parent: str | None = None,
    insufficient: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "dimensionId": dimension_id,
        "parentDimensionId": parent,
        "dimensionRole": role,
        "requiredExistenceSignals": list(existence_signals),
        "observableModes": [
            {"mode": mode, "priority": index + 1}
            for index, mode in enumerate(modes)
        ],
        "satisfactionContract": _contract(*criteria, insufficient=insufficient),
        "priorSources": [{
            "type": "gve16_skill",
            "sourceRef": "benchmark_execution_prior_v1",
            "reason": "execution_dimension_check_only",
        }],
    }


# Runtime-only, provisional benchmark prior. It asks what to inspect and does
# not contain current-project answers or test expectations.
BENCHMARK_EXECUTION_PRIOR_V1: dict[str, list[dict[str, Any]]] = {
    "monster_movement_attack": [
        _dimension("movement.state", "core", "movement_state", modes=("temporal", "static")),
        _dimension("attack.entry", "core", "entry_condition", "entry_transition", modes=("temporal",)),
        _dimension("attack.execution", "core", "execution_event", "execution_result", modes=("temporal",)),
        _dimension("attack.exit", "core", "exit_condition", "exit_result", modes=("temporal",),
                   insufficient=("exit_condition_without_result",)),
        _dimension("attack.post_exit_state", "core", "post_exit_state", modes=("temporal",)),
        _dimension("attack.death_interrupt", "core", "death_event", "interruption_result", modes=("temporal",)),
        _dimension("attack.target_selection", "conditional", "target_selection_rule",
                   existence_signals=("target_selection_exists",)),
        _dimension("attack.repeat.exists", "conditional", "repeat_exists",
                   existence_signals=("repeat_attack_exists",), modes=("temporal",)),
        _dimension("attack.repeat.interval", "conditional", "repeat_interval",
                   existence_signals=("attack_interval_exists",), modes=("temporal", "hidden_parameter"),
                   parent="attack.repeat.exists"),
        _dimension("attack.target_invalidation", "conditional", "invalidation_condition", "invalidation_result",
                   existence_signals=("target_invalidation_exists",), modes=("temporal", "hidden_behavior")),
    ],
    "weapon_execution": [
        _dimension("weapon.acquire", "core", "acquisition_source", "acquisition_result", modes=("static", "temporal")),
        _dimension("weapon.slot_activation", "core", "slot_or_activation_condition", "active_state", modes=("mixed",)),
        _dimension("weapon.attack_trigger", "core", "attack_trigger", modes=("temporal",)),
        _dimension("weapon.damage_trigger", "core", "damage_event", modes=("temporal",)),
        _dimension("weapon.damage_attribution", "core", "attribution_source", "attribution_consumer"),
        _dimension("weapon.target_selection", "conditional", "target_selection_rule",
                   existence_signals=("target_selection_exists",)),
        _dimension("weapon.cooldown", "conditional", "cooldown_start", "cooldown_end",
                   existence_signals=("cooldown_exists",), modes=("temporal", "hidden_parameter")),
        _dimension("weapon.slot_full", "conditional", "slot_full_condition", "slot_full_result",
                   existence_signals=("slot_full_exists",)),
        _dimension("weapon.replacement_removal", "conditional", "replacement_or_removal_result",
                   existence_signals=("replacement_exists",)),
    ],
    "battle_level_three_choice": [
        _dimension("choice.trigger", "core", "trigger_condition", modes=("temporal", "static")),
        _dimension("choice.candidate_generation", "core", "candidate_generation_event", modes=("temporal", "static")),
        _dimension("choice.temporary_state", "core", "temporary_state_entry", "temporary_state_duration", modes=("temporal",)),
        _dimension("choice.confirm", "core", "confirmation_action", "committed_result", modes=("temporal",)),
        _dimension("choice.apply", "core", "application_target", "application_result", modes=("temporal", "static")),
        _dimension("choice.exit", "core", "exit_condition", "exit_result", modes=("temporal",)),
        _dimension("choice.pause_resume", "conditional", "pause_state", "resume_condition",
                   existence_signals=("pause_exists",), modes=("temporal",)),
        _dimension("choice.refresh.exists", "conditional", "refresh_exists",
                   existence_signals=("refresh_exists",), modes=("temporal", "static")),
        _dimension("choice.refresh.cost", "conditional", "refresh_cost",
                   existence_signals=("refresh_cost_exists",), parent="choice.refresh.exists", modes=("static", "hidden_parameter")),
        _dimension("choice.duplicate_rule", "conditional", "duplicate_handling",
                   existence_signals=("duplicate_handling_exists",)),
        _dimension("choice.pool_algorithm", "conditional", "pool_construction_rule",
                   existence_signals=("pool_algorithm_exists",)),
        _dimension("choice.cross_run_reset", "conditional", "cross_run_reset_rule",
                   existence_signals=("cross_run_persistence_exists",)),
    ],
    "independent_weapon_draw": [
        _dimension("draw.entry", "core", "entry_condition", modes=("temporal", "static")),
        _dimension("draw.result_generation", "core", "generation_event", modes=("temporal", "static")),
        _dimension("draw.result_commitment", "core", "commit_action", "committed_result", modes=("temporal",)),
        _dimension("draw.downstream_effect", "core", "effect_consumer", "effect_result", modes=("temporal", "static")),
        _dimension("draw.cost", "conditional", "cost_source", "cost_consumption",
                   existence_signals=("draw_cost_exists",), modes=("static", "hidden_parameter")),
        _dimension("draw.pool", "conditional", "pool_membership_rule", existence_signals=("draw_pool_exists",)),
        _dimension("draw.weight", "conditional", "weight_rule", existence_signals=("draw_weight_exists",), modes=("hidden_parameter",)),
        _dimension("draw.pity", "conditional", "pity_trigger", "pity_result", existence_signals=("pity_exists",)),
        _dimension("draw.animation_relation", "conditional", "animation_result_relation",
                   existence_signals=("draw_animation_exists",), modes=("temporal",)),
        _dimension("draw.abandon_replacement", "conditional", "abandon_or_replace_result",
                   existence_signals=("draw_abandon_exists",)),
    ],
    "stage_boss_end": [
        _dimension("stage.transition", "core", "stage_exit", "next_stage_entry", modes=("temporal",)),
        _dimension("boss.entry", "core", "boss_entry_condition", "boss_entry_state", modes=("temporal", "static")),
        _dimension("boss.termination", "core", "boss_termination_condition", "termination_result", modes=("temporal",)),
        _dimension("battle.next_state", "core", "next_state", modes=("temporal", "static")),
        _dimension("stage.completion_after_boss", "conditional", "completion_condition", "completion_result",
                   existence_signals=("post_boss_continuation_exists",), modes=("temporal",),
                   parent="boss.termination"),
        _dimension("boss.initialization", "conditional", "boss_initial_state", existence_signals=("boss_initialization_exists",)),
        _dimension("stage.failure_interrupt", "conditional", "failure_or_interrupt_condition", "result",
                   existence_signals=("stage_failure_branch_exists",), modes=("temporal",)),
        _dimension("stage.level_reset", "conditional", "level_reset_scope", existence_signals=("level_reset_exists",)),
    ],
    "damage_statistics": [
        _dimension("statistics.start", "core", "statistics_start_scope", modes=("temporal", "static")),
        _dimension("statistics.period", "core", "statistics_period"),
        _dimension("statistics.attribution", "core", "attribution_source", "attribution_target"),
        _dimension("statistics.additional_effect_attribution", "conditional", "additional_effect_attribution_rule",
                   existence_signals=("additional_effect_exists",), parent="statistics.attribution"),
        _dimension("statistics.aggregation", "core", "aggregation_input", "aggregation_result"),
        _dimension("statistics.end", "core", "statistics_end_condition", "end_result", modes=("temporal", "static")),
        _dimension("statistics.settlement_snapshot", "conditional", "snapshot_condition", "snapshot_result",
                   existence_signals=("settlement_statistics_exists",)),
        _dimension("statistics.dps", "conditional", "dps_window", "dps_formula", existence_signals=("dps_exists",)),
        _dimension("statistics.ranking", "conditional", "ranking_key", "ranking_order", existence_signals=("ranking_exists",)),
        _dimension("statistics.refresh_frequency", "conditional", "refresh_frequency", existence_signals=("statistics_refresh_exists",)),
        _dimension("statistics.persistence", "conditional", "persistence_scope", existence_signals=("statistics_persistence_exists",)),
    ],
    "outcome_settlement": [
        _dimension("outcome.success_trigger", "core", "success_condition", "success_result", modes=("temporal", "static")),
        _dimension("outcome.failure_trigger", "core", "failure_condition", "failure_result", modes=("temporal", "static")),
        _dimension("outcome.termination", "core", "termination_effect", modes=("temporal",)),
        _dimension("settlement.entry", "core", "settlement_entry_condition", "settlement_state", modes=("temporal", "static")),
        _dimension("settlement.next_state", "core", "next_state", modes=("temporal", "static")),
        _dimension("outcome.priority", "conditional", "priority_rule", existence_signals=("outcome_priority_exists",)),
        _dimension("outcome.pending_events", "conditional", "pending_event_handling", existence_signals=("pending_events_exist",)),
        _dimension("settlement.reward_calculation", "conditional", "reward_inputs", "reward_result",
                   existence_signals=("reward_calculation_exists",)),
        _dimension("settlement.persistence", "conditional", "persistence_scope", existence_signals=("settlement_persistence_exists",)),
    ],
}


def stable_requirement_id(mechanic_id: str, dimension_id: str) -> str:
    identity = f"mechanic-requirement-v1\x1f{mechanic_id}\x1f{dimension_id}"
    return "REQ-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()


def _is_active(dimension: dict[str, Any], signals: set[str]) -> bool:
    if dimension["dimensionRole"] == "core":
        return True
    required = set(dimension.get("requiredExistenceSignals", []))
    return bool(required and required.issubset(signals))


def _satisfying_rules(
    mechanic_id: str,
    dimension: dict[str, Any],
    rules: Iterable[dict[str, Any]],
) -> list[str]:
    criteria = set(dimension["satisfactionContract"].get("criteria", []))
    matched: list[dict[str, Any]] = []
    for rule in rules:
        allowed_mechanics = set(rule.get("satisfiesMechanicIds", [])) | {rule.get("mechanicId")}
        if not rule.get("valid", False) or mechanic_id not in allowed_mechanics:
            continue
        if dimension["dimensionId"] not in rule.get("dimensionIds", []):
            continue
        matched.append(rule)
    combined_facets = {facet for rule in matched for facet in rule.get("satisfactionFacets", [])}
    if not criteria.issubset(combined_facets):
        return []
    return sorted({rule["ruleId"] for rule in matched if set(rule.get("satisfactionFacets", [])) & criteria})


def _initial_status(dimension: dict[str, Any]) -> tuple[str, dict[str, str]]:
    modes = [item["mode"] for item in dimension.get("observableModes", [])]
    if any(mode in {"static", "temporal", "mixed"} for mode in modes):
        return "evidence_probe", {}
    if "hidden_parameter" in modes:
        return "review_required", {"reviewType": "parameter", "routingTarget": "P6"}
    return "review_required", {"reviewType": "behavior", "routingTarget": "P4"}


def discover_requirements(
    mechanics: Iterable[dict[str, Any]],
    *,
    rules: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    rules = list(rules)
    for mechanic in mechanics:
        mechanic_id = mechanic["mechanicId"]
        prior_types = mechanic.get("executionPriorTypes") or [mechanic.get("mechanicType")]
        dimensions = [dimension for prior_type in prior_types
                      for dimension in BENCHMARK_EXECUTION_PRIOR_V1.get(prior_type, [])]
        signals = set(mechanic.get("existenceSignals", []))
        for dimension in dimensions:
            requirement_id = stable_requirement_id(mechanic_id, dimension["dimensionId"])
            base = {
                "requirementId": requirement_id,
                "mechanicId": mechanic_id,
                "executionDimensionId": dimension["dimensionId"],
                "parentDimensionId": dimension.get("parentDimensionId"),
                "dimensionRole": dimension["dimensionRole"],
                "ownerPath": dict(mechanic.get("ownerPath", {})),
                "priorSources": list(dimension.get("priorSources", [])),
                "satisfactionContract": dimension["satisfactionContract"],
                "observableModes": list(dimension.get("observableModes", [])),
            }
            if not _is_active(dimension, signals):
                result.append({**base, "status": "dormant_optional", "statusHistory": ["dormant_optional"]})
                continue
            satisfying = _satisfying_rules(mechanic_id, dimension, rules)
            if satisfying:
                result.append({**base, "status": "resolved", "statusHistory": ["resolved"],
                               "satisfiedByRuleIds": satisfying})
                continue
            status, routing = _initial_status(dimension)
            result.append({**base, "status": status, "statusHistory": [status], **routing})
    return result


def recognize_benchmark_mechanics(
    models: Iterable[dict[str, Any]],
    chains: Iterable[dict[str, Any]],
    observation_dimensions: Iterable[str],
) -> list[dict[str, Any]]:
    """Select benchmark priors from explicit mechanic, chain, and Fact signals."""
    chains = list(chains)
    observations = set(observation_dimensions)
    result: list[dict[str, Any]] = []
    for model in models:
        mechanic_id = model["mechanicId"]
        mechanic_type = model.get("mechanicType")
        owned_chains = [chain for chain in chains if mechanic_id in chain.get("mechanicIds", [chain.get("mechanicId")])]
        chain_types = {chain.get("chainType") for chain in owned_chains}
        semantics = {
            step.get("semantic")
            for chain in owned_chains
            for field in ("entry", "playerAction", "systemResponse", "stateChange", "progressionResult", "exitOrNext")
            for step in (([chain.get(field)] if isinstance(chain.get(field), dict) else chain.get(field, [])) or [])
            if isinstance(step, dict)
        }
        prior_types: list[str] = []
        signals: set[str] = set()
        if mechanic_type == "monster_attack":
            prior_types.append("monster_movement_attack")
        elif mechanic_type == "attack":
            prior_types.append("weapon_execution")
            if "acquire_weapon" in semantics:
                prior_types.append("independent_weapon_draw")
            if "select_target" in semantics:
                signals.add("target_selection_exists")
            if "affix_thunder_cooldown" in observations:
                signals.add("cooldown_exists")
            if "weapon_draw_skip" in observations:
                signals.add("draw_animation_exists")
        elif mechanic_type == "randomization" and "three_choice_core" in chain_types:
            prior_types.append("battle_level_three_choice")
            if "pause_combat" in semantics:
                signals.add("pause_exists")
            if "refresh_candidates" in semantics:
                signals.add("refresh_exists")
            if "refresh_requirement" in semantics:
                signals.add("refresh_cost_exists")
        elif mechanic_type == "level_flow" and "boss_arrival" in observations:
            prior_types.append("stage_boss_end")
            if any(rule.get("schemaSlot") == "failure_condition" for rule in model.get("knownGameRules", [])):
                signals.add("stage_failure_branch_exists")
            if "victory_result" in observations:
                signals.add("post_boss_continuation_exists")
        elif mechanic_type == "settlement":
            if observations & {"settlement_weapon_damage", "settlement_total_damage"}:
                prior_types.append("damage_statistics")
                signals.add("settlement_statistics_exists")
            if observations & {"affix_multi_explosion", "affix_poison_damage", "ultimate_four_way_penalty"}:
                signals.add("additional_effect_exists")
            if "victory_result" in observations or any(
                rule.get("schemaSlot") == "failure_condition" for rule in model.get("knownGameRules", [])
            ):
                prior_types.append("outcome_settlement")
        if not prior_types:
            continue
        result.append({
            "mechanicId": mechanic_id,
            "mechanicType": mechanic_type,
            "executionPriorTypes": prior_types,
            "ownerPath": {
                "system": model.get("chapterId", ""),
                "subsystem": model.get("name", ""),
                "mechanic": model.get("name", ""),
            },
            "existenceSignals": sorted(signals),
            "recognitionBasis": {
                "chainTypes": sorted(value for value in chain_types if value),
                "chainSemantics": sorted(value for value in semantics if value),
                "observationDimensions": sorted(observations),
            },
        })
    return result


_CHAIN_SEMANTIC_SATISFACTION: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "acquire_weapon": (("weapon.acquire", ("acquisition_source", "acquisition_result")),),
    "automatic_targeting_mode": (("weapon.attack_trigger", ("attack_trigger",)),),
    "select_target": (("weapon.target_selection", ("target_selection_rule",)),),
    "enter_and_move": (("movement.state", ("movement_state",)),),
    "contact_damage": (("attack.execution", ("execution_event", "execution_result")),),
    "upgrade_trigger": (("choice.trigger", ("trigger_condition",)),),
    "generate_candidates": (("choice.candidate_generation", ("candidate_generation_event",)),),
    "pause_combat": (("choice.temporary_state", ("temporary_state_entry",)),),
    "select_candidate": (("choice.confirm", ("confirmation_action",)),),
    "apply_selected_effect": (
        ("choice.apply", ("application_target", "application_result")),
        ("choice.confirm", ("committed_result",)),
    ),
    "refresh_candidates": (("choice.refresh.exists", ("refresh_exists",)),),
    "attribute_damage": (("statistics.attribution", ("attribution_source", "attribution_target")),),
}


def project_chain_dimension_satisfaction(chains: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project explicit Phase 5.6 chain semantics to satisfaction facets without reading text."""
    projected: dict[tuple[str, str], dict[str, Any]] = {}
    for chain in chains:
        mechanic_id = chain.get("mechanicId")
        if not mechanic_id or mechanic_id == "CROSS-SYSTEM":
            continue
        for field in ("entry", "playerAction", "systemResponse", "stateChange", "progressionResult", "exitOrNext"):
            value = chain.get(field)
            steps = [value] if isinstance(value, dict) else (value or [])
            for step in steps:
                contracts = _CHAIN_SEMANTIC_SATISFACTION.get(step.get("semantic"), ())
                if not contracts:
                    continue
                for dimension_id, facets in contracts:
                    for rule_id in step.get("ruleIds", []):
                        key = (rule_id, dimension_id)
                        item = projected.setdefault(key, {
                            "ruleId": rule_id,
                            "mechanicId": mechanic_id,
                            "valid": True,
                            "dimensionIds": [dimension_id],
                            "satisfactionFacets": [],
                            "projectionBasis": [],
                        })
                        item["satisfactionFacets"] = sorted(set(item["satisfactionFacets"]) | set(facets))
                        item["projectionBasis"].append({"chainId": chain.get("chainId"), "semantic": step.get("semantic")})
    return list(projected.values())


def select_evidence_source(
    observable_modes: Iterable[dict[str, Any]],
    availability: dict[str, Any],
) -> dict[str, Any]:
    modes = sorted(observable_modes, key=lambda item: item.get("priority", 999))
    first = modes[0]["mode"] if modes else "hidden_behavior"
    if first == "temporal":
        if availability.get("videoAvailable") or availability.get("continuousFramesAvailable"):
            return {"strategy": "video_or_continuous_frames", "mode": "temporal"}
        return {"strategy": "unavailable", "mode": "temporal"}
    if first == "static":
        return {"strategy": "screenshots", "mode": "static"}
    if first == "mixed":
        coverage = float(availability.get("orderedScreenshotCoverage", 0.0))
        continuity = float(availability.get("screenshotTemporalContinuity", 0.0))
        if coverage >= 0.9 and continuity >= 0.9:
            return {"strategy": "ordered_screenshots", "mode": "mixed"}
        if availability.get("videoAvailable"):
            return {"strategy": "combined_video_and_screenshots", "mode": "mixed"}
        return {"strategy": "screenshots_with_gaps", "mode": "mixed"}
    return {"strategy": "review", "mode": first}


def evaluate_probe(probe: dict[str, Any]) -> dict[str, Any]:
    candidates = list(probe.get("candidates", []))
    if candidates:
        reliable = []
        for item in candidates:
            event_ok = item.get("eventRecognitionConfidence", 0.0) >= 0.7
            mode = item.get("claimMode", "causal_rule")
            if mode == "observation":
                accepted = event_ok
            elif mode == "state_transition":
                accepted = event_ok and item.get("stateCorrelation") == "supported"
            else:
                accepted = (event_ok and item.get("transitionCausalityConfidence", 0.0) >= 0.7
                            and item.get("causalSupport") == "supported")
            if accepted:
                reliable.append(item)
        if reliable:
            return {"status": "evidence_resolvable", "evidenceCandidateIds": [
                item["evidenceCandidateId"] for item in reliable
            ]}
        return {"status": "evidence_probe"}
    exhausted = all(probe.get(field) is True for field in (
        "fullSelectedSourceScanned",
        "allAnchorWindowsScanned",
        "allCandidateWindowsExpanded",
        "noNewCandidateWindows",
        "auditTrailRecorded",
    ))
    return ({"status": "evidence_unknown", "reopenable": True}
            if exhausted else {"status": "evidence_probe"})


def build_evidence_candidate(
    *,
    requirement_id: str,
    source_id: str,
    before: dict[str, Any],
    transition: dict[str, Any],
    after: dict[str, Any],
    event_confidence: float,
    causality_confidence: float,
    causal_conditions_verified: bool = False,
    claim_mode: str = "causal_rule",
    observed_facets: Iterable[str] = (),
    execution_dimension_id: str | None = None,
) -> dict[str, Any]:
    raw = f"{requirement_id}:{source_id}:{before.get('timestampMs')}:{after.get('timestampMs')}"
    candidate_id = "EVC-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    effective_causality = causality_confidence if causal_conditions_verified else min(causality_confidence, 0.69)
    correlation = "supported" if causality_confidence >= 0.7 else "uncertain"
    causal = "supported" if effective_causality >= 0.7 else "uncertain"
    candidate = {
        "evidenceCandidateId": candidate_id,
        "requirementId": requirement_id,
        "sourceId": source_id,
        "eventWindow": {"startMs": before.get("timestampMs"), "endMs": after.get("timestampMs")},
        "beforeObservation": dict(before),
        "transitionObservation": dict(transition),
        "afterObservation": dict(after),
        "supportingWindows": [],
        "counterexampleWindows": [],
        "claimMode": claim_mode,
        "observedFacets": list(observed_facets),
        "eventRecognitionConfidence": event_confidence,
        "transitionCausalityConfidence": effective_causality,
        "observedOrder": "before<transition<after",
        "stateCorrelation": correlation,
        "causalSupport": causal,
        "causalLimitations": ([] if causal == "supported" else ["temporal_order_does_not_establish_causality"]),
    }
    if execution_dimension_id:
        candidate["executionDimensionId"] = execution_dimension_id
    return candidate


def build_review_item(
    requirement: dict[str, Any],
    *,
    confirmed_context: Iterable[str],
    question: str,
    probe_summary_ref: str,
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if requirement.get("status") != "review_required":
        raise ValueError("only review_required requirements can be routed to P4/P6")
    return {
        "reviewItemId": f"{requirement['routingTarget']}-{requirement['requirementId'][4:]}",
        "requirementId": requirement["requirementId"],
        "ownerPath": dict(requirement.get("ownerPath", {})),
        "executionDimensionId": requirement["executionDimensionId"],
        "reviewType": requirement["reviewType"],
        "routingTarget": requirement["routingTarget"],
        "probeSummaryRef": probe_summary_ref,
        "defaultView": (build_proposal_review_view(
            confirmed_context=confirmed_context, question=question, proposal=proposal)
            if proposal else {"confirmed": list(confirmed_context), "stillNeedsDefinition": question}),
    }


def promote_candidates_to_evidence_facts(
    candidates: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    evidence_records = []
    facts = []
    for candidate in candidates:
        if evaluate_probe({"candidates": [candidate]}).get("status") != "evidence_resolvable":
            continue
        candidate_id = candidate["evidenceCandidateId"]
        if not candidate.get("executionDimensionId"):
            raise ValueError("evidence candidate must bind an execution dimension")
        digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16].upper()
        evidence_id = f"EVD-{digest}"
        fact_id = f"FACT-{digest}"
        evidence_records.append({
            "evidenceId": evidence_id,
            "sourceEvidenceCandidateId": candidate_id,
            "originRequirementId": candidate["requirementId"],
            "sourceId": candidate.get("sourceId"),
            "eventWindow": candidate["eventWindow"],
            "frameRefs": [candidate[field]["frameRef"] for field in (
                "beforeObservation", "transitionObservation", "afterObservation"
            )],
            "claimMode": candidate["claimMode"],
            "eventRecognitionConfidence": candidate["eventRecognitionConfidence"],
            "transitionCausalityConfidence": candidate["transitionCausalityConfidence"],
            "causalSupport": candidate["causalSupport"],
        })
        facts.append({
            "factId": fact_id,
            "sourceEvidenceIds": [evidence_id],
            "originRequirementIds": [candidate["requirementId"]],
            "executionDimensionId": candidate["executionDimensionId"],
            "factType": "temporal_observation",
            "beforeState": candidate["beforeObservation"].get("state"),
            "observedEvent": candidate["transitionObservation"].get("event"),
            "afterState": candidate["afterObservation"].get("state"),
            "observedFacets": list(candidate.get("observedFacets", [])),
            "causalClaimAllowed": candidate.get("causalSupport") == "supported",
            "rulePromotionStatus": "pending_normal_pipeline",
        })
    return {"evidence": evidence_records, "facts": facts, "rules": []}


def promote_fact_bundle_to_rule(
    requirement: dict[str, Any],
    facts: Iterable[dict[str, Any]],
    *,
    rule_text: str,
    claim_semantics: str,
) -> dict[str, Any] | None:
    """Promote a fully satisfying Fact bundle while preserving REQ/Evidence lineage."""
    related = [fact for fact in facts
               if requirement["requirementId"] in fact.get("originRequirementIds", [])]
    criteria = set(requirement.get("satisfactionContract", {}).get("criteria", []))
    observed = {facet for fact in related for facet in fact.get("observedFacets", [])}
    if not related or not criteria.issubset(observed):
        return None
    if claim_semantics == "causal_rule" and not all(fact.get("causalClaimAllowed") for fact in related):
        return None
    if claim_semantics not in {"observed_sequence", "causal_rule"}:
        raise ValueError(f"unsupported claim semantics: {claim_semantics}")
    fact_ids = sorted({fact["factId"] for fact in related})
    digest = hashlib.sha256(
        f"{requirement['requirementId']}:{':'.join(fact_ids)}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return {
        "ruleId": f"RULE-{digest}",
        "mechanicId": requirement["mechanicId"],
        "valid": True,
        "ruleStatus": "evidence_derived_valid",
        "sourceType": "temporal_evidence",
        "text": rule_text,
        "claimSemantics": claim_semantics,
        "dimensionIds": [requirement["executionDimensionId"]],
        "satisfactionFacets": sorted(criteria),
        "sourceFactIds": fact_ids,
        "sourceEvidenceIds": sorted({evidence_id for fact in related
                                     for evidence_id in fact.get("sourceEvidenceIds", [])}),
        "originRequirementIds": [requirement["requirementId"]],
        "satisfiesRequirementIds": [requirement["requirementId"]],
    }


def build_mechanic_skeleton_placeholder(
    *,
    skeleton_id: str,
    mechanic_id: str,
    owner_chapter: str,
    rule_group: str,
    segments: Iterable[dict[str, str]],
    requirements: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Build a non-Rule mechanic outline with only currently unresolved slots."""
    statuses = {item["requirementId"]: item["status"] for item in requirements}
    texts = []
    requirement_ids = []
    for segment in segments:
        requirement_id = segment.get("requirementId")
        if not requirement_id:
            texts.append(segment["text"])
        elif statuses.get(requirement_id) != "resolved":
            texts.append(f"[{segment['placeholder']}]")
            requirement_ids.append(requirement_id)
    return {
        "placeholderId": f"MSP-{skeleton_id}",
        "mechanicId": mechanic_id,
        "ownerChapter": owner_chapter,
        "ruleGroup": rule_group,
        "text": " → ".join(texts),
        "itemType": "mechanic_skeleton_placeholder",
        "publicationEligible": True,
        "isValidRule": False,
        "requirementIds": requirement_ids,
    }


def build_ai_proposed_rule(
    requirement: dict[str, Any],
    *,
    proposal_text: str,
    known_context_refs: Iterable[str],
    proposal_bases: Iterable[dict[str, str]],
    uncertainties: Iterable[str],
    assumption_level: str,
    proposal_mode: str,
    unsupported_specificity: Iterable[str],
    proposal_type: str = "conservative",
    reasoning_basis: Iterable[str] = (),
    conflicting_evidence: Iterable[str] = (),
    alternatives: Iterable[dict[str, Any]] = (),
    recommended_alternative_id: str | None = None,
    information_gain: Iterable[dict[str, str]] = (),
) -> dict[str, Any]:
    """Create a review-only first draft; this is deliberately not a Rule."""
    if requirement.get("status") in {"resolved", "dormant_optional", "not_applicable"}:
        raise ValueError("AI proposals are only allowed for active unresolved requirements")
    bases = [dict(item) for item in proposal_bases]
    uncertainty_items = list(uncertainties)
    unsupported_items = list(unsupported_specificity)
    reasoning_items = list(reasoning_basis)
    conflict_items = list(conflicting_evidence)
    alternative_items = [dict(item) for item in alternatives]
    gain_items = [dict(item) for item in information_gain]
    allowed_gain_types = {
        "trigger_condition", "state_change", "object_relation", "data_source",
        "aggregation_calculation", "branch_handling", "lifecycle_result",
        "config_meaning", "exception_boundary",
    }
    if assumption_level not in {"low", "medium", "high"}:
        raise ValueError("invalid proposal assumption level")
    if proposal_mode not in {"minimal_completion", "behavior_hypothesis"}:
        raise ValueError("invalid proposal mode")
    if proposal_type not in {"conservative", "design_inference", "alternative_design"}:
        raise ValueError("invalid proposal type")
    if proposal_type == "design_inference" and not reasoning_items:
        raise ValueError("design inference requires reasoning basis")
    if proposal_type == "alternative_design":
        if not 2 <= len(alternative_items) <= 3:
            raise ValueError("alternative design requires two or three options")
        option_ids = {item.get("alternativeId") for item in alternative_items}
        if recommended_alternative_id not in option_ids:
            raise ValueError("alternative design requires a valid recommended option")
        required_fields = {"alternativeId", "text", "gameplayImpact", "advantages", "risks", "compatibility"}
        if any(not required_fields.issubset(item) for item in alternative_items):
            raise ValueError("alternative option is incomplete")
    if not gain_items or any(item.get("type") not in allowed_gain_types
                             or not item.get("decision", "").strip() for item in gain_items):
        raise ValueError("proposal must add structured executable information")
    generic_patterns = (
        r"^战斗开始后开始统计.*战斗结束后结束统计",
        r"^满足.+条件后.+$",
        r"^按规则.+$",
    )
    if any(re.match(pattern, item["decision"].strip()) for item in gain_items
           for pattern in generic_patterns):
        raise ValueError("proposal information gain is only semantic completion")
    if assumption_level == "low" and unsupported_items:
        raise ValueError("low-assumption proposal cannot contain unsupported specificity")
    if not proposal_text.strip() or not bases or not uncertainty_items:
        raise ValueError("proposal text, derivation bases, and uncertainties are required")
    raw = f"{requirement['requirementId']}:{proposal_text.strip()}"
    proposal_id = "PROP-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    return {
        "proposalId": proposal_id,
        "originRequirementId": requirement["requirementId"],
        "mechanicId": requirement["mechanicId"],
        "executionDimensionId": requirement["executionDimensionId"],
        "proposalText": proposal_text.strip(),
        "knownContextRefs": list(dict.fromkeys(known_context_refs)),
        "proposalBases": bases,
        "uncertainties": uncertainty_items,
        "assumptionLevel": assumption_level,
        "proposalMode": proposal_mode,
        "unsupportedSpecificity": unsupported_items,
        "proposalType": proposal_type,
        "reasoningBasis": reasoning_items,
        "conflictingEvidence": conflict_items,
        "alternatives": alternative_items,
        "alternativeCount": len(alternative_items),
        "recommendedAlternativeId": recommended_alternative_id,
        "informationGain": gain_items,
        "informationGainCount": len(gain_items),
        "proposalStatus": "proposed",
        "valid": False,
        "publicationEligible": False,
        "countsAsConfirmedRule": False,
        "evidenceIntegrityClass": "unconfirmed_ai_proposal",
        "reviewActions": ["accept", "edit", "reject", "defer"],
        "defaultReviewEligible": True,
    }


def build_proposal_review_view(
    *, confirmed_context: Iterable[str], question: str, proposal: dict[str, Any] | None,
) -> dict[str, Any]:
    context = list(confirmed_context)
    if proposal is None:
        return {"mode": "question_only", "confirmedContext": context, "question": question}
    if proposal.get("proposalType") == "alternative_design":
        return {"mode": "alternative_design_review", "confirmedContext": context,
                "question": question, "proposalId": proposal["proposalId"],
                "recommendedAlternativeId": proposal["recommendedAlternativeId"],
                "alternatives": list(proposal["alternatives"]),
                "actions": ["accept_recommended", "choose_alternative", "edit", "reject"]}
    display_text = proposal["proposalText"]
    if proposal.get("assumptionLevel") == "medium":
        display_text = f"AI推测：{display_text}"
    return {
        "mode": "proposal_review",
        "confirmedContext": context,
        "question": question,
        "aiProposedRule": display_text,
        "uncertainties": list(proposal.get("uncertainties", [])),
        "actions": ["accept", "edit", "reject", "defer"],
        "proposalId": proposal["proposalId"],
        "proposalType": proposal.get("proposalType", "conservative"),
        "reasoningBasis": list(proposal.get("reasoningBasis", [])),
        "conflictingEvidence": list(proposal.get("conflictingEvidence", [])),
    }


def promote_reviewed_proposal_to_rule(
    requirement: dict[str, Any], proposal: dict[str, Any], *, action: str,
    edited_text: str | None = None,
    chosen_alternative_id: str | None = None,
) -> dict[str, Any] | None:
    if action not in {"accept", "edit", "accept_recommended", "choose_alternative"}:
        return None
    if proposal.get("originRequirementId") != requirement.get("requirementId"):
        raise ValueError("proposal does not belong to requirement")
    if action == "edit" and not (edited_text or "").strip():
        raise ValueError("edited proposal requires edited text")
    if action in {"accept_recommended", "choose_alternative"}:
        alternative_id = (proposal.get("recommendedAlternativeId") if action == "accept_recommended"
                          else chosen_alternative_id)
        option = next((item for item in proposal.get("alternatives", [])
                       if item.get("alternativeId") == alternative_id), None)
        if option is None:
            raise ValueError("selected alternative does not exist")
        text = option["text"]
    else:
        text = proposal["proposalText"] if action == "accept" else edited_text.strip()
    digest = hashlib.sha256(
        f"{proposal['proposalId']}:{action}:{text}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return {
        "ruleId": f"RULE-{digest}",
        "mechanicId": requirement["mechanicId"],
        "valid": True,
        "ruleStatus": "approved_review",
        "sourceType": "planner_approved_proposal",
        "sourceProposalId": proposal["proposalId"],
        "text": text,
        "dimensionIds": [requirement["executionDimensionId"]],
        "satisfactionFacets": list(requirement.get("satisfactionContract", {}).get("criteria", [])),
        "originRequirementIds": [requirement["requirementId"]],
        "satisfiesRequirementIds": [requirement["requirementId"]],
        "approvalAction": action,
    }


def finalize_requirement_after_probe(
    requirement: dict[str, Any],
    facts: Iterable[dict[str, Any]],
    *,
    probe_exhausted: bool,
) -> dict[str, Any]:
    criteria = set(requirement.get("satisfactionContract", {}).get("criteria", []))
    facets = {
        facet for fact in facts
        if requirement["requirementId"] in fact.get("originRequirementIds", [])
        for facet in fact.get("observedFacets", [])
    }
    if criteria.issubset(facets):
        return dict(requirement)
    status = "evidence_unknown" if probe_exhausted else "evidence_probe"
    history = list(requirement.get("statusHistory", []))
    if not history or history[-1] != status:
        history.append(status)
    return {**requirement, "status": status, "statusHistory": history,
            "reopenable": status == "evidence_unknown",
            "unresolvedCriteria": sorted(criteria - facets)}


def route_hidden_requirement(kind: str) -> dict[str, str]:
    if kind == "hidden_parameter":
        return {"status": "review_required", "reviewType": "parameter", "routingTarget": "P6"}
    if kind == "hidden_behavior":
        return {"status": "review_required", "reviewType": "behavior", "routingTarget": "P4"}
    raise ValueError(f"unsupported hidden requirement kind: {kind}")


_REVIEW_QUESTIONS = {
    "weapon.damage_attribution": "一次伤害应归属于哪个武器或效果，归因以什么事件为准？",
    "weapon.slot_full": "武器栏已满时，新获得的武器应如何处理？",
    "draw.pool": "本次抽取允许进入结果集合的内容由什么规则确定？",
    "statistics.attribution": "统计伤害时，伤害应按什么规则归属于具体武器或效果？",
    "statistics.additional_effect_attribution": "附加伤害是否归属于产生该效果的来源武器？",
    "statistics.aggregation": "本局伤害记录应从哪些事件累计，并按什么口径聚合？",
    "settlement.reward_calculation": "结算奖励由哪些已确认输入决定？",
    "statistics.settlement_snapshot": "关卡完成后，结算应冻结哪一时点的伤害统计结果？",
}


def review_question_for_dimension(dimension_id: str) -> str:
    return _REVIEW_QUESTIONS.get(dimension_id, f"请定义 {dimension_id} 对应的玩法行为。")


_PLANNER_RELEVANT_IMPACTS = frozenset({
    "gameplay_rule", "numeric_config", "qa_acceptance", "player_state",
})


def evaluate_planner_relevance(requirement: dict[str, Any]) -> dict[str, Any]:
    impacts = set(requirement.get("decisionImpacts", []))
    relevant = bool(impacts & _PLANNER_RELEVANT_IMPACTS)
    return {
        "plannerRelevant": relevant,
        "action": "retain" if relevant else "suppress_implementation_detail",
        "reason": ("changes_planner_visible_contract" if relevant
                   else "only_changes_internal_implementation"),
    }


def reassess_requirement(
    requirement: dict[str, Any],
    rules: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    satisfying = []
    requirement_id = requirement["requirementId"]
    for rule in rules:
        if not rule.get("valid", False):
            continue
        if requirement_id not in rule.get("satisfiesRequirementIds", []):
            continue
        allowed_mechanics = set(rule.get("satisfiesMechanicIds", [])) | {rule.get("mechanicId")}
        if requirement.get("mechanicId") not in allowed_mechanics:
            continue
        if requirement.get("executionDimensionId") not in rule.get("dimensionIds", []):
            continue
        satisfying.append(rule["ruleId"])
    if not satisfying:
        return dict(requirement)
    history = list(requirement.get("statusHistory", []))
    if not history or history[-1] != "resolved":
        history.append("resolved")
    return {**requirement, "status": "resolved", "statusHistory": history,
            "satisfiedByRuleIds": sorted(set(satisfying))}
