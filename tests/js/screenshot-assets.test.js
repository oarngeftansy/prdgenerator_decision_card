const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function loadAssets() {
  const elements = new Map();
  const context = {
    Intl,
    module: undefined,
    URL: { createObjectURL: (file) => `blob:${file.name}`, revokeObjectURL: () => {} },
    Image: class {
      set src(_value) { this.naturalWidth = 1080; this.naturalHeight = 1920; this.onload(); }
    },
    document: { createElement: () => ({}) },
    state: { screenshots: [], auxiliaryVideo: null, assets: [], frames: [], sceneGroups: [], videoSummary: null },
    $: (id) => {
      if (!elements.has(id)) elements.set(id, { value: "", textContent: "", innerHTML: "", disabled: false });
      return elements.get(id);
    },
    renderFrames: () => {},
    setProgress: () => {},
    setStatus: () => {},
    frameText: (value) => String(value),
  };
  vm.runInNewContext(fs.readFileSync("js/screenshot-input.js", "utf8"), context);
  vm.runInNewContext(fs.readFileSync("js/assets.js", "utf8"), context);
  return { context, elements };
}

function image(name, relativePath) {
  return { name, type: "image/png", size: 1, webkitRelativePath: relativePath };
}

test("replacing a screenshot folder preserves the auxiliary video", async () => {
  const { context } = loadAssets();
  context.state.auxiliaryVideo = { id: "V01", kind: "video", name: "helper.mp4" };

  await context.replaceScreenshotFolder([
    image("10.png", "shots/10.png"),
    image("2.png", "shots/2.png"),
  ]);

  assert.deepEqual(Array.from(context.state.screenshots, (asset) => asset.name), ["2.png", "10.png"]);
  assert.equal(context.state.auxiliaryVideo.name, "helper.mp4");
  assert.deepEqual(Array.from(context.state.assets, (asset) => asset.kind), ["image", "image", "video"]);
});

test("moving or deleting screenshots invalidates previous analysis", () => {
  const { context } = loadAssets();
  context.state.screenshots = [{ id: "A" }, { id: "B" }, { id: "C" }];
  context.state.frames = [{ id: "F0001" }];
  context.state.sceneGroups = [{ sceneId: 0 }];

  context.reorderScreenshot(2, 0);
  assert.deepEqual(Array.from(context.state.screenshots, (asset) => asset.id), ["C", "A", "B"]);
  assert.deepEqual(Array.from(context.state.frames), []);
  assert.deepEqual(Array.from(context.state.sceneGroups), []);

  context.removeScreenshot(1);
  assert.deepEqual(Array.from(context.state.screenshots, (asset) => asset.id), ["C", "B"]);
});
