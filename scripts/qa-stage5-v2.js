const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE5_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage5-v2-browser-acceptance");

function assert(value, message) { if (!value) throw new Error(message); }

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
  const browserErrors = [];
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => { if (message.type() === "error") browserErrors.push(message.text()); });

  async function proof(title, filename, build) {
    await page.evaluate(({ title, build }) => {
      document.querySelector("#stage5-v2-proof")?.remove();
      const root = document.createElement("div");
      root.id = "stage5-v2-proof";
      root.innerHTML = `<h1>${title}</h1><div class="proof-body"></div>`;
      Object.assign(root.style, { position: "absolute", zIndex: "999999", left: "0", top: "0", width: "1660px", height: "auto", minHeight: "0", maxHeight: "none", overflow: "visible", padding: "36px 48px", boxSizing: "border-box", background: "#f3f6fb", color: "#17233f", font: "15px/1.65 Microsoft YaHei" });
      const body = root.querySelector(".proof-body");
      const data = window.__stage5V2;
      const escape = value => String(value ?? "").replace(/[&<>\"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[ch]));
      if (build === "coverage") {
        const covered = data.model.contentCoverage.items.filter(x => x.status === "covered").length;
        const decisions = data.model.contentCoverage.items.filter(x => x.status === "decision_required").length;
        body.innerHTML = `<p><b>正式任务：</b>${data.model.jobId}　<b>版本：</b>${data.model.revision}　<b>覆盖：</b>${covered}　<b>需决策：</b>${decisions}　<b>遗漏：</b>0</p><table><thead><tr><th>内容</th><th>证据</th><th>承载位置</th><th>状态</th></tr></thead><tbody>${data.model.contentCoverage.items.map(x => `<tr><td>${escape(x.label)}</td><td>${escape(x.sourceIds.join("、"))}</td><td>${escape(x.carrierIds.join("、"))}</td><td>${x.status === "covered" ? "已覆盖" : "需要策划决定"}</td></tr>`).join("")}</tbody></table>`;
      } else if (build === "chapters") {
        const wanted = ["战场推进与载具生存", "武器槽位与自动攻击", "局内升级与三选一强化", "终极词条与攻击形态变化", "关卡阶段与首领战"];
        document.querySelectorAll(".final-document-chapter").forEach(node => { if (wanted.includes(node.querySelector("h3")?.textContent.trim())) body.append(node.cloneNode(true)); });
      } else if (build === "attributes") {
        const wanted = new Set(["载具等级", "载具栏位与特权", "武器基础属性", "武器解锁与养成", "武器词条", "怪物战斗属性", "关卡波次与刷怪配置结构"]);
        document.querySelectorAll(".final-document-chapter").forEach(chapter => {
          const matched = [...chapter.querySelectorAll(".final-document-table-title")].filter(title => wanted.has(title.textContent.trim()));
          if (!matched.length) return;
          const clone = chapter.cloneNode(true);
          clone.querySelectorAll(".final-document-inline-figure,.final-document-gameplay-diagram,.final-document-paragraph,.final-document-list").forEach(node => node.remove());
          body.append(clone);
        });
      } else if (build === "diagrams") {
        const seen = new Set();
        document.querySelectorAll(".final-document-gameplay-diagram").forEach(node => {
          const chapter = node.closest(".final-document-chapter");
          if (chapter && !seen.has(chapter.id)) { seen.add(chapter.id); body.append(chapter.cloneNode(true)); }
        });
      } else if (build === "boards") {
        [".final-document-planning-board", ".final-document-competitor-board"].forEach(selector => { const node = document.querySelector(selector); if (node) body.append(node.cloneNode(true)); });
      } else if (build === "planning-native") {
        const node = document.querySelector(".final-document-planning-board");
        if (node) body.append(node.cloneNode(true));
        root.style.width = "8640px";
      } else if (build === "alignment") {
        const rows = data.preview.sampleAlignment.chapters.flatMap(c => [
          ...(c.granularity || []).map(x => [c.title || c.chapterId, x.label || x.axis, x.status === "satisfied" ? "通过" : x.status === "not_applicable" ? "有依据地不适用" : "未通过", `${x.sampleMethod || ""} ${x.basis || ""}`]),
          [c.title || c.chapterId, "语言组织与表述逻辑", c.language?.status === "satisfied" ? "通过" : "未通过", c.language?.sampleMethod || "按条件—动作—结果—边界组织并跨载体去重"],
        ]);
        body.innerHTML = `<p><b>颗粒度审计：</b>${data.preview.granularityAudit.passed ? "通过" : "未通过"}　<b>语言审计：</b>${data.preview.languageAudit.passed ? "通过" : "未通过"}　<b>交付一致性：</b>${data.preview.deliveryAlignment.passed ? "通过" : "未通过"}</p><table><thead><tr><th>章节</th><th>核对项</th><th>结论</th><th>依据/方法</th></tr></thead><tbody>${rows.map(r => `<tr>${r.map(x => `<td>${escape(x)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
      } else if (build === "decisions") {
        const cards = data.model.chapters.flatMap(c => (c.decisionCards || []).map(card => ({ chapter: c.scope, ...card })));
        body.innerHTML = `<p><b>完成度：</b>${data.preview.completionSnapshot.percent}%　<b>导出：</b>阻止　<b>原因：</b>5 项素材不足以唯一判断的问题尚未选择。</p>${cards.map(card => `<section><h2>${escape(card.chapter)}｜${escape(card.question)}</h2><ul>${card.options.map(o => `<li>${o.recommended ? "推荐：" : "选项："}${escape(o.label)} — ${escape(o.reason)}</li>`).join("")}<li>自己填写</li><li>暂时跳过</li></ul><p><b>应用后更新：</b>${escape(card.impacts.join("、"))}</p></section>`).join("")}`;
      } else if (build === "trace") {
        const trace = data.model.planningGameplayTrace || [];
        body.innerHTML = `<p><b>草图解读：</b>${trace.length} 项　<b>进入正文：</b>${trace.filter(x => x.status === "delivered").length}　<b>仅留画板：</b>${trace.filter(x => x.status === "board_only").length}　<b>遗漏：</b>0</p><table><thead><tr><th>来源环节</th><th>解读内容</th><th>目标章节/载体</th><th>同步状态</th></tr></thead><tbody>${trace.map(x => `<tr><td>${escape(x.stageName)}</td><td>${escape(x.text)}</td><td>${escape(x.targetChapterId || "策划草图")} / ${escape(x.carrier)}</td><td>${x.status === "delivered" ? "已进入正文" : "仅保留策划草图"}</td></tr>`).join("")}</tbody></table>`;
      } else if (build === "p7") {
        const headings = [...document.querySelectorAll(".final-document-content h1")].map(node => node.textContent.trim());
        const score = document.querySelector(".final-document-score")?.outerHTML || "";
        const checks = document.querySelector(".final-document-checks")?.outerHTML || "";
        const footer = document.querySelector(".final-document-footer")?.outerHTML || "";
        body.innerHTML = `<section><h2>当前发布状态</h2>${score}${checks}${footer}</section><section><h2>最终文档顺序</h2><ol>${headings.map(x => `<li>${escape(x)}</li>`).join("")}</ol></section>`;
      }
      root.querySelectorAll("table").forEach(t => t.style.cssText = "width:100%;border-collapse:collapse;background:white");
      root.querySelectorAll("th,td").forEach(x => x.style.cssText = "border:1px solid #d5deeb;padding:9px 11px;text-align:left;vertical-align:top;overflow-wrap:anywhere");
      root.querySelectorAll("th").forEach(x => x.style.background = "#e7eef9");
      root.querySelectorAll("svg").forEach(svg => svg.style.cssText = "display:block;width:100%;height:auto;min-width:0");
      if (build === "planning-native") root.querySelectorAll("svg").forEach(svg => {
        const width = Number(svg.getAttribute("width") || String(svg.getAttribute("viewBox") || "").split(/\s+/)[2] || 0);
        svg.style.cssText = `display:block;width:${width}px;height:auto;max-width:none;min-width:0`;
      });
      root.querySelectorAll("section,.final-document-chapter").forEach(x => { x.style.breakInside = "avoid"; x.style.background = "white"; x.style.margin = "16px 0"; x.style.padding = "20px"; });
      document.body.append(root);
    }, { title, build });
    await page.locator("#stage5-v2-proof").screenshot({ path: path.join(output, filename), animations: "disabled" });
  }

  try {
    await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle", timeout: 30000 });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 20000 });
    await page.locator('[data-workbench-step="p7"]').evaluate(node => node.click());
    await page.locator(".final-document-shell").waitFor({ state: "visible", timeout: 30000 });
    const result = await page.evaluate(async () => {
      const model = state.gameplayReviewWorkspace.model;
      const response = await fetch(`/api/jobs/${state.gameplayReviewClient.jobId}/gameplay-review-model/final-preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision: model.revision }) });
      if (!response.ok) throw new Error(`final preview ${response.status}: ${await response.text()}`);
      const preview = await response.json();
      state.gameplayReviewWorkspace = { ...state.gameplayReviewWorkspace, preview, previewStatus: "ready", previewError: "" };
      renderCombinedFinalPreview();
      window.__stage5V2 = { model, preview };
      const text = document.querySelector(".final-document-content")?.textContent || "";
      return {
        revision: model.revision,
        chapterTitles: model.chapters.map(c => c.scope), coverage: model.contentCoverage.items,
        diagramTitles: model.diagrams.map(d => d.title), renderedDiagrams: document.querySelectorAll(".final-document-gameplay-diagram").length,
        pendingCards: model.chapters.flatMap(c => c.decisionCards || []).filter(c => c.status === "pending").length,
        percent: preview.completionSnapshot.percent, ready: preview.completionSnapshot.ready,
        audit: preview.granularityAudit.passed, language: preview.languageAudit.passed, delivery: preview.deliveryAlignment.passed,
        planning: !!document.querySelector(".final-document-planning-board svg"), competitor: !!document.querySelector(".final-document-competitor-board svg"),
        competitorCards: document.querySelectorAll('.final-document-competitor-board [data-node-kind="competitor-reference"]').length,
        inlineFigures: document.querySelectorAll(".final-document-inline-figure").length,
        planningBoardWidth: Number(document.querySelector(".final-document-planning-board svg")?.getAttribute("width") || 0),
        interactionRevision: preview.interactionRevision,
        hasChineseDiagramTitles: ["关卡完整主循环", "三选一玩家操作与系统处理", "终极词条进入、候选与生效状态", "武器抽取可见操作流程", "首领阶段切换与胜负分流", "武器命中、反馈与伤害归集"].every(x => text.includes(x)),
        leaksEnglishType: /state_flow|effect_chain/.test(text), internalFramesInCopy: /F\d{4}/.test(text),
        fixedHeadingLeak: [...document.querySelectorAll(".final-document-chapter h4")].some(node => node.textContent.trim() === "规则与边界"),
        auditCopyLeak: /仅能证明|不能冒充|当前素材|素材不足|不能据图|不能据此|无法由截图|依据不足|缺少当前资料|不能伪造/.test([...document.querySelectorAll(".final-document-chapter")].map(node => node.textContent).join("\n")),
        attributeHeadings: [...document.querySelectorAll(".final-document-table-title")].map(node => node.textContent.trim()),
        vehicleAttributesVisible: ["等级", "升级道具ID", "消耗数量", "攻击力", "生命值", "固定减伤", "默认武器栏", "自选武器栏", "特权礼包ID", "特权技能ID"].every(x => document.querySelector("#final-doc-GCH-001")?.textContent.includes(x)),
        weaponAttributesVisible: ["武器类型", "基础伤害比例", "元素伤害", "触发间隔(s)", "持续时间(s)", "直接目标数", "间接目标数", "间接伤害比例", "冷却(s)", "索敌范围", "伤害范围", "前置词条ID", "最大等级", "权重", "作用技能ID", "效果参数"].every(x => document.querySelector("#final-doc-GCH-003")?.textContent.includes(x)),
        monsterAttributesVisible: ["怪物ID", "类型", "基础生命值", "基础攻击力", "移动速度", "攻击距离", "攻速(ms)", "最终减伤", "元素减伤", "闪避(万分比)", "格挡次数", "免疫效果", "攻击动作ID", "子弹ID"].every(x => document.querySelector("#final-doc-GCH-006")?.textContent.includes(x)),
        genericAuditTableLeak: [...document.querySelectorAll(".final-document-table")].some(table => ["属性", "说明", "类型与单位", "配置或计算", "限制条件"].every(x => table.textContent.includes(x))),
        vehicleRulesExpanded: ["初始等级为 1 级", "1 个默认武器栏", "4 个自选武器栏", "特权载具"].every(x => document.querySelector("#final-doc-GCH-001")?.textContent.includes(x)),
        weaponRulesExpanded: ["关卡外解锁", "不同武器独立养成", "前置词条", "达到最大等级后移出随机池"].every(x => document.querySelector("#final-doc-GCH-003")?.textContent.includes(x)),
        monsterRulesExpanded: ["每个波次开始时刷新怪物", "x、y 偏移", "进入攻击距离后停止前进", "优先判定闪避"].every(x => document.querySelector("#final-doc-GCH-006")?.textContent.includes(x)),
        genericBoundaryHeadingLeak: [...document.querySelectorAll(".final-document-content h1,.final-document-content h2,.final-document-content h3,.final-document-content h4")].some(node => /^(规则与边界|异常与边界|关键规则|特殊情况)$/.test(node.textContent.trim())),
        waveTableVisible: document.querySelector("#final-doc-GCH-006")?.textContent.includes("关卡波次与刷怪配置结构") && document.querySelector("#final-doc-GCH-006")?.textContent.includes("刷怪点类型"),
        planningTraceComplete: (model.planningGameplayTrace || []).every(item => item.status === "board_only" || (item.status === "delivered" && document.querySelector(`#final-doc-${item.targetChapterId}`)?.textContent.includes(item.text))),
        planningTraceCount: (model.planningGameplayTrace || []).length,
      };
    });

    fs.writeFileSync(path.join(output, "debug-result.json"), JSON.stringify(result, null, 2));
    assert(result.revision >= 158, `expected rebuilt revision >= 158, got ${result.revision}`);
    assert(result.chapterTitles.length === 7, `expected 7 chapters, got ${result.chapterTitles.length}`);
    assert(result.coverage.length === 67, `expected 67 coverage items, got ${result.coverage.length}`);
    assert(result.coverage.filter(x => x.status === "covered").length === 62, "covered item count mismatch");
    assert(result.coverage.filter(x => x.status === "decision_required").length === 5, "decision item count mismatch");
    assert(result.audit && result.language && result.delivery, "one or more Stage 5 audits failed");
    assert(result.diagramTitles.length === 6 && new Set(result.diagramTitles).size === 6 && result.renderedDiagrams === 6, "six distinct diagrams were not rendered once at their prose anchors");
    assert(result.hasChineseDiagramTitles && !result.leaksEnglishType, "diagram titles are missing or leak internal English types");
    assert(result.planning && result.competitor && result.competitorCards >= 15, "planning/competitor boards are incomplete");
    assert(result.planningBoardWidth >= 8000 && result.interactionRevision === 31, "P3 planning board is not the full current approved board");
    assert(result.inlineFigures >= 8, `expected at least 8 inline rule screenshots, got ${result.inlineFigures}`);
    assert(result.vehicleAttributesVisible && result.weaponAttributesVisible && result.monsterAttributesVisible && result.waveTableVisible, "entity attributes or wave table are not visible in their actual P7 chapters");
    assert(!result.genericAuditTableLeak, "formal output still contains the generic five-column field audit table");
    assert(result.vehicleRulesExpanded && result.weaponRulesExpanded && result.monsterRulesExpanded, "entity behavior, growth, or combat rules remain table-only instead of being expanded in prose");
    assert(!result.genericBoundaryHeadingLeak, "formal output still contains a fixed generic rule/boundary heading");
    assert(result.planningTraceComplete && result.planningTraceCount === 7, "planning-board gameplay insights are not completely synchronized into their target chapters");
    assert(["载具等级", "载具栏位与特权", "武器基础属性", "武器解锁与养成", "武器词条", "怪物战斗属性", "关卡波次与刷怪配置结构"].every(x => result.attributeHeadings.includes(x)), "mechanism-specific configuration tables lack visible business headings");
    assert(!result.fixedHeadingLeak && !result.auditCopyLeak, "formal copy still contains fixed headings or audit language");
    assert(result.pendingCards === 5 && result.percent === 91 && result.ready === false, "decision-card export gate is not truthful");
    assert(!result.internalFramesInCopy, "formal gameplay copy leaks internal frame IDs");

    await proof("S5R-TC1｜全部素材内容覆盖矩阵（67 项）", "s5r-tc01-content-coverage-full.png", "coverage");
    await proof("S5R-TC2｜核心正文的规则深度与自然组织", "s5r-tc02-prose-depth-full.png", "chapters");
    await proof("S5R-TC3｜载具、武器、词条、怪物与刷怪配置分对象列示", "s5r-tc03-entity-attributes-full.png", "attributes");
    await proof("S5R-TC4～TC5｜六张流程图嵌入对应正文语境", "s5r-tc04-05-six-distinct-diagrams-full.png", "diagrams");
    await proof("S5R-TC6｜策划草图与竞品参考双画板", "s5r-tc06-two-boards-full.png", "boards");
    await proof("S5R-TC14｜P3 revision 31 策划草图原始宽度完整证据", "s5r-tc14-planning-board-native-full.png", "planning-native");
    await proof("S5R-TC7｜样例颗粒度、语言与交付同源审计", "s5r-tc07-sample-alignment-full.png", "alignment");
    await proof("S5R-TC8｜真实决策阻塞与影响范围", "s5r-tc08-decision-gate-full.png", "decisions");
    await proof("S5R-TC9｜策划草图解读同步到玩法正文", "s5r-tc09-planning-gameplay-trace-full.png", "trace");
    await page.evaluate(() => document.querySelector("#stage5-v2-proof")?.remove());
    await proof("S5R-TC10｜P7 顺序与完成度（当前因 5 项决策保持 91%）", "s5r-tc10-p7-order-and-status.png", "p7");

    const payload = { passed: browserErrors.length === 0, jobId, origin, ...result, browserErrors };
    fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(payload, null, 2));
    assert(payload.passed, `browser errors: ${browserErrors.join(" | ")}`);
    console.log(JSON.stringify(payload, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
