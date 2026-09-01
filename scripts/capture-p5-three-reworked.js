const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

const origin = "http://127.0.0.1:8000";
const jobId = "8312a91c89e144e6a59f81b982f14c06";
const output = path.resolve(__dirname, "..", "artifacts", "p5-three-reworked-review");
const wanted = [
  ["GCH-001", "GDI-101", "TC-R1-level-loop.png"],
  ["GCH-003", "GDI-106", "TC-R2-weapon-hit-chain.png"],
  ["GCH-012", "GDI-102", "TC-R3-three-choice-flow.png"],
];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 } });
  await page.goto(`${origin}/?job=${jobId}&ui=diagrams`, { waitUntil: "networkidle", timeout: 40000 });
  await page.locator(".gameplay-diagrams").waitFor({ state: "visible", timeout: 20000 });
  const statuses = await page.locator(".gameplay-diagram-nav-item").evaluateAll(nodes => nodes.map(node => ({ text: node.textContent.trim(), status: node.dataset.status, label: node.dataset.statusLabel })));
  assert.ok(statuses.some(item => item.status === "open" && item.label === "待审核"));
  await page.locator(".gameplay-diagram-nav").screenshot({ path: path.join(output, "TC-R0-navigation-status.png"), animations: "disabled" });
  for (const [chapterId, diagramId, filename] of wanted) {
    await page.locator(`.gameplay-diagram-nav-item[data-chapter-id="${chapterId}"]`).click();
    const card = page.locator(`.gameplay-diagram-card[data-diagram-id="${diagramId}"]`);
    await card.waitFor({ state: "visible" });
    const relationship = await card.evaluate(node => ({ lines: node.querySelectorAll("line,path,polyline").length, arrows: node.querySelectorAll("polygon").length, text: node.innerText }));
    assert.ok(relationship.lines > 0 && relationship.arrows > 0, `${diagramId} 缺少流程连线或箭头`);
    await card.screenshot({ path: path.join(output, filename), animations: "disabled" });
  }
  fs.writeFileSync(path.join(output, "status.json"), JSON.stringify({ statuses }, null, 2));
  await browser.close();
  console.log(JSON.stringify({ output, statuses }, null, 2));
})().catch(error => { console.error(error.stack || error); process.exit(1); });
