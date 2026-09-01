// 截图为主素材，辅助视频保持独立；state.assets 仅供旧渲染链路兼容。

function syncLegacyAssets() {
  state.assets = [...state.screenshots, ...(state.auxiliaryVideo ? [state.auxiliaryVideo] : [])];
}

function invalidateScreenshotResult() {
  state.frames = [];
  state.sceneGroups = [];
  state.videoSummary = null;
  const output = $("output");
  if (output) output.value = "";
  syncLegacyAssets();
  if (typeof renderFrames === "function") renderFrames();
}

async function replaceScreenshotFolder(files) {
  const selection = selectTopLevelScreenshots(files);
  if (!selection.accepted.length) return;
  if (typeof detachJobForNewEvidence === "function") detachJobForNewEvidence();
  state.screenshots.forEach((asset) => asset.url && URL.revokeObjectURL(asset.url));
  state.screenshots = selection.accepted.map((file, index) => ({
    id: `IMG${String(index + 1).padStart(3, "0")}`,
    file,
    kind: "image",
    name: file.name,
    size: file.size,
    type: file.type,
    relativePath: file.webkitRelativePath || file.name,
    url: URL.createObjectURL(file),
    width: 0,
    height: 0,
    duration: 0,
  }));
  await Promise.all(state.screenshots.map(enrichAsset));
  invalidateScreenshotResult();
  renderScreenshotInputs(selection);
  renderStats();
  setProgress(0, "等待开始分析");
  const validation = validateScreenshotCount(state.screenshots.length);
  setStatus(validation.valid
    ? `已读取 <strong>${state.screenshots.length}</strong> 张截图，请确认顺序后开始分析。`
    : validation.message);
}

async function setAuxiliaryVideo(file) {
  if (state.auxiliaryVideo?.url) URL.revokeObjectURL(state.auxiliaryVideo.url);
  state.auxiliaryVideo = null;
  if (file) {
    if (!file.type.startsWith("video/")) throw new Error("辅助素材必须是视频文件。");
    state.auxiliaryVideo = {
      id: "V01",
      file,
      kind: "video",
      name: file.name,
      size: file.size,
      type: file.type,
      url: URL.createObjectURL(file),
      width: 0,
      height: 0,
      duration: 0,
    };
    await enrichAsset(state.auxiliaryVideo);
  }
  syncLegacyAssets();
  renderScreenshotInputs();
  renderStats();
}

function reorderScreenshot(fromIndex, toIndex) {
  state.screenshots = moveItem(state.screenshots, fromIndex, toIndex);
  invalidateScreenshotResult();
  renderScreenshotInputs();
  renderStats();
}

function removeScreenshot(index) {
  const [removed] = state.screenshots.splice(index, 1);
  if (removed?.url) URL.revokeObjectURL(removed.url);
  invalidateScreenshotResult();
  renderScreenshotInputs();
  renderStats();
}

function renderScreenshotInputs(selection = {}) {
  const list = $("screenshotPreviewList");
  const readOnly = state.screenshots.some((asset) => asset.readOnly);
  if (list) list.innerHTML = state.screenshots.map((asset, index) => `
    <article class="screenshot-preview-item" draggable="${readOnly ? "false" : "true"}" data-index="${index}">
      <span class="screenshot-sequence">${index + 1}</span>
      <img src="${frameText(asset.url)}" alt="第 ${index + 1} 张：${frameText(asset.name)}">
      <div class="screenshot-file"><strong>${frameText(asset.name)}</strong><span>${asset.width || "?"} × ${asset.height || "?"}</span></div>
      <div class="screenshot-order-actions">
        <button class="btn" type="button" data-action="up" data-index="${index}" ${readOnly || index === 0 ? "disabled" : ""} aria-label="上移 ${frameText(asset.name)}">上移</button>
        <button class="btn" type="button" data-action="down" data-index="${index}" ${readOnly || index === state.screenshots.length - 1 ? "disabled" : ""} aria-label="下移 ${frameText(asset.name)}">下移</button>
        <button class="btn warn" type="button" data-action="remove" data-index="${index}" ${readOnly ? "disabled" : ""} aria-label="删除 ${frameText(asset.name)}">删除</button>
      </div>
    </article>`).join("");
  const validation = validateScreenshotCount(state.screenshots.length);
  const broken = state.screenshots.filter((asset) => !asset.width || !asset.height);
  const notice = $("screenshotValidation");
  if (notice) {
    const ignored = Number(selection.ignoredCount || 0) + Number(selection.nestedCount || 0);
    notice.textContent = broken.length
      ? `无法读取：${broken.map((asset) => asset.name).join("、")}`
      : `${validation.message}${ignored ? ` 已忽略 ${ignored} 个非图片或子目录文件。` : ""}`;
  }
  const folder = $("screenshotFolderMeta");
  if (folder && selection.folderName) folder.textContent = `${selection.folderName} · ${state.screenshots.length} 张有效截图`;
  const auxiliary = $("auxVideoMeta");
  if (auxiliary) auxiliary.textContent = state.auxiliaryVideo
    ? `${state.auxiliaryVideo.name} · 仅补充动效与过渡`
    : "未添加；不影响截图分析。";
}

// 兼容旧拖放入口；拖入的一组图片仍按截图组处理。
async function addFiles(files) {
  return replaceScreenshotFolder(files);
}

function enrichAsset(asset) {
  return new Promise((resolve) => {
    if (asset.kind === "image") {
      const img = new Image();
      img.onload = () => { asset.width = img.naturalWidth; asset.height = img.naturalHeight; resolve(); };
      img.onerror = resolve;
      img.src = asset.url;
      return;
    }
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      asset.duration = video.duration || 0;
      asset.width = video.videoWidth || 0;
      asset.height = video.videoHeight || 0;
      resolve();
    };
    video.onerror = resolve;
    video.src = asset.url;
  });
}

function renderStats() {
  syncLegacyAssets();
  $("fileCount").textContent = state.screenshots.length;
  $("frameCount").textContent = state.frames.length;
  $("confirmedCount").textContent = state.frames.filter((frame) => frame.confirmed).length;
  const hasWorkspaceData = state.assets.length > 0 || state.frames.length > 0 || Boolean($("output").value.trim());
  const count = validateScreenshotCount(state.screenshots.length);
  $("extractBtn").disabled = !count.valid || state.screenshots.some((asset) => !asset.file || !asset.width || !asset.height);
  $("copyBtn").disabled = !$("output").value.trim();
  $("downloadBtn").disabled = !$("output").value.trim();
  $("clearBtn").disabled = !hasWorkspaceData;
}
