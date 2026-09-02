from __future__ import annotations

from fastapi.testclient import TestClient

import canonical_api_server
from backend import server as server_module


def test_import_does_not_mutate_legacy_gameplay_route() -> None:
    routes = [
        route for route in server_module.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/gameplay-review/generate"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is not canonical_api_server.generate_canonical_gameplay_understanding


def test_gameplay_generate_url_is_owned_only_by_canonical_entrypoint_while_running() -> None:
    with TestClient(canonical_api_server.app):
        routes = [
            route for route in canonical_api_server.app.router.routes
            if getattr(route, "path", None) == "/api/jobs/{job_id}/gameplay-review/generate"
            and "POST" in (getattr(route, "methods", None) or set())
        ]
        assert len(routes) == 1
        assert routes[0].endpoint is canonical_api_server.generate_canonical_gameplay_understanding

    restored = [
        route for route in server_module.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/gameplay-review/generate"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(restored) == 1
    assert restored[0].endpoint is not canonical_api_server.generate_canonical_gameplay_understanding


def test_production_worker_semantic_owner_is_understanding_v1_2_without_monkey_patch() -> None:
    assert canonical_api_server._generate_canonical_understanding_job is not server_module._generate_gameplay_review
    assert server_module.generate_gameplay_structure.__module__ == "backend.gameplay_analysis"


def test_canonical_generate_route_has_no_interaction_review_precondition() -> None:
    source = canonical_api_server.generate_canonical_gameplay_understanding.__doc__ or ""
    assert "No Interaction Model precondition" in source
