const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");

const url = "http://192.168.50.67:8000/?job=8312a91c89e144e6a59f81b982f14c06&ui=final_preview";
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const failed = [];
  page.on("requestfailed", request => failed.push({ url: request.url(), error: request.failure()?.errorText }));
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 30000 });
  await page.locator('[data-workbench-step="p7"]').evaluate(node => node.click());
  await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
  await page.waitForTimeout(1500);
  const result = await page.evaluate(() => [...document.querySelectorAll(".final-document-planning-board,.final-document-competitor-board")].map(section => {
    const canvas = section.querySelector(".final-document-planning-board-canvas");
    const svg = canvas?.querySelector("svg");
    const images = [...(svg?.querySelectorAll("image") || [])];
    return {
      kind: section.classList.contains("final-document-competitor-board") ? "competitor" : "planning",
      sectionRect: section.getBoundingClientRect().toJSON(), canvasRect: canvas?.getBoundingClientRect().toJSON(),
      scrollLeft: canvas?.scrollLeft, scrollWidth: canvas?.scrollWidth, clientWidth: canvas?.clientWidth,
      svgWidth: svg?.getAttribute("width"), viewBox: svg?.getAttribute("viewBox"), imageCount: images.length,
      images: images.map(image => { const href = image.getAttribute("href") || image.getAttribute("xlink:href") || ""; return ({ hrefKind: href.slice(0, 24), hrefLength: href.length, rect: image.getBoundingClientRect().toJSON() }); }),
      textLength: svg?.textContent?.trim().length || 0,
    };
  }));
  const output = path.resolve(__dirname, "..", "artifacts", "stage5-live-boards");
  fs.mkdirSync(output, { recursive: true });
  await page.locator(".final-document-planning-board").screenshot({ path: path.join(output, "planning-board-live.png"), animations: "disabled" });
  await page.locator(".final-document-competitor-board").screenshot({ path: path.join(output, "competitor-board-live.png"), animations: "disabled" });
  console.log(JSON.stringify({ result, failed }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
