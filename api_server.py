import copy
import sys
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
from backend.feishu_render import render_feishu_document  # noqa: E402
from backend.master_planner import MasterPlannerError  # noqa: E402
from backend.p7_master_gate import combine_master_p7_gate, merge_completion_snapshot  # noqa: E402
from backend.production_planning import ProductionPlanningError, build_master_planning_delivery  # noqa: E402
from backend.review_preview import _delivery_preview_html  # noqa: E402

server_module.BUILT_IN_VISION_API_BASE = DEFAULT_API_BASE
server_module.BUILT_IN_VISION_MODEL = DEFAULT_MODEL
server_module.BUILT_IN_VISION_API_KEY = ""

app = server_module.app  # noqa: E402,F401


def _provider_config(payload: dict) -> ProviderConfig:
    runtime = server_module._runtime_ai_config(
        str(payload.get("apiBase") or ""),
        str(payload.get("model") or ""),
        str(payload.get("apiKey") or ""),
    )
    return ProviderConfig(api_base=runtime["apiBase"], model=runtime["model"], api_key=runtime["apiKey"])


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
        if current_gameplay.get("revision") != expected:
            raise HTTPException(409, {"currentRevision": current_gameplay.get("revision", 0)})
        if gate["ready"]:
            current_gameplay.setdefault("reviewState", {})["previewRevision"] = expected
            current_gameplay["reviewState"]["status"] = "preview_ready"
        else:
            current_gameplay.setdefault("reviewState", {})["previewRevision"] = None
        current["masterPlanning"] = {
            "gameplayRevision": expected,
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
