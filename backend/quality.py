from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


UNKNOWN = {None, "", "未知待确认", "unknown"}


def _is_unknown(value: Any) -> bool:
    if isinstance(value, (dict, list, tuple, set)):
        return not value
    return value in UNKNOWN


def reconcile_and_audit(job: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    frames = job.get("frames", [])
    scenes = job.get("scenes", [])
    review: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    uncertain_scenes: set[int] = set()
    warning_groups: set[tuple[int, str]] = set()

    for frame in frames:
        analysis = frame.get("analysis", {})
        evidence = analysis.get("evidenceLevel", "未知待确认")
        confidence = analysis.get("confidence", "低")
        facts.append({
            "frameId": frame["id"], "sceneId": frame["sceneId"], "timestamp": frame["timestamp"],
            "state": analysis.get("gameState") or analysis.get("afterState") or analysis.get("what"),
            "action": analysis.get("userAction"), "response": analysis.get("systemResponse"),
            "evidenceLevel": evidence, "confidence": confidence,
        })
        if (evidence != "明确展示" or confidence == "低") and frame["sceneId"] not in uncertain_scenes:
            review.append(_item("uncertain", "需确认的低置信度结论", frame, f"{evidence} / {confidence}", 2))
            uncertain_scenes.add(frame["sceneId"])
        if not _is_unknown(analysis.get("userAction")):
            missing = [name for name in ("beforeState", "systemResponse", "afterState") if _is_unknown(analysis.get(name))]
            if missing:
                review.append(_item("causal-gap", "事件因果链不完整", frame, "缺少：" + "、".join(missing), 1))
        warning = frame.get("structure", {}).get("warning")
        warning_key = (frame["sceneId"], str(warning))
        if warning and warning_key not in warning_groups:
            review.append(_item("structure-warning", "结构检测降级", frame, warning, 1))
            warning_groups.add(warning_key)

    # 同一组件轨迹出现多种类别，通常意味着追踪或检测存在冲突。
    for track in job.get("componentTracks", []):
        if len(track.get("observations", [])) == 1:
            continue
        facts.append({"trackId": track["id"], "class": track["class"], "observationCount": len(track["observations"])})

    scene_types = defaultdict(list)
    for scene in scenes:
        scene_type = scene.get("analysis", {}).get("sceneType")
        if not _is_unknown(scene_type):
            scene_types[str(scene_type).strip()].append(scene["id"])
        if not scene.get("analysis", {}).get("entryCondition") or not scene.get("analysis", {}).get("exitCondition"):
            first = next((frame for frame in frames if frame["sceneId"] == scene["id"]), None)
            if first:
                review.append(_item("scene-boundary", "场景进入/退出条件不完整", first, f"场景 {scene['id'] + 1}", 2))

    counts = Counter(item["type"] for item in review)
    semantic_frames = max(1, len(frames))
    uncertain_frames = sum(
        1 for frame in frames
        if frame.get("analysis", {}).get("evidenceLevel") != "明确展示"
        or frame.get("analysis", {}).get("confidence") == "低"
    )
    uncertainty_ratio = uncertain_frames / semantic_frames
    model_enabled = bool(job.get("analysisSummary", {}).get("modelEnabled"))
    semantic_penalty = round(uncertainty_ratio * 45) + (0 if model_enabled else 15)
    base_penalty = (
        counts["causal-gap"] * 4
        + counts["structure-warning"] * 3
        + counts["scene-boundary"] * 2
    )
    report = {
        "score": max(0, 100 - base_penalty - semantic_penalty),
        "reviewItemCount": len(review),
        "counts": dict(counts),
        "factCount": len(facts),
        "uncertainFrameCount": uncertain_frames,
        "uncertaintyRatio": round(uncertainty_ratio, 4),
        "modelEnabled": model_enabled,
        "checks": ["evidence-confidence", "causal-chain", "structure-engine", "scene-boundary", "component-track"],
    }
    review.sort(key=lambda item: (item["priority"], item["timestamp"]))
    return facts, review, report


def _item(kind: str, title: str, frame: dict[str, Any], detail: str, priority: int) -> dict[str, Any]:
    return {
        "id": f"{kind}-{frame['id']}", "type": kind, "title": title, "detail": detail,
        "priority": priority, "frameId": frame["id"], "sceneId": frame["sceneId"], "timestamp": frame["timestamp"],
    }
