from __future__ import annotations

import api_server


def test_legacy_feishu_url_is_owned_only_by_master_planner() -> None:
    routes = [
        route for route in api_server.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/feishu/publish"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is api_server.publish_master_plan_to_feishu


def test_master_publication_guard_accepts_master_authority_without_legacy_gameplay_depth_gate() -> None:
    job = {
        "masterPlanning": {
            "gameplayRevision": 8,
            "interactionRevision": 3,
            "p7Gate": {"ready": True},
            "qualityJudge": {"ready": True},
        },
        "acceptedPublication": {"source": "master_planner_v1"},
        "gameplayReviewModel": {
            "revision": 8,
            "reviewState": {"previewRevision": 8},
            # Deliberately no legacy plannerSections/depth fields. The new
            # publication guard must not make those old fields authoritative.
        },
        "reviewModel": {},
    }
    assert api_server._master_publication_guard(job) == {
        "gameplayRevision": 8,
        "interactionRevision": None,
    }


def test_master_publication_guard_rejects_stale_gameplay_revision() -> None:
    job = {
        "masterPlanning": {
            "gameplayRevision": 7,
            "interactionRevision": None,
            "p7Gate": {"ready": True},
            "qualityJudge": {"ready": True},
        },
        "acceptedPublication": {"source": "master_planner_v1"},
        "gameplayReviewModel": {"revision": 8, "reviewState": {"previewRevision": 8}},
        "reviewModel": {},
    }
    try:
        api_server._master_publication_guard(job)
    except Exception as exc:
        assert "gameplay revision changed" in str(exc)
    else:
        raise AssertionError("stale gameplay revision must block publication")
