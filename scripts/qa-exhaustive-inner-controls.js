const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8015").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));

async function waitView(page, view) {
  await page.waitForFunction((expected) => document.querySelector("#reviewWorkspace")?.dataset.activeView === expected, view);
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(30000);
  const errors = [];
  const results = {};
  page.on("pageerror", (error) => errors.push(`page:${error.message}`));
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console:${message.text()}`); });
  try {
    await page.goto(`${base}/?job=${encodeURIComponent(job)}&ui=gameplay_directory`, { waitUntil: "domcontentloaded" });
    await waitView(page, "gameplay_directory");

    const focusTrail = [];
    for (let index = 0; index < 12; index += 1) {
      await page.keyboard.press("Tab");
      focusTrail.push(await page.evaluate(() => ({
        tag: document.activeElement?.tagName || "",
        text: (document.activeElement?.innerText || document.activeElement?.getAttribute?.("aria-label") || "").trim().replace(/\s+/g, " ").slice(0, 80),
        visible: Boolean(document.activeElement && document.activeElement.getBoundingClientRect().width),
      })));
    }
    assert.ok(focusTrail.filter((item) => item.tag === "BUTTON" && item.visible).length >= 8);

    const directoryItems = page.locator(".gameplay-directory-tree-item:visible");
    const directoryCount = await directoryItems.count();
    assert.ok(directoryCount >= 7);
    for (let index = 0; index < directoryCount; index += 1) {
      await directoryItems.nth(index).click();
      assert.equal(await directoryItems.nth(index).evaluate((node) => node.classList.contains("is-selected")), true);
      assert.equal(await page.locator(".gameplay-directory-tree-item.is-selected:visible").count(), 1);
    }
    await page.screenshot({ path: path.join(output, "CTRL-P1-all-chapters-keyboard.png"), animations: "disabled" });
    results.p1 = { directoryCount, focusTrail };

    await page.locator('[data-workbench-step="p2"]').click();
    await waitView(page, "flow");
    const stageItems = page.locator(".interaction-stage-nav-item:visible");
    const stageCount = await stageItems.count();
    assert.ok(stageCount >= 2);
    const stageNames = [];
    for (let index = 0; index < stageCount; index += 1) {
      await stageItems.nth(index).click();
      stageNames.push((await stageItems.nth(index).innerText()).trim().replace(/\s+/g, " "));
      assert.ok((await stageItems.nth(index).getAttribute("aria-current")) === "true" || await stageItems.nth(index).evaluate((node) => node.classList.contains("is-active")));
    }
    assert.equal(new Set(stageNames).size, stageNames.length);
    await page.screenshot({ path: path.join(output, "CTRL-P2-all-stages.png"), animations: "disabled" });
    results.p2 = { stageCount, uniqueStageNames: true };

    await page.locator('[data-workbench-step="p3"]').click();
    await waitView(page, "interaction_preview");
    const previewSvg = page.locator("#exportPreviewView svg").first();
    await previewSvg.waitFor();
    const toolbarButtons = page.locator("#exportPreviewView .export-preview-board-toolbar button:visible");
    const toolbarCount = await toolbarButtons.count();
    assert.ok(toolbarCount >= 3);
    const transformStates = [];
    for (let index = 0; index < toolbarCount; index += 1) {
      await toolbarButtons.nth(index).click();
      transformStates.push(await previewSvg.getAttribute("style"));
    }
    assert.ok(new Set(transformStates).size >= 2);
    await page.screenshot({ path: path.join(output, "CTRL-P3-board-toolbar.png"), animations: "disabled" });
    results.p3 = { toolbarCount, transformChanged: true };

    await page.locator('[data-workbench-step="p4"]').click();
    await waitView(page, "gameplay");
    const chapterItems = page.locator(".gameplay-chapter-item:visible");
    const chapterCount = await chapterItems.count();
    const selectedIds = [];
    for (let index = 0; index < chapterCount; index += 1) {
      await chapterItems.nth(index).click();
      selectedIds.push(await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId));
      assert.equal(await chapterItems.nth(index).evaluate((node) => node.classList.contains("is-selected")), true);
    }
    assert.equal(new Set(selectedIds).size, chapterCount);
    await chapterItems.first().click();
    const evidenceButton = page.locator(".gameplay-evidence-thumbnails button:visible").first();
    let evidenceEscape = "not-applicable";
    if (await evidenceButton.count()) {
      await evidenceButton.click();
      await page.locator(".gameplay-evidence-dialog:visible").waitFor();
      await page.keyboard.press("Escape");
      await page.locator(".gameplay-evidence-dialog:visible").waitFor({ state: "detached" });
      evidenceEscape = "closed";
    }
    await page.screenshot({ path: path.join(output, "CTRL-P4-all-chapters-evidence.png"), animations: "disabled" });
    results.p4 = { chapterCount, uniqueSelectedIds: true, evidenceEscape };

    await page.locator('[data-workbench-step="p5"]').click();
    await waitView(page, "diagrams");
    const diagramItems = page.locator(".gameplay-diagram-nav-item:visible");
    const diagramCount = await diagramItems.count();
    for (let index = 0; index < diagramCount; index += 1) {
      await diagramItems.nth(index).click();
      assert.equal(await diagramItems.nth(index).getAttribute("aria-current"), "true");
    }
    await page.screenshot({ path: path.join(output, "CTRL-P5-all-diagrams.png"), animations: "disabled" });
    results.p5 = { diagramCount };

    await page.locator('[data-workbench-step="p6"]').click();
    await waitView(page, "tables");
    const tableNav = page.locator(".gameplay-table-nav-item:visible");
    const tableNavCount = await tableNav.count();
    let selectedRows = 0;
    for (let index = 0; index < tableNavCount; index += 1) {
      await tableNav.nth(index).click();
      assert.equal(await tableNav.nth(index).getAttribute("aria-current"), "true");
      const cards = page.locator(".gameplay-table-card:visible");
      for (let cardIndex = 0; cardIndex < await cards.count(); cardIndex += 1) {
        const rows = cards.nth(cardIndex).locator("tbody tr:visible");
        if (!await rows.count()) continue;
        await rows.first().click();
        assert.equal(await rows.first().evaluate((node) => node.classList.contains("is-selected")), true);
        selectedRows += 1;
      }
    }
    await page.screenshot({ path: path.join(output, "CTRL-P6-all-tables-rows.png"), animations: "disabled" });
    results.p6 = { tableNavCount, selectedRows };

    await page.locator('[data-workbench-step="p7"]').click();
    await waitView(page, "final_preview");
    await page.locator(".final-document-shell").waitFor();
    const tocToggles = page.locator(".final-document-toc-toggle:visible");
    const tocToggleCount = await tocToggles.count();
    for (let index = 0; index < tocToggleCount; index += 1) {
      await tocToggles.nth(index).click();
      assert.equal(await tocToggles.nth(index).getAttribute("aria-expanded"), "false");
      await tocToggles.nth(index).click();
      assert.equal(await tocToggles.nth(index).getAttribute("aria-expanded"), "true");
    }
    const tocItems = page.locator(".final-document-toc-item:visible");
    const tocItemCount = await tocItems.count();
    assert.ok(tocItemCount > 3);
    const scroll = page.locator(".final-document-scroll");
    const beforeToc = await scroll.evaluate((node) => node.scrollTop);
    await tocItems.nth(Math.min(3, tocItemCount - 1)).click();
    const afterToc = await scroll.evaluate((node) => node.scrollTop);
    assert.notEqual(afterToc, beforeToc);
    const next = page.locator(".final-document-next:visible");
    const previous = page.locator(".final-document-prev:visible");
    await next.click();
    await previous.click();
    await page.screenshot({ path: path.join(output, "CTRL-P7-toc-prev-next.png"), animations: "disabled" });
    results.p7 = { tocToggleCount, tocItemCount, tocNavigationMoved: true, previousNext: true };

    assert.deepEqual(errors, []);
    const payload = { passed: true, results, errors };
    fs.writeFileSync(path.join(output, "inner-controls.json"), JSON.stringify(payload, null, 2));
    console.log(JSON.stringify(payload, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
