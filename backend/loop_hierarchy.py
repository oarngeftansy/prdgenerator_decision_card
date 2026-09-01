from __future__ import annotations

from copy import deepcopy
from typing import Any


UNKNOWN = "未知待确认"


def _timestamp(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds or 0) * 1000))
    minutes, remainder = divmod(milliseconds, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{minutes:02d}:{whole_seconds:02d}.{millis:03d}"


def _text(value: Any, default: str = UNKNOWN) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _frame_map(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(frame.get("id")): frame for frame in job.get("frames") or []}


def _evidence(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceType": "video",
        "sourceId": str(frame.get("id") or ""),
        "locator": _timestamp(frame.get("timestamp", 0)),
        "confidence": _text((frame.get("analysis") or {}).get("confidence"), "低"),
    }


def _fallback(job: dict[str, Any]) -> dict[str, Any]:
    frames = _frame_map(job)
    stage_groups: list[tuple[str, list[dict[str, Any]]]] = []
    for scene in job.get("scenes") or []:
        analysis = scene.get("analysis") or {}
        kind = _text(analysis.get("sceneType"), "未分类环节")
        if not stage_groups or stage_groups[-1][0] != kind:
            stage_groups.append((kind, []))
        stage_groups[-1][1].append(scene)

    stages = []
    for stage_index, (kind, scenes) in enumerate(stage_groups, 1):
        steps = []
        for step_index, scene in enumerate(scenes, 1):
            analysis = scene.get("analysis") or {}
            refs = [_evidence(frames[frame_id]) for frame_id in scene.get("frameIds") or [] if frame_id in frames]
            steps.append({
                "id": f"STEP-{stage_index:02d}-{step_index:02d}",
                "title": _text(analysis.get("title"), f"{kind}步骤 {step_index}"),
                "userAction": _text(analysis.get("userAction")),
                "systemResponse": _text(analysis.get("systemResponse") or analysis.get("summary")),
                "stateChange": analysis.get("stateChanges") or [],
                "evidence": refs,
                "confidence": _text(analysis.get("confidence"), "低"),
            })
        first = scenes[0].get("analysis") or {}
        last = scenes[-1].get("analysis") or {}
        small_loop = {
            "id": f"SMALL-{stage_index:02d}-01",
            "title": f"{kind}小循环",
            "goal": _text(first.get("objective"), f"完成{kind}"),
            "entryCondition": _text(first.get("entryCondition")),
            "repeatCondition": f"用户再次进入“{kind}”且目标尚未完成时重复",
            "exitCondition": _text(last.get("exitCondition")),
            "steps": steps,
            "confidence": "低" if any(step["confidence"] == "低" for step in steps) else "中",
            "reviewStatus": "pending",
        }
        stages.append({
            "id": f"STAGE-{stage_index:02d}",
            "title": kind,
            "purpose": _text(first.get("objective"), f"完成{kind}阶段"),
            "entryCondition": small_loop["entryCondition"],
            "exitCondition": small_loop["exitCondition"],
            "smallLoops": [small_loop],
            "reviewStatus": "pending",
        })

    first_stage = stages[0] if stages else {}
    last_stage = stages[-1] if stages else {}
    mode = (job.get("metadata") or {}).get("mode")
    return {
        "schemaVersion": "2.0",
        "mode": mode,
        "largeLoops": [{
            "id": "LOOP-001",
            "title": "完整交互任务循环" if mode == "interaction" else "完整玩法循环",
            "goal": _text((job.get("metadata") or {}).get("scope"), "完成视频展示的核心目标"),
            "entryCondition": _text(first_stage.get("entryCondition")),
            "repeatCondition": "上一轮结束后，用户或玩家再次发起相同目标时重复",
            "exitCondition": _text(last_stage.get("exitCondition")),
            "stages": stages,
            "reviewStatus": "pending",
        }] if stages else [],
        "sourceSceneCount": len(job.get("scenes") or []),
        "sourceFrameCount": len(job.get("frames") or []),
        "generation": "deterministic-fallback",
    }


def _normalize_provider_hierarchy(job: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    hierarchy = deepcopy(source)
    hierarchy.setdefault("schemaVersion", "2.0")
    hierarchy.setdefault("mode", (job.get("metadata") or {}).get("mode"))
    hierarchy.setdefault("sourceSceneCount", len(job.get("scenes") or []))
    hierarchy.setdefault("sourceFrameCount", len(job.get("frames") or []))
    hierarchy.setdefault("generation", "model-synthesis")
    for large_index, large_loop in enumerate(hierarchy.get("largeLoops") or [], 1):
        large_loop.setdefault("id", f"LOOP-{large_index:03d}")
        large_loop.setdefault("entryCondition", UNKNOWN)
        large_loop.setdefault("repeatCondition", UNKNOWN)
        large_loop.setdefault("exitCondition", UNKNOWN)
        large_loop.setdefault("reviewStatus", "pending")
        for stage_index, stage in enumerate(large_loop.get("stages") or [], 1):
            stage.setdefault("id", f"{large_loop['id']}-STAGE-{stage_index:02d}")
            stage.setdefault("reviewStatus", "pending")
            for small_index, small_loop in enumerate(stage.get("smallLoops") or [], 1):
                small_loop.setdefault("id", f"{stage['id']}-SMALL-{small_index:02d}")
                small_loop.setdefault("entryCondition", UNKNOWN)
                small_loop.setdefault("repeatCondition", UNKNOWN)
                small_loop.setdefault("exitCondition", UNKNOWN)
                small_loop.setdefault("reviewStatus", "pending")
    return hierarchy


def _confirmed_review_hierarchy(job: dict[str, Any]) -> dict[str, Any] | None:
    review = job.get("reviewModel") or {}
    stages = sorted(
        (stage for stage in review.get("stages") or [] if (stage.get("confirmation") or {}).get("confirmed")),
        key=lambda stage: (stage.get("order", 0), stage.get("id", "")),
    )
    if not stages:
        return None
    frames = _frame_map(job)
    hierarchy_stages = []
    for index, stage in enumerate(stages, 1):
        loop = stage.get("smallLoop") or {}
        steps = []
        for step_index, representative in enumerate(stage.get("representativeFrames") or [], 1):
            frame = frames.get(str(representative.get("frameId") or ""))
            if not frame:
                continue
            role_labels = {"entry": "操作前", "change": "变化过程", "result": "操作后"}
            steps.append({
                "id": f"{stage.get('id')}-STEP-{step_index:03d}",
                "title": role_labels.get(str(representative.get("role") or ""), "关键画面"),
                "userAction": _text(loop.get("trigger")),
                "systemResponse": _text(loop.get("feedback")),
                "stateChange": [loop.get("result")] if loop.get("result") else [],
                "evidence": [_evidence(frame)],
                "confidence": "high",
            })
        hierarchy_stages.append({
            "id": str(stage.get("id") or f"STAGE-{index:03d}"),
            "title": _text(stage.get("name"), f"stage {index}"),
            "purpose": _text(stage.get("objective")),
            "entryCondition": _text(stage.get("entryCondition")),
            "exitCondition": _text(stage.get("exitCondition")),
            "smallLoops": [{
                "id": f"{stage.get('id')}-SMALL-001",
                "title": _text(loop.get("display"), _text(stage.get("name"))),
                "goal": _text(stage.get("objective")),
                "entryCondition": _text(stage.get("entryCondition")),
                "repeatCondition": _text(loop.get("retry")),
                "exitCondition": _text(stage.get("exitCondition")),
                "steps": steps,
                "confidence": "high",
                "reviewStatus": "confirmed",
            }],
            "reviewStatus": "confirmed",
        })
    first, last = stages[0], stages[-1]
    return {
        "schemaVersion": "2.0",
        "mode": (job.get("metadata") or {}).get("mode"),
        "largeLoops": [{
            "id": "LOOP-001",
            "title": "玩家操作流程",
            "goal": _text((job.get("metadata") or {}).get("scope")),
            "entryCondition": _text(first.get("entryCondition")),
            "repeatCondition": _text((last.get("smallLoop") or {}).get("retry")),
            "exitCondition": _text(last.get("exitCondition")),
            "stages": hierarchy_stages,
            "reviewStatus": "confirmed",
        }],
        "sourceSceneCount": len(job.get("scenes") or []),
        "sourceFrameCount": len(job.get("frames") or []),
        "generation": "confirmed-review",
    }


def build_loop_hierarchy(job: dict[str, Any]) -> dict[str, Any]:
    if hierarchy := _confirmed_review_hierarchy(job):
        return hierarchy
    source = job.get("analysisHierarchy")
    if isinstance(source, dict) and isinstance(source.get("largeLoops"), list):
        return _normalize_provider_hierarchy(job, source)
    return _fallback(job)


def validate_loop_hierarchy(hierarchy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    large_loops = hierarchy.get("largeLoops")
    if not isinstance(large_loops, list) or not large_loops:
        return ["largeLoops must be a non-empty list"]
    for large_index, large_loop in enumerate(large_loops):
        for field in ("entryCondition", "repeatCondition", "exitCondition"):
            if not _text(large_loop.get(field), ""):
                errors.append(f"largeLoops[{large_index}].{field} is required")
        for stage_index, stage in enumerate(large_loop.get("stages") or []):
            for small_index, small_loop in enumerate(stage.get("smallLoops") or []):
                for field in ("entryCondition", "repeatCondition", "exitCondition"):
                    if not _text(small_loop.get(field), ""):
                        errors.append(
                            f"largeLoops[{large_index}].stages[{stage_index}].smallLoops[{small_index}].{field} is required"
                        )
                evidence = [item for step in small_loop.get("steps") or [] for item in step.get("evidence") or []]
                if not evidence:
                    errors.append(
                        f"largeLoops[{large_index}].stages[{stage_index}].smallLoops[{small_index}] requires evidence"
                    )
    return errors


def loop_quality_gate(hierarchy: dict[str, Any], quality_report: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    if int(quality_report.get("score") or 0) < 70:
        failed.append("quality-score")
    if float(quality_report.get("uncertaintyRatio") or 0) > 0.4:
        failed.append("uncertainty")
    if validate_loop_hierarchy(hierarchy):
        failed.append("loop-closure")
    return {
        "status": "draft" if failed else "publishable",
        "publishable": not failed,
        "failedChecks": failed,
        "thresholds": {"qualityScore": 70, "maximumUncertaintyRatio": 0.4},
    }
