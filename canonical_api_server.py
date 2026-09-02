"""Canonical production API entrypoint.

`backend.server` remains the stable infrastructure host. `api_server` owns the
canonical Final/Feishu routes. This module makes Gameplay Understanding Skill
v1.2 the production owner of the first semantic generation stage without
monkey-patching the legacy worker at import time.

Route replacement happens only while this production app is running. Importing
this module in unit tests therefore does not silently change `backend.server.app`.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from fastapi import Form, HTTPException

import api_server
from backend import server as server_module
from backend.ai_provider import DEFAULT_API_BASE, DEFAULT_MODEL
from backend.gameplay_understanding_runtime import generate_gameplay_understanding


app = api_server.app
_LEGACY_GAMEPLAY_GENERATE_PATH = "/api/jobs/{job_id}/gameplay-review/generate"
_CANONICAL_ROUTE_NAME = "generate_canonical_gameplay_understanding"
_original_gameplay_routes = [
    route for route in app.router.routes
    if getattr(route, "path", None) == _LEGACY_GAMEPLAY_GENERATE_PATH
    and "POST" in (getattr(route, "methods", None) or set())
]
_canonical_route_installed = False


def _generation_active(current: dict[str, Any], generation_id: str) -> bool:
    generation = current.get("gameplayReviewGeneration") or {}
    return generation.get("generationId") in {None, generation_id} and generation.get("status") in {"queued", "running"}


def _canonical_progress(job_id: str, generation_id: str, value: int, message: str) -> None:
    reported = max(0, min(100, int(value)))

    def update(current: dict[str, Any]) -> None:
        if not _generation_active(current, generation_id):
            return
        previous = current.get("gameplayReviewGeneration") or {}
        current["gameplayReviewGeneration"] = {
            **previous,
            "status": "running",
            "progress": max(int(previous.get("progress") or 0), reported),
            "message": message[:240] or "Generating gameplay understanding.",
            "phase": server_module._gameplay_generation_phase(reported),
            "generationId": generation_id,
            "lastProgressAt": datetime.now(timezone.utc).isoformat(),
            "semanticOwner": "gameplay-understanding-v1.2",
        }

    server_module.storage.mutate_job(job_id, update)


def _generate_canonical_understanding_job(
    job_id: str,
    runtime_config: dict[str, Any],
    generation_id: str,
) -> None:
    """Stable background worker whose semantic owner is Understanding v1.2."""
    try:
        def mark_running(current: dict[str, Any]) -> None:
            if not _generation_active(current, generation_id):
                return
            previous = current.get("gameplayReviewGeneration") or {}
            current["gameplayReviewGeneration"] = {
                **previous,
                "status": "running",
                "progress": int(previous.get("progress") or 0),
                "message": "Generating gameplay understanding.",
                "phase": "understanding",
                "generationId": generation_id,
                "semanticOwner": "gameplay-understanding-v1.2",
                "startedAt": previous.get("startedAt") or datetime.now(timezone.utc).isoformat(),
            }

        server_module.storage.mutate_job(job_id, mark_running)
        current = server_module.load_job(job_id)
        understanding, compatibility_model = generate_gameplay_understanding(
            current,
            server_module.job_path(job_id),
            runtime_config,
            lambda value, message: _canonical_progress(job_id, generation_id, value, message),
        )
        compatibility_model["gameplayUnderstandingModel"] = copy.deepcopy(understanding)
        compatibility_model["understandingDigest"] = understanding.get("digest")
        compatibility_model["lifecycleState"] = "ready"
        compatibility_model["contentState"] = "ready"

        def complete(job: dict[str, Any]) -> None:
            if not _generation_active(job, generation_id):
                return
            previous = job.get("gameplayReviewGeneration") or {}
            job["gameplayUnderstandingModel"] = copy.deepcopy(understanding)
            job["gameplayReviewModel"] = copy.deepcopy(compatibility_model)
            job["gameplayReviewGeneration"] = {
                **previous,
                "status": "completed",
                "progress": 100,
                "message": "Gameplay Understanding v1.2 ready for interaction review.",
                "phase": "finalizing",
                "generationId": generation_id,
                "semanticOwner": "gameplay-understanding-v1.2",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
            }

        server_module.storage.mutate_job(job_id, complete)
    except Exception as exc:
        server_module.logger.exception("canonical gameplay understanding failed for job %s", job_id)

        def fail(current: dict[str, Any]) -> None:
            generation = current.get("gameplayReviewGeneration") or {}
            if generation.get("generationId") not in {None, generation_id}:
                return
            current["gameplayReviewGeneration"] = {
                **generation,
                "status": "failed",
                "progress": int(generation.get("progress") or 0),
                "message": "Gameplay Understanding generation failed. Please retry.",
                "error": server_module._safe_gameplay_generation_error(exc),
                "failureKind": server_module._gameplay_generation_failure_kind(exc),
                "semanticOwner": "gameplay-understanding-v1.2",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
            }

        try:
            server_module.storage.mutate_job(job_id, fail)
        except Exception:
            server_module.logger.exception("failed to persist canonical understanding error for %s", job_id)


def generate_canonical_gameplay_understanding(
    job_id: str,
    api_base: str = Form(DEFAULT_API_BASE),
    model: str = Form(DEFAULT_MODEL),
    api_key: str = Form(""),
    force: bool = Form(False),
) -> dict[str, Any]:
    """Evidence/Video -> Gameplay Understanding v1.2.

    No Interaction Model precondition is allowed here. Interaction is a later
    canonical stage. Existing review UI state is compatibility data only.
    """
    generation_id = uuid.uuid4().hex
    runtime_config = server_module._runtime_ai_config(api_base, model, api_key)
    if not runtime_config["apiKey"]:
        raise HTTPException(400, "视觉模型未配置：请填写 API Key 后重试")

    def queue(current: dict[str, Any]) -> dict[str, Any]:
        generation = current.get("gameplayReviewGeneration") or {}
        if generation.get("status") in {"queued", "running"}:
            raise HTTPException(409, "gameplay understanding generation is already running")

        existing = current.get("gameplayUnderstandingModel")
        if not force and isinstance(existing, dict) and existing.get("digest"):
            current["gameplayReviewGeneration"] = {
                "status": "completed",
                "progress": 100,
                "message": "Gameplay Understanding v1.2 already exists.",
                "phase": "finalizing",
                "generationId": generation_id,
                "semanticOwner": "gameplay-understanding-v1.2",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
            }
            return server_module._public_gameplay_review_generation(current["gameplayReviewGeneration"])

        previous_model = current.get("gameplayReviewModel")
        if isinstance(previous_model, dict):
            previous_model["contentState"] = "pending"
            if server_module.gameplay_model_has_content(previous_model):
                previous_model["lastValidRevision"] = previous_model.get("revision")

        started_at = datetime.now(timezone.utc)
        current["gameplayReviewGeneration"] = {
            "status": "queued",
            "progress": 0,
            "message": "Queued Gameplay Understanding v1.2.",
            "phase": "queued",
            "generationId": generation_id,
            "startedAt": started_at.isoformat(),
            "lastProgressAt": started_at.isoformat(),
            "deadlineAt": (
                started_at + timedelta(seconds=server_module.GAMEPLAY_GENERATION_TIMEOUT_SECONDS)
            ).isoformat(),
            "semanticOwner": "gameplay-understanding-v1.2",
        }
        return server_module._public_gameplay_review_generation(current["gameplayReviewGeneration"])

    try:
        generation = server_module._mutate_review_job(job_id, queue)
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "job not found") from exc

    if generation.get("status") == "completed":
        return generation

    try:
        server_module.executor.submit(
            _generate_canonical_understanding_job,
            job_id,
            runtime_config,
            generation_id,
        )
        server_module._schedule_gameplay_generation_timeout(job_id, generation_id)
    except Exception:
        try:
            server_module.storage.mutate_job(
                job_id,
                lambda current: current.__setitem__(
                    "gameplayReviewGeneration",
                    {
                        "status": "failed",
                        "progress": 0,
                        "message": "Gameplay Understanding generation failed. Please retry.",
                    },
                ),
            )
        except Exception:
            server_module.logger.exception("failed to persist canonical understanding submission error for %s", job_id)
        raise
    return generation


def _install_canonical_routes() -> None:
    global _canonical_route_installed
    if _canonical_route_installed:
        return
    app.router.routes[:] = [
        route for route in app.router.routes
        if not (
            getattr(route, "path", None) == _LEGACY_GAMEPLAY_GENERATE_PATH
            and "POST" in (getattr(route, "methods", None) or set())
        )
    ]
    app.add_api_route(
        _LEGACY_GAMEPLAY_GENERATE_PATH,
        generate_canonical_gameplay_understanding,
        methods=["POST"],
        status_code=202,
        name=_CANONICAL_ROUTE_NAME,
    )
    app.openapi_schema = None
    _canonical_route_installed = True


def _restore_legacy_routes() -> None:
    global _canonical_route_installed
    if not _canonical_route_installed:
        return
    app.router.routes[:] = [
        route for route in app.router.routes
        if getattr(route, "name", None) != _CANONICAL_ROUTE_NAME
    ]
    for route in _original_gameplay_routes:
        if route not in app.router.routes:
            app.router.routes.append(route)
    app.openapi_schema = None
    _canonical_route_installed = False


@app.on_event("startup")
def _canonical_startup() -> None:
    _install_canonical_routes()


@app.on_event("shutdown")
def _canonical_shutdown() -> None:
    _restore_legacy_routes()
