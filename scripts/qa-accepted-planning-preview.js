const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8031").replace(/\/$/, "");
const output = path.resolve(option("--output"));
const edge = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: edge });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const report = { cases: [], consoleErrors: [], pageErrors: [], failedRequests: [] };
  page.on("console", (message) => { if (message.type() === "error") report.consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => report.pageErrors.push(error.message));
  page.on("requestfailed", (request) => report.failedRequests.push(request.url()));
  const tabs = [
    ["planning", "执行策划案"], ["ue", "UE 流转图"], ["sketch", "策划草图"],
    ["competitor", "竞品参考"], ["diagrams", "必要图解"], ["parameters", "参数配置表"],
    ["benchmark", "GVE16 逐章核对"],
  ];
  try {
    await page.goto(`${base}/accepted-planning-preview`, { waitUntil: "networkidle" });
    const planningText = await page.locator("#planning").innerText();
    assert.match(planningText, /玩法概述[\s\S]*UE流转图[\s\S]*单局流程[\s\S]*载具[\s\S]*武器[\s\S]*怪物[\s\S]*战斗规则[\s\S]*关卡规则/);
    assert.match(planningText, /怪物[\s\S]*普通怪物[\s\S]*首领[\s\S]*出现[\s\S]*战斗[\s\S]*死亡/);
    assert.match(planningText, /关卡规则[\s\S]*内部逻辑[\s\S]*关卡流程[\s\S]*战斗等级[\s\S]*三选一[\s\S]*独立抽取[\s\S]*战斗统计[\s\S]*胜负判定[\s\S]*外部逻辑/);
    assert.match(planningText, /玩家目标[\s\S]*基础操作[\s\S]*核心循环[\s\S]*成长与资源[\s\S]*怎样获胜[\s\S]*怎样失败[\s\S]*关卡规则/);
    assert.equal(await page.locator("#planning .inline-delivery").count(), 14);
    assert.equal(await page.locator("#planning .native-board-card.inline-delivery").count(), 3);
    assert.equal(await page.locator("#planning .diagram-card.inline-delivery").count(), 5);
    assert.equal(await page.locator("#planning .inline-delivery table").count(), 6);
    for (let index = 0; index < tabs.length; index += 1) {
      const [target, label] = tabs[index];
      const button = page.locator(`.tabs button[data-target="${target}"]`);
      await button.click();
      assert.equal(await button.evaluate((node) => node.classList.contains("active")), true);
      assert.equal(await page.locator(`#${target}`).isVisible(), true);
      for (const [other] of tabs.filter(([key]) => key !== target)) assert.equal(await page.locator(`#${other}`).isHidden(), true);
      const screenshot = `WEB-FINAL-${String(index + 1).padStart(2, "0")}-${target}.png`;
      await page.screenshot({ path: path.join(output, screenshot), fullPage: false, animations: "disabled" });
      report.cases.push({ id: `WEB-FINAL-${String(index + 1).padStart(2, "0")}`, title: label, target, screenshot });
      await page.goto(`${base}/accepted-planning-preview?tab=${target}`, { waitUntil: "networkidle" });
      assert.equal(await page.locator(`#${target}`).isVisible(), true);
      await page.reload({ waitUntil: "networkidle" });
      assert.equal(await page.locator(`#${target}`).isVisible(), true);
    }
    assert.equal(await page.locator("#ue svg").count(), 1);
    assert.equal(await page.locator("#sketch svg").count(), 1);
    assert.equal(await page.locator("#competitor svg").count(), 1);
    assert.equal(await page.locator("#diagrams svg").count(), 5);
    assert.equal(await page.locator("#parameters table").count(), 6);
    assert.deepEqual(report.consoleErrors, []);
    assert.deepEqual(report.pageErrors, []);
    assert.deepEqual(report.failedRequests, []);
    report.completed = true;
    fs.writeFileSync(path.join(output, "acceptance.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ completed: true, cases: report.cases.length }, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
