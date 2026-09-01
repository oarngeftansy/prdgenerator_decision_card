const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || "" : fallback;
}

const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8014").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(30000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console: ${message.text()}`); });
  try {
    await page.goto(`${base}/?job=${job}&ui=gameplay`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay");
    await page.waitForFunction(() => (state.gameplayReviewWorkspace?.model?.chapters || []).some((item) => (item.decisionCards || []).length));
    const injection = await page.evaluate(async () => {
      const model = state.gameplayReviewWorkspace?.model;
      const chapter = (model?.chapters || []).find((item) => (item.decisionCards || []).length);
      const card = chapter?.decisionCards?.[0];
      if (!chapter || !card) return { chapterId: "", ok: false, status: 0, detail: "missing card" };
      const cards = chapter.decisionCards.map((item, index) => index ? item : ({
        ...item,
        status: "pending",
        selectedOptionIds: [],
        customValue: "",
        resolvedText: "",
      }));
      const activeJobId = state.gameplayReviewClient?.jobId || state.reviewClient?.jobId;
      const response = await fetch(`/api/jobs/${activeJobId}/gameplay-review-model/operations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expectedRevision: model.revision,
          operations: [{ type: "set_chapter_field", chapterId: chapter.id, field: "decisionCards", value: cards }],
        }),
      });
      return { chapterId: chapter.id, ok: response.ok, status: response.status, detail: await response.text() };
    });
    assert.equal(injection.ok, true, JSON.stringify(injection));
    const chapterId = injection.chapterId;
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "gameplay");
    await page.evaluate((selectedChapterId) => {
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, selectedChapterId };
      renderGameplayReviewWorkspace();
      persistGameplayUiState();
    }, chapterId);
    const card = page.locator("#gameplayReviewView .planner-decision-card").first();
    await card.waitFor();
    assert.ok(await card.locator('input[type="radio"], input[type="checkbox"]').count() >= 2);
    assert.equal(await card.locator(".planner-decision-custom input").count(), 1);
    assert.equal(await card.locator(".planner-decision-skip").count(), 1);
    assert.equal(await card.locator(".planner-decision-apply").count(), 1);
    assert.equal(await card.locator(".planner-decision-recommendation").count(), 1);
    assert.equal(await card.locator(".planner-decision-impacts").count(), 1);
    await card.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, "UX-TC12-P4-decision-card-default.png"), fullPage: false, animations: "disabled" });
    await card.locator('input[type="radio"], input[type="checkbox"]').first().check();
    await page.screenshot({ path: path.join(output, "UX-TC12-P4-decision-card-selected.png"), fullPage: false, animations: "disabled" });
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "TC12.json"), JSON.stringify({
      passed: true,
      chapterId,
      optionCount: await card.locator('input[type="radio"], input[type="checkbox"]').count(),
      hasCustom: true,
      hasSkip: true,
      hasRecommendation: true,
      hasImpacts: true,
      errors,
    }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
