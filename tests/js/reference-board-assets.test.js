const test = require("node:test");
const assert = require("node:assert/strict");
const ReferenceBoardAssets = require("../../js/reference-board-assets.js");

test("board upload manifest preserves visible selection order", () => {
  const files = [{ name: "ux_10.png" }, { name: "ux_2.png" }];
  assert.equal(ReferenceBoardAssets.manifest(files), JSON.stringify(["ux_10.png", "ux_2.png"]));
});

test("board summaries expose planning and competitor only", () => {
  const summary = ReferenceBoardAssets.summaries({
    ux: { assets: [{ id: "legacy" }], status: "ready" },
    planning: { status: "generated" },
    competitor: { assets: [], status: "pending" },
  }, 4);

  assert.deepEqual(summary.map(({ key, editable, label }) => [key, editable, label]), [
    ["planning", false, "自动生成"],
    ["competitor", true, "本次未提供"],
  ]);
  assert.equal(ReferenceBoardAssets.boardStatus(summary[1]).message, "本次未提供竞品参考（可选，不影响导出）");
});

test("moving an asset produces a complete stable order without changing its id", () => {
  const assets = [{ id: "UXA-001" }, { id: "UXA-002" }, { id: "UXA-003" }];
  assert.deepEqual(ReferenceBoardAssets.movedIds(assets, 0, 1), ["UXA-002", "UXA-001", "UXA-003"]);
  assert.deepEqual(ReferenceBoardAssets.movedIds(assets, 2, 1), ["UXA-001", "UXA-003", "UXA-002"]);
});

test("board state persists uploading and failed status for the affected board", () => {
  assert.deepEqual(ReferenceBoardAssets.boardStatus({ status: "pending" }, { status: "uploading" }), { status: "uploading", message: "正在保存素材…" });
  assert.deepEqual(ReferenceBoardAssets.boardStatus({ status: "ready" }, { status: "failed", error: "网络异常" }), { status: "failed", message: "网络异常" });
});
