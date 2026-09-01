from __future__ import annotations

import json
import re
from typing import Any


_LEVELS = {
    "明确展示": "observed",
    "合理推断": "inferred",
    "未知待确认": "unknown",
    "observed": "observed",
    "inferred": "inferred",
    "unknown": "unknown",
}
_RESULT_TYPES = {"navigate", "state_change", "open_overlay", "close_overlay", "return", "loop", "terminal"}
_TARGET_RESULT_TYPES = {"navigate", "open_overlay", "return", "loop"}


def _planner_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?<![A-Za-z])BOSS(?![A-Za-z])", "首领", text, flags=re.I)
    text = re.sub(r"首领\s*首领", "首领", text)
    text = re.sub(r"[（(]\s*inferred from damage numbers\s*[）)]", "（根据伤害数字推测）", text, flags=re.I)
    text = re.sub(r"\bdamage numbers\b", "伤害数字", text, flags=re.I)
    return re.sub(r"\binferred from\b", "根据画面推测", text, flags=re.I)


def build_standard_prompt(mode: str, plan_example: str = "") -> str:
    if mode not in {"gameplay", "interaction"}:
        raise ValueError("mode must be gameplay or interaction")
    requirements = (
        "玩家目标、核心循环、玩家操作、事件因果链、玩法状态机、规则与数值、胜负结算、反馈、HUD与证据索引"
        if mode == "gameplay" else
        "用户目标、任务流、页面与弹窗、组件层级、交互因果链、组件状态与校验、动效、异常状态与证据索引"
    )
    prompt = (
        f"默认执行 GVE16 {('玩法' if mode == 'gameplay' else '交互')}策划规范。"
        f"必须覆盖：{requirements}。每条结论区分明确展示、合理推断、默认值和未知待确认，并引用时间戳证据。"
    )
    if plan_example.strip():
        prompt += f"\n已批准样例仅用于校准结构、术语和颗粒度：\n{plan_example[:12000]}"
    return prompt


def _timestamp(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    minutes, remainder = divmod(milliseconds, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{minutes:02d}:{whole_seconds:02d}.{millis:03d}"


def _evidence(frame: dict[str, Any]) -> dict[str, Any]:
    analysis = frame.get("analysis", {})
    source_type = "image_sequence" if frame.get("sequenceIndex") is not None else "video"
    return {
        "sourceType": source_type,
        "sourceId": frame["id"],
        "locator": str(frame["sequenceIndex"]) if source_type == "image_sequence" else _timestamp(frame.get("timestamp", 0)),
        "sceneId": f"SCN-{int(frame.get('sceneId', 0)) + 1:03d}",
        "evidenceLevel": _LEVELS.get(analysis.get("evidenceLevel"), "unknown"),
        "confidence": analysis.get("confidence", "低"),
    }


def _events(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for index, frame in enumerate(frames, 1):
        analysis = frame.get("analysis", {})
        events.append({
            "id": f"EVT-{index:03d}",
            "sceneId": f"SCN-{int(frame.get('sceneId', 0)) + 1:03d}",
            "trigger": analysis.get("eventType") or "unknown",
            "action": analysis.get("userAction") or "未知待确认",
            "beforeState": analysis.get("beforeState") or "未知待确认",
            "response": analysis.get("systemResponse") or "未知待确认",
            "afterState": analysis.get("afterState") or "未知待确认",
            "resultType": "state_change",
            "targetStageId": None,
            "resultState": analysis.get("afterState") or "未知待确认",
            "evidence": [_evidence(frame)],
            "unknowns": analysis.get("unknowns") or [],
        })
    return events


def _event_frames(mode: str, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if mode != "interaction":
        return frames
    detail_frames = [frame for frame in frames if (frame.get("analysis") or {}).get("isDetailFrame")]
    return detail_frames or frames


def _scenes(scenes: list[dict[str, Any]], frames: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, scene in enumerate(scenes, 1):
        analysis = scene.get("analysis", {})
        refs = [_evidence(frames[frame_id]) for frame_id in scene.get("frameIds", []) if frame_id in frames]
        result.append({
            "id": f"SCN-{index:03d}",
            "sourceSceneId": scene.get("id"),
            "title": analysis.get("title") or f"场景 {index}",
            "type": analysis.get("sceneType") or "未知待确认",
            "objective": analysis.get("objective") or "未知待确认",
            "timeRange": {"start": scene.get("start", 0), "end": scene.get("end", 0)},
            "entryCondition": analysis.get("entryCondition") or "未知待确认",
            "exitCondition": analysis.get("exitCondition") or "未知待确认",
            "visibleRules": analysis.get("visibleRules") or [],
            "stateChanges": analysis.get("stateChanges") or [],
            "evidence": refs,
        })
    return result


def _components(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tracks = [
        track for track in tracks
        if len(track.get("observations") or []) > 1
        or str(track.get("class") or "").lower() not in {"", "component", "unknown", "region"}
    ][:999]
    return [{
        "id": f"CMP-{index:03d}",
        "sourceTrackId": track.get("id"),
        "type": track.get("class") or "component",
        "states": ["observed"],
        "observations": track.get("observations") or [],
    } for index, track in enumerate(tracks, 1)]


def build_planning_model(job: dict[str, Any]) -> dict[str, Any]:
    mode = job.get("metadata", {}).get("mode")
    if mode not in {"gameplay", "interaction"}:
        raise ValueError("mode must be gameplay or interaction")
    frames = job.get("frames") or []
    events = _events(_event_frames(mode, frames))
    scenes = _scenes(job.get("scenes") or [], {frame["id"]: frame for frame in frames})
    flow = [{
        "id": f"FLOW-{index:03d}",
        "eventId": event["id"],
        "sourceStageId": event["sceneId"],
        "targetStageId": event["targetStageId"],
        "resultType": event["resultType"],
        "resultState": event["resultState"],
        "from": event["beforeState"],
        "to": event["afterState"],
        "trigger": event["action"],
    } for index, event in enumerate(events, 1)]
    model = {
        "schemaVersion": "1.0",
        "standard": "GVE16",
        "mode": mode,
        "project": {
            "id": job.get("id"),
            "name": job.get("metadata", {}).get("projectName") or "未命名项目",
            "scope": job.get("metadata", {}).get("scope") or "",
            "sourceType": job.get("metadata", {}).get("inputType", "video"),
            "sourceVideo": job.get("video") or {},
        },
        "scenes": scenes,
        "events": events,
        "components": _components(job.get("componentTracks") or []),
        "evidence": [reference for scene in scenes for reference in scene["evidence"]],
        "gameplay": {"coreLoop": flow, "rules": [rule for scene in scenes for rule in scene["visibleRules"]]} if mode == "gameplay" else None,
        "interaction": {"taskFlow": flow, "componentStates": []} if mode == "interaction" else None,
        "designHandoff": {
            "status": "schema-ready",
            "targets": ["feishu-whiteboard", "figma"],
            "generatedArtifacts": [],
            "flowEdges": flow,
        },
        "acceptanceCriteria": [
            {"id": "AC-001", "type": "evidence", "description": "所有事件均可回链视频时间点"},
            {"id": "AC-002", "type": "flow", "description": "关键操作形成前置状态、输入、响应、后置状态闭环"},
            {"id": "AC-003", "type": "uncertainty", "description": "观察、推断和未知信息明确区分"},
        ],
        "quality": job.get("qualityReport") or {},
    }
    return model


def _confirmed(item: dict[str, Any]) -> bool:
    return bool((item.get("confirmation") or {}).get("confirmed"))


def _review_evidence(job: dict[str, Any], frame_id: str, scene_id: str) -> dict[str, Any]:
    frame = next((item for item in job.get("frames") or [] if item.get("id") == frame_id), {})
    source_type = job.get("metadata", {}).get("inputType", "video")
    locator = str(frame.get("sequenceIndex") or frame_id) if source_type == "image_sequence" else _timestamp(frame.get("timestamp", 0))
    analysis = frame.get("analysis") or {}
    return {
        "sourceType": source_type,
        "sourceId": frame_id,
        "locator": locator,
        "sceneId": scene_id,
        "evidenceLevel": _LEVELS.get(analysis.get("evidenceLevel"), "unknown"),
        "confidence": analysis.get("confidence", "低"),
    }


def compile_confirmed_planning_model(job: dict[str, Any]) -> dict[str, Any]:
    """Compile the confirmed review boundary into the GVE16 delivery model."""
    review = job.get("reviewModel") or {}
    mode = job.get("metadata", {}).get("mode", "interaction")
    if mode not in {"gameplay", "interaction"}:
        raise ValueError("mode must be gameplay or interaction")

    stages = sorted(
        (item for item in review.get("stages") or [] if _confirmed(item)),
        key=lambda item: (item.get("order", 0), item.get("id", "")),
    )
    scene_ids = {stage["id"]: f"SCN-{stage.get('order', index):03d}" for index, stage in enumerate(stages, 1)}
    evidence: list[dict[str, Any]] = []
    scenes = []
    hierarchy_stages = []
    for index, stage in enumerate(stages, 1):
        scene_id = scene_ids[stage["id"]]
        references = [_review_evidence(job, item["frameId"], scene_id) for item in stage.get("representativeFrames") or []]
        evidence.extend(references)
        scenes.append({
            "id": scene_id,
            "sourceStageId": stage["id"],
            "title": stage.get("name") or f"阶段 {index}",
            "type": "interaction_stage" if mode == "interaction" else "gameplay_stage",
            "objective": stage.get("objective") or "未知待确认",
            "timeRange": {},
            "entryCondition": stage.get("entryCondition") or "未知待确认",
            "exitCondition": stage.get("exitCondition") or "未知待确认",
            "visibleRules": [],
            "stateChanges": [],
            "evidence": references,
        })
        loop = stage.get("smallLoop") or {}
        hierarchy_stages.append({
            "id": stage["id"], "title": stage.get("name") or f"阶段 {index}",
            "entryCondition": stage.get("entryCondition") or "未知待确认",
            "exitCondition": stage.get("exitCondition") or "未知待确认",
            "smallLoops": [{
                "id": f"{stage['id']}-SMALL-001", "title": loop.get("display") or stage.get("name") or f"阶段 {index}",
                "entryCondition": stage.get("entryCondition") or "未知待确认",
                "repeatCondition": loop.get("retry") or "未知待确认",
                "exitCondition": stage.get("exitCondition") or "未知待确认",
                "steps": [{
                    "id": f"{stage['id']}-STEP-{step_index:03d}", "title": {"entry": "操作前", "change": "变化过程", "result": "操作后"}.get(str(item.get("role") or ""), "关键画面"),
                    "userAction": _planner_text(loop.get("trigger") or "未知待确认"), "systemResponse": _planner_text(loop.get("feedback") or "未知待确认"),
                    "evidence": [_review_evidence(job, item["frameId"], scene_id)],
                } for step_index, item in enumerate(stage.get("representativeFrames") or [], 1)],
            }],
        })

    events, flow = [], []
    for index, transition in enumerate(sorted(review.get("transitions") or [], key=lambda item: item.get("id", "")), 1):
        if not transition.get("included") or not _confirmed(transition) or transition.get("sourceStageId") not in scene_ids:
            continue
        event_id = f"EVT-{index:03d}"
        source_scene_id = scene_ids[transition["sourceStageId"]]
        refs = [_review_evidence(job, transition["sourceFrameId"], source_scene_id)]
        evidence.extend(refs)
        result_type = transition.get("resultType") or "unknown"
        target_scene_id = scene_ids.get(transition.get("targetStageId"))
        if result_type not in _TARGET_RESULT_TYPES:
            target_scene_id = None
        event = {
            "id": event_id, "sourceTransitionId": transition["id"], "sceneId": source_scene_id,
            "trigger": transition.get("triggerType") or "unknown", "action": transition.get("triggerLabel") or "未知待确认",
            "beforeState": transition.get("condition") or "未知待确认", "response": transition.get("response") or "未知待确认",
            "afterState": transition.get("resultState") or "未知待确认", "resultState": transition.get("resultState") or "未知待确认",
            "resultType": result_type, "targetStageId": target_scene_id, "evidence": refs, "unknowns": [],
        }
        events.append(event)
        flow.append({
            "id": f"FLOW-{len(flow) + 1:03d}", "eventId": event_id, "from": event["beforeState"], "to": event["afterState"],
            "trigger": event["action"], "sourceTransitionId": transition["id"], "sourceStageId": source_scene_id,
            "targetStageId": target_scene_id, "resultType": result_type, "resultState": event["resultState"],
        })

    selected_regions = [item for item in review.get("regions") or [] if _confirmed(item) and item.get("stageId") in scene_ids]
    selected_components = [item for item in review.get("components") or [] if _confirmed(item) and item.get("stageId") in scene_ids]
    components_by_region = {item.get("regionId"): item for item in selected_components if item.get("regionId")}
    component_sources = [components_by_region.get(region.get("id"), region) for region in selected_regions]
    component_sources.extend(item for item in selected_components if not item.get("regionId"))
    components = []
    component_ids: dict[str, str] = {}
    for index, item in enumerate(component_sources, 1):
        source_id = str(item.get("id") or f"component-{index}")
        component_id = f"CMP-{index:03d}"
        component_ids[source_id] = component_id
        components.append({
            "id": component_id, "sourceComponentId": source_id, "sceneId": scene_ids[item["stageId"]],
            "type": item.get("type") or "region", "name": item.get("name") or item.get("label") or source_id,
            "bounds": item.get("bounds"), "states": {key: "unknown" for key in ("default", "pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet")}, "rule": item.get("rule") or {},
        })
    component_states = []
    for item in review.get("componentStates") or []:
        component_id = component_ids.get(str(item.get("componentId")))
        if component_id and _confirmed(item):
            states = {key: str((item.get("states") or {}).get(key) or "unknown") for key in ("default", "pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet")}
            component_states.append({"componentId": component_id, "states": states})
            next(component for component in components if component["id"] == component_id)["states"] = states

    constraints = [dict(item) for item in review.get("crossStateConstraints") or []]
    first_stage, last_stage = (stages[0] if stages else {}), (stages[-1] if stages else {})
    model = {
        "schemaVersion": "1.0", "standard": "GVE16", "mode": mode,
        "project": {
            "id": job.get("id"), "name": job.get("metadata", {}).get("projectName") or "未命名项目",
            "scope": job.get("metadata", {}).get("scope") or "", "sourceType": job.get("metadata", {}).get("inputType", "video"),
        },
        "scenes": scenes, "events": events, "components": components, "evidence": evidence,
        "gameplay": {"coreLoop": flow, "rules": []} if mode == "gameplay" else None,
        "interaction": {"taskFlow": flow, "componentStates": component_states} if mode == "interaction" else None,
        "extensions": {"crossStateConstraints": constraints},
        "loopHierarchy": {"largeLoops": [{
            "id": "LOOP-001", "title": "玩家操作流程" if mode == "interaction" else "核心玩法循环",
            "entryCondition": first_stage.get("entryCondition") or "未知待确认", "repeatCondition": "再次发起相同目标时重复",
            "exitCondition": last_stage.get("exitCondition") or "未知待确认", "stages": hierarchy_stages,
        }] if hierarchy_stages else []},
        "designHandoff": {"status": "schema-ready", "targets": ["feishu-whiteboard", "figma"], "generatedArtifacts": [], "flowEdges": flow},
        "acceptanceCriteria": [
            {"id": "AC-001", "type": "evidence", "description": "每个已确认事件均可回链代表画面"},
            {"id": "AC-002", "type": "flow", "description": "已确认交互形成状态变化闭环"},
            {"id": "AC-003", "type": "constraint", "description": "跨状态约束作为独立扩展保留"},
        ],
        "quality": job.get("qualityReport") or {},
    }
    errors = validate_planning_model(model)
    if errors:
        raise ValueError("confirmed planning model validation failed: " + "; ".join(errors))
    return model


def validate_planning_model(model: dict[str, Any]) -> list[str]:
    errors = []
    try:
        json.dumps(model, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        errors.append("model must be JSON serializable")
    if model.get("standard") != "GVE16":
        errors.append("standard must be GVE16")
    if model.get("mode") not in {"gameplay", "interaction"}:
        errors.append("mode must be gameplay or interaction")
    for collection in ("scenes", "events", "components", "evidence", "acceptanceCriteria"):
        if not isinstance(model.get(collection), list):
            errors.append(f"{collection} must be a list")

    def validate_ids(collection: str, prefix: str) -> set[str]:
        raw_values = model.get(collection)
        values, seen = raw_values if isinstance(raw_values, list) else [], set()
        for index, item in enumerate(values):
            value = item.get("id") if isinstance(item, dict) else None
            if not isinstance(value, str) or not re.fullmatch(fr"{prefix}-\d{{3}}", value) or value in seen:
                errors.append(f"{collection}[{index}].id must be a unique {prefix}-### id")
            if isinstance(value, str):
                seen.add(value)
        return seen

    scene_ids = validate_ids("scenes", "SCN")
    event_ids = validate_ids("events", "EVT")
    component_ids = validate_ids("components", "CMP")
    flow_path = "gameplay.coreLoop" if model.get("mode") == "gameplay" else "interaction.taskFlow"
    branch = model.get("gameplay") if model.get("mode") == "gameplay" else model.get("interaction")
    flows = branch.get("coreLoop" if model.get("mode") == "gameplay" else "taskFlow") if isinstance(branch, dict) else None
    if not isinstance(flows, list):
        errors.append(f"{flow_path} must be a list")
        flows = []
    seen_flow_ids: set[str] = set()
    for index, flow in enumerate(flows):
        flow_id = flow.get("id") if isinstance(flow, dict) else None
        if not isinstance(flow_id, str) or not re.fullmatch(r"FLOW-\d{3}", flow_id) or flow_id in seen_flow_ids:
            errors.append(f"{flow_path}[{index}].id must be a unique FLOW-### id")
        if isinstance(flow_id, str):
            seen_flow_ids.add(flow_id)
        if not isinstance(flow, dict):
            continue
        if flow.get("eventId") not in event_ids:
            errors.append(f"{flow_path}[{index}].eventId must reference an event")
        if flow.get("sourceStageId") not in scene_ids:
            errors.append(f"{flow_path}[{index}].sourceStageId must reference a scene")
        _validate_result(flow, f"{flow_path}[{index}]", scene_ids, errors)

    canonical_evidence = model.get("evidence") if isinstance(model.get("evidence"), list) else []
    project_source_type = (model.get("project") or {}).get("sourceType") if isinstance(model.get("project"), dict) else None

    def validate_evidence(items: Any, path: str, expected_scene_id: str | None = None) -> None:
        if not isinstance(items, list) or not items:
            errors.append(f"{path} must be a non-empty list")
            return
        for index, item in enumerate(items):
            item_path = f"{path}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_path} must be an object")
                continue
            for field in ("sourceId", "sceneId", "locator", "evidenceLevel", "confidence"):
                value = item.get(field)
                if value is None or value == "" or (isinstance(value, str) and not value.strip()):
                    errors.append(f"{item_path}.{field} is required")
                elif isinstance(value, (dict, list, set, tuple)):
                    errors.append(f"{item_path}.{field} must be a non-empty scalar")
            if item.get("sourceType") not in {"video", "image_sequence"}:
                errors.append(f"{item_path}.sourceType must be video or image_sequence")
            elif project_source_type in {"video", "image_sequence"} and item.get("sourceType") != project_source_type:
                errors.append(f"{item_path}.sourceType must match project sourceType")
            if item.get("evidenceLevel") not in {"observed", "inferred", "unknown"}:
                errors.append(f"{item_path}.evidenceLevel is invalid")
            if item.get("sceneId") not in scene_ids:
                errors.append(f"{item_path}.sceneId must reference a scene")
            if expected_scene_id is not None and item.get("sceneId") != expected_scene_id:
                errors.append(f"{item_path}.sceneId must equal {expected_scene_id}")
            if item not in canonical_evidence:
                errors.append(f"{item_path} must reference model evidence")

    scenes = model.get("scenes") if isinstance(model.get("scenes"), list) else []
    events = model.get("events") if isinstance(model.get("events"), list) else []
    for index, scene in enumerate(scenes):
        if isinstance(scene, dict):
            validate_evidence(scene.get("evidence"), f"scenes[{index}].evidence", scene.get("id"))
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        if event.get("sceneId") not in scene_ids:
            errors.append(f"events[{index}].sceneId must reference a scene")
        _validate_result(event, f"events[{index}]", scene_ids, errors)
        validate_evidence(event.get("evidence"), f"events[{index}].evidence", event.get("sceneId"))

    scene_by_source = {scene.get("sourceStageId"): scene.get("id") for scene in scenes if isinstance(scene, dict)}
    hierarchy = model.get("loopHierarchy") if isinstance(model.get("loopHierarchy"), dict) else {}
    large_loops = hierarchy.get("largeLoops") if isinstance(hierarchy.get("largeLoops"), list) else []
    for loop_index, large_loop in enumerate(large_loops):
        hierarchy_stages = large_loop.get("stages") if isinstance(large_loop, dict) and isinstance(large_loop.get("stages"), list) else []
        for stage_index, stage in enumerate(hierarchy_stages):
            expected_scene_id = scene_by_source.get(stage.get("id")) if isinstance(stage, dict) else None
            small_loops = stage.get("smallLoops") if isinstance(stage, dict) and isinstance(stage.get("smallLoops"), list) else []
            for small_index, small_loop in enumerate(small_loops):
                steps = small_loop.get("steps") if isinstance(small_loop, dict) and isinstance(small_loop.get("steps"), list) else []
                for step_index, step in enumerate(steps):
                    if isinstance(step, dict):
                        path = f"loopHierarchy.largeLoops[{loop_index}].stages[{stage_index}].smallLoops[{small_index}].steps[{step_index}].evidence"
                        validate_evidence(step.get("evidence"), path, expected_scene_id)

    interaction = model.get("interaction") if isinstance(model.get("interaction"), dict) else {}
    component_states = interaction.get("componentStates") if isinstance(interaction.get("componentStates"), list) else []
    for index, item in enumerate(component_states):
        if not isinstance(item, dict) or item.get("componentId") not in component_ids:
            errors.append(f"interaction.componentStates[{index}].componentId must reference a component")
    return errors


def _validate_result(item: dict[str, Any], path: str, scene_ids: set[str], errors: list[str]) -> None:
    result_type = item.get("resultType")
    target = item.get("targetStageId")
    if result_type not in _RESULT_TYPES:
        errors.append(f"{path}.resultType is invalid")
        return
    if target is not None and target not in scene_ids:
        errors.append(f"{path}.targetStageId must reference a scene")
    if result_type in _TARGET_RESULT_TYPES:
        if target is None:
            errors.append(f"{path}.targetStageId is required for {result_type}")
    elif result_type == "terminal" and target is not None:
        errors.append(f"{path}.targetStageId must be null for terminal")
    elif result_type in {"state_change", "close_overlay"} and (
        item.get("resultState") is None or item.get("resultState") == ""
    ):
        errors.append(f"{path}.resultState is required for {result_type}")
