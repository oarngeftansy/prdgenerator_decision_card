from __future__ import annotations

import api_server


def _master_ready_job(*, gameplay_revision: int = 8, preview_revision: int = 8) -> dict:
    return {
        "masterPlanning": {
            "gameplayRevision": gameplay_revision,
            "interactionRevision": None,
            "p7Gate": {"ready": True},
            "qualityJudge": {"ready": True},
        },
        "acceptedPublication": {"source": "master_planner_v1"},
        "gameplayReviewModel": {
            "revision": 8,
            "reviewState": {"previewRevision": preview_revision},
        },
        "reviewModel": {},
    }


def test_legacy_feishu_url_is_owned_only_by_master_planner() -> None:
    routes = [
        route for route in api_server.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/feishu/publish"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is api_server.publish_master_plan_to_feishu


def test_master_publication_guard_accepts_master_authority_without_legacy_gameplay_depth_gate() -> None:
    job = _master_ready_job()
    assert api_server._master_publication_guard(job) == {
        "gameplayRevision": 8,
        "interactionRevision": None,
    }


def test_master_publication_guard_rejects_stale_gameplay_revision() -> None:
    job = _master_ready_job(gameplay_revision=7)
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "gameplay revision changed" in str(exc)
    else:
        raise AssertionError("stale gameplay revision must block publication")


def test_master_publication_guard_rejects_stale_final_preview() -> None:
    job = _master_ready_job(preview_revision=7)
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "Master Planner Final preview is stale" in str(exc)
    else:
        raise AssertionError("stale Master Planner Final preview must block publication")
