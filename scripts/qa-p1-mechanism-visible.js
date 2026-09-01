const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8000").replace(/\/$/, "");
const jobId = option("--job");
const edgePath = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");
const screenshotPath = option("--screenshot", path.resolve("artifacts/qa-p1-system-to-mechanisms.png"));

if (!playwrightPath || !fs.existsSync(playwrightPath)) throw new Error("Pass a valid --playwright module path.");
if (!jobId) throw new Error("Pass --job for a task currently in the P1 mechanism step.");

const { chromium } = require(path.resolve(playwrightPath));

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: edgePath });
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto(`${baseUrl}/?job=${encodeURIComponent(jobId)}&ui=gameplay_directory&qa=${Date.now()}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => {
      const root = document.querySelector("#gameplayDirectoryView");
      return root && !root.hidden && root.textContent.includes("第二步：确认具体机制");
    });
    assert.match(page.url(), /ui=gameplay_directory/);
    assert.equal(await page.locator("#gameplayDirectoryView").isVisible(), true);
    assert.match(await page.locator("#gameplayDirectoryView").innerText(), /第二步：确认具体机制/);
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
    await page.screenshot({ path: screenshotPath, fullPage: true });
    assert.deepEqual(pageErrors, []);
    console.log(`PASS P1 mechanism step is visible (${screenshotPath})`);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
