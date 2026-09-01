const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8014").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));
const fixture = path.resolve(option("--fixture"));

async function waitView(page, view) {
  await page.waitForFunction((expected) => document.querySelector("#reviewWorkspace")?.dataset.activeView === expected, view);
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  const results = {};
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console: ${message.text()}`); });
  try {
    await page.goto(`${base}/`, { waitUntil: "domcontentloaded" });
    assert.equal(new URL(page.url()).searchParams.has("job"), false);
    assert.equal(await page.locator("#reviewWorkspace").isHidden(), true);
    await page.screenshot({ path: path.join(output, "UX-TC01-root-new-task.png"), fullPage: false });
    results.root = { url: page.url(), reviewHidden: true };

    await page.goto(`${base}/?job=${job}&ui=gameplay_directory`, { waitUntil: "domcontentloaded" });
    await waitView(page, "gameplay_directory");
    await page.locator('[data-workbench-step="p2"]').click();
    await waitView(page, "flow");
    await page.locator('[data-workbench-step="p3"]').click();
    await waitView(page, "interaction_preview");
    assert.equal(new URL(page.url()).searchParams.get("job"), job);
    await page.goBack({ waitUntil: "domcontentloaded" });
    await waitView(page, "flow");
    assert.equal(new URL(page.url()).searchParams.get("job"), job);
    await page.goBack({ waitUntil: "domcontentloaded" });
    await waitView(page, "gameplay_directory");
    await page.goForward({ waitUntil: "domcontentloaded" });
    await waitView(page, "flow");
    await page.screenshot({ path: path.join(output, "UX-TC21-browser-back-forward.png"), fullPage: false });
    results.browserHistory = { backSequence: ["interaction_preview", "flow", "gameplay_directory"], forward: "flow", jobPreserved: true };

    await page.locator('[data-workbench-step="p7"]').click();
    await waitView(page, "final_preview");
    await page.locator("#finalExportPreviewView .final-document-back").click();
    await waitView(page, "tables");
    await page.goBack({ waitUntil: "domcontentloaded" });
    await waitView(page, "final_preview");
    await page.goForward({ waitUntil: "domcontentloaded" });
    await waitView(page, "tables");
    await page.screenshot({ path: path.join(output, "UX-TC17-p7-return-history.png"), fullPage: false });
    results.finalReturn = { buttonTarget: "tables", browserBack: "final_preview", browserForward: "tables" };

    await page.goto(`${base}/?job=${job}&ui=final_preview`, { waitUntil: "domcontentloaded" });
    await waitView(page, "final_preview");
    await page.screenshot({ path: path.join(output, "UX-TC03-before-new-upload-old-job.png"), fullPage: false });
    await page.locator("#screenshotFolderInput").setInputFiles(fixture);
    await page.waitForFunction(() => document.querySelectorAll(".screenshot-preview-item").length === 2);
    assert.equal(new URL(page.url()).searchParams.has("job"), false);
    assert.equal(await page.locator("#reviewWorkspace").isHidden(), true);
    assert.equal(await page.locator("#fileCount").textContent(), "2");
    await page.screenshot({ path: path.join(output, "UX-TC03-new-upload-detaches-old-job.png"), fullPage: false });
    results.newUploadIsolation = { count: 2, detachedOldJob: true, reviewHidden: true };

    const failedId = "qa-failed-formal";
    const failedJob = {
      id: failedId,
      status: "failed",
      progress: 0,
      stage: "分析未通过",
      error: "视觉模型连接失败：2/2 个请求未完成",
      metadata: { inputType: "image_sequence", projectName: "失败任务工作台验收", mode: "interaction" },
      frames: [1, 2].map((index) => ({ id: `F000${index}`, sequenceIndex: index, sceneId: index - 1, imageUrl: "/missing.jpg", sourceName: `${index}.jpg`, analysis: {} })),
      scenes: [],
      analysisSummary: { detailFrameCount: 2, qualifiedDetailFrameCount: 0, modelEnabled: true },
    };
    let failedStatus = failedJob;
    await page.route(`**/api/jobs/${failedId}`, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(failedStatus) }));
    await page.route("**/missing.jpg", (route) => route.fulfill({ status: 200, contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640"><rect width="100%" height="100%" fill="#eef2ff"/></svg>' }));
    await page.goto(`${base}/?job=${failedId}`, { waitUntil: "domcontentloaded" });
    await page.screenshot({ path: path.join(output, "UX-TC04-failed-history-card-entry.png"), fullPage: false });
    await page.getByRole("button", { name: "进入工作台", exact: true }).click();
    await waitView(page, "analysis_failed");
    await page.screenshot({ path: path.join(output, "UX-TC04-failed-workbench-opened.png"), fullPage: false });
    let retryRequests = 0;
    let resolveRetry;
    const retryObserved = new Promise((resolve) => { resolveRetry = resolve; });
    await page.route(`**/api/jobs/${failedId}/retry`, async (route) => {
      retryRequests += 1;
      resolveRetry();
      failedStatus = { ...failedJob, status: "queued", stage: "等待重试", error: "" };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(failedStatus) });
    });
    await page.locator("#apiKey").fill("qa-retry-key");
    await page.evaluate(() => document.querySelector("#analysisFailedRetryBtn").click());
    await retryObserved;
    assert.equal(retryRequests, 1);
    await page.waitForFunction(() => document.body.innerText.includes("等待重试") || document.body.innerText.includes("任务已重新开始"));
    await page.screenshot({ path: path.join(output, "UX-TC05-failed-retry-same-job.png"), fullPage: false });
    failedStatus = failedJob;
    await page.goto(`${base}/?job=${failedId}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "进入工作台", exact: true }).click();
    await waitView(page, "analysis_failed");
    await page.getByRole("button", { name: "返回素材", exact: true }).click();
    assert.equal(await page.locator("#reviewWorkspace").isHidden(), true);
    await page.getByRole("button", { name: "进入工作台", exact: true }).click();
    await waitView(page, "analysis_failed");
    await page.screenshot({ path: path.join(output, "UX-TC04-TC05-failed-workbench-return.png"), fullPage: false });
    results.failedWorkbench = { enterAllowed: true, returnAssets: true, reenterAllowed: true, retryVisible: true, retryRequests, retryJobId: failedId };

    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "return-matrix.json"), JSON.stringify({ passed: true, results, errors }, null, 2));
    console.log(JSON.stringify({ passed: true, results }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
