from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .gameplay_directory import directory_errors, ensure_directory, legacy_directory
from .chapter_classifier import classify_text
from .gameplay_copy import refresh_directory_copy
from .gameplay_rule_copy import migrate_gameplay_rule_copy, optional_module_errors, planner_sections
from .gameplay_lifecycle import gameplay_model_has_reviewable_detail
from .rule_normalizer import build_approved_data_v2, build_rule_intelligence_v1
from .lead_planner_gate import lead_planner_output_audit
from .gameplay_flow_semantics import route_structured_rules


MECHANISM_SCHEMAS = {
    "custom": ("participants", "goal", "inputs", "stateChanges", "rules", "data", "feedback", "dependencies", "acceptance"),
    "core_loop": ("playerGoal", "trigger", "phaseOrder", "completion", "failure", "reset"),
    "spatial_drag": ("objects", "legalRegion", "matchRule", "replacement", "failureReturn", "bounds", "saveCondition"),
    "entity_behavior": ("spawn", "targeting", "movement", "attack", "cooldown", "hit", "death"),
    "formula": ("inputs", "units", "ranges", "formula", "stackOrder", "rounding", "example", "configSource"),
    "progression": ("scope", "unlock", "cost", "levels", "cap", "reset", "effect"),
    "random_pool": ("eligibility", "exclusions", "drawOrder", "replacementRule", "weightFormula", "emptyResult", "temporaryResult", "confirm", "reroll", "cost", "reset"),
    "economy_reward": ("sources", "costs", "settlement", "accumulation", "failure", "lifecycle"),
    "level_wave": ("entry", "phaseOrder", "distanceOrTime", "spawns", "multipliers", "movement", "experience", "reward", "completion"),
    "buff_chain": ("target", "trigger", "parameters", "calculation", "stacks", "duration", "replacement", "removal"),
    "settlement": ("win", "failure", "rewardBoundary", "statistics", "messages", "exit"),
    "external_entry": ("unlock", "eligibility", "entryCost", "costTiming", "failureRefund", "sweep", "rewards"),
    "statistics_feedback": ("metric", "aggregation", "refresh", "sorting", "reset", "displayStates"),
}

_CLAIM_SOURCE_TYPES = {"material", "reference_document", "inference", "planner", "pending"}
_CHAPTER_FIELDS = ("scope", "claims", "mechanism", "parameters", "dependencies", "acceptanceCases", "unknowns", "decisionCards", "sourceFrameIds", "status", "confirmation")
_METADATA_FIELDS = ("type", "unit", "range", "source")


def _structure_name(value: Any, fallback: str) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    return name or fallback


def normalize_gameplay_structure(model: dict[str, Any]) -> dict[str, Any]:
    """Build an open hierarchy from the names already present in the material model."""
    result = deepcopy(model)
    systems: list[dict[str, Any]] = []
    system_by_name: dict[str, dict[str, Any]] = {}
    subsystem_count = 0
    for chapter in result.get("chapters") or []:
        if not isinstance(chapter, dict) or not isinstance(chapter.get("id"), str):
            continue
        system_name = _structure_name(chapter.get("systemName") or chapter.get("group"), "其他玩法")
        subsystem_name = _structure_name(chapter.get("subsystemName"), system_name)
        system = system_by_name.get(system_name)
        if system is None:
            system = {"id": f"GSY-{len(systems) + 1:03d}", "name": system_name, "subsystems": []}
            system_by_name[system_name] = system
            systems.append(system)
        subsystem = next((item for item in system["subsystems"] if item["name"] == subsystem_name), None)
        if subsystem is None:
            subsystem_count += 1
            subsystem = {"id": f"GSS-{subsystem_count:03d}", "name": subsystem_name, "chapterIds": []}
            system["subsystems"].append(subsystem)
        subsystem["chapterIds"].append(chapter["id"])
        chapter["systemId"] = system["id"]
        chapter["subsystemId"] = subsystem["id"]
    result["systems"] = systems
    return result


def required_parameter_fields(mechanism_type: str) -> tuple[str, ...]:
    return MECHANISM_SCHEMAS.get(mechanism_type, ())


def configured_parameter_items(chapter: dict[str, Any]) -> list[tuple[str, Any]]:
    mechanism_fields = {field for fields in MECHANISM_SCHEMAS.values() for field in fields}
    return [(name, value) for name, value in (chapter.get("parameters") or {}).items() if name not in mechanism_fields]


def _frames(job: dict[str, Any]) -> set[str]:
    return {item.get("id") for item in job.get("frames") or [] if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _evidence_anchor(index: int, frame_id: str, frames: dict[str, dict[str, Any]]) -> dict[str, Any]:
    frame = frames.get(frame_id, {})
    anchor: dict[str, Any] = {"id": f"GEV-{index:03d}", "frameId": frame_id}
    if isinstance(frame.get("imageUrl"), str) and frame["imageUrl"].strip():
        anchor["imageUrl"] = frame["imageUrl"]
    source: dict[str, Any] = {}
    if isinstance(frame.get("sourceName"), str) and frame["sourceName"].strip():
        source["name"] = frame["sourceName"]
    if isinstance(frame.get("timestamp"), (int, float)) and not isinstance(frame.get("timestamp"), bool):
        source["timestamp"] = frame["timestamp"]
    if type(frame.get("sequenceIndex")) is int:
        source["sequenceIndex"] = frame["sequenceIndex"]
    if source:
        anchor["source"] = source
    structure = frame.get("structure") if isinstance(frame.get("structure"), dict) else {}
    width, height = structure.get("width"), structure.get("height")
    if isinstance(width, (int, float)) and width > 0 and isinstance(height, (int, float)) and height > 0:
        anchor["width"], anchor["height"] = width, height
    return anchor


def _evidence_caption(chapter: dict[str, Any], frame_id: str) -> str:
    claims = chapter.get("evidenceClaims") or chapter.get("claims") or []
    for claim in claims:
        if not isinstance(claim, dict) or frame_id not in (claim.get("sourceFrameIds") or []):
            continue
        text = str(claim.get("text") or "").strip()
        if text:
            text = re.sub(r"\bBoss\b", "首领", text, flags=re.I)
            text = re.sub(r"\b(?:SCN|EVT|GEV)-\d+\b", "", text).strip()
            return f"支持判断：{text}"
    summary = str((chapter.get("plannerSections") or {}).get("summary") or chapter.get("plannerSummary") or chapter.get("scope") or "当前玩法规则").strip()
    return f"支持判断：{summary}"


def refresh_inline_evidence(model: dict[str, Any]) -> dict[str, Any]:
    anchors = {item.get("frameId"): item for item in model.get("evidenceAnchors") or [] if isinstance(item, dict)}
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        items, seen = [], set()
        for frame_id in chapter.get("sourceFrameIds") or []:
            if not isinstance(frame_id, str) or frame_id in seen or frame_id not in anchors:
                continue
            seen.add(frame_id)
            anchor = anchors[frame_id]
            item = {
                "anchorId": anchor.get("id"), "frameId": frame_id,
                "caption": _evidence_caption(chapter, frame_id),
            }
            for key in ("imageUrl", "width", "height"):
                if anchor.get(key) not in (None, ""):
                    item[key] = deepcopy(anchor[key])
            items.append(item)
        chapter["inlineEvidence"] = items
    return model


def _refresh_anchor_sources(model: dict[str, Any], job: dict[str, Any]) -> None:
    frames = {item.get("id"): item for item in job.get("frames") or [] if isinstance(item, dict)}
    if isinstance(job.get("id"), str) and job["id"].strip():
        model["jobId"] = job["id"]
    for anchor in model.get("evidenceAnchors") or []:
        if not isinstance(anchor, dict):
            continue
        frame = frames.get(anchor.get("frameId")) or {}
        image_url = frame.get("imageUrl")
        if isinstance(image_url, str) and image_url.strip():
            anchor["imageUrl"] = image_url
        elif frame:
            anchor.pop("imageUrl", None)
        structure = frame.get("structure") if isinstance(frame.get("structure"), dict) else {}
        width, height = structure.get("width"), structure.get("height")
        if isinstance(width, (int, float)) and width > 0 and isinstance(height, (int, float)) and height > 0:
            anchor["width"], anchor["height"] = width, height


def _chapter(index: int, draft: dict[str, Any], evidence_ids: set[str]) -> dict[str, Any] | None:
    source_frame_ids = list(dict.fromkeys(draft.get("sourceFrameIds") or []))
    if not source_frame_ids or not all(frame_id in evidence_ids for frame_id in source_frame_ids):
        return None
    claims = deepcopy(draft.get("claims") or [])
    mechanism = deepcopy(draft.get("mechanism") or {})
    if "type" not in mechanism and draft.get("mechanismType") is not None:
        mechanism["type"] = draft["mechanismType"]
    classification = classify_text(
        str(draft.get("scope") or draft.get("title") or ""),
        [str(item.get("text") or "") for item in claims if isinstance(item, dict)],
    )
    chapter = {
        "id": f"GCH-{index:03d}",
        "scope": draft.get("scope") or draft.get("title") or "pending",
        "claims": claims,
        "mechanism": mechanism,
        "parameters": deepcopy(draft.get("parameters") or {}),
        "dependencies": deepcopy(draft.get("dependencies") or []),
        "acceptanceCases": deepcopy(draft.get("acceptanceCases") or []),
        "unknowns": deepcopy(draft.get("unknowns") or []),
        "decisionCards": deepcopy(draft.get("decisionCards") or []),
        "sourceFrameIds": source_frame_ids,
        "status": draft.get("status") or "draft",
        "confirmation": deepcopy(draft.get("confirmation") or {"confirmed": False, "revision": None}),
        "plannerSections": deepcopy(draft.get("plannerSections") or planner_sections(draft)),
        "evidenceClaims": deepcopy(draft.get("evidenceClaims") or claims),
        "atomicFacts": deepcopy(draft.get("atomicFacts") or []),
        "chapterType": classification.chapter_type,
        "mechanicVariant": classification.mechanic_variant,
        "matchedSchema": classification.matched_schema,
        "classificationEvidence": list(classification.classification_evidence),
    }
    for field in ("systemName", "subsystemName"):
        if isinstance(draft.get(field), str) and draft[field].strip():
            chapter[field] = draft[field].strip()
    for field in ("parameterSchema", "formulae", "workedExamples", "configurationSources", "presentationRules"):
        if draft.get(field):
            chapter[field] = deepcopy(draft[field])
    _enrich_planning_modules(chapter)
    return chapter


def _enrich_planning_modules(chapter: dict[str, Any]) -> None:
    """Turn visible gameplay values into the target studio's fields and formula modules."""
    source_ids = deepcopy(chapter.get("sourceFrameIds") or [])
    claim_text = "\n".join(
        str(item.get("text") if isinstance(item, dict) else item or "")
        for item in (chapter.get("claims") or [])
    )
    parameter_rows = list(chapter.get("parameterSchema") or [])
    known_names = {str(item.get("name") or "") for item in parameter_rows if isinstance(item, dict)}
    for name, value in re.findall(r"([\u4e00-\u9fffA-Za-z0-9]{2,18}?(?:伤害|范围|概率|速度|数量|生命|攻击))\s*(?:增加|提升|扩大|降低|减少|为)?\s*(-?\d+(?:\.\d+)?)%", claim_text):
        if name in known_names:
            continue
        parameter_rows.append({
            "name": name,
            "plannerMeaning": f"{name}在本次强化或结算中采用的比例",
            "type": "百分比",
            "unit": "%",
            "defaultValue": value,
            "range": "由配置表确定",
            "configurationSource": "素材画面中的强化说明",
            "rounding": "按实现配置",
            "evidenceLevel": "material",
            "sourceFrameIds": source_ids,
            "status": "素材明确展示",
        })
        known_names.add(name)
    if parameter_rows:
        chapter["parameterSchema"] = parameter_rows

    scope = str(chapter.get("scope") or "")
    if "伤害" in scope:
        numbers = re.findall(r"(?<!\d)(\d{2,5})(?!\d)", claim_text)
        if numbers:
            chapter["workedExamples"] = [{"title": "画面核对", "steps": f"实现结果需与素材中可见的伤害数字（{'、'.join(numbers[:5])}）进行对照；参数未确认前不反推具体公式。"}]


def _interaction_revision(job: dict[str, Any]) -> int | None:
    interaction = job.get("interactionModel") or job.get("reviewModel") or {}
    revision = interaction.get("revision") if isinstance(interaction, dict) else None
    return revision if type(revision) is int else None


def _ensure_acceptance_ids(model: dict[str, Any]) -> None:
    acceptances = [item for chapter in model.get("chapters") or [] for item in chapter.get("acceptanceCases") or [] if isinstance(item, dict)]
    used = {item.get("id") for item in acceptances if isinstance(item.get("id"), str)}
    number = 1
    for item in acceptances:
        if isinstance(item.get("id"), str):
            continue
        while f"GAC-{number:03d}" in used:
            number += 1
        item["id"] = f"GAC-{number:03d}"
        used.add(item["id"])


def _ensure_claim_ids(model: dict[str, Any]) -> None:
    claims = [
        item
        for chapter in model.get("chapters") or []
        if isinstance(chapter, dict)
        for item in chapter.get("claims") or []
        if isinstance(item, dict)
    ]
    used: set[str] = set()
    number = 1
    for item in claims:
        claim_id = item.get("id")
        if isinstance(claim_id, str) and re.fullmatch(r"GCL-\d{3}", claim_id) and claim_id not in used:
            used.add(claim_id)
            continue
        while f"GCL-{number:03d}" in used:
            number += 1
        item["id"] = f"GCL-{number:03d}"
        used.add(item["id"])


def _ensure_decision_card_ids(model: dict[str, Any]) -> None:
    """Normalize legacy descriptive ids before they are exposed to the UI."""
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        used: set[str] = set()
        next_number = 1
        for card in chapter.get("decisionCards") or []:
            if not isinstance(card, dict):
                continue
            card_id = card.get("id")
            if isinstance(card_id, str) and re.fullmatch(r"GDC-\d{3}", card_id) and card_id not in used:
                used.add(card_id)
                continue
            while f"GDC-{next_number:03d}" in used:
                next_number += 1
            if isinstance(card_id, str) and card_id:
                card["legacyIds"] = list(dict.fromkeys([*(card.get("legacyIds") or []), card_id]))
            card["id"] = f"GDC-{next_number:03d}"
            used.add(card["id"])
            next_number += 1


def _sync_structured_review_cache(model: dict[str, Any]) -> None:
    """Render P4 copy from the same structured Rules later consumed by Final."""
    projection = model.get("ruleIntelligenceProjection") or {}
    projected = projection.get("reviewProjection") or {}
    by_title = {
        str(chapter.get("title") or ""): chapter
        for chapter in projected.get("chapters") or [] if isinstance(chapter, dict)
    }
    for chapter in model.get("chapters") or []:
        target = by_title.get(str(chapter.get("scope") or ""))
        if not target:
            continue
        visible = [*(target.get("ruleDefinitions") or []), *(target.get("references") or [])]
        chapter["structuredRuleIds"] = [rule.get("ruleId") for rule in visible if rule.get("ruleId")]
        routed = route_structured_rules(visible)
        chapter["plannerSections"] = {
            "summary": str(chapter.get("scope") or target.get("title") or "玩法规则"),
            **routed, "specialCases": [], "acceptanceExamples": [],
        }


def build_gameplay_review_model(job: dict, chapter_drafts: list[dict], directory_proposal: dict | None = None) -> dict:
    frame_ids = _frames(job)
    frames = {item["id"]: item for item in job.get("frames") or [] if isinstance(item, dict) and isinstance(item.get("id"), str)}
    chapters = []
    for draft in chapter_drafts:
        if not isinstance(draft, dict):
            continue
        if chapter := _chapter(len(chapters) + 1, draft, frame_ids):
            chapters.append(chapter)
    anchored_frame_ids = list(dict.fromkeys(frame_id for chapter in chapters for frame_id in chapter["sourceFrameIds"]))
    model = {
        "schemaVersion": "1.0",
        "standard": "GVE16",
        "revision": 1,
        "jobId": job.get("id"),
        "interactionRevision": _interaction_revision(job),
        "evidenceAnchors": [_evidence_anchor(index, frame_id, frames) for index, frame_id in enumerate(anchored_frame_ids, 1)],
        "chapters": chapters,
        "contextWindows": [],
        "temporalProbeRequests": [],
        "temporalEvidence": {"facts": [], "observations": [], "ruleCandidates": [], "gaps": []},
        "diagrams": [],
        "tables": [],
        "reviewState": {"status": "chapter_review", "findings": [], "interactionHandoffConfirmed": directory_proposal is None},
        "editHistory": [],
    }
    if isinstance(job.get("temporalProbeContexts"), list):
        model["temporalProbeContexts"] = deepcopy(job["temporalProbeContexts"])
    _ensure_acceptance_ids(model)
    _ensure_claim_ids(model)
    _ensure_decision_card_ids(model)
    if job.get("contentModelVersion") == 2:
        model["contentModelVersion"] = 2
        for chapter in model["chapters"]:
            chapter.pop("plannerSections", None)
        model["approvedData"] = build_approved_data_v2(model)
        model["ruleIntelligenceProjection"] = build_rule_intelligence_v1(model, model["approvedData"])
        _sync_structured_review_cache(model)
    model["directory"] = deepcopy(directory_proposal) if isinstance(directory_proposal, dict) else legacy_directory(chapters)
    refresh_directory_copy(model)
    refresh_inline_evidence(model)
    return model


def gameplay_model_has_content(model: Any) -> bool:
    return isinstance(model, dict) and any(
        isinstance(chapter, dict) for chapter in model.get("chapters") or []
    )


def build_deterministic_gameplay_skeleton(job: dict[str, Any]) -> dict[str, Any]:
    """Project approved interaction flow/state into a rule-free gameplay skeleton."""
    interaction = job.get("reviewModel") if isinstance(job.get("reviewModel"), dict) else {}
    review_state = interaction.get("reviewState") if isinstance(interaction.get("reviewState"), dict) else {}
    flow_confirmed = review_state.get("flowConfirmed") is True
    confirmed_stage_ids = review_state.get("confirmedStageIds")
    if not isinstance(confirmed_stage_ids, list):
        confirmed_stage_ids = []
    confirmed_ids = {
        item for item in confirmed_stage_ids if isinstance(item, str)
    }
    interaction_stages = interaction.get("stages")
    if not isinstance(interaction_stages, list):
        interaction_stages = []
    approved_stages = []
    if flow_confirmed:
        approved_stages = sorted(
            (
                item for item in interaction_stages
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and (
                    item["id"] in confirmed_ids
                    or (
                        isinstance(item.get("confirmation"), dict)
                        and item["confirmation"].get("confirmed") is True
                    )
                )
            ),
            key=lambda item: (item.get("order", 0), item.get("id", "")),
        )
    approved_stage_ids = {item["id"] for item in approved_stages}

    stages = []
    for index, stage in enumerate(approved_stages, 1):
        source_frame_ids = stage.get("sourceFrameIds")
        if not isinstance(source_frame_ids, list):
            source_frame_ids = []
        projected = {
            "sourceStageId": stage["id"],
            "order": stage.get("order") if type(stage.get("order")) is int else index,
            "name": str(stage.get("name") or stage.get("title") or "").strip(),
            "entryCondition": str(stage.get("entryCondition") or "").strip(),
            "exitCondition": str(stage.get("exitCondition") or "").strip(),
            "sourceFrameIds": [
                frame_id for frame_id in source_frame_ids if isinstance(frame_id, str)
            ],
        }
        small_loop = stage.get("smallLoop") if isinstance(stage.get("smallLoop"), dict) else {}
        if small_loop:
            projected["approvedStateFlow"] = {
                key: deepcopy(small_loop[key])
                for key in ("display", "trigger", "feedback", "result", "retry")
                if small_loop.get(key) not in (None, "")
            }
        stages.append(projected)

    interaction_transitions = interaction.get("transitions")
    if not isinstance(interaction_transitions, list):
        interaction_transitions = []
    transitions = []
    for transition in sorted(
        (item for item in interaction_transitions if isinstance(item, dict)),
        key=lambda item: str(item.get("id") or ""),
    ):
        source_id, target_id = transition.get("sourceStageId"), transition.get("targetStageId")
        if not flow_confirmed or source_id not in approved_stage_ids:
            continue
        if target_id is not None and target_id not in approved_stage_ids:
            continue
        confirmation = transition.get("confirmation")
        if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
            continue
        transitions.append({
            "sourceTransitionId": transition.get("id"),
            "sourceStageId": source_id,
            "targetStageId": target_id,
            "triggerType": transition.get("triggerType"),
            "triggerLabel": transition.get("triggerLabel"),
            "condition": transition.get("condition"),
            "response": transition.get("response"),
            "resultType": transition.get("resultType"),
            "resultState": transition.get("resultState"),
        })

    interaction_component_states = interaction.get("componentStates")
    if not isinstance(interaction_component_states, list):
        interaction_component_states = []
    component_states = []
    if flow_confirmed:
        for state in sorted(
            (item for item in interaction_component_states if isinstance(item, dict)),
            key=lambda item: str(item.get("id") or item.get("componentId") or ""),
        ):
            if not isinstance(state.get("componentId"), str):
                continue
            states = state.get("states")
            if not isinstance(states, list):
                states = []
            component_states.append({
                "sourceStateId": state.get("id"),
                "componentId": state["componentId"],
                "states": deepcopy(states),
            })

    return {
        "schemaVersion": "approved-flow-state-skeleton-v1",
        "source": "approved_flow_state",
        "interactionRevision": _interaction_revision(job),
        "inputType": str(
            (job.get("metadata") if isinstance(job.get("metadata"), dict) else {}).get("inputType")
            or "unknown"
        ),
        "flowConfirmed": flow_confirmed,
        "stages": stages,
        "transitions": transitions,
        "componentStates": component_states,
    }


def _mark_empty_gameplay_lifecycle(model: dict[str, Any], job: dict[str, Any]) -> None:
    generation = job.get("gameplayReviewGeneration")
    generation_failed = isinstance(generation, dict) and generation.get("status") == "failed"
    model["lifecycleState"] = "generation_failed" if generation_failed else "generation_required"
    model["contentState"] = "failed" if generation_failed else "pending"
    model["interactionRevision"] = _interaction_revision(job)
    model["deterministicSkeleton"] = build_deterministic_gameplay_skeleton(job)
    model.setdefault("directory", legacy_directory([]))["status"] = "pending_generation"
    model.setdefault("reviewState", {})["status"] = "generation_required"
    model["reviewState"]["structurePhase"] = "pending"


def build_gameplay_recovery_model(job: dict[str, Any]) -> dict[str, Any]:
    model = {
        "schemaVersion": "1.0",
        "standard": "GVE16",
        "revision": 1,
        "jobId": job.get("id"),
        "interactionRevision": _interaction_revision(job),
        "evidenceAnchors": [],
        "chapters": [],
        "contextWindows": [],
        "temporalProbeRequests": [],
        "temporalEvidence": {"facts": [], "observations": [], "ruleCandidates": [], "gaps": []},
        "diagrams": [],
        "tables": [],
        "reviewState": {"status": "generation_required", "findings": [], "interactionHandoffConfirmed": False},
        "editHistory": [],
        "directory": legacy_directory([]),
    }
    _mark_empty_gameplay_lifecycle(model, job)
    return model


def ensure_gameplay_review_model(job: dict) -> dict:
    model = job.get("gameplayReviewModel")
    last_valid = job.get("gameplayReviewLastValidModel")
    current_has_reviewable_detail = gameplay_model_has_reviewable_detail(model, expected_job_id=job.get("id"))
    if (
        not current_has_reviewable_detail
        and gameplay_model_has_reviewable_detail(last_valid, expected_job_id=job.get("id"))
    ):
        model = deepcopy(last_valid)
        job["gameplayReviewModel"] = model
    if isinstance(model, dict):
        job_id = job.get("id")
        model_job_id = model.get("jobId")
        if job_id and model_job_id != job_id:
            isolated = build_gameplay_recovery_model(job)
            job["gameplayReviewModel"] = isolated
            return isolated
        model.setdefault("temporalProbeRequests", [])
        model.setdefault("temporalEvidence", {"facts": [], "observations": [], "ruleCandidates": [], "gaps": []})
        _ensure_acceptance_ids(model)
        _ensure_claim_ids(model)
        _ensure_decision_card_ids(model)
        for chapter in model.get("chapters") or []:
            if isinstance(chapter, dict):
                _enrich_planning_modules(chapter)
        ensure_directory(model)
        if model.get("contentModelVersion") == 2 and not isinstance(model.get("approvedData"), dict):
            model["approvedData"] = build_approved_data_v2(model)
        if model.get("contentModelVersion") == 2 and not isinstance(model.get("ruleIntelligenceProjection"), dict):
            model["ruleIntelligenceProjection"] = build_rule_intelligence_v1(model, model["approvedData"])
        if model.get("contentModelVersion") == 2:
            _sync_structured_review_cache(model)
        if model.get("ruleCopyVersion", 0) < 4:
            migrate_gameplay_rule_copy(job)
        _refresh_anchor_sources(model, job)
        refresh_inline_evidence(model)
        if (model.get("directory") or {}).get("presentationVersion", 0) < 3:
            refresh_directory_copy(model)
        model["deterministicSkeleton"] = build_deterministic_gameplay_skeleton(job)
        if gameplay_model_has_content(model):
            model.setdefault("lifecycleState", "ready")
            generation = job.get("gameplayReviewGeneration")
            generation_status = generation.get("status") if isinstance(generation, dict) else None
            if generation_status == "failed":
                model["contentState"] = "failed"
                model["lastValidRevision"] = model.get("revision")
            elif generation_status in {"queued", "running", "generating"}:
                model["contentState"] = "pending"
                model["lastValidRevision"] = model.get("revision")
            else:
                model.setdefault("contentState", "ready")
        else:
            _mark_empty_gameplay_lifecycle(model, job)
        return model
    model = build_gameplay_review_model(job, job.get("gameplayChapterDrafts") or [])
    if gameplay_model_has_content(model):
        model["lifecycleState"] = "ready"
        model["contentState"] = "ready"
        model["deterministicSkeleton"] = build_deterministic_gameplay_skeleton(job)
    else:
        _mark_empty_gameplay_lifecycle(model, job)
    job["gameplayReviewModel"] = model
    return model


def _list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{path}: expected a list")
        return []
    return value


def _valid_id(value: Any, prefix: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(rf"{prefix}-\d{{3}}", value))


def validate_gameplay_review_model(model: dict) -> list[str]:
    if not isinstance(model, dict):
        return ["model: expected an object"]
    ensure_directory(model)
    errors: list[str] = []
    if model.get("schemaVersion") != "1.0":
        errors.append("schemaVersion: expected '1.0'")
    if model.get("standard") != "GVE16":
        errors.append("standard: expected 'GVE16'")
    if type(model.get("revision")) is not int or model["revision"] < 1:
        errors.append("revision: expected a positive integer")
    if not isinstance(model.get("jobId"), str) or not model["jobId"].strip():
        errors.append("jobId: expected a non-empty string")
    if model.get("interactionRevision") is not None and type(model["interactionRevision"]) is not int:
        errors.append("interactionRevision: expected an integer or null")

    anchors = _list(model.get("evidenceAnchors"), "evidenceAnchors", errors)
    anchor_ids, frame_ids = set(), set()
    for index, anchor in enumerate(anchors):
        path = f"evidenceAnchors[{index}]"
        if not isinstance(anchor, dict):
            errors.append(f"{path}: expected an object")
            continue
        anchor_id, frame_id = anchor.get("id"), anchor.get("frameId")
        if not _valid_id(anchor_id, "GEV") or anchor_id in anchor_ids:
            errors.append(f"{path}.id: expected a unique GEV-### id")
        else:
            anchor_ids.add(anchor_id)
        if not isinstance(frame_id, str) or not frame_id:
            errors.append(f"{path}.frameId: expected a non-empty string")
        elif frame_id in frame_ids:
            errors.append(f"{path}.frameId: duplicate evidence {frame_id}")
        else:
            frame_ids.add(frame_id)

    chapters = _list(model.get("chapters"), "chapters", errors)
    chapter_ids: set[str] = set()
    claim_ids: set[str] = set()
    acceptance_ids: set[str] = set()
    for index, chapter in enumerate(chapters):
        path = f"chapters[{index}]"
        if not isinstance(chapter, dict):
            errors.append(f"{path}: expected an object")
            continue
        chapter_id = chapter.get("id")
        label = chapter_id if isinstance(chapter_id, str) else path
        if not _valid_id(chapter_id, "GCH") or chapter_id in chapter_ids:
            errors.append(f"{path}.id: expected a unique GCH-### id")
        else:
            chapter_ids.add(chapter_id)
        for field in _CHAPTER_FIELDS:
            if field not in chapter:
                errors.append(f"{label}: missing {field}")
        if not isinstance(chapter.get("scope"), str) or not chapter.get("scope", "").strip():
            errors.append(f"{label}.scope: expected a non-empty string")
        for field in ("claims", "dependencies", "acceptanceCases", "unknowns", "decisionCards", "sourceFrameIds"):
            _list(chapter.get(field), f"{label}.{field}", errors)
        if not isinstance(chapter.get("parameters"), dict):
            errors.append(f"{label}.parameters: expected an object")
        mechanism = chapter.get("mechanism")
        if not isinstance(mechanism, dict):
            errors.append(f"{label}.mechanism: expected an object")
        elif mechanism.get("type") not in MECHANISM_SCHEMAS:
            errors.append(f"{label}: unknown mechanism type {mechanism.get('type')!r}")
        for claim_index, claim in enumerate(chapter.get("claims") or []):
            claim_path = f"{label}.claims[{claim_index}]"
            if not isinstance(claim, dict):
                errors.append(f"{claim_path}: expected an object")
                continue
            if "id" in claim:
                claim_id = claim.get("id")
                if not _valid_id(claim_id, "GCL") or claim_id in claim_ids:
                    errors.append(f"{claim_path}.id: expected a unique GCL-### id")
                else:
                    claim_ids.add(claim_id)
            if claim.get("sourceType") not in _CLAIM_SOURCE_TYPES:
                errors.append(f"{claim_path}.sourceType: invalid source type")
            for frame_id in claim.get("sourceFrameIds") or []:
                if frame_id not in frame_ids:
                    errors.append(f"{claim_path}.sourceFrameIds: unknown evidence {frame_id}")
        for acceptance_index, acceptance in enumerate(chapter.get("acceptanceCases") or []):
            acceptance_path = f"{label}.acceptanceCases[{acceptance_index}]"
            if not isinstance(acceptance, dict):
                errors.append(f"{acceptance_path}: expected an object")
                continue
            if "id" in acceptance:
                acceptance_id = acceptance.get("id")
                if not _valid_id(acceptance_id, "GAC") or acceptance_id in acceptance_ids:
                    errors.append(f"{acceptance_path}.id: expected a unique GAC-### id")
                else:
                    acceptance_ids.add(acceptance_id)
        decision_ids: set[str] = set()
        for card_index, card in enumerate(chapter.get("decisionCards") or []):
            card_path = f"{label}.decisionCards[{card_index}]"
            if not isinstance(card, dict):
                errors.append(f"{card_path}: expected an object")
                continue
            card_id = card.get("id")
            if not _valid_id(card_id, "GDC") or card_id in decision_ids:
                errors.append(f"{card_path}.id: expected a unique GDC-### id")
            else:
                decision_ids.add(card_id)
            if not isinstance(card.get("question"), str) or not card["question"].strip():
                errors.append(f"{card_path}.question: expected a non-empty string")
            if card.get("selectionMode", "single") not in {"single", "multiple"}:
                errors.append(f"{card_path}.selectionMode: invalid mode")
            options = card.get("options")
            if not isinstance(options, list) or len(options) < 2:
                errors.append(f"{card_path}.options: expected at least two choices")
            elif any(not isinstance(option, dict) or not option.get("id") or not str(option.get("label") or "").strip() for option in options):
                errors.append(f"{card_path}.options: every choice needs id and label")
            if card.get("status", "pending") not in {"pending", "skipped", "resolved"}:
                errors.append(f"{card_path}.status: invalid status")
        for frame_index, frame_id in enumerate(chapter.get("sourceFrameIds") or []):
            if frame_id not in frame_ids:
                errors.append(f"{label}.sourceFrameIds[{frame_index}]: unknown evidence {frame_id}")
        confirmation = chapter.get("confirmation")
        if not isinstance(confirmation, dict) or not isinstance(confirmation.get("confirmed"), bool):
            errors.append(f"{label}.confirmation: expected a confirmed flag")
        elif confirmation.get("decision") is not None and confirmation.get("decision") not in {"approved", "conditional", "rejected", "not_applicable"}:
            errors.append(f"{label}.confirmation.decision: invalid decision")

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = chapter.get("id") or "CHAPTER_INVALID"
        for dependency in chapter.get("dependencies") or []:
            if dependency not in chapter_ids:
                errors.append(f"{chapter_id}.dependencies: unknown chapter {dependency}")

    for index, diagram in enumerate(_list(model.get("diagrams"), "diagrams", errors)):
        path = f"diagrams[{index}]"
        if not isinstance(diagram, dict):
            errors.append(f"{path}: expected an object")
            continue
        diagram_id = diagram.get("id")
        if not _valid_id(diagram_id, "GDI"):
            errors.append(f"{path}.id: expected a GDI-### id")
        for chapter_id in diagram.get("chapterIds") or []:
            if chapter_id not in chapter_ids:
                errors.append(f"{diagram_id or path}.chapterIds: unknown chapter {chapter_id}")
    for field in ("contextWindows", "editHistory"):
        _list(model.get(field), field, errors)
    if "temporalProbeRequests" in model:
        _list(model.get("temporalProbeRequests"), "temporalProbeRequests", errors)
    if "temporalEvidence" in model and not isinstance(model.get("temporalEvidence"), dict):
        errors.append("temporalEvidence: expected an object")
    if not isinstance(model.get("reviewState"), dict):
        errors.append("reviewState: expected an object")
    errors.extend(directory_errors(model))
    return errors


def _interaction_evidence_ids(interaction_model: dict) -> set[str] | None:
    if not isinstance(interaction_model, dict):
        return None
    frames = interaction_model.get("frames")
    if isinstance(frames, list):
        return {item.get("id") for item in frames if isinstance(item, dict) and isinstance(item.get("id"), str)}
    sources = interaction_model.get("sources")
    if isinstance(sources, dict):
        return {key for key in sources if isinstance(key, str)}
    return None


def _has_gameplay_depth(chapter: dict[str, Any]) -> bool:
    mechanism = chapter.get("mechanism") if isinstance(chapter.get("mechanism"), dict) else {}
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    meaningful_mechanism = [
        value for key, value in mechanism.items()
        if key not in {"type", "name", "description"} and value not in (None, "", [], {})
    ]
    checks = (
        bool(meaningful_mechanism or planner.get("normalFlow") or planner.get("keyRules")),
        bool(configured_parameter_items(chapter) or chapter.get("parameterSchema") or chapter.get("formulae")),
        bool(chapter.get("dependencies")),
        bool(chapter.get("acceptanceCases") or planner.get("acceptanceExamples")),
        bool(planner.get("specialCases") or chapter.get("unknowns")),
    )
    return sum(checks) >= 2


def _gameplay_depth_gaps(chapter: dict[str, Any]) -> list[str]:
    mechanism = chapter.get("mechanism") if isinstance(chapter.get("mechanism"), dict) else {}
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    mechanism_type = str(mechanism.get("type") or "custom")
    meaningful = {
        key: value for key, value in mechanism.items()
        if key not in {"type", "name", "description"} and value not in (None, "", [], {})
    }
    gaps: list[str] = []
    if not meaningful and not planner.get("normalFlow") and not planner.get("keyRules"):
        gaps.append("RULES_MISSING")
    if not chapter.get("acceptanceCases") and not planner.get("acceptanceExamples"):
        gaps.append("VERIFICATION_MISSING")
    has_control_detail = bool(
        configured_parameter_items(chapter) or chapter.get("parameterSchema") or chapter.get("formulae")
        or planner.get("specialCases") or chapter.get("unknowns")
    )
    if not has_control_detail:
        gaps.append("BOUNDARY_OR_CONFIGURATION_MISSING")
    if mechanism_type == "formula" and not chapter.get("formulae") and not mechanism.get("formula"):
        gaps.append("FORMULA_DEFINITION_MISSING")
    if mechanism_type == "random_pool" and not any(mechanism.get(key) for key in ("weightFormula", "drawOrder", "eligibility", "exclusions")):
        gaps.append("DRAW_RULE_MISSING")
    if mechanism_type == "spatial_drag" and not any(mechanism.get(key) for key in ("legalRegion", "matchRule", "bounds", "failureReturn")):
        gaps.append("SPATIAL_RULE_MISSING")
    return gaps


def gameplay_gate(model: dict, interaction_model: dict) -> dict:
    blockers: list[str] = []
    detail_quality = model.get("detailQuality") if isinstance(model, dict) and isinstance(model.get("detailQuality"), dict) else {}
    if detail_quality.get("passed") is False:
        blockers.append("DETAIL_QUALITY_FAILED")
        blockers.extend(str(item) for item in detail_quality.get("errors") or [] if item)
    ensure_directory(model)
    # Legacy and test-created review models may have valid chapter ownership but no
    # materialized system tree yet. Build the canonical hierarchy before auditing.
    model.update(normalize_gameplay_structure(model))
    blockers.extend(directory_errors(model, require_confirmed=True))
    validation_errors = validate_gameplay_review_model(model)
    chapters = model.get("chapters") if isinstance(model, dict) and isinstance(model.get("chapters"), list) else []
    not_applicable_ids = {
        chapter.get("id") for chapter in chapters
        if isinstance(chapter, dict) and chapter.get("status") == "not_applicable" and (chapter.get("confirmation") or {}).get("confirmed")
    }
    blockers.extend(
        finding for finding in lead_planner_output_audit(model, "details")
        if not any(str(finding).startswith(f"{chapter_id}:") for chapter_id in not_applicable_ids if chapter_id)
    )
    anchors = model.get("evidenceAnchors") if isinstance(model, dict) and isinstance(model.get("evidenceAnchors"), list) else []
    interaction_revision = interaction_model.get("revision") if isinstance(interaction_model, dict) else None
    if type(interaction_revision) is int and model.get("interactionRevision") != interaction_revision:
        blockers.append("INTERACTION_REVISION_STALE")
    valid_evidence = _interaction_evidence_ids(interaction_model)
    if valid_evidence is not None:
        for anchor in anchors:
            if isinstance(anchor, dict) and anchor.get("frameId") not in valid_evidence:
                blockers.append(anchor.get("id") or "EVIDENCE_INVALID")
    for chapter in chapters:
        if not isinstance(chapter, dict):
            blockers.append("CHAPTER_INVALID")
            continue
        chapter_id = chapter.get("id") or "CHAPTER_INVALID"
        if chapter.get("status") == "not_applicable" and (chapter.get("confirmation") or {}).get("confirmed"):
            continue
        known_frame_ids = {anchor.get("frameId") for anchor in anchors if isinstance(anchor, dict)}
        if any(frame_id not in known_frame_ids for frame_id in chapter.get("sourceFrameIds") or []):
            blockers.append(chapter_id)
        for claim in chapter.get("claims") or []:
            if isinstance(claim, dict) and any(frame_id not in known_frame_ids for frame_id in claim.get("sourceFrameIds") or []):
                blockers.append(chapter_id)
                break
        if chapter.get("status") not in {"approved", "conditional"} or not (chapter.get("confirmation") or {}).get("confirmed"):
            blockers.append(chapter_id)
        if review_state_depth := (model.get("reviewState") or {}).get("depthContractVersion"):
            if review_state_depth >= 1:
                gaps = _gameplay_depth_gaps(chapter)
                if gaps:
                    blockers.append(f"{chapter_id}:GAMEPLAY_DEPTH_INSUFFICIENT")
                    blockers.extend(f"{chapter_id}:{gap}" for gap in gaps)
                if optional_module_errors(chapter):
                    blockers.append(f"{chapter_id}:OPTIONAL_MODULE_EVIDENCE_INVALID")
        mechanism = chapter.get("mechanism") or {}
        for field, metadata in configured_parameter_items(chapter):
            if not isinstance(metadata, dict) or any(not metadata.get(key) for key in _METADATA_FIELDS):
                blockers.append(chapter_id)
                break
    review_state = model.get("reviewState") if isinstance(model, dict) and isinstance(model.get("reviewState"), dict) else {}
    for finding in review_state.get("findings") or []:
        if isinstance(finding, dict) and finding.get("severity") == "blocker" and finding.get("status") != "resolved":
            blockers.append(finding.get("id") or "FINDING_INVALID")
    for diagram in model.get("diagrams") or []:
        if not isinstance(diagram, dict):
            blockers.append("DIAGRAM_INVALID")
            continue
        diagram_id = diagram.get("id") or "DIAGRAM_INVALID"
        if diagram.get("status") == "deleted" and diagram.get("optional", True):
            continue
        if diagram.get("status") != "reviewed" or (type(interaction_revision) is int and diagram.get("interactionRevision") != interaction_revision):
            blockers.append(diagram_id)
    for table in model.get("tables") or []:
        if not isinstance(table, dict):
            blockers.append("TABLE_INVALID")
            continue
        table_id = table.get("id") or "TABLE_INVALID"
        if table.get("status") == "deleted" and table.get("optional", True):
            continue
        if table.get("status") != "reviewed":
            blockers.append(table_id)
    if validation_errors:
        blockers.append("MODEL_INVALID")
    return {"exportReady": not blockers, "blockers": list(dict.fromkeys(blockers)), "warnings": []}
