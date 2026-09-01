const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { chromium } = require("playwright");

const viewport = { width: 1600, height: 1000 };
const targets = [
  "wireframe.html",
  "wireframe-interaction.html",
  "wireframe - p3.html",
  "wireframe - p4.html",
  "wireframe - p5.html",
  "wireframe - p6.html",
  "wireframe - p7.html",
];
const desktop = "C:\\Users\\momoca\\Desktop";
const output = path.resolve(__dirname, "..", "artifacts", "wireframe-comparison");
const appUrl = "http://127.0.0.1:8000/?job=4180cd72eeaa4819be41db50bb4c5011&ui=wireframe-comparison";

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  try {
    for (let index = 0; index < targets.length; index += 1) {
      const target = await browser.newPage({ viewport });
      await target.goto(pathToFileURL(path.join(desktop, targets[index])).href, { waitUntil: "load" });
      await target.screenshot({ path: path.join(output, `p${index + 1}-target.png`) });
      await target.close();
    }

    const current = await browser.newPage({ viewport });
    await current.goto(appUrl, { waitUntil: "networkidle" });
    await current.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
    for (let index = 0; index < targets.length; index += 1) {
      const views = ["gameplay_directory", "flow", "interaction_preview", "gameplay", "diagrams", "tables", "final_preview"];
      if (index < 6) {
        await current.evaluate(async (view) => {
          const originalRoute = ReviewWorkspace.routeForModel;
          ReviewWorkspace.routeForModel = () => view;
          state.reviewWorkspace = { ...state.reviewWorkspace, view };
          renderReviewWorkspace(state.reviewWorkspace.model);
          ReviewWorkspace.routeForModel = originalRoute;
          if (view === "interaction_preview") {
            const latestResponse = await fetch(`/api/jobs/${state.currentJobId}/review-model`);
            const model = await latestResponse.json();
            state.reviewWorkspace.model = model;
            const response = await fetch(`/api/jobs/${state.currentJobId}/review-model/preview`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ expectedRevision: model.revision }),
            });
            const preview = await response.json();
            console.log("P3 preview", response.status, preview.revision, (preview.boardPreviewSvg || "").length, (ExportPreview.sanitizeBoardSvg(preview.boardPreviewSvg || "") || "").length);
            state.reviewWorkspace.preview = preview;
            ExportPreview.render({ root: document.querySelector("#exportPreviewView"), preview, model, onContinue: () => {} });
          }
        }, views[index]);
      } else {
        await current.evaluate(async () => {
          state.reviewWorkspace.view = "final_preview";
          document.querySelector("#reviewWorkspace").classList.add("is-final-preview");
          document.querySelectorAll(".review-view").forEach((view) => { view.hidden = view.id !== "finalExportPreviewView"; });
          const gameplay = state.gameplayReviewWorkspace.model;
          const interactionResponse = await fetch(`/api/jobs/4180cd72eeaa4819be41db50bb4c5011/review-model`);
          const interaction = await interactionResponse.json();
          console.log("P7 real interaction", interaction.stages?.length || 0, (interaction.stages || []).filter((stage) => stage.confirmation?.confirmed).length);
          FinalDocumentPreview.render({
            root: document.querySelector("#finalExportPreviewView"),
            preview: state.gameplayReviewWorkspace.preview || {
              documentTitle: "移动端交互与玩法完整策划案",
              analysisNote: "本文档根据已确认的交互流程、玩法规则、参数表格与有效图解生成。",
              interactionRevision: interaction.revision,
              gameplayRevision: gameplay.revision,
            },
            model: gameplay,
            interaction,
            view: { exportDisabled: false },
          });
          window.__p7Debug = {
            stageCount: interaction.stages?.length || 0,
            confirmedStageCount: (interaction.stages || []).filter((stage) => stage.confirmation?.confirmed).length,
            checks: Array.from(document.querySelectorAll(".final-document-check"), (item) => item.textContent),
          };
        });
        console.log("P7 debug", await current.evaluate(() => window.__p7Debug));
      }
      await current.waitForTimeout(1200);
      await current.locator(".review-view:not([hidden])").waitFor({ state: "visible", timeout: 10000 });
      await current.screenshot({ path: path.join(output, `p${index + 1}-current.png`) });
    }
    await current.close();
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
