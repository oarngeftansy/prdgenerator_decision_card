const test = require("node:test");
const assert = require("node:assert/strict");
const reviewer = require("../../js/frame-reviewer.js");

test("sortFrames orders every frame by timestamp without mutation and stays stable", () => {
  const input = [
    { id: "B", timestamp: 9 },
    { id: "A", timestamp: 1 },
    { id: "C", timestamp: 9 },
  ];
  assert.deepEqual(reviewer.sortFrames(input).map((item) => item.id), ["A", "B", "C"]);
  assert.deepEqual(input.map((item) => item.id), ["B", "A", "C"]);
});

test("moveIndex stops at first and last frame", () => {
  assert.equal(reviewer.moveIndex(0, -1, 3), 0);
  assert.equal(reviewer.moveIndex(2, 1, 3), 2);
  assert.equal(reviewer.moveIndex(1, 1, 3), 2);
  assert.equal(reviewer.moveIndex(0, 1, 0), 0);
});

test("findFrameIndex resolves id first and timestamp as fallback", () => {
  const frames = [{ id: "A", timestamp: 1 }, { id: "B", timestamp: 4 }];
  assert.equal(reviewer.findFrameIndex(frames, "B", 1), 1);
  assert.equal(reviewer.findFrameIndex(frames, "missing", 1), 0);
  assert.equal(reviewer.findFrameIndex([], "missing", 1), -1);
});

test("mode fields use distinct GVE16 plain-language labels", () => {
  const gameplay = reviewer.fieldsForMode("gameplay");
  const interaction = reviewer.fieldsForMode("interaction");
  const visible = [...gameplay, ...interaction].map((item) => item.label).join(" ");
  assert.match(visible, /玩家做了什么/);
  assert.match(visible, /当前是什么界面/);
  assert.notDeepEqual(gameplay, interaction);
  for (const term of ["default", "loading", "success", "error", "beforeState", "afterState", "component tree"])
    assert.doesNotMatch(visible, new RegExp(term, "i"));
});

test("isTextEditingTarget protects form fields and editable content", () => {
  assert.equal(reviewer.isTextEditingTarget({ tagName: "TEXTAREA" }), true);
  assert.equal(reviewer.isTextEditingTarget({ tagName: "INPUT" }), true);
  assert.equal(reviewer.isTextEditingTarget({ tagName: "SELECT" }), true);
  assert.equal(reviewer.isTextEditingTarget({ tagName: "DIV", isContentEditable: true }), true);
  assert.equal(reviewer.isTextEditingTarget({ tagName: "BUTTON" }), false);
});

test("filterFrames exposes plain-language review groups", () => {
  const frames = [
    { id: "A", timestamp: 1, confidence: "低", evidenceLevel: "明确展示", confirmed: true, gameState: "战斗", userAction: "移动" },
    { id: "B", timestamp: 2, confidence: "高", evidenceLevel: "未知待确认", confirmed: false, unknowns: "没有展示失败", gameState: "战斗", userAction: "攻击" },
    { id: "C", timestamp: 3, confidence: "高", evidenceLevel: "明确展示", confirmed: false, hasConflict: true, gameState: "战斗", userAction: "攻击" },
    { id: "D", timestamp: 4, confidence: "高", evidenceLevel: "明确展示", confirmed: true, gameState: "战斗", userAction: "攻击" },
    { id: "E", timestamp: 5, confidence: "高", evidenceLevel: "明确展示", confirmed: true, gameState: "", what: "", userAction: "攻击" },
  ];
  assert.deepEqual(reviewer.filterFrames(frames, "attention", "gameplay").map((frame) => frame.id), ["A", "C", "E"]);
  assert.deepEqual(reviewer.filterFrames(frames, "unknown").map((frame) => frame.id), ["B"]);
  assert.deepEqual(reviewer.filterFrames(frames, "unconfirmed").map((frame) => frame.id), ["B", "C"]);
  assert.deepEqual(reviewer.filterFrames(frames, "all").map((frame) => frame.id), ["A", "B", "C", "D", "E"]);
});

test("scene representative filter keeps one default review card per scene and prefers detail frames", () => {
  const frames = [
    { id: "A", timestamp: 1, sceneGroup: 0 },
    { id: "B", timestamp: 2, sceneGroup: 0, isDetailFrame: true },
    { id: "C", timestamp: 3, sceneGroup: 0 },
    { id: "D", timestamp: 4, sceneGroup: 1 },
    { id: "E", timestamp: 5, sceneGroup: 1 },
  ];
  assert.deepEqual(reviewer.filterFrames(frames, "scene_representatives").map((frame) => frame.id), ["B", "E"]);
});

test("attention uses mode-specific critical fields", () => {
  const completeInteraction = { id: "A", timestamp: 1, confidence: "高", what: "设置页", userAction: "点击保存", unknowns: "未展示弱网" };
  const missingAction = { id: "B", timestamp: 2, confidence: "高", what: "设置页", userAction: "" };
  assert.deepEqual(reviewer.filterFrames([completeInteraction, missingAction], "attention", "interaction").map((frame) => frame.id), ["B"]);
});

test("attentionReasons explains gameplay review needs in plain language and priority order", () => {
  const reasons = reviewer.attentionReasons({
    confidence: "低",
    hasConflict: true,
    gameState: "",
    userAction: "",
  }, "gameplay");
  assert.deepEqual(reasons, [
    { label: "前后结论不一致", suggestion: "请对照前后画面，确认操作和结果是否连贯。" },
    { label: "缺少玩家操作", suggestion: "请回看前后 2–3 秒，补充玩家做了什么。" },
    { label: "玩法目的不明确", suggestion: "请补充这一段在玩什么、玩家需要完成什么。" },
  ]);
  assert.equal(reasons.length, 3);
});

test("attentionReasons uses interaction wording and returns nothing for a complete frame", () => {
  assert.deepEqual(reviewer.attentionReasons({ confidence: "高", what: "设置页", userAction: "点击保存" }, "interaction"), []);
  assert.deepEqual(reviewer.attentionReasons({ confidence: "高", what: "", userAction: "" }, "interaction"), [
    { label: "缺少用户操作", suggestion: "请回看前后 2–3 秒，补充用户进行了什么操作。" },
    { label: "当前界面不明确", suggestion: "请补充当前是什么界面，以及界面的主要用途。" },
  ]);
});

test("attentionReasons describes low confidence without exposing model jargon", () => {
  const reasons = reviewer.attentionReasons({ confidence: "low", gameState: "战斗", userAction: "攻击", systemResponse: "敌人受击", afterState: "继续战斗" }, "gameplay");
  assert.deepEqual(reasons, [
    { label: "画面信息不足", suggestion: "请检查画面是否清楚，或回看相邻画面补足依据。" },
  ]);
  assert.doesNotMatch(JSON.stringify(reasons), /confidence|gameState|userAction/i);
});

test("attentionReasons replaces a vague low-confidence warning with specific evidence problems", () => {
  assert.deepEqual(reviewer.attentionReasons({
    confidence: "低", gameState: "战斗", userAction: "攻击",
    unknowns: ["该帧继承场景摘要，未进行独立视觉模型分析。"],
  }, "gameplay"), [
    { label: "关键操作可能发生在两帧之间", suggestion: "建议补取前后画面，确认操作发生的准确时刻。" },
    { label: "操作结果没有画面证明", suggestion: "请补取操作后的画面，确认系统反馈和最终状态。" },
  ]);
});

test("attentionReasons maps controlled model signals to planner language", () => {
  const reasons = reviewer.attentionReasons({
    confidence: "高", gameState: "战斗", userAction: "攻击", systemResponse: "爆炸", afterState: "敌人消失",
    attentionSignals: ["text_unreadable", "visual_occlusion", "state_chain_broken", "invalid"],
  }, "gameplay");
  assert.deepEqual(reasons, [
    { label: "前后状态无法连上", suggestion: "请对照连续画面，补全操作前、操作后和系统反馈。" },
    { label: "界面文字看不清", suggestion: "请查看更清楚的相邻画面，确认关键文案和数值。" },
    { label: "画面被特效或弹窗遮挡", suggestion: "请补取遮挡前后的画面，确认被遮住的玩法或界面信息。" },
  ]);
  assert.deepEqual(reviewer.filterFrames([{ id: "A", ...{
    confidence: "高", gameState: "战斗", userAction: "攻击", systemResponse: "爆炸", afterState: "敌人消失",
    attentionSignals: ["text_unreadable"],
  }}], "attention", "gameplay").map((frame) => frame.id), ["A"]);
});

test("ordinary unknown notes still do not expand the attention filter", () => {
  const frame = {
    id: "A", confidence: "高", gameState: "战斗", userAction: "攻击",
    systemResponse: "敌人受击", afterState: "继续战斗", unknowns: "未展示失败条件",
  };
  assert.deepEqual(reviewer.attentionReasons(frame, "gameplay"), []);
  assert.deepEqual(reviewer.filterFrames([frame], "attention", "gameplay"), []);
});

test("unknown filter accepts explicit missing-video notes and legacy values", () => {
  const frames = [
    { id: "A", timestamp: 2, evidenceLevel: "unknown" },
    { id: "B", timestamp: 1, unknowns: "视频没有展示失败情况" },
  ];
  assert.deepEqual(reviewer.filterFrames(frames, "unknown").map((frame) => frame.id), ["B", "A"]);
});

test("firstFrameIndexForScene resolves within the filtered ordered subset", () => {
  const frames = [
    { id: "B", timestamp: 5, sceneGroup: 2, confirmed: false },
    { id: "A", timestamp: 1, sceneGroup: 2, confirmed: true },
  ];
  assert.equal(reviewer.firstFrameIndexForScene(frames, 2, "all"), 0);
  assert.equal(reviewer.firstFrameIndexForScene(frames, 2, "unconfirmed"), 0);
  assert.equal(reviewer.firstFrameIndexForScene(frames, 9, "all"), -1);
});

test("filterOptions uses the approved user-facing labels", () => {
  assert.deepEqual(reviewer.filterOptions(), [
    { value: "scene_representatives", label: "每个场景 1 帧" },
    { value: "all", label: "全部" },
    { value: "attention", label: "需要重点检查" },
    { value: "unknown", label: "视频没有明确展示" },
    { value: "unconfirmed", label: "尚未人工确认" },
  ]);
});
