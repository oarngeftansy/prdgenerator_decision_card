const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name) { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] : ""; }
const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(20000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem("vpr_client_cache_schema", "legacy-ui-cache");
    localStorage.setItem("vpr_gameplay_review_ui_stale", "stale");
    localStorage.setItem("vpr_planning_board_ui_stale", "stale");
    localStorage.setItem("vpr_last_job", "must-survive");
    localStorage.setItem("vpr_api_key", "must-survive");
  });
  try {
    await page.goto(`${base}/?job=${job}&ui=gameplay`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay");
    const cache = await page.evaluate(() => ({
      gameplay: localStorage.getItem("vpr_gameplay_review_ui_stale"),
      board: localStorage.getItem("vpr_planning_board_ui_stale"),
      job: localStorage.getItem("vpr_last_job"),
      api: localStorage.getItem("vpr_api_key"),
    }));
    assert.deepEqual({ gameplay: cache.gameplay, board: cache.board, api: cache.api }, { gameplay: null, board: null, api: "must-survive" });
    assert.equal(cache.job, job, "the active job key must be updated rather than deleted by cache migration");
    await page.screenshot({ path: path.join(output, "WEB-CACHE-01-migrated.png"), fullPage: true, animations: "disabled" });

    const chapters = page.locator("#gameplayReviewView .gameplay-chapter-item");
    let card = null;
    for (let index = 0; index < await chapters.count(); index += 1) {
      await chapters.nth(index).click();
      const candidate = page.locator("#gameplayReviewView .planner-decision-card").first();
      if (await candidate.count()) { card = candidate; break; }
    }
    assert.ok(card, "at least one pending decision card must be reachable from a chapter");
    assert.equal(await page.evaluate(() => Boolean(state.gameplayOperationQueue)), true, "decision cards require an active gameplay operation queue");
    await card.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, "WEB-DECISION-01-default.png"), fullPage: true, animations: "disabled" });

    const apply = card.getByRole("button", { name: "应用选择", exact: true });
    await apply.click();
    const error = card.locator(".planner-decision-error");
    assert.match((await error.innerText()).trim(), /请选择|填写/);
    await page.screenshot({ path: path.join(output, "WEB-DECISION-02-empty-validation.png"), fullPage: true, animations: "disabled" });

    const radio = card.locator('input[type="radio"]').first();
    await radio.check();
    const custom = card.locator(".planner-decision-custom input");
    await custom.fill("按当前关卡配置触发");
    assert.equal(await radio.isChecked(), false, "custom answer must clear a prior single choice");
    await page.screenshot({ path: path.join(output, "WEB-DECISION-03-custom-exclusive.png"), fullPage: true, animations: "disabled" });
    const cardId = await card.getAttribute("data-decision-card-id");
    const responsePromise = page.waitForResponse((response) => response.url().includes("/gameplay-review-model/operations") && response.request().method() === "POST");
    await apply.click();
    const response = await responsePromise;
    assert.equal(response.ok(), true, `decision apply request failed: ${response.status()} ${await response.text()}`);
    await page.locator(`[data-decision-card-id="${cardId}"]`).waitFor({ state: "hidden" });
    await page.screenshot({ path: path.join(output, "WEB-DECISION-04-applied.png"), fullPage: true, animations: "disabled" });

    await page.locator('[data-review-view="gameplay"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay");
    let remaining = page.locator("#gameplayReviewView .planner-decision-card:visible").first();
    if (!(await remaining.count())) {
      const currentChapters = page.locator("#gameplayReviewView .gameplay-chapter-item");
      for (let index = 0; index < await currentChapters.count(); index += 1) {
        await currentChapters.nth(index).click();
        remaining = page.locator("#gameplayReviewView .planner-decision-card:visible").first();
        if (await remaining.count()) break;
      }
    }
    let skipped = false;
    if (await remaining.count()) {
      const skipResponsePromise = page.waitForResponse((response) => response.url().includes("/gameplay-review-model/operations") && response.request().method() === "POST");
      await remaining.getByRole("button", { name: "暂时跳过", exact: true }).click();
      const skipResponse = await skipResponsePromise;
      assert.equal(skipResponse.ok(), true, `decision skip request failed: ${skipResponse.status()} ${await skipResponse.text()}`);
      skipped = true;
      await page.screenshot({ path: path.join(output, "WEB-DECISION-05-skipped.png"), fullPage: true, animations: "disabled" });
    }
    assert.deepEqual(errors, []);
    const report = { passed: true, cache, customChoiceExclusive: true, applied: true, skipped, errors };
    fs.writeFileSync(path.join(output, "decision-cache-report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
