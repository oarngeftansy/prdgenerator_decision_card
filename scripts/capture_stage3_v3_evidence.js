const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "artifacts", "stage3-v3-acceptance");
const source = JSON.parse(fs.readFileSync(path.join(output, "payloads.json"), "utf8"));
const selectedCaseId = process.env.STAGE3_CASE_ID || "";
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const digest = value => crypto.createHash("sha256").update(value).digest("hex");
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const labels = {
  carrier: "修改载体", issue: "问题", basis: "判断依据", action: "修改动作", remediation: "改善路径",
  impact: "影响范围", retest: "复验条件", passed: "是否通过", findings: "发现的问题",
  chapterId: "章节", text: "内容", prose: "正文", tables: "配置表",
  formulae: "公式", planningBoard: "策划草图", code: "问题类型", message: "问题说明",
  id: "编号", title: "标题", claim: "待发布结论", sourceType: "来源类型", premises: "推断前提",
  steps: "推断步骤", alternatives: "其他可能解释", explanation: "可能解释", excludedBy: "排除依据",
  confidence: "可信度", publicationAllowed: "允许写入正文", publicationReason: "发布判断理由",
  observableFacts: "画面可见事实", forbiddenConclusions: "禁止推出的结论", reason: "原因",
  omissions: "省略内容", omitted: "有意省略", mechanism: "机制", carriers: "载体分工",
  content: "承载内容", source: "素材来源", sources: "来源", chapter: "章节", chapters: "涉及章节",
  chapterIds: "关联章节", question: "回答的问题", example: "示例", expression: "表达式",
  variables: "变量", rounding: "取整规则", sequence: "执行顺序", status: "状态",
  scope: "章节名称", plannerSections: "正文结构", summary: "概述", rows: "表格行",
  parts: "内容组成", part: "组成部分", orderReason: "排序原因", type: "类型", sample: "样例",
};
const values = {
  screenshot_fact: "截图直接事实", video_sequence: "视频时序事实",
  reference_document: "参考文档事实", configuration_table: "配置表事实",
  planner_decision: "策划确认结论", context_inference: "上下文推断",
  reviewed: "已审核", high: "高", medium: "中", low: "低",
};
const label = key => labels[key] || values[key] || key;

function render(value) {
  if (value === null || value === undefined) return '<p class="empty">无</p>';
  if (["string", "number", "boolean"].includes(typeof value)) return `<p class="value">${escapeHtml(value === true ? "是" : value === false ? "否" : values[value] || value)}</p>`;
  if (Array.isArray(value)) {
    if (!value.length) return '<p class="empty">无</p>';
    if (value.every(item => Array.isArray(item))) {
      const [head, ...rows] = value;
      return `<table><thead><tr>${head.map(cell => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    if (value.every(item => item && typeof item === "object" && !Array.isArray(item))) {
      return `<div class="records">${value.map((item, index) => `<article class="record"><h3>记录 ${index + 1}</h3>${render(item)}</article>`).join("")}</div>`;
    }
    return `<ul>${value.map(item => `<li>${typeof item === "object" ? render(item) : escapeHtml(item)}</li>`).join("")}</ul>`;
  }
  return `<dl>${Object.entries(value).map(([key, item]) => `<dt>${escapeHtml(label(key))}</dt><dd>${render(item)}</dd>`).join("")}</dl>`;
}

const css = `
*{box-sizing:border-box}body{margin:0;background:#edf2f7;color:#16243a;font-family:"Microsoft YaHei",Arial,sans-serif;font-size:15px;line-height:1.65}
header{position:relative;display:flex;align-items:center;gap:18px;padding:20px 42px;background:#14233f;color:white}header strong{font-size:22px}header span{font-size:18px;font-weight:700}header em{margin-left:auto;font-style:normal;color:#c9d7ef}
main{padding:28px 48px 48px;max-width:1540px;margin:auto}.summary,.card{background:white;border:1px solid #dbe4ef;border-radius:12px;padding:22px 26px;margin-bottom:18px;box-shadow:0 4px 14px #1b335015}
h1{font-size:21px;margin:0 0 14px}h2{font-size:19px;margin:0 0 14px;border-bottom:1px solid #dfe6ef;padding-bottom:10px}h3{font-size:15px;margin:0 0 9px;color:#2c4c75}
.meta{display:grid;grid-template-columns:110px 1fr;gap:8px 14px}.meta p{margin:0}.hash{font-family:Consolas,monospace;font-size:12px;color:#49617f;overflow-wrap:anywhere}
dl{display:grid;grid-template-columns:minmax(120px,180px) minmax(0,1fr);margin:0;border:1px solid #dfe6ef;border-radius:8px;overflow:hidden}dt,dd{margin:0;padding:9px 12px;border-bottom:1px solid #e8edf3}dt{background:#f1f5fa;font-weight:700}dd{background:white;min-width:0}dl>*:nth-last-child(-n+2){border-bottom:0}
.records{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.record{border:1px solid #dfe6ef;border-radius:9px;padding:14px;background:#fbfcfe}.record dl{grid-template-columns:120px minmax(0,1fr)}
.value{white-space:pre-wrap;margin:0}.empty{margin:0;color:#718096}ul{margin:0;padding-left:22px}li+li{margin-top:5px}
table{width:100%;border-collapse:collapse}th,td{padding:10px 12px;border:1px solid #dfe6ef;text-align:left;vertical-align:top}th{background:#f1f5fa}
`;

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  const manifestPath = path.join(output, "evidence-manifest.json");
  const previous = selectedCaseId && fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, "utf8")) : { entries: [] };
  const entries = selectedCaseId ? previous.entries.filter(item => item.caseId !== selectedCaseId) : [];
  try {
    for (const item of source.payloads) {
      if (selectedCaseId && selectedCaseId !== item.caseId) continue;
      const cards = item.sections.map(section => `<section class="card"><h2>${escapeHtml(section.label)}</h2>${render(section.value)}</section>`).join("");
      await page.setContent(`<style>${css}</style><header><strong>${item.caseId}</strong><span>${escapeHtml(item.title)}</span><em>阶段 3 · 独立真实证据</em></header><main><section class="summary"><h1>本用例输入与身份</h1><div class="meta"><b>输入摘要</b><p>${escapeHtml(item.inputSummary)}</p><b>输入哈希</b><p class="hash">${item.inputHash}</p><b>正文哈希</b><p class="hash">${item.bodyHash}</p></div></section>${cards}</main>`);
      const filename = `${item.caseId.toLowerCase()}-full.png`;
      const target = path.join(output, filename);
      await page.screenshot({ path: target, fullPage: true });
      entries.push({ caseId:item.caseId, visibleCaseId:item.caseId, inputHash:item.inputHash, bodyHash:item.bodyHash,
        screenshot:path.resolve(target), screenshotHash:digest(fs.readFileSync(target)), viewport:"1600x1000", fullPage:true, humanInspected:false });
    }
  } finally { await browser.close(); }
  entries.sort((a,b) => a.caseId.localeCompare(b.caseId));
  fs.writeFileSync(manifestPath, JSON.stringify({ officialJobBefore:source.officialJobBefore, entries }, null, 2));
  console.log(JSON.stringify({ count:entries.length, uniqueScreenshots:new Set(entries.map(item => item.screenshotHash)).size, output }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
