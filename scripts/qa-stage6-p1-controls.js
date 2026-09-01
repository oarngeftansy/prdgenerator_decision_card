const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = process.env.STAGE6_JOB_ID || "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage6-browser-acceptance", "tc02");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const errors = [];
  const failedResponses = [];
  const requests = [];
  page.on("dialog", dialog => dialog.accept());
  page.on("pageerror", error => errors.push(error.message));
  page.on("response", response => { if (response.status() >= 400) failedResponses.push({ status: response.status(), url: response.url() }); });
  page.on("request", request => {
    if (request.url().includes("gameplay-review-model")) requests.push({ method: request.method(), url: request.url(), body: request.postData() });
  });
  page.on("console", message => { if (message.type() === "error" && !message.text().includes("Failed to load resource")) errors.push(message.text()); });
  await page.goto(`${origin}/?job=${jobId}&ui=gameplay_directory`, { waitUntil: "networkidle" });
  await page.getByLabel("当前章节说明").waitFor();

  const titles = () => page.locator('input[aria-label^="第"][aria-label$="章名称"]').evaluateAll(nodes => nodes.map(node => node.value));
  const beforeTitles = await titles();
  const originalSummary = await page.getByLabel("当前章节说明").inputValue();

  await page.getByLabel("当前章节说明").fill(`${originalSummary}未保存内容`);
  await page.getByRole("button", { name: "取消", exact: true }).click();
  const afterCancel = await page.getByLabel("当前章节说明").inputValue();
  if (afterCancel !== originalSummary) throw new Error("取消按钮没有恢复当前章节说明");

  await page.getByRole("button", { name: "+ 添加章节", exact: true }).click();
  await page.waitForFunction(count => document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]').length === count, beforeTitles.length + 1);
  const afterAddCount = (await titles()).length;
  if (afterAddCount !== beforeTitles.length + 1) throw new Error(`添加章节数量错误：${afterAddCount}`);
  await page.locator(".gameplay-directory-tree-item").last().click();
  await page.getByRole("button", { name: "删除空章节", exact: true }).click();
  await page.waitForFunction(count => document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]').length === count, beforeTitles.length);
  const afterDeleteTitles = await titles();
  if (JSON.stringify(afterDeleteTitles) !== JSON.stringify(beforeTitles)) throw new Error("临时空章节删除后目录未恢复");

  await page.locator(".gameplay-directory-tree-item").first().click();
  await page.getByRole("button", { name: "↓ 下移", exact: true }).click();
  await page.waitForFunction(before => JSON.stringify([...document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]')].map(node => node.value)) !== JSON.stringify(before), beforeTitles);
  const movedTitles = await titles();
  if (JSON.stringify(movedTitles) === JSON.stringify(beforeTitles)) throw new Error("下移按钮未改变目录顺序");
  await page.locator('button[aria-label="撤销最近的审核修改"]').click();
  await page.waitForFunction(before => JSON.stringify([...document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]')].map(node => node.value)) === JSON.stringify(before), beforeTitles);
  const afterUndoTitles = await titles();
  if (JSON.stringify(afterUndoTitles) !== JSON.stringify(beforeTitles)) throw new Error("撤销未恢复目录顺序");

  const radios = page.locator('input[name="gameplay-directory-module"]');
  const checkedBefore = await radios.evaluateAll(nodes => nodes.findIndex(node => node.checked));
  const alternative = checkedBefore === 0 ? 1 : 0;
  await radios.nth(alternative).check();
  await page.waitForFunction(index => [...document.querySelectorAll('input[name="gameplay-directory-module"]')].findIndex(node => node.checked) === index, alternative);
  const checkedChanged = await radios.evaluateAll(nodes => nodes.findIndex(node => node.checked));
  if (checkedChanged !== alternative) throw new Error("模块切换未生效");
  await page.locator('button[aria-label="撤销最近的审核修改"]').click();
  await page.waitForFunction(index => [...document.querySelectorAll('input[name="gameplay-directory-module"]')].findIndex(node => node.checked) === index, checkedBefore);
  const checkedRestored = await radios.evaluateAll(nodes => nodes.findIndex(node => node.checked));
  if (checkedRestored !== checkedBefore) throw new Error("模块切换撤销后未恢复");

  await page.getByRole("button", { name: "确认理解和目录，开始审核", exact: true }).click();
  await page.locator('#reviewWorkspace[data-active-view="flow"]').waitFor({ state: "visible", timeout: 10000 });
  await page.locator('[data-workbench-step="p1"]').click();
  await page.locator('#reviewWorkspace[data-active-view="gameplay_directory"]').waitFor({ state: "visible" });

  await page.reload({ waitUntil: "networkidle" });
  await page.getByLabel("当前章节说明").waitFor();
  const finalTitles = await titles();
  if (JSON.stringify(finalTitles) !== JSON.stringify(beforeTitles)) throw new Error("刷新后目录与初始快照不同");
  if (errors.length || failedResponses.length) throw new Error(JSON.stringify({ errors, failedResponses, requests }));
  const canonical = await page.evaluate(async job => fetch(`/api/jobs/${job}/gameplay-review-model`).then(response => response.json()), jobId);
  if (canonical.directory?.status !== "confirmed") throw new Error(`目录状态未恢复：${canonical.directory?.status}`);
  const result = { beforeTitles, afterCancel, afterAddCount, afterDeleteTitles, movedTitles, afterUndoTitles, checkedBefore, checkedChanged, checkedRestored, finalTitles, directoryStatus: canonical.directory.status, revision: canonical.revision, errors, failedResponses, requests };
  fs.writeFileSync(path.join(output, "S6-TC02-controls-result.json"), JSON.stringify(result, null, 2));
  await page.screenshot({ path: path.join(output, "S6-TC02-P1-controls-cleaned.png"), fullPage: true });
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
