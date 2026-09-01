const test = require("node:test");
const assert = require("node:assert/strict");
const UeFlowReview = require("../../js/ue-flow-review.js");

test("UE review rejects pending copy and projects confirmed topology", () => {
  const lines = UeFlowReview.pageCopy(
    { pageInfo: { purpose: "武器升级选择弹窗", action: "待确认" } },
    { id: "S2", name: "选择武器" },
    { id: "S1", name: "战斗" },
    { id: "S3", name: "继续战斗" },
    "F2",
  );
  assert.deepEqual(lines, [
    "页面职责：选择武器",
    "画面内容：武器升级选择弹窗",
    "由「战斗」进入本页",
    "完成本页后进入「继续战斗」",
  ]);
  assert.doesNotMatch(lines.join(""), /待确认/);
});

test("UE review chooses a semantically supported owned frame instead of the first representative frame", () => {
  const model = {
    transitions: [],
    sources: {
      F1: { stageId: "S1", imageUrl: "/wrong.jpg", pageInfo: { purpose: "待确认" } },
      F2: { stageId: "S1", imageUrl: "/right.jpg", pageInfo: { purpose: "武器升级选择弹窗" } },
    },
  };
  const stage = { id: "S1", name: "选择武器强化", representativeFrames: [{ frameId: "F1" }, { frameId: "F2" }] };
  assert.equal(UeFlowReview.authoritativeSource(model, stage).frameId, "F2");
});

test("UE review accepts an explicitly owned representative screenshot when legacy OCR lacks a page title", () => {
  const model = {
    transitions: [],
    sources: { F1: { stageId: "S1", imageUrl: "/owned.jpg", pageInfo: { purpose: "待确认" } } },
  };
  const stage = { id: "S1", name: "持续攻击首领", representativeFrames: [{ frameId: "F1" }] };
  assert.deepEqual(UeFlowReview.authoritativeSource(model, stage), {
    frameId: "F1", source: model.sources.F1, titleFromStage: true,
  });
});

test("UE review does not borrow a wrong screenshot when no trustworthy binding exists", () => {
  const model = { transitions: [], sources: { F1: { stageId: "S2", imageUrl: "/other.jpg", pageInfo: { purpose: "关卡结算" } } } };
  const stage = { id: "S1", name: "武器抽取", representativeFrames: [{ frameId: "F1" }] };
  assert.equal(UeFlowReview.authoritativeSource(model, stage).frameId, "");
});

test("UE review accepts one to four meaningful component annotations without forcing filler regions", () => {
  const components = [1, 2, 3].map(number => ({ number, name: `控件${number}`, purpose: `执行功能${number}`, anchor: { x: number / 5, y: .5 } }));
  const model = { stages: [{ id: "S1" }], sources: { F1: {} }, ueFlowAnnotations: { pages: [{ stageId: "S1", frameId: "F1", title: "选择页", components }] } };
  assert.equal(UeFlowReview.annotationPages(model).length, 1);
  model.ueFlowAnnotations.pages[0].components.push(...[4, 5].map(number => ({ number, name: `控件${number}`, purpose: `执行功能${number}`, anchor: { x: .5, y: .5 } })));
  assert.equal(UeFlowReview.annotationPages(model).length, 0);
  model.ueFlowAnnotations.pages[0].components.pop();
  model.ueFlowAnnotations.pages[0].components[0].purpose = "待确认";
  assert.equal(UeFlowReview.annotationPages(model).length, 0);
});

test("UE review exposes one readable challenge loop split into exhaustive stage groups", () => {
  const pages = [
    { id: "P1", stageId: "S1", frameId: "F1", title: "选择", components: [{ number: 1, name: "候选", purpose: "完成选择", anchor: { x: .5, y: .5 } }] },
    { id: "P2", stageId: "S2", frameId: "F2", title: "首领", components: [{ number: 1, name: "生命", purpose: "显示生命", anchor: { x: .5, y: .5 } }] },
    { id: "P3", stageId: "S3", frameId: "F3", title: "结算", components: [{ number: 1, name: "结果", purpose: "显示结果", anchor: { x: .5, y: .5 } }] },
  ];
  const model = {
    stages: [{ id: "S1" }, { id: "S2" }, { id: "S3" }], sources: { F1: {}, F2: {}, F3: {} },
    ueFlowAnnotations: { pages, transitions: [
      { id: "T1", sourcePageId: "P1", targetPageId: "P2" },
      { id: "T2", sourcePageId: "P2", targetPageId: "P3" },
      { id: "T3", sourcePageId: "P3", targetPageId: "P1" },
    ], loops: [{ id: "LOOP-1", title: "局内挑战循环", groups: [
      { id: "GROUP-1", title: "成长选择", stageIds: ["S1"], entryPageId: "P1", exitTransitionId: "T1" },
      { id: "GROUP-2", title: "首领战斗", stageIds: ["S2"], entryPageId: "P2", exitTransitionId: "T2" },
      { id: "GROUP-3", title: "结算返回", stageIds: ["S3"], entryPageId: "P3", exitTransitionId: "T3" },
    ] }] },
  };
  const loops = UeFlowReview.annotationLoops(model);
  assert.equal(loops[0].title, "局内挑战循环");
  assert.deepEqual(loops[0].groups.map(group => group.title), ["成长选择", "首领战斗", "结算返回"]);
  model.ueFlowAnnotations.loops[0].groups[2].stageIds = ["S2"];
  assert.deepEqual(UeFlowReview.annotationLoops(model), []);
});

test("UE annotation topology binds a real component to a target page and distinguishes return edges", () => {
  const model = {
    stages: [{ id: "S1" }, { id: "S2" }],
    sources: { F1: {}, F2: {} },
    ueFlowAnnotations: {
      pages: [
        { id: "P1", stageId: "S1", frameId: "F1", title: "选择页", components: [1,2,3,4].map(number => ({ number, name: `控件${number}`, purpose: `作用${number}`, anchor: { x: .2, y: .2 } })) },
        { id: "P2", stageId: "S2", frameId: "F2", title: "战斗页", components: [1,2,3,4].map(number => ({ number, name: `控件${number}`, purpose: `作用${number}`, anchor: { x: .2, y: .2 } })) },
      ],
      transitions: [
        { id: "T1", sourcePageId: "P1", targetPageId: "P2", triggerComponentNumber: 2, direction: "forward", condition: "选择一项" },
        { id: "T2", sourcePageId: "P2", targetPageId: "P1", triggerComponentNumber: 4, direction: "return", condition: "再次升级" },
      ],
    },
  };
  assert.deepEqual(UeFlowReview.annotationTransitions(model).map(item => [item.id, item.direction]), [["T1", "forward"], ["T2", "return"]]);
  model.ueFlowAnnotations.transitions[0].triggerComponentNumber = 9;
  assert.deepEqual(UeFlowReview.annotationTransitions(model).map(item => item.id), ["T2"]);
});

test("UE annotation topology supports an approved external return target without inventing a screenshot page", () => {
  const components = [1,2,3,4].map(number => ({ number, name: `控件${number}`, purpose: `作用${number}`, anchor: { x: .2, y: .2 } }));
  const model = {
    stages: [{ id: "S1" }], sources: { F1: {} },
    ueFlowAnnotations: {
      pages: [{ id: "P1", stageId: "S1", frameId: "F1", title: "结算", components }],
      externalTargets: [{ id: "EXT-LEVEL-ENTRY", title: "当前挑战的关卡入口页" }],
      transitions: [{ id: "T-RETURN", sourcePageId: "P1", targetExternalId: "EXT-LEVEL-ENTRY", triggerComponentNumber: 4, direction: "return", condition: "点击返回" }],
    },
  };
  assert.deepEqual(UeFlowReview.annotationTransitions(model), [{
    id: "T-RETURN", sourcePageId: "P1", targetExternalId: "EXT-LEVEL-ENTRY", triggerComponentNumber: 4,
    direction: "return", condition: "点击返回", targetTitle: "当前挑战的关卡入口页",
  }]);
});

test("UE annotation topology accepts named system triggers but rejects unnamed automatic edges", () => {
  const components = [{ number: 1, name: "提示", purpose: "显示阶段提示", anchor: { x: .5, y: .5 } }];
  const model = {
    stages: [{ id: "S1" }, { id: "S2" }], sources: { F1: {}, F2: {} },
    ueFlowAnnotations: {
      pages: [
        { id: "P1", stageId: "S1", frameId: "F1", title: "预警", components },
        { id: "P2", stageId: "S2", frameId: "F2", title: "战斗", components },
      ],
      transitions: [{ id: "T-SYSTEM", sourcePageId: "P1", targetPageId: "P2", triggerType: "system", triggerLabel: "预警展示完成", direction: "forward", condition: "生成首领" }],
    },
  };
  assert.deepEqual(UeFlowReview.annotationTransitions(model).map(item => item.id), ["T-SYSTEM"]);
  delete model.ueFlowAnnotations.transitions[0].triggerLabel;
  assert.deepEqual(UeFlowReview.annotationTransitions(model), []);
});
