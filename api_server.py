import copy
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
python_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
runtime_packages = ROOT / "runtime_packages"
calibration_packages = ROOT / "calibration_packages"


def _is_compatible_dependency_root(path: Path) -> bool:
    return any((path / "pydantic_core").glob(f"_pydantic_core.{python_tag}-*.pyd"))


dependency_root = next(
    (path for path in (runtime_packages, calibration_packages) if _is_compatible_dependency_root(path)),
    None,
)
if dependency_root is not None:
    sys.path.insert(0, str(dependency_root))
sys.path.insert(0, str(ROOT))

from fastapi import Body, HTTPException  # noqa: E402
from backend import server as server_module  # noqa: E402
from backend.ai_provider import DEFAULT_API_BASE, DEFAULT_MODEL, ProviderConfig, ProviderError, validate_connectivity  # noqa: E402
from backend.feishu_publish import FeishuPublisher, PublicationConflict, ReviewApprovalConflict  # noqa: E402
from backend.feishu_render import render_feishu_document  # noqa: E402
from backend.master_planner import MasterPlannerError  # noqa: E402
from backend.p7_master_gate import combine_master_p7_gate, merge_completion_snapshot  # noqa: E402
from backend.production_planning import ProductionPlanningError, build_master_planning_delivery  # noqa: E402
from backend.review_model import review_gate  # noqa: E402
from backend.review_preview import _delivery_preview_html  # noqa: E402

server_module.BUILT_IN_VISION_API_BASE = DEFAULT_API_BASE
server_module.BUILT_IN_VISION_MODEL = DEFAULT_MODEL
server_module.BUILT_IN_VISION_API_KEY = ""

app = server_module.app  # noqa: E402,F401
logger = logging.getLogger("mirror-eye.master-planner")


def _provider_config(payload: dict) -> ProviderConfig:
    runtime = server_module._runtime_ai_config(
        str(payload.get("apiBase") or ""),
        str(payload.get("model") or ""),
        str(payload.get("apiKey") or ""),
    )
    return ProviderConfig(api_base=runtime["apiBase"], model=runtime["model"], api_key=runtime["apiKey"])


def _master_publication_guard(job: dict, *, expected_gameplay: int | None = None, expected_interaction: int | None = None) -> dict:
    """Validate the current Master Planner publication authority.

    Legacy gameplay depth gates are intentionally excluded here. They are
    superseded by Master Planner + Execution Readiness Judge. Revision, media,
    board, diagram and table safety were already captured by the current P7 gate.
    """
    master = job.get("masterPlanning") if isinstance(job.get("masterPlanning"), dict) else {}
    gameplay = job.get("gameplayReviewModel") if isinstance(job.get("gameplayReviewModel"), dict) else {}
    interaction = job.get("reviewModel") if isinstance(job.get("reviewModel"), dict) else {}
    accepted = job.get("acceptedPublication") if isinstance(job.get("acceptedPublication"), dict) else {}
    gameplay_revision = gameplay.get("revision")
    interaction_revision = interaction.get("revision")
    if not master or accepted.get("source") != "master_planner_v1":
        raise ReviewApprovalConflict("Master Planner Final has not been generated")
    if master.get("gameplayRevision") != gameplay_revision:
        raise ReviewApprovalConflict("gameplay revision changed; regenerate Master Planner Final")
    if master.get("interactionRevision") != interaction_revision:
        raise ReviewApprovalConflict("interaction revision changed; regenerate Master Planner Final")
    if expected_gameplay is not None and gameplay_revision != expected_gameplay:
        raise PublicationConflict("gameplay publication approval pin changed")
    if expected_interaction is not None and interaction_revision != expected_interaction:
        raise PublicationConflict("interaction publication approval pin changed")
    if not (master.get("p7Gate") or {}).get("ready"):
        raise ReviewApprovalConflict("Master Planner P7 gate is not ready")
    if not (master.get("qualityJudge") or {}).get("ready"):
        raise ReviewApprovalConflict("Master Planner execution readiness is not ready")
    if gameplay.get("reviewState", {}).get("previewRevision") != gameplay_revision:
        raise ReviewApprovalConflict("Master Planner Final preview is stale")
    if interaction and (
        interaction.get("reviewState", {}).get("previewRevision") != interaction_revision
        or not review_gate(interaction)["exportReady"]
    ):
        raise ReviewApprovalConflict("interaction preview is stale")
    return {
        "gameplayRevision": gameplay_revision,
        "interactionRevision": interaction_revision,
    }


@app.post("/api/config/validate")
def validate_runtime_provider(payload: dict = Body(default={})):
    """Validate real provider authentication before a fan-out generation job starts."""
    return validate_connectivity(_provider_config(payload))


@app.post("/api/jobs/{job_id}/master-plan/final-preview")
def create_master_planning_final_preview(job_id: str, payload: dict = Body(default={})):
    """Production P7: legacy delivery safety + canonical Master Planner Final."""
    try:
        job = server_module.load_job(job_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "job not found") from exc
    gameplay = job.get("gameplayReviewModel")
    if not isinstance(gameplay, dict):
        raise HTTPException(409, "gameplay review model required")
    expected = payload.get("expectedRevision")
    if type(expected) is not int or expected != gameplay.get("revision"):
        raise HTTPException(409, {"currentRevision": gameplay.get("revision", 0)})

    # Keep legacy ownership of revision/media/diagram/table/board safety. The
    # resulting planner-depth blockers are classified after canonical planning.
    legacy_preview = server_module.create_gameplay_final_preview(job_id, payload)
    job = server_module.load_job(job_id)
    gameplay = copy.deepcopy(job.get("gameplayReviewModel") or {})
    interaction = copy.deepcopy(job.get("reviewModel") or {})
    if gameplay.get("revision") != expected:
        raise HTTPException(409, {"currentRevision": gameplay.get("revision", 0)})

    try:
        delivery = build_master_planning_delivery(gameplay, _provider_config(payload))
    except ProviderError as exc:
        raise HTTPException(502 if exc.retryable else 400, exc.public()) from exc
    except (MasterPlannerError, ProductionPlanningError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc

    quality = delivery.get("qualityJudge") or {}
    master_ready = bool(quality.get("ready")) and not (delivery.get("document") or {}).get("unresolvedDiagnostics")
    gate = combine_master_p7_gate(legacy_preview, master_ready=master_ready, master_quality=quality)
    completion = merge_completion_snapshot(
        legacy_preview.get("completionSnapshot"), gate, master_quality=quality,
    )

    def persist(current: dict) -> None:
        current_gameplay = current.get("gameplayReviewModel") or {}
        current_interaction = current.get("reviewModel") or {}
        if current_gameplay.get("revision") != expected:
            raise HTTPException(409, {"currentRevision": current_gameplay.get("revision", 0)})
        if current_interaction.get("revision") != interaction.get("revision"):
            raise HTTPException(409, {"currentInteractionRevision": current_interaction.get("revision", 0)})
        if gate["ready"]:
            current_gameplay.setdefault("reviewState", {})["previewRevision"] = expected
            current_gameplay["reviewState"]["status"] = "preview_ready"
        else:
            current_gameplay.setdefault("reviewState", {})["previewRevision"] = None
        current["masterPlanning"] = {
            "gameplayRevision": expected,
            "interactionRevision": current_interaction.get("revision"),
            "projection": copy.deepcopy(delivery["projection"]),
            "document": copy.deepcopy(delivery["document"]),
            "markdown": delivery["markdown"],
            "feishuXml": delivery["feishuXml"],
            "qualityJudge": copy.deepcopy(quality),
            "masterPlanner": copy.deepcopy(delivery.get("masterPlanner") or {}),
            "p7Gate": copy.deepcopy(gate),
            "completionSnapshot": copy.deepcopy(completion),
        }

        # Existing Feishu renderer remains responsible for boards/P5/P6. Only
        # the textual authority is replaced by canonical Master Planner output.
        existing_accepted = current.get("acceptedPublication") if isinstance(current.get("acceptedPublication"), dict) else {}
        accepted_markdown = delivery["acceptedMarkdown"].rstrip() + (
            "\n\n## 策划草图\n\n<!-- EMBED:BOARD:planning -->\n"
        )
        current["acceptedPublication"] = {
            **copy.deepcopy(existing_accepted),
            "source": "master_planner_v1",
            "gameplayRevision": expected,
            "interactionRevision": current_interaction.get("revision"),
            "markdown": accepted_markdown,
            "p5Diagrams": copy.deepcopy(current_gameplay.get("diagrams") or []),
            "p6Tables": copy.deepcopy(current_gameplay.get("tables") or []),
        }

    try:
        server_module.storage.mutate_job(job_id, persist)
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "job not found") from exc

    # P7 preview must be byte-semantically aligned with the renderer later used
    # by Feishu publishing; otherwise preview/Final drift returns.
    try:
        persisted_job = server_module.load_job(job_id)
        exact_render = render_feishu_document(persisted_job, server_module.job_path(job_id))
        exact_preview_html = _delivery_preview_html(exact_render)
    except Exception as exc:
        raise HTTPException(422, f"accepted Final render failed: {exc}") from exc

    preview = dict(legacy_preview)
    preview.update({
        "exportReady": bool(gate["ready"]),
        "blockerIds": list(gate["blockerIds"]),
        "legacyBlockerIds": list(gate["legacyBlockerIds"]),
        "plannerSupersededBlockerIds": list(gate["plannerSupersededBlockerIds"]),
        "completionSnapshot": completion,
        "masterPlanningReady": master_ready,
        "masterPlanningDocument": delivery["document"],
        "masterPlanningMarkdown": delivery["markdown"],
        "masterPlanningFeishuXml": delivery["feishuXml"],
        "masterPlanningQuality": quality,
        "masterPlanner": delivery.get("masterPlanner") or {},
        "legacyDeliveryPreviewHtml": legacy_preview.get("deliveryPreviewHtml", ""),
        "deliveryPreviewHtml": exact_preview_html,
    })
    return preview


def _publish_master_feishu(job_id: str, request_id: str, mode: str, gameplay_revision: int, interaction_revision: int) -> None:
    """Publish with Master P7 authority while preserving Feishu conflict safety."""
    def approval_guard() -> None:
        _master_publication_guard(
            server_module.load_job(job_id),
            expected_gameplay=gameplay_revision,
            expected_interaction=interaction_revision,
        )

    def persist_publication(publication: dict, history: list[dict] | None = None) -> dict:
        def merge(current: dict) -> dict:
            _master_publication_guard(
                current,
                expected_gameplay=gameplay_revision,
                expected_interaction=interaction_revision,
            )
            record = current.get("feishuPublication") or {}
            if record.get("requestId") not in {None, "", request_id}:
                raise PublicationConflict("publication operation was superseded")
            canonical = copy.deepcopy(publication)
            canonical.update(
                requestId=request_id,
                approvedGameplayRevision=gameplay_revision,
                approvedReviewRevision=interaction_revision,
                publicationAuthority="master_planner_v1",
            )
            current["feishuPublication"] = canonical
            if history is not None:
                current["feishuPublicationHistory"] = copy.deepcopy(history)
            return copy.deepcopy(canonical)
        return server_module.storage.mutate_job(job_id, merge)

    try:
        job = server_module.load_job(job_id)
        approval_guard()
        FeishuPublisher(
            server_module.LarkCli(),
            server_module.job_path(job_id),
            persist_publication,
            approval_guard=approval_guard,
        ).publish(job, request_id, mode)
    except (ReviewApprovalConflict, PublicationConflict) as exc:
        logger.info("Master Feishu publication stopped for %s: %s", job_id, exc)
        try:
            def mark_conflict(current: dict) -> None:
                record = current.get("feishuPublication") or {}
                if record.get("requestId") == request_id:
                    record.update(
                        status="conflict",
                        message="策划案版本已变化，请重新生成完整预览。",
                        updatedAt=datetime.now(timezone.utc).isoformat(),
                    )
            server_module.storage.mutate_job(job_id, mark_conflict)
        except Exception:
            logger.exception("failed to persist Master Feishu publication conflict for %s", job_id)
    except Exception:
        logger.exception("Master Feishu publication failed for %s", job_id)
        try:
            def mark_failed(current: dict) -> None:
                record = current.get("feishuPublication") or {}
                if record.get("requestId") == request_id:
                    record.update(
                        status="failed",
                        message="飞书连接失败，可以重试。",
                        updatedAt=datetime.now(timezone.utc).isoformat(),
                    )
            server_module.storage.mutate_job(job_id, mark_failed)
        except Exception:
            logger.exception("failed to persist Master Feishu publication failure for %s", job_id)


@app.post("/api/jobs/{job_id}/master-plan/feishu/publish", status_code=202)
def publish_master_plan_to_feishu(job_id: str, payload: dict = Body(...)):
    request_id = str(payload.get("requestId") or "")
    mode = str(payload.get("mode") or "update")
    folder_token = str(payload.get("folderToken") or "")
    folder_name = str(payload.get("folderName") or "").strip()[:160]
    if mode == "reuse":
        mode = "update"
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,80}", request_id):
        raise HTTPException(400, "invalid publication request id")
    if mode not in {"update", "new_version"}:
        raise HTTPException(400, "invalid publication mode")
    if folder_token and not re.fullmatch(r"[A-Za-z0-9_-]{4,256}", folder_token):
        raise HTTPException(400, "invalid Feishu folder token")

    def pin(current: dict):
        if current.get("archived"):
            raise HTTPException(409, "archived job is read-only")
        if server_module._competitor_mutation_active(current):
            raise HTTPException(409, "competitor reference mutation must finish before publication")
        try:
            revisions = _master_publication_guard(current)
        except ReviewApprovalConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        if current.get("status") != "completed" or not current.get("planningModel"):
            raise HTTPException(409, "completed planning document required")
        record = current.setdefault("feishuPublication", {})
        if record.get("requestId") == request_id and record.get("status") in {*server_module._PUBLICATION_BUSY_STATES, "published"}:
            return copy.deepcopy(server_module._public_feishu_publication(record)), False, revisions
        resume_partial = record.get("status") == "partial" and mode == "update"
        effective_request_id = str(record.get("requestId") or request_id) if resume_partial else request_id
        record.update(
            status="checking_auth",
            requestId=effective_request_id,
            resumePartial=resume_partial,
            approvedGameplayRevision=revisions["gameplayRevision"],
            approvedReviewRevision=revisions["interactionRevision"],
            publicationAuthority="master_planner_v1",
            message="正在检查飞书登录",
        )
        if mode == "new_version" or not record.get("documentToken"):
            if folder_token:
                record.update(folderToken=folder_token, folderName=folder_name or "已选择文件夹")
            else:
                record.pop("folderToken", None)
                record["folderName"] = "我的空间 / 策划案"
        return copy.deepcopy(server_module._public_feishu_publication(record)), True, revisions

    try:
        response, should_submit, revisions = server_module.storage.mutate_job(job_id, pin)
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "job not found") from exc
    if should_submit:
        effective_id = str((server_module.load_job(job_id).get("feishuPublication") or {}).get("requestId") or request_id)
        server_module.executor.submit(
            _publish_master_feishu,
            job_id,
            effective_id,
            mode,
            revisions["gameplayRevision"],
            revisions["interactionRevision"],
        )
    return response


@app.get("/api/jobs/{job_id}/master-plan")
def get_master_plan(job_id: str):
    try:
        job = server_module.load_job(job_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "job not found") from exc
    record = job.get("masterPlanning")
    if not isinstance(record, dict):
        raise HTTPException(404, "master plan not generated")
    return record
