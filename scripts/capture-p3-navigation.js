const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    await page.goto("http://127.0.0.1:8000/?job=4180cd72eeaa4819be41db50bb4c5011&ui=p3-navigation", { waitUntil: "networkidle" });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
    const tab = page.locator('[data-review-view="interaction_preview"]');
    await tab.click();
    const board = page.locator("#exportPreviewView .export-preview-board > svg").first();
    await board.waitFor({ state: "visible", timeout: 30000 });
    const text = await board.textContent();
    if (/æ­|å|ç/.test(text)) throw new Error("P3 SVG still contains UTF-8 mojibake");
    await page.screenshot({ path: path.resolve("artifacts/wireframe-comparison/p3-navigation-current.png") });
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
