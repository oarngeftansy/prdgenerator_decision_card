const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const output = path.resolve(__dirname, "..", "artifacts", "stage6-rule-sections");
fs.mkdirSync(output, { recursive: true });
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto("http://127.0.0.1:8000/?job=8312a91c89e144e6a59f81b982f14c06&ui=final_preview", { waitUntil: "networkidle", timeout: 40000 });
  const heading = page.getByText("触发与战斗状态", { exact: true }).last();
  await heading.scrollIntoViewIfNeeded();
  const section = heading.locator("xpath=ancestor::*[contains(@class,'final-document-content')]");
  const text = await section.innerText();
  const result = {
    headings: ["触发与战斗状态", "属性与承伤判定", "胜负结算"].map((value) => ({ value, count: text.split(value).length - 1 })),
    duplicateConfirmSentenceCount: text.split("不要求玩家点击确认").length - 1,
    hasGenericOtherRules: text.includes("其他规则"),
  };
  await heading.evaluate((node) => {
    const scroller = node.closest(".final-document-scroll");
    if (scroller) scroller.scrollTop = Math.max(0, node.offsetTop - 180);
  });
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(output, "S6R-TC5-boss-rules-semantic-sections.png") });
  fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
