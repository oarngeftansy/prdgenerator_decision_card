// Regression: a failed task without reviewModel could not open its workbench.
// Found by staged E2E acceptance on 2026-08-13.
const test = require("node:test");
const assert = require("node:assert/strict");
const ReviewWorkspace = require("../../js/review-workspace.js");

test("failed jobs without a review model get a read-only workbench model", () => {
  const model = ReviewWorkspace.failedModelForJob({
    status: "failed",
    error: "视觉模型连接失败",
    frames: [{ id: "F0001", imageUrl: "/frame.jpg", sourceName: "1.png" }],
  });
  assert.equal(model.quality.qualified, false);
  assert.deepEqual(model.quality.blockers, ["视觉模型连接失败"]);
  assert.equal(model.sources.F0001.imageUrl, "/frame.jpg");
  assert.equal(ReviewWorkspace.routeForModel(model), "analysis_failed");
});

test("analysis_failed is a persistent workbench deep-link view", () => {
  const source = require("node:fs").readFileSync(require("node:path").join(__dirname, "../../js/backend.js"), "utf8");
  assert.match(source, /"analysis_failed"\]\.includes\(value\)/);
  assert.match(source, /job\.status === "failed" && !job\.reviewModel && requestedReviewViewFromUrl\(\) === "analysis_failed"/);
});
