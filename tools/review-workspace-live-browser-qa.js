const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8000").replace(/\/$/, "");
const jobId = option("--job", "final-review-live-qa");
const imagePath = option("--image");
const edgePath = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");
const screenshotPath = option("--screenshot", path.resolve(__dirname, "../artifacts/review-workspace-live-qa.png"));
const timeoutMs = 20000;

if (!playwrightPath || !fs.existsSync(playwrightPath)) throw new Error("Playwright is required: pass --playwright <module-path>.");
if (!imagePath || !fs.existsSync(imagePath)) throw new Error("Fixture image is required: pass --image <path>.");
if (!fs.existsSync(edgePath)) throw new Error(`Browser executable is unavailable: ${edgePath}`);

const { chromium } = require(path.resolve(playwrightPath));
const wait = (promise, label) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs)),
]);
const imageBase64 = fs.readFileSync(imagePath).toString("base64");

async function run() {
  let browser;
  try {
    const health = await fetch(`${baseUrl}/api/health`).then((response) => ({ status: response.status, body: response.json() }));
    assert.equal(health.status, 200);
    assert.equal((await health.body).ok, true);
    browser = await wait(chromium.launch({ headless: true, executablePath: edgePath }), "Edge launch");
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.setDefaultTimeout(timeoutMs);
    page.setDefaultNavigationTimeout(timeoutMs);
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    // Mock only Feishu publication; every review and asset call below reaches the live backend.
    await page.route(`**/api/jobs/${jobId}/feishu/publish`, (route) => route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ status: "checking_auth" }),
    }));

    await wait(page.goto(`${baseUrl}/?job=${encodeURIComponent(jobId)}`, { waitUntil: "domcontentloaded" }), "live job page load");
    // The UI below drives the live /review-model/confirm-flow, /review-model/confirm-stage, and /review-model/preview endpoints.
    await wait(page.waitForFunction(() => !document.querySelector("#reviewWorkspace").hidden && !document.querySelector("#reviewConfirmFlowBtn").disabled), "live flow review");
    await page.locator("#reviewConfirmFlowBtn").click();
    await wait(page.waitForFunction(() => !document.querySelector("#stageReviewView").hidden && !document.querySelector("#reviewConfirmStageBtn").disabled), "live first stage review");
    const summaryLabels = await page.locator(".stage-summary-row dt").allTextContents();
    assert.deepEqual(summaryLabels, ["页面/环节名称", "当前目标", "如何进入", "用户操作或自动触发", "系统反馈与结果", "关键组件"]);
    assert.equal(await page.locator(".stage-advanced-editor").getAttribute("open"), null, "internal stage fields stay collapsed by default");
    const stageTabs = page.locator(".stage-nav button");
    if (await stageTabs.count() > 1) {
      const firstRegion = page.locator(".stage-region-chip").first();
      if (await firstRegion.count()) await firstRegion.click();
      await stageTabs.nth(1).click();
      assert.equal(await page.locator(".stage-region-box.is-selected").count(), 0, "stage switching clears the prior region selection");
      await stageTabs.nth(0).click();
    }
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(mobileOverflow <= 1, `mobile review must not overflow horizontally: ${mobileOverflow}px`);
    assert.deepEqual(await page.locator(".stage-summary-row dt").allTextContents(), summaryLabels);
    await page.setViewportSize({ width: 1440, height: 900 });
    const firstStageLabel = await page.locator("#reviewConfirmStageBtn").textContent();
    await page.locator("#reviewConfirmStageBtn").click();
    await wait(page.waitForFunction((previousLabel) => {
      const button = document.querySelector("#reviewConfirmStageBtn");
      return button && !button.hidden && !button.disabled && button.textContent !== previousLabel;
    }, firstStageLabel), "live second stage review");
    await page.locator("#reviewConfirmStageBtn").click();
    await wait(page.waitForFunction(() => !document.querySelector("#exportPreviewView").hidden), "live direct preview route");
    await page.locator('[data-review-view="interaction_preview"]').click();
    await wait(page.waitForFunction(() => Boolean(document.querySelector("#exportPreviewView svg"))), "live preview generation");
    assert.equal(await page.locator("#referenceBoardHeading").textContent(), "UE 两画板准备");

    const uxAttempt = await page.evaluate(async ({ baseUrl, jobId, imageBase64 }) => {
      const before = await fetch(`${baseUrl}/api/jobs/${jobId}/review-model`, { cache: "no-store" }).then((response) => response.json());
      const bytes = Uint8Array.from(atob(imageBase64), (character) => character.charCodeAt(0));
      const body = new FormData();
      body.append("images", new File([bytes], "legacy-ux.png", { type: "image/png" }));
      body.append("manifest", JSON.stringify(["legacy-ux.png"]));
      body.append("expectedRevision", String(before.revision));
      const response = await fetch(`${baseUrl}/api/jobs/${jobId}/review-model/reference-boards/ux/assets`, { method: "POST", body });
      const after = await fetch(`${baseUrl}/api/jobs/${jobId}/review-model`, { cache: "no-store" }).then((item) => item.json());
      return { status: response.status, text: await response.text(), beforeRevision: before.revision, afterRevision: after.revision, beforeUx: before.referenceBoards.ux, afterUx: after.referenceBoards.ux };
    }, { baseUrl, jobId, imageBase64 });
    assert.equal(uxAttempt.status, 400, "legacy UX mutation is rejected by the live backend");
    assert.match(uxAttempt.text, /competitor/i);
    assert.equal(uxAttempt.afterRevision, uxAttempt.beforeRevision);
    assert.deepEqual(uxAttempt.afterUx, uxAttempt.beforeUx);

    const externalUpload = await page.evaluate(async ({ baseUrl, jobId, imageBase64 }) => {
      const model = await fetch(`${baseUrl}/api/jobs/${jobId}/review-model`, { cache: "no-store" }).then((response) => response.json());
      const bytes = Uint8Array.from(atob(imageBase64), (character) => character.charCodeAt(0));
      const body = new FormData();
      body.append("images", new File([bytes], "external.png", { type: "image/png" }));
      body.append("manifest", JSON.stringify(["external.png"]));
      body.append("expectedRevision", String(model.revision));
      const response = await fetch(`${baseUrl}/api/jobs/${jobId}/review-model/reference-boards/competitor/assets`, { method: "POST", body });
      return { status: response.status, model: await response.json() };
    }, { baseUrl, jobId, imageBase64 });
    assert.equal(externalUpload.status, 200);
    assert.equal(externalUpload.model.referenceBoards.competitor.assets.length, 1);

    await page.locator('.reference-board-card:not(.reference-board-planning) input[type="file"]').setInputFiles({
      name: "user-upload.png", mimeType: "image/png", buffer: fs.readFileSync(imagePath),
    });
    await wait(page.getByRole("button", { name: /重试.*竞品/ }).waitFor(), "stale competitor mutation exposes retry");
    assert.match(await page.locator("#exportPreviewView").textContent(), /保存失败|重试/);
    assert.equal(await page.locator('[data-review-view="interaction_preview"]').isDisabled(), true);
    assert.equal(await page.locator("#copyBtn").isDisabled(), true);
    assert.equal(await page.locator("#downloadBtn").isDisabled(), true);
    assert.equal(await page.locator("#feishuPublication button").isDisabled(), true);

    await page.getByRole("button", { name: /重试.*竞品/ }).click();
    await wait(page.waitForFunction(() => !document.querySelector('.reference-board-card:not(.reference-board-planning)')?.textContent.includes("重试")), "competitor retry recovery");
    await page.locator('[data-review-view="interaction_preview"]').click();
    await wait(page.waitForFunction(() => document.querySelectorAll(".reference-board-item").length === 2 && !document.querySelector("#exportPreviewView .btn.primary").disabled), "successful retry persists competitor assets");

    const persisted = await page.evaluate(async ({ baseUrl, jobId }) => fetch(`${baseUrl}/api/jobs/${jobId}/review-model`, { cache: "no-store" }).then((response) => response.json()), { baseUrl, jobId });
    assert.equal(persisted.referenceBoards.competitor.assets.length, 2);
    assert.deepEqual(persisted.referenceBoards.competitor.assets.map((asset) => asset.sourceName), ["external.png", "user-upload.png"]);

    await page.reload({ waitUntil: "domcontentloaded" });
    await wait(page.waitForFunction(() => document.querySelectorAll(".reference-board-item").length === 2), "live history recovery");
    assert.equal(await page.getByRole("button", { name: /重试.*竞品/ }).count(), 0);
    await page.setViewportSize({ width: 390, height: 844 });
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
    await page.screenshot({ path: screenshotPath, fullPage: true });
    assert.deepEqual(pageErrors, []);
    console.log(`PASS live backend Edge QA: confirmations, preview, legacy UX authorization, stale competitor failure/retry, persistence and recovery (${screenshotPath})`);
  } finally {
    if (browser) await Promise.race([browser.close(), new Promise((resolve) => setTimeout(resolve, 2000))]);
  }
}

run().catch((error) => { console.error(`FAIL live backend Edge QA: ${error.stack || error}`); process.exitCode = 1; });
