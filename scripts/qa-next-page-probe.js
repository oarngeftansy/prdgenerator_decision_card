const fs = require("node:fs");
const path = require("node:path");

const playwrightPath = process.argv[2];
const url = process.argv[3];
if (!playwrightPath || !url) throw new Error("usage: node qa-next-page-probe.js <playwright-path> <url>");
const { chromium } = require(path.resolve(playwrightPath));

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    page.setDefaultTimeout(30000);
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => !document.querySelector("#reviewWorkspace")?.hidden);
    await page.waitForTimeout(1000);
    const result = await page.evaluate(() => ({
      url: location.href,
      activeView: document.querySelector("#reviewWorkspace")?.dataset.activeView,
      headings: Array.from(document.querySelectorAll("h1,h2,h3,h4")).filter((node) => node.offsetParent).slice(0, 30).map((node) => node.textContent.trim()),
      buttons: Array.from(document.querySelectorAll("button")).filter((node) => node.offsetParent).map((node) => ({ text: node.textContent.trim(), disabled: node.disabled, className: node.className })),
    }));
    process.stdout.write(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.stack || error); process.exit(1); });
