const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE5_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-v2-browser-acceptance", "attribute-toc-sync");
const entries = [
  ["载具", "final-doc-GCH-001-attribute-object-0", "final-document-toc-item"],
  ["承伤与武器换算", "final-doc-GCH-001-attribute-group-0", "final-document-toc-leaf"],
  ["等级与栏位状态", "final-doc-GCH-001-attribute-group-1", "final-document-toc-leaf"],
  ["特权载具", "final-doc-GCH-001-attribute-group-2", "final-document-toc-leaf"],
];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1900, height: 1100 }, deviceScaleFactor: 1 });
  try {
    await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle", timeout: 30000 });
    await page.locator('[data-workbench-step="p7"]').evaluate((button) => button.click());
    await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
    const checks = [];
    for (const [label, targetId, className] of entries) {
      const tocItem = page.locator(`.${className}`, { hasText: label }).filter({ hasText: new RegExp(`^${label}$`) }).first();
      if (await tocItem.count() !== 1) throw new Error(`目录缺少或重复：${label}`);
      const target = page.locator(`#${targetId}`);
      if (await target.count() !== 1) throw new Error(`正文锚点缺少或重复：${label}`);
      const targetText = (await target.textContent()).trim();
      if (targetText !== label) throw new Error(`目录与正文不一致：${label}/${targetText}`);
      await tocItem.click();
      await page.waitForTimeout(450);
      const position = await target.evaluate((node) => {
        const reader = node.closest(".final-document-scroll");
        const targetRect = node.getBoundingClientRect();
        const readerRect = reader.getBoundingClientRect();
        return { targetTop: targetRect.top, readerTop: readerRect.top, readerBottom: readerRect.bottom, readerScrollTop: reader.scrollTop, readerScrollHeight: reader.scrollHeight, readerClientHeight: reader.clientHeight, readerOverflow: getComputedStyle(reader).overflowY, visible: targetRect.top >= readerRect.top - 2 && targetRect.top < readerRect.bottom };
      });
      if (!position.visible) throw new Error(`点击后未定位到正文：${label} ${JSON.stringify(position)}`);
      checks.push({ label, targetId, targetText, position, passed: true });
      if (label === "载具" || label === "等级与栏位状态") {
        await page.screenshot({ path: path.join(output, label === "载具" ? "toc-to-vehicle.png" : "toc-to-level-slot.png"), animations: "disabled" });
      }
    }
    const payload = { passed: true, url: page.url(), entries: checks, screenshots: [path.join(output, "toc-to-vehicle.png"), path.join(output, "toc-to-level-slot.png")] };
    fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(payload, null, 2));
    console.log(JSON.stringify(payload, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
