(function (root, factory) {
const GameplayWorkspaceApi = factory();
if (typeof module !== "undefined" && module.exports) module.exports = GameplayWorkspaceApi;
else root.GameplayWorkspace = GameplayWorkspaceApi;
})(typeof window !== "undefined" ? window : globalThis, function () {
function initialState(model = {}) {
  return { model, selectedChapterId: model.chapters?.[0]?.id || null, panel: "chapters", evidenceDrawer: null, selectedDiagramId: null, selectedTableId: null, saveStatus: "saved", preview: null, previewStatus: "idle", previewError: "", finalPreviewEligible: model.reviewState?.previewRevision === model.revision };
}

function canEnter(interactionModel) {
  const gate = interactionModel?.gate || interactionModel?.reviewGate;
  return interactionModel?.reviewState?.previewRevision === interactionModel?.revision && gate?.exportReady === true;
}

function validId(items, id) { return (items || []).some((item) => item?.id === id) ? id : null; }

function rebuild(model = {}, saveStatus = "saved", previous = null) {
  const base = initialState(model);
  const sameRevision = previous?.model?.revision === model.revision;
  const preview = sameRevision && (previous?.preview?.revision === model.revision || previous?.preview?.gameplayRevision === model.revision) ? previous.preview : null;
  const previewStatus = preview ? "ready" : sameRevision && ["loading", "failed"].includes(previous?.previewStatus) ? previous.previewStatus : "idle";
  return {
    ...base,
    selectedChapterId: validId(model.chapters, previous?.selectedChapterId) || base.selectedChapterId,
    panel: previous?.panel || base.panel,
    evidenceDrawer: validId(model.evidenceAnchors, previous?.evidenceDrawer),
    selectedDiagramId: validId(model.diagrams, previous?.selectedDiagramId),
    selectedTableId: validId(model.tables, previous?.selectedTableId),
    saveStatus,
    preview,
    previewStatus,
    previewError: previewStatus === "failed" ? previous?.previewError || "" : "",
    activeTab: previous?.activeTab || "content",
    expandedGroups: Array.isArray(previous?.expandedGroups) ? previous.expandedGroups : [],
    editedGroups: Array.isArray(previous?.editedGroups) ? previous.editedGroups : [],
    contextStatus: previous?.contextStatus || "",
    diagramRequestState: previous?.diagramRequestState || { generation: {}, byId: {} },
  };
}

function selectChapter(state, selectedChapterId) { return { ...state, selectedChapterId: validId(state.model?.chapters, selectedChapterId) }; }
function setPanel(state, panel) { return { ...state, panel }; }
function openEvidence(state, evidenceDrawer) { return { ...state, evidenceDrawer: validId(state.model?.evidenceAnchors, evidenceDrawer) }; }
function closeEvidence(state) { return { ...state, evidenceDrawer: null }; }
function historyControls(model) {
  const history = model?.editHistory || {};
  return { canUndo: Array.isArray(history.undo) ? history.undo.length > 0 : Array.isArray(history) && history[0]?.undo?.length > 0, canRedo: Array.isArray(history.redo) ? history.redo.length > 0 : Array.isArray(history) && history[0]?.redo?.length > 0 };
}

return { initialState, rebuild, selectChapter, setPanel, openEvidence, closeEvidence, canEnter, historyControls };
});
