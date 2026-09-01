const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const job = "8312a91c89e144e6a59f81b982f14c06";
const url = `http://127.0.0.1:8000/?job=${job}&ui=final_preview`;
const output = path.resolve(__dirname, "..", "artifacts", "stage6-cross-carrier-layout");
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(url, { waitUntil: "networkidle", timeout: 40000 });
  await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 20000 });

  const shell = page.locator(".final-document-shell");
  const bodyText = await shell.innerText();
  const required = [
    "局内强化与效果", "剧毒炮：学习剧毒炮", "迅猛喷射：本次截图显示",
    "火焰扩张：本次截图显示",
  ];
  const forbidden = [
    "图中的升级、首领和胜负节点由后续章节分别展开", "本节继续说明载具推进与生存边界",
  ];
  const assertions = {
    required: Object.fromEntries(required.map((text) => [text, bodyText.includes(text)])),
    forbidden: Object.fromEntries(forbidden.map((text) => [text, bodyText.includes(text)])),
  };

  const weaponHeading = shell.getByText("局内强化与效果", { exact: true }).first();
  await weaponHeading.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(output, "S6R-TC1-weapon-board-facts-in-prose.png") });

  const diagramInventory = await shell.evaluate((root) => {
    const scroller = root.querySelector(".final-document-scroll");
    const diagrams = [...root.querySelectorAll(".final-document-gameplay-diagram")];
    const diagram = diagrams.find((item) => item.innerText.includes("关卡完整主循环")) || diagrams.find((item) => item.querySelector("svg")) || diagrams[0];
    if (scroller && diagram) scroller.scrollTop = Math.max(0, diagram.offsetTop - 420);
    return diagrams.map((item) => ({ text: item.innerText.slice(0, 80), title: item.getAttribute("aria-label"), offsetTop: item.offsetTop }));
  });
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(output, "S6R-TC2-complete-rules-before-diagram.png") });

  const responsive = {};
  for (const [label, width] of [["narrow", 1000], ["compact", 680]]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.waitForTimeout(350);
    await shell.locator(".final-document-status").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    const metrics = await shell.evaluate((root) => {
      const status = root.querySelector(".final-document-status");
      const button = root.querySelector(".final-document-footer .btn");
      const rect = status.getBoundingClientRect();
      const buttonRect = button?.getBoundingClientRect();
      return {
        statusWidth: Math.round(rect.width),
        buttonWidth: Math.round(buttonRect?.width || 0),
        statusOverflow: status.scrollWidth > status.clientWidth + 1,
        buttonOverflow: Boolean(buttonRect && (buttonRect.left < rect.left - 1 || buttonRect.right > rect.right + 1)),
        statusDisplay: getComputedStyle(status).display,
      };
    });
    responsive[label] = metrics;
    await page.screenshot({ path: path.join(output, `S6R-TC3-${label}-feishu-export-layout.png`) });
    await shell.locator(".final-document-footer").screenshot({ path: path.join(output, `S6R-TC3-${label}-feishu-export-footer.png`) });
  }

  fs.writeFileSync(path.join(output, "result.json"), JSON.stringify({ assertions, diagramInventory, responsive }, null, 2));
  console.log(JSON.stringify({ assertions, diagramInventory, responsive }, null, 2));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
