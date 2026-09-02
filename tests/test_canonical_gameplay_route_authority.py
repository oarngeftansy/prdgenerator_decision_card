from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

import canonical_api_server
from backend import server as server_module


def _post_routes(path: str):
    return [
        route for route in canonical_api_server.app.router.routes
        if getattr(route, "path", None) == path
        and "POST" in (getattr(route, "methods", None) or set())
    ]


def test_import_does_not_mutate_legacy_gameplay_route() -> None:
    routes = [
        route for route in server_module.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/gameplay-review/generate"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is not canonical_api_server.generate_canonical_gameplay_understanding


def test_production_routes_replace_legacy_generation_detail_and_final_authorities() -> None:
    with TestClient(canonical_api_server.app):
        assert _post_routes("/api/jobs/{job_id}/gameplay-review/generate")[0].endpoint is canonical_api_server.generate_canonical_gameplay_understanding
        assert _post_routes("/api/jobs/{job_id}/gameplay-review-model/confirm-directory")[0].endpoint is canonical_api_server.confirm_canonical_gameplay_directory
        assert _post_routes("/api/jobs/{job_id}/master-plan/prepare-publication")[0].endpoint is canonical_api_server.prepare_canonical_publication
        assert _post_routes("/api/jobs/{job_id}/master-plan/final-preview")[0].endpoint is canonical_api_server.finalize_canonical_publication
        assert _post_routes("/api/jobs/{job_id}/gameplay-review-model/final-preview")[0].endpoint is canonical_api_server.finalize_canonical_publication


def test_legacy_routes_restore_after_canonical_app_shutdown() -> None:
    with TestClient(canonical_api_server.app):
        pass
    restored_generation = [
        route for route in server_module.app.router.routes
        if getattr(route, "path", None) == "/api/jobs/{job_id}/gameplay-review/generate"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(restored_generation) == 1
    assert restored_generation[0].endpoint is not canonical_api_server.generate_canonical_gameplay_understanding


def test_production_worker_semantic_owner_is_understanding_v1_2_without_monkey_patch() -> None:
    assert canonical_api_server._generate_canonical_understanding_job is not server_module._generate_gameplay_review
    assert server_module.generate_gameplay_structure.__module__ == "backend.gameplay_analysis"


def test_directory_confirmation_cannot_launch_legacy_detail_generation() -> None:
    source = inspect.getsource(canonical_api_server.confirm_canonical_gameplay_directory)
    assert "_generate_confirmed_gameplay_details" not in source
    assert "legacyDetailGenerationDisabled" in source


def test_final_preview_is_pure_snapshot_p7_without_provider_or_execution_planning() -> None:
    source = inspect.getsource(canonical_api_server.finalize_canonical_publication)
    assert "assemble_validate_render" in source
    assert "prepare_publication_input" not in source
    assert "_provider_config" not in source
    assert "build_master_planning_delivery" not in source
    assert "Execution Planning" not in source
