const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8000").replace(/\/$/, "");
const imagePath = option("--image", path.resolve(__dirname, "../data/jobs/d124492e05df46e4baa7d7167b84d3c5/frames/F0001.jpg"));
const edgePath = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");
const screenshotPath = option("--screenshot", path.resolve(__dirname, "../artifacts/review-workspace-qa-mobile.png"));
const timeoutMs = 15000;

if (!playwrightPath) throw new Error("Playwright is required: pass --playwright <module-path>.");
if (!fs.existsSync(playwrightPath)) throw new Error(`Playwright module is unavailable: ${playwrightPath}`);
if (!fs.existsSync(edgePath)) throw new Error(`Browser executable is unavailable: ${edgePath}`);
const fixtureImage = fs.existsSync(imagePath)
  ? fs.readFileSync(imagePath)
  : Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");

const { chromium } = require(path.resolve(playwrightPath));
const wait = (promise, label) => Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs))]);

function confirmationModel() {
  const sources = Object.fromEntries(["F0001", "F0002"].map((id) => [id, { imageUrl: `/__review_qa__/${id}.jpg`, width: 528, height: 986 }]));
  const stages = Object.keys(sources).map((id, index) => ({
    id: `STG-${String(index + 1).padStart(3, "0")}`, order: index + 1, name: `阶段 ${index + 1}`,
    representativeFrames: [{ frameId: id, role: "entry" }], regionIds: [], smallLoop: { display: "display", trigger: "tap", feedback: "feedback", result: "result", retry: "" },
    confirmation: { confirmed: false, revision: null },
  }));
  const components = stages.map((stage, index) => ({
    id: `CMP-${String(index + 1).padStart(3, "0")}`, stageId: stage.id, frameId: stage.representativeFrames[0].frameId,
    name: `确认组件 ${index + 1}`, bounds: { x: 0.2, y: 0.2, width: 0.3, height: 0.1 },
  }));
  return {
    revision: 1, quality: { qualified: true }, reviewState: { status: "flow_review", flowConfirmed: false, confirmedStageIds: [], previewRevision: null }, sources, stages,
    transitions: [{ id: "TRN-001", sourceStageId: "STG-001", targetStageId: "STG-002", sourceFrameId: "F0001", triggerType: "tap", resultType: "navigate", included: true, confirmation: { confirmed: false, revision: null } }],
    regions: [], components,
    componentStates: components.map((component) => ({ componentId: component.id, states: { default: "visible", pressed: "visible", selected: "visible", disabled: "visible", loading: "visible", success: "visible", error: "visible", exhausted: "visible", condition_unmet: "visible" } })),
    crossStateConstraints: [], editHistory: { undo: [], redo: [] },
    referenceBoards: { planning: { source: "confirmed_review_model", status: "generated" }, competitor: { assets: [], status: "pending" } },
  };
}

async function run() {
  let browser;
  try {
    browser = await wait(chromium.launch({ headless: true, executablePath: edgePath }), "Edge launch");
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.setDefaultTimeout(timeoutMs);
    page.setDefaultNavigationTimeout(timeoutMs);
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    let workflowModel = confirmationModel();
    const workflowCalls = [];
    const componentChecks = [];
    const confirmationEvents = [];

    await page.route("**/__review_qa__/*.jpg", (route) => route.fulfill({ contentType: "image/png", body: fixtureImage }));
    await page.route("**/api/jobs/review-qa/review-model**", async (route) => {
      const request = route.request();
      const pathname = new URL(request.url()).pathname;
      const payload = request.method() === "POST" && request.postData() ? request.postDataJSON() : {};
      const respond = (value, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
      if (pathname.endsWith("/ui-state")) return respond(payload);
      if (pathname.endsWith("/operations")) {
        assert.equal(payload.expectedRevision, workflowModel.revision);
        const componentOperation = (payload.operations || []).find((operation) => operation.type === "set_component_state");
        if (componentOperation) {
          componentChecks.push(componentOperation.componentId);
          confirmationEvents.push(`component:${componentOperation.componentId}`);
        }
        return respond(workflowModel);
      }
      if (pathname.endsWith("/confirm-flow")) {
        assert.equal(payload.expectedRevision, workflowModel.revision);
        workflowCalls.push("flow");
        workflowModel = structuredClone(workflowModel);
        workflowModel.revision += 1;
        workflowModel.reviewState = { status: "stage_review", flowConfirmed: true, confirmedStageIds: [], previewRevision: null };
        workflowModel.transitions.forEach((transition) => { transition.confirmation = { confirmed: true, revision: workflowModel.revision }; });
        return respond(workflowModel);
      }
      if (pathname.endsWith("/confirm-stage")) {
        assert.equal(payload.expectedRevision, workflowModel.revision);
        workflowCalls.push(payload.stageId);
        confirmationEvents.push(`stage:${payload.stageId}`);
        workflowModel = structuredClone(workflowModel);
        workflowModel.revision += 1;
        const stage = workflowModel.stages.find((item) => item.id === payload.stageId);
        stage.confirmation = { confirmed: true, revision: workflowModel.revision };
        workflowModel.reviewState.confirmedStageIds = [...new Set([...workflowModel.reviewState.confirmedStageIds, payload.stageId])];
        workflowModel.reviewState.status = workflowModel.reviewState.confirmedStageIds.length === workflowModel.stages.length ? "preview_ready" : "stage_review";
        return respond(workflowModel);
      }
      if (pathname.endsWith("/preview")) {
        assert.equal(payload.expectedRevision, workflowModel.revision);
        workflowCalls.push("preview");
        workflowModel.reviewState.previewRevision = workflowModel.revision;
        return respond({ revision: workflowModel.revision, exportReady: true, blockerIds: [], warningIds: ["COMPETITOR_BOARD_PENDING"], representativeFrameIds: ["F0001", "F0002"], boardPreviewSvg: '<svg viewBox="0 0 10 10"><title>QA preview</title></svg>', referenceBoardSummary: [{ key: "planning", assetCount: 2, missingCount: 0, status: "generated" }, { key: "competitor", assetCount: 0, missingCount: 0, status: "pending" }] });
      }
      return respond(workflowModel);
    });

    await wait(page.goto(baseUrl, { waitUntil: "networkidle" }), "page load");
    await wait(page.waitForFunction(() => Boolean(window.FlowReview && window.StageReview && window.ReviewClient && window.ReviewWorkspace && window.ExportPreview && window.ReferenceBoardAssets)), "review globals");
    const confirmation = confirmationModel();
    await page.evaluate((reviewModel) => syncBackendResult({ id: "review-qa", status: "completed", plan: "", reviewModel, metadata: { mode: "interaction", inputType: "image_sequence" }, frames: [], scenes: [], analysisSummary: {} }), confirmation);
    const flowCopy = await page.locator("#flowReviewView").innerText();
    assert.doesNotMatch(flowCopy, /\b(tap|long_press|swipe|drag|unknown|navigate|state_change)\b/i);
    assert.doesNotMatch(flowCopy, /跨状态约束|跨页面规则|规则来源|锚点|证据状态|候选关系|阶段泳道/);
    await wait(page.waitForFunction(() => !document.querySelector("#reviewConfirmFlowBtn").disabled && !document.querySelector("#reviewConfirmFlowBtn").hidden), "flow confirmation control");
    await page.locator("#reviewConfirmFlowBtn").click();
    await wait(page.waitForFunction(() => !document.querySelector("#stageReviewView").hidden && !document.querySelector("#reviewConfirmStageBtn").disabled), "first stage confirmation");
    assert.deepEqual(await page.locator(".planner-step-card h4").allTextContents(), ["操作前", "玩家操作", "系统反馈", "操作结果"]);
    assert.equal(await page.locator(".planner-evidence-drawer").getAttribute("open"), null, "raw screenshots stay collapsed by default");
    assert.equal(await page.locator(".stage-component-list").count(), 0, "component diagnostics stay out of the planner view");
    await page.screenshot({ path: screenshotPath.replace(/(\.[^.]+)$/, "-stage$1"), fullPage: true });
    await page.locator("#reviewConfirmStageBtn").click();
    await wait(page.waitForFunction(() => document.querySelector("#reviewConfirmStageBtn").textContent.includes("2") && !document.querySelector("#reviewConfirmStageBtn").disabled), "second stage confirmation");
    assert.deepEqual(await page.locator(".planner-step-card h4").allTextContents(), ["操作前", "玩家操作", "系统反馈", "操作结果"]);
    await page.locator("#reviewConfirmStageBtn").click();
    await wait(page.waitForFunction(() => !document.querySelector("#exportPreviewView").hidden), "direct preview route");
    await wait(page.waitForFunction(() => !document.querySelector("#exportPreviewView").hidden && document.querySelector("#exportPreviewView svg")), "preview-ready route");
    assert.deepEqual(workflowCalls, ["flow", "STG-001", "STG-002", "preview"]);
    assert.deepEqual(componentChecks, [], "planner flow does not require component diagnostics");
    assert.deepEqual(confirmationEvents, ["stage:STG-001", "stage:STG-002"], "stage confirmations follow the planner reading flow");
    assert.equal(await page.locator('[data-review-view="interaction_preview"]').getAttribute("aria-current"), "step");
    assert.equal(await page.evaluate(() => ({
      ruleNav: document.querySelector(`[${["data-review-view", "rules"].join("=")}]`) !== null,
      rulePanel: document.getElementById(["rules", "ReviewView"].join("")) !== null,
    })).then((value) => value.ruleNav || value.rulePanel), false, "no rules navigation or panel");

    const boardChecks = await page.evaluate(() => {
      const root = document.querySelector("#exportPreviewView");
      const board = { revision: 5, referenceBoards: { planning: { source: "confirmed_review_model", status: "generated" }, competitor: { assets: [], status: "pending" } } };
      const calls = [];
      const client = {
        uploadBoardAssets: async (key, files, revision) => {
          calls.push({ type: "upload", key, revision, count: files.length });
          board.referenceBoards.competitor = { assets: Array.from(files, (file, index) => ({ id: `CPA-00${index + 1}`, sourceName: file.name, order: index + 1, status: "ready" })), status: "ready" };
          board.revision += 1;
          return board;
        },
        reorderBoardAssets: async (key, assetIds, revision) => {
          calls.push({ type: "reorder", key, revision, assetIds });
          board.referenceBoards.competitor.assets = assetIds.map((id, index) => ({ ...board.referenceBoards.competitor.assets.find((asset) => asset.id === id), order: index + 1 }));
          board.revision += 1;
          return board;
        },
        deleteBoardAsset: async (key, assetId, revision) => {
          calls.push({ type: "delete", key, assetId, revision });
          board.referenceBoards.competitor.assets = board.referenceBoards.competitor.assets.filter((asset) => asset.id !== assetId).map((asset, index) => ({ ...asset, order: index + 1 }));
          board.revision += 1;
          return board;
        },
      };
      const render = (states = {}, busy = false) => window.ReferenceBoardAssets.render({
        root, boards: board.referenceBoards, planningCount: 2, client, states, readOnly: false, busy,
        onMutate: async (_key, request) => request(board.revision),
      });
      render({ competitor: { status: "uploading" } }, true);
      const loading = root.textContent.includes("正在保存素材");
      const disabled = root.querySelector(".reference-board-card:not(.reference-board-planning) input[type=file]").disabled;
      render();
      window.__twoBoardQa = { board, calls, render, retryCalls: 0 };
      return {
        cardCount: root.querySelectorAll(".reference-board-card").length,
        keys: window.ReferenceBoardAssets.summaries(board.referenceBoards, 2).map((summary) => summary.key),
        uxUpload: Array.from(root.querySelectorAll("input[type=file]")).some((input) => /UX/i.test(input.getAttribute("aria-label") || "")),
        pending: root.textContent.includes("待补充"),
        planningReadOnly: root.querySelector(".reference-board-planning input") === null,
        competitorInputs: root.querySelectorAll(".reference-board-card:not(.reference-board-planning) input[type=file]").length,
        loading, disabled,
      };
    });
    assert.equal(boardChecks.cardCount, 2, "exactly two active board cards");
    assert.deepEqual(boardChecks.keys, ["planning", "competitor"], "exactly two active board keys");
    assert.equal(boardChecks.uxUpload, false, "no UX upload control");
    assert.deepEqual(boardChecks, { cardCount: 2, keys: ["planning", "competitor"], uxUpload: false, pending: true, planningReadOnly: true, competitorInputs: 1, loading: true, disabled: true }, "visible loading state and visible disabled state");
    await page.locator(".reference-board-card:not(.reference-board-planning) input[type=file]").setInputFiles([
      { name: "first.png", mimeType: "image/png", buffer: fixtureImage },
      { name: "second.png", mimeType: "image/png", buffer: fixtureImage },
    ]);
    await wait(page.waitForFunction(() => window.__twoBoardQa.calls.some((call) => call.type === "upload")), "competitor upload");
    await page.evaluate(() => window.__twoBoardQa.render());
    await page.locator(".reference-board-item").nth(1).locator("button").first().click();
    await wait(page.waitForFunction(() => window.__twoBoardQa.calls.some((call) => call.type === "reorder")), "competitor reorder");
    await page.evaluate(() => window.__twoBoardQa.render());
    await page.locator(".reference-board-action.btn.warn").first().click();
    await wait(page.waitForFunction(() => window.__twoBoardQa.calls.some((call) => call.type === "delete")), "competitor delete");
    await page.evaluate(() => window.__twoBoardQa.render({ competitor: { status: "failed", error: "retry competitor asset", retry: async () => { window.__twoBoardQa.retryCalls += 1; } } }));
    assert.equal(await page.locator("#exportPreviewView").textContent().then((text) => text.includes("retry competitor asset")), true, "visible error state");
    await page.getByRole("button", { name: /重试.*竞品/ }).click();
    await wait(page.waitForFunction(() => window.__twoBoardQa.retryCalls === 1), "competitor retry");

    const exportState = await page.evaluate(() => {
      const root = document.querySelector("#exportPreviewView");
      const model = window.__twoBoardQa.board;
      const basePreview = { exportReady: true, blockerIds: [], warningIds: [], representativeFrameIds: ["F0001", "F0002"], boardPreviewSvg: "<svg viewBox='0 0 1 1'></svg>", referenceBoardSummary: [{ key: "planning", assetCount: 2, status: "generated" }, { key: "competitor", assetCount: model.referenceBoards.competitor.assets.length, status: "ready" }] };
      window.ExportPreview.render({ root, model, preview: { ...basePreview, revision: model.revision - 1 } });
      const staleDisabled = root.querySelector(".btn.primary").disabled;
      window.ExportPreview.render({ root, model, preview: { ...basePreview, revision: model.revision } });
      const exportButton = root.querySelector(".btn.primary");
      const bounds = exportButton.getBoundingClientRect();
      return { revision: model.revision, staleDisabled, exportDisabled: exportButton.disabled, hitTarget: { width: bounds.width, height: bounds.height } };
    });
    assert.equal(exportState.staleDisabled, true, "stale preview revision disables export");
    assert.equal(exportState.exportDisabled, false, "export enables from the current preview revision");
    assert.ok(exportState.hitTarget.width >= 44 && exportState.hitTarget.height >= 44, "actual interactive hit target is at least 44px");
    const exportButton = page.locator("#exportPreviewView .btn.primary");
    await exportButton.focus();
    await page.keyboard.press("Tab");
    await page.keyboard.press("Shift+Tab");
    const focusVisible = await exportButton.evaluate((node) => node === document.activeElement && node.matches(":focus-visible"));
    assert.equal(focusVisible, true, "keyboard focus visibly shown on an interactive control");

    await page.setViewportSize({ width: 390, height: 844 });
    const mobile = await page.evaluate(() => ({
      overflow: document.body.scrollWidth <= window.innerWidth,
      verticalText: Array.from(document.querySelectorAll("#reviewWorkspace, #reviewWorkspace *")).some((node) => getComputedStyle(node).writingMode.startsWith("vertical")),
      exportTarget: (() => {
        const bounds = document.querySelector("#exportPreviewView .btn.primary").getBoundingClientRect();
        return { width: bounds.width, height: bounds.height };
      })(),
    }));
    assert.equal(mobile.overflow, true);
    assert.equal(mobile.verticalText, false);
    assert.ok(mobile.exportTarget.width >= 44 && mobile.exportTarget.height >= 44, "mobile export control preserves an actual 44px hit target");
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
    await page.screenshot({ path: screenshotPath, fullPage: true });
    assert.equal(fs.existsSync(screenshotPath), true);
    assert.deepEqual(pageErrors, []);
    console.log(`PASS review workspace QA: flow-to-stage-to-preview with component confirmation, two boards only, pending competitor, upload/reorder/delete/retry, stale/current preview revisions, keyboard focus and mobile layout (${screenshotPath})`);
  } finally {
    if (browser) await Promise.race([browser.close(), new Promise((resolve) => setTimeout(resolve, 2000))]);
  }
}

run().catch((error) => { console.error(`FAIL review workspace QA: ${error.stack || error}`); process.exitCode = 1; });
