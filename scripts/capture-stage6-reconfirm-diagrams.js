const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const job = "8312a91c89e144e6a59f81b982f14c06";
const output = path.resolve(__dirname, "..", "artifacts", "stage6-diagram-reconfirm");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1200 }, deviceScaleFactor: 1 });
  await page.goto(`http://127.0.0.1:8000/?job=${job}&ui=diagrams`, { waitUntil: "networkidle", timeout: 40000 });
  await page.locator(".gameplay-diagrams").waitFor({ state: "visible", timeout: 30000 });
  const seen = new Set();
  const result = [];
  const items = page.locator(".gameplay-diagram-nav-item");
  for (let index = 0; index < await items.count(); index += 1) {
    await items.nth(index).click();
    await page.waitForTimeout(180);
    const cards = page.locator(".gameplay-diagram-card:not([hidden])");
    for (let cardIndex = 0; cardIndex < await cards.count(); cardIndex += 1) {
      const card = cards.nth(cardIndex);
      const id = await card.getAttribute("data-diagram-id");
      if (!id || seen.has(id)) continue;
      seen.add(id);
      const file = `${String(result.length + 1).padStart(2, "0")}-${id}.png`;
      await card.screenshot({ path: path.join(output, file), animations: "disabled" });
      result.push({ id, file, status: (await card.locator(".gameplay-diagram-status").textContent() || "").trim() });
    }
  }
  const summary = (await page.locator(".gameplay-diagram-summary").textContent() || "").trim();
  fs.writeFileSync(path.join(output, "manifest.json"), JSON.stringify({ summary, result }, null, 2));
  await browser.close();
  console.log(JSON.stringify({ output, summary, result }, null, 2));
})().catch((error) => { console.error(error.stack || error); process.exit(1); });
