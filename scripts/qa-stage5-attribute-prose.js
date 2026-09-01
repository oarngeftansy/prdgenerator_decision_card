const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE5_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-v2-browser-acceptance");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1900, height: 1200 }, deviceScaleFactor: 1 });
  try {
    await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle", timeout: 30000 });
    await page.locator('[data-workbench-step="p7"]').evaluate((button) => button.click());
    await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
    const chapter = page.locator("#final-doc-GCH-001");
    await chapter.waitFor({ state: "visible" });
    const result = await chapter.evaluate((node) => {
      const text = node.textContent.replace(/\s+/g, " ");
      const count = (needle) => text.split(needle).length - 1;
      const headings = [...node.querySelectorAll("h3,h4,h5")].map((item) => ({ level: item.tagName, text: item.textContent.trim() }));
      const checks = {
        objectHeading: headings.some((item) => item.level === "H3" && item.text === "载具"),
        damageGroup: headings.some((item) => item.level === "H4" && item.text === "承伤与武器换算"),
        levelSlotGroup: headings.some((item) => item.level === "H4" && item.text === "等级与栏位状态"),
        privilegeGroup: headings.some((item) => item.level === "H4" && item.text === "特权载具"),
        oldHeadingRemoved: !text.includes("推进、升级与载具状态"),
        mapFeedbackOnce: count("左侧小地图显示道路形态和当前推进位置") === 1,
        hitFeedbackOnce: count("敌人命中载具后立即扣除生命值") === 1,
        hudEntryOnce: count("暂停、倍速和伤害统计是战斗 HUD 的独立操作入口") === 1,
        noEvidenceMeta: !text.includes("这些数值只证明"),
        noStageMeta: !text.includes("留待阶段6逐项验证"),
        proseBeforeTable: node.querySelector(".final-document-attribute-section") && (!node.querySelector("table") || (node.querySelector(".final-document-attribute-section").compareDocumentPosition(node.querySelector("table")) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0),
      };
      return { checks, headings, excerpt: text, passed: Object.values(checks).every(Boolean) };
    });
    if (!result.passed) throw new Error(`验收失败：${JSON.stringify(result.checks)}`);
    await page.evaluate(() => {
      const chapter = document.querySelector("#final-doc-GCH-001");
      const proof = document.createElement("div");
      proof.id = "vehicle-attribute-proof";
      const revision = window.state?.gameplayReviewWorkspace?.model?.revision || "current";
      proof.innerHTML = `<h1>载具正文精简与属性层级自检</h1><p class='proof-note'>revision ${revision} · 实际 P7 DOM 内容</p>`;
      Object.assign(proof.style, { display: "block", width: "1500px", height: "auto", minHeight: "0", overflow: "visible", padding: "40px 56px", background: "#fff", color: "#1f2329", boxSizing: "border-box", font: "16px/1.75 Microsoft YaHei" });
      const nodes = [...chapter.children];
      const ruleHeadingIndex = nodes.findIndex((node) => node.tagName === "H4" && node.textContent.trim() === "推进与战斗反馈");
      const tableHeadingIndex = nodes.findIndex((node) => node.tagName === "H4" && node.textContent.includes("载具等级"));
      const start = Math.max(0, ruleHeadingIndex);
      const end = tableHeadingIndex >= 0 ? Math.min(nodes.length, tableHeadingIndex + 2) : nodes.length;
      nodes.slice(start, end).forEach((node) => proof.append(node.cloneNode(true)));
      proof.querySelectorAll("img,svg").forEach((node) => node.remove());
      Object.assign(proof.querySelector("h1").style, { display: "block", width: "100%", fontSize: "30px", margin: "0 0 4px" });
      Object.assign(proof.querySelector(".proof-note").style, { display: "block", width: "100%", color: "#646a73", margin: "0 0 28px" });
      [...proof.children].forEach((node) => {
        if (node.tagName !== "H1" && !node.classList.contains("proof-note")) Object.assign(node.style, { display: "block", width: "100%", maxWidth: "none", height: "auto", boxSizing: "border-box", position: "static", float: "none", gridArea: "auto", columns: "auto" });
      });
      proof.querySelectorAll(".final-document-attribute-section").forEach((node) => Object.assign(node.style, { display: "block", width: "100%", margin: "0" }));
      proof.querySelectorAll("h4").forEach((node) => Object.assign(node.style, { fontSize: "24px", margin: "28px 0 12px", borderBottom: "1px solid #dfe3e8", paddingBottom: "8px" }));
      proof.querySelectorAll("h5").forEach((node) => Object.assign(node.style, { fontSize: "19px", margin: "20px 0 8px" }));
      proof.querySelectorAll("li").forEach((node) => Object.assign(node.style, { margin: "7px 0" }));
      proof.querySelectorAll("table").forEach((node) => Object.assign(node.style, { width: "100%", borderCollapse: "collapse", fontSize: "13px", tableLayout: "fixed" }));
      proof.querySelectorAll("th,td").forEach((node) => Object.assign(node.style, { border: "1px solid #dfe3e8", padding: "8px", overflowWrap: "anywhere", verticalAlign: "top" }));
      proof.querySelectorAll("th").forEach((node) => node.style.background = "#f4f6f8");
      document.body.append(proof);
    });
    const file = path.join(output, "s5r-tc-vehicle-object-attribute-hierarchy-full.png");
    await page.locator("#vehicle-attribute-proof").screenshot({ path: file, animations: "disabled" });
    const revision = await page.evaluate(() => window.state?.gameplayReviewWorkspace?.model?.revision || null);
    const payload = { passed: true, revision, url: page.url(), file, ...result };
    fs.writeFileSync(path.join(output, "s5r-tc-vehicle-object-attribute-hierarchy-result.json"), JSON.stringify(payload, null, 2));
    console.log(JSON.stringify(payload, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
