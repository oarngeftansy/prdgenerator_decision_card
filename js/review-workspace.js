const WORKBENCH_STEPS = Object.freeze([
  { id: "p1", label: "确认玩法目录", views: ["gameplay_directory"] },
  { id: "p2", label: "审核交互", views: ["flow", "stage"] },
  { id: "p3", label: "预览交互交付物", views: ["interaction_preview"] },
  { id: "p4", label: "审核玩法规则", views: ["gameplay"] },
  { id: "p5", label: "审核必要图解", views: ["diagrams"] },
  { id: "p6", label: "审核玩法表格", views: ["tables"] },
  { id: "p7", label: "预览并发布完整文档", views: ["final_preview"] },
]);

function stepForView(view) {
  return WORKBENCH_STEPS.find((step) => step.views.includes(view)) || null;
}

function modelPreviewIsCurrent(model) {
  const review = model?.reviewState || {};
  const ready = ["preview", "preview_ready"].includes(review.status);
  return ready && review.previewRevision === model?.revision;
}

function stageStatus(stage = {}) {
  if (stage.confirmation?.confirmed) return "complete";
  const warnings = stage.validation?.warnings || stage.warnings || [];
  return warnings.length ? "needs_attention" : "pending";
}

function nextUnconfirmedStageId(model = {}, currentStageId = "") {
  const stages = [...(model.stages || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  const currentIndex = stages.findIndex((stage) => stage.id === currentStageId);
  const following = currentIndex < 0 ? stages : [...stages.slice(currentIndex + 1), ...stages.slice(0, currentIndex)];
  return following.find((stage) => !stage.confirmation?.confirmed)?.id || null;
}

function initialState(model) {
  return {
    model,
    view: "flow",
    selectedStageId: model.stages?.[0]?.id || null,
    selectedTransitionId: null,
    selectedFrameId: null,
    selection: null,
    preview: null,
    previewStatus: "idle",
    previewError: "",
    referenceBoardBusy: false,
    referenceBoardStates: {},
    showAllFrames: false,
    saveStatus: "saved",
    confirmStatus: "idle",
    confirmError: "",
    projectDrawerOpen: false,
  };
}

function select(state, selection) {
  return {
    ...state,
    selection,
    selectedStageId: selection.stageId || state.selectedStageId,
    selectedTransitionId: selection.type === "transition" ? selection.id : null,
    selectedFrameId: selection.frameId || state.selectedFrameId,
  };
}

function selectStage(state, model, stageId) {
  const stage = (model.stages || []).find((item) => item.id === stageId);
  if (!stage || stage.id === state.selectedStageId) return state;
  return {
    ...state,
    selectedStageId: stage.id,
    selectedFrameId: stage.representativeFrames?.[0]?.frameId || null,
    selectedTransitionId: null,
    selection: null,
  };
}

function routeForModel(model) {
  const stages = model.stages || [];
  const allStagesConfirmed = Boolean(model.reviewState?.flowConfirmed) && stages.every((stage) => stage.confirmation?.confirmed);
  if (model.quality?.qualified === false) return "analysis_failed";
  const earlyGameplay = model.gameplayReviewModel;
  if (earlyGameplay?.directory && earlyGameplay.directory.status !== "confirmed") return "gameplay_directory";
  if (!modelPreviewIsCurrent(model) && !allStagesConfirmed) return model.reviewState?.flowConfirmed ? "stage" : "flow";
  const gameplay = earlyGameplay;
  if (!gameplay) return "interaction_preview";
  if (gameplay.reviewState?.interactionHandoffConfirmed === false) return "interaction_preview";
  if (!(gameplay.chapters || []).every((chapter) => chapter.confirmation?.confirmed) || !(gameplay.chapters || []).length) return "gameplay";
  const diagrams = gameplay.diagrams || [];
  const activeDiagrams = diagrams.filter((diagram) => !(diagram.status === "deleted" && diagram.optional !== false));
  if (gameplay.diagramReview?.status !== "ready" || !activeDiagrams.every((diagram) => diagram.status === "reviewed")) return "diagrams";
  const tables = (gameplay.tables || []).filter((table) => table.status !== "deleted");
  if (gameplay.tableReview?.status !== "ready" || !tables.every((table) => table.status === "reviewed")) return "tables";
  return "final_preview";
}

function routeForJob(job) {
  const reusableReview = job?.reviewModel && ["completed", "failed"].includes(job?.status);
  return reusableReview ? "review_workspace" : "legacy_frames";
}

function failedModelForJob(job = {}) {
  const sources = Object.fromEntries((job.frames || []).map((frame) => [frame.id, {
    id: frame.id,
    frameId: frame.id,
    imageUrl: frame.imageUrl || "",
    sourceName: frame.sourceName || "",
  }]));
  return {
    revision: Number.isInteger(job.reviewModel?.revision) ? job.reviewModel.revision : 0,
    stages: [], transitions: [], sources,
    quality: { qualified: false, blockers: [job.error || "视觉分析未达到交付标准"] },
    reviewState: { status: "analysis_failed" },
    editHistory: { undo: [], redo: [] },
  };
}

function selectionExists(model, selection) {
  if (!selection) return false;
  const collections = { stage: "stages", transition: "transitions", region: "regions", component: "components", constraint: "crossStateConstraints" };
  const collection = collections[selection.type];
  if (collection && !(model[collection] || []).some((item) => item.id === selection.id)) return false;
  return !selection.frameId || !model.sources || Boolean(model.sources[selection.frameId]);
}

function rebuild(model, saveStatus = "saved", previous = null) {
  const base = initialState(model);
  const saved = previous || (typeof ReviewClient !== "undefined" ? ReviewClient.restoreUiState(model, model.reviewUiState) : null);
  const stageIds = new Set((model.stages || []).map((item) => item.id));
  const transitionIds = new Set((model.transitions || []).map((item) => item.id));
  const selectedTransitionId = transitionIds.has(saved?.selectedTransitionId) ? saved.selectedTransitionId : null;
  const selectedStageId = stageIds.has(saved?.selectedStageId) ? saved.selectedStageId : base.selectedStageId;
  const selectedFrameId = model.sources?.[saved?.selectedFrameId] ? saved.selectedFrameId : null;
  const selection = selectionExists(model, saved?.selection) ? saved.selection : null;
  const savedView = ["rules", "preview"].includes(saved?.view) ? "interaction_preview" : saved?.view;
  const routedView = routeForModel(model);
  const reviewOrder = { gameplay_directory: 0, flow: 1, stage: 2, ue_flow: 3, interaction_preview: 4, gameplay: 5, diagrams: 6, tables: 7, final_preview: 8 };
  const savedIsReachable = Object.hasOwn(reviewOrder, savedView) && reviewOrder[savedView] <= reviewOrder[routedView];
  const view = model.quality?.qualified === false ? routedView : savedIsReachable ? savedView : routedView;
  const sameRevision = previous?.model?.revision === model.revision;
  const preview = sameRevision && previous?.preview?.revision === model.revision && previous?.preview?.boardPreviewSvg ? previous.preview : null;
  const previewStatus = preview ? "ready" : sameRevision && ["loading", "failed"].includes(previous?.previewStatus) ? previous.previewStatus : "idle";
  const previewError = previewStatus === "failed" ? previous?.previewError || "" : "";
  const referenceBoardStates = Object.fromEntries(Object.entries(saved?.referenceBoardStates || {}).filter(([, item]) => item && ["uploading", "failed"].includes(item.status)).map(([key, item]) => [key, { ...item }]));
  return { ...base, view, saveStatus, preview, previewStatus, previewError, projectDrawerOpen: Boolean(saved?.projectDrawerOpen), showAllFrames: Boolean(saved?.showAllFrames), selectedStageId, selectedFrameId, selectedTransitionId, referenceBoardBusy: Boolean(saved?.referenceBoardBusy), referenceBoardStates, selection };
}

function needsPreviewLoad(state) {
  return ["interaction_preview", "preview"].includes(state?.view) && modelPreviewIsCurrent(state.model) && !state.preview?.boardPreviewSvg && state.previewStatus === "idle";
}

function competitorMutationBlocked(state) {
  return false;
}

function competitorMutationBlockMessage(state) {
  return "";
}

function showAllFrames(state, value) { return { ...state, showAllFrames: Boolean(value) }; }

function historyControls(model) {
  const history = model?.editHistory || {};
  return { canUndo: Array.isArray(history.undo) && history.undo.length > 0, canRedo: Array.isArray(history.redo) && history.redo.length > 0 };
}

function suggestionOperation(entity, id, field, value) {
  if (entity === "region" && field === "bounds") return { type: "set_region_bounds", id, bounds: value };
  if (entity === "transition" && field === "anchor") return { type: "set_anchor", id, anchor: value };
  if (entity === "stage" && field === "representativeFrames") return { type: "set_representative_frames", id, frames: value };
  if (entity === "stage" && field === "smallLoop") return { type: "set_small_loop", id, smallLoop: value };
  if (entity === "component" && field === "states") return { type: "set_component_state", componentId: id, states: value };
  return { type: "set", entity, id, field, value };
}

const ReviewWorkspaceApi = { WORKBENCH_STEPS, stepForView, initialState, select, selectStage, stageStatus, nextUnconfirmedStageId, routeForModel, routeForJob, failedModelForJob, rebuild, needsPreviewLoad, competitorMutationBlocked, competitorMutationBlockMessage, historyControls, showAllFrames, suggestionOperation };
if (typeof module !== "undefined") module.exports = ReviewWorkspaceApi;
else window.ReviewWorkspace = ReviewWorkspaceApi;
