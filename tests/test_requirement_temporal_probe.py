from backend import requirement_temporal_probe as probe
from backend.planning_content_models import AtomicFact


def test_temporal_atomic_fact_serializes_observation_authority_and_lineage():
    fact = AtomicFact(
        "TF-1", "载具", "position_changed", "发生相对位移", {}, ("VF-1", "VF-2"), .9,
        entity_id="vehicle", property_path="position", before_value=[10, 10], after_value=[20, 10],
        time_range=(1.0, 2.0), evidence_timestamps=(1.0, 2.0), source_kind="auxiliary_video",
        observation_mode="targeted_temporal_probe", inference_level="observed",
        temporal_pattern="moving", reference_frame_status="stable", persistence_score=.8,
        probe_request_id="TPR-1", source_video_id="video-v1", evidence_window=(0.5, 2.5),
        track_candidate_id="TTC-1", identity_status="confirmed",
    ).to_dict()

    assert fact["reviewStatus"] == "unreviewed"
    assert fact["temporalPattern"] == "moving"
    assert fact["referenceFrameStatus"] == "stable"
    assert fact["probeRequestId"] == "TPR-1"
    assert fact["evidenceWindow"] == [0.5, 2.5]


def test_only_video_resolvable_unresolved_gaps_create_pending_probe_requests():
    gaps = [
        {"gapId": "G-MOVE", "gapKind": "movement_driver_unknown", "status": "unresolved", "subjectEntityId": "vehicle"},
        {"gapId": "G-WEIGHT", "gapKind": "parameter_unknown", "intent": "WeightRule", "status": "unresolved"},
        {"gapId": "G-DONE", "gapKind": "missing_lifecycle_node", "intent": "Spawn", "status": "resolved", "subjectEntityId": "enemy"},
    ]

    result = probe.build_targeted_probe_requests(gaps, evidence_revision="video-v1")

    assert [item["sourceGapId"] for item in result["requests"]] == ["G-MOVE"]
    assert result["requests"][0]["status"] == "pending"
    assert result["requests"][0]["probeType"] == "PersistentStateProbe"
    assert result["requests"][0]["targetProperty"] == "position"
    assert result["ineligibleGapIds"] == ["G-WEIGHT"]


def test_completed_or_exhausted_probe_is_not_reactivated_without_new_evidence():
    gap = {"gapId": "G-SPAWN", "gapKind": "missing_lifecycle_node", "intent": "Spawn", "status": "unresolved", "subjectEntityId": "enemy"}
    existing = [{
        "probeRequestId": "TPR-G-SPAWN", "sourceGapId": "G-SPAWN", "status": "exhausted",
        "evidenceRevision": "video-v1", "attemptCount": 1, "searchedWindows": [[0.0, 10.0]],
        "searchedTimeRange": [0.0, 10.0], "evidenceCoverage": {"reviewedWindowCount": 1},
        "exhaustionReason": "no_observation_in_reviewed_video",
    }]

    unchanged = probe.build_targeted_probe_requests([gap], existing_requests=existing, evidence_revision="video-v1")
    refreshed = probe.build_targeted_probe_requests([gap], existing_requests=existing, evidence_revision="video-v2")

    assert unchanged["requests"] == existing
    assert refreshed["requests"][0]["status"] == "pending"
    assert refreshed["requests"][0]["attemptCount"] == 1
    assert refreshed["requests"][0]["evidenceRevision"] == "video-v2"


def test_candidate_windows_are_bounded_by_request_and_low_cost_activity_index():
    request = {"searchWindow": {"start": 4.0, "end": 12.0}, "anchor": {"timestamp": 8.0}}
    index = {"activityWindows": [
        {"start": 1.0, "end": 2.0, "score": .8},
        {"start": 5.0, "end": 7.0, "score": .7},
        {"start": 10.0, "end": 14.0, "score": .9},
    ]}

    assert probe.discover_candidate_windows(request, index) == [
        {"start": 5.0, "end": 7.0, "score": .7, "source": "activity_index"},
        {"start": 10.0, "end": 12.0, "score": .9, "source": "activity_index"},
    ]


def test_confirmed_and_probable_identity_have_different_entity_authority():
    request = {"probeRequestId": "TPR-1", "entityId": "vehicle"}
    confirmed = probe.build_temporal_entity_track_candidate(request, [
        {"frameId": "F1", "timestamp": 1.0, "bbox": [0, 0, 10, 10], "class": "actor", "trackId": "T1", "anchorEntityMatch": True},
        {"frameId": "F2", "timestamp": 2.0, "bbox": [2, 0, 12, 10], "class": "actor", "trackId": "T1", "anchorEntityMatch": True},
    ])
    probable = probe.build_temporal_entity_track_candidate(request, [
        {"frameId": "F1", "timestamp": 1.0, "bbox": [0, 0, 10, 10], "class": "actor", "trackId": "T1", "appearanceSimilarity": .9},
        {"frameId": "F2", "timestamp": 2.0, "bbox": [2, 0, 12, 10], "class": "actor", "trackId": "T2", "appearanceSimilarity": .88},
    ])

    assert confirmed["identityStatus"] == "confirmed" and confirmed["entityId"] == "vehicle"
    assert confirmed["candidateEntityId"] is None
    assert probable["identityStatus"] == "probable" and probable["entityId"] is None
    assert probable["candidateEntityId"] == "vehicle"
    assert probable["publicationEligibility"] == "review_required"


def test_multiple_same_class_entities_are_ambiguous_and_only_create_identity_gap():
    result = probe.build_temporal_entity_track_candidate(
        {"probeRequestId": "TPR-2", "entityId": "enemy"},
        [{"frameId": "F1", "timestamp": 1.0, "bbox": [0, 0, 10, 10], "class": "actor", "sameClassCandidateCount": 2}],
    )

    assert result["identityStatus"] == "ambiguous"
    assert result["entityId"] is None
    assert result["ruleCandidateEligible"] is False
    assert result["gaps"] == [{
        "gapId": "GAP-TPR-2-identity", "gapKind": "identity_unresolved",
        "status": "unresolved", "subjectEntityId": None, "candidateEntityId": "enemy",
        "blockingScope": "review_only",
    }]


def _track(*centers, background=(0.0, 0.0), ui=(0.0, 0.0)):
    return {
        "trackCandidateId": "TTC-1", "entityId": "entity-1", "candidateEntityId": None,
        "identityStatus": "confirmed", "trackConfidence": .95,
        "observations": [
            {"frameId": f"F{index}", "timestamp": float(index), "sceneId": 1,
             "bbox": [x - 5, y - 5, x + 5, y + 5],
             "backgroundDelta": list(background), "uiDelta": list(ui)}
            for index, (x, y) in enumerate(centers, 1)
        ],
    }


def test_stable_reference_frame_allows_movement_candidate_but_never_rule():
    result = probe.analyze_persistent_state(
        {"probeRequestId": "TPR-MOVE", "targetProperty": "position"},
        _track((10, 10), (20, 10), (30, 10)),
    )

    assert result["observation"]["observationType"] == "VisualPositionChange"
    assert result["observation"]["referenceFrameStatus"] == "stable"
    assert result["movementCandidate"]["status"] == "candidate"
    assert result["ruleCandidates"][0]["reviewStatus"] == "unreviewed"
    assert result["ruleCandidates"][0]["candidateKind"] == "temporal_rule_candidate"


def test_stable_low_then_high_rate_creates_speed_change_candidate_without_config_or_trigger():
    result = probe.analyze_persistent_state(
        {"probeRequestId": "TPR-RATE", "targetProperty": "position"},
        _track((0, 10), (2, 10), (4, 10), (14, 10), (24, 10)),
    )

    candidate = result["movementSpeedChangeCandidate"]
    assert candidate["candidateKind"] == "MovementSpeedChangeCandidate"
    assert candidate["phenomenonStatus"] == "observed"
    assert candidate["triggerStatus"] == "unresolved"
    assert "configuredSpeed" not in candidate
    assert "trigger" not in candidate
    assert result["speedChangeGaps"][0]["gapKind"] == "speed_change_trigger_unknown"
    assert result["temporalFacts"][-1]["predicate"] == "movement_rate_changed"
    assert result["ruleCandidates"][-1]["schemaSlot"] == "movement_rate_change"
    assert result["ruleCandidates"][-1]["reviewStatus"] == "unreviewed"


def test_entity_and_background_common_motion_is_camera_motion_not_entity_movement():
    result = probe.analyze_persistent_state(
        {"probeRequestId": "TPR-CAMERA", "targetProperty": "position"},
        _track((10, 10), (20, 10), (30, 10), background=(10.0, 0.0), ui=(10.0, 0.0)),
    )

    assert result["observation"]["referenceFrameStatus"] == "camera_moving"
    assert result["movementCandidate"] is None
    assert result["gaps"][0]["gapKind"] == "coordinate_frame_unknown"
    assert result["ruleCandidates"] == []


def test_background_scroll_is_representation_evidence_not_gameplay_movement():
    result = probe.analyze_persistent_state(
        {"probeRequestId": "TPR-SCROLL", "targetProperty": "position"},
        _track((10, 10), (10.5, 10), (10, 10), background=(-8.0, 0.0), ui=(0.0, 0.0)),
    )

    assert result["observation"]["referenceFrameStatus"] == "background_scrolling"
    assert result["movementCandidate"] is None
    assert result["ruleCandidates"] == []
    assert all("forward" not in str(value).lower() for value in result.values())


def test_missing_reference_frame_measurements_remain_unknown_not_stable():
    track = _track((10, 10), (20, 10), (30, 10))
    for item in track["observations"]:
        item.pop("backgroundDelta")
        item.pop("uiDelta")

    result = probe.analyze_persistent_state(
        {"probeRequestId": "TPR-NO-REFERENCE", "targetProperty": "position"}, track,
    )

    assert result["observation"]["referenceFrameStatus"] == "unknown"
    assert result["movementCandidate"] is None
    assert result["ruleCandidates"] == []


def test_unknown_reference_can_raise_review_only_speed_phenomenon_without_movement_rule():
    track = _track((0, 10), (2, 10), (4, 10), (14, 10), (24, 10))
    for item in track["observations"]:
        item.pop("backgroundDelta")
        item.pop("uiDelta")

    result = probe.analyze_persistent_state(
        {"probeRequestId": "TPR-RATE-UNKNOWN", "targetProperty": "movement_rate"}, track,
    )

    assert result["observation"]["referenceFrameStatus"] == "unknown"
    assert result["movementCandidate"] is None
    assert result["movementSpeedChangeCandidate"]["publicationEligibility"] == "review_required"
    assert result["movementSpeedChangeCandidate"]["referenceFrameStatus"] == "unknown"
    assert result["ruleCandidates"][0]["reviewStatus"] == "unreviewed"


def test_first_appearance_is_temporal_fact_and_never_spawn_rule():
    result = probe.analyze_lifecycle_boundary(
        {"probeRequestId": "TPR-SPAWN", "sourceGapId": "G-SPAWN", "entityId": "enemy", "targetProperty": "first_appearance"},
        {"sourceVideoId": "video-v1", "identityStatus": "confirmed", "entityId": "enemy", "observations": [
            {"frameId": "VF-1", "timestamp": 4.0, "present": False},
            {"frameId": "VF-2", "timestamp": 5.0, "present": True},
        ]},
    )

    fact = result["temporalFacts"][0]
    assert fact["predicate"] == "first_appearance"
    assert fact["beforeValue"] is False and fact["afterValue"] is True
    assert fact["reviewStatus"] == "unreviewed"
    assert result["ruleCandidates"] == []
    assert all(term not in str(result) for term in ("spawn_interval", "spawn_source", "spawn_count"))


def test_repeated_events_report_observed_intervals_not_configured_interval():
    result = probe.analyze_repeated_events(
        {"probeRequestId": "TPR-ATTACK", "entityId": "entity-1", "targetProperty": "attack_event"},
        {"sourceVideoId": "video-v1", "identityStatus": "confirmed", "entityId": "entity-1"},
        [
            {"frameId": "VF-1", "timestamp": 1.0},
            {"frameId": "VF-2", "timestamp": 2.1},
            {"frameId": "VF-3", "timestamp": 3.0},
        ],
    )

    assert result["repeatedEventObservation"]["observedIntervals"] == [1.1, .9]
    assert result["repeatedEventObservation"]["parameterSource"] == "observed_value"
    assert "configuredInterval" not in result["repeatedEventObservation"]
    assert result["ruleCandidates"] == []


def test_probe_exhaustion_records_search_and_prevents_same_evidence_reactivation():
    request = {
        "probeRequestId": "TPR-G1", "sourceGapId": "G1", "probeType": "LifecycleBoundaryProbe",
        "targetProperty": "first_appearance", "status": "active", "attemptCount": 1,
        "evidenceRevision": "video-v1", "searchedWindows": [], "evidenceCoverage": {},
    }
    finalized = probe.finalize_probe_request(
        request, {"temporalFacts": [], "ruleCandidates": [], "gaps": []},
        searched_windows=[{"start": 0.0, "end": 10.0}],
    )

    assert finalized["request"]["status"] == "exhausted"
    assert finalized["request"]["searchedTimeRange"] == [0.0, 10.0]
    assert finalized["gapUpdate"] == {"gapId": "G1", "status": "not_observed"}
    rebuilt = probe.build_targeted_probe_requests(
        [{"gapId": "G1", "gapKind": "missing_lifecycle_node", "intent": "Spawn", "status": "unresolved", "subjectEntityId": "enemy"}],
        existing_requests=[finalized["request"]], evidence_revision="video-v1",
    )
    assert rebuilt["requests"][0]["status"] == "exhausted"


def test_temporal_coverage_is_count_based_and_mechanic_closure_excludes_optional_slots():
    temporal = probe.temporal_evidence_coverage([
        {"status": "completed"}, {"status": "exhausted"}, {"status": "pending"}, {"status": "active"},
    ], ineligible_gap_count=3)
    closure = probe.mechanic_closure_coverage([
        {"requiredSlots": ["Spawn", "Movement"], "slots": {"Spawn": "confirmed", "Movement": "unresolved", "Reward": "not_applicable"}},
    ])

    assert temporal == {
        "eligibleProbeCount": 4, "completedProbeCount": 1, "unresolvedProbeCount": 2,
        "exhaustedProbeCount": 1, "ineligibleGapCount": 3,
    }
    assert closure == {"resolvedRequiredResponsibilityCount": 1, "applicableRequiredResponsibilityCount": 2, "coverage": .5}


def test_targeted_probe_orchestrator_uses_candidate_windows_and_returns_auditable_result():
    request = {
        "probeRequestId": "TPR-1", "sourceGapId": "G1", "probeType": "PersistentStateProbe",
        "targetProperty": "position", "status": "pending", "attemptCount": 0,
        "searchWindow": {"start": 0.0, "end": 4.0}, "evidenceRevision": "video-v1",
    }
    track = _track((10, 10), (20, 10), (30, 10))
    result = probe.run_targeted_temporal_probe(
        request, temporal_index={"activityWindows": [{"start": 1.0, "end": 3.0, "score": .8}]},
        track_candidate=track,
    )

    assert result["request"]["status"] == "completed"
    assert result["request"]["attemptCount"] == 1
    assert result["request"]["searchedWindows"] == [[1.0, 3.0]]
    assert result["temporalFacts"][0]["probeRequestId"] == "TPR-1"


def test_temporal_index_is_not_probe_exhaustion(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "inspect_video", lambda *_args: (
        {"duration": 10.0, "fps": 30.0, "frameCount": 300, "scanSamples": 32,
         "activityWindows": [{"start": 1.0, "end": 2.0}]},
        [{"time": 1.5, "score": 0.8}], [0.0, 1.5, 9.9],
    ))
    index = probe.build_requirement_temporal_index(tmp_path / "source.mp4")
    assert index["fullTimelineScanned"] is True
    assert index["exhaustionEligible"] is False
    assert "counterexamples_not_reviewed" in index["exhaustionBlockers"]


def test_coverage_requires_counterexample_review_and_candidate_convergence():
    index = {"fullTimelineScanned": True}
    incomplete = probe.build_probe_coverage(
        index, requirement_id="REQ-1", anchor_windows_scanned=True,
        candidate_windows_expanded=True, counterexamples_reviewed=False,
        no_new_candidate_windows=True, audit_trail_recorded=True,
    )
    assert incomplete["exhaustionEligible"] is False
    complete = probe.build_probe_coverage(
        index, requirement_id="REQ-1", anchor_windows_scanned=True,
        candidate_windows_expanded=True, counterexamples_reviewed=True,
        no_new_candidate_windows=True, audit_trail_recorded=True,
    )
    assert complete["exhaustionEligible"] is True
