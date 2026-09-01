const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

test("renderer exposes one accessible active-frame reviewer", () => {
  const source = fs.readFileSync("js/frames-models.js", "utf8");
  for (const term of ["showFrameAt", "frame-reviewer", "frame-prev", "frame-next", "aria-live"])
    assert.match(source, new RegExp(term));
  assert.match(source, /const frame = frameOverride \|\| ordered\[state\.currentFrameIndex\]/);
  assert.match(source, /frame-show-all/);
  assert.match(source, /frame-representatives-only/);
  for (const term of ["frame-scene-select", "frame-filter-select", "reviewableFrames", "当前没有需要检查的关键帧"])
    assert.match(source, new RegExp(term));
});

test("renderer explains attention reasons and resolves them without navigating", () => {
  const source = fs.readFileSync("js/frames-models.js", "utf8");
  for (const term of ["attentionReasons", "frame-attention-reasons", "frame-attention-resolved", "这一帧已不再需要重点检查", "refreshFrameAttentionFeedback"])
    assert.match(source, new RegExp(term));
});

test("renderer exposes supplemental evidence and edit-safe suggestions", () => {
  const source = fs.readFileSync("js/frames-models.js", "utf8");
  for (const term of [
    "补取前后画面", "正在补取画面", "正在重新解读", "supplemental-evidence",
    "supplement-thumb", "analysisSuggestion", "采用建议", "保留当前内容",
    "frame-supplement-action", "frame-suggestion-accept", "frame-suggestion-reject",
  ]) assert.match(source, new RegExp(term));
  assert.match(source, /frame\.inputType !== "image_sequence"/);
});

test("backend client polls frame repair without replacing the main frame list", () => {
  const source = fs.readFileSync("js/backend.js", "utf8");
  for (const term of ["supplementAndReanalyzeFrame", "pollFrameRepair", "resolveFrameSuggestion", "supplementalEvidence", "attentionSignals"])
    assert.match(source, new RegExp(term));
});

test("manual field edits are sent explicitly to protect planner work", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const renderer = fs.readFileSync("js/frames-models.js", "utf8");
  assert.match(backend, /humanEditedFields: frame\.humanEditedFields/);
  assert.match(renderer, /frame\.humanEditedFields/);
});
