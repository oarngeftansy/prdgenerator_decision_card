(function (root) {
const MIN_SIZE = 0.02;
const COMPONENT_STATE_KEYS = ["default", "pressed", "selected", "disabled", "loading", "success", "error", "exhausted", "condition_unmet"];
const FRAME_ROLES = ["entry", "change", "result"];

function finite(value, fallback = 0) { const number = Number(value); return Number.isFinite(number) ? number : fallback; }
function clampBounds(value = {}) {
  const width = Math.max(MIN_SIZE, Math.min(1, finite(value.width, MIN_SIZE)));
  const height = Math.max(MIN_SIZE, Math.min(1, finite(value.height, MIN_SIZE)));
  return { x: Math.max(0, Math.min(1 - width, finite(value.x))), y: Math.max(0, Math.min(1 - height, finite(value.y))), width, height };
}
function resizeBounds(start, handle, delta = {}) {
  const box = clampBounds(start); const right = box.x + box.width; const bottom = box.y + box.height;
  let { x, y, width, height } = box;
  if (handle.includes("e")) width = Math.max(MIN_SIZE, Math.min(1 - x, width + finite(delta.dx)));
  if (handle.includes("s")) height = Math.max(MIN_SIZE, Math.min(1 - y, height + finite(delta.dy)));
  if (handle.includes("w")) { x = Math.max(0, Math.min(right - MIN_SIZE, x + finite(delta.dx))); width = right - x; }
  if (handle.includes("n")) { y = Math.max(0, Math.min(bottom - MIN_SIZE, y + finite(delta.dy))); height = bottom - y; }
  return { x, y, width, height };
}
function renumberRegions(regions = []) { return [...regions].sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0)).map((item, index) => ({ ...item, displayNumber: Number.isInteger(item.displayNumber) ? item.displayNumber : index + 1 })); }
function stageRegions(model, stageId) { return renumberRegions((model.regions || []).filter((item) => item.stageId === stageId)); }
function regionsFor(model, stageId, frameId) { return stageRegions(model, stageId).filter((item) => item.frameId === frameId); }
function regionReorderIndex(model, stageId, regionId, delta) { const regions = stageRegions(model, stageId); return Math.max(0, Math.min(regions.length - 1, regions.findIndex((item) => item.id === regionId) + delta)); }
function representativeFrames(frames = [], sources = {}) {
  const copy = frames.slice(); const roles = copy.map((item) => item?.role); const ids = copy.map((item) => item?.frameId); const expected = { 1: ["entry"], 2: ["entry", "result"], 3: ["entry", "change", "result"] }[copy.length];
  return { valid: Boolean(expected) && copy.every((item) => item && FRAME_ROLES.includes(item.role) && Object.prototype.hasOwnProperty.call(sources, item.frameId)) && new Set(ids).size === ids.length && new Set(roles).size === roles.length && expected.every((role, index) => roles[index] === role), frames: copy };
}
function representativeFrameChange(frames, frameId, role, sources) {
  const next = (frames || []).filter((item) => item.frameId !== frameId && (!role || item.role !== role));
  if (role) next.push({ frameId, role });
  next.sort((a, b) => FRAME_ROLES.indexOf(a.role) - FRAME_ROLES.indexOf(b.role));
  return representativeFrames(next, sources);
}
function representativeFrameOperation(stageId, frames, frameId, role, sources) {
  const displaced = role && (frames || []).find((item) => item.role === role && item.frameId !== frameId);
  if (displaced && !(frames || []).some((item) => item.frameId === frameId)) {
    return { type: "replace_representative_frame", id: stageId, oldFrameId: displaced.frameId, frame: { frameId, role } };
  }
  const change = representativeFrameChange(frames, frameId, role, sources);
  return change.valid ? { type: "set_representative_frames", id: stageId, frames: change.frames } : null;
}
function canAnnotateFrame(stage, frameId, readOnly) {
  return !readOnly && (stage?.representativeFrames || []).some((item) => item.frameId === frameId);
}
function missingStateSlots(states = {}) { return COMPONENT_STATE_KEYS.filter((key) => !Object.prototype.hasOwnProperty.call(states, key)); }
function defaultBounds() { return { x: 0.4, y: 0.4, width: 0.2, height: 0.2 }; }
function sourceAspectRatio(source = {}) {
  const width = finite(source.width); const height = finite(source.height);
  return width > 0 && height > 0 ? `${width} / ${height}` : null;
}
function naturalAspectRatio(image = {}) {
  return sourceAspectRatio({ width: image.naturalWidth, height: image.naturalHeight });
}
function mobileTabIndex(current, key) {
  if (key === "ArrowLeft" || key === "Home") return 0;
  if (key === "ArrowRight" || key === "End") return 1;
  return null;
}
function panelAriaHidden(index, selectedIndex, mobile) { return String(Boolean(mobile && index !== selectedIndex)); }
function resizeByKey(bounds, handle, key, event = {}) {
  const step = event.shiftKey ? 0.1 : 0.01; const delta = { dx: 0, dy: 0 };
  if (key === "ArrowRight") delta.dx = handle.includes("w") ? step : handle.includes("e") ? step : 0;
  if (key === "ArrowLeft") delta.dx = handle.includes("w") ? -step : handle.includes("e") ? -step : 0;
  if (key === "ArrowDown") delta.dy = handle.includes("n") ? step : handle.includes("s") ? step : 0;
  if (key === "ArrowUp") delta.dy = handle.includes("n") ? -step : handle.includes("s") ? -step : 0;
  return delta.dx || delta.dy ? resizeBounds(bounds, handle, delta) : null;
}

function pointerSession(event, handlers, surface = document) {
  const pointerId = event.pointerId; const target = event.currentTarget; const blurSurface = surface.defaultView || surface; let active = true;
  target?.setPointerCapture?.(pointerId);
  const cleanup = () => { if (!active) return; active = false; ["pointermove", "pointerup", "pointercancel"].forEach((type) => surface.removeEventListener(type, listeners[type])); blurSurface.removeEventListener("blur", listeners.blur); target?.releasePointerCapture?.(pointerId); };
  const listeners = {
    pointermove: (moveEvent) => { if (active && moveEvent.pointerId === pointerId) handlers.move?.(moveEvent); },
    pointerup: (upEvent) => { if (upEvent.pointerId !== pointerId) return; cleanup(); handlers.commit?.(upEvent); },
    pointercancel: (cancelEvent) => { if (cancelEvent.pointerId !== pointerId) return; cleanup(); handlers.cancel?.(cancelEvent); },
    blur: () => { cleanup(); handlers.cancel?.(); },
  };
  ["pointermove", "pointerup", "pointercancel"].forEach((type) => surface.addEventListener(type, listeners[type]));
  blurSurface.addEventListener("blur", listeners.blur);
  return { cancel: listeners.pointercancel, cleanup };
}

function el(tag, text = "", attributes = {}) {
  const node = document.createElement(tag);
  if (text) node.textContent = plannerText(text);
  Object.entries(attributes).forEach(([name, value]) => value !== undefined && value !== null && node.setAttribute(name, String(value)));
  return node;
}
function button(text, onClick, options = {}) {
  const node = el("button", text, { type: "button", "aria-label": options.label || text });
  node.className = options.className || "stage-review-button";
  node.disabled = Boolean(options.disabled);
  node.addEventListener("click", onClick);
  return node;
}
function input(value = "", multiline = false) {
  const node = document.createElement(multiline ? "textarea" : "input");
  if (!multiline) node.type = "text";
  node.value = plannerText(value);
  return node;
}
function field(label, control) { const node = el("label", "", { class: "stage-review-field" }); node.append(el("span", label), control); return node; }
function sourceUrl(workspace, source) { return workspace.resolveSourceUrl?.(source?.imageUrl) || source?.imageUrl || ""; }
function stageFor(model, id) { return (model.stages || []).find((item) => item.id === id) || model.stages?.[0]; }
function plannerText(value) {
  const text = String(value || "").trim();
  if (/(?:当前帧|当前截图|截图)[^)）。]*(?:静态展示|未捕捉到)[^)）。]*(?:点击|滑动|操作)/.test(text)) {
    return "待确认：需结合相邻画面或视频确认玩家操作";
  }
  if (!text || text.toLowerCase() === "unknown" || text === "未知待确认") return "待确认";
  const cleaned = text
    .replace(/\bBOSS\b/gi, "首领")
    .replace(/[（(]\s*inferred from damage numbers\s*[）)]/gi, "（根据伤害数字推测）")
    .replace(/\bdamage numbers\b/gi, "伤害数字")
    .replace(/\binferred from\b/gi, "根据画面推测")
    .replace(/(?:^|[，,；;。])[^，,；;。]*(?:鼠标|光标|悬停)[^，,；;。]*(?=$|[，,；;。])/g, "")
    .replace(/^[，,；;。\s]+|[，,；;。\s]+$/g, "");
  if (!/[\p{L}\p{N}]/u.test(cleaned)) return "待确认";
  const uncertain = cleaned.match(/^未知待确认\s*[（(](?:根据[^，,]*推测[，,]\s*)?(.+)[）)]$/);
  return uncertain ? `请确认：${uncertain[1].replace(/可能/g, "是否").replace(/或处于/g, "，还是处于")}` : (cleaned || "待确认");
}
function stageSummary(stage = {}, components = []) {
  const loop = stage.smallLoop || {};
  return [
    ["页面/环节名称", stage.name],
    ["当前目标", stage.objective],
    ["如何进入", stage.entryCondition],
    ["用户操作或自动触发", loop.trigger],
    ["系统反馈与结果", [loop.feedback, loop.result].filter(Boolean).join("；")],
    ["关键组件", components.map((item) => item.name || item.title).filter(Boolean).join("、")],
  ].map(([label, value]) => ({ label, value: plannerText(value) }));
}
function renderStageSummary(root, stage, components) {
  const card = el("section", "", { class: "stage-summary-card", "aria-labelledby": "stageSummaryHeading" });
  card.append(el("h3", "这一环节发生了什么？", { id: "stageSummaryHeading" }));
  const items = stageSummary(stage, components);
  const values = Object.fromEntries(items.map((item) => [item.label, item.value]));
  card.append(el("p", `${values["如何进入"]}；${values["用户操作或自动触发"]}；系统随后${values["系统反馈与结果"]}。`, { class: "planner-stage-summary-text" }));
  const details = el("details", "", { class: "planner-summary-details" });
  details.append(el("summary", "展开环节信息"));
  const list = el("dl");
  items.forEach((item) => {
    const row = el("div", "", { class: "stage-summary-row" });
    row.append(el("dt", item.label), el("dd", item.value));
    list.append(row);
  });
  details.append(list); card.append(details); root.append(card);
}
function selectedComponent(model, stageId, selection) {
  if (!selection) return null;
  return (model.components || []).find((component) => component.stageId === stageId && (
    (selection.type === "component" && component.id === selection.id) ||
    (selection.type === "region" && component.regionId === selection.id)
  )) || null;
}
function selectRegion(workspace, region) { workspace.onSelect?.({ type: "region", id: region.id, stageId: region.stageId, frameId: region.frameId }); }

function applyPointerDrag(event, region, layer, workspace, mode, handle = "") {
  if (workspace.readOnly) return;
  event.preventDefault();
  const rect = layer.getBoundingClientRect();
  const start = clampBounds(region.bounds);
  const origin = { x: event.clientX, y: event.clientY };
  const preview = (bounds) => {
    const box = layer.querySelector(`[data-region-id="${region.id}"]`);
    if (!box) return;
    Object.assign(box.style, { left: `${bounds.x * 100}%`, top: `${bounds.y * 100}%`, width: `${bounds.width * 100}%`, height: `${bounds.height * 100}%` });
  };
  const move = (moveEvent) => {
    const delta = { dx: (moveEvent.clientX - origin.x) / rect.width, dy: (moveEvent.clientY - origin.y) / rect.height };
    preview(mode === "resize" ? resizeBounds(start, handle, delta) : clampBounds({ ...start, x: start.x + delta.dx, y: start.y + delta.dy }));
  };
  const finish = (upEvent) => {
    const delta = { dx: (upEvent.clientX - origin.x) / rect.width, dy: (upEvent.clientY - origin.y) / rect.height };
    const bounds = mode === "resize" ? resizeBounds(start, handle, delta) : clampBounds({ ...start, x: start.x + delta.dx, y: start.y + delta.dy });
    workspace.onOperation?.([{ type: "set_region_bounds", id: region.id, bounds }]);
  };
  pointerSession(event, { move, commit: finish }, document);
}

function handleResizeKey(event, region, handle, workspace) {
  event.stopPropagation();
  const bounds = resizeByKey(region.bounds, handle, event.key, event);
  if (!bounds || workspace.readOnly) return false;
  event.preventDefault();
  workspace.onOperation?.([{ type: "set_region_bounds", id: region.id, bounds }]);
  return true;
}

function renderBoxes(layer, workspace, regions) {
  regions.forEach((region) => {
    const bounds = clampBounds(region.bounds);
    const selected = workspace.selection?.type === "region" && workspace.selection.id === region.id;
    const box = el("div", "", { class: `stage-region-box${selected ? " is-selected" : ""}`, "data-region-id": region.id, tabindex: "0", role: "button", "aria-label": `区域 ${region.displayNumber}: ${region.name || region.id}` });
    Object.assign(box.style, { left: `${bounds.x * 100}%`, top: `${bounds.y * 100}%`, width: `${bounds.width * 100}%`, height: `${bounds.height * 100}%` });
    const marker = el("span", String(region.displayNumber), { class: "stage-region-marker", "aria-hidden": "true" });
    box.append(marker);
    box.addEventListener("click", (event) => { event.stopPropagation(); selectRegion(workspace, region); });
    box.addEventListener("pointerdown", (event) => { if (!event.target.closest("[data-handle]")) applyPointerDrag(event, region, layer, workspace, "move"); });
    box.addEventListener("keydown", (event) => {
      if (event.key === "Delete" && !workspace.readOnly && !region.primary) {
        event.preventDefault(); workspace.onOperation?.([{ type: "delete_region", id: region.id }]); return;
      }
      const changes = { ArrowLeft: { dx: -0.01, dy: 0 }, ArrowRight: { dx: 0.01, dy: 0 }, ArrowUp: { dx: 0, dy: -0.01 }, ArrowDown: { dx: 0, dy: 0.01 } }[event.key];
      if (!changes || workspace.readOnly) return;
      event.preventDefault(); workspace.onOperation?.([{ type: "set_region_bounds", id: region.id, bounds: clampBounds({ ...bounds, x: bounds.x + changes.dx, y: bounds.y + changes.dy }) }]);
    });
    ["n", "ne", "e", "se", "s", "sw", "w", "nw"].forEach((handle) => {
      const grip = el("button", "", { class: `stage-region-handle stage-region-handle-${handle}`, type: "button", "data-handle": handle, "aria-label": `调整 ${handle}` });
      grip.addEventListener("pointerdown", (event) => { event.stopPropagation(); applyPointerDrag(event, region, layer, workspace, "resize", handle); });
      grip.addEventListener("keydown", (event) => handleResizeKey(event, region, handle, workspace));
      box.append(grip);
    });
    layer.append(box);
  });
}

function renderFrame(root, workspace, stage, frameId) {
  const source = workspace.model.sources?.[frameId];
  if (!source) return;
  const editableWorkspace = { ...workspace, readOnly: !canAnnotateFrame(stage, frameId, workspace.readOnly) };
  const figure = el("figure", "", { class: `stage-shot${editableWorkspace.readOnly ? " is-read-only" : ""}`, "aria-label": editableWorkspace.readOnly ? `${frameId} 只读截图` : `${frameId} 可标注截图` });
  const image = el("img", "", { src: sourceUrl(workspace, source), alt: `${frameId} 截图` });
  const layer = el("div", "", { class: "stage-box-layer", "aria-label": `${frameId} 标注区域` });
  const ratio = sourceAspectRatio(source);
  if (ratio) figure.style.setProperty("--stage-shot-ratio", ratio);
  else layer.hidden = true;
  image.addEventListener("load", () => {
    const naturalRatio = naturalAspectRatio(image);
    if (naturalRatio) figure.style.setProperty("--stage-shot-ratio", naturalRatio);
    layer.hidden = false;
  });
  const regions = regionsFor(workspace.model, stage.id, frameId);
  renderBoxes(layer, editableWorkspace, regions);
  layer.addEventListener("pointerdown", (event) => {
    if (editableWorkspace.readOnly || event.target !== layer) return;
    const rect = layer.getBoundingClientRect(); const start = { x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height };
    const preview = el("div", "", { class: "stage-region-box is-draft" }); layer.append(preview);
    const move = (moveEvent) => { const bounds = clampBounds({ x: Math.min(start.x, (moveEvent.clientX - rect.left) / rect.width), y: Math.min(start.y, (moveEvent.clientY - rect.top) / rect.height), width: Math.abs(moveEvent.clientX - event.clientX) / rect.width, height: Math.abs(moveEvent.clientY - event.clientY) / rect.height }); Object.assign(preview.style, { left: `${bounds.x * 100}%`, top: `${bounds.y * 100}%`, width: `${bounds.width * 100}%`, height: `${bounds.height * 100}%` }); };
    const finish = (upEvent) => { const bounds = clampBounds({ x: Math.min(start.x, (upEvent.clientX - rect.left) / rect.width), y: Math.min(start.y, (upEvent.clientY - rect.top) / rect.height), width: Math.abs(upEvent.clientX - event.clientX) / rect.width, height: Math.abs(upEvent.clientY - event.clientY) / rect.height }); editableWorkspace.onOperation?.([{ type: "upsert_region", region: { stageId: stage.id, frameId, bounds } }]); };
    pointerSession(event, { move, commit: finish, cancel: () => preview.remove() }, document);
  });
  figure.append(image, layer); root.append(figure);
  if (typeof workspace.onReanalyzeFrame === "function") {
    const status = source.supplementalEvidence?.status || "idle";
    const busy = status === "extracting" || status === "analyzing";
    const actions = el("div", "", { class: "stage-shot-actions" });
    const retry = button(busy ? "正在重新识别…" : "重新识别这张图", () => workspace.onReanalyzeFrame(frameId), { disabled: busy, className: "btn" });
    if (busy) retry.setAttribute("aria-busy", "true");
    actions.append(retry);
    if (status === "failed" && source.supplementalEvidence?.message) actions.append(el("p", source.supplementalEvidence.message, { class: "stage-review-muted" }));
    root.append(actions);
  }
}

function renderRuleEditor(root, workspace, stage, selected) {
  const region = selected?.type === "region" ? (workspace.model.regions || []).find((item) => item.id === selected.id) : null;
  const panel = el("section", "", { class: "stage-rule-panel" });
  panel.append(el("h3", region ? `规则 ${region.displayNumber || ""}` : "选择一个区域"));
  if (!region) { panel.append(el("p", "点击截图红色编号、区域列表或规则卡以同步选择。", { class: "stage-review-muted" })); root.append(panel); return; }
  const form = el("form", "", { class: "stage-rule-form" });
  const name = input(region.name); const rule = region.rule || {}; const controls = { display: input(rule.display, true), condition: input(rule.condition, true), action: input(rule.action, true), feedback: input(rule.feedback, true), result: input(rule.result, true), exception: input(rule.exception, true) };
  form.append(field("名称", name), ...Object.entries(controls).map(([key, control]) => field(key, control)));
  form.append(button("保存规则", () => workspace.onOperation?.([{ type: "upsert_region", region: { id: region.id, name: name.value, rule: Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.value])) } }]), { disabled: workspace.readOnly, className: "btn primary" }));
  form.append(button("删除区域", () => workspace.onOperation?.([{ type: "delete_region", id: region.id }]), { disabled: workspace.readOnly || region.primary, className: "btn warn" }));
  form.addEventListener("submit", (event) => event.preventDefault()); panel.append(form); const suggestions = suggestionPanel(region, "region", workspace); if (suggestions) panel.append(suggestions); root.append(panel);
}

function suggestionPanel(entity, entityType, workspace) {
  const suggestions = entity?.suggestions || {};
  if (!Object.keys(suggestions).length) return null;
  const panel = el("section", "", { class: "review-suggestions", "aria-label": "模型建议" });
  panel.append(el("h4", "模型建议"));
  Object.entries(suggestions).forEach(([field, value]) => {
    const row = el("div", "", { class: "review-suggestion" });
    row.append(el("strong", field), el("p", `当前：${JSON.stringify(entity[field] ?? "")}`), el("p", `建议：${JSON.stringify(value)}`));
    row.append(button("采用建议", () => workspace.onOperation?.([ReviewWorkspace.suggestionOperation(entityType, entity.id, field, value)]), { disabled: workspace.readOnly, className: "btn" }));
    row.append(button("保留当前内容", () => workspace.onOperation?.([{ type: "reject_suggestion", entity: entityType, id: entity.id, field }]), { disabled: workspace.readOnly, className: "btn" }));
    panel.append(row);
  });
  return panel;
}

function renderStageControls(root, workspace, stage) {
  const panel = el("section", "", { class: "stage-small-loop" }); panel.append(el("h3", "Small loop"));
  const loop = stage.smallLoop || {}; const controls = Object.fromEntries(["display", "trigger", "feedback", "result", "retry"].map((key) => [key, input(loop[key] || "unknown", true)]));
  Object.entries(controls).forEach(([key, control]) => panel.append(field(key, control)));
  panel.append(button("保存 small loop", () => workspace.onOperation?.([{ type: "set_small_loop", id: stage.id, smallLoop: Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.value])) }]), { disabled: workspace.readOnly, className: "btn" })); const suggestions = suggestionPanel(stage, "stage", workspace); if (suggestions) panel.append(suggestions); root.append(panel);
}

function renderComponentEditor(root, workspace, component) {
  const record = (workspace.model.componentStates || []).find((item) => item.componentId === component.id) || {};
  const states = { ...Object.fromEntries(COMPONENT_STATE_KEYS.map((key) => [key, "unknown"])), ...(record.states || component.states || {}) };
  const group = el("form", "", { class: "stage-state-grid" }); group.append(el("h4", component.name || component.id));
  const controls = Object.fromEntries(COMPONENT_STATE_KEYS.map((key) => [key, input(states[key], true)]));
  Object.entries(controls).forEach(([key, control]) => group.append(field(key, control)));
  group.append(button("保存状态", () => workspace.onOperation?.([{ type: "set_component_state", componentId: component.id, states: Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.value || "unknown"])) }]), { disabled: workspace.readOnly, className: "btn" }));
  group.addEventListener("submit", (event) => event.preventDefault());
  const suggestions = suggestionPanel(component, "component", workspace); if (suggestions) group.append(suggestions);
  root.append(group);
}

function renderComponentStates(root, workspace, stage) {
  const panel = el("section", "", { class: "stage-component-states" }); panel.append(el("h3", "组件状态"));
  const components = (workspace.model.components || []).filter((item) => item.stageId === stage.id);
  if (!components.length) panel.append(el("p", "截图或视频未展示组件状态；待确认。", { class: "stage-review-muted" }));
  const componentList = el("div", "", { class: "stage-component-list" });
  components.forEach((component) => componentList.append(button(component.name || component.id, () => workspace.onSelect?.({ type: "component", id: component.id, stageId: component.stageId, frameId: component.frameId || null }), { className: "stage-region-chip" })));
  panel.append(componentList);
  const selected = selectedComponent(workspace.model, stage.id, workspace.selection);
  if (selected) renderComponentEditor(panel, workspace, selected);
  else if (components.length) panel.append(el("p", "点击画面编号或关键组件，按需展开详细状态。", { class: "stage-review-muted" }));
  root.append(panel);
}

function renderLegacy(workspace) {
  if (typeof document === "undefined" || !workspace?.root) return;
  const { root, model } = workspace; root.__stageReviewCleanup?.(); const stage = stageFor(model, workspace.selectedStageId); root.textContent = "";
  if (!stage) { root.append(el("p", "没有可审核的阶段。", { class: "stage-review-muted" })); return; }
  const header = el("section", "", { class: "stage-review-header" }); header.append(el("h3", "页面审核"));
  const nav = el("div", "", { class: "stage-nav", role: "tablist", "aria-label": "阶段" }); [...(model.stages || [])].sort((a, b) => a.order - b.order).forEach((item, index) => nav.append(button(`${index + 1}. ${item.name || item.id}`, () => workspace.onSelect?.({ type: "stage", id: item.id, stageId: item.id }), { className: `stage-review-button${item.id === stage.id ? " is-active" : ""}` })));
  header.append(nav); root.append(header);
  const layout = el("div", "", { class: "stage-review-layout" }); const left = el("section", "", { class: "stage-frame-panel", id: "stageFramePanel", role: "tabpanel", "aria-labelledby": "stagePictureTab" });
  const reps = stage.representativeFrames || []; left.append(el("h3", "代表帧（1–3）"));
  const frameControls = el("div", "", { class: "stage-frame-controls" }); Object.keys(model.sources || {}).forEach((frameId) => { const current = reps.find((item) => item.frameId === frameId); const select = document.createElement("select"); [["", "不作为代表帧"], ...FRAME_ROLES.map((role) => [role, role])].forEach(([value, label]) => { const option = el("option", label, { value }); option.selected = value === (current?.role || ""); select.append(option); }); select.setAttribute("aria-label", `${frameId} 代表帧角色`); select.disabled = workspace.readOnly; select.addEventListener("change", () => { const operation = representativeFrameOperation(stage.id, reps, frameId, select.value, model.sources || {}); if (operation) workspace.onOperation?.([operation]); else select.value = current?.role || ""; }); const row = el("div", "", { class: "stage-frame-role" }); row.append(button(frameId, () => workspace.onSelect?.({ type: "frame", id: frameId, stageId: stage.id, frameId }), { className: "stage-review-button" }), select); frameControls.append(row); }); left.append(frameControls);
  left.append(button(workspace.showAllFrames ? "仅显示当前帧" : "显示全部截图", () => workspace.onShowAllFrames?.(!workspace.showAllFrames), { className: "btn" }));
  const activeFrameId = workspace.selectedFrameId || reps[0]?.frameId || Object.keys(model.sources || {})[0]; renderFrame(left, workspace, stage, activeFrameId);
  if (workspace.showAllFrames) Object.keys(model.sources || {}).filter((id) => id !== activeFrameId).forEach((frameId) => renderFrame(left, workspace, stage, frameId));
  const list = el("section", "", { class: "stage-region-list" }); list.append(el("h3", "阶段区域")); const visibleRegions = stageRegions(model, stage.id); visibleRegions.forEach((region, index) => { const row = el("div", "", { class: "stage-region-row" }); row.append(button(`${region.displayNumber}. ${region.name || region.id} · ${region.frameId}`, () => selectRegion(workspace, region), { className: "stage-region-chip" })); row.append(button("上移", () => workspace.onOperation?.([{ type: "reorder_region", id: region.id, toIndex: regionReorderIndex(model, stage.id, region.id, -1) }]), { disabled: workspace.readOnly || index === 0 })); row.append(button("下移", () => workspace.onOperation?.([{ type: "reorder_region", id: region.id, toIndex: regionReorderIndex(model, stage.id, region.id, 1) }]), { disabled: workspace.readOnly || index === visibleRegions.length - 1 })); list.append(row); }); list.append(button("新增区域", () => workspace.onOperation?.([{ type: "upsert_region", region: { stageId: stage.id, frameId: activeFrameId, bounds: defaultBounds() } }]), { disabled: !canAnnotateFrame(stage, activeFrameId, workspace.readOnly), className: "btn" })); left.append(list); layout.append(left);
  const right = el("aside", "", { class: "stage-detail-panel", id: "stageRulePanel", role: "tabpanel", "aria-labelledby": "stageRuleTab" });
  const stageComponents = (model.components || []).filter((item) => item.stageId === stage.id);
  renderStageSummary(right, stage, stageComponents);
  const advanced = el("details", "", { class: "stage-advanced-editor" }); advanced.append(el("summary", "编辑规则与环节细节"));
  renderRuleEditor(advanced, workspace, stage, workspace.selection); renderStageControls(advanced, workspace, stage); right.append(advanced);
  renderComponentStates(right, workspace, stage); layout.append(right);
  const mobileTabs = el("div", "", { class: "stage-mobile-tabs", role: "tablist", "aria-label": "页面审核内容" });
  const picture = button("画面", () => selectPanel(0), { className: "stage-review-button" });
  const rule = button("规则", () => selectPanel(1), { className: "stage-review-button" });
  const tabs = [picture, rule]; const panels = [left, right];
  const media = window.matchMedia?.("(max-width: 700px)"); let selectedPanel = 0;
  const syncPanels = () => {
    const mobile = Boolean(media?.matches);
    layout.classList.toggle("is-mobile-rule", selectedPanel === 1);
    tabs.forEach((tab, tabIndex) => {
      const selected = tabIndex === selectedPanel;
      tab.classList.toggle("is-active", selected); tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((panel, panelIndex) => panel.setAttribute("aria-hidden", panelAriaHidden(panelIndex, selectedPanel, mobile)));
  };
  const selectPanel = (index, focus = false) => {
    selectedPanel = index; syncPanels();
    if (focus) tabs[index].focus();
  };
  picture.setAttribute("id", "stagePictureTab"); picture.setAttribute("role", "tab"); picture.setAttribute("aria-controls", "stageFramePanel");
  rule.setAttribute("id", "stageRuleTab"); rule.setAttribute("role", "tab"); rule.setAttribute("aria-controls", "stageRulePanel");
  tabs.forEach((tab, index) => tab.addEventListener("keydown", (event) => {
    const next = mobileTabIndex(index, event.key);
    if (next === null) return;
    event.preventDefault(); selectPanel(next, true);
  }));
  media?.addEventListener("change", syncPanels);
  root.__stageReviewCleanup = () => media?.removeEventListener("change", syncPanels);
  selectPanel(0);
  mobileTabs.append(picture, rule); root.append(mobileTabs, layout);
}

const PLANNER_STEPS = [
  ["before", "操作前", ["beforeState", "entryCondition"], "需要补充操作发生前的页面状态"],
  ["action", "玩家操作", ["userAction", "trigger"], "需要补充玩家如何触发这一步"],
  ["feedback", "系统反馈", ["systemFeedback", "systemResponse", "feedback"], "需要补充系统给玩家的即时反馈"],
  ["result", "操作结果", ["afterState", "result", "exitCondition"], "需要补充操作完成后的状态"],
];

function readableValue(value, fallback) {
  const text = String(value || "").trim();
  if (!text || /^(unknown|n\/a|null|待确认)$/i.test(text) || !/[\u3400-\u9fffA-Za-z0-9]/.test(text)) return fallback;
  const commonEnglish = {
    tap: "点击对应入口",
    click: "点击对应入口",
    feedback: "展示操作反馈",
    result: "进入操作完成后的状态",
    entry: "进入当前环节",
  };
  if (commonEnglish[text.toLowerCase()]) return commonEnglish[text.toLowerCase()];
  if (/^[\x00-\x7F]+$/.test(text) && /[a-z]/i.test(text)) return `${fallback}（原识别内容需要转换为中文）`;
  return text;
}

function firstStageValue(stage, fields) {
  for (const name of fields) {
    const value = stage?.[name] ?? stage?.smallLoop?.[name];
    if (String(value || "").trim()) return value;
  }
  return "";
}

function contextualRules(model = {}, stage = {}, stepKey = "") {
  const keywords = {
    action: /触发|点击|拖动|选择|互斥|输入|操作/,
    feedback: /反馈|显示|隐藏|动效|声音|高亮|提示/,
    result: /结果|跳转|返回|保留|同步|状态|关闭|解锁/,
    before: /前置|进入|初始|操作前/,
  };
  const regionRules = (model.regions || [])
    .filter((item) => item.stageId === stage.id)
    .flatMap((item) => Object.values(item.rule || {}).filter((value) => typeof value === "string"));
  const stageRules = [
    ...(stage.rules || []),
    ...(stage.constraints || []),
  ].map((item) => typeof item === "string" ? item : item?.text || item?.description || "");
  return [...new Set([...regionRules, ...stageRules].map((item) => item.trim()).filter((item) => item && keywords[stepKey]?.test(item)))];
}

function plannerSteps(model = {}, stage = {}) {
  return PLANNER_STEPS.map(([key, title, fields, fallback]) => ({
    key,
    title,
    content: readableValue(firstStageValue(stage, fields), fallback),
    rules: contextualRules(model, stage, key),
    questions: key === "result" ? [...(stage.unresolvedQuestions || stage.pendingQuestions || [])].map((item) => typeof item === "string" ? item : item?.text || "").filter(Boolean) : [],
  }));
}

function stageEditOperations(stage = {}, draft = {}) {
  const loop = stage.smallLoop || {};
  const operations = [];
  const title = String(draft.title ?? "");
  const before = String(draft.before ?? "");
  const nextLoop = {
    display: String(loop.display || stage.name || "unknown"),
    trigger: String(draft.action ?? ""),
    feedback: String(draft.feedback ?? ""),
    result: String(draft.result ?? ""),
    retry: String(loop.retry || "unknown"),
  };
  if (title !== String(stage.name || "")) operations.push({ type: "set", entity: "stage", id: stage.id, field: "name", value: title });
  if (before !== String(stage.entryCondition || stage.beforeState || "")) operations.push({ type: "set", entity: "stage", id: stage.id, field: "entryCondition", value: before });
  if (["display", "trigger", "feedback", "result", "retry"].some((key) => nextLoop[key] !== String(loop[key] || (key === "display" ? stage.name : key === "retry" ? "unknown" : "")))) {
    operations.push({
      type: "set_small_loop",
      id: stage.id,
      smallLoop: nextLoop,
    });
  }
  return operations;
}

function plannerStageStatus(stage) {
  if (stage.confirmation?.confirmed) return ["已完成", "is-complete"];
  if ((stage.validation?.warnings || stage.warnings || []).length || (stage.unresolvedQuestions || []).length) return ["存在待确认", "needs-attention"];
  return ["待检查", "is-pending"];
}

function transitionDecisionCopy(stage = {}, target = {}, transition = {}) {
  const hasTarget = Boolean(target?.name);
  const targetName = target?.name || "流程结束";
  const trigger = ({
    tap: "玩家点按后", long_press: "玩家长按后", swipe: "玩家滑动后",
    drag: "玩家拖动后", automatic: "系统条件满足后", auto: "系统条件满足后",
  })[transition.triggerType] || "完成当前操作后";
  return {
    question: hasTarget ? `完成“${stage.name || "当前环节"}”后，下一步是否进入“${targetName}”？` : `完成“${stage.name || "当前环节"}”后，流程是否结束？`,
    yes: hasTarget ? `是，进入“${targetName}”` : "是，本流程到这里结束",
    no: "否，这不是下一步",
    trigger,
  };
}

function exclusiveBranchOperations(transitions = [], selectedId = "") {
  const selected = transitions.find((item) => item.id === selectedId);
  if (!selected || selected.choiceMode !== "exclusive" || !selected.choiceGroupId) return [];
  return transitions
    .filter((item) => item.choiceGroupId === selected.choiceGroupId && !item.duplicateOf)
    .filter((item) => Boolean(item.included) !== (item.id === selectedId))
    .map((item) => ({ type: "set_transition_included", id: item.id, included: item.id === selectedId }));
}

function stageSourceIds(model = {}, stageId = "") {
  return Object.entries(model.sources || {})
    .filter(([, source]) => source?.stageId === stageId)
    .sort((left, right) => Number(left[1]?.sequenceIndex || 0) - Number(right[1]?.sequenceIndex || 0))
    .map(([frameId]) => frameId);
}

function materialRoleLabel(role = "") {
  return ({ independent_page: "独立页面", supplemental: "补充画面", duplicate: "重复画面" })[role] || "需要分类";
}

function frameInformation(source = {}) {
  const info = source.pageInfo || {};
  return {
    purpose: readableValue(info.purpose, "需要补充这张画面的主要用途"),
    before: readableValue(info.before, "需要补充画面出现前的状态"),
    action: readableValue(info.action, "需要补充玩家操作或自动触发条件"),
    feedback: readableValue(info.feedback, "需要补充系统反馈"),
    result: readableValue(info.result, "需要补充操作后的结果"),
    secondary: Array.isArray(source.secondaryInformation) ? source.secondaryInformation.filter(Boolean) : [],
  };
}

function evidenceOpen(selectedFrameId, frameIds = []) {
  return Boolean(selectedFrameId && frameIds.includes(selectedFrameId));
}

function renderFrameInformation(parent, workspace, stage, frameId, onShowFrame) {
  const source = workspace.model.sources?.[frameId] || {};
  const info = frameInformation(source);
  const card = el("article", "", { class: "planner-frame-information", "data-frame-id": frameId });
  const heading = el("header", "", { class: "planner-frame-information-heading" });
  heading.append(el("h4", `${frameId} · ${materialRoleLabel(source.materialRole)}`));
  heading.append(button("查看这张截图", () => onShowFrame?.(frameId), { className: "btn" }));
  card.append(heading);
  [["画面用途", info.purpose], ["出现前", info.before], ["玩家操作", info.action], ["系统反馈", info.feedback], ["操作结果", info.result]]
    .forEach(([label, value]) => { const row = el("p", "", { class: "planner-frame-information-row" }); row.append(el("strong", label), el("span", value)); card.append(row); });
  if (info.secondary.length) {
    const list = el("ul", "", { class: "planner-frame-secondary" });
    info.secondary.forEach((item) => list.append(el("li", item)));
    card.append(el("strong", "页面上的等级、资源与状态信息"), list);
  }
  parent.append(card);
}

function render(workspace) {
  if (typeof document === "undefined" || !workspace?.root) return;
  const { root, model } = workspace;
  root.__stageReviewCleanup?.();
  root.textContent = "";
  const stage = stageFor(model, workspace.selectedStageId);
  if (!stage) {
    root.append(el("p", "目前没有需要检查的交互环节。", { class: "stage-review-muted" }));
    return;
  }

  const contextBar = el("header", "", { class: "review-context-bar" });
  contextBar.append(el("strong", "当前环节"), el("span", `当前素材 / 交互流程 / ${stage.name || "待命名环节"}`));
  root.append(contextBar);

  const shell = el("div", "", { class: "planner-review-shell" });
  const navigation = el("nav", "", { class: "planner-stage-nav", "aria-label": "交互环节" });
  navigation.append(el("h3", "交互环节"));
  [...(model.stages || [])].sort((a, b) => (a.order || 0) - (b.order || 0)).forEach((item) => {
    const [statusLabel, statusClass] = plannerStageStatus(item);
    const tab = button("", () => workspace.onSelect?.({ type: "stage", id: item.id, stageId: item.id }), {
      className: `planner-stage-button ${statusClass}`,
      label: `${item.name || "待命名环节"}，${statusLabel}`,
    });
    tab.append(el("span", item.name || "待命名环节", { class: "planner-stage-name" }), el("span", statusLabel, { class: "planner-stage-status" }));
    tab.classList.toggle("is-active", item.id === stage.id);
    tab.setAttribute("aria-current", item.id === stage.id ? "step" : "false");
    navigation.append(tab);
  });

  const content = el("section", "", { class: "planner-stage-content", "aria-labelledby": "plannerStageTitle" });
  const heading = el("header", "", { class: "planner-stage-heading" });
  heading.append(el("p", "当前检查", { class: "planner-eyebrow" }), el("h3", stage.name || "待命名环节", { id: "plannerStageTitle" }));
  heading.append(el("p", "请检查这个环节的操作与反馈是否准确。", { class: "planner-stage-objective" }));
  content.append(heading);

  const outgoing = (model.transitions || []).filter((item) => item.sourceStageId === stage.id && !item.duplicateOf);
  if (outgoing.length > 1) {
    const flow = el("section", "", { class: "planner-stage-flow" });
    flow.append(el("h4", "确认分支去向"), el("p", "当前环节存在多个可能去向，请保留素材中实际发生的分支。", { class: "stage-review-muted" }));
    const renderedGroups = new Set();
    outgoing.forEach((transition) => {
      if (transition.choiceMode === "exclusive" && renderedGroups.has(transition.choiceGroupId)) return;
      if (transition.choiceMode === "exclusive") renderedGroups.add(transition.choiceGroupId);
      const target = (model.stages || []).find((item) => item.id === transition.targetStageId);
      const copy = transitionDecisionCopy(stage, target, transition);
      const row = el("fieldset", "", { class: "planner-stage-flow-row" });
      if (transition.choiceMode === "exclusive") {
        row.append(el("legend", "这几个去向只能选择一个"));
        outgoing.filter((item) => item.choiceGroupId === transition.choiceGroupId).forEach((choice) => {
          const choiceTarget = (model.stages || []).find((item) => item.id === choice.targetStageId);
          const option = el("label", "", { class: "planner-stage-flow-option" }); const input = el("input");
          input.type = "radio"; input.name = transition.choiceGroupId; input.checked = Boolean(choice.included); input.disabled = Boolean(workspace.readOnly);
          input.addEventListener("change", () => { if (input.checked) workspace.onOperation?.(exclusiveBranchOperations(outgoing, choice.id)); });
          option.append(input, el("span", transitionDecisionCopy(stage, choiceTarget, choice).yes)); row.append(option);
        });
      } else {
        row.append(el("legend", copy.question));
        [[true, copy.yes], [false, copy.no]].forEach(([included, label]) => {
          const option = el("label", "", { class: "planner-stage-flow-option" }); const input = el("input");
          input.type = "radio"; input.name = `transition-${transition.id}`; input.checked = Boolean(transition.included) === included; input.disabled = Boolean(workspace.readOnly);
          input.addEventListener("change", () => { if (input.checked) workspace.onOperation?.([{ type: "set_transition_included", id: transition.id, included }]); });
          option.append(input, el("span", label)); row.append(option);
        });
      }
      flow.append(row);
    });
    content.append(flow);
  }

  const stepDetails = el("details", "", { class: "planner-step-details" });
  stepDetails.open = true;
  stepDetails.append(el("summary", "AI 识别流程 · 只读"));
  const stepList = el("div", "", { class: "planner-step-list" });
  plannerSteps(model, stage).forEach((step, index) => {
    const card = el("article", "", { class: `planner-step-card planner-step-${step.key}` });
    const marker = el("div", "", { class: "planner-step-marker", "aria-hidden": "true" });
    marker.append(el("span", String(index + 1)), el("strong", step.title));
    const body = el("div", "", { class: "planner-step-body" });
    body.append(el("h4", step.title), el("p", step.content, { class: "planner-step-description" }));
    if (step.rules.length) {
      const rules = el("ul", "", { class: "planner-rule-list" });
      step.rules.forEach((rule) => rules.append(el("li", rule)));
      body.append(el("h5", "相关规则"), rules);
    }
    if (step.questions.length) {
      const questions = el("div", "", { class: "planner-inline-questions" });
      questions.append(el("strong", "需要确认"));
      step.questions.forEach((question) => questions.append(el("p", question)));
      body.append(questions);
    }
    card.append(marker, body);
    stepList.append(card);
  });
  stepDetails.append(stepList);
  content.append(stepDetails);

  const editor = el("details", "", { class: "planner-evidence-drawer planner-page-editor" });
  editor.open = true;
  editor.append(el("summary", "策划确认与修改"));
  const editorForm = el("form", "", { class: "flow-review-form planner-evidence-body planner-page-editor-form" });
  editorForm.append(el("p", "修改内容会用于策划草图中的页面名称、页面功能和页面流转。", { class: "stage-review-muted planner-page-editor-help" }));
  const loop = stage.smallLoop || {};
  const editorControls = {
    title: input(stage.name || ""),
    before: input(stage.entryCondition || stage.beforeState || "", true),
    action: input(loop.trigger || stage.trigger || stage.userAction || "", true),
    feedback: input(loop.feedback || stage.systemFeedback || stage.systemResponse || "", true),
    result: input(loop.result || stage.afterState || stage.exitCondition || "", true),
  };
  Object.values(editorControls).forEach((control) => { control.disabled = Boolean(workspace.readOnly); });
  [["页面名称", "title"], ["操作前", "before"], ["玩家操作", "action"], ["系统反馈", "feedback"], ["操作结果", "result"]]
    .forEach(([label, key]) => editorForm.append(field(label, editorControls[key])));
  editorForm.append(button("保存修改", () => workspace.onOperation?.([stageEditOperations(stage, Object.fromEntries(
    Object.entries(editorControls).map(([key, control]) => [key, control.value])
  ))].flat()), { disabled: workspace.readOnly, className: "btn primary" }));
  editorForm.addEventListener("submit", (event) => event.preventDefault());
  editor.append(editorForm);
  content.append(editor);

  const evidence = el("details", "", { class: "planner-evidence-drawer" });
  const evidenceFrameIds = stageSourceIds(model, stage.id);
  evidence.open = true;
  evidence.append(el("summary", "本环节截图"));
  const evidenceBody = el("div", "", { class: "planner-evidence-body" });
  const loadEvidence = () => {
    if (!evidence.open || evidenceBody.childNodes.length) return;
    const frameIds = evidenceFrameIds;
    const frameId = workspace.selectedFrameId || frameIds[0] || stage.representativeFrames?.[0]?.frameId || Object.keys(model.sources || {})[0];
    const viewer = el("div", "", { class: "planner-frame-viewer" });
    const showFrame = (nextFrameId) => {
      viewer.replaceChildren();
      renderFrame(viewer, workspace, stage, nextFrameId);
      workspace.onSelectFrame?.({ type: "frame", id: nextFrameId, stageId: stage.id, frameId: nextFrameId });
    };
    if (frameId) { renderFrame(viewer, workspace, stage, frameId); evidenceBody.append(viewer); }
    else evidenceBody.append(el("p", "当前环节没有可查看的原始截图。", { class: "stage-review-muted" }));
    if (frameIds.length) {
      const information = el("section", "", { class: "planner-frame-information-list", "aria-label": "每张截图的信息与页面关系" });
      information.append(el("h4", "每张截图的信息与页面关系"));
      frameIds.forEach((id) => renderFrameInformation(information, workspace, stage, id, showFrame));
      evidenceBody.append(information);
    }
  };
  evidence.addEventListener("toggle", loadEvidence);
  loadEvidence();
  evidence.append(evidenceBody);
  content.append(evidence);

  const remaining = [...(stage.validation?.warnings || stage.warnings || [])];
  if (remaining.length) {
    const pending = el("section", "", { class: "planner-pending-list" });
    pending.append(el("h4", "稍后补充"), el("p", "这些事项不会阻止你确认当前环节，最终会集中放入待确认清单。"));
    const list = el("ul");
    remaining.forEach((item) => list.append(el("li", typeof item === "string" ? item : item?.message || item?.text || "需要补充一项规则")));
    pending.append(list);
    content.append(pending);
  }

  shell.append(navigation, content);
  root.append(shell);
}

const api = { clampBounds, resizeBounds, resizeByKey, renumberRegions, regionsFor, stageRegions, regionReorderIndex, representativeFrames, representativeFrameChange, representativeFrameOperation, canAnnotateFrame, missingStateSlots, defaultBounds, sourceAspectRatio, naturalAspectRatio, mobileTabIndex, panelAriaHidden, pointerSession, handleResizeKey, stageSummary, selectedComponent, readableValue, contextualRules, plannerSteps, stageEditOperations, plannerText, transitionDecisionCopy, exclusiveBranchOperations, stageSourceIds, materialRoleLabel, frameInformation, evidenceOpen, render };
if (typeof module !== "undefined") module.exports = api;
else root.StageReview = api;
}(typeof window !== "undefined" ? window : globalThis));
