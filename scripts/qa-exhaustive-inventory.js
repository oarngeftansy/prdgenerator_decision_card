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

const steps = [
  ["p1", "gameplay_directory", "gameplay_directory", ".gameplay-directory-tree-item"],
  ["p2", "flow", "flow", ".interaction-stage-nav-item"],
  ["p2-ue", "ue_flow", "ue_flow", "#ueFlowCanvas .ue-flow-page-card"],
  ["p3", "interaction_preview", "interaction_preview", "#exportPreviewView svg"],
  ["p4", "gameplay", "gameplay", "#gameplayReviewView .gameplay-chapter-item"],
  ["p5", "diagrams", "diagrams", ".gameplay-diagram-nav-item"],
  ["p6", "tables", "tables", ".gameplay-table-nav-item"],
  ["p7", "final_preview", "final_preview", ".final-document-shell"],
];

async function waitView(page, view) {
  await page.waitForFunction(
    (expected) => document.querySelector("#reviewWorkspace")?.dataset.activeView === expected,
    view,
  );
  await page.waitForTimeout(350);
}

async function inspect(page, step, view, expectedUi) {
  const state = await page.evaluate(({ expectedStep, expectedView }) => {
    const visible = (node) => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    const buttons = [...document.querySelectorAll("button")]
      .filter(visible)
      .map((button) => ({
        text: (button.innerText || button.getAttribute("aria-label") || "").trim().replace(/\s+/g, " "),
        disabled: button.disabled,
        current: button.getAttribute("aria-current") || "",
        id: button.id || "",
        className: String(button.className || ""),
      }));
    const duplicates = Object.entries(buttons.reduce((map, item) => {
      if (item.text) map[item.text] = (map[item.text] || 0) + 1;
      return map;
    }, {})).filter(([, count]) => count > 1);
    const viewport = { width: innerWidth, height: innerHeight };
    const overflow = [...document.querySelectorAll("#reviewWorkspace *")]
      .filter(visible)
      .map((node) => {
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        return {
          tag: node.tagName,
          id: node.id || "",
          className: String(node.className || "").slice(0, 160),
          text: (node.innerText || "").trim().replace(/\s+/g, " ").slice(0, 120),
          right: Math.round(rect.right),
          left: Math.round(rect.left),
          scrollWidth: node.scrollWidth,
          clientWidth: node.clientWidth,
          overflowX: style.overflowX,
        };
      })
      .filter((item) => item.right > viewport.width + 2 || item.left < -2)
      .slice(0, 40);
    const current = [...document.querySelectorAll('[aria-current="step"]')]
      .filter(visible)
      .map((node) => ({
        step: node.dataset.workbenchStep || "",
        text: (node.innerText || "").trim().replace(/\s+/g, " "),
        value: node.getAttribute("aria-current"),
      }));
    return {
      expectedStep,
      expectedView,
      actualView: document.querySelector("#reviewWorkspace")?.dataset.activeView || "",
      current,
      buttons,
      duplicates,
      overflow,
      documentScroll: {
        width: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      },
    };
  }, { expectedStep: step, expectedView: view });
  state.url = page.url();
  state.ui = new URL(page.url()).searchParams.get("ui");
  state.expectedUi = expectedUi;
  return state;
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(30000);
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push({ url: page.url(), text: message.text() });
  });
  page.on("pageerror", (error) => pageErrors.push({ url: page.url(), text: error.message }));
  const results = [];
  const issues = [];
  try {
    await page.goto(`${base}/?job=${job}&ui=gameplay_directory`, { waitUntil: "domcontentloaded" });
    for (const [step, view, ui, readySelector] of steps) {
      const nav = page.locator(`[data-review-view="${view}"]`);
      await nav.waitFor({ state: "visible" });
      await page.waitForFunction((target) => !document.querySelector(target)?.disabled, `[data-workbench-step="${step}"]`);
      await nav.click();
      await waitView(page, view);
      await page.locator(readySelector).first().waitFor({ state: "visible" });
      const before = await inspect(page, step, view, ui);
      await page.screenshot({
        path: path.join(output, `INV-${step}-${view}.png`),
        fullPage: false,
        animations: "disabled",
      });
      await page.reload({ waitUntil: "domcontentloaded" });
      await waitView(page, view);
      await page.locator(readySelector).first().waitFor({ state: "visible" });
      const afterRefresh = await inspect(page, step, view, ui);
      for (const [phase, state] of [["before", before], ["afterRefresh", afterRefresh]]) {
        if (state.actualView !== view) issues.push({ step, phase, kind: "active-view", expected: view, actual: state.actualView });
        if (state.ui !== ui) issues.push({ step, phase, kind: "url-ui", expected: ui, actual: state.ui });
      const currentMatches = state.current.length === 1 && (
          state.current[0].step === step
          || (step === "p2-ue" && state.current[0].text.includes("UE流转图"))
          || (step === "p7" && state.current[0].text.includes("文档导出"))
        );
        if (!currentMatches) {
          issues.push({ step, phase, kind: "current-step", expected: step, actual: state.current });
        }
      }
      results.push({ step, view, before, afterRefresh });
    }
    fs.writeFileSync(
      path.join(output, "inventory.json"),
      JSON.stringify({ passed: issues.length === 0, issues, consoleErrors, pageErrors, results }, null, 2),
    );
    console.log(JSON.stringify({
      passed: issues.length === 0,
      issues: issues.length,
      pages: results.length,
      consoleErrors: consoleErrors.length,
      pageErrors: pageErrors.length,
      duplicateGroups: results.reduce((sum, item) => sum + item.before.duplicates.length, 0),
      overflowItems: results.reduce((sum, item) => sum + item.before.overflow.length, 0),
    }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
