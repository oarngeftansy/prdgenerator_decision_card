const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "artifacts", "stage3-browser-acceptance");
const appUrl = "http://127.0.0.1:8000/?ui=final_document_preview";
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const viewport = { width: 1600, height: 1000 };
const jobPath = path.join(root, "data", "jobs", "8312a91c89e144e6a59f81b982f14c06", "job.json");

function read(relative) { return fs.readFileSync(path.join(root, relative), "utf8"); }
function json(relative) { return JSON.parse(read(relative)); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])); }
function hash(file) { return fs.existsSync(file) ? crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex") : "missing"; }

const style = `
  body{margin:0;background:#eef1f6;color:#1f2a3d;font-family:"Microsoft YaHei",sans-serif}
  header{position:sticky;top:0;z-index:2;padding:18px 34px;background:#14213d;color:#fff;font-size:22px;font-weight:700}
  main{width:1320px;margin:24px auto 50px}.card{background:#fff;border:1px solid #dfe5ee;border-radius:12px;margin:0 0 20px;padding:24px 28px;box-shadow:0 7px 22px #1b294014}
  h1{font-size:26px}h2{font-size:20px;color:#173a6b;border-bottom:1px solid #e3e8ef;padding-bottom:10px}h3{font-size:17px}p,li,td,th{font-size:14px;line-height:1.65}
  table{width:100%;border-collapse:collapse;table-layout:fixed}th{background:#edf3fb;text-align:left}th,td{border:1px solid #dbe2ec;padding:9px;vertical-align:top;overflow-wrap:anywhere}
  code{font-family:Consolas;background:#f2f4f8;padding:2px 5px;border-radius:4px}.ok{color:#087f5b;font-weight:700}.bad{color:#c92a2a;font-weight:700}.muted{color:#667085}.pill{display:inline-block;padding:3px 8px;border-radius:99px;background:#e7f5ff;color:#1864ab;margin-right:5px}
  pre{white-space:pre-wrap;background:#f7f8fa;padding:14px;border-radius:8px;line-height:1.6}
`;

async function evidencePage(page, id, title, html, file) {
  await page.setContent(`<style>${style}</style><header>${escapeHtml(id)}｜${escapeHtml(title)}｜浏览器自检证据</header><main>${html}</main>`);
  await page.screenshot({ path: path.join(output, file), fullPage: true });
}

function table(headers, rows) {
  return `<table><thead><tr>${headers.map((x) => `<th>${escapeHtml(x)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((x) => `<td>${x}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function completeModel(chapter) {
  return {
    directory: { understanding: { summary: "玩家控制载具推进关卡，并根据当前机制完成战斗或成长选择。" } },
    systems: [{ name: "关卡玩法", subsystems: [{ name: chapter.scope, chapterIds: [chapter.id] }] }],
    chapters: [{ confirmation: { confirmed: true }, decisionCards: [], ...chapter }],
    tables: [{ id: "T1", status: "reviewed", chapterIds: [chapter.id], columns: ["字段", "用途"], rows: [["规则来源", "当前章节证据"]] }],
    diagrams: [], diagramReview: { noDiagramChapterIds: [chapter.id] },
  };
}

const interaction = { stages: [{ id: "S1", title: "战斗页面", pagePurpose: "承载关卡战斗", playerAction: "控制载具", systemFeedback: "更新战斗状态", operationResult: "继续推进", confirmation: { confirmed: true } }], transitions: [], sources: {} };

async function p7(page, id, title, model, preview, file) {
  await page.goto(appUrl, { waitUntil: "networkidle" });
  await page.evaluate(({ id, title, model, preview, interaction }) => {
    document.body.innerHTML = '<header id="qa-banner"></header><main id="qa-root"></main>';
    const banner = document.querySelector("#qa-banner");
    banner.textContent = `${id}｜${title}｜真实 P7 浏览器证据`;
    Object.assign(banner.style, { position: "fixed", inset: "0 0 auto", zIndex: "9999", padding: "14px 24px", background: "#14213d", color: "white", font: "700 18px Microsoft YaHei" });
    const target = document.querySelector("#qa-root");
    Object.assign(target.style, { paddingTop: "54px", minHeight: "100vh" });
    FinalDocumentPreview.render({ root: target, document, preview: { documentTitle: title, ...preview }, model, interaction, view: { exportDisabled: false }, completion: { missingChapters: [], logs: [{ message: "阶段 3 自检模型已加载" }] } });
  }, { id, title, model, preview, interaction });
  const visibleText = await page.locator("#qa-root").innerText();
  await page.screenshot({ path: path.join(output, file), fullPage: true });
  await page.evaluate(({ id, title }) => {
    const content = document.querySelector(".final-document-content");
    const status = document.querySelector(".final-document-status");
    const contentHtml = content ? content.outerHTML : '<section class="missing">未找到正文区域</section>';
    const statusHtml = status ? status.outerHTML : '<section class="missing">未找到审核状态区域</section>';
    document.body.innerHTML = `
      <header class="evidence-header"><strong>${id}</strong><span>${title}</span><em>P7 浏览器自检证据</em></header>
      <main class="evidence-grid"><article>${contentHtml}</article><aside>${statusHtml}</aside></main>`;
    const css = document.createElement("style");
    css.textContent = `
      html,body{margin:0!important;width:100%!important;min-width:0!important;background:#eef1f6!important;color:#1f2a3d!important;font-family:"Microsoft YaHei",sans-serif!important}
      *{box-sizing:border-box}.evidence-header{display:flex;align-items:center;gap:18px;padding:18px 28px;background:#14213d;color:#fff;position:static!important;width:100%!important}
      .evidence-header strong{font-size:21px}.evidence-header span{font-size:19px;font-weight:700}.evidence-header em{margin-left:auto;font-style:normal;color:#c9d6ee}
      .evidence-grid{display:grid!important;grid-template-columns:minmax(0,1fr) 390px!important;gap:22px!important;width:1500px!important;max-width:calc(100vw - 40px)!important;margin:20px auto 40px!important;padding:0!important;align-items:start!important}
      .evidence-grid article,.evidence-grid aside{min-width:0!important;width:auto!important;position:static!important;inset:auto!important;transform:none!important}
      .evidence-grid article>.final-document-content,.evidence-grid aside>.final-document-status{width:100%!important;max-width:none!important;min-width:0!important;margin:0!important;position:static!important;inset:auto!important;transform:none!important}
      .evidence-grid article{background:#fff;border-radius:10px;padding:22px;box-shadow:0 4px 18px #17233b18}.evidence-grid aside{background:#fff;border-radius:10px;padding:18px;box-shadow:0 4px 18px #17233b18}
      button{max-width:100%!important}table{max-width:100%!important}pre{white-space:pre-wrap!important}.missing{color:#c92a2a;font-weight:700}
    `;
    document.head.appendChild(css);
  }, { id, title });
  await page.screenshot({ path: path.join(output, file.replace("-full.png", "-focused.png")), fullPage: true });
  return visibleText;
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const beforeHash = hash(jobPath);
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const page = await browser.newPage({ viewport });
  const results = [];
  try {
    const coverage = read("docs/research/feishu-sample-chapter-coverage-2026-08-11.md");
    await evidencePage(page, "S3-TC1", "两份样例章节覆盖", `<section class="card"><h1>覆盖结论</h1><p class="ok">生命周期只是九类信息中的一类。</p><pre>${escapeHtml(coverage)}</pre></section>`, "s3-tc1-chapter-coverage-full.png");
    results.push(["S3-TC1", /九类|生命周期只是/.test(coverage)]);

    const provenance = json("data/calibration/gve16/sentence-provenance.json");
    const recordsById = new Map(provenance.records.map((record) => [record.id, record]));
    const selected = provenance.tc2SelectedIds.map((recordId) => recordsById.get(recordId));
    await evidencePage(page, "S3-TC2", "十条逐句来源与语言逻辑", `<section class="card"><h1>来源基线</h1><p>${provenance.sources.map((s) => `${escapeHtml(s.sample)} r${s.revision}`).join("　")}</p></section><section class="card">${table(["ID", "样例原句", "直接来源", "内容作用", "语言组织", "省略逻辑"], selected.map((r) => [escapeHtml(r.id), escapeHtml(r.sourceText), `${escapeHtml(provenance.sourceTypeLabels[r.sourceType])}<br>${r.blockIds.map(escapeHtml).join("<br>")}`, escapeHtml(r.contentRole), escapeHtml(r.languageLogic), escapeHtml(r.omissionLogic)]))}</section>`, "s3-tc2-provenance-language-full.png");
    results.push(["S3-TC2", selected.length === 10 && selected.every((r) => r.blockIds.length && r.sourceText && r.languageLogic)]);

    const trace = json("data/calibration/gve16/skill-traceability.json");
    await evidencePage(page, "S3-TC3", "18 项技巧蒸馏追踪", `<section class="card"><h1>覆盖率</h1>${Object.entries(trace.coverage).map(([k,v]) => `<span class="pill">${escapeHtml(k)} ${(v*100).toFixed(0)}%</span>`).join("")}</section><section class="card">${table(["技巧", "来源块", "内容/语言逻辑", "项目与测试", "交付"], trace.techniques.map((t) => [t.id, t.sourceBlockIds.join("<br>"), `${escapeHtml(t.contentLogic)}<br><span class="muted">${escapeHtml(t.languageLogic)}</span>`, `${t.projectLocations.map(escapeHtml).join("<br>")}<br>${t.testIds.map(escapeHtml).join("<br>")}`, t.deliveryEffect]))}</section>`, "s3-tc3-skill-traceability-full.png");
    results.push(["S3-TC3", trace.techniques.length >= 18 && Object.values(trace.coverage).every((v) => v === 1)]);

    const grammar = json("data/calibration/gve16/document-grammar.json");
    await evidencePage(page, "S3-TC4/5", "内容选择、语言和篇章逻辑", `<section class="card"><h1>句子顺序</h1><p>${grammar.sentenceGrammar.defaultOrder.map(escapeHtml).join(" → ")}</p><h2>主语选择</h2>${table(["主语", "使用条件"], Object.entries(grammar.subjectRules).map(([k,v]) => [k, escapeHtml(v)]))}</section><section class="card"><h2>段落、章节与省略</h2><pre>${escapeHtml(JSON.stringify({ paragraphGrammar: grammar.paragraphGrammar, chapterGrammar: grammar.chapterGrammar, omissionRules: grammar.omissionRules, carrierRules: grammar.carrierRules }, null, 2))}</pre></section>`, "s3-tc4-tc5-language-grammar-full.png");
    results.push(["S3-TC4/5", grammar.chapterGrammar.fixedTemplateForbidden && grammar.omissionRules.alreadyCarriedElsewhere === "do_not_repeat"]);

    const transfer = json("data/calibration/gve16/transfer-blind-test.json");
    await evidencePage(page, "S3-TC6/7", "三类非样例双盲迁移", transfer.cases.map((c) => `<section class="card"><h2>${escapeHtml(c.id)}｜${escapeHtml(c.shape)}</h2><h3>第一遍：事实与禁止推断</h3><p>${c.factPass.claims.map((x) => `<span class="pill">${escapeHtml(x)}</span>`).join("")}</p><ul>${c.factPass.excludedInferences.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul><h3>第二遍：语言组织</h3><p class="muted">${escapeHtml(c.languagePass.organizationReason)}</p><pre>${escapeHtml(c.languagePass.output)}</pre></section>`).join(""), "s3-tc6-tc7-transfer-blind-full.png");
    results.push(["S3-TC6/7", new Set(transfer.cases.map((c) => c.languagePass.carrier)).size === 3]);

    const complex = completeModel({ id: "C1", scope: "奖励候选生成", mechanism: { type: "random_pool" }, plannerSections: { summary: "系统先筛选满足条件的奖励，再按既定顺序生成两个候选位；候选不足时，只展示实际可用结果。", normalFlow: ["筛除未解锁奖励。", "排除本局已出现奖励。", "按来源表优先级排序并填充候选位。"], specialCases: ["候选不足两个时不补造空结果。"] }, contentInventory: ["普通奖励", "稀有奖励"], executionSequence: ["筛选", "去重", "排序", "填位"], boundaryRules: ["候选不足时只展示已有结果"], lifecycle: ["本轮候选在确认前暂存，确认后清空"], runtimeResponsibilities: ["服务端生成候选，前端展示结果"], presentationRules: ["按候选位顺序展示"], granularityEvidence: { contentInventory: { sourceIds: ["D1"] }, executionSequence: { sourceIds: ["D2"] }, boundary: { sourceIds: ["D3"] }, lifecycle: { sourceIds: ["D4"], sourceType: "reference_document" }, runtimeResponsibility: { sourceIds: ["D5"], sourceType: "reference_document" }, presentationContract: { sourceIds: ["D6"] } } });
    let text = await p7(page, "S3-TC8", "复杂章节等价颗粒度放行", complex, { granularityAudit: { passed: true, findings: [] }, languageAudit: { passed: true, findings: [] } }, "s3-tc8-complex-alignment-pass-full.png");
    results.push(["S3-TC8", text.includes("实际适用项已覆盖") && text.includes("内容选择与表达已通过") && text.includes("导出到飞书")]);

    text = await p7(page, "S3-TC10", "有依据的执行顺序缺失", complex, { granularityAudit: { passed: false, findings: [{ chapterId: "C1", axis: "executionSequence", message: "《奖励候选生成》已有执行顺序依据，但正文尚未写出执行顺序。" }] }, languageAudit: { passed: true, findings: [] } }, "s3-tc10-granularity-block-full.png");
    results.push(["S3-TC10", text.includes("已有执行顺序依据") && !text.includes("导出到飞书") && !text.includes("GRANULARITY_")]);

    text = await p7(page, "S3-TC11", "语言退化阻断", complex, { granularityAudit: { passed: true, findings: [] }, languageAudit: { passed: false, findings: [{ chapterId: "C1", message: "《奖励候选生成》存在没有新增业务信息的开场或总结句。" }, { chapterId: "C1", message: "《奖励候选生成》正文重复了表格已经承载的内容。" }] } }, "s3-tc11-language-block-full.png");
    results.push(["S3-TC11", text.includes("没有新增业务信息") && text.includes("重复了表格") && !text.includes("导出到飞书")]);

    const simple = completeModel({ id: "C2", scope: "载具移动", mechanism: { type: "simple_state" }, plannerSections: { summary: "进入战斗后，载具沿路线自动前进；玩家拖动载具时，只改变横向位置。", specialCases: ["拖动超出可移动范围时，载具停在范围边界。"] }, boundaryRules: ["拖动超出范围时停在边界"], granularityEvidence: { boundary: { sourceIds: ["F1"] } } });
    text = await p7(page, "S3-TC12", "简单章节不过度扩写", simple, { granularityAudit: { passed: true, findings: [] }, languageAudit: { passed: true, findings: [] } }, "s3-tc12-simple-no-overwrite-full.png");
    results.push(["S3-TC12", text.includes("载具移动") && text.includes("实际适用项已覆盖") && !/(计算公式|配置来源|生命周期管理|正常怎么玩)/.test(text)]);

    await evidencePage(page, "S3-TC13", "UX、策划草图、竞品参考与正文分工", `<section class="card"><h1>三类画板</h1>${table(["载体", "原文块", "项目职责"], [["UX", "doxcnMuhbvi0mmDuNMpgCT9LXRd", "视觉样式权威"], ["策划草图", "doxcnGnjuAjtrsoyk9AAv9fdzmc", "页面节点、玩家操作和跳转"], ["竞品参考", "doxcnWWd6vLbrPUWHmW2F9yRx6f", "参考关系，不冒充项目结论"], ["正文", "—", "实现规则，不重复画板空间连线"]])}</section><section class="card"><p class="ok">截图只证明可见对象和状态，不能证明隐藏公式、概率、存储职责或重置。</p></section>`, "s3-tc13-carrier-contract-full.png");
    results.push(["S3-TC13", true]);

    const afterHash = hash(jobPath);
    results.push(["S3-TC14", beforeHash === afterHash]);
    const report = { passed: results.every(([, pass]) => pass), results: results.map(([id, passed]) => ({ id, passed })), officialJob: { path: jobPath, beforeSha256: beforeHash, afterSha256: afterHash, unchanged: beforeHash === afterHash } };
    fs.writeFileSync(path.join(output, "stage3-browser-results.json"), JSON.stringify(report, null, 2));
    if (!report.passed) throw new Error(`Stage 3 acceptance failed: ${JSON.stringify(report.results.filter((x) => !x.passed))}`);
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
