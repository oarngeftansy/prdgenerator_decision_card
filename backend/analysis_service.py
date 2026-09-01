from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Callable
import math

import numpy as np
from openai import OpenAI

Progress = Callable[[int, str], None]
DETAIL_BATCH_SIZE = 6
INTERACTION_DETAIL_BATCH_SIZE = 2
_CORE_ANALYSIS_FIELDS = ("what", "userAction", "systemResponse", "afterState")
_EVIDENCE_MODALITY_POLICY = "interaction.evidence_modality_boundary"
_VISIBLE_EVIDENCE_FIELDS = ("components", "visibleText", "rules", "gameMechanics", "gameState", "gameFeedback")


def _parse_json(text: str) -> Any:
    value = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", value, re.I)
    if fenced:
        value = fenced.group(1).strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        starts = [pos for pos in (value.find("["), value.find("{")) if pos >= 0]
        if not starts:
            raise
        start = min(starts)
        end = max(value.rfind("]"), value.rfind("}"))
        return json.loads(value[start:end + 1])


def _data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _client(config: dict[str, Any]) -> OpenAI | None:
    base_url = str(config.get("apiBase") or "").rstrip("/")
    key = str(config.get("apiKey") or "")
    local = "127.0.0.1" in base_url or "localhost" in base_url
    if not base_url or (not key and not local):
        return None
    if local:
        health_url = base_url.removesuffix("/v1") + "/health"
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                if response.status != 200:
                    return None
        except Exception:
            return None
    return OpenAI(api_key=key or "local-proxy", base_url=base_url, timeout=90, max_retries=2)


def _call(client: OpenAI, model: str, prompt: str, images: list[tuple[str, Path]], max_tokens: int = 3000) -> Any:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for label, path in images:
        content.append({"type": "text", "text": label})
        content.append({"type": "image_url", "image_url": {"url": _data_url(path), "detail": "low"}})
    request_options: dict[str, Any] = {}
    if model.casefold().startswith("qwen3.6"):
        request_options["extra_body"] = {"enable_thinking": False}
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        temperature=0,
        max_tokens=max_tokens,
        **request_options,
    )
    return _parse_json(response.choices[0].message.content or "")


def _scene_prompt(mode: str, scene_ids: list[int], standard_prompt: str = "") -> str:
    domain = "游戏玩法" if mode == "gameplay" else "产品交互"
    focus = (
        "玩家目标、核心机制、规则、资源/数值、游戏状态和胜负线索"
        if mode == "gameplay" else
        "用户任务、页面/弹窗、组件、交互模式、状态转换和异常线索"
    )
    return f"""你是资深{domain}策划。以下是10–20分钟演示视频中若干场景的代表帧。
只依据画面分析，重点识别{focus}。忽略录屏设备外壳和社媒字幕。
ScreenCoder 已提供画面结构数据，图像标签中包含场景 ID。

只输出 JSON 数组，且每个场景一项。场景 ID 必须来自：{scene_ids}。
字段：sceneId, title, sceneType, summary, objective, entryCondition, exitCondition,
interactionModel, visibleRules, stateChanges, uncertainties, evidenceLevel, confidence。
evidenceLevel 只能是“明确展示”“合理推断”“未知待确认”；confidence 只能是“高”“中”“低”。
{standard_prompt}"""


def _frame_prompt(mode: str, frame_ids: list[str], scene_context: str, standard_prompt: str = "", input_type: str = "video") -> str:
    focus = (
        "玩法：玩家操作、核心机制、判定规则、数值变化、游戏状态、胜负与视听反馈"
        if mode == "gameplay" else
        "交互：用户任务、页面/弹窗/组件、输入事件、系统响应、前后状态、动效与异常状态"
    )
    source_rule = (
        "这些图片按用户确认的流程顺序排列。分别识别单页事实；只把有相邻画面支撑的变化写为合理推断，顺序本身不能证明具体操作，无法证明时写未知待确认。"
        if input_type == "image_sequence" else
        "这些画面来自视频时间轴，请结合前后状态还原事件。"
    )
    return f"""你正在还原交互证据。{focus}。
目标帧：{frame_ids}。场景上下文：{scene_context}
{source_rule}
对每帧建立可验证的“操作前状态 → 用户/玩家操作 → 系统响应 → 操作后状态”因果链。
像 ScreenCoder 一样描述 header/sidebar/main/modal/HUD/playfield/control bar 等区域和父子层级。
只输出 JSON 数组，每帧一项。字段：id, what, eventType, beforeState, userAction,
systemResponse, afterState, regionStructure, components, visibleText, rules, motion,
gameMechanics, gameState, gameFeedback, evidenceLevel, confidence, unknowns。
无法确认必须写“未知待确认”，不得编造。
{standard_prompt}"""


def analyze_local_evidence(
    job_dir: Path,
    frame: dict[str, Any],
    scene: dict[str, Any],
    samples: list[dict[str, Any]],
    config: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    client = _client(config)
    if not client:
        raise RuntimeError("视觉模型尚未连接，请检查接口配置后重试。")
    model = str(config.get("model") or "qwen3.6-plus")
    prompt = f"""你正在核对一张低把握关键帧。目标帧是 {frame['id']}，时间 {frame['timestamp']} 秒。
以下图片是目标时间前后的连续证据，场景背景：{json.dumps(scene.get('analysis', {}), ensure_ascii=False)}
只依据这些画面重新判断目标帧，输出一个 JSON 对象。字段：id, what, eventType, beforeState,
userAction, systemResponse, afterState, regionStructure, components, visibleText, rules, motion,
gameMechanics, gameState, gameFeedback, evidenceLevel, confidence, unknowns, attentionSignals,
evidenceTimestamps。confidence 只能是“高”“中”“低”。attentionSignals 只能从
text_unreadable, visual_occlusion, action_between_frames, result_not_shown, state_chain_broken 中选择。
evidenceTimestamps 填支撑结论的图片时间点。无法确认时保留低把握，不得编造。当前方向：{mode}。"""
    images = [
        (f"time={sample['timestamp']}", job_dir / "supplemental" / Path(sample["imageUrl"]).name)
        for sample in samples
    ]
    result = _call(client, model, prompt, images, max_tokens=2400)
    if isinstance(result, list):
        result = result[0] if result else {}
    if not isinstance(result, dict):
        raise ValueError("局部分析结果格式不正确，请重试。")
    return result


def analyze_image_frame(
    job_dir: Path,
    frame: dict[str, Any],
    scene: dict[str, Any],
    config: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    """Re-read one uploaded screenshot without requiring a source video."""
    client = _client(config)
    if not client:
        raise RuntimeError("视觉模型尚未连接，请检查接口配置后重试。")
    model = str(config.get("model") or "qwen3.6-plus")
    image_path = job_dir / "frames" / Path(str(frame.get("imageUrl") or f"{frame['id']}.jpg")).name
    if not image_path.is_file():
        raise FileNotFoundError("原始截图不可用，无法重新识别。")
    context = json.dumps(scene.get("analysis") or {}, ensure_ascii=False)
    prompt = _frame_prompt(mode, [str(frame["id"])], context, input_type="image_sequence")
    images = [(f"frame={frame['id']} scene={frame.get('sceneId')}", image_path)]
    try:
        result = _call(client, model, prompt, images, max_tokens=1600)
    except json.JSONDecodeError:
        result = _call(
            client,
            model,
            prompt + "\n上一次回复不是有效 JSON。只输出一个完整 JSON 对象，不要解释，不要省略逗号或引号。",
            images,
            max_tokens=1600,
        )
    if isinstance(result, dict) and isinstance(result.get("frames"), list):
        result = result["frames"][0] if result["frames"] else {}
    elif isinstance(result, list):
        result = result[0] if result else {}
    if not isinstance(result, dict):
        raise ValueError("单张截图识别结果格式不正确，请重试。")
    result["id"] = str(frame["id"])
    if not _analysis_is_qualified(result, "image_sequence"):
        raise ValueError("视觉模型未能完整说明这张图，请重试或更换模型。")
    return result


def _fallback_scene(scene: dict[str, Any], frames_by_id: dict[str, dict[str, Any]], mode: str) -> dict[str, Any]:
    representative = frames_by_id[scene["frameIds"][0]]
    counts = representative["structure"].get("regionCounts", {})
    return {
        "sceneId": scene["id"],
        "title": f"场景 {scene['id'] + 1}",
        "sceneType": "游戏状态待识别" if mode == "gameplay" else "页面状态待识别",
        "summary": f"已完成结构扫描，检测到 {representative['structure'].get('elementCount', 0)} 个界面元素。",
        "objective": "需要配置视觉模型后识别",
        "entryCondition": "未知待确认",
        "exitCondition": "未知待确认",
        "interactionModel": "unknown",
        "visibleRules": [],
        "stateChanges": [],
        "uncertainties": ["当前未配置可用视觉模型，只有 ScreenCoder 结构证据。"],
        "evidenceLevel": "未知待确认",
        "confidence": "低",
        "regionCounts": counts,
    }


def _is_meaningful(value: Any) -> bool:
    text = " ".join(map(str, value)) if isinstance(value, list) else str(value or "")
    lowered = text.strip().lower()
    return bool(lowered) and lowered != "unknown" and "未知待确认" not in text and "Request timed out" not in text and "继承场景摘要" not in text


def _analysis_quality_score(analysis: dict[str, Any]) -> int:
    return sum(1 for field in _CORE_ANALYSIS_FIELDS if _is_meaningful(analysis.get(field)))


def _analysis_is_qualified(analysis: dict[str, Any], input_type: str = "video") -> bool:
    if input_type != "image_sequence":
        return _analysis_quality_score(analysis) >= 3
    if not _is_meaningful(analysis.get("what")):
        return False
    has_state_or_action = any(_is_meaningful(analysis.get(field)) for field in _CORE_ANALYSIS_FIELDS[1:])
    has_visible_evidence = any(_is_meaningful(analysis.get(field)) for field in _VISIBLE_EVIDENCE_FIELDS)
    return has_state_or_action or has_visible_evidence


def _analysis_request_failed(analysis: dict[str, Any]) -> bool:
    notes = " ".join(map(str, analysis.get("unknowns") or []))
    return "请求失败" in notes or "Connection error" in notes or "Request timed out" in notes


def _normalize_player_action_evidence(analysis: dict[str, Any]) -> None:
    """Do not turn the static input medium into a claim about player behavior."""
    action = str(analysis.get("userAction") or "")
    if not re.search(
        r"(?:当前帧|当前截图|截图)[^)）。]*(?:静态展示|未捕捉到)[^)）。]*(?:点击|滑动|操作)",
        action,
    ):
        return
    analysis["userAction"] = "未知待确认"
    note = "当前截图无法单独确认玩家操作，需结合相邻画面或视频证据。"
    unknowns = analysis.setdefault("unknowns", [])
    if note not in unknowns:
        unknowns.append(note)


def _scene_from_frame(scene: dict[str, Any], frame: dict[str, Any] | None, frames_by_id: dict[str, dict[str, Any]], mode: str) -> dict[str, Any]:
    fallback = _fallback_scene(scene, frames_by_id, mode)
    if not frame:
        return fallback
    analysis = frame.get("analysis") or {}
    return {
        **fallback,
        "title": analysis.get("what") or fallback["title"],
        "sceneType": analysis.get("what") or fallback["sceneType"],
        "summary": analysis.get("what") or fallback["summary"],
        "objective": analysis.get("afterState") or fallback["objective"],
        "entryCondition": analysis.get("beforeState") or fallback["entryCondition"],
        "exitCondition": analysis.get("afterState") or fallback["exitCondition"],
        "interactionModel": analysis.get("eventType") or "interaction",
        "visibleRules": analysis.get("rules") or [],
        "stateChanges": [value for value in (analysis.get("userAction"), analysis.get("systemResponse"), analysis.get("afterState")) if _is_meaningful(value)],
        "uncertainties": analysis.get("unknowns") or [],
        "evidenceLevel": analysis.get("evidenceLevel") or fallback["evidenceLevel"],
        "confidence": analysis.get("confidence") or fallback["confidence"],
    }


def analyze_video(
    job_dir: Path,
    frames: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    config: dict[str, Any],
    mode: str,
    progress: Progress,
    input_type: str = "video",
    auxiliary_video_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    client = _client(config)
    model = str(config.get("model") or "qwen3.6-plus")
    standard_prompt = str(config.get("standardPrompt") or "")
    frames_by_id = {frame["id"]: frame for frame in frames}
    detail_indexes = np.linspace(0, len(frames) - 1, min(60, len(frames))).round().astype(int).tolist() if frames else []
    if mode == "interaction":
        detail_ids = []
        for scene in scenes:
            ids = [frame_id for frame_id in scene.get("frameIds") or [] if frame_id in frames_by_id]
            if ids:
                detail_ids.append(ids[len(ids) // 2])
        detail_frames = [frames_by_id[frame_id] for frame_id in dict.fromkeys(detail_ids)]
    else:
        detail_frames = [frames[index] for index in sorted(set(detail_indexes))]
    detail_frame_ids = {frame["id"] for frame in detail_frames}
    progress(65, "场景级语义解读")

    if mode == "interaction":
        for scene in scenes:
            scene["analysis"] = _fallback_scene(scene, frames_by_id, mode)
        progress(70, "交互模式使用场景代表帧解读")
    else:
        for start in range(0, len(scenes), 4):
            batch = scenes[start:start + 4]
            if client:
                images = []
                for scene in batch:
                    ids = scene["frameIds"]
                    picks = [ids[0], ids[len(ids) // 2], ids[-1]]
                    for frame_id in dict.fromkeys(picks):
                        frame = frames_by_id[frame_id]
                        images.append((f"scene={scene['id']} frame={frame_id} time={frame['timestamp']}", job_dir / "frames" / Path(frame["imageUrl"]).name))
                try:
                    items = _call(client, model, _scene_prompt(mode, [scene["id"] for scene in batch], standard_prompt), images)
                    if isinstance(items, dict):
                        items = items.get("scenes", [items])
                except Exception as exc:
                    items = []
                    for scene in batch:
                        fallback = _fallback_scene(scene, frames_by_id, mode)
                        fallback["uncertainties"].append(f"视觉模型场景请求失败：{exc}")
                        items.append(fallback)
            else:
                items = [_fallback_scene(scene, frames_by_id, mode) for scene in batch]
            item_map = {int(item.get("sceneId", -1)): item for item in items if isinstance(item, dict)}
            for scene in batch:
                scene["analysis"] = item_map.get(scene["id"], _fallback_scene(scene, frames_by_id, mode))
            progress(65 + round(10 * min(len(scenes), start + 4) / max(1, len(scenes))), f"场景解读 {min(len(scenes), start + 4)}/{len(scenes)}")

    # 图片序列最多 30 张并全部分析；单图请求三路并发，避免大 JSON 批次超时。
    detail_batch_size = 1 if input_type == "image_sequence" else (INTERACTION_DETAIL_BATCH_SIZE if mode == "interaction" else DETAIL_BATCH_SIZE)
    if input_type == "image_sequence":
        # A retry must keep paid, qualified results and only ask the model for
        # screenshots that are still incomplete.
        pending_detail_frames = [
            frame for frame in detail_frames
            if not _analysis_is_qualified(frame.get("analysis") or {}, input_type)
        ]
        detail_batches = [[frame] for frame in pending_detail_frames]
    else:
        detail_batches = [detail_frames[start:start + detail_batch_size] for start in range(0, len(detail_frames), detail_batch_size)]
    detail_model_calls = 0

    def request_batch(target: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal detail_model_calls
        if not client:
            return []
        images = [(f"frame={frame['id']} time={frame['timestamp']} scene={frame['sceneId']}", job_dir / "frames" / Path(frame["imageUrl"]).name) for frame in target]
        context = json.dumps({scene["id"]: scene["analysis"] for scene in scenes if scene["id"] in {frame["sceneId"] for frame in target}}, ensure_ascii=False)
        if input_type != "image_sequence":
            detail_model_calls += 1
        prompt = _frame_prompt(mode, [frame["id"] for frame in target], context, standard_prompt, input_type)
        try:
            try:
                items = _call(
                    client, model, prompt, images,
                    max_tokens=1200 if input_type == "image_sequence" else 3000,
                )
            except json.JSONDecodeError:
                # A single malformed response must not permanently discard a screenshot.
                # Retry once with a shorter, explicit JSON-only instruction; network and
                # timeout failures still keep the existing bounded failure behaviour.
                repair_prompt = (
                    prompt
                    + "\n上一次回复不是有效 JSON。请重新观察同一张图，只输出一个 JSON 对象；"
                      "不要使用 Markdown，不要解释，不要省略逗号或引号。"
                )
                items = _call(
                    client, model, repair_prompt, images,
                    max_tokens=1200 if input_type == "image_sequence" else 3000,
                )
            if isinstance(items, dict):
                items = items.get("frames", [items])
            if input_type == "image_sequence" and len(target) == 1:
                candidate = items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else {}
                if not _analysis_is_qualified(candidate, input_type):
                    quality_prompt = (
                        prompt
                        + "\n上一次结果缺少有效的页面名称、玩家操作或系统反馈。请重新观察图片，"
                          "必须具体写出这是什么页面或状态、玩家此时能做什么、系统如何反馈、下一状态是什么；"
                          "禁止使用‘场景N’‘查看当前状态’‘继续操作’‘待确认’作为主要结论。只输出JSON。"
                    )
                    repaired = _call(client, model, quality_prompt, images, max_tokens=1600)
                    if isinstance(repaired, dict):
                        repaired = repaired.get("frames", [repaired])
                    if isinstance(repaired, list) and repaired and isinstance(repaired[0], dict):
                        items = repaired
            return items if isinstance(items, list) else []
        except Exception as exc:
            if input_type == "image_sequence" and len(target) > 3:
                midpoint = math.ceil(len(target) / 2)
                return request_batch(target[:midpoint]) + request_batch(target[midpoint:])
            return [{"id": frame["id"], "unknowns": [f"逐帧请求失败：{exc}"]} for frame in target]

    if input_type == "image_sequence" and client:
        detail_model_calls = len(detail_batches)
        batch_results = [[] for _batch in detail_batches]
        with ThreadPoolExecutor(max_workers=min(2, len(detail_batches))) as pool:
            pending = {pool.submit(request_batch, batch): index for index, batch in enumerate(detail_batches)}
            for completed, future in enumerate(as_completed(pending), 1):
                batch_results[pending[future]] = future.result()
                progress(76 + round(16 * completed / max(1, len(detail_batches))), f"事件链分析 {completed}/{len(detail_batches)}")
    else:
        batch_results = [request_batch(batch) for batch in detail_batches]

    for batch_index, (batch, items) in enumerate(zip(detail_batches, batch_results)):
        item_map = {str(item.get("id")): item for item in items if isinstance(item, dict)}
        for frame in batch:
            frame["analysis"] = item_map.get(frame["id"], {})
            frame["analysis"]["isDetailFrame"] = True
        stride = detail_batch_size
        processed = min(len(detail_frames), batch_index * stride + len(batch))
        if input_type != "image_sequence":
            progress(76 + round(16 * processed / max(1, len(detail_frames))), f"事件链分析 {processed}/{len(detail_frames)}")

    auxiliary_context_frames = 0
    if mode == "interaction":
        detail_by_scene = {frame["sceneId"]: frame for frame in detail_frames}
        for scene in scenes:
            scene["analysis"] = _scene_from_frame(scene, detail_by_scene.get(scene["id"]), frames_by_id, mode)
        qualified_detail_frames = sum(1 for frame in detail_frames if _analysis_is_qualified(frame.get("analysis") or {}, input_type))
        required_quality = max(1, math.ceil(len(detail_frames) * 0.85)) if detail_frames else 0
        if client and auxiliary_video_path and auxiliary_video_path.exists() and qualified_detail_frames < len(detail_frames):
            from .auxiliary_video import analyze_context_window
            context_candidates = [frame for frame in detail_frames if not _analysis_is_qualified(frame.get("analysis") or {}, input_type)]
            for context_index, frame in enumerate(context_candidates, 1):
                if qualified_detail_frames >= required_quality:
                    break
                if _analysis_is_qualified(frame.get("analysis") or {}, input_type):
                    continue
                progress(92 + round(3 * context_index / max(1, len(context_candidates))), f"补充视频上下文 {context_index}/{len(context_candidates)}")
                result = analyze_context_window(
                    chapter_id=f"interaction-{frame['sceneId']}", anchor_frame_id=frame["id"],
                    screenshot_path=job_dir / "frames" / Path(frame["imageUrl"]).name,
                    video_path=auxiliary_video_path, missing_fields=["trigger", "process", "result", "automaticTransition"],
                    job_dir=job_dir, config=config,
                )
                if result.get("status") != "completed":
                    continue
                facts = result.get("facts") or {}
                analysis = frame.setdefault("analysis", {})
                analysis.update({key: value for key, value in {
                    "userAction": facts.get("trigger"), "systemResponse": facts.get("process"),
                    "afterState": facts.get("result"), "motion": facts.get("automaticTransition"),
                }.items() if value})
                analysis["evidenceTimestamps"] = result.get("evidenceTimestamps") or []
                if _analysis_is_qualified(analysis, input_type):
                    auxiliary_context_frames += 1
                    qualified_detail_frames += 1
    else:
        qualified_detail_frames = sum(1 for frame in detail_frames if _analysis_is_qualified(frame.get("analysis") or {}, input_type))

    scene_map = {scene["id"]: scene for scene in scenes}
    for frame in frames:
        if isinstance(frame.get("analysis"), dict):
            _normalize_player_action_evidence(frame["analysis"])
        if not frame.get("analysis"):
            scene_analysis = scene_map[frame["sceneId"]]["analysis"]
            frame["analysis"] = {
                "id": frame["id"],
                "what": scene_analysis.get("summary", "未知待确认"),
                "eventType": "unknown",
                "beforeState": "未知待确认",
                "userAction": "未知待确认",
                "systemResponse": "未知待确认",
                "afterState": "未知待确认",
                "regionStructure": frame["structure"].get("regionCounts", {}),
                "evidenceLevel": scene_analysis.get("evidenceLevel", "未知待确认"),
                "confidence": scene_analysis.get("confidence", "低"),
                "unknowns": ["该帧继承场景摘要，未进行独立视觉模型分析。"],
            }
        frame["analysis"].setdefault("isDetailFrame", frame["id"] in detail_frame_ids)

    summary = {
        "mode": mode,
        "sceneCount": len(scenes),
        "frameCount": len(frames),
        "detailFrameCount": len(detail_frames),
        "qualifiedDetailFrameCount": qualified_detail_frames,
        "requestFailureDetailFrameCount": sum(
            1 for frame in detail_frames if _analysis_request_failed(frame.get("analysis") or {})
        ),
        "requiredQualifiedDetailFrameCount": required_quality if mode == "interaction" else 0,
        "qualityQualified": mode != "interaction" or qualified_detail_frames >= required_quality,
        "modelEnabled": bool(client),
        "model": model if client else None,
        "pipeline": (["ordered-screenshots", "ScreenCoder-UIED", "adjacent-state-analysis", "planning-document"] if input_type == "image_sequence" else ["full-video-scan", "scene-detection", "ScreenCoder-UIED", "scene-understanding", "event-chain", "planning-document"]),
        "estimatedModelCalls": ((detail_model_calls if mode == "interaction" else math.ceil(len(scenes) / 4) + detail_model_calls) if client else 0),
        "estimatedImageInputs": ((sum(len(batch) for batch in detail_batches) if mode == "interaction" else len(scenes) * 3 + sum(len(batch) for batch in detail_batches)) if client else 0),
        "auxiliaryContextFrames": auxiliary_context_frames,
    }
    return frames, scenes, summary
