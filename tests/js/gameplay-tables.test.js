const test = require("node:test");
const assert = require("node:assert/strict");
const GameplayTables = require("../../js/gameplay-tables.js");

class FakeNode {
  constructor(tag = "div") { this.tagName = tag.toUpperCase(); this.children = []; this.className = ""; this.listeners = {}; this.attributes = {}; this.textContent = ""; this.hidden = false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = String(value); if (name === "class") this.className = String(value); }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  dispatch(type) { this.listeners[type]?.({ preventDefault() {} }); }
  matches(selector) { return selector.startsWith(".") ? this.className.split(" ").includes(selector.slice(1)) : this.tagName === selector.toUpperCase(); }
  querySelectorAll(selector) { return this.children.flatMap(child => child instanceof FakeNode ? [child, ...child.querySelectorAll(selector)] : []).filter(node => node.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const document = { createElement: tag => new FakeNode(tag) };

test("P6 does not list chapters that have no evidence-backed table", () => {
  const root = new FakeNode();
  GameplayTables.render({ root, model: { chapters: [{ id: "GCH-001", scope: "生命值状态管理" }], tables: [], tableReview: { status: "ready", noTableChapterIds: ["GCH-001"] } }, document });
  assert.ok(root.querySelector(".gameplay-tables-layout"));
  assert.equal(root.querySelector(".gameplay-table-nav-item"), null);
  assert.match(root.querySelector(".gameplay-tables").className, /has-no-artifacts/);
  assert.equal(root.querySelector(".gameplay-table-empty").textContent, "当前素材没有可确认的玩法表格。");
  assert.ok(root.querySelector(".gameplay-table-canvas"));
  assert.ok(root.querySelector(".gameplay-table-decision"));
});

test("P6 navigation contains only chapters backed by an active table", () => {
  const root = new FakeNode();
  GameplayTables.render({ root, model: {
    chapters: [{ id: "GCH-001", scope: "生命值" }, { id: "GCH-002", scope: "伤害计算" }],
    tables: [{ id: "GTB-001", title: "伤害表", chapterIds: ["GCH-002"], columns: ["字段"], rows: [["攻击"]] }],
    tableReview: { status: "ready", noTableChapterIds: ["GCH-001"] },
  }, document });
  assert.equal(root.querySelectorAll(".gameplay-table-nav-item").length, 1);
  assert.equal(root.querySelector(".gameplay-table-nav-item").textContent, "伤害计算");
  assert.equal(root.querySelector(".gameplay-table-empty").hidden, true);
  assert.equal(root.querySelector(".gameplay-table-card").hidden, false);
});

test("P6 converts legacy audit columns into the approved parameter review headers", () => {
  const root = new FakeNode();
  GameplayTables.render({ root, model: {
    chapters: [{ id: "GCH-001", scope: "现有武器数值强化" }],
    tables: [{ id: "GTB-001", kind: "chapter_parameters", title: "强化参数表", chapterIds: ["GCH-001"],
      columns: ["字段", "策划含义", "类型", "单位", "当前值", "当前依据"],
      rows: [["火焰喷射范围", "强化比例", "百分比", "%", "30", "素材明确展示"]] }],
    tableReview: { status: "ready" },
  }, document });
  assert.deepEqual(root.querySelectorAll("th").map((cell) => cell.textContent), ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"]);
  assert.deepEqual(root.querySelectorAll("td").map((cell) => cell.textContent), ["火焰喷射范围", "百分比（%）", "30", "", "待确认", ""]);
  assert.equal(root.querySelector(".gameplay-table-row-confirm").textContent, "确认");
  assert.equal(root.querySelector(".gameplay-table-value-input").value, "30");
});

test("P6 follows the target three-column parameter review structure", () => {
  const root = new FakeNode();
  GameplayTables.render({ root, model: {
    systems: [{ name: "核心战斗系统", subsystems: [{ chapterIds: ["GCH-001"] }] }],
    chapters: [{ id: "GCH-001", scope: "生命值状态管理" }],
    tables: [{ id: "GTB-001", kind: "chapter_parameters", title: "生命值参数", chapterIds: ["GCH-001"], columns: ["字段"], rows: [["基础生命值", "整数", "500", "500", "待确认", "确认"]] }],
    tableReview: { status: "ready" },
  }, document });
  assert.equal(root.querySelector(".gameplay-table-nav-title").textContent, "参数目录");
  assert.equal(root.querySelector(".gameplay-table-nav-group").querySelector("h4").textContent, "核心战斗系统");
  assert.equal(root.querySelector(".gameplay-table-workbar-title").querySelector("strong").textContent, "生命值参数");
  assert.equal(root.querySelector(".gameplay-table-prev"), null);
  assert.equal(root.querySelector(".gameplay-table-next"), null);
  assert.ok(root.querySelector(".gameplay-table-continue"));
  assert.equal(root.querySelector(".gameplay-table-decision").querySelector("h3").textContent, "参数详情");
});

test("P6 typography and cells allow natural wrapping without ellipsis", () => {
  const css = require("node:fs").readFileSync("css/gameplay-tables.css", "utf8");
  assert.match(css, /font-family:\s*"PingFang SC",\s*"Microsoft YaHei"/);
  assert.match(css, /\.gameplay-generated-table td\s*\{[^}]*white-space:\s*normal[^}]*overflow-wrap:\s*anywhere/s);
});

test("P6 selects a row, updates the detail panel and exposes progress actions", () => {
  const root = new FakeNode();
  GameplayTables.render({ root, model: {
    chapters: [{ id: "GCH-001", scope: "生命值状态管理" }],
    tables: [{ id: "GTB-001", title: "生命值参数", chapterIds: ["GCH-001"], columns: ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"],
      rows: [["基础生命值", "整数", "500", "500", "已确认", "确认"], ["恢复量", "小数", "20", "30", "待确认", "确认"]],
      rowDetails: [{ field: "基础生命值", purpose: "确定初始生存能力", source: "载具配置", basis: "参考文档", formula: "" }, { field: "恢复量", purpose: "控制生存节奏", source: "成长配置", basis: "参考文档", formula: "当前生命值加恢复量" }] }], tableReview: { status: "ready" },
  }, document });
  const rows = root.querySelectorAll("tr").slice(1);
  rows[1].dispatch("click");
  assert.match(rows[1].className, /is-selected/);
  assert.equal(root.querySelector(".gameplay-table-detail-name").textContent, "恢复量");
  assert.equal(root.querySelector(".gameplay-table-progress").textContent, "1/2 已确认");
  assert.equal(root.querySelector(".gameplay-table-regenerate").textContent, "AI 重新生成此表");
  assert.equal(root.querySelector(".gameplay-table-approve").textContent, "通过此表");
  assert.equal(root.querySelector(".gameplay-table-fold").textContent, "计算公式　1 个");
});

test("P6 row confirmation persists the edited value and chapter navigation changes the visible group", () => {
  const root = new FakeNode(); const calls = []; const selectedChapters = [];
  GameplayTables.render({ root, model: { chapters: [{ id: "C1", scope: "战斗" }, { id: "C2", scope: "成长" }], tables: [
    { id: "T1", title: "战斗参数", chapterIds: ["C1"], columns: ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"], rows: [["攻击", "整数", "10", "12", "待确认", "确认"]] },
    { id: "T2", title: "成长参数", chapterIds: ["C2"], columns: ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"], rows: [["等级", "整数", "1", "1", "待确认", "确认"]] },
  ], tableReview: { status: "ready" } }, onAction: (...args) => calls.push(args), onSelectChapter: id => selectedChapters.push(id), document });
  root.querySelector(".gameplay-table-row-confirm").dispatch("click");
  assert.deepEqual(calls[0], ["confirm_row", "T1", JSON.stringify({ rowIndex: 0, value: "12" })]);
  root.querySelectorAll(".gameplay-table-nav-item")[1].dispatch("click");
  assert.equal(root.querySelectorAll(".gameplay-table-card")[0].hidden, true);
  assert.equal(root.querySelectorAll(".gameplay-table-card")[1].hidden, false);
  assert.deepEqual(selectedChapters, ["C2"]);
});

test("P6 preserves dynamic planning headers and the last table continues to P7", () => {
  const root = new FakeNode(); let continued = false;
  GameplayTables.render({ root, model: { chapters: [{ id: "C1", scope: "武器配置" }], tables: [{ id: "T1", kind: "weapon_config", status: "reviewed", title: "武器配置表", chapterIds: ["C1"], columns: ["武器名称", "元素", "基础伤害", "攻击间隔"], rows: [["雷暴枪", "雷", "100", "0.8秒"]] }], tableReview: { status: "ready" } }, onContinue: () => { continued = true; }, document });
  assert.deepEqual(root.querySelectorAll("th").map(cell => cell.textContent), ["武器名称", "元素", "基础伤害", "攻击间隔"]);
  const next = root.querySelector(".gameplay-table-continue"); assert.equal(next.textContent, "进入文档预览"); next.dispatch("click"); assert.equal(continued, true);
});

test("P6 cannot show reviewed or continue while parameter rows remain unconfirmed", () => {
  const root = new FakeNode(); let continued = false;
  GameplayTables.render({ root, model: { chapters: [{ id: "C1", scope: "生命值" }], tables: [{ id: "T1", kind: "chapter_parameters", status: "reviewed", title: "生命值参数", chapterIds: ["C1"], columns: ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"], rows: [["生命", "整数", "100", "100", "已确认", "确认"], ["恢复", "整数", "5", "5", "待确认", "确认"]] }], tableReview: { status: "ready" } }, onContinue: () => { continued = true; }, document });
  assert.equal(root.querySelector(".gameplay-table-status").textContent, "待审核");
  assert.equal(root.querySelector(".gameplay-table-approve").disabled, true);
  assert.equal(root.querySelector(".gameplay-table-continue").disabled, true);
  root.querySelector(".gameplay-table-continue").dispatch("click");
  assert.equal(continued, false);
});

test("P6 reports whole-table review progress for business configuration tables", () => {
  const root = new FakeNode();
  GameplayTables.render({ root, model: {
    chapters: [{ id: "C1", scope: "武器" }],
    tables: [
      { id: "T1", kind: "weapon_config", status: "reviewed", title: "武器基础属性", chapterIds: ["C1"], columns: ["属性", "说明"], rows: [["攻击力", "基础伤害换算"]] },
      { id: "T2", kind: "weapon_growth", status: "stale", title: "武器解锁与养成", chapterIds: ["C1"], columns: ["等级", "解锁内容"], rows: [["1", "默认解锁"]] },
    ], tableReview: { status: "ready" },
  }, document });
  assert.deepEqual(root.querySelectorAll(".gameplay-table-progress").map(node => node.textContent), ["整表已通过", "整表待审核"]);
  assert.equal(root.querySelector(".gameplay-table-review-summary").textContent, "1/2 张表已通过");
});

test("P6 only allows entering P7 after every active table is reviewed", () => {
  const root = new FakeNode(); let continued = false;
  GameplayTables.render({ root, model: {
    chapters: [{ id: "C1", scope: "武器" }],
    tables: [
      { id: "T1", kind: "weapon_config", status: "stale", title: "武器基础属性", chapterIds: ["C1"], columns: ["属性"], rows: [["攻击力"]] },
      { id: "T2", kind: "weapon_growth", status: "reviewed", title: "武器养成", chapterIds: ["C1"], columns: ["等级"], rows: [["1"]] },
    ], tableReview: { status: "ready" },
  }, onContinue: () => { continued = true; }, document });
  const next = root.querySelector(".gameplay-table-continue");
  assert.equal(next.textContent, "进入文档预览");
  assert.equal(next.disabled, true);
  next.dispatch("click");
  assert.equal(continued, false);
});

test("P6 restores the selected table's chapter without hiding sibling tables", () => {
  const root = new FakeNode();
  GameplayTables.render({ root, model: {
    chapters: [{ id: "C1", scope: "武器" }],
    tables: [
      { id: "T1", status: "reviewed", title: "武器基础属性", chapterIds: ["C1"], columns: ["属性"], rows: [["攻击力"]] },
      { id: "T2", status: "stale", title: "武器词条", chapterIds: ["C1"], columns: ["词条"], rows: [["暴击"]] },
    ], tableReview: { status: "ready" },
  }, state: { generation: {}, byId: {}, selectedTableId: "T2" }, document });
  const cards = root.querySelectorAll(".gameplay-table-card");
  assert.equal(cards[0].hidden, false);
  assert.equal(cards[1].hidden, false);
  assert.match(cards[1].className, /is-active/);
});

test("P6 records the target table before submitting an approval", () => {
  const root = new FakeNode(); const calls = [];
  GameplayTables.render({ root, model: {
    chapters: [{ id: "C1", scope: "武器" }],
    tables: [{ id: "T2", status: "stale", title: "武器词条", chapterIds: ["C1"], columns: ["词条"], rows: [["暴击"]] }],
    tableReview: { status: "ready" },
  }, onSelect: id => calls.push(["select", id]), onAction: (action, id) => calls.push([action, id]), document });
  root.querySelector(".gameplay-table-approve").dispatch("click");
  assert.deepEqual(calls, [["select", "T2"], ["approve", "T2"]]);
});

test("P6 resolves parameter range decisions before treating them as confirmed values", () => {
  const root = new FakeNode(); const operations = [];
  GameplayTables.render({ root, model: { chapters: [{ id: "GCH-001", scope: "刷新消耗", decisionCards: [{ id: "GDC-001", question: "刷新消耗采用哪种范围？", status: "pending", selectionMode: "single", options: [{ id: "fixed", label: "固定消耗" }, { id: "growth", label: "逐次递增" }], impacts: ["参数表", "玩法正文", "最终文档"] }] }], tables: [], tableReview: { status: "ready" } }, onOperation: batch => operations.push(batch), document });
  assert.ok(root.querySelector(".planner-decision-card"));
  root.querySelectorAll("input").find(input => input.value === "growth").checked = true;
  root.querySelector(".planner-decision-apply").dispatch("click");
  assert.equal(operations[0][0].selectedOptionIds[0], "growth");
});
