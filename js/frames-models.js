// 关键帧提取、数据模型与渲染

// ---- 自适应抽帧策略 ----

function chooseVideoSamples(duration) {
  if (!duration || !Number.isFinite(duration)) return [0];
  // 短视频：密集抽帧，保留动效细节
  if (duration <= 10) return uniformSamples(duration, 16);
  if (duration <= 35) return uniformSamples(duration, 18);
  // 中视频：适度间隔
  if (duration <= 120) return uniformSamples(duration, Math.round(duration / 2));
  // 长视频：每 10-15 秒一帧，上限 80 帧（后续场景检测会增补）
  if (duration <= 1200) return uniformSamples(duration, Math.min(80, Math.round(duration / 10)));
  // 超长视频（>20min）：每 15 秒一帧，上限 100 帧
  return uniformSamples(duration, Math.min(100, Math.round(duration / 15)));
}

function uniformSamples(duration, count) {
  const safeEnd = Math.max(0.3, duration - 0.25);
  const step = safeEnd / Math.max(1, count - 1);
  const samples = [];
  for (let i = 0; i < count; i++) {
    samples.push(Math.min(safeEnd, i * step));
  }
  return Array.from(new Set(samples.map((s) => Number(s.toFixed(2)))));
}

// ---- 场景变化检测 ----

function detectSceneChanges(pixelArrays, threshold = 0.35) {
  // pixelArrays: [{ second, pixels }] 按时间排序
  const changes = [];
  for (let i = 1; i < pixelArrays.length; i++) {
    const diff = pixelDiff(pixelArrays[i - 1].pixels, pixelArrays[i].pixels);
    if (diff >= threshold) {
      changes.push({
        second: pixelArrays[i].second,
        diff,
        prevSecond: pixelArrays[i - 1].second
      });
    }
  }
  return changes;
}

function pixelDiff(pixelsA, pixelsB) {
  if (!pixelsA || !pixelsB || pixelsA.length !== pixelsB.length) return 1;
  let diffCount = 0;
  const step = 4; // 每像素 RGBA 4 字节，只比较亮度（R 通道，跳过 3 个）
  for (let i = 0; i < pixelsA.length; i += step) {
    if (Math.abs(pixelsA[i] - pixelsB[i]) > 30) diffCount++;
  }
  return diffCount / (pixelsA.length / step);
}

async function captureVideoThumbnail(url, second, size = 32) {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.onloadedmetadata = () => {
      video.currentTime = Math.min(Math.max(0, second), Math.max(0, (video.duration || second) - 0.05));
    };
    video.onseeked = () => {
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, size, size);
      const imageData = ctx.getImageData(0, 0, size, size);
      resolve({ second, pixels: imageData.data });
    };
    video.onerror = () => resolve({ second, pixels: null });
    video.src = url;
  });
}

async function scanVideoScenes(asset) {
  const duration = asset.duration || 0;
  if (duration <= 35) return { baseSamples: chooseVideoSamples(duration), sceneChanges: [] };

  // 始终覆盖完整视频。长视频最多扫描 200 个低分辨率样本，而不是只扫描前 400 秒。
  const sampleInterval = Math.max(1, duration / 200);
  const scanCount = Math.min(200, Math.ceil(duration / sampleInterval) + 1);
  const thumbnails = [];

  for (let i = 0; i < scanCount; i++) {
    const second = Math.min(duration - 0.1, i * sampleInterval);
    const thumb = await captureVideoThumbnail(asset.url, second);
    thumbnails.push(thumb);
  }

  const sceneChanges = detectSceneChanges(thumbnails);
  return { baseSamples: chooseVideoSamples(duration), sceneChanges };
}

function mergeSceneSamples(baseSamples, sceneChanges) {
  const merged = new Set(baseSamples);
  for (const change of sceneChanges) {
    merged.add(change.second);
    // ScreenCoder 式局部加密：围绕边界框/场景变化点补取前后状态，形成事件证据链。
    for (const offset of [-0.8, -0.35, 0.35, 0.8]) merged.add(Math.max(0, change.second + offset));
  }
  const ordered = Array.from(merged).map((s) => Number(s.toFixed(2))).sort((a, b) => a - b);
  return limitSamplesAcrossTimeline(ordered, 160);
}

function limitSamplesAcrossTimeline(samples, limit) {
  if (samples.length <= limit) return samples;
  const selected = [];
  const last = samples.length - 1;
  for (let i = 0; i < limit; i++) selected.push(samples[Math.round((i / (limit - 1)) * last)]);
  return Array.from(new Set(selected));
}

// ---- 帧提取核心 ----

function imageToDataUrl(url, maxWidth = 512) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxWidth / img.naturalWidth);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve({ dataUrl: canvas.toDataURL("image/jpeg", 0.52), width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => resolve({ dataUrl: "", width: 0, height: 0 });
    img.src = url;
  });
}

function captureVideoFrame(url, second, maxWidth = 512) {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.onloadedmetadata = () => {
      video.currentTime = Math.min(Math.max(0, second), Math.max(0, (video.duration || second) - 0.1));
    };
    video.onseeked = () => {
      const width = video.videoWidth || 1;
      const height = video.videoHeight || 1;
      const scale = Math.min(1, maxWidth / width);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
      resolve({ dataUrl: canvas.toDataURL("image/jpeg", 0.52), width, height });
    };
    video.onerror = () => resolve({ dataUrl: "", width: 0, height: 0 });
    video.src = url;
  });
}

async function extractFrames() {
  if (!state.assets.length) {
    setStatus("请先上传视频或图片。");
    return;
  }
  state.frames = [];
  state.sceneGroups = [];
  setProgress(2, "准备抽帧");
  setStatus("正在扫描视频并提取关键帧...");
  let imageIndex = 1;
  let videoIndex = 1;
  const totalAssets = state.assets.length || 1;
  let doneAssets = 0;

  for (const asset of state.assets) {
    if (asset.kind === "image") {
      const img = await imageToDataUrl(asset.url);
      state.frames.push(makeFrame(`IMG-${String(imageIndex).padStart(2, "0")}`, asset, img, `图片 ${imageIndex}`));
      imageIndex++;
    } else {
      setProgress(5 + (doneAssets / totalAssets) * 25, `扫描场景：${asset.name}`);
      const { baseSamples, sceneChanges } = await scanVideoScenes(asset);
      const allSamples = mergeSceneSamples(baseSamples, sceneChanges);
      setProgress(5 + (doneAssets / totalAssets) * 30, `场景检测完成：${sceneChanges.length} 个切换点，共 ${allSamples.length} 个关键帧`);

      let doneSamples = 0;
      for (const second of allSamples) {
        const frame = await captureVideoFrame(asset.url, second);
        const frameObj = makeFrame(`V${String(videoIndex).padStart(2, "0")}-${formatTime(second)}`, asset, frame, `${formatTime(second)} / ${formatTime(asset.duration || 0)}`);
        frameObj.timestamp = second;
        frameObj.sceneGroup = findSceneGroup(second, sceneChanges);
        state.frames.push(frameObj);
        doneSamples++;
        const assetProgress = (doneAssets + doneSamples / allSamples.length) / totalAssets;
        setProgress(5 + assetProgress * 45, `抽帧中：${asset.name} ${doneSamples}/${allSamples.length}`);
      }
      // 保存场景分组信息
      buildSceneGroups(state.frames, sceneChanges);
      videoIndex++;
    }
    doneAssets++;
    setProgress(5 + (doneAssets / totalAssets) * 45, `已处理素材 ${doneAssets}/${totalAssets}`);
  }

  renderFrames();
  renderStats();
  setProgress(55, `已提取 ${state.frames.length} 个关键帧`);
  setStatus(`已提取 <strong>${state.frames.length}</strong> 个关键帧${state.sceneGroups.length ? `，检测到 <strong>${state.sceneGroups.length}</strong> 个场景切换` : ""}，正在进入 AI 解读...`);
  await aiInterpretFrames();
}

function findSceneGroup(second, sceneChanges) {
  if (!sceneChanges.length) return -1;
  for (let i = sceneChanges.length - 1; i >= 0; i--) {
    if (second >= sceneChanges[i].second) return i + 1;
  }
  return 0;
}

function buildSceneGroups(frames, sceneChanges) {
  state.sceneGroups = [];
  let groupIndex = 0;
  let groupFrames = [];
  for (const frame of frames) {
    const scene = findSceneGroup(frame.timestamp || 0, sceneChanges);
    if (scene !== groupIndex && groupFrames.length > 0) {
      state.sceneGroups.push({ sceneId: groupIndex, frames: groupFrames, label: `场景 ${groupIndex + 1}` });
      groupFrames = [];
    }
    groupIndex = scene;
    groupFrames.push(frame);
  }
  if (groupFrames.length > 0) {
    state.sceneGroups.push({ sceneId: groupIndex, frames: groupFrames, label: `场景 ${groupIndex + 1}` });
  }
}

function makeFrame(id, asset, image, label) {
  return {
    id,
    sourceName: asset.name,
    label,
    dataUrl: image.dataUrl,
    width: image.width,
    height: image.height,
    timestamp: 0,
    sceneGroup: -1,
    what: "",
    requirement: "",
    formula: "",
    visual: "",
    components: "",
    assets: "",
    layout: "",
    motion: "",
    gameMechanics: "",
    gameState: "",
    gameFeedback: "",
    regionStructure: "",
    eventType: "",
    userAction: "",
    beforeState: "",
    systemResponse: "",
    afterState: "",
    valueChanges: "",
    stateVariations: "",
    promptText: "",
    unknowns: "",
    evidenceLevel: "明确展示",
    confidence: "中",
    confirmed: false
  };
}

function renderFrames() {
  const frameList = $("frameList");
  if (!state.frames.length) {
    frameList.innerHTML = '<div class="notice">还没有关键帧。上传素材后点击"提取关键帧"。</div>';
    return;
  }
  let html = "";
  if (state.sceneGroups.length) {
    html += `<div class="notice" style="margin-bottom:12px">检测到 <strong>${state.sceneGroups.length}</strong> 个场景切换，帧已按场景分组。</div>`;
  }
  let lastScene = -1;
  html += state.frames.map((frame, index) => {
    const sceneLabel = frame.sceneGroup >= 0 && frame.sceneGroup !== lastScene
      ? (lastScene = frame.sceneGroup, `<div class="scene-divider"><span>场景 ${frame.sceneGroup + 1}</span>${typeof lastCompletedJobId !== "undefined" && lastCompletedJobId ? `<button class="btn scene-reanalyze" type="button" data-scene-id="${frame.sceneGroup}">重分析本场景</button>` : ""}</div>`)
      : "";
    return sceneLabel + `
    <article class="frame-card" data-index="${index}" data-frame-id="${frame.id}">
      <div class="frame-top">
        <img src="${frame.dataUrl}" alt="${frame.id}">
        <div class="frame-meta">
          <b>${frame.id}</b>
          <span>${frame.sourceName}</span>
          <span>${frame.label}</span>
          <span>${frame.width}x${frame.height}</span>
          ${frame.sceneGroup >= 0 ? `<span class="scene-tag">场景${frame.sceneGroup + 1}</span>` : ""}
          ${frame.timestamp != null && typeof lastCompletedJobId !== "undefined" && lastCompletedJobId ? `<button class="btn evidence-seek" type="button" data-time="${frame.timestamp}" data-frame-id="${frame.id}">在视频中定位</button>` : ""}
        </div>
      </div>
      <details class="frame-body" ${index < 2 ? "open" : ""}>
        <summary>展开审核字段 · ${frame.evidenceLevel || "待确认"} / ${frame.confidence || "-"}</summary>
        <div class="field">
          <label>这一帧在干什么 / 产品状态</label>
          <textarea data-field="what" data-index="${index}" placeholder="例如：用户在创建页填写收件人、选择邮票和花朵，右侧实时预览明信片。">${frame.what}</textarea>
        </div>
        <div class="field">
          <label>需求含义 / 需要复刻什么</label>
          <textarea data-field="requirement" data-index="${index}" placeholder="例如：需要有表单字段、字符计数、素材选择器、实时预览和提交按钮禁用规则。">${frame.requirement}</textarea>
        </div>
        <div class="field">
          <label>视觉 / 字体 / 构图</label>
          <textarea data-field="visual" data-index="${index}" placeholder="例如：米白背景，优雅衬线标题，居中窄列布局，拟物纸张质感，黑色圆角主按钮。">${frame.visual || ""}</textarea>
        </div>
        <div class="field">
          <label>排版公式 / 视觉骨架</label>
          <textarea data-field="formula" data-index="${index}" placeholder="例如：留白排版 + 中心排版 + 重叠排版；主视觉居中，四周留白 12%，卡片错位叠放形成焦点。">${frame.formula || ""}</textarea>
        </div>
        <div class="field">
          <label>组件清单 / 状态</label>
          <textarea data-field="components" data-index="${index}" placeholder="例如：顶部品牌字、To 输入框、From 输入框、邮票选择器、消息文本域、花朵选择器、预览卡、翻转提示、分享按钮。">${frame.components || ""}</textarea>
        </div>
        <div class="field">
          <label>素材 / 装饰 / 图形元素</label>
          <textarea data-field="assets" data-index="${index}" placeholder="例如：邮票图案、植物插画、星形吊坠、信封内衬照片、纸纹背景、手写标题贴纸、阴影叠层。">${frame.assets || ""}</textarea>
        </div>
        <div class="field">
          <label>布局 / 尺寸 / 空间关系</label>
          <textarea data-field="layout" data-index="${index}" placeholder="例如：左表单右预览双栏；预览卡约占右栏 70%；主视觉居中，卡片有 8-12deg 倾斜叠放；CTA 宽度接近主视觉。">${frame.layout || ""}</textarea>
        </div>
        <div class="field">
          <label>动效 / 转场 / 反馈</label>
          <textarea data-field="motion" data-index="${index}" placeholder="例如：点击后卡片翻转；选择素材后预览即时替换；分享按钮从禁用态变为可点击。">${frame.motion || ""}</textarea>
        </div>
        <div class="field">
          <label>页面区域 / 组件层级</label>
          <textarea data-field="regionStructure" data-index="${index}" placeholder="例如：顶部 HUD / 中央玩法区 / 底部操作区；或导航 / 主内容 / 弹窗；列出父子组件和覆盖层。">${frame.regionStructure || ""}</textarea>
        </div>
        <div class="field">
          <label>事件因果链</label>
          <textarea data-field="userAction" data-index="${index}" placeholder="用户或玩家做了什么；若无可见操作写“无明确操作”。">${frame.userAction || ""}</textarea>
          <textarea data-field="beforeState" data-index="${index}" placeholder="操作前状态">${frame.beforeState || ""}</textarea>
          <textarea data-field="systemResponse" data-index="${index}" placeholder="系统即时响应 / 反馈">${frame.systemResponse || ""}</textarea>
          <textarea data-field="afterState" data-index="${index}" placeholder="操作后状态">${frame.afterState || ""}</textarea>
        </div>
        <div class="field">
          <label>证据等级 / 置信度</label>
          <select data-field="evidenceLevel" data-index="${index}">
            ${["明确展示", "合理推断", "未知待确认"].map((v) => `<option ${frame.evidenceLevel === v ? "selected" : ""}>${v}</option>`).join("")}
          </select>
          <select data-field="confidence" data-index="${index}">
            ${["高", "中", "低"].map((v) => `<option ${frame.confidence === v ? "selected" : ""}>${v}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>游戏机制 / 核心玩法</label>
          <textarea data-field="gameMechanics" data-index="${index}" placeholder="例如：三消匹配、跑酷躲避、答题闯关、养成收集、放置挂机；核心循环是什么。">${frame.gameMechanics || ""}</textarea>
        </div>
        <div class="field">
          <label>游戏状态</label>
          <textarea data-field="gameState" data-index="${index}" placeholder="例如：主菜单、关卡选择、游戏中、暂停、胜利、失败、结算、排行榜。">${frame.gameState || ""}</textarea>
        </div>
        <div class="field">
          <label>游戏交互反馈</label>
          <textarea data-field="gameFeedback" data-index="${index}" placeholder="例如：消除粒子特效、得分飘字、连击特效、血条变化、屏幕震动、音效提示、倒计时动画。">${frame.gameFeedback || ""}</textarea>
        </div>
        <div class="confirm-row">
          <label><input type="checkbox" data-field="confirmed" data-index="${index}" ${frame.confirmed ? "checked" : ""}> 确认这帧解读无误，纳入 PRD</label>
          <span class="status">${frame.confirmed ? "已确认" : "待确认"}</span>
        </div>
      </details>
    </article>
  `;
  }).join("");
  frameList.innerHTML = html;
}

function frameText(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function frameLocator(frame) {
  return frame?.inputType === "image_sequence" ? `第 ${frame.sequenceIndex || 1} 张` : formatTime(frame?.timestamp || 0);
}

function reviewableFrames() {
  return FrameReviewer.filterFrames(state.frames, state.frameFilter, state.analysisMode);
}

function frameReviewToolbar(currentFrame = null) {
  const imageSequence = currentFrame?.inputType === "image_sequence";
  const sceneOptions = state.sceneGroups.map((scene) => {
    const start = imageSequence || scene.startTime == null ? "" : ` · ${formatTime(scene.startTime)}–${formatTime(scene.endTime || scene.startTime)}`;
    return `<option value="${scene.sceneId}" ${String(currentFrame?.sceneGroup) === String(scene.sceneId) ? "selected" : ""}>${frameText(scene.label || `场景 ${scene.sceneId + 1}`)}${start}</option>`;
  }).join("");
  const filterOptions = FrameReviewer.filterOptions().map((option) => `<option value="${option.value}" ${state.frameFilter === option.value ? "selected" : ""}>${option.label}</option>`).join("");
  const allFramesAction = state.frameFilter === "all"
    ? '<button class="btn frame-representatives-only" type="button">回到场景代表帧</button>'
    : '<button class="btn frame-show-all" type="button">查看所有帧信息</button>';
  return `<div class="frame-review-toolbar"><div class="field"><label for="frame-scene-select">快速跳到场景</label><select id="frame-scene-select"><option value="">选择场景</option>${sceneOptions}</select></div><div class="field"><label for="frame-filter-select">只看这些帧</label><select id="frame-filter-select">${filterOptions}</select></div>${allFramesAction}</div>`;
}

function frameSuggestion(frame, field) {
  if (!Object.prototype.hasOwnProperty.call(frame.analysisSuggestion || {}, field)) return "";
  const value = frame.analysisSuggestion[field];
  const display = typeof value === "string" ? value : stringifyFieldValue(value);
  return `<aside class="frame-field-suggestion"><strong>新分析建议</strong><p>${frameText(display)}</p><div><button class="btn frame-suggestion-accept" type="button" data-frame-id="${frameText(frame.id)}" data-suggestion-field="${field}">采用建议</button><button class="btn frame-suggestion-reject" type="button" data-frame-id="${frameText(frame.id)}" data-suggestion-field="${field}">保留当前内容</button></div></aside>`;
}

function frameSupplementalEvidence(frame) {
  const samples = (frame.supplementalEvidence?.samples || []).slice().sort((left, right) => left.timestamp - right.timestamp);
  if (!samples.length) return "";
  return `<section class="supplemental-evidence" aria-label="补取的前后画面"><h4>补取的前后画面</h4><div>${samples.map((sample) => `<button class="supplement-thumb" type="button" data-time="${sample.timestamp}" data-supplement-url="${frameText(`${BACKEND_BASE}${sample.imageUrl}`)}" aria-label="查看 ${formatTime(sample.timestamp)} 的补充画面"><img src="${frameText(`${BACKEND_BASE}${sample.imageUrl}`)}" alt="${formatTime(sample.timestamp)} 的补充画面"><span>${formatTime(sample.timestamp)}</span></button>`).join("")}</div></section>`;
}

function frameAttentionFeedback(frame, wasAttention = false) {
  const reasons = FrameReviewer.attentionReasons(frame, state.analysisMode);
  const status = frame.supplementalEvidence?.status;
  const processing = status === "extracting" || status === "analyzing";
  const action = frame.inputType !== "image_sequence" && reasons.length && typeof lastCompletedJobId !== "undefined" && lastCompletedJobId
    ? `<div class="frame-supplement-action"><button class="btn primary frame-supplement-action-button" type="button" data-frame-id="${frameText(frame.id)}" ${processing ? "disabled" : ""}>${status === "failed" ? "重新尝试" : status === "ready" ? "重新补取" : "补取前后画面"}</button>${processing ? `<span role="status">${status === "extracting" ? "正在补取画面" : "正在重新解读"}</span>` : status === "failed" ? `<span role="status">${frameText(frame.supplementalEvidence.message || "局部重新解读失败，可以重试。")}</span>` : ""}</div>`
    : "";
  if (reasons.length) {
    const items = reasons.map((reason) => `<li><strong>${frameText(reason.label)}</strong><span>${frameText(reason.suggestion)}</span></li>`).join("");
    return `<section class="frame-attention-reasons" aria-label="为什么需要重点检查"><h4>为什么需要重点检查</h4><ul>${items}</ul>${action}</section>`;
  }
  return wasAttention ? '<div class="frame-attention-resolved" role="status"><strong>这一帧已不再需要重点检查</strong><span>修改已保留，可以使用右箭头查看下一条。</span></div>' : "";
}

function refreshFrameAttentionFeedback(frame) {
  const container = document.querySelector(".frame-attention-feedback");
  if (!container) return;
  const wasAttention = container.dataset.wasAttention === "true";
  container.innerHTML = frameAttentionFeedback(frame, wasAttention);
  const resolved = wasAttention && !FrameReviewer.attentionReasons(frame, state.analysisMode).length;
  document.querySelector(".frame-reviewer")?.setAttribute("data-attention-resolved", String(resolved));
}

function markFrameHumanEdited(frame, field) {
  if (!field || field === "confirmed") return;
  frame.humanEditedFields = Array.from(new Set([...(frame.humanEditedFields || []), field]));
}

function showFrameAt(index, options = {}) {
  const ordered = reviewableFrames();
  state.currentFrameIndex = FrameReviewer.moveIndex(index, 0, ordered.length);
  renderSingleFrame();
  if (options.focus) document.querySelector(".frame-reviewer h3")?.focus();
}

function renderSingleFrame(frameOverride = null, wasAttentionOverride = false) {
  const frameList = $("frameList");
  if (!state.frames.length) {
    frameList.innerHTML = '<div class="notice">还没有关键画面。选择截图文件夹并开始分析后，这里会按确认顺序显示。</div>';
    return;
  }
  const ordered = reviewableFrames();
  if (!ordered.length && !frameOverride) {
    frameList.innerHTML = `${frameReviewToolbar()}<div class="notice frame-filter-empty">当前没有需要检查的关键帧。可以选择其他筛选条件。</div>`;
    return;
  }
  if (!frameOverride) state.currentFrameIndex = FrameReviewer.moveIndex(state.currentFrameIndex, 0, ordered.length);
  const frame = frameOverride || ordered[state.currentFrameIndex];
  const originalIndex = state.frames.indexOf(frame);
  const pendingPlaceholder = frame.inputType === "image_sequence" ? "截图没有明确展示时，请写‘待确认’" : "视频没有明确展示时，请写‘待确认’";
  const fields = FrameReviewer.fieldsForMode(state.analysisMode).map(({ field, label }) => {
    const controlId = `frame-${originalIndex}-${field}`;
    return `<div class="field"><label for="${controlId}">${label}</label><textarea id="${controlId}" data-field="${field}" data-index="${originalIndex}" placeholder="${pendingPlaceholder}">${frameText(frame[field])}</textarea>${frameSuggestion(frame, field)}</div>`;
  }).join("");
  const scene = frame.sceneGroup >= 0 ? `场景 ${frame.sceneGroup + 1}` : "未分场景";
  const countText = state.frameFilter === "all" ? `第 ${state.currentFrameIndex + 1} / ${ordered.length} 帧` : `筛选后第 ${state.currentFrameIndex + 1} / ${ordered.length} 帧 · 全部 ${state.frames.length} 帧`;
  const reasons = FrameReviewer.attentionReasons(frame, state.analysisMode);
  const wasAttention = wasAttentionOverride || reasons.length > 0;
  const previousDisabled = state.currentFrameIndex === 0;
  const nextDisabled = frameOverride ? !ordered.length || state.currentFrameIndex >= ordered.length : state.currentFrameIndex === ordered.length - 1;
  const seekAction = frame.inputType === "image_sequence" ? "" : `<button class="btn evidence-seek" type="button" data-time="${frame.timestamp || 0}" data-frame-id="${frameText(frame.id)}">在视频中定位</button>`;
  frameList.innerHTML = `${frameReviewToolbar(frame)}<article class="frame-reviewer" data-frame-id="${frameText(frame.id)}" data-attention-resolved="${wasAttention && !reasons.length}" aria-live="polite"><nav class="frame-reviewer-nav" aria-label="关键画面切换"><button class="frame-arrow frame-prev" type="button" aria-label="上一张" ${previousDisabled ? "disabled" : ""}>←</button><div><h3 tabindex="-1">${scene} · ${frameText(frame.id)}</h3><span>${frameLocator(frame)} · ${countText}</span></div><button class="frame-arrow frame-next" type="button" aria-label="下一张" ${nextDisabled ? "disabled" : ""}>→</button></nav><div class="frame-attention-feedback" data-was-attention="${wasAttention}" aria-live="polite">${frameAttentionFeedback(frame, wasAttention)}</div><div class="frame-reviewer-body"><div class="frame-visual"><img src="${frameText(frame.dataUrl)}" alt="${scene}的${frameLocator(frame)}画面">${seekAction}${frameSupplementalEvidence(frame)}</div><div class="frame-explanation">${fields}<div class="frame-assurance"><div class="field"><label>这条结论来自哪里</label><select data-field="evidenceLevel" data-index="${originalIndex}">${["明确展示", "合理推断", "未知待确认"].map((v) => `<option ${frame.evidenceLevel === v ? "selected" : ""}>${v}</option>`).join("")}</select>${frameSuggestion(frame, "evidenceLevel")}</div><div class="field"><label>判断把握</label><select data-field="confidence" data-index="${originalIndex}">${["高", "中", "低"].map((v) => `<option ${frame.confidence === v ? "selected" : ""}>${v}</option>`).join("")}</select>${frameSuggestion(frame, "confidence")}</div></div><div class="confirm-row"><label><input type="checkbox" data-field="confirmed" data-index="${originalIndex}" ${frame.confirmed ? "checked" : ""}> 确认这一帧可纳入策划案</label><span class="status">${frame.confirmed ? "已确认" : "待确认"}</span></div></div></div></article>`;
}

renderFrames = renderSingleFrame;

// 帧列表事件监听（输入和确认勾选）
(function bindFrameListEvents() {
  const frameList = $("frameList");
  frameList.addEventListener("input", (event) => {
    const target = event.target;
    const index = Number(target.dataset.index);
    if (!Number.isFinite(index)) return;
    state.frames[index][target.dataset.field] = target.value;
    markFrameHumanEdited(state.frames[index], target.dataset.field);
    refreshFrameAttentionFeedback(state.frames[index]);
    renderStats();
    if (typeof scheduleReviewSave === "function") scheduleReviewSave();
  });
  frameList.addEventListener("change", (event) => {
    const target = event.target;
    if (target.id === "frame-filter-select") {
      const currentId = frameList.querySelector(".frame-reviewer")?.dataset.frameId;
      state.frameFilter = target.value;
      const nextFrames = reviewableFrames();
      const preserved = nextFrames.findIndex((frame) => String(frame.id) === String(currentId));
      showFrameAt(preserved >= 0 ? preserved : 0, { focus: true });
      return;
    }
    if (target.id === "frame-scene-select" && target.value !== "") {
      let index = FrameReviewer.firstFrameIndexForScene(state.frames, target.value, state.frameFilter, state.analysisMode);
      if (index < 0) {
        state.frameFilter = "all";
        index = FrameReviewer.firstFrameIndexForScene(state.frames, target.value, "all", state.analysisMode);
      }
      if (index >= 0) showFrameAt(index, { focus: true });
      return;
    }
    const index = Number(target.dataset.index);
    if (!Number.isFinite(index)) return;
    if (target.dataset.field !== "confirmed") {
      if (target.dataset.field) {
        state.frames[index][target.dataset.field] = target.value;
        markFrameHumanEdited(state.frames[index], target.dataset.field);
        refreshFrameAttentionFeedback(state.frames[index]);
        renderStats();
        if (typeof scheduleReviewSave === "function") scheduleReviewSave();
      }
      return;
    }
    state.frames[index].confirmed = target.checked;
    renderStats();
    if (typeof scheduleReviewSave === "function") scheduleReviewSave();
    renderFrames();
  });
  frameList.addEventListener("click", (event) => {
    const previous = event.target.closest(".frame-prev");
    const next = event.target.closest(".frame-next");
    const button = event.target.closest(".scene-reanalyze");
    const seek = event.target.closest(".evidence-seek");
    const supplement = event.target.closest(".frame-supplement-action-button");
    const supplementThumb = event.target.closest(".supplement-thumb");
    const acceptSuggestion = event.target.closest(".frame-suggestion-accept");
    const rejectSuggestion = event.target.closest(".frame-suggestion-reject");
    const showAllFrames = event.target.closest(".frame-show-all");
    const representativesOnly = event.target.closest(".frame-representatives-only");
    if (showAllFrames || representativesOnly) {
      const currentId = frameList.querySelector(".frame-reviewer")?.dataset.frameId;
      state.frameFilter = showAllFrames ? "all" : "scene_representatives";
      const nextFrames = reviewableFrames();
      const preserved = nextFrames.findIndex((frame) => String(frame.id) === String(currentId));
      showFrameAt(preserved >= 0 ? preserved : 0, { focus: true });
      return;
    }
    if (previous || next) {
      const resolved = frameList.querySelector(".frame-reviewer")?.dataset.attentionResolved === "true";
      const delta = previous ? -1 : (resolved ? 0 : 1);
      showFrameAt(FrameReviewer.moveIndex(state.currentFrameIndex, delta, reviewableFrames().length), { focus: true });
      return;
    }
    if (seek) {
      jumpToEvidence(seek.dataset.time, seek.dataset.frameId);
      return;
    }
    if (supplement) {
      supplementAndReanalyzeFrame(supplement.dataset.frameId).catch((error) => setStatus(error.message));
      return;
    }
    if (supplementThumb) {
      jumpToEvidence(supplementThumb.dataset.time);
      const preview = frameList.querySelector(".frame-visual img");
      if (preview) preview.src = supplementThumb.dataset.supplementUrl;
      return;
    }
    if (acceptSuggestion || rejectSuggestion) {
      const action = acceptSuggestion || rejectSuggestion;
      resolveFrameSuggestion(action.dataset.frameId, action.dataset.suggestionField, Boolean(acceptSuggestion)).catch((error) => setStatus(error.message));
      return;
    }
    if (!button) return;
    const sceneId = Number(button.dataset.sceneId);
    reanalyzeBackendScene(sceneId).catch((error) => setStatus(error.message));
  });
})();
