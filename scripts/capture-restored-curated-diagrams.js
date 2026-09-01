const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const job = "8312a91c89e144e6a59f81b982f14c06";
const output = path.resolve(__dirname, "..", "artifacts", "stage6-feishu-curated-diagram-check");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 } });
  await page.goto(`http://127.0.0.1:8000/?job=${job}&ui=diagrams`, { waitUntil: "networkidle", timeout: 40000 });
  await page.locator(".gameplay-diagrams").waitFor({ state: "visible", timeout: 30000 });
  const items = page.locator(".gameplay-diagram-nav-item");
  const result = [];
  for (let index = 0; index < await items.count(); index += 1) {
    const item = items.nth(index);
    await item.click();
    await page.waitForTimeout(250);
    const card = page.locator(".gameplay-diagram-card:not([hidden])").last();
    await card.waitFor({ state: "visible" });
    const id = await card.getAttribute("data-diagram-id");
    const file = `${String(index + 1).padStart(2, "0")}-${id}.png`;
    await card.screenshot({ path: path.join(output, file), animations: "disabled" });
    result.push({ id, file, title: (await item.textContent() || "").trim() });
  }
  fs.writeFileSync(path.join(output, "manifest.json"), JSON.stringify(result, null, 2));
  await browser.close();
  console.log(JSON.stringify({ output, result }, null, 2));
})().catch(error => { console.error(error.stack || error); process.exit(1); });
