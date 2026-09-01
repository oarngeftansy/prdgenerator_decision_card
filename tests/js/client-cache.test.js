const test = require("node:test");
const assert = require("node:assert/strict");
const Cache = require("../../js/client-cache.js");

function storage(initial) {
  const values = new Map(Object.entries(initial));
  return {
    get length() { return values.size; },
    key(index) { return [...values.keys()][index] || null; },
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

test("cache migration removes stale UI state but preserves jobs and API configuration", () => {
  const target = storage({
    vpr_gameplay_review_ui_old: "stale",
    vpr_planning_board_ui_old: "stale",
    vpr_last_job: "job-1",
    vpr_api_key: "secret-is-preserved",
  });

  assert.deepEqual(Cache.cleanup(target).sort(), ["vpr_gameplay_review_ui_old", "vpr_planning_board_ui_old"]);
  assert.equal(target.getItem("vpr_gameplay_review_ui_old"), null);
  assert.equal(target.getItem("vpr_planning_board_ui_old"), null);
  assert.equal(target.getItem("vpr_last_job"), "job-1");
  assert.equal(target.getItem("vpr_api_key"), "secret-is-preserved");
  assert.equal(target.getItem(Cache.SCHEMA_KEY), Cache.CURRENT_SCHEMA);
  assert.deepEqual(Cache.cleanup(target), []);
});
