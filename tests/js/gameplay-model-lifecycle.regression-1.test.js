const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function loadBackend() {
  const context = {
    Intl,
    module: undefined,
    File,
    FormData,
    URLSearchParams,
    location: { hostname: "127.0.0.1", port: "8000", origin: "http://127.0.0.1:8000", protocol: "http:", search: "" },
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    state: { screenshots: [], auxiliaryVideo: null, assets: [], frames: [], sceneGroups: [], analysisMode: "interaction" },
    $: () => ({ value: "", textContent: "", innerHTML: "", disabled: false, classList: { add: () => {} } }),
    document: { querySelector: () => ({ classList: { add: () => {} } }) },
    rememberApiConfig: () => {},
    setStatus: () => {},
    setProgress: () => {},
  };
  vm.runInNewContext(fs.readFileSync("js/screenshot-input.js", "utf8"), context);
  vm.runInNewContext(fs.readFileSync("js/backend.js", "utf8"), context);
  return context;
}


// Regression: ISSUE-GAMEPLAY-MODEL-LIFECYCLE — an empty recovery container was mistaken for a usable gameplay model.
// Found by /qa on 2026-08-25.
// Report: .gstack/qa-reports/qa-report-192.168.50.210-2026-08-25.md
test("pending and failed gameplay containers still require generation", () => {
  const context = loadBackend();

  assert.equal(context.gameplayModelNeedsGeneration({
    lifecycleState: "generation_required", chapters: [], reviewState: { status: "generation_required" },
  }), true);
  assert.equal(context.gameplayModelNeedsGeneration({
    lifecycleState: "generation_failed", chapters: [], reviewState: { status: "generation_required" },
  }), true);
  assert.equal(context.gameplayModelNeedsGeneration({
    lifecycleState: "ready", chapters: [{ id: "GCH-001" }], reviewState: { status: "chapter_review" },
  }), false);
});


test("P1 rendering and navigation route pending containers through recovery", () => {
  const source = fs.readFileSync("js/backend.js", "utf8");
  const renderSection = source.slice(
    source.indexOf("function renderGameplayDirectoryWorkspace"),
    source.indexOf("function renderGameplayDiagramWorkspace"),
  );
  const bindSection = source.slice(
    source.indexOf("function bindReviewWorkspace"),
    source.indexOf("async function syncBackendResult"),
  );

  assert.match(renderSection, /const needsInitialGeneration = !state\.gameplayReviewWorkspace \|\| gameplayModelNeedsGeneration\(currentModel\)/);
  assert.match(renderSection, /const needsDetailGeneration/);
  assert.match(renderSection, /\u751f\u6210\u73a9\u6cd5\u76ee\u5f55/);
  assert.match(renderSection, /gameplay-directory-recovery/);
  assert.match(renderSection, /gameplay-directory-recovery-card/);
  assert.match(bindSection, /!gameplayModelReviewReady\(state\.gameplayReviewWorkspace\?\.model\)/);
  assert.match(bindSection, /gameplayViewsRequiringModel\.has\(button\.dataset\.reviewView\)/);
  assert.match(bindSection, /setReviewWorkspaceView\("gameplay_directory"\)/);
});

test("direct URLs for P4-P7 are canonicalized to the recovery route", () => {
  const context = loadBackend();
  const pending = { lifecycleState: "generation_failed", reviewState: { status: "generation_required" } };

  assert.equal(context.recoverableReviewView("gameplay", pending), "gameplay_directory");
  assert.equal(context.recoverableReviewView("diagrams", pending), "gameplay_directory");
  assert.equal(context.recoverableReviewView("tables", pending), "gameplay_directory");
  assert.equal(context.recoverableReviewView("final_preview", pending), "gameplay_directory");
  assert.equal(context.recoverableReviewView("flow", pending), "flow");
  assert.equal(context.recoverableReviewView("gameplay", {
    lifecycleState: "ready",
    reviewState: { status: "chapter_review", structurePhase: "detailed" },
    chapters: [{ id: "GCH-001" }],
  }), "gameplay");
});
