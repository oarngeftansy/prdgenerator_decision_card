const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8014").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(30000);
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let requests = 0;
  await page.route(`**/api/jobs/${job}/gameplay-review-model/diagrams/*/approve`, async (route) => {
    requests += 1;
    await gate;
    await route.continue();
  });
  try {
    await page.goto(`${base}/?job=${job}&ui=diagrams`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "diagrams");
    await page.waitForFunction(() => (state.gameplayReviewWorkspace?.model?.diagrams || []).filter((item) => item.status === "reviewed").length === 5);
    const chapters = page.locator(".gameplay-diagram-nav-item:visible");
    let apply = null;
    for (let index = 0; index < await chapters.count() && !apply; index += 1) {
      await chapters.nth(index).click();
      const card = page.locator('.gameplay-diagram-card:visible:not([data-status="stale"])').first();
      if (!await card.count()) continue;
      await card.click();
      await page.locator('.gameplay-diagram-decision input[value="approve"]').check();
      apply = page.locator(".gameplay-diagram-decision .gameplay-diagram-apply");
    }
    assert.ok(apply);
    const pending = apply.click();
    await page.waitForTimeout(100);
    await apply.click({ force: true }).catch(() => {});
    await page.locator('[data-workbench-step="p1"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay_directory");
    release();
    await pending;
    await page.waitForTimeout(1200);
    assert.equal(requests, 1);
    assert.equal(await page.locator("#reviewWorkspace").getAttribute("data-active-view"), "gameplay_directory");
    assert.equal(new URL(page.url()).searchParams.get("ui"), "gameplay_directory");
    const directoryItems = page.locator(".gameplay-directory-tree-item:visible");
    if (await directoryItems.count() > 1) await directoryItems.nth(1).click();
    await page.screenshot({ path: path.join(output, "UX-TC18-late-save-keeps-latest-page.png"), fullPage: false, animations: "disabled" });
    fs.writeFileSync(path.join(output, "race.json"), JSON.stringify({ passed: true, requests, latestView: "gameplay_directory" }, null, 2));
    console.log(JSON.stringify({ passed: true, requests }, null, 2));
  } finally { release?.(); await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
