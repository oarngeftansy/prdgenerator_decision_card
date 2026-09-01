from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import server
from tests.review_fixtures import make_confirmed_job


def png_bytes(color: tuple[int, int, int] = (20, 40, 80)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (12, 20), color).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def reference_api(tmp_path, monkeypatch):
    job = make_confirmed_job()
    job["id"] = "job-reference-assets"
    job["reviewModel"]["jobId"] = job["id"]
    job["reviewModel"]["ruleDomains"] = {"legacy": "preserve"}
    job["reviewModel"]["referenceBoards"]["ux"] = {"assets": [{"legacy": "preserve"}], "status": "ready"}
    job_dir = tmp_path / job["id"]
    job_dir.mkdir()
    store = {job["id"]: job}
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server, "job_path", lambda job_id: job_dir)
    return TestClient(server.app), job, store, job_dir


def _upload(client, job, board_key, names):
    return client.post(
        f"/api/jobs/{job['id']}/review-model/reference-boards/{board_key}/assets",
        files=[("images", (name, png_bytes(), "image/png")) for name in names],
        data={"manifest": json.dumps(names), "expectedRevision": str(job["reviewModel"]["revision"])},
    )


def test_upload_reference_board_assets_updates_only_requested_board(reference_api):
    client, job, store, job_dir = reference_api
    revision = job["reviewModel"]["revision"]
    legacy_rules = dict(job["reviewModel"]["ruleDomains"])
    legacy_ux = dict(job["reviewModel"]["referenceBoards"]["ux"])

    response = _upload(client, job, "competitor", ["competitor_2.png", "competitor_10.png"])

    assert response.status_code == 200
    model = response.json()
    assert [asset["sourceName"] for asset in model["referenceBoards"]["competitor"]["assets"]] == ["competitor_2.png", "competitor_10.png"]
    assert model["revision"] == revision + 1
    assert model["reviewState"]["previewRevision"] is None
    assert model["ruleDomains"] == legacy_rules
    assert model["referenceBoards"]["ux"] == legacy_ux
    assert str(job_dir) not in json.dumps(model)
    assert store[job["id"]]["reviewModel"]["revision"] == model["revision"]
    assert store[job["id"]]["reviewModel"]["referenceBoards"] == model["referenceBoards"]


def test_reference_asset_upload_rejects_stale_revisions_and_board_keys(reference_api):
    client, job, _, _ = reference_api

    stale = client.post(
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/assets",
        files=[("images", ("asset.png", png_bytes(), "image/png"))],
        data={"expectedRevision": str(job["reviewModel"]["revision"] - 1)},
    )
    ux = _upload(client, job, "ux", ["asset.png"])
    planning = _upload(client, job, "planning", ["asset.png"])

    assert stale.status_code == 409
    assert stale.json()["detail"] == {"currentRevision": job["reviewModel"]["revision"]}
    assert ux.status_code == 400
    assert planning.status_code == 400


@pytest.mark.parametrize("operation", ["upload", "replace", "delete", "reorder"])
def test_valid_legacy_ux_board_mutations_are_rejected_before_model_or_filesystem_changes(reference_api, operation):
    client, job, _, job_dir = reference_api
    ux_dir = job_dir / "reference_boards" / "ux"
    ux_dir.mkdir(parents=True)
    ready_path = ux_dir / "UXA-002.png"
    ready_path.write_bytes(png_bytes((90, 40, 10)))
    job["reviewModel"]["referenceBoards"]["ux"] = {
        "assets": [
            {
                "id": "UXA-001", "sourceName": "missing.png", "order": 1,
                "relativePath": "reference_boards/ux/UXA-001.png", "width": 12, "height": 20, "status": "missing",
            },
            {
                "id": "UXA-002", "sourceName": "ready.png", "order": 2,
                "relativePath": "reference_boards/ux/UXA-002.png", "width": 12, "height": 20, "status": "ready",
            },
        ],
        "assetIdHighWater": 2,
        "status": "ready",
    }
    revision = job["reviewModel"]["revision"]
    before_model = json.dumps(job["reviewModel"], ensure_ascii=False, sort_keys=True)
    before_files = {path.relative_to(job_dir).as_posix(): path.read_bytes() for path in job_dir.rglob("*") if path.is_file()}

    if operation == "upload":
        response = _upload(client, job, "ux", ["new.png"])
    elif operation == "replace":
        response = client.post(
            f"/api/jobs/{job['id']}/review-model/reference-boards/ux/assets/UXA-001/replace",
            files={"image": ("recovered.png", png_bytes(), "image/png")},
            data={"expectedRevision": str(revision)},
        )
    elif operation == "delete":
        response = client.request(
            "DELETE", f"/api/jobs/{job['id']}/review-model/reference-boards/ux/assets/UXA-002",
            json={"expectedRevision": revision},
        )
    else:
        response = client.post(
            f"/api/jobs/{job['id']}/review-model/reference-boards/ux/order",
            json={"assetIds": ["UXA-002", "UXA-001"], "expectedRevision": revision},
        )

    assert response.status_code == 400
    assert "competitor" in response.text.lower()
    assert json.dumps(job["reviewModel"], ensure_ascii=False, sort_keys=True) == before_model
    assert {path.relative_to(job_dir).as_posix(): path.read_bytes() for path in job_dir.rglob("*") if path.is_file()} == before_files


def test_replace_missing_asset_is_atomic_at_capacity_and_returns_the_canonical_model(reference_api):
    client, job, _, job_dir = reference_api
    uploaded = _upload(client, job, "competitor", [f"asset-{index}.png" for index in range(30)])
    assert uploaded.status_code == 200
    missing = uploaded.json()["referenceBoards"]["competitor"]["assets"][0]
    (job_dir / missing["relativePath"]).unlink()
    refreshed = client.get(f"/api/jobs/{job['id']}/review-model")
    revision = refreshed.json()["revision"]
    legacy_rules = dict(refreshed.json()["ruleDomains"])

    stale = client.post(
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/assets/{missing['id']}/replace",
        files={"image": ("recovered.png", png_bytes(), "image/png")},
        data={"expectedRevision": str(revision - 1)},
    )
    replaced = client.post(
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/assets/{missing['id']}/replace",
        files={"image": ("recovered.png", png_bytes(), "image/png")},
        data={"expectedRevision": str(revision)},
    )

    assert stale.status_code == 409
    assert stale.json()["detail"] == {"currentRevision": revision}
    assert replaced.status_code == 200
    model = replaced.json()
    assert model["revision"] == revision + 1
    assert len(model["referenceBoards"]["competitor"]["assets"]) == 30
    assert model["referenceBoards"]["competitor"]["assets"][0]["id"] == missing["id"]
    assert model["referenceBoards"]["competitor"]["assets"][0]["sourceName"] == "recovered.png"
    assert model["reviewState"]["previewRevision"] is None
    assert model["ruleDomains"] == legacy_rules


def test_delete_and_reorder_reference_assets_update_the_canonical_revision(reference_api):
    client, job, _, _ = reference_api
    uploaded = _upload(client, job, "competitor", ["first.png", "second.png"])
    assert uploaded.status_code == 200
    uploaded_model = uploaded.json()
    revision = uploaded_model["revision"]

    ordered = client.post(
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/order",
        json={"assetIds": ["CPA-002", "CPA-001"], "expectedRevision": revision},
    )
    assert ordered.status_code == 200
    assert [asset["id"] for asset in ordered.json()["referenceBoards"]["competitor"]["assets"]] == ["CPA-002", "CPA-001"]

    removed = client.request(
        "DELETE",
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/assets/CPA-002",
        json={"expectedRevision": ordered.json()["revision"]},
    )
    assert removed.status_code == 200
    assert [asset["id"] for asset in removed.json()["referenceBoards"]["competitor"]["assets"]] == ["CPA-001"]
    assert removed.json()["revision"] == revision + 2


def test_upload_rolls_back_files_and_model_when_final_validation_fails(reference_api):
    client, job, _, job_dir = reference_api
    job["reviewModel"]["jobId"] = ""

    response = _upload(client, job, "competitor", ["new.png"])

    assert response.status_code == 400
    assert job["reviewModel"]["referenceBoards"]["competitor"]["assets"] == []
    assert not list((job_dir / "reference_boards" / "competitor").glob("*"))


def test_reference_asset_get_refreshes_missing_status_and_persists(reference_api):
    client, job, store, job_dir = reference_api
    assert _upload(client, job, "competitor", ["asset.png"]).status_code == 200
    asset = job["reviewModel"]["referenceBoards"]["competitor"]["assets"][0]
    (job_dir / asset["relativePath"]).unlink()

    response = client.get(f"/api/jobs/{job['id']}/review-model")

    assert response.status_code == 200
    assert response.json()["referenceBoards"]["competitor"]["assets"][0]["status"] == "missing"
    assert store[job["id"]]["reviewModel"]["referenceBoards"]["competitor"]["assets"][0]["status"] == "missing"


def test_missing_asset_get_advances_revision_once_and_invalidates_preview(reference_api):
    client, job, _, job_dir = reference_api
    assert _upload(client, job, "competitor", ["asset.png"]).status_code == 200
    model = job["reviewModel"]
    model["reviewState"]["previewRevision"] = model["revision"]
    legacy_rules = dict(model["ruleDomains"])
    (job_dir / model["referenceBoards"]["competitor"]["assets"][0]["relativePath"]).unlink()
    before = model["revision"]

    refreshed = client.get(f"/api/jobs/{job['id']}/review-model")
    unchanged = client.get(f"/api/jobs/{job['id']}/review-model")

    assert refreshed.status_code == 200
    assert refreshed.json()["revision"] == before + 1
    assert refreshed.json()["reviewState"]["previewRevision"] is None
    assert refreshed.json()["ruleDomains"] == legacy_rules
    assert unchanged.status_code == 200
    assert unchanged.json()["revision"] == before + 1


def test_get_refreshes_the_active_competitor_board_in_one_revision(reference_api):
    client, job, _, job_dir = reference_api
    assert _upload(client, job, "competitor", ["competitor.png"]).status_code == 200
    model = job["reviewModel"]
    (job_dir / model["referenceBoards"]["competitor"]["assets"][0]["relativePath"]).unlink()
    before = model["revision"]

    response = client.get(f"/api/jobs/{job['id']}/review-model")

    assert response.status_code == 200
    assert response.json()["revision"] == before + 1
    assert response.json()["referenceBoards"]["competitor"]["assets"][0]["status"] == "missing"


def test_public_job_get_refreshes_missing_status(reference_api):
    client, job, _, job_dir = reference_api
    assert _upload(client, job, "competitor", ["asset.png"]).status_code == 200
    asset = job["reviewModel"]["referenceBoards"]["competitor"]["assets"][0]
    (job_dir / asset["relativePath"]).unlink()

    response = client.get(f"/api/jobs/{job['id']}")

    assert response.status_code == 200
    assert response.json()["reviewModel"]["referenceBoards"]["competitor"]["assets"][0]["status"] == "missing"


def test_unchanged_public_and_review_gets_do_not_rewrite_job(reference_api, monkeypatch):
    client, job, _, _ = reference_api
    monkeypatch.setattr(server.storage, "mutate_job", lambda *_args: (_ for _ in ()).throw(AssertionError("read-only GET rewrote the job")))

    public_response = client.get(f"/api/jobs/{job['id']}")
    review_response = client.get(f"/api/jobs/{job['id']}/review-model")

    assert public_response.status_code == 200
    assert review_response.status_code == 200


def test_reference_asset_reorder_refreshes_missing_status(reference_api):
    client, job, _, job_dir = reference_api
    assert _upload(client, job, "competitor", ["first.png", "second.png"]).status_code == 200
    asset = job["reviewModel"]["referenceBoards"]["competitor"]["assets"][0]
    (job_dir / asset["relativePath"]).unlink()
    before = job["reviewModel"]["revision"]

    response = client.post(
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/order",
        json={"assetIds": ["CPA-002", "CPA-001"], "expectedRevision": job["reviewModel"]["revision"]},
    )

    assert response.status_code == 200
    assert response.json()["revision"] == before + 1
    assert response.json()["referenceBoards"]["competitor"]["assets"][1]["status"] == "missing"


def test_reference_asset_delete_refreshes_missing_status_on_remaining_asset(reference_api):
    client, job, _, job_dir = reference_api
    assert _upload(client, job, "competitor", ["first.png", "second.png"]).status_code == 200
    missing = job["reviewModel"]["referenceBoards"]["competitor"]["assets"][0]
    (job_dir / missing["relativePath"]).unlink()
    before = job["reviewModel"]["revision"]

    response = client.request(
        "DELETE",
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/assets/CPA-002",
        json={"expectedRevision": job["reviewModel"]["revision"]},
    )

    assert response.status_code == 200
    assert response.json()["revision"] == before + 1
    assert response.json()["referenceBoards"]["competitor"]["assets"] == [{
        **missing, "status": "missing",
    }]


def test_corrupt_absolute_reference_path_is_rejected_without_leaking(reference_api):
    client, job, _, job_dir = reference_api
    absolute_path = str(job_dir / "reference_boards" / "competitor" / "CPA-001.png")
    target = Path(absolute_path)
    target.parent.mkdir(parents=True)
    target.write_bytes(png_bytes())
    job["reviewModel"]["referenceBoards"]["competitor"]["assets"] = [{
        "id": "CPA-001", "sourceName": "asset.png", "order": 1,
        "relativePath": absolute_path, "width": 12, "height": 20, "status": "ready",
    }]

    response = client.post(
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/order",
        json={"assetIds": ["CPA-001"], "expectedRevision": job["reviewModel"]["revision"]},
    )

    assert response.status_code == 400
    assert absolute_path not in response.text

    fetched = client.get(f"/api/jobs/{job['id']}/review-model")
    assert fetched.status_code == 400
    assert absolute_path not in fetched.text

    public = client.get(f"/api/jobs/{job['id']}")
    assert public.status_code == 400
    assert absolute_path not in public.text

    removed = client.request(
        "DELETE",
        f"/api/jobs/{job['id']}/review-model/reference-boards/competitor/assets/CPA-001",
        json={"expectedRevision": job["reviewModel"]["revision"]},
    )
    assert removed.status_code == 400
    assert absolute_path not in removed.text
    assert target.exists()
