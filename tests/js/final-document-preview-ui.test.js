const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const FinalDocumentPreview = require("../../js/final-document-preview.js");

class FakeNode {
  constructor(tag = "div") { this.tagName = tag.toUpperCase(); this.children = []; this.className = ""; this.attributes = {}; this.textContent = ""; this.style = {}; this.disabled = false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  matches(selector) { return selector.startsWith(".") ? this.className.split(" ").includes(selector.slice(1)) : this.tagName === selector.toUpperCase(); }
  querySelectorAll(selector) { return this.children.flatMap((child) => child instanceof FakeNode ? [child, ...child.querySelectorAll(selector)] : []).filter((node) => node.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const document = { createElement: (tag) => new FakeNode(tag), getElementById: () => null };
const readyChecks = ["语言与表述", "内容颗粒度", "玩法目录", "交互审核", "策划草图", "竞品参考", "规则审核", "图解审核", "参数审核", "策划决策", "交付一致性"].map((label) => ({ label, detail: "已完成", done: true }));
const readySteps = ["AI理解", "玩法目录", "交互审核", "规则审核", "图解审核", "参数审核", "文档导出"].map((label) => ({ label, done: true }));
const passedAudits = {
  granularityAudit: { passed: true, findings: [], chapters: [] },
  languageAudit: { passed: true, findings: [], chapters: [] },
  completionSnapshot: { ready: true, percent: 100, checks: readyChecks, steps: readySteps },
};

test("P7 source keeps the target document hierarchy and Chinese publishing actions", () => {
  const source = fs.readFileSync("js/final-document-preview.js", "utf8");
  assert.match(source, /文档概述/);
  assert.match(source, /第\$\{groupIndex \+ chapterOffset\}章/);
  assert.match(source, /导出到飞书/);
  assert.match(source, /导出到飞书/);
  assert.doesNotMatch(source, /"Connected"|"scope:"/);
});

test("P7 keeps rule sequences intact and never publishes diagram placement narration", () => {
  const source = fs.readFileSync("js/final-document-preview.js", "utf8");
  assert.doesNotMatch(source, /diagram\.placement\?\.followUp/);
  assert.doesNotMatch(source, /afterFlowIndex/);
  assert.match(source, /appendFlow\(doc, section, normalFlow\);\s*anchoredDiagrams\.forEach\(renderDiagram\)/s);
});

test("P7 uses target editorial typography and natural wrapping", () => {
  const css = fs.readFileSync("css/gameplay-tables.css", "utf8");
  assert.match(css, /\.final-document-shell\s*\{[^}]*font-family:\s*"PingFang SC",\s*"Microsoft YaHei"/s);
  assert.match(css, /\.final-document-content\s*\{[^}]*font-size:\s*14px/s);
  assert.match(css, /\.final-document-(paragraph|rule-value)[^{]*\{[^}]*overflow-wrap:\s*anywhere/s);
});

test("P7 real data state renders missing chapters, logs and all publish actions", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document,
    preview: { documentTitle: "完整策划案", interactionRevision: 2, gameplayRevision: 3, analysisNote: "已确认内容" },
    model: { systems: [{ name: "战斗系统", subsystems: [{ name: "核心战斗", chapterIds: ["C1", "C2"] }] }], chapters: [{ id: "C1", scope: "移动机制", summary: "玩家控制载具移动。", confirmation: { confirmed: true } }, { id: "C2", scope: "怪物刷新", summary: "", confirmation: { confirmed: false } }], tables: [], diagrams: [] },
    interaction: { stages: [{ id: "S1" }] }, view: { exportDisabled: true }, completion: { progress: 88, missingChapters: [{ id: "C2", title: "怪物刷新" }], logs: [{ message: "玩法目录已确认" }, { message: "规则说明已生成" }] },
  });
  assert.equal(root.querySelector(".final-document-missing").textContent, "怪物刷新：内容需要补充后才能发布");
  assert.equal(root.querySelector(".final-document-log").children.length, 2);
  assert.equal(root.querySelector(".final-document-resolve").textContent, "处理未完成项");
  assert.equal(root.querySelectorAll(".final-document-feishu-action").length, 0);
});

test("P7 keeps one unambiguous Feishu action after the document is complete", () => {
  const calls = [];
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: { documentTitle: "策划案", interactionRevision: 1, gameplayRevision: 1, ...passedAudits }, model: { chapters: [{ id: "C1", scope: "核心战斗", summary: "规则完整", confirmation: { confirmed: true } }], systems: [], tables: [{ id: "T1", status: "reviewed" }], diagrams: [], diagramReview: { noDiagramChapterIds: ["C1"] } }, interaction: { stages: [{ id: "S1", confirmation: { confirmed: true }, representativeFrames: [{ frameId: "F1" }] }], sources: { F1: { imageUrl: "frame.png", pageInfo: { action: "点击开始" } } } }, view: { exportDisabled: false }, onMarkdown: () => calls.push("markdown"), onExport: () => calls.push("export"), onPublish: () => calls.push("publish") });
  root.querySelector(".final-document-markdown").onclick(); root.querySelector(".final-document-feishu-action").onclick();
  assert.deepEqual(calls, ["markdown", "export"]);
  assert.equal(root.querySelectorAll(".final-document-feishu-action").length, 1);
  assert.equal(root.querySelector(".final-document-publish"), null);
  assert.doesNotMatch(root.textContent, /undefined/);
});

test("P7 real completeness gate blocks publish when a chapter is unconfirmed", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, model: { chapters: [{ id: "C1", scope: "规则", confirmation: { confirmed: false } }], systems: [], tables: [], diagrams: [] }, interaction: { stages: [] }, view: { exportDisabled: false } });
  assert.equal(root.querySelector(".final-document-feishu-action"), null);
  assert.equal(root.querySelector(".final-document-resolve").disabled, false);
});

test("P7 incomplete action uses its blocker callback instead of the generic return-to-edit action", () => {
  const calls = [];
  const root = new FakeNode();
  FinalDocumentPreview.render({
    root, document, preview: {},
    model: { chapters: [{ id: "C1", scope: "规则", confirmation: { confirmed: false } }], systems: [], tables: [], diagrams: [] },
    interaction: { stages: [{ confirmation: { confirmed: true } }] },
    view: { exportDisabled: true },
    onBack: () => calls.push("back"),
    onResolveIncomplete: () => calls.push("blocker"),
  });
  root.querySelector(".final-document-resolve").onclick();
  assert.deepEqual(calls, ["blocker"]);
});

test("P7 exposes unresolved planner decisions without publishing them as document conclusions", () => {
  const root = new FakeNode(); const operations = [];
  FinalDocumentPreview.render({ root, document, preview: {}, model: { chapters: [{ id: "C1", scope: "强化触发", confirmation: { confirmed: true }, decisionCards: [{ id: "GDC-001", question: "强化如何触发？", status: "pending", options: [{ id: "auto", label: "升级后自动触发" }, { id: "manual", label: "玩家手动打开" }], impacts: ["玩法正文", "最终文档"] }] }], systems: [], tables: [], diagrams: [] }, interaction: { stages: [{ confirmation: { confirmed: true } }] }, view: { exportDisabled: false }, onDecisionOperation: batch => operations.push(batch) });
  assert.ok(root.querySelector(".planner-decision-card"));
  assert.doesNotMatch(root.querySelector(".final-document-content").textContent, /升级后自动触发|玩家手动打开/);
  root.querySelectorAll("input")[0].checked = true;
  root.querySelector(".planner-decision-apply").onclick();
  assert.equal(operations[0][0].type, "resolve_decision_card");
  assert.equal(root.querySelector(".final-document-feishu-action"), null);
});

test("P7 pending action shows the real decision count and targets the first unresolved card", () => {
  const root = new FakeNode(); const targets = [];
  FinalDocumentPreview.render({ root, document, preview: {}, model: { chapters: [
    { id: "C1", confirmation: { confirmed: true }, decisionCards: [{ id: "D1", status: "pending", question: "第一项", options: [{ id: "a" }, { id: "b" }] }] },
    { id: "C2", confirmation: { confirmed: true }, decisionCards: [{ id: "D2", status: "skipped", question: "第二项", options: [{ id: "a" }, { id: "b" }] }] },
  ], systems: [], tables: [], diagrams: [] }, interaction: { stages: [{ confirmation: { confirmed: true } }] }, view: { exportDisabled: true }, onResolvePending: target => targets.push(target) });
  const action = root.querySelector(".final-document-resolve");
  assert.equal(action.textContent, "处理 2 项策划决策");
  action.onclick();
  assert.deepEqual(targets, [{ chapterId: "C1", cardId: "D1" }]);
});

test("P7 requires at least one confirmed interaction stage before export", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, model: { chapters: [{ id: "C1", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [] }, interaction: { stages: [] }, view: { exportDisabled: false } });
  assert.equal(root.querySelector(".final-document-feishu-action"), null);
  assert.equal(root.querySelector(".final-document-ready").textContent, "● 完善中");
});

test("P7 chapter toolbar exposes real previous and next controls instead of decorative copy", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, model: { chapters: [{ id: "C1", scope: "第一节", confirmation: { confirmed: true } }, { id: "C2", scope: "第二节", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [] }, interaction: { stages: [{ confirmation: { confirmed: true } }] }, view: { exportDisabled: false } });
  assert.equal(root.querySelector(".final-document-prev").tagName, "BUTTON");
  assert.equal(root.querySelector(".final-document-next").tagName, "BUTTON");
  assert.equal(root.querySelector(".final-document-fullscreen").tagName, "BUTTON");
  assert.doesNotMatch(root.querySelector(".final-document-toolbar").textContent, /适配/);
});

test("P7 incomplete checks use a neutral hollow marker instead of a green success badge", () => {
  const css = fs.readFileSync(require("node:path").join(__dirname, "../../css/gameplay-tables.css"), "utf8");
  assert.match(css, /final-document-check\.is-incomplete b\s*\{[^}]*background:\s*transparent[^}]*color:\s*#9aa0ab/s);
});

test("P7 status checks only show green completion for actually finished sections", () => {
  const root = new FakeNode();
  const checks = readyChecks.map((item, index) => ({ ...item, done: ![2, 3, 5].includes(index), detail: [2, 3, 5].includes(index) ? "未完成" : "已完成" }));
  FinalDocumentPreview.render({ root, document, preview: { completionSnapshot: { ready: false, percent: 70, checks, steps: readySteps.map((item, index) => ({ ...item, done: index < 2 })) } }, model: { chapters: Array.from({ length: 18 }, (_, index) => ({ id: `C${index}`, confirmation: { confirmed: index < 15 } })), tables: [], diagrams: [] }, interaction: { stages: [] }, view: { exportDisabled: true }, completion: { progress: 80 } });
  const renderedChecks = root.querySelectorAll(".final-document-check");
  assert.equal(renderedChecks[2].querySelector("b").textContent, "○");
  assert.equal(renderedChecks[3].querySelector("b").textContent, "○");
  assert.equal(renderedChecks[5].querySelector("b").textContent, "○");
  assert.equal(root.querySelector(".final-document-score").querySelector("strong").textContent, "70%");
});

test("P7 marks document export as the current page while incomplete steps remain pending", () => {
  const root = new FakeNode();
  const steps = readySteps.map((item, index) => ({ ...item, done: index < 3 }));
  FinalDocumentPreview.render({ root, document, preview: { completionSnapshot: { ready: false, percent: 45, checks: readyChecks, steps } }, model: { chapters: [], tables: [], diagrams: [] }, interaction: { stages: [] }, view: { exportDisabled: true } });
  const rendered = root.querySelectorAll(".final-document-step");
  assert.equal(rendered.some((node) => node.className.includes("is-active")), false);
  assert.match(rendered.at(-1).className, /is-current/);
  assert.equal(rendered.at(-1).attributes["aria-current"], "step");
  assert.match(rendered[3].className, /is-pending/);
});

test("P7 final chapter preserves the confirmed rule depth instead of collapsing to one sentence", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, interaction: { stages: [{ confirmation: { confirmed: true } }] }, view: { exportDisabled: false }, model: {
    systems: [{ name: "战斗系统", subsystems: [{ name: "伤害规则", chapterIds: ["C1"] }] }],
    chapters: [{ id: "C1", scope: "伤害计算", summary: "攻击命中后按属性与倍率结算伤害。", confirmation: { confirmed: true },
      plannerSections: { normalPlay: ["锁定有效目标", "命中后进入伤害结算"], validation: ["用视频伤害数字与实现录屏对照"], edgeCases: ["目标无效时不结算"] },
      claims: [{ text: "基础伤害由攻击属性与武器倍率共同决定" }],
      formulae: [{ name: "基础伤害", expression: "攻击属性 × 武器倍率" }],
      parameters: { 攻击属性: { value: 100, type: "整数", unit: "点", source: "属性配置" } },
      acceptanceCases: [{ case: "普通命中", expected: "扣减对应生命值" }],
    }], tables: [], diagrams: [],
  }});
  for (const heading of ["正常怎么玩", "关键规则", "参与计算的字段", "计算公式", "怎么验证", "特殊情况", "计算示例", "配置来源"]) {
    assert.equal(root.querySelectorAll("h4").some((node) => node.textContent === heading), false, `unexpected template heading ${heading}`);
  }
  assert.match(root.querySelector(".final-document-formula").textContent, /攻击属性 × 武器倍率/);
  assert.equal(root.querySelector(".final-document-parameter-table"), null);
});

test("P7 presents concise nearby parameter names and removes suggestion copy after adoption", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: passedAudits, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "载具生存", confirmation: { confirmed: true }, fieldDictionary: [{
      plannerName: "载具当前生命值", suggestedCodeName: "vehicleCurrentHp", type: "整数", unit: "点",
      source: "竞品截图可见信息", status: "建议命名，待程序或配置表确认",
    }, {
      plannerName: "武器名称", suggestedCodeName: "weaponName", type: "文本", source: "策划采用",
      status: "confirmed", decisionStatus: "accepted",
    }] }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [{ id: "S1", confirmation: { confirmed: true } }] } });
  const mapping = root.querySelector(".final-document-parameter-naming");
  assert.match(mapping.children[0].textContent, /载具当前生命值/);
  assert.match(mapping.children[0].textContent, /vehicleCurrentHp/);
  assert.match(mapping.children[0].textContent, /建议/);
  assert.doesNotMatch(mapping.children[0].textContent, /整数|竞品截图|待程序或配置表确认/);
  assert.equal(mapping.children[1].textContent, "武器名称：weaponName");
  assert.equal(root.querySelector(".final-document-parameter-table"), null);
});

test("P7 keeps boundary rules outside the parameter naming block", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: passedAudits, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "终极强化", ruleHeading: "词条生效范围", confirmation: { confirmed: true }, plannerSections: {
      summary: "终极词条会改变武器攻击逻辑。",
      normalFlow: ["满足终极强化条件。", "展示终极词条。", "选择后应用对应效果。"],
      specialCases: ["伤害降低 20% 只属于对应词条，不能推广为所有终极强化。"],
    }, fieldDictionary: [
      { plannerName: "终极喷射方向数", suggestedCodeName: "ultimateDirectionCount", status: "suggested" },
      { plannerName: "终极词条伤害修正", suggestedCodeName: "ultimateDamageModifier", status: "suggested" },
    ] }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [{ id: "S1", confirmation: { confirmed: true } }] } });
  const chapter = root.querySelector(".final-document-chapter");
  const naming = chapter.querySelector(".final-document-parameter-naming");
  assert.equal(naming.children.length, 2);
  assert.doesNotMatch(naming.children.map((node) => node.textContent).join("\n"), /伤害降低 20%/);
  assert.equal(chapter.querySelectorAll("h4").some((node) => node.textContent === "词条生效范围"), true);
  assert.equal(chapter.children.indexOf(chapter.querySelectorAll("h4").find((node) => node.textContent === "词条生效范围")) < chapter.children.indexOf(naming), true);
});

test("P7 gives a deep mechanism semantic subheadings derived from its chapter", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "武器攻击", ruleHeading: "索敌与伤害结算", confirmation: { confirmed: true }, plannerSections: {
      summary: "武器自动攻击范围内敌人。",
      normalFlow: ["搜索目标。", "确认目标在射程内。", "执行攻击并结算伤害。"],
      keyRules: ["目标离开射程时不造成伤害。"],
    } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const chapter = root.querySelector(".final-document-chapter");
  assert.deepEqual(chapter.querySelectorAll("h4").map((node) => node.textContent), ["武器攻击流程", "索敌与伤害结算"]);
  assert.equal(chapter.querySelectorAll("h4").some((node) => node.textContent === "规则与边界"), false);
});

test("P7 places a relevant screenshot beside the mechanism instead of a detached evidence gallery", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: passedAudits, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "首领阶段", confirmation: { confirmed: true }, inlineFigures: [
      { frameId: "F11", caption: "首领来袭警告用于说明普通战斗切换到首领阶段。" },
    ], plannerSections: { summary: "达到首领条件后切换阶段。", normalFlow: ["播放首领来袭警告。", "进入首领战。"] } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [], sources: { F11: { frameId: "F11", imageUrl: "/frames/F11.jpg" } } } });
  const figure = root.querySelector(".final-document-inline-figure");
  assert.ok(figure);
  assert.equal(figure.querySelector("img").src, "/frames/F11.jpg");
  assert.match(figure.querySelector("figcaption").textContent, /首领来袭警告/);
  assert.equal(root.querySelector(".final-document-evidence-gallery"), null);
});

test("P7 never leaks internal frame ids from evidence claims into confirmed planner copy", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: passedAudits, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "首领战", confirmation: { confirmed: true },
      plannerSections: { summary: "首领登场后进入独立战斗阶段。", normalFlow: ["显示首领预警。", "进入首领战。", "首领生命值归零后进入结算。"], keyRules: ["首领具有多种攻击表现，但素材不足以确认轮换顺序。"] },
      claims: [{ text: "首领展示F0012机械臂、F0013雷电和F0014分裂攻击。" }],
      mechanism: { type: "custom", description: "画面F0012、F0013、F0014分别展示不同攻击。" },
    }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [{ id: "S1", confirmation: { confirmed: true } }] } });
  const collect = node => [node.textContent, ...(node.children || []).map(collect)].join("\n");
  assert.doesNotMatch(collect(root.querySelector(".final-document-content")), /F\d{4}/);
});

test("P7 exports confirmed interaction flows before gameplay chapters", () => {
  global.ExportPreview = { sanitizeBoardSvg: (value) => value };
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, interactionPreview: { boardPreviewSvg: "<svg><text>选择强化</text></svg>" }, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "核心战斗", summary: "持续攻击敌人", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: {
    stages: [{ id: "S1", title: "选择强化", pagePurpose: "供玩家选择本次强化", playerAction: "点击一张强化卡片", systemFeedback: "高亮所选卡片", operationResult: "关闭弹窗并返回战斗", confirmation: { confirmed: true } }],
    transitions: [{ sourceStageId: "S1", targetStageId: "S2", triggerLabel: "点击强化卡片" }],
    sources: { F1: { id: "F1", stageId: "S1", imageUrl: "/frames/F1.jpg" } },
  }});
  assert.equal(root.querySelectorAll(".final-document-interaction-stage").length, 0);
  assert.equal(root.querySelectorAll(".final-document-planning-board-canvas").length, 1);
  const headings = root.querySelectorAll(".final-document-h1").map((node) => node.textContent);
  assert.ok(headings.indexOf("策划草图") < headings.indexOf("其他玩法"));
  assert.equal(headings.includes("交互与页面流程"), false);
});

test("P7 derives interaction copy from the canonical stage and transition schema without pending filler", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: passedAudits, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: {
    stages: [{ id: "S1", name: "进入首领战", objective: "展示首领预警并进入战斗", entryCondition: "关卡时间达到首领节点", exitCondition: "首领战正式开始", smallLoop: { display: "待确认", trigger: "待确认" }, confirmation: { confirmed: true } }],
    transitions: [{ sourceStageId: "S1", targetStageId: null, triggerLabel: "系统自动触发首领预警", response: "显示红色预警遮罩", resultState: "进入首领战" }], sources: {},
  }});
  assert.equal(root.querySelectorAll(".final-document-interaction-stage").length, 0);
  assert.equal(root.querySelector(".final-document-planning-board").querySelector(".final-document-h1").textContent, "策划草图");
});

test("P7 directory groups are real collapsible controls", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: passedAudits, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "核心战斗", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [{ id: "S1", title: "战斗主页", confirmation: { confirmed: true } }] } });
  const toggles = root.querySelectorAll(".final-document-toc-toggle");
  assert.ok(toggles.length >= 2);
  const panel = toggles[0].tocPanel;
  assert.equal(toggles[0].attributes["aria-expanded"], "true");
  toggles[0].onclick();
  assert.equal(toggles[0].attributes["aria-expanded"], "false");
  assert.equal(panel.hidden, true);
  toggles[0].onclick();
  assert.equal(panel.hidden, false);
});

test("P7 omits model-configuration placeholders from the published interaction copy", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [{ id: "S1", name: "升级选择", objective: "需要配置视觉模型后识别", confirmation: { confirmed: true } }] } });
  assert.doesNotMatch(root.querySelector(".final-document-planning-board").textContent, /需要配置视觉模型/);
});

test("P7 previous and next controls switch from the planning board to gameplay sections", () => {
  const visited = [];
  const navigationDocument = {
    createElement: (tag) => new FakeNode(tag),
    getElementById: (id) => ({ scrollIntoView: () => visited.push(id) }),
  };
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document: navigationDocument, preview: {}, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "核心战斗", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [{ id: "S1", title: "持续战斗", confirmation: { confirmed: true } }, { id: "S2", title: "选择强化", confirmation: { confirmed: true } }] } });
  root.querySelector(".final-document-next").onclick();
  assert.equal(visited.at(-1), "final-doc-C1");
  root.querySelector(".final-document-prev").onclick();
  assert.equal(visited.at(-1), "final-doc-planning-board");
});

test("P7 confirmed interaction text is ready without an optional source image", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: { completionSnapshot: { ready: false, percent: 90, checks: readyChecks.map((item) => item.label === "交互审核" ? { ...item, detail: "1/1 环节" } : item), steps: readySteps } }, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "核心战斗", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: {
    stages: [{ id: "S1", title: "进入首领战", objective: "展示首领预警并进入战斗", entryCondition: "关卡到达首领节点", confirmation: { confirmed: true } }],
    transitions: [{ sourceStageId: "S1", triggerLabel: "系统自动触发预警", response: "显示首领预警遮罩", resultState: "进入首领战" }],
    sources: {},
  }});
  const check = root.querySelectorAll(".final-document-check").find((item) => item.querySelector("span")?.textContent === "交互审核");
  assert.ok(check);
  assert.match(check.querySelector("small").textContent, /1\/1/);
  assert.equal(check.querySelector("b").textContent, "✓");
});

test("P7 shows 100 percent and the sole Feishu action when every visible audit row is complete", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: passedAudits, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "强化选择", summary: "选择强化后立即生效", confirmation: { confirmed: true } }],
    systems: [], tables: [{ id: "T1", status: "reviewed", rows: [] }], diagrams: [], diagramReview: { noDiagramChapterIds: ["C1"] },
  }, interaction: { stages: [{ id: "S1", objective: "选择一项强化", confirmation: { confirmed: true } }] }, completion: { status: "idle", missingChapters: [] } });
  assert.equal(root.querySelector(".final-document-score").querySelector("strong").textContent, "100%");
  assert.equal(root.querySelectorAll(".final-document-feishu-action").length, 1);
  assert.equal(root.querySelectorAll(".final-document-resolve").length, 0);
});

test("P7 blocks export when either real audit report is absent", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: false }, model: {
    chapters: [{ id: "C1", scope: "强化选择", confirmation: { confirmed: true } }],
    systems: [], tables: [{ id: "T1", status: "reviewed", rows: [] }], diagrams: [], diagramReview: { noDiagramChapterIds: ["C1"] },
  }, interaction: { stages: [{ id: "S1", objective: "选择强化", confirmation: { confirmed: true } }] }, completion: { missingChapters: [] } });

  assert.equal(root.querySelectorAll(".final-document-feishu-action").length, 0);
  assert.match(root.querySelector(".final-document-granularity-gaps").children[0].textContent, /尚未获得真实内容颗粒度审核结果/);
  assert.match(root.querySelector(".final-document-language-gaps").children[0].textContent, /尚未获得真实语言与表述审核结果/);
});

test("P7 exposes the real sample-alignment basis instead of a generic passed label", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, view: { exportDisabled: false }, preview: {
    ...passedAudits,
    sampleAlignment: { chapters: [{ chapterId: "C1", title: "奖励候选", granularity: [
      { label: "执行顺序", status: "satisfied", basis: "来源 DOC-21 要求的执行顺序事实均已写入正文。" },
      { label: "公式依据", status: "not_applicable", basis: "素材没有提供概率或计算表达式。" },
    ] }] },
  }, model: {
    chapters: [{ id: "C1", scope: "奖励候选", confirmation: { confirmed: true } }], systems: [],
    tables: [{ id: "T1", status: "reviewed", rows: [] }], diagrams: [], diagramReview: { noDiagramChapterIds: ["C1"] },
  }, interaction: { stages: [{ id: "S1", objective: "选择奖励", confirmation: { confirmed: true } }] }, completion: { missingChapters: [] } });

  const rows = root.querySelectorAll(".final-document-alignment-row");
  assert.equal(rows.length, 2);
  assert.match(rows[0].textContent, /执行顺序：已覆盖/);
  assert.match(rows[0].textContent, /DOC-21/);
  assert.match(rows[1].textContent, /公式依据：不适用/);
  assert.match(rows[1].textContent, /没有提供概率或计算表达式/);
});

test("P7 blocks export and explains an evidence-conditioned granularity gap in planner language", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, view: { exportDisabled: false }, preview: {
    granularityAudit: { passed: false, findings: [{ chapterId: "C1", axis: "lifecycle", message: "《载具移动》已有生命周期依据，但正文尚未写出生命周期。" }] },
  }, model: {
    chapters: [{ id: "C1", scope: "载具移动", summary: "载具沿路线前进。", confirmation: { confirmed: true } }],
    systems: [], tables: [{ id: "T1", status: "reviewed", rows: [] }], diagrams: [], diagramReview: { noDiagramChapterIds: ["C1"] },
  }, interaction: { stages: [{ id: "S1", objective: "控制载具", confirmation: { confirmed: true } }] }, completion: { missingChapters: [] } });

  assert.equal(root.querySelectorAll(".final-document-feishu-action").length, 0);
  assert.match(root.querySelector(".final-document-granularity-gaps").children[0].textContent, /已有生命周期依据/);
  assert.doesNotMatch(root.querySelector(".final-document-granularity-gaps").textContent, /GRANULARITY_/);
});

test("P7 blocks export and shows language comparison findings without internal codes", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, view: { exportDisabled: false }, preview: {
    languageAudit: { passed: false, findings: [{ chapterId: "C1", code: "LANGUAGE_FILLER", message: "《载具移动》存在没有新增业务信息的开场或总结句。" }] },
  }, model: {
    chapters: [{ id: "C1", scope: "载具移动", confirmation: { confirmed: true } }], systems: [],
    tables: [{ id: "T1", status: "reviewed", rows: [] }], diagrams: [], diagramReview: { noDiagramChapterIds: ["C1"] },
  }, interaction: { stages: [{ id: "S1", objective: "控制载具", confirmation: { confirmed: true } }] }, completion: { missingChapters: [] } });

  assert.equal(root.querySelectorAll(".final-document-feishu-action").length, 0);
  assert.match(root.querySelector(".final-document-language-gaps").children[0].textContent, /没有新增业务信息/);
  assert.doesNotMatch(root.querySelector(".final-document-language-gaps").textContent, /LANGUAGE_FILLER/);
});

test("P7 does not repeat the same gameplay sentence in flow and key rules", () => {
  const root = new FakeNode();
  const sentence = "武器无需手动瞄准，自动攻击射程内敌人。";
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "自动攻击", confirmation: { confirmed: true }, plannerSections: { normalFlow: [sentence] }, claims: [{ label: "规则", text: sentence }] }],
    systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const mergedCopy = root.querySelector(".final-document-merged-rule").textContent;
  assert.equal(mergedCopy.split(sentence).length - 1, 1);
});

test("P7 never substitutes review-state filler for missing gameplay copy", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "生命值状态管理", confirmation: { confirmed: true }, claims: [{ text: "载具生命归零时本局失败。" }] }],
    systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const copy = root.querySelectorAll(".final-document-paragraph").map((node) => node.textContent).join("\n");
  assert.doesNotMatch(copy, /本节规则已完成审核/);
  assert.match(copy, /载具生命归零时本局失败/);
});

test("P7 renders a distinct player-view gameplay overview from the confirmed directory understanding", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    directory: { understanding: { summary: "玩家控制载具推进关卡，通过战斗获得强化并击败首领。", playerGoal: "击败关卡首领", basicControls: "横向移动并选择强化", coreLoop: "战斗、升级、继续推进", completion: "击败首领", failure: "载具生命归零" } },
    chapters: [{ id: "C1", scope: "核心战斗", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const overview = root.querySelector(".final-document-gameplay-overview");
  assert.equal(overview.querySelector("h1").textContent, "玩法概述");
  assert.deepEqual(overview.querySelectorAll("dt").map((node) => node.textContent), ["玩家目标", "基础操作", "核心循环", "怎样获胜", "怎样失败"]);
  assert.deepEqual(overview.querySelectorAll("dd").map((node) => node.textContent).slice(0, 2), ["击败关卡首领", "横向移动并选择强化"]);
});

test("P7 renders labeled gameplay overview lines as separate paragraphs", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    directory: { understanding: { summary: "核心目标：击败首领。\n\n基础操作：横向移动。\n\n核心循环：战斗、强化、推进。\n\n胜败条件：击败首领获胜，生命归零失败。", playerGoal: "击败首领" } },
    chapters: [{ id: "C1", scope: "核心战斗", confirmation: { confirmed: true } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const overview = root.querySelector(".final-document-gameplay-overview");
  assert.deepEqual(
    overview.querySelectorAll(".final-document-overview-line").map((node) => node.textContent),
    ["核心目标：击败首领。", "基础操作：横向移动。", "核心循环：战斗、强化、推进。", "胜败条件：击败首领获胜，生命归零失败。"],
  );
});

test("P7 preserves explicit configuration sources and worked examples without an audit table", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "载具等级", confirmation: { confirmed: true },
      parameterSchema: [{ name: "等级", plannerMeaning: "载具当前等级", type: "整数", unit: "级", defaultValue: 1, range: "1~20", configurationSource: "GveMagicBookVehicle._id" }],
      configurationSources: [{ title: "载具配置表", field: "GveMagicBookVehicle" }],
      workedExamples: [{ name: "升级算例", expression: "1级升级到2级消耗100道具" }],
    }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const chapter = root.querySelector(".final-document-chapter");
  assert.equal(chapter.querySelectorAll("h4").some((node) => node.textContent === "需要配置的数值"), false);
  assert.equal(chapter.querySelector(".final-document-parameter-table"), null);
  assert.equal(chapter.textContent.includes("GveMagicBookVehicle._id"), false);
  assert.ok(chapter.querySelectorAll("li").some((node) => /载具配置表.*GveMagicBookVehicle/.test(node.textContent)));
  assert.ok(chapter.querySelectorAll("li").some((node) => /升级算例.*1级升级到2级消耗100道具/.test(node.textContent)));
});

test("P7 explains entity attributes in prose before the lookup table", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, model: { chapters: [{
    id: "C1", scope: "怪物作战", confirmation: { confirmed: true },
    plannerSections: { summary: "怪物按波次刷新。", normalFlow: ["开始波次。", "怪物刷新。", "怪物进入战斗。"], attributeSections: [{ heading: "承伤、攻击与移动", items: ["生命值：由基础生命值乘以当前波次生命值倍率。", "闪避：先判定闪避，累计达到上限后下一次攻击必定命中。"] }] },
    parameterSchema: [{ name: "生命值", plannerMeaning: "当前可承受伤害", defaultValue: "按波次计算" }],
  }], systems: [], tables: [], diagrams: [] }, interaction: { stages: [{ confirmation: { confirmed: true } }] }, view: { exportDisabled: true } });
  const chapter = root.querySelector(".final-document-chapter");
  const attribute = chapter.querySelector(".final-document-attribute-section");
  assert.equal(attribute.querySelector("h4").textContent, "承伤、攻击与移动");
  assert.match(attribute.querySelector("li").textContent, /基础生命值乘以当前波次生命值倍率/);
  assert.ok(chapter.querySelectorAll(".final-document-attribute-section").length === 1);
});

test("P7 renders a sparse mechanism as natural rule copy without a repeated form template", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "载具移动", summary: "载具自动向前，玩家负责横向调整位置。", confirmation: { confirmed: true }, plannerSections: { normalFlow: ["拖动摇杆后，载具在可移动范围内横向移动。"] } }],
    systems: [{ name: "核心战斗", subsystems: [{ name: "角色控制", chapterIds: ["C1"] }] }], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const chapter = root.querySelector(".final-document-chapter");
  assert.equal(chapter.querySelectorAll("h4").length, 0);
  assert.match(chapter.querySelector(".final-document-merged-rule").textContent, /拖动摇杆/);
  assert.equal(chapter.querySelectorAll("li").length, 0);
});

test("P7 keeps structured subheadings only for a genuinely deep mechanism", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "伤害计算", summary: "命中后按攻击和倍率结算。", confirmation: { confirmed: true }, plannerSections: { normalFlow: ["命中有效目标后进入结算。"], specialCases: ["目标无效时不结算。"] }, formulae: [{ name: "基础伤害", expression: "攻击×倍率" }], acceptanceCases: [{ case: "普通命中", expected: "扣减生命值" }] }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const headings = root.querySelector(".final-document-chapter").querySelectorAll("h4").map((node) => node.textContent);
  for (const heading of ["正常怎么玩", "关键规则", "计算公式", "怎么验证", "特殊情况"]) assert.equal(headings.includes(heading), false);
});

test("P7 renders one reviewed configuration table without repeating an inferred parameter table", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "载具等级", confirmation: { confirmed: true }, plannerSections: { summary: "玩家消耗升级道具提升载具等级。" }, parameterSchema: [{ name: "等级", defaultValue: 1, range: "1~20", configurationSource: "载具配置表" }] }],
    systems: [], diagrams: [], tables: [{ id: "T1", status: "reviewed", chapterIds: ["C1"], columns: ["字段", "默认值", "范围", "来源"], rows: [["等级", "1", "1~20", "载具配置表"]] }],
  }, interaction: { stages: [] } });
  assert.equal(root.querySelector(".final-document-chapter").querySelectorAll("table").length, 1);
});

test("P7 collapses a confirmed audit table into parameter and confirmed value", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "强化选择", confirmation: { confirmed: true } }], systems: [], diagrams: [],
    tables: [{ id: "T1", status: "reviewed", chapterIds: ["C1"], columns: ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"], rows: [
      ["火焰射击范围", "百分比（%）", "30", "30", "已确认", "确认"],
      ["雷暴枪伤害", "百分比（%）", "80", "100", "已确认", "确认"],
    ] }],
  }, interaction: { stages: [] } });
  const table = root.querySelector(".final-document-chapter").querySelector("table");
  assert.deepEqual(table.querySelectorAll("th").map((node) => node.textContent), ["参数", "确认值"]);
  assert.deepEqual(table.querySelector("tbody").children.map((row) => row.children.map((cell) => cell.textContent)), [["火焰射击范围", "30%"], ["雷暴枪伤害", "100%"]]);
});

test("P7 numbers a real multi-step sequence under a chapter-derived flow heading", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "升级选择", confirmation: { confirmed: true }, plannerSections: { summary: "达到条件后完成一次强化选择。", normalFlow: ["暂停战斗。", "生成候选。", "选择强化。", "继续战斗。"] } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const chapter = root.querySelector(".final-document-chapter");
  assert.equal(chapter.querySelector("ol").children.length, 4);
  assert.equal(chapter.querySelector("h4").textContent, "升级选择流程");
});

test("P7 and Feishu use the confirmed planner summary instead of stale legacy chapter copy", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "刷新机制", summary: "旧模板摘要不应继续显示。", confirmation: { confirmed: true }, plannerSections: {
      summary: "玩家消耗已确认的刷新资源后替换本轮候选内容。",
      normalFlow: ["玩家发起刷新后，系统重新生成本轮候选内容。"],
    } }], systems: [], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const copy = root.querySelector(".final-document-chapter").textContent
    + root.querySelector(".final-document-chapter").querySelectorAll("p").map((node) => node.textContent).join("\n");
  assert.match(copy, /玩家消耗已确认的刷新资源后替换本轮候选内容/);
  assert.doesNotMatch(copy, /旧模板摘要不应继续显示/);
  assert.match(root.querySelector(".final-document-one-liner").textContent, /玩家消耗已确认的刷新资源后替换本轮候选内容/);
  assert.doesNotMatch(root.querySelector(".final-document-one-liner").textContent, /旧模板摘要不应继续显示/);
});

test("P7 merges several sparse mechanisms into one business section", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    directory: { understanding: { summary: "玩家控制载具推进关卡并在战斗中保持生存。" } },
    chapters: [
      { id: "C1", scope: "载具移动机制", confirmation: { confirmed: true }, plannerSections: { summary: "载具自动前进，玩家负责横向调整位置。", normalFlow: ["拖动后，载具在可移动范围内横向移动。"] } },
      { id: "C2", scope: "生命值状态管理", confirmation: { confirmed: true }, plannerSections: { summary: "载具受到伤害时扣减生命值，生命归零后本局失败。", keyRules: ["无效攻击不会扣减生命值。"] } },
    ],
    systems: [{ name: "核心战斗", subsystems: [{ name: "载具控制", chapterIds: ["C1"] }, { name: "生存规则", chapterIds: ["C2"] }] }], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const reader = root.querySelector(".final-document-scroll");
  assert.equal(reader.querySelectorAll("h1").some((node) => node.textContent === "玩法概述"), false);
  assert.ok(reader.querySelectorAll("h1").some((node) => /核心战斗/.test(node.textContent)));
  assert.equal(reader.querySelectorAll("h2").length, 0);
  assert.equal(reader.querySelectorAll("h3").length, 0);
  const mergedCopy = reader.querySelectorAll(".final-document-merged-rule").map((node) => node.textContent).join("\n");
  assert.match(mergedCopy, /载具移动：.*载具自动前进/);
  assert.match(mergedCopy, /生命值：.*生命归零后本局失败/);
  assert.equal(reader.querySelectorAll(".final-document-chapter ul").length, 0);
});

test("P7 keeps a genuinely deep mechanism as its own subsection", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "伤害结算", confirmation: { confirmed: true }, plannerSections: { summary: "命中后结算伤害。", normalFlow: ["确认目标。", "读取攻击属性。", "应用武器倍率。", "扣减目标生命值。"] }, formulae: [{ name: "最终伤害", expression: "攻击属性 × 武器倍率" }] }],
    systems: [{ name: "核心战斗", subsystems: [{ name: "战斗结算", chapterIds: ["C1"] }] }], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  const reader = root.querySelector(".final-document-scroll");
  assert.ok(reader.querySelectorAll("h2").some((node) => /战斗结算/.test(node.textContent)));
  assert.ok(reader.querySelectorAll("h3").some((node) => node.textContent === "伤害结算"));
});
test("P7 merges a redundant chapter title into the object title and business subgroups", () => {
  const root = new FakeNode();
  FinalDocumentPreview.render({ root, document, preview: {}, view: { exportDisabled: true }, model: {
    chapters: [{ id: "C1", scope: "载具", confirmation: { confirmed: true }, plannerSections: {
      summary: "载具承担推进与战斗。", normalFlow: ["载具进入战斗。", "载具持续推进。", "载具承受伤害。"],
      attributeHeading: "载具", attributeSections: [{ heading: "承伤与武器换算", items: ["生命值：受击后扣减。"] }],
    } }], systems: [{ name: "核心战斗", subsystems: [{ name: "载具", chapterIds: ["C1"] }] }], tables: [], diagrams: [],
  }, interaction: { stages: [] } });
  assert.ok(root.querySelectorAll("h3").some((node) => node.textContent === "载具"));
  assert.ok(root.querySelectorAll("h4").some((node) => node.textContent === "承伤与武器换算"));
  assert.equal(root.querySelectorAll("h3").some((node) => node.textContent === "战场推进与载具生存"), false);
  assert.ok(root.querySelectorAll(".final-document-toc-item").some((node) => node.textContent === "载具"));
  assert.ok(root.querySelectorAll(".final-document-toc-leaf").some((node) => node.textContent === "承伤与武器换算"));
  assert.ok(root.querySelectorAll("h3").some((node) => node.attributes.id === "final-doc-C1-attribute-object-0"));
  assert.ok(root.querySelectorAll("h4").some((node) => node.attributes.id === "final-doc-C1-attribute-group-0"));
});
