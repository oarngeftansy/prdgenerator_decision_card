const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

const css = fs.readFileSync("css/style.css", "utf8");
const interaction = fs.readFileSync("js/flow-review.js", "utf8");
const preview = fs.readFileSync("js/export-preview.js", "utf8");
const gameplay = fs.readFileSync("js/gameplay-review.js", "utf8");

test("P2 uses the approved screenshot flow canvas with compact planner typography", () => {
  assert.match(css, /\.review-workspace\[data-active-view="flow"\][\s\S]*grid-template-columns:\s*220px\s+minmax\(0,\s*1fr\)\s+300px/);
  assert.match(css, /font-family:\s*"PingFang SC",\s*"Microsoft YaHei"/);
  assert.match(interaction, /interaction-flow-board/);
  assert.match(interaction, /跳转依据/);
});

test("P3 renders a page-focused interaction deliverable instead of a generic board summary", () => {
  assert.match(preview, /interaction-page-preview/);
  assert.match(preview, /页面信息/);
  assert.match(preview, /关联交互/);
  assert.match(css, /\.interaction-page-preview\s*\{[\s\S]*grid-template-columns:\s*220px\s+minmax\(0,\s*1fr\)\s+300px/);
});

test("P4 uses the target rule audit hierarchy and compact evidence column", () => {
  assert.match(gameplay, /gameplay-rule-audit/);
  assert.match(gameplay, /规则理解/);
  assert.match(gameplay, /玩法流程/);
  assert.match(gameplay, /配置与验证/);
  assert.equal((gameplay.match(/add\(4, "配置与验证"\)/g) || []).length, 1);
  assert.match(css, /\.gameplay-rule-audit\s*\{[\s\S]*grid-template-columns:\s*240px\s+320px\s+minmax\(0,\s*1fr\)/);
});

test("P2 does not label an evidence-poor stage as confirmed", () => {
  assert.match(interaction, /evidenceStatus/);
  assert.match(interaction, /已有补充画面 · 操作待复核/);
  assert.match(interaction, /hasCorrespondingFrame && actionIsObserved/);
});

test("P4 renumbers only visible audit modules", () => {
  assert.match(gameplay, /gameplay-rule-audit-section:not\(\[hidden\]\)/);
  assert.match(gameplay, /badge\.textContent = String\(index \+ 1\)/);
});
