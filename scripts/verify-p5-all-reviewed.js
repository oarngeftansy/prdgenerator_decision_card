const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
  const output = path.resolve("artifacts/p5-all-reviewed");
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 } });
  await page.goto("http://127.0.0.1:8000/?job=8312a91c89e144e6a59f81b982f14c06&ui=diagrams", { waitUntil: "networkidle" });
  await page.locator(".gameplay-diagrams").waitFor({ state: "visible" });
  const summary = await page.locator(".gameplay-diagram-summary").innerText();
  assert.match(summary, /6 已通过/);
  assert.match(summary, /0 待审核/);
  await page.screenshot({ path: path.join(output, "P5-6-of-6-reviewed-full.png"), fullPage: true, animations: "disabled" });
  await page.locator('[data-workbench-step="p6"]').click();
  await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.getAttribute("data-active-view") === "tables");
  assert.equal(new URL(page.url()).searchParams.get("ui"), "tables");
  await page.screenshot({ path: path.join(output, "P6-after-navigation-full.png"), fullPage: true, animations: "disabled" });
  await page.reload({ waitUntil: "networkidle" });
  assert.equal(await page.locator("#reviewWorkspace").getAttribute("data-active-view"), "tables");
  await page.screenshot({ path: path.join(output, "P6-refresh-restored-full.png"), fullPage: true, animations: "disabled" });
  console.log(JSON.stringify({ summary, url: page.url(), active: await page.locator("#reviewWorkspace").getAttribute("data-active-view"), output }, null, 2));
  await browser.close();
})().catch(error => { console.error(error.stack || error); process.exit(1); });
