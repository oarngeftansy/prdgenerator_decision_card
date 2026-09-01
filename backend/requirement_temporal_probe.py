from __future__ import annotations

from pathlib import Path
import hashlib
import math
from typing import Any, Callable

from backend.video_pipeline import inspect_video


_PROBE_POLICIES = {
    "movement_driver_unknown": ("PersistentStateProbe", "position"),
    "coordinate_frame_unknown": ("PersistentStateProbe", "reference_frame"),
    "missing_temporal_trigger": ("TemporalProcessProbe", "trigger"),
    "missing_result_transition": ("TemporalProcessProbe", "result_transition"),
    "missing_timing_observation": ("TemporalProcessProbe", "timing"),
}
_LIFECYCLE_TARGETS = {
    "Spawn": "first_appearance",
    "Movement": "start_movement",
    "Attack": "attack_start",
    "AttackTrigger": "attack_start",
    "Death": "death",
    "Despawn": "disappearance",
    "PhaseChange": "phase_change",
}
_INELIGIBLE_INTENTS = {
    "WeightRule", "Probability", "GuaranteeRule", "Formula",
    "ConfigurationSource", "PriorityRule", "RandomAlgorithm",
}


def _probe_policy(gap: dict[str, Any]) -> tuple[str, str] | None:
    if gap.get("probeEligible") is True:
        probe_type = str(gap.get("probeType") or "").strip()
        target_property = str(gap.get("targetProperty") or "").strip()
        if probe_type and target_property:
            return probe_type, target_property
    if str(gap.get("intent") or "") in _INELIGIBLE_INTENTS:
        return None
    kind = str(gap.get("gapKind") or "")
    if kind == "missing_lifecycle_node":
        target = _LIFECYCLE_TARGETS.get(str(gap.get("intent") or ""))
        return ("LifecycleBoundaryProbe", target) if target else None
    return _PROBE_POLICIES.get(kind)


def build_targeted_probe_requests(
    gaps: list[dict[str, Any]], *, existing_requests: list[dict[str, Any]] | None = None,
    evidence_revision: str,
) -> dict[str, Any]:
    """Create bounded probes only for unresolved, video-observable Gaps.

    Completed/exhausted probes are stable for the same evidence revision.  A new
    video or anchor revision reactivates the request without erasing its audit
    history or attempt count.
    """
    existing = {
        (str(item.get("sourceGapId")), str(item.get("sourceEvidenceRevision") or item.get("evidenceRevision") or "")): item for item in existing_requests or []
        if isinstance(item, dict) and item.get("sourceGapId")
    }
    requests, ineligible = [], []
    for gap in gaps:
        declared_policy = gap.get("probeEligible") is True
        if gap.get("status") not in ({"open", "unresolved"} if declared_policy else {"unresolved"}):
            continue
        policy = _probe_policy(gap)
        if policy is None:
            ineligible.append(str(gap.get("gapId")))
            continue
        if declared_policy and (
            not gap.get("subjectEntityId")
            or not (isinstance(gap.get("anchor"), dict) or isinstance(gap.get("searchWindow"), dict))
        ):
            ineligible.append(str(gap.get("gapId")))
            continue
        gap_id = str(gap.get("gapId"))
        prior = existing.get((gap_id, evidence_revision))
        latest = next((item for item in reversed(existing_requests or []) if item.get("sourceGapId") == gap_id), None)
        prior_revision = (prior or {}).get("sourceEvidenceRevision") or (prior or {}).get("evidenceRevision")
        if prior and prior_revision == evidence_revision:
            requests.append(dict(prior))
            continue
        probe_type, target = policy
        request = {
            "probeRequestId": str((prior or {}).get("probeRequestId") or f"TPR-{gap_id}-{hashlib.sha1(evidence_revision.encode()).hexdigest()[:8].upper()}"),
            "sourceGapId": gap_id, "entityId": gap.get("subjectEntityId"),
            "ownerChapterId": gap.get("chapterId"), "schemaSlot": gap.get("schemaSlot"),
            "probeType": probe_type, "targetProperty": target,
            "status": "pending", "attemptCount": int((latest or {}).get("attemptCount") or 0),
            "searchedWindows": [], "searchedTimeRange": None, "evidenceCoverage": {},
            "exhaustionReason": None, "evidenceRevision": evidence_revision,
            "sourceEvidenceRevision": evidence_revision,
        }
        for field in ("anchor", "searchWindow", "evidenceQuestion"):
            if gap.get(field) is not None:
                request[field] = gap[field]
        requests.append(request)
    return {"requests": requests, "ineligibleGapIds": ineligible}


def discover_candidate_windows(request: dict[str, Any], index: dict[str, Any]) -> list[dict[str, Any]]:
    """Intersect the requested range with low-cost activity candidates."""
    search = request.get("searchWindow") if isinstance(request.get("searchWindow"), dict) else {}
    start = float(search.get("start", 0.0))
    end = float(search.get("end", index.get("duration", start)))
    if end < start:
        raise ValueError("search window end must not precede start")
    result = []
    for source in index.get("activityWindows") or []:
        left, right = max(start, float(source.get("start", start))), min(end, float(source.get("end", end)))
        if right <= left:
            continue
        result.append({
            "start": round(left, 3), "end": round(right, 3),
            "score": float(source.get("score") or 0), "source": "activity_index",
        })
    return sorted(result, key=lambda item: (item["start"], item["end"]))


def build_temporal_entity_track_candidate(
    request: dict[str, Any], observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assign conservative identity authority to an already discovered track."""
    probe_id = str(request.get("probeRequestId") or "TPR-unknown")
    requested_entity = request.get("entityId")
    ambiguous = any(int(item.get("sameClassCandidateCount") or 1) > 1 for item in observations)
    if not observations:
        identity = "lost"
    elif ambiguous:
        identity = "ambiguous"
    else:
        tracks = {str(item.get("trackId")) for item in observations if item.get("trackId")}
        anchored = all(item.get("anchorEntityMatch") is True for item in observations)
        if anchored and len(tracks) == 1:
            identity = "confirmed"
        else:
            similarities = [float(item.get("appearanceSimilarity") or 0) for item in observations]
            classes = {str(item.get("class") or "") for item in observations}
            identity = "probable" if len(classes) == 1 and similarities and min(similarities) >= .75 else "ambiguous"
    confidence = {
        "confirmed": .95, "probable": .75, "ambiguous": .35, "lost": 0.0,
    }[identity]
    result = {
        "trackCandidateId": f"TTC-{probe_id.removeprefix('TPR-')}",
        "entityId": requested_entity if identity == "confirmed" else None,
        "candidateEntityId": requested_entity if identity != "confirmed" else None,
        "observations": [dict(item) for item in observations],
        "trackConfidence": confidence, "identityStatus": identity,
        "publicationEligibility": "review_required" if identity == "probable" else "blocked" if identity in {"ambiguous", "lost"} else "evidence_only",
        "ruleCandidateEligible": identity in {"confirmed", "probable"}, "gaps": [],
    }
    if identity in {"ambiguous", "lost"}:
        result["gaps"] = [{
            "gapId": f"GAP-{probe_id}-identity", "gapKind": "identity_unresolved",
            "status": "unresolved", "subjectEntityId": None,
            "candidateEntityId": requested_entity, "blockingScope": "review_only",
        }]
    return result


def _mean_vector(observations: list[dict[str, Any]], field: str) -> tuple[float, float]:
    vectors = [item.get(field) for item in observations if isinstance(item.get(field), (list, tuple)) and len(item[field]) == 2]
    if not vectors:
        return 0.0, 0.0
    return sum(float(item[0]) for item in vectors) / len(vectors), sum(float(item[1]) for item in vectors) / len(vectors)


def _magnitude(vector: tuple[float, float]) -> float:
    return math.hypot(*vector)


def analyze_persistent_state(request: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    """Describe screen-space persistence without asserting a gameplay rule."""
    observations = list(track.get("observations") or [])
    located_observations = []
    for item in observations:
        bbox = item.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            located_observations.append((
                item,
                ((float(bbox[0]) + float(bbox[2])) / 2, (float(bbox[1]) + float(bbox[3])) / 2),
            ))
    centers = [center for _item, center in located_observations]
    deltas = [(right[0] - left[0], right[1] - left[1]) for left, right in zip(centers, centers[1:])]
    entity_vector = (
        sum(item[0] for item in deltas) / len(deltas),
        sum(item[1] for item in deltas) / len(deltas),
    ) if deltas else (0.0, 0.0)
    background = _mean_vector(observations, "backgroundDelta")
    ui = _mean_vector(observations, "uiDelta")
    has_reference_measurements = bool(observations) and all(
        isinstance(item.get("backgroundDelta"), (list, tuple)) and len(item["backgroundDelta"]) == 2
        and isinstance(item.get("uiDelta"), (list, tuple)) and len(item["uiDelta"]) == 2
        for item in observations
    )
    entity_motion, background_motion, ui_motion = map(_magnitude, (entity_vector, background, ui))
    crosses_scene = len({item.get("sceneId") for item, _center in located_observations}) > 1
    aligned = entity_motion > 1.5 and background_motion > 1.5 and _magnitude((entity_vector[0] - background[0], entity_vector[1] - background[1])) <= max(2.0, background_motion * .35)
    if crosses_scene or len(centers) < 2 or not has_reference_measurements:
        reference = "unknown"
    elif aligned and ui_motion > 1.5:
        reference = "camera_moving"
    elif background_motion > 1.5 and ui_motion <= 1.5:
        reference = "background_scrolling"
    elif background_motion <= 1.5:
        reference = "stable"
    else:
        reference = "unknown"
    consistent = sum(1 for delta in deltas if _magnitude(delta) > 1.0 and (delta[0] * entity_vector[0] + delta[1] * entity_vector[1]) >= 0)
    persistence = consistent / len(deltas) if deltas else 0.0
    timestamped_rates = []
    for (left, _left_center), (right, _right_center), delta in zip(
        located_observations, located_observations[1:], deltas,
    ):
        elapsed = float(right.get("timestamp") or 0) - float(left.get("timestamp") or 0)
        if elapsed > 0:
            timestamped_rates.append(round(_magnitude(delta) / elapsed, 6))
    rate_change = False
    if len(timestamped_rates) >= 4:
        midpoint = len(timestamped_rates) // 2
        early = sum(timestamped_rates[:midpoint]) / midpoint
        late_values = timestamped_rates[midpoint:]
        late = sum(late_values) / len(late_values)
        baseline = max(min(early, late), 1e-6)
        rate_change = max(early, late) / baseline >= 1.5
    probe_id = str(request.get("probeRequestId") or "TPR-unknown")
    observation = {
        "observationId": f"OBS-{probe_id.removeprefix('TPR-')}",
        "observationType": "VisualPositionChange" if entity_motion > 1.0 else "VisualMotionRepresentation",
        "entityId": track.get("entityId"), "candidateEntityId": track.get("candidateEntityId"),
        "identityStatus": track.get("identityStatus", "unknown"),
        "propertyPath": str(request.get("targetProperty") or "position"),
        "samples": [
            {"frameId": item.get("frameId"), "timestamp": item.get("timestamp"), "position": list(center)}
            for item, center in located_observations
        ],
        "temporalPattern": "moving" if entity_motion > 1.0 else "stable",
        "referenceFrameStatus": reference, "persistenceScore": round(persistence, 3),
        "confidence": min(float(track.get("trackConfidence") or 0), .95),
    }
    candidate = None
    gaps = []
    if reference == "stable" and entity_motion > 1.0 and track.get("identityStatus") in {"confirmed", "probable"}:
        candidate = {
            "candidateId": f"MOVE-{observation['observationId']}",
            "entityId": track.get("entityId"), "candidateEntityId": track.get("candidateEntityId"),
            "sourceObservationId": observation["observationId"], "status": "candidate",
            "publicationEligibility": "review_required",
        }
    elif reference != "stable":
        gaps.append({
            "gapId": f"GAP-{probe_id}-reference", "gapKind": "coordinate_frame_unknown" if reference in {"unknown", "camera_moving"} else "movement_driver_unknown",
            "status": "unresolved", "subjectEntityId": track.get("entityId"),
            "candidateEntityId": track.get("candidateEntityId"), "blockingScope": "review_only",
        })
    temporal_facts = []
    rule_candidates = []
    speed_change_candidate = None
    speed_change_gaps = []
    if len(observation["samples"]) >= 2:
        fact = _temporal_fact(
            request, track, predicate="visual_position_changed",
            before=observation["samples"][0]["position"], after=observation["samples"][-1]["position"],
            evidence=[item for item, _center in located_observations], pattern=observation["temporalPattern"],
        )
        fact.update({
            "referenceFrameStatus": reference, "persistenceScore": observation["persistenceScore"],
            "trackCandidateId": track.get("trackCandidateId"),
        })
        temporal_facts.append(fact)
        if candidate is not None and request.get("targetProperty") != "movement_rate":
            suffix = probe_id.removeprefix("TPR-")
            rule_candidates.append({
                "ruleId": f"TRC-{suffix}-movement", "semanticKey": f"temporal:{suffix}:movement",
                "ownerChapterId": request.get("ownerChapterId"), "canonicalOwner": request.get("ownerChapterId"),
                "definitionMode": "full_definition", "ruleType": "logic",
                "schemaSlot": request.get("schemaSlot") or "movement_direction",
                "subject": str(track.get("entityId") or track.get("candidateEntityId") or "unresolved_entity"),
                "behavior": "当前视频样本观察到对象持续发生相对位置变化。",
                "trigger": None, "conditions": [], "result": None, "stateChange": "position_changed",
                "exitCondition": None, "exception": None, "parameterRefs": [],
                "evidenceIds": list(fact["evidenceIds"]), "sourceFactIds": [fact["factId"]],
                "reviewStatus": "unreviewed", "intent": "Movement",
                "authorityStatus": "observed_unreviewed", "inferenceLevel": "observed",
                "confidence": observation["confidence"], "candidateKind": "temporal_rule_candidate",
                "candidateEntityId": track.get("candidateEntityId"),
            })
        if rate_change and track.get("identityStatus") in {"confirmed", "probable"}:
            midpoint = len(timestamped_rates) // 2
            early_rate = round(sum(timestamped_rates[:midpoint]) / midpoint, 6)
            late_rate = round(sum(timestamped_rates[midpoint:]) / len(timestamped_rates[midpoint:]), 6)
            speed_change_candidate = {
                "candidateId": f"RATE-{observation['observationId']}",
                "candidateKind": "MovementSpeedChangeCandidate",
                "entityId": track.get("entityId"), "candidateEntityId": track.get("candidateEntityId"),
                "sourceObservationId": observation["observationId"],
                "phenomenonStatus": "observed", "triggerStatus": "unresolved",
                "observedRates": timestamped_rates,
                "valueAuthority": "observed_run_value",
                "referenceFrameStatus": reference,
                "observationBasis": "entity_screen_position",
                "publicationEligibility": "review_required",
            }
            rate_fact = _temporal_fact(
                request, track, predicate="movement_rate_changed",
                before=early_rate, after=late_rate,
                evidence=[item for item, _center in located_observations],
                pattern="rate_changed",
            )
            rate_fact.update({
                "propertyPath": "movement_rate", "valueAuthority": "observed_run_value",
                "triggerStatus": "unresolved", "referenceFrameStatus": reference,
            })
            temporal_facts.append(rate_fact)
            suffix = probe_id.removeprefix("TPR-")
            rule_candidates.append({
                "ruleId": f"TRC-{suffix}-speed-change",
                "semanticKey": f"temporal:{suffix}:movement_rate_change",
                "ownerChapterId": request.get("ownerChapterId"),
                "canonicalOwner": request.get("ownerChapterId"),
                "definitionMode": "full_definition", "ruleType": "logic",
                "schemaSlot": "movement_rate_change", "intent": "Movement",
                "subject": str(track.get("entityId") or track.get("candidateEntityId") or "移动对象"),
                "behavior": "移动速度会在关卡过程中发生阶段性变化。",
                "stateChange": "movement_rate_changed", "triggerStatus": "unresolved",
                "referenceFrameStatus": reference,
                "evidenceIds": list(rate_fact["evidenceIds"]), "sourceFactIds": [rate_fact["factId"]],
                "reviewStatus": "unreviewed", "authorityStatus": "observed_unreviewed",
                "inferenceLevel": "observed", "confidence": observation["confidence"],
                "candidateKind": "temporal_rule_candidate",
                "candidateSubtype": "MovementSpeedChangeCandidate",
                "candidateEntityId": track.get("candidateEntityId"),
            })
            speed_change_gaps.append({
                "gapId": f"GAP-{probe_id}-speed-trigger", "gapKind": "speed_change_trigger_unknown",
                "chapterId": request.get("ownerChapterId"), "schemaSlot": "movement_rate_change",
                "status": "reviewed_open", "gapDomain": "planning", "specificity": "concrete_decision",
                "subjectEntityId": track.get("entityId"), "candidateEntityId": track.get("candidateEntityId"),
                "question": "速度变化的触发条件待确认。", "applicabilityStatus": "applicable",
            })
    return {
        "observation": observation, "movementCandidate": candidate,
        "movementSpeedChangeCandidate": speed_change_candidate, "speedChangeGaps": speed_change_gaps,
        "temporalFacts": temporal_facts, "ruleCandidates": rule_candidates, "gaps": [*gaps, *speed_change_gaps],
    }


def _temporal_fact(
    request: dict[str, Any], track: dict[str, Any], *, predicate: str,
    before: Any, after: Any, evidence: list[dict[str, Any]], pattern: str,
) -> dict[str, Any]:
    probe_id = str(request.get("probeRequestId") or "TPR-unknown")
    timestamps = [float(item["timestamp"]) for item in evidence]
    confirmed_identity = track.get("identityStatus") == "confirmed"
    return {
        "factId": f"TF-{probe_id.removeprefix('TPR-')}-{predicate}",
        "subject": str(request.get("entityId") or "unresolved_entity"),
        "entityId": track.get("entityId") if confirmed_identity else None,
        "candidateEntityId": request.get("entityId") if not confirmed_identity else None,
        "predicate": predicate, "object": pattern, "propertyPath": request.get("targetProperty"),
        "beforeValue": before, "afterValue": after,
        "evidenceIds": [str(item.get("frameId")) for item in evidence if item.get("frameId")],
        "evidenceTimestamps": timestamps, "timeRange": [min(timestamps), max(timestamps)],
        "evidenceWindow": [min(timestamps), max(timestamps)],
        "sourceKind": "auxiliary_video", "sourceVideoId": track.get("sourceVideoId"),
        "observationMode": "targeted_temporal_probe", "temporalPattern": pattern,
        "referenceFrameStatus": "unknown", "probeRequestId": probe_id,
        "identityStatus": track.get("identityStatus", "unknown"),
        "confidence": float(track.get("trackConfidence") or .8),
        "inferenceLevel": "observed", "reviewStatus": "unreviewed",
    }


def analyze_lifecycle_boundary(request: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    """Record an appearance boundary without interpreting its spawn mechanism."""
    observations = sorted(track.get("observations") or [], key=lambda item: float(item.get("timestamp") or 0))
    transition = next(
        ((left, right) for left, right in zip(observations, observations[1:])
         if left.get("present") is False and right.get("present") is True),
        None,
    )
    if transition is None:
        return {"temporalFacts": [], "ruleCandidates": [], "gaps": [{
            "gapId": f"GAP-{request.get('probeRequestId')}-boundary", "gapKind": "missing_evidence",
            "status": "not_observed", "subjectEntityId": track.get("entityId"), "blockingScope": "review_only",
        }]}
    fact = _temporal_fact(
        request, track, predicate="first_appearance", before=False, after=True,
        evidence=list(transition), pattern="appeared",
    )
    return {"temporalFacts": [fact], "ruleCandidates": [], "gaps": []}


def analyze_repeated_events(
    request: dict[str, Any], track: dict[str, Any], events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report sample intervals without claiming configuration or formula authority."""
    ordered = sorted(events, key=lambda item: float(item.get("timestamp") or 0))
    timestamps = [float(item.get("timestamp") or 0) for item in ordered]
    intervals = [round(right - left, 3) for left, right in zip(timestamps, timestamps[1:])]
    observation = {
        "observationId": f"REPEAT-{str(request.get('probeRequestId') or '').removeprefix('TPR-')}",
        "entityId": track.get("entityId") if track.get("identityStatus") == "confirmed" else None,
        "candidateEntityId": request.get("entityId") if track.get("identityStatus") != "confirmed" else None,
        "eventProperty": request.get("targetProperty"), "eventTimestamps": timestamps,
        "observedIntervals": intervals, "parameterSource": "observed_value",
        "observationMode": "targeted_temporal_probe", "reviewStatus": "unreviewed",
    }
    facts = []
    if len(ordered) >= 2:
        facts.append(_temporal_fact(
            request, track, predicate="repeated_event_observed", before=timestamps[0], after=timestamps[-1],
            evidence=ordered, pattern="changed",
        ))
    return {"repeatedEventObservation": observation, "temporalFacts": facts, "ruleCandidates": [], "gaps": []}


def finalize_probe_request(
    request: dict[str, Any], result: dict[str, Any], *, searched_windows: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = dict(request)
    normalized_windows = [
        [float(item["start"]), float(item["end"])] for item in searched_windows
        if isinstance(item, dict) and "start" in item and "end" in item
    ]
    updated["searchedWindows"] = normalized_windows
    updated["searchedTimeRange"] = (
        [min(item[0] for item in normalized_windows), max(item[1] for item in normalized_windows)]
        if normalized_windows else None
    )
    observed = bool(result.get("temporalFacts") or result.get("observations") or result.get("repeatedEventObservation"))
    updated["status"] = "completed" if observed else "exhausted"
    updated["evidenceCoverage"] = {
        "reviewedWindowCount": len(normalized_windows),
        "evidenceTimestampCount": sum(len(item.get("evidenceTimestamps") or []) for item in result.get("temporalFacts") or []),
    }
    updated["exhaustionReason"] = None if observed else "no_observation_in_reviewed_video"
    return {
        "request": updated,
        "gapUpdate": None if observed else {"gapId": request.get("sourceGapId"), "status": "not_observed"},
    }


def temporal_evidence_coverage(
    requests: list[dict[str, Any]], *, ineligible_gap_count: int,
) -> dict[str, int]:
    statuses = [str(item.get("status") or "pending") for item in requests]
    return {
        "eligibleProbeCount": len(requests),
        "completedProbeCount": statuses.count("completed"),
        "unresolvedProbeCount": statuses.count("pending") + statuses.count("active"),
        "exhaustedProbeCount": statuses.count("exhausted"),
        "ineligibleGapCount": int(ineligible_gap_count),
    }


def mechanic_closure_coverage(closures: list[dict[str, Any]]) -> dict[str, int | float]:
    total = resolved = 0
    for closure in closures:
        slots = closure.get("slots") or {}
        for slot in closure.get("requiredSlots") or []:
            total += 1
            if slots.get(slot) in {"confirmed", "resolved"}:
                resolved += 1
    return {
        "resolvedRequiredResponsibilityCount": resolved,
        "applicableRequiredResponsibilityCount": total,
        "coverage": round(resolved / total, 4) if total else 1.0,
    }


def run_targeted_temporal_probe(
    request: dict[str, Any], *, temporal_index: dict[str, Any],
    track_candidate: dict[str, Any], events: list[dict[str, Any]] | None = None,
    lesson_registry=None,
) -> dict[str, Any]:
    """Run one bounded probe against pre-discovered frame/track evidence."""
    if request.get("status") not in {"pending", "active"}:
        raise ValueError("probe is not runnable for the current evidence revision")
    if lesson_registry is None:
        from .system_lesson_registry import load_system_lesson_registry
        lesson_registry = load_system_lesson_registry()
    active = dict(request)
    active["status"] = "active"
    active["attemptCount"] = int(active.get("attemptCount") or 0) + 1
    windows = discover_candidate_windows(active, temporal_index)
    probe_type = active.get("probeType")
    if probe_type == "PersistentStateProbe":
        analysis = analyze_persistent_state(active, track_candidate)
        payload = {
            "temporalFacts": analysis.get("temporalFacts") or [],
            "ruleCandidates": analysis.get("ruleCandidates") or [],
            "observations": [analysis["observation"]] if analysis.get("observation") else [],
            "gaps": analysis.get("gaps") or [],
            "movementCandidates": [analysis["movementCandidate"]] if analysis.get("movementCandidate") else [],
        }
        if not lesson_registry.is_policy_enabled(
            "temporal.persistent_state", "temporal_probe"
        ):
            payload["ruleCandidates"] = [
                rule for rule in payload["ruleCandidates"]
                if rule.get("candidateSubtype") != "MovementSpeedChangeCandidate"
            ]
            payload["temporalFacts"] = [
                fact for fact in payload["temporalFacts"]
                if fact.get("predicate") != "movement_rate_changed"
            ]
            payload["gaps"] = [
                gap for gap in payload["gaps"]
                if gap.get("gapKind") != "speed_change_trigger_unknown"
            ]
    elif probe_type == "LifecycleBoundaryProbe":
        analysis = analyze_lifecycle_boundary(active, track_candidate)
        payload = {**analysis, "observations": []}
    elif probe_type == "TemporalProcessProbe":
        analysis = analyze_repeated_events(active, track_candidate, events or [])
        payload = {
            **analysis, "observations": [analysis["repeatedEventObservation"]],
        }
    else:
        raise ValueError("unknown targeted temporal probe type")
    finalized = finalize_probe_request(active, payload, searched_windows=windows)
    return {**payload, **finalized}


def build_requirement_temporal_index(
    video_path: Path,
    progress: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Build a read-only full-timeline index for later Requirement queries."""
    metadata, scene_changes, sample_times = inspect_video(video_path, progress or (lambda *_: None))
    return {
        "sourceVideo": str(video_path),
        "duration": metadata["duration"],
        "fps": metadata["fps"],
        "frameCount": metadata["frameCount"],
        "fullTimelineScanned": True,
        "scanSampleCount": metadata["scanSamples"],
        "candidateSampleTimes": sample_times,
        "sceneChanges": scene_changes,
        "activityWindows": metadata["activityWindows"],
        "exhaustionEligible": False,
        "exhaustionBlockers": [
            "requirement_specific_candidates_not_reviewed",
            "anchor_windows_not_reviewed",
            "counterexamples_not_reviewed",
        ],
    }


def build_probe_coverage(
    index: dict[str, Any],
    *,
    requirement_id: str,
    anchor_windows_scanned: bool,
    candidate_windows_expanded: bool,
    counterexamples_reviewed: bool,
    no_new_candidate_windows: bool,
    audit_trail_recorded: bool,
) -> dict[str, Any]:
    fields = {
        "fullSelectedSourceScanned": index.get("fullTimelineScanned") is True,
        "allAnchorWindowsScanned": anchor_windows_scanned,
        "allCandidateWindowsExpanded": candidate_windows_expanded and counterexamples_reviewed,
        "noNewCandidateWindows": no_new_candidate_windows,
        "auditTrailRecorded": audit_trail_recorded,
    }
    return {
        "probeCoverageId": f"PRB-{requirement_id.removeprefix('REQ-')}",
        "requirementId": requirement_id,
        **fields,
        "exhaustionEligible": all(fields.values()),
    }
