const test = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const ExportPreview = require("../../js/export-preview.js");

test("P7 status and Feishu export never collapse into a one-character column", () => {
  const css = readFileSync(join(process.cwd(), "css/gameplay-tables.css"), "utf8");
  assert.match(css, /final-document-shell[^}]*container-type:\s*inline-size/s);
  assert.match(css, /@container\s*\(max-width:\s*1050px\)[\s\S]*final-document-status[^}]*display:\s*grid[^}]*grid-column:\s*1\s*\/\s*-1/s);
  assert.match(css, /final-document-status[^}]*grid-template-columns:\s*minmax\(0,1fr\)\s+minmax\(260px,320px\)/s);
  assert.match(css, /final-document-feishu-state[^}]*display:\s*grid[^}]*min-width:\s*0/s);
  assert.match(css, /final-document-feishu-state>\.btn[^}]*width:\s*100%[^}]*min-width:\s*0/s);
});

test("blockers navigate to their source while warnings keep export available", () => {
  const ready = ExportPreview.viewModel({ exportReady: true, blockerIds: [], warningIds: ["CST-001"], revision: 4 }, { revision: 4 });
  assert.equal(ready.exportDisabled, false);
  const blocked = ExportPreview.viewModel({ exportReady: false, blockerIds: ["STG-001"], warningIds: [], revision: 3 }, { revision: 4 });
  assert.equal(blocked.exportDisabled, true);
  assert.deepEqual(ExportPreview.routeForIssue("STG-001"), { view: "stage", stageId: "STG-001" });
  assert.deepEqual(ExportPreview.routeForIssue("CST-001"), { view: "flow", selection: { type: "constraint", id: "CST-001" } });
});

test("preview summarizes the planning board only", () => {
  const view = ExportPreview.viewModel({
    exportReady: true, blockerIds: [], warningIds: [], revision: 4,
    referenceBoardSummary: [
      { key: "planning", assetCount: 2, missingCount: 0, status: "generated" },
      { key: "competitor", assetCount: 1, missingCount: 1, status: "missing" },
    ],
  }, { revision: 4 });

  assert.equal(view.referenceBoardSummary[0].assetCount, 2);
  assert.equal(view.referenceBoardSummary.length, 1);
  assert.deepEqual(ExportPreview.routeForIssue("GDE-001"), { view: "flow", issueId: "GDE-001" });
});

test("competitor mutation intent disables every preview export action until recovery", () => {
  const preview = { exportReady: true, blockerIds: [], warningIds: [], revision: 4 };
  const model = { revision: 4 };

  assert.equal(ExportPreview.viewModel(preview, model, true).exportDisabled, true);
  assert.equal(ExportPreview.viewModel(preview, model, false).exportDisabled, false);
});

test("combined preview requires matching interaction and gameplay revisions", () => {
  const preview = { exportReady: true, interactionRevision: 4, gameplayRevision: 7 };
  const models = { interaction: { revision: 4 }, gameplay: { revision: 7 } };
  assert.equal(ExportPreview.combinedViewModel(preview, models, false).exportDisabled, false);
  assert.equal(ExportPreview.combinedViewModel(preview, { ...models, gameplay: { revision: 8 } }, false).exportDisabled, true);
  assert.equal(ExportPreview.combinedViewModel(preview, models, true).exportDisabled, true);
});

test("combined preview explains automatic chapter completion in planner language", () => {
  assert.deepEqual(ExportPreview.autoCompletionView({ status: "queued", progress: 0 }), {
    busy: true,
    progress: 0,
    message: "正在自动补全已确认的玩法章节",
    detail: "系统会保留已确认结论，并根据原始素材补齐规则、验证方式和边界说明。",
  });
  assert.deepEqual(ExportPreview.autoCompletionView({ status: "failed", progress: 0 }), {
    busy: false,
    progress: 0,
    message: "自动补全失败",
    detail: "请重试；系统不会覆盖已经确认的策划结论。",
  });
});

test("gameplay generation status is planner-readable and failed work is retryable", () => {
  assert.deepEqual(ExportPreview.generationView({
    status: "running",
    progress: 42,
    logs: [{ progress: 42, message: "已补全 6/13 个玩法机制" }],
  }), {
    busy: true, progress: 42, message: "正在生成玩法章节", detail: "已补全 6/13 个玩法机制", failed: false,
  });
  assert.deepEqual(ExportPreview.generationView({ status: "failed", error: "视觉模型未配置" }), {
    busy: false, progress: 0, message: "生成失败：视觉模型未配置。", detail: "点击下方按钮重新生成玩法章节。", failed: true,
  });
  assert.deepEqual(ExportPreview.generationView({
    status: "failed",
    progress: 90,
    error: "视觉模型返回内容不符合玩法章节要求",
    qualityIssues: ["主策完整性检查未通过"],
  }), {
    busy: false,
    progress: 90,
    message: "生成失败：视觉模型返回内容不符合玩法章节要求。",
    detail: "未通过：主策完整性检查未通过。请重试；目录和已有审核内容不会丢失。",
    failed: true,
  });
});

test("failed gameplay generation exposes an explicit retry action", () => {
  const source = require("node:fs").readFileSync("js/export-preview.js", "utf8");
  assert.match(source, /generationState\.failed \? "重新生成玩法章节"/);
  assert.match(source, /gameplay-generation-progress gameplay-generation-failure/);
  assert.match(source, /role", "alert"/);
});

test("gameplay generation renderer exposes an accessible determinate progress bar", () => {
  const source = require("node:fs").readFileSync("js/export-preview.js", "utf8");
  assert.match(source, /role", "progressbar"/);
  assert.match(source, /aria-valuenow/);
  assert.match(source, /gameplay-generation-progress-bar/);
  assert.match(source, /`正在生成玩法章节 \$\{generationState\.progress\}%…`/);
});

test("sanitizer removes case-insensitive external URL attributes on root and descendants", () => {
  class Node {
    constructor(localName, attributes = [], children = []) {
      this.localName = localName;
      this.attributes = attributes.map(([name, value]) => ({ name, value }));
      this.children = children;
    }
    querySelectorAll(selector) { return selector === "*" ? this.children : []; }
    removeAttribute(name) { this.attributes = this.attributes.filter((item) => item.name !== name); }
    remove() {}
  }
  const child = new Node("path", [["fill", "URL(javascript:alert(1))"], ["stroke", "URL(#safe)"]]);
  const root = new Node("svg", [["fill", "URL(https://evil.example/image.svg)"]], [child]);
  const priorParser = global.DOMParser;
  const priorSerializer = global.XMLSerializer;
  global.DOMParser = class { parseFromString() { return { documentElement: root, querySelector: () => null }; } };
  global.XMLSerializer = class { serializeToString() { return JSON.stringify({ root: root.attributes, child: child.attributes }); } };
  try {
    const sanitized = JSON.parse(ExportPreview.sanitizeBoardSvg("<svg/>"));
    assert.deepEqual(sanitized.root, []);
    assert.deepEqual(sanitized.child, [{ name: "stroke", value: "URL(#safe)" }]);
  } finally {
    global.DOMParser = priorParser;
    global.XMLSerializer = priorSerializer;
  }
});

test("page-spec preview keeps its readable SVG width and scrolls its container", () => {
  const css = require("node:fs").readFileSync("css/review-workspace.css", "utf8");

  assert.match(css, /\.export-preview-board\s*\{[^}]*overflow:\s*auto;/);
  assert.match(css, /\.export-preview-board svg\s*\{[^}]*min-width:\s*1380px;/);
  assert.match(css, /\.export-preview-board svg\s*\{[^}]*width:\s*auto;/);
  assert.match(css, /\.export-preview-board svg\s*\{[^}]*max-width:\s*none;/);
});

test("preview controls scroll away with the document instead of covering later content", () => {
  const css = require("node:fs").readFileSync("css/review-workspace.css", "utf8");
  const toolbarRule = css.match(/\.export-preview-board-toolbar\s*\{([^}]*)\}/)?.[1] || "";

  assert.doesNotMatch(toolbarRule, /position:\s*sticky/);
  assert.match(toolbarRule, /position:\s*static/);
});

test("board zoom stays readable and exposes fit and fullscreen controls", () => {
  assert.equal(ExportPreview.clampBoardZoom(0.1), 0.35);
  assert.equal(ExportPreview.clampBoardZoom(1.25), 1.25);
  assert.equal(ExportPreview.clampBoardZoom(4), 4);
  assert.equal(ExportPreview.clampBoardZoom(8), 5);
  const source = require("node:fs").readFileSync("js/export-preview.js", "utf8");
  assert.match(source, /适应窗口/);
  assert.match(source, /全屏查看/);
});

test("page-spec preview aligns only after its board is mounted with layout metrics", () => {
  const board = {
    isConnected: false,
    clientWidth: 0,
    scrollWidth: 0,
    scrollLeft: 0,
    getBoundingClientRect: () => ({ left: 0 }),
  };
  const page = { getBoundingClientRect: () => ({ left: 690 }) };
  board.querySelector = (selector) => selector === '[data-node-kind="page-spec"]' ? page : null;
  const root = {
    append(node) {
      node.isConnected = true;
      node.clientWidth = 886;
      node.scrollWidth = 1988;
    },
  };

  ExportPreview.alignFirstPageSpec(board);
  assert.equal(board.scrollLeft, 0);

  root.append(board);
  ExportPreview.alignFirstPageSpec(board);
  assert.equal(board.scrollLeft, 666);

  board.scrollLeft = 320;
  assert.equal(board.scrollLeft, 320);
  assert.doesNotThrow(() => ExportPreview.alignFirstPageSpec({ isConnected: true, querySelector: () => null }));

  const source = require("node:fs").readFileSync("js/export-preview.js", "utf8");
  assert.ok(source.indexOf("root.append(boardShell)") < source.indexOf("alignFirstPageSpec(board);"));
});

test("planning board view state survives page switches and refreshes", () => {
  const values = new Map();
  const storage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) };
  ExportPreview.saveBoardViewState(storage, "job-1", { zoom: 1.6, left: 420, top: 35 });
  assert.deepEqual(ExportPreview.loadBoardViewState(storage, "job-1"), { zoom: 1.6, left: 420, top: 35 });
  assert.deepEqual(ExportPreview.loadBoardViewState(storage, "missing"), { zoom: 1.15, left: 0, top: 0 });
});

test("gameplay generation progress is a readable status card instead of a compressed footer strip", () => {
  const css = readFileSync(join(__dirname, "../../css/style.css"), "utf8");
  assert.match(css, /interaction-page-preview\s*>\s*\.gameplay-generation-progress\s*\{[^}]*grid-column:\s*1\s*\/\s*3[^}]*grid-row:\s*3/s);
  assert.match(css, /interaction-page-preview\s*>\s*\.gameplay-generation-progress\s*\{[^}]*min-height:\s*72px/s);
  assert.match(css, /interaction-page-preview\s*\{[^}]*grid-template-rows:\s*44px\s+minmax\(0,1fr\)\s+96px/s);
  assert.match(css, /gameplay-generation-progress-track\s*\{[^}]*min-width:\s*0/s);
});

test("interaction confirmation remains clickable when generation can repair preview blockers", () => {
  const blocked = { exportDisabled: true, mutationBlocked: false };
  assert.equal(ExportPreview.continueDisabled(blocked, true, false), false);
  assert.equal(ExportPreview.continueDisabled({ ...blocked, mutationBlocked: true }, true, false), true);
  assert.equal(ExportPreview.continueDisabled(blocked, true, true), true);
  assert.equal(ExportPreview.continueDisabled(blocked, false, false), true);
});

test("only a detailed ready gameplay model continues to rule review without regeneration", () => {
  const previewSource = readFileSync(join(__dirname, "../../js/export-preview.js"), "utf8");
  const backendSource = readFileSync(join(__dirname, "../../js/backend.js"), "utf8");
  assert.match(previewSource, /continueLabel\s*=\s*""/);
  assert.match(previewSource, /continueLabel\s*\|\|/);
  assert.match(backendSource, /gameplayDraftReady\s*\?\s*"进入规则审核"/);
  assert.match(backendSource, /gameplayDraftReady\s*=\s*gameplayModelReviewReady/);
  assert.match(backendSource, /setReviewWorkspaceView\("gameplay"\)/);
});

test("an unusable board never renders a blank P3 canvas and exposes rebuild", () => {
  class FakeNode {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.className = "";
      this.classList = { add: (...names) => { this.className = [this.className, ...names].filter(Boolean).join(" "); } };
      this.style = {};
    }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = [...nodes]; }
    setAttribute(name, value) { this[name] = value; }
    querySelector(selector) {
      if (selector.startsWith(".")) {
        const wanted = selector.slice(1);
        if (String(this.className).split(/\s+/).includes(wanted)) return this;
      }
      if (selector === "h4" && this.tagName === "H4") return this;
      for (const child of this.children) {
        const match = child?.querySelector?.(selector);
        if (match) return match;
      }
      return null;
    }
  }
  const previousDocument = global.document;
  global.document = { createElement: (tag) => new FakeNode(tag) };
  try {
    const root = new FakeNode("main");
    let calls = 0;
    ExportPreview.render({
      root,
      preview: { exportReady: false, blockerIds: ["TRN-001"], warningIds: [], revision: 1, boardPreviewSvg: "" },
      model: { revision: 1, crossStateConstraints: [] },
      onRetry: () => { calls += 1; },
    });
    const button = root.querySelector(".interaction-preview-retry");
    assert.ok(root.querySelector(".interaction-recovery-page"));
    assert.ok(root.querySelector(".interaction-recovery-status"));
    assert.ok(button);
    button.onclick();
    assert.equal(calls, 1);
  } finally {
    global.document = previousDocument;
  }
});

test("page-spec preview performs a second alignment after browser layout", () => {
  const source = require("node:fs").readFileSync("js/export-preview.js", "utf8");

  assert.match(source, /requestAnimationFrame[\s\S]*alignFirstPageSpec\(board\)/);
});

test("opening the interaction preview brings the actual board into view", () => {
  const source = require("node:fs").readFileSync("js/export-preview.js", "utf8");

  assert.match(source, /boardShell\.scrollIntoView\(\{\s*block:\s*"start"/);
});

test("loading preview keeps the page workbench visible instead of a blank panel", () => {
  assert.equal(typeof ExportPreview.renderLoading, "function");
  const source = require("node:fs").readFileSync("js/export-preview.js", "utf8");
  assert.match(source, /interaction-page-loading/);
  assert.match(source, /正在整理页面关系/);
});

test("an empty or failed interaction deliverable renders a recoverable P3 workbench", () => {
  assert.equal(typeof ExportPreview.renderRecovery, "function");
  class FakeNode {
    constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.className = ""; this.classList = { add: (...names) => { this.className = [this.className, ...names].filter(Boolean).join(" "); } }; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = [...nodes]; }
    setAttribute(name, value) { this[name] = value; }
    querySelector(selector) {
      if (selector.startsWith(".") && String(this.className).split(/\s+/).includes(selector.slice(1))) return this;
      for (const child of this.children) { const match = child?.querySelector?.(selector); if (match) return match; }
      return null;
    }
  }
  const previousDocument = global.document;
  global.document = { createElement: (tag) => new FakeNode(tag) };
  try {
    const root = new FakeNode("main"); let retries = 0;
    ExportPreview.renderRecovery(root, { failed: true, message: "页面关系暂未生成", onRetry: () => { retries += 1; } });
    assert.match(root.className, /interaction-page-preview/);
    assert.ok(root.querySelector(".interaction-preview-retry"));
    root.querySelector(".interaction-preview-retry").onclick();
    assert.equal(retries, 1);
  } finally { global.document = previousDocument; }
});
