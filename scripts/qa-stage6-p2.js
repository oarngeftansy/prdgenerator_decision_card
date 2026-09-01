const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage6-browser-acceptance", "tc03");
const marker = "【S6-TC03 保存恢复自检】";

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const failures = []; const requests = []; const errors = [];
  page.on("response", response => { if (response.status() >= 400) failures.push({ status: response.status(), url: response.url() }); });
  page.on("request", request => { if (request.method() !== "GET" && request.url().includes("review")) requests.push({ url: request.url(), body: request.postData() }); });
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && !message.text().includes("Failed to load resource")) errors.push(message.text()); });

  await page.goto(`${origin}/?job=${jobId}&ui=flow`, { waitUntil: "networkidle" });
  await page.locator('#reviewWorkspace[data-active-view="flow"]').waitFor();
  await page.locator(".interaction-stage-nav-item").first().click();
  await page.waitForFunction(() => [...document.querySelectorAll(".interaction-stage-nav-item")].findIndex(node => node.classList.contains("is-active")) === 0);
  const initial = await page.evaluate(async job => fetch(`/api/jobs/${job}/review-model`).then(response => response.json()), jobId);
  const firstStage = initial.stages[0];
  const editor = page.locator(".interaction-stage-editor-form");
  const action = editor.locator("textarea").nth(1);
  const originalAction = await action.inputValue();

  await action.fill(`${originalAction}${marker}`);
  await editor.getByRole("button", { name: "保存修改", exact: true }).click();
  await page.waitForFunction(text => document.body.innerText.includes(text), marker);
  await page.reload({ waitUntil: "networkidle" });
  await page.locator('#reviewWorkspace[data-active-view="flow"]').waitFor();
  const afterRefresh = await page.locator(".interaction-stage-editor-form textarea").nth(1).inputValue();
  if (!afterRefresh.endsWith(marker)) throw new Error("P2 保存后刷新未恢复");
  await page.screenshot({ path: path.join(output, "S6-TC03-P2-saved-after-refresh.png"), fullPage: true });

  await page.locator('button[aria-label="撤销最近的审核修改"]').click();
  await page.waitForFunction(text => !document.body.innerText.includes(text), marker);
  const restoredAction = await page.locator(".interaction-stage-editor-form textarea").nth(1).inputValue();
  if (restoredAction !== originalAction) throw new Error("P2 撤销后操作文案未恢复");

  const board = page.locator(".interaction-flow-board");
  await board.evaluate(node => { node.scrollLeft = Math.min(300, node.scrollWidth - node.clientWidth); node.scrollTop = 20; });
  const beforeFit = await board.evaluate(node => ({ left: node.scrollLeft, top: node.scrollTop }));
  await page.getByRole("button", { name: "适配画板", exact: true }).click();
  await page.waitForFunction(() => { const node = document.querySelector(".interaction-flow-board"); return node && node.scrollLeft === 0 && node.scrollTop === 0; });
  const afterFit = await board.evaluate(node => ({ left: node.scrollLeft, top: node.scrollTop }));

  const nav = page.locator(".interaction-stage-nav-item");
  const navCount = await nav.count(); const visited = [];
  for (let index = 0; index < navCount; index += 1) {
    await nav.nth(index).click();
    await page.waitForFunction(target => [...document.querySelectorAll(".interaction-stage-nav-item")].findIndex(node => node.classList.contains("is-active")) === target, index);
    visited.push((await nav.nth(index).innerText()).trim());
  }

  await nav.nth(0).click();
  await page.getByRole("button", { name: "应用并下一环节", exact: true }).click();
  await page.waitForFunction(() => [...document.querySelectorAll(".interaction-stage-nav-item")].findIndex(node => node.classList.contains("is-active")) === 1);
  await page.screenshot({ path: path.join(output, "S6-TC03-P2-apply-next-stage.png"), fullPage: true });

  await nav.nth(3).click();
  await page.waitForTimeout(700);
  await page.reload({ waitUntil: "networkidle" });
  await page.locator('#reviewWorkspace[data-active-view="flow"]').waitFor();
  const selectedAfterRefresh = await page.locator(".interaction-stage-nav-item").evaluateAll(nodes => nodes.findIndex(node => node.classList.contains("is-active")));
  if (selectedAfterRefresh !== 3) throw new Error(`P2 环节刷新后复位到 ${selectedAfterRefresh + 1}`);
  await page.screenshot({ path: path.join(output, "S6-TC03-P2-selection-after-refresh.png"), fullPage: true });

  await page.locator(".interaction-stage-nav-item").first().click();
  const final = await page.evaluate(async job => fetch(`/api/jobs/${job}/review-model`).then(response => response.json()), jobId);
  const finalStage = final.stages.find(stage => stage.id === firstStage.id);
  const result = { firstStageId: firstStage.id, originalAction, afterRefresh, restoredAction, beforeFit, afterFit, navCount, visited, selectedAfterRefresh, finalAction: finalStage.smallLoop?.trigger || finalStage.userAction || finalStage.trigger || "", failures, errors, requests };
  if (result.finalAction !== originalAction || failures.length || errors.length) throw new Error(JSON.stringify(result));
  fs.writeFileSync(path.join(output, "S6-TC03-result.json"), JSON.stringify(result, null, 2));
  await page.screenshot({ path: path.join(output, "S6-TC03-P2-final-restored.png"), fullPage: true });
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
