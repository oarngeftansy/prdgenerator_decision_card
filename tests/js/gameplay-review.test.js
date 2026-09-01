const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

const Forms = require("../../js/gameplay-mechanism-forms.js");
const GameplayReview = require("../../js/gameplay-review.js");

class FakeNode {
  constructor(document, tag) { this.document = document; this.tag = tag; this.children = []; this.attrs = {}; this.listeners = {}; this.className = ""; this.hidden = false; this.value = ""; this._text = ""; }
  set textContent(value) { this._text = String(value); if (value === "") this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child?.textContent || "").join(""); }
  setAttribute(name, value) { this.attrs[name] = String(value); if (name === "class") this.className = String(value); }
  getAttribute(name) { return this.attrs[name]; }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  dispatch(name, event = {}) { (this.listeners[name] || []).forEach((callback) => callback({ preventDefault() {}, stopPropagation() {}, currentTarget: this, target: this, key: "", ...event })); }
  focus() { this.document.activeElement = this; }
  matches(selector) {
    if (selector.startsWith(".")) return this.className.split(/\s+/).includes(selector.slice(1));
    const attr = selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
    if (attr) return Object.hasOwn(this.attrs, attr[1]) && (attr[2] === undefined || this.attrs[attr[1]] === attr[2]);
    return this.tag === selector;
  }
  querySelectorAll(selector) { return this.children.flatMap((child) => child instanceof FakeNode ? [child, ...child.querySelectorAll(selector)] : []).filter((node) => node.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

class FakeDocument {
  constructor() { this.activeElement = null; }
  createElement(tag) { return new FakeNode(this, tag); }
}

function renderDom(model, state = {}, callbacks = {}) {
  const previous = global.document;
  const document = new FakeDocument();
  const root = document.createElement("div");
  global.document = document;
  try { GameplayReview.render({ root, model, state, ...callbacks }); } finally { global.document = previous; }
  return { root, document };
}

const chapter = (overrides = {}) => ({
  id: "GCH-001", scope: "战斗循环", status: "draft", confirmation: { confirmed: false },
  mechanism: { type: "core_loop" }, parameters: {}, claims: [], dependencies: [], acceptanceCases: [], unknowns: [], sourceFrameIds: ["F0001"], ...overrides,
});

test("mechanism fields mirror every backend schema and retain Chinese labels", () => {
  assert.deepEqual(Forms.fieldsFor("core_loop").map((field) => field.key), ["playerGoal", "trigger", "phaseOrder", "completion", "failure", "reset"]);
  assert.deepEqual(Forms.fieldsFor("economy_reward").map((field) => field.key), ["sources", "costs", "settlement", "accumulation", "failure", "lifecycle"]);
  assert.equal(Forms.fieldsFor("unknown").length, 0);
  Forms.fieldsFor("random_pool").forEach((field) => {
    assert.equal(typeof field.label, "string");
    assert.equal(typeof field.helper, "string");
    assert.equal(field.kind, "parameter");
  });
});

test("chapter review status never exposes its internal value", () => {
  assert.equal(GameplayReview.statusLabel("chapter_review"), "待检查");
});

test("chapter content follows planner reading order without backend rule headings", () => {
  const planned = chapter({ plannerSections: {
    summary: "玩家在局内成长时选择一项强化，使本局能力发生变化。",
    normalFlow: ["玩家升级后暂停战斗。", "玩家选择一项强化后继续战斗。"],
    keyRules: ["每次只能选择一项强化。"], specialCases: ["候选不足时不重复展示同一项。"],
    acceptanceExamples: [{ scene: "玩家升级", action: "选择一项强化", expected: "强化生效并继续战斗" }],
  } });
  const { root } = renderDom({ chapters: [planned], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: planned.id });
  const copy = root.textContent;
  assert.ok(copy.indexOf("一句话玩法") < copy.indexOf("正常怎么玩"));
  assert.match(copy, /关键规则/);
  assert.match(copy, /特殊情况/);
  assert.doesNotMatch(copy, /前置状态|处理规则|状态分支|重置方式/);
});

test("chapter shows one primary evidence image and supporting thumbnails", () => {
  const planned = chapter({ plannerSections: {
    summary: "玩家选择强化。", normalFlow: ["升级后选择一项。"], keyRules: ["每次选择一项。"], specialCases: [], acceptanceExamples: [],
  }, inlineEvidence: [1, 2, 3, 4].map((index) => ({
    anchorId: `GEV-00${index}`, frameId: `F000${index}`, imageUrl: `/shot-${index}.jpg`,
    width: 494, height: 924, caption: `支持判断：规则${index}`,
  })) });
  const { root } = renderDom({ chapters: [planned], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: planned.id });
  assert.equal(root.querySelectorAll(".gameplay-inline-evidence-primary").length, 1);
  assert.equal(root.querySelectorAll(".gameplay-inline-evidence-image").length, 4);
  assert.match(root.textContent, /支持判断：规则1/);
  assert.ok(root.querySelector(".gameplay-evidence-thumbnails"));
  const first = root.querySelector(".gameplay-inline-evidence-image");
  assert.equal(first.getAttribute("width"), "494");
  assert.equal(first.getAttribute("height"), "924");
});

test("presentation and numeric rules never render inside gameplay flow", () => {
  const planned = chapter({ plannerSections: {
    summary: "店铺升级影响经营收益。",
    normalFlow: ["玩家确认升级后，系统扣除钞票并提升店铺等级。"],
    keyRules: ["达到等级上限后不可继续升级。"],
    presentationRules: ["底部面板显示当前等级。"],
    numericRules: ["每秒收益等于基础收入加其他加成。"],
    specialCases: [], acceptanceExamples: [],
  } });
  const { root } = renderDom({ chapters: [planned], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: planned.id });
  const flowSection = root.querySelectorAll(".gameplay-rule-audit-section").find((node) => node.textContent.includes("玩法流程"));

  assert.match(flowSection.textContent, /玩家确认升级/);
  assert.doesNotMatch(flowSection.textContent, /底部面板|每秒收益/);
  assert.match(root.textContent, /表现规则.*底部面板显示当前等级/);
  assert.match(root.textContent, /数值规则.*每秒收益等于基础收入加其他加成/);
});

test("legacy scalar rule information renders as one item instead of one bullet per character", () => {
  const planned = chapter({ plannerSections: {
    summary: "规则仍需确认。", normalFlow: [], keyRules: [],
    acceptanceExamples: "未知待确认，仅展示静态信息，触发交互逻辑仍需确认",
  } });
  const { root } = renderDom({ chapters: [planned], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: planned.id });
  const verification = root.querySelectorAll(".gameplay-rule-audit-section").find((node) => node.textContent.includes("配置与验证"));
  assert.equal(verification.querySelectorAll("li").length, 1);
  assert.match(verification.textContent, /未知待确认，仅展示静态信息，触发交互逻辑仍需确认/);
});

test("a chapter without configuration sources or acceptance cases does not invent a verification template", () => {
  const planned = chapter({ plannerSections: {
    summary: "店铺收益规则。", normalFlow: [], keyRules: ["店铺升级后提高收益。"],
    acceptanceExamples: [],
  }, acceptanceCases: [], configurationSources: [] });
  const { root } = renderDom({ chapters: [planned], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: planned.id });
  const verification = root.querySelectorAll(".gameplay-rule-audit-section").find((node) => node.textContent.includes("配置与验证"));

  assert.equal(verification, undefined);
  assert.doesNotMatch(root.textContent, /结合本节参考画面，核对触发、过程变化与最终结果/);
});

test("a failed evidence image retries in place before opening the preview", () => {
  const opened = [];
  const planned = chapter({ inlineEvidence: [{
    anchorId: "GEV-001", frameId: "F0001", imageUrl: "/frames/F0001.jpg",
    width: 494, height: 924, caption: "支持判断：玩家可以进入战斗。",
  }] });
  const { root } = renderDom(
    { chapters: [planned], evidenceAnchors: [], reviewState: { findings: [] } },
    { selectedChapterId: planned.id },
    { onOpenEvidence: (id) => opened.push(id) },
  );
  const card = root.querySelector(".gameplay-inline-evidence-card");
  const image = root.querySelector(".gameplay-inline-evidence-image");

  image.dispatch("error");
  assert.match(card.textContent, /画面加载失败，点击重试/);
  card.dispatch("click");

  assert.deepEqual(opened, []);
  assert.match(image.getAttribute("src"), /vpr_image_retry=1/);
  assert.match(card.textContent, /正在重试/);

  image.dispatch("load");
  card.dispatch("click");
  assert.deepEqual(opened, ["GEV-001"]);
});

test("v2 P4 renders atomic rules by schema slot and type without planner prose", () => {
  const model = {
    contentModelVersion: 2, chapters: [], evidenceAnchors: [], reviewState: { findings: [] },
    approvedData: {
      chapters: [{ chapterId: "V2CH-001", system: "核心战斗", object: "载具", title: "受击及死亡" }],
      rules: [
        { ruleId: "R1", ownerChapterId: "V2CH-001", schemaSlot: "damage_death_definition", ruleType: "logic", behavior: "命中后扣除生命值", evidenceIds: ["F1"], reviewStatus: "unreviewed" },
        { ruleId: "R2", ownerChapterId: "V2CH-001", schemaSlot: "damage_death_definition", ruleType: "presentation", behavior: "生命值变化后刷新生命条", evidenceIds: ["F1"], reviewStatus: "unreviewed" },
      ],
    },
  };
  const { root } = renderDom(model, { selectedChapterId: "V2CH-001" });
  assert.match(root.textContent, /结构化规则审核/);
  assert.match(root.textContent, /逻辑规则/);
  assert.match(root.textContent, /表现规则/);
  assert.match(root.textContent, /受击及死亡/);
  assert.doesNotMatch(root.textContent, /damage_death_definition/);
  assert.doesNotMatch(root.textContent, /一句话玩法/);
});

test("v2 P4 exposes temporal candidates with timestamps through the existing rule review action", () => {
  const reviewed = [];
  const candidate = {
    ruleId: "TRC-1", ownerChapterId: "V2CH-001", schemaSlot: "movement_direction",
    ruleType: "logic", behavior: "当前视频样本观察到对象持续发生相对位置变化。",
    evidenceIds: ["VF-1", "VF-2"], sourceFactIds: ["TF-1"], reviewStatus: "unreviewed",
    candidateKind: "temporal_rule_candidate",
  };
  const model = {
    contentModelVersion: 2, chapters: [], evidenceAnchors: [], reviewState: { findings: [] },
    approvedData: { chapters: [{ chapterId: "V2CH-001", system: "玩法", object: "对象", title: "移动" }], rules: [] },
    ruleIntelligenceProjection: { ruleCandidates: [candidate] },
    temporalEvidence: { facts: [{ factId: "TF-1", evidenceTimestamps: [1.25, 2.5], reviewStatus: "unreviewed" }] },
  };

  const { root } = renderDom(model, { selectedChapterId: "V2CH-001" }, {
    onRuleReview: (ruleId, decision) => reviewed.push([ruleId, decision]),
  });

  assert.match(root.textContent, /视频观察 · 待确认/);
  assert.match(root.textContent, /1.25s、2.5s/);
  const approve = root.querySelectorAll("button").find((node) => node.textContent === "通过");
  approve.dispatch("click");
  assert.deepEqual(reviewed, [["TRC-1", "approved"]]);
});

test("evidence studio renders system subsystem and mechanism without flattening", () => {
  const first = chapter({ id: "GCH-001", scope: "伤害计算" });
  const second = chapter({ id: "GCH-002", scope: "升级选择" });
  const model = {
    chapters: [first, second], evidenceAnchors: [], reviewState: { findings: [] },
    systems: [{ id: "GSY-001", name: "战斗与关卡", subsystems: [
      { id: "GSS-001", name: "核心战斗", chapterIds: ["GCH-001"] },
      { id: "GSS-002", name: "局内成长", chapterIds: ["GCH-002"] },
    ] }],
  };

  const { root } = renderDom(model, { selectedChapterId: first.id });

  assert.equal(root.querySelectorAll("[data-gameplay-system]").length, 1);
  assert.equal(root.querySelectorAll("[data-gameplay-subsystem]").length, 2);
  assert.match(root.textContent, /战斗与关卡/);
  assert.match(root.textContent, /伤害计算/);
  assert.ok(root.querySelector(".gameplay-evidence-column"));
  assert.ok(root.querySelector(".gameplay-rules-column"));
});

test("legacy confirmed directory is upgraded to the evidence studio hierarchy", () => {
  const first = chapter({ id: "GCH-001", scope: "核心战斗" });
  const second = chapter({ id: "GCH-002", scope: "首领出现" });
  const model = {
    chapters: [first, second], evidenceAnchors: [], reviewState: { findings: [] },
    directory: { status: "confirmed", entries: [
      { chapterId: "GCH-001", sectionTitle: "战斗与关卡", order: 1 },
      { chapterId: "GCH-002", sectionTitle: "战斗与关卡", order: 2 },
    ] },
  };

  const { root } = renderDom(model, { selectedChapterId: first.id });

  assert.equal(root.querySelectorAll("[data-gameplay-system]").length, 1);
  assert.equal(root.querySelectorAll("[data-gameplay-subsystem]").length, 1);
  assert.match(root.textContent, /战斗与关卡/);
  assert.match(root.textContent, /玩法机制/);
  assert.match(root.textContent, /核心战斗/);
  assert.match(root.textContent, /首领出现/);
});

test("right column shows only useful planner modules with familiar Chinese labels", () => {
  const current = chapter({
    plannerSections: { summary: "伤害由攻击属性和武器倍率共同决定。", normalFlow: [], keyRules: [], specialCases: [], acceptanceExamples: [] },
    formulae: [{ expression: "最终伤害 = 攻击属性 × 武器倍率" }],
    workedExamples: [{ title: "计算示例", steps: "100 × 1.5 = 150" }],
    configurationSources: [{ title: "武器基础属性表", field: "damageRatio" }],
  });

  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });

  assert.match(root.textContent, /计算方法/);
  assert.match(root.textContent, /计算示例/);
  assert.match(root.textContent, /数值从哪里配置/);
  assert.doesNotMatch(root.textContent, /字段结构|parameterSchema|formulae|configurationSources/);
  assert.equal(root.querySelector(".gameplay-parameter-schema"), null);
});

test("repeated evidence captions are replaced with concise supplemental labels", () => {
  const repeated = chapter({ inlineEvidence: [1, 2].map((index) => ({
    anchorId: `GEV-00${index}`, frameId: `F000${index}`, imageUrl: `/frames/${index}.jpg`,
    caption: "支持判断：玩家正在持续攻击敌人。", width: 494, height: 924,
  })) });
  const { root } = renderDom({ chapters: [repeated], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: repeated.id });
  assert.equal(root.textContent.match(/支持判断：玩家正在持续攻击敌人。/g)?.length, 1);
  assert.match(root.textContent, /同一过程的补充画面/);
});

test("chapter view model stays compact and expands unresolved or edited chapters", () => {
  const complete = chapter({ status: "reviewed", confirmation: { confirmed: true }, parameters: { playerGoal: { type: "text", unit: "次", range: "1", source: "F0001" } } });
  const unresolved = chapter({ unknowns: ["触发时机待确认"] });
  const model = GameplayReview.viewModel({ chapters: [complete, unresolved], reviewState: { findings: [{ severity: "blocker", status: "open", chapterId: "GCH-001X" }] } }, { selectedChapterId: complete.id });

  assert.equal(model.chapters[0].collapsed, true);
  assert.equal(model.chapters[1].collapsed, false);
  assert.equal(model.chapters[1].blockers, 0);
  assert.match(GameplayReview.statusLabel("approved"), /已/);
});

test("view model counts only unresolved blockers without duplicating global findings", () => {
  const chapters = [chapter({ id: "GCH-001" }), chapter({ id: "GCH-002" })];
  const warning = GameplayReview.viewModel({ chapters, reviewState: { findings: [{ severity: "warning", status: "open" }] } });
  assert.equal(warning.totalBlockers, 0);
  assert.deepEqual(warning.chapters.map((item) => item.blockers), [0, 0]);

  const global = GameplayReview.viewModel({ chapters, reviewState: { findings: [{ severity: "blocker", status: "open" }] } });
  assert.equal(global.totalBlockers, 1);
  assert.deepEqual(global.chapters.map((item) => item.blockers), [0, 0]);

  const owned = GameplayReview.viewModel({ chapters, reviewState: { findings: [{ severity: "blocker", status: "open", chapterId: "GCH-002" }, { severity: "blocker", status: "resolved", chapterId: "GCH-001" }] } });
  assert.equal(owned.totalBlockers, 1);
  assert.deepEqual(owned.chapters.map((item) => item.blockers), [0, 1]);
});

test("chapter rail shows review progress and keyboard-safe pending navigation", () => {
  const selections = [];
  const chapters = [
    chapter({ id: "GCH-001", confirmation: { confirmed: true }, status: "approved" }),
    chapter({ id: "GCH-002", scope: "奖励", unknowns: ["奖励值待确认"] }),
    chapter({ id: "GCH-003", scope: "结算" }),
  ];
  const { root } = renderDom({ chapters, evidenceAnchors: [], reviewState: { findings: [{ severity: "blocker", status: "open", chapterId: "GCH-002" }] } }, { selectedChapterId: "GCH-002" }, { onSelectChapter: (id) => selections.push(id) });
  const rail = root.querySelector(".gameplay-chapter-rail");
  assert.match(rail.textContent, /已确认 1\/3/);
  assert.match(rail.textContent, /确认前需要补全 1/);
  const pendingButtons = rail.querySelectorAll(".gameplay-pending-button");
  assert.deepEqual(pendingButtons.map((item) => item.getAttribute("type")), ["button", "button"]);
  pendingButtons[0].dispatch("click"); pendingButtons[1].dispatch("click");
  assert.deepEqual(selections, ["GCH-003", "GCH-003"]);
});

test("mechanism rule fields never mount as numeric parameter editors", () => {
  const full = Object.fromEntries(Forms.fieldsFor("core_loop").map(({ key }) => [key, { type: "text", unit: "次", range: "1", source: "F0001" }]));
  const complete = chapter({ status: "approved", confirmation: { confirmed: true }, claims: [{ id: "GCL-001", text: "攻击", sourceType: "material", sourceFrameIds: ["F0001"] }], parameters: full });
  const compact = renderDom({ chapters: [complete], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: complete.id });
  assert.equal(compact.root.querySelectorAll(".gameplay-parameter").length, 0);
  assert.equal(compact.root.querySelectorAll(".gameplay-claim-editor").length, 0);

  const missing = chapter({ claims: [], parameters: { ...full, trigger: undefined } });
  const exception = renderDom({ chapters: [missing], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: missing.id, draftDecision: "needs_edit" });
  assert.equal(exception.root.querySelectorAll(".gameplay-parameter").length, 0);
  assert.match(exception.root.textContent, /新增规则/);
});

test("pending unbacked and edited claims expand and persist Chinese-labelled source status", () => {
  const operations = [];
  const pending = chapter({ claims: [{ id: "GCL-001", text: "待核实攻击", sourceType: "pending", sourceFrameIds: [] }] });
  const { root } = renderDom({ chapters: [pending], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: pending.id }, { onOperation: (batch) => operations.push(...batch) });
  assert.equal(root.querySelectorAll(".gameplay-claim-editor").length, 1);
  const source = root.querySelector(".gameplay-claim-source");
  assert.deepEqual(source.children.map((option) => option.textContent), ["素材中明确展示", "参考文档明确说明", "根据前后内容推断", "策划已经确认", "还需要确认"]);
  source.value = "planner"; source.dispatch("change");
  assert.equal(operations[0].claim.sourceType, "planner");

  const backed = chapter({ claims: [{ id: "GCL-002", text: "已证实攻击", sourceType: "material", sourceFrameIds: ["F0001"] }] });
  const compact = renderDom({ chapters: [backed], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: backed.id });
  assert.equal(compact.root.querySelectorAll(".gameplay-claim-editor").length, 0);
  const edited = renderDom({ chapters: [backed], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: backed.id, editedGroups: [`${backed.id}:claims`] });
  assert.equal(edited.root.querySelectorAll(".gameplay-claim-editor").length, 1);
});

test("parameter editors only require values that actually exist in the chapter", () => {
  const empty = renderDom({ chapters: [chapter()], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: "GCH-001" });
  assert.equal(empty.root.querySelectorAll(".gameplay-parameter").length, 0);
  assert.doesNotMatch(empty.root.textContent, /还有 6 项/);
  const configured = chapter({ parameters: { currentLevel: { type: "数字", unit: "级", range: "1-10", source: "玩法配置表" } } });
  const { root } = renderDom({ chapters: [configured], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: "GCH-001", expandedGroups: ["GCH-001:parameters"] });
  const inputs = root.querySelectorAll(".gameplay-parameter").flatMap((card) => card.querySelectorAll("input"));
  assert.ok(inputs.length > 0);
  assert.ok(inputs.every((input) => input.getAttribute("inputmode") === "decimal"));
  assert.match(root.querySelector(".gameplay-parameter").textContent, /填写格式.*数值单位.*可用范围.*数值从哪里配置/s);
});

test("numeric parameters stay visible while embedded mechanism fields are excluded", () => {
  const configured = chapter({ parameters: {
    currentLevel: { type: "数字", unit: "级", range: "1-10", source: "玩法配置表" },
    remainingTime: { type: "数字", unit: "秒", range: "0-300", source: "关卡配置表" },
    playerGoal: { type: "文本", unit: "无", range: "无", source: "素材" },
    trigger: { type: "文本", unit: "无", range: "无", source: "素材" },
  } });
  assert.deepEqual(GameplayReview.configuredParameterFields(configured).map(({ key }) => key), ["currentLevel", "remainingTime"]);
});

test("empty global findings do not reserve a third layout column", () => {
  const { root } = renderDom({ chapters: [chapter()], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: "GCH-001" });
  assert.match(root.querySelector(".gameplay-review").getAttribute("class"), /no-findings/);
  assert.equal(root.querySelector(".gameplay-findings-panel"), null);
});

test("shared exception editor exposes dependency acceptance and claim operations without legacy unknown editor", () => {
  const operations = [];
  const model = { chapters: [chapter(), chapter({ id: "GCH-002", scope: "奖励" })], evidenceAnchors: [], reviewState: { findings: [] } };
  const { root } = renderDom(model, { selectedChapterId: "GCH-001", expandedGroups: ["GCH-001:issues"], draftDecision: "needs_edit" }, { onOperation: (batch) => operations.push(...batch) });
  assert.ok(root.querySelector(".gameplay-dependency-editor"));
  assert.ok(root.querySelector(".gameplay-acceptance-editor"));
  assert.equal(root.querySelector(".gameplay-unknown-editor"), null);
  const addClaim = root.querySelector(".gameplay-add-claim");
  addClaim.dispatch("click");
  assert.equal(operations.length, 0);
  assert.ok(root.querySelectorAll(".gameplay-field-error").some((node) => /请填写/.test(node.textContent)));
});

test("planner check methods render their situation and expected result without internal empty values", () => {
  const withChecks = chapter({ acceptanceCases: [{
    id: "GAC-001", case: "点击刷新按钮", expected: "三个选项重新生成",
  }] });
  const { root } = renderDom({ chapters: [withChecks], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: withChecks.id, expandedGroups: [`${withChecks.id}:issues`] });

  assert.match(root.textContent, /怎么判断这部分做对了/);
  assert.match(root.textContent, /操作或情况/);
  assert.match(root.textContent, /应该看到的结果/);
  assert.match(root.textContent, /删除这条检查方法/);
  assert.doesNotMatch(root.textContent, /验收|undefined/);
});

test("expanded rule panels survive a save rerender and only change on manual toggle", () => {
  const toggles = [];
  const state = { selectedChapterId: "GCH-001", expandedGroups: ["GCH-001:rules", "GCH-001:parameters"] };
  const { root } = renderDom({ chapters: [chapter()], evidenceAnchors: [], reviewState: { findings: [] } }, state, { onToggleGroup: (id, group) => toggles.push(`${id}:${group}`) });
  const rules = root.querySelector(".gameplay-rule-details");
  const parameters = root.querySelector(".gameplay-parameter-details");
  assert.equal(rules.open, true);
  assert.equal(parameters.open, true);
  rules.open = false; rules.dispatch("toggle");
  assert.deepEqual(toggles, ["GCH-001:rules"]);
});

test("edit rules uses one explicit action that can reveal the complete nested editor", () => {
  const opened = [];
  const current = chapter({ claims: [{ id: "GCL-001", text: "玩家自动攻击", sourceType: "material", sourceFrameIds: ["F0001"] }] });
  const { root } = renderDom(
    { chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } },
    { selectedChapterId: current.id, expandedGroups: [] },
    { onEditRules: (chapterId) => opened.push(chapterId) },
  );

  root.querySelectorAll("button").find((item) => item.textContent === "编辑规则").dispatch("click");

  assert.deepEqual(opened, ["GCH-001"]);
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const handler = backend.slice(backend.indexOf("onEditRules: (chapterId)"), backend.indexOf("onOperation: runGameplayOperations"));
  assert.match(handler, /draftDecision:\s*"needs_edit"/);
  assert.match(handler, /gameplay-planner-summary-editor/);
});

test("every structured pending item offers planner decisions instead of a bare delete button", () => {
  const operations = []; const notices = [];
  const pending = chapter({ decisionCards: [{ id: "GDC-001", question: "升级触发方式？", selectionMode: "single", status: "pending", allowCustom: true, options: [{ id: "auto", label: "自动" }, { id: "manual", label: "手动" }] }] });
  const { root } = renderDom({ chapters: [pending], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: pending.id, expandedGroups: [`${pending.id}:issues`] }, { onOperation: batch => operations.push(batch), onNotice: message => notices.push(message) });
  const buttons = root.querySelectorAll("button");
  assert.ok(buttons.find(item => item.textContent === "应用选择"));
  assert.ok(buttons.find(item => item.textContent === "暂时跳过"));
  buttons.find(item => item.textContent === "暂时跳过").dispatch("click");
  assert.equal(operations.length, 1);
});

test("approved chapters explain retained decisions without presenting them as confirmed conclusions", () => {
  const approved = chapter({ status: "approved", confirmation: { confirmed: true }, decisionCards: [{ id: "a", question: "伤害公式？", status: "skipped", options: [{id:"1",label:"A"},{id:"2",label:"B"}] }, { id: "b", question: "经验曲线？", status: "skipped", options: [{id:"1",label:"A"},{id:"2",label:"B"}] }] });
  const { root } = renderDom({ chapters: [approved], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: approved.id });
  assert.match(root.textContent, /本章已通过/);
  assert.match(root.textContent, /2 项尚未选择/);
  assert.doesNotMatch(root.textContent, /待确认/);
});

test("next pending chapter skips already confirmed chapters", () => {
  const chapters = [chapter({ id: "GCH-001", confirmation: { confirmed: true }, status: "reviewed" }), chapter({ id: "GCH-002" }), chapter({ id: "GCH-003" })];
  assert.equal(GameplayReview.nextPending(chapters, "GCH-001", 1).id, "GCH-002");
  assert.equal(GameplayReview.nextPending(chapters, "GCH-003", 1).id, "GCH-002");
});

test("next pending chapter continues forward after the current chapter was just confirmed", () => {
  const chapters = [
    chapter({ id: "GCH-001" }),
    chapter({ id: "GCH-002", confirmation: { confirmed: true } }),
    chapter({ id: "GCH-003" }),
  ];
  assert.equal(GameplayReview.nextPending(chapters, "GCH-002", 1).id, "GCH-003");
});

test("chapter decision always shows saving or failure feedback beside the buttons", () => {
  const saving = renderDom({ chapters: [chapter()], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: "GCH-001", confirmationStatus: "saving" });
  assert.match(saving.root.textContent, /正在保存审核结论/);
  assert.ok(saving.root.querySelectorAll("[data-gameplay-decision]").every((item) => item.disabled));
  const failed = renderDom({ chapters: [chapter()], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: "GCH-001", confirmationStatus: "failed", confirmationMessage: "还有数值没有填写完整" });
  assert.match(failed.root.textContent, /还有数值没有填写完整/);
});

test("mobile tabs expose content, parameters, and findings without a wide layout", () => {
  assert.deepEqual(GameplayReview.mobileTabs().map((item) => item.key), ["content", "parameters", "issues"]);
  const selected = [];
  const { root } = renderDom({ chapters: [chapter()], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: "GCH-001", activeTab: "parameters" }, { onTab: (key) => selected.push(key) });
  assert.equal(root.querySelector(".gameplay-review").getAttribute("data-active-tab"), "parameters");
  const tabs = root.querySelectorAll(".gameplay-mobile-tab");
  assert.deepEqual(tabs.map((tab) => tab.getAttribute("aria-selected")), ["false", "true", "false"]);
  tabs[2].dispatch("click");
  assert.deepEqual(selected, ["issues"]);
});

test("evidence stays out of the editor until drawer opens and restores opener focus on Escape", () => {
  const document = new FakeDocument();
  const opener = document.createElement("button");
  const calls = [];
  const model = { chapters: [chapter()], evidenceAnchors: [{ id: "GEV-001", frameId: "F0001", imageUrl: "/shot.jpg", source: { name: "01.png", timestamp: 1.2 } }], reviewState: { findings: [] } };
  const closed = renderDom(model, { selectedChapterId: "GCH-001" });
  assert.equal(closed.root.querySelectorAll("img").length, 0);
  const opened = renderDom(model, { selectedChapterId: "GCH-001", evidenceDrawer: "GEV-001", evidenceOpener: opener }, { onOpenEvidence: (id) => calls.push(id), resolveEvidenceUrl: (url) => `http://backend${url}` });
  const image = opened.root.querySelector("img");
  assert.equal(image.getAttribute("src"), "http://backend/shot.jpg");
  assert.match(image.getAttribute("alt"), /F0001/);
  assert.match(opened.root.textContent, /01\.png/);
  opened.root.querySelector(".gameplay-evidence-drawer").dispatch("keydown", { key: "Escape" });
  assert.deepEqual(calls, [null]);
  assert.equal(opener.document.activeElement, opener);
});

test("save and context outcomes are visible in live regions even when evidence is closed", () => {
  assert.equal(GameplayReview.saveStatusLabel("conflict"), "版本冲突，正在同步");
  assert.equal(GameplayReview.contextStatusLabel("needs_location"), "请补充对应的视频位置后再试。");
  assert.deepEqual(GameplayReview.contextFieldsFor(chapter({ parameters: {} })), []);
  const { root } = renderDom({ chapters: [chapter()], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: "GCH-001", saveStatus: "failed", contextStatus: "failed" });
  assert.match(root.querySelector(".gameplay-save-status").textContent, /保存失败/);
  assert.match(root.querySelector(".gameplay-context-status").textContent, /没有找到/);
  assert.equal(root.querySelector(".gameplay-context-status").getAttribute("aria-live"), "polite");
});

test("chapter editor payloads use canonical gameplay operations", () => {
  assert.deepEqual(GameplayReview.parameterOperation("GCH-001", "trigger", { type: "number", unit: "秒", range: "0-10", source: "F0001" }), {
    type: "upsert_parameter", chapterId: "GCH-001", name: "trigger", parameter: { type: "number", unit: "秒", range: "0-10", source: "F0001" },
  });
  assert.deepEqual(GameplayReview.chapterOperation("GCH-001", "scope", "新的范围"), {
    type: "set_chapter_field", chapterId: "GCH-001", field: "scope", value: "新的范围",
  });
});

test("gameplay review separates values verification and planner decisions", () => {
  const planned = chapter({
    parameterSchema: [{ name: "攻击", plannerMeaning: "本次攻击使用的基础值", type: "整数", unit: "点", configurationSource: "载具属性表" }],
    acceptanceCases: [{ case: "攻击普通敌人", expected: "按伤害规则扣减生命" }],
    decisionCards: [{ id: "GDC-001", question: "暴击是否在最终伤害前计算", status: "pending", options: [{id:"before",label:"之前"},{id:"after",label:"之后"}] }],
  });
  const { root } = renderDom({ chapters: [planned], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: planned.id });
  const focus = root.querySelector(".gameplay-review-focus");
  assert.ok(focus);
  assert.match(focus.textContent, /数值与配置.*1 项.*怎么验证.*1 条.*需要策划决定.*1 项/s);
});

test("gameplay review hides empty focus cards that look like disabled actions", () => {
  const empty = chapter({ parameterSchema: [], acceptanceCases: [], unknowns: [] });
  const { root } = renderDom({ chapters: [empty], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: empty.id });
  assert.equal(root.querySelector(".gameplay-review-focus"), null);
});

test("previous and next pending buttons are disabled when no target exists", () => {
  const only = chapter({ confirmation: { confirmed: false } });
  const { root } = renderDom({ chapters: [only], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: only.id });
  const controls = root.querySelectorAll(".gameplay-pending-button");
  assert.equal(controls.length, 2);
  assert.equal(controls[0].disabled, true);
  assert.equal(controls[1].disabled, true);
});

test("planner first sees the gameplay conclusion and document-style actions", () => {
  const current = chapter({ plannerSections: { summary: "玩家升级后选择一项强化，选择后立即生效并继续战斗。" } });
  const { root } = renderDom(
    { chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } },
    { selectedChapterId: current.id }
  );

  assert.match(root.textContent, /玩家升级后选择一项强化/);
  assert.deepEqual(
    root.querySelectorAll("[data-gameplay-decision]").map((node) => node.textContent),
    ["返回修改", "确认本节通过"]
  );
  assert.equal(root.querySelector(".gameplay-parameters"), null);
  assert.equal(root.querySelector(".gameplay-dependency-editor"), null);
});

test("editing appears only for a partial result and supplemental details require real content", () => {
  const current = chapter({ parameters: {}, dependencies: [], acceptanceCases: [], unknowns: [] });
  const compact = renderDom(
    { chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } },
    { selectedChapterId: current.id }
  );
  assert.equal(compact.root.querySelector(".gameplay-planner-summary-editor"), null);
  assert.equal(compact.root.querySelector(".gameplay-supplemental-details"), null);

  const editing = renderDom(
    { chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } },
    { selectedChapterId: current.id, draftDecision: "needs_edit" }
  );
  assert.ok(editing.root.querySelector(".gameplay-planner-summary-editor"));
  assert.ok(editing.root.querySelector(".gameplay-supplemental-details"));
});

test("planner decisions map to save stay or skip behavior", () => {
  assert.deepEqual(GameplayReview.decisionAction("approved"), { decision: "approved", advance: true });
  assert.deepEqual(GameplayReview.decisionAction("needs_edit"), { decision: null, advance: false });
  assert.deepEqual(GameplayReview.decisionAction("not_applicable"), { decision: "not_applicable", advance: true });
});

test("rule audit always exposes numbered flow parameters and verification sections", () => {
  const source = require("node:fs").readFileSync("js/gameplay-review.js", "utf8");
  assert.match(source, /gameplay-rule-audit-section/);
  ["规则理解", "玩法流程", "参数配置", "验证方式"].forEach((label) => assert.match(source, new RegExp(label)));
});

test("P4 matches the target rule hierarchy and exposes complete chapter navigation", () => {
  const first = chapter({ id: "GCH-001", scope: "三选一强化池", decisionCards: [{ id: "GDC-001", question: "强化池是否允许重复", status: "pending", options: [{id:"yes",label:"允许"},{id:"no",label:"不允许"}] }] });
  const second = chapter({ id: "GCH-002", scope: "新武器解锁" });
  const calls = [];
  const { root } = renderDom(
    { chapters: [first, second], evidenceAnchors: [], reviewState: { findings: [] } },
    { selectedChapterId: first.id },
    { onSelectChapter: (id) => calls.push(["select", id]), onSave: () => calls.push(["save"]), onDecision: (id, decision) => calls.push(["decision", id, decision]) }
  );
  assert.match(root.querySelector(".gameplay-rule-head").textContent, /规则审核 \/.*三选一强化池.*1 \/ 2/);
  assert.equal(root.querySelectorAll(".gameplay-rule-audit-number").length, 4);
  assert.match(root.textContent, /策划决策/);
  const nav = root.querySelector(".gameplay-rule-footer-nav").querySelectorAll(".btn");
  assert.equal(nav.length, 2);
  assert.equal(nav[0].disabled, true);
  nav[1].dispatch("click");
  assert.deepEqual(calls.at(-1), ["select", "GCH-002"]);
  root.querySelector(".gameplay-rule-save").dispatch("click");
  assert.deepEqual(calls.at(-1), ["save"]);
  root.querySelector(".gameplay-rule-confirm").dispatch("click");
  assert.deepEqual(calls.at(-1), ["decision", "GCH-001", "approved"]);
});

test("P4 separates chapter title audit cards body copy and supporting fields", () => {
  const { root } = renderDom(
    { chapters: [chapter({ id: "GCH-001" })], evidenceAnchors: [], reviewState: { findings: [] } },
    { selectedChapterId: "GCH-001" }
  );
  assert.equal(root.querySelector(".sr-only"), null);
  const css = fs.readFileSync("css/gameplay-review.css", "utf8");
  assert.match(css, /\.gameplay-summary>h3\s*\{[^}]*font-size\s*:\s*20px[^}]*font-weight\s*:\s*600/s);
  assert.match(css, /\.gameplay-rule-audit-section\s+h4\s*\{[^}]*font-size\s*:\s*14px[^}]*font-weight\s*:\s*600/s);
  assert.match(css, /\.gameplay-rule-audit-section\s+p[^}]*font-size\s*:\s*13px[^}]*line-height\s*:\s*1\.7/s);
  assert.match(css, /\.gameplay-rule-audit-table\s+(?:th|td)[^}]*font-size\s*:\s*12px[^}]*color\s*:\s*#596273/s);
});

test("P4 reserves content space for its sticky footer", () => {
  const css = fs.readFileSync("css/gameplay-review.css", "utf8");
  assert.match(css, /\.gameplay-summary\s*\{[^}]*padding\s*:\s*18px 0 96px/s);
  assert.doesNotMatch(css, /\.gameplay-decision\s*\{[^}]*margin-top\s*:\s*-64px/s);
});

test("P4 semantically deduplicates evidence mechanism conclusions and ordered flow", () => {
  const repeated = "升级时暂停游戏，出现三选一强化池，选择后立即生效并继续战斗。";
  const current = chapter({
    plannerSections: { summary: repeated, normalFlow: [repeated, "玩家确认一项强化。", "确认后恢复战斗。"], keyRules: [], specialCases: [], acceptanceExamples: [] },
    inlineEvidence: [{ anchorId: "GEV-001", imageUrl: "/pool.png", caption: "画面显示三个强化选项" }],
    evidenceClaims: [repeated, "画面中央可见三张强化卡片。"],
  });
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  const sections = root.querySelectorAll(".gameplay-rule-audit-section");
  const facts = root.querySelector(".gameplay-evidence-facts");
  assert.doesNotMatch(facts.textContent, /升级时暂停游戏/);
  assert.match(facts.textContent, /画面中央可见三张强化卡片/);
  assert.doesNotMatch(sections[0].textContent, /升级时暂停游戏/);
  assert.equal(sections[1].textContent.match(/升级时暂停游戏/g)?.length, 1);
});

test("P4 preserves editor scroll and focused input across same-chapter rerenders only", () => {
  const previous = global.document; const document = new FakeDocument(); const root = document.createElement("div"); global.document = document;
  const current = chapter({ plannerSections: { summary: "三选一强化机制", normalFlow: ["升级后暂停", "选择强化", "恢复战斗"] } });
  const model = { chapters: [current, chapter({ id: "GCH-002", scope: "奖励" })], evidenceAnchors: [], reviewState: { findings: [] } };
  try {
    GameplayReview.render({ root, model, state: { selectedChapterId: current.id, draftDecision: "needs_edit", expandedGroups: [`${current.id}:supplemental`] } });
    const editor = root.querySelector(".gameplay-chapter-editor"); const textarea = root.querySelector("textarea");
    editor.scrollTop = 640; textarea.focus();
    GameplayReview.render({ root, model: { ...model, revision: "refresh-2" }, state: { selectedChapterId: current.id, draftDecision: "needs_edit", expandedGroups: [`${current.id}:supplemental`] } });
    assert.equal(root.querySelector(".gameplay-chapter-editor").scrollTop, 640);
    assert.equal(document.activeElement?.tag, "textarea");
    GameplayReview.render({ root, model, state: { selectedChapterId: "GCH-002" } });
    assert.equal(root.querySelector(".gameplay-chapter-editor").scrollTop || 0, 0);
  } finally { global.document = previous; }
});

test("P4 exposes one save and one approval action instead of duplicating them in the header", () => {
  const current = chapter();
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  assert.equal(root.querySelectorAll(".gameplay-rule-save").length, 1);
  assert.equal(root.querySelectorAll(".gameplay-rule-confirm").length, 1);
  const headerActions = root.querySelector(".gameplay-studio-actions");
  assert.equal(headerActions.querySelectorAll("button").length, 1);
  assert.equal(headerActions.querySelector("button").textContent, "调整目录");
});

test("P4 hides an empty flow module instead of rendering a numbered blank card", () => {
  const current = chapter({ plannerSections: { summary: "载具会沿路线自动前进。", normalFlow: [], keyRules: [], specialCases: [], acceptanceExamples: [] } });
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  const flow = root.querySelectorAll(".gameplay-rule-audit-section")[1];
  assert.equal(flow.hidden, true);
  assert.equal(flow.querySelectorAll("li").length, 0);
});

test("P4 hides an empty planner decision module instead of showing decorative filler", () => {
  const current = chapter({ unknowns: [] });
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  assert.doesNotMatch(root.textContent, /本节没有需要额外决定的内容/);
  assert.doesNotMatch(root.textContent, /策划决策/);
});

test("uncertainty decisions render as actionable cards with evidence recommendation impacts and custom entry", () => {
  const operations = [];
  const current = chapter({ unknowns: ["这一环节是如何触发的？"], decisionCards: [{
    id: "GDC-001", question: "这一环节是如何触发的？", selectionMode: "single", status: "pending", allowCustom: true,
    options: [{ id: "wave", label: "击败当前一波敌人后自动出现" }, { id: "level", label: "经验达到升级条件后自动出现", recommended: true, reason: "相邻截图出现升级界面" }],
    evidence: [{ frameId: "F0001", label: "升级界面截图" }], impacts: ["玩法正文", "策划草图", "最终文档"],
  }] });
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id }, { onOperation: batch => operations.push(batch) });
  const card = root.querySelector(".planner-decision-card");
  assert.ok(card);
  assert.match(card.textContent, /AI 推荐.*经验达到升级条件/);
  assert.match(card.textContent, /判断依据.*升级界面截图/);
  assert.match(card.textContent, /保存后会更新.*玩法正文.*策划草图.*最终文档/s);
  assert.equal(card.querySelector("input").getAttribute("type"), "radio");
  assert.match(card.textContent, /自己填写/);
  assert.match(card.textContent, /暂时跳过/);
  card.querySelector('[value="level"]').checked = true;
  card.querySelector(".planner-decision-apply").dispatch("click");
  assert.deepEqual(operations[0], [{ type: "resolve_decision_card", chapterId: current.id, cardId: "GDC-001", selectedOptionIds: ["level"], customValue: "" }]);
});

test("bare unknown text is not shown as a fake decision card", () => {
  const current = chapter({ unknowns: ["触发方式待确认"], decisionCards: [] });
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  assert.equal(root.querySelector(".planner-decision-card"), null);
  assert.doesNotMatch(root.textContent, /需要判断的内容|新增待确认项|触发方式待确认/);
});

test("resolved planner decisions appear in the visible rule body", () => {
  const current = chapter({ plannerSections: { summary: "升级时出现强化选择。", normalFlow: ["玩家选择一项强化。"], keyRules: ["强化触发方式：击败当前波次后出现"] } });
  const { root } = renderDom({ chapters: [current], evidenceAnchors: [], reviewState: { findings: [] } }, { selectedChapterId: current.id });
  assert.match(root.textContent, /关键规则.*强化触发方式：击败当前波次后出现/s);
});
