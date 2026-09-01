const test = require("node:test");
const assert = require("node:assert/strict");
const ReviewClient = require("../../js/review-client.js");

test("load returns the canonical review model from the revisioned endpoint", async () => {
  const originalFetch = global.fetch;
  let requestedUrl = "";
  global.fetch = async (url) => {
    requestedUrl = url;
    return { ok: true, json: async () => ({ revision: 8, stages: [] }) };
  };
  try {
    const model = await new ReviewClient("http://127.0.0.1:8000", "job-8").load();
    assert.equal(requestedUrl, "http://127.0.0.1:8000/api/jobs/job-8/review-model");
    assert.equal(model.revision, 8);
  } finally {
    global.fetch = originalFetch;
  }
});

test("request exposes a revision conflict for canonical reload handling", async () => {
  const originalFetch = global.fetch;
  global.fetch = async () => ({ ok: false, status: 409, json: async () => ({ detail: { currentRevision: 9 } }) });
  try {
    await assert.rejects(() => new ReviewClient("http://127.0.0.1:8000", "job-9").undo(8), (error) => error.status === 409 && error.currentRevision === 9);
  } finally {
    global.fetch = originalFetch;
  }
});

test("flow, stage, and rule confirmations use revisioned canonical endpoints", async () => {
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ revision: calls.length + 10 }) };
  };
  try {
    const client = new ReviewClient("http://127.0.0.1:8000", "job-confirm");
    await client.confirmFlow(7);
    await client.confirmStage("STG-002", 8);
    await client.confirmRules(9);
  } finally {
    global.fetch = originalFetch;
  }
  assert.deepEqual(calls.map(({ url, options }) => ({ url, method: options.method, body: JSON.parse(options.body) })), [
    { url: "http://127.0.0.1:8000/api/jobs/job-confirm/review-model/confirm-flow", method: "POST", body: { expectedRevision: 7 } },
    { url: "http://127.0.0.1:8000/api/jobs/job-confirm/review-model/confirm-stage", method: "POST", body: { stageId: "STG-002", expectedRevision: 8 } },
    { url: "http://127.0.0.1:8000/api/jobs/job-confirm/review/confirm-rules", method: "POST", body: { expectedRevision: 9 } },
  ]);
});

test("competitor board mutations use dedicated canonical endpoints and revision payloads", async () => {
  const originalFetch = global.fetch;
  const originalFormData = global.FormData;
  const calls = [];
  global.FormData = class { constructor() { this.entries = []; } append(...entry) { this.entries.push(entry); } };
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ revision: 12 }) };
  };
  try {
    const client = new ReviewClient("http://127.0.0.1:8000", "job-board");
    await client.uploadBoardAssets("competitor", [{ name: "a.png" }, { name: "b.png" }], 9);
    await client.deleteBoardAsset("competitor", "CPA-001", 10);
    await client.reorderBoardAssets("competitor", ["CPA-002", "CPA-001"], 11);
  } finally {
    global.fetch = originalFetch;
    global.FormData = originalFormData;
  }
  assert.equal(calls[0].url, "http://127.0.0.1:8000/api/jobs/job-board/review-model/reference-boards/competitor/assets");
  assert.deepEqual(calls[0].options.body.entries.map((entry) => [entry[0], entry[1]?.name || entry[1]]), [["images", "a.png"], ["images", "b.png"], ["manifest", '["a.png","b.png"]'], ["expectedRevision", "9"]]);
  assert.deepEqual(calls.slice(1).map(({ url, options }) => ({ url, method: options.method, body: JSON.parse(options.body) })), [
    { url: "http://127.0.0.1:8000/api/jobs/job-board/review-model/reference-boards/competitor/assets/CPA-001", method: "DELETE", body: { expectedRevision: 10 } },
    { url: "http://127.0.0.1:8000/api/jobs/job-board/review-model/reference-boards/competitor/order", method: "POST", body: { expectedRevision: 11, assetIds: ["CPA-002", "CPA-001"] } },
  ]);
});

test("missing competitor board replacement is a single revisioned multipart request", async () => {
  const originalFetch = global.fetch;
  const originalFormData = global.FormData;
  let call;
  global.FormData = class { constructor() { this.entries = []; } append(...entry) { this.entries.push(entry); } };
  global.fetch = async (url, options) => {
    call = { url, options };
    return { ok: true, json: async () => ({ revision: 14 }) };
  };
  try {
    await new ReviewClient("http://127.0.0.1:8000", "job-replace").replaceBoardAsset("competitor", "CPA-001", { name: "recovered.png" }, 13);
  } finally {
    global.fetch = originalFetch;
    global.FormData = originalFormData;
  }
  assert.equal(call.url, "http://127.0.0.1:8000/api/jobs/job-replace/review-model/reference-boards/competitor/assets/CPA-001/replace");
  assert.deepEqual(call.options.body.entries.map((entry) => [entry[0], entry[1]?.name || entry[1]]), [["image", "recovered.png"], ["expectedRevision", "13"]]);
});

test("client rejects legacy UX board mutations", () => {
  const client = new ReviewClient("http://127.0.0.1:8000", "job-board");
  assert.throws(() => client.uploadBoardAssets("ux", [], 1), /Only competitor reference assets/);
});
