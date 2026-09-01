class ReviewClient {
  constructor(baseUrl, jobId) { this.baseUrl = baseUrl; this.jobId = jobId; }
  async request(path = "", options = {}) {
    const response = await fetch(path.startsWith("/api/") ? `${this.baseUrl}${path}` : `${this.baseUrl}/api/jobs/${this.jobId}/review-model${path}`, options);
    const body = await response.json();
    if (!response.ok) {
      const error = new Error(body.detail?.message || body.detail || "审核数据保存失败");
      error.status = response.status;
      error.currentRevision = body.detail?.currentRevision;
      throw error;
    }
    return body;
  }
  load() { return this.request(); }
  preview(expectedRevision) { return this.request("/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  operations(expectedRevision, operations, { keepalive = false } = {}) { return this.request("/operations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, operations }), keepalive }); }
  saveUiState(reviewUiState, { keepalive = false } = {}) { return this.request("/ui-state", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(reviewUiState), keepalive }); }
  undo(expectedRevision) { return this.request("/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  redo(expectedRevision) { return this.request("/redo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  confirmFlow(expectedRevision) { return this.request("/confirm-flow", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  confirmStage(stageId, expectedRevision) { return this.request("/confirm-stage", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stageId, expectedRevision }) }); }
  confirmUeFlow(expectedRevision) { return this.request("/confirm-ue-flow", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  confirmRules(expectedRevision) { return this.request(`/api/jobs/${this.jobId}/review/confirm-rules`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  assertActiveBoard(boardKey) {
    if (boardKey !== "competitor") throw new Error("Only competitor reference assets are active in this review flow");
  }
  uploadBoardAssets(boardKey, files, expectedRevision) {
    this.assertActiveBoard(boardKey);
    const body = new FormData();
    Array.from(files || []).forEach((file) => body.append("images", file, file.name));
    body.append("manifest", JSON.stringify(Array.from(files || [], (file) => file.name)));
    body.append("expectedRevision", String(expectedRevision));
    return this.request(`/reference-boards/${boardKey}/assets`, { method: "POST", body });
  }
  replaceBoardAsset(boardKey, assetId, file, expectedRevision) {
    this.assertActiveBoard(boardKey);
    const body = new FormData();
    body.append("image", file, file.name);
    body.append("expectedRevision", String(expectedRevision));
    return this.request(`/reference-boards/${boardKey}/assets/${assetId}/replace`, { method: "POST", body });
  }
  deleteBoardAsset(boardKey, assetId, expectedRevision) { this.assertActiveBoard(boardKey); return this.request(`/reference-boards/${boardKey}/assets/${assetId}`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  reorderBoardAssets(boardKey, assetIds, expectedRevision) { this.assertActiveBoard(boardKey); return this.request(`/reference-boards/${boardKey}/order`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, assetIds }) }); }
}

function createOperationQueue({ send, onStatus = () => {}, onFailure = () => {}, isActive = () => true, delay = 300 }) {
  let pending = [];
  let timer = null;
  let scheduledRevision = null;
  let inFlight = null;
  let exitInFlight = null;
  const notify = (status) => { if (isActive()) onStatus(status); };
  const fail = (error) => {
    if (!isActive()) return;
    try { Promise.resolve(onFailure(error)).catch(() => {}); } catch (_) {}
  };
  const schedule = (revision, immediate) => {
    scheduledRevision = revision;
    clearTimeout(timer);
    if (immediate) {
      timer = null;
      Promise.resolve().then(() => flush(scheduledRevision)).catch(() => {});
      return;
    }
    timer = setTimeout(() => flush(scheduledRevision).catch(() => {}), delay);
  };
  const flush = async (revision, operations) => {
    clearTimeout(timer);
    timer = null;
    if (inFlight || exitInFlight) {
      if (operations?.length) pending = [...operations, ...pending];
      return inFlight || exitInFlight;
    }
    const batch = operations === undefined ? pending.splice(0) : operations;
    if (!batch.length) return null;
    let sendBatch;
    try { sendBatch = send(revision, batch); } catch (error) { sendBatch = Promise.reject(error); }
    inFlight = (async () => {
      let failed = false;
      let canonicalRevision = revision;
      notify("saving");
      try {
        const result = await sendBatch;
        if (Number.isInteger(result?.revision)) canonicalRevision = result.revision;
        notify("saved");
        return result;
      } catch (error) {
        failed = true;
        pending = [...batch, ...pending];
        notify(error.status === 409 && Number.isInteger(error.currentRevision) ? "conflict" : "failed");
        fail(error);
        throw error;
      } finally {
        inFlight = null;
        if (!failed && pending.length && !timer) schedule(canonicalRevision, true);
      }
    })();
    return inFlight;
  };
  return {
    push(operation, revision, { immediate = false } = {}) { pending.push(operation); notify("queued"); schedule(revision, immediate); },
    flush,
    flushOnExit: (revision) => {
      if (inFlight) return inFlight;
      if (exitInFlight) return exitInFlight;
      if (!pending.length) return null;
      clearTimeout(timer);
      timer = null;
      const batch = pending;
      pending = [];
      notify("saving");
      let sendBatch;
      try { sendBatch = send(revision, batch, { keepalive: true }); } catch (error) { sendBatch = Promise.reject(error); }
      exitInFlight = (async () => {
        let failed = false;
        let canonicalRevision = revision;
        try {
          const result = await sendBatch;
          if (Number.isInteger(result?.revision)) canonicalRevision = result.revision;
          notify("saved");
          return result;
        } catch (error) {
          failed = true;
          pending = [...batch, ...pending];
          notify(error.status === 409 && Number.isInteger(error.currentRevision) ? "conflict" : "failed");
          fail(error);
          throw error;
        } finally {
          exitInFlight = null;
          if (!failed && pending.length && !timer) schedule(canonicalRevision, true);
        }
      })();
      return exitInFlight;
    },
    pending: () => [...pending],
    hasPending: () => Boolean(pending.length || inFlight || exitInFlight),
    clear: () => { if (pending.length || inFlight || exitInFlight) throw new Error("use discard() to drop review operations"); clearTimeout(timer); timer = null; },
    discard: () => { pending = []; clearTimeout(timer); timer = null; },
  };
}

function restoreUiState(model, saved = {}) {
  const selection = saved.selection;
  const stageIds = new Set((model.stages || []).map((item) => item.id));
  const idsByType = {
    stage: stageIds,
    transition: new Set((model.transitions || []).map((item) => item.id)),
    region: new Set((model.regions || []).map((item) => item.id)),
    component: new Set((model.components || []).map((item) => item.id)),
    constraint: new Set((model.crossStateConstraints || []).map((item) => item.id)),
  };
  const sources = model.sources || {};
  return {
    view: saved.view === "rules" ? "preview" : ["gameplay_directory", "flow", "stage", "preview", "interaction_preview", "gameplay", "diagrams", "tables", "final_preview"].includes(saved.view) ? saved.view : "flow",
    selectedStageId: stageIds.has(saved.selectedStageId) ? saved.selectedStageId : model.stages?.[0]?.id || null,
    selectedTransitionId: idsByType.transition.has(saved.selectedTransitionId) ? saved.selectedTransitionId : null,
    selectedFrameId: sources[saved.selectedFrameId] ? saved.selectedFrameId : null,
    selection: selection && idsByType[selection.type]?.has(selection.id) ? selection : null,
    projectDrawerOpen: Boolean(saved.projectDrawerOpen),
  };
}

ReviewClient.createOperationQueue = createOperationQueue;
ReviewClient.restoreUiState = restoreUiState;
if (typeof module !== "undefined") module.exports = ReviewClient;
else window.ReviewClient = ReviewClient;
