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

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(30000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  try {
    await page.goto(`${base}/?job=${job}&ui=gameplay_directory`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay_directory");
    await page.locator(".gameplay-directory-tree-item").first().click();
    const merge = page.locator(".gameplay-directory-editor-actions button").filter({ hasText: "合并" }).first();
    if (!await merge.count()) console.log(JSON.stringify(await page.locator("button:visible").allInnerTexts()));
    assert.equal(await merge.count(), 1);
    const revisionBefore = await page.evaluate(() => state.gameplayReviewWorkspace?.model?.revision || 0);
    page.once("dialog", (dialog) => dialog.accept());
    await merge.click();
    await page.waitForFunction((revision) => (state.gameplayReviewWorkspace?.model?.revision || 0) > revision, revisionBefore);
    const split = page.locator(".gameplay-directory-editor-actions button").filter({ hasText: "\u62c6\u6210\u4e24\u9879" }).first();
    assert.equal(await split.count(), 1);
    await split.click();
    const panel = page.locator(".gameplay-directory-split:visible");
    await panel.waitFor();
    assert.ok(await panel.locator('input[type="checkbox"]').count() >= 2);
    assert.equal(await panel.locator("button").filter({ hasText: "\u786e\u8ba4\u62c6\u5206" }).count(), 1);
    await panel.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(output, "UX-TC06-P1-merge-then-split-panel.png"),
      fullPage: false,
      animations: "disabled",
    });
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "TC06.json"), JSON.stringify({
      passed: true,
      mergeRequestPersisted: true,
      splitPanelVisible: true,
      splitClaimCount: await panel.locator('input[type="checkbox"]').count(),
      errors,
    }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
