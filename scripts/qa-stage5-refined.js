const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE5_ORIGIN || "http://127.0.0.1:8009";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-refined-browser");

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  try {
    await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle" });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 20000 });
    await page.locator('[data-workbench-step="p7"]').evaluate(node => node.click());
    await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
    const result = await page.evaluate(async () => {
      const revision = state.gameplayReviewWorkspace.model.revision;
      const response = await fetch(`/api/jobs/${state.gameplayReviewClient.jobId}/gameplay-review-model/final-preview`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision: revision }),
      });
      if (!response.ok) throw new Error(`final preview ${response.status}: ${await response.text()}`);
      const preview = await response.json();
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview, previewStatus: "ready", previewError: "" };
      renderCombinedFinalPreview();
      const snapshot = preview.completionSnapshot;
      const text = document.querySelector(".final-document-content")?.textContent || "";
      const order = preview.documentOrder.map(item => item.key || item.title);
      return {
        snapshot, order, exportButtons: document.querySelectorAll(".final-document-feishu-action").length,
        planningGameplayTrace: state.gameplayReviewWorkspace.model.planningGameplayTrace || [],
        planning: !!document.querySelector(".final-document-planning-board svg"),
        competitor: !!document.querySelector(".final-document-competitor-board svg"),
        competitorCards: document.querySelectorAll('.final-document-competitor-board [data-node-kind="competitor-reference"]').length,
        fieldMappings: document.querySelectorAll(".final-document-parameter-naming li").length,
        noInternalFrameIds: !/F\d{4}/.test(text),
        hasRequiredCopy: ["参数命名", "武器名称：weaponName（建议）", "首领生命值归零后结束战斗并进入关卡结算", "刷新不等同于确认强化"].every(value => text.includes(value)),
        noMechanicalFieldDump: !text.includes("建议命名，待程序或配置表确认"),
      };
    });
    if (!result.snapshot.ready || result.snapshot.percent !== 100) throw new Error("real completion snapshot is not ready/100%");
    if (result.exportButtons !== 1) throw new Error(`expected one Feishu action, got ${result.exportButtons}`);
    if (!result.planning || !result.competitor || result.competitorCards < 15) throw new Error("planning/competitor evidence is incomplete");
    if (result.fieldMappings < 1 || !result.hasRequiredCopy) throw new Error("gameplay depth or nearby parameter mappings are missing");
    if (!result.noMechanicalFieldDump) throw new Error("parameter naming still serializes review metadata into prose");
    if (!result.noInternalFrameIds) throw new Error("final gameplay copy leaks internal Fxxxx frame identifiers");
    if (result.planningGameplayTrace.filter(item => item.status === "delivered").length < 6 || result.planningGameplayTrace.some(item => item.status === "missing_target")) throw new Error("planning-board gameplay insights are not fully delivered");
    if (result.order[2] !== "planning" || result.order[3] !== "competitor") throw new Error(`wrong document order: ${result.order.join(" > ")}`);

    await page.evaluate(() => {
      const banner = document.createElement("div");
      banner.id = "stage5-evidence-banner";
      banner.textContent = "阶段5真实任务｜完成度、策划草图、竞品参考、玩法正文与参数命名";
      Object.assign(banner.style, { position: "fixed", inset: "0 0 auto", zIndex: 100000, padding: "12px 20px", background: "#17233f", color: "white", font: "600 16px Microsoft YaHei" });
      document.body.append(banner);
    });
    await page.screenshot({ path: path.join(output, "s5-real-status.png") });

    async function proof(selector, title, filename) {
      await page.evaluate(({ selector, title }) => {
        document.querySelector("#stage5-proof")?.remove();
        const source = document.querySelector(selector);
        if (!source) throw new Error(`proof source missing: ${selector}`);
        const wrapper = document.createElement("section");
        wrapper.id = "stage5-proof";
        wrapper.innerHTML = `<h1>${title}</h1>`;
        wrapper.append(source.cloneNode(true));
        Object.assign(wrapper.style, { width: "1700px", padding: "30px", background: "#eef2f7", boxSizing: "border-box", color: "#17233f" });
        wrapper.querySelectorAll("svg").forEach(svg => { svg.style.cssText = "display:block;width:100%;height:auto;max-width:none"; });
        wrapper.querySelectorAll(".final-document-planning-board-canvas").forEach(node => { node.style.cssText = "overflow:visible;width:100%;height:auto;max-height:none"; });
        document.body.append(wrapper);
      }, { selector, title });
      await page.locator("#stage5-proof").screenshot({ path: path.join(output, filename), animations: "disabled" });
    }

    await proof(".final-document-planning-board", "S5｜策划草图：保留截图解读并增加页面关系箭头", "s5-planning-board-complete.png");
    await proof(".final-document-competitor-board", "S5｜竞品参考：原图、可见信息、采用点与推导边界", "s5-competitor-board-complete.png");
    await proof(".final-document-content", "S5｜完整玩法正文：复杂章节分点、就近参数命名、配置表", "s5-gameplay-content-complete.png");
    await page.evaluate(() => {
      document.querySelector("#stage5-proof")?.remove();
      const chapters = [...document.querySelectorAll(".final-document-chapter")];
      const selected = chapters.filter(node => ["战斗移动与生存", "武器攻击", "关卡战斗流程"].includes(node.querySelector("h3")?.textContent?.trim()));
      const wrapper = document.createElement("section"); wrapper.id = "stage5-proof";
      wrapper.innerHTML = "<h1>S5｜核心战斗：按真实执行顺序分点</h1>";
      selected.forEach(node => wrapper.append(node.cloneNode(true)));
      Object.assign(wrapper.style, { width: "1200px", padding: "36px 60px", background: "white", boxSizing: "border-box", color: "#17233f", font: "16px/1.8 Microsoft YaHei" });
      document.body.append(wrapper);
    });
    await page.locator("#stage5-proof").screenshot({ path: path.join(output, "s5-core-combat-readable.png") });
    await page.evaluate(() => {
      document.querySelector("#stage5-proof")?.remove();
      const chapters = [...document.querySelectorAll(".final-document-chapter")];
      const selected = chapters.filter(node => node.querySelector(".final-document-parameter-naming") || node.querySelector(".final-document-table"));
      const wrapper = document.createElement("section"); wrapper.id = "stage5-proof";
      wrapper.innerHTML = "<h1>S5｜参数载体：就近命名映射与独立配置表</h1>";
      selected.forEach(node => wrapper.append(node.cloneNode(true)));
      Object.assign(wrapper.style, { width: "1400px", padding: "36px 60px", background: "white", boxSizing: "border-box", color: "#17233f", font: "15px/1.7 Microsoft YaHei" });
      document.body.append(wrapper);
    });
    await page.locator("#stage5-proof").screenshot({ path: path.join(output, "s5-parameter-carriers-readable.png") });
    await page.evaluate((trace) => {
      document.querySelector("#stage5-proof")?.remove();
      const wrapper = document.createElement("section"); wrapper.id = "stage5-proof";
      wrapper.innerHTML = `<h1>S5｜策划草图解读同步到玩法正文</h1><p>逐条核对草图来源、玩法章节与正文承载位置；纯页面布局不重复写入正文。</p><table><thead><tr><th>策划草图环节</th><th>解读内容</th><th>玩法正文落点</th><th>状态</th></tr></thead><tbody>${trace.map(item => `<tr><td>${item.stageName || item.stageId}</td><td>${item.text}</td><td>${item.status === "board_only" ? "仅保留策划草图" : `${item.targetChapterId} / ${item.carrier}`}</td><td>${item.status === "delivered" ? "已进入正文" : item.status === "board_only" ? "无需迁移" : "未完成"}</td></tr>`).join("")}</tbody></table><p><b>结果：</b>${trace.filter(item => item.status === "delivered").length} 条已进入玩法正文；${trace.filter(item => item.status === "board_only").length} 条仅属于画板；${trace.filter(item => !["delivered", "board_only"].includes(item.status)).length} 条遗漏。</p>`;
      Object.assign(wrapper.style, { width: "1500px", padding: "40px 60px", background: "white", boxSizing: "border-box", color: "#17233f", font: "16px/1.65 Microsoft YaHei" });
      wrapper.querySelector("table").style.cssText = "width:100%;border-collapse:collapse;margin-top:24px";
      wrapper.querySelectorAll("th,td").forEach(node => node.style.cssText = "border:1px solid #d8deea;padding:12px 14px;text-align:left;vertical-align:top");
      wrapper.querySelectorAll("th").forEach(node => node.style.background = "#eef2f7");
      document.body.append(wrapper);
    }, result.planningGameplayTrace);
    await page.locator("#stage5-proof").screenshot({ path: path.join(output, "s5-planning-insights-to-gameplay.png") });

    const payload = { passed: errors.length === 0, jobId, origin, ...result, errors };
    fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(payload, null, 2));
    if (!payload.passed) throw new Error(errors.join("\n"));
    console.log(JSON.stringify(payload, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
