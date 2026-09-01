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
const edge = option("--edge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");

const defaultPages = [
  { id: "p1", view: "gameplay_directory", ready: ".gameplay-directory-tree-item" },
  { id: "p2", view: "flow", ready: ".interaction-stage-nav-item" },
  { id: "p3", view: "interaction_preview", ready: "#exportPreviewView svg" },
  { id: "p4", view: "gameplay", ready: ".gameplay-chapter-item" },
  { id: "p5", view: "diagrams", ready: ".gameplay-diagram-nav-item" },
  { id: "p6", view: "tables", ready: ".gameplay-table-nav-item" },
  { id: "p7", view: "final_preview", ready: ".final-document-shell" },
];
const requestedPages = new Set(option("--pages").split(",").filter(Boolean));
const pages = requestedPages.size ? defaultPages.filter((page) => requestedPages.has(page.id)) : defaultPages;

const defaultViewports = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 900 },
  { width: 1024, height: 900 },
  { width: 768, height: 900 },
  { width: 390, height: 844 },
];
const requestedWidths = option("--widths").split(",").map(Number).filter(Boolean);
const viewports = requestedWidths.length
  ? requestedWidths.map((width) => ({ width, height: width <= 480 ? 844 : 900 }))
  : defaultViewports;

async function waitForPage(page, spec) {
  await page.waitForFunction(
    (view) => document.querySelector("#reviewWorkspace")?.dataset.activeView === view,
    spec.view,
  );
  await page.locator(`${spec.ready}:visible`).first().waitFor({ state: "visible" });
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: edge });
  const results = [];
  const runtimeErrors = [];
  try {
    for (const viewport of viewports) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      page.setDefaultTimeout(30000);
      page.on("pageerror", (error) => runtimeErrors.push(`${viewport.width}:page:${error.message}`));
      page.on("console", (message) => {
        if (message.type() === "error") runtimeErrors.push(`${viewport.width}:console:${message.text()}`);
      });

      for (const spec of pages) {
        await page.goto(`${base}/?job=${encodeURIComponent(job)}&ui=${spec.view}&qa=${Date.now()}`, {
          waitUntil: "domcontentloaded",
        });
        await waitForPage(page, spec);
        await page.waitForTimeout(250);

        const audit = await page.evaluate(({ pageId, viewportWidth }) => {
          const visible = (node) => {
            const style = getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
          };
          const text = (node) => (node.innerText || node.textContent || "").trim().replace(/\s+/g, " ");
          const duplicateIds = Object.entries(
            [...document.querySelectorAll("[id]")].reduce((map, node) => {
              map[node.id] = (map[node.id] || 0) + 1;
              return map;
            }, {}),
          ).filter(([, count]) => count > 1);
          const visibleButtons = [...document.querySelectorAll("button")].filter(visible);
          const emptyButtons = visibleButtons.filter((button) => !(
            text(button)
            || button.getAttribute("aria-label")
            || button.getAttribute("title")
          )).map((button) => button.outerHTML.slice(0, 180));
          const horizontallyReachable = (node) => {
            for (let parent = node.parentElement; parent; parent = parent.parentElement) {
              const style = getComputedStyle(parent);
              if (["auto", "scroll"].includes(style.overflowX) && parent.scrollWidth > parent.clientWidth + 1) return true;
            }
            return false;
          };
          const clippedButtons = visibleButtons.map((button) => {
            const rect = button.getBoundingClientRect();
            return { label: text(button).slice(0, 60), left: rect.left, right: rect.right, width: rect.width, reachable: horizontallyReachable(button) };
          }).filter((item) => (item.left < -1 || item.right > viewportWidth + 1) && !item.reachable);
          const unlabeledInputs = [...document.querySelectorAll("input:not([type=hidden]), textarea, select")]
            .filter(visible)
            .filter((input) => {
              if (input.getAttribute("aria-label") || input.getAttribute("aria-labelledby") || input.title) return false;
              if (input.id && document.querySelector(`label[for="${CSS.escape(input.id)}"]`)) return false;
              return !input.closest("label");
            })
            .map((input) => ({ tag: input.tagName, type: input.type || "", name: input.name || "", placeholder: input.placeholder || "" }));
          const narrowText = [...document.querySelectorAll("p, li, label, td, th, button, .final-document-sidebar *")]
            .filter(visible)
            .map((node) => {
              const rect = node.getBoundingClientRect();
              return { tag: node.tagName, label: text(node).slice(0, 80), width: rect.width, height: rect.height };
            })
            .filter((item) => item.label.length >= 8 && item.width < 34 && item.height > 80);
          const currentSteps = pageId === "p7"
            ? [...document.querySelectorAll('.final-document-step[aria-current="step"]')].filter(visible).length
            : [...document.querySelectorAll('[data-workbench-step][aria-current="step"]')].filter(visible).length;
          const root = document.documentElement;
          const bodyOverflow = Math.max(0, root.scrollWidth - root.clientWidth);
          const workspace = document.querySelector("#reviewWorkspace");
          const visibleView = [...(workspace?.querySelectorAll(".review-view") || [])].find(visible);
          const activeLayout = visibleView?.querySelector(
            ".gameplay-directory-layout, .planner-review-shell, .interaction-page-preview, .gameplay-review, .gameplay-diagrams-layout, .gameplay-tables-layout, .final-document-layout",
          );
          return {
            pageId,
            viewportWidth,
            activeView: workspace?.dataset.activeView || "",
            bodyOverflow,
            currentSteps,
            duplicateIds,
            emptyButtons,
            clippedButtons,
            unlabeledInputs,
            narrowText,
            visibleButtonCount: visibleButtons.length,
            media: {
              max640: matchMedia("(max-width: 640px)").matches,
              max900: matchMedia("(max-width: 900px)").matches,
              max1200: matchMedia("(max-width: 1200px)").matches,
            },
            geometry: {
              workspace: workspace?.getBoundingClientRect().toJSON?.(),
              body: workspace?.querySelector(".review-workspace-body")?.getBoundingClientRect().toJSON?.(),
              canvas: workspace?.querySelector(".review-canvas")?.getBoundingClientRect().toJSON?.(),
              visibleView: visibleView?.getBoundingClientRect().toJSON?.(),
              activeLayout: activeLayout?.getBoundingClientRect().toJSON?.(),
              p4: [".gameplay-chapter-rail", ".gameplay-evidence-column", ".gameplay-chapter-editor"].map((selector) => {
                const node = visibleView?.querySelector(selector);
                const style = node ? getComputedStyle(node) : null;
                return { selector, rect: node?.getBoundingClientRect().toJSON?.(), gridColumn: style?.gridColumn, gridRow: style?.gridRow };
              }),
            },
          };
        }, { pageId: spec.id, viewportWidth: viewport.width });

        results.push(audit);
        await page.screenshot({
          path: path.join(output, `${spec.id}-${viewport.width}.png`),
          fullPage: false,
          animations: "disabled",
        });
      }
      await context.close();
    }

    const hardIssues = results.flatMap((item) => {
      const issues = [];
      if (item.activeView !== pages.find((page) => page.id === item.pageId).view) issues.push("wrong-active-view");
      if (item.currentSteps !== 1) issues.push(`current-step-count:${item.currentSteps}`);
      if (item.duplicateIds.length) issues.push(`duplicate-ids:${item.duplicateIds.length}`);
      if (item.emptyButtons.length) issues.push(`empty-buttons:${item.emptyButtons.length}`);
      if (item.clippedButtons.length) issues.push(`clipped-buttons:${item.clippedButtons.length}`);
      if (item.narrowText.length) issues.push(`single-character-columns:${item.narrowText.length}`);
      return issues.map((issue) => ({ page: item.pageId, width: item.viewportWidth, issue }));
    });
    const payload = { passed: hardIssues.length === 0 && runtimeErrors.length === 0, hardIssues, runtimeErrors, results };
    fs.writeFileSync(path.join(output, "responsive-a11y.json"), JSON.stringify(payload, null, 2));
    console.log(JSON.stringify({ passed: payload.passed, hardIssues, runtimeErrors }, null, 2));
    assert.deepEqual(runtimeErrors, []);
    assert.deepEqual(hardIssues, []);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
