from __future__ import annotations

import canonical_api_server
from backend import server as server_module


def test_gameplay_generate_url_is_owned_only_by_canonical_entrypoint() -> None:
    routes = [
        route for route in canonical_api_server.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/gameplay-review/generate"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is canonical_api_server.generate_canonical_gameplay_understanding


def test_production_worker_semantic_owner_is_understanding_v1_2() -> None:
    assert server_module.generate_gameplay_structure is canonical_api_server._canonical_generate_gameplay_structure


def test_canonical_generate_route_has_no_interaction_review_precondition() -> None:
    source = canonical_api_server.generate_canonical_gameplay_understanding.__doc__ or ""
    assert "No Interaction Model precondition" in source
