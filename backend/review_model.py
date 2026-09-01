from __future__ import annotations

import re
from copy import deepcopy
from math import isfinite
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


TRIGGER_TYPES = {
    "tap",
    "long_press",
    "swipe",
    "drag",
    "animation_end",
    "media_end",
    "timeout",
    "condition_met",
    "system_event",
    "unknown",
}
RESULT_TYPES = {
    "navigate",
    "state_change",
    "open_overlay",
    "close_overlay",
    "return",
    "loop",
    "terminal",
    "unknown",
}
FRAME_ROLES = {"entry", "change", "result"}
MATERIAL_ROLES = {"independent_page", "supplemental", "duplicate"}
COMPONENT_STATE_KEYS = ("default", "pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet")
RULE_DOMAIN_KEYS = ("narrative", "guidance", "redDots")
ACTIVE_REFERENCE_BOARD_KEYS = ("planning", "competitor")
_REPRESENTATIVE_ROLE_SEQUENCES = {1: ("entry",), 2: ("entry", "result"), 3: ("entry", "change", "result")}

_UNKNOWN = "待确认"
_UNKNOWN_VALUES = {"unknown", _UNKNOWN, "未知待确认"}
_TRIGGER_TYPE_TOKENS = (
    ("animation_end", ("animation end", "animation_end", "动画结束")),
    ("media_end", ("media end", "media_end", "媒体结束", "视频结束")),
    ("timeout", ("timeout", "等待", "超时", "延时", "秒后")),
    ("condition_met", ("condition met", "condition_met", "条件满足", "达成条件", "满足条件", "条件达成")),
    ("system_event", ("system", "automatic", "auto", "系统", "自动")),
    ("long_press", ("long press", "long_press", "长按")),
    ("swipe", ("swipe", "滑动")),
    ("drag", ("drag", "拖拽", "拖动")),
    ("tap", ("tap", "click", "点击", "点按")),
)
_RESULT_TYPES_REQUIRING_TARGET = {"navigate", "open_overlay", "return", "loop"}
_TIMEOUT_SECONDS_PATTERN = re.compile(r"\b(?:wait|delay|after)\s+\d+\s+seconds?\b")
_FUNCTION_STAGE_SUFFIX_PATTERN = re.compile(r"\s*[-—：:]?\s*(?:开始|持续|展开|结果|过程|阶段\s*\d+)\s*$", re.IGNORECASE)
_STATIC_ACTION_PATTERN = re.compile(
    r"无\s*操作\s*[（(]?\s*静态\s*展示\s*[）)]?"
    r"|(?:当前帧|截图|静态).*(?:静态展示|无操作|未捕捉|未检测)"
    r"|(?:无操作|未捕捉|未检测).*(?:点击|滑动|交互)"
)

_INTERACTION_DECISION_OPTIONS = [
    {"id": "tap", "label": "点击当前页面中的按钮或入口", "triggerType": "tap"},
    {"id": "swipe", "label": "滑动页面", "triggerType": "swipe"},
    {"id": "drag", "label": "拖动页面中的对象", "triggerType": "drag"},
    {"id": "system_event", "label": "满足条件后由系统自动触发", "triggerType": "system_event"},
]


def empty_rule_domains() -> dict[str, Any]:
    return {
        "narrative": [],
        "guidance": [],
        "redDots": [],
        "reviewedDomains": [],
        "confirmation": {"confirmed": False, "revision": None},
    }


def active_reference_boards() -> dict[str, Any]:
    return {
        "planning": {"source": "confirmed_review_model", "status": "generated"},
        "competitor": {"assets": [], "status": "pending"},
    }


def is_reference_asset_path(board_name: str, value: Any) -> bool:
    if board_name not in {"ux", "competitor"} or not isinstance(value, str) or not value or "\\" in value:
        return False
    posix_path, windows_path = PurePosixPath(value), PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive or windows_path.root:
        return False
    if value != posix_path.as_posix():
        return False
    parts = posix_path.parts
    if len(parts) != 3 or parts[:2] != ("reference_boards", board_name) or parts[2] in {"", ".", ".."}:
        return False
    filename = PureWindowsPath(parts[2])
    return filename.name == parts[2] and not filename.drive and not filename.root


def _is_unknown(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip() or value.strip().lower() in _UNKNOWN_VALUES


def _trigger_type(action: Any) -> str:
    if _is_unknown(action):
        return "unknown"
    label = action.strip().lower()
    if _TIMEOUT_SECONDS_PATTERN.search(label):
        return "timeout"
    for trigger_type, tokens in _TRIGGER_TYPE_TOKENS:
        if any(token in label for token in tokens):
            return trigger_type
    return "unknown"


def validate_representative_frames(frames: Any, sources: dict[str, Any]) -> str | None:
    if not isinstance(frames, list) or len(frames) not in _REPRESENTATIVE_ROLE_SEQUENCES:
        return "representative frames must contain one to three frames"
    frame_ids, roles = [], []
    for frame in frames:
        if not isinstance(frame, dict) or frame.get("frameId") not in sources or frame.get("role") not in FRAME_ROLES:
            return "invalid representative frames"
        frame_ids.append(frame["frameId"])
        roles.append(frame["role"])
    if len(set(frame_ids)) != len(frame_ids) or len(set(roles)) != len(roles):
        return "representative frame ids and roles must be unique"
    if tuple(roles) != _REPRESENTATIVE_ROLE_SEQUENCES[len(frames)]:
        return "representative frames must use entry, result, and change roles in order"
    return None


def representative_frames_for_ids(frame_ids: list[str]) -> list[dict[str, str]]:
    selected = frame_ids[:3]
    return [{"frameId": frame_id, "role": _REPRESENTATIVE_ROLE_SEQUENCES[len(selected)][index]} for index, frame_id in enumerate(selected)] if selected else []


_PLANNER_ENGLISH = (
    (r"\bBoss\b", "首领"), (r"\bLevel\s*Up\b", "升级"), (r"\bModal\b", "弹窗"),
    (r"\bGacha\b", "抽取"), (r"\bCrafting\b", "合成"), (r"\bUI\b", "界面"),
    (r"\bPassive\s*/\s*None\b", "系统自动触发"),
    (r"\bTrigger\s+Boss\s+Warning\s+Overlay\b", "显示首领来袭提示"),
    (r"\bRed\s+Vignette\b", "红色警示遮罩"), (r"\bWarning\s+Active\b", "警示状态生效"),
    (r"\bHigh\b", "高"), (r"\bMedium\b", "中"), (r"\bLow\b", "低"),
)


def _planner_visible_text(value: Any, fallback: str = _UNKNOWN) -> str:
    """Flatten model-shaped values and enforce Chinese planner-facing copy."""
    if isinstance(value, dict):
        ordered = [value.get(key) for key in ("description", "action", "details", "result", "status", "evidence")]
        parts = [_planner_visible_text(item, "") for item in ordered]
        text = "；".join(item for item in parts if item)
    elif isinstance(value, list):
        text = "；".join(item for item in (_planner_visible_text(entry, "") for entry in value) if item)
    else:
        text = str(value or "").strip()
    for pattern, replacement in _PLANNER_ENGLISH:
        text = re.sub(pattern, replacement, text, flags=re.I)
    text = re.sub(r"\b[A-Za-z][A-Za-z\s/_-]*\b", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[，,；;。]\s*[，,；;。]+", "；", text).strip(" ，,；;。:：'‘’\"“”?!？！（）()")
    if not re.search(r"[\w\u4e00-\u9fff]", text):
        text = ""
    return text or fallback


def sanitize_review_planner_copy(model: dict[str, Any]) -> dict[str, Any]:
    """Apply the Chinese-only planner contract to every user-visible review field."""
    for stage in model.get("stages") or []:
        for field in ("name", "objective", "entryCondition", "exitCondition"):
            stage[field] = _planner_visible_text(stage.get(field))
        loop = stage.get("smallLoop") if isinstance(stage.get("smallLoop"), dict) else {}
        for field in ("display", "trigger", "feedback", "result", "retry"):
            loop[field] = _planner_visible_text(loop.get(field))
        stage["smallLoop"] = loop
    for transition in model.get("transitions") or []:
        for field in ("triggerLabel", "condition", "response", "resultState", "sourceLevel", "confidence"):
            transition[field] = _planner_visible_text(transition.get(field), "低" if field == "confidence" else _UNKNOWN)
    return model


def _planner_stage_name(index: int, analysis: dict[str, Any]) -> str:
    title = str(analysis.get("title") or "").strip()
    evidence = " ".join(str(analysis.get(key) or "") for key in ("title", "objective", "summary", "what", "userAction", "systemResponse", "afterState")).lower()
    if ("boss" in evidence or "首领" in evidence) and any(word in evidence for word in ("攻击", "战斗", "闪电")):
        return "操控角色攻击首领"
    routes = (
        (("weapon", "upgrade", "select weapon", "武器", "强化", "三选一", "升级", "词条"), "选择武器强化", 2),
        (("boss", "warning", "首领", "警告"), "查看首领战提示", 2),
        (("glossary", "term", "unlock", "词条", "解锁"), "查看新解锁内容", 2),
        (("battle", "combat", "战斗", "伤害", "敌人"), "持续战斗并击退敌人", 1),
    )
    for (keywords, label, minimum) in routes:
        if sum(keyword in evidence for keyword in keywords) >= minimum:
            return label
    unknown_values = {"", "待确认", "未知待确认", "unknown", "需要配置视觉模型后识别"}
    action = str(analysis.get("userAction") or "").strip()
    if action.casefold() not in unknown_values:
        action = re.sub(r"（[^）]*）|\([^)]*\)", "", action).replace("Boss", "首领").replace("boss", "首领")
        action = re.split(r"[，。；：]", action, maxsplit=1)[0].strip()
        if action:
            return action[:17] + ("…" if len(action) > 17 else "")
    if title and not re.fullmatch(r"(?:场景|环节|页面|scene|stage)\s*\d+", title, re.IGNORECASE):
        concise = re.split(r"[，。；：]", re.sub(r"（[^）]*）|\([^)]*\)", "", title), maxsplit=1)[0].strip()
        if concise:
            return concise[:17] + ("…" if len(concise) > 17 else "")
    return "查看当前状态并继续操作"


def _stage(index: int, scene: dict[str, Any]) -> dict[str, Any]:
    analysis = scene.get("analysis") or {}
    frame_ids = list(scene.get("frameIds") or [])
    representatives = representative_frames_for_ids(frame_ids)
    return sanitize_review_planner_copy({
        "id": f"STG-{index:03d}",
        "sourceSceneId": scene.get("id"),
        "order": index,
        "name": _planner_stage_name(index, analysis),
        "objective": _planner_visible_text(analysis.get("objective")),
        "entryCondition": _planner_visible_text(analysis.get("entryCondition")),
        "exitCondition": _planner_visible_text(analysis.get("exitCondition")),
        "terminal": False,
        "representativeFrames": representatives,
        "regionIds": [],
        "transitionIds": [],
        "smallLoop": {
            "display": _UNKNOWN,
            "trigger": _UNKNOWN,
            "feedback": _UNKNOWN,
            "result": _UNKNOWN,
            "retry": _UNKNOWN,
        },
        "confirmation": {"confirmed": False, "revision": None},
        "unknowns": [],
    })


def _functional_stage_name(stage: dict[str, Any]) -> str:
    name = str(stage.get("name") or "").strip()
    compact = _FUNCTION_STAGE_SUFFIX_PATTERN.sub("", name).strip()
    return compact or name


def _merge_generated_stage_group(group: list[dict[str, Any]], order: int) -> dict[str, Any]:
    generic_names = {"查看当前状态并继续操作", "待确认", "未知待确认", ""}
    representative = max(group, key=lambda stage: (
        str(stage.get("name") or "").strip() not in generic_names,
        len(str(stage.get("name") or "").strip()),
    ))
    merged = deepcopy(representative)
    frame_ids = []
    for stage in group:
        for frame in stage.get("representativeFrames") or []:
            frame_id = frame.get("frameId")
            if frame_id and frame_id not in frame_ids:
                frame_ids.append(frame_id)
    merged.update({
        "id": f"STG-{order:03d}",
        "order": order,
        "name": _functional_stage_name(representative) if len(group) > 1 else representative["name"],
        "sourceSceneId": representative.get("sourceSceneId"),
        "sourceSceneIds": [stage.get("sourceSceneId") for stage in group if stage.get("sourceSceneId") is not None],
        "representativeFrames": representative_frames_for_ids(
            frame_ids if len(frame_ids) <= 3 else [frame_ids[0], frame_ids[len(frame_ids) // 2], frame_ids[-1]]
        ),
        "regionIds": [],
        "transitionIds": [],
    })
    return merged


def compact_generated_stages(stages: list[dict[str, Any]], minimum: int = 3, maximum: int = 7) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for stage in stages:
        if groups and _functional_stage_name(groups[-1][-1]).casefold() == _functional_stage_name(stage).casefold():
            groups[-1].append(stage)
        else:
            groups.append([stage])
    while len(groups) > maximum and len(groups) > minimum:
        merge_index = next((
            index for index in range(len(groups) - 1)
            if _functional_stage_name(groups[index][-1]).lower() == _functional_stage_name(groups[index + 1][0]).lower()
        ), None)
        if merge_index is None:
            merge_index = min(range(len(groups) - 1), key=lambda index: len(groups[index]) + len(groups[index + 1]))
        groups[merge_index:merge_index + 2] = [groups[merge_index] + groups[merge_index + 1]]
    return [_merge_generated_stage_group(group, index) for index, group in enumerate(groups, 1)]


def build_review_model(job: dict[str, Any]) -> dict[str, Any]:
    stages = [_stage(index, scene) for index, scene in enumerate(job.get("scenes") or [], 1)]
    stages = compact_generated_stages(stages)
    transitions = []
    frame_by_id = {frame["id"]: frame for frame in job.get("frames") or []}
    for stage_index, stage in enumerate(stages):
        representatives = stage["representativeFrames"]
        frame = frame_by_id.get(representatives[0]["frameId"]) if representatives else None
        if not frame:
            continue
        analysis = frame.get("analysis") or {}
        target = stages[stage_index + 1]["id"] if stage_index + 1 < len(stages) else None
        transition = {
            "id": f"TRN-{len(transitions) + 1:03d}",
            "sourceStageId": stage["id"],
            "targetStageId": target,
            "triggerType": _trigger_type(analysis.get("userAction")),
            "triggerLabel": _planner_visible_text(analysis.get("userAction")),
            "componentId": None,
            "sourceFrameId": frame["id"],
            "anchor": None,
            "condition": _planner_visible_text(analysis.get("beforeState")),
            "response": _planner_visible_text(analysis.get("systemResponse")),
            "resultType": "navigate" if target else "terminal",
            "resultState": _planner_visible_text(analysis.get("afterState")),
            "trueBranchTargetId": target,
            "falseBranchTargetId": None,
            "primary": True,
            "included": True,
            "sourceLevel": _planner_visible_text(analysis.get("evidenceLevel")),
            "confidence": _planner_visible_text(analysis.get("confidence"), "低"),
            "confirmation": {"confirmed": False, "revision": None},
        }
        transitions.append(transition)
        stage["transitionIds"].append(transition["id"])
    scene_by_frame = {
        frame_id: scene.get("id")
        for scene in job.get("scenes") or []
        for frame_id in scene.get("frameIds") or []
    }
    stage_by_scene = {
        scene_id: stage
        for stage in stages
        for scene_id in (stage.get("sourceSceneIds") or [stage.get("sourceSceneId")])
        if scene_id is not None
    }
    sources = {}
    first_frame_by_image: dict[str, str] = {}
    for frame in job.get("frames") or []:
        stage = stage_by_scene.get(frame.get("sceneId", scene_by_frame.get(frame.get("id"))))
        analysis = frame.get("analysis") or {}
        image_key = str(frame.get("imageUrl") or "").strip()
        duplicate_of = first_frame_by_image.get(image_key) if image_key else None
        if image_key and not duplicate_of:
            first_frame_by_image[image_key] = frame["id"]
        prior_stage_frames = stage.get("sourceFrameIds") or [] if stage else []
        material_role = "duplicate" if duplicate_of else ("independent_page" if not prior_stage_frames else "supplemental")
        source = {
            "sourceType": job.get("metadata", {}).get("inputType", "video"),
            "sourceName": frame.get("sourceName"),
            "sequenceIndex": frame.get("sequenceIndex"),
            "imageUrl": frame.get("imageUrl"),
            "stageId": stage.get("id") if stage else None,
            "materialRole": material_role,
            "pageInfo": {
                "purpose": _planner_visible_text(analysis.get("what"), _UNKNOWN),
                "before": _planner_visible_text(analysis.get("beforeState"), _UNKNOWN),
                "action": _planner_visible_text(analysis.get("userAction"), _UNKNOWN),
                "feedback": _planner_visible_text(analysis.get("systemResponse"), _UNKNOWN),
                "result": _planner_visible_text(analysis.get("afterState"), _UNKNOWN),
            },
            "secondaryInformation": _secondary_information(frame),
        }
        if duplicate_of:
            source["duplicateOf"] = duplicate_of
        if stage:
            stage.setdefault("sourceFrameIds", []).append(frame["id"])
        if frame.get("supplementalEvidence"):
            source["supplementalEvidence"] = deepcopy(frame["supplementalEvidence"])
        if dimensions := _source_dimensions(frame.get("structure") or {}):
            source["width"], source["height"] = dimensions
        sources[frame["id"]] = source
    model = {
        "schemaVersion": "2.0",
        "standard": "GVE16",
        "revision": 1,
        "jobId": job.get("id"),
        "sources": sources,
        "stages": stages,
        "transitions": transitions,
        "regions": [],
        "components": [],
        "componentStates": [],
        "crossStateConstraints": [],
        "referenceBoards": active_reference_boards(),
        "reviewState": {
            "status": "ai_draft",
            "flowConfirmed": False,
            "confirmedStageIds": [],
            "previewRevision": None,
        },
        "editHistory": {"undo": [], "redo": []},
    }
    _backfill_interaction_decision_cards(model)
    return model


def _meaningful(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and not any(marker in text for marker in _UNKNOWN_VALUES)


def _normalized_bounds(element: dict[str, Any], width: float, height: float) -> dict[str, float] | None:
    bbox = element.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        left, top, right, bottom = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return None
    if not all(isfinite(value) for value in (left, top, right, bottom)):
        return None
    left, right = max(0.0, min(left, width)), max(0.0, min(right, width))
    top, bottom = max(0.0, min(top, height)), max(0.0, min(bottom, height))
    if left >= right or top >= bottom:
        return None
    return {
        "x": left / width,
        "y": top / height,
        "width": (right - left) / width,
        "height": (bottom - top) / height,
    }


def _salient_elements(elements: list[dict[str, Any]], width: float, height: float) -> list[dict[str, Any]]:
    candidates = []
    for element in elements:
        bounds = _normalized_bounds(element, width, height)
        if bounds is None:
            continue
        area = bounds["width"] * bounds["height"]
        generic = str(element.get("class") or "").lower() in {"", "component", "unknown", "region"}
        if generic and area < 0.005:
            continue
        candidates.append((area, element))
    return [element for _area, element in sorted(candidates, key=lambda item: item[0], reverse=True)[:12]]


def _secondary_information(frame: dict[str, Any]) -> list[str]:
    groups = (
        ("等级", ("level", "lv", "等级")),
        ("武器槽", ("weapon", "slot", "武器", "槽位")),
        ("资源", ("resource", "currency", "coin", "gem", "金币", "钻石", "资源")),
        ("状态", ("status", "health", "hp", "time", "progress", "生命", "血量", "时间", "进度")),
    )
    results: list[str] = []
    for element in (frame.get("structure") or {}).get("elements") or []:
        if not isinstance(element, dict):
            continue
        raw = " ".join(str(element.get(key) or "") for key in ("class", "name", "text", "label", "value")).strip()
        lowered = raw.casefold()
        category = next((label for label, tokens in groups if any(token.casefold() in lowered for token in tokens)), None)
        if not category:
            continue
        visible = str(element.get("text") or element.get("label") or element.get("name") or element.get("value") or element.get("class") or "").strip()
        item = f"{category}：{visible}" if visible else category
        if item not in results:
            results.append(item)
    analysis = frame.get("analysis") or {}
    analysis_text = " ".join(
        str(analysis.get(key) or "")
        for key in ("what", "userAction", "systemResponse", "afterState", "motion")
    ).casefold()
    fallback_copy = {
        "等级": "等级：画面包含等级信息",
        "武器槽": "武器槽：画面包含武器或技能栏信息",
        "资源": "资源：画面包含资源数量信息",
        "状态": "状态：画面包含生命、时间或进度信息",
    }
    for label, tokens in groups:
        item = fallback_copy[label]
        if any(token.casefold() in analysis_text for token in tokens) and not any(value.startswith(f"{label}：") for value in results):
            results.append(item)
    return results


def _quality(model: dict[str, Any]) -> dict[str, Any]:
    qualified_stages = sum(
        1
        for stage in model.get("stages") or []
        if _meaningful(stage.get("name"))
        and (
            any(_meaningful(value) for value in (stage.get("smallLoop") or {}).values())
            or (
                (stage.get("confirmation") or {}).get("confirmed") is True
                and _meaningful(stage.get("objective"))
                and bool(stage.get("representativeFrames"))
            )
        )
    )
    transitions = model.get("transitions") or []
    return {
        "qualified": qualified_stages > 0,
        "blockers": [] if qualified_stages > 0 else ["NO_QUALIFIED_STAGE"],
        "candidateTransitionCount": sum(
            transition.get("targetBasis") == "sequence_candidate" for transition in transitions
        ),
        "stageCount": len(model.get("stages") or []),
    }


def _backfill_review_metadata(model: dict[str, Any]) -> None:
    stage_by_id = {stage.get("id"): stage for stage in model.get("stages") or []}
    for transition in model.get("transitions") or []:
        if transition.get("targetBasis"):
            continue
        source = stage_by_id.get(transition.get("sourceStageId"))
        target = stage_by_id.get(transition.get("targetStageId"))
        if not transition.get("targetStageId"):
            transition["targetBasis"] = "sequence_end"
        elif source and target and target.get("order") == source.get("order", 0) + 1:
            transition["targetBasis"] = "sequence_candidate"
        else:
            transition["targetBasis"] = "visual"
    _backfill_transition_groups(model)
    model["quality"] = _quality(model)


def _backfill_interaction_decision_cards(model: dict[str, Any]) -> None:
    """Turn unproven screenshot actions into planner decisions, never 'no action'."""
    cards = model.setdefault("interactionDecisionCards", [])
    card_by_transition = {
        card.get("transitionId"): card for card in cards
        if isinstance(card, dict) and card.get("transitionId")
    }
    stage_by_id = {stage.get("id"): stage for stage in model.get("stages") or []}
    for transition in model.get("transitions") or []:
        human_fields = set(transition.get("humanEditedFields") or [])
        label = str(transition.get("triggerLabel") or "").strip()
        if "triggerLabel" not in human_fields and _STATIC_ACTION_PATTERN.search(label):
            transition["triggerLabel"] = _UNKNOWN
            transition["triggerType"] = "unknown"
        is_unknown = transition.get("triggerType") == "unknown" or _is_unknown(transition.get("triggerLabel"))
        existing = card_by_transition.get(transition.get("id"))
        if not is_unknown or not transition.get("included", True):
            if existing and existing.get("status") != "resolved":
                existing["status"] = "obsolete"
            continue
        if existing:
            continue
        source = stage_by_id.get(transition.get("sourceStageId")) or {}
        target = stage_by_id.get(transition.get("targetStageId")) or {}
        cards.append({
            "id": f"IDC-{len(cards) + 1:03d}",
            "transitionId": transition.get("id"),
            "question": f"从“{source.get('name') or '当前页面'}”进入“{target.get('name') or '下一状态'}”时，实际由什么操作或事件触发？",
            "selectionMode": "single",
            "options": deepcopy(_INTERACTION_DECISION_OPTIONS),
            "allowCustom": True,
            "evidenceFrameIds": [transition.get("sourceFrameId")] if transition.get("sourceFrameId") else [],
            "impacts": ["交互流程", "策划草图", "玩法规则", "最终文档"],
            "status": "pending",
        })
    for stage in model.get("stages") or []:
        loop = stage.get("smallLoop") if isinstance(stage.get("smallLoop"), dict) else {}
        if "smallLoop" not in set(stage.get("humanEditedFields") or []) and _STATIC_ACTION_PATTERN.search(str(loop.get("trigger") or "")):
            loop["trigger"] = _UNKNOWN
    for source in (model.get("sources") or {}).values():
        page = source.get("pageInfo") if isinstance(source, dict) and isinstance(source.get("pageInfo"), dict) else {}
        human_fields = set(source.get("humanEditedFields") or []) if isinstance(source, dict) else set()
        if "pageInfo.action" not in human_fields and _STATIC_ACTION_PATTERN.search(str(page.get("action") or "")):
            page["action"] = _UNKNOWN


def _backfill_transition_groups(model: dict[str, Any]) -> None:
    """Remove exact generated duplicates and mark genuine alternatives as one choice."""
    by_source: dict[str, list[dict[str, Any]]] = {}
    for transition in model.get("transitions") or []:
        transition.pop("duplicateOf", None)
        transition.pop("choiceGroupId", None)
        transition.pop("choiceMode", None)
        by_source.setdefault(str(transition.get("sourceStageId") or ""), []).append(transition)
    for source_id, transitions in by_source.items():
        unique: list[dict[str, Any]] = []
        signatures: dict[tuple[Any, ...], dict[str, Any]] = {}
        for transition in transitions:
            signature = tuple(transition.get(field) for field in (
                "targetStageId", "triggerType", "triggerLabel", "componentId", "regionId", "condition", "response", "resultType", "resultState"
            ))
            original = signatures.get(signature)
            if original:
                transition["duplicateOf"] = original.get("id")
                if not transition.get("humanEditedFields"):
                    transition["included"] = False
                continue
            signatures[signature] = transition
            unique.append(transition)
        if len(unique) > 1:
            group_id = f"CHOICE-{source_id}"
            for transition in unique:
                transition["choiceGroupId"] = group_id
                transition["choiceMode"] = "exclusive"


def _next_component_id(model: dict[str, Any]) -> str:
    existing = {item.get("id") for item in model.get("components") or []}
    number = 1
    while f"CMP-{number:04d}" in existing:
        number += 1
    return f"CMP-{number:04d}"


def _backfill_seeded_components(model: dict[str, Any]) -> None:
    components = model.setdefault("components", [])
    states = model.setdefault("componentStates", [])
    for region in model.get("regions") or []:
        if region.get("sourceType") != "model" or not _meaningful(region.get("name")):
            continue
        component = next((item for item in components if item.get("regionId") == region.get("id")), None)
        if not component:
            component = {"id": _next_component_id(model), "stageId": region.get("stageId"), "frameId": region.get("frameId"), "regionId": region.get("id"), "name": region.get("name"), "bounds": region.get("bounds"), "sourceType": "model"}
            components.append(component)
        state = next((item for item in states if item.get("componentId") == component["id"]), None)
        if state:
            state["states"] = {key: str((state.get("states") or {}).get(key) or "unknown") for key in COMPONENT_STATE_KEYS}
        else:
            states.append({"id": f"CST-{len(states) + 1:03d}", "componentId": component["id"], "states": {key: "unknown" for key in COMPONENT_STATE_KEYS}})


def _backfill_region_numbers(model: dict[str, Any]) -> None:
    for stage in model.get("stages") or []:
        regions = [item for item in model.get("regions") or [] if item.get("stageId") == stage.get("id")]
        regions.sort(key=lambda item: (item.get("displayOrder", 0), item.get("id", "")))
        for index, region in enumerate(regions, 1):
            region["displayOrder"] = index
            region["displayNumber"] = index


def _source_dimensions(structure: dict[str, Any]) -> tuple[float, float] | None:
    try:
        width, height = float(structure.get("width")), float(structure.get("height"))
    except (TypeError, ValueError):
        return None
    return (width, height) if isfinite(width) and isfinite(height) and width > 0 and height > 0 else None


def _backfill_source_dimensions(model: dict[str, Any], job: dict[str, Any]) -> None:
    for frame in job.get("frames") or []:
        source = (model.get("sources") or {}).get(frame.get("id"))
        dimensions = _source_dimensions(frame.get("structure") or {})
        if source is not None and dimensions:
            source.setdefault("width", dimensions[0])
            source.setdefault("height", dimensions[1])


def _backfill_source_coverage(model: dict[str, Any], job: dict[str, Any]) -> None:
    stage_by_scene = {
        scene_id: stage
        for stage in model.get("stages") or []
        for scene_id in (stage.get("sourceSceneIds") or [stage.get("sourceSceneId")])
        if scene_id is not None
    }
    stage_by_representative = {
        frame.get("frameId"): stage
        for stage in model.get("stages") or []
        for frame in stage.get("representativeFrames") or []
    }
    for stage in model.get("stages") or []:
        stage["sourceFrameIds"] = []
    first_frame_by_image: dict[str, str] = {}
    for frame in job.get("frames") or []:
        source = (model.get("sources") or {}).get(frame.get("id"))
        if not isinstance(source, dict):
            continue
        stage = stage_by_scene.get(frame.get("sceneId")) or stage_by_representative.get(frame.get("id"))
        if stage is None and model.get("stages"):
            stage = model["stages"][0]
        image_key = str(frame.get("imageUrl") or source.get("imageUrl") or "").strip()
        duplicate_of = first_frame_by_image.get(image_key) if image_key else None
        if image_key and not duplicate_of:
            first_frame_by_image[image_key] = frame["id"]
        role = "duplicate" if duplicate_of else ("independent_page" if not stage.get("sourceFrameIds") else "supplemental")
        source["stageId"] = stage.get("id") if stage else None
        source["materialRole"] = role
        if duplicate_of:
            source["duplicateOf"] = duplicate_of
        else:
            source.pop("duplicateOf", None)
        analysis = frame.get("analysis") or {}
        previous_page = source.get("pageInfo") if isinstance(source.get("pageInfo"), dict) else {}
        page_info = {
            "purpose": _planner_visible_text(analysis.get("what"), _UNKNOWN),
            "before": _planner_visible_text(analysis.get("beforeState"), _UNKNOWN),
            "action": _planner_visible_text(analysis.get("userAction"), _UNKNOWN),
            "feedback": _planner_visible_text(analysis.get("systemResponse"), _UNKNOWN),
            "result": _planner_visible_text(analysis.get("afterState"), _UNKNOWN),
        }
        if "pageInfo.action" in (source.get("humanEditedFields") or []) and _meaningful(previous_page.get("action")):
            page_info["action"] = previous_page["action"]
        source["pageInfo"] = page_info
        source["secondaryInformation"] = _secondary_information(frame)
        if stage:
            stage["sourceFrameIds"].append(frame["id"])


def _backfill_active_reference_boards(model: dict[str, Any]) -> None:
    if "referenceBoards" not in model:
        model["referenceBoards"] = active_reference_boards()
        return
    boards = model["referenceBoards"]
    if not isinstance(boards, dict):
        return
    for key, default in active_reference_boards().items():
        boards.setdefault(key, default)


def ensure_review_model(job: dict[str, Any]) -> dict[str, Any]:
    if model := job.get("reviewModel"):
        _backfill_source_dimensions(model, job)
        _backfill_source_coverage(model, job)
        _backfill_active_reference_boards(model)
        _backfill_region_numbers(model)
        _backfill_seeded_components(model)
        _backfill_review_metadata(model)
        _backfill_interaction_decision_cards(model)
        return model

    model = build_review_model(job)
    _backfill_source_coverage(model, job)
    for frame in job.get("frames") or []:
        structure = frame.get("structure") or {}
        stage = next(
            (item for item in model["stages"] if item.get("sourceSceneId") == frame.get("sceneId")),
            None,
        )
        if not stage:
            continue
        analysis = frame.get("analysis") or {}
        representatives = stage.get("representativeFrames") or []
        if representatives and frame["id"] == representatives[0].get("frameId"):
            stage["smallLoop"] = {
                "display": analysis.get("what") or _UNKNOWN,
                "trigger": analysis.get("userAction") or _UNKNOWN,
                "feedback": analysis.get("systemResponse") or _UNKNOWN,
                "result": analysis.get("afterState") or _UNKNOWN,
                "retry": _UNKNOWN,
            }
        dimensions = _source_dimensions(structure)
        if not dimensions:
            continue
        width, height = dimensions
        for element in _salient_elements(structure.get("elements") or [], width, height):
            bounds = _normalized_bounds(element, width, height)
            if bounds is None:
                continue
            region_id = f"REG-{len(model['regions']) + 1:04d}"
            model["regions"].append(
                {
                    "id": region_id,
                    "stageId": stage["id"],
                    "frameId": frame["id"],
                    "name": element.get("class") or "region",
                    "bounds": bounds,
                    "displayOrder": len(stage["regionIds"]) + 1,
                    "displayNumber": None,
                    "sourceType": "model",
                    "primary": False,
                    "rule": {
                        "display": _UNKNOWN,
                        "condition": _UNKNOWN,
                        "action": _UNKNOWN,
                        "feedback": _UNKNOWN,
                        "result": _UNKNOWN,
                        "exception": _UNKNOWN,
                    },
                    "confirmation": {"confirmed": False},
                }
            )
            stage["regionIds"].append(region_id)
    _backfill_region_numbers(model)
    _backfill_seeded_components(model)
    _backfill_review_metadata(model)
    job["reviewModel"] = model
    return model


def _canonical_list(model: dict[str, Any], field: str, errors: list[str]) -> list[Any]:
    value = model.get(field)
    if not isinstance(value, list):
        errors.append(f"{field}: expected a list")
        return []
    return value


def _validate_normalized_bounds(bounds: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(bounds, dict):
        errors.append(f"{path}: expected an object")
        return False
    values: dict[str, float] = {}
    for field in ("x", "y", "width", "height"):
        value = bounds.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            errors.append(f"{path}.{field}: expected a finite normalized value")
        else:
            values[field] = float(value)
    if len(values) != 4:
        return False
    if (
        values["x"] < 0
        or values["y"] < 0
        or values["width"] <= 0
        or values["height"] <= 0
        or values["x"] + values["width"] > 1
        or values["y"] + values["height"] > 1
    ):
        errors.append(f"{path}: must stay within normalized bounds")
        return False
    return True


def _validate_normalized_point(point: Any, path: str, errors: list[str]) -> tuple[float, float] | None:
    if not isinstance(point, dict):
        errors.append(f"{path}: expected an object")
        return None
    values: dict[str, float] = {}
    for field in ("x", "y"):
        value = point.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            errors.append(f"{path}.{field}: expected a finite normalized value")
        else:
            values[field] = float(value)
    if len(values) != 2:
        return None
    if any(value < 0 or value > 1 for value in values.values()):
        errors.append(f"{path}: must stay within normalized bounds")
        return None
    return values["x"], values["y"]


def _validate_stage_owned_ids(
    stage: dict[str, Any],
    stage_path: str,
    field: str,
    owned_ids: set[str],
    entity_stage_by_id: dict[str, Any],
    errors: list[str],
) -> None:
    values = stage.get(field)
    if not isinstance(values, list):
        errors.append(f"{stage_path}.{field}: expected a list")
        return
    seen: set[str] = set()
    for index, entity_id in enumerate(values):
        path = f"{stage_path}.{field}[{index}]"
        if entity_id in seen:
            errors.append(f"{path}: duplicate id {entity_id!r}")
        seen.add(entity_id)
        if entity_id not in entity_stage_by_id:
            errors.append(f"{path}: unknown id {entity_id!r}")
        elif entity_stage_by_id[entity_id] != stage.get("id"):
            errors.append(f"{path}: does not belong to this stage")
    for entity_id in owned_ids - set(values):
        errors.append(f"{stage_path}.{field}: missing owned id {entity_id!r}")


NARRATIVE_FIELDS = ("title", "stageId", "triggerScene", "triggerNode", "presentation", "continuation")
GUIDANCE_FIELDS = ("title", "stageId", "scopeCount", "prerequisite", "steps", "destination")
RED_DOT_FIELDS = ("title", "stageId", "showCondition", "clearCondition", "path")


def _validate_rule_component(
    rule_id: str,
    component_id: Any,
    stage_id: Any,
    component_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    if component_id is None:
        return
    if not isinstance(component_id, str):
        errors.append(f"{rule_id}: expected string componentId")
        return
    component = component_by_id.get(component_id)
    if component is None:
        errors.append(f"{rule_id}: unknown componentId {component_id!r}")
    elif component.get("stageId") != stage_id:
        errors.append(f"{rule_id}: componentId {component_id!r} does not belong to stage {stage_id!r}")


def _validate_rule_path(
    rule_id: str,
    value: Any,
    field: str,
    stage_id: Any,
    component_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    if not isinstance(value, list):
        errors.append(f"{rule_id}: {field} expected a list")
        return
    nested_ids: set[str] = set()
    for index, item in enumerate(value):
        path = f"{rule_id}.{field}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path}: expected an object")
            continue
        nested_id = item.get("id")
        if not isinstance(nested_id, str) or not nested_id:
            errors.append(f"{path}.id: expected a stable non-empty id")
        elif nested_id in nested_ids:
            errors.append(f"{path}.id: duplicate id {nested_id!r}")
        else:
            nested_ids.add(nested_id)
        _validate_rule_component(rule_id, item.get("componentId"), stage_id, component_by_id, errors)


def _validate_rule_domains(
    model: dict[str, Any],
    stage_by_id: dict[str, dict[str, Any]],
    component_by_id: dict[str, dict[str, Any]],
    source_ids: set[str],
    errors: list[str],
) -> None:
    domains = model.get("ruleDomains")
    if not isinstance(domains, dict):
        errors.append("RULE_DOMAINS: expected an object")
        return
    definitions = (
        ("narrative", "NAR-", NARRATIVE_FIELDS, None),
        ("guidance", "GDE-", GUIDANCE_FIELDS, "steps"),
        ("redDots", "RDT-", RED_DOT_FIELDS, "path"),
    )
    rule_ids: set[str] = set()
    for domain, prefix, fields, nested_field in definitions:
        entries = domains.get(domain)
        if not isinstance(entries, list):
            errors.append(f"RULE_DOMAIN_{domain}: expected a list")
            continue
        for index, entry in enumerate(entries):
            path = f"RULE_DOMAIN_{domain}[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{path}: expected an object")
                continue
            rule_id = entry.get("id")
            if not isinstance(rule_id, str) or not rule_id.startswith(prefix):
                errors.append(f"{path}.id: expected a {prefix} id")
                rule_id = path
            elif rule_id in rule_ids:
                errors.append(f"{rule_id}: duplicate rule id")
            else:
                rule_ids.add(rule_id)
            for field in fields:
                value = entry.get(field)
                if field == nested_field:
                    continue
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{rule_id}: expected non-empty {field}")
            stage_id = entry.get("stageId")
            if not isinstance(stage_id, str):
                errors.append(f"{rule_id}: expected string stageId")
            elif stage_id not in stage_by_id:
                errors.append(f"{rule_id}: unknown stageId {stage_id!r}")
            frame_id = entry.get("frameId")
            if frame_id is not None:
                if not isinstance(frame_id, str):
                    errors.append(f"{rule_id}: expected string frameId")
                elif frame_id not in source_ids:
                    errors.append(f"{rule_id}: unknown frameId {frame_id!r}")
            _validate_rule_component(rule_id, entry.get("componentId"), stage_id, component_by_id, errors)
            if nested_field:
                _validate_rule_path(rule_id, entry.get(nested_field), nested_field, stage_id, component_by_id, errors)

    reviewed = domains.get("reviewedDomains")
    if not isinstance(reviewed, list):
        errors.append("RULE_DOMAIN_reviewedDomains: expected a list")
    elif any(domain not in RULE_DOMAIN_KEYS for domain in reviewed):
        errors.append("RULE_DOMAIN_reviewedDomains: contains an unknown domain")
    confirmation = domains.get("confirmation")
    if not isinstance(confirmation, dict) or not isinstance(confirmation.get("confirmed"), bool):
        errors.append("RULE_DOMAIN_confirmation: expected a confirmed flag")


def _validate_reference_boards(model: dict[str, Any], errors: list[str], *, include_legacy: bool) -> None:
    boards = model.get("referenceBoards")
    if not isinstance(boards, dict):
        errors.append("RULE_REFERENCE_BOARDS: expected an object")
        return
    board_names = ACTIVE_REFERENCE_BOARD_KEYS + (("ux",) if include_legacy and "ux" in boards else ())
    for board_name in board_names:
        board = boards.get(board_name)
        path = f"referenceBoards.{board_name}"
        if not isinstance(board, dict):
            errors.append(f"{path}: expected an object")
            continue
        if board_name == "planning":
            continue
        assets = board.get("assets")
        if not isinstance(assets, list):
            errors.append(f"{path}.assets: expected a list")
            continue
        asset_ids, asset_paths, asset_orders = set(), set(), set()
        asset_prefix = "UXA" if board_name == "ux" else "CPA"
        asset_numbers: list[int] = []
        for index, asset in enumerate(assets):
            asset_path = f"{path}.assets[{index}]"
            if not isinstance(asset, dict):
                errors.append(f"{asset_path}: expected an object")
                continue
            asset_id, value_path, order = asset.get("id"), asset.get("relativePath"), asset.get("order")
            if not isinstance(asset_id, str) or not asset_id:
                errors.append(f"{asset_path}.id: expected a non-empty string")
            elif asset_id in asset_ids:
                errors.append(f"{asset_path}: duplicate id {asset_id!r}")
            else:
                asset_ids.add(asset_id)
                match = re.fullmatch(rf"{asset_prefix}-(\d+)", asset_id)
                if match:
                    asset_numbers.append(int(match.group(1)))
            if not is_reference_asset_path(board_name, value_path):
                errors.append(f"{asset_path}.relativePath: expected canonical board-relative path")
            elif value_path in asset_paths:
                errors.append(f"{asset_path}: duplicate relativePath {value_path!r}")
            else:
                asset_paths.add(value_path)
            if type(order) is not int or order < 1:
                errors.append(f"{asset_path}.order: expected a positive integer")
            elif order in asset_orders:
                errors.append(f"{asset_path}: duplicate order {order}")
            else:
                asset_orders.add(order)
        high_water = board.get("assetIdHighWater")
        if high_water is not None and (type(high_water) is not int or high_water < max(asset_numbers, default=0)):
            errors.append(f"{path}.assetIdHighWater: expected a non-negative integer at least the asset id maximum")


def validate_review_model(model: dict[str, Any], *, include_legacy: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(model, dict):
        return ["model: expected an object"]
    if model.get("schemaVersion") != "2.0":
        errors.append("schemaVersion: expected '2.0'")
    if model.get("standard") != "GVE16":
        errors.append("standard: expected 'GVE16'")
    if type(model.get("revision")) is not int or model["revision"] < 1:
        errors.append("revision: expected a positive integer")
    if not isinstance(model.get("jobId"), str) or not model["jobId"].strip():
        errors.append("jobId: expected a non-empty string")

    sources = model.get("sources")
    if not isinstance(sources, dict):
        errors.append("sources: expected an object")
        sources = {}
    source_ids = {source_id for source_id in sources if isinstance(source_id, str) and source_id}
    for source_id in sources:
        if source_id not in source_ids:
            errors.append("sources: source ids must be non-empty strings")

    collection_names = ("stages", "regions", "components", "componentStates", "transitions", "crossStateConstraints")
    collections = {name: _canonical_list(model, name, errors) for name in collection_names}
    entity_locations: dict[str, tuple[str, int]] = {}
    entity_maps: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in collection_names}
    for name, items in collections.items():
        for index, item in enumerate(items):
            path = f"{name}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path}: expected an object")
                continue
            entity_id = item.get("id")
            if not isinstance(entity_id, str) or not entity_id:
                errors.append(f"{path}.id: expected a non-empty string")
                continue
            if previous := entity_locations.get(entity_id):
                errors.append(f"{path}.id: duplicates {previous[0]}[{previous[1]}].id {entity_id!r}")
                continue
            entity_locations[entity_id] = (name, index)
            entity_maps[name][entity_id] = item

    stages = collections["stages"]
    stage_by_id = entity_maps["stages"]
    stage_frames: dict[str, set[str]] = {}
    orders: set[int] = set()
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        stage_id = stage.get("id")
        order = stage.get("order")
        if type(order) is not int or order < 1:
            errors.append(f"{stage_id}: invalid order")
        elif order in orders:
            errors.append(f"{stage_id}: duplicate order")
        else:
            orders.add(order)
        if error := validate_representative_frames(stage.get("representativeFrames"), sources):
            errors.append(f"{stage_id}: {error}")
        else:
            stage_frames[stage_id] = {frame["frameId"] for frame in stage["representativeFrames"]}

    covered_sources: list[str] = []
    for source_id, source in sources.items():
        if not isinstance(source, dict):
            errors.append(f"sources.{source_id}: expected an object")
            continue
        if source.get("materialRole") not in MATERIAL_ROLES:
            errors.append(f"sources.{source_id}.materialRole: explicit classification required")
        if source.get("stageId") not in stage_by_id:
            errors.append(f"sources.{source_id}.stageId: unknown stage {source.get('stageId')!r}")
    for stage in stages:
        frame_ids = stage.get("sourceFrameIds")
        if not isinstance(frame_ids, list) or not frame_ids:
            errors.append(f"{stage.get('id')}: sourceFrameIds must cover the page material")
            continue
        covered_sources.extend(frame_ids)
    if sorted(covered_sources) != sorted(source_ids):
        errors.append("sources: every screenshot must belong to exactly one page")

    regions = collections["regions"]
    region_by_id = entity_maps["regions"]
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            continue
        path, stage_id, frame_id = f"regions[{index}]", region.get("stageId"), region.get("frameId")
        if stage_id not in stage_by_id:
            errors.append(f"{path}.stageId: unknown stage {stage_id!r}")
        if frame_id not in source_ids:
            errors.append(f"{path}.frameId: unknown source {frame_id!r}")
        elif stage_id in stage_by_id and frame_id not in stage_frames.get(stage_id, set()):
            errors.append(f"{path}.frameId: does not belong to stage {stage_id!r}")
        _validate_normalized_bounds(region.get("bounds"), f"{path}.bounds", errors)

    components = collections["components"]
    component_by_id = entity_maps["components"]
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            continue
        path, stage_id, region_id = f"components[{index}]", component.get("stageId"), component.get("regionId")
        if stage_id not in stage_by_id:
            errors.append(f"{path}.stageId: unknown stage {stage_id!r}")
        region = region_by_id.get(region_id)
        if region is None:
            errors.append(f"{path}.regionId: unknown region {region_id!r}")
            continue
        if stage_id != region.get("stageId"):
            errors.append(f"{path}.stageId: does not match region {region_id!r}")
        frame_id = component.get("frameId")
        if frame_id != region.get("frameId"):
            errors.append(f"{path}.frameId: does not match region {region_id!r}")
        if frame_id not in source_ids:
            errors.append(f"{path}.frameId: unknown source {frame_id!r}")
        if component.get("bounds") is not None:
            _validate_normalized_bounds(component["bounds"], f"{path}.bounds", errors)

    states_by_component: dict[str, list[int]] = {}
    for index, state in enumerate(collections["componentStates"]):
        if not isinstance(state, dict):
            continue
        path, component_id = f"componentStates[{index}]", state.get("componentId")
        if component_id not in component_by_id:
            errors.append(f"{path}.componentId: unknown component {component_id!r}")
            continue
        states_by_component.setdefault(component_id, []).append(index)
        values = state.get("states")
        if not isinstance(values, dict):
            errors.append(f"{path}.states: expected an object")
            continue
        missing = [key for key in COMPONENT_STATE_KEYS if key not in values]
        if missing:
            errors.append(f"{path}.states: missing required slots {', '.join(missing)}")
    for component_id, indexes in states_by_component.items():
        for index in indexes[1:]:
            errors.append(f"componentStates[{index}].componentId: duplicate state record for component {component_id!r}")
    for component_id, (_, index) in ((key, entity_locations[key]) for key in component_by_id):
        if component_id not in states_by_component:
            errors.append(f"components[{index}].componentState: missing state slots")

    transitions = collections["transitions"]
    transition_by_id = entity_maps["transitions"]
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            continue
        path, transition_id = f"transitions[{index}]", transition.get("id")
        source_stage_id = transition.get("sourceStageId")
        if source_stage_id not in stage_by_id:
            errors.append(f"{transition_id}: invalid sourceStageId")
        for field in ("targetStageId", "trueBranchTargetId", "falseBranchTargetId"):
            target_stage_id = transition.get(field)
            if field == "targetStageId" and transition.get("resultType") in _RESULT_TYPES_REQUIRING_TARGET and not target_stage_id:
                errors.append(f"{transition_id}: missing targetStageId")
            elif target_stage_id and target_stage_id not in stage_by_id:
                if field == "targetStageId":
                    errors.append(f"{transition_id}: invalid targetStageId")
                errors.append(f"{path}.{field}: unknown stage {target_stage_id!r}")
        if transition.get("triggerType") not in TRIGGER_TYPES:
            errors.append(f"{transition_id}: invalid triggerType")
        if transition.get("resultType") not in RESULT_TYPES:
            errors.append(f"{transition_id}: invalid resultType")
        source_frame_id = transition.get("sourceFrameId")
        if source_frame_id not in source_ids:
            errors.append(f"{transition_id}: invalid sourceFrameId")
        elif source_stage_id in stage_by_id and source_frame_id not in stage_frames.get(source_stage_id, set()):
            errors.append(f"{path}.sourceFrameId: does not belong to stage {source_stage_id!r}")

        component_id, region_id = transition.get("componentId"), transition.get("regionId")
        component = component_by_id.get(component_id) if component_id else None
        if component_id and component is None:
            errors.append(f"{transition_id}: invalid componentId")
        region = region_by_id.get(region_id) if region_id else None
        if region_id and region is None:
            errors.append(f"{path}.regionId: unknown region {region_id!r}")
        if component and region_id and component.get("regionId") != region_id:
            errors.append(f"{path}.regionId: does not match component {component_id!r}")
        binding = component or region
        if binding and binding.get("stageId") != source_stage_id:
            errors.append(f"{path}.{('componentId' if component else 'regionId')}: does not belong to source stage")
        if binding and binding.get("frameId") != source_frame_id:
            errors.append(f"{path}.{('componentId' if component else 'regionId')}: frame does not match sourceFrameId")
        anchor = transition.get("anchor")
        if anchor is not None:
            if transition.get("triggerType") not in {"tap", "long_press"}:
                errors.append(f"{transition_id}: automatic transition cannot have anchor")
            if not binding:
                errors.append(f"{path}.anchor: requires a componentId or regionId")
            else:
                point = _validate_normalized_point(anchor, f"{path}.anchor", errors)
                bounds = binding.get("bounds") or (region or {}).get("bounds")
                if point and isinstance(bounds, dict) and all(isinstance(bounds.get(key), (int, float)) for key in ("x", "y", "width", "height")):
                    x, y = point
                    if not (bounds["x"] <= x <= bounds["x"] + bounds["width"] and bounds["y"] <= y <= bounds["y"] + bounds["height"]):
                        errors.append(f"{path}.anchor: must stay within bound region")

    region_stage_by_id = {entity_id: item.get("stageId") for entity_id, item in region_by_id.items()}
    transition_stage_by_id = {entity_id: item.get("sourceStageId") for entity_id, item in transition_by_id.items()}
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict) or stage.get("id") not in stage_by_id:
            continue
        stage_id = stage["id"]
        _validate_stage_owned_ids(stage, f"stages[{index}]", "regionIds", {item_id for item_id, owner in region_stage_by_id.items() if owner == stage_id}, region_stage_by_id, errors)
        _validate_stage_owned_ids(stage, f"stages[{index}]", "transitionIds", {item_id for item_id, owner in transition_stage_by_id.items() if owner == stage_id}, transition_stage_by_id, errors)
    if include_legacy and "ruleDomains" in model:
        _validate_rule_domains(model, stage_by_id, component_by_id, source_ids, errors)
    _validate_reference_boards(model, errors, include_legacy=include_legacy)
    return errors


def _stage_has_core_unknown(stage: dict[str, Any], source_ids: set[str]) -> bool:
    if any(_is_unknown(stage.get(field)) for field in ("name", "objective", "entryCondition", "exitCondition")):
        return True
    small_loop = stage.get("smallLoop")
    if not isinstance(small_loop, dict) or any(
        _is_unknown(small_loop.get(field)) for field in ("display", "trigger", "feedback", "result")
    ):
        return True
    return False


def _included_transition_has_core_unknown(transition: dict[str, Any]) -> bool:
    return (
        transition.get("triggerType") == "unknown"
        or transition.get("resultType") == "unknown"
        or any(
            _is_unknown(transition.get(field))
            for field in ("sourceStageId", "sourceFrameId", "triggerLabel", "condition", "response", "resultState")
        )
    )


def review_gate(model: dict[str, Any]) -> dict[str, Any]:
    blockers, warnings = validate_review_model(model, include_legacy=False), []
    if not model.get("reviewState", {}).get("flowConfirmed"):
        blockers.append("FLOW_NOT_CONFIRMED")
    source_ids = set((model.get("sources") or {}).keys())
    for stage in model.get("stages") or []:
        stage_id = stage.get("id") or "STAGE_INVALID"
        if not stage.get("confirmation", {}).get("confirmed"):
            blockers.append(stage_id)
        if validate_representative_frames(stage.get("representativeFrames"), {source_id: {} for source_id in source_ids}) is not None:
            blockers.append(stage_id)
        elif _stage_has_core_unknown(stage, source_ids):
            if stage.get("confirmation", {}).get("confirmed"):
                warnings.append(f"{stage_id}_PENDING_DETAILS")
            else:
                blockers.append(stage_id)
    for transition in model.get("transitions") or []:
        if not transition.get("included"):
            continue
        transition_id = transition.get("id") or "TRANSITION_INVALID"
        structural_unknown = any(
            _is_unknown(transition.get(field))
            for field in ("sourceStageId", "sourceFrameId", "resultType")
        )
        if not transition.get("confirmation", {}).get("confirmed") or structural_unknown:
            blockers.append(transition_id)
        elif _included_transition_has_core_unknown(transition):
            warnings.append(f"{transition_id}_PENDING_DETAILS")
    for item in model.get("crossStateConstraints") or []:
        if item.get("status") != "unknown":
            continue
        if item.get("severity") == "core":
            blockers.append(item.get("id") or "CONSTRAINT_INVALID")
        elif item.get("severity") == "non_core":
            warnings.append(item["id"])
    return {
        "exportReady": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": warnings,
    }
