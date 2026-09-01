from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .analysis_service import _call, _client
from .image_io import read_image, write_jpeg
from .video_pipeline import _difference_hash, _hamming, _read_at


_ALLOWED_FIELDS = {"trigger", "process", "result", "timing", "automaticTransition"}
_MATCH_THRESHOLD = 0.28


def _histogram(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    values = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    return cv2.normalize(values, values).flatten()


def _distance(screenshot: np.ndarray, candidate: np.ndarray) -> float:
    hash_distance = _hamming(_difference_hash(screenshot), _difference_hash(candidate)) / 64
    histogram_distance = float(cv2.compareHist(_histogram(screenshot), _histogram(candidate), cv2.HISTCMP_BHATTACHARYYA))
    return (hash_distance + max(0.0, min(1.0, histogram_distance))) / 2


def _candidate_times(duration: float, step: float) -> list[float]:
    values = [round(index * step, 3) for index in range(max(1, math.floor(duration / step) + 1))]
    last = round(max(0.0, duration - 0.05), 3)
    return values if last in values else values + [last]


def match_screenshot_to_video(screenshot_path: Path, video_path: Path, coarse_step: float = 1.0) -> dict:
    """Locate one screenshot without deriving any whole-video gameplay facts."""
    if coarse_step <= 0:
        raise ValueError("coarse_step must be positive")
    screenshot = read_image(screenshot_path)
    if screenshot is None:
        raise ValueError("screenshot unavailable")
    capture = cv2.VideoCapture(str(video_path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if fps > 0 else 0
        if not capture.isOpened() or duration <= 0:
            raise ValueError("auxiliary video unavailable")
        candidates = []
        for timestamp in _candidate_times(duration, coarse_step):
            frame = _read_at(capture, timestamp)
            if frame is not None:
                candidates.append((_distance(screenshot, frame), timestamp))
        if not candidates:
            raise ValueError("no readable auxiliary frames")
        _, coarse_time = min(candidates)
        refine_step = min(0.25, coarse_step / 4)
        for offset in (-coarse_step, -refine_step, 0.0, refine_step, coarse_step):
            timestamp = min(max(0.0, coarse_time + offset), max(0.0, duration - 0.05))
            frame = _read_at(capture, timestamp)
            if frame is not None:
                candidates.append((_distance(screenshot, frame), timestamp))
        score, timestamp = min(candidates)
    finally:
        capture.release()
    if score > _MATCH_THRESHOLD:
        return {"status": "needs_planner_location"}
    return {"status": "matched", "matchedTime": round(timestamp, 3), "confidence": round(1 - score, 3)}


def _sample_context(video_path: Path, job_dir: Path, matched_time: float, radius: float) -> list[dict[str, Any]]:
    capture = cv2.VideoCapture(str(video_path))
    output_dir = job_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        timestamps = sorted({round(max(0.0, matched_time + offset), 3) for offset in (-radius, -radius / 2, 0.0, radius / 2, radius)})
        samples = []
        for index, timestamp in enumerate(timestamps, 1):
            if (image := _read_at(capture, timestamp)) is None:
                continue
            path = output_dir / f"context-{int(matched_time * 1000):010d}-{int(radius * 10):03d}-{index}.jpg"
            if write_jpeg(path, image, 82):
                samples.append({"timestamp": timestamp, "path": path})
        return samples
    finally:
        capture.release()


def _analyze_context_samples(samples: list[dict[str, Any]], missing_fields: list[str], config: dict[str, Any]) -> dict[str, Any]:
    client = _client(config)
    if not client:
        raise RuntimeError("vision model unavailable")
    requested = ", ".join(missing_fields)
    prompt = (
        "Compare only this bounded screen-recording window anchored to a supplied screenshot. "
        f"Return a JSON object with only these requested fields: {requested}. "
        'Each field value must use exactly {"closed": boolean, "observation": string}. '
        "Set closed to false when evidence is insufficient; only closed observations are accepted."
    )
    result = _call(client, str(config.get("model") or "qwen3.6-plus"), prompt,
                   [(f"time={sample['timestamp']}", sample["path"]) for sample in samples], max_tokens=1200)
    observations = {}
    if isinstance(result, dict):
        for field in missing_fields:
            observation = _closed_observation(result.get(field))
            if observation is not None:
                observations[field] = observation
    return observations


def _closed_observation(value: Any) -> str | None:
    if not isinstance(value, dict) or set(value) != {"closed", "observation"} or value.get("closed") is not True:
        return None
    observation = value.get("observation")
    return observation.strip() if isinstance(observation, str) and observation.strip() else None


def analyze_context_window(
    chapter_id, anchor_frame_id, screenshot_path, video_path, missing_fields, job_dir, config,
    radii=(2.0, 5.0, 10.0), manual_timestamp: float | None = None,
) -> dict:
    """Analyze only progressively larger windows around a verified screenshot match."""
    if (not isinstance(missing_fields, list) or not missing_fields
            or any(not isinstance(field, str) for field in missing_fields) or set(missing_fields) - _ALLOWED_FIELDS):
        raise ValueError("invalid missing fields")
    try:
        if manual_timestamp is not None:
            if not isinstance(manual_timestamp, (int, float)) or manual_timestamp < 0:
                raise ValueError("manual timestamp must be a non-negative number")
            match = {"status": "matched", "matchedTime": float(manual_timestamp), "confidence": 1.0}
            anchor_authority = "planner_confirmed_location"
        else:
            match = match_screenshot_to_video(Path(screenshot_path), Path(video_path))
            anchor_authority = "visual_match"
        if match.get("status") != "matched":
            return {"status": "needs_planner_location"}
        attempt_root = Path(job_dir) / "auxiliary"
        attempt_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".context-", dir=attempt_root) as attempt_dir:
            facts: dict[str, Any] = {}
            evidence_timestamps: list[float] = []
            for radius in radii:
                pending = [field for field in missing_fields if field not in facts]
                if not pending:
                    break
                samples = _sample_context(Path(video_path), Path(attempt_dir), float(match["matchedTime"]), radius=float(radius))
                if not samples:
                    continue
                observations = _analyze_context_samples(samples, pending, config)
                facts.update({field: value.strip() for field, value in observations.items()
                              if field in pending and isinstance(value, str) and value.strip()})
                evidence_timestamps.extend(sample["timestamp"] for sample in samples)
                if all(field in facts for field in missing_fields):
                    return {
                        "status": "completed", "chapterId": chapter_id, "anchorFrameId": anchor_frame_id,
                        "matchedTime": match["matchedTime"], "radius": float(radius),
                        "evidenceTimestamps": sorted(set(evidence_timestamps)), "facts": facts,
                        "confidence": match.get("confidence", 0),
                        "anchorAuthority": anchor_authority,
                        "observationAuthority": "observed_unreviewed",
                    }
        return {"status": "failed"}
    except Exception:
        return {"status": "failed"}
