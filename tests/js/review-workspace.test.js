const test = require("node:test");
const assert = require("node:assert/strict");
const ReviewWorkspace = require("../../js/review-workspace.js");

test("the planner workbench exposes the seven approved P1 to P7 stages", () => {
  assert.deepEqual(ReviewWorkspace.WORKBENCH_STEPS.map(({ id, label, views }) => ({ id, label, views })), [
    { id: "p1", label: "确认玩法目录", views: ["gameplay_directory"] },
    { id: "p2", label: "审核交互", views: ["flow", "stage"] },
    { id: "p3", label: "预览交互交付物", views: ["interaction_preview"] },
    { id: "p4", label: "审核玩法规则", views: ["gameplay"] },
    { id: "p5", label: "审核必要图解", views: ["diagrams"] },
    { id: "p6", label: "审核玩法表格", views: ["tables"] },
    { id: "p7", label: "预览并发布完整文档", views: ["final_preview"] },
  ]);
  assert.equal(ReviewWorkspace.stepForView("stage").id, "p2");
  assert.equal(ReviewWorkspace.stepForView("final_preview").id, "p7");
});

test("planner stage status uses pending attention and complete states", () => {
  assert.equal(ReviewWorkspace.stageStatus({ confirmation: { confirmed: false } }), "pending");
  assert.equal(ReviewWorkspace.stageStatus({ confirmation: { confirmed: false }, validation: { warnings: ["补充反馈"] } }), "needs_attention");
  assert.equal(ReviewWorkspace.stageStatus({ confirmation: { confirmed: true } }), "complete");
});

test("next stage skips confirmed stages and ends after the last stage", () => {
  const model = { stages: [
    { id: "STG-001", order: 1, confirmation: { confirmed: true } },
    { id: "STG-002", order: 2, confirmation: { confirmed: false } },
  ] };
  assert.equal(ReviewWorkspace.nextUnconfirmedStageId(model, "STG-001"), "STG-002");
  model.stages[1].confirmation.confirmed = true;
  assert.equal(ReviewWorkspace.nextUnconfirmedStageId(model, "STG-002"), null);
});

test("completed interaction jobs enter full-flow review", () => {
  const state = ReviewWorkspace.initialState({ reviewState: { status: "ai_draft" }, stages: [{ id: "STG-001" }] });
  assert.equal(state.view, "flow");
  assert.equal(state.selectedStageId, "STG-001");
});

test("selection is one shared object across frame marker list and form", () => {
  const state = ReviewWorkspace.initialState({ reviewState: {}, stages: [{ id: "STG-001" }] });
  const selected = ReviewWorkspace.select(state, { type: "region", id: "REG-0002", stageId: "STG-001", frameId: "F0001" });
  assert.deepEqual(selected.selection, { type: "region", id: "REG-0002", stageId: "STG-001", frameId: "F0001" });
});

test("selecting another stage resets frame region component and transition context", () => {
  const model = { stages: [
    { id: "STG-001", representativeFrames: [{ frameId: "F1" }] },
    { id: "STG-002", representativeFrames: [{ frameId: "F2" }] },
  ], sources: { F1: {}, F2: {} } };
  const current = {
    ...ReviewWorkspace.initialState(model),
    selectedFrameId: "F1",
    selectedTransitionId: "TRN-1",
    selection: { type: "component", id: "CMP-1", stageId: "STG-001", frameId: "F1" },
  };

  assert.deepEqual(ReviewWorkspace.selectStage(current, model, "STG-002"), {
    ...current,
    selectedStageId: "STG-002",
    selectedFrameId: "F2",
    selectedTransitionId: null,
    selection: null,
  });
});

test("transition selection persists its detail target in the shared workspace state", () => {
  const state = ReviewWorkspace.initialState({ reviewState: {}, stages: [{ id: "STG-001" }] });
  const selected = ReviewWorkspace.select(state, { type: "transition", id: "TRN-001", stageId: "STG-001" });
  assert.equal(selected.selectedTransitionId, "TRN-001");
});

test("selecting a region clears the prior transition detail target", () => {
  const state = { ...ReviewWorkspace.initialState({ reviewState: {}, stages: [{ id: "STG-001" }] }), selectedTransitionId: "TRN-001" };
  const selected = ReviewWorkspace.select(state, { type: "region", id: "REG-001", stageId: "STG-001", frameId: "F0001" });
  assert.equal(selected.selectedTransitionId, null);
  assert.equal(selected.selection.type, "region");
});

test("rebuild preserves a still-valid transition detail and shared selection", () => {
  const model = { reviewState: {}, stages: [{ id: "STG-001" }], transitions: [{ id: "TRN-001", sourceStageId: "STG-001" }], sources: { F0001: {} } };
  const previous = { ...ReviewWorkspace.initialState(model), selectedTransitionId: "TRN-001", selection: { type: "transition", id: "TRN-001", stageId: "STG-001", frameId: "F0001" } };
  const rebuilt = ReviewWorkspace.rebuild(model, "saved", previous);
  assert.equal(rebuilt.selectedTransitionId, "TRN-001");
  assert.deepEqual(rebuilt.selection, previous.selection);
});

test("rebuild preserves a selected stage and frame across a saved stage operation", () => {
  const model = { reviewState: {}, stages: [{ id: "STG-001" }, { id: "STG-002" }], sources: { F0001: {}, F0002: {} } };
  const previous = { ...ReviewWorkspace.initialState(model), selectedStageId: "STG-002", selectedFrameId: "F0002", selection: { type: "frame", id: "F0002", stageId: "STG-002", frameId: "F0002" } };
  const rebuilt = ReviewWorkspace.rebuild(model, "saved", previous);
  assert.equal(rebuilt.selectedStageId, "STG-002");
  assert.equal(rebuilt.selectedFrameId, "F0002");
});

test("rebuild clears a deleted transition detail and its shared selection", () => {
  const previous = { ...ReviewWorkspace.initialState({ reviewState: {}, stages: [{ id: "STG-001" }] }), selectedTransitionId: "TRN-001", selection: { type: "transition", id: "TRN-001", stageId: "STG-001" } };
  const rebuilt = ReviewWorkspace.rebuild({ reviewState: {}, stages: [{ id: "STG-001" }], transitions: [] }, "saved", previous);
  assert.equal(rebuilt.selectedTransitionId, null);
  assert.equal(rebuilt.selection, null);
});

test("rebuild clears any shared selection whose canonical entity was deleted", () => {
  const previous = { ...ReviewWorkspace.initialState({ reviewState: {}, stages: [{ id: "STG-001" }] }), selection: { type: "region", id: "REG-001", stageId: "STG-001", frameId: "F0001" } };
  const rebuilt = ReviewWorkspace.rebuild({ reviewState: {}, stages: [{ id: "STG-001" }], regions: [], sources: { F0001: {} } }, "saved", previous);
  assert.equal(rebuilt.selection, null);
});

test("confirmed stages route directly to the planning-board preview", () => {
  assert.equal(ReviewWorkspace.routeForModel({ quality: { qualified: false } }), "analysis_failed");
  assert.equal(ReviewWorkspace.routeForModel({ revision: 2, reviewState: { status: "preview_ready", previewRevision: 2 } }), "interaction_preview");
  assert.equal(ReviewWorkspace.routeForModel({ stages: [{ confirmation: { confirmed: true } }], reviewState: { flowConfirmed: true }, ruleDomains: { confirmation: { confirmed: false } } }), "interaction_preview");
  assert.equal(ReviewWorkspace.routeForModel({ stages: [{ confirmation: { confirmed: true } }], reviewState: { flowConfirmed: true, ueFlowConfirmed: true }, ruleDomains: { confirmation: { confirmed: false } } }), "interaction_preview");
  assert.equal(ReviewWorkspace.routeForModel({ stages: [{ confirmation: { confirmed: false } }], reviewState: { flowConfirmed: true } }), "stage");
  assert.equal(ReviewWorkspace.routeForModel({ reviewState: {} }), "flow");
});

test("legacy saved rules and preview views skip the retired UE flow gate", () => {
  const model = { reviewState: { flowConfirmed: true }, stages: [{ id: "STG-001", confirmation: { confirmed: true } }] };
  const rebuilt = ReviewWorkspace.rebuild(model, "saved", { view: "rules", model });
  assert.equal(rebuilt.view, "interaction_preview");
  assert.equal(ReviewWorkspace.rebuild(model, "saved", { view: "preview", model }).view, "interaction_preview");
});

test("gameplay routes advance from chapter review through diagrams and tables to final preview", () => {
  const interaction = { revision: 2, reviewState: { status: "preview_ready", previewRevision: 2 } };
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { directory: { status: "draft" }, reviewState: { interactionHandoffConfirmed: false }, chapters: [] } }), "gameplay_directory");
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { directory: { status: "confirmed" }, reviewState: { interactionHandoffConfirmed: false }, chapters: [{ confirmation: { confirmed: false } }] } }), "interaction_preview");
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: false } }] } }), "gameplay");
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [{ status: "open" }] } }), "diagrams");
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [{ status: "reviewed" }], diagramReview: { status: "ready" } } }), "tables");
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [{ status: "reviewed" }], diagramReview: { status: "ready" }, tables: [{ status: "open" }], tableReview: { status: "ready" } } }), "tables");
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [{ status: "reviewed" }], diagramReview: { status: "ready" }, tables: [{ status: "reviewed" }], tableReview: { status: "ready" } } }), "final_preview");
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [], diagramReview: { status: "ready" }, tables: [], tableReview: { status: "ready" } } }), "final_preview");
  for (const status of ["open", "stale", "revising"]) {
    assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel: { chapters: [{ confirmation: { confirmed: true } }], diagrams: [{ status }] } }), "diagrams");
  }
});

test("deleted legacy tables never block the final document route", () => {
  const interaction = { revision: 6, stages: [], reviewState: { flowConfirmed: true, ueFlowConfirmed: true, status: "preview_ready", previewRevision: 6 }, quality: { qualified: true } };
  const gameplayReviewModel = {
    chapters: [{ confirmation: { confirmed: true } }],
    diagrams: [], diagramReview: { status: "ready" },
    tables: [
      { id: "GTB-current", status: "reviewed", optional: true },
      { id: "GTB-legacy", status: "deleted", optional: false },
    ],
    tableReview: { status: "ready" },
  };
  assert.equal(ReviewWorkspace.routeForModel({ ...interaction, gameplayReviewModel }), "final_preview");
});

test("a background gameplay refresh does not kick the planner out of an earlier review step", () => {
  const gameplay = { directory: { status: "confirmed" }, chapters: [{ confirmation: { confirmed: false } }], reviewState: { interactionHandoffConfirmed: true } };
  const model = { revision: 4, stages: [], quality: { qualified: true }, reviewState: { flowConfirmed: true }, gameplayReviewModel: gameplay };
  const previous = { ...ReviewWorkspace.initialState(model), view: "gameplay_directory", model };

  assert.equal(ReviewWorkspace.rebuild({ ...model, revision: 5 }, "synced", previous).view, "gameplay_directory");
});

test("saved review workspaces remain available after a later analysis failure", () => {
  assert.equal(ReviewWorkspace.routeForJob({ status: "completed", reviewModel: {} }), "review_workspace");
  assert.equal(ReviewWorkspace.routeForJob({ status: "failed", reviewModel: { revision: 45 } }), "review_workspace");
  assert.equal(ReviewWorkspace.routeForJob({ status: "completed" }), "legacy_frames");
  assert.equal(ReviewWorkspace.routeForJob({ status: "running", reviewModel: {} }), "legacy_frames");
});

test("legacy completed jobs retain the frame reviewer fallback", () => {
  const route = ReviewWorkspace.routeForJob({ status: "completed", metadata: { mode: "interaction" }, frames: [{ id: "F0001" }] });
  assert.equal(route, "legacy_frames");
  assert.equal(ReviewWorkspace.routeForJob({ status: "completed", metadata: { mode: "interaction" }, reviewModel: { quality: { qualified: true } } }), "review_workspace");
});

test("canonical model rebuild keeps an analysis failure as a distinct read-only route", () => {
  const rebuilt = ReviewWorkspace.rebuild({ revision: 7, stages: [], quality: { qualified: false, blockers: ["NO_QUALIFIED_STAGE"] } }, "conflict_synced");
  assert.equal(rebuilt.view, "analysis_failed");
  assert.equal(rebuilt.saveStatus, "conflict_synced");
  assert.equal(rebuilt.selectedStageId, null);
});

test("history controls derive availability from canonical edit history", () => {
  assert.deepEqual(ReviewWorkspace.historyControls({ editHistory: { undo: [], redo: [{}] } }), { canUndo: false, canRedo: true });
  assert.deepEqual(ReviewWorkspace.historyControls({}), { canUndo: false, canRedo: false });
});

test("a review model revision invalidates a cached export preview", () => {
  const previous = { ...ReviewWorkspace.initialState({ revision: 1, stages: [{ id: "STG-001" }] }), preview: { revision: 1, exportReady: true } };
  const rebuilt = ReviewWorkspace.rebuild({ revision: 2, reviewState: {}, stages: [{ id: "STG-001" }] }, "saved", previous);
  assert.equal(rebuilt.preview, null);
});

test("model-backed preview readiness never creates a synthetic export payload", () => {
  const ready = ReviewWorkspace.initialState({ revision: 4, stages: [], reviewState: { status: "preview_ready", previewRevision: 4 } });
  const stale = ReviewWorkspace.initialState({ revision: 4, stages: [], reviewState: { status: "preview_ready", previewRevision: 3 } });

  assert.equal(ready.preview, null);
  assert.equal(ready.previewStatus, "idle");
  assert.equal(ReviewWorkspace.needsPreviewLoad({ ...ready, view: "preview" }), true);
  assert.equal(stale.preview, null);
  assert.equal(ReviewWorkspace.needsPreviewLoad(stale), false);
});

test("canonical rebuild requests a real preview instead of restoring a placeholder", () => {
  const rebuilt = ReviewWorkspace.rebuild({ revision: 5, stages: [], reviewState: { status: "preview", previewRevision: 5 } });

  assert.equal(rebuilt.preview, null);
  assert.equal(ReviewWorkspace.needsPreviewLoad(rebuilt), true);
});

test("retired competitor state never blocks the planning-only workflow", () => {
  const empty = ReviewWorkspace.initialState({ referenceBoards: { competitor: { assets: [], status: "pending" } } });
  assert.equal(ReviewWorkspace.competitorMutationBlocked(empty), false);
  assert.equal(ReviewWorkspace.competitorMutationBlocked({ ...empty, referenceBoardBusy: true }), false);
  assert.equal(ReviewWorkspace.competitorMutationBlocked({ ...empty, referenceBoardStates: { competitor: { status: "uploading" } } }), false);
  assert.equal(ReviewWorkspace.competitorMutationBlocked({ ...empty, referenceBoardStates: { competitor: { status: "failed", retry() {} } } }), false);
  assert.equal(ReviewWorkspace.competitorMutationBlocked({ ...empty, model: { referenceBoards: { competitor: { assets: [{ id: "asset-1" }] } } }, referenceBoardStates: { competitor: { status: "failed", retry() {} } } }), false);
  assert.equal(ReviewWorkspace.competitorMutationBlocked({ ...empty, referenceBoardStates: {} }), false);
});
