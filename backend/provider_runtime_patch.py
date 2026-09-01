from __future__ import annotations

import re
from typing import Any

from fastapi import Body, HTTPException

from . import analysis_service, gameplay_analysis, server
from .master_planner_sanitizer import (
    sanitize_optional_modules_for_master_planner,
    sanitize_semantics_for_master_planner,
)
from .provider_adapter import (
    DEFAULT_API_BASE,
    DEFAULT_MODEL,
    ProviderConfig,
    ProviderError,
    create_client,
    validate_connection,
)


_installed = False
_original_client = analysis_service._client
_original_detail_prompt = gameplay_analysis._prompt
_original_structure_prompt = gameplay_analysis._structure_prompt
_original_cached_call = gameplay_analysis._cached_call

_MASTER_PLANNER_OVERRIDE = r"""

【Master Planner 最终规则：以下要求优先于本提示词中更早出现的 evidence-only / pending-only 约束】
- 证据不足不阻断机制重建。可以根据跨帧状态、上下文、机制常识和项目内已知规则形成具体结论。
- 每条新增机制结论必须携带 knowledgeStatus：CONFIRMED / INFERRED / PROPOSED / CONFLICT。
- INFERRED 用于复原原玩法；PROPOSED 用于为了研发闭环主动补出的实现方案。两者都是可发布正文。
- 正文只写具体策划结论，不得写“【推断】”“根据现有素材推测”“尚未确认”“建议确认”等来源说明，也不要仅因状态较低使用“可能/或许/大概率”逃避决策。
- 若 mechanism、claim、formula、parameter 或 acceptance case 是推断/方案，请把状态放进 knowledgeStatus，而不是改写成 unknown/pending。
- 只有存在明确互斥证据且无法形成唯一结论时才使用 CONFLICT。
- 参数、公式、生命周期、波次、随机池等实现闭环内容可以由 AI 提出 PROPOSED 方案；不得因为缺少直接画面证据自动删除这些内容或强制转换成决策卡。
""".strip()


def _runtime_client(config: dict[str, Any]):
    base = str(config.get("apiBase") or "").strip().rstrip("/")
    if "127.0.0.1" in base or "localhost" in base:
        return _original_client(config)
    try:
        return create_client(ProviderConfig.from_mapping(config))
    except ProviderError:
        return None


def _master_detail_prompt(frame_ids: list[str]) -> str:
    return _original_detail_prompt(frame_ids) + "\n\n" + _MASTER_PLANNER_OVERRIDE


def _master_structure_prompt(frame_ids: list[str]) -> str:
    prompt = _original_structure_prompt(frame_ids)
    prompt = re.sub(
        r"每个子系统最多包含 8 个机制，超过时必须按真实业务责任拆分为多个子系统，不能把整个项目压成一个大组。",
        "子系统与机制数量没有固定上限；只按真实业务责任与可独立审核的规则边界拆分，禁止为了满足数量限制而合并或拆分。",
        prompt,
    )
    return prompt + "\n\n" + _MASTER_PLANNER_OVERRIDE + r"""
目录阶段也必须给每个 mechanism 增加 knowledgeStatus。CONFIRMED 必须引用真实 sourceFrameIds；INFERRED / PROPOSED 应尽量引用提供上下文的 sourceFrameIds，但引用仅表示上下文来源，不会把推断伪装成画面事实。不得因为缺少直接截图而删除一个对核心循环必要的隐藏机制。
"""


def _master_cached_call(job, job_dir, runtime_config, phase, prompt, images, max_tokens, structure=None):
    """Ensure the Master Planner contract is the last instruction seen by the model."""
    return _original_cached_call(
        job, job_dir, runtime_config, phase,
        str(prompt).rstrip() + "\n\n" + _MASTER_PLANNER_OVERRIDE,
        images, max_tokens, structure,
    )


def _master_validate_structure_response(value: Any, known_frame_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("systems"), list) or not value["systems"]:
        raise gameplay_analysis.GameplayAnalysisQualityError("gameplay structure response must contain systems")
    result: dict[str, Any] = {"systems": []}
    seen_systems: set[str] = set()
    seen_mechanisms: set[str] = set()

    def title_key(raw: Any) -> str:
        title = re.sub(r"[\s\-—_·:：/（）()]+", "", str(raw or "").casefold())
        return re.sub(r"(?:玩法)?(?:系统|子系统|机制|规则)$", "", title)

    interface_title = re.compile(r"(?:页面|界面|弹窗|面板|信息板|按钮)$")
    allowed_status = {"CONFIRMED", "INFERRED", "PROPOSED", "CONFLICT"}

    for raw_system in value["systems"]:
        if not isinstance(raw_system, dict) or not str(raw_system.get("name") or "").strip():
            raise gameplay_analysis.GameplayAnalysisQualityError("gameplay system name is required")
        system = {"name": str(raw_system["name"]).strip(), "reason": str(raw_system.get("reason") or "").strip(), "subsystems": []}
        system_key = title_key(system["name"])
        if not system_key or system_key in seen_systems:
            raise gameplay_analysis.GameplayAnalysisQualityError("duplicate gameplay system title")
        seen_systems.add(system_key)
        raw_subsystems = raw_system.get("subsystems") or []
        if not isinstance(raw_subsystems, list) or not raw_subsystems:
            raise gameplay_analysis.GameplayAnalysisQualityError("gameplay system requires subsystems")
        for raw_subsystem in raw_subsystems:
            if not isinstance(raw_subsystem, dict) or not str(raw_subsystem.get("name") or "").strip():
                raise gameplay_analysis.GameplayAnalysisQualityError("gameplay subsystem name is required")
            subsystem = {"name": str(raw_subsystem["name"]).strip(), "mechanisms": []}
            subsystem_key = title_key(subsystem["name"])
            if not subsystem_key or subsystem_key == system_key:
                raise gameplay_analysis.GameplayAnalysisQualityError("hierarchy titles must be distinct")
            raw_mechanisms = raw_subsystem.get("mechanisms") or []
            if not isinstance(raw_mechanisms, list) or not raw_mechanisms:
                raise gameplay_analysis.GameplayAnalysisQualityError("gameplay subsystem requires mechanisms")
            for raw_mechanism in raw_mechanisms:
                if not isinstance(raw_mechanism, dict) or not str(raw_mechanism.get("name") or "").strip():
                    raise gameplay_analysis.GameplayAnalysisQualityError("gameplay mechanism name is required")
                name = str(raw_mechanism["name"]).strip()
                key = title_key(name)
                if interface_title.search(name):
                    raise gameplay_analysis.GameplayAnalysisQualityError("interface title cannot be a gameplay mechanism")
                if not key or key in {system_key, subsystem_key} or key in seen_mechanisms:
                    raise gameplay_analysis.GameplayAnalysisQualityError("duplicate or invalid gameplay mechanism title")
                seen_mechanisms.add(key)
                status = str(raw_mechanism.get("knowledgeStatus") or "CONFIRMED").strip().upper()
                if status not in allowed_status:
                    status = "CONFIRMED"
                ids = list(dict.fromkeys(str(item) for item in (raw_mechanism.get("sourceFrameIds") or []) if item))
                if any(item not in known_frame_ids for item in ids):
                    raise gameplay_analysis.GameplayAnalysisQualityError("gameplay mechanism references unknown evidence frames")
                if status == "CONFIRMED" and not ids:
                    raise gameplay_analysis.GameplayAnalysisQualityError("confirmed gameplay mechanism requires evidence frames")
                subsystem["mechanisms"].append({
                    "name": name, "reason": str(raw_mechanism.get("reason") or "").strip(),
                    "sourceFrameIds": ids, "knowledgeStatus": status,
                })
            system["subsystems"].append(subsystem)
        result["systems"].append(system)
    return result


def install_provider_runtime_patch(app) -> None:
    global _installed
    if _installed:
        return
    _installed = True
    server.BUILT_IN_VISION_API_BASE = DEFAULT_API_BASE
    server.BUILT_IN_VISION_MODEL = DEFAULT_MODEL
    analysis_service._client = _runtime_client
    gameplay_analysis._client = _runtime_client
    gameplay_analysis._prompt = _master_detail_prompt
    gameplay_analysis._structure_prompt = _master_structure_prompt
    gameplay_analysis._cached_call = _master_cached_call
    gameplay_analysis._validate_structure_response = _master_validate_structure_response
    gameplay_analysis.sanitize_generated_optional_modules = sanitize_optional_modules_for_master_planner
    gameplay_analysis.sanitize_generated_semantics = sanitize_semantics_for_master_planner

    @app.post("/api/config/validate")
    def validate_ai_config(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return validate_connection(ProviderConfig.from_mapping(payload))
        except ProviderError as exc:
            status = exc.status_code if exc.status_code in {400, 401, 403, 429, 502, 503, 504} else 400
            if exc.kind in {"provider", "network"}:
                status = exc.status_code or 503
            elif exc.kind == "timeout":
                status = 504
            raise HTTPException(status_code=status, detail=exc.to_dict()) from exc
