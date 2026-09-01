from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from .gameplay_review_service import add_targeted_temporal_probe_result
from .requirement_temporal_probe import (
    build_requirement_temporal_index,
    build_targeted_probe_requests,
    build_temporal_entity_track_candidate,
    run_targeted_temporal_probe,
)
from .video_pipeline import extract_and_structure


@dataclass(frozen=True)
class TemporalProbeOrchestrationOutcome:
    model: dict[str, Any]
    created_request_count: int
    executed_probe_count: int
    projection_rebuild_count: int


def _video_inputs(
    video_path: Path,
    workspace: Path,
    temporal_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    frames_dir = workspace / "frames"
    structures_dir = workspace / "structures"
    frames_dir.mkdir(parents=True, exist_ok=True)
    structures_dir.mkdir(parents=True, exist_ok=True)
    frames, _scenes, tracks = extract_and_structure(
        video_path,
        frames_dir,
        structures_dir,
        list(temporal_index.get("candidateSampleTimes") or []),
        list(temporal_index.get("sceneChanges") or []),
        lambda *_args: None,
    )
    return frames, tracks


def _track_candidate(
    request: dict[str, Any],
    *,
    frames: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
    source_video_id: str,
) -> dict[str, Any]:
    anchor = request.get("anchor") if isinstance(request.get("anchor"), dict) else {}
    anchor_track_id = str(anchor.get("sourceVideoTrackId") or "").strip() if anchor.get("sourceVideoId") == source_video_id else ""
    entity_class = str(anchor.get("entityClass") or "").strip()
    matches = [
        track for track in tracks
        if isinstance(track, dict)
        and (str(track.get("id") or "") == anchor_track_id if anchor_track_id else str(track.get("class") or "") == entity_class)
    ] if anchor_track_id or entity_class else []
    selected = matches[0] if matches else {"id": None, "class": entity_class, "observations": []}
    by_frame = {
        str(item.get("frameId")): item
        for item in selected.get("observations") or []
        if isinstance(item, dict) and item.get("frameId")
    }
    observations = []
    for frame in sorted(frames, key=lambda item: float(item.get("timestamp") or 0)):
        frame_id = str(frame.get("id") or "")
        source = by_frame.get(frame_id)
        observation: dict[str, Any] = {
            "frameId": frame_id,
            "timestamp": float(frame.get("timestamp") or 0),
            "present": source is not None,
            "trackId": selected.get("id"),
            "class": selected.get("class"),
            "sameClassCandidateCount": len(matches),
            "anchorEntityMatch": bool(
                (anchor_track_id and selected.get("id") == anchor_track_id)
                or (anchor.get("plannerConfirmed") is True and selected.get("anchorConfirmed") is True)
            ),
        }
        if source is not None and isinstance(source.get("bbox"), list) and len(source["bbox"]) == 4:
            left, top, right, bottom = map(float, source["bbox"])
            observation["bbox"] = list(source["bbox"])
            observation["entityCenter"] = [(left + right) / 2, (top + bottom) / 2]
        for field in ("backgroundDelta", "uiDelta", "sceneId"):
            if source is not None and source.get(field) is not None:
                observation[field] = source[field]
            elif frame.get(field) is not None:
                observation[field] = frame[field]
        observations.append(observation)
    candidate = build_temporal_entity_track_candidate(request, observations)
    candidate["sourceVideoId"] = source_video_id
    return candidate


def _anchored_template_track(
    video_path: Path,
    request: dict[str, Any],
    frames: list[dict[str, Any]],
    source_video_id: str,
) -> dict[str, Any] | None:
    """Follow one planner-confirmed visual anchor inside a bounded probe window.

    This is deliberately a small template probe, not cross-scene Re-ID.  Its
    output remains observation evidence and always requires the normal review
    chain before a gameplay rule can be approved.
    """
    anchor = request.get("anchor") if isinstance(request.get("anchor"), dict) else {}
    bbox = anchor.get("bbox")
    if (
        anchor.get("sourceVideoId") != source_video_id
        or anchor.get("plannerConfirmed") is not True
        or not isinstance(bbox, list)
        or len(bbox) != 4
    ):
        return None
    try:
        left, top, right, bottom = [int(round(float(value))) for value in bbox]
        anchor_time = float(anchor.get("timestamp"))
    except (TypeError, ValueError):
        return None
    if right <= left or bottom <= top:
        return None

    capture = cv2.VideoCapture(str(video_path))

    def read_at(second: float):
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, second) * 1000)
        ok, image = capture.read()
        return image if ok else None

    anchor_image = read_at(anchor_time)
    if anchor_image is None:
        capture.release()
        return None
    height, width = anchor_image.shape[:2]
    left, right = max(0, left), min(width, right)
    top, bottom = max(0, top), min(height, bottom)
    if right <= left or bottom <= top:
        capture.release()
        return None
    template = cv2.cvtColor(anchor_image[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
    template_height, template_width = template.shape[:2]
    search = request.get("searchWindow") if isinstance(request.get("searchWindow"), dict) else {}
    start, end = float(search.get("start", anchor_time)), float(search.get("end", anchor_time))
    threshold = min(.95, max(.2, float(anchor.get("minSimilarity") or .3)))
    region = anchor.get("searchRegion") if isinstance(anchor.get("searchRegion"), list) else [0, 0, width, height]
    try:
        sx1, sy1, sx2, sy2 = [int(round(float(value))) for value in region]
    except (TypeError, ValueError):
        sx1, sy1, sx2, sy2 = 0, 0, width, height
    sx1, sy1, sx2, sy2 = max(0, sx1), max(0, sy1), min(width, sx2), min(height, sy2)
    observations = []
    for frame in sorted(frames, key=lambda item: float(item.get("timestamp") or 0)):
        timestamp = float(frame.get("timestamp") or 0)
        if timestamp < start or timestamp > end:
            continue
        image = read_at(timestamp)
        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        search_image = gray[sy1:sy2, sx1:sx2]
        if search_image.shape[0] < template_height or search_image.shape[1] < template_width:
            continue
        match = cv2.matchTemplate(search_image, template, cv2.TM_CCOEFF_NORMED)
        _, similarity, _, location = cv2.minMaxLoc(match)
        if similarity < threshold:
            continue
        x, y = sx1 + int(location[0]), sy1 + int(location[1])
        observations.append({
            "frameId": frame.get("id"), "timestamp": timestamp,
            "bbox": [x, y, x + template_width, y + template_height],
            "appearanceSimilarity": round(float(similarity), 6),
            "sceneId": frame.get("sceneId"),
        })
    capture.release()
    if not observations:
        return None
    return {
        "id": f"TPL-{request.get('entityId') or 'entity'}",
        "class": str(anchor.get("entityClass") or "anchored_entity"),
        "anchorConfirmed": True,
        "observations": observations,
    }


def orchestrate_targeted_temporal_probes(
    model: dict[str, Any],
    *,
    auxiliary_video_path: Path | None,
    probe_workspace: Path,
) -> TemporalProbeOrchestrationOutcome:
    """Run declared, bounded temporal probes after a v2 projection has been built."""
    result = deepcopy(model)
    projection = result.get("ruleIntelligenceProjection")
    gaps = list(projection.get("gaps") or []) if isinstance(projection, dict) else []
    declared = [gap for gap in gaps if isinstance(gap, dict) and gap.get("probeEligible") is True]
    if not declared or auxiliary_video_path is None:
        return TemporalProbeOrchestrationOutcome(result, 0, 0, 0)

    prior = list(result.get("temporalProbeRequests") or [])
    runnable = []
    for evidence_revision in dict.fromkeys(str(gap.get("sourceEvidenceRevision") or "").strip() for gap in declared):
        if evidence_revision:
            group = [gap for gap in declared if str(gap.get("sourceEvidenceRevision") or "").strip() == evidence_revision]
            built = build_targeted_probe_requests(group, existing_requests=prior, evidence_revision=evidence_revision)
            runnable.extend(request for request in built["requests"] if request.get("status") == "pending")
    if not runnable:
        return TemporalProbeOrchestrationOutcome(result, 0, 0, 0)

    temporal_index = build_requirement_temporal_index(auxiliary_video_path)
    frames, tracks = _video_inputs(auxiliary_video_path, probe_workspace, temporal_index)
    for request in runnable:
        anchor = request.get("anchor") if isinstance(request.get("anchor"), dict) else {}
        request_tracks = tracks
        if not anchor.get("sourceVideoTrackId"):
            template_track = _anchored_template_track(
                auxiliary_video_path,
                request,
                frames,
                str(request.get("sourceEvidenceRevision") or ""),
            )
            if template_track is not None:
                request_tracks = [template_track]
        candidate = _track_candidate(
            request,
            frames=frames,
            tracks=request_tracks,
            source_video_id=str(request.get("sourceEvidenceRevision") or ""),
        )
        probe_result = run_targeted_temporal_probe(
            request,
            temporal_index=temporal_index,
            track_candidate=candidate,
        )
        result = add_targeted_temporal_probe_result(
            result,
            probe_result,
            result["revision"],
            rebuild_projection=False,
        )
    from .rule_normalizer import build_rule_intelligence_v1
    result["ruleIntelligenceProjection"] = build_rule_intelligence_v1(result, result["approvedData"])
    return TemporalProbeOrchestrationOutcome(result, len(runnable), len(runnable), 1)
