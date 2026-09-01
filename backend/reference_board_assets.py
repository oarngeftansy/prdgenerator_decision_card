from __future__ import annotations

import json
import os
import re
import uuid
from copy import deepcopy
from pathlib import Path, PureWindowsPath
from typing import Any

import cv2
import numpy as np
from fastapi import UploadFile

from .review_model import is_reference_asset_path


class ReferenceBoardAssetError(ValueError):
    pass


_BOARD_PREFIXES = {"competitor": "CPA"}
_IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_NATURAL_PARTS = re.compile(r"(\d+)")
_ASSET_ID = re.compile(r"^(UXA|CPA)-(\d+)$")
_MAX_ASSETS = 30


def _board(job: dict[str, Any], board_key: str) -> dict[str, Any]:
    if board_key not in _BOARD_PREFIXES:
        raise ReferenceBoardAssetError("only competitor reference board assets are mutable")
    board = ((job.get("reviewModel") or {}).get("referenceBoards") or {}).get(board_key)
    if not isinstance(board, dict) or not isinstance(board.get("assets"), list):
        raise ReferenceBoardAssetError("reference board assets unavailable")
    return board


def _board_assets(job: dict[str, Any], board_key: str) -> list[dict[str, Any]]:
    return _board(job, board_key)["assets"]


def _safe_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ReferenceBoardAssetError(f"invalid {label}")
    path, windows_path = Path(value), PureWindowsPath(value)
    if path.name != value or windows_path.name != value or value in {".", ".."}:
        raise ReferenceBoardAssetError(f"invalid {label}")
    return value


def _natural_key(name: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.casefold() for part in _NATURAL_PARTS.split(name)]


def _ordered_uploads(uploads: list[UploadFile], manifest: str) -> list[UploadFile]:
    names = [_safe_name(upload.filename or "", "filename") for upload in uploads]
    if len(set(names)) != len(names):
        raise ReferenceBoardAssetError("duplicate upload filename")
    if not manifest.strip():
        return sorted(uploads, key=lambda upload: _natural_key(upload.filename or ""))
    try:
        requested = json.loads(manifest)
    except json.JSONDecodeError as exc:
        raise ReferenceBoardAssetError("invalid manifest") from exc
    if not isinstance(requested, list) or any(not isinstance(name, str) for name in requested):
        raise ReferenceBoardAssetError("invalid manifest")
    requested = [_safe_name(name, "manifest filename") for name in requested]
    if len(requested) != len(set(requested)):
        raise ReferenceBoardAssetError("duplicate manifest filename")
    if set(requested) != set(names):
        raise ReferenceBoardAssetError("manifest does not match uploads")
    by_name = dict(zip(names, uploads))
    return [by_name[name] for name in requested]


def _decode(upload: UploadFile, payload: bytes) -> tuple[str, int, int]:
    suffix = Path(_safe_name(upload.filename or "", "filename")).suffix.lower()
    if _IMAGE_TYPES.get(suffix) != upload.content_type:
        raise ReferenceBoardAssetError("unsupported image format")
    if not payload:
        raise ReferenceBoardAssetError("empty image")
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or not image.size:
        raise ReferenceBoardAssetError("invalid image")
    height, width = image.shape[:2]
    return suffix, width, height


def _board_dir(job_dir: Path, board_key: str) -> tuple[Path, Path]:
    root = job_dir.resolve()
    directory = (root / "reference_boards" / board_key).resolve()
    if root not in directory.parents:
        raise ReferenceBoardAssetError("invalid board path")
    return root, directory


def _asset_path(root: Path, directory: Path, asset: dict[str, Any]) -> Path | None:
    relative_path = asset.get("relativePath")
    if not is_reference_asset_path(directory.name, relative_path):
        return None
    candidate = (root / relative_path).resolve()
    return candidate if candidate.parent == directory and root in candidate.parents else None


def refresh_reference_assets(job: dict[str, Any], job_dir: Path, board_key: str) -> bool:
    assets = _board_assets(job, board_key)
    root, directory = _board_dir(job_dir, board_key)
    changed = False
    # Recover files that were already accepted and promoted but whose metadata
    # was lost by an older task migration. This is deliberately limited to an
    # empty board and stable CPA filenames; normal user deletion removes files.
    if not assets and directory.is_dir():
        recovered = []
        for candidate in sorted(directory.iterdir(), key=lambda path: _natural_key(path.name)):
            match = re.fullmatch(r"CPA-(\d+)\.(jpg|jpeg|png|webp)", candidate.name, re.I)
            if not candidate.is_file() or not match:
                continue
            payload = np.fromfile(str(candidate), dtype=np.uint8)
            image = cv2.imdecode(payload, cv2.IMREAD_COLOR)
            if image is None or not image.size:
                continue
            height, width = image.shape[:2]
            number = int(match.group(1))
            recovered.append({
                "id": f"CPA-{number:03d}",
                "order": number,
                "sourceName": candidate.name,
                "relativePath": candidate.relative_to(root).as_posix(),
                "mimeType": _IMAGE_TYPES.get(candidate.suffix.lower(), "image/jpeg"),
                "width": width,
                "height": height,
                "status": "ready",
            })
        if recovered:
            assets.extend(recovered)
            board = _board(job, board_key)
            board["assetIdHighWater"] = max(int(item["id"].split("-")[1]) for item in recovered)
            board["status"] = "ready"
            changed = True
    for asset in assets:
        if not isinstance(asset, dict):
            raise ReferenceBoardAssetError("invalid reference asset")
        target = _asset_path(root, directory, asset)
        if target is None:
            raise ReferenceBoardAssetError("invalid reference asset path")
        status = "ready" if target.is_file() else "missing"
        if asset.get("status") != status:
            asset["status"] = status
            changed = True
    return changed


def _next_asset_number(board: dict[str, Any], prefix: str) -> int:
    assets = board["assets"]
    numbers = [int(match.group(2)) for asset in assets if isinstance(asset, dict) and (match := _ASSET_ID.match(str(asset.get("id", "")))) and match.group(1) == prefix]
    stored = board.get("assetIdHighWater", 0)
    if type(stored) is not int or stored < 0:
        raise ReferenceBoardAssetError("invalid reference asset high-water mark")
    return max(stored, max(numbers, default=0)) + 1


def _restore_board(board: dict[str, Any], snapshot: dict[str, Any]) -> None:
    board.clear()
    board.update(snapshot)


def _remove_paths(paths: list[Path]) -> list[OSError]:
    failures = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            failures.append(exc)
    return failures


def _record_cleanup_failures(error: Exception, failures: list[OSError]) -> None:
    if failures:
        error.cleanup_failed = True
        error.add_note("reference asset cleanup failed")


def persist_reference_assets(job: dict, job_dir: Path, board_key: str, uploads: list[UploadFile], manifest: str) -> list[dict]:
    board = _board(job, board_key)
    assets = board["assets"]
    if not uploads:
        raise ReferenceBoardAssetError("at least one image is required")
    if len(assets) + len(uploads) > _MAX_ASSETS:
        raise ReferenceBoardAssetError("reference board supports at most 30 assets")
    ordered_uploads = _ordered_uploads(uploads, manifest)
    decoded = []
    for upload in ordered_uploads:
        payload = upload.file.read()
        upload.file.seek(0)
        suffix, width, height = _decode(upload, payload)
        decoded.append((_safe_name(upload.filename or "", "filename"), payload, suffix, width, height))
    snapshot = deepcopy(board)
    temporary, promoted = [], []
    try:
        root, directory = _board_dir(job_dir, board_key)
        directory.mkdir(parents=True, exist_ok=True)
        refresh_reference_assets(job, job_dir, board_key)
        prefix, number = _BOARD_PREFIXES[board_key], _next_asset_number(board, _BOARD_PREFIXES[board_key])
        next_order = max((asset.get("order", 0) for asset in assets if isinstance(asset, dict) and type(asset.get("order")) is int), default=0)
        new_assets, staged = [], []
        for source_name, payload, suffix, width, height in decoded:
            asset_id = f"{prefix}-{number:03d}"
            target = (directory / f"{asset_id}{suffix}").resolve()
            if target.parent != directory:
                raise ReferenceBoardAssetError("invalid asset path")
            temporary_path = directory / f".{asset_id}.{uuid.uuid4().hex}.tmp"
            temporary.append(temporary_path)
            temporary_path.write_bytes(payload)
            staged.append((temporary_path, target))
            next_order += 1
            new_assets.append({
                "id": asset_id, "sourceName": source_name, "order": next_order,
                "relativePath": target.relative_to(root).as_posix(), "width": width,
                "height": height, "status": "ready",
            })
            number += 1
        for temporary_path, target in staged:
            os.replace(temporary_path, target)
            promoted.append(target)
        assets.extend(new_assets)
        assets.sort(key=lambda asset: asset.get("order", 0))
        board["assetIdHighWater"] = number - 1
        return assets
    except OSError as exc:
        cleanup_failures = _remove_paths(temporary + promoted)
        _restore_board(board, snapshot)
        failure = ReferenceBoardAssetError("unable to save reference assets")
        _record_cleanup_failures(failure, cleanup_failures)
        raise failure from exc
    except ReferenceBoardAssetError as exc:
        _record_cleanup_failures(exc, _remove_paths(temporary + promoted))
        _restore_board(board, snapshot)
        raise


def replace_reference_asset(job: dict, job_dir: Path, board_key: str, asset_id: str, upload: UploadFile) -> list[dict]:
    board = _board(job, board_key)
    snapshot = deepcopy(board)
    temporary, promoted = [], []
    try:
        root, directory = _board_dir(job_dir, board_key)
        refresh_reference_assets(job, job_dir, board_key)
        asset = next((item for item in board["assets"] if isinstance(item, dict) and item.get("id") == asset_id), None)
        if asset is None or asset.get("status") != "missing":
            raise ReferenceBoardAssetError("reference asset is not missing")
        payload = upload.file.read()
        upload.file.seek(0)
        suffix, width, height = _decode(upload, payload)
        directory.mkdir(parents=True, exist_ok=True)
        target = (directory / f"{asset_id}{suffix}").resolve()
        if target.parent != directory:
            raise ReferenceBoardAssetError("invalid asset path")
        temporary_path = directory / f".{asset_id}.{uuid.uuid4().hex}.tmp"
        temporary.append(temporary_path)
        temporary_path.write_bytes(payload)
        os.replace(temporary_path, target)
        promoted.append(target)
        asset.update({
            "sourceName": _safe_name(upload.filename or "", "filename"),
            "relativePath": target.relative_to(root).as_posix(),
            "width": width,
            "height": height,
            "status": "ready",
        })
        return board["assets"]
    except OSError as exc:
        cleanup_failures = _remove_paths(temporary + promoted)
        _restore_board(board, snapshot)
        failure = ReferenceBoardAssetError("unable to save reference assets")
        _record_cleanup_failures(failure, cleanup_failures)
        raise failure from exc
    except ReferenceBoardAssetError as exc:
        _record_cleanup_failures(exc, _remove_paths(temporary + promoted))
        _restore_board(board, snapshot)
        raise


def delete_reference_asset(job: dict, job_dir: Path, board_key: str, asset_id: str) -> list[dict]:
    assets = _board_assets(job, board_key)
    refresh_reference_assets(job, job_dir, board_key)
    if not isinstance(asset_id, str) or not asset_id:
        raise ReferenceBoardAssetError("invalid asset id")
    asset = next((item for item in assets if isinstance(item, dict) and item.get("id") == asset_id), None)
    if asset is None:
        raise ReferenceBoardAssetError("reference asset not found")
    root, directory = _board_dir(job_dir, board_key)
    target = _asset_path(root, directory, asset)
    if target is None:
        raise ReferenceBoardAssetError("invalid asset path")
    if target.exists():
        target.unlink()
    assets.remove(asset)
    assets.sort(key=lambda item: item.get("order", 0))
    for index, item in enumerate(assets, 1):
        item["order"] = index
    return assets


def reorder_reference_assets(job: dict, job_dir: Path, board_key: str, asset_ids: list[str]) -> list[dict]:
    assets = _board_assets(job, board_key)
    refresh_reference_assets(job, job_dir, board_key)
    if not isinstance(asset_ids, list) or any(not isinstance(asset_id, str) for asset_id in asset_ids):
        raise ReferenceBoardAssetError("assetIds must be a list of ids")
    current_ids = [asset.get("id") for asset in assets if isinstance(asset, dict)]
    if len(asset_ids) != len(set(asset_ids)) or set(asset_ids) != set(current_ids) or len(current_ids) != len(assets):
        raise ReferenceBoardAssetError("assetIds must match current reference assets")
    by_id = {asset["id"]: asset for asset in assets}
    assets[:] = [by_id[asset_id] for asset_id in asset_ids]
    for index, asset in enumerate(assets, 1):
        asset["order"] = index
    return assets


def rollback_reference_assets(job: dict[str, Any], job_dir: Path, board_key: str, previous_board: dict[str, Any]) -> list[OSError]:
    board = _board(job, board_key)
    previous_paths = {
        asset.get("relativePath") for asset in previous_board.get("assets", []) if isinstance(asset, dict)
    }
    root, directory = _board_dir(job_dir, board_key)
    created = [
        target for asset in board["assets"] if isinstance(asset, dict) and asset.get("relativePath") not in previous_paths
        if (target := _asset_path(root, directory, asset)) is not None
    ]
    failures = _remove_paths(created)
    _restore_board(board, previous_board)
    return failures


def rollback_replaced_reference_asset(job: dict[str, Any], job_dir: Path, board_key: str, asset_id: str, previous_board: dict[str, Any]) -> list[OSError]:
    board = _board(job, board_key)
    root, directory = _board_dir(job_dir, board_key)
    asset = next((item for item in board["assets"] if isinstance(item, dict) and item.get("id") == asset_id), None)
    target = _asset_path(root, directory, asset) if asset else None
    failures = _remove_paths([target] if target is not None else [])
    _restore_board(board, previous_board)
    return failures
