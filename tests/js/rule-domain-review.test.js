const test = require("node:test");
const assert = require("node:assert/strict");
const RuleDomainReview = require("../../js/rule-domain-review.js");

class FakeNode {
  constructor(document, tag) { this.document = document; this.tag = tag; this.children = []; this.attrs = {}; this.listeners = {}; this.hidden = false; }
  set id(value) { this._id = value; this.document.nodes.set(value, this); }
  get id() { return this._id; }
  setAttribute(name, value) { this.attrs[name] = String(value); if (name === "id") this.id = String(value); }
  getAttribute(name) { return this.attrs[name]; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  dispatch(name, event = {}) { this.listeners[name]?.({ preventDefault() {}, ...event }); }
  focus() { this.document.activeElement = this; }
}

class FakeDocument {
  constructor() { this.nodes = new Map(); this.activeElement = null; }
  createElement(tag) { return new FakeNode(this, tag); }
  getElementById(id) { return this.nodes.get(id) || null; }
}

test("tabs keep fixed one-to-one panels and restore focus after arrow navigation", () => {
  const previousDocument = global.document;
  const document = new FakeDocument();
  const model = { stages: [], sources: {}, components: [], ruleDomains: { narrative: [], guidance: [], redDots: [] } };
  const root = document.createElement("div");
  const render = (selectedRuleDomain, focusRuleTab = null) => RuleDomainReview.render({
    root, model, selectedRuleDomain, selectedRuleId: null, ruleMobilePane: "list", focusRuleTab,
    onSelectDomain: (domain, focus) => render(domain, focus ? domain : null), onVisitDomain: () => {},
  });
  global.document = document;
  try {
    render("narrative");
    for (const domain of RuleDomainReview.DOMAIN_KEYS) {
      const tab = document.getElementById(`rule-domain-tab-${domain}`);
      const panel = document.getElementById(`rule-domain-panel-${domain}`);
      assert.ok(tab && panel);
      assert.equal(tab.getAttribute("aria-controls"), panel.id);
      assert.equal(panel.getAttribute("aria-labelledby"), tab.id);
      assert.equal(panel.hidden, domain !== "narrative");
    }
    document.getElementById("rule-domain-tab-narrative").dispatch("keydown", { key: "ArrowRight" });
    assert.equal(document.activeElement.id, "rule-domain-tab-guidance");
    assert.equal(document.getElementById("rule-domain-panel-narrative").hidden, true);
    assert.equal(document.getElementById("rule-domain-panel-guidance").hidden, false);
  } finally {
    global.document = previousDocument;
  }
});

test("empty domains remain empty and expose the approved pending copy", () => {
  const summary = RuleDomainReview.domainSummary({ narrative: [], guidance: [], redDots: [] }, "narrative");
  assert.deepEqual(summary, { count: 0, pending: 0, emptyText: "本次素材未展示，待确认" });
});

test("components are filtered by the selected stage", () => {
  const model = { components: [{ id: "CMP-1", stageId: "STG-1" }, { id: "CMP-2", stageId: "STG-2" }] };
  assert.deepEqual(RuleDomainReview.componentsForStage(model, "STG-1").map((item) => item.id), ["CMP-1"]);
});

test("guidance steps and red-dot paths produce stable reorder operations", () => {
  assert.deepEqual(RuleDomainReview.reorderNested("guidance", "GDE-1", "steps", 2, 0), {
    type: "reorder_rule_nested", domain: "guidance", id: "GDE-1", field: "steps", fromIndex: 2, toIndex: 0,
  });
  assert.deepEqual(RuleDomainReview.reorderNested("redDots", "RDT-1", "path", 1, 0), {
    type: "reorder_rule_nested", domain: "redDots", id: "RDT-1", field: "path", fromIndex: 1, toIndex: 0,
  });
});

test("new drafts carry only the fields required by their explicit domain", () => {
  const draft = RuleDomainReview.newRuleDraft("guidance", "STG-1");
  assert.equal(draft.stageId, "STG-1");
  assert.deepEqual(draft.steps, []);
  assert.equal("path" in draft, false);
});

test("rule selection is valid only within its explicit domain", () => {
  const model = { ruleDomains: { narrative: [{ id: "NAR-1" }], guidance: [], redDots: [{ id: "RDT-1" }] } };
  assert.equal(RuleDomainReview.selectionExists(model, { type: "rule", domain: "redDots", id: "RDT-1" }), true);
  assert.equal(RuleDomainReview.selectionExists(model, { type: "rule", domain: "guidance", id: "RDT-1" }), false);
});
