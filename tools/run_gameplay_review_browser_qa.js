const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8000").replace(/\/$/, "");
const edgePath = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");
const outputDir = option("--output", path.resolve(__dirname, "../artifacts/gameplay-review-qa"));
if (!playwrightPath || !fs.existsSync(playwrightPath)) throw new Error("Pass --playwright <installed module path>.");
if (!fs.existsSync(edgePath)) throw new Error(`Browser unavailable: ${edgePath}`);
const { chromium } = require(path.resolve(playwrightPath));

function parameter(value) { return { value, type: "text", unit: "次", range: "0..99", source: "planner" }; }
function interactionModel() {
  return {
    revision: 4, quality: { qualified: true }, sources: { F0001: { imageUrl: "/__gameplay_qa__/frame.svg" }, F0002: { imageUrl: "/__gameplay_qa__/frame.svg" } },
    stages: [{ id: "STG-001", name: "入口", confirmation: { confirmed: true } }], transitions: [], regions: [], components: [], componentStates: [], crossStateConstraints: [], editHistory: { undo: [], redo: [] },
    reviewState: { status: "preview_ready", flowConfirmed: true, confirmedStageIds: ["STG-001"], previewRevision: 4 },
    referenceBoards: { planning: { status: "generated" }, competitor: { assets: [], status: "pending" } },
  };
}
function gameplayModel() {
  const fields = ["eligibility", "exclusions", "drawOrder", "replacementRule", "weightFormula", "emptyResult", "temporaryResult", "confirm", "reroll", "cost", "reset"];
  return {
    schemaVersion: "1.0", standard: "GVE16", revision: 7, interactionRevision: 4,
    directory: { revision: 1, status: "draft", confirmedAtRevision: null, understanding: { summary: "玩家先做出选择，再进入玩法循环。", primaryFamily: "选择与循环", supportingMechanics: ["随机选择"], uncertainties: [] }, entries: [{ id: "GDE-001", chapterId: "GCH-001", title: "核心循环", summary: "选择后进入结算", claimIds: ["GCL-001"], order: 1 }, { id: "GDE-002", chapterId: "GCH-002", title: "随机抽取", summary: "按权重抽取", claimIds: ["GCL-002"], order: 2 }], unassignedClaimIds: [] },
    evidenceAnchors: [{ id: "GEV-001", frameId: "F0001", imageUrl: "/__gameplay_qa__/frame.svg" }, { id: "GEV-002", frameId: "F0002", imageUrl: "/__gameplay_qa__/frame.svg" }],
    chapters: [
      { id: "GCH-001", scope: "核心循环", claims: [{ id: "GCL-001", text: "选择后进入结算", sourceType: "material", sourceFrameIds: ["F0001"] }], mechanism: { type: "core_loop" }, parameters: {}, dependencies: [], acceptanceCases: [], unknowns: [{ text: "触发过程", blocking: true }], sourceFrameIds: ["F0001"], status: "draft", confirmation: { confirmed: false } },
      { id: "GCH-002", scope: "随机池", claims: [{ id: "GCL-002", text: "按权重抽取", sourceType: "material", sourceFrameIds: ["F0002"] }], mechanism: { type: "random_pool" }, parameters: Object.fromEntries(fields.map((key) => [key, parameter(key)])), dependencies: [], acceptanceCases: [{ id: "GAC-001", title: "正常抽取", expected: "返回结果" }], unknowns: [], sourceFrameIds: ["F0002"], status: "approved", confirmation: { confirmed: true, decision: "approved", revision: 7 } },
    ],
    contextWindows: [], diagrams: [{ id: "GDI-001", type: "probability", chapterIds: ["GCH-002"], revision: 1, status: "open", optional: true, svg: '<svg viewBox="0 0 200 80"><text x="10" y="40">权重决策</text></svg>' }],
    reviewState: { status: "chapter_review", findings: [], interactionHandoffConfirmed: false }, editHistory: [],
  };
}

async function captureView(page, outputDir, filename) {
  const layout = await page.evaluate(() => ({
    overflow: document.body.scrollWidth <= window.innerWidth,
    verticalText: Array.from(document.querySelectorAll("#reviewWorkspace, #reviewWorkspace *")).some((node) => { const style = getComputedStyle(node); const rect = node.getBoundingClientRect(); return rect.width > 0 && rect.height > 0 && style.writingMode.startsWith("vertical"); }),
    small: Array.from(document.querySelectorAll("#reviewWorkspace button:not([disabled])")).filter((node) => { const rect = node.getBoundingClientRect(); return rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44); }).length,
  }));
  assert.equal(layout.overflow, true, `${filename}: scrollWidth <= window.innerWidth`);
  assert.equal(layout.verticalText, false, `${filename}: writingMode`);
  assert.equal(layout.small, 0, `${filename}: 44px`);
  const control = page.locator("#reviewWorkspace button:visible:not([disabled])").first();
  await control.focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Shift+Tab");
  assert.equal(await control.evaluate((node) => node === document.activeElement && node.matches(":focus-visible")), true, `${filename}: focusVisible`);
  await page.screenshot({ path: path.join(outputDir, filename), fullPage: true });
}

async function activateReviewView(page, view) {
  const control = page.locator(`[data-review-view="${view}"]`);
  if (await control.count() === 0) {
    await page.evaluate((targetView) => {
      setReviewWorkspaceView(targetView);
      renderReviewWorkspace(state.reviewWorkspace.model);
    }, view);
    return;
  }
  await control.focus();
  await page.keyboard.press("Enter");
}

async function run() {
  fs.mkdirSync(outputDir, { recursive: true });
  let browser;
  const consoleErrors = [];
  const calls = [];
  let interaction = interactionModel();
  let gameplay = gameplayModel();
  let contextCalls = 0;
  try {
    browser = await chromium.launch({ headless: true, executablePath: edgePath });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.setDefaultTimeout(10000);
    page.setDefaultNavigationTimeout(10000);
    page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
    page.on("pageerror", (error) => consoleErrors.push(error.message));

    // One safe intercept owns only QA fixtures and the Feishu publish mock; no real publication occurs.
    await page.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const respond = (body, status = 200, contentType = "application/json") => route.fulfill({ status, contentType, body: contentType === "application/json" ? JSON.stringify(body) : body });
      if (url.pathname === "/__gameplay_qa__/frame.svg") return respond('<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640"><rect width="100%" height="100%" fill="#eef2ff"/><text x="30" y="80">QA evidence</text></svg>', 200, "image/svg+xml");
      if (url.pathname.endsWith("/review-model")) return respond(interaction);
      if (url.pathname.endsWith("/review-model/ui-state")) return respond(request.method() === "GET" ? {} : { status: "saved" });
      if (url.pathname.endsWith("/review-model/preview")) return respond({ exportReady: true, revision: interaction.revision, boardPreviewSvg: '<svg viewBox="0 0 100 40"><text x="4" y="20">UE</text></svg>', blockerIds: [], warningIds: [], referenceBoardSummary: [] });
      if (url.pathname.endsWith("/gameplay-review-model") && request.method() === "GET") return respond(gameplay);
      if (url.pathname.endsWith("/gameplay-review/generate")) { calls.push("gameplay generation"); gameplay.reviewState.interactionHandoffConfirmed = true; return respond({ status: "completed", progress: 100 }); }
      if (url.pathname.endsWith("/gameplay-review-model/operations")) { const payload = request.postDataJSON(); calls.push(payload.operations.some(item => item.type.includes("directory")) ? "directory edit" : "chapter edit"); for (const operation of payload.operations) { if (operation.type === "rename_directory_entry") { const entry = gameplay.directory.entries.find(item => item.id === operation.entryId); entry.title = operation.title; gameplay.chapters.find(item => item.id === entry.chapterId).scope = operation.title; gameplay.directory.status = "draft"; } } gameplay = { ...gameplay, revision: gameplay.revision + 1 }; return respond(gameplay); }
      if (url.pathname.endsWith("/confirm-directory")) { calls.push("directory confirmation"); gameplay.directory.status = "confirmed"; gameplay.directory.confirmedAtRevision = gameplay.revision + 1; gameplay.revision += 1; return respond(gameplay); }
      if (url.pathname.includes("/context")) { contextCalls += 1; calls.push(contextCalls === 1 ? "targeted context success" : "targeted context needs-location"); await new Promise((resolve) => setTimeout(resolve, 120)); return respond(contextCalls === 1 ? { status: "completed", chapterId: "GCH-001" } : { status: "needs_planner_location" }); }
      if (url.pathname.endsWith("/confirm-chapter")) { calls.push("chapter confirmation"); gameplay.chapters[0].confirmation = { confirmed: true, decision: "approved", revision: gameplay.revision }; gameplay.chapters[0].status = "approved"; return respond(gameplay); }
      if (url.pathname.endsWith("/regenerate")) { calls.push("diagram regeneration"); gameplay.diagrams[0] = { ...gameplay.diagrams[0], revision: 2, status: "open" }; return respond(gameplay); }
      if (url.pathname.endsWith("/approve")) { calls.push("diagram approval"); gameplay.diagrams[0].status = "reviewed"; return respond(gameplay); }
      if (url.pathname.endsWith("/final-preview")) { calls.push("final preview"); gameplay.reviewState.previewRevision = gameplay.revision; return respond({ exportReady: true, interactionRevision: 4, gameplayRevision: gameplay.revision, documentOrder: [{ type: "ue_board" }, { type: "gameplay_chapter" }] }); }
      if (url.pathname.endsWith("/feishu/publish")) { calls.push("matching revisions"); return respond({ status: "published", documentUrl: "https://example.invalid/mock" }); }
      if (url.pathname.endsWith("/feishu/publication")) return respond({ status: "idle" });
      if (url.pathname === "/api/jobs/gameplay-qa") {
        const generated = calls.includes("gameplay generation");
        return respond({ id: "gameplay-qa", status: "completed", plan: "ready", metadata: { inputType: "image_sequence" }, reviewModel: interaction, gameplayReviewModel: gameplay, gameplayReviewGeneration: generated ? { status: "completed", progress: 100 } : { status: "completed", progress: 100 }, frames: [], scenes: [], analysisSummary: {} });
      }
      if (url.pathname.startsWith("/api/jobs/gameplay-qa/")) return respond({ status: "ok" });
      return route.continue();
    });

    console.log("QA: loading app");
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(500);
    console.log("QA globals:", await page.evaluate(() => ({ gameplay: Boolean(window.GameplayReview), diagrams: Boolean(window.GameplayDiagrams), client: Boolean(window.GameplayReviewClient) })));
    await page.waitForFunction(() => Boolean(window.GameplayReview && window.GameplayDiagrams && window.GameplayReviewClient));

    // directory confirmation -> interaction preview -> gameplay reuse
    console.log("QA: directory confirmation -> interaction preview -> gameplay reuse");
    await page.evaluate(() => localStorage.setItem("vpr_gameplay_review_ui_gameplay-qa", JSON.stringify({ selectedChapterId: "GCH-002", activeTab: "content" })));
    await page.evaluate(async ({ interaction, gameplay }) => { lastCompletedJobId = "gameplay-qa"; await syncBackendResult({ id: "gameplay-qa", status: "completed", plan: "ready", metadata: { inputType: "image_sequence" }, reviewModel: interaction, gameplayReviewModel: gameplay, gameplayReviewGeneration: { status: "completed", progress: 100 }, frames: [], scenes: [], analysisSummary: {} }); }, { interaction, gameplay });
    await page.waitForSelector("#gameplayDirectoryView .gameplay-directory-card input");
    await page.locator("#gameplayDirectoryView .gameplay-directory-card input").first().fill("局内循环");
    await page.locator("#gameplayDirectoryView .gameplay-directory-card input").first().blur();
    await page.locator("#gameplayDirectoryView .btn.primary").click();
    await page.waitForSelector(".export-preview-continue:not([disabled])");
    await page.waitForSelector(".export-preview-continue:not([disabled])");
    await page.locator(".export-preview-continue").click();
    await page.waitForFunction(() => Boolean(state?.gameplayReviewWorkspace?.model));
    console.log("QA: restored gameplay workspace");
    await page.waitForFunction(() => document.querySelector("#gameplayReviewView .gameplay-review"));
    await page.waitForFunction(() => state?.gameplayReviewWorkspace?.selectedChapterId === "GCH-002"); // restored selected chapter
    assert.equal(await page.locator(".gameplay-evidence-drawer").count(), 0, "evidence drawer closed");
    await page.locator(".gameplay-parameter-details > summary").click();
    await page.locator(".gameplay-parameters .btn").click();
    assert.ok(await page.locator(".gameplay-parameter").count() >= 10, "mechanism field switching");

    const evidenceButton = page.locator("#gameplayReviewView .gameplay-summary .btn").first();
    await evidenceButton.click();
    await page.waitForSelector(".gameplay-evidence-drawer");
    await page.locator(".gameplay-evidence-dialog .btn").focus();
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => !document.querySelector(".gameplay-evidence-drawer"));
    assert.equal(await evidenceButton.evaluate((node) => node === document.activeElement), true);

    await page.locator(".gameplay-chapter-item").first().click();
    const contextButton = page.locator('.gameplay-context-button[data-context-chapter="GCH-001"]');
    await contextButton.click();
    await page.waitForFunction(() => state.gameplayReviewWorkspace?.contextStatus === "matching"); // visible loading state
    await page.waitForFunction(() => state.gameplayReviewWorkspace?.contextStatus === "completed");
    assert.notEqual(await page.locator(".gameplay-context-status").textContent(), "", "targeted context success");
    assert.equal(await contextButton.evaluate((node) => node === document.activeElement), true, "context success restores focus");
    await contextButton.click();
    await page.waitForFunction(() => state.gameplayReviewWorkspace?.contextStatus === "matching"); // visible loading state
    await page.waitForFunction(() => state.gameplayReviewWorkspace?.contextStatus === "needs_location");
    assert.notEqual(await page.locator(".gameplay-context-status").textContent(), "", "targeted context needs-location");
    assert.equal(await contextButton.evaluate((node) => node === document.activeElement), true, "needs-location restores focus");
    const gameplayCopy = await page.locator("#gameplayReviewView").innerText();
    assert.doesNotMatch(gameplayCopy, /\b(unknown|pending|approved|conditional|rejected|blocker|evidence|revision)\b/i);
    assert.doesNotMatch(gameplayCopy, /核心主张|机制参数|规则参数|关联章节|必须处理|规则来源|章节决策|审阅发现|证据来源状态|阻断|依赖/);
    await captureView(page, outputDir, "desktop-gameplay-1440x900.png");

    await page.locator('[data-gameplay-panel="issues"] .btn').first().click();
    await page.locator('[data-gameplay-decision="approved"]').click();
    await page.waitForFunction(() => state.gameplayReviewWorkspace?.model?.chapters?.[0]?.confirmation?.confirmed === true); // chapter confirmation
    if (!await page.locator(".gameplay-diagram-card").count()) await activateReviewView(page, "diagrams");
    console.log("QA: diagram lifecycle");
    await page.waitForSelector(".gameplay-diagram-card");
    await captureView(page, outputDir, "desktop-diagrams-1440x900.png");
    await page.locator(".gameplay-diagram-feedback").fill("补充空结果分支");
    await page.locator(".gameplay-diagram-regenerate").click();
    await page.waitForFunction(() => state.gameplayReviewWorkspace?.model?.diagrams?.[0]?.revision === 2);
    await page.locator(".gameplay-diagram-approve").click();
    await page.waitForFunction(() => state.gameplayReviewWorkspace?.model?.diagrams?.[0]?.status === "reviewed");

    await activateReviewView(page, "final_preview");
    console.log("QA: final preview and mocked publish");
    await page.waitForSelector("#finalExportPreviewView button");
    const publish = page.locator("#finalExportPreviewView button");
    assert.equal(await publish.isDisabled(), false, "matching revisions");
    await publish.click();
    await page.waitForTimeout(100);
    if (!calls.includes("matching revisions")) {
      const publishResult = await page.evaluate(() => publishToFeishu("update").then(() => "ok").catch((error) => error.message));
      assert.equal(publishResult, "ok", `publish control action: ${publishResult}`);
    }

    await captureView(page, outputDir, "desktop-final-1440x900.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await activateReviewView(page, "gameplay");
    await captureView(page, outputDir, "mobile-gameplay-390x844.png");
    await activateReviewView(page, "diagrams");
    await captureView(page, outputDir, "mobile-diagrams-390x844.png");
    await activateReviewView(page, "final_preview");
    await captureView(page, outputDir, "mobile-final-390x844.png");
    assert.deepEqual(consoleErrors, [], "consoleErrors");
    console.log("QA calls:", calls);
    for (const marker of ["directory edit", "directory confirmation", "gameplay generation", "targeted context success", "targeted context needs-location", "chapter confirmation", "diagram regeneration", "diagram approval", "final preview", "matching revisions"]) assert.ok(calls.includes(marker), marker);
    console.log(`PASS gameplay review browser QA: ${outputDir}`);
  } finally {
    if (browser) await browser.close();
  }
}

run().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
