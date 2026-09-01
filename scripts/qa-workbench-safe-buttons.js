const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8000").replace(/\/$/, "");
const jobId = option("--job", "8312a91c89e144e6a59f81b982f14c06");
const output = path.resolve(option("--output", "artifacts/qa-safe-buttons-2026-08-13"));
const edgePath = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");
const { chromium } = require(path.resolve(playwrightPath));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: edgePath });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(`page:${error.message}`));
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console:${message.text()}`); });
  const results = {};
  try {
    await page.goto(`${baseUrl}/?job=${jobId}&ui=flow&qa=${Date.now()}`, { waitUntil: "domcontentloaded" });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 30000 });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "flow");

    const stageButtons = page.locator("#flowReviewView .interaction-stage-nav-item");
    const stageCount = await stageButtons.count();
    if (stageCount > 1) {
      await stageButtons.nth(1).click();
      const second = (await stageButtons.nth(1).textContent()).trim();
      await stageButtons.first().click();
      const first = (await stageButtons.first().textContent()).trim();
      results.p2 = { stageCount, first, second, returned: await stageButtons.first().getAttribute("aria-current") };
    }

    await page.locator('[data-workbench-step="p3"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "interaction_preview");
    await page.waitForFunction(() => document.querySelector("#exportPreviewView svg") || /失败|重试/.test(document.querySelector("#exportPreviewView")?.innerText || ""), null, { timeout: 30000 });
    results.p3 = await page.evaluate(() => ({
      hasSvg: Boolean(document.querySelector("#exportPreviewView svg")),
      text: (document.querySelector("#exportPreviewView")?.innerText || "").slice(0, 300),
      previewStatus: state.reviewWorkspace?.previewStatus,
    }));

    await page.locator('[data-workbench-step="p4"]').waitFor({ state: "visible" });
    await page.waitForFunction(() => !document.querySelector('[data-workbench-step="p4"]')?.disabled, null, { timeout: 30000 });
    await page.locator('[data-workbench-step="p4"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay");
    const chapterButtons = page.locator("#gameplayReviewView .gameplay-directory-item");
    const chapterCount = await chapterButtons.count();
    const selectedBefore = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    const nextButton = page.getByRole("button", { name: "下一节", exact: true }).last();
    if (await nextButton.isEnabled()) await nextButton.click();
    const selectedNext = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    const previousButton = page.getByRole("button", { name: "上一节", exact: true }).last();
    if (await previousButton.isEnabled()) await previousButton.click();
    const selectedReturned = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    await page.getByRole("button", { name: "调整目录", exact: true }).click();
    const directoryView = await page.locator("#reviewWorkspace").getAttribute("data-active-view");
    await page.locator('[data-workbench-step="p4"]').click();
    results.p4 = { chapterCount, selectedBefore, selectedNext, selectedReturned, directoryView, returnedToOriginal: selectedReturned === selectedBefore };
    assert.notEqual(selectedNext, selectedBefore);
    assert.equal(selectedReturned, selectedBefore);
    assert.equal(directoryView, "gameplay_directory");

    await page.locator('[data-workbench-step="p5"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "diagrams");
    const diagrams = page.locator("#gameplayDiagramView .gameplay-diagram-nav-item");
    const diagramCount = await diagrams.count();
    if (diagramCount > 1) await diagrams.nth(1).click();
    const selectedDiagramText = diagramCount > 1 ? (await diagrams.nth(1).textContent()).trim() : diagramCount ? (await diagrams.first().textContent()).trim() : "";
    const selectedDiagramCurrent = diagramCount > 1 ? await diagrams.nth(1).getAttribute("aria-current") : diagramCount ? await diagrams.first().getAttribute("aria-current") : "";
    results.p5 = { diagramCount, selectedDiagramText, selectedDiagramCurrent };
    if (diagramCount) assert.equal(selectedDiagramCurrent, "true");

    await page.locator('[data-workbench-step="p6"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "tables");
    const tableTabs = page.locator("#gameplayTableView .gameplay-table-chapter-nav button");
    const tableTabCount = await tableTabs.count();
    const tableBefore = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId
      || state.gameplayReviewWorkspace.model.tables.find((item) => item.status !== "deleted")?.id
      || null);
    const tableNext = page.locator("#gameplayTableView").getByRole("button", { name: "下一节", exact: true }).first();
    if (await tableNext.isEnabled()) await tableNext.click();
    const tableAfter = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
    const tablePrevious = page.locator("#gameplayTableView").getByRole("button", { name: "上一节", exact: true }).first();
    if (await tablePrevious.isEnabled()) await tablePrevious.click();
    const tableReturned = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
    results.p6 = { tableTabCount, tableBefore, tableAfter, tableReturned, returnedToOriginal: tableReturned === tableBefore };
    assert.notEqual(tableAfter, tableBefore);
    assert.equal(tableReturned, tableBefore);

    await page.locator('[data-workbench-step="p7"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "final_preview");
    await page.waitForTimeout(30000);
    const p7 = await page.evaluate(() => ({
      text: document.querySelector("#finalExportPreviewView")?.innerText || "",
      buttons: Array.from(document.querySelectorAll("#finalExportPreviewView button")).map((item) => ({ text: item.textContent.trim(), disabled: item.disabled })),
      previewStatus: state.gameplayReviewWorkspace?.previewStatus,
      previewError: state.gameplayReviewWorkspace?.previewError,
    }));
    results.p7 = p7;
    await page.screenshot({ path: path.join(output, "p7-stable.png"), fullPage: false, animations: "disabled" });
    const nextItem = page.locator("#finalExportPreviewView").getByRole("button", { name: "下一项 ›", exact: true });
    const previousItem = page.locator("#finalExportPreviewView").getByRole("button", { name: "‹ 上一项", exact: true });
    if (await nextItem.count()) { await nextItem.click(); await previousItem.click(); }
    const unresolved = page.locator("#finalExportPreviewView .final-document-resolve");
    if (await unresolved.count()) await unresolved.click();
    results.p7.unresolvedTarget = await page.locator("#reviewWorkspace").getAttribute("data-active-view");
    assert.equal(results.p7.unresolvedTarget, "interaction_preview");
    await page.locator('[data-workbench-step="p7"]').click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "final_preview");
    await page.waitForFunction(() => document.querySelector("#finalExportPreviewView .final-document-shell"), null, { timeout: 30000 });
    await page.locator("#finalExportPreviewView .final-document-back").click();
    results.p7.backTarget = await page.locator("#reviewWorkspace").getAttribute("data-active-view");
    assert.equal(results.p7.backTarget, "tables");
    fs.writeFileSync(path.join(output, "safe-button-audit.json"), JSON.stringify({ results, errors }, null, 2));
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ results, errors }, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
