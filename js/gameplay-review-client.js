(function (root, factory) {
const GameplayReviewClientApi = factory(typeof module !== "undefined" && module.exports ? require("./review-client.js") : root.ReviewClient);
if (typeof module !== "undefined" && module.exports) module.exports = GameplayReviewClientApi;
else root.GameplayReviewClient = GameplayReviewClientApi;
})(typeof window !== "undefined" ? window : globalThis, function (ReviewClient) {
class GameplayReviewClient {
  constructor(baseUrl, jobId) { this.baseUrl = baseUrl; this.jobId = jobId; }
  async request(path = "", options = {}) {
    const response = await fetch(`${this.baseUrl}/api/jobs/${this.jobId}${path}`, options);
    const body = await response.json();
    if (!response.ok) {
      const detail = body.detail;
      const message = typeof detail === "object" && detail
        ? (detail.message || detail.kind || JSON.stringify(detail))
        : detail;
      const error = new Error(message || "Gameplay review request failed");
      error.status = response.status;
      error.currentRevision = detail?.currentRevision;
      error.kind = detail?.kind;
      error.retryable = detail?.retryable;
      throw error;
    }
    return body;
  }
  load() { return this.request("/gameplay-review-model"); }
  generate(config) { return this.request("/gameplay-review/generate", { method: "POST", body: config }); }
  operations(expectedRevision, operations, { keepalive = false } = {}) { return this.request("/gameplay-review-model/operations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, operations }), keepalive }); }
  reviewRule(ruleId, expectedRevision, decision, patch = {}) { return this.operations(expectedRevision, [{ type: "review_rule", ruleId, decision, patch }]); }
  undo(expectedRevision) { return this.request("/gameplay-review-model/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  redo(expectedRevision) { return this.request("/gameplay-review-model/redo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  confirmChapter(chapterId, expectedRevision, decision = "approved") { return this.request("/gameplay-review-model/confirm-chapter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chapterId, expectedRevision, ...(decision !== "approved" ? { decision } : {}) }) }); }
  confirmDirectory(expectedRevision, config = {}) { return this.request("/gameplay-review-model/confirm-directory", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, ...config }) }); }
  reopenChapter(chapterId, expectedRevision) { return this.request("/gameplay-review-model/reopen-chapter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chapterId, expectedRevision }) }); }
  context(chapterId, expectedRevision, anchorFrameId, missingFields, manualTimestamp = null) { return this.request(`/gameplay-review/chapters/${chapterId}/context`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, anchorFrameId, missingFields, ...(manualTimestamp == null ? {} : { manualTimestamp }) }) }); }
  generateDiagram(expectedRevision, chapterIds, diagramType) { return this.request("/gameplay-review-model/diagrams", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, chapterIds, diagramType }) }); }
  diagramAction(action, expectedRevision, diagramId, feedback = "") { return this.request(`/gameplay-review-model/diagrams/${diagramId}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, ...(feedback ? { feedback } : {}) }) }); }
  feedbackDiagram(expectedRevision, diagramId, feedback) { return this.diagramAction("feedback", expectedRevision, diagramId, feedback); }
  regenerateDiagram(expectedRevision, diagramId, feedback) { return this.diagramAction("regenerate", expectedRevision, diagramId, feedback); }
  approveDiagram(expectedRevision, diagramId) { return this.diagramAction("approve", expectedRevision, diagramId); }
  deleteDiagram(expectedRevision, diagramId) { return this.diagramAction("delete", expectedRevision, diagramId); }
  diagrams(expectedRevision) { return this.request("/gameplay-review-model/diagrams", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  tables(expectedRevision) { return this.request("/gameplay-review-model/tables", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) }); }
  tableAction(action, expectedRevision, tableId, feedback = "") { return this.request(`/gameplay-review-model/tables/${tableId}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, ...(feedback ? { feedback } : {}) }) }); }
  preparePublication(expectedRevision, config = {}) { return this.request("/master-plan/prepare-publication", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision, ...config }) }); }
  async finalPreview(expectedRevision, config = {}) {
    await this.preparePublication(expectedRevision, config);
    return this.request("/master-plan/final-preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expectedRevision }) });
  }
}

function createOperationQueue(options) {
  if (!ReviewClient?.createOperationQueue) throw new Error("ReviewClient operation queue is required");
  return ReviewClient.createOperationQueue(options);
}

GameplayReviewClient.createOperationQueue = createOperationQueue;
return GameplayReviewClient;
});