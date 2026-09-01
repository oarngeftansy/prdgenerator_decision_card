const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage6-browser-acceptance", "tc02");
const marker = "【S6-TC02 理解编辑自检】";

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const failures = []; const requests = [];
  page.on("response", response => { if (response.status() >= 400) failures.push({ status: response.status(), url: response.url() }); });
  page.on("request", request => { if (request.method() !== "GET" && request.url().includes("gameplay-review-model")) requests.push({ url: request.url(), body: request.postData() }); });
  page.on("dialog", async dialog => dialog.type() === "prompt" ? dialog.accept("S6临时系统") : dialog.accept());
  await page.goto(`${origin}/?job=${jobId}&ui=gameplay_directory`, { waitUntil: "networkidle" });
  const initial = await page.evaluate(async job => fetch(`/api/jobs/${job}/gameplay-review-model`).then(response => response.json()), jobId);
  const originalUnderstanding = initial.directory.understanding.summary;
  const originalTitles = initial.directory.entries.map(entry => entry.title);
  const originalSystems = initial.systems.map(system => system.name);

  await page.getByRole("button", { name: "编辑玩法理解", exact: true }).click();
  const understanding = page.getByLabel("玩法概述，最多四句话");
  await understanding.fill(`${originalUnderstanding}${marker}`);
  await page.getByRole("button", { name: "保存玩法理解", exact: true }).click();
  await page.waitForFunction(text => document.body.innerText.includes(text), marker);
  await page.locator('button[aria-label="撤销最近的审核修改"]').click();
  await page.waitForFunction(text => !document.body.innerText.includes(text), marker);

  await page.getByRole("button", { name: "+ 添加系统", exact: true }).click();
  await page.waitForFunction(count => document.querySelector(".gameplay-directory-heading")?.innerText.includes(`${count} 系统`), originalSystems.length + 1);
  await page.screenshot({ path: path.join(output, "S6-TC02-P1-add-system-real-action.png"), fullPage: true });
  await page.locator('button[aria-label="撤销最近的审核修改"]').click();
  await page.waitForFunction(count => document.querySelector(".gameplay-directory-heading")?.innerText.includes(`${count} 系统`), originalSystems.length);

  await page.getByRole("button", { name: "添加一个玩法章节", exact: true }).click();
  await page.waitForFunction(count => document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]').length === count, originalTitles.length + 1);
  await page.locator('button[aria-label="撤销最近的审核修改"]').click();
  await page.waitForFunction(count => document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]').length === count, originalTitles.length);

  await page.locator(".gameplay-directory-tree-item").first().click();
  await page.getByRole("button", { name: "与下一项合并", exact: true }).click();
  await page.waitForFunction(count => document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]').length === count, originalTitles.length - 1);
  await page.screenshot({ path: path.join(output, "S6-TC02-P1-merge-real-action.png"), fullPage: true });
  await page.locator('button[aria-label="撤销最近的审核修改"]').click();
  await page.waitForFunction(count => document.querySelectorAll('input[aria-label^="第"][aria-label$="章名称"]').length === count, originalTitles.length);

  await page.getByRole("button", { name: "确认理解和目录，开始审核", exact: true }).click();
  await page.locator('#reviewWorkspace[data-active-view="flow"]').waitFor({ state: "visible", timeout: 10000 });
  const final = await page.evaluate(async job => fetch(`/api/jobs/${job}/gameplay-review-model`).then(response => response.json()), jobId);
  const result = {
    originalTitles, finalTitles: final.directory.entries.map(entry => entry.title),
    originalSystems, finalSystems: final.systems.map(system => system.name),
    understandingRestored: final.directory.understanding.summary === originalUnderstanding,
    directoryStatus: final.directory.status, revision: final.revision, requests, failures,
  };
  if (JSON.stringify(result.finalTitles) !== JSON.stringify(originalTitles) || JSON.stringify(result.finalSystems) !== JSON.stringify(originalSystems) || !result.understandingRestored || result.directoryStatus !== "confirmed" || failures.length) throw new Error(JSON.stringify(result));
  fs.writeFileSync(path.join(output, "S6-TC02-extra-controls-result.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
