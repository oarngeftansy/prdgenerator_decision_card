const test = require("node:test");
const assert = require("node:assert/strict");

const {
  selectTopLevelScreenshots,
  validateScreenshotCount,
  moveItem,
  buildImageManifest,
} = require("../../js/screenshot-input.js");

function fakeFile(name, type, webkitRelativePath = name) {
  return { name, type, size: 1, webkitRelativePath };
}

test("filters supported first-level images and sorts filenames naturally", () => {
  const result = selectTopLevelScreenshots([
    fakeFile("10.png", "image/png", "shots/10.png"),
    fakeFile("2.png", "image/png", "shots/2.png"),
    fakeFile("nested.jpg", "image/jpeg", "shots/child/nested.jpg"),
    fakeFile("notes.txt", "text/plain", "shots/notes.txt"),
  ]);

  assert.deepEqual(result.accepted.map((file) => file.name), ["2.png", "10.png"]);
  assert.equal(result.nestedCount, 1);
  assert.equal(result.ignoredCount, 1);
  assert.equal(result.folderName, "shots");
});

test("accepts only the inclusive 2 to 50 screenshot boundary", () => {
  assert.equal(validateScreenshotCount(1).valid, false);
  assert.equal(validateScreenshotCount(2).valid, true);
  assert.equal(validateScreenshotCount(42).valid, true);
  assert.equal(validateScreenshotCount(50).valid, true);
  assert.equal(validateScreenshotCount(51).valid, false);
});

test("reordering and manifest generation share the authoritative array order", () => {
  const moved = moveItem([{ id: "A", name: "a.png" }, { id: "B", name: "b.png" }], 1, 0);

  assert.deepEqual(buildImageManifest(moved), [
    { clientId: "B", originalName: "b.png", order: 1 },
    { clientId: "A", originalName: "a.png", order: 2 },
  ]);
  assert.deepEqual(moveItem(moved, -1, 0), moved);
});
