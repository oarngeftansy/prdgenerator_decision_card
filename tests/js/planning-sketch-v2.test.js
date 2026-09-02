const test = require("node:test");
const assert = require("node:assert/strict");
const Sketch = require("../../js/planning-sketch-v2.js");

test("planning sketch renders mechanic-agnostic contexts", () => {
  const html = Sketch.render({
    version: "planning_sketch_v2",
    authority: "canonical_rule_projection",
    ruleCount: 3,
    contexts: [
      {contextType: "gameplay_context", title: "场景移动", interactions: [{publicationState: "confirmed", ruleRefs: ["R-MOVE"], action: "角色按照通行规则更新位置", trigger: "方向输入", result: "位置更新"}]},
      {contextType: "ui_surface", title: "商店交易", interactions: [{publicationState: "inferred", ruleRefs: ["R-SHOP"], action: "点击购买后校验货币并提交交易", result: "获得商品"}]},
      {contextType: "system_context", title: "离线生产", interactions: [{publicationState: "proposed", ruleRefs: ["R-SIM"], action: "系统累计离线产出", result: "生成可领取产出"}]},
    ],
  });
  assert.match(html, /data-authority="canonical_rule_projection"/);
  assert.match(html, /场景移动/);
  assert.match(html, /商店交易/);
  assert.match(html, /离线生产/);
  assert.match(html, /data-rule-refs="R-MOVE"/);
});

test("inferred and proposed use yellow visual state without provenance labels", () => {
  const html = Sketch.render({
    version: "planning_sketch_v2",
    ruleCount: 2,
    contexts: [{contextType: "system_context", title: "资源结算", interactions: [
      {publicationState: "inferred", action: "结算完成后写入资源余额"},
      {publicationState: "proposed", action: "重复结算请求只生效一次"},
    ]}],
  });
  assert.equal((html.match(/data-publication-visual="yellow"/g) || []).length, 2);
  assert.doesNotMatch(html, /【推断】|【建议】|黄色：推断|根据素材推测|待确认|可能|或许/);
});

test("conflict is red and confirmed remains normal", () => {
  assert.equal(Sketch.visualState("conflict"), "conflict");
  assert.equal(Sketch.visualState("confirmed"), "confirmed");
  assert.equal(Sketch.visualState("inferred"), "yellow");
  assert.equal(Sketch.visualState("proposed"), "yellow");
});

test("missing canonical sketch has neutral empty state instead of review language", () => {
  const html = Sketch.render(null);
  assert.match(html, /策划草图尚未生成/);
  assert.doesNotMatch(html, /待确认|推测|可能/);
});
