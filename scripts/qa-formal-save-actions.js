const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8014").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));
async function waitView(page, view) { await page.waitForFunction((expected) => document.querySelector("#reviewWorkspace")?.dataset.activeView === expected, view); }
function approvedCount(summary) {
  const match = String(summary || "").match(/(\d+)\s*\u5df2\u901a\u8fc7/);
  assert.ok(match, `missing approved count in summary: ${summary}`);
  return Number(match[1]);
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(30000);
  const errors = [], results = {};
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console: ${message.text()}`); });
  try {
    await page.goto(`${base}/?job=${job}&ui=diagrams`, { waitUntil: "domcontentloaded" });
    await waitView(page, "diagrams");
    await page.waitForFunction(() => (state.gameplayReviewWorkspace?.model?.diagrams || []).length > 0);
    const summaryBefore = (await page.locator(".gameplay-diagram-summary").innerText()).trim();
    const approvedBefore = approvedCount(summaryBefore);
    const chapterButtons = page.locator(".gameplay-diagram-nav-item:visible");
    let approved = false;
    let selectedChapterId = "";
    let selectedWasApproved = false;
    let requestCount = 0;
    page.on("request", (request) => { if (/\/diagrams\/[^/]+\/approve$/.test(request.url()) && request.method() === "POST") requestCount += 1; });
    for (let chapterIndex = 0; chapterIndex < await chapterButtons.count() && !approved; chapterIndex += 1) {
      await chapterButtons.nth(chapterIndex).click();
      selectedChapterId = await chapterButtons.nth(chapterIndex).getAttribute("data-chapter-id");
      const candidates = page.locator('.gameplay-diagram-card:visible:not([data-status="stale"])');
      if (!await candidates.count()) continue;
      selectedWasApproved = (await candidates.first().getAttribute("data-status")) === "reviewed";
      await candidates.first().click();
      const approve = page.locator('.gameplay-diagram-decision input[value="approve"]');
      await approve.check();
      const apply = page.locator(".gameplay-diagram-decision .gameplay-diagram-apply");
      await apply.click();
      await page.waitForFunction(() => !document.querySelector(".gameplay-diagram-decision .gameplay-diagram-apply")?.disabled);
      approved = true;
    }
    assert.equal(approved, true);
    const summaryAfter = (await page.locator(".gameplay-diagram-summary").innerText()).trim();
    const approvedAfter = approvedCount(summaryAfter);
    assert.equal(approvedAfter, approvedBefore + (selectedWasApproved ? 0 : 1));
    assert.equal(requestCount, 1);
    assert.equal(await page.locator(`.gameplay-diagram-nav-item[data-chapter-id="${selectedChapterId}"]`).getAttribute("aria-current"), "true");
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitView(page, "diagrams");
    assert.equal(await page.locator(`.gameplay-diagram-nav-item[data-chapter-id="${selectedChapterId}"]`).getAttribute("aria-current"), "true");
    await page.screenshot({ path: path.join(output, "UX-TC13-diagram-approval-count-refresh.png"), fullPage: false, animations: "disabled" });
    results.diagrams = { summaryBefore, summaryAfter, approvedBefore, approvedAfter, selectedWasApproved, oneRequest: true, chapterPreservedAfterRefresh: true };

    await page.locator('[data-workbench-step="p6"]').click();
    await waitView(page, "tables");
    const tableChapters = page.locator(".gameplay-table-nav-item:visible");
    let targetChapterId = "", targetTableId = "", targetTableTitle = "", confirmedRow = false;
    for (let chapterIndex = 0; chapterIndex < await tableChapters.count() && !confirmedRow; chapterIndex += 1) {
      await tableChapters.nth(chapterIndex).click();
      const visibleCards = page.locator(".gameplay-table-card:visible");
      const cardCount = await visibleCards.count();
      for (let cardIndex = Math.max(0, cardCount - 1); cardIndex >= 0 && !confirmedRow; cardIndex -= 1) {
        const card = visibleCards.nth(cardIndex);
        const confirm = card.getByRole("button", { name: "确认", exact: true }).first();
        if (!await confirm.count()) continue;
        targetChapterId = await tableChapters.nth(chapterIndex).getAttribute("data-chapter-id");
        targetTableTitle = (await card.locator(".gameplay-table-workbar-title").innerText()).trim();
        await confirm.click();
        await page.waitForFunction(() => {
          const id = state.gameplayReviewWorkspace?.selectedTableId;
          const table = (state.gameplayReviewWorkspace?.model?.tables || []).find((item) => item.id === id);
          return Boolean(id && (table?.rowReviews || []).some((review) => review.confirmed));
        });
        targetTableId = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
        confirmedRow = true;
      }
    }
    assert.equal(confirmedRow, true);
    assert.equal(await page.locator(`.gameplay-table-nav-item[data-chapter-id="${targetChapterId}"]`).getAttribute("aria-current"), "true");
    const activeTitle = (await page.locator(".gameplay-table-card.is-active:visible .gameplay-table-workbar-title").innerText()).trim();
    assert.equal(activeTitle, targetTableTitle);
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitView(page, "tables");
    assert.equal(await page.locator(`.gameplay-table-nav-item[data-chapter-id="${targetChapterId}"]`).getAttribute("aria-current"), "true");
    const activeAfterRefresh = (await page.locator(".gameplay-table-card.is-active:visible .gameplay-table-workbar-title").innerText()).trim();
    assert.equal(activeAfterRefresh, targetTableTitle);
    await page.screenshot({ path: path.join(output, "UX-TC14-parameter-confirm-keeps-table.png"), fullPage: false, animations: "disabled" });
    results.tables = { targetChapterId, targetTableId, targetTableTitle, confirmedRow: true, tablePreservedAfterResponse: true, tablePreservedAfterRefresh: true };

    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "save-actions.json"), JSON.stringify({ passed: true, results, errors }, null, 2));
    console.log(JSON.stringify({ passed: true, results }, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
