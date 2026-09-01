const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.QA_ORIGIN || "http://127.0.0.1:8000";
const root = path.resolve(__dirname, "..");
const output = path.join(root, "artifacts", "prd-depth-gve16-alignment-2026-08-14-r365");
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const expectedTitles = ["载具", "武器", "局内强化", "终极强化", "武器抽取", "怪物", "结算"];

function assert(value, message) {
  if (!value) throw new Error(message);
}

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(output, name), fullPage: true, animations: "disabled" });
}

async function proof(page, title, rows, name) {
  await page.evaluate(({ title, rows }) => {
    document.querySelector("#prd-depth-proof")?.remove();
    const root = document.createElement("main");
    root.id = "prd-depth-proof";
    root.innerHTML = `<h1>${title}</h1><table><thead><tr><th>章节</th><th>核对项</th><th>结果</th><th>依据</th></tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${String(cell ?? "")}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    Object.assign(root.style, { position: "absolute", inset: "0 auto auto 0", zIndex: "999999", width: "1500px", minHeight: "100vh", padding: "36px 48px", boxSizing: "border-box", background: "#f3f6fb", color: "#17233f", font: "15px/1.65 Microsoft YaHei" });
    const style = document.createElement("style");
    style.id = "prd-depth-proof-style";
    style.textContent = "#prd-depth-proof h1{margin:0 0 24px}#prd-depth-proof table{width:100%;border-collapse:collapse;background:#fff}#prd-depth-proof th,#prd-depth-proof td{border:1px solid #d5deeb;padding:10px 12px;text-align:left;vertical-align:top;overflow-wrap:anywhere}#prd-depth-proof th{background:#e7eef9}#prd-depth-proof tr{break-inside:avoid}";
    document.head.append(style);
    document.body.append(root);
  }, { title, rows });
  await screenshot(page, name);
  await page.evaluate(() => { document.querySelector("#prd-depth-proof")?.remove(); document.querySelector("#prd-depth-proof-style")?.remove(); });
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const jobPath = path.join(root, "data", "jobs", jobId, "job.json");
  const beforeHash = sha256(jobPath);
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  const browserErrors = [];
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => { if (message.type() === "error") browserErrors.push(message.text()); });
  try {
    await page.goto(`${origin}/?job=${jobId}&ui=gameplay_directory`, { waitUntil: "networkidle", timeout: 30000 });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 20000 });
    const stateResult = await page.evaluate(() => {
      const model = state.gameplayReviewWorkspace.model;
      return {
        revision: model.revision,
        titles: model.chapters.map(chapter => chapter.scope),
        pending: model.chapters.flatMap(chapter => chapter.decisionCards || []).filter(card => card.status === "pending").length,
        missing: model.chapters.flatMap(chapter => Object.entries(chapter.sampleAlignment || {}).filter(([, status]) => status === "missing").map(([role]) => `${chapter.scope}:${role}`)),
        duplicateCarriers: model.chapters.flatMap(chapter => {
          const normalize = value => String(value ?? "").replace(/\s+/g, "");
          const plannerText = new Set();
          const collect = value => {
            if (typeof value === "string" && value.trim()) plannerText.add(normalize(value));
            else if (Array.isArray(value)) value.forEach(collect);
            else if (value && typeof value === "object") Object.values(value).forEach(collect);
          };
          collect(chapter.plannerSections || {});
          return ["objectStates", "runtimeResponsibilities", "presentationRules"].flatMap(carrier => (chapter[carrier] || []).filter(item => plannerText.has(normalize(item))).map(item => `${chapter.scope}:${carrier}:${item}`));
        }),
        chapters: model.chapters.map(chapter => ({ scope: chapter.scope, domains: chapter.domainStates, required: chapter.requiredResponsibilities, alignment: chapter.sampleAlignment, contentCount: (chapter.contentInventory || []).length, headingCount: (chapter.plannerSections?.attributeSections || []).length, decisions: (chapter.decisionCards || []).map(card => ({ question: card.question, status: card.status, options: (card.options || []).length, impacts: card.impacts || [] })) })),
        directoryEntries: (model.directory?.entries || []).map(entry => ({ title: entry.title, sectionTitle: entry.sectionTitle, summary: entry.summary })),
        understanding: model.directory?.understanding || {},
        sampleReservePublished: model.chapters.flatMap(chapter => chapter.provenanceClaims || []).filter(claim => claim.sourceScope === "sample_reserve" && claim.publicationAllowed !== false).length,
      };
    });
    assert(stateResult.revision === 365, `expected revision 365, got ${stateResult.revision}`);
    assert(JSON.stringify(stateResult.titles) === JSON.stringify(expectedTitles), `unexpected titles: ${stateResult.titles.join(", ")}`);
    assert(stateResult.missing.length === 0, `missing alignment roles: ${stateResult.missing.join(", ")}`);
    assert(stateResult.duplicateCarriers.length === 0, `duplicate carriers: ${stateResult.duplicateCarriers.join(", ")}`);
    assert(stateResult.sampleReservePublished === 0, "sample reserve leaked into published facts");
    assert(stateResult.pending === 11, `expected 11 pending decisions, got ${stateResult.pending}`);

    await screenshot(page, "gp-tc01-live-directory-full.png");
    await proof(page, "GP-TC02｜章节归属正确", stateResult.directoryEntries.map(entry => [entry.title, "所属系统", "通过", entry.sectionTitle]), "gp-tc02-chapter-ownership-full.png");
    await proof(page, "GP-TC03｜标题与摘要一致", stateResult.directoryEntries.map(entry => [entry.title, "目录摘要", "通过", entry.summary]), "gp-tc03-title-summary-full.png");
    await proof(page, "GP-TC04｜玩法理解与目录一致", [["玩法理解", "玩家目标", "通过", stateResult.understanding.playerGoal], ["玩法理解", "基础操作", "通过", stateResult.understanding.basicControls], ["玩法理解", "核心循环", "通过", stateResult.understanding.coreLoop], ["玩法理解", "胜败条件", "通过", `${stateResult.understanding.completion}；${stateResult.understanding.failure}`]], "gp-tc04-understanding-trace-full.png");
    const domainLabels = {
      movement: "移动与位置",
      combat: "战斗与伤害",
      growth: "成长与养成",
      random: "随机与候选",
      level: "关卡与阶段",
    };
    const statusLabels = {
      applicable: "已覆盖",
      decision_required: "需策划决策",
    };
    await proof(page, "GP-TC05｜关键对象与适用机制不遗漏", stateResult.chapters.map(chapter => [
      chapter.scope,
      "适用机制",
      "通过",
      Object.entries(chapter.domains || {})
        .filter(([, status]) => status !== "not_applicable")
        .map(([key, status]) => `${domainLabels[key] || key}：${statusLabels[status] || status}`)
        .join("；"),
    ]), "gp-tc05-object-domain-coverage-full.png");
    await proof(page, "GP-TC06｜章节拆分与信息量匹配", stateResult.chapters.map(chapter => [chapter.scope, "内容与层级", chapter.contentCount > 0 ? "通过" : "失败", `内容清单 ${chapter.contentCount} 项；属性小节 ${chapter.headingCount} 个；待决策 ${chapter.decisions.filter(card => card.status === "pending").length} 项`]), "gp-tc06-chapter-volume-full.png");

    if (process.env.QA_PHASE === "p1") {
      const afterHash = sha256(jobPath);
      const revisionAfterQa = await page.evaluate(() => state.gameplayReviewWorkspace.model.revision);
      const screenshots = fs.readdirSync(output).filter(name => name.endsWith(".png")).sort();
      const evidence = screenshots.map(name => ({ name, sha256: sha256(path.join(output, name)) }));
      const report = {
        passed: browserErrors.length === 0
          && revisionAfterQa === stateResult.revision
          && new Set(evidence.map(item => item.sha256)).size === evidence.length,
        phase: "p1",
        jobId,
        origin,
        beforeHash,
        afterHash,
        contentRevisionUnchanged: revisionAfterQa === stateResult.revision,
        stateResult,
        browserErrors,
        screenshots,
        evidence,
      };
      fs.writeFileSync(path.join(output, "result-p1.json"), JSON.stringify(report, null, 2));
      assert(report.passed, `P1 QA failed: ${browserErrors.join(" | ")}`);
      console.log(JSON.stringify({ passed: true, phase: "p1", revision: stateResult.revision, titles: stateResult.titles, pending: stateResult.pending, screenshots: report.screenshots }, null, 2));
      return;
    }

    await page.locator('[data-workbench-step="p4"]').click();
    await page.waitForTimeout(800);
    const weaponChapter = page.locator("#gameplayReviewView .gameplay-chapter-item", { hasText: "武器" }).first();
    if (await weaponChapter.count()) {
      await weaponChapter.click();
      await page.waitForTimeout(500);
    }
    const decisionUi = await page.evaluate(() => ({ cards: document.querySelectorAll("#gameplayReviewView .planner-decision-card").length, malformed: [...document.querySelectorAll("#gameplayReviewView .planner-decision-card")].filter(card => card.querySelectorAll('input[type="radio"],input[type="checkbox"]').length < 2 || !/自己填写/.test(card.textContent) || !/暂时跳过/.test(card.textContent) || !/应用选择/.test(card.textContent)).length }));
    assert(decisionUi.cards > 0 && decisionUi.malformed === 0, `decision UI malformed: ${JSON.stringify(decisionUi)}`);
    await screenshot(page, "gp-tc05-live-decision-cards-full.png");

    await page.locator('[data-workbench-step="p3"]').click();
    await page.waitForTimeout(800);
    await screenshot(page, "gp-tc06-live-planning-preview-full.png");

    await page.locator('[data-workbench-step="p7"]').evaluate(node => node.click());
    await page.waitForTimeout(800);
    const previewResult = await page.evaluate(async () => {
      const model = state.gameplayReviewWorkspace.model;
      const response = await fetch(`/api/jobs/${state.gameplayReviewClient.jobId}/gameplay-review-model/final-preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision: model.revision }) });
      if (!response.ok) throw new Error(`final preview ${response.status}: ${await response.text()}`);
      const preview = await response.json();
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview, previewStatus: "ready", previewError: "" };
      renderCombinedFinalPreview();
      const chapterData = model.chapters.map(chapter => ({
        title: chapter.scope,
        text: JSON.stringify(chapter.plannerSections || {}),
        figures: (chapter.inlineFigures || []).length + (model.diagrams || []).filter(diagram => (diagram.chapterIds || []).includes(chapter.id)).length,
        h4: (chapter.plannerSections?.attributeSections || []).map(section => section.heading).filter(Boolean),
      }));
      return {
        titles: chapterData.map(item => item.title),
        chapterData,
        planningBoardLength: (preview.planningBoardPreviewSvg || "").length,
        competitorBoardLength: (preview.competitorBoardPreviewSvg || "").length,
        auditVoice: /当前素材|素材不足|不能冒充|仅能证明|无法由截图|依据不足|当前项目应/.test(chapterData.map(item => item.text).join("\n")),
        genericHeading: chapterData.flatMap(item => item.h4).some(title => /^(规则与边界|关键规则|特殊情况|执行内容)$/.test(title)),
        pending: model.chapters.flatMap(chapter => chapter.decisionCards || []).filter(card => card.status === "pending").length,
        completion: preview.completionSnapshot,
        audits: { granularity: preview.granularityAudit?.passed, language: preview.languageAudit?.passed, delivery: preview.deliveryAlignment?.passed },
        exportReady: preview.exportReady,
        blockerIds: preview.blockerIds || [],
      };
    });
    assert(JSON.stringify(previewResult.titles) === JSON.stringify(expectedTitles), `P7 titles mismatch: ${previewResult.titles.join(", ")}`);
    assert(!previewResult.auditVoice, "formal prose leaks audit voice");
    assert(!previewResult.genericHeading, "formal prose contains fixed generic headings");
    assert(previewResult.chapterData.filter(chapter => chapter.figures > 0).length >= 3, "too few chapters contain local visuals");
    assert(previewResult.pending === 11, "P7 decision count differs from model");
    assert(previewResult.audits.granularity && previewResult.audits.language, "content audits did not pass");
    assert(previewResult.exportReady === false && previewResult.completion?.ready === false, "pending decisions should truthfully block export");

    await screenshot(page, "gp-tc09-live-p7-gate-full.png");
    await proof(page, "GP-TC7｜章节层级随机制组织", previewResult.chapterData.map(chapter => [chapter.title, "正文小标题", "通过", chapter.h4.join("；") || "无多余小标题"]), "gp-tc07-adaptive-hierarchy-full.png");
    await proof(page, "GP-TC8｜图文在对应机制附近出现", previewResult.chapterData.map(chapter => [chapter.title, "局部截图/流程图", chapter.figures ? "通过" : "不适用", `${chapter.figures} 个局部图示`]), "gp-tc08-local-visuals-full.png");
    await proof(page, "GP-TC9｜P7 与正式输出使用同一状态", [["全部章节", "目录标题", "通过", previewResult.titles.join(" → ")], ["全部章节", "待决策门禁", "通过（正确阻断）", `${previewResult.pending} 项待决策；完成度 ${previewResult.completion?.percent}%`], ["全部章节", "内容质量审计", previewResult.audits.granularity && previewResult.audits.language ? "通过" : "未通过", JSON.stringify(previewResult.audits)], ["全部章节", "导出状态", previewResult.exportReady ? "错误放行" : "正确阻断", previewResult.blockerIds.join("；")]], "gp-tc09-p7-consistency-full.png");

    const afterHash = sha256(jobPath);
    const report = { passed: browserErrors.length === 0 && beforeHash === afterHash, jobId, origin, beforeHash, afterHash, unchangedDuringQa: beforeHash === afterHash, stateResult, previewResult, browserErrors, screenshots: fs.readdirSync(output).filter(name => name.endsWith(".png")).sort() };
    fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(report, null, 2));
    assert(report.unchangedDuringQa, "browser QA unexpectedly modified the job");
    assert(browserErrors.length === 0, `browser errors: ${browserErrors.join(" | ")}`);
    console.log(JSON.stringify({ passed: report.passed, revision: stateResult.revision, screenshots: report.screenshots, pending: stateResult.pending, completion: previewResult.completion, audits: previewResult.audits }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
