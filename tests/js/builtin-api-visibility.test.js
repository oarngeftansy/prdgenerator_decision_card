const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function loadConfig(publicConfig) {
  const elements = {
    apiConfigPanel: { hidden: false, open: true },
    apiConfigSummary: { textContent: "" },
    apiConfigNotice: { textContent: "" },
    apiKey: { value: "" },
    apiUrl: { value: "" },
    model: { value: "" },
    transcriptionApiKey: { value: "" },
  };
  const context = {
    BACKEND_BASE: "",
    fetch: async () => ({ ok: true, json: async () => publicConfig }),
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    $: (id) => elements[id],
  };
  vm.runInNewContext(fs.readFileSync("js/config.js", "utf8"), context);
  return { context, elements };
}

test("built-in API hides the editable API configuration panel", async () => {
  const { context, elements } = loadConfig({
    hasBuiltInApi: true,
    apiBase: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen3.6-plus",
  });

  await context.loadPublicApiDefaults();

  assert.equal(elements.apiConfigPanel.hidden, true);
  assert.equal(elements.apiConfigPanel.open, false);
});
