const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE4_ORIGIN || "http://127.0.0.1:8000";
const base = `${origin}/?job=${jobId}&ui=gameplay_directory`;
const output = path.resolve(__dirname, "..", "artifacts", "stage4-browser-acceptance");
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

async function banner(page, caseId, title) {
  await page.evaluate(({ caseId, title, jobId }) => {
    document.querySelector("#stage4-qa-banner")?.remove();
    const node = document.createElement("div");
    node.id = "stage4-qa-banner";
    node.textContent = `${caseId}｜${title}｜正式任务 ${jobId}`;
    Object.assign(node.style, { position:"fixed", inset:"0 0 auto 0", zIndex:"100000", padding:"10px 18px", background:"#17233f", color:"white", font:"600 16px Microsoft YaHei" });
    document.body.append(node);
  }, { caseId, title, jobId });
}

async function expandScrollable(page, step) {
  await page.evaluate((step) => {
    if (step === "p1") {
      for (const selector of ["#reviewWorkspace", "#gameplayDirectoryView", ".gameplay-directory", ".gameplay-directory-layout"]) {
        const node = document.querySelector(selector);
        if (node) { node.style.height = "auto"; node.style.maxHeight = "none"; node.style.minHeight = "0"; node.style.overflow = "visible"; }
      }
      for (const selector of [".gameplay-directory-tree-column", ".gameplay-directory-understanding-body", ".gameplay-directory-confirm-column"]) {
        const node = document.querySelector(selector);
        if (node) { node.style.height = "auto"; node.style.maxHeight = "none"; node.style.overflow = "visible"; }
      }
      return;
    }
    for (const node of document.querySelectorAll("#reviewWorkspace *")) {
      const style = getComputedStyle(node);
      if ((style.overflowY === "auto" || style.overflowY === "scroll") && node.scrollHeight > node.clientHeight + 8) {
        node.style.height = `${node.scrollHeight}px`;
        node.style.maxHeight = "none";
        node.style.overflow = "visible";
      }
    }
    const workspace = document.querySelector("#reviewWorkspace");
    if (workspace) { workspace.style.height = "auto"; workspace.style.maxHeight = "none"; workspace.style.overflow = "visible"; }
  }, step);
}

async function openStep(page, step, caseId, title, filename) {
  await page.goto(base, { waitUntil: "networkidle" });
  await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
  const nav = page.locator(`[data-workbench-step="${step}"]`);
  await nav.waitFor({ state: "visible" });
  await nav.evaluate(button => button.click());
  await page.waitForTimeout(step === "p7" ? 1800 : 700);
  await expandScrollable(page, step);
  await banner(page, caseId, title);
  const activeView = await page.locator("#reviewWorkspace").getAttribute("data-active-view");
  await page.screenshot({ path: path.join(output, filename), fullPage: true });
  return { activeView, text: await page.locator("#reviewWorkspace").innerText() };
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.setDefaultTimeout(15000);
  const browserErrors = [];
  const responseFailures = [];
  page.on("console", message => { if (message.type() === "error") browserErrors.push(message.text()); });
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("response", response => { if (response.status() >= 400) {
    browserErrors.push(`${response.status()} ${response.url()}`);
    responseFailures.push(response.text().then(body => ({ status:response.status(), url:response.url(), body })).catch(() => ({ status:response.status(), url:response.url(), body:"<unreadable>" })));
  }});
  try {
    await page.goto(base, { waitUntil: "networkidle" });
    try {
      await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 8000 });
    } catch (error) {
      const diagnostics = await page.evaluate(() => ({
        body: document.body.innerText.slice(0, 3000),
        visibleSections: [...document.querySelectorAll("body > section, main > section")].filter(node => !node.hidden).map(node => node.id || node.className),
      }));
      const failures = await Promise.all(responseFailures);
      throw new Error(`workspace hidden; browserErrors=${JSON.stringify(browserErrors)} failures=${JSON.stringify(failures)} diagnostics=${JSON.stringify(diagnostics)}`);
    }
    const model = await page.evaluate(async jobId => (await fetch(`/api/jobs/${jobId}/gameplay-review-model`)).json(), jobId);
    if (model.revision !== 136 || model.chapters.length !== 18) throw new Error("migrated model identity mismatch");
    if (model.editHistory.length !== 0) throw new Error("legacy gameplay history remains");
    if (model.chapters.some(chapter => (chapter.parameterSchema || []).some(item => item.evidenceLevel === "根据素材推断"))) throw new Error("inferred parameter remains");
    if (model.diagrams.some(item => item.status !== "deleted")) throw new Error("deleted diagram decision was revived");

    const p1 = await openStep(page, "p1", "S4-TC07-P1", "原任务目录与十八章保留", "s4-tc07-p1-directory-full.png");
    if (!p1.text.includes("共 18 章") || model.directory.entries.length !== 18) throw new Error("P1 chapter directory incomplete");

    const p4 = await openStep(page, "p4", "S4-TC03-P4", "人工确认章节内容保留", "s4-tc03-p4-planner-content-full.png");
    if (!p4.text.includes("载具移动机制")) throw new Error("P4 planner chapter missing");

    const p5 = await openStep(page, "p5", "S4-TC06-P5", "已删除图解没有复活", "s4-tc06-p5-no-revived-diagram-full.png");
    if (/公式图|伤害公式图/.test(p5.text)) throw new Error("obsolete formula diagram revived");

    const p6 = await openStep(page, "p6", "S4-TC05-P6", "仅保留真实字段的参数表", "s4-tc05-p6-rebuilt-table-full.png");
    if (!p6.text.includes("现有武器数值强化参数表")) throw new Error("rebuilt P6 table missing");
    for (const forbidden of ["变化前生命值", "本次承受伤害", "当前攻击属性", "武器伤害比例", "其他伤害修正"]) {
      if (p6.text.includes(forbidden)) throw new Error(`P6 contains legacy field: ${forbidden}`);
    }

    const p7 = await openStep(page, "p7", "S4-TC06-P7", "当前 revision 预览与真实阻断", "s4-tc06-p7-current-revision-full.png");
    if (!/尚未|需要|阻止|未完成|不可|不能/.test(p7.text)) throw new Error("P7 did not expose real blockers");

    await page.reload({ waitUntil: "networkidle" });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible" });
    await page.waitForTimeout(800);
    await banner(page, "S4-TC07-REFRESH", "刷新后仍是同一正式任务", jobId);
    const restoredModel = await page.evaluate(async jobId => (await fetch(`/api/jobs/${jobId}/gameplay-review-model`)).json(), jobId);
    if (restoredModel.jobId !== jobId || restoredModel.revision !== 136 || restoredModel.chapters.length !== 18) throw new Error("refresh restored wrong task state");
    await page.screenshot({ path: path.join(output, "s4-tc07-refresh-restored-full.png"), fullPage: true });

    const result = { passed: browserErrors.length === 0, jobId, revision:model.revision, chapters:model.chapters.length,
      activeTables:model.tables.filter(item => item.status !== "deleted").length,
      activeDiagrams:model.diagrams.filter(item => item.status !== "deleted").length,
      pages:{ p1:p1.activeView, p4:p4.activeView, p5:p5.activeView, p6:p6.activeView, p7:p7.activeView }, browserErrors };
    fs.writeFileSync(path.join(output, "browser-result.json"), JSON.stringify(result, null, 2));
    if (!result.passed) throw new Error(browserErrors.join("\n"));
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
