from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .planning_gameplay_sync import sync_planning_gameplay_insights
from .atomic_fact_normalizer import normalize_claims

from .analysis_service import _call, _client
from .gameplay_review_model import MECHANISM_SCHEMAS, _CLAIM_SOURCE_TYPES, build_gameplay_review_model, normalize_gameplay_structure, validate_gameplay_review_model
from .gameplay_directory import synthesize_directory
from .gameplay_rule_copy import enrich_gameplay_draft, sanitize_generated_optional_modules, sanitize_generated_semantics
from .lead_planner_gate import lead_planner_output_audit, lead_planner_preflight
from .gameplay_generation_quality import (
    GameplayGenerationQualityError,
    evidence_fingerprint, load_cached_response, preserve_planner_decisions,
    remove_cached_response, require_quality_floor, save_cached_response,
)
from .gameplay_quality_reference import find_quality_reference
from .feishu_prd_depth_contract import PROMPT_CONTRACT


class GameplayAnalysisQualityError(ValueError):
    pass


_DRAFT_FIELDS = (
    "title", "mechanismType", "sourceFrameIds", "claims", "mechanism", "parameters",
    "dependencies", "acceptanceCases", "unknowns", "confidence", "attributeSections",
)
_LIST_FIELDS = ("claims", "dependencies", "acceptanceCases", "unknowns", "sourceFrameIds", "attributeSections")
_PLACEHOLDER_WORDS = ("pending", "unknown", "timeout", "failure", "failed", "未知", "待确认", "超时", "失败")


_STRUCTURE_PROMPT_VERSION = "gameplay-structure-v5-project-isolated-hierarchy"
_DETAIL_PROMPT_VERSION = "gameplay-detail-v6-evidence-grounded-review"
_STRUCTURE_HIERARCHY_POLICY = "gameplay.structure_hierarchy_quality"


def _require_generation_quality(
    model: dict[str, Any],
    phase: str,
    references: list[dict[str, Any]] | None = None,
    *,
    allow_pending_decisions: bool = False,
) -> None:
    try:
        require_quality_floor(
            model, phase, references=references,
            allow_pending_decisions=allow_pending_decisions,
        )
    except GameplayGenerationQualityError as exc:
        raise GameplayAnalysisQualityError(str(exc)) from exc


def _cached_call(job: dict, job_dir: Path, runtime_config: dict, phase: str, prompt: str, images: list, max_tokens: int, structure: Any = None) -> tuple[Any, str, bool]:
    model_name = str(runtime_config.get("model") or "qwen3.6-plus")
    prompt_version = _STRUCTURE_PROMPT_VERSION if phase == "structure" else _DETAIL_PROMPT_VERSION
    fingerprint = evidence_fingerprint(job, job_dir, model=model_name, prompt_version=prompt_version, structure=structure)
    cache_root = job_dir.parent / ".gameplay-generation-cache"
    cached = load_cached_response(cache_root, fingerprint)
    if cached is not None:
        return cached, fingerprint, True
    client = _client(runtime_config)
    if client is None:
        raise GameplayAnalysisQualityError("gameplay vision model is unavailable")
    response = _call(client, model_name, prompt, images, max_tokens=max_tokens)
    return response, fingerprint, False


def _prompt(frame_ids: list[str]) -> str:
    mechanism_types = ", ".join(MECHANISM_SCHEMAS)
    return PROMPT_CONTRACT + "\n\n" + """Analyze these ordered gameplay screenshots. Return JSON only: a list of chapter drafts.
Each draft must contain title, mechanismType, sourceFrameIds, claims, mechanism, parameters,
dependencies, acceptanceCases, unknowns, decisionCards, and confidence. Each claim must include sourceType and
sourceFrameIds. Source frame IDs must come only from the supplied screenshots and sourceType must
be material, reference_document, inference, planner, or pending. Do not invent evidence; use
pending only for uncertainty. Group screenshots that evidence the same gameplay mechanism.
Write every planner-facing title, claim, question, acceptance case, mechanism name, and parameter label/value in concise Simplified Chinese. Keep only the required JSON keys and controlled enum values in English.
mechanismType must be exactly one of these internal values; choose the closest match and never create a new value: """ + mechanism_types + """.
mechanism and parameters must be JSON objects, never text or arrays. Use mechanism={"type": mechanismType, "description": "简明规则"}. Use parameters={"参数名": {"value": "画面可见值或待确认", "type": "text or number", "unit": "单位或待确认", "range": "范围或待确认", "source": "对应截图ID"}}. claims must be an array of objects with text, sourceType and sourceFrameIds.
mechanism must describe the actual gameplay rather than the screen layout. Fill every rule field that the screenshots support for the selected mechanismType: how play starts, what state already exists, what the system does in order, what the player can choose, what changes after each choice, what persists or resets, and what happens at limits or invalid conditions. Do not use those phrases as planner-facing headings; store them in the mechanismType fields.
claims store visible evidence such as pages, buttons, colors, effects and displayed values. acceptanceCases must be an array of objects with scene, action and expected in Chinese. dependencies must be an empty array; cross-chapter relationships are confirmed after the directory is generated.
Only when at least two reasonable interpretations remain and the supplied evidence cannot select one, create a decisionCards item instead of showing a bare unknown. Each card must contain id (GDC-###), question, selectionMode (single or multiple), at least two executable options with id and label, one recommended option with a short evidence-based reason when possible, allowCustom=true, evidence with frameId/label or reference, impacts naming every downstream artifact that changes, and status="pending". Keep unknowns only as an internal compatibility list of the same card questions. Do not create a card when the evidence already determines the answer.
The output depth must match a production game-design specification, not a screenshot caption. For every mechanism, separate visible evidence from the planner rule. Explain the player's goal, the normal rule sequence, state changes, results, reset behavior and evidenced boundary cases in mechanism fields and planner-facing claims.
When the mechanism contains values, attributes, costs, probabilities, levels, durations, damage, health, rewards or any calculation input, parameterSchema is REQUIRED and must be a JSON array. Each row must contain category, name, plannerMeaning, type, unit, defaultValue, range, configurationSource, deliverySource, rounding, evidenceLevel, and sourceFrameIds or referenceSource. category is a material-specific planner grouping; derive it from the current game rather than applying a fixed template. deliverySource explains where the value comes from or is increased, while configurationSource identifies the implementation table or document. Use "待策划确认" only for a specific unsupported property; never replace the entire row with a generic unknown.
For every evidenced core entity with attributes, attributeSections is also REQUIRED. Set attributeHeading to the plain object name, such as “载具”, “武器” or “怪物”. attributeSections must be a JSON array of {"heading":"该对象下的业务分组，例如承伤与武器换算、等级与栏位状态","items":["属性名：说明属性含义、所属对象、参与的计算或判断、读取/写入或生效时机，以及已知边界"]}. Do not repeat the object name in every subgroup heading. Group by real business responsibility and content volume, not universal headings such as “基础属性” or “规则与边界”. The prose must add behavioral meaning and must not mechanically serialize parameterSchema rows. A complete parameterSchema never substitutes for attributeSections.
When an authoritative reference document or configuration table supplies table and field names, place business-name-to-field mappings beside the owning behavior. If authority is absent, do not invent an official table or field. Keep values, units and ranges in the parameter table after the prose explanation.
When screenshots show multiple weapons, skills, upgrades, enemies, rewards or other configurable content, enumerate every visibly distinct item in a dedicated content-catalog mechanism. Record each visible name, type, effect, displayed value, rarity/state and evidence frame. Do not collapse a visible weapon list into a generic sentence such as “存在多种武器”.
When the mechanism performs a calculation, formulae is REQUIRED. Each formula must contain name, expression, calculationOrder, rounding, evidenceLevel, sourceFrameIds or referenceSource, plus variables. Every variable must contain name, plannerMeaning, type, unit, evidenceLevel and sourceFrameIds or referenceSource. If evidence proves the inputs but not the exact relationship, place the proposed relationship in unknowns instead of inventing a formula.
When all values used by a formula are evidenced, workedExamples is REQUIRED and must show substituted values, calculation steps and result. When a table or document source is visible or provided, configurationSources is REQUIRED and must identify the planner-facing table/source name and field. Omit only modules that genuinely do not apply.
Each acceptance case must be concrete enough to reproduce and must cover the normal result plus every evidenced failure, limit, repeated operation, invalid target, reset or exit/re-entry case. Every parameter row, formula, and formula variable must include evidenceLevel plus sourceFrameIds or referenceSource. Never invent a formula from interface layout alone.
Before returning JSON, silently review the result as a lead game designer: reject screenshot-caption prose in gameplay rules, interaction terms in gameplay summaries, unsupported formulas, attributes present only in tables, generic chapter copy, fixed-template systems, audit/process phrases such as “素材只证明” or “仍由决策卡确认”, internal English labels, duplicated chapters, and mismatched evidence. Revise the draft until each planner-facing section is directly usable by a game designer.
Supplied frame IDs: """ + json.dumps(frame_ids)


def _structure_prompt(frame_ids: list[str]) -> str:
    return PROMPT_CONTRACT + "\n\n" + """分析这些按顺序排列的玩法截图，只返回一个 JSON 对象，格式为：
{"systems":[{"name":"玩法系统名称","reason":"划分依据","subsystems":[{"name":"子系统名称","mechanisms":[{"name":"具体机制名称","reason":"画面依据","sourceFrameIds":["F0001"]}]}]}]}。
先识别素材实际存在的对象、目标、操作、状态、资源、空间关系和结果，再据此建立系统层级。颗粒度必须达到可独立编写规则的机制层：例如战斗素材不能只写“核心战斗”，还要在证据支持时拆出攻击方式、攻击目标与范围、受击与死亡、首领出现条件、战斗阶段与反馈、战斗属性、伤害计算、伤害数字表现、进度与时间、胜负与结算；但不得机械照抄这些示例。
如果一个机制拥有独立的输入字段、计算顺序、配置来源、触发条件、状态变化或边界处理，就必须成为独立机制。系统、子系统和机制三层不得互相重复命名，不得用“战斗过程”“玩法信息”等宽泛标题代替可审核规则。
机制标题必须描述可独立审核的规则责任，不能直接使用“页面、界面、弹窗、面板、显示、提示、按钮、状态”等 UI 或展示名称。相同机制只能出现一次；同义条目必须合并。每个子系统最多包含 8 个机制，超过时必须按真实业务责任拆分为多个子系统，不能把整个项目压成一个大组。
素材中只要出现多个可区分的武器、技能、强化、敌人或奖励，就必须增加对应的内容清单机制，并在后续详情阶段逐项拆解画面可见的名称、类别、效果和数值；不得只写“武器系统”或“存在多种武器”。
不得套用固定游戏目录，不得因为知识库中存在武器、敌人、合成、经营或其他范例就添加素材未展示的系统。
允许识别从未预定义的新玩法或混合玩法；名称必须使用简明的简体中文。每个具体机制必须引用给定截图 ID。
本阶段只建立目录，不生成参数、公式、验收用例或完整规则正文。
返回前必须以主策视角静默自检：系统边界来自当前素材；机制名称可直接用于策划目录；画面位置、按钮、弹窗、颜色、特效和截图数字只作为依据，不能充当玩法说明；不得出现固定模板、内部英文、重复机制或无证据章节。不合格时先修正再返回 JSON。
给定截图 ID：""" + json.dumps(frame_ids, ensure_ascii=False)


def _validate_structure_response(value: Any, known_frame_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("systems"), list) or not value["systems"]:
        raise GameplayAnalysisQualityError("gameplay structure response must contain systems")
    result = {"systems": []}
    seen_systems: set[str] = set()
    seen_mechanisms: set[str] = set()

    def title_key(value: Any) -> str:
        title = re.sub(r"[\s\-—_·:：/（）()]+", "", str(value or "").casefold())
        return re.sub(r"(?:玩法)?(?:系统|子系统|机制|规则)$", "", title)

    interface_title = re.compile(r"(?:页面|界面|弹窗|面板|信息板|显示|展示|提示|图标|按钮|状态)$")
    for raw_system in value["systems"]:
        if not isinstance(raw_system, dict) or not str(raw_system.get("name") or "").strip():
            raise GameplayAnalysisQualityError("gameplay system name is required")
        system = {"name": str(raw_system["name"]).strip(), "reason": str(raw_system.get("reason") or "").strip(), "subsystems": []}
        system_key = title_key(system["name"])
        if not system_key or system_key in seen_systems:
            raise GameplayAnalysisQualityError("duplicate gameplay system title")
        seen_systems.add(system_key)
        for raw_subsystem in raw_system.get("subsystems") or []:
            if not isinstance(raw_subsystem, dict) or not str(raw_subsystem.get("name") or "").strip():
                raise GameplayAnalysisQualityError("gameplay subsystem name is required")
            subsystem = {"name": str(raw_subsystem["name"]).strip(), "mechanisms": []}
            subsystem_key = title_key(subsystem["name"])
            if not subsystem_key or subsystem_key == system_key:
                raise GameplayAnalysisQualityError("hierarchy titles must be distinct")
            raw_mechanisms = raw_subsystem.get("mechanisms") or []
            if len(raw_mechanisms) > 8:
                raise GameplayAnalysisQualityError("overloaded subsystem must be split into coherent rule groups")
            for raw_mechanism in raw_mechanisms:
                ids = list(dict.fromkeys(raw_mechanism.get("sourceFrameIds") or [])) if isinstance(raw_mechanism, dict) else []
                if (not isinstance(raw_mechanism, dict) or not str(raw_mechanism.get("name") or "").strip()
                        or not ids or any(item not in known_frame_ids for item in ids)):
                    raise GameplayAnalysisQualityError("gameplay mechanism requires a name and known evidence frames")
                mechanism_name = str(raw_mechanism["name"]).strip()
                mechanism_key = title_key(mechanism_name)
                if interface_title.search(mechanism_name):
                    raise GameplayAnalysisQualityError("interface title cannot be a gameplay mechanism")
                if not mechanism_key or mechanism_key in {system_key, subsystem_key}:
                    raise GameplayAnalysisQualityError("hierarchy titles must be distinct")
                if mechanism_key in seen_mechanisms:
                    raise GameplayAnalysisQualityError("duplicate mechanism title")
                seen_mechanisms.add(mechanism_key)
                subsystem["mechanisms"].append({
                    "name": mechanism_name,
                    "reason": str(raw_mechanism.get("reason") or "").strip(),
                    "sourceFrameIds": ids,
                })
            if subsystem["mechanisms"]:
                system["subsystems"].append(subsystem)
        if system["subsystems"]:
            result["systems"].append(system)
    if not result["systems"]:
        raise GameplayAnalysisQualityError("gameplay structure produced zero evidenced mechanisms")
    return result


def _generate_gameplay_structure_once(job: dict, job_dir: Path, runtime_config: dict, progress=lambda *_: None) -> dict:
    if lead_errors := lead_planner_preflight(job, "structure"):
        raise GameplayAnalysisQualityError("lead planner preflight failed: " + "; ".join(lead_errors))
    frames = [item for item in job.get("frames") or [] if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if not frames:
        raise GameplayAnalysisQualityError("gameplay structure requires evidence frames")
    frame_ids = [item["id"] for item in frames]
    images = [(f"frame={item['id']} index={index}", job_dir / "frames" / Path(str(item.get("imageUrl") or "")).name) for index, item in enumerate(frames, 1)]
    progress(10, "正在识别玩法结构")
    quality_feedback = str(runtime_config.get("_qualityFeedback") or "")
    prompt = _structure_prompt(frame_ids)
    if quality_feedback:
        prompt += "\n上一次候选未通过主策质量门禁。只修复以下问题，不得降低已有信息：" + quality_feedback
    response, cache_key, cache_hit = _cached_call(
        job, job_dir, runtime_config, "structure", prompt, images, 4000,
        structure={"qualityFeedback": quality_feedback},
    )
    structure = _validate_structure_response(response, set(frame_ids))
    drafts = []
    for system in structure["systems"]:
        for subsystem in system["subsystems"]:
            for mechanism in subsystem["mechanisms"]:
                reason = mechanism["reason"] or f"素材展示了{mechanism['name']}"
                drafts.append({
                    "title": mechanism["name"], "systemName": system["name"], "subsystemName": subsystem["name"],
                    "mechanismType": "custom", "sourceFrameIds": mechanism["sourceFrameIds"],
                    "claims": [{"text": reason, "sourceType": "material", "sourceFrameIds": mechanism["sourceFrameIds"]}],
                    "mechanism": {"type": "custom", "description": reason}, "parameters": {}, "dependencies": [],
                    "acceptanceCases": [], "unknowns": [], "confidence": "structure-only",
                })
    model = build_gameplay_review_model(job, drafts, directory_proposal=synthesize_directory(drafts))
    model.update(normalize_gameplay_structure(model))
    model["reviewState"]["status"] = "system_directory_review"
    model["reviewState"]["structurePhase"] = "systems"
    model["reviewState"]["depthContractVersion"] = 2
    if lead_errors := lead_planner_output_audit(model, "structure"):
        raise GameplayAnalysisQualityError("lead planner output audit failed: " + "; ".join(lead_errors[:20]))
    _require_generation_quality(model, "structure")
    if not cache_hit:
        save_cached_response(job_dir.parent / ".gameplay-generation-cache", cache_key, response)
    progress(100, "玩法结构已生成")
    return sync_planning_gameplay_insights(job, model)


def generate_gameplay_structure(job: dict, job_dir: Path, runtime_config: dict, progress=lambda *_: None) -> dict:
    try:
        return _generate_gameplay_structure_once(job, job_dir, runtime_config, progress)
    except GameplayAnalysisQualityError as exc:
        if runtime_config.get("_qualityRetry"):
            raise
        progress(55, "首次结果未通过主策检查，正在自动修正（1/1）")
        retry_config = dict(runtime_config, _qualityRetry=True, _qualityFeedback=str(exc))
        return _generate_gameplay_structure_once(job, job_dir, retry_config, progress)


def _generate_gameplay_details_once(
    job: dict,
    structure_model: dict,
    job_dir: Path,
    runtime_config: dict,
    progress=lambda *_: None,
) -> dict:
    """Fill a planner-confirmed structure without allowing the model to reshape it."""
    if lead_errors := lead_planner_preflight(job, "details", structure_model):
        raise GameplayAnalysisQualityError("lead planner preflight failed: " + "; ".join(lead_errors))
    chapters = [item for item in structure_model.get("chapters") or [] if isinstance(item, dict)]
    known_frames = {
        item.get("id") for item in job.get("frames") or []
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if not chapters:
        raise GameplayAnalysisQualityError("confirmed gameplay structure has no mechanisms")
    candidates: list[dict[str, Any]] = []
    quality_references: list[dict[str, Any]] = []
    cache_root = job_dir.parent / ".gameplay-generation-cache"
    batch_cache_keys: list[str] = []
    quality_retry = bool(runtime_config.get("_qualityRetry"))
    progress(5, "正在进行第二轮语义修复" if quality_retry else "正在按确认目录补全玩法规则")
    for index, chapter in enumerate(chapters, 1):
        frame_ids = [item for item in chapter.get("sourceFrameIds") or [] if item in known_frames]
        if not frame_ids:
            raise GameplayAnalysisQualityError("confirmed gameplay mechanism has no valid evidence frames")
        images = [
            (f"frame={frame_id}", job_dir / "frames" / f"{frame_id}.jpg")
            for frame_id in frame_ids
        ]
        constraint = (
            "\n本次只补全一个已由策划确认的具体机制。不得修改机制名称、所属系统、所属子系统，"
            "不得新增或删除章节。确认结构："
            + json.dumps({
                "system": chapter.get("systemName"),
                "subsystem": chapter.get("subsystemName"),
                "mechanism": chapter.get("scope"),
            }, ensure_ascii=False)
        )
        constraint += (
            "\n不得让所有章节机械套用同一组模块。简单机制使用连贯自然正文，避免为了形式拆出只有一句话的多层标题；"
            "只有素材或参考文档确实支持复杂规则时，才展开参数、公式、分支、生命周期和验收。"
            "章节语言应像主策写给执行团队的策划案，不得逐图复述，不得重复同一句结论。"
            "画面可见数字只能写成当前观测值，不得由单帧反推公式、成长曲线、配置表、上限、失败分支或服务器实现。"
            "验收用例必须能逐项回溯到当前素材或参考文档；缺少操作、反馈、结果或出口时，使用决策卡，不得自行补齐。"
        )
        reference = find_quality_reference(job_dir.parent, chapter)
        quality_references.append(reference)
        if reference:
            constraint += (
                "\n参考已通过主策审核的相近章节，只对齐信息密度和模块选择，不得复制其中的玩法事实。"
                "结构密度参考：" + json.dumps(reference, ensure_ascii=False)
            )
        quality_feedback = str(runtime_config.get("_qualityFeedback") or "")
        if quality_feedback:
            constraint += "\n上一次候选未通过主策质量门禁。只修复以下问题，不得改动已确认结构：" + quality_feedback
        # Keep project and approved-model identity in every per-chapter cache
        # key. Identical screenshots in different projects must never share a
        # response.
        chapter_job = {
            "id": job.get("id"),
            "interactionModel": copy.deepcopy(job.get("interactionModel")),
            "reviewModel": copy.deepcopy(job.get("reviewModel")),
            "gameplayReviewModel": {"revision": structure_model.get("revision")},
            "frames": [item for item in job.get("frames") or [] if item.get("id") in frame_ids],
        }
        response, cache_key, cache_hit = _cached_call(
            chapter_job, job_dir, runtime_config, "details", _prompt(frame_ids) + constraint,
            images, 5000, structure={
                "system": chapter.get("systemName"), "subsystem": chapter.get("subsystemName"),
                "mechanism": chapter.get("scope"),
                "qualityReference": reference,
                "qualityFeedback": quality_feedback,
            },
        )
        if not isinstance(response, list) or len(response) != 1:
            raise GameplayAnalysisQualityError("gameplay detail response must contain exactly one mechanism")
        draft = _validate_draft(response[0], set(frame_ids))
        # The confirmed planner structure wins over any title emitted by the model.
        draft["title"] = chapter.get("scope")
        draft["systemName"] = chapter.get("systemName")
        draft["subsystemName"] = chapter.get("subsystemName")
        draft, optional_warnings = sanitize_generated_optional_modules(draft)
        draft = sanitize_generated_semantics(draft)
        if optional_warnings:
            progress(
                round((index - 0.5) * 90 / len(chapters)),
                f"第{index}个玩法机制有无依据内容，已转为待确认并继续处理：{'；'.join(optional_warnings)}",
            )
        candidates.append(enrich_gameplay_draft(draft))
        # A syntactically valid, evidence-sanitized chapter is a safe restart
        # checkpoint. Network/system failure in a later chapter can resume
        # here instead of regenerating the whole project.
        if not cache_hit:
            save_cached_response(cache_root, cache_key, response)
        batch_cache_keys.append(cache_key)
        progress(
            round(index * 90 / len(chapters)),
            (f"语义修复 {index}/{len(chapters)} 个玩法机制" if quality_retry else f"已补全 {index}/{len(chapters)} 个玩法机制"),
        )

    try:
        generated = build_gameplay_review_model(job, candidates, directory_proposal=synthesize_directory(candidates))
        result = copy.deepcopy(structure_model)
        detail_by_position = generated.get("chapters") or []
        if len(detail_by_position) != len(chapters):
            raise GameplayAnalysisQualityError("gameplay detail generation changed the confirmed structure")
        preserved = {"id", "scope", "systemId", "systemName", "subsystemId", "subsystemName"}
        for target, detail in zip(result["chapters"], detail_by_position):
            identity = {key: copy.deepcopy(target.get(key)) for key in preserved if key in target}
            target.clear()
            target.update(copy.deepcopy(detail))
            target.update(identity)
            target["status"] = "pending"
            target["confirmation"] = {"confirmed": False}
        result["revision"] = int(structure_model.get("revision") or 0) + 1
        result["granularityAuditVersion"] = 5
        result["contentCoverage"] = {"items": [
            {
                "id": f"coverage-{chapter.get('id') or index + 1}",
                "label": str(chapter.get("scope") or chapter.get("id") or "当前机制"),
                "sourceIds": copy.deepcopy(chapter.get("sourceFrameIds") or []),
                "carrierIds": [str(chapter.get("id"))] if chapter.get("id") else [],
                "status": "covered",
            }
            for index, chapter in enumerate(result.get("chapters") or [])
            if isinstance(chapter, dict)
        ]}
        state = result.setdefault("reviewState", {})
        state.update({"status": "chapter_review", "structurePhase": "detailed", "previewRevision": None, "depthContractVersion": 2})
        result.update(normalize_gameplay_structure(result))
        errors = validate_gameplay_review_model(result)
        if errors:
            raise GameplayAnalysisQualityError("invalid detailed gameplay model: " + "; ".join(errors[:12]))
        result = preserve_planner_decisions(structure_model, result, refresh_confirmed_content=True)
        if lead_errors := lead_planner_output_audit(result, "details", allow_pending_decisions=True):
            raise GameplayAnalysisQualityError("lead planner output audit failed: " + "; ".join(lead_errors[:20]))
        # A grounded draft with explicit planner decisions is reviewable even when
        # screenshots do not prove every value or formula. Final delivery remains
        # blocked until those decision cards are resolved.
        _require_generation_quality(
            result, "details", references=quality_references,
            allow_pending_decisions=True,
        )
    except GameplayAnalysisQualityError:
        # A batch-level semantic rejection must not poison a later manual
        # retry. Transport/system errors occur before this block and keep all
        # already validated chapter checkpoints.
        for cache_key in batch_cache_keys:
            remove_cached_response(cache_root, cache_key)
        raise
    progress(100, "玩法规则已补全")
    return sync_planning_gameplay_insights(job, result)


def generate_gameplay_details(
    job: dict,
    structure_model: dict,
    job_dir: Path,
    runtime_config: dict,
    progress=lambda *_: None,
) -> dict:
    try:
        return _generate_gameplay_details_once(job, structure_model, job_dir, runtime_config, progress)
    except GameplayAnalysisQualityError as exc:
        if runtime_config.get("_qualityRetry"):
            raise
        progress(55, "首次结果未通过主策检查，正在自动修正（1/1）")
        retry_config = dict(runtime_config, _qualityRetry=True, _qualityFeedback=str(exc))
        return _generate_gameplay_details_once(job, structure_model, job_dir, retry_config, progress)


def _key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _union(left: list[Any], right: list[Any]) -> list[Any]:
    result = copy.deepcopy(left)
    seen = {_key(value) for value in result}
    for value in right:
        if _key(value) not in seen:
            result.append(copy.deepcopy(value))
            seen.add(_key(value))
    return result


def _placeholder_claim(claim: dict[str, Any]) -> bool:
    if claim.get("sourceType") == "pending":
        return True
    text = " ".join(str(value).casefold() for value in claim.values() if isinstance(value, (str, int, float)))
    return any(word in text for word in _PLACEHOLDER_WORDS)


def _parameter_metadata(value: Any, source: str = "视觉识别") -> dict[str, Any]:
    metadata = copy.deepcopy(value) if isinstance(value, dict) else {"value": value}
    metadata.setdefault("type", "text")
    metadata.setdefault("unit", "待确认")
    metadata.setdefault("range", "待确认")
    metadata.setdefault("source", source)
    return metadata


def _planner_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "description", "question", "case", "chapter", "name", "value"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
    return json.dumps(value, ensure_ascii=False, default=str)


def _normalize_draft_shapes(draft: Any, known_frame_ids: set[str] | None = None) -> Any:
    if not isinstance(draft, dict):
        return draft
    normalized = copy.deepcopy(draft)
    # Attribute prose is mandatory only when the evidenced mechanism owns
    # configurable attributes. Sparse mechanisms remain valid with no groups.
    normalized.setdefault("attributeSections", [])
    mechanism_type = normalized.get("mechanismType")
    raw_source_ids = normalized.get("sourceFrameIds")
    if isinstance(raw_source_ids, str):
        raw_source_ids = [raw_source_ids]
    source_ids = [
        item for item in raw_source_ids or []
        if isinstance(item, str) and (known_frame_ids is None or item in known_frame_ids)
    ]
    normalized["sourceFrameIds"] = source_ids
    source_label = ",".join(source_ids) or "视觉识别"
    mechanism = normalized.get("mechanism")
    if isinstance(mechanism, str):
        normalized["mechanism"] = {"type": mechanism_type, "description": mechanism}
    elif isinstance(mechanism, list):
        normalized["mechanism"] = {"type": mechanism_type, "details": mechanism}
    elif isinstance(mechanism, dict):
        normalized["mechanism"]["type"] = mechanism_type
    parameters = normalized.get("parameters")
    if isinstance(parameters, list):
        mapped: dict[str, Any] = {}
        for index, item in enumerate(parameters, 1):
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("label") or item.get("key") or f"补充说明{index}")
                metadata = {key: copy.deepcopy(value) for key, value in item.items() if key not in {"name", "label", "key"}}
                mapped[name] = _parameter_metadata(metadata or item, source_label)
            else:
                mapped[f"补充说明{index}"] = _parameter_metadata(item, source_label)
        normalized["parameters"] = mapped
    elif isinstance(parameters, str):
        normalized["parameters"] = {"补充说明": _parameter_metadata(parameters, source_label)}
    elif isinstance(parameters, dict):
        normalized["parameters"] = {
            str(name): _parameter_metadata(value, source_label) for name, value in parameters.items()
        }
    elif parameters is None:
        normalized["parameters"] = {}
    claims = normalized.get("claims")
    if isinstance(claims, list):
        normalized_claims = []
        for claim in claims:
            claim_source_ids = claim.get("sourceFrameIds", source_ids) if isinstance(claim, dict) else source_ids
            if isinstance(claim_source_ids, str):
                claim_source_ids = [claim_source_ids]
            claim_source_ids = [item for item in claim_source_ids if item in source_ids] or source_ids
            source_type = claim.get("sourceType", "material") if isinstance(claim, dict) else "material"
            if source_type not in _CLAIM_SOURCE_TYPES:
                source_type = "material"
            normalized_claims.append({
                "text": _planner_text(claim), "sourceType": source_type, "sourceFrameIds": claim_source_ids,
            })
        normalized["claims"] = normalized_claims
        normalized["atomicFacts"] = [
            fact.to_dict()
            for index, claim in enumerate(normalized_claims, 1)
            if claim.get("sourceType") not in {"planner", "pending"}
            for fact in normalize_claims({"id": f"ANALYSIS-{index:03d}", **claim}, str(normalized.get("title") or "待确认对象"))
        ]
    acceptance_cases = normalized.get("acceptanceCases")
    if isinstance(acceptance_cases, list):
        normalized["acceptanceCases"] = [
            {key: copy.deepcopy(value) for key, value in item.items() if key != "id"}
            if isinstance(item, dict) else {"description": _planner_text(item)}
            for item in acceptance_cases
        ]
    raw_unknowns = normalized.get("unknowns")
    if isinstance(raw_unknowns, str):
        raw_unknowns = [raw_unknowns]
    unknowns = [_planner_text(item) for item in raw_unknowns or []]
    dependencies = normalized.get("dependencies")
    if dependencies and not isinstance(dependencies, list):
        dependencies = [dependencies]
    if isinstance(dependencies, list) and dependencies:
        unknowns.extend(f"可能关联：{_planner_text(item)}（请在目录确认后核对）" for item in dependencies)
        normalized["dependencies"] = []
    normalized["unknowns"] = list(dict.fromkeys(item for item in unknowns if item))
    raw_cards = normalized.get("decisionCards")
    cards = []
    for index, card in enumerate(raw_cards if isinstance(raw_cards, list) else [], 1):
        if not isinstance(card, dict) or not str(card.get("question") or "").strip():
            continue
        options = [copy.deepcopy(option) for option in card.get("options") or [] if isinstance(option, dict) and str(option.get("id") or "").strip() and str(option.get("label") or "").strip()]
        if len(options) < 2:
            continue
        cards.append({
            "id": str(card.get("id") or f"GDC-{index:03d}"), "question": str(card["question"]).strip(),
            "selectionMode": card.get("selectionMode") if card.get("selectionMode") in {"single", "multiple"} else "single",
            "options": options, "allowCustom": card.get("allowCustom") is not False,
            "evidence": copy.deepcopy(card.get("evidence") or []), "impacts": copy.deepcopy(card.get("impacts") or ["玩法正文", "最终文档"]),
            "status": "pending",
        })
    normalized["decisionCards"] = cards
    return normalized


def _validate_draft(draft: Any, known_frame_ids: set[str]) -> dict[str, Any]:
    draft = _normalize_draft_shapes(draft, known_frame_ids)
    if not isinstance(draft, dict):
        raise GameplayAnalysisQualityError("gameplay chapter must be an object")
    missing = [field for field in _DRAFT_FIELDS if field not in draft]
    if missing:
        raise GameplayAnalysisQualityError(f"gameplay chapter missing fields: {', '.join(missing)}")
    if not isinstance(draft["title"], str) or not draft["title"].strip():
        raise GameplayAnalysisQualityError("gameplay chapter title must be a non-empty string")
    if draft["mechanismType"] not in MECHANISM_SCHEMAS:
        raise GameplayAnalysisQualityError(
            f"gameplay chapter has an invalid mechanism type: {draft['mechanismType']!r}"
        )
    if not isinstance(draft["mechanism"], dict) or not isinstance(draft["parameters"], dict):
        raise GameplayAnalysisQualityError("gameplay chapter mechanism and parameters must be objects")
    if draft["mechanism"].get("type") not in (None, draft["mechanismType"]):
        raise GameplayAnalysisQualityError("gameplay chapter mechanism type does not match")
    if not isinstance(draft["confidence"], (str, int, float)):
        raise GameplayAnalysisQualityError("gameplay chapter confidence has an invalid type")
    for field in _LIST_FIELDS:
        if not isinstance(draft[field], list):
            raise GameplayAnalysisQualityError(f"gameplay chapter {field} must be a list")
    source_ids = draft["sourceFrameIds"]
    if not source_ids or any(not isinstance(frame_id, str) or frame_id not in known_frame_ids for frame_id in source_ids):
        raise GameplayAnalysisQualityError("gameplay chapter cites an unknown frame")
    if not draft["claims"]:
        raise GameplayAnalysisQualityError("gameplay chapter must include claims")
    for claim in draft["claims"]:
        if not isinstance(claim, dict) or claim.get("sourceType") not in _CLAIM_SOURCE_TYPES:
            raise GameplayAnalysisQualityError("gameplay claim has an invalid source type")
        claim_ids = claim.get("sourceFrameIds")
        if not isinstance(claim_ids, list) or not claim_ids or any(not isinstance(frame_id, str) or frame_id not in known_frame_ids for frame_id in claim_ids):
            raise GameplayAnalysisQualityError("gameplay claim cites an unknown frame")
    if all(_placeholder_claim(claim) for claim in draft["claims"]):
        raise GameplayAnalysisQualityError("gameplay chapter contains placeholder-only claims")
    return copy.deepcopy(draft)


def _merge_drafts(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for draft in drafts:
        key = (str(draft["mechanismType"]).casefold().strip(), " ".join(draft["title"].casefold().split()))
        existing = merged.get(key)
        if existing is None:
            merged[key] = draft
            continue
        for field in _LIST_FIELDS:
            existing[field] = _union(existing[field], draft[field])
        existing["mechanism"].update(draft["mechanism"])
        existing["parameters"].update(draft["parameters"])
    return list(merged.values())


def generate_gameplay_chapters(job: dict, job_dir: Path, runtime_config: dict, progress) -> dict:
    frames = [frame for frame in job.get("frames") or [] if isinstance(frame, dict) and isinstance(frame.get("id"), str)]
    if not frames:
        raise GameplayAnalysisQualityError("gameplay review requires evidence frames")
    client = _client(runtime_config)
    if client is None:
        raise GameplayAnalysisQualityError("gameplay vision model is unavailable")
    model_name = str(runtime_config.get("model") or "qwen3.6-plus")
    drafts: list[dict[str, Any]] = []
    progress(5, "Preparing gameplay evidence")
    batch_size = 3
    for start in range(0, len(frames), batch_size):
        batch = frames[start:start + batch_size]
        frame_ids = [frame["id"] for frame in batch]
        images = [
            (f"frame={frame['id']} index={index}", job_dir / "frames" / Path(str(frame.get("imageUrl") or "")).name)
            for index, frame in enumerate(batch, start + 1)
        ]
        try:
            response = _call(client, model_name, _prompt(frame_ids), images, max_tokens=5000)
        except json.JSONDecodeError as exc:
            raise GameplayAnalysisQualityError("gameplay model returned incomplete JSON") from exc
        except Exception as exc:
            raise GameplayAnalysisQualityError("gameplay model request failed") from exc
        if not isinstance(response, list):
            raise GameplayAnalysisQualityError("gameplay model response must be a JSON list")
        drafts.extend(_validate_draft(draft, set(frame_ids)) for draft in response)
        progress(round((start + len(batch)) * 100 / len(frames)), f"Generated gameplay evidence for {start + len(batch)}/{len(frames)} frames")
    candidates = [enrich_gameplay_draft(item) for item in _merge_drafts(drafts)]
    if not candidates:
        raise GameplayAnalysisQualityError("gameplay model produced zero valid chapters")
    gameplay_model = build_gameplay_review_model(job, candidates, directory_proposal=synthesize_directory(candidates))
    errors = validate_gameplay_review_model(gameplay_model)
    if errors or not gameplay_model["chapters"]:
        detail = "; ".join(errors[:12]) if errors else "zero chapters"
        raise GameplayAnalysisQualityError(f"invalid gameplay review model: {detail}")
    return sync_planning_gameplay_insights(job, gameplay_model)
