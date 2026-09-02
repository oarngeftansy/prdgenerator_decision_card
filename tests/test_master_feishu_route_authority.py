from __future__ import annotations

import api_server


def _master_ready_job(*, gameplay_revision: int = 8, preview_revision: int = 8) -> dict:
    snapshot_digest = "snapshot-abc"
    return {
        "masterPlanning": {
            "gameplayRevision": gameplay_revision,
            "interactionRevision": None,
            "p7Gate": {"ready": True},
            "qualityJudge": {"ready": True},
            "planningSketch": {"version": "planning_sketch_v2", "authority": "canonical_rule_projection"},
            "interactionReview": {"version": "interaction_review_v2", "ready": True},
            "publicationInputSnapshot": {"version": "publication_input_snapshot_v1", "digest": snapshot_digest},
            "p7Delivery": {"version": "p7_delivery_v1", "publicationInputDigest": snapshot_digest},
        },
        "acceptedPublication": {
            "source": "canonical_pipeline_v1",
            "publicationInputDigest": snapshot_digest,
        },
        "gameplayReviewModel": {
            "revision": 8,
            "reviewState": {"previewRevision": preview_revision},
        },
        "reviewModel": {},
    }


def test_legacy_feishu_url_is_owned_only_by_canonical_pipeline() -> None:
    routes = [
        route for route in api_server.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/feishu/publish"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is api_server.publish_master_plan_to_feishu


def test_publication_guard_accepts_snapshot_pinned_canonical_authority() -> None:
    job = _master_ready_job()
    assert api_server._master_publication_guard(job) == {
        "gameplayRevision": 8,
        "interactionRevision": None,
        "publicationInputDigest": "snapshot-abc",
    }


def test_legacy_interaction_export_gate_no_longer_controls_canonical_final() -> None:
    job = _master_ready_job()
    job["reviewModel"] = {
        "revision": 3,
        "reviewState": {"previewRevision": None},
        "stages": [],
        "transitions": [],
    }
    job["masterPlanning"]["interactionRevision"] = 3
    assert api_server._master_publication_guard(job)["interactionRevision"] == 3


def test_publication_guard_rejects_failed_canonical_interaction_review() -> None:
    job = _master_ready_job()
    job["masterPlanning"]["interactionReview"] = {
        "version": "interaction_review_v2",
        "ready": False,
        "criticalIssues": ["planning_sketch_rule_coverage_incomplete"],
    }
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "canonical interaction review is not ready" in str(exc)
    else:
        raise AssertionError("failed canonical interaction review must block publication")


def test_publication_guard_rejects_missing_canonical_planning_sketch() -> None:
    job = _master_ready_job()
    job["masterPlanning"]["planningSketch"] = {}
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "canonical planning sketch is missing or stale" in str(exc)
    else:
        raise AssertionError("missing canonical planning sketch must block publication")


def test_publication_guard_rejects_stale_gameplay_revision() -> None:
    job = _master_ready_job(gameplay_revision=7)
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "gameplay revision changed" in str(exc)
    else:
        raise AssertionError("stale gameplay revision must block publication")


def test_publication_guard_rejects_stale_final_preview() -> None:
    job = _master_ready_job(preview_revision=7)
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "Canonical Final preview is stale" in str(exc)
    else:
        raise AssertionError("stale Canonical Final preview must block publication")


def test_publication_guard_rejects_snapshot_drift() -> None:
    job = _master_ready_job()
    job["masterPlanning"]["p7Delivery"]["publicationInputDigest"] = "different"
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "PublicationInputSnapshot is missing or stale" in str(exc)
    else:
        raise AssertionError("P7 must be pinned to the exact PublicationInputSnapshot")
