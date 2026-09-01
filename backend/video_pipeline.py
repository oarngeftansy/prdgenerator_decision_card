from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from .image_io import write_jpeg
from .screen_adapter import ScreenCoderAdapter

Progress = Callable[[int, str], None]


def _read_at(capture: cv2.VideoCapture, second: float) -> np.ndarray | None:
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, second) * 1000)
    ok, frame = capture.read()
    return frame if ok else None


def _signature(frame: np.ndarray) -> np.ndarray:
    return cv2.resize(frame, (64, 36))


def _difference_hash(frame: np.ndarray) -> int:
    gray = cv2.cvtColor(cv2.resize(frame, (9, 8)), cv2.COLOR_BGR2GRAY)
    bits = gray[:, 1:] > gray[:, :-1]
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return value


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _visual_difference(previous: np.ndarray, current: np.ndarray) -> float:
    previous_hsv = cv2.cvtColor(previous, cv2.COLOR_BGR2HSV)
    current_hsv = cv2.cvtColor(current, cv2.COLOR_BGR2HSV)
    previous_hist = cv2.calcHist([previous_hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    current_hist = cv2.calcHist([current_hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    previous_hist = cv2.normalize(previous_hist, previous_hist).flatten()
    current_hist = cv2.normalize(current_hist, current_hist).flatten()
    correlation = cv2.compareHist(previous_hist, current_hist, cv2.HISTCMP_CORREL)
    histogram_delta = max(0.0, 1 - correlation)
    # Histograms ignore position, so blend in a spatial pixel delta to catch
    # cursor movement, button feedback, dragging and small UI animations.
    pixel_delta = float(np.mean(cv2.absdiff(previous, current))) / 255.0
    return float(max(0.0, min(1.0, max(histogram_delta, pixel_delta * 5.0))))


def _uniform(duration: float, count: int) -> list[float]:
    if count <= 1:
        return [0.0]
    end = max(0.1, duration - 0.15)
    return [round(i * end / (count - 1), 3) for i in range(count)]


def _limit_across_timeline(samples: list[float], limit: int) -> list[float]:
    values = sorted(set(round(max(0.0, value), 3) for value in samples))
    if len(values) <= limit:
        return values
    indexes = np.linspace(0, len(values) - 1, limit).round().astype(int)
    return [values[index] for index in sorted(set(indexes.tolist()))]


def inspect_video(video_path: Path, progress: Progress) -> tuple[dict[str, Any], list[dict[str, Any]], list[float]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("无法读取视频，请确认格式可由 OpenCV/FFmpeg 解码。")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frame_count / fps if fps > 0 else 0
    if duration <= 0:
        capture.release()
        raise ValueError("无法获取有效视频时长。")

    scan_count = min(240, max(32, math.ceil(duration / 3)))
    scan_times = _uniform(duration, scan_count)
    signatures: list[tuple[float, np.ndarray]] = []
    progress(5, "低频扫描完整视频")
    for index, second in enumerate(scan_times):
        frame = _read_at(capture, second)
        if frame is not None:
            signatures.append((second, _signature(frame)))
        if index % 8 == 0:
            progress(5 + round(18 * (index + 1) / len(scan_times)), f"全片扫描 {index + 1}/{len(scan_times)}")

    differences = []
    for index in range(1, len(signatures)):
        differences.append((signatures[index][0], _visual_difference(signatures[index - 1][1], signatures[index][1])))
    scores = np.array([score for _, score in differences], dtype=float)
    threshold = float(max(0.28, np.quantile(scores, 0.82))) if scores.size else 1.0
    changes = [{"time": second, "score": round(score, 4)} for second, score in differences if score >= threshold]
    activity_threshold = float(max(0.12, np.quantile(scores, 0.62))) if scores.size else 1.0
    activity_windows = [{"center": second, "score": round(score, 4), "start": max(0, second - 0.8), "end": min(duration, second + 0.8)} for second, score in differences if score >= activity_threshold]

    base_count = min(80, max(36, round(duration / 12)))
    samples = _uniform(duration, base_count)
    for change in changes:
        for offset in (-1.2, -0.5, 0, 0.5, 1.2):
            samples.append(min(duration - 0.1, max(0, change["time"] + offset)))
    # 疑似操作区间按5FPS二次采样，随后统一去重和全时间轴限额。
    for window in activity_windows:
        second = window["start"]
        while second <= window["end"]:
            samples.append(min(duration - 0.1, second))
            second += 0.2
    # OpenCV cannot seek beyond the final decoded frame.  Low-FPS videos make
    # duration-0.15 invalid, so explicitly sample the last real frame.
    last_decodable = round(max(0.0, duration - max(1.0 / max(fps, 1.0), 0.05)), 3)
    samples.append(last_decodable)
    samples = _limit_across_timeline(samples, 140)
    if last_decodable not in samples:
        samples[-1] = last_decodable
        samples = sorted(set(samples))
    capture.release()

    metadata = {
        "filename": video_path.name,
        "duration": round(duration, 3),
        "fps": round(fps, 3),
        "frameCount": frame_count,
        "width": width,
        "height": height,
        "scanSamples": len(scan_times),
        "keyframeSamples": len(samples),
        "sceneThreshold": round(threshold, 4),
        "activityThreshold": round(activity_threshold, 4),
        "activityWindows": activity_windows,
    }
    return metadata, changes, samples


def extract_and_structure(
    video_path: Path,
    frames_dir: Path,
    structures_dir: Path,
    samples: list[float],
    changes: list[dict[str, Any]],
    progress: Progress,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    capture = cv2.VideoCapture(str(video_path))
    adapter = ScreenCoderAdapter()
    frames: list[dict[str, Any]] = []
    tracks: dict[str, dict[str, Any]] = {}
    previous_elements: list[dict[str, Any]] = []
    last_hash: int | None = None
    last_kept_time = -999.0
    change_times = [item["time"] for item in changes]
    for index, second in enumerate(samples):
        image = _read_at(capture, second)
        if image is None:
            continue
        image_hash = _difference_hash(image)
        near_boundary = any(abs(second - change) <= 1.3 for change in change_times)
        if last_hash is not None and _hamming(last_hash, image_hash) <= 5 and second - last_kept_time < 8 and not near_boundary:
            continue
        frame_id = f"F{index + 1:04d}"
        filename = f"{frame_id}_{int(second * 1000):010d}.jpg"
        path = frames_dir / filename
        if not write_jpeg(path, image, 82):
            continue
        structure = adapter.analyze(path, structures_dir)
        _assign_tracks(structure.get("elements", []), previous_elements, tracks, frame_id, second)
        previous_elements = structure.get("elements", [])
        scene_index = sum(1 for change in change_times if second >= change)
        frames.append({
            "id": frame_id,
            "timestamp": round(second, 3),
            "sceneId": scene_index,
            "imageUrl": f"/artifacts/{frames_dir.parent.name}/frames/{filename}",
            "structure": structure,
            "analysis": {},
            "confirmed": False,
            "perceptualHash": f"{image_hash:016x}",
        })
        last_hash = image_hash
        last_kept_time = second
        progress(25 + round(38 * (index + 1) / len(samples)), f"关键帧结构扫描 {index + 1}/{len(samples)}")
    capture.release()

    scenes: list[dict[str, Any]] = []
    for scene_id in sorted({frame["sceneId"] for frame in frames}):
        scene_frames = [frame for frame in frames if frame["sceneId"] == scene_id]
        scenes.append({
            "id": scene_id,
            "start": min(frame["timestamp"] for frame in scene_frames),
            "end": max(frame["timestamp"] for frame in scene_frames),
            "frameIds": [frame["id"] for frame in scene_frames],
            "analysis": {},
        })
    return frames, scenes, list(tracks.values())


def _iou(left: list[int], right: list[int]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if not intersection:
        return 0.0
    left_area = max(1, (left[2] - left[0]) * (left[3] - left[1]))
    right_area = max(1, (right[2] - right[0]) * (right[3] - right[1]))
    return intersection / (left_area + right_area - intersection)


def _assign_tracks(elements: list[dict[str, Any]], previous: list[dict[str, Any]], tracks: dict[str, dict[str, Any]], frame_id: str, timestamp: float) -> None:
    for element in elements:
        candidates = [item for item in previous if item.get("class") == element.get("class") and item.get("trackId")]
        match = max(candidates, key=lambda item: _iou(item["bbox"], element["bbox"]), default=None)
        if match and _iou(match["bbox"], element["bbox"]) >= 0.38:
            track_id = match["trackId"]
        else:
            track_id = f"T{len(tracks) + 1:04d}"
            tracks[track_id] = {"id": track_id, "class": element.get("class", "component"), "observations": []}
        element["trackId"] = track_id
        tracks[track_id]["observations"].append({"frameId": frame_id, "timestamp": round(timestamp, 3), "bbox": element["bbox"]})
