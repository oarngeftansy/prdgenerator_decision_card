from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import UploadFile

from .image_io import read_image, write_jpeg
from .screen_adapter import ScreenCoderAdapter
from .video_pipeline import _assign_tracks, _difference_hash


class ImageSequenceError(ValueError):
    pass


_FORMATS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _write_import_manifest(job_dir: Path, payload: dict[str, Any]) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    target = job_dir / "image-import-manifest.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def _parse_manifest(raw: str) -> list[dict[str, Any]]:
    try:
        items = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ImageSequenceError("图片清单不是有效 JSON") from exc
    if not isinstance(items, list):
        raise ImageSequenceError("图片清单必须是数组")
    required = {"clientId", "originalName", "order"}
    if any(not isinstance(item, dict) or set(item) != required for item in items):
        raise ImageSequenceError("图片清单字段不完整")
    if any(not isinstance(item["clientId"], str) or not isinstance(item["originalName"], str) or not isinstance(item["order"], int) for item in items):
        raise ImageSequenceError("图片清单字段类型错误")
    if [item["order"] for item in items] != list(range(1, len(items) + 1)):
        raise ImageSequenceError("图片清单顺序必须从 1 连续递增")
    if len({item["clientId"] for item in items}) != len(items):
        raise ImageSequenceError("图片清单客户端 ID 重复")
    if len({item["originalName"] for item in items}) != len(items):
        raise ImageSequenceError("图片清单存在重复文件名")
    return items


def _decode(upload: UploadFile, payload: bytes) -> np.ndarray:
    suffix = Path(upload.filename or "").suffix.lower()
    expected_type = _FORMATS.get(suffix)
    if not expected_type or upload.content_type != expected_type:
        raise ImageSequenceError(f"不支持的图片格式：{upload.filename}")
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or not image.size:
        raise ImageSequenceError(f"图片损坏或无法读取：{upload.filename}")
    return image


def persist_image_sequence(
    job_dir: Path,
    uploads: list[UploadFile],
    manifest_json: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not 2 <= len(uploads) <= 50:
        raise ImageSequenceError("截图数量必须为 2–50 张")
    manifest = _parse_manifest(manifest_json)
    if len(manifest) != len(uploads):
        raise ImageSequenceError("图片清单数量与上传文件数量不一致")

    upload_by_name = {upload.filename: upload for upload in uploads}
    if len(upload_by_name) != len(uploads):
        raise ImageSequenceError("上传图片存在重复文件名")
    if set(upload_by_name) != {item["originalName"] for item in manifest}:
        raise ImageSequenceError("图片清单文件名与上传文件不一致")

    _write_import_manifest(job_dir, {
        "schemaVersion": 1,
        "status": "preparing",
        "expectedCount": len(manifest),
        "items": manifest,
    })

    decoded = []
    for entry in manifest:
        upload = upload_by_name[entry["originalName"]]
        payload = upload.file.read()
        decoded.append((entry, upload, payload, _decode(upload, payload)))

    frames_dir = job_dir / "frames"
    structures_dir = job_dir / "structures"
    sources_dir = job_dir / "source_images"
    for directory in (frames_dir, structures_dir, sources_dir):
        directory.mkdir(parents=True, exist_ok=True)

    adapter = ScreenCoderAdapter()
    frames: list[dict[str, Any]] = []
    scenes: list[dict[str, Any]] = []
    tracks: dict[str, dict[str, Any]] = {}
    previous_elements: list[dict[str, Any]] = []
    for index, (entry, upload, payload, image) in enumerate(decoded, 1):
        frame_id = f"F{index:04d}"
        source_name = f"{frame_id}{Path(upload.filename or '').suffix.lower()}"
        (sources_dir / source_name).write_bytes(payload)
        frame_name = f"{frame_id}.jpg"
        frame_path = frames_dir / frame_name
        if not write_jpeg(frame_path, image, 90):
            raise ImageSequenceError(f"图片保存失败：{upload.filename}")
        structure = adapter.analyze(frame_path, structures_dir)
        timestamp = float(index - 1)
        _assign_tracks(structure.get("elements", []), previous_elements, tracks, frame_id, timestamp)
        previous_elements = structure.get("elements", [])
        frames.append({
            "id": frame_id,
            "timestamp": timestamp,
            "sequenceIndex": index,
            "sceneId": index - 1,
            "sourceName": entry["originalName"],
            "imageUrl": f"/artifacts/{job_dir.name}/frames/{frame_name}",
            "structure": structure,
            "analysis": {},
            "confirmed": False,
            "perceptualHash": f"{_difference_hash(image):016x}",
        })
        scenes.append({
            "id": index - 1,
            "start": timestamp,
            "end": timestamp,
            "frameIds": [frame_id],
            "analysis": {},
        })
    _write_import_manifest(job_dir, {
        "schemaVersion": 1,
        "status": "complete",
        "expectedCount": len(manifest),
        "items": manifest,
    })
    return frames, scenes, list(tracks.values())


def recover_persisted_image_sequence(
    job_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]] | None:
    frames_dir = job_dir / "frames"
    structures_dir = job_dir / "structures"
    sources_dir = job_dir / "source_images"
    if not all(directory.is_dir() for directory in (frames_dir, structures_dir, sources_dir)):
        return None

    frame_paths = {path.stem: path for path in frames_dir.glob("F*.jpg") if path.is_file()}
    structure_paths = {
        path.name.removesuffix(".structure.json"): path
        for path in structures_dir.glob("F*.structure.json")
        if path.is_file()
    }
    source_paths = {path.stem: path for path in sources_dir.glob("F*.*") if path.is_file()}
    frame_ids = sorted(set(frame_paths) & set(structure_paths) & set(source_paths))
    if not 2 <= len(frame_ids) <= 50:
        return None
    if frame_ids != [f"F{index:04d}" for index in range(1, len(frame_ids) + 1)]:
        return None
    if set(frame_paths) != set(frame_ids) or set(structure_paths) != set(frame_ids) or set(source_paths) != set(frame_ids):
        return None

    manifest_path = job_dir / "image-import-manifest.json"
    manifest_items: list[dict[str, Any]] = []
    if manifest_path.exists():
        try:
            import_record = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected_count = int(import_record.get("expectedCount") or 0)
            manifest_items = import_record.get("items") or []
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if expected_count != len(frame_ids) or len(manifest_items) != len(frame_ids):
            return None

    frames: list[dict[str, Any]] = []
    scenes: list[dict[str, Any]] = []
    tracks: dict[str, dict[str, Any]] = {}
    previous_elements: list[dict[str, Any]] = []
    for index, frame_id in enumerate(frame_ids, 1):
        try:
            structure = json.loads(structure_paths[frame_id].read_text(encoding="utf-8"))
            image = read_image(frame_paths[frame_id])
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if image is None or not image.size or not isinstance(structure, dict):
            return None
        timestamp = float(index - 1)
        elements = structure.get("elements") if isinstance(structure.get("elements"), list) else []
        _assign_tracks(elements, previous_elements, tracks, frame_id, timestamp)
        previous_elements = elements
        source_name = (
            str(manifest_items[index - 1].get("originalName") or source_paths[frame_id].name)
            if manifest_items else source_paths[frame_id].name
        )
        frames.append({
            "id": frame_id,
            "timestamp": timestamp,
            "sequenceIndex": index,
            "sceneId": index - 1,
            "sourceName": source_name,
            "imageUrl": f"/artifacts/{job_dir.name}/frames/{frame_paths[frame_id].name}",
            "structure": structure,
            "analysis": {},
            "confirmed": False,
            "perceptualHash": f"{_difference_hash(image):016x}",
        })
        scenes.append({
            "id": index - 1,
            "start": timestamp,
            "end": timestamp,
            "frameIds": [frame_id],
            "analysis": {},
        })
    return frames, scenes, list(tracks.values())
