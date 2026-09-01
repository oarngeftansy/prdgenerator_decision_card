const test = require("node:test");
const assert = require("node:assert/strict");
const Cards = require("../../js/planner-decision-cards.js");

class Node {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.className = ""; this.textContent = ""; this.value = ""; this.checked = false; this.hidden = false; }
  append(...items) { this.children.push(...items); }
  matches(selector) { return selector.startsWith(".") ? this.className.split(" ").includes(selector.slice(1)) : this.tagName === selector.toUpperCase(); }
  querySelectorAll(selector) { return this.children.flatMap(item => item instanceof Node ? [item, ...item.querySelectorAll(selector)] : []).filter(item => item.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const document = { createElement: tag => new Node(tag) };
const card = (extra = {}) => ({ id: "GDC-001", question: "强化如何触发？", selectionMode: "single", status: "pending", allowCustom: true,
  options: [{ id: "level", label: "升级后自动触发", recommended: true, reason: "相邻画面出现升级界面" }, { id: "manual", label: "玩家手动打开" }],
  evidence: [{ frameId: "F1", label: "升级界面截图" }], impacts: ["玩法正文", "参数表", "最终文档"], ...extra });

test("shared decision card exposes recommendation evidence impacts choices custom entry and skip", () => {
  const root = new Node("div"); const calls = [];
  Cards.render({ root, document, cards: [card()], context: { chapterId: "GCH-001" }, onResolve: value => calls.push(value), onSkip: value => calls.push(value) });
  assert.match(root.textContent + root.querySelector(".planner-decision-card").children.map(item => item.textContent).join(""), /强化如何触发/);
  assert.match(JSON.stringify(root), /AI 推荐|判断依据|保存后会更新|自己填写/);
  const inputs = root.querySelectorAll("input"); inputs[0].checked = true;
  root.querySelector(".planner-decision-apply").onclick();
  assert.deepEqual(calls[0], { chapterId: "GCH-001", cardId: "GDC-001", selectedOptionIds: ["level"], customValue: "" });
  root.querySelector(".planner-decision-skip").onclick();
  assert.deepEqual(calls[1], { chapterId: "GCH-001", cardId: "GDC-001" });
});

test("shared decision cards hide resolved malformed and bare unknown content", () => {
  const root = new Node("div");
  Cards.render({ root, document, cards: [card({ status: "resolved" }), card({ id: "bad", options: [{ id: "a", label: "A" }] })] });
  assert.equal(root.querySelector(".planner-decision-card"), null);
});

test("single-choice card can switch between an option and custom text without getting stuck", () => {
  const root = new Node("div"); const calls = [];
  Cards.render({ root, document, cards: [card()], context: { chapterId: "GCH-001" }, onResolve: value => calls.push(value) });
  const inputs = root.querySelectorAll("input");
  const option = inputs[0];
  const custom = inputs.at(-1);

  option.checked = true;
  option.onclick();
  custom.value = "按关卡配置触发";
  custom.oninput();
  assert.equal(option.checked, false);
  root.querySelector(".planner-decision-apply").onclick();
  assert.deepEqual(calls[0], { chapterId: "GCH-001", cardId: "GDC-001", selectedOptionIds: [], customValue: "按关卡配置触发" });

  custom.value = "旧内容";
  option.checked = true;
  option.onclick();
  assert.equal(custom.value, "");
});
