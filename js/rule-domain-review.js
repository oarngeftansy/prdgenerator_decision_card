(function (root) {
  const DOMAIN_KEYS = ["narrative", "guidance", "redDots"];
  const DOMAIN_LABELS = { narrative: "叙事", guidance: "引导", redDots: "红点" };
  const EMPTY_TEXT = "本次素材未展示，待确认";
  const RULE_FIELDS = {
    narrative: [["title", "规则标题"], ["triggerScene", "触发场景"], ["triggerNode", "触发节点"], ["presentation", "呈现方式"], ["continuation", "后续承接"]],
    guidance: [["title", "规则标题"], ["scopeCount", "覆盖数量"], ["prerequisite", "前置条件"], ["destination", "引导目标"]],
    redDots: [["title", "规则标题"], ["showCondition", "展示条件"], ["clearCondition", "消失条件"]],
  };

  function domainSummary(ruleDomains, key) {
    const rules = ruleDomains?.[key] || [];
    return { count: rules.length, pending: rules.filter((item) => item.unknownReason).length, emptyText: rules.length ? "" : EMPTY_TEXT };
  }

  function componentsForStage(model, stageId) { return (model.components || []).filter((item) => item.stageId === stageId); }

  function newRuleDraft(domain, stageId) {
    const common = { title: "", stageId: stageId || "", frameId: null, componentId: null, sourceLevel: "unknown", confidence: "低", unknownReason: "待确认" };
    if (domain === "narrative") return { ...common, triggerScene: "", triggerNode: "", presentation: "", continuation: "" };
    if (domain === "guidance") return { ...common, scopeCount: "", prerequisite: "", steps: [], destination: "" };
    return { ...common, showCondition: "", clearCondition: "", path: [] };
  }

  function reorderNested(domain, id, field, fromIndex, toIndex) { return { type: "reorder_rule_nested", domain, id, field, fromIndex, toIndex }; }

  function selectionExists(model, selection) {
    return selection?.type === "rule" && DOMAIN_KEYS.includes(selection.domain) && (model.ruleDomains?.[selection.domain] || []).some((item) => item.id === selection.id);
  }

  function element(tag, text = "", attrs = {}) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    Object.entries(attrs).forEach(([name, value]) => { if (value !== undefined && value !== null) node.setAttribute(name, String(value)); });
    return node;
  }

  function button(text, callback, { className = "rule-domain-action", disabled = false, label = text } = {}) {
    const node = element("button", text, { type: "button", "aria-label": label });
    node.className = className;
    node.disabled = Boolean(disabled);
    node.addEventListener("click", callback);
    return node;
  }

  function field(labelText, control) {
    const label = element("label", "", { class: "rule-domain-field" });
    label.append(element("span", labelText), control);
    return label;
  }

  function textInput(value = "", multiline = false) {
    const control = document.createElement(multiline ? "textarea" : "input");
    if (!multiline) control.type = "text";
    control.value = value || "";
    return control;
  }

  function selectInput(value, options) {
    const control = document.createElement("select");
    options.forEach(([optionValue, label]) => {
      const option = element("option", label, { value: optionValue });
      option.selected = String(optionValue) === String(value ?? "");
      control.append(option);
    });
    return control;
  }

  function nestedDraft(rule, field) {
    const items = rule[field] || [];
    const suffix = items.length + 1;
    return { id: `${rule.id}-${field}-${suffix}`, text: "", componentId: null };
  }

  function tabList(workspace, domain) {
    const tabs = element("div", "", { class: "rule-domain-tabs", role: "tablist", "aria-label": "规则域" });
    DOMAIN_KEYS.forEach((key) => {
      const summary = domainSummary(workspace.model.ruleDomains, key);
      const reviewed = workspace.reviewedDomains?.includes(key);
      const tab = button(`${DOMAIN_LABELS[key]} ${summary.count} · ${reviewed ? "已查看" : "待查看"}`, () => workspace.onSelectDomain?.(key), { className: "rule-domain-tab", label: `查看${DOMAIN_LABELS[key]}规则（${reviewed ? "已查看" : "待查看"}）` });
      tab.id = `rule-domain-tab-${key}`;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", `rule-domain-panel-${key}`);
      tab.setAttribute("aria-selected", String(domain === key));
      tab.tabIndex = domain === key ? 0 : -1;
      tab.addEventListener("keydown", (event) => {
        const keys = { ArrowLeft: -1, ArrowRight: 1, Home: -Infinity, End: Infinity };
        if (!(event.key in keys)) return;
        event.preventDefault();
        const current = DOMAIN_KEYS.indexOf(key);
        const next = event.key === "Home" ? 0 : event.key === "End" ? DOMAIN_KEYS.length - 1 : (current + keys[event.key] + DOMAIN_KEYS.length) % DOMAIN_KEYS.length;
        workspace.onSelectDomain?.(DOMAIN_KEYS[next], true);
      });
      tabs.append(tab);
    });
    return tabs;
  }

  function ruleList(workspace, domain, rules, selectedId) {
    const panel = element("aside", "", { class: "rule-domain-list", "aria-label": `${DOMAIN_LABELS[domain]}规则列表` });
    const summary = domainSummary(workspace.model.ruleDomains, domain);
    panel.append(element("h3", `${DOMAIN_LABELS[domain]}规则`));
    if (!rules.length) panel.append(element("p", summary.emptyText, { class: "rule-domain-muted" }));
    rules.forEach((rule, index) => {
      const row = element("div", "", { class: "rule-domain-list-row" });
      const select = button(rule.title || rule.id, () => workspace.onSelectRule?.(domain, rule.id), { className: `rule-domain-list-select${selectedId === rule.id ? " is-selected" : ""}`, label: `编辑 ${rule.title || rule.id}` });
      row.append(select);
      row.append(button("上移", () => workspace.onOperation?.([{ type: "reorder_rule", domain, id: rule.id, toIndex: index - 1 }]), { disabled: workspace.readOnly || index === 0, label: `上移 ${rule.title || rule.id}` }));
      row.append(button("下移", () => workspace.onOperation?.([{ type: "reorder_rule", domain, id: rule.id, toIndex: index === rules.length - 1 ? index : index + 1 }]), { disabled: workspace.readOnly || index === rules.length - 1, label: `下移 ${rule.title || rule.id}` }));
      panel.append(row);
    });
    panel.append(button("新增规则", () => workspace.onCreateRule?.(domain), { className: "btn primary rule-domain-action", disabled: workspace.readOnly, label: `新增${DOMAIN_LABELS[domain]}规则` }));
    return panel;
  }

  function nestedEditor(workspace, domain, rule, field) {
    const section = element("section", "", { class: "rule-domain-nested", "aria-label": field === "steps" ? "引导步骤" : "红点路径" });
    section.append(element("h4", field === "steps" ? "引导步骤" : "红点路径"));
    const values = rule[field] || [];
    values.forEach((item, index) => {
      const row = element("div", "", { class: "rule-domain-nested-row" });
      const text = textInput(item.text || item.label || "", true);
      const component = selectInput(item.componentId || "", [["", "未绑定组件"], ...componentsForStage(workspace.model, rule.stageId).map((candidate) => [candidate.id, candidate.name || candidate.id])]);
      row.append(field(index + 1, text), field("组件", component));
      row.append(button("保存", () => {
        const updated = values.map((current, currentIndex) => currentIndex === index ? { ...current, text: text.value, componentId: component.value || null } : current);
        workspace.onOperation?.([{ type: "upsert_rule", domain, rule: { id: rule.id, [field]: updated } }]);
      }, { disabled: workspace.readOnly }));
      row.append(button("上移", () => workspace.onOperation?.([reorderNested(domain, rule.id, field, index, index - 1)]), { disabled: workspace.readOnly || index === 0 }));
      row.append(button("下移", () => workspace.onOperation?.([reorderNested(domain, rule.id, field, index, index + 1)]), { disabled: workspace.readOnly || index === values.length - 1 }));
      row.append(button("删除", () => workspace.onOperation?.([{ type: "upsert_rule", domain, rule: { id: rule.id, [field]: values.filter((_, currentIndex) => currentIndex !== index) } }]), { className: "rule-domain-action btn warn", disabled: workspace.readOnly, label: `删除第${index + 1}项` }));
      section.append(row);
    });
    section.append(button(field === "steps" ? "新增步骤" : "新增路径节点", () => workspace.onOperation?.([{ type: "upsert_rule", domain, rule: { id: rule.id, [field]: [...values, nestedDraft(rule, field)] } }]), { disabled: workspace.readOnly }));
    return section;
  }

  function editor(workspace, domain, rule) {
    const panel = element("section", "", { class: "rule-domain-editor" });
    panel.append(element("h3", rule ? `编辑${DOMAIN_LABELS[domain]}规则` : `新增${DOMAIN_LABELS[domain]}规则`));
    panel.append(button("返回规则列表", () => workspace.onSetMobilePane?.("list"), { className: "rule-domain-back", label: "返回规则列表" }));
    const draft = rule ? { ...rule } : newRuleDraft(domain, workspace.selectedStageId);
    const form = element("form", "", { class: "rule-domain-form" });
    const stage = selectInput(draft.stageId, [["", "请选择页面阶段"], ...(workspace.model.stages || []).map((item) => [item.id, item.name || item.id])]);
    const frame = selectInput(draft.frameId || "", [["", "未绑定截图"], ...Object.keys(workspace.model.sources || {}).map((id) => [id, id])]);
    const component = selectInput(draft.componentId || "", [["", "未绑定组件"], ...componentsForStage(workspace.model, draft.stageId).map((item) => [item.id, item.name || item.id])]);
    stage.addEventListener("change", () => {
      const options = [["", "未绑定组件"], ...componentsForStage(workspace.model, stage.value).map((item) => [item.id, item.name || item.id])];
      component.replaceChildren(...options.map(([value, label]) => element("option", label, { value })));
    });
    form.append(field("页面阶段", stage), field("截图", frame), field("组件", component));
    const controls = Object.fromEntries(RULE_FIELDS[domain].map(([key, label]) => [key, textInput(draft[key], ["presentation", "continuation", "prerequisite", "showCondition", "clearCondition"].includes(key))]));
    RULE_FIELDS[domain].forEach(([key, label]) => form.append(field(label, controls[key])));
    const confidence = selectInput(draft.confidence || "低", [["高", "高"], ["中", "中"], ["低", "低"]]);
    const sourceLevel = selectInput(draft.sourceLevel || "unknown", [["observed", "已展示"], ["inferred", "推断"], ["unknown", "待确认"]]);
    const unknownReason = textInput(draft.unknownReason || "", true);
    form.append(field("置信度", confidence), field("证据级别", sourceLevel), field("待确认说明", unknownReason));
    form.append(button("保存规则", () => {
      const value = { ...draft, stageId: stage.value, frameId: frame.value || null, componentId: component.value || null, confidence: confidence.value, sourceLevel: sourceLevel.value, unknownReason: unknownReason.value, ...Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.value])) };
      workspace.onOperation?.([{ type: "upsert_rule", domain, rule: value }]);
    }, { className: "btn primary rule-domain-action", disabled: workspace.readOnly }));
    if (rule) form.append(button("删除规则", () => workspace.onOperation?.([{ type: "delete_rule", domain, id: rule.id }]), { className: "btn warn rule-domain-action", disabled: workspace.readOnly }));
    form.addEventListener("submit", (event) => event.preventDefault());
    panel.append(form);
    if (rule && (domain === "guidance" || domain === "redDots")) panel.append(nestedEditor(workspace, domain, rule, domain === "guidance" ? "steps" : "path"));
    return panel;
  }

  function render(workspace) {
    if (typeof document === "undefined" || !workspace?.root) return;
    const domain = DOMAIN_KEYS.includes(workspace.selectedRuleDomain) ? workspace.selectedRuleDomain : "narrative";
    workspace.onVisitDomain?.(domain);
    const tabs = tabList(workspace, domain);
    const boardRoot = element("div", "", { class: "rule-domain-reference-boards" });
    if (typeof ReferenceBoardAssets !== "undefined") ReferenceBoardAssets.render({
      root: boardRoot,
      boards: workspace.model.referenceBoards,
      planningCount: (workspace.model.stages || []).reduce((count, stage) => count + (stage.representativeFrames || []).length, 0),
      client: workspace.client,
      readOnly: workspace.readOnly,
      busy: workspace.referenceBoardBusy,
      states: workspace.referenceBoardStates,
      resolveAssetUrl: workspace.resolveAssetUrl,
      onMutate: workspace.onBoardMutation,
    });
    const panels = DOMAIN_KEYS.map((key) => {
      const domainRules = workspace.model.ruleDomains?.[key] || [];
      const selectedRule = domainRules.find((item) => item.id === workspace.selectedRuleId) || null;
      const panel = element("section", "", { class: "rule-domain-panel", id: `rule-domain-panel-${key}`, role: "tabpanel", "aria-labelledby": `rule-domain-tab-${key}` });
      panel.hidden = key !== domain;
      const layout = element("div", "", { class: `rule-domain-layout${key === domain && workspace.ruleMobilePane === "editor" ? " is-mobile-editor" : ""}` });
      layout.append(ruleList(workspace, key, domainRules, key === domain ? selectedRule?.id : null), editor(workspace, key, key === domain ? selectedRule : null));
      panel.append(layout);
      return panel;
    });
    workspace.root.replaceChildren(tabs, boardRoot, ...panels);
    if (workspace.focusRuleTab) document.getElementById(`rule-domain-tab-${workspace.focusRuleTab}`)?.focus?.();
  }

  const api = { DOMAIN_KEYS, domainSummary, componentsForStage, newRuleDraft, reorderNested, selectionExists, render };
  if (typeof module !== "undefined") module.exports = api;
  else root.RuleDomainReview = api;
})(typeof window !== "undefined" ? window : globalThis);
