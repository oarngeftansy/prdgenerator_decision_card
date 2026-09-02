"""Canonical production API entrypoint.

`backend.server` remains the stable infrastructure host. `api_server` owns the
canonical Final/Feishu routes. This module additionally makes Gameplay
Understanding Skill v1.2 the production owner of the first semantic generation
stage.

The legacy queue/timeout/storage machinery is reused, but its old interaction-
first gate and legacy structure prompt are not production authorities.
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


def _canonical_generate_gameplay_structure(job: dict, job_dir, runtime_config: dict, progress=lambda *_: None) -> dict:
    understanding, compatibility_model = generate_gameplay_understanding(
        job,
        job_dir,
        runtime_config,
        progress,
    )

    # Persist the first-class understanding independently from the compatibility
    # review model. The legacy worker subsequently persists the compatibility
    # shell; downstream canonical stages prefer this first-class object.
    job_id = str(job.get("id") or "")
    if job_id:
        expected_generation = str((job.get("gameplayReviewGeneration") or {}).get("generationId") or "")

        def persist(current: dict[str, Any]) -> None:
            current_generation = str((current.get("gameplayReviewGeneration") or {}).get("generationId") or "")
            if expected_generation and current_generation and current_generation != expected_generation:
                return
            current["gameplayUnderstandingModel"] = copy.deepcopy(understanding)

        server_module.storage.mutate_job(job_id, persist)

    compatibility_model["gameplayUnderstandingModel"] = copy.deepcopy(understanding)
    compatibility_model["understandingDigest"] = understanding.get("digest")
    return compatibility_model


# Reuse the stable worker, but redirect only its semantic structure function.
# This mutation exists only in the explicit production entrypoint; importing
# backend modules alone does not change legacy test/tool behavior.
server_module.generate_gameplay_structure = _canonical_generate_gameplay_structure

app = api_server.app

# The old endpoint required a completed interaction review before gameplay
# understanding could even run. That is the reverse of the canonical sequence.
_LEGACY_GAMEPLAY_GENERATE_PATH = "/api/jobs/{job_id}/gameplay-review/generate"
app.router.routes[:] = [
    route for route in app.router.routes
    if not (
        getattr(route, "path", None) == _LEGACY_GAMEPLAY_GENERATE_PATH
        and "POST" in (getattr(route, "methods", None) or set())
    )
]


@app.post(_LEGACY_GAMEPLAY_GENERATE_PATH, status_code=202)
def generate_canonical_gameplay_understanding(
    job_id: str,
    api_base: str = Form(DEFAULT_API_BASE),
    model: str = Form(DEFAULT_MODEL),
    api_key: str = Form(""),
    force: bool = Form(False),
) -> dict[str, Any]:
    """Evidence/Video -> Gameplay Understanding v1.2.

    No Interaction Model precondition is allowed here. Interaction is a later
    canonical stage. Existing review UI state is preserved as compatibility data.
    """
    generation_id = uuid.uuid4().hex
    runtime_config = server_module._runtime_ai_config(api_base, model, api_key)
    if not runtime_config["apiKey"]:
        raise HTTPException(400, "视觉模型未配置：请填写 API Key 后重试")

    def queue(current: dict[str, Any]) -> dict[str, Any]:
        generation = current.get("gameplayReviewGeneration") or {}
        if generation.get("status") in {"queued", "running"}:
            raise HTTPException(409, "gameplay understanding generation is already running")

        existing_understanding = current.get("gameplayUnderstandingModel")
        if not force and isinstance(existing_understanding, dict) and existing_understanding.get("digest"):
            current["gameplayReviewGeneration"] = {
                "status": "completed",
                "progress": 100,
                "message": "Gameplay Understanding v1.2 already exists.",
                "phase": "finalizing",
                "generationId": generation_id,
                "finishedAt": datetime.now(timezone.utc).isoformat(),
            }
            return server_module._public_gameplay_review_generation(current["gameplayReviewGeneration"])

        existing = current.get("gameplayReviewModel")
        if isinstance(existing, dict):
            existing["contentState"] = "pending"
            if server_module.gameplay_model_has_content(existing):
                existing["lastValidRevision"] = existing.get("revision")

        started_at = datetime.now(timezone.utc)
        current["gameplayReviewGeneration"] = {
            "status": "queued",
            "progress": 0,
            "message": "Queued gameplay review generation.",
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
            server_module._generate_gameplay_review,
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
                        "message": "Gameplay review generation failed. Please retry.",
                        "failureKind": "system",
                    },
                ),
            )
        except Exception:
            server_module.logger.exception("failed to persist canonical understanding submission error for %s", job_id)
        raise
    return generation
