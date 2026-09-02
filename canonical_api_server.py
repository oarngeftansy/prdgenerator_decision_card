"""Canonical production API entrypoint.

This module owns the production route order:
Evidence/Video -> Gameplay Understanding v1.2 -> Interaction -> P1/P2/P3
-> Execution Planning -> ExecutionRuleModel -> P4 -> P5/P6
-> PublicationInputSnapshot -> pure P7 -> Web/Feishu.

Legacy backend routes remain available to compatibility/unit-test imports, but the
production process replaces the routes that would otherwise invert this order or
re-run AI during Final preview.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from fastapi import Body, Form, HTTPException

import api_server
from backend import server as server_module
from backend.ai_provider import DEFAULT_API_BASE, DEFAULT_MODEL, ProviderError
from backend.canonical_pipeline import CanonicalPipelineError, assemble_validate_render
from backend.canonical_prepublication import PREPUBLICATION_STAGE_ORDER, prepare_publication_input
from backend.feishu_render import render_feishu_document
from backend.gameplay_understanding_runtime import generate_gameplay_understanding
from backend.p7_master_gate import combine_master_p7_gate, merge_completion_snapshot
from backend.review_preview import _delivery_preview_html


app = api_server.app

_GAMEPLAY_GENERATE_PATH = "/api/jobs/{job_id}/gameplay-review/generate"
_CONFIRM_DIRECTORY_PATH = "/api/jobs/{job_id}/gameplay-review-model/confirm-directory"
_LEGACY_FINAL_PATH = "/api/jobs/{job_id}/gameplay-review-model/final-preview"
_CANONICAL_FINAL_PATH = "/api/jobs/{job_id}/master-plan/final-preview"
_PREPARE_PUBLICATION_PATH = "/api/jobs/{job_id}/master-plan/prepare-publication"

_CANONICAL_ROUTE_NAMES = {
    "generate_canonical_gameplay_understanding",
    "confirm_canonical_gameplay_directory",
    "prepare_canonical_publication",
    "finalize_canonical_publication",
    "finalize_canonical_publication_legacy_alias",
}
_REPLACED_POST_PATHS = {
    _GAMEPLAY_GENERATE_PATH,
    _CONFIRM_DIRECTORY_PATH,
    _LEGACY_FINAL_PATH,
    _CANONICAL_FINAL_PATH,
    _PREPARE_PUBLICATION_PATH,
}
_original_routes = [
    route for route in app.router.routes
    if getattr(route, "path", None) in _REPLACED_POST_PATHS
    and "POST" in (getattr(route, "methods", None) or set())
]
_canonical_routes_installed = False


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
            job.pop("canonicalPipeline", None)
            job.pop("masterPlanning", None)
            job.pop("acceptedPublication", None)
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
    """Evidence/Video -> Gameplay Understanding v1.2 with no Interaction precondition."""
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
            "deadlineAt": (started_at + timedelta(seconds=server_module.GAMEPLAY_GENERATION_TIMEOUT_SECONDS)).isoformat(),
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
        server_module.executor.submit(_generate_canonical_understanding_job, job_id, runtime_config, generation_id)
        server_module._schedule_gameplay_generation_timeout(job_id, generation_id)
    except Exception:
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
        raise
    return generation


def confirm_canonical_gameplay_directory(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Confirm P1 directory without launching legacy gameplay-detail generation."""
    def mutation(model: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
        result = server_module.confirm_gameplay_directory(model, value.get("expectedRevision"))
        review_state = result.setdefault("reviewState", {})
        if review_state.get("status") == "detail_generation_pending":
            review_state["status"] = "canonical_planning_ready"
            review_state["legacyDetailGenerationDisabled"] = True
        review_state["previewRevision"] = None
        return result

    model = server_module._mutate_gameplay_model(job_id, payload, mutation)

    def invalidate(current: dict[str, Any]) -> None:
        current.pop("canonicalPipeline", None)
        current.pop("masterPlanning", None)
        current.pop("acceptedPublication", None)

    server_module.storage.mutate_job(job_id, invalidate)
    return model


def prepare_canonical_publication(job_id: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Run canonical planning through PublicationInputSnapshot, but never P7."""
    try:
        job = server_module.load_job(job_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "job not found") from exc
    gameplay = job.get("gameplayReviewModel")
    interaction = job.get("reviewModel")
    if not isinstance(gameplay, dict):
        raise HTTPException(409, "gameplay review model required")
    expected = payload.get("expectedRevision")
    if type(expected) is not int or expected != gameplay.get("revision"):
        raise HTTPException(409, {"currentRevision": gameplay.get("revision", 0)})

    try:
        prepared = prepare_publication_input(
            copy.deepcopy(gameplay),
            copy.deepcopy(interaction) if isinstance(interaction, dict) else {},
            api_server._provider_config(payload),
        )
    except ProviderError as exc:
        raise HTTPException(502 if exc.retryable else 400, exc.public()) from exc
    except (CanonicalPipelineError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc

    snapshot = prepared["publicationInputSnapshot"]
    p4 = prepared["p4Review"]
    interaction_revision = interaction.get("revision") if isinstance(interaction, dict) else None

    def persist(current: dict[str, Any]) -> None:
        current_gameplay = current.get("gameplayReviewModel") or {}
        current_interaction = current.get("reviewModel") if isinstance(current.get("reviewModel"), dict) else {}
        if current_gameplay.get("revision") != expected:
            raise HTTPException(409, {"currentRevision": current_gameplay.get("revision", 0)})
        if current_interaction.get("revision") != interaction_revision:
            raise HTTPException(409, {"currentInteractionRevision": current_interaction.get("revision", 0)})
        current_gameplay.setdefault("reviewState", {})["previewRevision"] = None
        current["canonicalPipeline"] = copy.deepcopy(prepared)
        current["masterPlanning"] = {
            "pipelineVersion": prepared.get("pipelineVersion"),
            "stageTrace": copy.deepcopy(prepared.get("stageTrace") or []),
            "gameplayRevision": expected,
            "interactionRevision": interaction_revision,
            "gameplayUnderstandingModel": copy.deepcopy(prepared["gameplayUnderstandingModel"]),
            "interactionModel": copy.deepcopy(prepared["interactionModel"]),
            "executionRuleModel": copy.deepcopy(prepared["executionRuleModel"]),
            "p4Review": copy.deepcopy(p4),
            "p5DiagramProjection": copy.deepcopy(prepared["p5DiagramProjection"]),
            "p6ParameterProjection": copy.deepcopy(prepared["p6ParameterProjection"]),
            "publicationInputSnapshot": copy.deepcopy(snapshot),
            "qualityJudge": copy.deepcopy(p4.get("qualityJudge") or {}),
            "planningSketch": copy.deepcopy(p4.get("planningSketch") or {}),
            "interactionReview": copy.deepcopy(p4.get("interactionReview") or {}),
        }
        current.pop("acceptedPublication", None)

    server_module.storage.mutate_job(job_id, persist)
    return {
        "prepared": True,
        "stageTrace": copy.deepcopy(prepared["stageTrace"]),
        "publicationInputDigest": snapshot.get("digest"),
        "p4Ready": bool(p4.get("ready")),
        "qualityJudge": copy.deepcopy(p4.get("qualityJudge") or {}),
        "interactionReview": copy.deepcopy(p4.get("interactionReview") or {}),
        "planningSketch": copy.deepcopy(p4.get("planningSketch") or {}),
    }


def finalize_canonical_publication(job_id: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Pure P7: read frozen PublicationInputSnapshot and render Web/Feishu output."""
    try:
        job = server_module.load_job(job_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "job not found") from exc
    gameplay = job.get("gameplayReviewModel") if isinstance(job.get("gameplayReviewModel"), dict) else {}
    master = job.get("masterPlanning") if isinstance(job.get("masterPlanning"), dict) else {}
    expected = payload.get("expectedRevision")
    if type(expected) is not int or expected != gameplay.get("revision"):
        raise HTTPException(409, {"currentRevision": gameplay.get("revision", 0)})
    if master.get("gameplayRevision") != expected:
        raise HTTPException(409, "PublicationInputSnapshot is stale; prepare publication again")
    interaction = job.get("reviewModel") if isinstance(job.get("reviewModel"), dict) else {}
    if master.get("interactionRevision") != interaction.get("revision"):
        raise HTTPException(409, "Interaction Model changed; prepare publication again")
    snapshot = master.get("publicationInputSnapshot") if isinstance(master.get("publicationInputSnapshot"), dict) else {}
    if not snapshot.get("digest"):
        raise HTTPException(409, "PublicationInputSnapshot required before Final preview")

    try:
        p7 = assemble_validate_render(copy.deepcopy(snapshot))
    except CanonicalPipelineError as exc:
        raise HTTPException(422, str(exc)) from exc

    p4 = snapshot.get("p4Review") if isinstance(snapshot.get("p4Review"), dict) else {}
    quality = copy.deepcopy(p4.get("qualityJudge") or {})
    interaction_review = copy.deepcopy(p4.get("interactionReview") or {})
    master_ready = (
        bool(p4.get("ready"))
        and bool(quality.get("ready"))
        and bool(interaction_review.get("ready"))
        and p7.get("publicationInputDigest") == snapshot.get("digest")
        and not (p7.get("document") or {}).get("unresolvedDiagnostics")
    )
    gate = combine_master_p7_gate({"blockerIds": []}, master_ready=master_ready, master_quality=quality)
    completion = merge_completion_snapshot(None, gate, master_quality=quality)

    def persist(current: dict[str, Any]) -> None:
        current_gameplay = current.get("gameplayReviewModel") or {}
        current_interaction = current.get("reviewModel") if isinstance(current.get("reviewModel"), dict) else {}
        current_master = current.get("masterPlanning") if isinstance(current.get("masterPlanning"), dict) else {}
        current_snapshot = current_master.get("publicationInputSnapshot") if isinstance(current_master.get("publicationInputSnapshot"), dict) else {}
        if current_gameplay.get("revision") != expected or current_snapshot.get("digest") != snapshot.get("digest"):
            raise HTTPException(409, "PublicationInputSnapshot changed during P7")
        if current_interaction.get("revision") != master.get("interactionRevision"):
            raise HTTPException(409, "Interaction Model changed during P7")
        if gate["ready"]:
            current_gameplay.setdefault("reviewState", {})["previewRevision"] = expected
            current_gameplay["reviewState"]["status"] = "preview_ready"
        current_master["p7Delivery"] = copy.deepcopy(p7)
        current_master["document"] = copy.deepcopy(p7["document"])
        current_master["markdown"] = p7["markdown"]
        current_master["feishuXml"] = p7["feishuXml"]
        current_master["p7Gate"] = copy.deepcopy(gate)
        current_master["completionSnapshot"] = copy.deepcopy(completion)
        current_master["stageTrace"] = [*list(current_master.get("stageTrace") or []), "p7_assemble_validate_render"]
        current["masterPlanning"] = current_master
        pipeline = current.get("canonicalPipeline") if isinstance(current.get("canonicalPipeline"), dict) else {}
        pipeline["stageTrace"] = copy.deepcopy(current_master["stageTrace"])
        pipeline["p7Delivery"] = copy.deepcopy(p7)
        current["canonicalPipeline"] = pipeline

        accepted_markdown = p7["acceptedMarkdown"].rstrip()
        sketch_markdown = str(p7.get("planningSketchMarkdown") or "").strip()
        if sketch_markdown:
            accepted_markdown += "\n\n" + sketch_markdown + "\n"
        current["acceptedPublication"] = {
            "source": "canonical_pipeline_v1",
            "gameplayRevision": expected,
            "interactionRevision": current_interaction.get("revision"),
            "publicationInputDigest": snapshot.get("digest"),
            "p7DeliveryDigest": p7.get("digest"),
            "markdown": accepted_markdown,
            "planningSketch": copy.deepcopy(p7.get("planningSketch") or {}),
            "interactionReview": copy.deepcopy(interaction_review),
            "p5Diagrams": copy.deepcopy((snapshot.get("p5DiagramProjection") or {}).get("diagrams") or []),
            "p6Tables": copy.deepcopy((snapshot.get("p6ParameterProjection") or {}).get("tables") or []),
        }

    server_module.storage.mutate_job(job_id, persist)

    try:
        persisted_job = server_module.load_job(job_id)
        exact_render = render_feishu_document(persisted_job, server_module.job_path(job_id))
        exact_preview_html = _delivery_preview_html(exact_render)
    except Exception as exc:
        raise HTTPException(422, f"accepted Final render failed: {exc}") from exc

    return {
        "exportReady": bool(gate["ready"]),
        "blockerIds": list(gate["blockerIds"]),
        "legacyBlockerIds": [],
        "plannerSupersededBlockerIds": [],
        "completionSnapshot": completion,
        "masterPlanningReady": bool(master_ready),
        "canonicalPipelineVersion": master.get("pipelineVersion"),
        "canonicalStageTrace": [*list(master.get("stageTrace") or []), "p7_assemble_validate_render"],
        "publicationInputDigest": snapshot.get("digest"),
        "masterPlanningDocument": p7["document"],
        "masterPlanningMarkdown": p7["markdown"],
        "masterPlanningFeishuXml": p7["feishuXml"],
        "masterPlanningQuality": quality,
        "masterPlanningSketch": p7.get("planningSketch") or {},
        "masterInteractionReview": interaction_review,
        "deliveryPreviewHtml": exact_preview_html,
    }


def _install_canonical_routes() -> None:
    global _canonical_routes_installed
    if _canonical_routes_installed:
        return
    app.router.routes[:] = [
        route for route in app.router.routes
        if not (
            getattr(route, "path", None) in _REPLACED_POST_PATHS
            and "POST" in (getattr(route, "methods", None) or set())
        )
    ]
    app.add_api_route(_GAMEPLAY_GENERATE_PATH, generate_canonical_gameplay_understanding, methods=["POST"], status_code=202, name="generate_canonical_gameplay_understanding")
    app.add_api_route(_CONFIRM_DIRECTORY_PATH, confirm_canonical_gameplay_directory, methods=["POST"], name="confirm_canonical_gameplay_directory")
    app.add_api_route(_PREPARE_PUBLICATION_PATH, prepare_canonical_publication, methods=["POST"], name="prepare_canonical_publication")
    app.add_api_route(_CANONICAL_FINAL_PATH, finalize_canonical_publication, methods=["POST"], name="finalize_canonical_publication")
    app.add_api_route(_LEGACY_FINAL_PATH, finalize_canonical_publication, methods=["POST"], name="finalize_canonical_publication_legacy_alias")
    app.openapi_schema = None
    _canonical_routes_installed = True


def _restore_legacy_routes() -> None:
    global _canonical_routes_installed
    if not _canonical_routes_installed:
        return
    app.router.routes[:] = [
        route for route in app.router.routes
        if getattr(route, "name", None) not in _CANONICAL_ROUTE_NAMES
    ]
    for route in _original_routes:
        if route not in app.router.routes:
            app.router.routes.append(route)
    app.openapi_schema = None
    _canonical_routes_installed = False


@app.on_event("startup")
def _canonical_startup() -> None:
    _install_canonical_routes()


@app.on_event("shutdown")
def _canonical_shutdown() -> None:
    _restore_legacy_routes()
