from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path

import pytest
from fastapi import UploadFile
from PIL import Image

from backend.review_model import build_review_model, validate_review_model


def png_bytes(color: tuple[int, int, int] = (20, 40, 80)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (12, 20), color).save(output, format="PNG")
    return output.getvalue()


def upload(name: str, payload: bytes | None = None, content_type: str = "image/png") -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(png_bytes() if payload is None else payload), headers={"content-type": content_type})


def job() -> dict:
    source = {
        "id": "job-assets",
        "frames": [{"id": "F0001", "imageUrl": "/artifacts/job-assets/frames/F0001.jpg"}],
        "scenes": [{"id": 0, "frameIds": ["F0001"], "analysis": {}}],
    }
    source["reviewModel"] = build_review_model(source)
    return source


def test_reference_assets_are_isolated_from_primary_frames(tmp_path):
    from backend.reference_board_assets import persist_reference_assets

    current = job()
    before_frames = deepcopy(current["frames"])
    before_sources = deepcopy(current["reviewModel"]["sources"])

    assets = persist_reference_assets(
        current, tmp_path, "competitor", [upload("competitor_10.png"), upload("competitor_2.png")], '["competitor_2.png", "competitor_10.png"]'
    )
    assert [item["sourceName"] for item in assets] == ["competitor_2.png", "competitor_10.png"]
    assert [item["id"] for item in assets] == ["CPA-001", "CPA-002"]
    assert [item["relativePath"] for item in assets] == [
        "reference_boards/competitor/CPA-001.png", "reference_boards/competitor/CPA-002.png",
    ]
    assert all(item["status"] == "ready" for item in assets)
    assert current["frames"] == before_frames
    assert current["reviewModel"]["sources"] == before_sources
    assert validate_review_model(current["reviewModel"]) == []


def test_refresh_recovers_promoted_competitor_files_when_legacy_metadata_is_empty(tmp_path):
    from backend.reference_board_assets import refresh_reference_assets

    current = job()
    directory = tmp_path / "reference_boards" / "competitor"
    directory.mkdir(parents=True)
    (directory / "CPA-001.png").write_bytes(png_bytes())

    assert refresh_reference_assets(current, tmp_path, "competitor") is True
    board = current["reviewModel"]["referenceBoards"]["competitor"]
    assert board["status"] == "ready"
    assert board["assets"] == [{
        "id": "CPA-001", "order": 1, "sourceName": "CPA-001.png",
        "relativePath": "reference_boards/competitor/CPA-001.png",
        "mimeType": "image/png", "width": 12, "height": 20, "status": "ready",
    }]

def test_competitor_assets_use_natural_filename_order_and_stable_ids(tmp_path):
    from backend.reference_board_assets import persist_reference_assets

    current = job()
    competitor = persist_reference_assets(current, tmp_path, "competitor", [upload("competitor_10.png"), upload("competitor_2.png")], "")
    competitor = persist_reference_assets(current, tmp_path, "competitor", [upload("competitor_3.png")], "")

    assert [item["sourceName"] for item in competitor] == ["competitor_2.png", "competitor_10.png", "competitor_3.png"]
    assert [item["id"] for item in competitor] == ["CPA-001", "CPA-002", "CPA-003"]


@pytest.mark.parametrize("board_key", ["planning", "ux", "unknown", "../competitor"])
def test_reference_assets_reject_unsupported_board_keys(tmp_path, board_key):
    from backend.reference_board_assets import ReferenceBoardAssetError, persist_reference_assets

    with pytest.raises(ReferenceBoardAssetError, match="board"):
        persist_reference_assets(job(), tmp_path, board_key, [upload("asset.png")], "")


@pytest.mark.parametrize(
    ("uploads", "manifest", "message"),
    [
        ([upload("empty.png", b"")], "", "empty"),
        ([upload("broken.png", b"not an image")], "", "image"),
        ([upload("asset.gif", content_type="image/gif")], "", "format"),
        ([upload("../escape.png")], "", "filename"),
        ([upload("asset.png")], '["asset.png", "asset.png"]', "duplicate"),
        ([upload("asset.png")], '["../asset.png"]', "manifest"),
    ],
)
def test_reference_assets_reject_invalid_uploads_and_manifests(tmp_path, uploads, manifest, message):
    from backend.reference_board_assets import ReferenceBoardAssetError, persist_reference_assets

    with pytest.raises(ReferenceBoardAssetError, match=message):
        persist_reference_assets(job(), tmp_path, "competitor", uploads, manifest)


def test_competitor_assets_stop_at_the_active_board_cap(tmp_path):
    from backend.reference_board_assets import ReferenceBoardAssetError, persist_reference_assets

    current = job()
    persist_reference_assets(current, tmp_path, "competitor", [upload(f"competitor_{index}.png") for index in range(30)], "")

    with pytest.raises(ReferenceBoardAssetError, match="30"):
        persist_reference_assets(current, tmp_path, "competitor", [upload("too-many.png")], "")


def test_replace_missing_asset_at_capacity_keeps_its_stable_id_and_order(tmp_path):
    from backend.reference_board_assets import persist_reference_assets, refresh_reference_assets, replace_reference_asset

    current = job()
    persisted = persist_reference_assets(current, tmp_path, "competitor", [upload(f"competitor_{index}.png") for index in range(30)], "")
    missing = persisted[0]
    (tmp_path / missing["relativePath"]).unlink()
    refresh_reference_assets(current, tmp_path, "competitor")

    replaced = replace_reference_asset(current, tmp_path, "competitor", missing["id"], upload("recovered.png"))

    assert len(replaced) == 30
    assert replaced[0]["id"] == missing["id"]
    assert replaced[0]["order"] == missing["order"]
    assert replaced[0]["sourceName"] == "recovered.png"
    assert replaced[0]["status"] == "ready"
    assert (tmp_path / replaced[0]["relativePath"]).is_file()
    assert validate_review_model(current["reviewModel"]) == []


def test_replace_missing_asset_rolls_back_metadata_and_files_on_write_failure(tmp_path, monkeypatch):
    from backend import reference_board_assets

    current = job()
    persisted = reference_board_assets.persist_reference_assets(current, tmp_path, "competitor", [upload("missing.png")], "")
    (tmp_path / persisted[0]["relativePath"]).unlink()
    reference_board_assets.refresh_reference_assets(current, tmp_path, "competitor")
    before = deepcopy(current)

    monkeypatch.setattr(Path, "write_bytes", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(reference_board_assets.ReferenceBoardAssetError, match="save"):
        reference_board_assets.replace_reference_asset(current, tmp_path, "competitor", "CPA-001", upload("recovered.png"))

    assert current == before
    assert not list((tmp_path / "reference_boards" / "competitor").glob("*.tmp"))


def test_delete_and_reorder_reference_assets_recover_from_missing_files(tmp_path):
    from backend.reference_board_assets import (
        delete_reference_asset,
        persist_reference_assets,
        reorder_reference_assets,
    )

    current = job()
    persisted = persist_reference_assets(current, tmp_path, "competitor", [upload("first.png"), upload("second.png")], "")
    (tmp_path / persisted[0]["relativePath"]).unlink()
    refreshed = persist_reference_assets(current, tmp_path, "competitor", [upload("third.png")], "")

    assert refreshed[0]["status"] == "missing"
    ordered = reorder_reference_assets(current, tmp_path, "competitor", ["CPA-003", "CPA-002", "CPA-001"])
    assert [(item["id"], item["order"]) for item in ordered] == [("CPA-003", 1), ("CPA-002", 2), ("CPA-001", 3)]
    remaining = delete_reference_asset(current, tmp_path, "competitor", "CPA-001")
    assert [item["id"] for item in remaining] == ["CPA-003", "CPA-002"]
    assert [item["order"] for item in remaining] == [1, 2]


def test_reorder_requires_the_current_asset_ids(tmp_path):
    from backend.reference_board_assets import ReferenceBoardAssetError, persist_reference_assets, reorder_reference_assets

    current = job()
    persist_reference_assets(current, tmp_path, "competitor", [upload("asset.png")], "")

    with pytest.raises(ReferenceBoardAssetError, match="assetIds"):
        reorder_reference_assets(current, tmp_path, "competitor", ["CPA-999"])


def test_reference_asset_ids_do_not_reuse_deleted_numbers_after_json_reload(tmp_path):
    from backend.reference_board_assets import delete_reference_asset, persist_reference_assets

    current = job()
    persist_reference_assets(current, tmp_path, "competitor", [upload("first.png"), upload("second.png")], "")
    delete_reference_asset(current, tmp_path, "competitor", "CPA-002")
    reloaded = json.loads(json.dumps(current))

    assets = persist_reference_assets(reloaded, tmp_path, "competitor", [upload("replacement.png")], "")

    assert [asset["id"] for asset in assets] == ["CPA-001", "CPA-003"]
    assert reloaded["reviewModel"]["referenceBoards"]["competitor"]["assetIdHighWater"] == 3


def test_reference_asset_write_failure_is_atomic(tmp_path, monkeypatch):
    from backend import reference_board_assets

    current = job()
    before = deepcopy(current)
    original_write = Path.write_bytes
    writes = 0

    def fail_second_write(path, payload):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("disk full")
        return original_write(path, payload)

    monkeypatch.setattr(Path, "write_bytes", fail_second_write)

    with pytest.raises(reference_board_assets.ReferenceBoardAssetError, match="save"):
        reference_board_assets.persist_reference_assets(current, tmp_path, "competitor", [upload("first.png"), upload("second.png")], "")

    assert current == before
    assert not list((tmp_path / "reference_boards" / "competitor").glob("*"))


def test_partial_temporary_write_failure_removes_the_temporary_file(tmp_path, monkeypatch):
    from backend import reference_board_assets

    current = job()
    original_write = Path.write_bytes

    def write_partial_then_fail(path, payload):
        original_write(path, payload[:5])
        raise OSError("disk full after partial write")

    monkeypatch.setattr(Path, "write_bytes", write_partial_then_fail)

    with pytest.raises(reference_board_assets.ReferenceBoardAssetError, match="save"):
        reference_board_assets.persist_reference_assets(current, tmp_path, "competitor", [upload("partial.png")], "")

    assert not list((tmp_path / "reference_boards" / "competitor").glob("*"))


def test_cleanup_failure_is_observable_without_hiding_the_write_failure(tmp_path, monkeypatch):
    from backend import reference_board_assets

    original_write, original_unlink = Path.write_bytes, Path.unlink

    def write_partial_then_fail(path, payload):
        original_write(path, payload[:5])
        raise OSError("primary write failure")

    monkeypatch.setattr(Path, "write_bytes", write_partial_then_fail)
    monkeypatch.setattr(Path, "unlink", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup failure")))
    with pytest.raises(reference_board_assets.ReferenceBoardAssetError, match="unable to save") as raised:
        reference_board_assets.persist_reference_assets(job(), tmp_path, "competitor", [upload("partial.png")], "")
    monkeypatch.setattr(Path, "unlink", original_unlink)
    for path in (tmp_path / "reference_boards" / "competitor").glob("*"):
        path.unlink()

    assert raised.value.cleanup_failed is True
    assert "cleanup failed" in " ".join(getattr(raised.value, "__notes__", []))


def test_reference_asset_promotion_failure_removes_every_new_file(tmp_path, monkeypatch):
    from backend import reference_board_assets

    current = job()
    before = deepcopy(current)
    original_replace = reference_board_assets.os.replace
    promotions = 0

    def fail_second_promotion(source, target):
        nonlocal promotions
        promotions += 1
        if promotions == 2:
            raise OSError("replace failed")
        return original_replace(source, target)

    monkeypatch.setattr(reference_board_assets.os, "replace", fail_second_promotion)

    with pytest.raises(reference_board_assets.ReferenceBoardAssetError, match="save"):
        reference_board_assets.persist_reference_assets(current, tmp_path, "competitor", [upload("first.png"), upload("second.png")], "")

    assert current == before
    assert not list((tmp_path / "reference_boards" / "competitor").glob("*"))


@pytest.mark.parametrize(
    "relative_path",
    [
        "/tmp/absolute.png",
        r"C:\\assets\\absolute.png",
        r"\\\\server\\share\\asset.png",
        "reference_boards/competitor/C:drive.png",
        "reference_boards/competitor/./alias.png",
        "reference_boards//competitor/alias.png",
        "reference_boards/ux/wrong-board.png",
        "reference_boards/competitor/../escape.png",
        r"reference_boards\\competitor\\backslash.png",
    ],
)
def test_reference_model_rejects_noncanonical_asset_paths(relative_path):
    current = job()
    current["reviewModel"]["referenceBoards"]["competitor"]["assets"] = [{
        "id": "CPA-001", "relativePath": relative_path, "order": 1,
    }]

    assert any("relativePath" in error for error in validate_review_model(current["reviewModel"]))


def test_reference_model_validates_asset_id_high_water_mark():
    current = job()
    current["reviewModel"]["referenceBoards"]["competitor"].update(
        assetIdHighWater=2,
        assets=[{"id": "CPA-003", "relativePath": "reference_boards/competitor/CPA-003.png", "order": 1}],
    )

    assert any("assetIdHighWater" in error for error in validate_review_model(current["reviewModel"]))
