const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.P5_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "p5-stale-recovery-acceptance");
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

function snapshot(model) {
  return {
    revision: model.revision,
    diagrams: (model.diagrams || []).filter(item => item.status !== "deleted").map(item => ({
      id: item.id,
      title: item.title,
      status: item.status,
      revision: item.revision,
      chapterIds: item.chapterIds,
    })),
    chapterCount: (model.chapters || []).length,
    tableCount: (model.tables || []).length,
  };
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  await page.addInitScript(() => {
    window.snapshotForQa = model => ({
      revision: model.revision,
      diagrams: (model.diagrams || []).filter(item => item.status !== "deleted").map(item => ({ id: item.id, title: item.title, status: item.status, revision: item.revision, chapterIds: item.chapterIds, hasConnector: /<(?:line|path|polyline)\b/i.test(item.svg || ""), hasArrow: /<polygon\b/i.test(item.svg || "") })),
      chapterCount: (model.chapters || []).length,
      tableCount: (model.tables || []).length,
    });
  });
  page.setDefaultTimeout(20000);
  const errors = [];
  page.on("pageerror", error => errors.push(`pageerror:${error.message}`));
  page.on("console", message => { if (message.type() === "error") errors.push(`console:${message.text()}`); });

  try {
    await page.goto(`${origin}/?job=${jobId}&ui=diagrams`, { waitUntil: "networkidle", timeout: 40000 });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible" });
    await page.locator(".gameplay-diagrams").waitFor({ state: "visible" });

    const before = await page.evaluate(() => snapshotForQa(state.gameplayReviewWorkspace.model));
    assert.equal(before.diagrams.length, 6, "正式任务应有 6 张有效图解");
    assert.equal(before.diagrams.filter(item => item.status === "stale").length, 5, "更新前应有 5 张过期图解");
    assert.equal(before.diagrams.filter(item => item.status === "reviewed").length, 1, "更新前应有 1 张已通过图解");
    assert.match(await page.locator(".gameplay-diagram-summary").innerText(), /5 张需按最新正文更新/);
    assert.match(await page.locator(".gameplay-diagram-stale-notice").innerText(), /关联玩法正文已经修改/);
    await page.screenshot({ path: path.join(output, "TC1-overdue-reason-full.png"), fullPage: true, animations: "disabled" });

    await page.locator(".gameplay-diagram-refresh-stale").click();
    await page.waitForFunction(() => {
      const model = state.gameplayReviewWorkspace?.model;
      return model && (model.diagrams || []).filter(item => item.status === "stale").length === 0;
    });
    await page.locator(".gameplay-diagram-card").first().waitFor({ state: "visible" });
    const refreshed = await page.evaluate(() => snapshotForQa(state.gameplayReviewWorkspace.model));
    assert.equal(refreshed.diagrams.filter(item => item.status === "stale").length, 0);
    assert.equal(refreshed.diagrams.filter(item => item.status === "open").length, 5);
    assert.equal(refreshed.diagrams.filter(item => item.hasConnector && item.hasArrow).length, 6, "6张图都必须包含真实连线和箭头");
    assert.equal(await page.locator(".gameplay-diagram-card").count(), 6, "P5 必须显示全部6张有效图解");
    for (const oldItem of before.diagrams.filter(item => item.status === "stale")) {
      const newItem = refreshed.diagrams.find(item => item.id === oldItem.id);
      assert.ok(newItem, `${oldItem.id} 更新后不能丢失`);
      assert.equal(newItem.revision, oldItem.revision + 1, `${oldItem.id} 图版本必须递增`);
      assert.deepEqual(newItem.chapterIds, oldItem.chapterIds, `${oldItem.id} 章节绑定必须保持`);
    }
    const previouslyReviewed = before.diagrams.find(item => item.status === "reviewed");
    const reviewedAfterRefresh = refreshed.diagrams.find(item => item.id === previouslyReviewed.id);
    assert.equal(reviewedAfterRefresh.status, "reviewed", "原已通过图解不能被打回");
    assert.equal(reviewedAfterRefresh.revision, previouslyReviewed.revision, "原已通过图解不能被重复生成");
    await page.screenshot({ path: path.join(output, "TC2-refreshed-awaiting-review-full.png"), fullPage: true, animations: "disabled" });

    let approvedNew = 0;
    while (await page.locator(".gameplay-diagram-card[data-status='open']").count()) {
      const card = page.locator(".gameplay-diagram-card[data-status='open']").first();
      await card.click();
      await page.locator(".gameplay-diagram-decision input[value='approve']").check();
      await page.locator(".gameplay-diagram-decision .gameplay-diagram-apply").click();
      approvedNew += 1;
      if (approvedNew === 1) {
        await page.waitForFunction(() => (state.gameplayReviewWorkspace?.model?.diagrams || []).filter(item => item.status === "reviewed").length === 2);
        await page.screenshot({ path: path.join(output, "TC3-first-approved-full.png"), fullPage: true, animations: "disabled" });
      } else if (approvedNew < 5) {
        await page.waitForFunction(expected => (state.gameplayReviewWorkspace?.model?.diagrams || []).filter(item => item.status === "reviewed").length === expected, approvedNew + 1);
      }
    }
    assert.equal(approvedNew, 5, "应逐张通过 5 张更新后的图解");
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.getAttribute("data-active-view") === "tables");
    assert.equal(new URL(page.url()).searchParams.get("ui"), "tables");
    await page.screenshot({ path: path.join(output, "TC4-entered-P6-full.png"), fullPage: true, animations: "disabled" });

    await page.reload({ waitUntil: "networkidle", timeout: 40000 });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.getAttribute("data-active-view") === "tables");
    assert.equal(new URL(page.url()).searchParams.get("ui"), "tables");
    await page.screenshot({ path: path.join(output, "TC4-refresh-restored-P6-full.png"), fullPage: true, animations: "disabled" });

    const after = await page.evaluate(() => snapshotForQa(state.gameplayReviewWorkspace.model));
    assert.equal(after.diagrams.length, 6);
    assert.equal(after.diagrams.filter(item => item.status === "reviewed").length, 6);
    assert.deepEqual(after.diagrams.map(item => item.id).sort(), before.diagrams.map(item => item.id).sort());
    assert.equal(after.chapterCount, before.chapterCount);
    assert.equal(after.tableCount, before.tableCount);
    fs.writeFileSync(path.join(output, "TC5-data-integrity.json"), JSON.stringify({ before, refreshed, after, browserErrors: errors }, null, 2));
    if (errors.length) throw new Error(`浏览器错误：${errors.join(" | ")}`);
    console.log(JSON.stringify({ passed: true, approvedNew, before, refreshed, after, output }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack || error); process.exit(1); });
