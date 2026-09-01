const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const StageReview = require("../../js/stage-review.js");

test("planner copy translates model annotations and boss terms before display", () => {
  assert.equal(StageReview.plannerText("Boss受到攻击（inferred from damage numbers）"), "首领受到攻击（根据伤害数字推测）");
  assert.equal(StageReview.plannerText("unknown"), "待确认");
  assert.equal(StageReview.plannerText("玩家移动，鼠标指针位于屏幕下方，可能点击技能"), "玩家移动，可能点击技能");
  assert.equal(StageReview.plannerText("未知待确认（根据首领血量推测，战斗可能刚开始或处于中段）"), "请确认：战斗是否刚开始，还是处于中段");
});

test("next-step confirmation asks one planner-readable yes-or-no question", () => {
  const stage = { name: "持续战斗并击退敌人" };
  const target = { name: "查看战斗状态" };

  assert.deepEqual(StageReview.transitionDecisionCopy(stage, target, { triggerType: "tap" }), {
    question: "完成“持续战斗并击退敌人”后，下一步是否进入“查看战斗状态”？",
    yes: "是，进入“查看战斗状态”",
    no: "否，这不是下一步",
    trigger: "玩家点按后",
  });
});

test("planner steps preserve the fixed causal reading order", () => {
  const stage = {
    entryCondition: "升级菜单尚未打开",
    trigger: "玩家点击升级按钮",
    systemResponse: "弹出三个武器选项并高亮可选项",
    exitCondition: "玩家可以选择一种强化",
    unresolvedQuestions: ["是否允许重复选择同一武器？"],
  };
  const steps = StageReview.plannerSteps({ regions: [] }, stage);
  assert.deepEqual(steps.map((step) => step.title), ["操作前", "玩家操作", "系统反馈", "操作结果"]);
  assert.equal(steps[1].content, "玩家点击升级按钮");
  assert.deepEqual(steps[3].questions, ["是否允许重复选择同一武器？"]);
});

test("page review edits map to existing revisioned page and four-step operations", () => {
  const stage = {
    id: "STG-001",
    name: "旧页面",
    entryCondition: "旧操作前",
    smallLoop: { display: "旧概述", trigger: "旧操作", feedback: "旧反馈", result: "旧结果", retry: "保留重试规则" },
  };

  assert.deepEqual(StageReview.stageEditOperations(stage, {
    title: "人工页面标题",
    before: "人工操作前",
    action: "人工玩家操作",
    feedback: "人工系统反馈",
    result: "人工操作结果",
  }), [
    { type: "set", entity: "stage", id: "STG-001", field: "name", value: "人工页面标题" },
    { type: "set", entity: "stage", id: "STG-001", field: "entryCondition", value: "人工操作前" },
    {
      type: "set_small_loop", id: "STG-001",
      smallLoop: { display: "旧概述", trigger: "人工玩家操作", feedback: "人工系统反馈", result: "人工操作结果", retry: "保留重试规则" },
    },
  ]);
  const source = fs.readFileSync("js/stage-review.js", "utf8");
  for (const label of ["策划确认与修改", "修改内容会用于策划草图中的页面名称、页面功能和页面流转。", "页面名称", "操作前", "玩家操作", "系统反馈", "操作结果", "保存修改"]) {
    assert.match(source, new RegExp(label));
  }
  assert.doesNotMatch(source, /修改页面名称与四步说明/);
  assert.doesNotMatch(source, />[^<]*(?:stage|transition|small loop)[^<]*</i);
});

test("planner copy converts internal unknown values into Chinese questions", () => {
  const steps = StageReview.plannerSteps({}, { trigger: "unknown" });
  assert.equal(steps[1].content, "需要补充玩家如何触发这一步");
  assert.doesNotMatch(JSON.stringify(steps), /unknown|component|entryCondition|exitCondition/i);
});

test("planner copy never exposes legacy English-only analysis", () => {
  const steps = StageReview.plannerSteps({}, { trigger: "tap", systemResponse: "feedback", exitCondition: "result" });
  assert.deepEqual(steps.slice(1).map((step) => step.content), ["点击对应入口", "展示操作反馈", "进入操作完成后的状态"]);
  assert.doesNotMatch(steps.map((step) => step.content).join(" "), /tap|feedback|result/i);
});

test("stage summary uses six Chinese labels and maps unknown to pending", () => {
  assert.deepEqual(StageReview.stageSummary({
    name: "武器选择",
    objective: "unknown",
    entryCondition: "点击武器栏",
    smallLoop: { trigger: "点击卡片", feedback: "弹出三选一", result: "装备武器" },
  }, [{ name: "武器卡" }]), [
    { label: "页面/环节名称", value: "武器选择" },
    { label: "当前目标", value: "待确认" },
    { label: "如何进入", value: "点击武器栏" },
    { label: "用户操作或自动触发", value: "点击卡片" },
    { label: "系统反馈与结果", value: "弹出三选一；装备武器" },
    { label: "关键组件", value: "武器卡" },
  ]);
});

test("component detail opens only for the selected component or its numbered region", () => {
  const model = { components: [{ id: "CMP-1", stageId: "STG-1", regionId: "REG-1" }] };

  assert.equal(StageReview.selectedComponent(model, "STG-1", { type: "component", id: "CMP-1" }).id, "CMP-1");
  assert.equal(StageReview.selectedComponent(model, "STG-1", { type: "region", id: "REG-1" }).id, "CMP-1");
  assert.equal(StageReview.selectedComponent(model, "STG-2", { type: "component", id: "CMP-1" }), null);
  assert.equal(StageReview.selectedComponent(model, "STG-1", null), null);
});

test("moving and resizing boxes stays normalized and inside the screenshot", () => {
  assert.deepEqual(StageReview.clampBounds({ x: -0.2, y: 0.8, width: 0.5, height: 0.4 }), { x: 0, y: 0.6, width: 0.5, height: 0.4 });
  assert.deepEqual(StageReview.resizeBounds({ x: 0.2, y: 0.2, width: 0.3, height: 0.3 }, "se", { dx: 0.8, dy: 0.8 }), { x: 0.2, y: 0.2, width: 0.8, height: 0.8 });
});

test("display numbers change while stable ids remain", () => {
  const result = StageReview.renumberRegions([{ id: "REG-B", displayOrder: 2 }, { id: "REG-A", displayOrder: 1 }]);
  assert.deepEqual(result.map((item) => [item.id, item.displayNumber]), [["REG-A", 1], ["REG-B", 2]]);
});

test("canonical stage numbers survive frame filtering and reorder targets stay global", () => {
  const model = { regions: [
    { id: "REG-A", stageId: "STG-001", frameId: "F1", displayOrder: 1 },
    { id: "REG-B", stageId: "STG-001", frameId: "F2", displayOrder: 2 },
    { id: "REG-C", stageId: "STG-001", frameId: "F1", displayOrder: 3 },
  ] };
  assert.deepEqual(StageReview.stageRegions(model, "STG-001").map((item) => [item.id, item.displayNumber]), [["REG-A", 1], ["REG-B", 2], ["REG-C", 3]]);
  assert.deepEqual(StageReview.regionsFor(model, "STG-001", "F1").map((item) => [item.id, item.displayNumber]), [["REG-A", 1], ["REG-C", 3]]);
  assert.equal(StageReview.regionReorderIndex(model, "STG-001", "REG-C", -1), 1);
});

test("one to three representative frames preserve explicit roles", () => {
  const sources = { F1: {}, F2: {}, F3: {}, F4: {} };
  const selected = StageReview.representativeFrames([{ frameId: "F1", role: "entry" }, { frameId: "F2", role: "change" }, { frameId: "F3", role: "result" }], sources);
  assert.equal(selected.valid, true);
  assert.equal(StageReview.representativeFrames([], sources).valid, false);
  assert.equal(StageReview.representativeFrames([{ frameId: "F1", role: "entry" }, { frameId: "F1", role: "result" }], sources).valid, false);
  assert.equal(StageReview.representativeFrames([{ frameId: "F1", role: "entry" }, { frameId: "F2", role: "entry" }], sources).valid, false);
  assert.equal(StageReview.representativeFrames([{ frameId: "F1", role: "entry" }, { frameId: "F2", role: "change" }], sources).valid, false);
  assert.equal(StageReview.representativeFrames([...selected.frames, { frameId: "F4", role: "result" }], sources).valid, false);
});

test("a seeded representative can be replaced atomically without an empty intermediate state", () => {
  const sources = { F1: {}, F2: {}, F3: {} };
  assert.deepEqual(
    StageReview.representativeFrameChange([{ frameId: "F1", role: "entry" }], "F2", "entry", sources),
    { valid: true, frames: [{ frameId: "F2", role: "entry" }] },
  );
  assert.deepEqual(
    StageReview.representativeFrameChange([{ frameId: "F1", role: "entry" }, { frameId: "F2", role: "result" }], "F3", "result", sources),
    { valid: true, frames: [{ frameId: "F1", role: "entry" }, { frameId: "F3", role: "result" }] },
  );
  assert.deepEqual(
    StageReview.representativeFrameOperation("STG-001", [{ frameId: "F1", role: "entry" }], "F2", "entry", sources),
    { type: "replace_representative_frame", id: "STG-001", oldFrameId: "F1", frame: { frameId: "F2", role: "entry" } },
  );
});

test("only representative frames are editable annotation surfaces", () => {
  const stage = { representativeFrames: [{ frameId: "F1", role: "entry" }] };
  assert.equal(StageReview.canAnnotateFrame(stage, "F1", false), true);
  assert.equal(StageReview.canAnnotateFrame(stage, "F2", false), false);
  assert.equal(StageReview.canAnnotateFrame(stage, "F1", true), false);
});

test("phase-one rules retain every GVE16 component state slot", () => {
  assert.deepEqual(StageReview.missingStateSlots({ default: "shown" }), ["pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet"]);
});

test("keyboard resize and accessible default creation stay inside the screenshot", () => {
  assert.deepEqual(StageReview.resizeByKey({ x: 0.2, y: 0.2, width: 0.3, height: 0.3 }, "e", "ArrowRight", { shiftKey: true }), { x: 0.2, y: 0.2, width: 0.4, height: 0.3 });
  assert.deepEqual(StageReview.defaultBounds(), { x: 0.4, y: 0.4, width: 0.2, height: 0.2 });
});

test("stage image ratio uses source dimensions and falls back to loaded natural dimensions", () => {
  assert.equal(StageReview.sourceAspectRatio({ width: 528, height: 986 }), "528 / 986");
  assert.equal(StageReview.sourceAspectRatio({}), null);
  assert.equal(StageReview.naturalAspectRatio({ naturalWidth: 528, naturalHeight: 986 }), "528 / 986");
});

test("mobile review tabs provide roving keyboard navigation", () => {
  assert.equal(StageReview.mobileTabIndex(0, "ArrowRight"), 1);
  assert.equal(StageReview.mobileTabIndex(1, "ArrowLeft"), 0);
  assert.equal(StageReview.mobileTabIndex(1, "Home"), 0);
  assert.equal(StageReview.mobileTabIndex(0, "End"), 1);
  assert.equal(StageReview.mobileTabIndex(0, "Enter"), null);
});

test("mobile panel accessibility state is cleared on a desktop viewport", () => {
  assert.equal(StageReview.panelAriaHidden(0, 1, true), "true");
  assert.equal(StageReview.panelAriaHidden(1, 1, true), "false");
  assert.equal(StageReview.panelAriaHidden(0, 1, false), "false");
  assert.equal(StageReview.panelAriaHidden(1, 1, false), "false");
});

test("keyboard resize handle stops propagation and submits exactly one operation", () => {
  const operations = [];
  const event = { key: "ArrowRight", shiftKey: false, prevented: false, stopped: false, preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; } };
  const workspace = { readOnly: false, onOperation(batch) { operations.push(...batch); } };

  StageReview.handleResizeKey(event, { id: "REG-001", bounds: { x: 0.2, y: 0.2, width: 0.3, height: 0.3 } }, "e", workspace);
  if (!event.stopped) workspace.onOperation([{ type: "set_region_bounds", id: "REG-001", bounds: { x: 0.21, y: 0.2, width: 0.3, height: 0.3 } }]);

  assert.equal(event.prevented, true);
  assert.equal(event.stopped, true);
  assert.deepEqual(operations, [{ type: "set_region_bounds", id: "REG-001", bounds: { x: 0.2, y: 0.2, width: 0.31, height: 0.3 } }]);
});

test("pointer cancellation and blur clean up without committing", () => {
  const listeners = new Map(); const blurListeners = new Map(); const target = { captured: [], released: [], setPointerCapture(id) { this.captured.push(id); }, releasePointerCapture(id) { this.released.push(id); } };
  const blurSurface = { addEventListener(name, handler) { blurListeners.set(name, handler); }, removeEventListener(name, handler) { if (blurListeners.get(name) === handler) blurListeners.delete(name); } };
  const surface = { defaultView: blurSurface, addEventListener(name, handler) { listeners.set(name, handler); }, removeEventListener(name, handler) { if (listeners.get(name) === handler) listeners.delete(name); } };
  let commits = 0; let cancels = 0;
  StageReview.pointerSession({ pointerId: 7, currentTarget: target }, { commit: () => { commits += 1; }, cancel: () => { cancels += 1; } }, surface);
  listeners.get("pointercancel")({ pointerId: 7 });
  assert.deepEqual({ commits, cancels, captured: target.captured, released: target.released, listeners: listeners.size }, { commits: 0, cancels: 1, captured: [7], released: [7], listeners: 0 });
  StageReview.pointerSession({ pointerId: 8, currentTarget: target }, { commit: () => { commits += 1; }, cancel: () => { cancels += 1; } }, surface);
  blurListeners.get("blur")();
  assert.deepEqual({ commits, cancels, released: target.released, listeners: listeners.size, blurListeners: blurListeners.size }, { commits: 0, cancels: 2, released: [7, 8], listeners: 0, blurListeners: 0 });
});

test("resize handles are keyboard-focusable buttons and new regions have a button alternative", () => {
  const source = fs.readFileSync("js/stage-review.js", "utf8");
  assert.match(source, /el\("button", "", \{ class: `stage-region-handle/);
  assert.match(source, /新增区域/);
});

test("mobile stage review exposes picture and rule tabs while Delete removes the selected editable region", () => {
  const source = fs.readFileSync("js/stage-review.js", "utf8");
  assert.match(source, /stage-mobile-tabs/);
  assert.match(source, /event\.key === "Delete"/);
  assert.match(source, /type: "delete_region"/);
});

test("the interaction workspace only asks about real multi-branch decisions", () => {
  const source = fs.readFileSync("js/stage-review.js", "utf8");
  assert.match(source, /outgoing\.length > 1/);
  assert.match(source, /确认分支去向/);
  assert.match(source, /否，这不是下一步/);
  assert.match(source, /set_transition_included/);
});

test("stage review does not confuse a static screenshot with a static player action", () => {
  const copy = StageReview.plannerText("未知待确认（当前帧为静态展示，未捕捉到点击或滑动操作）");
  assert.equal(copy, "待确认：需结合相邻画面或视频确认玩家操作");
  assert.doesNotMatch(copy, /静态展示|未捕捉到/);
});

test("planner copy converts punctuation-only model failures into a readable pending label", () => {
  assert.equal(StageReview.plannerText("', ."), "待确认");
  assert.equal(StageReview.plannerText("'' : '', ''."), "待确认");
});

test("saving an unchanged page does not invalidate completed review", () => {
  const stage = { id: "STG-001", name: "选择武器", entryCondition: "进入升级状态", smallLoop: { display: "查看三个选项", trigger: "点击一个选项", feedback: "选项生效", result: "返回战斗", retry: "可以刷新" } };
  assert.deepEqual(StageReview.stageEditOperations(stage, { title: "选择武器", before: "进入升级状态", action: "点击一个选项", feedback: "选项生效", result: "返回战斗" }), []);
});

test("exclusive branch selection disables siblings in one operation batch", () => {
  const transitions = [
    { id: "TRN-1", choiceGroupId: "CHOICE-STG-1", choiceMode: "exclusive", included: true },
    { id: "TRN-2", choiceGroupId: "CHOICE-STG-1", choiceMode: "exclusive", included: false },
    { id: "TRN-3", included: true },
  ];
  assert.deepEqual(StageReview.exclusiveBranchOperations(transitions, "TRN-2"), [
    { type: "set_transition_included", id: "TRN-1", included: false },
    { type: "set_transition_included", id: "TRN-2", included: true },
  ]);
});

test("every stage screenshot is listed with its own classification and information", () => {
  const model = { sources: {
    F1: { stageId: "STG-1", materialRole: "independent_page", pageInfo: { purpose: "战斗主界面" } },
    F2: { stageId: "STG-1", materialRole: "supplemental", pageInfo: { purpose: "升级后的补充状态" } },
    F3: { stageId: "STG-2", materialRole: "independent_page" },
  } };
  assert.deepEqual(StageReview.stageSourceIds(model, "STG-1"), ["F1", "F2"]);
  assert.equal(StageReview.materialRoleLabel("supplemental"), "补充画面");
  assert.equal(StageReview.frameInformation(model.sources.F2).purpose, "升级后的补充状态");
});

test("screenshot information replaces punctuation-only legacy output with planner guidance", () => {
  const info = StageReview.frameInformation({ pageInfo: { action: "'' : '', .", feedback: "unknown" } });
  assert.equal(info.action, "需要补充玩家操作或自动触发条件");
  assert.equal(info.feedback, "需要补充系统反馈");
});

test("selected screenshot keeps the evidence drawer open after rerender", () => {
  assert.equal(StageReview.evidenceOpen("F0002", ["F0001", "F0002"]), true);
  assert.equal(StageReview.evidenceOpen("F0003", ["F0001", "F0002"]), false);
  assert.equal(StageReview.evidenceOpen(null, ["F0001"]), false);
});
