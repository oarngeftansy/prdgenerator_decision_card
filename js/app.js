// ai策划案工具 - 主入口：DOM 引用、事件绑定、输出操作、初始化

// ---- 输出操作 ----

function copyOutput() {
  const output = $("output");
  if (!output.value.trim()) return;
  navigator.clipboard.writeText(output.value);
  setStatus("PRD 已复制。");
}

function downloadOutput() {
  const output = $("output");
  let text = output.value.trim();
  if (!text) return;
  if (typeof currentReviewReady !== "undefined" && !currentReviewReady) text = `> **草稿：人工审核尚未完成，仍包含未知或未确认结论。**\n\n${text}`;
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const name = ($("projectName").value.trim() || "reconstruction-prd").replace(/[\\/:*?"<>|]+/g, "-");
  a.href = url;
  a.download = `${name}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function clearAll() {
  if (state.reviewOperationQueue?.hasPending()) {
    state.reviewOperationQueue.flush(state.reviewWorkspace?.model.revision).then(() => clearAll()).catch(() => setStatus("审核修改未保存，已取消清空操作。"));
    return;
  }
  for (const asset of state.assets) URL.revokeObjectURL(asset.url);
  state.screenshots = [];
  state.auxiliaryVideo = null;
  state.assets = [];
  state.frames = [];
  state.sceneGroups = [];
  state.videoSummary = null;
  state.reviewWorkspace = null;
  state.reviewClient = null;
  state.reviewOperationQueue?.clear();
  state.reviewOperationQueue = null;
  $("screenshotFolderInput").value = "";
  $("auxVideoInput").value = "";
  $("output").value = "";
  $("timelineWorkbench").hidden = true;
  $("sourceVideo").pause();
  $("sourceVideo").removeAttribute("src");
  $("sourceVideo").load();
  $("sceneTimeline").innerHTML = "";
  $("evidenceTimeline").innerHTML = "";
  $("sceneSummaryList").innerHTML = "";
  $("reviewQueue").innerHTML = "";
  activeJobId = "";
  lastCompletedJobId = "";
  localStorage.removeItem("vpr_active_job");
  localStorage.removeItem("vpr_last_job");
  document.querySelector(".workspace")?.classList.remove("has-job");
  document.querySelector(".workspace")?.classList.remove("has-review");
  document.body?.classList.remove("has-review");
  $("reviewWorkspace").hidden = true;
  $("reviewProjectDrawer").classList.remove("is-open");
  $("reviewProjectDrawerToggle").setAttribute("aria-expanded", "false");
  ["flowReviewView", "stageReviewView", "exportPreviewView", "analysisFailedView"].forEach((id) => { $(id).hidden = true; });
  if (new URLSearchParams(location.search).has("job")) history.replaceState(null, document.title, location.pathname);
  renderFrames();
  renderScreenshotInputs();
  renderStats();
  setProgress(0, "未开始");
  setStatus("等待上传素材。");
}

// ---- 事件绑定 ----

function bindEvents() {
  const screenshotFolderInput = $("screenshotFolderInput");
  const auxVideoInput = $("auxVideoInput");
  const dropzone = $("dropzone");

  $("selectScreenshotFolderBtn").addEventListener("click", () => screenshotFolderInput.click());
  screenshotFolderInput.addEventListener("change", (event) => {
    if (event.target.files.length) replaceScreenshotFolder(event.target.files).catch((error) => setStatus(error.message));
  });
  $("selectAuxVideoBtn").addEventListener("click", () => auxVideoInput.click());
  auxVideoInput.addEventListener("change", (event) => {
    if (event.target.files[0]) setAuxiliaryVideo(event.target.files[0]).catch((error) => setStatus(error.message));
  });
  $("removeAuxVideoBtn").addEventListener("click", () => setAuxiliaryVideo(null));
  $("screenshotPreviewList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const index = Number(button.dataset.index);
    if (button.dataset.action === "up") reorderScreenshot(index, index - 1);
    if (button.dataset.action === "down") reorderScreenshot(index, index + 1);
    if (button.dataset.action === "remove") removeScreenshot(index);
  });
  let draggedScreenshotIndex = -1;
  $("screenshotPreviewList").addEventListener("dragstart", (event) => {
    draggedScreenshotIndex = Number(event.target.closest("[data-index]")?.dataset.index ?? -1);
  });
  $("screenshotPreviewList").addEventListener("dragover", (event) => event.preventDefault());
  $("screenshotPreviewList").addEventListener("drop", (event) => {
    event.preventDefault();
    const targetIndex = Number(event.target.closest("[data-index]")?.dataset.index ?? -1);
    if (draggedScreenshotIndex >= 0 && targetIndex >= 0) reorderScreenshot(draggedScreenshotIndex, targetIndex);
    draggedScreenshotIndex = -1;
  });
  $("extractBtn").addEventListener("click", async () => {
    try {
      const handled = await extractWithIntegratedBackend();
      if (!handled) {
        throw new Error("无法连接统一分析服务，请确认局域网服务正在运行后重试。");
      }
    } catch (error) {
      setStatus(`截图分析任务启动失败：${error.message}`);
      setProgress(0, "启动失败");
    }
  });
  $("aiBtn").addEventListener("click", aiInterpretFrames);
  $("reanalyzeAllBtn").addEventListener("click", () => reanalyzeWholeJob().catch((error) => setStatus(error.message)));
  $("confirmAllBtn").addEventListener("click", () => {
    state.frames.forEach((frame) => { frame.confirmed = true; });
    renderFrames();
    renderStats();
    setStatus("已勾选全部关键画面，请仍然人工检查说明是否准确。");
    scheduleReviewSave();
  });
  $("prdBtn").addEventListener("click", generatePrd);
  $("enterWorkbenchBtn").addEventListener("click", enterReviewWorkbench);
  $("copyBtn").addEventListener("click", copyOutput);
  $("downloadBtn").addEventListener("click", downloadOutput);
  $("feishuPublication").addEventListener("click", (event) => {
    const action = event.target.closest("[data-feishu-action]");
    if (!action) return;
    publishToFeishuWithAuthorization(action.dataset.feishuAction).catch((error) => {
      setStatus(error.message);
      renderFeishuPublicationState({ status: "failed", message: error.message }, Boolean($("output").value.trim()));
    });
  });
  $("clearBtn").addEventListener("click", clearAll);
  $("cancelJobBtn").addEventListener("click", cancelBackendJob);
  $("retryJobBtn").addEventListener("click", () => retryBackendJob().catch((error) => setStatus(error.message)));
  $("projectType").addEventListener("change", updateAnalysisMode);
  $("apiKey").addEventListener("input", rememberApiConfig);
  $("rememberKey").addEventListener("change", rememberApiConfig);
  $("returnToLastJobBtn").addEventListener("click", () => {
    rememberApiConfig();
    const jobId = localStorage.getItem("vpr_last_job");
    if (!jobId) return setStatus("目前没有可返回的工作台任务。");
    location.href = `/?job=${encodeURIComponent(jobId)}`;
  });
  $("timelineWorkbench").addEventListener("click", (event) => {
    const target = event.target.closest("[data-time]");
    if (!target) return;
    jumpToEvidence(target.dataset.time, target.dataset.frameId || "");
  });
  document.addEventListener("keydown", (event) => {
    if (!state.frames.length || FrameReviewer.isTextEditingTarget(event.target)) return;
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    showFrameAt(FrameReviewer.moveIndex(state.currentFrameIndex, event.key === "ArrowLeft" ? -1 : 1, reviewableFrames().length), { focus: true });
  });
  $("refreshHistoryBtn").addEventListener("click", loadJobHistory);
  $("saveStandardBtn").addEventListener("click", () => saveStandard().catch((error) => setStatus(error.message)));
  $("historyList").addEventListener("click", (event) => {
    const open = event.target.closest(".history-open");
    const archive = event.target.closest(".history-archive");
    if (archive) archiveHistoryJob(archive.dataset.jobId).catch((error) => setStatus(error.message));
    if (open) location.href = `/?job=${open.dataset.jobId}`;
  });

  dropzone.addEventListener("dragover", (event) => { event.preventDefault(); dropzone.classList.add("drag"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("drag");
    addFiles(event.dataTransfer.files);
  });
}

function updateAnalysisMode() {
  $("projectType").value = "interaction";
  $("platform").value = "Mobile Web";
  state.analysisMode = "interaction";
  $("modeHelp").textContent = "统一生成交互与玩法策划案：先确认玩家操作顺序和页面反馈，再按章节审核玩法规则、数值及必要图示，最终导出一份完整飞书文档。";
  $("outputTitle").textContent = "完整交互与玩法策划案";
  $("prdBtn").textContent = "生成完整策划案";
  if (state.frames.length) renderFrames();
}

// ---- 初始化 ----

function init() {
  if (typeof ClientCache !== "undefined") ClientCache.cleanup(localStorage);
  document.body.classList.toggle("setup-mode", new URLSearchParams(location.search).get("setup") === "1");
  loadApiConfig();
  renderFrames();
  renderStats();
  renderFeishuPublicationState();
  bindEvents();
  updateAnalysisMode();
  loadPublicApiDefaults().catch(() => renderApiConfigGate()).finally(checkLocalProxy);
  loadStandards();
  initializeJobHistory();
  resumeBackendJob();
}

document.addEventListener("DOMContentLoaded", init);
