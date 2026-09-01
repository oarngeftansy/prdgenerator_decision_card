const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8011").replace(/\/$/, "");
const jobId = option("--job");
const phase = option("--phase", "initial");
const outputDir = path.resolve(option("--output", "artifacts/nav-mainline-2026-08-13"));
if (!playwrightPath || !jobId) throw new Error("--playwright and --job are required");
const { chromium } = require(path.resolve(playwrightPath));

const expectedUi = {
  gameplay_directory: "gameplay_directory",
  flow: "flow",
  interaction_preview: "interaction_preview",
  gameplay: "gameplay",
  diagrams: "diagrams",
  tables: "tables",
  final_preview: "final_preview",
};

async function run() {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const report = { phase, steps: [], pageErrors: [], failedRequests: [], startedAt: new Date().toISOString() };
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    page.setDefaultTimeout(30000);
    await page.addInitScript(() => {
      localStorage.setItem("vpr_api_key", "qa-isolated-placeholder");
      localStorage.setItem("vpr_remember_key", "1");
    });
    page.on("pageerror", (error) => report.pageErrors.push(error.message));
    page.on("requestfailed", (request) => report.failedRequests.push({ url: request.url(), error: request.failure()?.errorText || "unknown" }));

    const urlFor = (view) => `${baseUrl}/?job=${encodeURIComponent(jobId)}&ui=${view}&qa=nav-${phase}-${Date.now()}`;
    const activeView = () => page.locator("#reviewWorkspace").getAttribute("data-active-view");
    const waitView = async (view) => {
      await page.waitForFunction((expected) => {
        const root = document.querySelector("#reviewWorkspace");
        return root && !root.hidden && root.dataset.activeView === expected;
      }, expectedUi[view]);
      assert.equal(new URL(page.url()).searchParams.get("ui"), view);
      report.steps.push({ view, url: page.url() });
    };
    const refreshStays = async (view) => {
      await page.reload({ waitUntil: "domcontentloaded" });
      await waitView(view);
    };
    const snap = async (name) => {
      const target = path.join(outputDir, name);
      await page.screenshot({ path: target, fullPage: true });
      report.steps.push({ screenshot: target });
    };
    const clickButton = async (name) => {
      const button = page.getByRole("button", { name, exact: typeof name === "string" }).filter({ visible: true }).last();
      await button.waitFor({ state: "visible" });
      assert.equal(await button.isDisabled(), false, `button should be enabled: ${name}`);
      await button.click();
    };

    if (phase === "initial") {
      await page.goto(urlFor("gameplay_directory"), { waitUntil: "domcontentloaded" });
      await waitView("gameplay_directory");
      await clickButton("确认系统划分，继续检查具体机制");
      await page.getByRole("heading", { name: "第二步：确认具体机制" }).waitFor();
      await snap("NAV-TC1-p1-system-to-mechanisms.png");
      await refreshStays("gameplay_directory");
      await page.getByRole("heading", { name: "第二步：确认具体机制" }).waitFor();
      await clickButton("确认机制目录，开始生成详细规则");
      await waitView("flow");
      await snap("NAV-TC1-p1-to-p2.png");
      await refreshStays("flow");

      for (let index = 0; index < 40 && await activeView() === "flow"; index += 1) {
        const next = page.locator(".interaction-next-step:visible");
        await next.waitFor();
        await page.waitForFunction(() => {
          const button = document.querySelector(".interaction-next-step");
          return button && !button.disabled;
        });
        assert.equal(await next.isDisabled(), false, `P2 next button disabled at iteration ${index}`);
        const previousStage = await page.locator(".interaction-stage-nav-item.is-active").textContent();
        await next.click();
        await page.waitForFunction((previous) => {
          const view = document.querySelector("#reviewWorkspace")?.dataset.activeView;
          const current = document.querySelector(".interaction-stage-nav-item.is-active")?.textContent || "";
          return view !== "flow" || current !== previous;
        }, previousStage);
      }
      await waitView("interaction_preview");
      await page.locator("#exportPreviewView svg").first().waitFor();
      await snap("NAV-TC2-p2-to-p3.png");
      await refreshStays("interaction_preview");

      await clickButton("进入规则审核");
      await waitView("gameplay");
      await snap("NAV-TC3-p3-to-p4.png");
      await refreshStays("gameplay");
      const chapter = page.locator('[data-chapter-id="GCH-001"]');
      if (await chapter.count()) await chapter.first().click();
      await clickButton("确认本节通过");
      await waitView("diagrams");
      await snap("NAV-TC3-p4-to-p5.png");
      await refreshStays("diagrams");
    } else if (phase === "p2last") {
      await page.goto(urlFor("flow"), { waitUntil: "domcontentloaded" });
      await waitView("flow");
      await page.locator(".interaction-stage-nav-item:visible").last().click();
      let sawFinalLabel = false;
      for (let index = 0; index < 20 && await activeView() === "flow"; index += 1) {
        const next = page.locator(".interaction-next-step:visible");
        await next.waitFor();
        await page.waitForFunction(() => !document.querySelector(".interaction-next-step")?.disabled);
        const label = (await next.textContent()).trim();
        if (label === "应用并进入交付物预览") sawFinalLabel = true;
        const previousStage = await page.locator(".interaction-stage-nav-item.is-active").textContent();
        await next.click();
        await page.waitForFunction((previous) => {
          const view = document.querySelector("#reviewWorkspace")?.dataset.activeView;
          const current = document.querySelector(".interaction-stage-nav-item.is-active")?.textContent || "";
          return view !== "flow" || current !== previous;
        }, previousStage);
      }
      assert.equal(sawFinalLabel, true, "the last P2 stage must expose the P3 progression label");
      await waitView("interaction_preview");
      await page.locator("#exportPreviewView svg").first().waitFor();
      await snap("NAV-TC2-p2-to-p3.png");
      await refreshStays("interaction_preview");

      await clickButton("进入规则审核");
      await waitView("gameplay");
      await snap("NAV-TC3-p3-to-p4.png");
      await refreshStays("gameplay");
      const chapter = page.locator('[data-chapter-id="GCH-001"]');
      if (await chapter.count()) await chapter.first().click();
      await clickButton("确认本节通过");
      await waitView("diagrams");
      await snap("NAV-TC3-p4-to-p5.png");
      await refreshStays("diagrams");
    } else if (phase === "race") {
      await page.goto(urlFor("diagrams"), { waitUntil: "domcontentloaded" });
      await waitView("diagrams");
      let release;
      const gate = new Promise((resolve) => { release = resolve; });
      await page.route(`**/api/jobs/${jobId}/gameplay-review-model/diagrams/*/approve`, async (route) => {
        await gate;
        await route.continue();
      });
      const approveChoice = page.locator('.gameplay-diagram-review-choice input[value="approve"]:visible').first();
      await approveChoice.check();
      const pending = page.locator(".gameplay-diagram-apply:visible").click();
      await page.waitForTimeout(100);
      await page.getByRole("button", { name: /玩法目录/ }).click();
      await waitView("gameplay_directory");
      release();
      await pending;
      await page.waitForTimeout(800);
      assert.equal(await activeView(), "gameplay_directory", "late P5 response must not override the user's latest navigation");
      await snap("NAV-TC5-race-keeps-latest-page.png");
    } else if (phase === "p5") {
      await page.goto(urlFor("diagrams"), { waitUntil: "domcontentloaded" });
      await waitView("diagrams");
      const approveChoice = page.locator('.gameplay-diagram-review-choice input[value="approve"]:visible').first();
      await approveChoice.check();
      await page.locator(".gameplay-diagram-apply:visible").click();
      await waitView("tables");
      await snap("NAV-TC3-p5-to-p6.png");
      await refreshStays("tables");
    } else if (phase === "p6") {
      await page.goto(urlFor("tables"), { waitUntil: "domcontentloaded" });
      await waitView("tables");
      await page.locator(".gameplay-table-approve:visible").first().click();
      await waitView("final_preview");
      await page.locator(".final-document-shell").waitFor();
      await snap("NAV-TC3-p6-to-p7.png");
      await refreshStays("final_preview");
    } else {
      throw new Error(`unknown phase: ${phase}`);
    }

    assert.deepEqual(report.pageErrors, []);
    assert.deepEqual(report.failedRequests, []);
    report.cacheResources = await page.evaluate(() => performance.getEntriesByType("resource").map((item) => item.name).filter((name) => name.includes("backend.js")));
    report.completedAt = new Date().toISOString();
    fs.writeFileSync(path.join(outputDir, `report-${phase}.json`), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error.stack || error); process.exit(1); });
