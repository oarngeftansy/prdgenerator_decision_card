const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const GameplayDiagrams = require("../../js/gameplay-diagrams.js");
const GameplayReviewClient = require("../../js/gameplay-review-client.js");

class FakeNode {
  constructor(tag = "div") { this.tagName = tag.toUpperCase(); this.children = []; this.attributes = {}; this.listeners = {}; this.textContent = ""; this.value = ""; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = String(value); if (name === "class") this.className = String(value); }
  getAttribute(name) { return this.attributes[name]; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  dispatch(type) { this.listeners[type]?.({ preventDefault() {} }); }
  matches(selector) { return selector.startsWith(".") ? (this.className || "").split(" ").includes(selector.slice(1)) : this.tagName === selector.toUpperCase(); }
  querySelectorAll(selector) { return this.children.flatMap((child) => child instanceof FakeNode ? [child, ...child.querySelectorAll(selector)] : []).filter((node) => node.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const document = { createElement: (tag) => new FakeNode(tag) };
const diagram = (status = "open") => ({ id: "GDI-001", type: "probability", chapterIds: ["GCH-001"], revision: 2, status, freshness: status === "stale" ? "stale" : "current", optional: true, svg: "<svg></svg>", feedback: [] });

test("diagram cards expose one mutually exclusive review action", () => {
  const root = new FakeNode(); const calls = [];
  GameplayDiagrams.render({ root, model: { chapters: [{ id: "GCH-001", scope: "武器抽取" }], diagrams: [diagram()], diagramReview: { status: "ready" } }, onAction: (...args) => calls.push(args), document });
  assert.equal(root.querySelector(".gameplay-diagram-approve"), null);
  assert.equal(root.querySelector(".gameplay-diagram-regenerate"), null);
  assert.equal(root.querySelector(".gameplay-diagram-delete"), null);
  root.querySelectorAll("input")[0].dispatch("change");
  root.querySelector(".gameplay-diagram-apply").dispatch("click");
  assert.deepEqual(calls[0], ["approve", "GDI-001", ""]);
  assert.equal(root.querySelectorAll(".gameplay-diagram-feedback").length, 1);
});

test("entry automatically generates without chapter type selectors or on-demand button", () => {
  const root = new FakeNode(); const calls = [];
  GameplayDiagrams.render({ root, model: { chapters: [{ id: "GCH-001", confirmation: { confirmed: true } }], diagrams: [] }, onGenerate: (...args) => calls.push(args), document });
  assert.equal(root.querySelector(".gameplay-diagram-chapter"), null);
  assert.equal(root.querySelector(".gameplay-diagram-type"), null);
  assert.equal(root.querySelector(".gameplay-diagram-generate"), null);
  assert.deepEqual(calls, [[]]);
});

test("no helpful diagram is shown as one compact project-level state", () => {
  const root = new FakeNode(); let continued = false;
  GameplayDiagrams.render({ root, model: { diagrams: [], diagramReview: { status: "ready", noDiagramChapterIds: ["GCH-001"] } }, onContinue: () => { continued = true; }, document });
  assert.equal(root.querySelector(".gameplay-diagram-empty-status").textContent, "当前素材无需额外图解");
  const action = root.querySelector(".gameplay-diagram-empty-confirm"); assert.equal(action.textContent, "确认无图解并进入参数审核"); action.dispatch("click"); assert.equal(continued, true);
  const css = require("node:fs").readFileSync("css/gameplay-diagrams.css", "utf8");
  assert.match(css, /^\.gameplay-diagram-empty\s*\{[^}]*min-height:\s*180px/ms);
});

test("P5 does not list chapters that have no useful diagram", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: { chapters: [{ id: "GCH-001", scope: "载具移动机制" }], diagrams: [], diagramReview: { status: "ready", noDiagramChapterIds: ["GCH-001"] } }, document });
  assert.ok(root.querySelector(".gameplay-diagrams-layout"));
  assert.equal(root.querySelector(".gameplay-diagram-nav-item"), null);
  assert.match(root.querySelector(".gameplay-diagrams").className, /has-no-artifacts/);
  assert.equal(root.querySelector(".gameplay-diagram-empty-status").textContent, "当前素材无需额外图解");
  assert.ok(root.querySelector(".gameplay-diagram-canvas"));
  assert.ok(root.querySelector(".gameplay-diagram-decision"));
});

test("P5 navigation contains only chapters backed by an active diagram", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: {
    chapters: [{ id: "GCH-001", scope: "载具移动" }, { id: "GCH-002", scope: "伤害计算" }],
    diagrams: [{ ...diagram(), chapterIds: ["GCH-002"] }],
    diagramReview: { status: "ready", noDiagramChapterIds: ["GCH-001"] },
  }, document });
  assert.equal(root.querySelectorAll(".gameplay-diagram-nav-item").length, 1);
  assert.equal(root.querySelector(".gameplay-diagram-nav-item").textContent, "伤害计算");
  assert.equal(root.querySelector(".gameplay-diagram-empty").hidden, true);
  assert.equal(root.querySelector(".gameplay-diagram-card").hidden, false);
});

test("P5 chapter navigation distinguishes pending stale and reviewed diagrams", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: {
    chapters: [
      { id: "GCH-001", scope: "待审核章节" },
      { id: "GCH-002", scope: "需更新章节" },
      { id: "GCH-003", scope: "已通过章节" },
    ],
    diagrams: [
      { ...diagram("open"), id: "GDI-001", chapterIds: ["GCH-001"] },
      { ...diagram("stale"), id: "GDI-002", chapterIds: ["GCH-002"] },
      { ...diagram("reviewed"), id: "GDI-003", chapterIds: ["GCH-003"] },
    ],
    diagramReview: { status: "ready" },
  }, document });
  const items = root.querySelectorAll(".gameplay-diagram-nav-item");
  assert.deepEqual(items.map(item => item.getAttribute("data-status")), ["open", "stale", "reviewed"]);
  assert.deepEqual(items.map(item => item.getAttribute("data-status-label")), ["待审核", "需更新", "已通过"]);
  assert.deepEqual(root.querySelectorAll(".gameplay-diagram-card").map(item => item.getAttribute("data-diagram-id")), ["GDI-001", "GDI-002", "GDI-003"]);
});

test("selecting a chapter switches the right review panel to that chapter's visible diagram", () => {
  const root = new FakeNode(); const calls = []; const selections = [];
  GameplayDiagrams.render({ root, model: {
    chapters: [{ id: "GCH-001", scope: "关卡循环" }, { id: "GCH-002", scope: "三选一" }],
    diagrams: [
      { ...diagram("open"), id: "GDI-101", chapterIds: ["GCH-001"] },
      { ...diagram("open"), id: "GDI-102", chapterIds: ["GCH-002"] },
    ],
    diagramReview: { status: "ready" },
  }, onAction: (...args) => calls.push(args), onSelectChapter: (id) => selections.push(id), document });

  root.querySelectorAll(".gameplay-diagram-nav-item")[1].dispatch("click");
  root.querySelector(".gameplay-diagram-decision").querySelectorAll("input")[0].dispatch("change");
  root.querySelector(".gameplay-diagram-decision").querySelector(".gameplay-diagram-apply").dispatch("click");

  assert.deepEqual(calls, [["approve", "GDI-102", ""]]);
  assert.deepEqual(selections, ["GCH-002"]);
});

test("P5 restores the persisted chapter instead of resetting to the first item", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: {
    chapters: [{ id: "GCH-001", scope: "关卡循环" }, { id: "GCH-002", scope: "三选一" }],
    diagrams: [
      { ...diagram("open"), id: "GDI-101", chapterIds: ["GCH-001"] },
      { ...diagram("open"), id: "GDI-102", chapterIds: ["GCH-002"] },
    ],
    diagramReview: { status: "ready" },
  }, state: { generation: {}, byId: {}, selectedChapterId: "GCH-002" }, document });

  const items = root.querySelectorAll(".gameplay-diagram-nav-item");
  assert.equal(items[0].getAttribute("aria-current"), "false");
  assert.equal(items[1].getAttribute("aria-current"), "true");
  assert.equal(root.querySelector(".gameplay-diagram-workbar-title").textContent, "图解审核 / 三选一");
});

test("P5 exposes the target review workbar, evidence summary and decision controls", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: {
    chapters: [{ id: "GCH-001", scope: "三选一强化池" }],
    diagrams: [{ ...diagram(), chapterIds: ["GCH-001"] }],
    diagramReview: { status: "ready" },
  }, document });
  assert.equal(root.querySelector(".gameplay-diagram-nav-title").textContent, "关联章节");
  assert.equal(root.querySelector(".gameplay-diagram-workbar-title").textContent, "图解审核 / 三选一强化池");
  assert.match(root.querySelector(".gameplay-diagram-summary").textContent, /1 张图解/);
  assert.equal(root.querySelector(".gameplay-diagram-decision").querySelector("h3").textContent, "图解审核");
  assert.equal(root.querySelector(".gameplay-diagram-apply").textContent, "应用审核结果");
  assert.deepEqual(root.querySelectorAll(".gameplay-diagram-review-choice-label").map((item) => item.textContent), ["通过", "需要修改", "删除"]);
});

test("P5 distinguishes linked chapter count from unique diagram totals", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: {
    chapters: [
      { id: "GCH-001", scope: "战斗推进" },
      { id: "GCH-002", scope: "载具生存" },
    ],
    diagrams: [{ ...diagram("reviewed"), chapterIds: ["GCH-001", "GCH-002"] }],
    diagramReview: { status: "ready" },
  }, document });

  assert.equal(root.querySelector(".gameplay-diagram-nav-title").textContent, "关联章节");
  assert.equal(root.querySelector(".gameplay-diagram-count").textContent, "2");
  assert.match(root.querySelector(".gameplay-diagram-summary").textContent, /已生成 1 张图解/);
});

test("P5 does not double-count diagrams awaiting reconfirmation as pending", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: {
    interactionRevision: 3,
    chapters: [{ id: "GCH-001", scope: "关卡循环" }],
    diagrams: [{ ...diagram("reviewed"), interactionRevision: 2 }],
    diagramReview: { status: "ready" },
  }, document });

  const summary = root.querySelector(".gameplay-diagram-summary").textContent;
  assert.match(summary, /0 待审核/);
  assert.match(summary, /1 张需重新确认/);
});

test("P5 target geometry keeps list canvas and review panel visible for useful diagrams", () => {
  const css = fs.readFileSync("css/gameplay-diagrams.css", "utf8");
  assert.match(css, /\.gameplay-diagrams-layout\s*\{[^}]*grid-template-columns:\s*240px\s+minmax\(0,1fr\)\s+280px/s);
  assert.match(css, /\.gameplay-diagram-card\s*\{[^}]*width:min\(640px,calc\(100% - 64px\)\)/s);
  assert.match(css, /\.gameplay-diagram-decision\s*\{[^}]*border-left/s);
});

test("generation failure shows retry and never claims no diagram", () => {
  const root = new FakeNode(); const calls = [];
  GameplayDiagrams.render({ root, model: { diagrams: [], diagramReview: { status: "pending" } }, state: { generation: { status: "error", message: "图解生成失败，请重试。" }, byId: {} }, onGenerate: (...args) => calls.push(args), document });
  assert.equal(root.querySelector(".gameplay-diagram-empty"), null);
  const retry = root.querySelector(".gameplay-diagram-retry");
  assert.equal(retry.textContent, "重新生成图解"); retry.dispatch("click"); assert.deepEqual(calls, [[]]);
});

test("deleted diagrams stay hidden and stale diagrams cannot be approved", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: { diagrams: [diagram("deleted"), diagram("stale")], diagramReview: { status: "ready" } }, document });
  assert.equal(root.querySelectorAll(".gameplay-diagram-card").length, 1);
  root.querySelectorAll("input")[0].dispatch("change");
  assert.equal(root.querySelector(".gameplay-diagram-apply").disabled, true);
});

test("stale diagrams expose a clear bulk refresh path instead of looking stuck", () => {
  const root = new FakeNode(); const calls = [];
  GameplayDiagrams.render({
    root,
    model: {
      chapters: [{ id: "GCH-001", scope: "关卡循环" }],
      diagrams: [diagram("stale"), { ...diagram("stale"), id: "GDI-002" }],
      diagramReview: { status: "ready" },
    },
    onGenerate: (...args) => calls.push(args),
    document,
  });
  assert.match(root.querySelector(".gameplay-diagram-summary").textContent, /2 张需按最新正文更新/);
  const refresh = root.querySelector(".gameplay-diagram-refresh-stale");
  assert.equal(refresh.textContent, "按最新正文更新 2 张图");
  refresh.dispatch("click");
  assert.deepEqual(calls, [[]]);
});

test("client sends the existing lifecycle requests", async () => {
  const calls = []; global.fetch = async (url, options = {}) => { calls.push({ url, body: JSON.parse(options.body) }); return { ok: true, json: async () => ({ revision: 2 }) }; };
  const client = new GameplayReviewClient("http://api", "job-1");
  await client.diagrams(1); await client.regenerateDiagram(2, "GDI-001", "补充分支"); await client.approveDiagram(3, "GDI-001"); await client.deleteDiagram(4, "GDI-001");
  assert.deepEqual(calls.map((item) => item.url.split("/").pop()), ["diagrams", "regenerate", "approve", "delete"]);
});

test("retry and card controls retain keyboard focus styling", () => {
  const css = fs.readFileSync("css/gameplay-diagrams.css", "utf8");
  assert.match(css, /gameplay-diagram-retry:focus-visible/);
  assert.match(css, /gameplay-diagram-actions button:focus-visible/);
});

test("P5 radio reflects canonical status and one apply action submits the selected decision", () => {
  const root = new FakeNode(); const calls = [];
  GameplayDiagrams.render({ root, model: { chapters: [{ id: "GCH-001", scope: "武器抽取" }], diagrams: [{ ...diagram("reviewed") }], diagramReview: { status: "ready" } }, onAction: (...args) => calls.push(args), document });
  const radios = root.querySelectorAll("input");
  assert.equal(radios[0].checked, true);
  radios[2].dispatch("change");
  root.querySelector(".gameplay-diagram-apply").dispatch("click");
  assert.deepEqual(calls[0], ["delete", "GDI-001", ""]);
  assert.equal(root.querySelector(".gameplay-diagram-actions"), null);
});

test("P5 excludes pure formula or text-only diagrams from the review queue", () => {
  assert.equal(GameplayDiagrams.diagramHasVisualStructure({ type: "formula", svg: "<svg><text>伤害=攻击×倍率</text></svg>" }), false);
  assert.equal(GameplayDiagrams.diagramHasVisualStructure({ type: "state_flow", svg: "<svg><text>开始</text><path d='M0 0L10 10'/></svg>" }), true);
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: { diagrams: [{ ...diagram(), type: "formula", svg: "<svg><text>公式</text></svg>" }], diagramReview: { status: "ready" } }, document });
  assert.equal(root.querySelector(".gameplay-diagram-card"), null);
  assert.ok(root.querySelector(".gameplay-diagram-empty-confirm"));
});

test("P5 no-diagram state explains the page purpose status and one next action", () => {
  const root = new FakeNode();
  GameplayDiagrams.render({ root, model: { diagrams: [], diagramReview: { status: "ready" } }, document });
  assert.equal(root.querySelector(".gameplay-diagram-empty-title").textContent, "必要图解审核");
  assert.match(root.querySelector(".gameplay-diagram-empty-purpose").textContent, /只保留确有助于理解玩法关系的结构图/);
  assert.equal(root.querySelector(".gameplay-diagram-empty-status").textContent, "当前素材无需额外图解");
  assert.equal(root.querySelectorAll("button").filter((item) => item.className.includes("gameplay-diagram-empty-confirm")).length, 1);
});

test("P5 asks whether a diagram is necessary through a real decision card", () => {
  const root = new FakeNode(); const operations = [];
  GameplayDiagrams.render({ root, model: { chapters: [{ id: "GCH-001", scope: "强化关系", decisionCards: [{ id: "GDC-001", question: "这里需要图解吗？", status: "pending", options: [{ id: "yes", label: "需要状态流程图" }, { id: "no", label: "正文已经足够" }], impacts: ["图解", "最终文档"] }] }], diagrams: [], diagramReview: { status: "ready" } }, onOperation: batch => operations.push(batch), document });
  assert.ok(root.querySelector(".planner-decision-card"));
  const inputs = root.querySelectorAll("input"); inputs.find(input => input.value === "no").checked = true;
  root.querySelector(".planner-decision-apply").dispatch("click");
  assert.equal(operations[0][0].type, "resolve_decision_card");
});
