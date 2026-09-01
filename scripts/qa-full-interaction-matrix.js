const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8011").replace(/\/$/, "");
const job = option("--job", "8312a91c89e144e6a59f81b982f14c06");
const output = path.resolve(option("--output", "artifacts/e2e-full-acceptance-2026-08-13-run1/interaction-matrix"));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const consoleErrors = [], pageErrors = [], failedRequests = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || "failed"}`));
  const report = {};
  const waitView = (view) => page.waitForFunction((target) => document.querySelector("#reviewWorkspace")?.dataset.activeView === target, view);
  const screenshot = (name) => page.screenshot({ path: path.join(output, name), fullPage: false, animations: "disabled" });
  try {
    await page.goto(`${base}/`, { waitUntil: "domcontentloaded" });
    assert.equal(new URL(page.url()).searchParams.get("job"), null);
    assert.equal(await page.locator("#reviewWorkspace").isHidden(), true);
    await screenshot("TC01-root-new-task.png");

    await page.goto(`${base}/?job=${job}&ui=flow`, { waitUntil: "domcontentloaded" });
    await waitView("flow");
    const stages = page.locator(".interaction-stage-nav-item:visible");
    const stageCount = await stages.count();
    assert.ok(stageCount > 1);
    const selectedIndex = Math.min(3, stageCount - 1);
    await stages.nth(selectedIndex).click();
    const selectedText = (await stages.nth(selectedIndex).innerText()).trim();
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitView("flow");
    await page.waitForFunction((index) => [...document.querySelectorAll(".interaction-stage-nav-item")].findIndex((node) => node.classList.contains("is-active")) === index, selectedIndex);
    const activeAfterRefresh = (await page.locator(".interaction-stage-nav-item.is-active").innerText()).trim();
    assert.equal(activeAfterRefresh, selectedText);
    const next = page.locator(".interaction-next-step:visible");
    assert.equal(await next.isDisabled(), false);
    assert.match((await next.innerText()).trim(), /应用并查看下一环节|应用并进入交付物预览/);
    await screenshot("TC07-p2-selection-refresh.png");
    report.p2 = { stageCount, selectedIndex, selectedText, activeAfterRefresh, nextLabel: (await next.innerText()).trim() };

    await page.locator('[data-workbench-step="p4"]').click();
    await waitView("gameplay");
    const chapterBefore = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    const nextChapter = page.locator("#gameplayReviewView").getByRole("button", { name: "下一节", exact: true }).last();
    if (await nextChapter.isEnabled()) await nextChapter.click();
    const chapterNext = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    assert.notEqual(chapterNext, chapterBefore);
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitView("gameplay");
    const chapterAfterRefresh = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    assert.equal(chapterAfterRefresh, chapterNext);
    await screenshot("TC09-p4-chapter-refresh.png");
    report.p4 = { chapterBefore, chapterNext, chapterAfterRefresh };

    await page.locator('[data-workbench-step="p5"]').click();
    await waitView("diagrams");
    const diagramNav = page.locator(".gameplay-diagram-nav-item:visible");
    const diagramCount = await diagramNav.count();
    const diagramIndex = Math.min(1, Math.max(0, diagramCount - 1));
    if (diagramCount) await diagramNav.nth(diagramIndex).click();
    const diagramText = diagramCount ? (await diagramNav.nth(diagramIndex).innerText()).trim() : "";
    const diagramChapterId = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitView("diagrams");
    assert.equal(await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId), diagramChapterId);
    const activeDiagramText = diagramCount ? (await page.locator('.gameplay-diagram-nav-item[aria-current="true"]:visible').innerText()).trim() : "";
    assert.equal(activeDiagramText, diagramText);
    await screenshot("TC10-p5-diagram-refresh.png");
    report.p5 = { diagramCount, diagramText, activeDiagramText, diagramChapterId };

    await page.locator('[data-workbench-step="p6"]').click();
    await waitView("tables");
    const tableBefore = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
    const nextTable = page.locator("#gameplayTableView").getByRole("button", { name: "下一节", exact: true }).first();
    if (await nextTable.isEnabled()) await nextTable.click();
    const tableNext = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
    assert.notEqual(tableNext, tableBefore);
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitView("tables");
    const tableAfterRefresh = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
    assert.equal(tableAfterRefresh, tableNext);
    await screenshot("TC11-p6-table-refresh.png");
    report.p6 = { tableBefore, tableNext, tableAfterRefresh };

    await page.locator('[data-workbench-step="p7"]').click();
    await waitView("final_preview");
    await page.locator(".final-document-shell").waitFor();
    const beforeScroll = await page.locator(".final-document-scroll").evaluate((node) => node.scrollTop);
    await page.getByRole("button", { name: "下一项 ›", exact: true }).click();
    await page.waitForTimeout(800);
    const afterNext = await page.locator(".final-document-scroll").evaluate((node) => node.scrollTop);
    assert.ok(afterNext !== beforeScroll);
    await page.getByRole("button", { name: "‹ 上一项", exact: true }).click();
    await screenshot("TC12-p7-prev-next.png");
    report.p7 = { beforeScroll, afterNext };

    const responsive = [];
    for (const viewport of [{ width: 1280, height: 900 }, { width: 900, height: 900 }, { width: 620, height: 900 }]) {
      await page.setViewportSize(viewport);
      await page.waitForTimeout(300);
      const metrics = await page.evaluate(() => ({ bodyOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, workspaceOverflow: document.querySelector("#reviewWorkspace").scrollWidth - document.querySelector("#reviewWorkspace").clientWidth }));
      assert.ok(metrics.bodyOverflow <= 1, `body overflow at ${viewport.width}: ${metrics.bodyOverflow}`);
      responsive.push({ ...viewport, ...metrics });
      await screenshot(`TC16-responsive-${viewport.width}.png`);
    }
    report.responsive = responsive;

    assert.deepEqual(consoleErrors, []);
    assert.deepEqual(pageErrors, []);
    assert.deepEqual(failedRequests, []);
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify({ passed: true, report, consoleErrors, pageErrors, failedRequests }, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
