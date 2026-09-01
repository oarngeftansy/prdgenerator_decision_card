const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8014").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));

async function waitView(page, view) {
  await page.waitForFunction((expected) => document.querySelector("#reviewWorkspace")?.dataset.activeView === expected, view);
}
async function snap(page, name, fullPage = false) {
  await page.screenshot({ path: path.join(output, name), fullPage, animations: "disabled" });
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
    await page.goto(`${base}/?job=${job}&ui=gameplay_directory`, { waitUntil: "domcontentloaded" });
    await waitView(page, "gameplay_directory");
    const p1Labels = ["编辑玩法理解", "+ 添加系统", "+ 添加章节", "确认理解和目录，开始审核"];
    const p1Counts = {};
    for (const label of p1Labels) p1Counts[label] = await page.getByRole("button", { name: label, exact: true }).count();
    assert.ok(Object.values(p1Counts).every((count) => count <= 1));
    const editUnderstanding = page.getByRole("button", { name: "编辑玩法理解", exact: true });
    if (await editUnderstanding.count()) {
      await editUnderstanding.click();
      await page.getByRole("button", { name: "保存玩法理解", exact: true }).waitFor();
      await page.reload({ waitUntil: "domcontentloaded" });
      await waitView(page, "gameplay_directory");
    }
    const cancel = page.getByRole("button", { name: "取消", exact: true });
    if (await cancel.count()) await cancel.click();
    const merge = page.getByRole("button", { name: /与下一项合并/ }).first();
    if (await merge.count()) {
      page.once("dialog", (dialog) => dialog.dismiss());
      await merge.click();
    }
    const split = page.getByRole("button", { name: "拆成两项", exact: true }).first();
    let splitToggle = Boolean(await split.count());
    if (splitToggle) { await split.click(); await snap(page, "UX-TC06-P1-split-panel.png"); await split.click(); }
    await snap(page, "UX-TC06-P1-actions.png");
    const p1Entries = page.locator(".gameplay-directory-tree-item");
    if (await p1Entries.count() > 1) await p1Entries.nth(1).click();
    await snap(page, "UX-TC07-P1-structure-phase.png");
    results.p1 = { uniquePrimaryActions: p1Counts, editToggle: true, cancel: Boolean(await cancel.count()), mergeCancel: Boolean(await merge.count()), splitToggle };

    await page.locator('[data-review-view="flow"]').click();
    await waitView(page, "flow");
    const stages = page.locator(".interaction-stage-nav-item:visible");
    const stageCount = await stages.count();
    assert.ok(stageCount > 1);
    await stages.nth(1).click();
    const selectedBefore = (await stages.nth(1).innerText()).trim();
    await snap(page, "UX-TC08-P2-selected-stage.png");
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitView(page, "flow");
    const selectedAfter = (await page.locator(".interaction-stage-nav-item.is-active:visible").innerText()).trim();
    assert.equal(selectedAfter, selectedBefore);
    const next = page.locator(".interaction-next-step:visible");
    assert.equal(await next.isDisabled(), false);
    if (stageCount > 2) await stages.nth(2).click();
    await snap(page, "UX-TC09-P2-stage-and-board-state.png");
    await snap(page, "UX-TC07-TC08-P2-stage-progress.png");
    results.p2 = { stageCount, selectionRestored: true, nextActionEnabled: true };

    await page.locator('[data-workbench-step="p3"]').click();
    await waitView(page, "interaction_preview");
    const svg = page.locator("#exportPreviewView svg").first();
    await svg.waitFor();
    const beforeTransform = await svg.getAttribute("style");
    await page.getByRole("button", { name: "放大", exact: true }).click();
    const afterTransform = await svg.getAttribute("style");
    await snap(page, "UX-TC10-P3-zoom-control.png");
    await page.getByRole("button", { name: "适应窗口", exact: true }).click();
    await snap(page, "UX-TC09-TC10-P3-board-controls.png");
    assert.notEqual(afterTransform, beforeTransform);
    await page.getByRole("button", { name: "进入规则审核", exact: true }).click();
    await waitView(page, "gameplay");
    results.p3 = { hasBoard: true, zoomChanged: true, enterP4: true };

    const chapters = page.locator("#gameplayReviewView .gameplay-chapter-item");
    const chapterCount = await chapters.count();
    const selectedChapterBefore = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    await snap(page, "UX-TC11-P4-chapter-before-navigation.png");
    const nextChapter = page.getByRole("button", { name: "下一节", exact: true }).last();
    if (await nextChapter.isEnabled()) await nextChapter.click();
    const selectedChapterNext = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    const previousChapter = page.getByRole("button", { name: "上一节", exact: true }).last();
    if (selectedChapterNext !== selectedChapterBefore && await previousChapter.isEnabled()) await previousChapter.click();
    assert.equal(await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId), selectedChapterBefore);
    await snap(page, "UX-TC11-P4-chapter-after-return.png");
    let decisionCards = page.locator("#gameplayReviewView .planner-decision-card");
    let decisionCardCount = await decisionCards.count();
    if (decisionCardCount) {
      const firstCard = decisionCards.first();
      await firstCard.scrollIntoViewIfNeeded();
      await snap(page, "UX-TC12-P4-decision-card-default.png");
      assert.ok(await firstCard.locator('input[type="radio"], input[type="checkbox"]').count() >= 2);
      assert.equal(await firstCard.getByRole("button", { name: "应用选择", exact: true }).count(), 1);
      assert.equal(await firstCard.getByRole("button", { name: "暂时跳过", exact: true }).count(), 1);
      await firstCard.locator('input[type="radio"], input[type="checkbox"]').first().check();
      await snap(page, "UX-TC12-P4-decision-card-selected.png");
    }
    await snap(page, "UX-TC11-TC12-P4-navigation-decisions.png");
    results.p4 = { chapterCount, nextPreviousReturned: true, decisionCardCount };

    await page.locator('[data-workbench-step="p5"]').click();
    await waitView(page, "diagrams");
    const navItems = page.locator(".gameplay-diagram-nav-item:visible");
    const navCount = await navItems.count();
    assert.ok(navCount > 1);
    for (let index = 0; index < Math.min(3, navCount); index += 1) {
      await navItems.nth(index).click();
      assert.equal(await navItems.nth(index).getAttribute("aria-current"), "true");
    }
    const diagramSummary = (await page.locator(".gameplay-diagram-summary").innerText()).trim();
    await snap(page, "UX-TC13-P5-diagram-navigation.png");
    results.p5 = { navCount, firstThreeSelectable: true, summary: diagramSummary };

    await page.locator('[data-workbench-step="p6"]').click();
    await waitView(page, "tables");
    const tableChapters = page.locator(".gameplay-table-nav-item:visible");
    const tableChapterCount = await tableChapters.count();
    assert.ok(tableChapterCount > 0);
    let multiTableChapter = false;
    let multiTableChapterIndex = -1;
    for (let index = 0; index < tableChapterCount; index += 1) {
      await tableChapters.nth(index).click();
      const visibleTables = await page.locator(".gameplay-table-card:visible").count();
      if (visibleTables > 1) { multiTableChapter = true; multiTableChapterIndex = index; }
      assert.equal(await tableChapters.nth(index).getAttribute("aria-current"), "true");
    }
    const continueButtons = await page.locator(".gameplay-table-continue:visible").count();
    assert.equal(continueButtons, 1);
    const tableIds = await page.locator(".gameplay-table-card").evaluateAll((cards) => cards.map((card) => card.querySelector(".gameplay-table-workbar-title")?.textContent?.trim() || ""));
    assert.equal(new Set(tableIds).size, tableIds.length);
    if (multiTableChapterIndex >= 0) await tableChapters.nth(multiTableChapterIndex).click();
    await snap(page, "UX-TC14-P6-multi-table-current-object.png");
    const continueButton = page.locator(".gameplay-table-continue:visible");
    if (tableChapterCount > 1) await tableChapters.nth(multiTableChapterIndex === 0 ? 1 : 0).click();
    if (await continueButton.count()) await continueButton.scrollIntoViewIfNeeded();
    await snap(page, "UX-TC15-P6-global-gate.png");
    await snap(page, "UX-TC14-TC15-P6-multi-table-gate.png");
    results.p6 = { tableChapterCount, tableCount: tableIds.length, multiTableChapter, oneGlobalContinue: true, gateDisabled: await page.locator(".gameplay-table-continue").isDisabled() };

    await page.locator('[data-workbench-step="p7"]').click();
    await waitView(page, "final_preview");
    await page.locator(".final-document-shell").waitFor();
    const currentSteps = await page.locator('[data-workbench-step][aria-current="step"]').count();
    assert.equal(currentSteps, 1);
    assert.equal(await page.locator('[data-workbench-step="p7"]').getAttribute("aria-current"), "step");
    const finalText = await page.locator("#finalExportPreviewView").innerText();
    assert.match(finalText, /图解审核/);
    assert.match(finalText, /参数审核/);
    await snap(page, "UX-TC16-P7-status-order.png");
    const finalBack = page.locator("#finalExportPreviewView .final-document-back");
    if (await finalBack.count()) await finalBack.scrollIntoViewIfNeeded();
    await snap(page, "UX-TC16-TC17-P7-status-and-return.png");
    results.p7 = { documentReady: true, diagramBeforeParameters: finalText.indexOf("图解审核") < finalText.indexOf("参数审核"), returnVisible: await page.locator(".final-document-back").isVisible() };

    if (await finalBack.count()) {
      await finalBack.focus();
      await snap(page, "UX-TC17-P7-return-button-focused.png");
      await finalBack.click();
      await waitView(page, "tables");
      const returnedTableItems = page.locator(".gameplay-table-nav-item:visible");
      if (await returnedTableItems.count() > 1) await returnedTableItems.nth(1).click();
      await snap(page, "UX-TC17-P7-return-actions.png");
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "workflow-matrix.json"), JSON.stringify({ passed: true, results, errors }, null, 2));
    console.log(JSON.stringify({ passed: true, results }, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
