const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const playwrightPath = process.argv[2];
const baseUrl = process.argv[3];
const folder = path.resolve(process.argv[4]);
const screenshot = path.resolve(process.argv[5]);
const expectedCount = Number(process.argv[6] || 42);
const expectedEnabled = expectedCount >= 2 && expectedCount <= 50;
const { chromium } = require(path.resolve(playwrightPath));

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    page.setDefaultTimeout(30000);
    await page.goto(`${baseUrl.replace(/\/$/, "")}/?qa=upload-${expectedCount}-${Date.now()}`, { waitUntil: "domcontentloaded" });
    await page.locator("#screenshotFolderInput").setInputFiles(folder);
    await page.waitForFunction((count) => document.querySelectorAll(".screenshot-preview-item").length === count, expectedCount);
    assert.equal(await page.locator("#fileCount").textContent(), String(expectedCount));
    assert.equal(await page.locator("#extractBtn").isDisabled(), !expectedEnabled);
    if (expectedEnabled) assert.match(await page.locator("#screenshotValidation").textContent(), new RegExp(`已选择 ${expectedCount} 张截图`));
    else assert.match(await page.locator("#screenshotValidation").textContent(), /最多.*50 张/);
    fs.mkdirSync(path.dirname(screenshot), { recursive: true });
    await page.screenshot({ path: screenshot, fullPage: true });
    console.log(JSON.stringify({ count: expectedCount, extractEnabled: expectedEnabled, screenshot }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.stack || error); process.exit(1); });
