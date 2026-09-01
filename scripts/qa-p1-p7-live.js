const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const url = "http://127.0.0.1:8000/?job=4180cd72eeaa4819be41db50bb4c5011&ui=qa-p1-p7-live";
const outDir = path.resolve(__dirname, "..", "artifacts", "qa-p1-p7-2026-08-10");

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.setDefaultTimeout(4000);
  const errors = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console:${message.text()}`); });
  page.on("pageerror", (error) => errors.push(`pageerror:${error.message}`));
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
  await page.waitForTimeout(1200);
  const results = [];
  for (let index = 1; index <= 7; index += 1) {
    const nav = page.locator(`[data-workbench-step="p${index}"]`);
    const enabled = await nav.isEnabled();
    if (enabled) await nav.evaluate((button) => button.click());
    await page.waitForTimeout(index === 3 ? 1000 : 350);
    const workspace = page.locator("#reviewWorkspace");
    const text = await workspace.innerText();
    const badTokens = ["undefined", "component", "pending_details", "scope:", "未知待确认"]
      .filter((token) => text.toLowerCase().includes(token.toLowerCase()));
    const activeView = await workspace.getAttribute("data-active-view");
    const visibleButtons = await workspace.locator("button:visible").count();
    const horizontalOverflow = await workspace.evaluate((node) => node.scrollWidth - node.clientWidth);
    await page.screenshot({ path: path.join(outDir, `p${index}.png`), fullPage: false });
    results.push({ page: `P${index}`, enabled, activeView, visibleButtons, badTokens, horizontalOverflow });
  }

  await page.waitForTimeout(350);
  const details = page.locator("#finalDocumentPreviewView details");
  let accordion = "not-present";
  if (await details.count()) {
    const before = await details.first().getAttribute("open");
    await details.first().locator("summary").click({ force: true, timeout: 3000 });
    const after = await details.first().getAttribute("open");
    accordion = before !== after ? "pass" : "fail";
  }
  const p7Text = await page.locator("#finalDocumentPreviewView").innerText();
  results.push({ page: "P7-interaction", accordion, containsInteraction: /交互/.test(p7Text), containsGameplay: /玩法|规则/.test(p7Text) });
  console.log(JSON.stringify({ results, errors }, null, 2));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
