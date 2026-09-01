const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const FlowReview = require("../../js/flow-review.js");

test("flow copy hides punctuation-only visual model failures", () => {
  assert.equal(FlowReview.plannerText("', ."), "待确认");
});

test("flow copy translates model annotations before display", () => {
  assert.equal(FlowReview.plannerText("BOSS释放攻击 (inferred from damage numbers)"), "首领释放攻击 （根据伤害数字推测）");
});

test("static screenshot evidence is not presented as a static player action", () => {
  const copy = FlowReview.plannerText("未知待确认（当前帧为静态展示，未捕捉到点击或滑动操作）");
  assert.equal(copy, "待策划选择操作");
  assert.doesNotMatch(copy, /静态展示|未捕捉到/);
});

test("unknown interaction action is rendered as a decision card with one selectable operation", () => {
  const source = fs.readFileSync("js/flow-review.js", "utf8");
  assert.match(source, /data-interaction-decision-card/);
  assert.match(source, /选择这一步的实际操作/);
  assert.match(source, /resolve_interaction_decision_card/);
  assert.match(source, /skip_interaction_decision_card/);
  assert.match(source, /请先选择一种操作，或填写真实操作/);
});

test("candidate transitions group by source and retain automatic triggers", () => {
  const groups = FlowReview.groupCandidates([
    { id: "TRN-001", sourceStageId: "STG-001", triggerType: "tap", included: true },
    { id: "TRN-002", sourceStageId: "STG-001", triggerType: "animation_end", included: false },
  ]);
  assert.deepEqual(groups.map((group) => [group.stageId, group.items.length]), [["STG-001", 2]]);
});

test("click anchor clamps inside the normalized component box", () => {
  const anchor = FlowReview.anchorFromPointer(
    { x: 900, y: 50 },
    { left: 0, top: 0, width: 1000, height: 2000 },
    { x: 0.1, y: 0.2, width: 0.4, height: 0.3 },
  );
  assert.deepEqual(anchor, { x: 0.5, y: 0.2 });
});

test("automatic transitions never render an anchor editor", () => {
  assert.equal(FlowReview.canEditAnchor({ triggerType: "animation_end" }), false);
  assert.equal(FlowReview.canEditAnchor({ triggerType: "tap", componentId: "CMP-001" }), true);
});

test("visible lane only includes included transitions in stage order", () => {
  const lane = FlowReview.visibleLane({
    stages: [{ id: "STG-002", order: 2 }, { id: "STG-001", order: 1 }],
    transitions: [
      { id: "TRN-001", sourceStageId: "STG-001", included: true },
      { id: "TRN-002", sourceStageId: "STG-001", included: false },
    ],
  });
  assert.deepEqual(lane.map((stage) => [stage.id, stage.transitions.map((item) => item.id)]), [["STG-001", ["TRN-001"]], ["STG-002", []]]);
});

test("single-stage transition draft is terminal without a target", () => {
  const draft = FlowReview.newTransitionDraft({ stages: [{ id: "STG-001", order: 1, representativeFrames: [{ frameId: "F0001" }] }] });
  assert.deepEqual({ targetStageId: draft.targetStageId, resultType: draft.resultType }, { targetStageId: null, resultType: "terminal" });
});

test("anchor bounds reject a bound component from another stage or frame", () => {
  [{ stageId: "STG-002", frameId: "F0001" }, { stageId: "STG-001", frameId: "F0002" }].forEach((binding) => {
    const model = { components: [{ id: "CMP-001", ...binding, bounds: { x: 0.1, y: 0.1, width: 0.2, height: 0.2 } }] };
    assert.equal(FlowReview.anchorBounds(model, { componentId: "CMP-001", sourceStageId: "STG-001", sourceFrameId: "F0001" }), null);
  });
});

test("stage lane is a horizontally scrolling nowrap rail", () => {
  const css = fs.readFileSync("css/review-workspace.css", "utf8");
  assert.match(css, /\.flow-stage-lane\s*\{[^}]*grid-auto-flow:\s*column[^}]*overflow-x:\s*auto/s);
  assert.match(css, /\.flow-stage-card\s*\{[^}]*width:\s*min\(/s);
});

test("existing constraint edits preserve the canonical text field", () => {
  assert.deepEqual(
    FlowReview.constraintDraft({ id: "CNS-001", text: "old", severity: "non_core", status: "unknown" }, { text: "new", severity: "core", status: "observed" }),
    { id: "CNS-001", text: "new", severity: "core", status: "observed" },
  );
});

test("P2 maps evidence into the contained screenshot and rejects wrong markers", () => {
  assert.deepEqual(FlowReview.containedImageRect({ width: 256, height: 480 }, { x: 12, y: 12, width: 256, height: 320 }), { x: 54.66666666666667, y: 12, width: 170.66666666666666, height: 320 });
  assert.deepEqual(FlowReview.mapEvidenceBox({ x: .25, y: .5, width: .5, height: .25 }, { x: 55, y: 12, width: 170, height: 320 }), { left: 97.5, top: 172, width: 85, height: 80 });
  assert.equal(FlowReview.validEvidenceAnchor({ x: .8, y: .8 }, { x: .1, y: .1, width: .2, height: .2 }), false);
});

test("P2 only selects screenshots owned by the current stage", () => {
  const model = { sources: { F1: { stageId: "S2" }, F2: { stageId: "S1", pageInfo: { purpose: "武器选择页面" } } } };
  assert.deepEqual(FlowReview.sourceForStage(model, { id: "S1", name: "选择武器", representativeFrames: [{ frameId: "F1" }, { frameId: "F2" }] }), { frameId: "F2", source: model.sources.F2 });
});

test("P2 prioritizes transition evidence and never reuses a frame for another semantic node", () => {
  const model = { sources: { F1: { stageId: "S1", pageInfo: { purpose: "武器选择" } }, F2: { stageId: "S1", pageInfo: { purpose: "武器选择" } } } };
  const stage = { id: "S1", name: "选择武器", representativeFrames: [{ frameId: "F1", role: "entry" }, { frameId: "F2", role: "result" }] };
  assert.equal(FlowReview.sourceForStage(model, stage, { sourceFrameId: "F2" }, new Set()).frameId, "F2");
  assert.equal(FlowReview.sourceForStage(model, stage, { sourceFrameId: "F2" }, new Set(["F2"])).frameId, "F1");
  assert.equal(FlowReview.sourceForStage(model, stage, {}, new Set(["F1", "F2"])).frameId, "");
});

test("P2 editor removes empty brackets and punctuation garbage", () => {
  assert.equal(FlowReview.plannerText("弹窗 '选择武器' (), : '火焰扩张' (), ."), "");
  assert.equal(FlowReview.plannerText("'刷新' (), ."), "");
});

test("P2 rejects a screenshot whose recognized page purpose does not support the node", () => {
  assert.equal(FlowReview.sourceSemanticallySupportsStage({ pageInfo: { purpose: "待确认" } }, { name: "选择武器强化" }), false);
  assert.equal(FlowReview.sourceSemanticallySupportsStage({ pageInfo: { purpose: "武器升级选择弹窗" } }, { name: "选择武器强化" }), true);
});

test("P2 never exposes manual coordinate capture and only renders existing anchors", () => {
  const source = fs.readFileSync("js/flow-review.js", "utf8");
  for (const token of ["interaction-coordinate-capture", "标记点击位置", "点击截图中的目标控件", "保存点击位置"]) assert.doesNotMatch(source, new RegExp(token));
  assert.match(source, /validEvidenceAnchor/);
});

test("P2 falls back to an owned stage frame without borrowing from another stage", () => {
  const model = { sources: {
    F1: { stageId: "S1", imageUrl: "/one.png", pageInfo: { purpose: "战斗画面" } },
    F2: { stageId: "S2", imageUrl: "/two.png", pageInfo: { purpose: "奖励选择" } },
  } };
  const result = FlowReview.sourceForStage(model, { id: "S1", name: "选择武器", representativeFrames: [{ frameId: "F1" }] });
  assert.equal(result.frameId, "F1");
  assert.equal(result.supplemental, true);
  assert.notEqual(result.frameId, "F2");
});
test("manual click capture ignores letterbox space outside the actual screenshot", () => {
  const rect = { x: 50, y: 10, width: 200, height: 300 };
  assert.equal(FlowReview.anchorFromImageClick({ x: 20, y: 100 }, rect), null);
  assert.deepEqual(FlowReview.anchorFromImageClick({ x: 150, y: 160 }, rect), { x: .5, y: .5 });
});

test("interaction review defaults to the first transition so its editor is never empty", () => {
  const transitions = [{ id: "TRN-001" }, { id: "TRN-002" }];
  assert.equal(FlowReview.selectedTransition(transitions, null)?.id, "TRN-001");
  assert.equal(FlowReview.selectedTransition(transitions, "TRN-002")?.id, "TRN-002");
});

test("formal interaction review derives one stage page from real stages sources and transitions", () => {
  const model = {
    stages: [
      { id: "STG-1", order: 1, name: "选择武器强化", entryCondition: "经验达到升级条件", representativeFrames: [{ frameId: "F1" }], smallLoop: { trigger: "点按一项强化", feedback: "所选属性立即提升", result: "关闭弹窗并继续战斗" } },
      { id: "STG-2", order: 2, name: "继续战斗" },
    ],
    sources: { F1: { stageId: "STG-1", imageUrl: "/jobs/demo/frames/F1.jpg" } },
    transitions: [{ id: "TRN-1", sourceStageId: "STG-1", targetStageId: "STG-2", sourceFrameId: "F1", included: true }],
  };
  const view = FlowReview.interactionStageView(model, "TRN-1");
  assert.equal(view.stage.name, "选择武器强化");
  assert.equal(view.frameId, "F1");
  assert.equal(view.source.imageUrl, "/jobs/demo/frames/F1.jpg");
  assert.deepEqual(view.steps.map(item => [item.title, item.content]), [
    ["操作前", "经验达到升级条件"],
    ["玩家操作", "点按一项强化"],
    ["系统反馈", "所选属性立即提升"],
    ["操作结果", "关闭弹窗并继续战斗"],
  ]);
});

test("interaction review fills sparse confirmed stages from their supporting screenshots instead of repeating pending", () => {
  const model = {
    stages: [
      { id: "STG-1", order: 1, name: "选择武器强化", representativeFrames: [{ frameId: "F1", role: "entry" }, { frameId: "F2", role: "result" }], smallLoop: { trigger: "待确认", feedback: "待确认", result: "待确认" } },
      { id: "STG-2", order: 2, name: "继续战斗" },
    ],
    sources: {
      F1: { stageId: "STG-1", pageInfo: { before: "待确认", action: "待确认", feedback: "待确认", result: "待确认" } },
      F2: { stageId: "STG-1", pageInfo: { before: "战斗暂停并打开强化选择界面", feedback: "系统保持强化选项可见，等待玩家选择", result: "选择完成后关闭弹窗" } },
    },
    transitions: [{ id: "TRN-1", sourceStageId: "STG-1", targetStageId: "STG-2", included: true, triggerType: "unknown", response: "', ." }],
  };
  const view = FlowReview.interactionStageView(model, "TRN-1");
  assert.deepEqual(view.steps.map((item) => item.content), [
    "战斗暂停并打开强化选择界面",
    "玩家选择武器强化",
    "系统保持强化选项可见，等待玩家选择",
    "选择完成后关闭弹窗",
  ]);
});

test("formal interaction page has target columns and removes candidate relationship cards", () => {
  const source = fs.readFileSync("js/flow-review.js", "utf8");
  const css = fs.readFileSync("css/style.css", "utf8");
  for (const token of ["interaction-stage-navigation", "interaction-stage-main", "interaction-flow-board", "interaction-flow-node", "interaction-stage-editor", "应用并查看下一环节"]) assert.match(source, new RegExp(token));
  assert.doesNotMatch(source.slice(source.indexOf("function render(workspace)")), /可能发生的下一步|候选关系|完整操作顺序/);
  assert.match(css, /\.interaction-review-target\s*\{[^}]*grid-template-columns:\s*220px\s+minmax\(0,\s*1fr\)\s+300px/s);
  assert.match(css, /\.interaction-flow-node-image\s*\{[^}]*object-fit:\s*contain/s);
  assert.match(css, /\.interaction-flow-node-rule[^}]*overflow-wrap:\s*anywhere/s);
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const router = backend.slice(backend.indexOf("function setReviewWorkspaceView"), backend.indexOf("function showReviewValidationError"));
  assert.doesNotMatch(router, /flowReviewView"\)\.hidden\s*=\s*true/);
});

test("P2 editor reserves an intrinsic row for wrapped transition evidence", () => {
  const css = fs.readFileSync("css/style.css", "utf8");
  assert.match(css, /\.interaction-stage-editor\s*\{[^}]*grid-template-rows:\s*auto\s+auto\s+auto\s+minmax\(0,\s*1fr\)\s+auto/s);
});

test("P2 follows the approved screenshot flow canvas contract", () => {
  const source = fs.readFileSync("js/flow-review.js", "utf8");
  const css = fs.readFileSync("css/style.css", "utf8");
  for (const token of ["interaction-flow-board", "interaction-flow-node", "interaction-flow-edge", "interaction-flow-node-image", "当前节点", "跳转依据", "适配画板"]) assert.match(source, new RegExp(token));
  assert.match(css, /\.interaction-flow-board\s*\{[^}]*overflow:\s*auto/s);
  assert.match(css, /\.interaction-flow-node-image\s*\{[^}]*object-fit:\s*contain/s);
  assert.doesNotMatch(source.slice(source.indexOf("function render(workspace)")), /interaction-stage-steps/);
  assert.match(source, /const nodeRule = explicitNodeRule\([^)]+\);\s*if \(nodeRule\) node\.append/s);
  assert.match(source, /function explicitNodeRule[\s\S]*请确认\|未知待确认\|待确认\|推测/);
  for (const token of ["interaction-flow-node-media", "interaction-flow-hotspot", "interaction-flow-gesture"]) assert.match(source, new RegExp(token));
  assert.match(source, /stageTransition\?\.anchor\s*&&\s*anchorBounds/);
  assert.match(css, /\.interaction-flow-connector-line\s*\{[^}]*stroke:/s);
  assert.doesNotMatch(FlowReview.plannerText("未知待确认（可能点击按钮）"), /请确认|未知待确认/);
  assert.equal(FlowReview.plannerText("未知待确认"), "");
});

test("P2 connectors start at the screenshot gesture, pass through player action, and end at the next screenshot", () => {
  const source = fs.readFileSync("js/flow-review.js", "utf8");
  const css = fs.readFileSync("css/style.css", "utf8");
  assert.match(source, /interaction-flow-connectors/);
  assert.match(source, /element\("span",\s*"👆",\s*\{\s*class:\s*"interaction-flow-gesture"/);
  assert.match(source, /drawFlowConnectors\(flow\)/);
  assert.match(source, /connectorPath\([^)]*gesture[^)]*edge[^)]*nextNode/);
  assert.match(source, /element\("strong",\s*"玩家操作"/);
  assert.doesNotMatch(source, /element\("strong",\s*"点击或操作"/);
  assert.match(css, /\.interaction-flow-connectors\s*\{[^}]*pointer-events:\s*none/s);
});

test("interaction editor maps changes back to the existing stage without internal labels", () => {
  const stage = { id: "STG-1", name: "旧名称", entryCondition: "旧状态", smallLoop: { display: "保留概述", trigger: "旧操作", feedback: "旧反馈", result: "旧结果", retry: "保留重置" } };
  assert.deepEqual(FlowReview.stageEditOperations(stage, { title: "新名称", before: "新状态", action: "新操作", feedback: "新反馈", result: "新结果" }), [
    { type: "set", entity: "stage", id: "STG-1", field: "name", value: "新名称" },
    { type: "set", entity: "stage", id: "STG-1", field: "entryCondition", value: "新状态" },
    { type: "set_small_loop", id: "STG-1", smallLoop: { display: "保留概述", trigger: "新操作", feedback: "新反馈", result: "新结果", retry: "保留重置" } },
  ]);
});

test("applying an interaction stage confirms it before selecting the next stage", () => {
  const source = fs.readFileSync("js/flow-review.js", "utf8");
  const applyHandler = source.slice(source.indexOf('const nextLabel = nextTransition'), source.indexOf("editor.append(footer)"));
  assert.match(applyHandler, /save\(\);\s*await onConfirmStage\?\.\(view\.stage\.id\);\s*if \(nextTransition\) onAdvanceStage/);
  assert.match(applyHandler, /nextTransition\s*\?\s*"应用并查看下一环节"\s*:\s*"应用并生成策划草图"/);
  assert.match(applyHandler, /disabled:\s*readOnly/);
  assert.doesNotMatch(applyHandler, /disabled:\s*readOnly\s*\|\|\s*!nextTransition/);
  const backend = fs.readFileSync("js/backend.js", "utf8");
  assert.match(backend, /onConfirmStage:\s*async\s*\(stageId\)\s*=>\s*\{[\s\S]*ReviewWorkspace\.selectStage\(state\.reviewWorkspace, model, stageId\);[\s\S]*await runReviewConfirmation\("stage"\)[\s\S]*setReviewWorkspaceView\("flow"\)[\s\S]*syncReviewViewUrl\("flow"\)/);
});

test("fit board is a real canvas reset action instead of a no-op button", () => {
  const source = fs.readFileSync("js/flow-review.js", "utf8");
  const handler = source.slice(source.indexOf('button("适配画板"'), source.indexOf('element("span", "原截图节点'));
  assert.match(handler, /board\.scrollTo/);
  assert.match(handler, /drawFlowConnectors\(flow\)/);
});
