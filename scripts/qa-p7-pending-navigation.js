const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-v2-browser-acceptance");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 } });
  try {
    await page.goto(`http://127.0.0.1:8000/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle", timeout: 30000 });
    await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
    const action = page.locator(".final-document-resolve");
    const label = (await action.textContent()).trim();
    if (label !== "处理 5 项策划决策") throw new Error(`unexpected action label: ${label}`);
    await action.click();
    await page.locator("#gameplayReviewView:not([hidden])").waitFor({ state: "visible", timeout: 10000 });
    await page.waitForTimeout(1000);
    const result = await page.evaluate(() => {
      const card = document.querySelector(".planner-decision-card");
      const rect = card?.getBoundingClientRect();
      return {
        view: state.reviewWorkspace.view,
        selectedChapterId: state.gameplayReviewWorkspace.selectedChapterId,
        cardId: card?.getAttribute("data-decision-card-id"),
        focused: document.activeElement === card,
        inViewport: Boolean(rect && rect.top < innerHeight && rect.bottom > 0),
        pending: state.gameplayReviewWorkspace.model.chapters.flatMap(chapter => chapter.decisionCards || []).filter(card => ["pending", "skipped"].includes(card.status)).length,
      };
    });
    if (result.view !== "gameplay" || !result.cardId || !result.focused || !result.inViewport || result.pending !== 5) throw new Error(JSON.stringify(result));
    const screenshot = path.join(output, "s5r-tc11-pending-decision-navigation.png");
    await page.screenshot({ path: screenshot, fullPage: true, animations: "disabled" });
    fs.writeFileSync(path.join(output, "s5r-tc11-result.json"), JSON.stringify({ passed: true, label, ...result }, null, 2));
    console.log(JSON.stringify({ passed: true, label, ...result, screenshot }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
