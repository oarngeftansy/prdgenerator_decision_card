from __future__ import annotations

import argparse
import base64
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .models import make_source_ref
from .vision_provider import load_env_file, resolve_provider


def _parse_json(text: str) -> Any:
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    value = (fenced.group(1) if fenced else text).strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        starts = [index for index in (value.find("["), value.find("{")) if index >= 0]
        if not starts:
            raise
        end = max(value.rfind("]"), value.rfind("}"))
        return json.loads(value[min(starts) : end + 1])


def _image_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _request(config: dict[str, str], prompt: str, images: list[tuple[str, Path]]) -> Any:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for label, path in images:
        content.extend([
            {"type": "text", "text": label},
            {"type": "image_url", "image_url": {"url": _image_url(path), "detail": "low"}},
        ])
    payload = json.dumps({
        "model": config["model"],
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 5000,
    }).encode("utf-8")
    request = urllib.request.Request(
        f'{config["baseUrl"]}/chat/completions',
        data=payload,
        headers={"content-type": "application/json", "authorization": f'Bearer {config["apiKey"]}'},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        envelope = json.loads(response.read().decode("utf-8"))
    return _parse_json(envelope["choices"][0]["message"]["content"])


def _prompt(level_id: str, scene_ids: list[int]) -> str:
    return f"""你是资深游戏系统策划和交互策划，正在校准同一玩法的两个关卡视频。
本批来自 {level_id}，场景 ID 为 {scene_ids}。每张图标签包含 scene、frame、time，图片按时间顺序排列。

只根据画面证据输出 JSON 对象：{{"scenes": [...], "events": [...]}}。
scenes 每项字段：sceneId,title,sceneType,objective,entryCondition,exitCondition,
visibleRules,gameState,uiRegions,visibleText,visualBehavior,evidenceLevel,confidence,unknowns。
events 每项字段：sceneId,beforeState,action,systemResponse,afterState,trigger,
rules,numericChanges,motion,audioClue,evidenceFrameIds,evidenceLevel,confidence,unknowns。

要求：
1. evidenceLevel 只能是 observed、inferred、unknown。
2. 没看到操作输入时 action 写 unknown，不得把结果倒推成已观察操作。
3. 区分静态 UI、战斗表现、技能/Buff 选择、成长、暂停、成功和失败结算。
4. 关注外部表现：飘字、血条、冷却、暂停、弹窗、动效、选中态和状态变化。
5. 每个结论引用真实 frame id；不输出 Markdown。"""


def enrich_video(
    artifact_path: Path,
    frames_root: Path,
    config: dict[str, str],
    batch_size: int = 3,
    max_scenes: int | None = None,
) -> dict[str, Any]:
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    frame_map = {frame["id"]: frame for frame in data["frames"]}
    scenes = data["scenes"][:max_scenes] if max_scenes else data["scenes"]
    scene_results: dict[int, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    for offset in range(0, len(scenes), batch_size):
        batch = scenes[offset : offset + batch_size]
        images: list[tuple[str, Path]] = []
        for scene in batch:
            ids = scene["frameIds"]
            picks = list(dict.fromkeys([ids[0], ids[len(ids) // 2], ids[-1]]))
            for frame_id in picks:
                frame = frame_map[frame_id]
                filename = Path(frame["imageUrl"]).name
                images.append((
                    f'scene={scene["id"]} frame={frame_id} time={frame["timestamp"]}',
                    frames_root / filename,
                ))
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                result = _request(config, _prompt(data["levelId"], [item["id"] for item in batch]), images)
                break
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 2:
                    raise RuntimeError(f"semantic batch {offset // batch_size + 1} failed") from exc
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError("semantic request failed") from last_error
        for item in result.get("scenes", []):
            scene_id = int(item.get("sceneId", -1))
            if scene_id >= 0:
                item["sourceRefs"] = [
                    make_source_ref("video", data["levelId"], str(frame_map[fid]["timestamp"]))
                    for fid in batch[scene_id - batch[0]["id"]]["frameIds"][:1]
                    if fid in frame_map
                ] if batch[0]["id"] <= scene_id <= batch[-1]["id"] else []
                scene_results[scene_id] = item
        for event in result.get("events", []):
            refs = []
            for frame_id in event.get("evidenceFrameIds", []):
                if frame_id in frame_map:
                    refs.append(make_source_ref("video", data["levelId"], str(frame_map[frame_id]["timestamp"])))
            event["sourceRefs"] = refs
            events.append(event)
        print(f'[{data["levelId"]}] semantic {min(offset + batch_size, len(scenes))}/{len(scenes)}', flush=True)
    for scene in data["scenes"]:
        scene["analysis"] = scene_results.get(scene["id"], {
            "sceneId": scene["id"], "evidenceLevel": "unknown", "unknowns": ["semantic result missing"]
        })
    data["events"] = events
    data["semantic"] = {
        "provider": config["provider"],
        "model": config["model"],
        "sceneCount": len(scene_results),
        "eventCount": len(events),
    }
    artifact_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--frames-root", type=Path, required=True)
    parser.add_argument("--env", type=Path, default=Path(".env.calibration"))
    parser.add_argument("--max-scenes", type=int)
    args = parser.parse_args()
    config = resolve_provider(load_env_file(args.env))
    enrich_video(args.artifact, args.frames_root, config, max_scenes=args.max_scenes)


if __name__ == "__main__":
    main()
