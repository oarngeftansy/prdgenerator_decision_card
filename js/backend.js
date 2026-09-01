// 统一分析任务：上传、轮询、交互审核与玩法审核结果同步。

const BACKEND_BASE = location.protocol === "http:" || location.protocol === "https:"
  ? location.origin
  : "http://127.0.0.1:8000";
let activeJobId = "";
let lastCompletedJobId = localStorage.getItem("vpr_last_job") || "";
let lastFailedJobId = "";
let pollTimer = null;
let currentReviewReady = false;
let reviewSaveTimer = null;
let reviewUiSaveTimer = null;
let reviewUiSaveInFlight = null;
let reviewUiSaveQueued = null;
let reviewSyncVersion = 0;
let reviewPreviewVersion = 0;
let reviewUiInteractionVersion = 0;
let reviewPagehideHandler = null;
let reviewPopstateHandler = null;
let currentFeishuPublication = {};
let gameplaySyncVersion = 0;
let jobContextVersion = 0;

function isCurrentJobContext(version) {
  return version === jobContextVersion;
}

function detachJobForNewEvidence() {
  jobContextVersion += 1;
  reviewSyncVersion += 1;
  gameplaySyncVersion += 1;
  reviewPreviewVersion += 1;
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = null;
  activeJobId = "";
  lastCompletedJobId = "";
  lastFailedJobId = "";
  localStorage.removeItem("vpr_active_job");
  state.reviewOperationQueue?.clear?.();
  state.gameplayOperationQueue?.clear?.();
  state.reviewOperationQueue = null;
  state.gameplayOperationQueue = null;
  state.reviewClient = null;
  state.gameplayReviewClient = null;
  state.reviewWorkspace = null;
  state.gameplayReviewWorkspace = null;
  document.querySelector(".workspace")?.classList.remove?.("has-job", "has-review");
  document.body?.classList.remove("has-review");
  const reviewRoot = $("reviewWorkspace");
  if (reviewRoot) reviewRoot.hidden = true;
  if (typeof history !== "undefined" && typeof history.replaceState === "function" && new URLSearchParams(location.search).has("job")) {
    history.replaceState(null, document.title, location.pathname);
  }
}

async function backendAvailable() {
  try {
    const response = await fetch(`${BACKEND_BASE}/api/health`, { cache: "no-store" });
    return response.ok;
  } catch (_) {
    return false;
  }
}

function buildJobFormData() {
  const data = backendConfigForm();
  state.screenshots.forEach((asset) => data.append("images", asset.file, asset.name));
  data.append("image_manifest", JSON.stringify(buildImageManifest(state.screenshots)));
  if (state.auxiliaryVideo) data.append("video", state.auxiliaryVideo.file, state.auxiliaryVideo.name);
  data.append("mode", "interaction");
  data.append("project_name", $("projectName").value.trim() || "未命名项目");
  data.append("scope", $("scope").value.trim());
  data.append("transcription_api_base", $("transcriptionApiUrl").value.trim() || $("apiUrl").value.trim());
  data.append("transcription_model", $("transcriptionModel").value.trim() || "whisper-1");
  data.append("transcription_api_key", $("transcriptionApiKey").value.trim() || $("apiKey").value.trim());
  data.append("standard_id", $("standardSelect").value);
  return data;
}

async function extractWithIntegratedBackend() {
  if (!canStartNewJob(activeJobId)) {
    setStatus("当前分析任务仍在运行，请等待完成或先取消任务。");
    return true;
  }
  const validation = validateScreenshotCount(state.screenshots.length);
  if (!validation.valid) throw new Error(validation.message);
  if (state.screenshots.some((asset) => !asset.file)) throw new Error("历史截图不能直接重新提交，请重新选择本地截图文件夹。");
  if (!hasVisionModelConfig()) {
    setStatus("请先配置视觉模型，再开始分析。素材不会被上传或丢失。");
    ensureVisionModelConfig();
    return true;
  }
  if (!(await backendAvailable())) return false;

  rememberApiConfig();
  const data = buildJobFormData();

  setProgress(1, "上传有序截图到本地分析服务");
  setStatus(`正在上传 <strong>${state.screenshots.length}</strong> 张截图，上传完成后会在后台持续处理。`);
  const response = await fetch(`${BACKEND_BASE}/api/jobs`, { method: "POST", body: data });
  if (!response.ok) throw new Error(`创建分析任务失败：${response.status} ${await response.text()}`);
  const job = await response.json();
  activeJobId = job.id;
  $("cancelJobBtn").disabled = false;
  $("retryJobBtn").disabled = true;
  localStorage.setItem("vpr_active_job", activeJobId);
  await pollBackendJob(activeJobId);
  return true;
}

async function pollBackendJob(jobId) {
  if (pollTimer) clearTimeout(pollTimer);
  try {
    const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`读取任务失败：${response.status}`);
    const job = await response.json();
    if (jobId !== activeJobId) return;
    setProgress(job.progress || 0, job.stage || "处理中");
    setStatus(`分析任务 <strong>${job.id.slice(0, 8)}</strong>：${job.stage || job.status}`);
    if (job.status === "processing" || job.status === "queued") renderBackendProcessing(job);
    if (job.status === "completed") {
      await syncBackendResult(job);
      lastCompletedJobId = job.id;
      localStorage.setItem("vpr_last_job", job.id);
      $("cancelJobBtn").disabled = true;
      $("retryJobBtn").disabled = false;
      localStorage.removeItem("vpr_active_job");
      $("cancelJobBtn").disabled = true;
      $("retryJobBtn").disabled = false;
      activeJobId = "";
      return;
    }
    if (job.status === "failed") {
      localStorage.removeItem("vpr_active_job");
      renderBackendFailure(job);
      activeJobId = "";
      return;
    }
    pollTimer = setTimeout(() => pollBackendJob(jobId), 1800);
  } catch (error) {
    setStatus(`后端任务异常：${error.message}`);
    setProgress(0, "任务异常");
  }
}

function renderBackendProcessing(job) {
  const total = job.frames?.length || job.scenes?.length || state.screenshots.length;
  const stage = job.stage || "等待视觉模型分析";
  $("reviewProgress").textContent = total
    ? `素材已接收：${total}/${total} · ${stage}`
    : `素材上传中 · ${stage}`;
  $("frameList").innerHTML = `<div class="notice">正在生成交互流程与玩法线索；分析完成后自动进入交互审核，无需逐帧确认。</div>`;
}

function renderBackendFailure(job) {
  lastFailedJobId = job.id || activeJobId || lastFailedJobId;
  document.querySelector(".workspace")?.classList.add("has-job");
  if (job.metadata?.projectName) $("projectName").value = job.metadata.projectName;
  if (job.metadata?.scope) $("scope").value = job.metadata.scope;
  if (job.metadata?.inputType === "image_sequence" && !state.screenshots.length) {
    state.screenshots = restoreScreenshotAssets(job);
    syncLegacyAssets();
    renderScreenshotInputs();
    renderStats();
  }
  const total = job.frames?.length || job.scenes?.length || state.screenshots.length;
  const legacyQuality = String(job.error || "").match(/(\d+)\s*\/\s*(\d+)\s*个代表帧达标/);
  const qualified = job.analysisSummary?.qualifiedDetailFrameCount != null
    ? Number(job.analysisSummary.qualifiedDetailFrameCount)
    : legacyQuality ? Number(legacyQuality[1]) : NaN;
  const detailTotal = job.analysisSummary?.detailFrameCount != null
    ? Number(job.analysisSummary.detailFrameCount)
    : legacyQuality ? Number(legacyQuality[2]) : NaN;
  $("reviewProgress").textContent = total ? `分析未通过 · 已保留 ${total} 张素材` : "分析未通过";
  $("frameList").innerHTML = `<div class="notice">视觉分析未达到交付标准。素材和结构识别结果已保留，点击“重试任务”即可继续，无需重新上传。</div>`;
  $("cancelJobBtn").disabled = true;
  $("retryJobBtn").disabled = false;
  if (Number.isFinite(qualified) && Number.isFinite(detailTotal) && detailTotal > 0) {
    setProgress(Math.round(qualified * 100 / detailTotal), `视觉分析 ${qualified}/${detailTotal}`);
  } else {
    setProgress(job.progress || 0, "分析未通过");
  }
  setStatus(`后端任务异常：${job.error || "视觉分析未达到交付标准"}`);
}

function backendConfigForm() {
  const data = new FormData();
  data.append("api_base", $("apiUrl").value.trim());
  data.append("model", $("model").value.trim());
  data.append("api_key", $("apiKey").value.trim());
  return data;
}

async function reanalyzeWholeJob() {
  if (!lastCompletedJobId) return;
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${lastCompletedJobId}/reanalyze`, { method: "POST", body: backendConfigForm() });
  if (!response.ok) throw new Error(`整片重解读失败：${response.status}`);
  activeJobId = lastCompletedJobId;
  $("cancelJobBtn").disabled = false;
  setStatus("正在复用既有关键帧和结构证据进行整片重新解读，不会重新扫描视频。");
  pollBackendJob(activeJobId);
}

function isLocalHistoryHost(hostname = location.hostname) {
  if (hostname === "localhost" || hostname === "::1" || /^127(?:\.|$)/.test(hostname)) return true;
  if (/^10\./.test(hostname) || /^192\.168\./.test(hostname)) return true;
  const match = hostname.match(/^172\.(\d+)\./);
  return Boolean(match && Number(match[1]) >= 16 && Number(match[1]) <= 31);
}

async function initializeJobHistory() {
  const panel = $("historyPanel");
  const local = isLocalHistoryHost();
  panel.hidden = !local;
  if (!local) return;
  try {
    await loadJobHistory();
  } catch (error) {
    $("historyList").innerHTML = `<div class="notice">任务历史读取失败：${escapeHtml(error.message)}</div>`;
  }
}

async function loadJobHistory() {
  if (!(await backendAvailable())) return;
  const response = await fetch(`${BACKEND_BASE}/api/jobs`, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const jobs = await response.json();
  $("historyList").innerHTML = jobs.length ? jobs.slice(0, 20).map((job) => `<div class="history-item"><button class="history-open" data-job-id="${job.id}"><b>${job.metadata?.projectName || job.metadata?.sourceName || job.id.slice(0, 8)}</b><span>${job.metadata?.mode === "interaction" ? "交互" : "玩法"} · ${job.status} · 质量 ${job.qualityReport?.score ?? "-"}</span></button><button class="btn history-archive" data-job-id="${job.id}">归档</button></div>`).join("") : '<div class="notice">暂无任务。</div>';
  const visibleIds = new Set(jobs.map((job) => job.id));
  const queryJob = new URLSearchParams(location.search).get("job");
  const shownJob = queryJob || activeJobId || lastCompletedJobId;
  if (shownJob && !visibleIds.has(shownJob)) clearAll();
}

async function archiveHistoryJob(jobId) {
  const data = new FormData(); data.append("archived", "true");
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}/archive`, { method: "POST", body: data });
  if (!response.ok) throw new Error(`归档失败：${response.status} ${await response.text()}`);
  const queryJob = new URLSearchParams(location.search).get("job");
  if (jobId === activeJobId || jobId === lastCompletedJobId || jobId === queryJob) clearAll();
  await loadJobHistory();
  setStatus("已归档该历史任务。");
}

async function loadStandards() {
  if (!(await backendAvailable())) return;
  const records = await fetch(`${BACKEND_BASE}/api/standards`).then((r) => r.json());
  $("standardSelect").innerHTML = '<option value="">GVE16 默认规范（不附加样例）</option>' + records.map((item) => `<option value="${item.id}">${item.name} · v${item.version} · ${item.mode === "interaction" ? "交互" : "玩法"}</option>`).join("");
}

async function saveStandard() {
  const name = $("standardName").value.trim();
  if (!name) throw new Error("请填写规范名称。");
  const data = new FormData();
  data.append("name", name); data.append("mode", $("projectType").value); data.append("version", $("standardVersion").value.trim() || "1.0");
  data.append("description", $("standardDescription").value.trim()); data.append("plan_example", $("standardPlanExample").value.trim()); data.append("source_job_id", lastCompletedJobId);
  const response = await fetch(`${BACKEND_BASE}/api/standards`, { method: "POST", body: data });
  if (!response.ok) throw new Error(`保存规范失败：${response.status}`);
  await loadStandards(); setStatus("规范样例已保存并可用于后续任务。");
}

async function persistReview() {
  if (!lastCompletedJobId) return;
  const editableFields = [...new Set(["evidenceLevel", "confidence", ...FrameReviewer.fieldsForMode("gameplay").map((item) => item.field), ...FrameReviewer.fieldsForMode("interaction").map((item) => item.field)])];
  const frames = Object.fromEntries(state.frames.map((frame) => [frame.id, { confirmed: frame.confirmed, humanEditedFields: frame.humanEditedFields || [], analysis: Object.fromEntries(editableFields.map((field) => [field, frame[field] ?? ""])) }]));
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${lastCompletedJobId}/review`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ frames }) });
  if (!response.ok) throw new Error(`保存审核修改失败：${response.status}`);
  const progress = await response.json();
  state.reviewUnsaved = false;
  renderReviewProgress(progress);
}

function renderReviewProgress(progress) {
  const value = progress || { confirmed: state.frames.filter((f) => f.confirmed).length, total: state.frames.length, unresolved: state.frames.filter((f) => f.evidenceLevel === "未知待确认").length };
  $("reviewProgress").textContent = `审核进度：${value.confirmed}/${value.total} · 未知项 ${value.unresolved} · ${value.readyForFinal ? "可导出正式版" : "当前导出为草稿"}`;
  currentReviewReady = Boolean(value.readyForFinal) && !state.reviewUnsaved;
  if (state.reviewUnsaved) $("reviewProgress").textContent += " · 尚未保存到任务";
}

function scheduleReviewSave() {
  if (!lastCompletedJobId) return;
  clearTimeout(reviewSaveTimer);
  reviewSaveTimer = setTimeout(() => persistReview().catch((error) => {
    state.reviewUnsaved = true;
    currentReviewReady = false;
    renderReviewProgress();
    setStatus(`修改保留在当前页面，但尚未保存到任务：${error.message}`);
  }), 500);
}

async function cancelBackendJob() {
  if (!activeJobId) return;
  await fetch(`${BACKEND_BASE}/api/jobs/${activeJobId}/cancel`, { method: "POST" });
  setStatus("已请求取消，当前处理步骤结束后任务会停止。");
}

async function retryBackendJob() {
  const jobId = retryTargetJobId(activeJobId, lastFailedJobId, lastCompletedJobId);
  if (!jobId) return;
  if (!hasVisionModelConfig()) {
    ensureVisionModelConfig();
    return;
  }
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}/retry`, { method: "POST", body: backendConfigForm() });
  if (!response.ok) throw new Error(`重试失败：${response.status}`);
  activeJobId = jobId;
  localStorage.setItem("vpr_active_job", jobId);
  $("cancelJobBtn").disabled = false;
  $("retryJobBtn").disabled = true;
  pollBackendJob(jobId);
}

function canStartNewJob(activeId) {
  return !activeId;
}

function retryTargetJobId(activeId, failedId, completedId) {
  return activeId || failedId || completedId || "";
}

function workbenchTargetJobId(search, failedId, completedId) {
  const linkedId = new URLSearchParams(search || "").get("job") || "";
  return linkedId || failedId || completedId || "";
}

function openFailedJobWorkbench(job) {
  const model = ReviewWorkspace.failedModelForJob(job);
  state.reviewWorkspace = { ...ReviewWorkspace.rebuild(model, "saved"), view: "analysis_failed" };
  document.querySelector(".workspace")?.classList.add("has-job", "has-review");
  document.body?.classList.add("has-review");
  $("analysisFailedEvidence").textContent = `已保留 ${job.frames?.length || state.screenshots.length || 0} 张素材${job.analysisSummary?.qualifiedDetailFrameCount ? `，其中 ${job.analysisSummary.qualifiedDetailFrameCount} 张已有可用分析` : ""}。`;
  renderReviewWorkspace(model);
  bindReviewWorkspace();
  if (typeof location !== "undefined" && typeof history !== "undefined" && typeof history.replaceState === "function") {
    const url = new URL(location.href);
    url.searchParams.set("job", job.id);
    url.searchParams.set("ui", "analysis_failed");
    history.replaceState({ ...(history.state || {}), reviewView: "analysis_failed", jobId: job.id }, "", url);
  } else syncReviewViewUrl("analysis_failed", { replace: true });
  $("reviewWorkspace").scrollIntoView?.({ block: "start", behavior: "smooth" });
}

async function enterReviewWorkbench() {
  if (state.reviewWorkspace?.model) {
    const view = state.reviewWorkspace.view || ReviewWorkspace.routeForModel(state.reviewWorkspace.model);
    document.querySelector(".workspace")?.classList.add("has-job", "has-review");
    document.body?.classList.add("has-review");
    $("reviewWorkspace").hidden = false;
    setReviewWorkspaceView(view);
    renderReviewWorkspace(state.reviewWorkspace.model);
    $("reviewWorkspace").scrollIntoView?.({ block: "start", behavior: "smooth" });
    return;
  }
  const jobId = workbenchTargetJobId(location.search, lastFailedJobId, lastCompletedJobId);
  if (!jobId) {
    setStatus("当前还没有可进入的审核任务，请先完成截图分析。");
    return;
  }
  const linkedId = new URLSearchParams(location.search || "").get("job") || "";
  if (linkedId === jobId) {
    const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
    if (!response.ok) return setStatus(`读取失败任务工作台失败：${response.status}`);
    const job = await response.json();
    if (job.status === "failed") {
      openFailedJobWorkbench(job);
      return;
    }
    setStatus("当前任务仍在处理中，完成后即可进入审核工作台。");
    return;
  }
  location.href = `/?job=${encodeURIComponent(jobId)}&ui=gameplay_directory`;
}

async function reanalyzeBackendScene(sceneId) {
  const jobId = lastCompletedJobId;
  if (!jobId) return;
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}/scenes/${sceneId}/reanalyze`, { method: "POST", body: backendConfigForm() });
  if (!response.ok) throw new Error(`场景重分析失败：${response.status}`);
  activeJobId = jobId;
  setStatus(`正在重新分析场景 ${sceneId + 1}。`);
  pollBackendJob(jobId);
}

function backendFrameToState(source, job) {
  const analysis = source.analysis || {};
  const imageSequence = job.metadata?.inputType === "image_sequence";
  return {
    id: source.id,
    sourceName: source.sourceName || job.video?.filename || job.metadata?.sourceName || "video",
    label: imageSequence ? `第 ${source.sequenceIndex} 张 · 场景 ${source.sceneId + 1}` : `${formatTime(source.timestamp)} · 场景 ${source.sceneId + 1}`,
    dataUrl: `${BACKEND_BASE}${source.imageUrl}`,
    width: source.structure?.width || job.video?.width || 0,
    height: source.structure?.height || job.video?.height || 0,
    timestamp: source.timestamp,
    sequenceIndex: source.sequenceIndex,
    inputType: job.metadata?.inputType || "video",
    sceneGroup: source.sceneId,
    what: analysis.what || analysis.summary || "",
    requirement: analysis.rules ? stringifyFieldValue(analysis.rules) : "",
    formula: "", visual: "",
    components: stringifyFieldValue(analysis.components || source.structure?.regionCounts || ""),
    assets: "", layout: "", motion: analysis.motion || "",
    gameMechanics: analysis.gameMechanics || "", gameState: analysis.gameState || "", gameFeedback: analysis.gameFeedback || "",
    regionStructure: stringifyFieldValue(analysis.regionStructure || source.structure?.regionCounts || ""),
    eventType: analysis.eventType || "unknown", userAction: analysis.userAction || "未知待确认",
    beforeState: analysis.beforeState || "未知待确认", systemResponse: analysis.systemResponse || "未知待确认",
    afterState: analysis.afterState || "未知待确认", valueChanges: analysis.valueChanges || "",
    stateVariations: analysis.stateVariations || "", promptText: analysis.promptText || "", unknowns: analysis.unknowns || "",
    evidenceLevel: analysis.evidenceLevel || "未知待确认", confidence: analysis.confidence || "低",
    isDetailFrame: Boolean(analysis.isDetailFrame),
    confirmed: Boolean(source.confirmed), backendStructure: source.structure,
    supplementalEvidence: source.supplementalEvidence || null,
    analysisSuggestion: source.analysisSuggestion || {},
    humanEditedFields: source.humanEditedFields || [],
    attentionSignals: source.attentionSignals || [],
  };
}

function restoreScreenshotAssets(job) {
  if (job.metadata?.inputType !== "image_sequence") return [];
  return [...(job.frames || [])]
    .sort((left, right) => Number(left.sequenceIndex || 0) - Number(right.sequenceIndex || 0))
    .map((frame) => ({
      id: frame.id,
      file: null,
      kind: "image",
      name: frame.sourceName || `${frame.id}.jpg`,
      size: 0,
      type: "image/jpeg",
      relativePath: frame.sourceName || `${frame.id}.jpg`,
      url: `${BACKEND_BASE}${frame.imageUrl}`,
      width: frame.structure?.width || 0,
      height: frame.structure?.height || 0,
      duration: 0,
      sequenceIndex: frame.sequenceIndex,
      readOnly: true,
    }));
}

async function supplementAndReanalyzeFrame(frameId) {
  if (!lastCompletedJobId) throw new Error("请先打开一个已完成的长视频任务。");
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${lastCompletedJobId}/frames/${encodeURIComponent(frameId)}/supplement-and-reanalyze`, { method: "POST", body: backendConfigForm() });
  if (!response.ok) throw new Error(`补取前后画面失败：${await response.text()}`);
  const frame = state.frames.find((item) => String(item.id) === String(frameId));
  if (frame) {
    frame.supplementalEvidence = { ...(frame.supplementalEvidence || {}), status: "extracting" };
    renderSingleFrame(frame, true);
  }
  setStatus("正在补取当前帧前后的画面。");
  pollFrameRepair(lastCompletedJobId, frameId);
}

async function pollFrameRepair(jobId, frameId) {
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`读取局部分析进度失败：${response.status}`);
  const job = await response.json();
  const source = (job.frames || []).find((item) => String(item.id) === String(frameId));
  if (!source) throw new Error("当前关键帧不存在。");
  const index = state.frames.findIndex((item) => String(item.id) === String(frameId));
  const wasAttention = index >= 0 && FrameReviewer.attentionReasons(state.frames[index], state.analysisMode).length > 0;
  const mapped = backendFrameToState(source, job);
  if (index >= 0) state.frames[index] = mapped;
  const status = mapped.supplementalEvidence?.status;
  if (status === "extracting" || status === "analyzing") {
    renderSingleFrame(mapped, wasAttention);
    setStatus(status === "extracting" ? "正在补取画面。" : "正在重新解读这组画面。");
    setTimeout(() => pollFrameRepair(jobId, frameId).catch((error) => setStatus(error.message)), 1200);
    return;
  }
  renderSingleFrame(mapped, wasAttention);
  renderStats();
  $("output").value = job.plan || $("output").value;
  setStatus(status === "ready" ? "局部重新解读完成，请核对更新内容和新分析建议。" : (mapped.supplementalEvidence?.message || "局部重新解读失败，可以重试。"));
}

async function resolveFrameSuggestion(frameId, field, accept) {
  const action = accept ? "accept" : "";
  const url = `${BACKEND_BASE}/api/jobs/${lastCompletedJobId}/frames/${encodeURIComponent(frameId)}/suggestions/${encodeURIComponent(field)}${action ? `/${action}` : ""}`;
  const response = await fetch(url, { method: accept ? "POST" : "DELETE" });
  if (!response.ok) throw new Error(`处理分析建议失败：${await response.text()}`);
  const source = await response.json();
  const job = await fetch(`${BACKEND_BASE}/api/jobs/${lastCompletedJobId}`, { cache: "no-store" }).then((item) => item.json());
  const index = state.frames.findIndex((item) => String(item.id) === String(frameId));
  const mapped = backendFrameToState(source, job);
  if (index >= 0) state.frames[index] = mapped;
  renderSingleFrame(mapped, true);
  setStatus(accept ? "已采用新分析建议。" : "已保留策划当前内容。");
}

function setReviewWorkspaceView(view) {
  const model = state.reviewWorkspace?.model || {};
  const previousView = state.reviewWorkspace?.view;
  const previewReady = ["preview", "preview_ready"].includes(model.reviewState?.status) && model.reviewState?.previewRevision === model.revision;
  const allStagesConfirmed = previewReady || Boolean(model.reviewState?.flowConfirmed) && (model.stages || []).every((stage) => stage.confirmation?.confirmed);
  const competitorMutationBlocked = Boolean(ReviewWorkspace.competitorMutationBlocked?.(state.reviewWorkspace));
  const aliases = { preview: "interaction_preview", ue_flow: "interaction_preview" };
  const views = ["gameplay_directory", "flow", "stage", "interaction_preview", "gameplay", "diagrams", "tables", "final_preview", "analysis_failed"];
  const requestedView = aliases[view] || (views.includes(view) ? view : "flow");
  const routedView = ReviewWorkspace.routeForModel?.(model) || (allStagesConfirmed ? "interaction_preview" : model.reviewState?.flowConfirmed ? "stage" : "flow");
  const order = { gameplay_directory: 0, flow: 1, stage: 2, ue_flow: 3, interaction_preview: 4, gameplay: 5, diagrams: 6, tables: 7, final_preview: 8 };
  const gameplayWorkspaceModel = state.gameplayReviewWorkspace?.model || model.gameplayReviewModel || null;
  const hasPendingPlannerDecisions = (gameplayWorkspaceModel?.chapters || []).some((chapter) =>
    (chapter.decisionCards || []).some((card) => ["pending", "skipped"].includes(card?.status || "pending"))
  );
  const hasGameplayWorkspace = gameplayModelReviewReady(gameplayWorkspaceModel);
  const hasInteractionWorkspace = Boolean((model.stages || []).length);
  const canInspectExistingInteraction = hasInteractionWorkspace && (
    requestedView === "flow" || (requestedView === "stage" && Boolean(model.reviewState?.flowConfirmed))
  );
  const canInspectExistingGameplay = hasGameplayWorkspace && order[requestedView] >= order.gameplay;
  const decisionImpactViews = new Set(["diagrams", "tables", "final_preview"]);
  const canInspectDecisionImpacts = hasPendingPlannerDecisions && order[routedView] >= order.gameplay && decisionImpactViews.has(requestedView);
  const activeView = requestedView === "analysis_failed" || routedView === "analysis_failed"
    ? routedView === "analysis_failed" ? "analysis_failed" : "flow"
    : order[requestedView] > order[routedView] && !canInspectExistingInteraction && !canInspectDecisionImpacts && !canInspectExistingGameplay ? routedView : requestedView;
  state.reviewWorkspace = { ...state.reviewWorkspace, view: activeView };
  if (previousView && previousView !== activeView) {
    const reviewCanvas = document.querySelector(".review-canvas");
    reviewCanvas?.scrollTo?.({ top: 0, left: 0, behavior: "instant" });
    window.scrollTo?.({ top: 0, left: 0, behavior: "instant" });
    if (document.documentElement) document.documentElement.scrollLeft = 0;
    if (document.body) document.body.scrollLeft = 0;
  }
  const workspaceRoot = $("reviewWorkspace");
  if (workspaceRoot?.dataset) workspaceRoot.dataset.activeView = activeView;
  workspaceRoot?.classList?.toggle("is-final-preview", activeView === "final_preview");
  const viewIds = { gameplay_directory: "gameplayDirectoryView", flow: "flowReviewView", stage: "stageReviewView", ue_flow: "ueFlowReviewView", interaction_preview: "exportPreviewView", gameplay: "gameplayReviewView", diagrams: "gameplayDiagramView", tables: "gameplayTableView", final_preview: "finalExportPreviewView", analysis_failed: "analysisFailedView" };
  Object.entries(viewIds).forEach(([name, id]) => {
    const root = $(id);
    root.hidden = name !== activeView;
  });
  document.querySelectorAll("[data-review-view]").forEach((button) => {
    const buttonView = aliases[button.dataset.reviewView] || button.dataset.reviewView;
    const buttonStep = ReviewWorkspace.stepForView?.(buttonView);
    const activeStep = ReviewWorkspace.stepForView?.(activeView);
    const exactSubstep = buttonView === activeView || (buttonView === "flow" && activeView === "stage");
    button.setAttribute("aria-current", exactSubstep ? "step" : "false");
    const canInspectButton = hasPendingPlannerDecisions && order[routedView] >= order.gameplay && decisionImpactViews.has(buttonView);
    const canInspectInteractionButton = hasInteractionWorkspace && (
      buttonView === "flow" || (buttonView === "stage" && Boolean(model.reviewState?.flowConfirmed))
    );
    const canInspectGameplayButton = hasGameplayWorkspace && order[buttonView] >= order.gameplay;
    button.disabled = activeView === "analysis_failed" || (order[buttonView] > order[routedView] && !canInspectInteractionButton && !canInspectButton && !canInspectGameplayButton) || (buttonView === "interaction_preview" && (!allStagesConfirmed || competitorMutationBlocked));
    button.title = !button.disabled
      ? ""
      : activeView === "analysis_failed"
        ? "请先修复截图分析失败"
        : buttonView === "interaction_preview"
          ? "请先完成全部交互环节审核"
          : order[buttonView] >= order.gameplay && !hasGameplayWorkspace
            ? "请先生成并确认玩法目录"
            : "请先完成前置审核";
  });
  const selectedStage = (model.stages || []).find((stage) => stage.id === state.reviewWorkspace.selectedStageId);
  const saveSettled = ["saved", "synced", "conflict_synced"].includes(state.reviewWorkspace.saveStatus);
  const confirmFlow = $("reviewConfirmFlowBtn");
  const confirmStage = $("reviewConfirmStageBtn");
  confirmFlow.hidden = activeView !== "flow";
  confirmFlow.disabled = activeView !== "flow" || model.reviewState?.flowConfirmed || !saveSettled;
  confirmStage.hidden = activeView !== "stage";
  const confirming = state.reviewWorkspace.confirmStatus === "saving";
  confirmStage.disabled = activeView !== "stage" || !model.reviewState?.flowConfirmed || !selectedStage || selectedStage.confirmation?.confirmed || !saveSettled || confirming;
  confirmStage.textContent = confirming ? "正在保存…" : selectedStage ? `确认当前环节：${selectedStage.name || "待命名环节"}` : "确认当前环节";
  const confirmStatus = $("reviewConfirmStatus");
  if (confirmStatus) {
    confirmStatus.textContent = confirming ? "正在保存当前环节，请稍候。" : state.reviewWorkspace.confirmStatus === "failed" ? state.reviewWorkspace.confirmError : "";
    confirmStatus.className = `review-confirm-status${confirming ? " is-saving" : state.reviewWorkspace.confirmStatus === "failed" ? " is-error" : ""}`;
    confirmStatus.setAttribute("role", state.reviewWorkspace.confirmStatus === "failed" ? "alert" : "status");
  }
  $("reviewRouteLabel").textContent = ReviewWorkspace.stepForView?.(activeView)?.label || "素材识别未完成";
}

function showReviewValidationError(message = "") {
  const target = $("reviewValidationError");
  target.textContent = message;
  target.hidden = !message;
}

function reviewUiState() {
  const workspace = state.reviewWorkspace || {};
  return {
    view: workspace.view,
    selectedStageId: workspace.selectedStageId,
    selectedTransitionId: workspace.selectedTransitionId,
    selectedFrameId: workspace.selectedFrameId,
    selection: workspace.selection,
    projectDrawerOpen: workspace.projectDrawerOpen,
  };
}

function clearReviewUiTimer() {
  if (typeof clearTimeout === "function") clearTimeout(reviewUiSaveTimer);
  reviewUiSaveTimer = null;
}

function drainReviewUiStateSave() {
  if (reviewUiSaveInFlight || !reviewUiSaveQueued) return;
  const next = reviewUiSaveQueued;
  reviewUiSaveQueued = null;
  if (state.reviewClient !== next.client) return drainReviewUiStateSave();
  const request = Promise.resolve().then(() => next.client.saveUiState(next.saved, { keepalive: Boolean(next.keepalive) }));
  reviewUiSaveInFlight = request;
  request.catch((error) => {
    if (state.reviewClient === next.client) setStatus(error.message);
  }).finally(() => {
    if (reviewUiSaveInFlight === request) reviewUiSaveInFlight = null;
    drainReviewUiStateSave();
  });
}

function persistReviewUiState(options = {}) {
  if (!state.reviewClient || !state.reviewWorkspace) return;
  if (typeof setTimeout !== "function" || typeof clearTimeout !== "function") return;
  const client = state.reviewClient;
  const saved = reviewUiState();
  clearReviewUiTimer();
  if (options.immediate) {
    reviewUiSaveQueued = { client, saved, keepalive: true };
    drainReviewUiStateSave();
    return;
  }
  reviewUiSaveTimer = setTimeout(() => {
    reviewUiSaveTimer = null;
    if (state.reviewClient !== client) return;
    reviewUiSaveQueued = { client, saved };
    drainReviewUiStateSave();
  }, 300);
}

function makeReviewOperationQueue(client) {
  if (typeof ReviewClient?.createOperationQueue !== "function") return null;
  const jobId = client.jobId;
  const active = () => state.reviewClient === client && client.jobId === jobId;
  return ReviewClient.createOperationQueue({
    isActive: active,
    send: (revision, operations, options) => client.operations(revision, operations, options).then((model) => {
      if (active()) rebuildReviewWorkspace(model);
      return model;
    }),
    onStatus: (saveStatus) => {
      if (!active() || !state.reviewWorkspace) return;
      state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus };
      renderReviewWorkspace(state.reviewWorkspace.model);
    },
    onFailure: (error) => active() && (error.status === 409 && Number.isInteger(error.currentRevision) ? resolveReviewConflict(client) : setStatus(error.message)),
  });
}

function localConflictOperations(model, operations) {
  const collections = { stage: "stages", transition: "transitions", region: "regions", component: "components", constraint: "crossStateConstraints" };
  return operations.filter((operation) => {
    if (operation.type !== "set") return typeof window === "undefined" || window.confirm("检测到结构修改冲突。确定保留本地修改并重新提交？");
    const server = (model[collections[operation.entity]] || []).find((item) => item.id === operation.id)?.[operation.field];
    return server === operation.value || typeof window === "undefined" || window.confirm(`检测到 ${operation.entity}.${operation.field} 冲突。服务器值：${server ?? "空"}\n本地值：${operation.value ?? "空"}\n确定保留本地值？`);
  });
}

async function resolveReviewConflict(client = state.reviewClient) {
  if (!client || client !== state.reviewClient || !state.reviewWorkspace || !state.reviewOperationQueue) return;
  try {
    const model = await loadCanonicalReviewModel(client, "conflict");
    if (!model) return;
    const localOperations = state.reviewOperationQueue.pending();
    const selectedOperations = localConflictOperations(model, localOperations);
    if (!selectedOperations.length) {
      state.reviewOperationQueue.discard();
      state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus: "saved" };
      renderReviewWorkspace(state.reviewWorkspace.model);
      return;
    }
    state.reviewOperationQueue.discard();
    await state.reviewOperationQueue.flush(model.revision, selectedOperations);
  } catch (error) {
    state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus: "failed" };
    renderReviewWorkspace(state.reviewWorkspace.model);
    setStatus(error.message);
  }
}

function renderReferenceBoardAssets(root, model, readOnly) {
  if (typeof ReferenceBoardAssets === "undefined") return;
  ReferenceBoardAssets.render({
    root,
    boards: model.referenceBoards,
    planningCount: (model.stages || []).reduce((count, stage) => count + (stage.representativeFrames || []).length, 0),
    client: state.reviewClient,
    readOnly,
    busy: state.reviewWorkspace.referenceBoardBusy,
    states: state.reviewWorkspace.referenceBoardStates,
    resolveAssetUrl: (relativePath) => `${BACKEND_BASE}/artifacts/${state.reviewClient.jobId}/${relativePath}`,
    onMutate: runReferenceBoardMutation,
  });
}

function gameplayUiStorageKey(client) { return `vpr_gameplay_review_ui_${client.jobId}`; }
function gameplaySavedUiState(client) { try { return JSON.parse(localStorage.getItem(gameplayUiStorageKey(client)) || "{}"); } catch (_) { return {}; } }
function persistGameplayUiState() {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace;
  if (!client || !workspace || typeof localStorage === "undefined") return;
  localStorage.setItem(gameplayUiStorageKey(client), JSON.stringify({ selectedChapterId: workspace.selectedChapterId, selectedTableId: workspace.selectedTableId, activeTab: workspace.activeTab || "content", expandedGroups: workspace.expandedGroups || [], editedGroups: workspace.editedGroups || [], draftDecision: workspace.draftDecision || "" }));
}
function renderGameplayReviewWorkspace() {
  if (!state.gameplayReviewWorkspace || typeof GameplayReview === "undefined") return;
  GameplayReview.render({
    root: $("gameplayReviewView"), model: state.gameplayReviewWorkspace.model, state: state.gameplayReviewWorkspace,
    onSelectChapter: (id) => { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, selectedChapterId: id }; renderGameplayReviewWorkspace(); persistGameplayUiState(); },
    onTab: (activeTab) => { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, activeTab }; renderGameplayReviewWorkspace(); persistGameplayUiState(); },
    onToggleGroup: (chapterId, group) => { const key = `${chapterId}:${group}`; const current = state.gameplayReviewWorkspace.expandedGroups || []; state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, expandedGroups: current.includes(key) ? current.filter((item) => item !== key) : [...current, key] }; renderGameplayReviewWorkspace(); persistGameplayUiState(); },
    onEditRules: (chapterId) => {
      const required = [`${chapterId}:supplemental`, `${chapterId}:rules`];
      const expandedGroups = [...new Set([...(state.gameplayReviewWorkspace.expandedGroups || []), ...required])];
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, selectedChapterId: chapterId, activeTab: "content", expandedGroups, draftDecision: "needs_edit" };
      renderGameplayReviewWorkspace();
      const ruleEditor = $("gameplayReviewView").querySelector?.(".gameplay-planner-summary-editor") || $("gameplayReviewView").querySelector?.(".gameplay-rule-details");
      ruleEditor?.scrollIntoView?.({ block: "start", behavior: "smooth" });
      ruleEditor?.querySelector?.("textarea, input")?.focus?.({ preventScroll: true });
      persistGameplayUiState();
    },
    onOperation: runGameplayOperations,
    onNotice: (message) => setStatus(message),
    onOpenEvidence: (id, opener) => { const returnFocus = opener || state.gameplayReviewWorkspace.evidenceOpener; state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, evidenceDrawer: id, evidenceOpener: id ? opener : null }; renderGameplayReviewWorkspace(); if (!id) document.querySelector(`[data-evidence-anchor="${returnFocus?.getAttribute?.("data-evidence-anchor") || ""}"]`)?.focus?.(); },
    onContext: runGameplayContext,
    onAdjustDirectory: () => navigateReviewWorkspace("gameplay_directory"),
    onSave: () => state.gameplayOperationQueue?.flush?.(state.gameplayReviewWorkspace.model.revision),
    onDecision: (chapterId, value) => {
      if (value === "needs_edit") {
        state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, draftDecision: value };
        renderGameplayReviewWorkspace();
        persistGameplayUiState();
        return;
      }
      runGameplayConfirmation(chapterId, value);
    },
    onConfirm: runGameplayConfirmation,
    resolveEvidenceUrl: (path) => path?.startsWith("/") ? `${BACKEND_BASE}${path}` : path,
  });
}

function openPendingGameplayDecision(target = {}) {
  if (!target.chapterId || !target.cardId || !state.gameplayReviewWorkspace) return;
  reviewUiInteractionVersion += 1;
  state.gameplayReviewWorkspace = {
    ...state.gameplayReviewWorkspace,
    selectedChapterId: target.chapterId,
    activeTab: "content",
  };
  setReviewWorkspaceView("gameplay");
  renderReviewWorkspace(state.reviewWorkspace.model);
  syncReviewViewUrl("gameplay");
  persistReviewUiState();
  persistGameplayUiState();
  setTimeout(() => {
    const card = document.querySelector(`[data-decision-card-id="${target.cardId}"]`);
    card?.scrollIntoView?.({ block: "center", behavior: "smooth" });
    card?.focus?.({ preventScroll: true });
  }, 0);
}

async function reanalyzeReviewFrame(frameId) {
  if (!lastCompletedJobId || !state.reviewWorkspace) throw new Error("请先打开审核工作台。");
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${lastCompletedJobId}/frames/${encodeURIComponent(frameId)}/reanalyze-image`, { method: "POST", body: backendConfigForm() });
  if (!response.ok) throw new Error(`重新识别失败：${await response.text()}`);
  const source = state.reviewWorkspace.model.sources?.[frameId];
  if (source) source.supplementalEvidence = { ...(source.supplementalEvidence || {}), status: "analyzing" };
  renderReviewWorkspace(state.reviewWorkspace.model);
  setStatus("正在重新识别这张原始截图。");
  pollReviewFrameRepair(lastCompletedJobId, frameId);
}

async function pollReviewFrameRepair(jobId, frameId) {
  const client = state.reviewClient;
  if (!client || client.jobId !== jobId) return;
  const model = await client.load();
  const status = model.sources?.[frameId]?.supplementalEvidence?.status;
  if (status === "extracting" || status === "analyzing") {
    rebuildReviewWorkspace(model);
    setTimeout(() => pollReviewFrameRepair(jobId, frameId).catch((error) => setStatus(error.message)), 1200);
    return;
  }
  rebuildReviewWorkspace(model);
  setStatus(status === "ready" ? "这张图已重新识别，请核对识别结果。" : (model.sources?.[frameId]?.supplementalEvidence?.message || "这张图重新识别失败，可以重试。"));
}
function gameplayModelNeedsGeneration(model) {
  return !model
    || ["generation_required", "generation_failed"].includes(model.lifecycleState)
    || model.reviewState?.status === "generation_required";
}
function gameplayDetailQualityErrorLabel(error) {
  const value = String(error || "").trim();
  const chapterId = value.match(/^(GCH-[^:]+):/)?.[1];
  const prefix = chapterId ? `${chapterId}：` : "";
  if (value.includes("FLOW_CHAIN_STATIC_EVIDENCE_IS_NOT_FLOW")) {
    return `${prefix}静态画面、数值或公式不能作为玩法流程`;
  }
  if (value.includes("FLOW_CHAIN_CAUSALITY_MISSING")) {
    return `${prefix}玩法流程缺少“触发或操作→系统结果或状态变化”的完整因果链`;
  }
  return value || "详细玩法规则未通过语义质量检查";
}
function gameplayModelReviewReady(model) {
  if (!model) return false;
  if ((model.reviewState?.structureQualityErrors || []).length) return false;
  if (model.detailQuality?.passed === false) return false;
  const status = model.reviewState?.status || "";
  const phase = model.reviewState?.structurePhase || "";
  if (["detail_generation_pending", "generation_required"].includes(status)) return false;
  const hasDetailedLastValidVersion = Boolean(
    model.lastValidRevision
    && (model.chapters || []).length
    && status === "chapter_review"
    && (phase === "detailed" || !phase)
  );
  if (["pending", "failed"].includes(model.contentState) && !hasDetailedLastValidVersion) return false;
  if (model.contentState === "ready") {
    return (model.chapters || []).length > 0 && status === "chapter_review" && (phase === "detailed" || !phase);
  }
  if (model.lifecycleState === "ready" && status === "chapter_review") {
    return (model.chapters || []).length > 0 && (phase === "detailed" || !phase);
  }
  return !status && !phase && Boolean((model.chapters || []).length || (model.diagrams || []).length || (model.tables || []).length);
}
function recoverableReviewView(requestedView, gameplayModel) {
  const gameplayViewsRequiringModel = new Set(["gameplay", "diagrams", "tables", "final_preview"]);
  return gameplayViewsRequiringModel.has(requestedView) && !gameplayModelReviewReady(gameplayModel)
    ? "gameplay_directory"
    : requestedView;
}
function gameplayGenerationFailureGuidance(record = {}, frameCount = 0) {
  const kind = ["configuration", "network", "quality", "system"].includes(record.failureKind)
    ? record.failureKind
    : "system";
  const reasons = {
    configuration: "视觉模型尚未配置，服务无法发起玩法内容生成。",
    network: "视觉模型连接失败或响应超时，本次生成没有拿到完整结果。",
    quality: "视觉模型已经返回内容，但结果没有通过玩法章节格式或质量校验。",
    system: "玩法生成过程中发生服务内部异常，本次内容没有完成。",
  };
  const actions = {
    configuration: "请先填写并保存视觉模型 API，再点击“生成玩法目录”重新发起。",
    network: "请检查模型服务可用性后重试；持续超时时可改用响应更快的模型。",
    quality: "可以直接重试；若连续失败，请补充能覆盖关键操作、反馈和结果的截图后重新分析。",
    system: "请点击“生成玩法目录”重新发起；若连续出现同类错误，请向管理员提供当前任务名称。",
  };
  const generic = !record.error || record.error === "玩法章节生成失败";
  const reason = generic ? reasons[kind] : record.error;
  let material = "系统尚未取得足够信息判断是否与素材有关。";
  if (Number.isInteger(frameCount) && frameCount >= 2) {
    material = kind === "quality"
      ? `当前项目有 ${frameCount} 张截图，数量已达上传门槛；但截图的有效信息覆盖仍可能不足。`
      : `当前项目有 ${frameCount} 张截图，已达到至少 2 张的上传门槛；本次不是截图数量不足。`;
  } else if (Number.isInteger(frameCount) && frameCount > 0) {
    material = `当前项目只有 ${frameCount} 张截图，少于 2 张上传门槛，请先补充截图。`;
  }
  return { kind, reason, material, action: actions[kind] };
}
function gameplayGenerationProgressView(record = {}, now = Date.now()) {
  const progress = Math.max(0, Math.min(100, Math.round(Number(record.progress) || 0)));
  const phaseLabels = {
    queued: "等待生成任务启动",
    requesting_model: "正在请求视觉模型",
    validating: "正在校验玩法结构",
    repairing: "正在补全玩法细节",
    finalizing: "正在保存生成结果",
  };
  const phaseLabel = phaseLabels[record.phase] || (progress > 0 ? "正在生成玩法内容" : "等待生成任务启动");
  const startedAt = Date.parse(record.startedAt || "");
  const deadlineAt = Date.parse(record.deadlineAt || "");
  const formatDuration = (milliseconds) => {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (!minutes) return `${seconds}秒`;
    return seconds ? `${minutes}分${String(seconds).padStart(2, "0")}秒` : `${minutes}分钟`;
  };
  const elapsedLabel = Number.isFinite(startedAt) ? `已等待 ${formatDuration(now - startedAt)}` : "正在等待服务响应";
  const timeoutLabel = Number.isFinite(startedAt) && Number.isFinite(deadlineAt) && deadlineAt > startedAt
    ? `超过 ${formatDuration(deadlineAt - startedAt)}会自动停止并允许重试`
    : "响应超时后会自动停止并允许重试";
  return { progress, phaseLabel, elapsedLabel, timeoutLabel };
}
function renderGameplayDirectoryWorkspace() {
  const root = $("gameplayDirectoryView");
  const currentModel = state.gameplayReviewWorkspace?.model;
  const structureQualityErrors = currentModel?.reviewState?.structureQualityErrors || [];
  const detailQualityErrors = currentModel?.detailQuality?.passed === false ? (currentModel.detailQuality.errors || []) : [];
  const detailQualityErrorLabels = detailQualityErrors.map(gameplayDetailQualityErrorLabel);
  const needsInitialGeneration = !state.gameplayReviewWorkspace || gameplayModelNeedsGeneration(currentModel);
  const needsDetailGeneration = Boolean(
    currentModel
    && !needsInitialGeneration
    && (
      currentModel.reviewState?.status === "detail_generation_pending"
      || (currentModel.contentState === "failed"
        && currentModel.directory?.status === "confirmed"
        && (currentModel.chapters || []).length)
    )
  );
  const needsStructureRepair = structureQualityErrors.length > 0;
  const needsDetailQualityRepair = detailQualityErrors.length > 0;
  if (needsInitialGeneration || needsDetailGeneration || needsStructureRepair || needsDetailQualityRepair) {
    const generationStatus = state.gameplayReviewGeneration?.status;
    const busy = ["queued", "running", "generating"].includes(generationStatus);
    const preservedChapterCount = needsDetailGeneration ? (currentModel.chapters || []).length : 0;
    const message = structureQualityErrors.length
      ? `检测到旧目录结构不合格：${structureQualityErrors.slice(0, 3).join("；")}。素材和已审核交互均已保留，请重新生成目录。`
      : needsDetailQualityRepair
      ? `详细规则质量未通过：${detailQualityErrorLabels.slice(0, 3).join("；")}。目录、素材和已审核交互均已保留，请重新生成详细规则。`
      : needsDetailGeneration
      ? `已确认的 ${preservedChapterCount} 个目录章节均已保留；详细正文生成完成前，不会开放规则、图解、参数或文档导出。`
      : generationStatus === "failed"
      ? "首次生成没有完成。可以安全重试，现有交互审核内容不会被覆盖。"
      : busy
        ? "玩法目录正在生成，完成后会自动显示。"
        : "当前项目尚未生成玩法目录。生成后即可继续规则、图解、参数和文档审核。";
    if (!document.createElement) {
      root.textContent = generationStatus === "failed"
        ? "玩法目录首次生成未完成。请点击“玩法目录”重新生成；现有交互审核内容不会被覆盖。"
        : message;
      return;
    }
    root.replaceChildren();
    root.classList.add("gameplay-directory-recovery");
    const card = document.createElement("section");
    card.className = "gameplay-directory-recovery-card";
    const eyebrow = document.createElement("span");
    eyebrow.className = `gameplay-directory-recovery-state${generationStatus === "failed" && !structureQualityErrors.length && !needsDetailQualityRepair ? " is-failed" : ""}`;
    eyebrow.textContent = busy ? "正在生成" : structureQualityErrors.length ? "结构需修复" : needsDetailQualityRepair ? "语义需修复" : generationStatus === "failed" ? "生成未完成" : "等待生成";
    const title = document.createElement("h2");
    title.textContent = structureQualityErrors.length ? "修复玩法目录" : needsDetailQualityRepair ? "修复详细玩法规则" : needsDetailGeneration ? "继续生成详细规则" : generationStatus === "failed" ? "重新生成玩法目录" : "生成玩法目录";
    const copy = document.createElement("p");
    copy.textContent = message;
    card.append(eyebrow, title, copy);
    if (busy) {
      const progressView = gameplayGenerationProgressView(state.gameplayReviewGeneration || {});
      const progressPanel = document.createElement("div");
      progressPanel.className = "gameplay-generation-progress";
      const progressHeader = document.createElement("div");
      progressHeader.className = "gameplay-generation-progress-header";
      const phase = document.createElement("strong");
      phase.textContent = progressView.phaseLabel;
      const percentage = document.createElement("span");
      percentage.textContent = `${progressView.progress}%`;
      progressHeader.append(phase, percentage);
      const progress = document.createElement("progress");
      progress.max = 100;
      progress.value = progressView.progress;
      progress.setAttribute("role", "progressbar");
      progress.setAttribute("aria-label", `玩法目录生成进度 ${progressView.progress}%`);
      const meta = document.createElement("p");
      meta.className = "gameplay-generation-progress-meta";
      meta.textContent = `${progressView.elapsedLabel} · ${progressView.timeoutLabel}`;
      progressPanel.append(progressHeader, progress, meta);
      card.append(progressPanel);
    }
    if (generationStatus === "failed" && !structureQualityErrors.length && !needsDetailQualityRepair) {
      const missingApiKey = !hasVisionModelConfig();
      const guidance = gameplayGenerationFailureGuidance(
        missingApiKey
          ? { ...(state.gameplayReviewGeneration || {}), failureKind: "configuration", error: "当前浏览器未填写 API Key，正式服务器也没有内置模型密钥。" }
          : state.gameplayReviewGeneration || {},
        Array.isArray(state.frames) ? state.frames.length : 0,
      );
      const reason = document.createElement("p");
      reason.className = "gameplay-directory-recovery-reason";
      reason.textContent = `失败原因：${guidance.reason}`;
      const material = document.createElement("p");
      material.textContent = guidance.material;
      const action = document.createElement("p");
      action.textContent = `下一步：${guidance.action}`;
      card.append(reason, material, action);
    }
    if (!busy) {
      const generate = document.createElement("button");
      generate.type = "button";
      generate.className = "btn primary";
      generate.textContent = hasVisionModelConfig() ? (structureQualityErrors.length ? "重新生成正确目录" : needsDetailQualityRepair ? "重新生成详细规则" : needsDetailGeneration ? "继续生成详细规则" : "生成玩法目录") : "填写 API Key 后重试";
      generate.onclick = () => void runGameplayGeneration();
      card.append(generate);
    }
    root.append(card);
    return;
  }
  root.classList.remove("gameplay-directory-recovery");
  if (typeof GameplayDirectory === "undefined") return;
  GameplayDirectory.render({
    root, model: state.gameplayReviewWorkspace.model, state: state.gameplayReviewWorkspace,
    onOperation: runGameplayOperations,
    onConfirm: async (pendingOperations = []) => {
      const applyConfirmedDirectoryModel = (confirmedModel) => {
        rebuildGameplayReviewWorkspace(confirmedModel);
        reviewUiInteractionVersion += 1;
        if (confirmedModel.reviewState?.status === "detail_generation_pending") {
          state.gameplayReviewGeneration = {
            status: "queued",
            progress: 0,
            startedFromConfirmedDirectory: true,
          };
          state.reviewWorkspace = { ...state.reviewWorkspace, view: "gameplay_directory" };
          setReviewWorkspaceView("gameplay_directory");
          renderReviewWorkspace(state.reviewWorkspace.model);
          syncReviewViewUrl("gameplay_directory");
          persistReviewUiState();
          setStatus("目录已确认，正在生成详细玩法规则；完成前不会开放后续审核与导出。");
          const jobId = state.reviewClient?.jobId || state.gameplayReviewClient?.jobId;
          if (jobId) setTimeout(() => void pollGameplayGeneration(jobId), 1000);
          return;
        }
        if (confirmedModel.reviewState?.structurePhase === "mechanisms") {
          state.reviewWorkspace = { ...state.reviewWorkspace, view: "gameplay_directory" };
          setReviewWorkspaceView("gameplay_directory");
          renderReviewWorkspace(state.reviewWorkspace.model);
          document.querySelector(".review-canvas")?.scrollTo?.({ top: 0, left: 0, behavior: "instant" });
          syncReviewViewUrl("gameplay_directory");
          persistReviewUiState();
          return;
        }
        state.reviewWorkspace = { ...state.reviewWorkspace, view: "flow" };
        setReviewWorkspaceView("flow");
        renderReviewWorkspace(state.reviewWorkspace.model);
        syncReviewViewUrl("flow");
        persistReviewUiState();
      };
      const attemptedModel = state.gameplayReviewWorkspace.model;
      try {
        if (attemptedModel.reviewState?.structurePhase === "mechanisms" && !ensureVisionModelConfig()) return;
        if (pendingOperations.length) runGameplayOperations(pendingOperations);
        await state.gameplayOperationQueue?.flush?.();
        state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, confirming: true }; renderGameplayDirectoryWorkspace();
        const confirmedModel = await state.gameplayReviewClient.confirmDirectory(
          state.gameplayReviewWorkspace.model.revision,
          { apiBase: $("apiUrl").value.trim(), model: $("model").value.trim(), apiKey: $("apiKey").value.trim() }
        );
        applyConfirmedDirectoryModel(confirmedModel);
      } catch (error) {
        if (error.status !== 409) {
          try {
            const canonical = await state.gameplayReviewClient.load();
            const advancedFromSystems = attemptedModel.reviewState?.structurePhase === "systems" && canonical.reviewState?.structurePhase === "mechanisms";
            const finalDirectoryConfirmed = attemptedModel.reviewState?.structurePhase !== "systems" && canonical.directory?.status === "confirmed";
            if (canonical.revision > attemptedModel.revision && (advancedFromSystems || finalDirectoryConfirmed)) {
              applyConfirmedDirectoryModel(canonical);
              return;
            }
          } catch (_) {}
        }
        state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, confirming: false, saveStatus: "failed" }; renderGameplayDirectoryWorkspace(); setStatus(error.message);
      }
    },
  });
}
function renderGameplayDiagramWorkspace() {
  const root = $("gameplayDiagramView");
  if (!state.gameplayReviewWorkspace?.model) {
    root.textContent = "正在加载玩法模型，请稍候。";
    return;
  }
  if (!gameplayModelReviewReady(state.gameplayReviewWorkspace.model)) {
    root.textContent = "详细玩法规则尚未生成完成，请返回玩法目录继续生成。";
    return;
  }
  if (typeof GameplayDiagrams === "undefined") {
    root.textContent = "图解审核组件加载失败，请刷新页面重试。";
    return;
  }
  GameplayDiagrams.render({
    root, model: state.gameplayReviewWorkspace.model,
    state: { ...(state.gameplayReviewWorkspace.diagramRequestState || { generation: {}, byId: {} }), selectedChapterId: state.gameplayReviewWorkspace.selectedChapterId },
    onGenerate: runGameplayDiagramGeneration,
    onAction: runGameplayDiagramAction,
    onOperation: runGameplayOperations,
    onSelectChapter: (selectedChapterId) => {
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, selectedChapterId };
      persistGameplayUiState();
    },
    onContinue: () => navigateReviewWorkspace("tables"),
  });
}

function navigateReviewWorkspace(view, { immediate = false, expectedUiVersion = null } = {}) {
  if (Number.isInteger(expectedUiVersion) && expectedUiVersion !== reviewUiInteractionVersion) return false;
  reviewUiInteractionVersion += 1;
  setReviewWorkspaceView(view);
  view = state.reviewWorkspace?.view || view;
  renderReviewWorkspace(state.reviewWorkspace.model);
  syncReviewViewUrl(view);
  persistReviewUiState(immediate ? { immediate: true } : {});
  return true;
}

function requestedReviewViewFromUrl() {
  try {
    const value = new URLSearchParams(location.search).get("ui");
    return ["gameplay_directory", "flow", "stage", "interaction_preview", "gameplay", "diagrams", "tables", "final_preview", "analysis_failed"].includes(value) ? value : "";
  } catch (_) { return ""; }
}

function syncReviewViewUrl(view, { replace = false } = {}) {
  if (typeof history === "undefined" || typeof history.replaceState !== "function" || typeof location === "undefined" || typeof URL === "undefined") return;
  const url = new URL(location.href);
  const currentView = url.searchParams.get("ui") || "";
  url.searchParams.set("ui", view);
  const nextState = { ...(history.state || {}), reviewView: view };
  if (replace || currentView === view || typeof history.pushState !== "function") history.replaceState(nextState, "", url);
  else history.pushState(nextState, "", url);
}
function hasVisionModelConfig() {
  const builtInConfigured = typeof publicApiConfig !== "undefined" && Boolean(publicApiConfig?.hasBuiltInApi);
  return Boolean($("apiKey").value.trim() || builtInConfigured);
}
function ensureVisionModelConfig() {
  if (hasVisionModelConfig()) return true;
  const pendingUrl = typeof location !== "undefined" ? location.href : "";
  const panel = $("apiConfigPanel");
  if (panel) { panel.hidden = false; panel.open = true; }
  document.querySelector(".workspace")?.classList.remove("has-review");
  document.body?.classList.remove("has-review");
  panel?.scrollIntoView?.({ block: "start", behavior: "smooth" });
  $("apiKey")?.focus?.();
  setStatus("请先在模型 API 设置中填写视觉模型密钥并保存，再继续自动生成。");
  if (pendingUrl && typeof history !== "undefined" && typeof history.replaceState === "function") {
    history.replaceState(history.state, "", pendingUrl);
  }
  return false;
}
function renderGameplayTableWorkspace() {
  if (!state.gameplayReviewWorkspace || typeof GameplayTables === "undefined") return;
  GameplayTables.render({ root: $("gameplayTableView"), model: state.gameplayReviewWorkspace.model, state: { ...(state.gameplayReviewWorkspace.tableRequestState || { generation: {}, byId: {} }), selectedTableId: state.gameplayReviewWorkspace.selectedTableId, selectedChapterId: state.gameplayReviewWorkspace.selectedChapterId }, onGenerate: runGameplayTableGeneration, onAction: runGameplayTableAction, onSelect: (selectedTableId) => { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, selectedTableId }; persistGameplayUiState(); }, onSelectChapter: (selectedChapterId) => { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, selectedChapterId, selectedTableId: null }; persistGameplayUiState(); }, onOperation: runGameplayOperations, onContinue: () => navigateReviewWorkspace("final_preview", { immediate: true }) });
}
function appendGameplayGenerationLog(root, record = state.gameplayReviewGeneration || {}) {
  const logs = Array.isArray(record.logs) ? record.logs : [];
  if (!logs.length) return;
  const panel = document.createElement("section");
  panel.className = "gameplay-generation-log";
  panel.setAttribute("aria-live", "polite");
  const heading = document.createElement("h4");
  heading.textContent = "生成记录";
  const list = document.createElement("ol");
  logs.forEach((entry) => {
    const row = document.createElement("li");
    row.className = `generation-log-${entry.level || "info"}`;
    row.textContent = `${Number(entry.progress) || 0}% · ${entry.message || "正在处理"}`;
    list.append(row);
  });
  panel.append(heading, list);
  root.append(panel);
  panel.scrollTop = panel.scrollHeight;
}
function localConfirmedFinalPreview(workspace, interaction) {
  const gameplay = workspace?.model || {};
  const confirmedStages = (interaction?.stages || []).filter((stage) => stage.confirmation?.confirmed);
  const confirmedChapters = (gameplay.chapters || []).filter((chapter) => chapter.confirmation?.confirmed);
  if (!confirmedStages.length && !confirmedChapters.length) return null;
  const missingChapters = (gameplay.chapters || []).filter((chapter) => !chapter.confirmation?.confirmed).map((chapter) => ({ id: chapter.id, title: chapter.scope || "待补全章节" }));
  return {
    documentTitle: $("projectName")?.value?.trim() || "完整交互与玩法策划案",
    analysisNote: "本预览直接使用已确认的交互流程与玩法章节生成；不会为已有确认内容强制调用视觉模型。",
    interactionRevision: interaction?.revision,
    gameplayRevision: gameplay.revision,
    // The final renderer still enforces chapters, interaction, tables and
    // diagrams independently. This flag only says the local confirmed model
    // is a valid preview source; keeping it false made an all-green review
    // permanently stop at 99%.
    exportReady: true,
    documentOrder: [],
    missingChapters,
    autoCompletion: { status: "idle", progress: missingChapters.length ? 80 : 100, missingChapters },
    localConfirmedPreview: true,
  };
}
function renderCombinedFinalPreview() {
  const root = $("finalExportPreviewView");
  const workspace = state.gameplayReviewWorkspace;
  const interaction = state.reviewWorkspace?.model;
  if (!root || !workspace || !interaction) return;
  // Only the server-built preview contains the current planning and competitor
  // board SVGs. A local summary must not make P7 look ready with empty boards.
  const preview = workspace.preview;
  root.replaceChildren();
  const contextBar = document.createElement("header"); contextBar.className = "review-context-bar";
  const contextTitle = document.createElement("strong"); contextTitle.textContent = "完整文档";
  const contextPath = document.createElement("span"); contextPath.textContent = "当前素材 / 交互交付物 / 玩法正文 / 飞书文档";
  contextBar.append(contextTitle, contextPath); root.append(contextBar);
  const heading = document.createElement("h3");
  heading.textContent = "完整飞书文档预览";
  if (!preview) {
    const emptyState = document.createElement("section");
    emptyState.className = "final-preview-empty-state";
    const message = document.createElement("p");
    message.textContent = workspace.previewStatus === "failed"
      ? (workspace.previewError || "最终预览生成失败，请重试。")
      : workspace.previewStatus === "loading"
        ? "正在校验交互与玩法版本…"
        : "尚未生成完整预览。点击下方按钮后再开始生成。";
    message.setAttribute("aria-live", "polite");
    emptyState.append(heading, message);
    root.append(emptyState);
    appendGameplayGenerationLog(emptyState);
    if (workspace.previewStatus === "failed") {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn primary";
      retry.textContent = "继续自动补全";
      retry.onclick = () => {
        if (!hasVisionModelConfig()) {
          setStatus("请先在模型设置中填写视觉模型密钥，再继续自动补全。");
          return;
        }
        state.gameplayReviewGeneration = null;
        state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview: null, previewStatus: "idle", previewError: "", autoRepairAttempts: 0 };
        void loadCombinedFinalPreview();
      };
      emptyState.append(retry);
    }
    if (workspace.previewStatus === "idle") {
      const generate = document.createElement("button");
      generate.type = "button";
      generate.className = "btn primary";
      generate.textContent = "生成完整预览";
      generate.onclick = () => void loadCombinedFinalPreview();
      emptyState.append(generate);
    }
    return;
  }
  root.append(heading);
  const mutationBlocked = Boolean(ReviewWorkspace.competitorMutationBlocked?.(state.reviewWorkspace));
  const view = ExportPreview.combinedViewModel(preview, { interaction, gameplay: workspace.model }, mutationBlocked);
  const generationCompletion = ExportPreview.autoCompletionView?.(state.gameplayReviewGeneration || {}) || { busy: false };
  const completion = generationCompletion.busy
    ? state.gameplayReviewGeneration
    : (preview.autoCompletion || generationCompletion);
  FinalDocumentPreview.render({
    root, preview: { ...preview, documentTitle: preview.documentTitle || $("projectName")?.value?.trim() || "完整交互与玩法策划案" }, model: workspace.model, interaction, view,
    interactionPreview: preview.planningBoardPreviewSvg ? { boardPreviewSvg: preview.planningBoardPreviewSvg } : (state.reviewWorkspace?.preview || null),
    completion, publication: currentFeishuPublication || {},
    onDecisionOperation: runGameplayOperations,
    onRegenerate: () => {
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview: null, previewStatus: "idle", previewError: "" };
      void loadCombinedFinalPreview({ forceServer: true });
    },
    onMarkdown: () => { if (typeof downloadOutput === "function") downloadOutput(); else setStatus("Markdown 内容尚未准备好，请重新生成预览。"); },
    onExport: () => publishToFeishuWithAuthorization("new_version").catch((error) => setStatus(error.message)),
    onPublish: () => publishToFeishuWithAuthorization("update").catch((error) => setStatus(error.message)),
    onFeishuAction: (action) => publishToFeishuWithAuthorization(action).catch((error) => setStatus(error.message)),
    onBack: () => {
      reviewUiInteractionVersion += 1;
      setReviewWorkspaceView("tables");
      renderReviewWorkspace(state.reviewWorkspace.model);
      syncReviewViewUrl("tables");
      persistReviewUiState();
    },
    onResolveIncomplete: () => {
      state.gameplayReviewWorkspace = {
        ...state.gameplayReviewWorkspace,
        preview: null,
        previewStatus: "idle",
        previewError: "",
        autoRepairAttempts: 0,
      };
      setStatus("正在根据已确认规则自动修复语言表述和内容颗粒度。");
      void loadCombinedFinalPreview({ forceServer: true });
    },
    onResolvePending: openPendingGameplayDecision,
  });
}
async function loadCombinedFinalPreview({ forceServer = false } = {}) {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace;
  if (!client || !workspace || workspace.previewStatus === "loading") return;
  const shouldAutoComplete = workspace.model.reviewState?.status === "detail_generation_pending" && hasVisionModelConfig();
  if (workspace.model.reviewState?.status === "detail_generation_pending" && !hasVisionModelConfig()) {
    state.gameplayReviewWorkspace = { ...workspace, previewStatus: "failed", previewError: "请先填写并保存视觉模型 API，再继续自动补全。" };
    renderCombinedFinalPreview();
    return;
  }
  state.gameplayReviewWorkspace = { ...workspace, previewStatus: "loading", previewError: "" }; renderCombinedFinalPreview();
  try {
    if (state.gameplayOperationQueue?.hasPending()) await state.gameplayOperationQueue.flush(workspace.model.revision);
    const preview = await client.finalPreview(state.gameplayReviewWorkspace.model.revision, {
      apiBase: $("apiUrl").value.trim(),
      model: $("model").value.trim(),
      apiKey: $("apiKey").value.trim(),
    });
    const completion = ExportPreview.autoCompletionView?.(preview.autoCompletion || {}) || { busy: false };
    if (completion.busy) {
      state.gameplayReviewGeneration = { ...preview.autoCompletion };
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview, previewStatus: "autofilling", previewError: "" };
      setStatus(`${completion.message}，完成后会自动重新生成完整策划案。`);
      const jobId = state.reviewClient?.jobId || client.jobId;
      setTimeout(() => pollGameplayGeneration(jobId, { returnToFinalPreview: true }), 1000);
    } else {
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview, previewStatus: "ready", previewError: "" };
    }
  } catch (error) {
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview: null, previewStatus: "failed", previewError: error.message };
  }
  renderCombinedFinalPreview(); renderCurrentFeishuPublication();
}
function rebuildGameplayReviewWorkspace(model, saveStatus = "saved") {
  const previous = state.gameplayReviewWorkspace || gameplaySavedUiState(state.gameplayReviewClient);
  const selectedReviewView = state.reviewWorkspace?.view;
  state.gameplayReviewWorkspace = GameplayWorkspace.rebuild(model, saveStatus, previous);
  state.gameplayReviewWorkspace.activeTab = previous.activeTab || "content";
  if (state.reviewWorkspace?.model) {
    const interaction = { ...state.reviewWorkspace.model, gameplayReviewModel: model };
    state.reviewWorkspace = ReviewWorkspace.rebuild(interaction, state.reviewWorkspace.saveStatus, state.reviewWorkspace);
    if (selectedReviewView) setReviewWorkspaceView(selectedReviewView);
    renderReviewWorkspace(interaction);
  } else renderGameplayReviewWorkspace();
  persistGameplayUiState();
}
function advanceToCurrentReviewRoute(expectedUiVersion = null) {
  const model = state.reviewWorkspace?.model;
  if (!model) return;
  const routedView = ReviewWorkspace.routeForModel(model);
  const currentView = state.reviewWorkspace?.view || routedView;
  const order = { gameplay_directory: 0, flow: 1, stage: 2, interaction_preview: 3, gameplay: 4, diagrams: 5, tables: 6, final_preview: 7 };
  // Saving an existing later artifact must not throw the planner back to an
  // earlier unfinished gate. Backward movement belongs to explicit return or
  // "resolve incomplete" actions; successful saves may stay or advance.
  const targetView = order[routedView] < order[currentView] ? currentView : routedView;
  navigateReviewWorkspace(targetView, { expectedUiVersion });
}
function makeGameplayOperationQueue(client) {
  const active = () => state.gameplayReviewClient === client;
  return GameplayReviewClient.createOperationQueue({
    isActive: active,
    send: (revision, operations, options) => client.operations(revision, operations, options).then((model) => { if (active()) rebuildGameplayReviewWorkspace(model); return model; }),
    onStatus: (saveStatus) => { if (active() && state.gameplayReviewWorkspace) { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, saveStatus }; renderGameplayReviewWorkspace(); } },
    onFailure: (error) => { if (active()) error.status === 409 ? syncGameplayReviewModel(client, "conflict_synced") : setStatus("玩法修改未保存，请重试。"); },
  });
}
async function syncGameplayReviewModel(client = state.gameplayReviewClient, saveStatus = "synced") {
  if (!client) return;
  const version = ++gameplaySyncVersion;
  try { const model = await client.load(); if (version === gameplaySyncVersion && client === state.gameplayReviewClient) rebuildGameplayReviewWorkspace(model, saveStatus); }
  catch (error) { if (client === state.gameplayReviewClient) { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, saveStatus: "failed" }; renderGameplayReviewWorkspace(); setStatus("玩法审阅加载失败，请重试。"); } }
}
function gameplayGenerationBusy() {
  return ["queued", "running", "generating"].includes(state.gameplayReviewGeneration?.status);
}
async function pollGameplayGeneration(jobId, { returnToFinalPreview = false } = {}) {
  try {
    const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`读取玩法生成进度失败：${response.status}`);
    const job = await response.json();
    state.gameplayReviewGeneration = job.gameplayReviewGeneration || null;
    if (job.gameplayReviewModel && state.gameplayReviewGeneration?.status === "completed") {
      await syncBackendResult(job);
      if (returnToFinalPreview) {
        setReviewWorkspaceView("final_preview");
        state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview: null, previewStatus: "idle", previewError: "" };
        renderReviewWorkspace(state.reviewWorkspace.model);
        setStatus("玩法章节已自动补全，正在重新生成完整策划案。");
        await loadCombinedFinalPreview();
        return;
      }
      setReviewWorkspaceView("gameplay_directory");
      renderReviewWorkspace(state.reviewWorkspace.model);
      setStatus("玩法章节已生成，请按章节审核规则、参数和待确认项。");
      return;
    }
    if (state.gameplayReviewGeneration?.status === "failed") {
      const failure = state.gameplayReviewGeneration;
      const attempts = Number(state.gameplayReviewWorkspace?.autoRepairAttempts || 0);
      if (returnToFinalPreview && failure.failureKind === "quality" && attempts < 3) {
        state.gameplayReviewWorkspace = {
          ...state.gameplayReviewWorkspace,
          preview: null,
          previewStatus: "idle",
          previewError: "",
          autoRepairAttempts: attempts + 1,
        };
        setStatus(`主策检查未通过，正在自动修复（第${attempts + 1}/3轮）。`);
        renderReviewWorkspace(state.reviewWorkspace.model);
        setTimeout(() => void loadCombinedFinalPreview(), 1000);
        return;
      }
      const failureError = new Error(failure.error || "玩法章节生成失败");
      failureError.generation = failure;
      throw failureError;
    }
    renderReviewWorkspace(state.reviewWorkspace.model);
    setTimeout(() => pollGameplayGeneration(jobId, { returnToFinalPreview }), 1000);
  } catch (error) {
    state.gameplayReviewGeneration = { ...(error.generation || state.gameplayReviewGeneration || {}), status: "failed", error: error.message };
    if (returnToFinalPreview && state.gameplayReviewWorkspace) {
      state.gameplayReviewWorkspace = {
        ...state.gameplayReviewWorkspace,
        previewStatus: "failed",
        previewError: "自动补全失败，请重试；已经确认的策划结论不会被覆盖。",
      };
    }
    renderReviewWorkspace(state.reviewWorkspace.model);
    setStatus(`玩法章节生成失败：${error.message}。请重试。`);
  }
}
async function runGameplayGeneration() {
  if (!state.reviewClient || !state.reviewWorkspace || gameplayGenerationBusy()) return;
  if (!ensureVisionModelConfig()) return;
  const jobId = state.reviewClient.jobId;
  state.gameplayReviewClient = state.gameplayReviewClient?.jobId === jobId ? state.gameplayReviewClient : new GameplayReviewClient(BACKEND_BASE, jobId);
  state.gameplayReviewGeneration = { status: "queued", progress: 0, startedFromInteractionPreview: true };
  renderReviewWorkspace(state.reviewWorkspace.model);
  setStatus("正在根据已确认的交互流程生成玩法章节…");
  try {
    const form = backendConfigForm();
    const currentModel = state.gameplayReviewWorkspace?.model || {};
    const depthVersion = Number(currentModel.reviewState?.depthContractVersion || 0);
    if (!(currentModel.systems || []).length
      || depthVersion < 2
      || (currentModel.reviewState?.structureQualityErrors || []).length
      || currentModel.detailQuality?.passed === false) {
      form.append("force", "true");
    }
    await state.gameplayReviewClient.generate(form);
    await pollGameplayGeneration(jobId);
  } catch (error) {
    state.gameplayReviewGeneration = { ...state.gameplayReviewGeneration, status: "failed", error: error.message };
    renderReviewWorkspace(state.reviewWorkspace.model);
    setStatus(`玩法章节生成失败：${error.message}。请重试。`);
  }
}
async function enterExistingGameplayReview() {
  const client = state.gameplayReviewClient;
  if (!client || !state.reviewWorkspace || !state.gameplayReviewWorkspace) return;
  const actionUiVersion = ++reviewUiInteractionVersion;
  try {
    await client.generate(backendConfigForm());
    if (client !== state.gameplayReviewClient || actionUiVersion !== reviewUiInteractionVersion) return;
    const model = await client.load();
    if (client !== state.gameplayReviewClient || actionUiVersion !== reviewUiInteractionVersion) return;
    rebuildGameplayReviewWorkspace(model);
    navigateReviewWorkspace("gameplay", { expectedUiVersion: actionUiVersion });
  } catch (error) {
    if (client !== state.gameplayReviewClient) return;
    setStatus(`进入规则审核失败：${error.message}`);
  }
}
function runGameplayOperations(operations) {
  const workspace = state.gameplayReviewWorkspace; const queue = state.gameplayOperationQueue;
  if (!workspace || !queue || !operations?.length) return;
  const revision = Number.isInteger(workspace.model?.revision)
    ? workspace.model.revision
    : state.reviewWorkspace?.model?.gameplayReviewModel?.revision;
  if (!Number.isInteger(revision)) {
    syncGameplayReviewModel(state.gameplayReviewClient, "conflict_synced");
    setStatus("玩法版本正在同步，请在内容恢复后重试本次操作。");
    return;
  }
  const editedGroups = [...(workspace.editedGroups || [])];
  operations.filter((operation) => ["upsert_claim", "delete_claim"].includes(operation.type)).forEach((operation) => { const key = `${operation.chapterId}:claims`; if (!editedGroups.includes(key)) editedGroups.push(key); });
  state.gameplayReviewWorkspace = { ...workspace, editedGroups };
  operations.forEach((operation) => queue.push(operation, revision));
}
async function runGameplayConfirmation(chapterId, decision) {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace;
  if (!client || !workspace) return;
  const actionUiVersion = ++reviewUiInteractionVersion;
  const applyConfirmedModel = (model) => {
    const next = decision === "rejected" ? null : GameplayReview.nextPending(model.chapters, chapterId, 1);
    rebuildGameplayReviewWorkspace(model);
    const message = decision === "rejected" ? "已标记为退回修改，请继续补充本章。" : next ? `已保存，接下来检查“${next.scope}”。` : "本章已保存，所有玩法章节均已完成。";
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, selectedChapterId: next?.id || chapterId, confirmationStatus: "saved", confirmationMessage: message };
    if (next) renderGameplayReviewWorkspace(); else advanceToCurrentReviewRoute(actionUiVersion);
    persistGameplayUiState(); setStatus(message);
  };
  state.gameplayReviewWorkspace = { ...workspace, confirmationStatus: "saving", confirmationMessage: "" }; renderGameplayReviewWorkspace();
  try {
    if (state.gameplayOperationQueue?.hasPending()) await state.gameplayOperationQueue.flush(workspace.model.revision);
    const model = await client.confirmChapter(chapterId, state.gameplayReviewWorkspace.model.revision, decision);
    applyConfirmedModel(model);
  } catch (error) {
    if (error.status === 409) return syncGameplayReviewModel(client, "conflict_synced");
    try {
      const canonical = await client.load();
      if (client !== state.gameplayReviewClient || !state.gameplayReviewWorkspace) return;
      const chapter = canonical.chapters?.find((item) => item.id === chapterId);
      const persisted = chapter?.status === decision && Boolean(chapter?.confirmation?.confirmed) === (decision !== "rejected");
      if (persisted) {
        applyConfirmedModel(canonical);
        return;
      }
    } catch (_) {}
    const raw = String(error.message || "");
    const message = /parameter .* incomplete/i.test(raw) ? "还有数值或条件没有填写完整，请展开数值区域检查。" : /source-backed claim/i.test(raw) ? "缺少可核对的素材依据，请先补充对应画面。" : /blocking findings|gameplay gate/i.test(raw) ? "还有需要处理的问题，请展开“需要你确认的问题”。" : "审核结论没有保存，请检查本章内容后重试。";
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, confirmationStatus: "failed", confirmationMessage: message };
    renderGameplayReviewWorkspace(); setStatus(message);
  }
}
function parseGameplayVideoTimestamp(value) {
  const input = String(value || "").trim();
  if (!input) return null;
  if (/^\d+(?:\.\d+)?$/.test(input)) return Number(input);
  const match = input.match(/^(\d+):(\d{1,2}(?:\.\d+)?)$/);
  if (!match || Number(match[2]) >= 60) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

async function runGameplayContext(chapterId, anchorFrameId, missingFields, opener, manualTimestamp = null) {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace;
  if (!client || !workspace) return;
  state.gameplayReviewWorkspace = { ...workspace, contextStatus: "matching" }; renderGameplayReviewWorkspace();
  try {
    const result = await client.context(chapterId, workspace.model.revision, anchorFrameId, missingFields, manualTimestamp);
    const contextStatus = result.status === "needs_planner_location" ? "needs_location" : result.status;
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, contextStatus }; renderGameplayReviewWorkspace();
    if (result.status === "completed") await syncGameplayReviewModel(client);
    if (result.status === "needs_planner_location" && manualTimestamp == null) {
      const entered = window.prompt("未能自动匹配截图。请输入对应视频时间（mm:ss 或秒数）：", "");
      const seconds = parseGameplayVideoTimestamp(entered);
      if (seconds != null) return runGameplayContext(chapterId, anchorFrameId, missingFields, opener, seconds);
    }
    document.querySelector(`.gameplay-context-button[data-context-chapter="${chapterId}"]`)?.focus();
  } catch (error) { if (error.status === 409) return syncGameplayReviewModel(client, "conflict_synced"); state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, contextStatus: "failed" }; renderGameplayReviewWorkspace(); document.querySelector(`.gameplay-context-button[data-context-chapter="${chapterId}"]`)?.focus(); }
}
async function runGameplayDiagramGeneration() {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace;
  if (!client || !workspace) return;
  const current = workspace.diagramRequestState || { generation: {}, byId: {} };
  if (current.generation?.status === "pending") return;
  state.gameplayReviewWorkspace = { ...workspace, diagramRequestState: { ...current, generation: { status: "pending", message: "正在生成图解…" } } }; renderGameplayDiagramWorkspace();
  try {
    rebuildGameplayReviewWorkspace(await client.diagrams(workspace.model.revision));
    const next = state.gameplayReviewWorkspace.diagramRequestState || { generation: {}, byId: {} };
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, diagramRequestState: { ...next, generation: { status: "success", message: "图解已生成。" } } }; renderGameplayDiagramWorkspace();
  } catch (error) {
    const status = error.status === 409 ? "conflict" : "error"; const message = status === "conflict" ? "版本已变化，正在同步最新图解。" : "图解生成失败，请重试。";
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, diagramRequestState: { ...(state.gameplayReviewWorkspace.diagramRequestState || current), generation: { status, message } } }; renderGameplayDiagramWorkspace();
    if (status === "conflict") return syncGameplayReviewModel(client, "conflict_synced");
    setStatus(error.message || message);
  }
}
async function runGameplayTableGeneration() {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace; if (!client || !workspace) return;
  const current = workspace.tableRequestState || { generation: {}, byId: {} }; if (current.generation?.status === "pending") return;
  state.gameplayReviewWorkspace = { ...workspace, tableRequestState: { ...current, generation: { status: "pending", message: "正在自动生成表格…" } } }; renderGameplayTableWorkspace();
  try { rebuildGameplayReviewWorkspace(await client.tables(workspace.model.revision)); const next = state.gameplayReviewWorkspace.tableRequestState || { generation: {}, byId: {} }; state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, tableRequestState: { ...next, generation: { status: "success", message: "表格已生成。" } } }; renderGameplayTableWorkspace(); }
  catch (error) { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, tableRequestState: { ...current, generation: { status: "error", message: "表格生成失败，请重试。" } } }; renderGameplayTableWorkspace(); setStatus(error.message); }
}
async function runGameplayTableAction(action, tableId, feedback) {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace; if (!client || !workspace) return;
  const actionUiVersion = ++reviewUiInteractionVersion;
  if (action === "regenerate" && !feedback) { setStatus("请先填写这张表的重修意见。"); return; }
  const current = workspace.tableRequestState || { generation: {}, byId: {} }; state.gameplayReviewWorkspace = { ...workspace, tableRequestState: { ...current, byId: { ...current.byId, [tableId]: { status: "pending" } } } }; renderGameplayTableWorkspace();
  try { rebuildGameplayReviewWorkspace(await client.tableAction(action, workspace.model.revision, tableId, feedback)); advanceToCurrentReviewRoute(actionUiVersion); }
  catch (error) { state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, tableRequestState: { ...current, byId: { ...current.byId, [tableId]: { status: "error", message: "处理失败，请重试。" } } } }; renderGameplayTableWorkspace(); setStatus(error.message); }
}
async function runGameplayDiagramAction(action, diagramId, feedback) {
  const client = state.gameplayReviewClient; const workspace = state.gameplayReviewWorkspace;
  if (!client || !workspace) return;
  const actionUiVersion = ++reviewUiInteractionVersion;
  if (action === "regenerate" && !feedback) { setStatus("请先填写这张图的重修意见。"); return; }
  const current = workspace.diagramRequestState || { generation: {}, byId: {} };
  if (current.byId?.[diagramId]?.status === "pending") return;
  const actionLabel = { approve: "通过", regenerate: "重修", delete: "删除" }[action] || "处理";
  state.gameplayReviewWorkspace = { ...workspace, diagramRequestState: { ...current, byId: { ...current.byId, [diagramId]: { status: "pending", message: `正在${actionLabel}这张图…` } } } }; renderGameplayDiagramWorkspace();
  try {
    const method = { approve: "approveDiagram", regenerate: "regenerateDiagram", delete: "deleteDiagram" }[action];
    if (!method) return;
    rebuildGameplayReviewWorkspace(await client[method](workspace.model.revision, diagramId, feedback));
    const next = state.gameplayReviewWorkspace.diagramRequestState || { generation: {}, byId: {} };
    const result = { status: "success", message: `图解已${actionLabel}。` };
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, diagramRequestState: { ...next, byId: { ...next.byId, [diagramId]: result }, ...(action === "delete" ? { announcement: result } : {}) } };
    advanceToCurrentReviewRoute(actionUiVersion);
  } catch (error) {
    const status = error.status === 409 ? "conflict" : "error"; const message = status === "conflict" ? "版本已变化，正在同步最新图解。" : `图解${actionLabel}失败，请重试。`;
    const next = state.gameplayReviewWorkspace.diagramRequestState || current;
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, diagramRequestState: { ...next, byId: { ...next.byId, [diagramId]: { status, message } } } }; renderGameplayDiagramWorkspace();
    if (status === "conflict") return syncGameplayReviewModel(client, "conflict_synced");
    setStatus(error.message || message);
  }
}

function renderReviewWorkspace(model) {
  $("reviewWorkspace").hidden = false;
  $("reviewStageCount").textContent = `${model.stages?.length || 0} 个`;
  const statusLabels = { queued: "等待保存…", saving: "正在保存…", failed: "保存失败，请重试", conflict: "检测到冲突，正在等待选择", synced: "已同步最新版本", conflict_synced: "检测到版本冲突，已同步最新版本", saved: "已保存" };
  const gameplayHistoryActive = typeof GameplayWorkspace !== "undefined" && ["gameplay_directory", "gameplay", "diagrams", "tables", "final_preview"].includes(state.reviewWorkspace.view) && state.gameplayReviewWorkspace?.model;
  const history = gameplayHistoryActive ? GameplayWorkspace.historyControls(state.gameplayReviewWorkspace.model) : ReviewWorkspace.historyControls(model);
  const readOnly = state.reviewWorkspace.view === "analysis_failed";
  const saveSettled = ["saved", "synced", "conflict_synced"].includes(state.reviewWorkspace.saveStatus);
  const competitorMutationBlocked = Boolean(ReviewWorkspace.competitorMutationBlocked?.(state.reviewWorkspace));
  $("copyBtn").disabled = competitorMutationBlocked || !$("output")?.value;
  $("downloadBtn").disabled = competitorMutationBlocked || !$("output")?.value;
  $("reviewSaveStatus").textContent = statusLabels[state.reviewWorkspace.saveStatus] || statusLabels.saved;
  $("reviewUndoBtn").disabled = readOnly || !saveSettled || !history.canUndo;
  $("reviewRedoBtn").disabled = readOnly || !saveSettled || !history.canRedo;
  $("analysisFailedMessage").textContent = model.quality?.blockers?.length
    ? `当前分析草稿未满足审核条件：${model.quality.blockers.join("、")}。请重新分析素材后再继续审核。`
    : "当前分析草稿未满足审核条件。请重新分析素材后再继续审核。";
  $("reviewProjectDrawer").classList.toggle("is-open", state.reviewWorkspace.projectDrawerOpen);
  $("reviewProjectDrawerToggle").setAttribute("aria-expanded", String(state.reviewWorkspace.projectDrawerOpen));
  setReviewWorkspaceView(state.reviewWorkspace.view);
  if (typeof FlowReview !== "undefined") {
    FlowReview.render({
      root: $("flowReviewView"),
      model,
      selectedTransitionId: state.reviewWorkspace.selection?.type === "transition" ? state.reviewWorkspace.selection.id : null,
      selection: state.reviewWorkspace.selection,
      readOnly,
      resolveSourceUrl: (path) => path?.startsWith("/") ? `${BACKEND_BASE}${path}` : path,
      onOperation: runReviewOperations,
      onConfirmStage: async (stageId) => {
        state.reviewWorkspace = ReviewWorkspace.selectStage(state.reviewWorkspace, model, stageId);
        await runReviewConfirmation("stage");
        if (state.reviewWorkspace?.view !== "stage") return;
        reviewUiInteractionVersion += 1;
        state.reviewWorkspace = { ...state.reviewWorkspace, view: "flow" };
        setReviewWorkspaceView("flow");
        renderReviewWorkspace(state.reviewWorkspace.model);
        syncReviewViewUrl("flow");
        persistReviewUiState();
      },
      onSelectTransition: (transition) => {
        state.reviewWorkspace = ReviewWorkspace.select(state.reviewWorkspace, { type: "transition", id: transition.id, stageId: transition.sourceStageId, frameId: transition.sourceFrameId });
        renderReviewWorkspace(model);
        persistReviewUiState({ immediate: true });
      },
      onAdvanceStage: (stage) => {
        if (!stage?.id) return;
        state.reviewWorkspace = ReviewWorkspace.selectStage(state.reviewWorkspace, state.reviewWorkspace.model, stage.id);
        renderReviewWorkspace(state.reviewWorkspace.model);
        persistReviewUiState({ immediate: true });
      },
    });
  }
  if (typeof StageReview !== "undefined") {
    StageReview.render({
      root: $("stageReviewView"), model, selectedStageId: state.reviewWorkspace.selectedStageId,
      selectedFrameId: state.reviewWorkspace.selectedFrameId, selection: state.reviewWorkspace.selection, readOnly,
      showAllFrames: state.reviewWorkspace.showAllFrames, resolveSourceUrl: (path) => path?.startsWith("/") ? `${BACKEND_BASE}${path}` : path,
      onOperation: runReviewOperations,
      onReanalyzeFrame: (frameId) => reanalyzeReviewFrame(frameId).catch((error) => setStatus(error.message)),
      onShowAllFrames: (value) => { state.reviewWorkspace = ReviewWorkspace.showAllFrames(state.reviewWorkspace, value); renderReviewWorkspace(model); },
      onSelectFrame: (selection) => {
        state.reviewWorkspace = ReviewWorkspace.select(state.reviewWorkspace, selection);
        persistReviewUiState();
      },
      onSelect: (selection) => {
        state.reviewWorkspace = selection.type === "stage"
          ? ReviewWorkspace.selectStage(state.reviewWorkspace, model, selection.stageId || selection.id)
          : ReviewWorkspace.select(state.reviewWorkspace, selection);
        renderReviewWorkspace(model);
        persistReviewUiState();
      },
    });
  }
  if (state.reviewWorkspace.view === "ue_flow" && typeof UeFlowReview !== "undefined") UeFlowReview.render({
    root: $("ueFlowReviewView"), model,
    resolveSourceUrl: (path) => path?.startsWith("/") ? `${BACKEND_BASE}${path}` : path,
    onBack: () => navigateReviewWorkspace("flow", { immediate: true }),
    onRegenerate: () => { setStatus("UE 流转图读取当前已确认交互数据；如需变更，请返回 P2-1 修改并重新确认。"); },
    onConfirm: () => runReviewConfirmation("ue_flow", { nextView: "interaction_preview" }),
  });
  if (state.reviewWorkspace.view === "gameplay_directory") renderGameplayDirectoryWorkspace();
  if (state.reviewWorkspace.view === "gameplay") renderGameplayReviewWorkspace();
  if (state.reviewWorkspace.view === "diagrams") renderGameplayDiagramWorkspace();
  if (state.reviewWorkspace.view === "tables") renderGameplayTableWorkspace();
  if (state.reviewWorkspace.view === "final_preview") renderCombinedFinalPreview();
  if (state.reviewWorkspace.view === "interaction_preview") {
    const previewRoot = $("exportPreviewView");
    const preview = state.reviewWorkspace.preview;
    const gameplayDraftReady = gameplayModelReviewReady(state.gameplayReviewWorkspace?.model || model.gameplayReviewModel);
    if (typeof ExportPreview !== "undefined" && preview?.boardPreviewSvg) ExportPreview.render({
      root: $("exportPreviewView"), model, preview: state.reviewWorkspace.preview,
      boardStateKey: `vpr_planning_board_ui_${state.reviewClient?.jobId || "current"}`,
      mutationBlocked: competitorMutationBlocked,
      onRoute: (route) => {
        if (route.selection) state.reviewWorkspace = ReviewWorkspace.select(state.reviewWorkspace, route.selection);
        if (route.stageId) state.reviewWorkspace = ReviewWorkspace.select(state.reviewWorkspace, { type: "stage", id: route.stageId, stageId: route.stageId });
        if (route.transitionId) {
          const transition = (model.transitions || []).find((item) => item.id === route.transitionId);
          if (transition) state.reviewWorkspace = ReviewWorkspace.select(state.reviewWorkspace, { type: "transition", id: transition.id, stageId: transition.sourceStageId, frameId: transition.sourceFrameId });
        }
        if (route.domain) {
          const rule = (model.ruleDomains?.[route.domain] || []).find((item) => item.id === route.ruleId);
          state.reviewWorkspace = { ...state.reviewWorkspace, selectedRuleDomain: route.domain, selectedRuleId: route.ruleId, ruleMobilePane: "editor", selection: rule ? { type: "rule", domain: route.domain, id: rule.id, stageId: rule.stageId, frameId: rule.frameId || null } : null };
        }
        navigateReviewWorkspace(route.view);
      },
      onContinue: gameplayDraftReady ? enterExistingGameplayReview : runGameplayGeneration,
      continueLabel: gameplayDraftReady ? "进入规则审核" : "",
      onRetry: () => loadReviewPreview({ flushPending: false }),
      continueBusy: gameplayGenerationBusy(),
      generation: (!gameplayDraftReady && (model.gameplayReviewModel || state.gameplayReviewGeneration?.startedFromInteractionPreview))
        ? (state.gameplayReviewGeneration || null)
        : null,
    });
    else if (competitorMutationBlocked) renderReferenceBoardAssets(previewRoot, model, readOnly);
    else if (state.reviewWorkspace.previewStatus === "loading") {
      if (typeof ExportPreview?.renderLoading === "function") ExportPreview.renderLoading(previewRoot, "正在整理页面关系");
      else previewRoot.textContent = "正在生成页面关系预览，请稍候。";
    }
    else if (state.reviewWorkspace.previewStatus === "failed") {
      if (typeof ExportPreview?.renderRecovery === "function") ExportPreview.renderRecovery(previewRoot, {
        failed: true,
        message: state.reviewWorkspace.previewError || "页面关系暂时没有生成，请重新尝试。",
        onRetry: () => loadReviewPreview({ flushPending: false }),
      });
      else previewRoot.textContent = `策划草图生成失败：${state.reviewWorkspace.previewError || "未知错误"}。请重试生成。`;
    }
    else if (state.reviewWorkspace.previewStatus === "idle") {
      if (typeof ExportPreview?.renderLoading === "function") ExportPreview.renderLoading(previewRoot, "正在生成策划草图");
      else previewRoot.textContent = "正在生成策划草图，请稍候。";
      void loadReviewPreview({ flushPending: false });
    }
    else if (typeof ExportPreview?.renderRecovery === "function") ExportPreview.renderRecovery(previewRoot, {
      message: "当前任务的页面关系还没有生成，点击下方按钮即可继续，不需要重新上传素材。",
      onRetry: () => loadReviewPreview({ flushPending: false }),
    });
    else previewRoot.textContent = "策划草图尚未生成，请重新生成。";
  }
}

function renderCurrentFeishuPublication() {
  renderFeishuPublicationState(currentFeishuPublication, Boolean($("output")?.value.trim()));
}

function rebuildReviewWorkspace(model, saveStatus = "saved", restoreSavedUiState = false) {
  const saved = restoreSavedUiState && typeof ReviewClient?.restoreUiState === "function" ? { ...state.reviewWorkspace, ...ReviewClient.restoreUiState(model, model.reviewUiState) } : state.reviewWorkspace;
  state.reviewWorkspace = ReviewWorkspace.rebuild(model, saveStatus, saved);
  renderReviewWorkspace(model);
  persistReviewUiState();
  if (ReviewWorkspace.needsPreviewLoad?.(state.reviewWorkspace)) void loadReviewPreview({ flushPending: false });
}

async function loadCanonicalReviewModel(client, saveStatus) {
  const syncVersion = ++reviewSyncVersion;
  const uiVersion = reviewUiInteractionVersion;
  const interactionModel = await client.load();
  if (syncVersion !== reviewSyncVersion || client !== state.reviewClient) return null;
  const selectedViewDuringSync = uiVersion !== reviewUiInteractionVersion ? state.reviewWorkspace?.view : null;
  const gameplayModel = state.gameplayReviewWorkspace?.model || state.reviewWorkspace?.model?.gameplayReviewModel;
  // The dedicated gameplay model is the authoritative, independently revised
  // copy. Never let a slower canonical-interaction response temporarily replace
  // it with the older embedded snapshot and make P5/P6 counts jump backwards.
  const model = gameplayModel
    ? { ...interactionModel, gameplayReviewModel: gameplayModel }
    : interactionModel;
  rebuildReviewWorkspace(model, saveStatus, uiVersion === reviewUiInteractionVersion);
  if (selectedViewDuringSync) {
    setReviewWorkspaceView(selectedViewDuringSync);
    renderReviewWorkspace(model);
    persistReviewUiState();
  }
  return model;
}

async function syncCanonicalReviewModel(client, saveStatus = "synced") {
  try {
    await loadCanonicalReviewModel(client, saveStatus);
  } catch (error) {
    if (client !== state.reviewClient) return;
    state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus: "failed" };
    renderReviewWorkspace(state.reviewWorkspace.model);
    setStatus(error.message);
  }
}

async function runReviewHistory(action) {
  if (!state.reviewClient || !state.reviewWorkspace) return;
  if (state.reviewOperationQueue?.hasPending()) {
    try {
      await state.reviewOperationQueue.flush(state.reviewWorkspace.model.revision);
    } catch (_) {
      setStatus("待保存的审核修改未能同步，不能执行撤销或重做。");
      return;
    }
  }
  const history = ReviewWorkspace.historyControls(state.reviewWorkspace.model);
  if ((action === "undo" && !history.canUndo) || (action === "redo" && !history.canRedo)) return;
  const operationVersion = ++reviewSyncVersion;
  state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus: "saving" };
  renderReviewWorkspace(state.reviewWorkspace.model);
  try {
    const model = await state.reviewClient[action](state.reviewWorkspace.model.revision);
    if (operationVersion !== reviewSyncVersion) return;
    rebuildReviewWorkspace(model);
  } catch (error) {
    if (operationVersion !== reviewSyncVersion) return;
    if (error.status === 409) return syncCanonicalReviewModel(state.reviewClient, "conflict_synced");
    state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus: "failed" };
    renderReviewWorkspace(state.reviewWorkspace.model);
    setStatus(error.message);
  }
}

async function runReviewConfirmation(kind, { nextView = "stage" } = {}) {
  const client = state.reviewClient;
  if (!client || !state.reviewWorkspace) return;
  const actionUiVersion = ++reviewUiInteractionVersion;
  const previousSaveStatus = state.reviewWorkspace.saveStatus;
  let attemptedStageId = null;
  showReviewValidationError();
  try {
    if (state.reviewOperationQueue?.hasPending()) await state.reviewOperationQueue.flush(state.reviewWorkspace.model.revision);
    if (client !== state.reviewClient || !state.reviewWorkspace) return;
    const revision = state.reviewWorkspace.model.revision;
    const stageId = state.reviewWorkspace.selectedStageId;
    attemptedStageId = stageId;
    const operationVersion = ++reviewSyncVersion;
    state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus: "saving", confirmStatus: "saving", confirmError: "" };
    renderReviewWorkspace(state.reviewWorkspace.model);
    const model = kind === "flow" ? await client.confirmFlow(revision) : kind === "ue_flow" ? await client.confirmUeFlow(revision) : await client.confirmStage(stageId, revision);
    if (operationVersion !== reviewSyncVersion || client !== state.reviewClient) return;
    rebuildReviewWorkspace(model);
    state.reviewWorkspace = { ...state.reviewWorkspace, confirmStatus: "idle", confirmError: "" };
    if (kind === "flow") {
      navigateReviewWorkspace(nextView, { expectedUiVersion: actionUiVersion });
      return;
    }
    if (kind === "ue_flow") {
      navigateReviewWorkspace(nextView, { expectedUiVersion: actionUiVersion });
      await loadReviewPreview({ flushPending: false });
      return;
    }
    const nextStageId = ReviewWorkspace.nextUnconfirmedStageId(model, stageId);
    if (nextStageId) {
      state.reviewWorkspace = ReviewWorkspace.select(state.reviewWorkspace, { type: "stage", id: nextStageId, stageId: nextStageId });
      navigateReviewWorkspace(nextView, { expectedUiVersion: actionUiVersion });
      return;
    }
    if (actionUiVersion !== reviewUiInteractionVersion) return;
    navigateReviewWorkspace("interaction_preview", { expectedUiVersion: actionUiVersion });
    await loadReviewPreview({ flushPending: false });
  } catch (error) {
    if (client !== state.reviewClient || !state.reviewWorkspace) return;
    if (error.status === 409) {
      showReviewValidationError("审核版本已更新，请检查最新内容后重试。");
      await syncCanonicalReviewModel(client, "conflict_synced");
      return;
    }
    if (kind === "stage" && attemptedStageId) {
      try {
        const canonical = await client.load();
        if (client !== state.reviewClient || !state.reviewWorkspace) return;
        if (!canonical.reviewState?.flowConfirmed) {
          const prerequisiteMessage = "请先确认整体交互流程，再保存当前环节。";
          rebuildReviewWorkspace(canonical);
          state.reviewWorkspace = { ...state.reviewWorkspace, confirmStatus: "idle", confirmError: prerequisiteMessage };
          navigateReviewWorkspace("flow", { expectedUiVersion: actionUiVersion });
          showReviewValidationError(prerequisiteMessage);
          setStatus(prerequisiteMessage);
          return;
        }
        const confirmed = canonical.stages?.find((stage) => stage.id === attemptedStageId)?.confirmation?.confirmed;
        if (confirmed) {
          rebuildReviewWorkspace(canonical);
          state.reviewWorkspace = { ...state.reviewWorkspace, confirmStatus: "idle", confirmError: "" };
          const nextStageId = ReviewWorkspace.nextUnconfirmedStageId(canonical, attemptedStageId);
          if (nextStageId) {
            state.reviewWorkspace = ReviewWorkspace.select(state.reviewWorkspace, { type: "stage", id: nextStageId, stageId: nextStageId });
            navigateReviewWorkspace(nextView, { expectedUiVersion: actionUiVersion });
          } else {
            navigateReviewWorkspace("interaction_preview", { expectedUiVersion: actionUiVersion });
            await loadReviewPreview({ flushPending: false });
          }
          return;
        }
      } catch (_) {}
    }
    const missingObservedAction = kind === "stage"
      && error.status === 400
      && /stage evidence has no explicit observed action/i.test(error.message || "");
    const publicMessage = missingObservedAction
      ? "当前环节缺少已确认的玩家操作。请先通过决策卡选择操作，再确认当前环节。"
      : kind === "stage" && error.status === 400
        ? "当前环节尚未满足确认条件。请补全对应页面、玩家操作和系统反馈后重试；当前内容仍已保留。"
      : kind === "stage"
        ? "当前环节保存失败，内容仍已保留。请检查服务状态后重试。"
        : error.message;
    state.reviewWorkspace = { ...state.reviewWorkspace, saveStatus: previousSaveStatus, confirmStatus: "failed", confirmError: publicMessage };
    renderReviewWorkspace(state.reviewWorkspace.model);
    showReviewValidationError(publicMessage);
    setStatus(error.message);
  }
}

async function runReviewOperations(operations) {
  if (!state.reviewClient || !state.reviewWorkspace || !operations.length) return;
  const queue = state.reviewOperationQueue;
  if (!queue) return;
  const immediate = operations.some((operation) => ["set_region_bounds", "upsert_region", "move_stage"].includes(operation.type));
  operations.forEach((operation) => queue.push(operation, state.reviewWorkspace.model.revision, { immediate }));
}

async function runReferenceBoardMutation(boardKey, request, assetId = null) {
  const client = state.reviewClient;
  if (!client || !state.reviewWorkspace || boardKey !== "competitor" || typeof request !== "function" || state.reviewWorkspace.referenceBoardBusy) return;
  const retry = request;
  state.reviewWorkspace = { ...state.reviewWorkspace, referenceBoardBusy: true, referenceBoardStates: { ...(state.reviewWorkspace.referenceBoardStates || {}), [boardKey]: { status: "uploading", assetId, retry } } };
  renderReviewWorkspace(state.reviewWorkspace.model);
  renderCurrentFeishuPublication();
  try {
    if (state.reviewOperationQueue?.hasPending()) await state.reviewOperationQueue.flush(state.reviewWorkspace.model.revision);
    if (client !== state.reviewClient || !state.reviewWorkspace) return;
    const model = await request(state.reviewWorkspace.model.revision);
    if (client !== state.reviewClient) return;
    const referenceBoardStates = { ...(state.reviewWorkspace.referenceBoardStates || {}) };
    delete referenceBoardStates[boardKey];
    state.reviewWorkspace = { ...state.reviewWorkspace, referenceBoardBusy: false, referenceBoardStates };
    rebuildReviewWorkspace(model);
    renderCurrentFeishuPublication();
  } catch (error) {
    if (client !== state.reviewClient || !state.reviewWorkspace) return;
    if (error.status === 409) await syncCanonicalReviewModel(client, "conflict_synced");
    if (client !== state.reviewClient || !state.reviewWorkspace) return;
    state.reviewWorkspace = { ...state.reviewWorkspace, referenceBoardStates: { ...(state.reviewWorkspace.referenceBoardStates || {}), [boardKey]: { status: "failed", assetId, error: error.status === 409 ? "素材版本已更新，请重新选择后再试。" : error.message, retry } } };
    renderReviewWorkspace(state.reviewWorkspace.model);
    renderCurrentFeishuPublication();
    setStatus(error.message);
    throw error;
  } finally {
    if (client === state.reviewClient && state.reviewWorkspace?.referenceBoardBusy) {
      state.reviewWorkspace = { ...state.reviewWorkspace, referenceBoardBusy: false };
      renderReviewWorkspace(state.reviewWorkspace.model);
      renderCurrentFeishuPublication();
    }
  }
}

async function loadReviewPreview({ flushPending = true } = {}) {
  const client = state.reviewClient;
  const previewUiVersion = reviewUiInteractionVersion;
  if (!client || !state.reviewWorkspace) return;
  const mutationBlock = ReviewWorkspace.competitorMutationBlockMessage?.(state.reviewWorkspace);
  if (mutationBlock) {
    setStatus(mutationBlock);
    renderReviewWorkspace(state.reviewWorkspace.model);
    renderCurrentFeishuPublication();
    return;
  }
  let previewVersion = 0;
  let revision = null;
  try {
    if (flushPending && state.reviewOperationQueue?.hasPending()) await state.reviewOperationQueue.flush(state.reviewWorkspace.model.revision);
    if (client !== state.reviewClient || !state.reviewWorkspace) return;
    revision = state.reviewWorkspace.model.revision;
    previewVersion = ++reviewPreviewVersion;
    setReviewWorkspaceView("interaction_preview");
    state.reviewWorkspace = { ...state.reviewWorkspace, preview: null, previewStatus: "loading", previewError: "" };
    renderReviewWorkspace(state.reviewWorkspace.model);
    renderCurrentFeishuPublication();
    const preview = await client.preview(revision);
    if (client !== state.reviewClient || previewVersion !== reviewPreviewVersion || state.reviewWorkspace?.model?.revision !== revision) return;
    if (!preview?.exportReady || preview.revision !== revision || !preview.boardPreviewSvg) {
      const blockers = Array.isArray(preview?.blockerIds) && preview.blockerIds.length ? `：${preview.blockerIds.join("、")}` : "";
      throw new Error(`导出预览未就绪${blockers}`);
    }
    const model = {
      ...state.reviewWorkspace.model,
      reviewState: { ...state.reviewWorkspace.model.reviewState, status: "preview_ready", previewRevision: revision },
    };
    const explicitUrlView = requestedReviewViewFromUrl();
    const resolvedView = explicitUrlView && explicitUrlView !== "interaction_preview"
      ? explicitUrlView
      : previewUiVersion === reviewUiInteractionVersion ? "interaction_preview" : state.reviewWorkspace.view;
    state.reviewWorkspace = { ...state.reviewWorkspace, model, view: resolvedView, preview, previewStatus: "ready", previewError: "" };
    renderReviewWorkspace(model);
    if (resolvedView === "interaction_preview") syncReviewViewUrl(resolvedView);
    persistReviewUiState();
    renderCurrentFeishuPublication();
  } catch (error) {
    if (client !== state.reviewClient || previewVersion !== reviewPreviewVersion || state.reviewWorkspace?.model?.revision !== revision) return;
    state.reviewWorkspace = { ...state.reviewWorkspace, preview: null, previewStatus: "failed", previewError: error.message };
    renderReviewWorkspace(state.reviewWorkspace.model);
    renderCurrentFeishuPublication();
    setStatus(error.message);
  }
}

function bindReviewWorkspace() {
  document.querySelectorAll("[data-review-view]").forEach((button) => {
    button.onclick = async () => {
      reviewUiInteractionVersion += 1;
      const uiVersion = reviewUiInteractionVersion;
      const gameplayViewsRequiringModel = new Set(["gameplay", "diagrams", "tables", "final_preview"]);
      if (gameplayViewsRequiringModel.has(button.dataset.reviewView)
          && !gameplayModelReviewReady(state.gameplayReviewWorkspace?.model)) {
        setReviewWorkspaceView("gameplay_directory");
        renderReviewWorkspace(state.reviewWorkspace.model);
        syncReviewViewUrl("gameplay_directory");
        persistReviewUiState();
        setStatus("请先完成玩法详细规则生成，再继续规则、图解和参数审核。");
        return;
      }
      if (["preview", "interaction_preview"].includes(button.dataset.reviewView)) {
        if (state.reviewWorkspace?.previewStatus === "loading") return;
        if (state.reviewWorkspace?.preview?.boardPreviewSvg) {
          setReviewWorkspaceView("interaction_preview");
          renderReviewWorkspace(state.reviewWorkspace.model);
          syncReviewViewUrl("interaction_preview");
          persistReviewUiState();
          return;
        }
        syncReviewViewUrl("interaction_preview");
        return loadReviewPreview();
      }
      if (button.dataset.reviewView === "gameplay_directory" && gameplayModelNeedsGeneration(state.gameplayReviewWorkspace?.model)) {
        const embedded = state.reviewWorkspace?.model?.gameplayReviewModel;
        const client = state.gameplayReviewClient;
        const generationStatus = state.gameplayReviewGeneration?.status;
        if (gameplayModelNeedsGeneration(embedded) && generationStatus === "failed") {
          setReviewWorkspaceView("gameplay_directory");
          renderGameplayDirectoryWorkspace();
          syncReviewViewUrl("gameplay_directory");
          persistReviewUiState();
          return;
        }
        if (gameplayModelNeedsGeneration(embedded) && ["queued", "running", "generating"].includes(generationStatus)) {
          setReviewWorkspaceView("gameplay_directory");
          $("gameplayDirectoryView").textContent = "玩法目录正在生成，完成后会自动显示。";
          syncReviewViewUrl("gameplay_directory");
          persistReviewUiState();
          return;
        }
        try {
          $("gameplayDirectoryView").textContent = "正在加载玩法目录…";
          const gameplayModel = embedded || await client?.load?.();
          if (uiVersion !== reviewUiInteractionVersion || client !== state.gameplayReviewClient) return;
          if (!gameplayModel) throw new Error("当前任务暂时没有可用的玩法目录数据");
          rebuildGameplayReviewWorkspace(gameplayModel);
        } catch (error) {
          if (uiVersion !== reviewUiInteractionVersion || client !== state.gameplayReviewClient) return;
          $("gameplayDirectoryView").textContent = "玩法目录加载失败，请点击“玩法目录”重试。";
          setStatus(`玩法目录加载失败：${error.message}`);
          return;
        }
      }
      setReviewWorkspaceView(button.dataset.reviewView);
      renderReviewWorkspace(state.reviewWorkspace.model);
      syncReviewViewUrl(button.dataset.reviewView);
      persistReviewUiState(button.dataset.reviewView === "final_preview" ? { immediate: true } : {});
    };
  });
  $("reviewProjectDrawerToggle").onclick = () => {
    state.reviewWorkspace = { ...state.reviewWorkspace, projectDrawerOpen: !state.reviewWorkspace.projectDrawerOpen };
    renderReviewWorkspace(state.reviewWorkspace.model);
    persistReviewUiState();
  };
  $("reviewUndoBtn").onclick = () => ["gameplay_directory", "gameplay", "diagrams", "tables", "final_preview"].includes(state.reviewWorkspace?.view) ? runGameplayHistory("undo") : runReviewHistory("undo");
  $("reviewRedoBtn").onclick = () => ["gameplay_directory", "gameplay", "diagrams", "tables", "final_preview"].includes(state.reviewWorkspace?.view) ? runGameplayHistory("redo") : runReviewHistory("redo");
  $("analysisFailedConfigBtn").onclick = () => ensureVisionModelConfig();
  $("analysisFailedRetryBtn").onclick = () => retryBackendJob().catch((error) => setStatus(error.message));
  $("analysisFailedAssetsBtn").onclick = () => {
    document.body?.classList.remove("has-review");
    document.querySelector(".workspace")?.classList.remove("has-review");
    $("reviewWorkspace").hidden = true;
    document.querySelector(".analysis-area")?.scrollIntoView?.({ block: "start", behavior: "smooth" });
  };
  $("reviewConfirmFlowBtn").onclick = () => runReviewConfirmation("flow");
  $("reviewConfirmStageBtn").onclick = () => runReviewConfirmation("stage");
  if (typeof window !== "undefined") {
    if (!reviewPopstateHandler) {
      reviewPopstateHandler = () => {
        const linkedJobId = new URLSearchParams(location.search || "").get("job") || "";
        const currentJobId = state.reviewClient?.jobId || state.gameplayReviewClient?.jobId || "";
        if (!linkedJobId || (currentJobId && linkedJobId !== currentJobId)) {
          location.reload();
          return;
        }
        const requestedView = requestedReviewViewFromUrl();
        if (!requestedView || !state.reviewWorkspace?.model) {
          location.reload();
          return;
        }
        reviewUiInteractionVersion += 1;
        setReviewWorkspaceView(requestedView);
        const activeView = state.reviewWorkspace?.view || requestedView;
        renderReviewWorkspace(state.reviewWorkspace.model);
        if (activeView !== requestedView) syncReviewViewUrl(activeView, { replace: true });
        persistReviewUiState({ immediate: true });
      };
      window.addEventListener("popstate", reviewPopstateHandler);
    }
    window.onbeforeunload = () => state.reviewOperationQueue?.hasPending() ? "审核修改仍在保存，请留在此页面。" : undefined;
    if (!reviewPagehideHandler) {
      reviewPagehideHandler = () => {
        if (!state.reviewOperationQueue?.hasPending()) return;
        Promise.resolve(state.reviewOperationQueue.flushOnExit?.(state.reviewWorkspace?.model.revision)).catch(() => {});
        setStatus("审核修改正在后台保存。");
      };
      window.addEventListener?.("pagehide", reviewPagehideHandler);
    }
  }
}

async function syncBackendResult(job) {
  const reviewWorkspace = ReviewWorkspace.routeForJob(job) === "review_workspace";
  document.querySelector(".workspace")?.classList.add("has-job");
  document.querySelector(".workspace")?.classList.toggle("has-review", reviewWorkspace);
  document.body?.classList.toggle("has-review", reviewWorkspace);
  if (job.metadata?.mode) {
    $("projectType").value = job.metadata.mode;
    updateAnalysisMode();
  }
  if (job.metadata?.projectName) $("projectName").value = job.metadata.projectName;
  if (job.metadata?.scope) $("scope").value = job.metadata.scope;
  state.videoSummary = job.analysisSummary || null;
  state.frameFilter = state.analysisMode === "interaction" ? "scene_representatives" : "all";
  state.currentFrameIndex = 0;
  if (job.metadata?.inputType === "image_sequence") {
    state.screenshots = restoreScreenshotAssets(job);
    state.auxiliaryVideo = job.auxiliaryVideo ? {
      id: "V01", file: null, kind: "video", name: job.auxiliaryVideo.filename,
      url: job.auxiliaryVideo.sourceUrl ? `${BACKEND_BASE}${job.auxiliaryVideo.sourceUrl}` : "",
      width: 0, height: 0, duration: 0, readOnly: true,
    } : null;
    syncLegacyAssets();
    renderScreenshotInputs();
  }
  state.frames = (job.frames || []).map((source) => backendFrameToState(source, job));
  renderRawAnalysisRecords();
  state.sceneGroups = (job.scenes || []).map((scene) => ({
    sceneId: scene.id,
    label: scene.analysis?.title || `场景 ${scene.id + 1}`,
    sceneType: scene.analysis?.sceneType || "",
    summary: scene.analysis?.summary || "",
    eventSummary: stringifyFieldValue(scene.analysis?.stateChanges || ""),
    startTime: scene.start,
    endTime: scene.end,
    frames: state.frames.filter((frame) => frame.sceneGroup === scene.id)
  }));
  $("output").value = job.plan || "";
  $("copyBtn").disabled = !job.plan;
  $("downloadBtn").disabled = !job.plan;
  $("clearBtn").disabled = false;
  if (reviewWorkspace) {
    currentFeishuPublication = job.feishuPublication || {};
    if (state.reviewClient?.jobId !== job.id) {
      if (state.reviewOperationQueue?.hasPending()) {
        try { await state.reviewOperationQueue.flush(state.reviewWorkspace?.model.revision); }
        catch (_) { setStatus("当前审核修改未保存，已取消切换任务。"); return; }
      }
      state.reviewOperationQueue?.clear();
      state.reviewOperationQueue = null;
      clearReviewUiTimer();
      state.reviewWorkspace = null;
      reviewPreviewVersion += 1;
    }
    state.reviewClient = state.reviewClient?.jobId === job.id ? state.reviewClient : new ReviewClient(BACKEND_BASE, job.id);
    state.reviewOperationQueue ||= makeReviewOperationQueue(state.reviewClient);
    const rawRequestedView = requestedReviewViewFromUrl();
    const requestedView = recoverableReviewView(rawRequestedView, job.gameplayReviewModel);
    const restoredReviewUiState = {
      ...(job.reviewUiState || job.reviewModel?.reviewUiState || {}),
      ...(requestedView ? { view: requestedView } : {}),
    };
    const initialReviewModel = {
      ...job.reviewModel,
      reviewUiState: restoredReviewUiState,
      ...(job.gameplayReviewModel ? { gameplayReviewModel: job.gameplayReviewModel } : {}),
    };
    rebuildReviewWorkspace(initialReviewModel, "saved", true);
    // The job payload is the first authoritative state available on reload.
    // Re-apply it after both interaction and gameplay models are attached so
    // a late default route cannot flash P2 and overwrite a saved P7 view.
    if (restoredReviewUiState.view) {
      setReviewWorkspaceView(restoredReviewUiState.view);
      renderReviewWorkspace(initialReviewModel);
    }
    bindReviewWorkspace();
    if (requestedView && state.reviewWorkspace?.view !== rawRequestedView) syncReviewViewUrl(state.reviewWorkspace.view, { replace: true });
    const requestedViewUiVersion = reviewUiInteractionVersion;
    const restoreRequestedViewIfCurrent = ({ final = false } = {}) => {
      if (!requestedView || requestedViewUiVersion !== reviewUiInteractionVersion) return;
      if (final) reviewUiInteractionVersion += 1;
      setReviewWorkspaceView(requestedView);
      renderReviewWorkspace(state.reviewWorkspace.model);
      syncReviewViewUrl(state.reviewWorkspace.view, { replace: true });
    };
    const restoreRequestedViewAfterSync = async () => {
      await syncCanonicalReviewModel(state.reviewClient);
      restoreRequestedViewIfCurrent();
      if (state.gameplayReviewClient) await syncGameplayReviewModel(state.gameplayReviewClient);
      restoreRequestedViewIfCurrent({ final: true });
    };
    state.gameplayReviewGeneration = job.gameplayReviewGeneration || null;
    if (job.gameplayReviewModel && typeof GameplayReviewClient !== "undefined" && typeof GameplayWorkspace !== "undefined") {
      if (state.gameplayReviewClient?.jobId !== job.id) {
        state.gameplayOperationQueue?.clear?.();
        state.gameplayReviewClient = new GameplayReviewClient(BACKEND_BASE, job.id);
        state.gameplayReviewWorkspace = null;
      }
      state.gameplayOperationQueue ||= makeGameplayOperationQueue(state.gameplayReviewClient);
      state.gameplayReviewWorkspace ||= GameplayWorkspace.rebuild(
        job.gameplayReviewModel,
        "saved",
        gameplaySavedUiState(state.gameplayReviewClient),
      );
      if (restoredReviewUiState.view) {
        setReviewWorkspaceView(restoredReviewUiState.view);
        renderReviewWorkspace(state.reviewWorkspace.model);
      }
    }
    // Keep the first render non-blocking, then restore the explicit URL phase after
    // both canonical models settle. A slow network must not blank the workbench.
    void restoreRequestedViewAfterSync();
  } else {
    reviewSyncVersion += 1;
    reviewPreviewVersion += 1;
    currentFeishuPublication = job.feishuPublication || {};
    if (state.reviewOperationQueue?.hasPending()) {
      try { await state.reviewOperationQueue.flush(state.reviewWorkspace?.model.revision); }
      catch (_) { setStatus("当前审核修改未保存，已取消离开工作台。"); return; }
    }
    state.reviewClient = null;
    clearReviewUiTimer();
    state.reviewOperationQueue?.clear();
    state.reviewOperationQueue = null;
    state.gameplayOperationQueue?.clear?.();
    state.gameplayOperationQueue = null;
    state.gameplayReviewClient = null;
    state.gameplayReviewWorkspace = null;
    state.reviewWorkspace = null;
    $("reviewWorkspace").hidden = true;
    renderReviewProgress(job.reviewProgress);
    renderTimelineWorkbench(job);
    renderFrames();
  }
  renderCurrentFeishuPublication();
  renderStats();
  setProgress(100, "策划案生成完成");
  const modelStats = job.analysisSummary?.modelEnabled
    ? `模型调用约 ${job.analysisSummary.estimatedModelCalls || 0} 次 / 图像输入约 ${job.analysisSummary.estimatedImageInputs || 0} 张。`
    : "视觉模型未连接，本次只完成结构证据，语义项已标为待确认。";
  const completion = job.metadata?.inputType === "image_sequence"
    ? `已完成 <strong>${state.frames.length}</strong> 张截图分析`
    : `已完成 <strong>${formatTime(job.video?.duration || 0)}</strong> 视频分析`;
  setStatus(`${completion}：${state.sceneGroups.length} 个场景，${state.frames.length} 个关键画面。${modelStats}`);
}

function renderTimelineWorkbench(job) {
  const workbench = $("timelineWorkbench");
  if (job.metadata?.inputType === "image_sequence") {
    workbench.hidden = true;
    return;
  }
  const duration = Math.max(0.1, job.video?.duration || 0.1);
  workbench.hidden = false;
  const video = $("sourceVideo");
  video.src = `${BACKEND_BASE}${job.sourceUrl}`;
  $("timelineMeta").textContent = `${formatTime(duration)} · ${job.scenes?.length || 0} 场景 · ${job.frames?.length || 0} 证据 · 质量 ${job.qualityReport?.score ?? "-"}`;
  $("sceneTimeline").innerHTML = (job.scenes || []).map((scene, index) => {
    const left = scene.start / duration * 100;
    const width = Math.max(0.6, (scene.end - scene.start) / duration * 100);
    return `<button class="timeline-scene tone-${index % 6}" style="left:${left}%;width:${width}%" data-time="${scene.start}" title="${scene.analysis?.title || `场景 ${index + 1}`}">${index + 1}</button>`;
  }).join("");
  $("evidenceTimeline").innerHTML = (job.frames || []).map((frame) => `<button class="evidence-dot" style="left:${frame.timestamp / duration * 100}%" data-time="${frame.timestamp}" data-frame-id="${frame.id}" title="${frame.id} · ${formatTime(frame.timestamp)}"></button>`).join("");
  $("sceneSummaryList").innerHTML = (job.scenes || []).map((scene) => `<button class="scene-summary" data-time="${scene.start}"><b>${formatTime(scene.start)}–${formatTime(scene.end)} · ${scene.analysis?.title || `场景 ${scene.id + 1}`}</b><span>${scene.analysis?.summary || "待确认"}</span></button>`).join("");
  const review = job.reviewQueue || [];
  $("reviewQueue").innerHTML = review.length ? review.slice(0, 80).map((item) => `<button class="review-item priority-${item.priority}" data-time="${item.timestamp}" data-frame-id="${item.frameId}"><b>${item.title}</b><span>${formatTime(item.timestamp)} · ${item.frameId} · ${item.detail}</span></button>`).join("") : '<div class="notice">没有待审核问题。</div>';
}

function jumpToEvidence(timestamp, frameId = "") {
  const targetInAll = FrameReviewer.findFrameIndex(state.frames, frameId, timestamp);
  const targetFrame = FrameReviewer.sortFrames(state.frames)[targetInAll];
  if (targetFrame && !reviewableFrames().some((frame) => String(frame.id) === String(targetFrame.id))) state.frameFilter = "all";
  const frameIndex = FrameReviewer.findFrameIndex(reviewableFrames(), targetFrame?.id || frameId, timestamp);
  if (frameIndex >= 0) showFrameAt(frameIndex);
  const video = $("sourceVideo");
  if (video?.src) {
    video.currentTime = Math.max(0, Number(timestamp) || 0);
    video.play().catch(() => {});
  }
  const reviewer = document.querySelector(".frame-reviewer");
  reviewer?.scrollIntoView({ behavior: "smooth", block: "center" });
  reviewer?.classList.add("evidence-focus");
  setTimeout(() => reviewer?.classList.remove("evidence-focus"), 1400);
}

async function resumeBackendJob() {
  const contextVersion = jobContextVersion;
  const jobId = resumableJobId(
    location.search,
    localStorage.getItem("vpr_active_job"),
    localStorage.getItem("vpr_last_job"),
  );
  if (jobId && await backendAvailable()) {
    if (!isCurrentJobContext(contextVersion)) return;
    const response = await fetch(`${BACKEND_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
    if (!response.ok) return clearAll();
    const job = await response.json();
    if (!isCurrentJobContext(contextVersion)) return;
    if (job.status === "failed" && !job.reviewModel && requestedReviewViewFromUrl() === "analysis_failed") {
      lastFailedJobId = jobId;
      renderBackendFailure(job);
      openFailedJobWorkbench(job);
      activeJobId = "";
      return;
    }
    const action = resumeActionForJob(job);
    if (action === "clear") return clearAll();
    if (action === "sync") {
      activeJobId = jobId;
      await syncBackendResult(job);
      lastCompletedJobId = jobId;
      localStorage.setItem("vpr_last_job", jobId);
      localStorage.removeItem("vpr_active_job");
      activeJobId = "";
      lastFailedJobId = "";
      return;
    }
    activeJobId = jobId;
    await pollBackendJob(jobId);
  }
}

async function runGameplayHistory(action) {
  const client = state.gameplayReviewClient;
  if (!client || !state.gameplayReviewWorkspace) return;
  if (state.gameplayOperationQueue?.hasPending()) await state.gameplayOperationQueue.flush(state.gameplayReviewWorkspace.model.revision);
  const history = GameplayWorkspace.historyControls(state.gameplayReviewWorkspace.model);
  if ((action === "undo" && !history.canUndo) || (action === "redo" && !history.canRedo)) return;
  state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, saveStatus: "saving" };
  renderGameplayReviewWorkspace();
  try {
    rebuildGameplayReviewWorkspace(await client[action](state.gameplayReviewWorkspace.model.revision));
  } catch (error) {
    if (error.status === 409) return syncGameplayReviewModel(client, "conflict_synced");
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, saveStatus: "failed" };
    renderGameplayReviewWorkspace();
    setStatus(error.message);
  }
}

function renderRawAnalysisRecords() {
  const disclosure = $("rawAnalysisDisclosure");
  const root = $("rawAnalysisRecords");
  if (!disclosure || !root) return;
  disclosure.open = false;
  root.replaceChildren();
  const frames = state.frames || [];
  const intro = document.createElement("p");
  intro.textContent = frames.length ? `共 ${frames.length} 张原始画面记录。以下内容仅帮助追溯素材，不作为审核进度。` : "当前没有可追溯的原始画面记录。";
  root.append(intro);
  if (!frames.length) return;
  const list = document.createElement("ol");
  list.className = "raw-analysis-records";
  frames.forEach((frame, index) => {
    const item = document.createElement("li");
    const raw = frame.what || frame.gameMechanics || frame.systemResponse || frame.afterState || "";
    const fallback = "该画面尚未形成可用的中文策划结论，请以正式工作台中的已确认内容为准";
    const readable = StageReview.readableValue(raw, fallback);
    item.textContent = `第 ${index + 1} 张：${readable}`;
    list.append(item);
  });
  root.append(list);
}

function resumeActionForJob(job) {
  if (!job || job.archived) return "clear";
  return job.reviewModel && ["completed", "failed"].includes(job.status) ? "sync" : "poll";
}

function resumableJobId(search, activeJob, completedJob) {
  const params = new URLSearchParams(search || "");
  if (params.get("setup") === "1") return "";
  return params.get("job") || "";
}
