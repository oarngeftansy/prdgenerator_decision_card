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

const pages = [
  { id: "p1", view: "gameplay_directory", root: ".gameplay-directory", action: ".gameplay-directory-gate .btn.primary", gate: ".gameplay-directory-gate" },
  { id: "p2", view: "flow", root: "#flowReviewView", action: ".interaction-next-step", gate: ".interaction-step-gate" },
  { id: "p3", view: "interaction_preview", root: "#exportPreviewView", action: ".export-preview-continue", gate: ".export-preview-blocked, .export-preview-ready" },
  { id: "p4", view: "gameplay", root: ".gameplay-review", action: ".gameplay-rule-confirm", gate: ".gameplay-review-gate" },
  { id: "p5", view: "diagrams", root: ".gameplay-diagrams", action: ".gameplay-diagram-continue", gate: ".gameplay-diagram-review-gate" },
  { id: "p6", view: "tables", root: ".gameplay-tables", action: ".gameplay-table-continue", gate: ".gameplay-table-review-gate" },
  { id: "p7", view: "final_preview", root: ".final-document-shell", action: ".final-document-footer .btn.primary", gate: ".final-document-gate-summary" },
];

function usefulGate(text) {
  return /(门禁|还需|完成|通过|确认|保存|进入|导出|授权)/.test(String(text || ""));
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.setDefaultTimeout(30000);
  const runtimeErrors = [];
  const results = [];
  page.on("pageerror", (error) => runtimeErrors.push(`page:${error.message}`));
  page.on("console", (message) => { if (message.type() === "error") runtimeErrors.push(`console:${message.text()}`); });
  try {
    for (const spec of pages) {
      await page.goto(`${base}/?job=${encodeURIComponent(job)}&ui=${spec.view}`, { waitUntil: "domcontentloaded" });
      await page.waitForFunction((view) => document.querySelector("#reviewWorkspace")?.dataset.activeView === view, spec.view);
      await page.locator(`${spec.root}:visible`).first().waitFor({ state: "visible" });
      const record = await page.evaluate((current) => {
        const root = document.querySelector(current.root);
        const action = root?.querySelector(current.action);
        const gate = root?.querySelector(current.gate);
        const rect = action?.getBoundingClientRect();
        const center = rect ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2) : null;
        return {
          id: current.id,
          actionText: action?.textContent?.trim() || "",
          actionVisible: Boolean(action && rect && rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight),
          actionDisabled: Boolean(action?.disabled),
          actionCovered: Boolean(action && center && center !== action && !action.contains(center)),
          gateText: gate?.textContent?.replace(/\s+/g, " ").trim() || "",
          gateVisible: Boolean(gate && gate.getBoundingClientRect().width > 0 && gate.getBoundingClientRect().height > 0),
          bodyOverflow: document.documentElement.scrollWidth > innerWidth + 2,
        };
      }, spec);
      record.usefulGate = usefulGate(record.gateText);
      results.push(record);
      await page.screenshot({ path: path.join(output, `${spec.id}-gate.png`), fullPage: false, animations: "disabled" });
    }
    const failures = results.flatMap((item) => {
      const issues = [];
      if (!item.actionVisible) issues.push("missing-or-invisible-primary-action");
      if (item.actionCovered) issues.push("primary-action-covered");
      if (!item.gateVisible || !item.usefulGate) issues.push("missing-actionable-gate-copy");
      if (item.bodyOverflow) issues.push("body-horizontal-overflow");
      return issues.map((issue) => `${item.id}:${issue}`);
    });
    const payload = { passed: failures.length === 0 && runtimeErrors.length === 0, failures, runtimeErrors, results };
    fs.writeFileSync(path.join(output, "step-gate-audit.json"), JSON.stringify(payload, null, 2));
    console.log(JSON.stringify(payload, null, 2));
    assert.deepEqual(runtimeErrors, []);
    assert.deepEqual(failures, []);
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
