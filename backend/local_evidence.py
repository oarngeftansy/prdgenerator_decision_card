from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import cv2

from .image_io import write_jpeg

ALLOWED_SIGNALS = {
    "text_unreadable",
    "visual_occlusion",
    "action_between_frames",
    "result_not_shown",
    "state_chain_broken",
}
CONTROL_FIELDS = {"attentionSignals", "evidenceTimestamps", "id"}


def sample_times(center: float, duration: float) -> list[float]:
    end = max(0.0, float(duration))
    values = {round(min(end, max(0.0, float(center) + offset)), 3) for offset in (-1, -0.5, 0, 0.5, 1)}
    if len(values) < 2 and end > 0:
        values.update((0.0, round(end, 3)))
    return sorted(values)


def normalize_attention_signals(value: Any) -> list[str]:
    items = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return list(dict.fromkeys(item for item in items if item in ALLOWED_SIGNALS))


def extract_supplemental(
    video_path: Path,
    output_dir: Path,
    frame_id: str,
    center: float,
    duration: float,
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("无法读取源视频。")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 1)
    samples = []
    try:
        for timestamp in sample_times(center, duration):
            filename = f"{frame_id}_{round(timestamp * 1000):010d}.jpg"
            path = output_dir / filename
            if not path.exists():
                capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ok, image = capture.read()
                if not ok and timestamp >= duration:
                    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, duration - 1 / fps) * 1000)
                    ok, image = capture.read()
                if not ok:
                    continue
                if not write_jpeg(path, image, 84):
                    continue
            samples.append({
                "timestamp": timestamp,
                "imageUrl": f"/artifacts/{output_dir.parent.name}/supplemental/{filename}",
            })
    finally:
        capture.release()
    if len(samples) < 2:
        raise ValueError("视频片段过短，无法补取更多画面。")
    return samples


def merge_local_analysis(frame: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(frame)
    analysis = result.setdefault("analysis", {})
    human_fields = set(result.get("humanEditedFields", []))
    suggestions = dict(result.get("analysisSuggestion", {}))
    model_analysis = {key: value for key, value in candidate.items() if key not in CONTROL_FIELDS}
    for field, value in model_analysis.items():
        if field in human_fields and analysis.get(field) != value:
            suggestions[field] = value
        else:
            analysis[field] = value
            suggestions.pop(field, None)
    result["analysisSuggestion"] = suggestions
    result["lastModelAnalysis"] = {**result.get("lastModelAnalysis", {}), **model_analysis}
    result["attentionSignals"] = normalize_attention_signals(candidate.get("attentionSignals"))
    return result
