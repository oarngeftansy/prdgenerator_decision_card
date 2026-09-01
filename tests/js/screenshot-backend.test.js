const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ReviewWorkspace = require("../../js/review-workspace.js");
const ReviewClient = require("../../js/review-client.js");

function loadBackend(overrides = {}) {
  const elements = new Map();
  const values = {
    apiUrl: "https://example.com/v1", model: "vision", apiKey: "key",
    transcriptionApiUrl: "", transcriptionModel: "whisper-1", transcriptionApiKey: "",
    projectName: "截图任务", scope: "只看交互", standardSelect: "",
  };
  const context = {
    Intl,
    module: undefined,
    File,
    FormData,
    URLSearchParams,
    location: overrides.location || { hostname: "127.0.0.1", port: "8000", origin: "http://127.0.0.1:8000", protocol: "http:", search: "" },
    fetch: overrides.fetch,
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    state: { screenshots: [], auxiliaryVideo: null, assets: [], frames: [], sceneGroups: [], analysisMode: "interaction" },
    $: (id) => {
      if (!elements.has(id)) elements.set(id, { value: values[id] || "", disabled: false, classList: { add: () => {} } });
      return elements.get(id);
    },
    document: { querySelector: () => ({ classList: { add: () => {} } }) },
    rememberApiConfig: () => {}, setStatus: () => {}, setProgress: overrides.setProgress || (() => {}),
  };
  vm.runInNewContext(fs.readFileSync("js/screenshot-input.js", "utf8"), context);
  vm.runInNewContext(fs.readFileSync("js/backend.js", "utf8"), context);
  return context;
}

test("LAN deployment uses its own origin instead of the viewer's localhost", async () => {
  let requestedUrl = "";
  const context = loadBackend({
    location: { hostname: "192.168.50.67", port: "8020", origin: "http://192.168.50.67:8020", protocol: "http:", search: "" },
    fetch: async (url) => { requestedUrl = url; return { ok: true }; },
  });

  assert.equal(await context.backendAvailable(), true);
  assert.equal(requestedUrl, "http://192.168.50.67:8020/api/health");
});

test("root URL starts a new task while explicit job links still restore their workspace", () => {
  const context = loadBackend();

  assert.equal(context.resumableJobId("", "", "completed-job"), "");
  assert.equal(context.resumableJobId("?setup=1", "active-job", "completed-job"), "");
  assert.equal(context.resumableJobId("?job=linked-job", "active-job", "completed-job"), "linked-job");
  assert.equal(context.resumableJobId("", "active-job", "completed-job"), "");
  assert.equal(context.resumeActionForJob({ status: "completed", reviewModel: {} }), "sync");
  assert.equal(context.resumeActionForJob({ status: "failed", reviewModel: { revision: 45 } }), "sync");
  assert.equal(context.resumeActionForJob({ status: "processing" }), "poll");
  assert.equal(context.resumeActionForJob({ status: "completed", archived: true }), "clear");
});

test("delivery card exposes a dedicated workbench entry for the current task", () => {
  const html = fs.readFileSync("index.html", "utf8");
  assert.match(html, /id="enterWorkbenchBtn"[^>]*>进入工作台<\/button>/);

  const context = loadBackend();
  assert.equal(context.workbenchTargetJobId("?job=linked-job&ui=final_preview", "failed-job", "completed-job"), "linked-job");
  assert.equal(context.workbenchTargetJobId("", "failed-job", "completed-job"), "failed-job");
  assert.equal(context.workbenchTargetJobId("", "", "completed-job"), "completed-job");
});

test("local final preview keeps the actual project name", () => {
  const context = loadBackend();
  context.$("projectName").value = "一路狂飙交互与玩法策划案";
  const preview = context.localConfirmedFinalPreview(
    { model: { revision: 2, chapters: [{ id: "C1", scope: "核心战斗", confirmation: { confirmed: true } }] } },
    { revision: 1, stages: [{ id: "S1", confirmation: { confirmed: true } }] },
  );
  assert.equal(preview.documentTitle, "一路狂飙交互与玩法策划案");
});

test("screenshot analysis refuses to start without a configured visual model", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /extractWithIntegratedBackend[\s\S]*if \(!hasVisionModelConfig\(\)\)[\s\S]*ensureVisionModelConfig\(\)[\s\S]*return true/);
  assert.match(backend, /请先配置视觉模型，再开始分析/);
});

test("late task restoration cannot overwrite a P1–P7 page the planner already selected", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /reviewUiInteractionVersion/);
  assert.match(backend, /rebuildReviewWorkspace\(model, saveStatus, uiVersion === reviewUiInteractionVersion\)/);
  assert.match(backend, /selectedViewDuringSync[\s\S]*setReviewWorkspaceView\(selectedViewDuringSync\)/);
});

test("gameplay model refresh preserves the review page selected by the planner", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("function rebuildGameplayReviewWorkspace"), backend.indexOf("function advanceToCurrentReviewRoute"));
  assert.match(section, /const selectedReviewView = state\.reviewWorkspace\?\.view/);
  assert.match(section, /setReviewWorkspaceView\(selectedReviewView\)/);
});

test("structure-only gameplay chapters cannot unlock rule or diagram review", () => {
  const context = loadBackend();
  assert.equal(typeof context.gameplayModelReviewReady, "function");
  const pending = {
    contentState: "pending",
    reviewState: { status: "detail_generation_pending", structurePhase: "confirmed" },
    chapters: [{ id: "GCH-001" }],
  };
  const ready = {
    contentState: "ready",
    reviewState: { status: "chapter_review", structurePhase: "detailed" },
    chapters: [{ id: "GCH-001" }],
  };
  assert.equal(context.gameplayModelReviewReady(pending), false);
  assert.equal(context.gameplayModelReviewReady(ready), true);
  assert.equal(context.gameplayModelReviewReady({ ...ready, detailQuality: { passed: false, errors: ["FLOW_CHAIN_INVALID"] } }), false);
  assert.equal(context.gameplayModelReviewReady({
    ...ready,
    reviewState: { ...ready.reviewState, structureQualityErrors: ["界面名称被当成机制：收购信息面板"] },
  }), false);
  assert.equal(context.recoverableReviewView("gameplay", pending), "gameplay_directory");
  assert.equal(context.recoverableReviewView("diagrams", pending), "gameplay_directory");
});

test("diagram review never leaves a blank panel while its gameplay model is unavailable", () => {
  const context = loadReviewBackend(() => ({}));
  context.state.gameplayReviewWorkspace = null;
  context.renderGameplayDiagramWorkspace();
  assert.match(context.$("gameplayDiagramView").textContent, /正在加载|返回玩法目录/);
});

test("P4 edit rules atomically opens the supplemental container and rule editor", () => {
  const context = loadReviewBackend(() => ({}));
  context.state.gameplayReviewWorkspace = {
    model: { revision: 3, chapters: [{ id: "GCH-001" }] },
    selectedChapterId: "GCH-001",
    expandedGroups: [],
  };
  let clicked = false;
  context.GameplayReview = { render(args) { if (!clicked) { clicked = true; args.onEditRules("GCH-001"); } } };

  context.renderGameplayReviewWorkspace();

  assert.deepEqual(Array.from(context.state.gameplayReviewWorkspace.expandedGroups), [
    "GCH-001:supplemental",
    "GCH-001:rules",
  ]);
});

test("canonical workbench hides the legacy frame reviewer and legacy export panel", () => {
  const css = fs.readFileSync("css/review-workspace.css", "utf8");
  assert.match(css, /\.workspace\.has-review \.analysis-area\s*\{\s*display:\s*none/);
});

test("canonical workbench exposes raw analysis only through a collapsed planner-safe disclosure", () => {
  const html = fs.readFileSync("index.html", "utf8");
  assert.match(html, /<details[^>]+id="rawAnalysisDisclosure"[^>]*>/);
  assert.match(html, /<summary>查看原始分析记录<\/summary>/);
  assert.doesNotMatch(html, /<details[^>]+id="rawAnalysisDisclosure"[^>]+open/);
  assert.match(html, /原始分析只用于追溯，不参与最终导出/);
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /StageReview\.readableValue/);
});

test("processing jobs show received screenshots instead of a false 0/0 review", () => {
  const context = loadBackend();
  context.renderBackendProcessing({ stage: "事件链分析 6/15", frames: Array.from({ length: 15 }) });

  assert.equal(context.$("reviewProgress").textContent, "素材已接收：15/15 · 事件链分析 6/15");
  assert.match(context.$("frameList").innerHTML, /分析完成后自动进入交互审核/);
});

test("failed analysis preserves screenshot count and failure progress", () => {
  const progress = [];
  const context = loadBackend({ setProgress: (...args) => progress.push(args) });
  context.renderBackendFailure({ progress: 92, frames: Array.from({ length: 15 }), error: "视觉模型未产出合格交互分析：5/15 个代表帧达标" });

  assert.equal(context.$("reviewProgress").textContent, "分析未通过 · 已保留 15 张素材");
  assert.match(context.$("frameList").innerHTML, /无需重新上传/);
  assert.deepEqual(progress.at(-1), [33, "视觉分析 5/15"]);
});

test("failed analysis progress reflects qualified screenshots instead of stale pipeline progress", () => {
  const progress = [];
  const context = loadBackend({ setProgress: (...args) => progress.push(args) });
  context.renderBackendFailure({
    progress: 92,
    frames: Array.from({ length: 18 }),
    analysisSummary: { qualifiedDetailFrameCount: 7, detailFrameCount: 18 },
    error: "视觉模型未产出合格交互分析：7/18 个代表帧达标",
  });

  assert.deepEqual(progress.at(-1), [39, "视觉分析 7/18"]);
});

test("legacy failed jobs derive the real quality rate from their error instead of showing 92 percent", () => {
  const progress = [];
  const context = loadBackend({ setProgress: (...args) => progress.push(args) });
  context.renderBackendFailure({
    progress: 92,
    frames: Array.from({ length: 18 }),
    error: "视觉模型未产出合格交互分析：0/18 个代表帧达标",
  });

  assert.deepEqual(progress.at(-1), [0, "视觉分析 0/18"]);
});

test("retry targets the failed upload instead of an older completed task", () => {
  const context = loadBackend();
  assert.equal(context.retryTargetJobId("", "new-failed-job", "older-completed-job"), "new-failed-job");
});

test("retry opens model settings instead of silently running without an API key", async () => {
  let requests = 0;
  const statuses = [];
  const context = loadBackend({
    fetch: async () => { requests += 1; return { ok: true, json: async () => ({}) }; },
  });
  context.setStatus = (message) => statuses.push(message);
  context.document.querySelector = () => ({ classList: { add: () => {}, remove: () => {} } });
  context.document.body = { classList: { remove: () => {} } };
  context.$("apiConfigPanel").scrollIntoView = () => {};
  context.$("apiKey").focus = () => {};
  context.$("apiKey").value = "";
  context.renderBackendFailure({ id: "failed-job", frames: Array.from({ length: 18 }), error: "analysis failed" });

  await context.retryBackendJob();

  assert.equal(requests, 0);
  assert.equal(context.$("apiConfigPanel").open, true);
  assert.match(statuses.at(-1), /API/);
});

test("an active upload blocks duplicate task creation", () => {
  const context = loadBackend();
  assert.equal(context.canStartNewJob("already-processing"), false);
  assert.equal(context.canStartNewJob(""), true);
});

test("new local evidence detaches an older case before analysis can restore it", () => {
  const context = loadBackend();
  context.state.reviewWorkspace = { model: { jobId: "old-case" } };
  context.state.reviewClient = { jobId: "old-case" };
  context.state.gameplayReviewClient = { jobId: "old-case" };

  context.detachJobForNewEvidence();

  assert.equal(context.state.reviewWorkspace, null);
  assert.equal(context.state.reviewClient, null);
  assert.equal(context.state.gameplayReviewClient, null);
  assert.equal(context.isCurrentJobContext(0), false);
});

test("a poll response from an older task cannot replace the new upload", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const poll = backend.slice(backend.indexOf("async function pollBackendJob"), backend.indexOf("function renderBackendProcessing"));
  assert.match(poll, /if \(jobId !== activeJobId\) return/);
});

function asset(id, name, type = "image/png") {
  return { id, name, kind: type.startsWith("video") ? "video" : "image", file: new File([name], name, { type }) };
}

function reviewClassList() {
  const names = new Set();
  return { add: (...items) => items.forEach((item) => names.add(item)), remove: (...items) => items.forEach((item) => names.delete(item)), toggle: (item, value) => value ? names.add(item) : names.delete(item), contains: (item) => names.has(item) };
}

function loadReviewBackend(createClient) {
  const elements = new Map();
  const timers = new Set();
  const publicationRenders = [];
  const previewRenders = [];
  const previewRenderArgs = [];
  const referenceBoardRenders = [];
  const statuses = [];
  const workspace = { classList: reviewClassList() };
  const pagehideHandlers = [];
  const reviewButtons = [];
  const context = {
    Intl, module: undefined, File, FormData, URLSearchParams, ReviewWorkspace,
    location: { hostname: "127.0.0.1", port: "8000", origin: "http://127.0.0.1:8000", search: "" },
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    state: { screenshots: [], auxiliaryVideo: null, assets: [], frames: [], sceneGroups: [], analysisMode: "interaction", reviewWorkspace: null, reviewClient: null },
    ReviewClient: function ReviewClient() { return createClient(); },
    ExportPreview: {
      render(args) { previewRenders.push(args.preview); previewRenderArgs.push(args); args.root.textContent = args.preview.boardPreviewSvg; },
      combinedViewModel(preview, models) { return { ...preview, exportDisabled: !preview.exportReady || preview.interactionRevision !== models.interaction.revision || preview.gameplayRevision !== models.gameplay.revision }; },
      autoCompletionView(value) { return { busy: ["queued", "running"].includes(value?.status), progress: value?.progress || 0, message: "正在自动补全已确认的玩法章节", detail: "保留已确认结论" }; },
    },
    FinalDocumentPreview: { render(args) { args.root.textContent = args.preview.documentTitle || "完整策划案"; } },
    ReferenceBoardAssets: { render(args) { referenceBoardRenders.push(args); args.root.textContent = args.states?.competitor?.status === "failed" ? "素材保存失败，请重试" : ""; } },
    $: (id) => {
      if (!elements.has(id)) elements.set(id, { value: "", textContent: "", disabled: false, hidden: false, children: [], classList: reviewClassList(), attrs: {}, append(...items) { this.children.push(...items); }, replaceChildren(...items) { this.children = [...items]; }, setAttribute(name, value) { this.attrs[name] = value; } });
      return elements.get(id);
    },
    document: {
      querySelector: () => workspace,
      querySelectorAll: (selector) => selector === "[data-review-view]" ? reviewButtons : [],
      createElement: () => ({ children: [], textContent: "", disabled: false, className: "", style: {}, attrs: {}, append(...items) { this.children.push(...items); }, replaceChildren(...items) { this.children = [...items]; }, setAttribute(name, value) { this.attrs[name] = value; } }),
    },
    window: { confirm: () => false, addEventListener(type, handler) { if (type === "pagehide") pagehideHandlers.push(handler); }, removeEventListener(type, handler) { if (type === "pagehide") { const index = pagehideHandlers.indexOf(handler); if (index >= 0) pagehideHandlers.splice(index, 1); } } },
    setTimeout: (callback) => { timers.add(callback); return callback; },
    clearTimeout: (callback) => timers.delete(callback),
    rememberApiConfig: () => {}, setStatus: (message) => statuses.push(message), setProgress: () => {}, updateAnalysisMode: () => {}, formatTime: () => "0:00",
    renderFeishuPublicationState: (publication, canPublish) => {
      if (context.state.reviewWorkspace?.model) {
        const preview = context.state.reviewWorkspace.preview;
        canPublish = Boolean(preview?.exportReady) && preview.revision === context.state.reviewWorkspace.model.revision;
      }
      publicationRenders.push({ publication, canPublish });
    }, renderStats: () => {}, syncLegacyAssets: () => {}, renderScreenshotInputs: () => {},
  };
  vm.runInNewContext(fs.readFileSync("js/screenshot-input.js", "utf8"), context);
  vm.runInNewContext(fs.readFileSync("js/backend.js", "utf8"), context);
  context.flushTimers = () => {
    const ready = [...timers];
    timers.clear();
    ready.forEach((callback) => callback());
  };
  context.publicationRenders = publicationRenders;
  context.previewRenders = previewRenders;
  context.previewRenderArgs = previewRenderArgs;
  context.pendingTimers = timers;
  context.referenceBoardRenders = referenceBoardRenders;
  context.statuses = statuses;
  context.pagehideHandlers = pagehideHandlers;
  context.reviewButtons = reviewButtons;
  context.workspace = workspace;
  return context;
}

function reviewJob(model) {
  return { id: "job-review", status: "completed", plan: "# plan", reviewModel: model, metadata: { mode: "interaction", inputType: "video" }, frames: [], scenes: [], analysisSummary: {} };
}

test("job form data appends screenshots in confirmed order", () => {
  const context = loadBackend();
  context.state.screenshots = [asset("B", "2.png"), asset("A", "10.png")];
  context.state.auxiliaryVideo = asset("V", "helper.mp4", "video/mp4");

  const data = context.buildJobFormData();

  assert.deepEqual(data.getAll("images").map((file) => file.name), ["2.png", "10.png"]);
  assert.deepEqual(JSON.parse(data.get("image_manifest")).map((item) => item.order), [1, 2]);
  assert.equal(data.get("video").name, "helper.mp4");
  assert.equal(data.get("mode"), "interaction");
});

test("history restoration preserves screenshot names and server order", () => {
  const context = loadBackend();
  const restored = context.restoreScreenshotAssets({
    id: "job-1",
    metadata: { inputType: "image_sequence" },
    frames: [
      { id: "F0002", sourceName: "second.png", sequenceIndex: 2, imageUrl: "/artifacts/job-1/frames/F0002.jpg" },
      { id: "F0001", sourceName: "first.png", sequenceIndex: 1, imageUrl: "/artifacts/job-1/frames/F0001.jpg" },
    ],
  });

  assert.deepEqual(Array.from(restored, (item) => item.name), ["first.png", "second.png"]);
  assert.equal(restored[0].file, null);
  assert.equal(restored[0].url, "http://127.0.0.1:8000/artifacts/job-1/frames/F0001.jpg");
  assert.equal(restored[0].readOnly, true);
});

test("workspace reconciles its initial job model with the canonical client model", async () => {
  const client = { loads: 0, load() { this.loads += 1; return Promise.resolve({ revision: 2, stages: [{ id: "STG-002" }], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }); } };
  const context = loadReviewBackend(() => client);
  context.syncBackendResult(reviewJob({ revision: 1, stages: [{ id: "STG-001" }], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }));
  await new Promise(setImmediate);
  assert.equal(client.loads, 1);
  assert.equal(context.state.reviewWorkspace.model.revision, 2);
  assert.equal(context.state.reviewWorkspace.selectedStageId, "STG-002");
});

test("canonical interaction refresh preserves a generated gameplay directory", async () => {
  const canonicalInteraction = {
    revision: 18, stages: [], reviewState: { status: "preview_ready", previewRevision: 18 },
    quality: { qualified: true }, editHistory: { undo: [], redo: [] },
  };
  const gameplay = {
    revision: 1, chapters: [{ id: "GCH-001", confirmation: { confirmed: false } }],
    directory: { status: "draft", entries: [{ id: "GDE-001", chapterId: "GCH-001" }] },
    reviewState: { interactionHandoffConfirmed: false }, diagrams: [],
  };
  const client = { load: async () => ({ ...canonicalInteraction }) };
  const context = loadReviewBackend(() => client);
  const job = { ...reviewJob(canonicalInteraction), gameplayReviewModel: gameplay, gameplayReviewGeneration: { status: "completed", progress: 100 } };

  await context.syncBackendResult(job);
  await new Promise(setImmediate);

  assert.equal(context.state.reviewWorkspace.model.gameplayReviewModel, gameplay);
  assert.equal(context.state.reviewWorkspace.view, "gameplay_directory");
});

test("initial review render does not enable publish from plan text when preview is stale", () => {
  const client = { load() { return new Promise(() => {}); } };
  const context = loadReviewBackend(() => client);
  context.syncBackendResult(reviewJob({ revision: 4, stages: [], reviewState: { status: "preview_ready", previewRevision: 3 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }));

  assert.equal(context.publicationRenders.at(-1).canPublish, false);
});

test("semantic interaction preview aliases the existing export preview and loads through its button", async () => {
  const client = { previewCalls: 0, load() { return new Promise(() => {}); }, preview() { this.previewCalls += 1; return Promise.resolve({ revision: 4, exportReady: true, boardPreviewSvg: "<svg />" }); } };
  const context = loadReviewBackend(() => client);
  const button = { dataset: { reviewView: "interaction_preview" }, disabled: false, setAttribute() {} };
  context.reviewButtons.push(button);
  const model = { revision: 4, stages: [], reviewState: { flowConfirmed: true, ueFlowConfirmed: true }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  context.state.reviewClient = client;
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(model), view: "interaction_preview" };
  context.renderReviewWorkspace(model);
  context.bindReviewWorkspace();
  button.onclick();
  await new Promise(setImmediate);
  assert.equal(client.previewCalls, 1);
  assert.equal(context.state.reviewWorkspace.view, "interaction_preview");
  assert.equal(context.$("exportPreviewView").hidden, false);
});

test("gameplay placeholders only switch when their ordered route is reachable", () => {
  const client = { load() { return new Promise(() => {}); } };
  const context = loadReviewBackend(() => client);
  const button = { dataset: { reviewView: "gameplay" }, disabled: false, setAttribute() {} };
  context.reviewButtons.push(button);
  const model = { revision: 2, stages: [], reviewState: { status: "preview_ready", previewRevision: 2 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] }, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: false } }], diagrams: [] } };
  context.syncBackendResult(reviewJob(model));
  context.bindReviewWorkspace();
  assert.equal(button.disabled, false);
  context.setReviewWorkspaceView("gameplay");
  assert.equal(context.$("gameplayReviewView").hidden, false);
  assert.equal(context.$("gameplayDiagramView").hidden, true);
  assert.equal(context.$("finalExportPreviewView").hidden, true);

  const diagramsModel = { ...model, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [{ status: "open" }] } };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(diagramsModel), view: "diagrams" };
  context.renderReviewWorkspace(diagramsModel);
  assert.equal(context.$("gameplayDiagramView").hidden, false);

  const finalModel = { ...model, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [{ status: "reviewed" }], diagramReview: { status: "ready" }, tables: [], tableReview: { status: "ready" } } };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(finalModel), view: "final_preview" };
  context.renderReviewWorkspace(finalModel);
  assert.equal(context.$("finalExportPreviewView").hidden, false);
});

test("switching back to gameplay directory renders its content instead of a blank panel", () => {
  const client = { load() { return new Promise(() => {}); } };
  const context = loadReviewBackend(() => client);
  const button = { dataset: { reviewView: "gameplay_directory" }, disabled: false, setAttribute() {} };
  context.reviewButtons.push(button);
  const gameplay = { revision: 3, directory: { entries: [] }, chapters: [] };
  const model = { revision: 2, stages: [], reviewState: { status: "preview_ready", previewRevision: 2 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] }, gameplayReviewModel: gameplay };
  context.GameplayDirectory = { render({ root }) { root.textContent = "玩法目录已渲染"; } };
  context.syncBackendResult(reviewJob(model));
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.bindReviewWorkspace();

  button.onclick();

  assert.equal(context.$("gameplayDirectoryView").textContent, "玩法目录已渲染");
});

test("switching to gameplay directory hydrates a missing stale-session model", async () => {
  const gameplay = { revision: 7, directory: { entries: [] }, chapters: [] };
  let loads = 0;
  const client = { load: async () => { loads += 1; return gameplay; } };
  const context = loadReviewBackend(() => client);
  const button = { dataset: { reviewView: "gameplay_directory" }, disabled: false, setAttribute() {} };
  context.reviewButtons.push(button);
  const interaction = { revision: 4, stages: [], reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayDirectory = { render({ root }) { root.textContent = "玩法目录恢复完成"; } };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(interaction), model: interaction, view: "flow" };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = null;
  context.bindReviewWorkspace();

  await button.onclick();

  assert.equal(loads, 1);
  assert.equal(context.state.reviewWorkspace.view, "gameplay_directory");
  assert.equal(context.$("gameplayDirectoryView").textContent, "玩法目录恢复完成");
});

test("switching to gameplay directory without a recoverable model shows retry guidance", async () => {
  const context = loadReviewBackend(() => ({ load: async () => null }));
  const button = { dataset: { reviewView: "gameplay_directory" }, disabled: false, setAttribute() {} };
  context.reviewButtons.push(button);
  const interaction = { revision: 4, stages: [], reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(interaction), model: interaction, view: "flow" };
  context.state.gameplayReviewClient = null;
  context.state.gameplayReviewWorkspace = null;
  context.bindReviewWorkspace();

  await button.onclick();

  assert.match(context.$("gameplayDirectoryView").textContent, /加载失败.*重试/);
  assert.doesNotMatch(context.$("gameplayDirectoryView").textContent, /正在加载/);
});

test("failed initial gameplay generation shows recovery without loading or silently retrying", async () => {
  let loads = 0;
  let generations = 0;
  const gameplayClient = {
    jobId: "job-failed-initial-structure",
    load: async () => { loads += 1; throw new Error("missing model"); },
    generate: async () => { generations += 1; return { status: "queued" }; },
  };
  const context = loadReviewBackend(() => ({}));
  const button = { dataset: { reviewView: "gameplay_directory" }, disabled: false, setAttribute() {} };
  context.reviewButtons.push(button);
  const interaction = { revision: 4, stages: [], reviewState: { status: "stage_review" }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  context.$("apiKey").value = "configured-key";
  context.state.reviewClient = { jobId: "job-failed-initial-structure" };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(interaction), model: interaction, view: "flow" };
  context.state.gameplayReviewClient = gameplayClient;
  context.state.gameplayReviewWorkspace = null;
  context.state.gameplayReviewGeneration = { status: "failed", progress: 0, error: "玩法章节生成失败" };
  context.bindReviewWorkspace();

  await button.onclick();

  assert.equal(loads, 0);
  assert.equal(generations, 0);
  assert.equal(context.state.reviewWorkspace.view, "gameplay_directory");
});

test("diagram controller exposes local pending success error and conflict states", async () => {
  const client = { load: async () => ({ revision: 9, chapters: [], diagrams: [] }) };
  const context = loadReviewBackend(() => client);
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  const renders = [];
  context.GameplayDiagrams = { render: (args) => renders.push(args) };
  context.state.gameplayReviewWorkspace = { model: { revision: 8, chapters: [], diagrams: [{ id: "GDI-001" }] }, diagramRequestState: { generation: {}, byId: {} } };
  context.state.gameplayReviewClient = client;

  let resolveGenerate; let generateCalls = 0;
  client.diagrams = () => { generateCalls += 1; return new Promise((resolve) => { resolveGenerate = resolve; }); };
  const pending = context.runGameplayDiagramGeneration();
  context.runGameplayDiagramGeneration();
  assert.equal(generateCalls, 1);
  assert.equal(context.state.gameplayReviewWorkspace.diagramRequestState.generation.status, "pending");
  resolveGenerate({ revision: 9, chapters: [], diagrams: [{ id: "GDI-001" }] });
  await pending;
  assert.equal(context.state.gameplayReviewWorkspace.diagramRequestState.generation.status, "success");

  client.regenerateDiagram = async () => { const error = new Error("network"); error.status = 500; throw error; };
  await context.runGameplayDiagramAction("regenerate", "GDI-001", "重画");
  assert.equal(context.state.gameplayReviewWorkspace.diagramRequestState.byId["GDI-001"].status, "error");

  client.approveDiagram = async () => { const error = new Error("conflict"); error.status = 409; throw error; };
  await context.runGameplayDiagramAction("approve", "GDI-001", "");
  assert.equal(context.state.gameplayReviewWorkspace.diagramRequestState.byId["GDI-001"].status, "conflict");
  client.deleteDiagram = async () => ({ revision: 10, chapters: [], diagrams: [{ id: "GDI-001", status: "deleted", optional: true }] });
  await context.runGameplayDiagramAction("delete", "GDI-001", "");
  assert.equal(context.state.gameplayReviewWorkspace.diagramRequestState.announcement.status, "success");
  assert.match(context.state.gameplayReviewWorkspace.diagramRequestState.announcement.message, /已删除/);
  assert.ok(renders.length > 0);
});

test("gameplay confirmation shows feedback and advances to the next pending chapter", async () => {
  const chapters = [
    { id: "GCH-001", scope: "核心战斗", confirmation: { confirmed: true } },
    { id: "GCH-002", scope: "强化选择", confirmation: { confirmed: false } },
    { id: "GCH-003", scope: "首领战", confirmation: { confirmed: false } },
  ];
  const confirmed = chapters.map((item) => item.id === "GCH-002" ? { ...item, confirmation: { confirmed: true }, status: "approved" } : item);
  const client = { confirmChapter: async () => ({ revision: 2, chapters: confirmed, diagrams: [], reviewState: {} }) };
  const context = loadReviewBackend(() => client);
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayReview = { ...require("../../js/gameplay-review.js"), render() {} };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = { model: { revision: 1, chapters, diagrams: [], reviewState: {} }, selectedChapterId: "GCH-002" };
  context.state.gameplayOperationQueue = { hasPending: () => false };

  await context.runGameplayConfirmation("GCH-002", "approved");

  assert.equal(context.state.gameplayReviewWorkspace.selectedChapterId, "GCH-003");
  assert.equal(context.state.gameplayReviewWorkspace.confirmationStatus, "saved");
  assert.match(context.state.gameplayReviewWorkspace.confirmationMessage, /接下来检查“首领战”/);
});

test("ambiguous gameplay chapter failure reconciles a server-side approval", async () => {
  const chapters = [
    { id: "GCH-001", scope: "核心战斗", status: "unreviewed", confirmation: { confirmed: false } },
    { id: "GCH-002", scope: "结算", status: "unreviewed", confirmation: { confirmed: false } },
  ];
  const canonical = {
    revision: 2,
    chapters: chapters.map((item) => item.id === "GCH-001" ? { ...item, status: "approved", confirmation: { confirmed: true, revision: 2 } } : item),
    diagrams: [], tables: [], reviewState: {},
  };
  const client = {
    confirmChapter: async () => { throw new Error("连接在响应返回前中断"); },
    load: async () => canonical,
  };
  const context = loadReviewBackend(() => client);
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayReview = { ...require("../../js/gameplay-review.js"), render() {} };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = { model: { revision: 1, chapters, diagrams: [], tables: [], reviewState: {} }, selectedChapterId: "GCH-001" };
  context.state.gameplayOperationQueue = { hasPending: () => false };

  await context.runGameplayConfirmation("GCH-001", "approved");

  assert.equal(context.state.gameplayReviewWorkspace.model.revision, 2);
  assert.equal(context.state.gameplayReviewWorkspace.model.chapters[0].confirmation.confirmed, true);
  assert.equal(context.state.gameplayReviewWorkspace.confirmationStatus, "saved");
  assert.equal(context.state.gameplayReviewWorkspace.selectedChapterId, "GCH-002");
});

test("existing gameplay workspaces keep every P4-P7 page inspectable while completion stays gated", () => {
  const context = loadReviewBackend(() => ({ load() { return new Promise(() => {}); } }));
  const buttons = ["gameplay", "diagrams", "tables", "final_preview"].map((reviewView) => ({
    dataset: { reviewView }, disabled: false, setAttribute() {},
  }));
  context.reviewButtons.push(...buttons);
  const interaction = {
    revision: 45,
    stages: [{ confirmation: { confirmed: true } }],
    reviewState: { flowConfirmed: true, status: "preview_ready", previewRevision: 45 },
    quality: { qualified: true },
    editHistory: { undo: [], redo: [] },
  };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(interaction), model: interaction };
  context.state.gameplayReviewWorkspace = {
    model: {
      revision: 358,
      directory: { status: "confirmed" },
      chapters: [{ confirmation: { confirmed: false } }],
      diagrams: [{ status: "open" }],
      tables: [{ status: "open" }],
    },
  };

  context.renderReviewWorkspace(interaction);

  assert.deepEqual(buttons.map((button) => button.disabled), [false, false, false, false]);
});

test("switching P1–P7 pages resets the shared canvas instead of inheriting the previous page scroll", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const body = backend.slice(backend.indexOf("function setReviewWorkspaceView"), backend.indexOf("function renderReviewProjectDrawer"));
  assert.match(body, /previousView/);
  assert.match(body, /reviewCanvas/);
  assert.match(body, /scrollTo\?\.\(\{ top: 0, left: 0/);
  assert.match(body, /window\.scrollTo\?\./);
  assert.match(body, /document\.documentElement\.scrollLeft = 0/);
  assert.match(body, /document\.body\.scrollLeft = 0/);
});

test("confirming the final gameplay directory opens interaction review before its preview", async () => {
  const gameplay = { revision: 2, directory: { status: "draft", entries: [] }, chapters: [], reviewState: { interactionHandoffConfirmed: true } };
  const confirmed = { ...gameplay, revision: 3, directory: { status: "confirmed", entries: [] } };
  const confirmCalls = [];
  const client = { confirmDirectory: async (...args) => { confirmCalls.push(args); return confirmed; } };
  const context = loadReviewBackend(() => client); let rendered;
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayDirectory = { render(args) { rendered = args; } };
  context.state.gameplayReviewClient = client; context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({
    revision: 4,
    stages: [{ id: "STG-001", confirmation: { confirmed: true } }],
    reviewState: { flowConfirmed: true, previewRevision: 4, status: "preview_ready" },
    quality: { qualified: true },
    gameplayReviewModel: gameplay,
  }), view: "gameplay_directory" };
  context.state.gameplayOperationQueue = { flush: async () => {} };
  context.$("apiUrl").value = "https://vision.example/v1";
  context.$("model").value = "vision-pro";
  context.$("apiKey").value = "secret";
  context.renderGameplayDirectoryWorkspace();

  await rendered.onConfirm();

  assert.equal(context.state.reviewWorkspace.view, "flow");
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const confirmHandler = backend.slice(
    backend.indexOf("onConfirm: async (pendingOperations = [])"),
    backend.indexOf("function renderGameplayDiagramWorkspace"),
  );
  assert.match(confirmHandler, /reviewUiInteractionVersion \+= 1/);
  assert.match(confirmHandler, /syncReviewViewUrl\("flow"\)/);
  assert.equal(confirmCalls[0][0], 2);
  assert.equal(confirmCalls[0][1].apiBase, "https://vision.example/v1");
  assert.equal(confirmCalls[0][1].model, "vision-pro");
  assert.equal(confirmCalls[0][1].apiKey, "secret");
});

test("confirming P1 system groups stays in P1 and renders the mechanism step", async () => {
  const gameplay = {
    revision: 2,
    directory: { status: "draft", entries: [] },
    chapters: [],
    reviewState: { structurePhase: "systems", interactionHandoffConfirmed: false },
  };
  const mechanisms = {
    ...gameplay,
    revision: 3,
    reviewState: { ...gameplay.reviewState, structurePhase: "mechanisms" },
  };
  const client = { confirmDirectory: async () => mechanisms };
  const context = loadReviewBackend(() => client); let rendered;
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayDirectory = { render(args) { rendered = args; } };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({
    revision: 4,
    stages: [],
    reviewState: {},
    quality: { qualified: true },
    gameplayReviewModel: gameplay,
  }), view: "gameplay_directory" };
  context.state.gameplayOperationQueue = { flush: async () => {} };
  context.location.href = "http://127.0.0.1:8000/?job=p1-step-job&ui=gameplay_directory";
  context.URL = URL;
  let replacedUrl = "";
  let resetToTop = false;
  context.history = { state: null, replaceState(_state, _title, url) { replacedUrl = String(url); } };
  context.workspace.scrollTo = ({ top }) => { resetToTop = top === 0; };
  context.renderGameplayDirectoryWorkspace();

  await rendered.onConfirm();

  assert.equal(context.state.gameplayReviewWorkspace.model.reviewState.structurePhase, "mechanisms");
  assert.equal(context.state.reviewWorkspace.view, "gameplay_directory");
  assert.equal(context.$("gameplayDirectoryView").hidden, false);
  assert.match(replacedUrl, /ui=gameplay_directory/);
  assert.equal(resetToTop, true);
});

test("confirming the mechanism directory stays on P1 and polls detailed generation instead of exposing skeleton chapters", async () => {
  const gameplay = {
    revision: 2,
    directory: { status: "draft", entries: [{ id: "GDE-001", chapterId: "GCH-001" }] },
    chapters: [{ id: "GCH-001" }],
    reviewState: { structurePhase: "mechanisms", status: "mechanism_directory_review" },
  };
  const pendingDetails = {
    ...gameplay,
    revision: 3,
    directory: { ...gameplay.directory, status: "confirmed" },
    reviewState: { structurePhase: "confirmed", status: "detail_generation_pending" },
  };
  const client = { jobId: "detail-job", confirmDirectory: async () => pendingDetails };
  const context = loadReviewBackend(() => client); let rendered;
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayDirectory = { render(args) { rendered = args; } };
  context.state.reviewClient = { jobId: "detail-job" };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({ revision: 4, stages: [], gameplayReviewModel: gameplay }), view: "gameplay_directory" };
  context.state.gameplayOperationQueue = { flush: async () => {} };
  context.$("apiKey").value = "configured-key";
  context.renderGameplayDirectoryWorkspace();

  await rendered.onConfirm();

  assert.equal(context.state.reviewWorkspace.view, "gameplay_directory");
  assert.equal(context.state.gameplayReviewGeneration.status, "queued");
  assert.ok(context.pendingTimers.size >= 1);
  assert.match(context.statuses.at(-1), /完成前不会开放后续审核与导出/);
});

test("ambiguous gameplay directory failure reconciles a server-side confirmation", async () => {
  const gameplay = {
    revision: 2,
    directory: { status: "draft", entries: [] },
    chapters: [],
    reviewState: { structurePhase: "systems", interactionHandoffConfirmed: false },
  };
  const canonical = {
    ...gameplay,
    revision: 3,
    reviewState: { ...gameplay.reviewState, structurePhase: "mechanisms" },
  };
  const client = {
    confirmDirectory: async () => { throw new Error("连接在响应返回前中断"); },
    load: async () => canonical,
  };
  const context = loadReviewBackend(() => client); let rendered;
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayDirectory = { render(args) { rendered = args; } };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({ revision: 4, stages: [], reviewState: {}, quality: { qualified: true }, gameplayReviewModel: gameplay }), view: "gameplay_directory" };
  context.state.gameplayOperationQueue = { flush: async () => {} };
  context.renderGameplayDirectoryWorkspace();

  await rendered.onConfirm();

  assert.equal(context.state.gameplayReviewWorkspace.model.revision, 3);
  assert.equal(context.state.gameplayReviewWorkspace.model.reviewState.structurePhase, "mechanisms");
  assert.equal(context.state.gameplayReviewWorkspace.saveStatus, "saved");
  assert.doesNotMatch(context.statuses.at(-1) || "", /失败|中断/);
});

test("P1 gameplay directory undo uses gameplay history instead of interaction history", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /function runGameplayHistory\(action\)/);
  assert.match(backend, /gameplay_directory[\s\S]*runGameplayHistory\("undo"\)/);
  assert.match(backend, /GameplayWorkspace\.historyControls\(state\.gameplayReviewWorkspace\.model\)/);
  assert.match(backend, /queue\.push\(operation, revision\)/);
  assert.match(backend, /flush\(state\.gameplayReviewWorkspace\.model\.revision\)/);
});

test("failed workbench keeps its job id in the deep link before retry configuration", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("function openFailedJobWorkbench"), backend.indexOf("async function enterReviewWorkbench"));
  assert.match(section, /url\.searchParams\.set\("job", job\.id\)/);
  assert.match(section, /url\.searchParams\.set\("ui", "analysis_failed"\)/);
  assert.match(section, /history\.replaceState/);
  const configSection = backend.slice(backend.indexOf("function ensureVisionModelConfig"), backend.indexOf("function renderGameplayTableWorkspace"));
  assert.match(configSection, /pendingUrl/);
  assert.match(configSection, /history\.replaceState\(history\.state, "", pendingUrl\)/);
});

test("detail generation opens model settings instead of submitting an empty key", async () => {
  const gameplay = { revision: 2, directory: { status: "draft", entries: [] }, chapters: [], reviewState: { structurePhase: "mechanisms" } };
  let calls = 0; let rendered;
  const client = { confirmDirectory: async () => { calls += 1; return gameplay; } };
  const context = loadReviewBackend(() => client);
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayDirectory = { render(args) { rendered = args; } };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({ revision: 4, stages: [], reviewState: {}, quality: { qualified: true }, gameplayReviewModel: gameplay }), view: "gameplay_directory" };
  context.state.gameplayOperationQueue = { flush: async () => {} };
  context.workspace.classList.add("has-review");
  context.renderGameplayDirectoryWorkspace();

  await rendered.onConfirm();

  assert.equal(calls, 0);
  assert.equal(context.$("apiConfigPanel").open, true);
  assert.equal(context.workspace.classList.contains("has-review"), false);
  assert.match(context.statuses.at(-1), /API/);
});

test("confirming the last gameplay chapter advances to automatic diagram review", async () => {
  const chapters = [{ id: "GCH-001", scope: "核心战斗", confirmation: { confirmed: false } }];
  const confirmed = [{ ...chapters[0], confirmation: { confirmed: true }, status: "approved" }];
  const client = { confirmChapter: async () => ({ revision: 2, chapters: confirmed, diagrams: [], reviewState: {}, diagramReview: { status: "pending" } }) };
  const context = loadReviewBackend(() => client);
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js");
  context.GameplayReview = { ...require("../../js/gameplay-review.js"), render() {} };
  context.GameplayDiagrams = { render() {} };
  context.state.gameplayReviewClient = client;
  context.state.gameplayReviewWorkspace = { model: { revision: 1, chapters, diagrams: [], reviewState: {} }, selectedChapterId: "GCH-001" };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({ revision: 4, stages: [], reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true } }), view: "gameplay" };
  context.state.gameplayOperationQueue = { hasPending: () => false };

  await context.runGameplayConfirmation("GCH-001", "approved");

  assert.equal(context.state.reviewWorkspace.view, "diagrams");
});

test("approving the last diagram advances to table review", async () => {
  const returned = { revision: 3, chapters: [{ id: "GCH-001", confirmation: { confirmed: true } }], diagrams: [{ id: "GDI-001", status: "reviewed" }], diagramReview: { status: "ready" }, tables: [], tableReview: { status: "pending" } };
  const client = { approveDiagram: async () => returned };
  const context = loadReviewBackend(() => client);
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js"); context.GameplayDiagrams = { render() {} }; context.GameplayTables = { render() {} };
  context.state.gameplayReviewClient = client; context.state.gameplayReviewWorkspace = { model: { ...returned, revision: 2, diagrams: [{ id: "GDI-001", status: "open" }] }, diagramRequestState: { generation: {}, byId: {} } };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({ revision: 4, stages: [], reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true } }), view: "diagrams" };

  await context.runGameplayDiagramAction("approve", "GDI-001", "");

  assert.equal(context.state.reviewWorkspace.view, "tables");
});

test("approving the last table advances to final preview", async () => {
  const returned = { revision: 4, chapters: [{ id: "GCH-001", confirmation: { confirmed: true } }], diagrams: [], diagramReview: { status: "ready" }, tables: [{ id: "GTB-001", status: "reviewed" }], tableReview: { status: "ready" } };
  const client = { tableAction: async () => returned };
  const context = loadReviewBackend(() => client);
  context.GameplayWorkspace = require("../../js/gameplay-workspace.js"); context.GameplayTables = { render() {} };
  context.state.gameplayReviewClient = client; context.state.gameplayReviewWorkspace = { model: { ...returned, revision: 3, tables: [{ id: "GTB-001", status: "open" }] }, tableRequestState: { generation: {}, byId: {} } };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState({ revision: 6, stages: [], reviewState: { status: "preview_ready", previewRevision: 6 }, quality: { qualified: true } }), view: "tables" };

  await context.runGameplayTableAction("approve", "GTB-001", "");

  assert.equal(context.state.reviewWorkspace.view, "final_preview");
});

test("final preview enters automatic completion instead of leaving export silently disabled", async () => {
  const context = loadReviewBackend(() => ({}));
  const interaction = { revision: 11, stages: [], reviewState: { previewRevision: 11 }, quality: { qualified: true } };
  const gameplay = { revision: 41, chapters: [], reviewState: { previewRevision: null } };
  context.state.reviewClient = { jobId: "job-autofill" };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(interaction), model: interaction, view: "final_preview" };
  context.state.gameplayReviewClient = {
    finalPreview: async () => ({
      interactionRevision: 11, gameplayRevision: 41, exportReady: false,
      blockerIds: ["GCH-001:RULES_MISSING"], documentOrder: [],
      autoCompletion: { status: "queued", progress: 0 },
    }),
  };
  context.state.gameplayReviewWorkspace = { model: gameplay, preview: null, previewStatus: "idle" };

  await context.loadCombinedFinalPreview();

  assert.equal(context.state.gameplayReviewWorkspace.previewStatus, "autofilling");
  assert.equal(context.state.gameplayReviewGeneration.status, "queued");
  assert.equal(context.pendingTimers.size, 1);
});

test("confirmed interaction and gameplay render a local P7 preview without requiring a visual API", () => {
  const context = loadReviewBackend(() => ({}));
  const interaction = { revision: 11, stages: [{ id: "S1", title: "持续战斗", confirmation: { confirmed: true } }], reviewState: { previewRevision: 11 }, quality: { qualified: true } };
  const gameplay = { revision: 41, chapters: [{ id: "C1", scope: "核心战斗", summary: "持续攻击敌人", confirmation: { confirmed: true } }], reviewState: {} };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(interaction), model: interaction, view: "final_preview" };
  context.state.gameplayReviewWorkspace = { model: gameplay, preview: null, previewStatus: "idle" };
  const preview = context.localConfirmedFinalPreview(context.state.gameplayReviewWorkspace, interaction);
  assert.equal(preview.interactionRevision, 11);
  assert.equal(preview.gameplayRevision, 41);
  assert.equal(preview.autoCompletion.status, "idle");
});

test("P7 renderer never substitutes the board-less local summary for the server preview", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const body = backend.slice(backend.indexOf("function renderCombinedFinalPreview"), backend.indexOf("async function loadCombinedFinalPreview"));
  assert.match(body, /const preview = workspace\.preview;/);
  assert.doesNotMatch(body, /workspace\.preview \|\| localConfirmedFinalPreview/);
  assert.match(body, /生成完整预览/);
  assert.doesNotMatch(body, /workspace\.previewStatus === "idle"\) void loadCombinedFinalPreview\(\)/);
});

test("P7 automatically completes pending gameplay when the browser already has model configuration", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const body = backend.slice(backend.indexOf("async function loadCombinedFinalPreview"), backend.indexOf("function rebuildGameplayReviewWorkspace"));
  assert.match(body, /shouldAutoComplete\s*=\s*workspace\.model\.reviewState\?\.status === "detail_generation_pending" && hasVisionModelConfig\(\)/);
  assert.match(body, /client\.finalPreview/);
  assert.doesNotMatch(body, /localConfirmedFinalPreview\(workspace/);
});

test("opening final preview never dismisses the workbench when model configuration is missing", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const body = backend.slice(backend.indexOf("async function loadCombinedFinalPreview"), backend.indexOf("function rebuildGameplayReviewWorkspace"));
  assert.match(body, /hasVisionModelConfig\(\)/);
  assert.doesNotMatch(body, /ensureVisionModelConfig\(\)/);
});

test("automatic completion renders a determinate progress bar in final preview", () => {
  const renderer = fs.readFileSync("js/final-document-preview.js", "utf8");
  assert.match(renderer, /final-document-score-track/);
  assert.match(renderer, /setAttribute\("role", "progressbar"\)/);
  assert.match(renderer, /setAttribute\("aria-valuenow", String\(percent\)\)/);
  assert.match(renderer, /style\.width = `\$\{percent\}%`/);
});

test("failed final preview offers a planner-facing automatic completion retry", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /继续自动补全/);
  assert.match(backend, /请先在模型设置中填写视觉模型密钥/);
  assert.match(backend, /void loadCombinedFinalPreview\(\)/);
});

test("interaction preview keeps the last gameplay generation failure visible instead of looking unresponsive", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const interactionPreview = backend.slice(backend.indexOf('if (state.reviewWorkspace.view === "interaction_preview")'), backend.indexOf("function renderAnalysisFailedWorkspace"));
  assert.match(interactionPreview, /model\.gameplayReviewModel\s*\|\|\s*state\.gameplayReviewGeneration\?\.startedFromInteractionPreview/);
  assert.match(interactionPreview, /state\.gameplayReviewGeneration\s*\|\|\s*null/);
  assert.doesNotMatch(interactionPreview, /generation:\s*gameplayGenerationBusy\(\)\s*\?/);
});

test("gameplay generation reads the built-in model configuration from the shared page binding", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const configGate = backend.slice(backend.indexOf("function hasVisionModelConfig"), backend.indexOf("function renderGameplayTableWorkspace"));
  assert.match(configGate, /typeof publicApiConfig !== "undefined"/);
  assert.doesNotMatch(configGate, /globalThis\.publicApiConfig/);
});

test("final preview prints safe gameplay generation logs while polling", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /生成记录/);
  assert.match(backend, /gameplay-generation-log/);
  assert.match(backend, /record\.logs/);
});

test("lead-planner quality failures automatically re-enter repair instead of showing a dead-end message", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /failureKind === "quality"/);
  assert.match(backend, /autoRepairAttempts/);
  assert.match(backend, /主策检查未通过，正在自动修复/);
  assert.doesNotMatch(backend, /当前内容还不能导出，请先补全页面中提示的内容，或重新生成预览/);
});

test("P7 final preview uses the target document reader instead of a printed order list", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const renderer = fs.readFileSync("js/final-document-preview.js", "utf8");
  assert.match(backend, /FinalDocumentPreview\.render/);
  assert.match(renderer, /final-document-shell/);
  assert.match(renderer, /final-document-stepbar/);
  const previewBackend = fs.readFileSync("backend/review_preview.py", "utf8");
  for (const label of ["AI理解", "玩法目录", "交互审核", "规则审核", "参数审核", "图解审核", "文档导出"]) {
    assert.match(previewBackend, new RegExp(label));
  }
  assert.match(renderer, /final-document-titlebar/);
  assert.match(renderer, /final-document-toc/);
  assert.match(renderer, /final-document-reader/);
  assert.match(renderer, /final-document-status/);
  assert.doesNotMatch(backend, /document-order-tree/);
});

test("P7 ignores a stale generation percentage after automatic completion has stopped", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /generationCompletion\.busy\s*\?/);
  assert.match(backend, /preview\.autoCompletion\s*\|\|\s*generationCompletion/);
  assert.doesNotMatch(backend, /completion:\s*state\.gameplayReviewGeneration\s*\|\|\s*preview\.autoCompletion/);
});

test("restored preview loads once, stays disabled while loading, then renders the real SVG", async () => {
  let resolvePreview;
  const model = { revision: 4, stages: [], ruleDomains: { confirmation: { confirmed: true } }, reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const client = {
    previewCalls: 0,
    load() { return Promise.resolve(model); },
    preview() {
      this.previewCalls += 1;
      return new Promise((resolve) => { resolvePreview = resolve; });
    },
  };
  const context = loadReviewBackend(() => client);
  context.syncBackendResult(reviewJob(model));

  assert.equal(client.previewCalls, 1);
  assert.equal(context.state.reviewWorkspace.preview, null);
  assert.equal(context.state.reviewWorkspace.previewStatus, "loading");
  assert.equal(context.publicationRenders.at(-1).canPublish, false);
  assert.match(context.$("exportPreviewView").textContent, /生成|加载/);

  resolvePreview({ revision: 4, exportReady: true, boardPreviewSvg: '<svg data-preview="real"></svg>', blockerIds: [] });
  await new Promise(setImmediate);

  assert.equal(client.previewCalls, 1);
  assert.equal(context.state.reviewWorkspace.previewStatus, "ready");
  assert.equal(context.state.reviewWorkspace.preview.boardPreviewSvg, '<svg data-preview="real"></svg>');
  assert.equal(context.previewRenders.at(-1).boardPreviewSvg, '<svg data-preview="real"></svg>');
  assert.equal(context.publicationRenders.at(-1).canPublish, true);
});

test("interaction delivery does not display a failed gameplay autofill from another stage", () => {
  const model = { revision: 4, stages: [], ruleDomains: { confirmation: { confirmed: true } }, reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const context = loadReviewBackend(() => ({ load: () => Promise.resolve(model) }));
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(model), view: "interaction_preview", preview: { boardPreviewSvg: "<svg></svg>", exportReady: true } };
  context.state.gameplayReviewGeneration = { status: "failed", error: "model configuration missing" };
  context.renderReviewWorkspace(model);
  assert.equal(context.previewRenderArgs.at(-1).generation, null);
});

test("restored preview failure stays disabled and exposes an explicit retry blocker", async () => {
  const client = {
    previewCalls: 0,
    load() { return new Promise(() => {}); },
    preview() { this.previewCalls += 1; return Promise.reject(new Error("preview service unavailable")); },
  };
  const context = loadReviewBackend(() => client);

  context.syncBackendResult(reviewJob({ revision: 4, stages: [], ruleDomains: { confirmation: { confirmed: true } }, reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }));
  await new Promise(setImmediate);

  assert.equal(client.previewCalls, 1);
  assert.equal(context.state.reviewWorkspace.preview, null);
  assert.equal(context.state.reviewWorkspace.previewStatus, "failed");
  assert.equal(context.publicationRenders.at(-1).canPublish, false);
  assert.match(context.$("exportPreviewView").textContent, /preview service unavailable/);
  assert.match(context.$("exportPreviewView").textContent, /重试/);
});

test("a preview response for an older revision is discarded", async () => {
  let resolvePreview;
  const client = {
    load() { return new Promise(() => {}); },
    preview() { return new Promise((resolve) => { resolvePreview = resolve; }); },
  };
  const context = loadReviewBackend(() => client);
  context.syncBackendResult(reviewJob({ revision: 4, stages: [], ruleDomains: { confirmation: { confirmed: true } }, reviewState: { status: "preview_ready", previewRevision: 4 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }));
  context.state.reviewWorkspace = {
    ...context.state.reviewWorkspace,
    model: { ...context.state.reviewWorkspace.model, revision: 5 },
    preview: null,
    previewStatus: "idle",
  };

  resolvePreview({ revision: 4, exportReady: true, boardPreviewSvg: '<svg data-preview="stale"></svg>' });
  await new Promise(setImmediate);

  assert.equal(context.state.reviewWorkspace.model.revision, 5);
  assert.equal(context.state.reviewWorkspace.preview, null);
  assert.equal(context.previewRenders.length, 0);
});

test("a late interaction preview response cannot pull the planner back from P4–P7", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const body = backend.slice(backend.indexOf("async function loadReviewPreview"), backend.indexOf("function bindReviewWorkspace"));
  assert.match(body, /previewUiVersion/);
  assert.match(body, /previewUiVersion === reviewUiInteractionVersion \? "interaction_preview" : state\.reviewWorkspace\.view/);
});

test("analysis failure renders the dedicated read-only workspace view", () => {
  const client = { load() { return new Promise(() => {}); } };
  const context = loadReviewBackend(() => client);
  context.syncBackendResult(reviewJob({ revision: 1, stages: [], reviewState: {}, quality: { qualified: false, blockers: ["NO_QUALIFIED_STAGE"] }, editHistory: { undo: [{}], redo: [{}] } }));
  assert.equal(context.$("analysisFailedView").hidden, false);
  assert.equal(context.$("flowReviewView").hidden, true);
  assert.equal(context.$("reviewUndoBtn").disabled, true);
  assert.match(context.$("analysisFailedMessage").textContent, /NO_QUALIFIED_STAGE/);
});

test("confirm flow rebuilds from the returned canonical model and advances to stage review", async () => {
  const confirmed = { revision: 2, stages: [{ id: "STG-001", confirmation: { confirmed: false } }], transitions: [], sources: { F0001: {} }, reviewState: { status: "stage_review", flowConfirmed: true, confirmedStageIds: [], previewRevision: null }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const calls = [];
  const client = {
    load() { return new Promise(() => {}); },
    confirmFlow(revision) { calls.push(revision); return Promise.resolve(confirmed); },
  };
  const context = loadReviewBackend(() => client);
  context.syncBackendResult(reviewJob({ ...confirmed, revision: 1, reviewState: { status: "flow_review", flowConfirmed: false, confirmedStageIds: [], previewRevision: null } }));

  await context.$("reviewConfirmFlowBtn").onclick();

  assert.deepEqual(calls, [1]);
  assert.equal(context.state.reviewWorkspace.model.revision, 2);
  assert.equal(context.state.reviewWorkspace.view, "stage");
});

test("confirming the last stage advances directly to the planning preview and exposes validation failures", async () => {
  const start = { revision: 1, stages: [{ id: "STG-001", representativeFrames: [{ frameId: "F0001", role: "entry" }], confirmation: { confirmed: false } }], transitions: [], sources: { F0001: {} }, reviewState: { status: "stage_review", flowConfirmed: true, confirmedStageIds: [], previewRevision: null }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const confirmed = { ...start, revision: 2, stages: [{ ...start.stages[0], confirmation: { confirmed: true, revision: 2 } }], ruleDomains: { narrative: [], guidance: [], redDots: [], reviewedDomains: [], confirmation: { confirmed: false, revision: null } }, reviewState: { status: "preview_ready", flowConfirmed: true, confirmedStageIds: ["STG-001"], previewRevision: 2 } };
  const client = {
    load() { return new Promise(() => {}); },
    confirmStage(stageId, revision) { assert.deepEqual([stageId, revision], ["STG-001", 1]); return Promise.resolve(confirmed); },
    preview() { return Promise.resolve({ revision: 2, exportReady: true, boardPreviewSvg: "<svg></svg>" }); },
  };
  const context = loadReviewBackend(() => client);
  context.syncBackendResult(reviewJob(start));

  await context.$("reviewConfirmStageBtn").onclick();
  await new Promise(setImmediate);

  assert.equal(context.state.reviewWorkspace.view, "interaction_preview");
  assert.equal(context.state.reviewWorkspace.previewStatus, "ready");

  client.confirmFlow = () => Promise.reject(new Error("cannot confirm flow: TRN-001"));
  context.state.reviewWorkspace = ReviewWorkspace.rebuild({ ...start, reviewState: { ...start.reviewState, flowConfirmed: false } });
  context.bindReviewWorkspace();
  await context.$("reviewConfirmFlowBtn").onclick();
  assert.equal(context.$("reviewValidationError").hidden, false);
  assert.match(context.$("reviewValidationError").textContent, /TRN-001/);
  assert.equal(context.$("reviewConfirmFlowBtn").disabled, false);
});

test("drawer state survives workspace rendering and canonical refresh", async () => {
  const model = { revision: 4, stages: [], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const client = { load() { return Promise.resolve({ ...model, revision: 5 }); } };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState(model);
  context.bindReviewWorkspace();
  context.$("reviewProjectDrawerToggle").onclick();
  assert.equal(context.state.reviewWorkspace.projectDrawerOpen, true);
  await context.syncCanonicalReviewModel(client);
  assert.equal(context.$("reviewProjectDrawer").classList.contains("is-open"), true);
  assert.equal(context.$("reviewProjectDrawerToggle").attrs["aria-expanded"], "true");
});

test("empty undo history does not send a review request", async () => {
  const client = { undoCalls: 0, undo() { this.undoCalls += 1; return Promise.resolve({}); } };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState({ revision: 3, stages: [], quality: { qualified: true }, editHistory: { undo: [], redo: [] } });
  await context.runReviewHistory("undo");
  assert.equal(client.undoCalls, 0);
});

test("undo flushes queued edits before sending the revisioned history request", async () => {
  const order = [];
  const client = { undo(revision) { order.push(`undo:${revision}`); return Promise.resolve({ revision: revision + 1, stages: [], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }); } };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState({ revision: 3, stages: [], quality: { qualified: true }, editHistory: { undo: [{}], redo: [] } });
  context.state.reviewOperationQueue = { hasPending: () => true, flush: async (revision) => { order.push(`flush:${revision}`); } };

  await context.runReviewHistory("undo");

  assert.deepEqual(order, ["flush:3", "undo:3"]);
});

test("task switching flushes the old queue before replacing its client", async () => {
  const order = [];
  const nextClient = { jobId: "job-review", load: () => Promise.resolve({ revision: 1, stages: [], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }) };
  const context = loadReviewBackend(() => nextClient);
  context.state.reviewClient = { jobId: "job-old" };
  context.state.reviewWorkspace = ReviewWorkspace.initialState({ revision: 7, stages: [], quality: { qualified: true }, editHistory: { undo: [], redo: [] } });
  context.state.reviewOperationQueue = { hasPending: () => true, flush: async (revision) => { order.push(`flush:${revision}`); }, clear: () => order.push("clear") };

  await context.syncBackendResult(reviewJob({ revision: 1, stages: [], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }));

  assert.deepEqual(order, ["flush:7", "clear"]);
  assert.equal(context.state.reviewClient, nextClient);
});

test("backend binds unload protection for pending review operations", () => {
  const source = fs.readFileSync("js/backend.js", "utf8");
  assert.match(source, /onbeforeunload/);
  assert.match(source, /pagehide/);
  assert.match(source, /hasPending\(\)/);
});

test("repeated workspace binds retain one pagehide handler and flush once", async () => {
  const context = loadReviewBackend(() => ({ load() { return new Promise(() => {}); } }));
  let flushes = 0;
  context.state.reviewWorkspace = ReviewWorkspace.initialState({ revision: 7, stages: [], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } });
  context.state.reviewOperationQueue = { hasPending: () => true, flushOnExit: async () => { flushes += 1; } };

  context.bindReviewWorkspace();
  context.bindReviewWorkspace();
  assert.equal(context.pagehideHandlers.length, 1);
  context.pagehideHandlers[0]({});
  await new Promise(setImmediate);
  assert.equal(flushes, 1);
});

test("revision conflict reloads the canonical model instead of retaining a stale revision", async () => {
  const conflict = Object.assign(new Error("conflict"), { status: 409, currentRevision: 6 });
  const client = { undo() { return Promise.reject(conflict); }, load() { return Promise.resolve({ revision: 6, stages: [], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } }); } };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState({ revision: 5, stages: [], quality: { qualified: true }, editHistory: { undo: [{}], redo: [] } });
  await context.runReviewHistory("undo");
  assert.equal(context.state.reviewWorkspace.model.revision, 6);
  assert.equal(context.state.reviewWorkspace.saveStatus, "conflict_synced");
});

test("ambiguous stage confirmation failure reconciles a server-side success", async () => {
  const model = {
    revision: 7,
    stages: [{ id: "STG-001", confirmation: { confirmed: false, revision: null } }],
    transitions: [], regions: [], components: [], componentStates: [],
    reviewState: { status: "stage_review", flowConfirmed: true, confirmedStageIds: [] },
    quality: { qualified: true }, editHistory: { undo: [], redo: [] },
  };
  const canonical = {
    ...model,
    revision: 8,
    stages: [{ id: "STG-001", confirmation: { confirmed: true, revision: 8 } }],
    reviewState: { status: "preview_pending", flowConfirmed: true, confirmedStageIds: ["STG-001"] },
  };
  const client = {
    confirmStage: async () => { throw new Error("连接在响应返回前中断"); },
    load: async () => canonical,
    saveUiState: async () => ({}),
    preview: async () => ({ revision: 8, exportReady: true, boardPreviewSvg: "<svg />" }),
  };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState(model);
  context.state.reviewOperationQueue = { hasPending: () => false };

  await context.runReviewConfirmation("stage");

  assert.equal(context.state.reviewWorkspace.model.revision, 8);
  assert.equal(context.state.reviewWorkspace.model.stages[0].confirmation.confirmed, true);
  assert.equal(context.state.reviewWorkspace.confirmStatus, "idle");
  assert.doesNotMatch(context.$("reviewValidationError").textContent || "", /当前环节保存失败/);
});

test("stage confirmation returns to flow review when the canonical flow is not confirmed", async () => {
  const stale = {
    revision: 7,
    stages: [{ id: "STG-001", confirmation: { confirmed: false, revision: null } }],
    transitions: [], regions: [], components: [], componentStates: [],
    reviewState: { status: "stage_review", flowConfirmed: true, confirmedStageIds: [] },
    quality: { qualified: true }, editHistory: { undo: [], redo: [] },
  };
  const canonical = {
    ...stale,
    reviewState: { status: "flow_review", flowConfirmed: false, confirmedStageIds: [] },
  };
  const prerequisite = Object.assign(new Error("flow must be confirmed before confirming a stage"), { status: 400 });
  const client = {
    confirmStage: async () => { throw prerequisite; },
    load: async () => canonical,
  };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(stale), view: "stage" };
  context.state.reviewOperationQueue = { hasPending: () => false };

  await context.runReviewConfirmation("stage");

  assert.equal(context.state.reviewWorkspace.view, "flow");
  assert.match(context.$("reviewValidationError").textContent || "", /先确认整体交互流程/);
  assert.doesNotMatch(context.$("reviewValidationError").textContent || "", /检查服务状态/);
});

test("stage confirmation explains missing observed action instead of blaming the service", async () => {
  const model = {
    revision: 26,
    stages: [{ id: "STG-006", confirmation: { confirmed: false, revision: null } }],
    transitions: [], regions: [], components: [], componentStates: [],
    reviewState: { status: "stage_review", flowConfirmed: true, confirmedStageIds: [] },
    quality: { qualified: true }, editHistory: { undo: [], redo: [] },
  };
  const validation = Object.assign(new Error("stage evidence has no explicit observed action"), { status: 400 });
  const client = {
    confirmStage: async () => { throw validation; },
    load: async () => model,
  };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(model), view: "stage" };
  context.state.reviewOperationQueue = { hasPending: () => false };

  await context.runReviewConfirmation("stage");

  assert.match(context.$("reviewValidationError").textContent || "", /缺少已确认的玩家操作/);
  assert.match(context.$("reviewValidationError").textContent || "", /决策卡/);
  assert.doesNotMatch(context.$("reviewValidationError").textContent || "", /检查服务状态/);
  assert.equal(context.state.reviewWorkspace.model.revision, 26);
  assert.equal(context.state.reviewWorkspace.view, "stage");
});

test("stage confirmation treats other validation rejections as unmet review conditions", async () => {
  const model = {
    revision: 4,
    stages: [{ id: "STG-002", confirmation: { confirmed: false, revision: null } }],
    transitions: [], regions: [], components: [], componentStates: [],
    reviewState: { status: "stage_review", flowConfirmed: true, confirmedStageIds: [] },
    quality: { qualified: true }, editHistory: { undo: [], redo: [] },
  };
  const validation = Object.assign(new Error("stage evidence is missing a corresponding image"), { status: 400 });
  const client = { confirmStage: async () => { throw validation; }, load: async () => model };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(model), view: "stage" };
  context.state.reviewOperationQueue = { hasPending: () => false };

  await context.runReviewConfirmation("stage");

  assert.match(context.$("reviewValidationError").textContent || "", /尚未满足确认条件/);
  assert.doesNotMatch(context.$("reviewValidationError").textContent || "", /检查服务状态/);
});

test("reference board controller rejects UX and locks competitor requests before flushing", async () => {
  let resolveFirst;
  const calls = [];
  const model = { revision: 7, stages: [], ruleDomains: { confirmation: { confirmed: false }, reviewedDomains: [] }, reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const context = loadReviewBackend(() => ({ load: () => Promise.resolve(model) }));
  context.state.reviewClient = { jobId: "job-board", load: () => Promise.resolve(model) };
  context.state.reviewWorkspace = ReviewWorkspace.initialState(model);
  context.state.reviewOperationQueue = { hasPending: () => true, flush: async () => {} };

  await context.runReferenceBoardMutation("ux", () => calls.push("legacy"));
  assert.equal(context.state.reviewWorkspace.referenceBoardStates.ux, undefined);
  const first = context.runReferenceBoardMutation("competitor", () => {
    calls.push("first");
    return new Promise((resolve) => { resolveFirst = resolve; });
  });
  const second = context.runReferenceBoardMutation("competitor", () => calls.push("second"));

  assert.equal(context.state.reviewWorkspace.referenceBoardBusy, true);
  await new Promise(setImmediate);
  assert.deepEqual(Array.from(calls), ["first"]);
  resolveFirst({ ...model, revision: 8 });
  await Promise.all([first, second]);
  assert.equal(context.state.reviewWorkspace.referenceBoardBusy, false);
  assert.deepEqual(Array.from(calls), ["first"]);
  assert.equal(calls.filter((call) => call === "second").length, 0);
});

test("failed optional competitor mutation never blocks the planning-only preview", async () => {
  const model = { revision: 7, stages: [], ruleDomains: { confirmation: { confirmed: false }, reviewedDomains: ["narrative", "guidance", "redDots"] }, reviewState: { flowConfirmed: true, ueFlowConfirmed: true }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const context = loadReviewBackend(() => ({ load: () => Promise.resolve(model) }));
  context.state.reviewClient = { jobId: "job-board" };
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(model), view: "preview" };

  await assert.rejects(() => context.runReferenceBoardMutation("competitor", () => Promise.reject(new Error("网络异常"))), /网络异常/);

  const failed = context.state.reviewWorkspace.referenceBoardStates.competitor;
  assert.equal(failed.status, "failed");
  assert.equal(failed.error, "网络异常");
  assert.equal(typeof failed.retry, "function");
  assert.equal(context.state.reviewWorkspace.view, "interaction_preview");
  assert.equal(ReviewWorkspace.competitorMutationBlocked(context.state.reviewWorkspace), false);
  assert.equal(context.state.reviewWorkspace.view, "interaction_preview");
});

test("optional empty competitor failure does not block preview and retry still clears it", async () => {
  const model = { revision: 7, stages: [], reviewState: { status: "preview_ready", flowConfirmed: true, ueFlowConfirmed: true, previewRevision: 7 }, quality: { qualified: true }, editHistory: { undo: [], redo: [] }, referenceBoards: { planning: { status: "generated" }, competitor: { assets: [], status: "pending" } } };
  let attempts = 0;
  const client = {
    jobId: "job-board",
    previewCalls: 0,
    preview() { this.previewCalls += 1; return Promise.resolve({ revision: 7, exportReady: true, boardPreviewSvg: "<svg></svg>" }); },
  };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(model), view: "preview" };
  const request = () => {
    attempts += 1;
    return attempts === 1 ? Promise.reject(new Error("网络异常")) : Promise.resolve({ ...model, revision: 8, reviewState: { ...model.reviewState, previewRevision: null } });
  };

  await assert.rejects(() => context.runReferenceBoardMutation("competitor", request), /网络异常/);
  assert.equal(ReviewWorkspace.competitorMutationBlocked(context.state.reviewWorkspace), false);
  await context.loadReviewPreview();
  assert.equal(client.previewCalls, 2);

  await context.runReferenceBoardMutation("competitor", context.state.reviewWorkspace.referenceBoardStates.competitor.retry);
  assert.equal(ReviewWorkspace.competitorMutationBlocked(context.state.reviewWorkspace), false);
  assert.equal(context.state.reviewWorkspace.referenceBoardStates.competitor, undefined);
});

test("board busy survives a real queued-operation rebuild until its board request resolves", async () => {
  let resolveBoard;
  const calls = [];
  const model = { revision: 7, stages: [], ruleDomains: { confirmation: { confirmed: false }, reviewedDomains: [] }, reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const canonical = { ...model, revision: 8 };
  const client = { jobId: "job-board", operations: () => Promise.resolve(canonical) };
  const context = loadReviewBackend(() => client);
  context.ReviewClient.createOperationQueue = ReviewClient.createOperationQueue;
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState(model);
  context.state.reviewOperationQueue = context.makeReviewOperationQueue(client);
  context.state.reviewOperationQueue.push({ type: "set", entity: "stage", id: "STG-001", field: "name", value: "updated" }, model.revision);

  const first = context.runReferenceBoardMutation("competitor", () => {
    calls.push("first");
    return new Promise((resolve) => { resolveBoard = resolve; });
  });
  await new Promise(setImmediate);
  const second = context.runReferenceBoardMutation("competitor", () => calls.push("second"));

  assert.equal(context.state.reviewWorkspace.referenceBoardBusy, true);
  assert.deepEqual(calls, ["first"]);
  resolveBoard({ ...canonical, revision: 9 });
  await Promise.all([first, second]);
  assert.equal(context.state.reviewWorkspace.referenceBoardBusy, false);
  assert.deepEqual(context.state.reviewWorkspace.referenceBoardStates, {});
});

test("failed competitor board state survives an unrelated queued-operation rebuild", async () => {
  const retry = () => Promise.resolve();
  const model = { revision: 7, stages: [], ruleDomains: { confirmation: { confirmed: false }, reviewedDomains: ["narrative", "guidance", "redDots"] }, reviewState: { flowConfirmed: true }, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const canonical = { ...model, revision: 8 };
  const client = { jobId: "job-board", operations: () => Promise.resolve(canonical) };
  const context = loadReviewBackend(() => client);
  context.ReviewClient.createOperationQueue = ReviewClient.createOperationQueue;
  context.state.reviewClient = client;
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(model), view: "preview", referenceBoardStates: { competitor: { status: "failed", error: "网络异常", retry } } };
  context.state.reviewOperationQueue = context.makeReviewOperationQueue(client);
  context.state.reviewOperationQueue.push({ type: "set", entity: "stage", id: "STG-001", field: "name", value: "updated" }, model.revision);

  await context.state.reviewOperationQueue.flush(model.revision);

  assert.equal(context.state.reviewWorkspace.referenceBoardStates.competitor.status, "failed");
  assert.equal(context.state.reviewWorkspace.referenceBoardStates.competitor.retry, retry);
});

test("declining every conflict restores the canonical model and discards pending work", async () => {
  const canonical = { revision: 6, stages: [{ id: "STG-001", name: "server" }], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } };
  const client = { load: () => Promise.resolve(canonical) };
  const context = loadReviewBackend(() => client);
  const discarded = [];
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState({ ...canonical, revision: 5, stages: [{ id: "STG-001", name: "local" }] });
  context.state.reviewOperationQueue = {
    pending: () => [{ type: "set", entity: "stage", id: "STG-001", field: "name", value: "local" }],
    discard: () => discarded.push("discard"),
    clear: () => { throw new Error("pending work must not use clear"); },
  };

  await context.resolveReviewConflict(client);

  assert.deepEqual(discarded, ["discard"]);
  assert.equal(context.state.reviewWorkspace.model.revision, 6);
  assert.equal(context.state.reviewWorkspace.saveStatus, "saved");
});

test("UI-state persistence serializes requests and coalesces the newest state after a failure", async () => {
  const requests = [];
  const deferred = () => {
    let resolve, reject;
    return { promise: new Promise((done, fail) => { resolve = done; reject = fail; }), resolve, reject };
  };
  const client = {
    saveUiState(value) {
      const request = deferred();
      requests.push({ value, request });
      return request.promise;
    },
  };
  const context = loadReviewBackend(() => client);
  context.state.reviewClient = client;
  context.state.reviewWorkspace = ReviewWorkspace.initialState({ revision: 4, stages: [{ id: "STG-001" }], reviewState: {}, quality: { qualified: true }, editHistory: { undo: [], redo: [] } });

  context.persistReviewUiState();
  context.flushTimers();
  context.state.reviewWorkspace = { ...context.state.reviewWorkspace, view: "stage", selectedStageId: "STG-001" };
  context.persistReviewUiState();
  context.flushTimers();
  context.state.reviewWorkspace = { ...context.state.reviewWorkspace, view: "preview", selection: { type: "stage", id: "STG-001" } };
  context.persistReviewUiState();
  context.flushTimers();

  await new Promise(setImmediate);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].value.view, "flow");
  requests[0].request.reject(new Error("offline"));
  await new Promise(setImmediate);

  assert.equal(requests.length, 2);
  assert.equal(requests[1].value.view, "preview");
  assert.deepEqual(requests[1].value.selection, { type: "stage", id: "STG-001" });
  requests[1].request.resolve({});
  await new Promise(setImmediate);
  assert.equal(requests.length, 2);
});
test("opening P3 automatically rebuilds a missing interaction preview", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf('if (state.reviewWorkspace.view === "interaction_preview")'), backend.indexOf("function renderCurrentFeishuPublication"));
  assert.match(section, /previewStatus === "idle"/);
  assert.match(section, /void loadReviewPreview\(\{ flushPending: false \}\)/);
});

test("local confirmed P7 preview can become export-ready when every public gate passes", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("function localConfirmedFinalPreview"), backend.indexOf("function renderCombinedFinalPreview"));
  assert.match(section, /exportReady:\s*true/);
});

test("clicking the final preview navigation persists that view without a debounce window", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("function bindReviewWorkspace"), backend.indexOf("async function startReviewWorkspace"));
  assert.match(section, /persistReviewUiState\(button\.dataset\.reviewView\s*===\s*["']final_preview["']\s*\?\s*\{\s*immediate:\s*true\s*\}/);
});

test("initial task restoration hydrates the saved P1-P7 view before the first render", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("async function syncBackendResult"), backend.indexOf("function renderTimelineWorkbench"));
  assert.match(section, /reviewUiState:\s*restoredReviewUiState/);
  assert.match(section, /rebuildReviewWorkspace\([\s\S]*?["']saved["'],\s*true\)/);
  assert.match(section, /setReviewWorkspaceView\(restoredReviewUiState\.view\)/);
});

test("refresh reapplies the URL phase after canonical interaction and gameplay syncs settle", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("async function syncBackendResult"), backend.indexOf("function renderTimelineWorkbench"));
  assert.match(section, /restoreRequestedViewAfterSync/);
  assert.match(section, /await syncCanonicalReviewModel\(state\.reviewClient\)/);
  assert.match(section, /await syncGameplayReviewModel\(state\.gameplayReviewClient\)/);
  assert.match(section, /restoreRequestedViewIfCurrent[\s\S]*setReviewWorkspaceView\(requestedView\)[\s\S]*renderReviewWorkspace[\s\S]*syncReviewViewUrl\(state\.reviewWorkspace\.view, \{ replace: true \}\)/);
  assert.match(section, /if \(final\) reviewUiInteractionVersion \+= 1/);
  assert.match(section, /void restoreRequestedViewAfterSync\(\)/);
});

test("failed gameplay generation keeps preserved interaction review inspectable", () => {
  const context = loadReviewBackend(() => ({}));
  const gameplay = {
    lifecycleState: "generation_failed",
    contentState: "failed",
    directory: { status: "pending_generation" },
    chapters: [],
    reviewState: { status: "generation_required" },
  };
  const interaction = {
    revision: 4,
    stages: [{ id: "STG-001", confirmation: { confirmed: true } }],
    reviewState: { flowConfirmed: true },
    quality: { qualified: true },
    gameplayReviewModel: gameplay,
  };
  const p1 = { dataset: { reviewView: "gameplay_directory" }, disabled: false, setAttribute() {} };
  const p2 = { dataset: { reviewView: "flow" }, disabled: false, setAttribute() {} };
  const p4 = { dataset: { reviewView: "gameplay" }, disabled: false, setAttribute() {} };
  context.reviewButtons.push(p1, p2, p4);
  context.document.documentElement = { scrollLeft: 0 };
  context.document.body = { scrollLeft: 0 };
  context.window.scrollTo = () => {};
  context.workspace.scrollTo = () => {};
  context.state.reviewWorkspace = { ...ReviewWorkspace.initialState(interaction), model: interaction, view: "gameplay_directory" };
  context.state.gameplayReviewWorkspace = { model: gameplay };

  context.setReviewWorkspaceView("flow");

  assert.equal(context.state.reviewWorkspace.view, "flow");
  assert.equal(p2.disabled, false);
  assert.equal(p4.disabled, true);
  assert.equal(p4.title, "请先生成并确认玩法目录");
  assert.equal(p2.title, "");
});

test("failed gameplay recovery identifies a missing API key before retry", () => {
  const context = loadReviewBackend(() => ({}));
  const gameplay = {
    lifecycleState: "generation_failed",
    contentState: "failed",
    directory: { status: "pending_generation" },
    chapters: [],
    reviewState: { status: "generation_required" },
  };
  context.$("apiKey").value = "";
  context.state.frames = Array.from({ length: 4 });
  context.state.gameplayReviewGeneration = { status: "failed", failureKind: "system", error: "玩法章节生成失败" };
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { model: { revision: 4, stages: [{ id: "STG-001" }], quality: { qualified: true }, gameplayReviewModel: gameplay }, view: "gameplay_directory" };

  context.renderGameplayDirectoryWorkspace();

  const text = JSON.stringify(context.$("gameplayDirectoryView").children);
  assert.match(text, /当前浏览器未填写 API Key/);
  assert.match(text, /填写 API Key 后重试/);
});

test("confirmed directory with missing details offers a global retry instead of rendering or exporting its skeleton", () => {
  const context = loadReviewBackend(() => ({}));
  const gameplay = {
    lifecycleState: "ready",
    contentState: "failed",
    directory: { status: "confirmed", entries: [{ id: "GDE-001", chapterId: "GCH-001", title: "商店等级" }] },
    chapters: [{ id: "GCH-001", scope: "商店等级", plannerSections: {} }],
    reviewState: { status: "detail_generation_pending", structurePhase: "confirmed" },
  };
  context.$("apiKey").value = "configured-key";
  context.state.gameplayReviewGeneration = { status: "failed", failureKind: "system", error: "服务内部异常" };
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { model: { revision: 4, stages: [{ id: "STG-001" }], gameplayReviewModel: gameplay }, view: "gameplay_directory" };

  context.renderGameplayDirectoryWorkspace();

  const text = JSON.stringify(context.$("gameplayDirectoryView").children);
  assert.match(text, /已确认的 1 个目录章节均已保留/);
  assert.match(text, /继续生成详细规则/);
  assert.doesNotMatch(text, /进入规则审核/);
});

test("an unconfirmed legacy bad directory shows its real structural errors and one regeneration action", () => {
  const context = loadReviewBackend(() => ({}));
  const gameplay = {
    lifecycleState: "generation_required", contentState: "pending", chapters: [{ id: "GCH-001" }],
    reviewState: { status: "generation_required", structureQualityErrors: ["重复机制：建筑", "界面名称被当成机制：收购信息面板"] },
  };
  context.$("apiKey").value = "configured-key";
  context.state.gameplayReviewGeneration = { status: "failed", failureKind: "system", error: "旧任务失败" };
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { model: { revision: 4, gameplayReviewModel: gameplay }, view: "gameplay_directory" };

  context.renderGameplayDirectoryWorkspace();

  const text = JSON.stringify(context.$("gameplayDirectoryView").children);
  assert.match(text, /修复玩法目录/);
  assert.match(text, /重复机制：建筑/);
  assert.match(text, /重新生成正确目录/);
  assert.doesNotMatch(text, /失败原因/);
  assert.doesNotMatch(text, /旧任务失败/);
});

test("failed detail semantic quality stays on P1 with actionable Chinese errors and a regeneration action", () => {
  const context = loadReviewBackend(() => ({}));
  const gameplay = {
    lifecycleState: "ready", contentState: "ready",
    systems: [{ name: "经营系统" }], chapters: [{ id: "GCH-001" }],
    directory: { status: "confirmed" },
    reviewState: { status: "chapter_review", structurePhase: "detailed", depthContractVersion: 2 },
    detailQuality: { passed: false, errors: ["GCH-001:FLOW_CHAIN_STATIC_EVIDENCE_IS_NOT_FLOW"] },
  };
  context.$("apiKey").value = "configured-key";
  context.state.gameplayReviewWorkspace = { model: gameplay };
  context.state.reviewWorkspace = { model: { revision: 4, gameplayReviewModel: gameplay }, view: "gameplay_directory" };

  context.renderGameplayDirectoryWorkspace();

  const text = JSON.stringify(context.$("gameplayDirectoryView").children);
  assert.match(text, /详细规则质量未通过/);
  assert.match(text, /静态画面、数值或公式不能作为玩法流程/);
  assert.doesNotMatch(text, /STATIC_EVIDENCE_IS_NOT_FLOW/);
  assert.match(text, /重新生成详细规则/);
  assert.doesNotMatch(text, /进入规则审核/);
});

test("running gameplay generation shows real progress elapsed time and timeout expectation", () => {
  const context = loadReviewBackend(() => ({}));
  const now = Date.parse("2026-08-25T06:11:41Z");
  const view = context.gameplayGenerationProgressView({
    status: "running",
    progress: 10,
    phase: "requesting_model",
    startedAt: "2026-08-25T06:10:36Z",
    deadlineAt: "2026-08-25T06:15:36Z",
  }, now);

  assert.deepEqual(JSON.parse(JSON.stringify(view)), {
    progress: 10,
    phaseLabel: "正在请求视觉模型",
    elapsedLabel: "已等待 1分05秒",
    timeoutLabel: "超过 5分钟会自动停止并允许重试",
  });

  context.state.gameplayReviewGeneration = {
    status: "running",
    progress: 10,
    phase: "requesting_model",
    startedAt: "2026-08-25T06:10:36Z",
    deadlineAt: "2026-08-25T06:15:36Z",
  };
  context.state.gameplayReviewWorkspace = { model: { lifecycleState: "generation_required", contentState: "pending", chapters: [] } };
  context.state.reviewWorkspace = { model: { revision: 4, stages: [{ id: "STG-001" }] }, view: "gameplay_directory" };
  context.renderGameplayDirectoryWorkspace();

  const text = JSON.stringify(context.$("gameplayDirectoryView").children);
  assert.match(text, /正在请求视觉模型/);
  assert.match(text, /progressbar/);
  assert.match(text, /10%/);
});

test("hidden gameplay recovery never overlays preserved interaction review", () => {
  const css = fs.readFileSync("css/gameplay-review.css", "utf8");
  assert.match(css, /#gameplayDirectoryView\.gameplay-directory-recovery\[hidden\]\s*\{\s*display:\s*none/);
});

test("late URL restoration cannot overwrite a phase selected while canonical models are loading", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("async function syncBackendResult"), backend.indexOf("function renderTimelineWorkbench"));
  assert.match(section, /const requestedViewUiVersion = reviewUiInteractionVersion/);
  assert.match(section, /if \(!requestedView \|\| requestedViewUiVersion !== reviewUiInteractionVersion\) return/);
});

test("explicit P4-P7 deep links stay visible between interaction and gameplay model syncs", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const start = backend.indexOf("const restoreRequestedViewAfterSync");
  const section = backend.slice(start, backend.indexOf("state.gameplayReviewGeneration", start));
  assert.match(section, /await syncCanonicalReviewModel\(state\.reviewClient\)[\s\S]*restoreRequestedViewIfCurrent\(\)[\s\S]*await syncGameplayReviewModel/);
});

test("generated gameplay pages remain inspectable while the separate gameplay client hydrates", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("async function syncBackendResult"), backend.indexOf("function renderTimelineWorkbench"));
  assert.match(section, /state\.gameplayReviewWorkspace \|\|= GameplayWorkspace\.rebuild\([\s\S]*job\.gameplayReviewModel[\s\S]*gameplaySavedUiState\(state\.gameplayReviewClient\)/);
});

test("P1-P7 navigation mirrors the active view into the URL for deterministic refresh", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /function syncReviewViewUrl/);
  const section = backend.slice(backend.indexOf("function bindReviewWorkspace"), backend.indexOf("async function syncBackendResult"));
  assert.match(section, /syncReviewViewUrl\(button\.dataset\.reviewView\)/);
});

test("P7 return-to-edit synchronizes the parameter-review URL before persistence", () => {
  const backendSource = fs.readFileSync("js/backend.js", "utf8");
  const section = backendSource.slice(
    backendSource.indexOf("onBack: () => {", backendSource.indexOf("FinalDocumentPreview.render")),
    backendSource.indexOf("onResolvePending:", backendSource.indexOf("FinalDocumentPreview.render")),
  );
  assert.match(section, /reviewUiInteractionVersion \+= 1[\s\S]*setReviewWorkspaceView\("tables"\)[\s\S]*syncReviewViewUrl\("tables"\)[\s\S]*persistReviewUiState\(\)/);
});

test("P7 incomplete action starts server-side quality repair instead of only navigating away", () => {
  const backendSource = fs.readFileSync("js/backend.js", "utf8");
  const section = backendSource.slice(
    backendSource.indexOf("FinalDocumentPreview.render"),
    backendSource.indexOf("async function loadCombinedFinalPreview"),
  );
  assert.match(section, /onResolveIncomplete:\s*\(\) => \{[\s\S]*previewStatus:\s*"idle"[\s\S]*loadCombinedFinalPreview\(\{ forceServer: true \}\)/);
  assert.doesNotMatch(section, /onResolveIncomplete:\s*\(\) => \{[\s\S]*ReviewWorkspace\.routeForModel\(state\.reviewWorkspace\.model\)/);
});

test("P7 pending decision navigation persists its P4 route", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("function openPendingGameplayDecision"), backend.indexOf("async function reanalyzeReviewFrame"));
  assert.match(section, /reviewUiInteractionVersion \+= 1[\s\S]*setReviewWorkspaceView\("gameplay"\)[\s\S]*syncReviewViewUrl\("gameplay"\)[\s\S]*persistReviewUiState\(\)/);
});

test("pending planner decisions keep downstream impact pages inspectable while export remains gated", () => {
  const backendSource = fs.readFileSync(require("node:path").join(__dirname, "../../js/backend.js"), "utf8");
  assert.match(backendSource, /hasPendingPlannerDecisions/);
  assert.match(backendSource, /decisionImpactViews = new Set\(\["diagrams", "tables", "final_preview"\]\)/);
  assert.match(backendSource, /canInspectDecisionImpacts/);
});

test("P3 preview mirrors its semantic interaction view into the URL after cached or async loading", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const loadSection = backend.slice(backend.indexOf("async function loadReviewPreview"), backend.indexOf("function bindReviewWorkspace"));
  const bindSection = backend.slice(backend.indexOf("function bindReviewWorkspace"), backend.indexOf("async function syncBackendResult"));
  assert.match(loadSection, /resolvedView === ["']interaction_preview["'][\s\S]*syncReviewViewUrl\(resolvedView\)/);
  assert.match(bindSection, /setReviewWorkspaceView\(["']interaction_preview["']\)[\s\S]*syncReviewViewUrl\(["']interaction_preview["']\)/);
});

test("automatic preview loading cannot replace an explicit non-P3 URL", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const loadSection = backend.slice(backend.indexOf("async function loadReviewPreview"), backend.indexOf("function bindReviewWorkspace"));
  const bindSection = backend.slice(backend.indexOf("function bindReviewWorkspace"), backend.indexOf("async function syncBackendResult"));
  assert.match(loadSection, /explicitUrlView = requestedReviewViewFromUrl\(\)[\s\S]*explicitUrlView !== "interaction_preview"[\s\S]*resolvedView/);
  assert.match(bindSection, /syncReviewViewUrl\("interaction_preview"\)[\s\S]*return loadReviewPreview\(\)/);
});

test("saving a later artifact never auto-navigates backward", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("function advanceToCurrentReviewRoute"), backend.indexOf("function makeGameplayOperationQueue"));
  assert.match(section, /const targetView = order\[routedView\] < order\[currentView\] \? currentView : routedView/);
  assert.match(section, /navigateReviewWorkspace\(targetView/);
});

test("workbench URL sync records real browser history and handles popstate", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /history\.pushState\(nextState/);
  assert.match(backend, /window\.addEventListener\("popstate", reviewPopstateHandler\)/);
  assert.match(backend, /linkedJobId !== currentJobId/);
});

test("canonical interaction hydration cannot replace the authoritative gameplay snapshot", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const section = backend.slice(backend.indexOf("async function loadCanonicalReviewModel"), backend.indexOf("async function syncCanonicalReviewModel"));
  assert.match(section, /state\.gameplayReviewWorkspace\?\.model \|\| state\.reviewWorkspace\?\.model\?\.gameplayReviewModel/);
  assert.match(section, /\{ \.\.\.interactionModel, gameplayReviewModel: gameplayModel \}/);
});
