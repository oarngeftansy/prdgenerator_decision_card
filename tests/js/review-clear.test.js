const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function classList(initial = []) {
  const values = new Set(initial);
  return { add: (...names) => names.forEach((name) => values.add(name)), remove: (...names) => names.forEach((name) => values.delete(name)), contains: (name) => values.has(name) };
}

function loadApp() {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, { id, value: "", hidden: false, innerHTML: "", classList: classList(id === "reviewProjectDrawer" ? ["is-open"] : []), attrs: {}, setAttribute(name, value) { this.attrs[name] = value; }, pause() {}, removeAttribute() {}, load() {} });
    return elements.get(id);
  };
  const workspace = { classList: classList(["has-job", "has-review"]) };
  const context = {
    URL, URLSearchParams,
    state: { assets: [], screenshots: [], auxiliaryVideo: null, frames: [], sceneGroups: [], videoSummary: {}, reviewWorkspace: { model: {} }, reviewClient: {} },
    activeJobId: "active", lastCompletedJobId: "completed",
    location: { search: "", pathname: "/" }, document: { title: "review", querySelector: () => workspace, addEventListener() {} },
    localStorage: { removeItem() {} }, history: { replaceState() {} },
    $: element, renderFrames() {}, renderScreenshotInputs() {}, renderStats() {}, setProgress() {}, setStatus() {},
  };
  vm.runInNewContext(fs.readFileSync("js/app.js", "utf8"), context);
  return { context, element, workspace };
}

test("clearAll exits review mode and resets workspace state", () => {
  const { context, element, workspace } = loadApp();
  context.clearAll();
  assert.equal(context.state.reviewWorkspace, null);
  assert.equal(context.state.reviewClient, null);
  assert.equal(workspace.classList.contains("has-review"), false);
  assert.equal(element("reviewWorkspace").hidden, true);
  assert.equal(element("reviewProjectDrawer").classList.contains("is-open"), false);
  assert.equal(element("reviewProjectDrawerToggle").attrs["aria-expanded"], "false");
  for (const id of ["flowReviewView", "stageReviewView", "exportPreviewView", "analysisFailedView"]) assert.equal(element(id).hidden, true);
});
