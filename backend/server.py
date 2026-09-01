from __future__ import annotations

import shutil
import uuid
import logging
import copy
import json
import os
import re
import threading
from ipaddress import ip_address
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis_service import analyze_image_frame, analyze_local_evidence, analyze_video
from .gameplay_analysis import GameplayAnalysisQualityError, generate_gameplay_chapters, generate_gameplay_details, generate_gameplay_structure
from .gameplay_review_model import build_gameplay_recovery_model, ensure_gameplay_review_model, gameplay_gate, gameplay_model_has_content
from .gameplay_generation_quality import prune_cached_responses
from .gameplay_copy import migrate_gameplay_presentation
from .gameplay_rule_copy import migrate_gameplay_rule_copy
from .gameplay_review_service import GameplayReviewConflict, add_gameplay_context, apply_gameplay_operations, confirm_gameplay_chapter, confirm_gameplay_directory, redo_gameplay, reopen_gameplay_chapter, undo_gameplay
from .temporal_probe_orchestration import orchestrate_targeted_temporal_probes
from .gameplay_diagrams import add_diagram_feedback, approve_diagram, auto_generate_diagrams, delete_diagram, generate_diagram, regenerate_diagram
from .gameplay_tables import auto_generate_tables, table_action
from .local_evidence import extract_supplemental, merge_local_analysis
from .feishu_cli import LarkCli
from .feishu_publish import FeishuPublisher, PublicationConflict, ReviewApprovalConflict
from .planner import generate_plan, write_scene_specs
from .planning_model import build_standard_prompt
from .quality import reconcile_and_audit
from .review_model import ensure_review_model, review_gate, validate_review_model
from .review_preview import build_final_review_preview, build_review_preview
from .granularity_audit import granularity_audit_report
from .feishu_language_quality import language_quality_report
from .review_service import ReviewConflict, apply_operations, confirm_flow, confirm_rule_domains, confirm_stage, confirm_ue_flow, ensure_review_entity_metadata, record_reanalysis_suggestions, redo, sanitize_review_ui_state, undo
from .media_evidence import extract_audio_evidence
from .image_sequence import ImageSequenceError, persist_image_sequence, recover_persisted_image_sequence
from .reference_board_assets import ReferenceBoardAssetError, delete_reference_asset, persist_reference_assets, refresh_reference_assets, reorder_reference_assets, replace_reference_asset, rollback_reference_assets, rollback_replaced_reference_asset
from .auxiliary_video import analyze_context_window
from . import storage
from .storage import DATA_ROOT, ROOT, STANDARDS_ROOT, job_path, list_jobs, list_standards, load_job, new_job, save_job, save_standard, update_job
from .video_pipeline import extract_and_structure, inspect_video

app = FastAPI(title="ai策划案工具 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/artifacts", StaticFiles(directory=str(DATA_ROOT)), name="artifacts")
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mirror-eye")
logger = logging.getLogger("mirror-eye")
_DETAILED_CONTENT_GATE_POLICY = "delivery.detailed_content_gate"
BUILT_IN_VISION_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
BUILT_IN_VISION_MODEL = "qwen3.6-plus"
BUILT_IN_VISION_API_KEY = ""
GAMEPLAY_GENERATION_TIMEOUT_SECONDS = 300
_EDITABLE_ANALYSIS_FIELDS = {
    "what", "requirement", "eventType", "beforeState", "userAction", "systemResponse", "afterState",
    "regionStructure", "components", "visibleText", "rules", "motion", "gameMechanics", "gameState",
    "gameFeedback", "valueChanges", "stateVariations", "promptText", "unknowns", "evidenceLevel", "confidence",
}


@lru_cache(maxsize=1)
def _vision_env_values() -> dict[str, str]:
    env_path = ROOT / ".env.calibration"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _configured_value(key: str, fallback: str) -> str:
    return os.environ.get(key) or _vision_env_values().get(key) or fallback


def _runtime_ai_config(api_base: str, model: str, api_key: str) -> dict[str, str]:
    return {
        "apiBase": api_base.strip() or _configured_value("VISION_API_BASE", BUILT_IN_VISION_API_BASE),
        "model": model.strip() or _configured_value("VISION_MODEL", BUILT_IN_VISION_MODEL),
        "apiKey": api_key.strip() or _configured_value("VISION_API_KEY", BUILT_IN_VISION_API_KEY),
    }


def _trusted_context_ai_config(profile: Any) -> dict[str, str]:
    trusted = _runtime_ai_config("", "", "")
    if (not isinstance(profile, dict)
            or profile.get("apiBase") != trusted["apiBase"]
            or profile.get("model") != trusted["model"]):
        raise ValueError("trusted vision configuration required")
    return trusted


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    public = copy.deepcopy(job)
    for frame in public.get("frames", []):
        frame.get("supplementalEvidence", {}).pop("technicalError", None)
    public.get("auxiliaryVideo", {}).get("analysis", {}).pop("technicalError", None)
    if "feishuPublication" in public:
        public["feishuPublication"] = _public_feishu_publication(public["feishuPublication"])
    if isinstance(public.get("feishuPublicationHistory"), list):
        public["feishuPublicationHistory"] = [
            _public_feishu_publication(record)
            for record in public["feishuPublicationHistory"]
            if isinstance(record, dict)
        ]
    if "gameplayReviewGeneration" in public:
        public["gameplayReviewGeneration"] = _public_gameplay_review_generation(public["gameplayReviewGeneration"])
    if isinstance(public.get("gameplayReviewModel"), dict):
        public["gameplayReviewModel"] = _public_gameplay_review_model(public["gameplayReviewModel"])
    public.pop("gameplayReviewLastValidModel", None)
    public.pop("runtimeProfile", None)
    return _strip_private_values(public)


def _public_history_job(job: dict[str, Any]) -> dict[str, Any]:
    summary = {
        key: copy.deepcopy(job[key])
        for key in ("id", "status", "stage", "progress", "updatedAt", "createdAt", "metadata", "archived")
        if key in job
    }
    quality = job.get("qualityReport") or {}
    if "score" in quality:
        summary["qualityReport"] = {"score": quality["score"]}
    if "feishuPublication" in job:
        summary["feishuPublication"] = _public_feishu_publication(job["feishuPublication"])
    if "gameplayReviewGeneration" in job:
        summary["gameplayReviewGeneration"] = _public_gameplay_review_generation(job["gameplayReviewGeneration"])
    if isinstance(job.get("gameplayReviewModel"), dict):
        summary["gameplayReviewModel"] = _public_gameplay_review_model(job["gameplayReviewModel"])
    return _strip_private_values(summary)


_PRIVATE_PUBLIC_KEYS = {
    "technicalerror", "apikey", "api_key", "apibase", "api_base",
    "runtimeprofile", "localpath", "videopath", "screenshotpath",
}
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^(?:[a-zA-Z]:[\\/]|\\\\)")


def _is_local_absolute_path(value: str) -> bool:
    return bool(
        _WINDOWS_ABSOLUTE_PATH.match(value)
        or value.startswith("file://")
        or (value.startswith("/") and not value.startswith("/artifacts/"))
    )


def _strip_private_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_private_values(item)
            for key, item in value.items()
            if str(key).replace("-", "").lower() not in _PRIVATE_PUBLIC_KEYS
            and not (
                str(key).lower().endswith("path")
                and isinstance(item, str)
                and _is_local_absolute_path(item)
            )
        }
    if isinstance(value, list):
        return [_strip_private_values(item) for item in value]
    if isinstance(value, str) and _is_local_absolute_path(value):
        return ""
    return value


def _public_gameplay_review_model(model: dict[str, Any]) -> dict[str, Any]:
    wrapper = {"gameplayReviewModel": copy.deepcopy(model)}
    migrate_gameplay_presentation(wrapper)
    migrate_gameplay_rule_copy(wrapper)
    public = wrapper["gameplayReviewModel"]
    public["contextWindows"] = [
        {
            key: copy.deepcopy(record[key])
            for key in ("chapterId", "status")
            if key in record
        }
        for record in public.get("contextWindows") or []
        if isinstance(record, dict)
    ]
    return _strip_private_values(public)


def _public_gameplay_review_generation(record: dict[str, Any] | None) -> dict[str, Any]:
    record = record or {}
    status = record.get("status") if record.get("status") in {"queued", "running", "completed", "failed"} else "failed"
    progress = record.get("progress") if type(record.get("progress")) is int and 0 <= record["progress"] <= 100 else 0
    messages = {
        "Queued gameplay review generation.", "Generating gameplay review.",
        "Generating gameplay details from the confirmed structure.",
        "Gameplay review generated.", "Gameplay review generation failed. Please retry.",
    }
    errors = {"视觉模型未配置", "视觉模型请求失败", "视觉模型响应超时，请重试；如果持续发生，请改用响应更快的视觉模型", "视觉模型返回内容不符合玩法章节要求", "玩法章节生成失败"}
    interrupted_error = "任务因服务重启暂停，请点击重新生成继续；现有审核结果已保留"
    result = {"status": status, "progress": progress, "message": record.get("message") if record.get("message") in messages else "Gameplay review generation failed. Please retry."}
    phase = record.get("phase")
    if phase in {"queued", "requesting_model", "validating", "repairing", "finalizing"}:
        result["phase"] = phase
    for timing_key in ("startedAt", "lastProgressAt", "deadlineAt", "finishedAt"):
        timing_value = record.get(timing_key)
        if isinstance(timing_value, str) and len(timing_value) <= 64:
            result[timing_key] = timing_value
    if record.get("error") in errors or record.get("error") == interrupted_error:
        result["error"] = record["error"]
    logs = []
    for item in record.get("logs") or []:
        if not isinstance(item, dict) or not isinstance(item.get("message"), str):
            continue
        item_progress = item.get("progress")
        logs.append({
            "progress": item_progress if type(item_progress) is int and 0 <= item_progress <= 100 else 0,
            "message": item["message"][:240],
            "level": item.get("level") if item.get("level") in {"info", "warning", "error", "success"} else "info",
        })
    if logs:
        result["logs"] = logs[-60:]
    failure_kind = record.get("failureKind")
    if failure_kind not in {"quality", "network", "configuration", "system"} and status == "failed":
        error = record.get("error")
        if error == "视觉模型未配置":
            failure_kind = "configuration"
        elif error in {"视觉模型请求失败", "视觉模型响应超时，请重试；如果持续发生，请改用响应更快的视觉模型"}:
            failure_kind = "network"
        elif error == "视觉模型返回内容不符合玩法章节要求":
            failure_kind = "quality"
        elif error == "玩法章节生成失败":
            failure_kind = "system"
    if failure_kind in {"quality", "network", "configuration", "system"}:
        result["failureKind"] = failure_kind
    quality_issues = record.get("qualityIssues")
    if status == "failed" and failure_kind == "quality" and isinstance(quality_issues, list):
        safe_issues = [item[:160] for item in quality_issues if isinstance(item, str) and item.strip()]
        if safe_issues:
            result["qualityIssues"] = safe_issues[:5]
    return result


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gameplay_generation_phase(progress: int) -> str:
    if progress <= 0:
        return "queued"
    if progress <= 10:
        return "requesting_model"
    if progress <= 55:
        return "validating"
    if progress < 100:
        return "repairing"
    return "finalizing"


def _active_gameplay_generation(job: dict[str, Any], generation_id: str) -> bool:
    generation = job.get("gameplayReviewGeneration") or {}
    return generation.get("generationId") == generation_id and generation.get("status") in {"queued", "running"}


def _monotonic_generation_progress(previous: dict[str, Any], reported_progress: int) -> int:
    reported = max(0, min(100, int(reported_progress)))
    previous_progress = previous.get("progress") if type(previous.get("progress")) is int else 0
    return max(previous_progress, reported)


def _refresh_gameplay_generation_activity(
    previous: dict[str, Any],
    progress: int,
    log_message: str = "",
) -> dict[str, Any]:
    """Refresh the inactivity deadline only when generation makes observable progress."""
    safe_progress = max(0, min(100, int(progress)))
    previous_progress = previous.get("progress") if type(previous.get("progress")) is int else -1
    logs = previous.get("logs") or []
    previous_log = logs[-1].get("message") if logs and isinstance(logs[-1], dict) else ""
    meaningful_log = bool(log_message) and log_message != previous_log
    if safe_progress <= previous_progress and not meaningful_log and previous.get("lastProgressAt"):
        return {}
    now = datetime.now(timezone.utc)
    return {
        "lastProgressAt": now.isoformat(),
        "deadlineAt": (now + timedelta(seconds=GAMEPLAY_GENERATION_TIMEOUT_SECONDS)).isoformat(),
    }


def _parse_generation_deadline(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _expire_gameplay_generation(job_id: str, generation_id: str) -> None:
    reschedule_after: float | None = None

    def expire(current: dict[str, Any]) -> None:
        nonlocal reschedule_after
        if not _active_gameplay_generation(current, generation_id):
            return
        generation = current.get("gameplayReviewGeneration") or {}
        deadline = _parse_generation_deadline(generation.get("deadlineAt"))
        now = datetime.now(timezone.utc)
        if deadline is not None and deadline > now:
            reschedule_after = max(0.1, (deadline - now).total_seconds())
            return
        current["gameplayReviewGeneration"] = {
            **generation,
            "status": "failed",
            "message": "Gameplay review generation failed. Please retry.",
            "error": "视觉模型响应超时，请重试；如果持续发生，请改用响应更快的视觉模型",
            "failureKind": "network",
            "finishedAt": _utc_timestamp(),
        }
        model = ensure_gameplay_review_model(current)
        model["contentState"] = "failed"
        if gameplay_model_has_content(model):
            model["lastValidRevision"] = model.get("revision")
        else:
            model["lifecycleState"] = "generation_failed"

    storage.mutate_job(job_id, expire)
    if reschedule_after is not None:
        _schedule_gameplay_generation_timeout(job_id, generation_id, reschedule_after)


def _schedule_gameplay_generation_timeout(
    job_id: str,
    generation_id: str,
    delay_seconds: float | None = None,
) -> None:
    try:
        if not _active_gameplay_generation(load_job(job_id), generation_id):
            return
    except Exception:
        return
    timer = threading.Timer(
        delay_seconds if delay_seconds is not None else GAMEPLAY_GENERATION_TIMEOUT_SECONDS,
        _expire_gameplay_generation,
        args=(job_id, generation_id),
    )
    timer.daemon = True
    timer.start()


def _safe_gameplay_generation_error(exc: Exception) -> str:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__
    names = {type(item).__name__ for item in chain}
    if names & {"APITimeoutError", "ReadTimeout", "TimeoutError"}:
        return "视觉模型响应超时，请重试；如果持续发生，请改用响应更快的视觉模型"
    if names & {
        "APIConnectionError", "APIStatusError", "InternalServerError", "RateLimitError",
        "RemoteProtocolError", "ConnectError", "ReadError",
    }:
        return "视觉模型请求失败"
    if not isinstance(exc, GameplayAnalysisQualityError):
        return "玩法章节生成失败"
    message = str(exc).casefold()
    if "unavailable" in message:
        return "视觉模型未配置"
    if "request failed" in message:
        return "视觉模型请求失败"
    return "视觉模型返回内容不符合玩法章节要求"


def _safe_gameplay_generation_quality_issues(exc: Exception) -> list[str]:
    if not isinstance(exc, GameplayAnalysisQualityError):
        return []
    technical_message = str(exc)
    message = technical_message.casefold()
    mappings = (
        ("invalid detailed gameplay model", "详细玩法模型字段、引用或因果链不完整"),
        ("lead planner output audit failed", "主策完整性检查未通过"),
        ("generation quality floor failed", "详细规则完整度未达到发布门槛"),
        ("must contain exactly one mechanism", "单个章节返回了错误数量的玩法机制"),
        ("changed the confirmed structure", "生成结果改动了已确认目录"),
        ("no valid evidence frames", "章节缺少有效素材依据"),
        ("has no mechanisms", "已确认目录中没有可生成的玩法机制"),
    )
    issues = [label for marker, label in mappings if marker in message][:3]
    if "lead planner output audit failed" not in message:
        return issues

    safe_labels = {
        "LEAD_PLANNER_RULE_DEPTH_INSUFFICIENT": "缺少可审核的规则正文或明确待确认选项",
        "LEAD_PLANNER_INTERNAL_LANGUAGE": "混入了内部字段、编号或生成占位词",
        "LEAD_PLANNER_SCREEN_CAPTION_AS_RULE": "把截图描述当成了玩法规则",
        "LEAD_PLANNER_RULE_TOO_SHALLOW": "规则说明过于空泛，无法用于审核",
        "LEAD_PLANNER_SYSTEM_HIERARCHY_MISSING": "缺少系统与子系统层级",
        "LANGUAGE_PRESENTATION_IN_PROSE": "把纯画面表现写进了玩法正文",
        "LANGUAGE_LOGIC_PRESENTATION_MIXED": "把玩法逻辑和画面表现混写在同一条规则中",
        "LANGUAGE_REVIEW_META": "混入了审核过程或生成状态说明",
        "LANGUAGE_FILLER": "包含没有新增业务信息的套话",
        "LANGUAGE_COMMON_KNOWLEDGE": "包含无法指导实现或测试的常识句",
        "LANGUAGE_EMPTY_ABSTRACTION": "包含没有具体对象、动作或结果的抽象句",
        "LANGUAGE_CROSS_CHAPTER_DUPLICATION": "与其他章节重复了同一段正文",
        "CARRIER_DUPLICATE_PRIMARY_FACT": "同一规则在多个正文载体重复出现",
        "SAMPLE_RESERVE_PUBLISHED_AS_FACT": "把其他项目样例误写成了当前项目事实",
    }
    pattern = re.compile(
        r"(?:(?:GCH-)(\d{3}):)?("
        + "|".join(re.escape(code) for code in safe_labels)
        + r")"
    )
    for chapter_number, code in pattern.findall(technical_message):
        prefix = f"第{int(chapter_number)}章" if chapter_number else "玩法模型"
        detail = prefix + safe_labels[code]
        if detail not in issues:
            issues.append(detail)
        if len(issues) >= 5:
            break
    return issues


def _gameplay_generation_failure_kind(exc: Exception) -> str:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__
    names = {type(item).__name__ for item in chain}
    if names & {
        "APIConnectionError", "APITimeoutError", "APIStatusError", "InternalServerError", "RateLimitError",
        "ReadTimeout", "TimeoutError", "RemoteProtocolError", "ConnectError", "ReadError",
    }:
        return "network"
    if isinstance(exc, GameplayAnalysisQualityError):
        return "configuration" if "unavailable" in str(exc).casefold() else "quality"
    return "system"


_PUBLICATION_FIELDS = {
    "status", "documentUrl", "folderName",
}
_PUBLICATION_MESSAGES = {
    "正在检查飞书登录",
    "飞书登录已过期",
    "飞书文档已有修改，不会自动覆盖",
    "审核版本已变化，请重新生成导出预览。",
    "飞书连接失败，可以重试。",
    "飞书文档已创建，但导出尚未完成；可继续重试",
    "飞书导出失败，可以重试",
    "已发布到飞书",
    "The Feishu document has remote edits; publish a new version to preserve them.",
}
_PUBLICATION_BUSY_STATES = {
    "checking_auth", "creating_folder", "creating_document", "uploading_evidence",
    "uploading_board_media", "creating_whiteboard", "verifying",
}


def _public_feishu_publication(record: dict[str, Any] | None) -> dict[str, Any]:
    record = record or {}
    public = {key: record[key] for key in _PUBLICATION_FIELDS if isinstance(record.get(key), str)}
    if record.get("message") in _PUBLICATION_MESSAGES:
        public["message"] = record["message"]
    return public


def _require_loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    try:
        address = ip_address(host)
        allowed = address.is_loopback or address.is_private
    except ValueError:
        allowed = False
    if not allowed:
        raise HTTPException(403, "task history is available only on this computer or its private LAN")


def _competitor_mutation_active(job: dict[str, Any]) -> bool:
    # Competitor boards are legacy, optional reference material.  The current
    # planning-only delivery must never let their upload state block Final,
    # preview generation, or publication.
    return False


def _publish_feishu(job_id: str, request_id: str, mode: str) -> None:
    approved: int | None = None
    approved_gameplay: int | None = None

    def require_current(current: dict[str, Any]) -> dict[str, Any]:
        record = current.get("feishuPublication") or {}
        if (
            record.get("requestId") != request_id
            or record.get("approvedReviewRevision") != approved
            or record.get("approvedGameplayRevision") != approved_gameplay
        ):
            raise PublicationConflict("publication operation was superseded")
        model = current.get("reviewModel") or {}
        if model and (
            approved != model.get("revision")
            or model.get("reviewState", {}).get("previewRevision") != approved
            or not review_gate(model)["exportReady"]
        ):
            raise ReviewApprovalConflict("审核版本已变化，请重新生成导出预览。")
        gameplay = current.get("gameplayReviewModel")
        if isinstance(gameplay, dict) and (
            approved_gameplay != gameplay.get("revision")
            or gameplay.get("reviewState", {}).get("previewRevision") != approved_gameplay
            or not gameplay_gate(gameplay, model)["exportReady"]
        ):
            raise ReviewApprovalConflict("gameplay review revision changed; regenerate final preview")
        if _competitor_mutation_active(current):
            raise ReviewApprovalConflict("competitor reference mutation is active")
        return record

    try:
        job = load_job(job_id)
        record = job.get("feishuPublication") or {}
        approved = record.get("approvedReviewRevision")
        approved_gameplay = record.get("approvedGameplayRevision")

        def approval_guard() -> None:
            require_current(load_job(job_id))

        def persist_publication(publication: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            def merge(current: dict[str, Any]) -> dict[str, Any]:
                require_current(current)
                if publication.get("requestId", request_id) != request_id:
                    raise PublicationConflict("publication operation was superseded")
                incoming_approved = publication.get("approvedReviewRevision", approved)
                if incoming_approved != approved:
                    raise PublicationConflict("publication approval pin changed")
                incoming_gameplay = publication.get("approvedGameplayRevision", approved_gameplay)
                if incoming_gameplay != approved_gameplay:
                    raise PublicationConflict("gameplay publication approval pin changed")
                canonical = copy.deepcopy(publication)
                canonical.update(
                    requestId=request_id,
                    approvedReviewRevision=approved,
                    approvedGameplayRevision=approved_gameplay,
                )
                current["feishuPublication"] = canonical
                if history is not None:
                    current["feishuPublicationHistory"] = copy.deepcopy(history)
                return copy.deepcopy(canonical)

            return storage.mutate_job(job_id, merge)

        approval_guard()
        FeishuPublisher(LarkCli(), job_path(job_id), persist_publication, approval_guard=approval_guard).publish(job, request_id, mode)
    except ReviewApprovalConflict:
        logger.info("Feishu publication review approval conflict for job %s", job_id)
        try:
            def mark_conflict(current: dict[str, Any]) -> None:
                record = current.get("feishuPublication") or {}
                if (
                    record.get("requestId") != request_id
                    or record.get("approvedReviewRevision") != approved
                    or record.get("approvedGameplayRevision") != approved_gameplay
                ):
                    raise PublicationConflict("publication operation was superseded")
                record.update(status="conflict", message="审核版本已变化，请重新生成导出预览。")

            storage.mutate_job(job_id, mark_conflict)
        except PublicationConflict:
            pass
    except PublicationConflict:
        logger.info("Feishu publication operation or remote revision conflict for job %s", job_id)
    except Exception:
        logger.exception("Feishu publication failed for job %s", job_id)
        try:
            def mark_failed(current: dict[str, Any]) -> None:
                record = current.get("feishuPublication") or {}
                if (
                    record.get("requestId") != request_id
                    or record.get("approvedReviewRevision") != approved
                    or record.get("approvedGameplayRevision") != approved_gameplay
                ):
                    raise PublicationConflict("publication operation was superseded")
                if record.get("status") in _PUBLICATION_BUSY_STATES:
                    record.update(status="failed", message="飞书连接失败，可以重试。", updatedAt=datetime.now(timezone.utc).isoformat())

            storage.mutate_job(job_id, mark_failed)
        except PublicationConflict:
            pass
        except Exception as exc:
            logger.exception("failed to persist Feishu publication error for job %s", job_id)


def _has_reusable_analysis(job: dict[str, Any]) -> bool:
    summary = job.get("analysisSummary") or {}
    return (
        job.get("checkpoint") == "analysis-complete"
        and summary.get("qualityQualified") is not False
        and summary.get("modelEnabled") is True
        and int(summary.get("qualifiedDetailFrameCount") or 0) > 0
        and bool(job.get("frames"))
        and all(bool(frame.get("analysis")) for frame in job["frames"])
    )


def _process(job_id: str, runtime_config: dict[str, Any]) -> None:
    def progress(value: int, stage: str) -> None:
        if load_job(job_id).get("cancelRequested"):
            raise InterruptedError("任务已由用户取消")
        update_job(job_id, status="processing", progress=value, stage=stage)

    try:
        job = load_job(job_id)
        if job.get("checkpoint") in {"frames-complete", "analysis-complete", "directory-pending"} and job.get("frames"):
            frames, scenes = job["frames"], job["scenes"]
        else:
            sources = list(job_path(job_id).glob("source.*"))
            if not sources:
                raise ValueError("source video missing")
            video_path = sources[0]
            metadata, changes, samples = inspect_video(video_path, progress)
            job.update(video=metadata, sceneChanges=changes, checkpoint="scan-complete")
            job["mediaEvidence"] = extract_audio_evidence(video_path, job_path(job_id), runtime_config)
            storage.mutate_job(job_id, lambda current: current.update(
                video=metadata, sceneChanges=changes, checkpoint="scan-complete",
                mediaEvidence=copy.deepcopy(job["mediaEvidence"]),
            ))
            frames, scenes, component_tracks = extract_and_structure(
                video_path, job_path(job_id) / "frames", job_path(job_id) / "structures",
                samples, changes, progress,
            )
            storage.mutate_job(job_id, lambda current: current.update(
                frames=copy.deepcopy(frames), scenes=copy.deepcopy(scenes),
                componentTracks=copy.deepcopy(component_tracks), checkpoint="frames-complete",
            ))
        if _has_reusable_analysis(job):
            summary = job["analysisSummary"]
        else:
            auxiliary_video_path = next(job_path(job_id).glob("auxiliary/source.*"), None)
            frames, scenes, summary = analyze_video(
                job_path(job_id), frames, scenes, runtime_config,
                job["metadata"]["mode"], progress,
                input_type=job["metadata"].get("inputType", "video"),
                auxiliary_video_path=auxiliary_video_path,
            )
            # Persist paid model output before downstream audit/rendering so a
            # post-processing failure can resume without repeating API calls.
            def persist_analysis(current: dict[str, Any]) -> None:
                current.update(
                    frames=copy.deepcopy(frames), scenes=copy.deepcopy(scenes),
                    analysisSummary=copy.deepcopy(summary), checkpoint="analysis-complete",
                )

            storage.mutate_job(job_id, persist_analysis)
            if summary.get("qualityQualified") is False:
                failed_requests = int(summary.get("requestFailureDetailFrameCount") or 0)
                detail_count = int(summary.get("detailFrameCount") or 0)
                if failed_requests == detail_count and detail_count:
                    raise RuntimeError(f"视觉模型连接失败：{failed_requests}/{detail_count} 个请求未完成，请检查网络或模型服务后重试。")
                raise RuntimeError(
                    "视觉模型未产出合格交互分析："
                    f"{summary.get('qualifiedDetailFrameCount', 0)}/{detail_count} 个代表帧达标，"
                    f"另有 {failed_requests} 个模型请求失败；已保存合格结果，重试时只处理未达标素材。"
                )

        def finalize(current: dict[str, Any]) -> None:
            if current.get("reviewModel"):
                candidate_job = copy.deepcopy(current)
                candidate_job.pop("reviewModel", None)
                current["reviewModel"] = record_reanalysis_suggestions(current["reviewModel"], ensure_review_model(candidate_job))
            else:
                current["reviewModel"] = ensure_review_model(current)
            if not current["reviewModel"]["quality"]["qualified"]:
                raise RuntimeError("Visual model did not produce a qualified GVE16 review draft; analyze again before manual review.")
            ensure_gameplay_review_model(current)
            _refresh_outputs(current)
            current["sceneSpecs"] = write_scene_specs(job_path(job_id), current)
            current.update(status="processing", progress=96, stage="正在整理玩法目录", checkpoint="directory-pending")

        storage.mutate_job(job_id, finalize)
        _generate_gameplay_review(job_id, runtime_config)
        update_job(job_id, status="completed", progress=100, stage="策划案生成完成", checkpoint="complete")
    except InterruptedError as exc:
        update_job(job_id, status="cancelled", stage="已取消", error=str(exc))
    except Exception as exc:
        logger.exception("job %s failed", job_id)
        update_job(job_id, status="failed", stage="处理失败", error=str(exc))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "mirror-eye",
        "screenCoder": (ROOT / "ScreenCoder").exists(),
        "systemLessons": (ROOT / "data" / "planner_knowledge" / "system-lessons-v1.json").exists(),
        "capabilities": [
            "interrupted-screenshot-import-recovery-v1",
            "resumable-gameplay-detail-generation-v1",
            "pending-evidence-decision-cards-v1",
            "review-entry-pending-decision-boundary-v1",
            "actionable-gameplay-quality-diagnostics-v1",
            "generated-rule-carrier-routing-v1",
            "generated-rule-carrier-routing-v2",
            "review-entry-pending-gap-quality-v1",
            "incomplete-flow-decision-routing-v1",
            "evidence-grounded-gameplay-review-v1",
        ],
    }


@app.get("/api/config/public")
def public_config() -> dict[str, Any]:
    config = _runtime_ai_config("", "", "")
    return {
        "hasBuiltInApi": bool(config["apiKey"]),
        "apiBase": config["apiBase"],
        "model": config["model"],
    }


_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _video_suffix(upload: UploadFile | None) -> str:
    suffix = Path(upload.filename or "video.mp4").suffix.lower() if upload else ""
    if suffix not in _VIDEO_SUFFIXES:
        raise ValueError("unsupported video format")
    return suffix


def _persist_primary_video(job_id: str, upload: UploadFile | None) -> str:
    suffix = _video_suffix(upload)
    target = job_path(job_id) / f"source{suffix}"
    with target.open("wb") as output:
        shutil.copyfileobj(upload.file, output, length=1024 * 1024)
    return f"/artifacts/{job_id}/{target.name}"


def _persist_auxiliary_video(job_id: str, upload: UploadFile) -> dict[str, Any]:
    suffix = _video_suffix(upload)
    target = job_path(job_id) / "auxiliary" / f"source{suffix}"
    target.parent.mkdir(exist_ok=True)
    with target.open("wb") as output:
        shutil.copyfileobj(upload.file, output, length=1024 * 1024)
    return {
        "filename": upload.filename,
        "sourceUrl": f"/artifacts/{job_id}/auxiliary/{target.name}",
        "status": "pending",
    }


@app.post("/api/jobs")
def create_job(
    video: UploadFile | None = File(None),
    images: list[UploadFile] | None = File(None),
    image_manifest: str = Form(""),
    mode: str = Form("gameplay"),
    project_name: str = Form("未命名项目"),
    scope: str = Form(""),
    api_base: str = Form("https://dashscope.aliyuncs.com/compatible-mode/v1"),
    model: str = Form("qwen3.6-plus"),
    api_key: str = Form(""),
    transcription_api_base: str = Form(""),
    transcription_model: str = Form("whisper-1"),
    transcription_api_key: str = Form(""),
    standard_id: str = Form(""),
) -> dict[str, Any]:
    if mode not in {"gameplay", "interaction"}:
        raise HTTPException(400, "mode must be gameplay or interaction")
    uploads = images or []
    input_type = "image_sequence" if uploads else "video"
    if not uploads and video is None:
        raise HTTPException(400, "请上传 2–50 张截图")
    job = new_job({
        "mode": mode,
        "projectName": project_name,
        "scope": scope,
        "sourceName": video.filename if video and not uploads else None,
        "inputType": input_type,
        "standardId": standard_id or None,
    })
    job["contentModelVersion"] = 2
    try:
        if uploads:
            frames, scenes, tracks = persist_image_sequence(job_path(job["id"]), uploads, image_manifest)
            job.update(frames=frames, scenes=scenes, componentTracks=tracks, checkpoint="frames-complete")
            if video is not None:
                job["auxiliaryVideo"] = _persist_auxiliary_video(job["id"], video)
        else:
            job["sourceUrl"] = _persist_primary_video(job["id"], video)
    except (ImageSequenceError, ValueError) as exc:
        shutil.rmtree(job_path(job["id"]), ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc
    plan_example = ""
    if standard_id:
        standard_path = STANDARDS_ROOT / f"{standard_id}.json"
        if standard_path.exists():
            standard = json.loads(standard_path.read_text(encoding="utf-8"))
            plan_example = f"{standard.get('description', '')}\n{standard.get('planExample', '')}"
    standard_prompt = build_standard_prompt(mode, plan_example)
    ai_config = _runtime_ai_config(api_base, model, api_key)
    runtime_config = {
        **ai_config,
        "transcriptionApiBase": transcription_api_base.strip() or ai_config["apiBase"],
        "transcriptionModel": transcription_model.strip() or "whisper-1",
        "transcriptionApiKey": transcription_api_key.strip() or ai_config["apiKey"],
        "standardPrompt": standard_prompt,
    }
    job["runtimeProfile"] = {key: value for key, value in runtime_config.items() if "Key" not in key}
    try:
        ensure_gameplay_review_model(job)
    except Exception:
        logger.warning(
            "gameplay model initialization failed during job creation for %s; using deterministic recovery model",
            job["id"],
            exc_info=True,
        )
        job["gameplayReviewModel"] = build_gameplay_recovery_model(job)
    save_job(job)
    executor.submit(_process, job["id"], runtime_config)
    return _public_job(job)


@app.get("/api/jobs")
def get_jobs(request: Request, include_archived: bool = False) -> list[dict[str, Any]]:
    _require_loopback(request)
    return [_public_history_job(job) for job in list_jobs(include_archived)]


@app.post("/api/jobs/{job_id}/archive")
def archive_job(job_id: str, request: Request, archived: bool = Form(True)) -> dict[str, Any]:
    _require_loopback(request)
    try:
        return update_job(job_id, archived=archived)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")


def _ensure_gameplay_model_for_read(job: dict[str, Any], job_id: str) -> None:
    try:
        ensure_gameplay_review_model(job)
    except Exception:
        logger.warning(
            "gameplay model normalization failed during read for job %s; returning deterministic recovery skeleton",
            job_id,
            exc_info=True,
        )
        job["gameplayReviewModel"] = build_gameplay_recovery_model(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    try:
        job = load_job(job_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")
    if "reviewModel" not in job:
        return _public_job(job)
    candidate = copy.deepcopy(job)
    _ensure_gameplay_model_for_read(candidate, job_id)
    try:
        refreshed = _refresh_reference_board_statuses(candidate, job_path(job_id))
        if refreshed:
            _finish_reference_status_refresh(candidate)
    except ReferenceBoardAssetError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _public_job(candidate)


def _generate_gameplay_review(job_id: str, runtime_config: dict[str, Any], generation_id: str | None = None) -> None:
    generation_id = generation_id or uuid.uuid4().hex

    def mark_running(current: dict[str, Any]) -> None:
        previous = current.get("gameplayReviewGeneration") or {}
        if previous.get("generationId") not in {None, generation_id}:
            return
        started_at = previous.get("startedAt") or _utc_timestamp()
        activity = {} if previous.get("deadlineAt") else _refresh_gameplay_generation_activity(previous, 0)
        current["gameplayReviewGeneration"] = {
            **previous,
            "status": "running",
            "progress": 0,
            "message": "Generating gameplay review.",
            "phase": "queued",
            "generationId": generation_id,
            "startedAt": started_at,
            **activity,
        }

    def progress(value: int, _message: str) -> None:
        reported_progress = max(0, min(100, int(value)))
        def update_progress(current: dict[str, Any]) -> None:
            if not _active_gameplay_generation(current, generation_id):
                return
            previous = current.get("gameplayReviewGeneration") or {}
            safe_progress = _monotonic_generation_progress(previous, reported_progress)
            activity = _refresh_gameplay_generation_activity(previous, safe_progress, _message)
            current["gameplayReviewGeneration"] = {
                **previous,
                "status": "running",
                "progress": safe_progress,
                "message": "Generating gameplay review.",
                "phase": _gameplay_generation_phase(safe_progress),
                **activity,
            }
        storage.mutate_job(job_id, update_progress)

    try:
        storage.mutate_job(job_id, mark_running)
        current = load_job(job_id)
        root = job_path(job_id)
        model = generate_gameplay_structure(current, root, runtime_config, progress)
        model["lifecycleState"] = "ready"
        model["contentState"] = "ready"
        previous = current.get("gameplayReviewModel") if isinstance(current.get("gameplayReviewModel"), dict) else {}
        if model.get("contentModelVersion") == 2 and previous:
            model["temporalProbeRequests"] = copy.deepcopy(previous.get("temporalProbeRequests") or [])
            model["temporalEvidence"] = copy.deepcopy(previous.get("temporalEvidence") or {"facts": [], "observations": [], "ruleCandidates": [], "gaps": []})
            from .rule_normalizer import build_rule_intelligence_v1
            model["ruleIntelligenceProjection"] = build_rule_intelligence_v1(model, model["approvedData"])
        auxiliary_video = next((root / "auxiliary").glob("source.*"), None) if root is not None else None
        if model.get("contentModelVersion") == 2 and auxiliary_video is not None:
            model = orchestrate_targeted_temporal_probes(
                model,
                auxiliary_video_path=auxiliary_video,
                probe_workspace=root / "temporal-probes",
            ).model
        def complete(current: dict[str, Any]) -> None:
            if not _active_gameplay_generation(current, generation_id):
                return
            previous_generation = current.get("gameplayReviewGeneration") or {}
            current.update(
                gameplayReviewModel=copy.deepcopy(model),
                gameplayReviewGeneration={
                    **previous_generation,
                    "status": "completed",
                    "progress": 100,
                    "message": "Gameplay structure ready for review.",
                    "phase": "finalizing",
                    "finishedAt": _utc_timestamp(),
                },
            )
        storage.mutate_job(job_id, complete)
    except Exception as exc:
        logger.exception("gameplay review generation failed for job %s", job_id)
        try:
            def preserve_failed_container(current: dict[str, Any]) -> None:
                if not _active_gameplay_generation(current, generation_id):
                    return
                previous_generation = current.get("gameplayReviewGeneration") or {}
                current["gameplayReviewGeneration"] = {
                    **previous_generation,
                    "status": "failed", "progress": 0,
                    "message": "Gameplay review generation failed. Please retry.",
                    "error": _safe_gameplay_generation_error(exc),
                    "failureKind": _gameplay_generation_failure_kind(exc),
                    "finishedAt": _utc_timestamp(),
                }
                model = ensure_gameplay_review_model(current)
                if not gameplay_model_has_content(model):
                    model["lifecycleState"] = "generation_failed"
                    model["contentState"] = "failed"
                else:
                    model["contentState"] = "failed"
                    model["lastValidRevision"] = model.get("revision")

            storage.mutate_job(job_id, preserve_failed_container)
        except Exception:
            logger.exception("failed to persist gameplay review generation error for job %s", job_id)


def _generate_confirmed_gameplay_details(
    job_id: str,
    runtime_config: dict[str, Any],
    generation_id: str | None = None,
) -> None:
    generation_id = generation_id or uuid.uuid4().hex

    def set_generation(current: dict[str, Any], status: str, value: int, log_message: str, level: str = "info") -> None:
        previous = current.get("gameplayReviewGeneration") or {}
        if previous.get("generationId") not in {None, generation_id}:
            return
        if status in {"running", "completed"} and previous.get("generationId") == generation_id and not _active_gameplay_generation(current, generation_id):
            return
        safe_progress = max(0, min(100, int(value)))
        display_progress = _monotonic_generation_progress(previous, safe_progress) if status == "running" else safe_progress
        logs = [copy.deepcopy(item) for item in previous.get("logs") or [] if isinstance(item, dict)]
        entry = {"progress": safe_progress, "message": log_message[:240], "level": level}
        if not logs or logs[-1] != entry:
            logs.append(entry)
        activity = _refresh_gameplay_generation_activity(previous, display_progress, log_message) if status == "running" else {}
        current["gameplayReviewGeneration"] = {
            **previous,
            "status": status,
            "progress": display_progress,
            "message": "Generating gameplay details from the confirmed structure." if status == "running" else "Gameplay review generation failed. Please retry.",
            "logs": logs[-60:],
            "phase": _gameplay_generation_phase(display_progress),
            "generationId": generation_id,
            "startedAt": previous.get("startedAt") or _utc_timestamp(),
            **activity,
        }
        if status in {"completed", "failed"}:
            current["gameplayReviewGeneration"]["finishedAt"] = _utc_timestamp()

    def progress(value: int, message: str) -> None:
        storage.mutate_job(job_id, lambda current: set_generation(current, "running", value, message))

    try:
        current = load_job(job_id)
        confirmed = copy.deepcopy(current.get("gameplayReviewModel") or {})
        chapter_count = len(confirmed.get("chapters") or [])
        storage.mutate_job(
            job_id,
            lambda job: set_generation(job, "running", 0, f"开始补全当前目录中的 {chapter_count} 个玩法章节"),
        )
        model = generate_gameplay_details(current, confirmed, job_path(job_id), runtime_config, progress)
        def complete(job: dict[str, Any]) -> None:
            if not _active_gameplay_generation(job, generation_id):
                return
            job["gameplayReviewModel"] = copy.deepcopy(model)
            set_generation(job, "completed", 100, f"当前目录中的 {chapter_count} 个玩法章节补全完成", "success")
            job["gameplayReviewGeneration"]["message"] = "Gameplay review generated."
        storage.mutate_job(job_id, complete)
    except Exception as exc:
        logger.exception("confirmed gameplay detail generation failed for job %s", job_id)
        def fail(current: dict[str, Any]) -> None:
            if not _active_gameplay_generation(current, generation_id):
                return
            previous_progress = int((current.get("gameplayReviewGeneration") or {}).get("progress") or 0)
            set_generation(current, "failed", previous_progress, "本次补全未完成，现有审核结果已保留", "error")
            current["gameplayReviewGeneration"]["error"] = _safe_gameplay_generation_error(exc)
            current["gameplayReviewGeneration"]["failureKind"] = _gameplay_generation_failure_kind(exc)
            quality_issues = _safe_gameplay_generation_quality_issues(exc)
            if quality_issues:
                current["gameplayReviewGeneration"]["qualityIssues"] = quality_issues
        storage.mutate_job(job_id, fail)


@app.post("/api/jobs/{job_id}/gameplay-review/generate", status_code=202)
def generate_gameplay_review(
    job_id: str,
    api_base: str = Form("https://dashscope.aliyuncs.com/compatible-mode/v1"),
    model: str = Form("qwen3.6-plus"),
    api_key: str = Form(""),
    force: bool = Form(False),
) -> dict[str, Any]:
    should_generate_details = False
    generation_id = uuid.uuid4().hex
    runtime_config = _runtime_ai_config(api_base, model, api_key)
    if not runtime_config["apiKey"]:
        raise HTTPException(400, "视觉模型未配置：请填写 API Key 后重试")

    def queue(current: dict[str, Any]) -> dict[str, Any]:
        nonlocal should_generate_details
        interaction = current.get("reviewModel") or {}
        existing = current.get("gameplayReviewModel")
        generation = current.get("gameplayReviewGeneration") or {}
        existing_has_content = gameplay_model_has_content(existing)
        retrying_failed_initial_structure = not existing_has_content and generation.get("status") == "failed"
        if not retrying_failed_initial_structure:
            if not interaction or not review_gate(interaction)["exportReady"]:
                raise HTTPException(409, "interaction review must be export-ready")
            if interaction.get("reviewState", {}).get("previewRevision") != interaction.get("revision"):
                raise HTTPException(409, "interaction preview is stale")
        if (current.get("gameplayReviewGeneration") or {}).get("status") in {"queued", "running"}:
            raise HTTPException(409, "gameplay review generation is already running")
        def mark_content_pending() -> None:
            if not isinstance(existing, dict):
                return
            existing["contentState"] = "pending"
            if existing_has_content:
                existing["lastValidRevision"] = existing.get("revision")
            else:
                existing["lifecycleState"] = "generation_required"
        if not force and existing_has_content and (existing.get("directory") or {}).get("status") == "confirmed":
            existing["interactionRevision"] = interaction.get("revision")
            existing.setdefault("reviewState", {})["previewRevision"] = None
            existing["reviewState"]["interactionHandoffConfirmed"] = True
            if existing["reviewState"].get("status") == "detail_generation_pending":
                mark_content_pending()
                started_at = datetime.now(timezone.utc)
                current["gameplayReviewGeneration"] = {
                    "status": "queued",
                    "progress": 0,
                    "message": "Queued gameplay review generation.",
                    "phase": "queued",
                    "generationId": generation_id,
                    "startedAt": started_at.isoformat(),
                    "lastProgressAt": started_at.isoformat(),
                    "deadlineAt": (started_at + timedelta(seconds=GAMEPLAY_GENERATION_TIMEOUT_SECONDS)).isoformat(),
                }
                should_generate_details = True
                return _public_gameplay_review_generation(current["gameplayReviewGeneration"])
            current["gameplayReviewGeneration"] = {"status": "completed", "progress": 100, "message": "Gameplay directory preserved after interaction review."}
            return _public_gameplay_review_generation(current["gameplayReviewGeneration"])
        mark_content_pending()
        started_at = datetime.now(timezone.utc)
        current["gameplayReviewGeneration"] = {
            "status": "queued",
            "progress": 0,
            "message": "Queued gameplay review generation.",
            "phase": "queued",
            "generationId": generation_id,
            "startedAt": started_at.isoformat(),
            "lastProgressAt": started_at.isoformat(),
            "deadlineAt": (started_at + timedelta(seconds=GAMEPLAY_GENERATION_TIMEOUT_SECONDS)).isoformat(),
        }
        return _public_gameplay_review_generation(current["gameplayReviewGeneration"])

    generation = _mutate_review_job(job_id, queue)
    if generation.get("status") == "completed":
        return generation
    try:
        executor.submit(_generate_confirmed_gameplay_details if should_generate_details else _generate_gameplay_review, job_id, runtime_config, generation_id)
        _schedule_gameplay_generation_timeout(job_id, generation_id)
    except Exception:
        try:
            storage.mutate_job(job_id, lambda current: current.__setitem__(
                "gameplayReviewGeneration", {"status": "failed", "progress": 0, "message": "Gameplay review generation failed. Please retry."}
            ))
        except Exception:
            logger.exception("failed to persist gameplay review submission error for job %s", job_id)
        raise
    return generation


@app.get("/api/jobs/{job_id}/plan")
def get_plan(job_id: str) -> dict[str, str]:
    try:
        job = load_job(job_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")
    return {"plan": job.get("plan", "")}


@app.post("/api/jobs/{job_id}/feishu/publish", status_code=202)
def publish_job_to_feishu(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
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

    def pin(job: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
        if job.get("archived"):
            raise HTTPException(409, "archived job is read-only")
        review_model = job.get("reviewModel") or {}
        if review_model:
            gate = review_gate(review_model)
            if not gate["exportReady"]:
                raise HTTPException(409, "审核未完成，无法发布")
            if review_model.get("reviewState", {}).get("previewRevision") != review_model.get("revision"):
                raise HTTPException(409, "请重新生成导出预览")
        gameplay_model = job.get("gameplayReviewModel")
        if isinstance(gameplay_model, dict):
            granularity = granularity_audit_report(gameplay_model)
            if not granularity["passed"]:
                message = granularity["findings"][0]["message"] if granularity["findings"] else "玩法正文颗粒度检查未通过"
                raise HTTPException(409, message)
            language = language_quality_report(gameplay_model)
            if not language["passed"]:
                message = language["findings"][0]["message"] if language["findings"] else "玩法正文语言检查未通过"
                raise HTTPException(409, message)
            if not gameplay_gate(gameplay_model, review_model)["exportReady"]:
                raise HTTPException(409, "gameplay review is not ready for publication")
            if gameplay_model.get("reviewState", {}).get("previewRevision") != gameplay_model.get("revision"):
                raise HTTPException(409, "gameplay final preview is stale")
        if _competitor_mutation_active(job):
            raise HTTPException(409, "competitor reference mutation must finish before publication")
        if job.get("status") != "completed" or not job.get("plan") or not job.get("planningModel"):
            raise HTTPException(409, "completed planning document required")
        record = job.setdefault("feishuPublication", {})
        if record.get("requestId") == request_id and (
            record.get("status") in _PUBLICATION_BUSY_STATES or record.get("status") == "published"
        ):
            if (
                record.get("approvedReviewRevision") != review_model.get("revision")
                or record.get("approvedGameplayRevision") != (
                    gameplay_model.get("revision") if isinstance(gameplay_model, dict) else None
                )
            ):
                raise HTTPException(409, "publication request belongs to an older review revision")
            return request_id, _public_feishu_publication(record), False
        resume_partial = record.get("status") == "partial" and mode == "update"
        if resume_partial and (
            record.get("approvedReviewRevision") not in {None, review_model.get("revision")}
            or record.get("approvedGameplayRevision") != (
                gameplay_model.get("revision") if isinstance(gameplay_model, dict) else None
            )
        ):
            raise HTTPException(409, "partial publication belongs to an older review revision")
        effective_request_id = str(record["requestId"]) if resume_partial and record.get("requestId") else request_id
        record.update(
            status="checking_auth", requestId=effective_request_id, resumePartial=resume_partial,
            approvedGameplayRevision=gameplay_model.get("revision") if isinstance(gameplay_model, dict) else None,
            approvedReviewRevision=review_model.get("revision"), message="正在检查飞书登录",
        )
        if mode == "new_version" or not record.get("documentToken"):
            if folder_token:
                record.update(folderToken=folder_token, folderName=folder_name or "已选择文件夹")
            else:
                record.pop("folderToken", None)
                record["folderName"] = "我的空间 / 策划案"
        return effective_request_id, _public_feishu_publication(record), True

    try:
        effective_request_id, response, should_submit = storage.mutate_job(job_id, pin)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")
    if should_submit:
        executor.submit(_publish_feishu, job_id, effective_request_id, mode)
    return response


@app.get("/api/jobs/{job_id}/feishu/publication")
def get_feishu_publication(job_id: str) -> dict[str, Any]:
    try:
        job = load_job(job_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")
    return _public_feishu_publication(job.get("feishuPublication"))


@app.post("/api/feishu/auth/start")
def start_feishu_auth() -> dict[str, str]:
    data = LarkCli().auth_start()
    url = str(data.get("verification_url") or data.get("verification_uri_complete") or "")
    device_code = str(data.get("device_code") or "")
    if not url or not device_code:
        raise HTTPException(502, "Feishu authorization did not return a verification URL")
    return {"verificationUrl": url, "deviceCode": device_code}


@app.get("/api/feishu/auth/status")
def get_feishu_auth_status() -> dict[str, Any]:
    data = LarkCli().auth_status()
    user = (data.get("identities") or {}).get("user") or {}
    authenticated = data.get("identity") == "user" or user.get("available") is True
    return {
        "authenticated": authenticated,
        "userName": str(user.get("userName") or data.get("user_name") or ""),
    }


@app.get("/api/feishu/folders")
def get_feishu_folders(parent_token: str = "") -> dict[str, Any]:
    if parent_token and not re.fullmatch(r"[A-Za-z0-9_-]{4,256}", parent_token):
        raise HTTPException(400, "invalid Feishu folder token")
    args = ["drive", "files", "list"]
    if parent_token:
        args.extend(["--folder-token", parent_token])
    args.extend(["--page-all", "--as", "user", "--json"])
    data = LarkCli().run(args).data
    items = data.get("files") or data.get("items") or []
    folders = []
    for item in items:
        if item.get("type") not in {None, "folder"}:
            continue
        token = str(item.get("token") or item.get("file_token") or item.get("folder_token") or "")
        name = str(item.get("name") or "").strip()
        if token and name:
            folders.append({"token": token, "name": name})
    folders.sort(key=lambda item: item["name"].casefold())
    return {"parentToken": parent_token, "folders": folders}


@app.post("/api/feishu/auth/complete")
def complete_feishu_auth(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    device_code = str(payload.get("deviceCode") or "")
    if not re.fullmatch(r"[A-Za-z0-9._-]{6,256}", device_code):
        raise HTTPException(400, "invalid Feishu device code")
    LarkCli().auth_complete(device_code)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    def cancel(job: dict[str, Any]) -> dict[str, Any]:
        if job["status"] not in {"completed", "failed", "cancelled"}:
            job["cancelRequested"] = True
            job["stage"] = "等待当前步骤结束后取消"
        return copy.deepcopy(job)

    try:
        return storage.mutate_job(job_id, cancel)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")


@app.post("/api/jobs/{job_id}/retry")
def retry_job(
    job_id: str,
    api_base: str = Form("https://dashscope.aliyuncs.com/compatible-mode/v1"),
    model: str = Form("qwen3.6-plus"),
    api_key: str = Form(""),
) -> dict[str, Any]:
    try:
        job = load_job(job_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")
    input_type = job.get("metadata", {}).get("inputType", "video")
    if input_type == "video" and not list(job_path(job_id).glob("source.*")):
        raise HTTPException(409, "source video missing")
    if input_type == "image_sequence" and not job.get("frames"):
        raise HTTPException(409, "截图素材未完整保存，无法原地重试；请重新选择原截图文件夹创建任务")
    def queue(current: dict[str, Any]) -> dict[str, Any]:
        checkpoint = "analysis-complete" if _has_reusable_analysis(current) else (
            "frames-complete" if current.get("metadata", {}).get("inputType") == "image_sequence" and current.get("frames") else None
        )
        current.update(status="queued", progress=0, stage="等待重试", error=None, cancelRequested=False, checkpoint=checkpoint)
        return copy.deepcopy(current)

    job = storage.mutate_job(job_id, queue)
    executor.submit(_process, job_id, _runtime_ai_config(api_base, model, api_key))
    return job


@app.post("/api/jobs/{job_id}/reanalyze")
def reanalyze_job(
    job_id: str,
    api_base: str = Form("https://dashscope.aliyuncs.com/compatible-mode/v1"),
    model: str = Form("qwen3.6-plus"),
    api_key: str = Form(""),
) -> dict[str, Any]:
    def queue(job: dict[str, Any]) -> dict[str, Any]:
        if not job.get("frames"):
            raise HTTPException(409, "existing evidence frames missing")
        job.update(status="queued", progress=63, stage="复用既有证据，准备整片重新解读", error=None, cancelRequested=False, checkpoint="frames-complete")
        return copy.deepcopy(job)

    job = _mutate_review_job(job_id, queue)
    executor.submit(_process, job_id, _runtime_ai_config(api_base, model, api_key))
    return job


@app.post("/api/jobs/{job_id}/review")
def save_review(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def mutate(job: dict[str, Any]) -> dict[str, Any]:
        decisions = payload.get("frames", {})
        for frame in job.get("frames", []):
            decision = decisions.get(frame["id"])
            if isinstance(decision, dict):
                frame["confirmed"] = bool(decision.get("confirmed"))
                if isinstance(decision.get("analysis"), dict):
                    baseline = frame.get("lastModelAnalysis") or frame.get("analysis", {})
                    human_fields = set(frame.get("humanEditedFields", []))
                    explicit_fields = decision.get("humanEditedFields")
                    if isinstance(explicit_fields, list):
                        human_fields.update(field for field in explicit_fields if field in _EDITABLE_ANALYSIS_FIELDS)
                    for field, value in decision["analysis"].items():
                        if not isinstance(explicit_fields, list) and field in _EDITABLE_ANALYSIS_FIELDS and value != baseline.get(field, ""):
                            human_fields.add(field)
                        frame["analysis"][field] = value
                    frame["humanEditedFields"] = sorted(human_fields)
        total = len(job.get("frames", []))
        confirmed = sum(1 for frame in job.get("frames", []) if frame.get("confirmed"))
        unresolved = sum(1 for frame in job.get("frames", []) if frame.get("analysis", {}).get("evidenceLevel") == "未知待确认")
        job["reviewProgress"] = {"confirmed": confirmed, "total": total, "percent": round(confirmed * 100 / max(1, total)), "unresolved": unresolved, "readyForFinal": bool(total and confirmed == total and unresolved == 0)}
        _refresh_outputs(job)
        return copy.deepcopy(job["reviewProgress"])

    return _mutate_review_job(job_id, mutate)


def _load_review_job(job_id: str) -> dict[str, Any]:
    try:
        job = load_job(job_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")
    return job


def _mutate_review_job(job_id: str, mutation) -> Any:
    def checked(job: dict[str, Any]) -> Any:
        if job.get("archived"):
            raise HTTPException(409, "archived job is read-only")
        return mutation(job)

    try:
        return storage.mutate_job(job_id, checked)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "job not found")


def _review_model_response(job: dict[str, Any]) -> dict[str, Any]:
    model = _public_job(job)["reviewModel"]
    model["reviewUiState"] = sanitize_review_ui_state(model, job.get("reviewUiState"))
    annotations_path = job_path(str(job.get("id") or "")) / "structures" / "ue-flow-annotations.json"
    if annotations_path.exists():
        try:
            annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
            if annotations.get("schemaVersion") == "ue-flow-annotations-v1":
                model["ueFlowAnnotations"] = annotations
        except (OSError, ValueError, TypeError):
            logger.warning("invalid UE flow annotation sidecar for job %s", job.get("id"))
    return model


def _require_review_revision(job: dict[str, Any], expected: Any) -> None:
    current = (job.get("reviewModel") or {}).get("revision")
    if type(expected) is not int or expected != current:
        raise ReviewConflict(current_revision=current or 0)


def _finish_reference_board_mutation(job: dict[str, Any], board_key: str) -> dict[str, Any]:
    model = job["reviewModel"]
    board = model["referenceBoards"][board_key]
    board["status"] = "ready" if board["assets"] else "pending"
    model["revision"] += 1
    model["reviewState"]["previewRevision"] = None
    if errors := validate_review_model(model, include_legacy=False):
        raise ValueError("; ".join(errors))
    return model


def _refresh_reference_board_statuses(job: dict[str, Any], job_dir: Path) -> bool:
    changed = False
    for board_key in ("competitor",):
        changed = refresh_reference_assets(job, job_dir, board_key) or changed
    return changed


def _finish_reference_status_refresh(job: dict[str, Any]) -> None:
    model = job["reviewModel"]
    model["revision"] += 1
    model["reviewState"]["previewRevision"] = None
    if errors := validate_review_model(model, include_legacy=False):
        raise ValueError("; ".join(errors))


def _mutate_review_model(job_id: str, payload: dict[str, Any], operation) -> dict[str, Any]:
    def mutate(job: dict[str, Any]) -> dict[str, Any]:
        model = ensure_review_model(job)
        ensure_review_entity_metadata(model)
        try:
            job["reviewModel"] = operation(model, payload)
            _refresh_reference_board_statuses(job, job_path(job_id))
        except ReviewConflict as exc:
            raise HTTPException(409, {"currentRevision": exc.current_revision})
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return _review_model_response(job)

    return _mutate_review_job(job_id, mutate)


def _gameplay_model_response(job: dict[str, Any]) -> dict[str, Any]:
    model = copy.deepcopy(job["gameplayReviewModel"])
    base_path = job_path(str(job.get("id") or ""))
    if not base_path:
        return model
    specs = (
        ("p5-review-diagrams.json", "p5-review-diagrams-v1", "diagrams", "p5Sidecar", "diagramCount", "P5 diagram"),
        ("p6-review-tables.json", "p6-review-tables-v1", "tables", "p6Sidecar", "tableCount", "P6 table"),
    )
    for filename, schema, collection_key, metadata_key, count_key, label in specs:
        sidecar_path = base_path / "structures" / filename
        if not sidecar_path.exists():
            continue
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            additions = sidecar.get(collection_key) if sidecar.get("schemaVersion") == schema else None
            if not isinstance(additions, list) or any(not isinstance(item, dict) or not item.get("id") for item in additions):
                raise ValueError(f"invalid {label} sidecar")
            by_id = {item.get("id"): index for index, item in enumerate(model.get(collection_key) or [])}
            merged = list(model.get(collection_key) or [])
            for item in additions:
                if item["id"] in by_id:
                    merged[by_id[item["id"]]] = copy.deepcopy(item)
                else:
                    merged.append(copy.deepcopy(item))
            model[collection_key] = merged
            model[metadata_key] = {"schemaVersion": schema, count_key: len(additions)}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logger.warning("invalid %s sidecar for job %s", label, job.get("id"))
    return model


def _mutate_gameplay_model(job_id: str, payload: dict[str, Any], operation) -> dict[str, Any]:
    def mutate(job: dict[str, Any]) -> dict[str, Any]:
        model = ensure_gameplay_review_model(job)
        try:
            job["gameplayReviewModel"] = operation(model, payload)
        except GameplayReviewConflict as exc:
            raise HTTPException(409, {"currentRevision": exc.current_revision}) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return _gameplay_model_response(job)

    return _mutate_review_job(job_id, mutate)


@app.get("/api/jobs/{job_id}/review-model")
def get_review_model(job_id: str) -> dict[str, Any]:
    job = _load_review_job(job_id)
    if "reviewModel" not in job:
        if job.get("archived"):
            job = copy.deepcopy(job)
            ensure_review_model(job)
            return _review_model_response(job)
        def create(current: dict[str, Any]) -> dict[str, Any]:
            ensure_review_model(current)
            return _review_model_response(current)

        return _mutate_review_job(job_id, create)
    if job.get("archived"):
        job = copy.deepcopy(job)
        try:
            if _refresh_reference_board_statuses(job, job_path(job_id)):
                _finish_reference_status_refresh(job)
        except ReferenceBoardAssetError as exc:
            raise HTTPException(400, str(exc)) from exc
        return _review_model_response(job)

    candidate = copy.deepcopy(job)
    try:
        candidate_model = candidate.get("reviewModel") or {}
        coverage_missing = any(
            not isinstance(source, dict) or not source.get("materialRole") or not source.get("stageId")
            for source in (candidate_model.get("sources") or {}).values()
        ) or any(
            not isinstance(stage, dict) or not isinstance(stage.get("sourceFrameIds"), list)
            for stage in candidate_model.get("stages") or []
        )
        if coverage_missing:
            ensure_review_model(candidate)
        model_changed = coverage_missing and candidate.get("reviewModel") != job.get("reviewModel")
        changed = _refresh_reference_board_statuses(candidate, job_path(job_id))
        if changed:
            _finish_reference_status_refresh(candidate)
    except ReferenceBoardAssetError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not changed and not model_changed:
        return _review_model_response(candidate)

    def refresh(current: dict[str, Any]) -> dict[str, Any]:
        ensure_review_model(current)
        try:
            if _refresh_reference_board_statuses(current, job_path(job_id)):
                _finish_reference_status_refresh(current)
        except ReferenceBoardAssetError as exc:
            raise HTTPException(400, str(exc)) from exc
        return _review_model_response(current)

    return _mutate_review_job(job_id, refresh)


def _mutate_reference_board(job_id: str, mutation) -> dict[str, Any]:
    def mutate(job: dict[str, Any]) -> dict[str, Any]:
        try:
            mutation(job)
            _refresh_reference_board_statuses(job, job_path(job_id))
        except ReviewConflict as exc:
            raise HTTPException(409, {"currentRevision": exc.current_revision})
        except (ReferenceBoardAssetError, ValueError) as exc:
            if getattr(exc, "cleanup_failed", False):
                logger.error("reference board asset cleanup failed for job %s", job_id)
            raise HTTPException(400, str(exc)) from exc
        return _review_model_response(job)

    return _mutate_review_job(job_id, mutate)


@app.post("/api/jobs/{job_id}/review-model/reference-boards/{board_key}/assets")
def upload_reference_board_assets(
    job_id: str,
    board_key: str,
    images: list[UploadFile] = File(...),
    manifest: str = Form(""),
    expectedRevision: int = Form(...),
) -> dict[str, Any]:
    def mutation(job: dict[str, Any]) -> None:
        before = copy.deepcopy(job["reviewModel"])
        persisted = False
        try:
            _require_review_revision(job, expectedRevision)
            persist_reference_assets(job, job_path(job_id), board_key, images, manifest)
            persisted = True
            _finish_reference_board_mutation(job, board_key)
        except Exception as exc:
            if persisted:
                cleanup_failures = rollback_reference_assets(job, job_path(job_id), board_key, before["referenceBoards"][board_key])
                if cleanup_failures:
                    exc.cleanup_failed = True
                    exc.add_note("reference asset cleanup failed")
            job["reviewModel"] = before
            raise

    return _mutate_reference_board(job_id, mutation)


@app.post("/api/jobs/{job_id}/review-model/reference-boards/{board_key}/assets/{asset_id}/replace")
def replace_missing_reference_board_asset(
    job_id: str,
    board_key: str,
    asset_id: str,
    image: UploadFile = File(...),
    expectedRevision: int = Form(...),
) -> dict[str, Any]:
    def mutation(job: dict[str, Any]) -> None:
        before = copy.deepcopy(job["reviewModel"])
        replaced = False
        try:
            _require_review_revision(job, expectedRevision)
            replace_reference_asset(job, job_path(job_id), board_key, asset_id, image)
            replaced = True
            _finish_reference_board_mutation(job, board_key)
        except Exception as exc:
            if replaced:
                cleanup_failures = rollback_replaced_reference_asset(job, job_path(job_id), board_key, asset_id, before["referenceBoards"][board_key])
                if cleanup_failures:
                    exc.cleanup_failed = True
                    exc.add_note("reference asset cleanup failed")
            job["reviewModel"] = before
            raise

    return _mutate_reference_board(job_id, mutation)


@app.delete("/api/jobs/{job_id}/review-model/reference-boards/{board_key}/assets/{asset_id}")
def remove_reference_board_asset(job_id: str, board_key: str, asset_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def mutation(job: dict[str, Any]) -> None:
        _require_review_revision(job, payload.get("expectedRevision"))
        delete_reference_asset(job, job_path(job_id), board_key, asset_id)
        _finish_reference_board_mutation(job, board_key)

    return _mutate_reference_board(job_id, mutation)


@app.post("/api/jobs/{job_id}/review-model/reference-boards/{board_key}/order")
def order_reference_board_assets(job_id: str, board_key: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def mutation(job: dict[str, Any]) -> None:
        _require_review_revision(job, payload.get("expectedRevision"))
        reorder_reference_assets(job, job_path(job_id), board_key, payload.get("assetIds"))
        _finish_reference_board_mutation(job, board_key)

    return _mutate_reference_board(job_id, mutation)


@app.post("/api/jobs/{job_id}/review-model/preview")
def create_review_preview(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def mutate(job: dict[str, Any]) -> dict[str, Any]:
        if "reviewModel" not in job:
            raise HTTPException(409, "review model required")
        expected = payload.get("expectedRevision")
        if type(expected) is not int or expected != job["reviewModel"].get("revision"):
            raise HTTPException(409, {"currentRevision": job["reviewModel"].get("revision")})
        preview = build_review_preview(job, job_path(job_id))
        job["plan"] = generate_plan(job)
        return preview

    return _mutate_review_job(job_id, mutate)


@app.post("/api/jobs/{job_id}/review-model/ui-state")
def save_review_ui_state(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def mutate(job: dict[str, Any]) -> dict[str, Any]:
        model = ensure_review_model(job)
        job["reviewUiState"] = sanitize_review_ui_state(model, payload)
        return copy.deepcopy(job["reviewUiState"])

    return _mutate_review_job(job_id, mutate)


@app.post("/api/jobs/{job_id}/review-model/operations")
def apply_review_operations(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(
        job_id,
        payload,
        lambda model, value: apply_operations(model, value.get("operations", []), value.get("expectedRevision")),
    )


@app.get("/api/jobs/{job_id}/gameplay-review-model")
def get_gameplay_review_model(job_id: str) -> dict[str, Any]:
    job = _load_review_job(job_id)
    candidate = copy.deepcopy(job)
    _ensure_gameplay_model_for_read(candidate, job_id)
    try:
        migrate_gameplay_presentation(candidate)
    except Exception:
        logger.warning("gameplay model normalization failed during read for job %s; returning deterministic recovery skeleton", job_id, exc_info=True)
        candidate["gameplayReviewModel"] = build_gameplay_recovery_model(candidate)
    return _gameplay_model_response(candidate)


@app.post("/api/jobs/{job_id}/gameplay-review-model/final-preview")
def create_gameplay_final_preview(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    should_queue_autofill = False

    def mutation(job: dict[str, Any]) -> dict[str, Any]:
        nonlocal should_queue_autofill
        model = job.get("gameplayReviewModel") or {}
        expected = payload.get("expectedRevision")
        if type(expected) is not int or expected != model.get("revision"):
            raise HTTPException(409, {"currentRevision": model.get("revision", 0)})
        if (model.get("reviewState") or {}).get("status") == "detail_generation_pending":
            raise HTTPException(409, "详细规则尚未生成完成，请返回玩法目录继续生成；已确认目录不会丢失")
        if _competitor_mutation_active(job):
            raise HTTPException(409, "competitor reference mutation must finish before preview")
        preview = build_final_review_preview(job, job_path(job_id))
        blockers = preview.get("blockerIds") or []
        chapters = [item for item in model.get("chapters") or [] if isinstance(item, dict)]
        confirmed = bool(chapters) and all(
            item.get("status") in {"approved", "conditional", "not_applicable"}
            and (item.get("confirmation") or {}).get("confirmed") is True
            for item in chapters
        )
        auto_codes = {
            "LEAD_PLANNER_RULE_DEPTH_INSUFFICIENT", "GAMEPLAY_DEPTH_INSUFFICIENT",
            "RULES_MISSING", "VERIFICATION_MISSING", "BOUNDARY_OR_CONFIGURATION_MISSING",
            "OPTIONAL_MODULE_EVIDENCE_INVALID",
        }
        only_repairable_depth_gaps = bool(blockers) and all(
            isinstance(item, str)
            and item.startswith("GCH-")
            and item.rsplit(":", 1)[-1] in auto_codes
            for item in blockers
        )
        repairable_quality_prefixes = ("LANGUAGE_", "GRANULARITY_")
        only_repairable_quality_gaps = bool(blockers) and all(
            isinstance(item, str) and item.startswith(repairable_quality_prefixes)
            for item in blockers
        )
        detail_generation_pending = (model.get("reviewState") or {}).get("status") == "detail_generation_pending"
        if detail_generation_pending or (confirmed and (only_repairable_depth_gaps or only_repairable_quality_gaps)):
            generation = job.get("gameplayReviewGeneration") or {}
            if generation.get("status") not in {"queued", "running"}:
                job["gameplayReviewGeneration"] = {
                    "status": "queued", "progress": 0,
                    "message": "正在根据已确认内容自动补全玩法章节。",
                }
                should_queue_autofill = True
            active = job.get("gameplayReviewGeneration") or {}
            preview["autoCompletion"] = {
                "status": active.get("status", "queued"),
                "progress": int(active.get("progress") or 0),
            }
        return preview

    preview = _mutate_review_job(job_id, mutation)
    if should_queue_autofill:
        try:
            executor.submit(_generate_confirmed_gameplay_details, job_id, _runtime_ai_config(
                str(payload.get("apiBase") or ""),
                str(payload.get("model") or ""),
                str(payload.get("apiKey") or ""),
            ))
        except Exception:
            storage.mutate_job(job_id, lambda current: current.__setitem__(
                "gameplayReviewGeneration", {
                    "status": "failed", "progress": 0,
                    "message": "自动补全未能启动，请重试。",
                    "error": "玩法章节自动补全未能启动",
                }
            ))
            preview["autoCompletion"] = {"status": "failed", "progress": 0}
    return preview


@app.post("/api/jobs/{job_id}/gameplay-review/chapters/{chapter_id}/context")
def create_gameplay_context(job_id: str, chapter_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    allowed_fields = {"trigger", "process", "result", "timing", "automaticTransition"}
    job = _load_review_job(job_id)
    if job.get("archived"):
        raise HTTPException(409, "archived job is read-only")
    model = ensure_gameplay_review_model(copy.deepcopy(job))
    expected = payload.get("expectedRevision")
    if type(expected) is not int or expected != model.get("revision"):
        raise HTTPException(409, {"currentRevision": model.get("revision", 0)})
    fields = payload.get("missingFields")
    anchor_frame_id = payload.get("anchorFrameId")
    manual_timestamp = payload.get("manualTimestamp")
    if manual_timestamp is not None and (not isinstance(manual_timestamp, (int, float)) or manual_timestamp < 0):
        raise HTTPException(400, "invalid manual timestamp")
    if (not isinstance(fields, list) or not fields or any(not isinstance(field, str) for field in fields)
            or len(fields) != len(set(fields)) or set(fields) - allowed_fields):
        raise HTTPException(400, "invalid missing fields")
    chapter = next((item for item in model.get("chapters") or [] if item.get("id") == chapter_id), None)
    anchor_ids = {item.get("frameId") for item in model.get("evidenceAnchors") or [] if isinstance(item, dict)}
    if not isinstance(chapter, dict) or not isinstance(anchor_frame_id, str) or anchor_frame_id not in anchor_ids or anchor_frame_id not in chapter.get("sourceFrameIds", []):
        raise HTTPException(400, "invalid chapter evidence anchor")
    root = job_path(job_id)
    screenshot_path = root / "frames" / f"{anchor_frame_id}.jpg"
    sources = list((root / "auxiliary").glob("source.*"))
    if not screenshot_path.is_file():
        raise HTTPException(409, "anchor screenshot unavailable")
    if not sources:
        raise HTTPException(409, "auxiliary video unavailable")
    try:
        config = _trusted_context_ai_config(job.get("runtimeProfile"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    result = analyze_context_window(
        chapter_id=chapter_id, anchor_frame_id=anchor_frame_id, screenshot_path=screenshot_path, video_path=sources[0],
        missing_fields=fields, job_dir=root, config=config, manual_timestamp=manual_timestamp,
    )
    if result.get("status") != "completed":
        return {"status": "needs_planner_location" if result.get("status") == "needs_planner_location" else "failed"}

    def persist(current: dict[str, Any]) -> dict[str, Any]:
        current_model = ensure_gameplay_review_model(current)
        context = {
            "chapterId": chapter_id, "anchorFrameId": anchor_frame_id, "matchedTime": result["matchedTime"],
            "radius": result["radius"], "evidenceTimestamps": result["evidenceTimestamps"],
            "facts": result["facts"], "confidence": result["confidence"], "status": "completed",
            "anchorAuthority": result.get("anchorAuthority", "visual_match"),
            "observationAuthority": result.get("observationAuthority", "observed_unreviewed"),
        }
        try:
            current["gameplayReviewModel"] = add_gameplay_context(current_model, chapter_id, context, expected)
        except GameplayReviewConflict as exc:
            raise HTTPException(409, {"currentRevision": exc.current_revision}) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return copy.deepcopy(current["gameplayReviewModel"]["contextWindows"][-1])

    return _mutate_review_job(job_id, persist)


@app.post("/api/jobs/{job_id}/gameplay-review-model/operations")
def apply_gameplay_review_operations(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: apply_gameplay_operations(model, value.get("operations", []), value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/undo")
def undo_gameplay_review_operations(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: undo_gameplay(model, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/redo")
def redo_gameplay_review_operations(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: redo_gameplay(model, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/confirm-chapter")
def confirm_gameplay_review_chapter(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: confirm_gameplay_chapter(model, value.get("chapterId", ""), value.get("expectedRevision"), value.get("decision", "approved")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/confirm-directory")
def confirm_gameplay_review_directory(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    model = _mutate_gameplay_model(job_id, payload, lambda current, value: confirm_gameplay_directory(current, value.get("expectedRevision")))
    if model.get("reviewState", {}).get("status") == "detail_generation_pending":
        try:
            executor.submit(_generate_confirmed_gameplay_details, job_id, _runtime_ai_config(
                str(payload.get("apiBase") or ""),
                str(payload.get("model") or ""),
                str(payload.get("apiKey") or ""),
            ))
        except Exception:
            storage.mutate_job(job_id, lambda current: current.__setitem__(
                "gameplayReviewGeneration", {
                    "status": "failed", "progress": 0,
                    "message": "Gameplay detail generation failed. Please retry.",
                }
            ))
            raise
    return model


@app.post("/api/jobs/{job_id}/gameplay-review-model/reopen-chapter")
def reopen_gameplay_review_chapter(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: reopen_gameplay_chapter(model, value.get("chapterId", ""), value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/diagrams")
def generate_gameplay_diagram(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(
        job_id,
        payload,
        lambda model, value: generate_diagram(model, value.get("chapterIds"), value.get("diagramType"), value.get("expectedRevision"))
        if value.get("chapterIds") or value.get("diagramType")
        else auto_generate_diagrams(model, value.get("expectedRevision")),
    )


@app.post("/api/jobs/{job_id}/gameplay-review-model/diagrams/{diagram_id}/feedback")
def feedback_gameplay_diagram(job_id: str, diagram_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: add_diagram_feedback(model, diagram_id, value.get("feedback"), value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/diagrams/{diagram_id}/regenerate")
def regenerate_gameplay_diagram(job_id: str, diagram_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: regenerate_diagram(model, diagram_id, value.get("feedback"), value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/diagrams/{diagram_id}/approve")
def approve_gameplay_diagram(job_id: str, diagram_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: approve_diagram(model, diagram_id, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/diagrams/{diagram_id}/delete")
def delete_gameplay_diagram(job_id: str, diagram_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: delete_diagram(model, diagram_id, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/tables")
def generate_gameplay_tables(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: auto_generate_tables(model, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/gameplay-review-model/tables/{table_id}/{action}")
def mutate_gameplay_table(job_id: str, table_id: str, action: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_gameplay_model(job_id, payload, lambda model, value: table_action(model, table_id, action, value.get("expectedRevision"), value.get("feedback", "")))


@app.post("/api/jobs/{job_id}/review-model/undo")
def undo_review_operations(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(job_id, payload, lambda model, value: undo(model, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/review-model/redo")
def redo_review_operations(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(job_id, payload, lambda model, value: redo(model, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/review-model/confirm-flow")
def confirm_review_flow(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(job_id, payload, lambda model, value: confirm_flow(model, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/review-model/confirm-stage")
def confirm_review_stage(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(job_id, payload, lambda model, value: confirm_stage(model, value.get("stageId", ""), value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/review-model/confirm-ue-flow")
def confirm_review_ue_flow(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(job_id, payload, lambda model, value: confirm_ue_flow(model, value.get("expectedRevision")))


@app.post("/api/jobs/{job_id}/review/confirm-rules")
def confirm_review_rules(job_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _mutate_review_model(job_id, payload, lambda model, value: confirm_rule_domains(model, value.get("expectedRevision")))


def _find_frame(job: dict[str, Any], frame_id: str) -> dict[str, Any]:
    frame = next((item for item in job.get("frames", []) if item.get("id") == frame_id), None)
    if not frame:
        raise HTTPException(404, "frame not found")
    return frame


def _refresh_outputs(job: dict[str, Any]) -> None:
    facts, review_queue, quality_report = reconcile_and_audit(job)
    job.update(factTable=facts, reviewQueue=review_queue, qualityReport=quality_report)
    job["plan"] = generate_plan(job)


def _reanalyze_frame(job_id: str, frame_id: str, runtime_config: dict[str, Any]) -> None:
    try:
        def mark_extracting(current: dict[str, Any]) -> None:
            frame = _find_frame(current, frame_id)
            frame["supplementalEvidence"] = {"status": "extracting", "samples": frame.get("supplementalEvidence", {}).get("samples", [])}

        storage.mutate_job(job_id, mark_extracting)
        job = load_job(job_id)
        frame = _find_frame(job, frame_id)
        source = next(iter(job_path(job_id).glob("source.*")), None)
        if not source:
            raise FileNotFoundError("源视频不可用，无法补取画面。")
        samples = extract_supplemental(
            source, job_path(job_id) / "supplemental", frame_id,
            float(frame.get("timestamp", 0)), float(job.get("video", {}).get("duration", 0)),
        )
        def mark_analyzing(current: dict[str, Any]) -> None:
            _find_frame(current, frame_id)["supplementalEvidence"] = {"status": "analyzing", "samples": samples}

        storage.mutate_job(job_id, mark_analyzing)
        job = load_job(job_id)
        frame = _find_frame(job, frame_id)
        scene = next(item for item in job.get("scenes", []) if item.get("id") == frame.get("sceneId"))
        candidate = analyze_local_evidence(job_path(job_id), frame, scene, samples, runtime_config, job["metadata"]["mode"])
        def merge_result(current: dict[str, Any]) -> None:
            canonical_frame = _find_frame(current, frame_id)
            merged = merge_local_analysis(canonical_frame, candidate)
            merged["supplementalEvidence"] = {
                "status": "ready", "samples": samples,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            current["frames"] = [merged if item.get("id") == frame_id else item for item in current["frames"]]
            source = (current.get("reviewModel", {}).get("sources") or {}).get(frame_id)
            if isinstance(source, dict):
                source["supplementalEvidence"] = copy.deepcopy(merged["supplementalEvidence"])
            _refresh_outputs(current)

        storage.mutate_job(job_id, merge_result)
    except Exception as exc:
        logger.exception("local frame reanalysis failed for %s/%s", job_id, frame_id)
        try:
            def mark_failed(current: dict[str, Any]) -> None:
                frame = _find_frame(current, frame_id)
                frame["supplementalEvidence"] = {
                    **frame.get("supplementalEvidence", {}),
                    "status": "failed", "message": "局部重新解读失败，可以保留现有内容后重试。",
                }

            storage.mutate_job(job_id, mark_failed)
        except Exception:
            logger.exception("failed to persist local reanalysis error")


@app.post("/api/jobs/{job_id}/frames/{frame_id}/supplement-and-reanalyze")
def supplement_and_reanalyze_frame(
    job_id: str,
    frame_id: str,
    api_base: str = Form("https://dashscope.aliyuncs.com/compatible-mode/v1"),
    model: str = Form("qwen3.6-plus"),
    api_key: str = Form(""),
) -> dict[str, Any]:
    def start(job: dict[str, Any]) -> dict[str, Any]:
        frame = _find_frame(job, frame_id)
        if frame.get("supplementalEvidence", {}).get("status") in {"extracting", "analyzing"}:
            raise HTTPException(409, "frame analysis already running")
        frame["supplementalEvidence"] = {**frame.get("supplementalEvidence", {}), "status": "extracting"}
        return copy.deepcopy(frame["supplementalEvidence"])

    supplemental = _mutate_review_job(job_id, start)
    executor.submit(_reanalyze_frame, job_id, frame_id, _runtime_ai_config(api_base, model, api_key))
    return supplemental


def _reanalyze_uploaded_frame(job_id: str, frame_id: str, runtime_config: dict[str, Any]) -> None:
    try:
        job = load_job(job_id)
        frame = _find_frame(job, frame_id)
        scene = next(item for item in job.get("scenes", []) if item.get("id") == frame.get("sceneId"))
        candidate = analyze_image_frame(job_path(job_id), frame, scene, runtime_config, job["metadata"]["mode"])

        def merge_result(current: dict[str, Any]) -> None:
            canonical = _find_frame(current, frame_id)
            merged = merge_local_analysis(canonical, candidate)
            merged["supplementalEvidence"] = {
                "status": "ready", "samples": [],
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            current["frames"] = [merged if item.get("id") == frame_id else item for item in current["frames"]]
            _refresh_outputs(current)

        storage.mutate_job(job_id, merge_result)
    except Exception as exc:
        logger.exception("uploaded frame reanalysis failed for %s/%s", job_id, frame_id)
        def mark_failed(current: dict[str, Any]) -> None:
            frame = _find_frame(current, frame_id)
            frame["supplementalEvidence"] = {
                **frame.get("supplementalEvidence", {}), "status": "failed",
                "message": str(exc) or "这张图重新识别失败，请检查模型配置后重试。",
            }
            source = (current.get("reviewModel", {}).get("sources") or {}).get(frame_id)
            if isinstance(source, dict):
                source["supplementalEvidence"] = copy.deepcopy(frame["supplementalEvidence"])
        try:
            storage.mutate_job(job_id, mark_failed)
        except Exception:
            logger.exception("failed to persist uploaded frame reanalysis error")


@app.post("/api/jobs/{job_id}/frames/{frame_id}/reanalyze-image")
def reanalyze_uploaded_frame(
    job_id: str,
    frame_id: str,
    api_base: str = Form("https://dashscope.aliyuncs.com/compatible-mode/v1"),
    model: str = Form("qwen3.6-plus"),
    api_key: str = Form(""),
) -> dict[str, Any]:
    def start(job: dict[str, Any]) -> dict[str, Any]:
        frame = _find_frame(job, frame_id)
        if frame.get("supplementalEvidence", {}).get("status") in {"extracting", "analyzing"}:
            raise HTTPException(409, "frame analysis already running")
        frame["supplementalEvidence"] = {**frame.get("supplementalEvidence", {}), "status": "analyzing", "samples": []}
        source = (job.get("reviewModel", {}).get("sources") or {}).get(frame_id)
        if isinstance(source, dict):
            source["supplementalEvidence"] = copy.deepcopy(frame["supplementalEvidence"])
        return copy.deepcopy(frame["supplementalEvidence"])

    status = _mutate_review_job(job_id, start)
    executor.submit(_reanalyze_uploaded_frame, job_id, frame_id, _runtime_ai_config(api_base, model, api_key))
    return status


def _resolve_suggestion(job_id: str, frame_id: str, field: str, accept: bool) -> dict[str, Any]:
    if field not in _EDITABLE_ANALYSIS_FIELDS:
        raise HTTPException(400, "field is not editable")
    def resolve(job: dict[str, Any]) -> dict[str, Any]:
        frame = _find_frame(job, frame_id)
        suggestions = frame.setdefault("analysisSuggestion", {})
        if field not in suggestions:
            raise HTTPException(404, "suggestion not found")
        if accept:
            frame.setdefault("analysis", {})[field] = suggestions[field]
            frame["humanEditedFields"] = sorted(set(frame.get("humanEditedFields", [])) | {field})
        suggestions.pop(field)
        _refresh_outputs(job)
        return copy.deepcopy(frame)

    return _mutate_review_job(job_id, resolve)


@app.post("/api/jobs/{job_id}/frames/{frame_id}/suggestions/{field}/accept")
def accept_frame_suggestion(job_id: str, frame_id: str, field: str) -> dict[str, Any]:
    return _resolve_suggestion(job_id, frame_id, field, True)


@app.delete("/api/jobs/{job_id}/frames/{frame_id}/suggestions/{field}")
def reject_frame_suggestion(job_id: str, frame_id: str, field: str) -> dict[str, Any]:
    return _resolve_suggestion(job_id, frame_id, field, False)


@app.get("/api/standards")
def get_standards() -> list[dict[str, Any]]:
    return list_standards()


@app.post("/api/standards")
def create_standard(
    name: str = Form(...), mode: str = Form(...), version: str = Form("1.0"),
    description: str = Form(""), plan_example: str = Form(""), source_job_id: str = Form(""),
) -> dict[str, Any]:
    if mode not in {"gameplay", "interaction"}:
        raise HTTPException(400, "mode must be gameplay or interaction")
    record = {"id": uuid.uuid4().hex, "name": name, "mode": mode, "version": version, "description": description, "planExample": plan_example, "sourceJobId": source_job_id or None, "createdAt": datetime.now(timezone.utc).isoformat()}
    return save_standard(record)


def _reanalyze_scene(job_id: str, scene_id: int, runtime_config: dict[str, Any]) -> None:
    try:
        job = load_job(job_id)
        selected_scene = next(scene for scene in job["scenes"] if scene["id"] == scene_id)
        ids = set(selected_scene["frameIds"])
        selected_frames = [frame for frame in job["frames"] if frame["id"] in ids]
        analyzed_frames, analyzed_scenes, summary = analyze_video(
            job_path(job_id), selected_frames, [selected_scene], runtime_config,
            job["metadata"]["mode"], lambda value, stage: update_job(job_id, stage=f"重分析场景 {scene_id + 1}：{stage}"),
        )
        frame_map = {frame["id"]: frame for frame in analyzed_frames}
        def merge_scene(current: dict[str, Any]) -> None:
            current["frames"] = [frame_map.get(frame["id"], frame) for frame in current["frames"]]
            current["scenes"] = [analyzed_scenes[0] if scene["id"] == scene_id else scene for scene in current["scenes"]]
            current.setdefault("analysisSummary", {})["lastSceneReanalysis"] = {"sceneId": scene_id, **summary}
            _refresh_outputs(current)
            current["sceneSpecs"] = write_scene_specs(job_path(job_id), current)
            current.update(status="completed", progress=100, stage=f"场景 {scene_id + 1} 重分析完成")

        storage.mutate_job(job_id, merge_scene)
    except Exception as exc:
        update_job(job_id, status="failed", stage="场景重分析失败", error=str(exc))


@app.post("/api/jobs/{job_id}/scenes/{scene_id}/reanalyze")
def reanalyze_scene(
    job_id: str,
    scene_id: int,
    api_base: str = Form("https://dashscope.aliyuncs.com/compatible-mode/v1"),
    model: str = Form("qwen3.6-plus"),
    api_key: str = Form(""),
) -> dict[str, Any]:
    def start(job: dict[str, Any]) -> dict[str, Any]:
        if not any(scene["id"] == scene_id for scene in job.get("scenes", [])):
            raise HTTPException(404, "scene not found")
        job.update(status="processing", stage=f"准备重分析场景 {scene_id + 1}", error=None)
        return copy.deepcopy(job)

    job = _mutate_review_job(job_id, start)
    executor.submit(_reanalyze_scene, job_id, scene_id, _runtime_ai_config(api_base, model, api_key))
    return job


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/mechanic-review")
def full_mechanic_review_page() -> FileResponse:
    return FileResponse(ROOT / "mechanic-review.html")


@app.get("/api/mechanic-review")
def full_mechanic_review_data() -> dict[str, Any]:
    artifact = ROOT / "artifacts/full-mechanic-reconstruction-2026-08-19/reconstructed-models.json"
    readability = ROOT / "artifacts/full-mechanic-reconstruction-2026-08-19/planner-readable-preview.json"
    acceptance_dir = ROOT / "artifacts/full-mechanic-acceptance-2026-08-19"
    decisions_path = acceptance_dir / "review-decisions.json"
    approved_rules_path = acceptance_dir / "approved-review-rules.json"
    if not artifact.exists():
        raise HTTPException(404, "mechanic reconstruction review is not available")
    approval_summary = None
    review_state = "pending_lead_planner_review"
    if decisions_path.exists() and approved_rules_path.exists():
        decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        approved = json.loads(approved_rules_path.read_text(encoding="utf-8"))
        if decisions.get("action") == "accept_all":
            review_state = "accepted"
            approval_summary = {
                "action": "accept_all",
                "approvedRuleCount": approved.get("approvedRuleCount", 0),
                "retainedConfirmedRuleCount": decisions.get("retainedConfirmedRuleCount", 0),
            }
    return {
        "artifactType": "mechanic_design_review",
        "publicationEligible": False,
        "reviewState": review_state,
        "approvalSummary": approval_summary,
        "models": json.loads(artifact.read_text(encoding="utf-8")),
        "plannerReadabilityProjection": json.loads(readability.read_text(encoding="utf-8")) if readability.exists() else [],
    }


@app.get("/accepted-planning-preview")
def accepted_planning_preview_page() -> FileResponse:
    return FileResponse(ROOT / "accepted-planning-preview.html")


@app.get("/api/accepted-planning-preview")
def accepted_planning_preview_data() -> dict[str, Any]:
    artifact = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19"
    planning = artifact / "human-planning-preview.md"
    sketch = artifact / "planning-sketch.md"
    body_crosswalk = artifact / "final-body-gve16-line-crosswalk.json"
    integrity = artifact / "publication-integrity.json"
    p5 = artifact / "p5-review-diagrams.json"
    p6 = artifact / "p6-review-tables.json"
    native_dir = artifact / "feishu-native-whiteboards"
    native_paths = {
        "planning": native_dir / "planning-preview.svg",
    }
    native_acceptance = native_dir / "acceptance.json"
    if not all(path.exists() for path in (planning, sketch, body_crosswalk, integrity, p5, p6, native_acceptance, *native_paths.values())):
        raise HTTPException(404, "accepted planning publication is not available")
    return {
        "publicationState": "published",
        "planningMarkdown": planning.read_text(encoding="utf-8"),
        "planningSketchMarkdown": sketch.read_text(encoding="utf-8"),
        "bodyCrosswalk": json.loads(body_crosswalk.read_text(encoding="utf-8")),
        "integrity": json.loads(integrity.read_text(encoding="utf-8")),
        "p5Diagrams": json.loads(p5.read_text(encoding="utf-8"))["diagrams"],
        "p6Tables": json.loads(p6.read_text(encoding="utf-8"))["tables"],
        "nativeBoards": [
            {"key": key, "title": "策划草图", "svg": path.read_text(encoding="utf-8")}
            for key, path in native_paths.items()
        ],
        "nativeBoardAcceptance": json.loads(native_acceptance.read_text(encoding="utf-8")),
    }


app.mount("/css", StaticFiles(directory=str(ROOT / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(ROOT / "js")), name="js")


@app.on_event("startup")
def resume_interrupted_jobs() -> None:
    prune_cached_responses(DATA_ROOT / ".gameplay-generation-cache")
    for record in DATA_ROOT.glob("*/job.json"):
        try:
            job = load_job(record.parent.name)
            generation = job.get("gameplayReviewGeneration") or {}
            if generation.get("status") in {"queued", "running"}:
                progress = generation.get("progress")
                job = update_job(job["id"], gameplayReviewGeneration={
                    "status": "failed",
                    "progress": progress if type(progress) is int and 0 <= progress <= 100 else 0,
                    "message": "Gameplay review generation failed. Please retry.",
                    "error": "任务因服务重启暂停，请点击重新生成继续；现有审核结果已保留",
                })
            if job.get("status") not in {"queued", "processing"} or job.get("cancelRequested"):
                continue
            input_type = job.get("metadata", {}).get("inputType", "video")
            if input_type == "video" and not list(record.parent.glob("source.*")):
                continue
            if input_type == "image_sequence" and not job.get("frames"):
                recovered = recover_persisted_image_sequence(record.parent)
                if not recovered:
                    update_job(
                        job["id"],
                        status="failed",
                        stage="截图导入被服务重启中断",
                        error="截图素材尚未完整保存，请重新选择原截图文件夹创建任务。",
                    )
                    continue
                recovered_frames, recovered_scenes, recovered_tracks = recovered
                def restore_import(current: dict[str, Any]) -> dict[str, Any]:
                    current.update(
                        frames=copy.deepcopy(recovered_frames),
                        scenes=copy.deepcopy(recovered_scenes),
                        componentTracks=copy.deepcopy(recovered_tracks),
                        checkpoint="frames-complete",
                    )
                    return current
                job = storage.mutate_job(job["id"], restore_import)
            runtime_config = _runtime_ai_config(
                "", str(job.get("runtimeProfile", {}).get("model") or "qwen3.6-plus"), "",
            )
            if not runtime_config["apiKey"] and not _has_reusable_analysis(job):
                update_job(
                    job["id"],
                    status="failed",
                    stage="素材已恢复，等待重新分析",
                    error=f"已恢复 {len(job.get('frames') or [])} 张截图；服务重启后无法恢复浏览器中的 API Key，请填写 API Key 后点击重试。",
                )
                continue
            job = update_job(job["id"], status="queued", stage=f"从检查点恢复：{job.get('checkpoint') or '开始'}")
            executor.submit(_process, job["id"], runtime_config)
        except Exception:
            continue
