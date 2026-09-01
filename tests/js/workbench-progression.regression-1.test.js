const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

const backend = fs.readFileSync("js/backend.js", "utf8");

function section(start, end) {
  return backend.slice(backend.indexOf(start), backend.indexOf(end, backend.indexOf(start)));
}

test("all explicit cross-page progressions share URL, persistence, and navigation-intent handling", () => {
  const helper = section("function navigateReviewWorkspace", "function requestedReviewViewFromUrl");
  assert.match(helper, /reviewUiInteractionVersion \+= 1/);
  assert.match(helper, /setReviewWorkspaceView\(view\)/);
  assert.match(helper, /renderReviewWorkspace\(state\.reviewWorkspace\.model\)/);
  assert.match(helper, /syncReviewViewUrl\(view\)/);
  assert.match(helper, /persistReviewUiState/);

  const diagrams = section("function renderGameplayDiagramWorkspace", "function requestedReviewViewFromUrl");
  assert.match(diagrams, /onContinue:\s*\(\)\s*=>\s*navigateReviewWorkspace\("tables"\)/);

  const tables = section("function renderGameplayTableWorkspace", "function appendGameplayGenerationLog");
  assert.match(tables, /onContinue:\s*\(\)\s*=>\s*navigateReviewWorkspace\("final_preview"/);

  const preview = section('if (state.reviewWorkspace.view === "interaction_preview")', "function renderAnalysisFailedWorkspace");
  assert.match(preview, /onContinue:\s*gameplayDraftReady\s*\?\s*enterExistingGameplayReview\s*:\s*runGameplayGeneration/);
  assert.match(preview, /onRoute:[\s\S]*navigateReviewWorkspace\(route\.view\)/);

  const handoff = section("async function enterExistingGameplayReview", "function runGameplayOperations");
  assert.match(handoff, /await client\.generate\(backendConfigForm\(\)\)/);
  assert.match(handoff, /await client\.load\(\)/);
  assert.match(handoff, /navigateReviewWorkspace\("gameplay",\s*\{\s*expectedUiVersion:\s*actionUiVersion\s*\}\)/);
});

test("automatic completion routes use the same deterministic progression helper", () => {
  const advance = section("function advanceToCurrentReviewRoute", "function makeGameplayOperationQueue");
  assert.match(advance, /const routedView = ReviewWorkspace\.routeForModel\(model\)/);
  assert.match(advance, /const targetView = order\[routedView\] < order\[currentView\] \? currentView : routedView/);
  assert.match(advance, /navigateReviewWorkspace\(targetView/);

  const interactionConfirmation = section("async function runReviewConfirmation", "async function runReviewOperations");
  assert.match(interactionConfirmation, /navigateReviewWorkspace\(nextView,\s*\{\s*expectedUiVersion:\s*actionUiVersion\s*\}\)/);
  assert.match(interactionConfirmation, /navigateReviewWorkspace\("interaction_preview",\s*\{\s*expectedUiVersion:\s*actionUiVersion\s*\}\)/);
  assert.match(interactionConfirmation, /kind === "ue_flow"[\s\S]*navigateReviewWorkspace\(nextView,\s*\{\s*expectedUiVersion:\s*actionUiVersion\s*\}\)[\s\S]*loadReviewPreview\(\{\s*flushPending:\s*false\s*\}\)/);
});
