from __future__ import annotations

from typing import Any
from pathlib import Path

from .planning_model import build_planning_model, compile_confirmed_planning_model, validate_planning_model
from .planning_board_model import planner_board_text
from .review_model import review_gate


def _time(seconds: float) -> str:
    value = max(0, int(seconds))
    return f"{value // 60:02d}:{value % 60:02d}"


def _value(value: Any) -> str:
    if value in (None, "", [], {}):
        return "未知待确认"
    if isinstance(value, list):
        return "；".join(map(str, value))
    if isinstance(value, dict):
        return "；".join(f"{key}：{val}" for key, val in value.items())
    return str(value)


def _frame_locator(frame: dict[str, Any], input_type: str) -> str:
    return f"第 {frame.get('sequenceIndex', int(frame.get('timestamp', 0)) + 1)} 张" if input_type == "image_sequence" else _time(frame["timestamp"])


def _scene_locator(scene: dict[str, Any], input_type: str) -> str:
    return f"第 {scene['id'] + 1} 张" if input_type == "image_sequence" else f"{_time(scene['start'])}–{_time(scene['end'])}"


def _scene_table(scenes: list[dict[str, Any]], input_type: str) -> str:
    rows = []
    for index, scene in enumerate(scenes, 1):
        analysis = scene.get("analysis", {})
        rows.append(
            f"| {index} | {_scene_locator(scene, input_type)} | "
            f"{_value(analysis.get('sceneType'))} | {_value(analysis.get('summary'))} | "
            f"{', '.join(scene['frameIds'][:8])} |"
        )
    return "\n".join(rows)


def _event_chains(frames: list[dict[str, Any]], input_type: str = "video") -> str:
    blocks = []
    for index, frame in enumerate(frames, 1):
        item = frame["analysis"]
        blocks.append(f"""### 事件 {index} · {_frame_locator(frame, input_type)}

- 事件类型：{_value(item.get('eventType'))}
- 操作前状态：{_value(item.get('beforeState'))}
- 用户/玩家操作：{_value(item.get('userAction'))}
- 系统响应：{_value(item.get('systemResponse'))}
- 操作后状态：{_value(item.get('afterState'))}
- 结论来源：{_value(item.get('evidenceLevel'))}；置信度：{_value(item.get('confidence'))}
- 未知项：{_value(item.get('unknowns'))}""")
    return "\n\n".join(blocks) or "- 当前画面信息不足以建立完整事件链，请检查模型配置和关键帧。"


def _document_frames(job: dict[str, Any]) -> list[dict[str, Any]]:
    frames = job["frames"]
    if job["metadata"].get("mode") != "interaction":
        return frames
    detail_frames = [frame for frame in frames if (frame.get("analysis") or {}).get("isDetailFrame")]
    return detail_frames or frames


def _auxiliary_state_notes(job: dict[str, Any]) -> str:
    analysis = job.get("auxiliaryVideo", {}).get("analysis", {})
    if not analysis:
        return ""
    if analysis.get("status") != "completed":
        return "\n- 辅助视频未完成分析；相关动效、过渡与短暂提示待确认。"
    notes = []
    for transition in analysis.get("transitions") or []:
        notes.append(f"- 辅助视频合理推断：{_value(transition)}")
    for prompt in analysis.get("temporaryPrompts") or []:
        notes.append(f"- 辅助视频短暂提示：{_value(prompt)}")
    for timing in analysis.get("operationTiming") or []:
        notes.append(f"- 辅助视频操作时序：{_value(timing)}")
    return "\n" + "\n".join(notes) if notes else ""


def _evidence_index(frames: list[dict[str, Any]]) -> str:
    rows = []
    for frame in frames:
        item = frame.get("analysis", {})
        rows.append(
            f"| {frame['id']} | {_time(frame['timestamp'])} | {_value(item.get('what'))} | "
            f"{_value(item.get('evidenceLevel'))} | {_value(item.get('confidence'))} | "
            f"{frame['structure'].get('engine', 'unknown')} |"
        )
    return "\n".join(rows)


def generate_plan(job: dict[str, Any]) -> str:
    review = job.get("reviewModel") or {}
    confirmed = bool(review) and review_gate(review)["exportReady"] and review.get("reviewState", {}).get("previewRevision") == review.get("revision")
    planning_model = compile_confirmed_planning_model(job) if confirmed else build_planning_model(job)
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError("策划模型校验失败：" + "；".join(errors))
    job["planningModel"] = planning_model
    if confirmed:
        return _confirmed_plan(planning_model)
    mode = job["metadata"]["mode"]
    frames = job["frames"]
    document_frames = _document_frames(job)
    scenes = job["scenes"]
    name = job["metadata"].get("projectName") or "未命名项目"
    input_type = job["metadata"].get("inputType", "video")
    screenshot_input = input_type == "image_sequence"
    unseen_source = "截图" if screenshot_input else "视频"
    source_line = (
        f"- 原始截图：{len(frames)} 张（按用户确认顺序）"
        if screenshot_input else
        f"- 原视频：{job['video']['filename']}（{_time(job['video']['duration'])}）"
    )
    source_section = "截图顺序与页面状态" if screenshot_input else "视频章节与场景"
    locator_header = "顺序位置" if screenshot_input else "时间范围"
    pipeline = "有序截图 → ScreenCoder/UIED 结构扫描 → 单页识别 → 相邻状态分析 → 策划案" if screenshot_input else "全片扫描 → 场景检测 → ScreenCoder/UIED 结构扫描 → 场景理解 → 事件因果链 → 策划案"
    shared = f"""# {name}｜{'玩法' if mode == 'gameplay' else '交互'}策划案

## 1. 分析说明

{source_line}
- 分析方向：{'玩法侧' if mode == 'gameplay' else '交互侧'}
- 场景数：{len(scenes)}
- 参考画面：{len(frames)}
- 详细事件帧：{job.get('analysisSummary', {}).get('detailFrameCount', 0)}
- 处理链路：{pipeline}
- 补充要求：{job['metadata'].get('scope') or '无'}

## 2. {source_section}

| # | {locator_header} | 场景/状态 | 摘要 | 参考画面 |
|---|---|---|---|---|
{_scene_table(scenes, input_type)}
"""
    if mode == "gameplay":
        domain = f"""
## 3. 核心玩法与玩家目标

{chr(10).join(f"- 场景 {scene['id'] + 1}：{_value(scene['analysis'].get('objective'))}；可见规则：{_value(scene['analysis'].get('visibleRules'))}" for scene in scenes)}

## 4. 核心循环

玩家观察当前游戏状态 → 执行输入 → 系统进行规则判定 → 产生数值/视听反馈 → 更新游戏状态 → 进入下一轮。具体节点以事件链为准，未展示环节不得作为事实。

## 5. 玩家操作与事件因果链

{_event_chains(frames, input_type)}

## 6. 游戏状态机

{chr(10).join(f"- {_time(scene['start'])}–{_time(scene['end'])}：{_value(scene['analysis'].get('sceneType'))}；进入：{_value(scene['analysis'].get('entryCondition'))}；退出：{_value(scene['analysis'].get('exitCondition'))}" for scene in scenes)}

## 7. 规则、数值和胜负条件

- 汇总所有明确展示的规则、资源变化、计分和胜负线索；后台参数及未出现的关卡配置列入待确认。

## 8. 游戏反馈

{chr(10).join(f"- {frame['id']} · {_time(frame['timestamp'])}：{_value(frame['analysis'].get('gameFeedback') or frame['analysis'].get('systemResponse'))}" for frame in frames if frame['analysis'].get('gameFeedback') or frame['analysis'].get('systemResponse'))}
"""
    else:
        domain = f"""
## 3. 用户目标与任务流程

{chr(10).join(f"{index + 1}. {_value(scene['analysis'].get('objective'))}（{_scene_locator(scene, input_type)}）" for index, scene in enumerate(scenes))}

## 4. 页面、弹窗与组件层级

{chr(10).join(f"- {frame['id']} · {_frame_locator(frame, input_type)}：{_value(frame['analysis'].get('regionStructure') or frame['structure'].get('regionCounts'))}" for frame in document_frames)}

## 5. 交互事件与状态转换

{_event_chains(document_frames, input_type)}

## 6. 组件状态与业务规则

- 每个组件需定义默认、悬停/按下、聚焦、选中、禁用、加载、成功和错误状态；只把视频明确出现的状态标记为事实。

## 7. 动效与即时反馈

{chr(10).join(f"- {frame['id']} · {_frame_locator(frame, input_type)}：{_value(frame['analysis'].get('motion') or frame['analysis'].get('systemResponse'))}" for frame in document_frames if frame['analysis'].get('motion') or frame['analysis'].get('systemResponse'))}

## 8. 异常、边界状态与响应式

- 检查加载、空、错误、无权限、弱网、重复提交、输入校验、撤销和设备安全区；{unseen_source}未展示项均标记为待确认。
{_auxiliary_state_notes(job)}
"""
    evidence = f"""
## 9. 未知与待确认项

{chr(10).join(f"- {frame['id']} · {_frame_locator(frame, input_type)}：{_value(frame['analysis'].get('unknowns'))}" for frame in document_frames if frame['analysis'].get('unknowns')) or '- 无'}

## 10. 验收标准

- 策划结论与原始素材展示的流程、页面状态和交互反馈保持一致。
- 明确展示、合理推断和未知待确认严格区分。
- 核心操作必须形成“前置状态 → 输入 → 响应 → 后置状态”闭环。
- 实现后录屏需对比流程、组件层级、反馈和状态结果是否一致。

## 11. 自动质量审计

- 质量分：{job.get('qualityReport', {}).get('score', '待计算')}/100
- 待审核项：{job.get('qualityReport', {}).get('reviewItemCount', 0)}
- 检查项：{_value(job.get('qualityReport', {}).get('checks'))}

## 12. 设计交付状态

- 结构状态：{planning_model['designHandoff']['status']}
- 可交付目标：{_value(planning_model['designHandoff']['targets'])}
- 已生成外部产物：{_value(planning_model['designHandoff']['generatedArtifacts'])}
- 说明：当前已生成可供飞书画板或 Figma 转换的结构数据；只有连接可调用且实际写入成功后，才标记为已生成外部产物。
"""
    return shared + domain + evidence


def _confirmed_plan(model: dict[str, Any]) -> str:
    project = model.get("project") or {}
    interaction = model.get("interaction") or {}
    flow = interaction.get("taskFlow") or (model.get("gameplay") or {}).get("coreLoop") or []
    constraints = (model.get("extensions") or {}).get("crossStateConstraints") or []
    scenes = model.get("scenes") or []
    components = model.get("components") or []
    scene_lines = []
    for scene in scenes:
        title = planner_board_text(scene.get("title")) or "未命名页面"
        entry = planner_board_text(scene.get("entryCondition")) or "进入该页面"
        exit_state = planner_board_text(scene.get("exitCondition")) or "完成当前操作"
        scene_lines.append(f"- {title}：{entry} → {exit_state}（代表帧：{', '.join(item.get('sourceId', '') for item in scene.get('evidence') or [])}）")
    flow_lines = []
    for item in flow:
        trigger = planner_board_text(item.get("trigger"))
        if not trigger or not any("\u4e00" <= char <= "\u9fff" for char in trigger) or trigger in {"无明确操作", "待确认", "未知待确认", "系统自动进入"}:
            continue
        source = planner_board_text(item.get("from")) or "当前页面"
        target = planner_board_text(item.get("to")) or "下一页面"
        flow_lines.append(f"- {source} → {trigger} → {target}")
    component_lines = [f"- {planner_board_text(item.get('name')) or '页面元素'}" for item in components]
    constraint_lines = []
    for item in constraints:
        text = planner_board_text(item.get("text"))
        if text:
            constraint_lines.append(f"- {text}")
    return "\n".join([
        f"# {project.get('name') or '未命名项目'}｜{'交互' if model.get('mode') == 'interaction' else '玩法'}策划案",
        "", "## 已确认流程", *scene_lines,
        "", "## 交互任务流", *(flow_lines or ["- 当前素材没有足够证据建立页面间跳转关系。"]),
        "", "## 页面元素与状态", *(component_lines or ["- 以各页面右侧说明为准。"]),
        "", "## 异常与跨页面影响", *(constraint_lines or ["- 当前没有需要单独标注的异常或跨页面影响。"]),
        "", "## 设计交付状态", "- 已生成策划审核结构",
    ])


def write_scene_specs(job_dir: Path, job: dict[str, Any]) -> list[str]:
    specs_dir = job_dir / "specs"
    specs_dir.mkdir(exist_ok=True)
    paths = []
    frame_map = {frame["id"]: frame for frame in job["frames"]}
    for scene in job["scenes"]:
        analysis = scene.get("analysis", {})
        scene_frames = [frame_map[frame_id] for frame_id in scene["frameIds"] if frame_id in frame_map]
        assets = [asset for frame in scene_frames for asset in frame.get("structure", {}).get("assetCandidates", [])]
        regions = [frame.get("structure", {}).get("regionTree", {}) for frame in scene_frames[:3]]
        content = f"""# Scene {scene['id'] + 1} Specification

## Overview

- Time: {_time(scene['start'])}–{_time(scene['end'])}
- Type: {_value(analysis.get('sceneType'))}
- Title: {_value(analysis.get('title'))}
- Objective: {_value(analysis.get('objective'))}
- Interaction model: {_value(analysis.get('interactionModel'))}
- Reference frames: {', '.join(scene['frameIds'])}

## Entry and Exit

- Entry condition: {_value(analysis.get('entryCondition'))}
- Exit condition: {_value(analysis.get('exitCondition'))}
- State changes: {_value(analysis.get('stateChanges'))}

## Region and Component Structure

```json
{__import__('json').dumps(regions, ensure_ascii=False, indent=2)}
```

## Assets

{chr(10).join(f"- {asset.get('path')} · bbox={asset.get('bbox')}" for asset in assets) or '- None detected'}

## Rules and Behaviors

- Visible rules: {_value(analysis.get('visibleRules'))}
- Summary: {_value(analysis.get('summary'))}

## Review Quality

- Conclusion level: {_value(analysis.get('evidenceLevel'))}
- Confidence: {_value(analysis.get('confidence'))}
- Uncertainties: {_value(analysis.get('uncertainties'))}
"""
        path = specs_dir / f"scene-{scene['id'] + 1:03d}.spec.md"
        path.write_text(content, encoding="utf-8")
        paths.append(f"specs/{path.name}")
    return paths
