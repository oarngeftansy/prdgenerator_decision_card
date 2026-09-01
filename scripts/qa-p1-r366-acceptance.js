const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.P1_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "p1-r366-acceptance");
const expected = ["载具", "武器", "局内强化", "终极强化", "武器抽取", "怪物", "关卡", "结算"];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  const errors = [];
  const failedResponses = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("response", response => { if (response.status() >= 400) failedResponses.push({ status: response.status(), url: response.url() }); });

  await page.goto(`${origin}/?job=${jobId}&ui=gameplay_directory`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.locator('#reviewWorkspace[data-active-view="gameplay_directory"]').waitFor({ state: "visible" });
  await page.getByLabel("当前章节说明").waitFor({ state: "visible" });

  const titles = await page.locator('input[aria-label^="第"][aria-label$="章名称"]').evaluateAll(nodes => nodes.map(node => node.value));
  if (JSON.stringify(titles) !== JSON.stringify(expected)) throw new Error(`P1 目录不一致：${JSON.stringify(titles)}`);
  const canonical = await page.evaluate(async job => fetch(`/api/jobs/${job}/gameplay-review-model`).then(response => response.json()), jobId);
  if (canonical.revision !== 369) throw new Error(`正式任务 revision 不是 369：${canonical.revision}`);
  if (canonical.chapters.length !== 8) throw new Error(`章节数量不是 8：${canonical.chapters.length}`);
  if (!canonical.chapters.every(chapter => chapter.fieldDictionary?.length && chapter.lifecycleRules?.length && chapter.formulaStatus)) {
    throw new Error("字段映射、公式状态或生命周期仍有空缺");
  }

  await page.screenshot({ path: path.join(output, "P1-TC01-eight-chapter-overview.png"), fullPage: true });
  const observations = {};
  for (const [caseId, title, required] of [
    ["P1-TC02", "怪物", ["移动", "攻击", "受击", "死亡"]],
    ["P1-TC03", "关卡", ["波次", "首领", "计时", "胜负"]],
    ["P1-TC04", "结算", ["成功", "失败", "中断", "奖励"]],
  ]) {
    await page.locator(".gameplay-directory-tree-item").nth(expected.indexOf(title)).click();
    const description = await page.getByLabel("当前章节说明").inputValue();
    if (!required.every(term => description.includes(term))) {
      throw new Error(`${title}职责说明缺项：${description}`);
    }
    observations[caseId] = { title, description };
    await page.screenshot({ path: path.join(output, `${caseId}-${title}-responsibility.png`), fullPage: true });
  }

  if (errors.length || failedResponses.length) throw new Error(JSON.stringify({ errors, failedResponses }));
  const result = { jobId, revision: canonical.revision, titles, observations, errors, failedResponses };
  fs.writeFileSync(path.join(output, "p1-r366-result.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
