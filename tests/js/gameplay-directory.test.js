const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const Directory = require("../../js/gameplay-directory.js");

class Node {
  constructor(doc, tag) { this.ownerDocument = doc; this.tag = tag; this.children = []; this.listeners = {}; this.className = ""; this.value = ""; this._text = ""; this.disabled = false; }
  set textContent(value) { this._text = String(value); if (value === "") this.children = []; }
  get textContent() { return this._text + this.children.map(item => item.textContent || "").join(""); }
  setAttribute() {}
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  click() { this.listeners.click?.({ currentTarget: this }); }
  querySelectorAll(tag) { return this.children.flatMap(item => item instanceof Node ? [item, ...item.querySelectorAll(tag)] : []).filter(item => item.tag === tag); }
}
class Document { createElement(tag) { return new Node(this, tag); } }

function render(callbacks = {}) {
  const doc = new Document(); const root = new Node(doc, "div");
  Directory.render({ root, model: { chapters: [{ id: "GCH-001", claims: [{ id: "GCL-001", text: "拖动方块" }, { id: "GCL-002", text: "放入目标位置" }] }], directory: { status: "draft", understanding: { summary: "玩家拖动方块完成拼合。", primaryFamily: "空间拼合", supportingMechanics: [], uncertainties: [] }, entries: [{ id: "GDE-001", chapterId: "GCH-001", title: "拼合规则", summary: "拖动方块进入目标位置", claimIds: ["GCL-001", "GCL-002"], order: 1 }] } }, state: {}, ...callbacks });
  return root;
}

test("directory leads with four-sentence understanding and planner copy", () => {
  const root = render();
  assert.match(root.textContent, /AI玩法理解/);
  assert.match(root.textContent, /玩法目录/);
  assert.match(root.textContent, /这一章主要讲什么/);
  assert.doesNotMatch(root.textContent, /claimId|mechanismType|sourceType|规则来源|关联章节/);
});

test("directory exposes add split and confirmation operations without internal ids", () => {
  const operations = []; let confirmed = false;
  const root = render({ onOperation: value => operations.push(...value), onConfirm: () => { confirmed = true; } });
  const buttons = root.querySelectorAll("button");
  buttons.find(item => item.textContent === "拆成两项").click();
  buttons.find(item => item.textContent === "确认拆分").click();
  buttons.find(item => item.textContent === "+ 添加章节").click();
  buttons.find(item => /确认理解和目录/.test(item.textContent)).click();
  assert.equal(operations[0].type, "split_directory_entry");
  assert.equal(operations[1].type, "add_directory_entry");
  assert.equal(confirmed, true);
  assert.equal(buttons.filter(item => /添加.*章节/.test(item.textContent)).length, 1);
});

test("add system is a real versioned gameplay operation instead of a no-op button", () => {
  const operations = [];
  const root = render({ onOperation: value => operations.push(...value) });
  root.querySelectorAll("button").find(item => item.textContent === "+ 添加系统").click();
  assert.deepEqual(operations.at(-1), { type: "add_gameplay_system", name: "新玩法系统" });
});

test("directory groups detailed chapters under actual gameplay systems", () => {
  const doc = new Document(); const root = new Node(doc, "div");
  Directory.render({ root, model: { chapters: [{ id: "GCH-001", claims: [] }, { id: "GCH-002", claims: [] }], directory: {
    understanding: {}, entries: [
      { id: "GDE-001", chapterId: "GCH-001", sectionTitle: "战斗与关卡", title: "核心战斗", summary: "持续战斗", order: 1 },
      { id: "GDE-002", chapterId: "GCH-002", sectionTitle: "局内成长", title: "强化选择", summary: "选择强化", order: 2 },
    ],
  } }, state: {} });
  assert.match(root.textContent, /战斗与关卡.*局内成长/);
  assert.deepEqual(root.querySelectorAll("textarea").slice(1, 3).map(item => item.value), ["持续战斗", "选择强化"]);
});

test("directory announces saving and saved outcomes instead of static guidance", () => {
  const saving = render({ state: { saveStatus: "saving" } });
  assert.match(saving.textContent, /正在保存/);
  const saved = render({ state: { saveStatus: "saved" } });
  assert.match(saved.textContent, /已保存/);
});

test("planner can edit what a generated gameplay chapter should explain", () => {
  const operations = [];
  const root = render({ onOperation: value => operations.push(...value) });
  const summary = root.querySelectorAll("textarea").find(item => item.value.includes("拖动方块进入目标位置"));
  assert.ok(summary);
  summary.value = "玩家拖动方块完成拼合，落位后立即结算。";
  summary.listeners.change();
  assert.deepEqual(operations[0], {
    type: "update_directory_entry_summary",
    entryId: "GDE-001",
    summary: "玩家拖动方块完成拼合，落位后立即结算。",
  });
});

test("canceling editor drafts does not enqueue a save while explicit save does", () => {
  const operations = [];
  const root = render({ onOperation: value => operations.push(...value) });
  const summary = root.querySelectorAll("textarea").at(-1);
  summary.value = "不应保存";
  root.querySelectorAll("button").find(item => item.textContent === "取消").click();
  assert.equal(operations.length, 0);
  const nextSummary = root.querySelectorAll("textarea").at(-1);
  nextSummary.value = "明确保存";
  root.querySelectorAll("button").find(item => item.textContent === "保存修改").click();
  assert.equal(operations.at(-1).type, "update_directory_entry_summary");
  assert.equal(operations.at(-1).summary, "明确保存");
});

test("P1 uses separate understanding directory and confirmation columns", () => {
  const root = render();
  const classes = root.querySelectorAll("div").map(item => item.className);
  assert.ok(classes.includes("gameplay-directory-layout"));
  assert.ok(classes.includes("gameplay-directory-tree-column"));
  assert.ok(root.querySelectorAll("aside").some(item => item.className === "gameplay-directory-confirm-column"));
});

test("P1 uses a compact directory tree and edits only the selected chapter on the right", () => {
  const root = render();
  assert.equal(root.querySelectorAll("textarea").length, 3);
  assert.ok(root.querySelectorAll("section").some(item => item.className.includes("gameplay-directory-tree-item")));
  assert.ok(root.querySelectorAll("section").some(item => item.className === "gameplay-directory-editor"));
  assert.match(root.textContent, /编辑章节/);
});

test("P1 renders chapter operations only for the selected chapter editor", () => {
  const root = render();
  const sections = root.querySelectorAll("section");
  assert.equal(sections.filter(item => item.className === "gameplay-directory-entry-actions").length, 1);
  assert.equal(root.querySelectorAll("div").filter(item => item.className === "gameplay-directory-actions").length, 0);
});

test("P1 right editor has target typography hierarchy and narrow-column wrapping", () => {
  const css = fs.readFileSync("css/gameplay-review.css", "utf8");
  assert.match(css, /#gameplayDirectoryView\s+\.gameplay-directory-editor>h3\s*\{[^}]*font-size\s*:\s*14px[^}]*font-weight\s*:\s*600/s);
  assert.match(css, /#gameplayDirectoryView\s+\.gameplay-directory-editor>p\s*\{[^}]*font-size\s*:\s*12px[^}]*color\s*:\s*#8a8f99[^}]*overflow-wrap\s*:\s*anywhere/s);
  assert.match(css, /#gameplayDirectoryView\s+\.gameplay-directory-editor\s+label[^}]*font-size\s*:\s*12px[^}]*font-weight\s*:\s*500/s);
  assert.match(css, /#gameplayDirectoryView\s+\.gameplay-directory-editor\s+input[^}]*font\s*:\s*13px\/1\.6\s+inherit[^}]*overflow-wrap\s*:\s*anywhere/s);
  assert.match(css, /\.gameplay-directory-editor-footer\s*\{[^}]*margin-top\s*:\s*auto[^}]*padding\s*:\s*12px 16px/s);
});

test("P1 matches the target three-column planner directory vocabulary", () => {
  const root = render();
  assert.match(root.textContent, /AI玩法理解.*只读/);
  assert.match(root.textContent, /玩法目录.*共 1 章节/);
  assert.match(root.textContent, /添加系统.*添加章节/);
  assert.match(root.textContent, /编辑章节.*章节名称.*章节说明.*所属模块.*操作/);
  assert.match(root.textContent, /取消.*保存修改/);
  assert.doesNotMatch(root.textContent, /目录确认.*检查玩法结构和章节边界/);
});

test("P1 groups chapters into bordered gameplay-system blocks", () => {
  const root = render();
  const classes = root.querySelectorAll("section").map(item => item.className);
  assert.ok(classes.includes("gameplay-directory-group"));
  assert.ok(classes.includes("gameplay-directory-group-body"));
});

test("confirming the directory flushes a summary that is still being edited", () => {
  let pending = null;
  const root = render({ onConfirm: operations => { pending = operations; } });
  const summary = root.querySelectorAll("textarea")[1];
  summary.value = "pending summary";
  summary.listeners.input();
  root.querySelectorAll("button").at(-1).click();
  assert.deepEqual(pending, [{
    type: "update_directory_entry_summary",
    entryId: "GDE-001",
    summary: "pending summary",
  }]);
});

test("P1 keeps its final confirmation action visible so interaction review can unlock", () => {
  const root = render();
  const confirm = root.querySelectorAll("button").find((item) => /确认.*目录.*开始审核/.test(item.textContent));
  assert.ok(confirm);
  assert.equal(confirm.disabled, false);
  const css = fs.readFileSync("css/gameplay-review.css", "utf8");
  assert.doesNotMatch(css, /#gameplayDirectoryView\s+\.gameplay-directory-confirm-column\s*>\s*\.btn\s*\{[^}]*display\s*:\s*none/s);
  assert.doesNotMatch(css, /#gameplayDirectoryView\s+\.gameplay-directory-confirm-column\s*>\s*\.btn\s*\{[^}]*position\s*:\s*sticky/s);
});

test("dynamic directory uses two clear planner confirmation steps", () => {
  const doc = new Document(); const root = new Node(doc, "div");
  const base = {
    chapters: [{ id: "GCH-001", claims: [] }],
    systems: [{ id: "GSY-001", name: "光路编织", subsystems: [{ id: "GSS-001", name: "连接规则", chapterIds: ["GCH-001"] }] }],
    directory: { status: "draft", understanding: {}, entries: [{ id: "GDE-001", chapterId: "GCH-001", title: "光点连线", summary: "连接相邻光点", claimIds: [] }] },
  };

  Directory.render({ root, model: { ...base, reviewState: { structurePhase: "systems" } }, state: {} });
  assert.match(root.textContent, /第一步：确认玩法系统/);
  assert.match(root.textContent, /光路编织/);
  assert.doesNotMatch(root.textContent, /这一章主要讲什么/);
  assert.match(root.querySelectorAll("button").at(-1).textContent, /确认系统划分/);

  Directory.render({ root, model: { ...base, reviewState: { structurePhase: "mechanisms" } }, state: {} });
  assert.match(root.textContent, /第二步：确认具体机制/);
  assert.match(root.textContent, /这一章主要讲什么/);
  assert.match(root.querySelectorAll("button").at(-1).textContent, /确认机制目录/);
});

test("P1 renders unresolved directory decisions and saves the selected result canonically", () => {
  const doc = new Document(); const root = new Node(doc, "div"); const operations = [];
  Directory.render({ root, document: doc, model: {
    chapters: [{ id: "GCH-001", claims: [], decisionCards: [{ id: "GDC-001", question: "这一机制属于哪个系统？", status: "pending", selectionMode: "single", options: [{ id: "combat", label: "战斗系统" }, { id: "growth", label: "成长系统" }], allowCustom: true, impacts: ["玩法目录", "玩法正文"] }] }],
    directory: { understanding: {}, entries: [{ id: "GDE-001", chapterId: "GCH-001", title: "强化选择", summary: "选择强化", claimIds: [] }] },
  }, state: {}, onOperation: batch => operations.push(batch) });
  assert.match(root.textContent, /这一机制属于哪个系统.*战斗系统.*成长系统.*自己填写.*暂时跳过.*应用选择/s);
  const inputs = root.querySelectorAll("input"); inputs.find(input => input.value === "combat").checked = true;
  root.querySelectorAll("button").find(button => button.textContent === "应用选择").click();
  assert.deepEqual(operations[0], [{ type: "resolve_decision_card", chapterId: "GCH-001", cardId: "GDC-001", selectedOptionIds: ["combat"], customValue: "" }]);
});
