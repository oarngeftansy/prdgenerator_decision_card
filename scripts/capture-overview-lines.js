const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.OVERVIEW_ORIGIN || "http://127.0.0.1:8009";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-refined-browser");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  try {
    await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle" });
    await page.locator('[data-workbench-step="p7"]').evaluate((node) => node.click());
    await page.locator(".final-document-gameplay-overview").waitFor({ state: "visible", timeout: 30000 });
    const lines = await page.locator(".final-document-gameplay-overview .final-document-overview-line").allTextContents();
    if (lines.length < 4) throw new Error(`expected at least four overview lines, got ${lines.length}`);
    await page.locator(".final-document-gameplay-overview").screenshot({ path: path.join(output, "s5-gameplay-overview-readable.png") });
    console.log(JSON.stringify({ passed: true, lines }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
