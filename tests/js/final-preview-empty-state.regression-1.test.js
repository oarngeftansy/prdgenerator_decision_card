// Regression: ISSUE-UX96-001 — P7 idle state rendered as unstyled text in a mostly blank page.
// Found by /qa on 2026-08-25
// Report: artifacts/qa-formal-ux96-20260825/report.json
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

test("P7 idle generation action is presented as a deliberate centered state card", () => {
  const backend = fs.readFileSync("js/backend.js", "utf8");
  const css = fs.readFileSync("css/review-workspace.css", "utf8");
  const renderer = backend.slice(
    backend.indexOf("function renderCombinedFinalPreview"),
    backend.indexOf("async function loadCombinedFinalPreview"),
  );

  assert.match(renderer, /className = "final-preview-empty-state"/);
  assert.match(renderer, /emptyState\.append\(heading, message\)/);
  assert.match(css, /\.final-preview-empty-state\s*\{[^}]*margin:[^;]*auto/);
  assert.match(css, /\.final-preview-empty-state\s*\{[^}]*background:#fff/);
});
