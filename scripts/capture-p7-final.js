const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto("http://127.0.0.1:8000/?job=4180cd72eeaa4819be41db50bb4c5011&ui=p7-final-state", { waitUntil: "domcontentloaded" });
  await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
  await page.waitForTimeout(800);
  if (!(await page.locator("#finalDocumentPreviewView .final-document-shell").isVisible())) {
    await page.evaluate(() => {
      setReviewWorkspaceView("final_preview");
      renderReviewWorkspace(state.reviewWorkspace.model);
    });
  }
  await page.locator("#finalDocumentPreviewView .final-document-shell").waitFor({ state: "visible", timeout: 15000 });
  const root = page.locator("#finalDocumentPreviewView");
  const result = {
    percent: await root.locator(".final-document-score strong").innerText(),
    checks: await root.locator(".final-document-check").allInnerTexts(),
    containsInteraction: (await root.innerText()).includes("交互与页面流程"),
    containsGameplay: (await root.innerText()).includes("核心战斗系统"),
  };
  await page.screenshot({ path: path.resolve(__dirname, "../artifacts/qa-p1-p7-2026-08-10/p7-final.png") });
  console.log(JSON.stringify(result));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
