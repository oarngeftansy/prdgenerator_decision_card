from copy import deepcopy
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import server
from backend.review_model import review_gate
from tests.review_fixtures import make_confirmed_job


@pytest.fixture
def legacy_three_board_job(tmp_path, monkeypatch):
    job = make_confirmed_job()
    job["id"] = "legacy-three-board"
    job["reviewModel"]["jobId"] = job["id"]
    job["reviewModel"]["ruleDomains"] = {
        "confirmation": {"confirmed": True, "revision": 7},
        "legacyRule": {"title": "keep this historical rule"},
    }
    job["reviewModel"]["referenceBoards"]["ux"] = {
        "assets": [{"legacy": "keep this historical UX board"}],
        "status": "ready",
    }
    job_dir = tmp_path / job["id"]
    frames = job_dir / "frames"
    frames.mkdir(parents=True)
    for frame in job["frames"]:
        frame["imagePath"] = f"frames/{frame['id']}.jpg"
        image = Image.new("RGB", (12, 20), (20, 40, 80))
        image.save(frames / f"{frame['id']}.jpg", format="JPEG")
    store = {job["id"]: job}
    monkeypatch.setattr(server, "load_job", lambda job_id: store[job_id])
    monkeypatch.setattr(server.storage, "mutate_job", lambda job_id, mutation: mutation(store[job_id]))
    monkeypatch.setattr(server, "job_path", lambda job_id: job_dir)
    return job


@pytest.fixture
def client():
    return TestClient(server.app)


def test_legacy_three_board_job_completes_new_two_board_workflow(client, legacy_three_board_job):
    job_id = legacy_three_board_job["id"]
    legacy_rules = deepcopy(legacy_three_board_job["reviewModel"]["ruleDomains"])
    legacy_ux = deepcopy(legacy_three_board_job["reviewModel"]["referenceBoards"]["ux"])

    model = client.get(f"/api/jobs/{job_id}").json()["reviewModel"]

    assert model["ruleDomains"] == legacy_rules
    assert model["referenceBoards"]["ux"] == legacy_ux
    assert review_gate(model)["exportReady"] is True
    preview = client.post(
        f"/api/jobs/{job_id}/review-model/preview",
        json={"expectedRevision": model["revision"]},
    ).json()
    assert [item["key"] for item in preview["referenceBoardSummary"]] == ["planning"]
    assert legacy_three_board_job["reviewModel"]["ruleDomains"] == legacy_rules
    assert legacy_three_board_job["reviewModel"]["referenceBoards"]["ux"] == legacy_ux


def test_legacy_confirmed_interaction_job_can_queue_gameplay_without_mutating_review_model(
    client, legacy_three_board_job, monkeypatch
):
    before = deepcopy(legacy_three_board_job["reviewModel"])
    submitted = []
    monkeypatch.setattr(server.executor, "submit", lambda *args: submitted.append(args))

    response = client.post(f"/api/jobs/{legacy_three_board_job['id']}/gameplay-review/generate")

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert submitted
    assert legacy_three_board_job["reviewModel"] == before
