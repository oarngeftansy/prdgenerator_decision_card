const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const { chromium } = require("playwright");

const output = path.resolve(__dirname, "..", "artifacts", "stage2-recheck-browser-acceptance");
const url = "http://127.0.0.1:8000/?ui=final_document_preview";
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const viewport = { width: 1600, height: 1000 };
const forbiddenCopy = ["阶段2", "隔离验收", "动态正文", "正常怎么玩", "关键规则", "特殊情况", "怎么验证", "需要配置的数值", "参与计算的字段", "计算公式", "计算示例", "配置来源", "本节规则已完成审核", "按实际配置"];

const interaction = {
  stages: [{ id: "S1", title: "战斗主页", pagePurpose: "承载关卡内的主要战斗", playerAction: "调整载具位置", systemFeedback: "载具继续攻击敌人", operationResult: "继续推进关卡", confirmation: { confirmed: true } }],
  transitions: [], sources: {},
};

function chapter(extra) {
  return { id: "C1", scope: "玩法机制", confirmation: { confirmed: true }, decisionCards: [], ...extra };
}

function baseModel(current) {
  const systemName = current.qaSystemName || "核心玩法";
  const subsystemName = current.qaSubsystemName || current.scope;
  const chapterModel = { ...current };
  delete chapterModel.qaSystemName;
  delete chapterModel.qaSubsystemName;
  return {
    directory: { understanding: { summary: "玩家控制载具推进关卡，并根据当前机制完成战斗或成长选择。" } },
    systems: [{ name: systemName, subsystems: [{ name: subsystemName, chapterIds: ["C1"] }] }],
    chapters: [chapterModel], tables: [], diagrams: [],
  };
}

async function mount(page, id, title, model) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.evaluate(({ id, title, model, interaction }) => {
    document.body.innerHTML = '<header id="qa-banner"></header><main id="qa-root"></main>';
    const banner = document.querySelector("#qa-banner");
    banner.textContent = `${id}｜${title}｜浏览器证据`;
    Object.assign(banner.style, { position: "fixed", inset: "0 0 auto 0", zIndex: "9999", padding: "14px 24px", background: "#17223b", color: "white", font: "600 18px Microsoft YaHei" });
    const root = document.querySelector("#qa-root");
    Object.assign(root.style, { paddingTop: "54px", minHeight: "100vh", width: "100vw", maxWidth: "none", margin: "0" });
    FinalDocumentPreview.render({ root, document, preview: { documentTitle: title, analysisNote: "本文档根据已确认的玩法内容生成。" }, model, interaction, view: { exportDisabled: true }, completion: { logs: [{ message: "正文已生成" }] } });
  }, { id, title, model, interaction });
  await page.locator(".final-document-chapter").first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(100);
}

async function shot(page, name) {
  if (name.includes("tc5-p7")) {
    await page.evaluate(() => {
      const heading = [...document.querySelectorAll(".final-document-content h1")].find((node) => node.textContent.includes("核心战斗"));
      const overview = heading?.nextElementSibling?.matches("p") ? heading.nextElementSibling : null;
      const chapters = [...document.querySelectorAll(".final-document-chapter")];
      const body = [heading?.outerHTML, overview?.outerHTML, ...chapters.map((node) => node.outerHTML)].filter(Boolean).join("");
      document.body.innerHTML = `<header>S2R-TC5-P7｜核心战斗短机制合并｜浏览器证据</header><article>${body}</article>`;
    });
    await page.addStyleTag({ content: "body{margin:0;background:#f4f5f7;font-family:'Microsoft YaHei';color:#263248}header{padding:14px 24px;background:#17223b;color:#fff;font-size:18px;font-weight:600}article{box-sizing:border-box;width:920px;margin:26px auto 40px;background:#fff;padding:54px 72px;box-shadow:0 10px 30px #25304a22}h1{border-bottom:1px solid #dfe3eb;padding-bottom:12px}p,li{font-size:16px;line-height:1.8}.final-document-chapter{margin-top:20px}" });
  }
  const visible = await page.locator("body").innerText();
  for (const word of forbiddenCopy) if (visible.includes(word)) throw new Error(`${name} found forbidden copy: ${word}`);
  await page.screenshot({ path: path.join(output, name), fullPage: true });
  const focusedName = name.replace(/\.png$/, "-focused.png");
  if (name.includes("tc5-p7")) {
    await page.locator("article").screenshot({ path: path.join(output, focusedName) });
  } else {
    const target = name.includes("feishu") ? page.locator("article") : page.locator(".final-document-chapter").first();
    await target.screenshot({ path: path.join(output, focusedName) });
  }
}

function feishuXml() {
  const python = process.env.STAGE2_PYTHON;
  if (!python) throw new Error("STAGE2_PYTHON is required");
  const code = [
    "from tests.test_gameplay_render import complete_job",
    "from backend.gameplay_render import render_gameplay_sections",
    "j=complete_job()",
    "from copy import deepcopy",
    "c=j['gameplayReviewModel']['chapters'][0]",
    "c.update({'id':'GCH-001','scope':'载具移动机制','claims':[],'evidenceClaims':[],'parameters':{},'formulae':[],'workedExamples':[],'configurationSources':[],'acceptanceCases':[],'unknowns':[]})",
    "c['plannerSections']={'summary':'载具沿路线自动前进；玩家拖动控制横向移动，范围受移动边界限制。','normalFlow':[],'keyRules':[],'specialCases':[],'acceptanceExamples':[]}",
    "d=deepcopy(c); d.update({'id':'GCH-002','scope':'生命值状态管理'})",
    "d['plannerSections']={'summary':'受击扣减生命值，归零后本局失败；无效攻击不扣减生命值。','normalFlow':[],'keyRules':[],'specialCases':[],'acceptanceExamples':[]}",
    "j['gameplayReviewModel']['chapters']=[c,d]",
    "j['gameplayReviewModel']['systems']=[{'id':'GSY-001','name':'核心战斗','subsystems':[{'id':'GSS-001','name':'载具控制','chapterIds':['GCH-001']},{'id':'GSS-002','name':'生存规则','chapterIds':['GCH-002']}]}]",
    "j['gameplayReviewModel']['directory'].update({'legacyDerived':False,'status':'confirmed','entries':[{'id':'GDE-001','chapterId':'GCH-001','title':'载具移动机制','order':1},{'id':'GDE-002','chapterId':'GCH-002','title':'生命值状态管理','order':2}]})",
    "j['gameplayReviewModel']['directory']['understanding']={'summary':'玩家控制载具推进关卡，并在战斗中保持生存。'}",
    "j['gameplayReviewModel']['diagrams']=[]; j['gameplayReviewModel']['reviewState']['findings']=[]",
    "print(render_gameplay_sections(j))",
  ].join(";");
  return execFileSync(python, ["-c", code], { cwd: path.resolve(__dirname, ".."), env: { ...process.env, PYTHONUTF8: "1", PYTHONPATH: ".runtime312;runtime_packages_pytest;." }, encoding: "utf8" });
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const page = await browser.newPage({ viewport });
  try {
    await mount(page, "S2R-TC1", "载具移动", baseModel(chapter({ scope: "载具移动", qaSystemName: "核心战斗", qaSubsystemName: "载具控制", plannerSections: { summary: "载具自动向前，玩家负责横向调整位置。", normalFlow: ["拖动后，载具在可移动范围内横向移动。"], keyRules: [], specialCases: [], acceptanceExamples: [] } })));
    if (await page.locator(".final-document-chapter h4").count()) throw new Error("TC1 rendered template headings");
    await shot(page, "s2r-tc1-simple-business-copy.png");

    await mount(page, "S2R-TC2A", "升级选择", baseModel(chapter({ scope: "升级选择", plannerSections: { summary: "玩家达到升级条件后暂停战斗并完成一次强化选择。", normalFlow: ["经验达到升级条件后暂停战斗。", "系统生成本轮候选强化。", "玩家选择一项强化后立即生效。", "选择完成后继续战斗。"], keyRules: [], specialCases: [], acceptanceExamples: [] } })));
    if (await page.locator(".final-document-chapter ol li").count() !== 4) throw new Error("TC2A missing real sequence");
    await shot(page, "s2r-tc2-real-sequence.png");
    await mount(page, "S2R-TC2B", "受击与失败", baseModel(chapter({ scope: "受击与失败", plannerSections: { summary: "载具受到攻击时扣减生命；生命归零后结束本局。", normalFlow: [], keyRules: ["无效攻击不会扣减生命。", "本局结束后不再处理新的伤害。"], specialCases: [], acceptanceExamples: [] } })));
    if (await page.locator(".final-document-chapter ol").count()) throw new Error("TC2B forced a sequence");
    await shot(page, "s2r-tc2-non-sequence-copy.png");

    const config = chapter({ scope: "载具等级", plannerSections: { summary: "玩家消耗升级道具提升载具等级。", normalFlow: ["满足消耗条件后提升一级。"], keyRules: ["升级结果在本次活动内生效。"], specialCases: ["达到等级上限后不可继续升级。"], acceptanceExamples: [] }, parameterSchema: [{ name: "等级", plannerMeaning: "载具当前等级", type: "整数", unit: "级", defaultValue: 1, range: "1~20", configurationSource: "GveMagicBookVehicle._id" }], configurationSources: [{ title: "载具配置表", field: "GveMagicBookVehicle" }] });
    const configModel = baseModel(config);
    configModel.tables = [{ id: "T1", title: "载具等级参数表", status: "reviewed", chapterIds: ["C1"], columns: ["字段", "类型", "默认值", "范围", "来源"], rows: [["等级", "整数", "1", "1~20", "GveMagicBookVehicle._id"]] }];
    await mount(page, "S2R-TC3", "载具等级", configModel);
    if (await page.locator(".final-document-chapter table").count() !== 1) throw new Error("TC3 repeated configuration table");
    await page.locator(".final-document-chapter table").scrollIntoViewIfNeeded();
    await shot(page, "s2r-tc3-single-config-table.png");

    await mount(page, "S2R-TC4A", "伤害结算", baseModel(chapter({ scope: "伤害结算", plannerSections: { summary: "攻击命中后按已确认属性和倍率结算伤害。", normalFlow: [], keyRules: ["目标无效时不结算伤害。"], specialCases: [], acceptanceExamples: [] }, formulae: [{ name: "最终伤害", expression: "攻击属性 × 武器倍率", evidenceLevel: "reference_document", referenceSource: "战斗配置表", variables: [{ name: "攻击属性", evidenceLevel: "reference_document", referenceSource: "角色属性表" }, { name: "武器倍率", evidenceLevel: "reference_document", referenceSource: "武器配置表" }] }], workedExamples: [{ title: "普通命中", expression: "100 × 1.5 = 150" }] })));
    await shot(page, "s2r-tc4-named-formula.png");

    await mount(page, "S2R-TC4B", "受击反馈", baseModel(chapter({ scope: "受击反馈", plannerSections: { summary: "载具受击后显示生命变化并继续处理战斗状态。", normalFlow: ["有效伤害会扣减载具生命值。"], keyRules: [], specialCases: [], acceptanceExamples: [] } })));
    if (await page.locator(".final-document-formula").count()) throw new Error("TC4B rendered unsupported formula");
    await shot(page, "s2r-tc4-no-evidence-no-formula.png");

    const tc5Move = chapter({ id: "C1", scope: "载具移动机制", plannerSections: { summary: "载具沿路线自动前进；玩家拖动控制横向移动，范围受移动边界限制。", normalFlow: [], keyRules: [], specialCases: [], acceptanceExamples: [] } });
    const tc5Health = chapter({ id: "C2", scope: "生命值状态管理", plannerSections: { summary: "受击扣减生命值，归零后本局失败；无效攻击不扣减生命值。", normalFlow: [], keyRules: [], specialCases: [], acceptanceExamples: [] } });
    const tc5Model = { directory: { understanding: { summary: "玩家控制载具推进关卡，并在战斗中保持生存。" } }, systems: [{ name: "核心战斗", subsystems: [{ name: "载具控制", chapterIds: ["C1"] }, { name: "生存规则", chapterIds: ["C2"] }] }], chapters: [tc5Move, tc5Health], tables: [], diagrams: [] };
    await mount(page, "S2R-TC5-P7", "核心战斗短机制合并", tc5Model);
    const p7Text = await page.locator("#qa-root").innerText();
    if (!p7Text.includes("载具移动") || !p7Text.includes("生命值") || p7Text.includes("候选刷新")) throw new Error("TC5 P7 merged copy mismatch");
    if (await page.locator(".final-document-scroll h2, .final-document-scroll h3").count()) throw new Error("TC5 P7 retained tiny subsection headings");
    await shot(page, "s2r-tc5-p7-natural-document.png");

    const xml = feishuXml();
    if (!xml.includes("载具移动") || !xml.includes("生命值") || xml.includes("候选刷新") || xml.includes("<h2>") || xml.includes("<h3>") || xml.includes("<ul>")) throw new Error("TC5 Feishu merged structure mismatch");
    await page.setContent(`<style>body{margin:0;background:#f4f5f7;font-family:'Microsoft YaHei';color:#263248}header{position:fixed;inset:0 0 auto;z-index:2;padding:14px 24px;background:#17223b;color:#fff;font-size:18px;font-weight:600}article{width:920px;margin:78px auto 40px;background:#fff;padding:54px 72px;box-shadow:0 10px 30px #25304a22}h1{border-bottom:1px solid #dfe3eb;padding-bottom:12px}h2,h3,h4{margin-top:28px}p,li{font-size:16px;line-height:1.8}</style><header>S2R-TC5-FEISHU｜核心战斗短机制合并｜浏览器证据</header><article>${xml}</article>`);
    await page.getByText("核心战斗", { exact: true }).scrollIntoViewIfNeeded();
    await shot(page, "s2r-tc5-feishu-natural-document.png");

    console.log("PASS S2R-TC1..TC5 browser acceptance; official task untouched");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
