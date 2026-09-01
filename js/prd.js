// 玩法 / 交互双策划案生成。所有核心结论回链关键帧和时间点。

function confirmedFrames() {
  return state.frames.filter((frame) => frame.confirmed && hasFrameInterpretation(frame));
}

function evidenceRef(frame) {
  return `${frame.id} · ${formatTime(frame.timestamp || 0)}`;
}

function valueOrUnknown(value) {
  return String(value || "").trim() || "未知待确认";
}

function sceneTimeline(frames) {
  const groups = state.sceneGroups.length ? state.sceneGroups : [{ sceneId: 0, label: "场景 1", frames }];
  return groups.map((group, index) => {
    const selected = group.frames.filter((frame) => frames.includes(frame));
    if (!selected.length) return "";
    const start = Math.min(...selected.map((frame) => frame.timestamp || 0));
    const end = Math.max(...selected.map((frame) => frame.timestamp || 0));
    return `| ${index + 1} | ${formatTime(start)}–${formatTime(end)} | ${escapeMd(group.sceneType || group.label || "未分类场景")} | ${escapeMd(group.summary || selected[0].what || "待补充")} | ${selected.map((frame) => frame.id).join(", ")} |`;
  }).filter(Boolean).join("\n");
}

function evidenceTable(frames) {
  return frames.map((frame) => `| ${evidenceRef(frame)} | ${escapeMd(frame.what)} | ${escapeMd(frame.evidenceLevel)} | ${escapeMd(frame.confidence)} |`).join("\n");
}

function eventChains(frames) {
  return frames.map((frame, index) => `### ${index + 1}. ${evidenceRef(frame)}

- 事件类型：${valueOrUnknown(frame.eventType)}
- 操作前状态：${valueOrUnknown(frame.beforeState)}
- 用户/玩家操作：${valueOrUnknown(frame.userAction)}
- 系统响应：${valueOrUnknown(frame.systemResponse)}
- 操作后状态：${valueOrUnknown(frame.afterState)}
- 证据等级：${valueOrUnknown(frame.evidenceLevel)}；置信度：${valueOrUnknown(frame.confidence)}`).join("\n\n");
}

function unknownItems(frames) {
  const uncertain = frames.filter((frame) => frame.evidenceLevel !== "明确展示" || frame.confidence === "低");
  if (!uncertain.length) return "- 当前确认帧中没有标记为低置信度的结论。";
  return uncertain.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.requirement)}（${frame.evidenceLevel} / ${frame.confidence}）`).join("\n");
}

function gameplayDocument({ projectName, platform, scope, frames }) {
  const mechanics = frames.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.gameMechanics)}`).join("\n");
  const states = frames.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.gameState)}`).join("\n");
  const feedback = frames.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.gameFeedback || frame.systemResponse)}`).join("\n");
  return `# ${projectName}｜玩法策划案

## 1. 文档说明

- 分析方向：玩法侧
- 目标平台：${platform}
- 视频素材：${state.assets.map((asset) => `${asset.name}${asset.duration ? `（${formatTime(asset.duration)}）` : ""}`).join("、")}
- 分析要求：${scope}
- 证据原则：明确展示、合理推断、未知待确认严格分开；关键结论必须回链时间点。

## 2. 玩法概述

- 根据确认视频证据，本案围绕玩家输入、规则响应、状态变化与反馈建立可复核的玩法定义。
- 尚未被视频展示的后台数值、完整关卡配置和商业化规则不得写成事实。

## 3. 视频章节与场景

| # | 时间范围 | 场景/游戏状态 | 场景摘要 | Evidence |
|---|---|---|---|---|
${sceneTimeline(frames)}

## 4. 核心玩法与循环

${mechanics}

### 4.1 核心循环归纳

玩家观察当前状态 → 执行操作 → 系统判定规则 → 给出视听/数值反馈 → 更新游戏状态 → 进入下一轮。具体规则以以下事件链和时间证据为准。

## 5. 玩家操作与事件因果链

${eventChains(frames)}

## 6. 游戏状态机

${states}

- 每个状态需补齐进入条件、允许操作、退出条件、失败路径和 UI 表现。
- 视频未出现的暂停、异常中断、重试和恢复流程标记为待确认。

## 7. 规则、数值、胜负条件

${frames.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.requirement)}`).join("\n")}

## 8. 反馈与表现

${feedback}

## 9. 场景结构与界面层级

${frames.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.regionStructure || frame.components)}`).join("\n")}

## 10. 证据索引

| Evidence / 时间点 | 画面或状态 | 结论类型 | 置信度 |
|---|---|---|---|
${evidenceTable(frames)}

## 11. 推断、未知与待确认项

${unknownItems(frames)}

## 12. 验收标准

- 核心循环可完整执行，输入、判定、反馈、状态更新形成闭环。
- 状态转换、计分/资源变化、胜负条件均可回链视频证据或明确标注推断。
- 实现录屏需与对应 Evidence 对比操作时序、反馈强度和状态结果。`;
}

function interactionDocument({ projectName, platform, scope, frames }) {
  return `# ${projectName}｜交互策划案

## 1. 文档说明

- 分析方向：交互侧
- 目标平台：${platform}
- 视频素材：${state.assets.map((asset) => `${asset.name}${asset.duration ? `（${formatTime(asset.duration)}）` : ""}`).join("、")}
- 分析要求：${scope}
- 证据原则：明确展示、合理推断、未知待确认严格分开；关键结论必须回链时间点。

## 2. 用户任务与产品流程

${frames.map((frame, index) => `${index + 1}. ${valueOrUnknown(frame.what)}（${evidenceRef(frame)}）`).join("\n")}

## 3. 视频章节、页面与弹窗

| # | 时间范围 | 页面/状态 | 场景摘要 | Evidence |
|---|---|---|---|---|
${sceneTimeline(frames)}

## 4. 页面区域与组件树

${frames.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.regionStructure || frame.components)}`).join("\n")}

## 5. 交互事件与状态转换

${eventChains(frames)}

## 6. 组件状态与业务规则

${frames.map((frame) => `- ${evidenceRef(frame)}\n  - 组件：${valueOrUnknown(frame.components)}\n  - 规则：${valueOrUnknown(frame.requirement)}`).join("\n")}

## 7. 动效和即时反馈

${frames.map((frame) => `- ${evidenceRef(frame)}：${valueOrUnknown(frame.motion || frame.systemResponse)}`).join("\n")}

## 8. 视觉、布局与资产

${frames.map((frame) => `- ${evidenceRef(frame)}\n  - 视觉：${valueOrUnknown(frame.visual)}\n  - 布局：${valueOrUnknown(frame.layout)}\n  - 资产：${valueOrUnknown(frame.assets)}`).join("\n")}

## 9. 异常与边界状态

- 检查加载、空状态、错误、无权限、弱网、重复提交、禁用、输入校验和操作撤销。
- 未在视频中展示的边界状态均为待确认，不得作为既定行为。

## 10. 响应式与设备差异

- 基于视频只确认已展示设备；其他断点需要额外素材或在实现阶段验证。
- 保持导航、主内容、弹层、固定操作区和软键盘避让关系一致。

## 11. 证据索引

| Evidence / 时间点 | 页面或状态 | 结论类型 | 置信度 |
|---|---|---|---|
${evidenceTable(frames)}

## 12. 推断、未知与待确认项

${unknownItems(frames)}

## 13. 验收标准

- 用户可以按视频顺序完成核心任务，所有操作均有明确反馈。
- 每个交互包含操作前状态、输入、系统响应、操作后状态。
- 页面、弹窗、组件状态和动效均能回链相应 Evidence 时间点。`;
}

function generatePrd() {
  const frames = confirmedFrames();
  if (!frames.length) {
    setStatus("请先确认至少一个关键帧，并填写帧解读。");
    return;
  }
  const params = {
    projectName: $("projectName").value.trim() || "未命名项目",
    platform: $("platform").value,
    scope: $("scope").value.trim() || "基于视频证据还原完整策划案。",
    frames
  };
  const gameplay = $("projectType").value === "gameplay";
  $("output").value = gameplay ? gameplayDocument(params) : interactionDocument(params);
  setStatus(`已基于 <strong>${frames.length}</strong> 个确认帧生成${gameplay ? "玩法" : "交互"}策划案。`);
}
