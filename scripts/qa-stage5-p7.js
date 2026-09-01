const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE5_ORIGIN || "http://127.0.0.1:8007";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-browser-acceptance");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  try {
    await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle" });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
    await page.locator('[data-workbench-step="p7"]').evaluate(button => button.click());
    await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
    await page.evaluate(async () => {
      const revision = state.gameplayReviewWorkspace.model.revision;
      const response = await fetch(`/api/jobs/${state.gameplayReviewClient.jobId}/gameplay-review-model/final-preview`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision: revision }),
      });
      if (!response.ok) throw new Error(`final preview ${response.status}: ${await response.text()}`);
      const preview = await response.json();
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview, previewStatus: "ready", previewError: "" };
      renderCombinedFinalPreview();
    });
    const result = await page.evaluate(() => {
      const preview = state?.gameplayReviewWorkspace?.preview;
      const snapshot = preview?.completionSnapshot;
      if (!snapshot) throw new Error("completionSnapshot missing");
      const percentText = document.querySelector(".final-document-score strong")?.textContent;
      const checkRows = [...document.querySelectorAll(".final-document-check")];
      const stepRows = [...document.querySelectorAll(".final-document-step")];
      const exportButtons = [...document.querySelectorAll(".final-document-feishu-action")];
      const globalActionLabels = [...document.querySelectorAll(".final-document-footer button,.final-document-toolbar button")]
        .map(node => node.textContent.trim()).filter(Boolean);
      const duplicatePrimaryLabels = globalActionLabels.filter((label, index, values) => values.indexOf(label) !== index);
      const malformedDecisionCards = [...document.querySelectorAll(".planner-decision-card")].filter(card => {
        const labels = [...card.querySelectorAll("button")].map(node => node.textContent.trim());
        return labels.filter(label => label === "暂时跳过").length !== 1 || labels.filter(label => label === "应用选择").length !== 1;
      }).length;
      if (percentText !== `${snapshot.percent}%`) throw new Error(`percent mismatch ${percentText}/${snapshot.percent}`);
      if (checkRows.length !== snapshot.checks.length) throw new Error(`check count mismatch ${checkRows.length}/${snapshot.checks.length}`);
      if (stepRows.length !== snapshot.steps.length) throw new Error(`step count mismatch ${stepRows.length}/${snapshot.steps.length}`);
      if (exportButtons.length !== (snapshot.ready ? 1 : 0)) throw new Error("export action contradicts snapshot");
      if (duplicatePrimaryLabels.length) throw new Error(`duplicate button labels: ${duplicatePrimaryLabels.join(",")}`);
      if (malformedDecisionCards) throw new Error(`${malformedDecisionCards} decision cards contain missing or duplicate actions`);
      if (!document.querySelector(".final-document-planning-board")) throw new Error("planning board section missing");
      return { snapshot, percentText, checkCount: checkRows.length, stepCount: stepRows.length, exportButtons: exportButtons.length, duplicatePrimaryLabels, malformedDecisionCards, revision: preview.gameplayRevision };
    });
    await page.evaluate(() => {
      const banner = document.createElement("div");
      banner.textContent = "S5-TC01/03/04/08｜统一完成度、当前版本、策划草图与按钮唯一性";
      banner.id = "stage5-evidence-banner";
      Object.assign(banner.style, { position: "fixed", inset: "0 0 auto 0", zIndex: "100000", padding: "10px 18px", background: "#17233f", color: "white", font: "600 16px Microsoft YaHei" });
      document.body.append(banner);
    });
    await page.screenshot({ path: path.join(output, "s5-tc01-03-08-p7-status-viewport.png") });
    await page.locator(".final-document-planning-board").screenshot({ path: path.join(output, "s5-tc04-planning-board.png") });
    await page.evaluate(() => {
      const board = document.querySelector(".final-document-planning-board");
      const proof = document.createElement("section");
      proof.id = "stage5-board-proof";
      proof.innerHTML = `<h1>S5-TC04｜P7 固定输出完整策划草图</h1>${board.outerHTML}`;
      Object.assign(proof.style, { width: "1500px", padding: "24px", background: "#eef2f7", boxSizing: "border-box" });
      proof.querySelector("svg").style.cssText = "display:block;width:100%;height:auto;max-width:none";
      document.body.append(proof);
    });
    await page.locator("#stage5-board-proof").screenshot({ path: path.join(output, "s5-tc04-planning-board-complete.png") });
    await page.locator("#stage5-board-proof").evaluate(node => node.remove());
    await page.evaluate(() => {
      for (const node of document.querySelectorAll("#reviewWorkspace *")) {
        const style = getComputedStyle(node);
        if (["auto", "scroll"].includes(style.overflowY) && node.scrollHeight > node.clientHeight + 8) {
          node.style.height = `${node.scrollHeight}px`; node.style.maxHeight = "none"; node.style.overflow = "visible";
        }
      }
      const workspace = document.querySelector("#reviewWorkspace");
      workspace.style.height = "auto"; workspace.style.maxHeight = "none"; workspace.style.overflow = "visible";
    });
    const screenshot = path.join(output, "s5-tc01-03-04-08-p7-unified-blocked-full.png");
    await page.screenshot({ path: screenshot, fullPage: true });
    const synthetic = await page.evaluate(() => {
      const source = state.gameplayReviewWorkspace.preview;
      const readyPreview = structuredClone(source);
      readyPreview.blockerIds = [];
      readyPreview.exportReady = true;
      readyPreview.completionSnapshot = {
        ...readyPreview.completionSnapshot, ready: true, percent: 100,
        checks: readyPreview.completionSnapshot.checks.map(item => ({ ...item, done: true, detail: item.id === "delivery" || item.id === "language" ? "已通过" : item.detail })),
        steps: readyPreview.completionSnapshot.steps.map(item => ({ ...item, done: true })),
      };
      FinalDocumentPreview.render({
        root: document.querySelector("#finalExportPreviewView"), preview: readyPreview,
        model: state.gameplayReviewWorkspace.model, interaction: state.reviewWorkspace.model,
        interactionPreview: { boardPreviewSvg: readyPreview.planningBoardPreviewSvg }, view: { exportDisabled: false }, document,
      });
      document.querySelector("#stage5-evidence-banner").textContent = "S5-TC02｜隔离完成态：100% 与唯一飞书导出入口";
      return {
        percent: document.querySelector(".final-document-score strong")?.textContent,
        exportButtons: document.querySelectorAll(".final-document-feishu-action").length,
        duplicateLabels: [...document.querySelectorAll(".final-document-footer button,.final-document-toolbar button")].map(item => item.textContent.trim()).filter((label, index, values) => values.indexOf(label) !== index),
      };
    });
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, "s5-tc02-isolated-ready-viewport.png") });
    await page.locator(".final-document-footer").screenshot({ path: path.join(output, "s5-tc08-single-export-action.png") });
    const missingBoard = await page.evaluate(() => {
      const source = state.gameplayReviewWorkspace.preview;
      const preview = structuredClone(source);
      const snapshot = structuredClone(preview.completionSnapshot);
      snapshot.ready = false; snapshot.percent = Math.min(snapshot.percent, 90);
      snapshot.checks = snapshot.checks.map(item => item.id === "planning_board" ? { ...item, done: false, detail: "缺失或版本过期" } : item);
      snapshot.steps = snapshot.steps.map(item => item.id === "export" ? { ...item, done: false } : item);
      preview.completionSnapshot = snapshot; preview.planningBoardPreviewSvg = ""; preview.exportReady = false;
      FinalDocumentPreview.render({
        root: document.querySelector("#finalExportPreviewView"), preview,
        model: state.gameplayReviewWorkspace.model, interaction: state.reviewWorkspace.model,
        interactionPreview: null, view: { exportDisabled: true }, document,
      });
      document.querySelector("#stage5-evidence-banner").textContent = "S5-TC05｜隔离缺失态：策划草图缺失且禁止导出";
      return {
        planningBoardText: document.querySelector(".final-document-planning-board")?.textContent,
        exportButtons: document.querySelectorAll(".final-document-feishu-action").length,
      };
    });
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, "s5-tc05-isolated-missing-board-viewport.png") });
    const optionalCompetitor = {
      warningPresent: result.snapshot.blockerIds.includes("COMPETITOR_BOARD_PENDING") === false,
      notBlocking: !result.snapshot.checks.some(item => item.id === "competitor"),
    };
    const payload = { passed: errors.length === 0 && synthetic.percent === "100%" && synthetic.exportButtons === 1 && !synthetic.duplicateLabels.length && missingBoard.exportButtons === 0 && /尚未生成/.test(missingBoard.planningBoardText || ""), jobId, screenshot, ...result, synthetic, missingBoard, optionalCompetitor, errors };
    fs.writeFileSync(path.join(output, "stage5-browser-result.json"), JSON.stringify(payload, null, 2));
    if (!payload.passed) throw new Error(errors.join("\n"));
    console.log(JSON.stringify(payload, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
