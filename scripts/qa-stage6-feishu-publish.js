const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8009";
const output = path.resolve(__dirname, "..", "artifacts", "stage6-browser-acceptance");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1700, height: 1050 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle" });
  await page.locator('[data-workbench-step="p7"]').click();
  await page.locator(".final-document-shell").waitFor({ state: "visible" });
  await page.evaluate(async () => {
    const revision = state.gameplayReviewWorkspace.model.revision;
    const response = await fetch(`/api/jobs/${state.gameplayReviewClient.jobId}/gameplay-review-model/final-preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision: revision }) });
    if (!response.ok) throw new Error(await response.text());
    state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview: await response.json(), previewStatus: "ready", previewError: "" };
    renderCombinedFinalPreview();
  });
  const action = page.locator(".final-document-feishu-action");
  if (await action.count() !== 1 || !await action.isEnabled()) throw new Error("expected one enabled Feishu publish action");
  await page.screenshot({ path: path.join(output, "s6-tc10-before-real-feishu-export.png") });
  await action.click();
  const deadline = Date.now() + 240000;
  let publication = {};
  while (Date.now() < deadline) {
    publication = await page.evaluate(async id => (await fetch(`/api/jobs/${id}/feishu/publication`, { cache: "no-store" })).json(), jobId);
    if (!["checking_auth", "creating_document", "uploading_media", "creating_boards", "writing_document", "publishing"].includes(publication.status)) break;
    await page.waitForTimeout(1500);
  }
  if (publication.status !== "published" || !publication.documentUrl) throw new Error(`Feishu publish failed: ${JSON.stringify(publication)}`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(output, "s6-tc10-after-real-feishu-export.png") });
  const result = { publication, errors };
  fs.writeFileSync(path.join(output, "feishu-publication-result.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
