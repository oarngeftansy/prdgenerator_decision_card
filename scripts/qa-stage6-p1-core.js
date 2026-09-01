const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = process.env.STAGE6_JOB_ID || "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage6-browser-acceptance", "tc02");
const marker = "【S6-TC02 保存恢复自检】";

async function waitForP1(page) {
  await page.locator('#reviewWorkspace[data-active-view="gameplay_directory"]').waitFor({ state: "visible" });
  await page.getByLabel("当前章节说明").waitFor({ state: "visible" });
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });

  await page.goto(`${origin}/?job=${jobId}&ui=gameplay_directory`, { waitUntil: "networkidle" });
  await waitForP1(page);
  const description = page.getByLabel("当前章节说明");
  const current = await description.inputValue();
  const original = current.endsWith(marker) ? current.slice(0, -marker.length) : current;
  const changed = `${original}${marker}`;

  await description.fill(changed);
  await page.getByRole("button", { name: "保存修改", exact: true }).click();
  const status = page.locator(".gameplay-directory-status");
  await page.waitForTimeout(100);
  const saveStatusEarly = await status.innerText();
  await page.waitForTimeout(400);
  const saveStatusSettled = await status.innerText();
  await page.reload({ waitUntil: "networkidle" });
  await waitForP1(page);
  const afterRefresh = await description.inputValue();
  if (afterRefresh !== changed) throw new Error(`P1 保存后刷新未恢复：${afterRefresh}`);
  await page.screenshot({ path: path.join(output, "S6-TC02-P1-saved-after-refresh.png"), fullPage: true });

  await page.getByRole("button", { name: "确认理解和目录，开始审核", exact: true }).click();
  await page.locator('#reviewWorkspace[data-active-view="flow"]').waitFor({ state: "visible", timeout: 10000 });
  const routeAfterConfirm = new URL(page.url()).searchParams.get("ui");
  if (routeAfterConfirm !== "flow") throw new Error(`P1 确认后路由错误：${routeAfterConfirm}`);
  await page.screenshot({ path: path.join(output, "S6-TC02-P1-confirm-enters-P2.png"), fullPage: true });

  await page.locator('[data-workbench-step="p1"]').click();
  await waitForP1(page);
  await description.fill(original);
  await page.getByRole("button", { name: "保存修改", exact: true }).click();
  await page.waitForTimeout(500);
  await page.reload({ waitUntil: "networkidle" });
  await waitForP1(page);
  const restored = await description.inputValue();
  if (restored !== original) throw new Error("P1 测试数据清理失败");
  await page.getByRole("button", { name: "确认理解和目录，开始审核", exact: true }).click();
  await page.locator('#reviewWorkspace[data-active-view="flow"]').waitFor({ state: "visible", timeout: 10000 });
  const canonical = await page.evaluate(async job => fetch(`/api/jobs/${job}/gameplay-review-model`).then(response => response.json()), jobId);
  if (canonical.directory?.status !== "confirmed") throw new Error(`目录状态未恢复：${canonical.directory?.status}`);

  const result = {
    jobId,
    original,
    changed,
    afterRefresh,
    routeAfterConfirm,
    restored,
    finalDirectoryStatus: canonical.directory.status,
    saveStatusEarly,
    saveStatusSettled,
    saveFeedbackVisible: [saveStatusEarly, saveStatusSettled].some(value => value.includes("已保存") || value.includes("保存成功")),
    errors,
  };
  if (errors.length) throw new Error(errors.join("\n"));
  fs.writeFileSync(path.join(output, "S6-TC02-core-result.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
