from copy import deepcopy

from backend.gameplay_review_model import build_gameplay_review_model
from backend.temporal_probe_orchestration import orchestrate_targeted_temporal_probes


def _eligible_gap(revision: str = "video-v1") -> dict:
    return {
        "gapId": "GAP-7B5CD346D948",
        "chapterId": "V2CH-001",
        "schemaSlot": "spawn_trigger",
        "status": "open",
        "subjectEntityId": "enemy-1",
        "probeEligible": True,
        "probeType": "LifecycleBoundaryProbe",
        "targetProperty": "first_appearance",
        "anchor": {"sourceVideoId": revision, "sourceVideoTrackId": "T0001", "entityClass": "enemy", "timestamp": 1.0},
        "searchWindow": {"start": 0.0, "end": 4.0},
        "evidenceQuestion": "该对象首次出现在哪个时点？",
        "sourceEvidenceRevision": revision,
    }


def _eligible_movement_gap(gap_id: str, entity_id: str, revision: str = "video-v1") -> dict:
    return {
        **_eligible_gap(revision),
        "gapId": gap_id,
        "chapterId": "V2CH-001",
        "schemaSlot": "movement_path",
        "subjectEntityId": entity_id,
        "probeType": "PersistentStateProbe",
        "targetProperty": "position",
        "evidenceQuestion": "该对象在稳定参考系中是否发生位置变化？",
    }


def _v2_model(*, gaps: list[dict] | None = None, requests: list[dict] | None = None) -> dict:
    requested = deepcopy((gaps or [_eligible_gap()])[0])
    model = build_gameplay_review_model({
        "id": "job-temporal-production",
        "contentModelVersion": 2,
        "frames": [{"id": "F0001", "timestamp": 1.0}],
        "temporalProbeContexts": ([{
            "scope": "刷新",
            "subjectEntityId": requested["subjectEntityId"],
            "anchor": requested["anchor"],
            "searchWindow": requested["searchWindow"],
            "sourceEvidenceRevision": requested["sourceEvidenceRevision"],
        }] if requested.get("probeEligible") is not False else []),
    }, [{
        "scope": "怪物刷新",
        "systemName": "战斗",
        "claims": [{
            "id": "GCL-001",
            "text": "怪物生成后进入战斗区域。",
            "sourceType": "material",
            "sourceFrameIds": ["F0001"],
        }],
        "mechanism": {"type": "core_loop"},
        "parameters": {},
        "dependencies": [],
        "acceptanceCases": [],
        "unknowns": [],
        "sourceFrameIds": ["F0001"],
    }])
    if gaps:
        # Additional gaps exercise orchestration batching; the first gap is still
        # emitted by the real schema producer above.
        produced_ids = {item["gapId"] for item in model["approvedData"]["gaps"]}
        extras = [item for item in gaps if item["gapId"] not in produced_ids]
        model["approvedData"]["gaps"].extend(deepcopy(extras))
        model["ruleIntelligenceProjection"]["gaps"].extend(deepcopy(extras))
    model["temporalProbeRequests"] = deepcopy(requests or [])
    return model


def _stub_video_boundaries(monkeypatch, *, calls: dict) -> None:
    from backend import temporal_probe_orchestration as orchestration

    def build_index(_video_path, _progress=None):
        calls["index"] = calls.get("index", 0) + 1
        return {
            "duration": 4.0,
            "candidateSampleTimes": [0.0, 2.0],
            "sceneChanges": [],
            "activityWindows": [{"start": 0.0, "end": 4.0, "score": 1.0}],
        }

    def extract(_video_path, _frames_dir, _structures_dir, _samples, _changes, _progress):
        calls["extract"] = calls.get("extract", 0) + 1
        return (
            [{"id": "VF-1", "timestamp": 0.0}, {"id": "VF-2", "timestamp": 2.0}],
            [],
            [{
                "id": "T0001",
                "class": "enemy",
                "observations": [{"frameId": "VF-2", "timestamp": 2.0, "bbox": [10, 10, 30, 30]}],
            }],
        )

    monkeypatch.setattr(orchestration, "build_requirement_temporal_index", build_index)
    monkeypatch.setattr(orchestration, "extract_and_structure", extract)


def _stub_movement_video_boundaries(monkeypatch, *, calls: dict) -> None:
    from backend import temporal_probe_orchestration as orchestration

    def build_index(_video_path, _progress=None):
        calls["index"] = calls.get("index", 0) + 1
        return {
            "duration": 4.0,
            "candidateSampleTimes": [0.0, 2.0],
            "sceneChanges": [],
            "activityWindows": [{"start": 0.0, "end": 4.0, "score": 1.0}],
        }

    def extract(_video_path, _frames_dir, _structures_dir, _samples, _changes, _progress):
        calls["extract"] = calls.get("extract", 0) + 1
        return (
            [
                {"id": "VF-1", "timestamp": 0.0, "backgroundDelta": [0.0, 0.0], "uiDelta": [0.0, 0.0]},
                {"id": "VF-2", "timestamp": 2.0, "backgroundDelta": [0.0, 0.0], "uiDelta": [0.0, 0.0]},
            ],
            [],
            [{
                "id": "T0001",
                "class": "enemy",
                "observations": [
                    {"frameId": "VF-1", "timestamp": 0.0, "bbox": [10, 10, 30, 30]},
                    {"frameId": "VF-2", "timestamp": 2.0, "bbox": [20, 10, 40, 30]},
                ],
            }],
        )

    monkeypatch.setattr(orchestration, "build_requirement_temporal_index", build_index)
    monkeypatch.setattr(orchestration, "extract_and_structure", extract)


def _stub_rate_change_video(monkeypatch, *, calls: dict) -> None:
    from backend import temporal_probe_orchestration as orchestration

    def build_index(_video_path, _progress=None):
        calls["index"] = calls.get("index", 0) + 1
        return {
            "duration": 5.0, "candidateSampleTimes": [0, 1, 2, 3, 4], "sceneChanges": [],
            "activityWindows": [{"start": 0.0, "end": 5.0, "score": 1.0}],
        }

    def extract(_video_path, _frames_dir, _structures_dir, _samples, _changes, _progress):
        calls["extract"] = calls.get("extract", 0) + 1
        frames = [
            {"id": f"VF-{i}", "timestamp": float(i), "backgroundDelta": [0, 0], "uiDelta": [0, 0]}
            for i in range(5)
        ]
        centers = [0, 2, 4, 14, 24]
        return frames, [], [{
            "id": "T0001", "class": "vehicle", "observations": [
                {"frameId": f"VF-{i}", "timestamp": float(i), "bbox": [x, 0, x + 10, 10]}
                for i, x in enumerate(centers)
            ],
        }]

    monkeypatch.setattr(orchestration, "build_requirement_temporal_index", build_index)
    monkeypatch.setattr(orchestration, "extract_and_structure", extract)


def test_t1_real_production_gap_creates_a_declarative_probe_request(monkeypatch, tmp_path):
    calls: dict[str, int] = {}
    _stub_video_boundaries(monkeypatch, calls=calls)
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")

    outcome = orchestrate_targeted_temporal_probes(
        _v2_model(gaps=[_eligible_gap()]),
        auxiliary_video_path=video,
        probe_workspace=tmp_path / "temporal-probe",
    )

    request = outcome.model["temporalProbeRequests"][0]
    assert request["sourceGapId"] == "GAP-7B5CD346D948"
    assert request["probeType"] == "LifecycleBoundaryProbe"
    assert request["targetProperty"] == "first_appearance"
    assert request["sourceEvidenceRevision"] == "video-v1"
    assert request["evidenceQuestion"]
    assert outcome.created_request_count == 1
    assert calls == {"index": 1, "extract": 1}


def test_t2_generate_gameplay_review_executes_and_persists_temporal_evidence(monkeypatch, tmp_path):
    from backend import server

    calls: dict[str, int] = {}
    _stub_video_boundaries(monkeypatch, calls=calls)
    auxiliary_dir = tmp_path / "auxiliary"
    auxiliary_dir.mkdir()
    (auxiliary_dir / "source.mp4").write_bytes(b"video")
    generated = _v2_model(gaps=[_eligible_gap()])
    job = {
        "id": "job-temporal-production",
        "contentModelVersion": 2,
        "auxiliaryVideo": {
            "sourceUrl": "/artifacts/job-temporal-production/auxiliary/source.mp4",
            "evidenceRevision": "video-v1",
        },
    }

    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server, "job_path", lambda _job_id: tmp_path)
    monkeypatch.setattr(server, "generate_gameplay_structure", lambda *_args, **_kwargs: deepcopy(generated))
    monkeypatch.setattr(server.storage, "mutate_job", lambda _job_id, mutation: mutation(job))

    server._generate_gameplay_review(job["id"], {})

    model = job["gameplayReviewModel"]
    assert model["temporalEvidence"]["facts"]
    assert model["temporalEvidence"]["facts"][0]["reviewStatus"] == "unreviewed"
    assert model["temporalEvidence"]["facts"][0]["observationMode"] == "targeted_temporal_probe"
    assert model["temporalProbeRequests"][0]["status"] == "completed"


def test_t3_multiple_probe_results_trigger_exactly_one_additional_projection_rebuild(monkeypatch, tmp_path):
    calls: dict[str, int] = {}
    _stub_movement_video_boundaries(monkeypatch, calls=calls)
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")

    outcome = orchestrate_targeted_temporal_probes(
        _v2_model(gaps=[
            _eligible_movement_gap("GAP-MOVE-A", "enemy-1"),
            _eligible_movement_gap("GAP-MOVE-B", "enemy-2"),
        ]),
        auxiliary_video_path=video,
        probe_workspace=tmp_path / "temporal-probe",
    )

    assert outcome.executed_probe_count == 3
    assert outcome.projection_rebuild_count == 1
    assert len(outcome.model["temporalEvidence"]["ruleCandidates"]) == 2
    assert outcome.model["ruleIntelligenceProjection"]["ruleCandidates"]


def test_t4_no_eligible_gap_makes_zero_video_calls(monkeypatch, tmp_path):
    from backend import temporal_probe_orchestration as orchestration

    monkeypatch.setattr(
        orchestration,
        "build_requirement_temporal_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("video index must not be built")),
    )
    monkeypatch.setattr(
        orchestration,
        "extract_and_structure",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("video must not be decoded")),
    )
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")
    ineligible = {**_eligible_gap(), "probeEligible": False}

    outcome = orchestrate_targeted_temporal_probes(
        _v2_model(gaps=[ineligible]),
        auxiliary_video_path=video,
        probe_workspace=tmp_path / "temporal-probe",
    )

    assert outcome.created_request_count == 0
    assert outcome.executed_probe_count == 0
    assert outcome.model["temporalProbeRequests"] == []


def test_t5_exhausted_probe_is_not_retried_for_the_same_evidence_revision(monkeypatch, tmp_path):
    from backend import temporal_probe_orchestration as orchestration

    monkeypatch.setattr(
        orchestration,
        "build_requirement_temporal_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("same revision must not read video")),
    )
    prior = {
        "probeRequestId": "TPR-GAP-7B5CD346D948",
        "sourceGapId": "GAP-7B5CD346D948",
        "entityId": "enemy-1",
        "probeType": "LifecycleBoundaryProbe",
        "targetProperty": "first_appearance",
        "status": "exhausted",
        "attemptCount": 1,
        "searchedWindows": [{"start": 0.0, "end": 4.0}],
        "evidenceCoverage": {},
        "exhaustionReason": "no_observation_in_reviewed_video",
        "evidenceRevision": "video-v1",
        "sourceEvidenceRevision": "video-v1",
    }

    outcome = orchestrate_targeted_temporal_probes(
        _v2_model(gaps=[_eligible_gap("video-v1")], requests=[prior]),
        auxiliary_video_path=tmp_path / "auxiliary.mp4",
        probe_workspace=tmp_path / "temporal-probe",
    )

    assert outcome.created_request_count == 0
    assert outcome.executed_probe_count == 0
    assert outcome.model["temporalProbeRequests"] == [prior]


def test_t6_new_evidence_revision_reactivates_an_exhausted_probe(monkeypatch, tmp_path):
    calls: dict[str, int] = {}
    _stub_video_boundaries(monkeypatch, calls=calls)
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")
    prior = {
        "probeRequestId": "TPR-GAP-7B5CD346D948",
        "sourceGapId": "GAP-7B5CD346D948",
        "entityId": "enemy-1",
        "probeType": "LifecycleBoundaryProbe",
        "targetProperty": "first_appearance",
        "status": "exhausted",
        "attemptCount": 1,
        "searchedWindows": [{"start": 0.0, "end": 4.0}],
        "evidenceCoverage": {},
        "exhaustionReason": "no_observation_in_reviewed_video",
        "evidenceRevision": "video-v1",
        "sourceEvidenceRevision": "video-v1",
    }

    outcome = orchestrate_targeted_temporal_probes(
        _v2_model(gaps=[_eligible_gap("video-v2")], requests=[prior]),
        auxiliary_video_path=video,
        probe_workspace=tmp_path / "temporal-probe",
    )

    request = next(item for item in outcome.model["temporalProbeRequests"] if item["sourceEvidenceRevision"] == "video-v2")
    assert outcome.created_request_count == 1
    assert outcome.executed_probe_count == 1
    assert request["sourceEvidenceRevision"] == "video-v2"
    assert request["attemptCount"] == 2
    assert len(outcome.model["temporalProbeRequests"]) == 2
    assert outcome.model["temporalProbeRequests"][0]["searchedWindows"] == [{"start": 0.0, "end": 4.0}]
    assert calls == {"index": 1, "extract": 1}


def test_cross_source_track_ids_do_not_confirm_or_bind_same_class_entities():
    from backend.temporal_probe_orchestration import _track_candidate

    candidate = _track_candidate(
        {"probeRequestId": "TPR-X", "entityId": "enemy-a", "anchor": {"trackId": "T0001", "entityClass": "enemy"}},
        frames=[{"id": "VF-1", "timestamp": 1.0}],
        tracks=[
            {"id": "T0001", "class": "enemy", "observations": [{"frameId": "VF-1", "bbox": [0, 0, 10, 10]}]},
            {"id": "T0002", "class": "enemy", "observations": [{"frameId": "VF-1", "bbox": [20, 0, 30, 10]}]},
        ],
        source_video_id="video-v1",
    )

    assert candidate["identityStatus"] == "ambiguous"
    assert candidate["entityId"] is None
    assert candidate["ruleCandidateEligible"] is False


def test_each_gap_uses_its_own_evidence_revision(monkeypatch, tmp_path):
    calls: dict[str, int] = {}
    _stub_video_boundaries(monkeypatch, calls=calls)
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")
    second = _eligible_movement_gap("GAP-REV-B", "enemy-2", "video-v2")

    outcome = orchestrate_targeted_temporal_probes(
        _v2_model(gaps=[_eligible_gap("video-v1"), second]),
        auxiliary_video_path=video,
        probe_workspace=tmp_path / "temporal-probe",
    )

    assert {item["sourceEvidenceRevision"] for item in outcome.model["temporalProbeRequests"]} == {"video-v1", "video-v2"}
    assert calls == {"index": 1, "extract": 1}


def test_confirmed_movement_rate_probe_enters_existing_review_chain(monkeypatch, tmp_path):
    calls = {}
    _stub_rate_change_video(monkeypatch, calls=calls)
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")
    gap = {
        **_eligible_movement_gap("GAP-RATE", "vehicle-1"),
        "schemaSlot": "movement_rate_change", "targetProperty": "movement_rate",
        "anchor": {"sourceVideoId": "video-v1", "sourceVideoTrackId": "T0001", "entityClass": "vehicle"},
    }
    model = _v2_model(gaps=[gap])

    outcome = orchestrate_targeted_temporal_probes(
        model, auxiliary_video_path=video, probe_workspace=tmp_path / "probe",
    )

    evidence = outcome.model["temporalEvidence"]
    assert any(item.get("predicate") == "movement_rate_changed" for item in evidence["facts"])
    candidate = next(item for item in evidence["ruleCandidates"] if item.get("schemaSlot") == "movement_rate_change")
    assert candidate["reviewStatus"] == "unreviewed"
    assert candidate["triggerStatus"] == "unresolved"


def test_planner_confirmed_bbox_anchor_uses_bounded_template_track(monkeypatch, tmp_path):
    from backend import temporal_probe_orchestration as orchestration

    calls = {}
    _stub_rate_change_video(monkeypatch, calls=calls)
    monkeypatch.setattr(
        orchestration,
        "_anchored_template_track",
        lambda *_args, **_kwargs: {
            "id": "TPL-vehicle-1", "class": "vehicle", "anchorConfirmed": True,
            "observations": [
                {"frameId": f"VF-{i}", "timestamp": float(i), "bbox": [x, 0, x + 10, 10]}
                for i, x in enumerate([0, 2, 4, 14, 24])
            ],
        },
    )
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")
    gap = {
        **_eligible_movement_gap("GAP-RATE-BBOX", "vehicle-1"),
        "schemaSlot": "movement_rate_change", "targetProperty": "movement_rate",
        "anchor": {
            "sourceVideoId": "video-v1", "entityClass": "vehicle",
            "timestamp": 1.0, "bbox": [0, 0, 10, 10], "plannerConfirmed": True,
        },
    }

    outcome = orchestrate_targeted_temporal_probes(
        _v2_model(gaps=[gap]), auxiliary_video_path=video, probe_workspace=tmp_path / "probe",
    )

    candidate = next(
        item for item in outcome.model["temporalEvidence"]["ruleCandidates"]
        if item.get("schemaSlot") == "movement_rate_change"
    )
    assert candidate["reviewStatus"] == "unreviewed"
    assert candidate["candidateEntityId"] is None
