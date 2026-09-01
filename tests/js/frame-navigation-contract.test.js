const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

test("all navigation paths and save failures share explicit state", () => {
  const app = fs.readFileSync("js/app.js", "utf8");
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const state = fs.readFileSync("js/state.js", "utf8");
  assert.match(app, /isTextEditingTarget/);
  assert.match(app, /ArrowLeft/);
  assert.match(backend, /findFrameIndex/);
  assert.match(backend, /showFrameAt/);
  assert.match(state, /reviewUnsaved/);
  assert.match(backend, /尚未保存到任务/);
  assert.match(backend, /state\.frameFilter = "all"/);
  assert.match(backend, /scene_representatives/);
  assert.match(backend, /reviewableFrames/);
});

test("supplemental thumbnails reuse evidence seeking instead of creating navigation state", () => {
  const source = fs.readFileSync("js/frames-models.js", "utf8");
  assert.match(source, /data-supplement-url/);
  assert.match(source, /jumpToEvidence/);
  assert.doesNotMatch(source, /state\.supplementalFrameIndex/);
});
