const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");

test("classic review scripts load together and expose both browser globals", () => {
  const window = {};
  const context = vm.createContext({ window });

  for (const file of ["flow-review.js", "stage-review.js"]) {
    const source = fs.readFileSync(path.join("js", file), "utf8");
    assert.doesNotThrow(() => vm.runInContext(source, context, { filename: file }));
  }

  assert.equal(typeof window.FlowReview, "object");
  assert.equal(typeof window.StageReview, "object");
});

test("gameplay classic scripts expose only intentional Gameplay globals", () => {
  const window = {};
  const context = vm.createContext({ window, globalThis: window, setTimeout, clearTimeout, fetch: async () => ({ ok: true, json: async () => ({}) }) });
  const files = ["gameplay-mechanism-forms.js", "gameplay-workspace.js", "gameplay-review-client.js", "gameplay-review.js", "gameplay-diagrams.js", "gameplay-directory.js"];
  files.forEach((name) => {
    const file = path.join(__dirname, "../../js", name);
    assert.doesNotThrow(() => vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file }));
  });
  assert.deepEqual(Object.keys(window).sort(), ["GameplayDiagrams", "GameplayDirectory", "GameplayMechanismForms", "GameplayReview", "GameplayReviewClient", "GameplayWorkspace"]);
  ["initialState", "rebuild", "SCHEMAS", "fieldsFor", "render"].forEach((name) => assert.equal(window[name], undefined));
});
