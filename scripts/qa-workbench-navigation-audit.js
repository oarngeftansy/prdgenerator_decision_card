const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8000").replace(/\/$/, "");
const jobId = option("--job", "8312a91c89e144e6a59f81b982f14c06");
const output = path.resolve(option("--output", "artifacts/qa-navigation-2026-08-13"));
const edgePath = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");
if (!playwrightPath || !fs.existsSync(playwrightPath)) throw new Error("Pass --playwright with an installed Playwright module.");
const { chromium } = require(path.resolve(playwrightPath));

const steps = [
  { id: "p1", requested: "gameplay_directory", allowed: ["gameplay_directory"], ready: "#gameplayDirectoryView .gameplay-directory" },
  { id: "p2", requested: "flow", allowed: ["flow", "stage"], ready: "#flowReviewView .interaction-stage-navigation" },
  { id: "p2-ue", requested: "ue_flow", allowed: ["ue_flow"], ready: "#ueFlowCanvas .ue-flow-page-card" },
  { id: "p3", requested: "interaction_preview", allowed: ["interaction_preview"], ready: "#exportPreviewView svg" },
  { id: "p4", requested: "gameplay", allowed: ["gameplay"], ready: "#gameplayReviewView .gameplay-review" },
  { id: "p5", requested: "diagrams", allowed: ["diagrams"], ready: "#gameplayDiagramView .gameplay-diagrams" },
  { id: "p6", requested: "tables", allowed: ["tables"], ready: "#gameplayTableView .gameplay-tables" },
  { id: "p7", requested: "final_preview", allowed: ["final_preview"], ready: "#finalExportPreviewView .final-document-shell" },
];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: edgePath });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || "failed"}`));
  const results = [];
  try {
    await page.goto(`${baseUrl}/?job=${encodeURIComponent(jobId)}&ui=final_preview&qa=${Date.now()}`, { waitUntil: "domcontentloaded" });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 30000 });
    await page.locator("#finalExportPreviewView .final-document-back").waitFor({ state: "visible", timeout: 30000 });
    await page.locator("#finalExportPreviewView .final-document-back").click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "tables", null, { timeout: 30000 });
    await page.waitForTimeout(5000);
    assert.equal(await page.locator("#reviewWorkspace").getAttribute("data-active-view"), "tables", "late deep-link restoration overwrote the P7 return action");
    for (const step of steps) {
      console.log(`CHECK ${step.id}: click ${step.requested}`);
      const nav = page.locator(`[data-review-view="${step.requested}"]`);
      const initiallyEnabled = await nav.isEnabled();
      const enableStartedAt = Date.now();
      if (!initiallyEnabled) await page.waitForFunction((view) => !document.querySelector(`[data-review-view="${view}"]`)?.disabled, step.requested, { timeout: 30000 });
      const enabled = await nav.isEnabled();
      const enableWaitMs = Date.now() - enableStartedAt;
      if (enabled) await nav.click();
      console.log(`CHECK ${step.id}: initial=${initiallyEnabled}, enabled=${enabled}, wait=${enableWaitMs}ms, immediate=${await page.locator("#reviewWorkspace").getAttribute("data-active-view")}`);
      await page.waitForFunction((allowed) => allowed.includes(document.querySelector("#reviewWorkspace")?.dataset.activeView), step.allowed, { timeout: 30000 });
      try {
        await page.locator(step.ready).first().waitFor({ state: "visible", timeout: 30000 });
      } catch (error) {
        console.error(`READY FAILURE ${step.id}`, await page.evaluate((selector) => {
          const target = document.querySelector(selector);
          const view = target?.closest?.(".review-view");
          const workspace = document.querySelector("#reviewWorkspace");
          return {
            activeView: workspace?.dataset.activeView,
            workspaceClass: workspace?.className,
            viewId: view?.id,
            viewHidden: view?.hidden,
            viewDisplay: view ? getComputedStyle(view).display : null,
            targetHidden: target?.hidden,
            targetDisplay: target ? getComputedStyle(target).display : null,
            targetRect: target?.getBoundingClientRect?.().toJSON?.(),
            url: location.href,
          };
        }, step.ready));
        throw error;
      }
      const beforeRefresh = await page.evaluate(() => {
        const workspace = document.querySelector("#reviewWorkspace");
        const visibleViews = Array.from(workspace.querySelectorAll(".review-view")).filter((item) => !item.hidden).map((item) => item.id);
        const buttons = Array.from(workspace.querySelectorAll("button")).filter((item) => {
          const style = getComputedStyle(item);
          const rect = item.getBoundingClientRect();
          return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
        }).map((item) => ({
          text: (item.textContent || "").trim().replace(/\s+/g, " "),
          id: item.id || "",
          disabled: item.disabled,
          current: item.getAttribute("aria-current") || "",
        }));
        return {
          activeView: workspace.dataset.activeView,
          visibleViews,
          buttons,
          overflow: workspace.scrollWidth - workspace.clientWidth,
          url: location.href,
        };
      });
      assert.ok(step.allowed.includes(beforeRefresh.activeView), `${step.id} opened ${beforeRefresh.activeView}`);
      assert.match(beforeRefresh.url, new RegExp(`ui=${step.requested}`));
      assert.equal(beforeRefresh.visibleViews.length, 1, `${step.id} must expose exactly one review view`);
      await page.screenshot({ path: path.join(output, `${step.id}-${beforeRefresh.activeView}.png`), fullPage: false, animations: "disabled" });
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 30000 });
      console.log(`CHECK ${step.id}: after reload immediate=${await page.locator("#reviewWorkspace").getAttribute("data-active-view")}`);
      await page.waitForFunction((allowed) => allowed.includes(document.querySelector("#reviewWorkspace")?.dataset.activeView), step.allowed, { timeout: 30000 });
      await page.locator(step.ready).first().waitFor({ state: "visible", timeout: 30000 });
      const afterRefresh = await page.locator("#reviewWorkspace").getAttribute("data-active-view");
      assert.equal(afterRefresh, beforeRefresh.activeView, `${step.id} changed after refresh`);
      results.push({ step: step.id, initiallyEnabled, enabled, enableWaitMs, ...beforeRefresh, afterRefresh });
    }
    const payload = { passed: true, results, consoleErrors, pageErrors, failedRequests };
    fs.writeFileSync(path.join(output, "navigation-audit.json"), JSON.stringify(payload, null, 2));
    assert.deepEqual(pageErrors, []);
    assert.deepEqual(consoleErrors, []);
    assert.deepEqual(failedRequests, []);
    console.log(JSON.stringify(payload, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
