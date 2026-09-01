const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function loadBackend(fetchImpl, hostname = "127.0.0.1") {
  const elements = {
    historyPanel: { hidden: true },
    historyList: { innerHTML: "" },
  };
  const context = {
    location: { hostname, port: "8000", origin: `http://${hostname}:8000`, search: "" },
    localStorage: { getItem: () => "", setItem: () => {}, removeItem: () => {} },
    fetch: fetchImpl,
    FormData,
    URLSearchParams,
    clearAll: () => {},
    setStatus: () => {},
    $: (id) => elements[id] || { innerHTML: "" },
  };
  vm.runInNewContext(fs.readFileSync("js/backend.js", "utf8"), context);
  return { context, elements };
}

test("archiveHistoryJob reports backend failures instead of swallowing them", async () => {
  const { context } = loadBackend(async () => ({
    ok: false,
    status: 500,
    text: async () => "archive exploded",
  }));

  await assert.rejects(
    context.archiveHistoryJob("job-1"),
    /归档失败|500|archive exploded/,
  );
});

test("local access reveals and loads task history", async () => {
  let requests = 0;
  const { context, elements } = loadBackend(async (url) => {
    requests += 1;
    if (String(url).endsWith("/api/health")) return { ok: true };
    return { ok: true, json: async () => [{ id: "job-1", status: "completed", metadata: { projectName: "本机任务", mode: "interaction" } }] };
  });

  await context.initializeJobHistory();

  assert.equal(elements.historyPanel.hidden, false);
  assert.match(elements.historyList.innerHTML, /本机任务/);
  assert.equal(requests, 2);
});

test("private LAN access reveals and loads task history", async () => {
  let requests = 0;
  const { context, elements } = loadBackend(async (url) => {
    requests += 1;
    if (String(url).endsWith("/api/health")) return { ok: true };
    return { ok: true, json: async () => [{ id: "job-lan", status: "failed", metadata: { projectName: "局域网任务", mode: "interaction" } }] };
  }, "192.168.50.67");

  await context.initializeJobHistory();

  assert.equal(elements.historyPanel.hidden, false);
  assert.match(elements.historyList.innerHTML, /局域网任务/);
  assert.equal(requests, 2);
});
