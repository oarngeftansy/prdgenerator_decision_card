(function (root) {
function groupCandidates(transitions) {
  const groups = new Map();
  for (const item of transitions || []) {
    if (!groups.has(item.sourceStageId)) groups.set(item.sourceStageId, []);
    groups.get(item.sourceStageId).push(item);
  }
  return Array.from(groups, ([stageId, items]) => ({ stageId, items }));
}

function visibleLane(model) {
  return [...(model.stages || [])]
    .sort((left, right) => left.order - right.order)
    .map((stage) => ({ ...stage, transitions: (model.transitions || []).filter((item) => item.included && item.sourceStageId === stage.id) }));
}

function canEditAnchor(transition) {
  return ["tap", "long_press"].includes(transition?.triggerType) && Boolean(transition?.componentId || transition?.regionId);
}

function anchorFromPointer(pointer, imageRect, bounds) {
  const rawX = (pointer.x - imageRect.left) / imageRect.width;
  const rawY = (pointer.y - imageRect.top) / imageRect.height;
  return {
    x: Math.max(bounds.x, Math.min(bounds.x + bounds.width, rawX)),
    y: Math.max(bounds.y, Math.min(bounds.y + bounds.height, rawY)),
  };
}

function element(tag, text = "", attributes = {}) {
  const node = document.createElement(tag);
  if (text) node.textContent = plannerText(text);
  Object.entries(attributes).forEach(([name, value]) => {
    if (value !== undefined && value !== null) node.setAttribute(name, String(value));
  });
  return node;
}

function plannerText(value) {
  const raw = String(value || "").trim();
  if (/(?:当前帧|当前截图|截图)[^)）。]*(?:静态展示|未捕捉到)[^)）。]*(?:点击|滑动|操作)/.test(raw)) {
    return "待策划选择操作";
  }
  if (/["'].*[（(]\s*[）)]/.test(raw)) return "";
  const cleaned = raw
    .replace(/\bBOSS\b/gi, "首领")
    .replace(/[（(]\s*inferred from damage numbers\s*[）)]/gi, "（根据伤害数字推测）")
    .replace(/\bdamage numbers\b/gi, "伤害数字")
    .replace(/\binferred from\b/gi, "根据画面推测")
    .replace(/(?:^|[，,；;。])[^，,；;。]*(?:鼠标|光标|悬停)[^，,；;。]*(?=$|[，,；;。])/g, "")
    .replace(/[（(]\s*[）)]/g, "")
    .replace(/[、，,；;。.]\s*[、，,；;。.]+/g, "。")
    .replace(/^[，,；;。、.\s]+|[，,；;。、.\s]+$/g, "");
  if (/^未知待确认(?:[：:].*)?$/.test(cleaned)) return "";
  if (!/[\p{L}\p{N}]/u.test(cleaned) || (!/[\u3400-\u9fff]/u.test(cleaned) && /[A-Za-z]/.test(cleaned))) return "待确认";
  const uncertain = cleaned.match(/^未知待确认\s*[（(](?:根据[^，,]*推测[，,]\s*)?(.+)[）)]$/);
  return uncertain ? uncertain[1].replace(/可能/g, "").trim() : cleaned.replace(/^请确认[：:]\s*/, "");
}

function containedImageRect(natural, viewport) {
  if (!(natural?.width > 0 && natural?.height > 0 && viewport?.width > 0 && viewport?.height > 0)) return null;
  const scale = Math.min(viewport.width / natural.width, viewport.height / natural.height);
  const width = natural.width * scale, height = natural.height * scale;
  return { x: viewport.x + (viewport.width - width) / 2, y: viewport.y + (viewport.height - height) / 2, width, height };
}
function mapEvidenceBox(box, rect) { return box && rect ? { left: rect.x + box.x * rect.width, top: rect.y + box.y * rect.height, width: box.width * rect.width, height: box.height * rect.height } : null; }
function anchorFromImageClick(pointer, rect) {
  if (!rect || pointer.x < rect.x || pointer.x > rect.x + rect.width || pointer.y < rect.y || pointer.y > rect.y + rect.height) return null;
  return { x: (pointer.x - rect.x) / rect.width, y: (pointer.y - rect.y) / rect.height };
}
function validEvidenceAnchor(anchor, bounds) { return Boolean(anchor && bounds && anchor.x >= bounds.x && anchor.x <= bounds.x + bounds.width && anchor.y >= bounds.y && anchor.y <= bounds.y + bounds.height); }
function sourceSemanticallySupportsStage(source, stage) {
  const purpose = meaningfulPlannerValue(source?.pageInfo?.purpose);
  if (!purpose) return false;
  const keywords = String(stage?.name || "").match(/[\u3400-\u9fff]{2}/g) || [];
  return keywords.some((token) => purpose.includes(token) || [...token].every((char) => purpose.includes(char)));
}
function sourceForStage(model, stage, transition = null, usedFrames = new Set()) {
  const candidates = [transition?.sourceFrameId, ...(stage?.representativeFrames || []).sort((a, b) => ({ entry: 0, key: 1, result: 2 }[a.role] ?? 3) - ({ entry: 0, key: 1, result: 2 }[b.role] ?? 3)).map((item) => item.frameId)].filter(Boolean);
  for (const frameId of [...new Set(candidates)]) {
    if (usedFrames.has(frameId)) continue;
    const source = model.sources?.[frameId];
    if (source && (!source.stageId || source.stageId === stage.id) && sourceSemanticallySupportsStage(source, stage)) return { frameId, source };
  }
  const stageOwned = [
    ...(stage?.representativeFrames || []).map((item) => item.frameId),
    ...Object.entries(model.sources || {}).filter(([, source]) => source?.stageId === stage.id).map(([frameId]) => frameId),
  ];
  for (const frameId of [...new Set(stageOwned)]) {
    if (usedFrames.has(frameId)) continue;
    const source = model.sources?.[frameId];
    if (source?.imageUrl && (!source.stageId || source.stageId === stage.id)) return { frameId, source, supplemental: true };
  }
  return { frameId: "", source: {} };
}

function connectorPoint(node, side, canvasRect) {
  const rect = node.getBoundingClientRect();
  return {
    x: (side === "left" ? rect.left : side === "right" ? rect.right : rect.left + rect.width / 2) - canvasRect.left,
    y: rect.top + rect.height / 2 - canvasRect.top,
  };
}

function connectorPath(gesture, edge, nextNode, canvasRect) {
  const start = connectorPoint(gesture, "center", canvasRect);
  const actionStart = connectorPoint(edge, "left", canvasRect);
  const actionEnd = connectorPoint(edge, "right", canvasRect);
  const target = connectorPoint(nextNode.querySelector(".interaction-flow-node-media") || nextNode, "left", canvasRect);
  return {
    before: `M ${start.x} ${start.y} L ${actionStart.x} ${actionStart.y}`,
    after: `M ${actionEnd.x} ${actionEnd.y} L ${target.x} ${target.y}`,
  };
}

function drawFlowConnectors(flow) {
  const svg = flow.querySelector(".interaction-flow-connectors");
  if (!svg || !flow.isConnected) return;
  svg.replaceChildren();
  const width = Math.max(flow.scrollWidth, flow.clientWidth);
  const height = Math.max(flow.scrollHeight, flow.clientHeight);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  const namespace = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(namespace, "defs");
  const marker = document.createElementNS(namespace, "marker");
  marker.setAttribute("id", "interaction-flow-arrowhead");
  marker.setAttribute("viewBox", "0 0 10 10"); marker.setAttribute("refX", "9"); marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "7"); marker.setAttribute("markerHeight", "7"); marker.setAttribute("orient", "auto-start-reverse");
  const arrow = document.createElementNS(namespace, "path"); arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  marker.append(arrow); defs.append(marker); svg.append(defs);
  const nodes = [...flow.querySelectorAll(".interaction-flow-node")];
  const edges = [...flow.querySelectorAll(".interaction-flow-edge")];
  const canvasRect = flow.getBoundingClientRect();
  edges.forEach((edge, index) => {
    const gesture = nodes[index]?.querySelector(".interaction-flow-gesture");
    const nextNode = nodes[index + 1];
    if (!gesture || !nextNode) return;
    const paths = connectorPath(gesture, edge, nextNode, canvasRect);
    [paths.before, paths.after].forEach((data, pathIndex) => {
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("d", data); path.setAttribute("class", "interaction-flow-connector-line");
      if (pathIndex === 1) path.setAttribute("marker-end", "url(#interaction-flow-arrowhead)");
      svg.append(path);
    });
  });
}

function button(text, onClick, options = {}) {
  const node = element("button", text, { type: "button", "aria-label": options.label || text });
  node.className = options.className || "flow-review-button";
  node.disabled = Boolean(options.disabled);
  node.addEventListener("click", onClick);
  return node;
}

function field(labelText, control) {
  const label = element("label", "", { class: "flow-review-field" });
  label.append(element("span", labelText));
  label.append(control);
  return label;
}

function textInput(value = "", multiline = false) {
  const node = document.createElement(multiline ? "textarea" : "input");
  if (!multiline) node.type = "text";
  node.value = plannerText(value);
  return node;
}

function selectInput(value, choices) {
  const select = document.createElement("select");
  choices.forEach(([choiceValue, label]) => {
    const option = element("option", label, { value: choiceValue });
    option.selected = choiceValue === (value || "");
    select.append(option);
  });
  return select;
}

function sourceLabel(model, stageId) {
  const stage = (model.stages || []).find((item) => item.id === stageId);
  return stage?.name || stageId || "结束";
}

function plannerTriggerLabel(type) {
  return ({ tap: "点击", long_press: "长按", swipe: "滑动", drag: "拖动", animation_end: "动画结束后", media_end: "播放结束后", timeout: "等待后", condition_met: "满足条件后", system_event: "自动发生", unknown: "待确认" })[type] || "待确认";
}

function anchorBounds(model, transition) {
  const regions = model.regions || [];
  const component = (model.components || []).find((item) => item.id === transition.componentId);
  if (component && !isAnchorBindingForTransition(component, transition)) return null;
  const region = (transition.regionId && regions.find((item) => item.id === transition.regionId))
    || (component?.regionId && regions.find((item) => item.id === component.regionId));
  if (region && !isAnchorBindingForTransition(region, transition)) return null;
  return component?.bounds || region?.bounds || null;
}

function isAnchorBindingForTransition(binding, transition) {
  return binding?.stageId === transition?.sourceStageId
    && (!binding.frameId || !transition.sourceFrameId || binding.frameId === transition.sourceFrameId);
}

function newTransitionDraft(model) {
  const stages = visibleLane(model);
  const source = stages[0];
  const target = stages[1];
  return {
    sourceStageId: source?.id || "", targetStageId: target?.id || null,
    sourceFrameId: source?.representativeFrames?.[0]?.frameId || "", triggerType: "unknown", triggerLabel: "",
    resultType: target ? "navigate" : "terminal", included: false,
  };
}

function selectedTransition(transitions, selectedId) {
  return (transitions || []).find((item) => item.id === selectedId) || (transitions || [])[0] || null;
}

function stageEditOperations(stage = {}, values = {}) {
  const operations = [];
  if ((stage.name || "") !== values.title) operations.push({ type: "set", entity: "stage", id: stage.id, field: "name", value: values.title });
  if ((stage.entryCondition || stage.beforeState || "") !== values.before) operations.push({ type: "set", entity: "stage", id: stage.id, field: "entryCondition", value: values.before });
  const loop = stage.smallLoop || {};
  if ((loop.trigger || stage.trigger || stage.userAction || "") !== values.action
      || (loop.feedback || stage.systemFeedback || stage.systemResponse || "") !== values.feedback
      || (loop.result || stage.afterState || stage.exitCondition || "") !== values.result) {
    operations.push({ type: "set_small_loop", id: stage.id, smallLoop: { ...loop, trigger: values.action, feedback: values.feedback, result: values.result } });
  }
  return operations;
}

function meaningfulPlannerValue(value) {
  const text = plannerText(value);
  return text && text !== "待确认" && !/^需要补充/.test(text) ? text : "";
}

function firstMeaningful(...values) {
  for (const value of values.flat(Infinity)) {
    const text = meaningfulPlannerValue(value);
    if (text) return text;
  }
  return "";
}

function explicitNodeRule(...values) {
  for (const value of values.flat(Infinity)) {
    const raw = String(value || "").trim();
    if (!raw || /请确认|未知待确认|待确认|推测/.test(raw)) continue;
    const text = meaningfulPlannerValue(raw);
    if (text) return text;
  }
  return "";
}

function supportingPageValue(pageInfos, key) {
  return firstMeaningful((pageInfos || []).map((info) => {
    const value = info?.[key];
    if (key === "action" && /未发生|未点击|未选择/.test(String(value || ""))) return "";
    if (key === "result" && /未被选中|保持开启|等待用户|等待玩家/.test(String(value || ""))) return "";
    return value;
  }));
}

function interactionStageView(model = {}, selectedTransitionId = null, selection = null) {
  const stages = [...(model.stages || [])].sort((left, right) => Number(left.order || 0) - Number(right.order || 0));
  const transition = selectedTransition(model.transitions, selectedTransitionId);
  const selectedStageId = selection?.stageId || (selection?.type === "stage" ? selection.id : null) || transition?.sourceStageId;
  const stage = stages.find((item) => item.id === selectedStageId) || stages[0] || null;
  if (!stage) return { stage: null, stages, transition: null, source: {}, frameId: null, steps: [] };
  const outgoing = (model.transitions || []).filter((item) => item.sourceStageId === stage.id && !item.duplicateOf);
  const activeTransition = outgoing.find((item) => item.id === selectedTransitionId) || outgoing.find((item) => item.included) || outgoing[0] || null;
  const sourceIds = Object.entries(model.sources || {})
    .filter(([, source]) => source?.stageId === stage.id)
    .sort((a, b) => Number(a[1]?.sequenceIndex || 0) - Number(b[1]?.sequenceIndex || 0))
    .map(([id]) => id);
  const frameId = activeTransition?.sourceFrameId || stage.representativeFrames?.[0]?.frameId || sourceIds[0] || null;
  const source = model.sources?.[frameId] || {};
  const sourcePageInfo = sourceIds.map((id) => model.sources?.[id]?.pageInfo || {});
  const loop = stage.smallLoop || {};
  const target = stages.find((item) => item.id === activeTransition?.targetStageId);
  const values = {
    before: firstMeaningful(stage.entryCondition, stage.beforeState, supportingPageValue(sourcePageInfo, "before"), stage.objective),
    action: firstMeaningful(loop.trigger, stage.trigger, stage.userAction, activeTransition?.triggerLabel,
      stage.name ? `玩家${stage.name}` : "", supportingPageValue(sourcePageInfo, "action"), plannerTriggerLabel(activeTransition?.triggerType)),
    feedback: firstMeaningful(loop.feedback, stage.systemFeedback, stage.systemResponse, activeTransition?.response,
      supportingPageValue(sourcePageInfo, "feedback")),
    result: firstMeaningful(loop.result, stage.afterState, activeTransition?.resultState,
      supportingPageValue(sourcePageInfo, "result"), target ? `进入${target.name}` : "", stage.exitCondition, "流程结束"),
  };
  const fallbacks = { before: "需要补充操作前的页面状态", action: "需要补充玩家如何完成这一步", feedback: "需要补充系统给玩家的即时反馈", result: "需要补充操作完成后的页面状态" };
  const actionText = plannerText(values.action || "");
  const hasCorrespondingFrame = sourceIds.some((id) => {
    const item = model.sources?.[id] || {};
    return Boolean(item.imageUrl || item.imagePath || item.thumbnailUrl);
  });
  const sourceActionIsObserved = sourceIds.some((id) => {
    const action = plannerText(model.sources?.[id]?.pageInfo?.action || "");
    return Boolean(action) && !/(?:需要补充|待确认|无明确操作|可能|推测|猜测)/.test(action);
  });
  const actionIsObserved = Boolean(actionText)
    && !/(?:需要补充|待确认|无明确操作|可能|推测|猜测)/.test(actionText)
    && (sourceActionIsObserved || activeTransition?.triggerType !== "unknown");
  return {
    stage, stages, transition: activeTransition, source, frameId, sourceIds,
    evidenceStatus: hasCorrespondingFrame && actionIsObserved ? "sufficient" : "insufficient",
    steps: [["before", "操作前"], ["action", "玩家操作"], ["feedback", "系统反馈"], ["result", "操作结果"]]
      .map(([key, title]) => ({ key, title, content: plannerText(values[key] || fallbacks[key]) })),
  };
}

function constraintDraft(constraint, values) {
  return { ...constraint, text: values.text, severity: values.severity, status: values.status };
}

function transitionDraft(transition, controls) {
  const triggerType = controls.triggerType.value;
  return {
    ...transition,
    triggerType,
    anchor: ["tap", "long_press"].includes(triggerType) ? transition.anchor : null,
    triggerLabel: controls.triggerLabel.value,
    sourceStageId: controls.sourceStageId.value,
    targetStageId: controls.targetStageId.value || null,
    sourceFrameId: controls.sourceFrameId.value,
    componentId: controls.componentId.value || null,
    regionId: controls.regionId.value || null,
    condition: controls.condition.value,
    response: controls.response.value,
    resultType: controls.resultType.value,
    resultState: controls.resultState.value,
  };
}

function suggestionPanel(entity, entityType, workspace) {
  const suggestions = entity?.suggestions || {};
  if (!Object.keys(suggestions).length) return null;
  const panel = element("section", "", { class: "review-suggestions", "aria-label": "修改建议" });
  panel.append(element("h4", "修改建议"));
  Object.entries(suggestions).forEach(([field, value]) => {
    const row = element("div", "", { class: "review-suggestion" });
    row.append(element("strong", field));
    row.append(element("p", `当前：${JSON.stringify(entity[field] ?? "")}`));
    row.append(element("p", `建议：${JSON.stringify(value)}`));
    row.append(button("采用建议", () => workspace.onOperation?.([ReviewWorkspace.suggestionOperation(entityType, entity.id, field, value)]), { disabled: workspace.readOnly, className: "btn" }));
    row.append(button("保留当前内容", () => workspace.onOperation?.([{ type: "reject_suggestion", entity: entityType, id: entity.id, field }]), { disabled: workspace.readOnly, className: "btn" }));
    panel.append(row);
  });
  return panel;
}

function renderTransitionDetail(root, workspace, transition) {
  const { model, onOperation, readOnly } = workspace;
  const panel = element("section", "", { class: "flow-review-detail", "aria-labelledby": "flowTransitionDetail" });
  panel.append(element("h3", "这一步如何发生", { id: "flowTransitionDetail" }));
  panel.append(element("p", `${sourceLabel(model, transition.sourceStageId)}：玩家${transition.triggerLabel || plannerTriggerLabel(transition.triggerType)}，系统${transition.response || "给出对应反馈"}，随后进入${sourceLabel(model, transition.targetStageId)}。`, { class: "flow-review-summary" }));
  const details = element("details", "", { class: "flow-review-rule-details" });
  details.append(element("summary", "展开详细规则"));
  const form = element("form", "", { class: "flow-review-form" });
  const controls = {
    sourceStageId: selectInput(transition.sourceStageId, (model.stages || []).map((item) => [item.id, item.name || item.id])),
    targetStageId: selectInput(transition.targetStageId, [["", "结束"], ...(model.stages || []).map((item) => [item.id, item.name || item.id])]),
    triggerType: selectInput(transition.triggerType, [["tap", "点击"], ["long_press", "长按"], ["swipe", "滑动"], ["drag", "拖动"], ["animation_end", "动画播放完毕"], ["media_end", "视频播放完毕"], ["timeout", "等待一段时间"], ["condition_met", "满足指定条件"], ["system_event", "系统自动触发"], ["unknown", "待确认"]]),
    triggerLabel: textInput(transition.triggerLabel),
    sourceFrameId: textInput(transition.sourceFrameId),
    componentId: textInput(transition.componentId),
    regionId: textInput(transition.regionId),
    condition: textInput(transition.condition, true),
    response: textInput(transition.response, true),
    resultType: selectInput(transition.resultType, [["navigate", "进入其他页面"], ["state_change", "当前页面发生变化"], ["open_overlay", "打开弹窗或浮层"], ["close_overlay", "关闭弹窗或浮层"], ["return", "返回上一步"], ["loop", "重复当前操作"], ["terminal", "流程结束"], ["unknown", "待确认"]]),
    resultState: textInput(transition.resultState, true),
  };
  [["从哪个环节开始", "sourceStageId"], ["完成后进入哪里", "targetStageId"], ["玩家如何触发", "triggerType"], ["具体操作说明", "triggerLabel"], ["什么情况下可以操作", "condition"], ["系统给出什么反馈", "response"], ["操作后发生什么", "resultType"], ["操作后的页面状态", "resultState"]].forEach(([label, key]) => form.append(field(label, controls[key])));
  const actions = element("div", "", { class: "flow-review-actions" });
  actions.append(button("保存这一步", () => onOperation([{ type: "upsert_transition", transition: transitionDraft(transition, controls) }]), { disabled: readOnly, className: "btn primary" }));
  actions.append(button("删除这一步", () => onOperation([{ type: "delete_transition", id: transition.id }]), { disabled: readOnly, className: "btn warn" }));
  form.append(actions);
  form.addEventListener("submit", (event) => event.preventDefault());
  details.append(form);
  panel.append(details);
  const transitionSuggestions = suggestionPanel(transition, "transition", workspace);
  if (transitionSuggestions) panel.append(transitionSuggestions);

  root.append(panel);
}

function renderInteractionDecisionCard(root, workspace, transition) {
  const card = (workspace.model.interactionDecisionCards || []).find((item) => item.transitionId === transition?.id && ["pending", "skipped"].includes(item.status));
  if (!card) return;
  const panel = element("section", "", { class: "interaction-operation-decision", "data-interaction-decision-card": card.id });
  panel.append(element("span", "需要策划确认", { class: "interaction-operation-decision-status" }), element("h4", card.question));
  const options = element("div", "", { class: "interaction-operation-options", role: "radiogroup", "aria-label": "选择这一步的实际操作" });
  let selected = "";
  const custom = textInput("");
  (card.options || []).forEach((option) => {
    const label = element("label", "", { class: "interaction-operation-option" });
    const input = element("input", "", { type: "radio", name: `interaction-operation-${card.id}`, value: option.id });
    input.addEventListener("change", () => { selected = option.id; custom.value = ""; });
    label.append(input, element("span", option.label)); options.append(label);
  });
  custom.setAttribute("placeholder", "以上都不是，填写真实操作"); custom.setAttribute("aria-label", "自定义真实操作");
  custom.addEventListener("input", () => { if (custom.value.trim()) { selected = ""; options.querySelectorAll?.('input[type="radio"]').forEach((input) => { input.checked = false; }); } });
  const message = element("p", "", { class: "interaction-operation-decision-message", role: "status" });
  const actions = element("div", "", { class: "interaction-operation-decision-actions" });
  actions.append(button("应用这个操作", () => {
    const customText = custom.value.trim();
    if (!selected && !customText) { message.textContent = "请先选择一种操作，或填写真实操作。"; return; }
    workspace.onOperation?.([{ type: "resolve_interaction_decision_card", cardId: card.id, optionId: selected || undefined, customText: customText || undefined }]);
  }, { disabled: workspace.readOnly, className: "btn primary" }));
  actions.append(button("暂时跳过", () => workspace.onOperation?.([{ type: "skip_interaction_decision_card", cardId: card.id }]), { disabled: workspace.readOnly, className: "btn" }));
  panel.append(options, custom, message, actions); root.append(panel);
}

function renderConstraints(root, workspace) {
  const { model, onOperation, readOnly } = workspace;
  const section = element("section", "", { class: "flow-review-constraints", "aria-labelledby": "flowConstraintHeading" });
  section.append(element("h3", "离开这个页面后，需要保留什么？", { id: "flowConstraintHeading" }));
  section.append(element("p", "例如：返回后仍然保留刚才的选择、两个选项不能同时选中，或另一个页面需要同步显示结果。没有这类要求可以不填。", { class: "flow-review-muted" }));
  section.append(button("添加一条保留要求", () => onOperation([{ type: "upsert_constraint", constraint: { text: "", severity: "non_core", status: "unknown" } }]), { disabled: readOnly, className: "btn" }));
  (model.crossStateConstraints || []).forEach((constraint) => {
    const form = element("form", "", { class: "flow-constraint-form", id: `constraint-${constraint.id}` });
    const text = textInput(constraint.text, true);
    const severity = selectInput(constraint.severity, [["core", "必须明确"], ["non_core", "可以稍后补充"]]);
    const status = selectInput(constraint.status, [["observed", "素材中已经看到"], ["inferred", "根据前后内容推断"], ["unknown", "还需要确认"]]);
    form.append(field("具体需要保留什么", text), field("不明确会不会影响后续操作", severity), field("这条内容是怎么确认的", status));
    const actions = element("div", "", { class: "flow-review-actions" });
    actions.append(button("保存规则", () => onOperation([{ type: "upsert_constraint", constraint: constraintDraft(constraint, { text: text.value, severity: severity.value, status: status.value }) }]), { disabled: readOnly, className: "btn" }));
    actions.append(button("删除规则", () => onOperation([{ type: "delete_constraint", id: constraint.id }]), { disabled: readOnly, className: "btn warn" }));
    form.append(actions);
    form.addEventListener("submit", (event) => event.preventDefault());
    section.append(form);
    const suggestions = suggestionPanel(constraint, "constraint", workspace);
    if (suggestions) section.append(suggestions);
  });
  root.append(section);
  const selected = workspace.selection;
  if (selected?.type === "constraint") root.querySelector?.(`#constraint-${selected.id}`)?.scrollIntoView?.({ block: "center" });
}

function render(workspace) {
  if (typeof document === "undefined" || !workspace?.root) return;
  const { root, model, selectedTransitionId, onOperation, onSelectTransition, onAdvanceStage, onConfirmStage, readOnly } = workspace;
  root.textContent = "";
  root.classList.add("interaction-review-target");
  const view = interactionStageView(model, selectedTransitionId, workspace.selection);
  if (!view.stage) { root.append(element("p", "目前没有需要审核的交互环节。", { class: "flow-review-muted" })); return; }
  const stageIndex = view.stages.findIndex((item) => item.id === view.stage.id);
  const transitionForStage = (stageId) => (model.transitions || []).find((item) => item.sourceStageId === stageId && item.included)
    || (model.transitions || []).find((item) => item.sourceStageId === stageId && !item.duplicateOf);

  const navigation = element("nav", "", { class: "interaction-stage-navigation", "aria-label": "交互环节" });
  const navHead = element("header", "", { class: "interaction-stage-navigation-head" });
  navHead.append(element("strong", "交互环节"), element("span", String(view.stages.length), { class: "interaction-stage-count" }));
  navigation.append(navHead);
  const navList = element("div", "", { class: "interaction-stage-list" });
  view.stages.forEach((stage, index) => {
    const targetTransition = transitionForStage(stage.id);
    const item = button("", () => targetTransition && onSelectTransition?.(targetTransition), {
      disabled: !targetTransition,
      className: `interaction-stage-nav-item${stage.id === view.stage.id ? " is-active" : ""}`,
      label: `查看${stage.name || `第${index + 1}个环节`}`,
    });
    item.append(element("span", String(index + 1).padStart(2, "0"), { class: "interaction-stage-number" }), element("span", stage.name || "待命名环节"));
    const stageView = interactionStageView(model, targetTransition?.id, { type: "stage", id: stage.id });
    if (stage.confirmation?.confirmed && stageView.evidenceStatus === "sufficient") item.append(element("small", "已确认"));
    else if (stageView.evidenceStatus === "insufficient") item.append(element("small", "已有补充画面 · 操作待复核"));
    navList.append(item);
  });
  navigation.append(navList);

  const main = element("main", "", { class: "interaction-stage-main" });
  const mainHead = element("header", "", { class: "interaction-stage-main-head" });
  const crumb = element("div", "", { class: "interaction-stage-crumb" });
  crumb.append(element("span", "交互审核 /"), element("strong", view.stage.name || "待命名环节"), element("small", `${stageIndex + 1} / ${view.stages.length}`));
  mainHead.append(crumb);
  if (view.sourceIds?.length > 1) mainHead.append(element("span", `本环节 ${view.sourceIds.length} 张截图`, { class: "interaction-stage-source-count" }));
  main.append(mainHead);

  const tools = element("div", "", { class: "interaction-flow-tools" });
  tools.append(button("适配画板", () => {
    board.scrollTo?.({ top: 0, left: 0, behavior: "smooth" });
    requestAnimationFrame(() => drawFlowConnectors(flow));
  }, { className: "btn" }), element("span", "原截图节点 · 带文字箭头表示玩家操作与页面跳转", { class: "flow-review-muted" }));
  main.append(tools);
  const board = element("section", "", { class: "interaction-flow-board", "aria-label": "交互流程画板" });
  const flow = element("div", "", { class: "interaction-flow-canvas" });
  const connectors = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  connectors.setAttribute("class", "interaction-flow-connectors"); connectors.setAttribute("aria-hidden", "true");
  flow.append(connectors);
  const usedFrames = new Set();
  view.stages.forEach((stage, index) => {
    const stageTransition = transitionForStage(stage.id);
    const owned = sourceForStage(model, stage, stageTransition, usedFrames);
    const frameId = owned.frameId;
    const source = owned.source;
    if (frameId) usedFrames.add(frameId);
    const node = element("article", "", { class: `interaction-flow-node${stage.id === view.stage.id ? " is-selected" : ""}`, "data-stage-id": stage.id });
    const nodeHead = element("header", "", { class: "interaction-flow-node-head" });
    nodeHead.append(element("span", `${String(index + 1).padStart(2, "0")} ${stage.name || "未命名页面"}`)); node.append(nodeHead);
    if (source.imageUrl) {
      const media = element("div", "", { class: "interaction-flow-node-media" });
      const image = element("img", "", { class: "interaction-flow-node-image", alt: `${stage.name || "当前页面"}原始截图` });
      image.src = workspace.resolveSourceUrl?.(source.imageUrl) || source.imageUrl; media.append(image);
      const bounds = stageTransition?.anchor && anchorBounds(model, stageTransition);
      if (validEvidenceAnchor(stageTransition?.anchor, bounds) && (!stageTransition.sourceFrameId || stageTransition.sourceFrameId === frameId)) {
        const hotspot = element("span", "", { class: "interaction-flow-hotspot", "aria-label": "操作热点" });
        const gesture = element("span", "👆", { class: "interaction-flow-gesture", "aria-label": "玩家点击位置" });
        const positionEvidence = () => {
          const rect = containedImageRect({ width: image.naturalWidth, height: image.naturalHeight }, { x: 12, y: 12, width: Math.max(0, image.clientWidth - 24), height: Math.max(0, image.clientHeight - 24) });
          const mapped = mapEvidenceBox(bounds, rect); if (!mapped) return;
          Object.assign(hotspot.style, { left: `${mapped.left}px`, top: `${mapped.top}px`, width: `${mapped.width}px`, height: `${mapped.height}px` });
          gesture.style.left = `${rect.x + stageTransition.anchor.x * rect.width}px`; gesture.style.top = `${rect.y + stageTransition.anchor.y * rect.height}px`;
          requestAnimationFrame(() => drawFlowConnectors(flow));
        };
        image.addEventListener("load", positionEvidence); requestAnimationFrame(positionEvidence);
        media.append(hotspot, gesture);
      }
      if (owned.supplemental) media.append(element("small", "同一页面补充状态", { class: "interaction-flow-source-note" }));
      node.append(media);
    } else node.append(element("div", "缺少对应画面", { class: "interaction-flow-node-empty" }));
    const loop = stage.smallLoop || {};
    const nodeRule = explicitNodeRule(loop.display, stage.entryCondition, loop.result);
    if (nodeRule) node.append(element("p", nodeRule, { class: "interaction-flow-node-rule" }));
    if (stageTransition) node.addEventListener("click", () => onSelectTransition?.(stageTransition));
    flow.append(node);
    if (index < view.stages.length - 1) {
      const edge = element("div", "", { class: "interaction-flow-edge", "data-transition-id": stageTransition?.id || "" });
      edge.append(element("strong", "玩家操作"), element("span", firstMeaningful(stageTransition?.triggerLabel, loop.trigger, "待策划选择操作")));
      flow.append(edge);
    }
  });
  board.append(flow); main.append(board);

  const editor = element("aside", "", { class: "interaction-stage-editor" });
  const editorHead = element("header", "", { class: "interaction-stage-editor-head" });
  editorHead.append(element("h3", `当前节点`), element("span", "编辑")); editor.append(editorHead);
  editor.append(element("p", `${view.stage.name || "当前页面"} · 跳转依据：${firstMeaningful(view.transition?.triggerLabel, view.stage.smallLoop?.trigger, "待策划选择操作")}`, { class: "interaction-flow-basis" }));
  renderInteractionDecisionCard(editor, workspace, view.transition);
  const form = element("form", "", { class: "interaction-stage-editor-form" });
  const controls = {
    title: textInput(view.stage.name || ""),
    before: textInput(view.steps[0].content, true),
    action: textInput(view.steps[1].content, true),
    feedback: textInput(view.steps[2].content, true),
    result: textInput(view.steps[3].content, true),
  };
  Object.values(controls).forEach((control) => { control.disabled = Boolean(readOnly); });
  [["页面名称", "title"], ["操作前", "before"], ["玩家操作", "action"], ["系统反馈", "feedback"], ["操作结果", "result"]]
    .forEach(([label, key]) => form.append(field(label, controls[key])));
  const save = () => {
    const operations = stageEditOperations(view.stage, Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.value.trim()])));
    if (operations.length) onOperation?.(operations);
  };
  form.append(button("保存修改", save, { disabled: readOnly, className: "btn" }));
  form.addEventListener("submit", (event) => event.preventDefault());
  editor.append(form);
  const nextStage = view.stages[stageIndex + 1];
  const nextTransition = nextStage ? transitionForStage(nextStage.id) : null;
  const footer = element("footer", "", { class: "interaction-stage-editor-footer" });
  const nextLabel = nextTransition ? "应用并查看下一环节" : "应用并生成策划草图";
  const destination = nextTransition ? `下一环节“${nextStage.name || nextStage.title || `第 ${stageIndex + 2} 环节`}”` : "策划草图预览";
  const gateCopy = readOnly
    ? "当前是只读工作台，可以检查本环节；重新分析成功后才能保存并继续。"
    : `门禁：保存当前环节的页面、玩家操作和系统反馈。完成后进入${destination}。`;
  footer.append(element("p", gateCopy, { class: "interaction-step-gate" }), button(nextLabel, async () => {
    save();
    await onConfirmStage?.(view.stage.id);
    if (nextTransition) onAdvanceStage?.(nextStage, nextTransition);
  }, { disabled: readOnly, className: "btn primary interaction-next-step", label: nextLabel }));
  editor.append(footer);
  root.append(navigation, main, editor);
  requestAnimationFrame(() => drawFlowConnectors(flow));
}

const api = { groupCandidates, visibleLane, canEditAnchor, anchorFromPointer, containedImageRect, mapEvidenceBox, anchorFromImageClick, validEvidenceAnchor, sourceSemanticallySupportsStage, sourceForStage, connectorPath, drawFlowConnectors, anchorBounds, newTransitionDraft, constraintDraft, selectedTransition, plannerText, stageEditOperations, interactionStageView, render };
if (typeof module !== "undefined") module.exports = api;
else root.FlowReview = api;
}(typeof window !== "undefined" ? window : globalThis));
