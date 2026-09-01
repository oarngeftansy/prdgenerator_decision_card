const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8023").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));
const edge = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");

async function run() {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: edge });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(30000);
  const report = { cases: [], consoleErrors: [], pageErrors: [], failedRequests: [] };
  page.on("console", (message) => { if (message.type() === "error") report.consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => report.pageErrors.push(error.message));
  page.on("requestfailed", (request) => report.failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || "failed"}`));
  let caseNumber = 0;
  const waitView = (view) => page.waitForFunction(
    (expected) => document.querySelector("#reviewWorkspace")?.dataset.activeView === expected,
    view,
  );
  const activeView = () => page.locator("#reviewWorkspace").getAttribute("data-active-view");
  const capture = async (title, expected, actual = "") => {
    caseNumber += 1;
    const slug = title.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]+/g, "-").replace(/^-|-$/g, "").slice(0, 64);
    const file = `TC-${String(caseNumber).padStart(3, "0")}-${slug}.png`;
    await page.screenshot({ path: path.join(output, file), fullPage: false, animations: "disabled" });
    report.cases.push({ id: `TC-${String(caseNumber).padStart(3, "0")}`, title, expected, actual: actual || await activeView(), url: page.url(), screenshot: file });
  };
  const clickVisible = async (locator, description) => {
    await locator.waitFor({ state: "visible" });
    assert.equal(await locator.isDisabled(), false, `${description} should be enabled`);
    await locator.click();
  };

  try {
    await page.goto(`${base}/?job=${encodeURIComponent(job)}&ui=gameplay_directory&qa=${Date.now()}`, { waitUntil: "domcontentloaded" });
    await waitView("gameplay_directory");
    const directoryItems = page.locator(".gameplay-directory-tree-item:visible");
    for (let index = 0; index < await directoryItems.count(); index += 1) {
      await directoryItems.nth(index).click();
      assert.equal(await page.locator(".gameplay-directory-tree-item.is-selected:visible").count(), 1);
      await capture(`玩法目录选择第${index + 1}章`, "唯一选中对应章节");
    }
    const directoryConfirm = page.getByRole("button", { name: /确认(?:理解和目录|机制目录).*?(?:开始审核|开始生成详细规则)/ }).last();
    await clickVisible(directoryConfirm, "目录确认");
    await waitView("flow");
    await capture("玩法目录进入交互审核", "gameplay_directory → flow");

    let flowIndex = 0;
    while (await activeView() === "flow") {
      const activeStageId = await page.evaluate(() => state.reviewWorkspace?.selectedStageId || "");
      const activeStage = (await page.locator(".interaction-stage-nav-item.is-active:visible").innerText()).trim().replace(/\s+/g, " ");
      await capture(`交互环节${flowIndex + 1}-${activeStage}`, "当前环节可见且下一步可用");
      const next = page.locator(".interaction-next-step:visible");
      await clickVisible(next, `交互环节${flowIndex + 1}下一步`);
      await page.waitForFunction((previousStageId) => {
        const view = document.querySelector("#reviewWorkspace")?.dataset.activeView;
        const currentStageId = state.reviewWorkspace?.selectedStageId || "";
        const saving = state.reviewWorkspace?.confirmStatus === "saving";
        return !saving && (view === "ue_flow" || (view === "flow" && currentStageId !== previousStageId));
      }, activeStageId);
      flowIndex += 1;
      assert.ok(flowIndex < 80, "interaction flow did not terminate");
    }
    assert.equal(await activeView(), "ue_flow", "last interaction stage must enter UE flow review before P3");
    await capture("交互审核进入UE流转图", "flow → ue_flow");

    const uePages = page.locator(".ue-flow-directory-item:visible");
    for (let index = 0; index < await uePages.count(); index += 1) {
      await uePages.nth(index).click();
      await capture(`UE流转图页面${index + 1}`, "目录项可点击并定位对应页面");
    }
    const ueBack = page.getByRole("button", { name: "返回 P2-1 修改", exact: true });
    await clickVisible(ueBack, "UE返回P2-1");
    await waitView("flow");
    await capture("UE返回交互审核", "ue_flow → flow");
    const ueNav = page.locator('[data-review-view="ue_flow"]');
    await clickVisible(ueNav, "顶部UE流转图导航");
    await waitView("ue_flow");
    await capture("顶部导航重返UE流转图", "flow → ue_flow");
    const ueConfirm = page.getByRole("button", { name: "确认 UE 流转图并进入 P3", exact: true });
    await clickVisible(ueConfirm, "确认UE流转图");
    await waitView("interaction_preview");
    await page.locator("#exportPreviewView svg").first().waitFor({ state: "visible" });
    await capture("UE流转图进入交付物预览", "ue_flow → interaction_preview");

    const previewToolbar = page.locator("#exportPreviewView .export-preview-board-toolbar button:visible");
    for (let index = 0; index < await previewToolbar.count(); index += 1) {
      const label = (await previewToolbar.nth(index).innerText()).trim() || `工具${index + 1}`;
      await clickVisible(previewToolbar.nth(index), `交付物预览${label}`);
      await capture(`交付物预览工具-${label}`, "按钮产生可见画板状态变化");
      if (/全屏/.test(label)) {
        await page.keyboard.press("Escape");
        if (await page.evaluate(() => Boolean(document.fullscreenElement))) {
          await page.evaluate(() => document.exitFullscreen());
        }
        await page.waitForFunction(() => !document.fullscreenElement);
        await capture("交付物预览退出全屏", "退出全屏后恢复页面按钮交互");
      }
    }
    const previewContinue = page.locator("#exportPreviewView .export-preview-continue:visible");
    await clickVisible(previewContinue, "进入规则审核");
    await waitView("gameplay");
    await capture("交付物预览进入规则审核", "interaction_preview → gameplay");

    const chapters = page.locator(".gameplay-chapter-item:visible");
    for (let index = 0; index < await chapters.count(); index += 1) {
      await chapters.nth(index).click();
      assert.equal(await chapters.nth(index).evaluate((node) => node.classList.contains("is-selected")), true);
      await capture(`规则审核第${index + 1}章`, "点击后唯一选中对应章节");
    }
    if (await chapters.count() > 1) {
      await chapters.first().click();
      const firstId = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
      const nextChapter = page.locator("#gameplayReviewView").getByRole("button", { name: "下一节", exact: true }).last();
      await clickVisible(nextChapter, "规则审核下一节");
      const secondId = await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId);
      assert.notEqual(secondId, firstId);
      await capture("规则审核下一节", "第 N 章 → 第 N+1 章", secondId);
      const previousChapter = page.locator("#gameplayReviewView").getByRole("button", { name: "上一节", exact: true }).last();
      await clickVisible(previousChapter, "规则审核上一节");
      assert.equal(await page.evaluate(() => state.gameplayReviewWorkspace.selectedChapterId), firstId);
      await capture("规则审核上一节", "第 N+1 章 → 第 N 章", firstId);
    }

    const topViews = [
      ["gameplay_directory", ".gameplay-directory-tree-item"], ["flow", ".interaction-stage-nav-item"],
      ["ue_flow", ".ue-flow-page-card"], ["interaction_preview", "#exportPreviewView svg"],
      ["gameplay", ".gameplay-chapter-item"], ["diagrams", ".gameplay-diagram-nav-item"],
      ["tables", ".gameplay-table-nav-item"], ["final_preview", ".final-document-shell"],
    ];
    for (const [view, ready] of topViews) {
      const nav = page.locator(`[data-review-view="${view}"]`);
      await clickVisible(nav, `顶部导航${view}`);
      await waitView(view);
      await page.locator(ready).first().waitFor({ state: "visible" });
      assert.equal(new URL(page.url()).searchParams.get("ui"), view);
      await capture(`顶部导航-${view}`, `进入${view}且URL同步`);
    }

    const finalBack = page.locator(".final-document-back:visible");
    await clickVisible(finalBack, "完整策划案返回修改");
    await waitView("tables");
    await capture("完整策划案返回修改", "final_preview → tables");
    await clickVisible(page.locator('[data-review-view="diagrams"]'), "顶部图解审核导航");
    await waitView("diagrams");
    const diagrams = page.locator(".gameplay-diagram-nav-item:visible");
    for (let index = 0; index < await diagrams.count(); index += 1) {
      await diagrams.nth(index).click();
      assert.equal(await diagrams.nth(index).getAttribute("aria-current"), "true");
      await capture(`图解审核第${index + 1}项`, "点击后显示对应图解");
    }

    await page.locator('[data-review-view="tables"]').click();
    await waitView("tables");
    const tables = page.locator(".gameplay-table-nav-item:visible");
    for (let index = 0; index < await tables.count(); index += 1) {
      await tables.nth(index).click();
      assert.equal(await tables.nth(index).getAttribute("aria-current"), "true");
      await capture(`参数审核第${index + 1}项`, "点击后显示对应参数表");
    }
    if (await tables.count() > 1 && await page.locator("#gameplayTableView").getByRole("button", { name: "下一节", exact: true }).count()) {
      await tables.first().click();
      const before = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
      const nextTable = page.locator("#gameplayTableView").getByRole("button", { name: "下一节", exact: true }).first();
      await clickVisible(nextTable, "参数审核下一节");
      const after = await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId);
      assert.notEqual(after, before);
      await capture("参数审核下一节", "第 N 表 → 第 N+1 表", after);
      const previousTable = page.locator("#gameplayTableView").getByRole("button", { name: "上一节", exact: true }).first();
      await clickVisible(previousTable, "参数审核上一节");
      assert.equal(await page.evaluate(() => state.gameplayReviewWorkspace.selectedTableId), before);
      await capture("参数审核上一节", "第 N+1 表 → 第 N 表", before);
    }

    await page.locator('[data-review-view="final_preview"]').click();
    await waitView("final_preview");
    const tocItems = page.locator(".final-document-toc-item:visible");
    for (let index = 0; index < await tocItems.count(); index += 1) {
      await tocItems.nth(index).click();
      await capture(`完整策划案目录第${index + 1}项`, "目录点击后正文滚动到对应章节");
    }
    const nextItem = page.locator(".final-document-next:visible");
    const previousItem = page.locator(".final-document-prev:visible");
    if (await nextItem.count() && await nextItem.isEnabled()) {
      await nextItem.click();
      await capture("完整策划案下一项", "第 N 项 → 第 N+1 项");
      await previousItem.click();
      await capture("完整策划案上一项", "第 N+1 项 → 第 N 项");
    }

    assert.deepEqual(report.pageErrors, []);
    assert.deepEqual(report.consoleErrors, []);
    assert.deepEqual(report.failedRequests, []);
    report.completed = true;
    fs.writeFileSync(path.join(output, "acceptance.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ completed: true, cases: report.cases.length }, null, 2));
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
