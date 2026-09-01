const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8000").replace(/\/$/, "");
const job = option("--job", "4180cd72eeaa4819be41db50bb4c5011");
const output = path.resolve(option("--output", "artifacts/current-workbench-restore-2026-08-20"));
const acceptedTitles = ["载具", "武器", "局内强化", "终极强化", "武器抽取", "怪物", "关卡", "结算"];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  try {
    await page.goto(`${base}/?job=${job}&ui=gameplay_directory`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay_directory");
    const entries = await page.locator(".gameplay-directory-tree-item").allTextContents();
    const renderedTitles = await page.locator('.gameplay-directory-tree-item input[aria-label^="第"]').evaluateAll(
      (nodes) => nodes.map((node) => node.value),
    );
    const body = await page.locator("body").innerText();
    assert.deepEqual(renderedTitles, acceptedTitles);
    assert.doesNotMatch(body, /载具移动机制|Roguelike成长系统|首领多阶段形态|战后资源结算/);
    assert.equal(entries.length, acceptedTitles.length);
    const screenshot = path.join(output, "WEB-P1-restored-eight-owner-directory.png");
    await page.screenshot({ path: screenshot, fullPage: false, animations: "disabled" });
    fs.writeFileSync(path.join(output, "acceptance.json"), JSON.stringify({
      job,
      acceptedTitles,
      renderedTitles,
      entryCount: entries.length,
      consoleErrors: errors,
      screenshot: path.basename(screenshot),
    }, null, 2));
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
