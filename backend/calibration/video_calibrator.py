from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.video_pipeline import extract_and_structure, inspect_video

UNKNOWN = "unknown"


def validate_video_calibration(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    duration = float(data.get("duration") or 0)
    sampled_until = float(data.get("sampledUntil") or 0)
    if duration <= 0 or duration - sampled_until > max(0.25, duration * 0.001):
        errors.append("video duration is not fully covered")
    for event in data.get("events", []):
        if event.get("importance") == "core" and (
            not event.get("systemResponse") or not event.get("afterState")
        ):
            errors.append("core event missing systemResponse and afterState")
    return errors


def calibrate_video(video_path: Path, level_id: str, workspace: Path) -> dict[str, Any]:
    frames_dir = workspace / level_id / "frames"
    structures_dir = workspace / level_id / "structures"
    frames_dir.mkdir(parents=True, exist_ok=True)
    structures_dir.mkdir(parents=True, exist_ok=True)

    def progress(value: int, stage: str) -> None:
        print(f"[{level_id}] {value:3d}% {stage}", flush=True)

    metadata, changes, samples = inspect_video(video_path, progress)
    duration = float(metadata["duration"])
    # Mark just beyond EOF as a boundary so the final decodable sample bypasses
    # perceptual deduplication without becoming a new scene.
    extraction_changes = [*changes, {"time": duration + 0.05, "score": 1.0, "synthetic": True}]
    frames, scenes, tracks = extract_and_structure(
        video_path, frames_dir, structures_dir, samples, extraction_changes, progress
    )
    sampled_until = max((frame["timestamp"] for frame in frames), default=0.0)
    final_tolerance = max(1.0 / max(float(metadata.get("fps") or 1), 1.0), 0.05)
    if duration - sampled_until <= final_tolerance + 0.1:
        sampled_until = duration
    return {
        "levelId": level_id,
        "source": {"filename": video_path.name},
        "duration": duration,
        "sampledUntil": sampled_until,
        "metadata": metadata,
        "sceneChanges": changes,
        "samplePlan": samples,
        "chapters": [],
        "scenes": scenes,
        "events": [],
        "frames": frames,
        "componentTracks": tracks,
        "audio": {"status": UNKNOWN},
        "diagnostics": {"validationErrors": []},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--level-id", required=True)
    parser.add_argument("--workspace", type=Path, default=Path("tmp/calibration"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = calibrate_video(args.video, args.level_id, args.workspace)
    result["diagnostics"]["validationErrors"] = validate_video_calibration(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
