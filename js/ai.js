// AI 视觉解读：API 调用、JSON 解析、帧数据同步

async function aiInterpretFrames() {
  const key = $("apiKey").value.trim();
  const apiBaseValue = $("apiUrl").value.trim();
  const usingLocalProxy = /^https?:\/\/(127\.0\.0\.1|localhost):8787\/v1\/?$/i.test(apiBaseValue);
  if (!key && !usingLocalProxy) {
    setProgress(55, "等待 API Key");
    setStatus("未填写 API Key。请先在左侧填入百炼 API Key；关键帧简述需要由 AI 生成。");
    return;
  }
  if (!state.frames.length) {
    setProgress(0, "未提取关键帧");
    setStatus("请先提取关键帧。");
    return;
  }

  rememberApiConfig();
  const apiUrl = normalizeChatCompletionsUrl(apiBaseValue || "http://127.0.0.1:8787/v1");
  const model = $("model").value.trim() || "qwen3.6-plus";
  const headers = usingLocalProxy
    ? { "Content-Type": "application/json" }
    : { "Content-Type": "application/json", "Authorization": `Bearer ${key}` };

  state.analysisMode = $("projectType").value;
  const useSystematic = $("systematicMode").checked && state.sceneGroups.length > 0;
  const totalFrames = state.frames.length;

  if (useSystematic) {
    await systematicInterpret({ apiUrl, model, headers, totalFrames });
  } else {
    await standardInterpret({ apiUrl, model, headers, totalFrames });
  }
}

// ---- 标准解读（短视频，逐帧）----

async function standardInterpret({ apiUrl, model, headers, totalFrames }) {
  // 根据帧数动态调整批次大小：总帧数多时每批 3 帧，少时每批 1 帧
  const batchSize = totalFrames > 30 ? 3 : totalFrames > 15 ? 2 : 1;
  const batches = chunkFrames(state.frames, batchSize);
  let totalMatched = 0;
  const rawLogs = [];

  for (let i = 0; i < batches.length; i++) {
    const batch = batches[i];
    const start = 58 + (i / Math.max(1, batches.length)) * 32;
    setProgress(start, `AI 解读第 ${i + 1}/${batches.length} 批，共 ${batch.length} 帧`);
    setStatus(`正在调用视觉模型解读关键帧：第 <strong>${i + 1}</strong> / ${batches.length} 批`);
    try {
      const result = await requestFrameBatch({
        apiUrl, model, headers, batch,
        contextFrames: contextFramesFor(batch[0]),
        batchIndex: i, totalBatches: batches.length,
        maxTokens: batchSize > 1 ? 3200 : 1600
      });
      rawLogs.push(`## Batch ${i + 1}/${batches.length}\n\n${result.text}`);
      totalMatched += syncFrameItems(result.items, batch);
      renderFrames();
    } catch (error) {
      rawLogs.push(`## Batch ${i + 1}/${batches.length} ERROR\n\n${error.message}`);
      setStatus(`第 <strong>${i + 1}</strong> 批超时或失败，已跳过，后面会按单帧自动重试。`);
    }
  }

  await retryMissingFrames({ apiUrl, model, headers, rawLogs, totalMatched });
}

// ---- 系统解读（长视频，场景 + 帧两级）----

async function systematicInterpret({ apiUrl, model, headers, totalFrames }) {
  const rawLogs = [];
  let totalMatched = 0;

  // Pass 1: 场景级概览 — 每个场景取首帧，AI 识别场景类型和整体结构
  setProgress(56, "系统解读：场景级概览");
  setStatus("正在系统解读：先识别场景结构...");
  const sceneSnapshots = state.sceneGroups.map((group) => ({
    sceneId: group.sceneId,
    label: group.label,
    frameCount: group.frames.length,
    thumbnail: group.frames[0] // 取场景首帧作为缩略图
  }));

  const sceneOverviewBatch = chunkFrames(sceneSnapshots.map((s) => s.thumbnail), Math.min(5, sceneSnapshots.length));
  const sceneOverviews = [];

  for (let i = 0; i < sceneOverviewBatch.length; i++) {
    const batch = sceneOverviewBatch[i];
    try {
      const result = await requestSceneOverview({ apiUrl, model, headers, batch, batchIndex: i, totalBatches: sceneOverviewBatch.length });
      rawLogs.push(`## Scene Overview Batch ${i + 1}\n\n${result.text}`);
      sceneOverviews.push(...(result.scenes || []));
    } catch (error) {
      rawLogs.push(`## Scene Overview Batch ${i + 1} ERROR\n\n${error.message}`);
    }
  }

  // Pass 2: 场景级摘要写入帧
  for (const overview of sceneOverviews) {
    const group = state.sceneGroups.find((g) => g.sceneId === overview.sceneId);
    if (!group) continue;
    group.sceneType = overview.sceneType || "";
    group.summary = overview.sceneDescription || "";
    group.eventSummary = overview.eventSummary || "";
    group.startTime = Math.min(...group.frames.map((frame) => frame.timestamp || 0));
    group.endTime = Math.max(...group.frames.map((frame) => frame.timestamp || 0));
    for (const frame of group.frames) {
      frame.what = frame.what || overview.sceneDescription || "";
      frame.gameState = frame.gameState || overview.sceneType || "";
    }
  }

  // Pass 3: 逐帧详细解读（场景内批量）
  setProgress(65, "系统解读：逐帧详细分析");
  setStatus("正在系统解读：逐帧详细分析...");
  const batchSize = Math.min(4, Math.max(2, Math.ceil(totalFrames / 20)));
  const batches = chunkFrames(state.frames, batchSize);

  for (let i = 0; i < batches.length; i++) {
    const batch = batches[i];
    const start = 65 + (i / Math.max(1, batches.length)) * 25;
    const sceneIds = [...new Set(batch.map((f) => f.sceneGroup).filter((id) => id >= 0))];
    setProgress(start, `详细解读第 ${i + 1}/${batches.length} 批（场景 ${sceneIds.join(", ")}）`);
    setStatus(`正在解读：第 <strong>${i + 1}</strong> / ${batches.length} 批，共 ${batch.length} 帧`);
    try {
      const result = await requestFrameBatch({
        apiUrl, model, headers, batch,
        contextFrames: contextFramesFor(batch[0]),
        batchIndex: i, totalBatches: batches.length,
        maxTokens: 3200,
        systematic: true,
        sceneContext: state.sceneGroups
      });
      rawLogs.push(`## Detail Batch ${i + 1}/${batches.length}\n\n${result.text}`);
      totalMatched += syncFrameItems(result.items, batch);
      renderFrames();
    } catch (error) {
      rawLogs.push(`## Detail Batch ${i + 1}/${batches.length} ERROR\n\n${error.message}`);
      setStatus(`第 <strong>${i + 1}</strong> 批超时或失败，已跳过。`);
    }
  }

  await retryMissingFrames({ apiUrl, model, headers, rawLogs, totalMatched });
}

// ---- 场景概览请求 ----

async function requestSceneOverview({ apiUrl, model, headers, batch, batchIndex, totalBatches }) {
  const mode = $("projectType").value;
  const modeInstruction = mode === "gameplay"
    ? "重点识别玩法阶段、核心机制、玩家目标、状态转换、胜负或结算线索。"
    : "重点识别用户任务、页面/弹窗、交互模式、操作路径、前后状态与异常状态。";
  const content = [{
    type: "text",
    text: `你是资深${mode === "gameplay" ? "游戏玩法策划" : "产品交互策划"}。这是长视频的场景首帧，请建立章节级概览。${modeInstruction}输出 JSON 数组。

每项字段：
- sceneId: 从 0 开始的序号
- sceneType: 场景类型（如：主菜单、关卡选择、核心玩法、暂停、胜利结算、失败结算、商店、图鉴、设置、Loading、信息展示、表单填写、预览编辑、结果展示、分享页等）
- sceneDescription: 一句话描述该场景的核心内容
- eventSummary: 该场景可能包含的“操作 → 系统响应 → 状态变化”摘要；无法确认时明确写未知

只输出 JSON 数组，不要 Markdown，不要解释。`
  }];
  for (let i = 0; i < batch.length; i++) {
    content.push({ type: "text", text: `场景 ${batch[i].sceneGroup >= 0 ? batch[i].sceneGroup : batchIndex * 5 + i}` });
    content.push({ type: "image_url", image_url: { url: batch[i].dataUrl } });
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  let res;
  try {
    res = await fetch(apiUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({ model, messages: [{ role: "user", content }], temperature: 0.1, max_tokens: 1200 }),
      signal: controller.signal
    });
  } catch (error) {
    clearTimeout(timeout);
    throw new Error(error.name === "AbortError" ? "场景概览超时" : `场景概览异常：${error.message}`);
  }
  clearTimeout(timeout);
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`场景概览失败：${res.status}\n${errText}`);
  }
  const json = await res.json();
  const text = json.choices?.[0]?.message?.content || "";
  let scenes = [];
  try {
    scenes = parseModelJson(text);
  } catch (_) { /* fallback */ }
  return { text, scenes: Array.isArray(scenes) ? scenes : [] };
}

// ---- 失败帧重试 ----

async function retryMissingFrames({ apiUrl, model, headers, rawLogs, totalMatched }) {
  const missing = state.frames.filter((frame) => shouldRetryInterpretation(frame));
  if (missing.length) {
    setProgress(92, `自动重试失败帧 ${missing.length} 个`);
    setStatus(`检测到 <strong>${missing.length}</strong> 个关键帧为空或明显无效，正在自动重试。`);
    const retryBatches = chunkFrames(missing, 1);
    for (let i = 0; i < retryBatches.length; i++) {
      const batch = retryBatches[i];
      try {
        const result = await requestFrameBatch({
          apiUrl, model, headers, batch,
          contextFrames: contextFramesFor(batch[0]),
          batchIndex: i, totalBatches: retryBatches.length,
          retry: true, maxTokens: 1600
        });
        rawLogs.push(`## Retry ${i + 1}/${retryBatches.length}\n\n${result.text}`);
        totalMatched += syncFrameItems(result.items, batch);
        renderFrames();
      } catch (error) {
        rawLogs.push(`## Retry ${i + 1}/${retryBatches.length} ERROR\n\n${error.message}`);
      }
    }
  }

  const stillMissing = state.frames.filter((frame) => shouldRetryInterpretation(frame));
  const weakFrames = state.frames.filter((frame) => !shouldRetryInterpretation(frame) && needsDetailReview(frame));
  const output = $("output");
  output.value = `AI 解读已分批同步到关键帧框。\n\n同步次数：${totalMatched}\n失败帧数：${stillMissing.length}/${state.frames.length}\n细节待补帧数：${weakFrames.length}/${state.frames.length}\n\n${rawLogs.join("\n\n---\n\n")}`;
  if (stillMissing.length) {
    setProgress(96, "仍有关键帧需要人工补充");
    setStatus(`AI 已完成分批解读，但仍有 <strong>${stillMissing.length}</strong> 帧为空或明显无效。右侧保留原始返回供检查。`);
  } else {
    setProgress(100, "AI 解读完成，等待人工确认");
    setStatus(`AI 已同步全部 <strong>${state.frames.length}</strong> 个关键帧。${weakFrames.length ? `其中 <strong>${weakFrames.length}</strong> 帧建议人工补充组件/素材/布局细节。` : "请人工检查、修正，然后勾选确认。"}`);
  }
}

// ---- 工具函数 ----

function chunkFrames(frames, size) {
  const chunks = [];
  for (let i = 0; i < frames.length; i += size) chunks.push(frames.slice(i, i + size));
  return chunks;
}

function contextFramesFor(frame) {
  const index = state.frames.findIndex((candidate) => candidate.id === frame.id);
  if (index < 0) return [frame];
  return state.frames.slice(Math.max(0, index - 1), Math.min(state.frames.length, index + 2));
}

async function requestFrameBatch({ apiUrl, model, headers, batch, contextFrames = batch, batchIndex, totalBatches, retry = false, maxTokens = 1600, systematic = false, sceneContext = [] }) {
  const targetIds = batch.map((frame) => frame.id).join(", ");
  const contextIds = contextFrames.map((frame) => frame.id).join(", ");

  let sceneHint = "";
  if (systematic && sceneContext.length) {
    const relatedScenes = [...new Set(batch.map((f) => f.sceneGroup).filter((id) => id >= 0))];
    sceneHint = `\n这些帧属于场景 ${relatedScenes.join(", ")}。请根据所属场景的上下文分析每帧的详细内容。`;
  }

  const mode = $("projectType").value;
  const domainRules = mode === "gameplay"
    ? `当前输出方向是玩法策划。重点还原玩家输入、核心循环、规则约束、数值变化、游戏状态机、胜负条件和反馈。不要把普通页面切换当成玩法机制。`
    : `当前输出方向是交互策划。重点还原用户任务、页面/弹窗/组件层级、操作前状态、输入事件、系统响应、操作后状态、动效和异常状态。不要虚构玩法规则。`;
  const content = [{
    type: "text",
    text: `只分析网页产品/游戏本体，忽略拍摄环境/设备/社媒字幕。目标帧：${targetIds}。上下文帧：${contextIds}，只用于比较，不要输出非目标帧。${sceneHint}

${domainRules}

请输出 JSON 数组，数组内只包含目标帧，每项字段固定为：
id, what, requirement, formula, visual, components, assets, layout, motion, regionStructure, eventType, userAction, beforeState, systemResponse, afterState, evidenceLevel, confidence, gameMechanics, gameState, gameFeedback。

要求：
- 每帧必须有描述；如果同前帧，必须写出本帧相对前后帧的差异或动效阶段。
- formula：从 54 排版公式中选 1-3 个，例如留白/中心/模块/拼贴/重叠/黄金比例/动态/玻璃/颗粒感等，并写焦点、视线路径、留白、密度、层级。
- visual/assets：每种视觉元素都写风格取向：可爱/写实/拟物/手绘/极简/复古/高级感/童趣/纸质拼贴/胶片感等，以及材质、纹理、阴影。
- components：列出可见网页组件和状态。
- regionStructure：像 ScreenCoder 一样分解可见区域与父子层级，例如 header/sidebar/main/modal/HUD/playfield/control bar，并说明遮挡或叠层关系。
- eventType：click/tap/drag/swipe/scroll/input/wait/state-transition/unknown 之一。
- userAction/beforeState/systemResponse/afterState：强制形成因果链；只写画面可支持的结论。
- evidenceLevel：只能是“明确展示”“合理推断”“未知待确认”；confidence 只能是“高”“中”“低”。
- layout：写位置、比例、对齐、间距、叠放、响应式推断。
- motion：写点击、滑动、输入、选择、hover/focus、提交、分享、翻卡/弹出等反馈；包含触发、对象、from/to、时长/easing 推断。
- gameMechanics：如果项目是游戏/玩法 Demo，识别核心玩法机制（如三消、跑酷、答题、养成、放置、塔防、弹球、切水果等），写出核心循环、操作方式、规则约束。
- gameState：如果是游戏，判断当前帧所处的游戏状态（主菜单、关卡选择、loading、游戏中、暂停、胜利、失败、结算、排行榜、商店、图鉴等）。
- gameFeedback：如果是游戏，识别游戏特有的交互反馈（得分飘字、连击/Combo 特效、粒子爆炸、血条/能量条变化、屏幕震动、倒计时、进度条、收集动画、升级提示等）。

不要输出 Markdown，不要解释，只返回 JSON。项目名：${$("projectName").value.trim() || "ai策划案工具项目"}`
  }];
  for (const frame of contextFrames) {
    const role = batch.some((target) => target.id === frame.id) ? "TARGET 输出此帧" : "CONTEXT 只用于比较，不要输出此帧";
    content.push({ type: "text", text: `${role} · Evidence ${frame.id} · ${frame.sourceName} · ${frame.label}` });
    content.push({ type: "image_url", image_url: { url: frame.dataUrl } });
  }

  const controller = new AbortController();
  const timeoutDuration = retry ? 60000 : (maxTokens > 2000 ? 90000 : 45000);
  const timeout = setTimeout(() => controller.abort(), timeoutDuration);
  let res;
  try {
    res = await fetch(apiUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({ model, messages: [{ role: "user", content }], temperature: 0.1, max_tokens: maxTokens }),
      signal: controller.signal
    });
  } catch (error) {
    clearTimeout(timeout);
    throw new Error(error.name === "AbortError" ? `AI 解读超时：${timeoutDuration / 1000} 秒未返回。` : `AI 请求异常：${error.message}`);
  }
  clearTimeout(timeout);
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`AI 解读失败：${res.status}\n${errText}`);
  }
  const json = await res.json();
  const text = json.choices?.[0]?.message?.content || json.output_text || (json.output || []).flatMap((item) => item.content || []).map((c) => c.text || "").join("\n");
  let items = [];
  try {
    items = parseModelJson(text);
  } catch (error) {
    items = buildFallbackItemsFromText(text, batch);
  }
  return { text, items: Array.isArray(items) ? items : [] };
}

// ---- JSON 解析与字段映射 ----

function buildFallbackItemsFromText(text, batch) {
  const raw = String(text || "").trim();
  if (!raw) return [];
  return batch.map((frame) => ({
    id: frame.id,
    what: raw.slice(0, 700),
    requirement: "AI 返回不是标准 JSON，已保留原始解读。请人工拆分为功能、组件、视觉和动效要求。",
    formula: "待人工从原始解读中确认排版公式；优先判断焦点、视线路径、留白、密度和层级。",
    visual: raw.slice(0, 700),
    components: "待人工从原始解读中提取可见组件。",
    assets: "待人工从原始解读中提取视觉资产和装饰元素。",
    layout: "待人工从原始解读中提取布局比例和空间关系。",
    motion: "待人工从原始解读中提取点击、滑动、输入、选择或转场反馈。",
    gameMechanics: "待人工从原始解读中确认游戏机制和核心玩法。",
    gameState: "待人工从原始解读中确认当前游戏状态。",
    gameFeedback: "待人工从原始解读中提取游戏交互反馈和特效。"
    ,regionStructure: "待人工识别页面区域与组件层级。"
    ,eventType: "unknown"
    ,userAction: "待人工确认操作。"
    ,beforeState: "待人工确认操作前状态。"
    ,systemResponse: "待人工确认系统响应。"
    ,afterState: "待人工确认操作后状态。"
    ,evidenceLevel: "未知待确认"
    ,confidence: "低"
  }));
}

function syncFrameItems(items, targetFrames) {
  let matched = 0;
  const usedIndexes = new Set();
  for (const item of items) {
    const normalized = normalizeFrameItem(item);
    const targetIndex = targetFrames.findIndex((f) => f.id === normalized.id);
    if (targetIndex < 0) continue;
    const frame = targetFrames[targetIndex];
    if (!frame) continue;
    usedIndexes.add(targetIndex);
    applyFrameItem(frame, normalized);
    matched++;
  }
  if (matched < targetFrames.length && items.length) {
    items.slice(0, targetFrames.length).forEach((item, index) => {
      if (usedIndexes.has(index)) return;
      const frame = targetFrames[index];
      if (!frame) return;
      applyFrameItem(frame, normalizeFrameItem(item));
      matched++;
    });
  }
  return matched;
}

function applyFrameItem(frame, item) {
  frame.what = item.what || frame.what;
  frame.requirement = item.requirement || frame.requirement;
  frame.formula = item.formula || frame.formula;
  frame.visual = item.visual || frame.visual;
  frame.components = item.components || frame.components;
  frame.assets = item.assets || frame.assets;
  frame.layout = item.layout || frame.layout;
  frame.motion = item.motion || frame.motion;
  frame.gameMechanics = item.gameMechanics || frame.gameMechanics;
  frame.gameState = item.gameState || frame.gameState;
  frame.gameFeedback = item.gameFeedback || frame.gameFeedback;
  frame.regionStructure = item.regionStructure || frame.regionStructure;
  frame.eventType = item.eventType || frame.eventType;
  frame.userAction = item.userAction || frame.userAction;
  frame.beforeState = item.beforeState || frame.beforeState;
  frame.systemResponse = item.systemResponse || frame.systemResponse;
  frame.afterState = item.afterState || frame.afterState;
  frame.evidenceLevel = item.evidenceLevel || frame.evidenceLevel;
  frame.confidence = item.confidence || frame.confidence;
}

function normalizeFrameItem(item) {
  return {
    id: readItemField(item, ["id", "ID", "evidence", "Evidence", "证据", "帧ID", "关键帧ID"]),
    what: readItemField(item, ["what", "state", "screen", "description", "这一帧在干什么", "产品状态", "页面状态", "用户动作", "画面说明"]),
    requirement: readItemField(item, ["requirement", "requirements", "need", "需求", "需求含义", "需要复刻什么", "复刻需求", "功能需求"]),
    formula: readItemField(item, ["formula", "layoutFormula", "typographyFormula", "composition", "排版公式", "视觉骨架", "构图公式", "版式公式"]),
    visual: readItemField(item, ["visual", "style", "aesthetic", "视觉", "视觉规格", "字体", "构图", "审美", "视觉风格"]),
    components: readItemField(item, ["components", "component", "componentList", "ui", "组件", "组件清单", "组件状态", "页面组件", "控件"]),
    assets: readItemField(item, ["assets", "asset", "materials", "decorations", "素材", "资产", "装饰", "图形元素", "视觉资产", "素材装饰"]),
    layout: readItemField(item, ["layout", "spacing", "size", "position", "布局", "尺寸", "空间关系", "比例", "位置", "排版"]),
    motion: readItemField(item, ["motion", "animation", "transition", "interaction", "动效", "转场", "反馈", "微交互", "动画"]),
    gameMechanics: readItemField(item, ["gameMechanics", "gameplay", "mechanic", "coreLoop", "游戏机制", "核心玩法", "玩法机制", "核心循环"]),
    gameState: readItemField(item, ["gameState", "state", "screen", "游戏状态", "当前状态", "游戏阶段"]),
    gameFeedback: readItemField(item, ["gameFeedback", "feedback", "fx", "游戏反馈", "交互反馈", "特效反馈", "游戏交互"])
    ,regionStructure: readItemField(item, ["regionStructure", "regions", "hierarchy", "页面区域", "组件层级", "区域结构"])
    ,eventType: readItemField(item, ["eventType", "event", "事件类型", "操作类型"])
    ,userAction: readItemField(item, ["userAction", "action", "input", "用户操作", "玩家操作"])
    ,beforeState: readItemField(item, ["beforeState", "before", "操作前状态", "前置状态"])
    ,systemResponse: readItemField(item, ["systemResponse", "response", "系统响应", "即时反馈"])
    ,afterState: readItemField(item, ["afterState", "after", "操作后状态", "结果状态"])
    ,evidenceLevel: readItemField(item, ["evidenceLevel", "evidenceType", "证据等级", "结论类型"])
    ,confidence: readItemField(item, ["confidence", "置信度"])
  };
}

function readItemField(item, names) {
  if (!item || typeof item !== "object") return "";
  for (const name of names) {
    if (Object.prototype.hasOwnProperty.call(item, name)) return stringifyFieldValue(item[name]);
  }
  return "";
}

function stringifyFieldValue(value) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.map(stringifyFieldValue).filter(Boolean).join("；");
  if (typeof value === "object") {
    return Object.entries(value).map(([key, val]) => `${key}：${stringifyFieldValue(val)}`).filter((line) => !line.endsWith("：")).join("；");
  }
  return String(value).trim();
}

function parseModelJson(text) {
  const cleaned = String(text || "").trim();
  const fenced = cleaned.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = fenced ? fenced[1].trim() : cleaned;
  try {
    return unwrapModelJson(JSON.parse(candidate));
  } catch (_) {
    const start = candidate.indexOf("[");
    const end = candidate.lastIndexOf("]");
    if (start >= 0 && end > start) return unwrapModelJson(JSON.parse(candidate.slice(start, end + 1)));
    throw _;
  }
}

function unwrapModelJson(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== "object") return [];
  for (const key of ["frames", "items", "results", "data", "关键帧", "解读", "结果"]) {
    if (Array.isArray(value[key])) return value[key];
  }
  return [value];
}

// ---- 质量检测 ----

function hasFrameInterpretation(frame) {
  return Boolean(
    (frame.what || "").trim() ||
    (frame.requirement || "").trim() ||
    (frame.formula || "").trim() ||
    (frame.visual || "").trim() ||
    (frame.components || "").trim() ||
    (frame.assets || "").trim() ||
    (frame.layout || "").trim() ||
    (frame.motion || "").trim() ||
    (frame.gameMechanics || "").trim() ||
    (frame.gameState || "").trim() ||
    (frame.gameFeedback || "").trim()
  );
}

function shouldRetryInterpretation(frame) {
  const text = [
    frame.what, frame.requirement, frame.formula, frame.visual,
    frame.components, frame.assets, frame.layout, frame.motion,
    frame.gameMechanics, frame.gameState, frame.gameFeedback
  ].map((value) => String(value || "").trim()).join("\n");
  if (!text) return true;
  const sameAsPrevious = /(上一帧|前一帧|同前帧|同上|相同|一致)/.test(text);
  const hasDelta = /(差异|变化|动效|动画|阶段|状态|从|到|变为|进入|离开|出现|消失|透明|位移|移动|缩放|旋转|翻转|焦点|选中|禁用|输入|预览|按钮|更新|过渡|停留)/.test(text);
  const invalidStatic = /(初始页面状态|确认.*状态|未展示明确|按静态状态)/.test(text);
  return text.length < 70 || invalidStatic || (sameAsPrevious && !hasDelta);
}

function needsDetailReview(frame) {
  const text = [
    frame.what, frame.requirement, frame.formula, frame.visual,
    frame.components, frame.assets, frame.layout, frame.motion,
    frame.gameMechanics, frame.gameState, frame.gameFeedback
  ].map((value) => String(value || "").trim()).join("\n");
  const detailBlocks = [frame.visual, frame.components, frame.assets, frame.layout].filter((value) => String(value || "").trim().length >= 18).length;
  return text.length < 150 || detailBlocks < 2;
}
