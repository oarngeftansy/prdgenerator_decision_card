const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  try {
    await page.goto("http://127.0.0.1:8000/?job=4180cd72eeaa4819be41db50bb4c5011&ui=p3-live", { waitUntil: "networkidle" });
    const button = page.locator('[data-workbench-step="p3"]');
    await button.click();
    await page.waitForTimeout(5000);
    const state = await page.evaluate(() => ({
      active: document.querySelector("#reviewWorkspace")?.getAttribute("data-active-view"),
      status: window.state?.reviewWorkspace?.previewStatus,
      svgLength: window.state?.reviewWorkspace?.preview?.boardPreviewSvg?.length || 0,
      renderedSvg: document.querySelector("#exportPreviewView svg")?.outerHTML?.length || 0,
      text: document.querySelector("#exportPreviewView")?.innerText?.slice(0, 240) || "",
    }));
    console.log(JSON.stringify(state));
    await page.screenshot({ path: path.resolve("artifacts/p3-live.png") });
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
