const test = require("node:test");
const assert = require("node:assert/strict");
const ReviewClient = require("../../js/review-client.js");
const ReviewWorkspace = require("../../js/review-workspace.js");

const { createOperationQueue, restoreUiState } = ReviewClient;
const model = {
  stages: [{ id: "STG-001" }, { id: "STG-002" }],
  regions: [{ id: "REG-0001" }],
  components: [],
  transitions: [],
  sources: { F0001: {} },
};

test("operation queue exposes saving saved and failed without losing edits", async () => {
  const statuses = [];
  const queue = createOperationQueue({
    send: async (revision, operations) => ({ revision: revision + 1, operations }),
    onStatus: (status) => statuses.push(status),
  });
  const operation = { type: "set", entity: "stage", id: "STG-001", field: "name", value: "选择武器" };
  await queue.flush(4, [operation]);
  assert.deepEqual(statuses, ["saving", "saved"]);

  const failed = createOperationQueue({ send: async () => { throw new Error("offline"); }, onStatus: () => {} });
  failed.push(operation);
  await assert.rejects(() => failed.flush(4));
  assert.deepEqual(failed.pending(), [operation]);
});

test("operation queue debounces normal pushes and flushes immediate pushes", async () => {
  const sent = [];
  const queue = createOperationQueue({ send: async (revision, operations) => { sent.push({ revision, operations }); return { revision: revision + 1 }; }, onStatus: () => {} });
  queue.push({ id: "slow" }, 4);
  await new Promise((resolve) => setTimeout(resolve, 320));
  assert.deepEqual(sent, [{ revision: 4, operations: [{ id: "slow" }] }]);
  queue.push({ id: "fast" }, 5, { immediate: true });
  await new Promise(setImmediate);
  assert.deepEqual(sent[1], { revision: 5, operations: [{ id: "fast" }] });
});

test("restore uses server view and selection only when referenced ids still exist", () => {
  const restored = restoreUiState(model, { view: "stage", selectedStageId: "STG-002", selection: { type: "region", id: "REG-MISSING" } });
  assert.equal(restored.view, "stage");
  assert.equal(restored.selectedStageId, "STG-002");
  assert.equal(restored.selection, null);
  assert.equal(restored.selectedFrameId, null);
});

test("refresh restores the final document workspace instead of returning to interaction review", () => {
  const restored = restoreUiState(model, { view: "final_preview", selectedStageId: "STG-002" });
  assert.equal(restored.view, "final_preview");
  assert.equal(restored.selectedStageId, "STG-002");
});

test("operation queue reports queued work and only discards through an explicit API", () => {
  const statuses = [];
  const queue = createOperationQueue({ send: async () => ({}), onStatus: (status) => statuses.push(status) });
  queue.push({ id: "pending" }, 4);
  assert.equal(queue.hasPending(), true);
  assert.equal(statuses[0], "queued");
  assert.throws(() => queue.clear(), /discard/);
  queue.discard();
  assert.equal(queue.hasPending(), false);
});

test("explicit flush reports a revision conflict exactly once", async () => {
  const conflict = Object.assign(new Error("conflict"), { status: 409, currentRevision: 5 });
  const failures = [];
  const queue = createOperationQueue({
    send: async () => { throw conflict; },
    onFailure: (error) => failures.push(error),
    onStatus: () => {},
  });
  queue.push({ id: "pending" }, 4);

  await assert.rejects(() => queue.flush(4), (error) => error === conflict);

  assert.deepEqual(failures, [conflict]);
  assert.deepEqual(queue.pending(), [{ id: "pending" }]);
});

test("scheduled flush reports a rejected send exactly once", async () => {
  const failures = [];
  const queue = createOperationQueue({
    send: async () => { throw new Error("offline"); },
    onFailure: (error) => failures.push(error.message),
    onStatus: () => {},
  });

  queue.push({ id: "pending" }, 4, { immediate: true });
  await new Promise(setImmediate);

  assert.deepEqual(failures, ["offline"]);
});

test("pagehide success clears its batch and leaves the queue usable after bfcache restore", async () => {
  const sends = [];
  const queue = createOperationQueue({
    send: async (revision, operations, options) => { sends.push({ revision, operations, options }); return {}; },
    onStatus: () => {},
  });
  queue.push({ id: "pending" }, 4);

  await queue.flushOnExit(4);
  queue.push({ id: "after-return" }, 5);
  await queue.flush(5);

  assert.deepEqual(sends, [
    { revision: 4, operations: [{ id: "pending" }], options: { keepalive: true } },
    { revision: 5, operations: [{ id: "after-return" }], options: undefined },
  ]);
  assert.deepEqual(queue.pending(), []);
  assert.equal(queue.hasPending(), false);
});

test("pagehide reuses a normal in-flight send instead of replaying its batch", async () => {
  let resolve;
  const sends = [];
  const queue = createOperationQueue({
    send: (revision, operations, options) => {
      sends.push({ revision, operations, options });
      return new Promise((done) => { resolve = done; });
    },
    onStatus: () => {},
  });
  queue.push({ id: "normal" }, 4, { immediate: true });
  await new Promise(setImmediate);

  const exit = queue.flushOnExit(4);
  resolve({ revision: 5 });
  await exit;

  assert.deepEqual(sends, [{ revision: 4, operations: [{ id: "normal" }], options: undefined }]);
  assert.equal(queue.hasPending(), false);
});

test("pagehide sends each pending batch once and restores it after a keepalive failure", async () => {
  let reject;
  const failures = [];
  const sends = [];
  const queue = createOperationQueue({
    send: (revision, operations, options) => {
      sends.push({ revision, operations, options });
      return new Promise((_, fail) => { reject = fail; });
    },
    onFailure: (error) => failures.push(error.message),
    onStatus: () => {},
  });
  queue.push({ id: "first" }, 4);
  queue.push({ id: "second" }, 4);

  const firstExit = queue.flushOnExit(4);
  const repeatedExit = queue.flushOnExit(4);
  assert.equal(firstExit, repeatedExit);
  assert.deepEqual(queue.pending(), []);
  await Promise.resolve();
  reject(new Error("exit offline"));
  await assert.rejects(firstExit, /exit offline/);

  assert.deepEqual(sends, [{ revision: 4, operations: [{ id: "first" }, { id: "second" }], options: { keepalive: true } }]);
  assert.deepEqual(queue.pending(), [{ id: "first" }, { id: "second" }]);
  assert.deepEqual(failures, ["exit offline"]);
});

test("review client forwards exit operations with fetch keepalive enabled", async () => {
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ revision: 5 }) };
  };
  try {
    await new ReviewClient("http://localhost:8765", "job-1").operations(4, [{ id: "pending" }], { keepalive: true });
  } finally {
    global.fetch = originalFetch;
  }
  assert.equal(calls[0].options.keepalive, true);
  assert.match(calls[0].url, /job-1\/review-model\/operations$/);
});

test("restore rejects cross-type selection and transition ids", () => {
  const restored = restoreUiState(model, {
    selectedTransitionId: "REG-0001",
    selection: { type: "transition", id: "REG-0001" },
  });
  assert.equal(restored.selectedTransitionId, null);
  assert.equal(restored.selection, null);
});

test("suggestion acceptance maps explicit editor fields to revisioned operations", () => {
  assert.deepEqual(ReviewWorkspace.suggestionOperation("region", "REG-0001", "bounds", { x: 0, y: 0, width: 1, height: 1 }), { type: "set_region_bounds", id: "REG-0001", bounds: { x: 0, y: 0, width: 1, height: 1 } });
  assert.deepEqual(ReviewWorkspace.suggestionOperation("transition", "TRN-001", "anchor", { x: 0.2, y: 0.3 }), { type: "set_anchor", id: "TRN-001", anchor: { x: 0.2, y: 0.3 } });
  assert.deepEqual(ReviewWorkspace.suggestionOperation("stage", "STG-001", "smallLoop", { display: "x" }), { type: "set_small_loop", id: "STG-001", smallLoop: { display: "x" } });
  assert.deepEqual(ReviewWorkspace.suggestionOperation("component", "CMP-001", "states", { selected: "shown" }), { type: "set_component_state", componentId: "CMP-001", states: { selected: "shown" } });
  assert.deepEqual(ReviewWorkspace.suggestionOperation("constraint", "CNS-001", "text", "must hold"), { type: "set", entity: "constraint", id: "CNS-001", field: "text", value: "must hold" });
});

test("queue ignores stale completion callbacks while retaining the operation owner", async () => {
  let finish;
  const statuses = [];
  let active = true;
  const queue = createOperationQueue({
    send: () => new Promise((resolve) => { finish = resolve; }),
    onStatus: (status) => statuses.push(status),
    isActive: () => active,
  });
  queue.push({ id: "owned" }, 4, { immediate: true });
  await new Promise(setImmediate);
  active = false;
  finish({ revision: 5 });
  await new Promise(setImmediate);
  assert.deepEqual(statuses, ["queued", "saving"]);
});

test("edits queued during an in-flight save use the returned canonical revision", async () => {
  let finishFirst;
  const sends = [];
  const queue = createOperationQueue({
    delay: 60000,
    send(revision, operations) {
      sends.push({ revision, operations });
      if (sends.length === 1) return new Promise((resolve) => { finishFirst = resolve; });
      return Promise.resolve({ revision: revision + 1 });
    },
    onStatus: () => {},
  });

  queue.push({ id: "first" }, 4, { immediate: true });
  await new Promise(setImmediate);
  queue.push({ id: "second" }, 4, { immediate: true });
  await new Promise(setImmediate);
  finishFirst({ revision: 5 });
  await new Promise(setImmediate);
  await new Promise(setImmediate);

  assert.deepEqual(sends, [
    { revision: 4, operations: [{ id: "first" }] },
    { revision: 5, operations: [{ id: "second" }] },
  ]);
});
