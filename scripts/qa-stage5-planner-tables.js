const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE5_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-planner-table-acceptance");
const expected = {
  "GCH-001": ["载具等级", "载具栏位与特权"],
  "GCH-003": ["武器基础属性", "武器解锁与养成", "武器词条"],
  "GCH-006": ["怪物战斗属性", "关卡波次与刷怪配置结构"],
};

function assert(value, message) { if (!value) throw new Error(message); }

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  try {
    await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle", timeout: 30000 });
    await page.locator('[data-workbench-step="p7"]').evaluate(node => node.click());
    await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
    const revision = await page.evaluate(() => state.gameplayReviewWorkspace.model.revision);
    const response = await page.evaluate(async revision => {
      const result = await fetch(`/api/jobs/${state.gameplayReviewClient.jobId}/gameplay-review-model/final-preview`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision: revision }),
      });
      if (!result.ok) throw new Error(await result.text());
      const preview = await result.json();
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview, previewStatus: "ready", previewError: "" };
      renderCombinedFinalPreview();
      return { audit: preview.granularityAudit.passed, language: preview.languageAudit.passed, delivery: preview.deliveryAlignment.passed };
    }, revision);
    assert(response.audit && response.language && response.delivery, "P7 audit gate failed");

    const results = {};
    for (const [chapterId, titles] of Object.entries(expected)) {
      const result = await page.evaluate(({ chapterId, titles }) => {
        document.querySelector("#planner-table-proof")?.remove();
        const source = document.querySelector(`#final-doc-${chapterId}`);
        if (!source) throw new Error(`chapter ${chapterId} missing`);
        const proof = document.createElement("main");
        proof.id = "planner-table-proof";
        proof.innerHTML = `<h1>${source.querySelector("h2,h3")?.textContent || chapterId}</h1>`;
        Object.assign(proof.style, { display: "block", position: "absolute", left: "0", top: "0", zIndex: "999999", width: "1720px", maxWidth: "none", height: "auto", padding: "32px 44px", boxSizing: "border-box", background: "#f3f6fb", color: "#17233f", font: "15px/1.65 Microsoft YaHei" });
        for (const title of titles) {
          const heading = [...source.querySelectorAll(".final-document-table-title")].find(node => node.textContent.trim() === title);
          if (!heading) throw new Error(`table ${title} missing`);
          const section = document.createElement("section");
          section.append(heading.cloneNode(true), heading.nextElementSibling.cloneNode(true));
          Object.assign(section.style, { display: "block", width: "100%", boxSizing: "border-box", clear: "both", background: "white", margin: "18px 0", padding: "22px", overflow: "hidden" });
          section.querySelector("table").style.cssText = "width:100%;border-collapse:collapse;table-layout:auto;font-size:14px";
          section.querySelectorAll("th,td").forEach(cell => cell.style.cssText = "border:1px solid #d5deeb;padding:10px 9px;text-align:left;vertical-align:top;white-space:normal;overflow-wrap:anywhere");
          section.querySelectorAll("th").forEach(cell => cell.style.background = "#e7eef9");
          proof.append(section);
        }
        document.body.append(proof);
        const metrics = [...proof.querySelectorAll("table")].map(table => ({
          title: table.previousElementSibling?.textContent.trim(),
          clientWidth: table.clientWidth, scrollWidth: table.scrollWidth,
          right: table.getBoundingClientRect().right, viewportRight: proof.getBoundingClientRect().right,
          columns: [...table.querySelectorAll("thead th")].map(node => node.textContent.trim()),
        }));
        return { titles: [...proof.querySelectorAll(".final-document-table-title")].map(node => node.textContent.trim()), metrics };
      }, { chapterId, titles });
      assert(titles.every(title => result.titles.includes(title)), `${chapterId} title mismatch`);
      assert(result.metrics.every(item => item.scrollWidth <= item.clientWidth + 1 && item.right <= item.viewportRight + 1), `${chapterId} contains clipped or overflowing table`);
      const file = chapterId === "GCH-001" ? "s5t-tc01-vehicle-tables-full.png" : chapterId === "GCH-003" ? "s5t-tc02-weapon-tables-full.png" : "s5t-tc03-monster-wave-tables-full.png";
      await page.locator("#planner-table-proof").screenshot({ path: path.join(output, file), animations: "disabled" });
      results[chapterId] = { ...result, file };
    }
    const allText = await page.locator(".final-document-content").innerText();
    const genericSchema = [
      ["属性", "说明", "类型与单位", "配置或计算", "限制条件"],
      ["字段", "策划含义", "当前值与范围", "类型与单位", "配置来源"],
      ["名称", "填写格式", "单位", "默认值"],
    ].some(schema => schema.every(value => allText.includes(value)));
    assert(!genericSchema, "generic five-column audit table remains visible");
    assert(errors.length === 0, `browser errors: ${errors.join(" | ")}`);
    fs.writeFileSync(path.join(output, "result.json"), JSON.stringify({ passed: true, jobId, revision, audits: response, genericSchema, results, browserErrors: errors }, null, 2));
    console.log(JSON.stringify({ passed: true, revision, audits: response, genericSchema, results, browserErrors: errors }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
