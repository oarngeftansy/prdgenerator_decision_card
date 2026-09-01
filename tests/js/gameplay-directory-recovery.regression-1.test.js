const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// Regression: ISSUE-ROLE-P1-BLANK — failed first-generation jobs restored directly to P1 rendered an empty canvas.
// Found by /qa on 2026-08-25.
// Report: .gstack/qa-reports/qa-report-192.168.50.210-2026-08-25.md
test("direct P1 restoration without a gameplay model renders recoverable guidance", () => {
  const elements = new Map();
  const context = {
    Intl,
    module: undefined,
    File,
    FormData,
    URLSearchParams,
    location: { hostname: "127.0.0.1", port: "8000", origin: "http://127.0.0.1:8000", protocol: "http:", search: "" },
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    state: { screenshots: [], auxiliaryVideo: null, assets: [], frames: [], sceneGroups: [], analysisMode: "interaction" },
    $: (id) => {
      if (!elements.has(id)) elements.set(id, { value: "", textContent: "", innerHTML: "", disabled: false, classList: { add: () => {} } });
      return elements.get(id);
    },
    document: { querySelector: () => ({ classList: { add: () => {} } }) },
    rememberApiConfig: () => {},
    setStatus: () => {},
    setProgress: () => {},
  };
  vm.runInNewContext(fs.readFileSync("js/screenshot-input.js", "utf8"), context);
  vm.runInNewContext(fs.readFileSync("js/backend.js", "utf8"), context);
  context.state.reviewWorkspace = { view: "gameplay_directory", model: { revision: 4 } };
  context.state.gameplayReviewWorkspace = null;
  context.state.gameplayReviewGeneration = { status: "failed", error: "玩法章节生成失败" };

  context.renderGameplayDirectoryWorkspace();

  assert.match(context.$("gameplayDirectoryView").textContent, /首次生成未完成/);
  assert.match(context.$("gameplayDirectoryView").textContent, /点击.*玩法目录.*重新生成/);
});

test("failed gameplay generation explains the failure class and screenshot threshold", () => {
  const context = {
    Intl,
    module: undefined,
    File,
    FormData,
    URLSearchParams,
    location: { hostname: "127.0.0.1", port: "8000", origin: "http://127.0.0.1:8000", protocol: "http:", search: "" },
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    state: { screenshots: [], auxiliaryVideo: null, assets: [], frames: [], sceneGroups: [], analysisMode: "interaction" },
    $: () => ({ value: "", textContent: "", disabled: false, classList: { add: () => {} } }),
    document: { querySelector: () => ({ classList: { add: () => {} } }) },
    rememberApiConfig: () => {},
    setStatus: () => {},
    setProgress: () => {},
  };
  vm.runInNewContext(fs.readFileSync("js/backend.js", "utf8"), context);

  const system = context.gameplayGenerationFailureGuidance(
    { status: "failed", failureKind: "system", error: "玩法章节生成遇到服务内部异常" },
    4,
  );
  assert.match(system.reason, /服务内部异常/);
  assert.match(system.material, /4 张截图/);
  assert.match(system.material, /不是截图数量不足/);
  assert.match(system.action, /重新发起/);

  const quality = context.gameplayGenerationFailureGuidance(
    { status: "failed", failureKind: "quality", error: "视觉模型返回内容不符合玩法章节要求" },
    4,
  );
  assert.match(quality.material, /数量已达.*门槛/);
  assert.match(quality.material, /有效信息覆盖/);
});

test("opening P1 after a failure shows recovery instead of silently retrying", () => {
  const source = fs.readFileSync("js/backend.js", "utf8");
  const start = source.indexOf('if (gameplayModelNeedsGeneration(embedded) && generationStatus === "failed")');
  const end = source.indexOf('if (gameplayModelNeedsGeneration(embedded) && ["queued"', start);
  const failedBranch = source.slice(start, end);

  assert.ok(start >= 0 && end > start);
  assert.match(failedBranch, /renderGameplayDirectoryWorkspace\(\)/);
  assert.doesNotMatch(failedBranch, /runGameplayGeneration\(/);
});
