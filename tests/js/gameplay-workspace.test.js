const test = require("node:test");
const assert = require("node:assert/strict");
const GameplayWorkspace = require("../../js/gameplay-workspace.js");
const GameplayReviewClient = require("../../js/gameplay-review-client.js");

const model = (revision = 1) => ({ revision, chapters: [{ id: "GCH-001" }], evidenceAnchors: [{ id: "GEV-001", frameId: "F0001" }], diagrams: [{ id: "GDI-001" }] });

test("canEnter requires a current interaction preview and export-ready gate", () => {
  assert.equal(GameplayWorkspace.canEnter({ revision: 3, reviewState: { previewRevision: 3 }, gate: { exportReady: true } }), true);
  assert.equal(GameplayWorkspace.canEnter({ revision: 3, reviewState: { previewRevision: 2 }, gate: { exportReady: true } }), false);
  assert.equal(GameplayWorkspace.canEnter({ revision: 3, reviewState: { previewRevision: 3 }, gate: { exportReady: false } }), false);
});

test("rebuild preserves valid gameplay selections and closes deleted evidence", () => {
  const previous = { ...GameplayWorkspace.initialState(model()), selectedChapterId: "GCH-001", evidenceDrawer: "GEV-001", selectedDiagramId: "GDI-001" };
  const kept = GameplayWorkspace.rebuild(model(), "saved", previous);
  assert.equal(kept.selectedChapterId, "GCH-001");
  assert.equal(kept.evidenceDrawer, "GEV-001");
  assert.equal(kept.selectedDiagramId, "GDI-001");
  const deleted = GameplayWorkspace.rebuild({ ...model(), evidenceAnchors: [] }, "saved", previous);
  assert.equal(deleted.evidenceDrawer, null);
});

test("rebuild preserves the selected parameter table when it still exists", () => {
  const current = { ...model(2), tables: [{ id: "GTB-001" }, { id: "GTB-002" }] };
  const rebuilt = GameplayWorkspace.rebuild(current, "saved", { selectedTableId: "GTB-002" });
  assert.equal(rebuilt.selectedTableId, "GTB-002");
  const removed = GameplayWorkspace.rebuild({ ...current, tables: [{ id: "GTB-001" }] }, "saved", { selectedTableId: "GTB-002" });
  assert.equal(removed.selectedTableId, null);
});

test("gameplay UI persistence includes the selected parameter table", () => {
  const source = require("node:fs").readFileSync("js/backend.js", "utf8");
  const persistence = source.slice(source.indexOf("function persistGameplayUiState"), source.indexOf("function renderGameplayReviewWorkspace"));
  assert.match(persistence, /selectedTableId:\s*workspace\.selectedTableId/);
});

test("a gameplay revision invalidates preview while preserving valid UI selections", () => {
  const previous = { ...GameplayWorkspace.initialState(model(1)), selectedChapterId: "GCH-001", editedGroups: ["GCH-001:claims"], preview: { revision: 1, exportReady: true }, previewStatus: "ready" };
  const rebuilt = GameplayWorkspace.rebuild(model(2), "saved", previous);
  assert.equal(rebuilt.selectedChapterId, "GCH-001");
  assert.equal(rebuilt.preview, null);
  assert.equal(rebuilt.previewStatus, "idle");
  assert.deepEqual(rebuilt.editedGroups, ["GCH-001:claims"]);
});

test("history restoration keeps selected chapter, diagram state, and pinned final eligibility", () => {
  const restoredModel = {
    ...model(4),
    chapters: [{ id: "GCH-001" }, { id: "GCH-002" }],
    diagrams: [{ id: "GDI-001", status: "reviewed" }],
    reviewState: { previewRevision: 4 },
  };
  const rebuilt = GameplayWorkspace.rebuild(restoredModel, "synced", { selectedChapterId: "GCH-002" });
  assert.equal(rebuilt.selectedChapterId, "GCH-002");
  assert.equal(rebuilt.finalPreviewEligible, true);
  assert.equal(rebuilt.model.diagrams[0].status, "reviewed");
});

test("gameplay client uses canonical endpoints and exposes revision conflicts", async () => {
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (calls.length === 2) return { ok: false, status: 409, json: async () => ({ detail: { currentRevision: 5 } }) };
    return { ok: true, json: async () => ({ revision: 4 }) };
  };
  try {
    const client = new GameplayReviewClient("http://127.0.0.1:8000", "job-5");
    await client.operations(3, [{ type: "set_chapter_field" }]);
    await assert.rejects(() => client.undo(4), (error) => error.status === 409 && error.currentRevision === 5);
    await client.confirmChapter("GCH-001", 5);
    await client.confirmChapter("GCH-001", 6, "rejected");
    await client.reopenChapter("GCH-001", 6);
    await client.context("GCH-001", 7, "F0001", ["trigger"]);
    await client.diagrams(8);
    await client.finalPreview(8, { apiBase: "https://vision.example/v1", model: "vision-model", apiKey: "configured-key" });
  } finally { global.fetch = originalFetch; }
  assert.deepEqual(calls.map(({ url, options }) => ({ url, method: options.method, body: options.body && JSON.parse(options.body) })), [
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review-model/operations", method: "POST", body: { expectedRevision: 3, operations: [{ type: "set_chapter_field" }] } },
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review-model/undo", method: "POST", body: { expectedRevision: 4 } },
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review-model/confirm-chapter", method: "POST", body: { chapterId: "GCH-001", expectedRevision: 5 } },
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review-model/confirm-chapter", method: "POST", body: { chapterId: "GCH-001", expectedRevision: 6, decision: "rejected" } },
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review-model/reopen-chapter", method: "POST", body: { chapterId: "GCH-001", expectedRevision: 6 } },
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review/chapters/GCH-001/context", method: "POST", body: { expectedRevision: 7, anchorFrameId: "F0001", missingFields: ["trigger"] } },
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review-model/diagrams", method: "POST", body: { expectedRevision: 8 } },
    { url: "http://127.0.0.1:8000/api/jobs/job-5/gameplay-review-model/final-preview", method: "POST", body: { expectedRevision: 8, apiBase: "https://vision.example/v1", model: "vision-model", apiKey: "configured-key" } },
  ]);
});

test("gameplay operations keep an independent queue helper", async () => {
  const sent = [];
  const queue = GameplayReviewClient.createOperationQueue({ send: async (revision, operations) => { sent.push({ revision, operations }); return { revision: revision + 1 }; }, delay: 0 });
  queue.push({ type: "set_chapter_field" }, 1, { immediate: true });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(sent, [{ revision: 1, operations: [{ type: "set_chapter_field" }] }]);
});

test("gameplay generation sends the configured vision model form", async () => {
  const originalFetch = global.fetch;
  const calls = [];
  const config = new FormData();
  config.append("api_key", "configured-key");
  global.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ status: "queued" }) };
  };
  try {
    const client = new GameplayReviewClient("http://127.0.0.1:8000", "job-5");
    await client.generate(config);
  } finally { global.fetch = originalFetch; }

  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.body, config);
});
