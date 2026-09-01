const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const playwrightPath = option("--playwright");
const baseUrl = option("--base", "http://127.0.0.1:8011").replace(/\/$/, "");
const output = path.resolve(option("--output", "artifacts/e2e-full-acceptance-2026-08-13-run1/tc05a-failed-workbench"));
const { chromium } = require(path.resolve(playwrightPath));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1500, height: 960 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  try {
    const jobId = "qa-failed-no-review";
    const failedJob = {
      id: jobId, status: "failed", progress: 0, stage: "分析未通过", error: "视觉模型连接失败：3/3 个请求未完成",
      metadata: { inputType: "image_sequence", projectName: "失败任务工作台验证", mode: "interaction" },
      frames: Array.from({ length: 3 }, (_, index) => ({ id: `F000${index + 1}`, sequenceIndex: index + 1, sceneId: index, imageUrl: "/missing.jpg", sourceName: `${index + 1}.png`, analysis: {} })),
      scenes: [], analysisSummary: { detailFrameCount: 3, qualifiedDetailFrameCount: 0, modelEnabled: true },
    };
    await page.route(`**/api/jobs/${jobId}`, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(failedJob) }));
    await page.route("**/missing.jpg", (route) => route.fulfill({ status: 200, contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640"><rect width="100%" height="100%" fill="#eef2ff"/></svg>' }));
    await page.goto(`${baseUrl}/?job=${jobId}`, { waitUntil: "domcontentloaded" });
    await page.getByText("分析未通过 · 已保留 3 张素材").waitFor();
    await page.getByRole("button", { name: "进入工作台", exact: true }).click();
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "analysis_failed");
    assert.equal(new URL(page.url()).searchParams.get("job"), jobId);
    assert.equal(new URL(page.url()).searchParams.get("ui"), "analysis_failed");
    await page.getByRole("heading", { name: "分析未通过" }).waitFor();
    await page.getByRole("button", { name: "配置模型" }).waitFor();
    await page.getByRole("button", { name: "重试任务", exact: true }).waitFor();
    await page.getByRole("button", { name: "返回素材" }).waitFor();
    await page.screenshot({ path: path.join(output, "TC05A-failed-task-workbench.png"), fullPage: true });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "analysis_failed");
    await page.screenshot({ path: path.join(output, "TC05A-failed-task-refresh.png"), fullPage: true });
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify({ passed: true, errors, url: page.url() }, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
