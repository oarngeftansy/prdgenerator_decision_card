const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

const jobId = process.env.STAGE6_JOB_ID || "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8009";
const url = `${origin}/?job=${jobId}&ui=gameplay_directory`;
const output = path.resolve(__dirname, "..", "artifacts", "stage6-browser-acceptance");

let browser;
(async () => {
  fs.mkdirSync(output, { recursive: true });
  browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.setDefaultTimeout(7000);
  const errors = [];
  page.on("console", message => { if (message.type() === "error") errors.push(`console:${message.text()}`); });
  page.on("pageerror", error => errors.push(`pageerror:${error.message}`));
  await page.goto(url, { waitUntil: "domcontentloaded" });
  console.log("loaded");
  await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
  await page.waitForTimeout(750);
  const workbench = page.locator("#reviewWorkspace");
  if (!await workbench.isVisible()) throw new Error("任务链接没有恢复到审核工作台");
  if (await page.locator("#analysisFailedView").isVisible()) throw new Error("任务被错误恢复为分析失败页");
  const buttons = page.locator(".review-step-nav [data-workbench-step]");
  const visibleNumbers = await buttons.locator(".review-step-number").allTextContents();
  assert.deepEqual(visibleNumbers, ["1", "2", "3", "4", "5", "6", "7"]);
  const shellMetrics = await page.evaluate(() => {
    const workspace = document.querySelector("#reviewWorkspace")?.getBoundingClientRect();
    const header = document.querySelector(".review-workspace-header")?.getBoundingClientRect();
    const rows = [...document.querySelectorAll(".review-step-nav [data-workbench-step]")].map(node => Math.round(node.getBoundingClientRect().top));
    const brand = document.querySelector("body > header");
    return {
      workspaceTop: Math.round(workspace?.top || 0),
      headerHeight: Math.round(header?.height || 0),
      navRows: new Set(rows).size,
      brandVisible: Boolean(brand && getComputedStyle(brand).display !== "none"),
    };
  });
  if (shellMetrics.brandVisible) throw new Error("Target workbench must not retain the upload-page brand header");
  if (shellMetrics.workspaceTop !== 0) throw new Error(`Target workbench must start at viewport top: ${shellMetrics.workspaceTop}`);
  if (Math.abs(shellMetrics.headerHeight - 52) > 1) throw new Error(`Target workbench header must be 52px: ${shellMetrics.headerHeight}`);
  if (shellMetrics.navRows !== 1) throw new Error(`P1-P7 navigation must remain in one row: ${shellMetrics.navRows}`);
  if (await buttons.count() !== 7) throw new Error(`P1–P7 导航数量错误：${await buttons.count()}`);
  const expectedViews = ["gameplay_directory", "flow", "interaction_preview", "gameplay", "diagrams", "tables", "final_preview"];
  for (let index = 0; index < 7; index += 1) {
    console.log(`checking-p${index + 1}`);
    const button = page.locator(`[data-workbench-step="p${index + 1}"]`);
    console.log(`view=${await button.getAttribute("data-review-view")},enabled=${await button.isEnabled()}`);
    if (await button.isEnabled()) {
      await button.click();
      await page.waitForTimeout(250);
      if (index === 0) await page.locator(".gameplay-directory-understanding").waitFor({ state: "visible", timeout: 5000 });
      const activeView = await workbench.getAttribute("data-active-view");
      if (index === 1 ? !["flow", "stage"].includes(activeView) : activeView !== expectedViews[index]) throw new Error(`P${index + 1} 点击后没有进入对应页面（当前：${activeView}）`);
      if (!await workbench.isVisible()) throw new Error(`P${index + 1} 点击后工作台被其他页面覆盖`);
      const pageText = (await workbench.innerText()).toLowerCase();
      const pageForbidden = ["undefined", "component", "unknown", "pending_details", "scope:"];
      const pageFound = pageForbidden.filter(item => pageText.includes(item));
      if (pageFound.length) throw new Error(`P${index + 1} 出现内部字段：${pageFound.join("、")}`);
      if (/[',.]{3,}/.test(pageText)) throw new Error(`P${index + 1} 出现无意义符号串`);
      if (index === 0) {
        const p1 = await page.evaluate(() => {
          const left = document.querySelector(".gameplay-directory-understanding")?.getBoundingClientRect();
          const right = document.querySelector(".gameplay-directory-confirm-column")?.getBoundingClientRect();
          const row = document.querySelector(".gameplay-directory-tree-item")?.getBoundingClientRect();
          const selected = document.querySelector(".gameplay-directory-tree-item.is-selected");
          const style = selected ? getComputedStyle(selected) : null;
          return { left: Math.round(left?.width || 0), right: Math.round(right?.width || 0), row: Math.round(row?.height || 0), font: style?.fontFamily || "", background: style?.backgroundColor || "" };
        });
        if (Math.abs(p1.left - 280) > 2) throw new Error(`P1 左栏应为 280px，当前 ${p1.left}px`);
        if (Math.abs(p1.right - 320) > 2) throw new Error(`P1 右栏应为 320px，当前 ${p1.right}px`);
        if (p1.row < 44 || p1.row > 60) throw new Error(`P1 目录行高应为 44–60px，当前 ${p1.row}px`);
        if (!/Microsoft YaHei|PingFang SC/.test(p1.font)) throw new Error(`P1 未使用目标中文字体栈：${p1.font}`);
        if (p1.background !== "rgb(238, 243, 255)") throw new Error(`P1 选择态颜色不符合目标稿：${p1.background}`);
        const rows = page.locator(".gameplay-directory-tree-item");
        if (await rows.count() > 1) {
          const expectedTitle = await rows.nth(1).locator("input").inputValue();
          await rows.nth(1).click();
          await page.waitForTimeout(100);
          const actualTitle = await page.locator('.gameplay-directory-editor input[aria-label="当前章节名称"]').inputValue();
          if (actualTitle !== expectedTitle) throw new Error(`P1 点击下一章后右侧没有同步：期望“${expectedTitle}”，实际“${actualTitle}”`);
          if (!await rows.nth(1).evaluate(node => node.classList.contains("is-selected"))) throw new Error("P1 点击下一章后选中态没有切换");
        }
      }
      if (index === 1) {
        const stageButtons = page.locator("#stageReviewView:visible .planner-stage-button:visible");
        const stageCount = await stageButtons.count();
        if (stageCount > 1) {
          const image = page.locator("#stageReviewView:visible .planner-frame-viewer img:visible");
          if (await image.count() !== 1) throw new Error("P2 当前环节没有唯一对应截图");
          const beforeSrc = await image.getAttribute("src");
          await stageButtons.nth(1).click();
          await page.waitForTimeout(250);
          if (await image.count() !== 1) throw new Error("P2 切换环节后截图数量异常");
          const afterSrc = await image.getAttribute("src");
          if (!afterSrc || afterSrc === beforeSrc) throw new Error("P2 切换环节后仍显示上一环节截图");
          const exclusiveGroups = await page.locator('#stageReviewView input[type="radio"]').evaluateAll(nodes => {
            const groups = {};
            nodes.forEach(node => { if (!node.name) return; groups[node.name] = (groups[node.name] || 0) + (node.checked ? 1 : 0); });
            return Object.values(groups);
          });
          if (exclusiveGroups.some(count => count > 1)) throw new Error("P2 互斥选项出现同时选中");
        }
      }
    }
    await page.screenshot({ path: path.join(output, `p${index + 1}.png`) });
    console.log(`checked-p${index + 1}`);
  }
  if (errors.length) throw new Error(errors.join("；"));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; })
  .finally(async () => { await browser?.close().catch(() => {}); });
