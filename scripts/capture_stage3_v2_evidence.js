const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "artifacts", "stage3-v2-acceptance");
const source = JSON.parse(fs.readFileSync(path.join(output, "payloads.json"), "utf8"));
const selectedCaseId = process.env.STAGE3_CASE_ID || "";
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const hash = (value) => crypto.createHash("sha256").update(value).digest("hex");
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const pretty = (value) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
const keyLabels = {
  id:"编号", title:"标题", claim:"待发布结论", sourceType:"来源类型", premises:"推断前提", steps:"推断步骤",
  alternatives:"替代解释", explanation:"可能解释", excludedBy:"排除依据", confidence:"可信度",
  publicationAllowed:"允许写入正文", publicationReason:"发布判断理由", observableFacts:"画面可见事实",
  forbiddenConclusions:"禁止推出的结论", reason:"原因", omissions:"省略情况", type:"类型", example:"示例",
  mechanism:"机制", carriers:"载体分工", carrier:"载体", content:"承载内容", source:"素材来源",
  shape:"机制形态", factPass:"事实建模", languagePass:"语言组织", claims:"确认事实", excludedInferences:"禁止推断",
  sectionCount:"章节数量", organizationReason:"组织原因", output:"实际输出", method:"执行方法"
  ,sample:"样例", chapter:"章节", parts:"内容组成", part:"组成部分", question:"回答的问题",
  orderReason:"排序原因", omitted:"有意省略", passed:"是否通过", findings:"发现的问题",
  chapters:"涉及章节", chapterId:"章节", findingCount:"问题数量", code:"问题类型", message:"问题说明"
};
const valueLabels = {
  screenshot_fact:"截图直接事实", video_sequence:"视频时序事实", reference_document:"参考文档事实",
  configuration_table:"配置表事实", planner_decision:"策划确认结论", context_inference:"上下文推断",
  sparse:"简单机制", interaction:"交互机制", algorithm:"算法机制", high:"高", medium:"中", low:"低"
};
const displayKey = (key) => keyLabels[key] || valueLabels[key] || key;
const displayScalar = (value) => {
  if (value === true) return "是";
  if (value === false) return "否";
  return typeof value === "string" && valueLabels[value] ? valueLabels[value] : value;
};
function renderValue(value) {
  if (value === null || value === undefined) return '<p class="empty">无</p>';
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return `<p class="value">${escapeHtml(displayScalar(value))}</p>`;
  if (Array.isArray(value)) {
    if (!value.length) return '<p class="empty">无</p>';
    if (value.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
      return `<div class="record-grid">${value.map((item, index) => `<article class="record"><h3>记录 ${index + 1}</h3>${renderValue(item)}</article>`).join("")}</div>`;
    }
    return `<ul>${value.map((item) => `<li>${typeof item === "object" ? renderValue(item) : escapeHtml(item)}</li>`).join("")}</ul>`;
  }
  return `<dl>${Object.entries(value).map(([key, item]) => `<dt>${escapeHtml(displayKey(key))}</dt><dd>${renderValue(item)}</dd>`).join("")}</dl>`;
}

const style = `
  *{box-sizing:border-box}html,body{margin:0;background:#edf1f6;color:#172033;font-family:"Microsoft YaHei",sans-serif}
  header{padding:20px 34px;background:#14213d;color:#fff;display:flex;align-items:center;gap:18px}header strong{font-size:24px}header span{font-size:20px;font-weight:700}header em{margin-left:auto;font-style:normal;color:#ccd7ec}
  main{width:1480px;max-width:calc(100vw - 48px);margin:24px auto 48px}.summary,.card{background:#fff;border:1px solid #dce3ed;border-radius:12px;padding:22px 26px;margin-bottom:18px;box-shadow:0 5px 18px #1b294014}
  h1{font-size:23px;margin:0 0 14px}h2{font-size:19px;color:#173a6b;margin:0 0 12px;border-bottom:1px solid #e1e7ef;padding-bottom:10px}p{font-size:15px;line-height:1.7;margin:7px 0}.meta{display:grid;grid-template-columns:150px 1fr;gap:8px 16px}.meta b{color:#526176}.hash{font-family:Consolas;overflow-wrap:anywhere;color:#315078}
  .value{white-space:pre-wrap;overflow-wrap:anywhere}.empty{color:#8791a3}ul{margin:4px 0;padding-left:22px}li{font-size:14px;line-height:1.65;margin:4px 0}
  dl{display:grid;grid-template-columns:150px minmax(0,1fr);gap:0;margin:0;border:1px solid #e1e7ef;border-radius:8px;overflow:hidden}dt,dd{margin:0;padding:10px 12px;border-bottom:1px solid #e8edf3;font-size:14px;line-height:1.6}dt{background:#f1f5fa;font-weight:700;color:#40516b}dd{background:#fff;min-width:0}dd>.value{margin:0}dl>*:nth-last-child(-n+2){border-bottom:0}
  .record-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.record{border:1px solid #dfe6ef;border-radius:9px;padding:14px;background:#fbfcfe}.record h3{margin:0 0 10px;color:#315078;font-size:15px}.record dl{grid-template-columns:120px minmax(0,1fr)}
  .card>.value{padding:14px;background:#f7f9fc;border:1px solid #e3e8f0;border-radius:8px}
`;

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:chrome});
  const page = await browser.newPage({viewport:{width:1600,height:1000}});
  const manifestPath = path.join(output,"evidence-manifest.json");
  const previous = selectedCaseId && fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, "utf8")) : {entries:[]};
  const evidence = selectedCaseId ? previous.entries.filter((item) => item.caseId !== selectedCaseId) : [];
  try {
    for (const item of source.payloads) {
      if (selectedCaseId && item.caseId !== selectedCaseId) continue;
      const cards = item.sections.map((section) => `<section class="card"><h2>${escapeHtml(section.label)}</h2>${renderValue(section.value)}</section>`).join("");
      await page.setContent(`<style>${style}</style><header><strong>${escapeHtml(item.caseId)}</strong><span>${escapeHtml(item.title)}</span><em>阶段 3 · 独立真实证据</em></header><main><section class="summary"><h1>本用例输入与身份</h1><div class="meta"><b>输入摘要</b><p>${escapeHtml(item.inputSummary)}</p><b>输入哈希</b><p class="hash">${item.inputHash}</p><b>正文哈希</b><p class="hash">${item.bodyHash}</p></div></section>${cards}</main>`, {waitUntil:"load"});
      const filename = `${item.caseId.toLowerCase()}-${item.title.replace(/[\\/:*?"<>|\s]+/g,"-")}-full.png`;
      const target = path.join(output, filename);
      await page.screenshot({path:target, fullPage:true});
      evidence.push({caseId:item.caseId, visibleCaseId:item.caseId, inputHash:item.inputHash, bodyHash:item.bodyHash, screenshot:path.resolve(target), screenshotHash:hash(fs.readFileSync(target)), humanInspected:false});
    }
  } finally { await browser.close(); }
  evidence.sort((a,b) => a.caseId.localeCompare(b.caseId));
  fs.writeFileSync(manifestPath, JSON.stringify({officialJobBefore:source.officialJobBefore, entries:evidence}, null, 2));
  console.log(JSON.stringify({count:evidence.length, uniqueScreenshots:new Set(evidence.map((item)=>item.screenshotHash)).size}, null, 2));
})().catch((error)=>{console.error(error);process.exitCode=1;});
