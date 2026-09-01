// Regression: failed jobs lost their preserved screenshots and hid the retry button after reload.
// Found by /qa on 2026-08-13.
// Report: artifacts/qa-e2e-2026-08-13/failure-recovery.png
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

test("a reloaded failed job restores its preserved evidence and exposes retry", () => {
  const elements = new Map();
  const workspaceClasses = new Set();
  const context = {
    Intl,
    File,
    FormData,
    URLSearchParams,
    location: { origin: "http://127.0.0.1:8001", protocol: "http:", search: "?job=failed-job" },
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    state: { screenshots: [], auxiliaryVideo: null, assets: [], frames: [], sceneGroups: [], analysisMode: "interaction" },
    $: (id) => {
      if (!elements.has(id)) elements.set(id, { value: "", disabled: true, classList: { add: () => {} } });
      return elements.get(id);
    },
    document: {
      querySelector: (selector) => selector === ".workspace"
        ? { classList: { add: (...names) => names.forEach((name) => workspaceClasses.add(name)) } }
        : null,
      body: { classList: { add: () => {}, remove: () => {}, toggle: () => {} } },
    },
    setStatus: () => {},
    setProgress: () => {},
  };
  vm.runInNewContext(fs.readFileSync("js/screenshot-input.js", "utf8"), context);
  vm.runInNewContext(fs.readFileSync("js/backend.js", "utf8"), context);
  let statsRenders = 0;
  context.restoreScreenshotAssets = () => [{ id: "F0001", name: "001.png", file: null, readOnly: true }];
  context.syncLegacyAssets = () => {};
  context.renderScreenshotInputs = () => {};
  context.renderStats = () => { statsRenders += 1; };

  context.renderBackendFailure({
    id: "failed-job",
    status: "failed",
    metadata: { inputType: "image_sequence", projectName: "失败任务" },
    frames: [{ id: "F0001" }],
    error: "视觉模型未产出合格交互分析：0/1 个代表帧达标",
  });

  assert.equal(context.state.screenshots.length, 1);
  assert.equal(context.$("projectName").value, "失败任务");
  assert.equal(context.$("retryJobBtn").disabled, false);
  assert.equal(workspaceClasses.has("has-job"), true);
  assert.equal(statsRenders, 1);
});
