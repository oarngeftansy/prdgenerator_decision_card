const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto("http://127.0.0.1:8000/?job=4180cd72eeaa4819be41db50bb4c5011&ui=check-live-nav", { waitUntil: "domcontentloaded" });
  await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
  await page.waitForTimeout(1500);
  const result = await page.evaluate(() => ({
    activeView: document.querySelector("#reviewWorkspace")?.dataset.activeView,
    steps: [...document.querySelectorAll("[data-workbench-step]")].map((node) => ({
      step: node.dataset.workbenchStep,
      view: node.dataset.reviewView,
      disabled: node.disabled,
      text: node.textContent.trim(),
    })),
    visibleViews: [...document.querySelectorAll("#reviewWorkspace > [id]")]
      .filter((node) => getComputedStyle(node).display !== "none")
      .map((node) => node.id),
  }));
  await page.locator('[data-workbench-step="p3"]').click();
  await page.waitForTimeout(1000);
  result.p3 = {
    activeView: await page.locator("#reviewWorkspace").getAttribute("data-active-view"),
    primaryText: await page.locator("#exportPreviewView .export-preview-continue").textContent(),
    generationFailureVisible: await page.locator("#exportPreviewView .export-preview-blocked").count(),
  };
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
