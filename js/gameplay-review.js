(function (root, factory) {
const GameplayReviewApi = factory(
  typeof module !== "undefined" && module.exports ? require("./gameplay-mechanism-forms.js") : root.GameplayMechanismForms,
  typeof module !== "undefined" && module.exports ? require("./planner-decision-cards.js") : root.PlannerDecisionCards
);
if (typeof module !== "undefined" && module.exports) module.exports = GameplayReviewApi;
else root.GameplayReview = GameplayReviewApi;
})(typeof window !== "undefined" ? window : globalThis, function (MechanismForms, DecisionCards) {
function text(value) { return value == null ? "" : String(value); }
function el(tag, content = "", attrs = {}) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  if (content !== "") node.textContent = content;
  return node;
}
function button(label, onClick, className = "") {
  const node = el("button", label, { type: "button", ...(className ? { class: className } : {}) });
  node.addEventListener("click", onClick);
  return node;
}
function field(label, value = "", kind = "input") {
  const wrap = el("label", "", { class: "gameplay-field" });
  const title = el("span", label);
  const input = el(kind, ""); input.value = text(value);
  const error = el("span", "", { class: "gameplay-field-error", role: "alert", "aria-live": "assertive" });
  wrap.append(title, input, error); input.errorNode = error;
  return { wrap, input, error };
}
function required(input, label) {
  const value = text(input.value).trim();
  input.errorNode.textContent = value ? "" : `请填写${label}`;
  return value;
}

const STATUS = { draft: "待检查", chapter_review: "待检查", reviewed: "已检查", approved: "已通过", conditional: "补充后通过", rejected: "退回修改" };
function statusLabel(status) { return STATUS[status] || text(status) || "待审阅"; }
function saveStatusLabel(status) {
  return ({ queued: "等待保存…", saving: "正在保存…", failed: "保存失败，请重试", conflict: "版本冲突，正在同步", conflict_synced: "已同步最新版本", synced: "已同步最新版本", saved: "已保存" })[status] || "已保存";
}
function contextStatusLabel(status) {
  return ({ matching: "正在查找前后画面…", completed: "已找到可以参考的前后画面。", needs_location: "请补充对应的视频位置后再试。", needs_planner_location: "请补充对应的视频位置后再试。", failed: "没有找到可用于确认这条规则的前后画面。" })[status] || "";
}
function parameterComplete(value) { return value && ["type", "unit", "range", "source"].every((key) => text(value[key]).trim() && text(value[key]).trim().toLowerCase() !== "unknown"); }
function configuredParameterFields(chapter) {
  const mechanismKeys = new Set(MechanismForms?.allFieldKeys?.() || []);
  return Object.keys(chapter?.parameters || {})
    .filter((key) => !mechanismKeys.has(key))
    .map((key) => ({ key, label: key, helper: "填写素材中已经出现、或策划明确需要配置的数值。" }));
}
function contextFieldsFor(chapter) {
  const missing = configuredParameterFields(chapter).filter(({ key }) => !parameterComplete(chapter?.parameters?.[key])).map(({ key }) => key.toLowerCase());
  const result = [];
  const add = (name) => { if (!result.includes(name)) result.push(name); };
  if (missing.some((key) => /trigger|entry|unlock|eligib|spawn/.test(key))) add("trigger");
  if (missing.some((key) => /phase|order|movement|attack|target|process|goal/.test(key))) add("process");
  if (missing.some((key) => /completion|failure|reward|result|effect|death|hit/.test(key))) add("result");
  if (missing.some((key) => /reset|duration|cooldown|refresh|time/.test(key))) add("timing");
  if (missing.some((key) => /transition/.test(key))) add("automaticTransition");
  if (missing.length && !result.length) ["trigger", "process", "result", "timing"].forEach(add);
  return result;
}
function chapterOperation(chapterId, fieldName, value) { return { type: "set_chapter_field", chapterId, field: fieldName, value }; }
function parameterOperation(chapterId, name, parameter) { return { type: "upsert_parameter", chapterId, name, parameter }; }
function nextPending(chapters, currentId, direction = 1) {
  const items = chapters || []; if (!items.length) return null;
  const pending = items.filter((item) => !item.confirmation?.confirmed); if (!pending.length) return null;
  const currentIndex = items.findIndex((item) => item.id === currentId); if (currentIndex < 0) return pending[0];
  for (let offset = 1; offset < items.length; offset += 1) {
    const candidate = items[(currentIndex + (direction < 0 ? -offset : offset) + items.length) % items.length];
    if (!candidate.confirmation?.confirmed) return candidate;
  }
  return null;
}
function mobileTabs() { return [{ key: "content", label: "内容" }, { key: "parameters", label: "参数" }, { key: "issues", label: "问题" }]; }
function decisionOptions() {
  return [
    { value: "approved", label: "识别正确" },
    { value: "needs_edit", label: "部分正确，需要修改" },
    { value: "not_applicable", label: "这一章不适用" },
  ];
}
function decisionAction(value) {
  if (value === "approved") return { decision: "approved", advance: true };
  if (value === "not_applicable") return { decision: "not_applicable", advance: true };
  return { decision: null, advance: false };
}
function hasSupplementalDetails(chapter, findings = []) {
  return configuredParameterFields(chapter).length > 0
    || (chapter.dependencies || []).length > 0
    || (chapter.acceptanceCases || []).length > 0
    || (chapter.decisionCards || []).some((card) => card.status === "pending" || card.status === "skipped")
    || (chapter.claims || []).some((claim) => claim.sourceType === "pending" || !(claim.sourceFrameIds || []).length)
    || findings.some((item) => item.chapterId === chapter.id && item.status !== "resolved");
}
function renderSummaryEditor(parent, workspace, chapter) {
  const editor = field("修改后的玩法说明", chapterSummary(chapter), "textarea");
  editor.wrap.setAttribute("class", "gameplay-field gameplay-planner-summary-editor");
  editor.input.addEventListener("blur", () => {
    const value = required(editor.input, "玩法说明");
    if (value && value !== chapterSummary(chapter)) workspace.onOperation?.([chapterOperation(chapter.id, "plannerSummary", value)]);
  });
  parent.append(editor.wrap);
}
function viewModel(model, state = {}) {
  const blockers = (model.reviewState?.findings || []).filter((item) => item.severity === "blocker" && item.status !== "resolved");
  return { chapters: (model.chapters || []).map((chapter) => ({ ...chapter, collapsed: chapter.confirmation?.confirmed && !(chapter.decisionCards || []).some((card) => card.status !== "resolved"), blockers: blockers.filter((item) => item.chapterId === chapter.id).length })), selectedChapterId: state.selectedChapterId, totalBlockers: blockers.length };
}
function expanded(state, chapterId, group) { return (state.expandedGroups || []).includes(`${chapterId}:${group}`); }
function keepDetailsState(details, workspace, chapterId, group) {
  details.open = expanded(workspace.state || {}, chapterId, group);
  details.addEventListener("toggle", () => {
    if (details.open !== expanded(workspace.state || {}, chapterId, group)) workspace.onToggleGroup?.(chapterId, group);
  });
}
function claimNeedsReview(chapter, state) {
  return expanded(state, chapter.id, "claims") || (state.editedGroups || []).includes(`${chapter.id}:claims`) || (chapter.claims || []).some((claim) => claim.sourceType === "pending" || !(claim.sourceFrameIds || []).length);
}
function chapterSummary(chapter) {
  return text(chapter?.plannerSections?.summary || chapter?.plannerSummary).trim() || "这部分玩法还需要补充明确的机制结论。";
}

function normalizeGameplayCopy(value) {
  return text(value).toLowerCase().replace(/[\s，。！？、；：,.!?;:'"“”‘’（）()\-]/g, "");
}

function semanticallyOverlaps(left, right) {
  const a = normalizeGameplayCopy(left); const b = normalizeGameplayCopy(right);
  if (!a || !b) return false;
  if (a.includes(b) || b.includes(a)) return Math.min(a.length, b.length) / Math.max(a.length, b.length) >= 0.72;
  const grams = (value) => new Set(Array.from({ length: Math.max(0, value.length - 1) }, (_, index) => value.slice(index, index + 2)));
  const ag = grams(a); const bg = grams(b); const shared = [...ag].filter((item) => bg.has(item)).length;
  return shared / Math.max(1, Math.min(ag.size, bg.size)) >= 0.82;
}

function gameplayList(value) {
  if (Array.isArray(value)) return value.flatMap(gameplayList);
  if (value == null) return [];
  const item = text(value).trim();
  return item ? [item] : [];
}

function uniqueGameplayCopy(items, excluded = []) {
  const values = gameplayList(items); const exclusions = gameplayList(excluded);
  return values.filter((item, index, all) => item && !exclusions.some((other) => semanticallyOverlaps(item, other)) && !all.slice(0, index).some((other) => semanticallyOverlaps(item, other)));
}

function chapterContentRoles(chapter) {
  const flow = uniqueGameplayCopy(chapter.plannerSections?.normalFlow || []);
  const summary = chapterSummary(chapter);
  const summaryIsFlow = flow.some((item) => semanticallyOverlaps(summary, item));
  return {
    flow,
    summary: summaryIsFlow ? "" : summary,
    keyRules: uniqueGameplayCopy(chapter.plannerSections?.keyRules || [], [summary, ...flow].filter(Boolean)),
    presentationRules: uniqueGameplayCopy(chapter.plannerSections?.presentationRules || [], [summary, ...flow].filter(Boolean)),
    numericRules: uniqueGameplayCopy(chapter.plannerSections?.numericRules || [], [summary, ...flow].filter(Boolean)),
    configurationRules: uniqueGameplayCopy(chapter.plannerSections?.configurationRules || [], [summary, ...flow].filter(Boolean)),
  };
}
function appendPlannerList(parent, title, values, ordered = false) {
  const items = gameplayList(values); if (!items.length) return;
  const list = el(ordered ? "ol" : "ul"); items.forEach((value) => list.append(el("li", value))); parent.append(el("h4", title), list);
}
function evidenceCard(workspace, item, primary = false, visibleCaption = "") {
  const caption = visibleCaption || item.caption || "这张图用于核对当前玩法规则";
  const source = workspace.resolveEvidenceUrl?.(item.imageUrl) || item.imageUrl || "";
  let imageFailed = false;
  let retryCount = 0;
  let image;
  let failure;
  const card = button("", (event) => {
    if (!imageFailed) return workspace.onOpenEvidence?.(item.anchorId, event.currentTarget);
    event.preventDefault();
    imageFailed = false;
    retryCount += 1;
    failure.textContent = "正在重试…";
    const hashAt = source.indexOf("#");
    const base = hashAt < 0 ? source : source.slice(0, hashAt);
    const hash = hashAt < 0 ? "" : source.slice(hashAt);
    image.setAttribute("src", `${base}${base.includes("?") ? "&" : "?"}vpr_image_retry=${retryCount}${hash}`);
  }, `gameplay-inline-evidence-card${primary ? " gameplay-inline-evidence-primary" : ""}`);
  card.setAttribute("aria-label", `${caption}，点击放大`);
  image = el("img", "", {
    class: "gameplay-inline-evidence-image", src: source,
    alt: item.caption || "玩法参考画面", loading: "lazy",
    ...(item.width ? { width: item.width } : {}), ...(item.height ? { height: item.height } : {}),
  });
  failure = el("span", "", { class: "gameplay-inline-evidence-error", role: "status" });
  image.addEventListener("error", () => { imageFailed = true; failure.textContent = "画面加载失败，点击重试"; });
  image.addEventListener("load", () => { imageFailed = false; failure.textContent = ""; });
  card.append(image, el("span", caption, { class: "gameplay-inline-evidence-caption" }), failure);
  return card;
}
function renderInlineEvidence(parent, workspace, chapter) {
  const evidence = (chapter.inlineEvidence || []).filter((item) => item && item.imageUrl);
  if (!evidence.length) return;
  const section = el("section", "", { class: "gameplay-inline-evidence" }); section.append(el("h4", "对应参考画面"));
  const seenCaptions = new Set();
  const captionFor = (item) => { const caption = text(item.caption).trim(); if (!caption || seenCaptions.has(caption)) return "同一过程的补充画面"; seenCaptions.add(caption); return caption; };
  const primary = el("div", "", { class: "gameplay-inline-evidence-grid" }); evidence.slice(0, 3).forEach((item) => primary.append(evidenceCard(workspace, item, true, captionFor(item)))); section.append(primary);
  if (evidence.length > 3) {
    const more = el("details", "", { class: "gameplay-inline-evidence-more" }); more.append(el("summary", `查看更多参考画面（${evidence.length - 3}）`));
    const grid = el("div", "", { class: "gameplay-inline-evidence-grid" }); evidence.slice(3).forEach((item) => grid.append(evidenceCard(workspace, item, false, captionFor(item)))); more.append(grid); section.append(more);
  }
  parent.append(section);
}

function systemsForDisplay(model) {
  if ((model.systems || []).length) return model.systems;
  const entries = [...(model.directory?.entries || [])].sort((left, right) => Number(left.order || 0) - Number(right.order || 0));
  if (!entries.some((item) => item.sectionTitle)) return [];
  const groups = [];
  entries.forEach((entry) => {
    const name = entry.sectionTitle || "其他玩法";
    let system = groups.find((item) => item.name === name);
    if (!system) {
      system = { id: `legacy-system-${groups.length + 1}`, name, subsystems: [{ id: `legacy-subsystem-${groups.length + 1}`, name: "玩法机制", chapterIds: [] }] };
      groups.push(system);
    }
    if (entry.chapterId) system.subsystems[0].chapterIds.push(entry.chapterId);
  });
  return groups;
}

function renderRuleAuditSections(parent, chapter) {
  const roles = chapterContentRoles(chapter);
  const sections = el("div", "", { class: "gameplay-rule-audit-sections" });
  const add = (number, title) => {
    const section = el("section", "", { class: "gameplay-rule-audit-section" });
    const heading = el("h4"); heading.append(el("span", String(number), { class: "gameplay-rule-audit-number" }), el("span", title));
    section.append(heading); sections.append(section); return section;
  };
  const understanding = add(1, "规则理解");
  if (roles.summary) understanding.append(el("p", roles.summary)); else understanding.hidden = true;
  const flow = add(2, "玩法流程");
  const flowList = el("ol"); roles.flow.slice(0, 5).forEach((item) => flowList.append(el("li", item))); flow.append(flowList);
  if (!roles.flow.length) flow.hidden = true;
  const ownedRules = [
    ["逻辑规则", roles.keyRules],
    ["表现规则", roles.presentationRules],
    ["数值规则", roles.numericRules],
    ["配置规则", roles.configurationRules],
  ].filter(([, items]) => items.length);
  if (ownedRules.length) {
    const rules = add(3, "关键规则");
    ownedRules.forEach(([label, items]) => {
      rules.append(el("h5", label));
      const ruleList = el("ul"); items.slice(0, 6).forEach((item) => ruleList.append(el("li", item))); rules.append(ruleList);
    });
  }
  const parameters = add(3, "参数配置");
  const table = el("table", "", { class: "gameplay-rule-audit-table" });
  const head = el("tr"); ["参数", "类型", "当前值", "状态"].forEach((label) => head.append(el("th", label))); table.append(head);
  const fields = configuredParameterFields(chapter);
  if (!fields.length) { const row = el("tr"); const cell = el("td", "本章没有需要单独配置的数值"); cell.setAttribute("colspan", "4"); row.append(cell); table.append(row); }
  fields.forEach(({ key, label }) => { const value = chapter.parameters?.[key] || {}; const row = el("tr"); [label, value.type || "—", value.value ?? value.default ?? "待填写", parameterComplete(value) ? "已确认" : "待确认"].forEach((item) => row.append(el("td", String(item)))); table.append(row); });
  parameters.append(table);
  const checks = gameplayList(chapter.plannerSections?.acceptanceExamples).length ? gameplayList(chapter.plannerSections?.acceptanceExamples) : gameplayList(chapter.acceptanceCases);
  const verificationItems = [
    ...(Array.isArray(chapter.configurationSources) ? chapter.configurationSources : gameplayList(chapter.configurationSources)).map((item) => typeof item === "string" ? item : `数值从哪里配置：${[moduleValue(item.title || item.name), moduleValue(item.field)].filter(Boolean).join(" · ")}`),
    ...checks,
  ];
  if (verificationItems.length) {
    const verify = add(4, "配置与验证");
    verify.setAttribute("aria-label", "验证方式");
    const list = el("ul"); verificationItems.slice(0, 5).forEach((item) => list.append(el("li", typeof item === "string" ? item : [item.scene, item.action, item.expected].filter(Boolean).join("：")))); verify.append(list);
  }
  const pendingDecisions = (chapter.decisionCards || []).filter((card) => card.status === "pending" || card.status === "skipped");
  if (pendingDecisions.length) {
    const decisions = add(5, "策划决策");
    const decisionList = el("ul");
    pendingDecisions.slice(0, 5).forEach((item) => decisionList.append(el("li", item.question)));
    decisions.append(decisionList);
  }
  [...sections.querySelectorAll(".gameplay-rule-audit-section:not([hidden])")].forEach((section, index) => {
    const badge = section.querySelector(".gameplay-rule-audit-number");
    if (badge) badge.textContent = String(index + 1);
  });
  parent.append(sections);
}

function renderDecisionCards(parent, workspace, chapter) {
  DecisionCards?.render?.({
    root: parent, cards: chapter.decisionCards || [], context: { chapterId: chapter.id }, document,
    onResolve: (value) => workspace.onOperation?.([DecisionCards.resolveOperation(value)]),
    onSkip: (value) => workspace.onOperation?.([DecisionCards.skipOperation(value)]),
  });
}
function renderRail(root, workspace, chapter) {
  const rail = el("nav", "", { class: "gameplay-chapter-rail", "aria-label": "玩法目录" }); rail.append(el("h3", "玩法目录"));
  const chapters = workspace.model.chapters || []; const review = viewModel(workspace.model, workspace.state || {});
  rail.append(el("p", `已确认 ${chapters.filter((item) => item.confirmation?.confirmed).length}/${chapters.length} · 确认前需要补全 ${review.totalBlockers}`));
  const chapterButton = (item) => {
    const selected = item.id === chapter?.id;
    return button(`${item.scope} · ${statusLabel(item.status)}`, () => workspace.onSelectChapter?.(item.id), `gameplay-chapter-item${selected ? " is-selected" : ""}`);
  };
  const chapterById = new Map(chapters.map((item) => [item.id, item]));
  const systems = systemsForDisplay(workspace.model);
  if (systems.length) {
    systems.forEach((system) => {
      const systemGroup = el("section", "", { class: "gameplay-system-group", "data-gameplay-system": system.id });
      systemGroup.append(el("h4", system.name || "其他玩法"));
      (system.subsystems || []).forEach((subsystem) => {
        const subsystemGroup = el("div", "", { class: "gameplay-subsystem-group", "data-gameplay-subsystem": subsystem.id });
        subsystemGroup.append(el("h5", subsystem.name || system.name || "其他玩法"));
        (subsystem.chapterIds || []).map((id) => chapterById.get(id)).filter(Boolean).forEach((item) => subsystemGroup.append(chapterButton(item)));
        systemGroup.append(subsystemGroup);
      });
      rail.append(systemGroup);
    });
  } else chapters.forEach((item) => rail.append(chapterButton(item)));
  const pending = el("div", "", { class: "gameplay-pending-nav" });
  [["上一个未通过", -1], ["下一个未通过", 1]].forEach(([label, direction]) => {
    const target = nextPending(chapters, chapter?.id, direction);
    const control = button(label, () => target && workspace.onSelectChapter?.(target.id), "gameplay-pending-button");
    control.disabled = !target;
    pending.append(control);
  });
  rail.append(pending); root.append(rail);
}
function renderEvidenceColumn(root, workspace, chapter) {
  const column = el("aside", "", { class: "gameplay-evidence-column", "aria-label": "对应素材" });
  const evidence = chapter?.inlineEvidence || [];
  column.append(el("div", "", { class: "gameplay-column-heading" }));
  column.children[0].append(el("h3", "本节参考画面"), el("span", `${evidence.length} 张有效证据`));
  if (evidence.length) {
    const primaryCaption = evidence[0].caption || "支持当前规则判断";
    const primary = el("div", "", { class: "gameplay-evidence-primary-view" });
    primary.append(evidenceCard(workspace, evidence[0], true, primaryCaption)); column.append(primary);
    if (evidence.length > 1) {
      const thumbs = el("div", "", { class: "gameplay-evidence-thumbnails" });
      evidence.slice(1, 5).forEach((item) => thumbs.append(evidenceCard(workspace, item, false, item.caption === primaryCaption ? "同一过程的补充画面" : item.caption || "补充画面"))); column.append(thumbs);
    }
    const facts = el("section", "", { class: "gameplay-evidence-facts" }); facts.append(el("h4", "画面可以确认"));
    const roles = chapterContentRoles(chapter); const reserved = [roles.summary, ...roles.flow].filter(Boolean);
    uniqueGameplayCopy((chapter.evidenceClaims || chapter.claims || []).map((claim) => text(claim.text || claim)), reserved)
      .slice(0, 4).forEach((claim) => facts.append(el("p", claim)));
    if (facts.children.length > 1) column.append(facts);
  } else column.append(el("p", "当前机制暂无可展示的参考画面。", { class: "gameplay-evidence-empty" }));
  root.append(column);
}
function moduleValue(value) {
  if (value == null) return "";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(moduleValue).filter(Boolean).join("、");
  return text(value.title || value.name || value.label || value.steps || value.expression || value.value || value.description || "");
}
function renderPlannerModules(parent, chapter) {
  const modules = el("div", "", { class: "gameplay-planner-modules" });
  if ((chapter.parameterSchema || []).length) {
    const section = el("section", "", { class: "gameplay-group gameplay-parameter-schema" }); section.append(el("h4", "需要配置的数值"));
    chapter.parameterSchema.forEach((item) => section.append(el("p", [moduleValue(item.name || item.title), moduleValue(item.type), moduleValue(item.unit), moduleValue(item.defaultValue || item.value)].filter(Boolean).join(" · ")))); modules.append(section);
  }
  if ((chapter.formulae || []).length) {
    const section = el("section", "", { class: "gameplay-group gameplay-formulae" }); section.append(el("h4", "计算方法"));
    chapter.formulae.forEach((item) => section.append(el("p", moduleValue(item.expression || item)))); modules.append(section);
  }
  if ((chapter.workedExamples || []).length) {
    const section = el("section", "", { class: "gameplay-group gameplay-worked-examples" }); section.append(el("h4", "计算示例"));
    chapter.workedExamples.forEach((item) => section.append(el("p", [moduleValue(item.title), moduleValue(item.steps || item.result || item)].filter(Boolean).join("：")))); modules.append(section);
  }
  if ((chapter.configurationSources || []).length) {
    const section = el("section", "", { class: "gameplay-group gameplay-configuration-sources" }); section.append(el("h4", "数值从哪里配置"));
    chapter.configurationSources.forEach((item) => section.append(el("p", [moduleValue(item.title || item.name), moduleValue(item.field)].filter(Boolean).join(" · ")))); modules.append(section);
  }
  if (modules.children?.length) parent.append(modules);
}
function planningRows(chapter) {
  const rows = (chapter.parameterSchema || []).map((item) => ({
    name: moduleValue(item.name || item.title || item.key),
    meaning: moduleValue(item.description || item.meaning || item.plannerMeaning),
    type: [moduleValue(item.type), moduleValue(item.unit)].filter(Boolean).join(" / "),
    source: moduleValue(item.source || item.configurationSource || item.currentBasis),
    status: moduleValue(item.status || item.confirmationStatus) || "待核定",
  }));
  configuredParameterFields(chapter).forEach(({ key, label, helper }) => {
    if (rows.some((row) => row.name === label || row.name === key)) return;
    const value = chapter.parameters?.[key] || {};
    rows.push({ name: label, meaning: helper, type: [value.type, value.unit].filter(Boolean).join(" / "), source: value.source || "当前素材", status: parameterComplete(value) ? "已确认" : "待核定" });
  });
  return rows;
}
function reviewFocus(chapter) {
  return [
    { key: "parameters", title: "数值与配置", count: planningRows(chapter).length, unit: "项", empty: "本章没有需要单独配置的数值" },
    { key: "issues", title: "怎么验证", count: (chapter.acceptanceCases || []).length, unit: "条", empty: "还没有检查方法" },
    { key: "issues", title: "需要策划决定", count: (chapter.decisionCards || []).filter((card) => card.status === "pending" || card.status === "skipped").length, unit: "项", empty: "没有遗留决策" },
  ];
}
function renderReviewFocus(parent, workspace, chapter) {
  const items = reviewFocus(chapter).filter((item) => item.count > 0);
  if (!items.length) return;
  const focus = el("section", "", { class: "gameplay-review-focus", "aria-label": "本章审核重点" });
  items.forEach((item) => {
    const card = el("button", "", { class: "gameplay-review-focus-card", type: "button" });
    card.append(el("strong", item.title), el("span", item.count ? `${item.count} ${item.unit}` : item.empty));
    card.addEventListener("click", () => workspace.onTab?.(item.key));
    focus.append(card);
  });
  parent.append(focus);
}
function renderPlanningDocument(parent, chapter) {
  const rows = planningRows(chapter);
  if (rows.length) {
    const section = el("section", "", { class: "gameplay-document-section" });
    section.append(el("h3", (chapter.formulae || []).length ? "参与计算的字段" : "规则所需的数值与条件"));
    const table = el("table", "", { class: "gameplay-planning-table" });
    const head = el("thead"); const headRow = el("tr"); ["字段", "策划含义", "类型与单位", "当前依据", "确认状态"].forEach((label) => headRow.append(el("th", label))); head.append(headRow); table.append(head);
    const body = el("tbody"); rows.forEach((row) => { const tr = el("tr"); tr.append(el("td", row.name || "未命名字段"), el("td", row.meaning || "需要策划补充这项数值的用途"), el("td", row.type || "待确认"), el("td", row.source || "当前素材")); const status = el("td"); status.append(el("span", row.status, { class: `gameplay-status-chip ${row.status.includes("确认") ? "is-confirmed" : "is-pending"}` })); tr.append(status); body.append(tr); }); table.append(body); section.append(table); parent.append(section);
  }
  if ((chapter.formulae || []).length) {
    const section = el("section", "", { class: "gameplay-document-section" }); const formulaTitle = el("h3", "当前可建立的公式"); formulaTitle.append(el("span", "计算方法", { class: "sr-only" })); section.append(formulaTitle);
    const formula = el("div", "", { class: "gameplay-formula-block" }); chapter.formulae.forEach((item) => formula.append(el("p", moduleValue(item.expression || item)))); section.append(formula);
    (chapter.workedExamples || []).forEach((item) => section.append(el("p", [moduleValue(item.title), moduleValue(item.steps || item.result || item)].filter(Boolean).join("："), { class: "gameplay-document-note" }))); parent.append(section);
  }
}
function renderTabs(editor, workspace) {
  const tabs = el("div", "", { class: "gameplay-mobile-tabs", role: "tablist", "aria-label": "章节审阅面板" });
  mobileTabs().forEach(({ key, label }) => tabs.append(button(label, () => workspace.onTab?.(key), "gameplay-mobile-tab")));
  tabs.querySelectorAll?.(".gameplay-mobile-tab").forEach?.((tab, index) => { tab.setAttribute("role", "tab"); tab.setAttribute("aria-selected", String(mobileTabs()[index].key === (workspace.state?.activeTab || "content"))); });
  editor.append(tabs);
}
function renderClaimEditor(panel, workspace, chapter, showExisting) {
  const group = el("section", "", { class: "gameplay-group" }); group.append(el("h3", "素材依据"));
  if ((chapter.claims || []).length) group.append(button(showExisting ? "收起素材依据" : `查看素材依据（${chapter.claims.length}）`, () => workspace.onToggleGroup?.(chapter.id, "claims"), "btn"));
  if (showExisting) (chapter.claims || []).forEach((claim) => {
    const item = field("素材中看到的内容", claim.text, "textarea"); item.wrap.setAttribute("class", "gameplay-field gameplay-claim-editor");
    item.input.addEventListener("blur", () => { const value = required(item.input, "素材内容"); if (value && value !== claim.text) workspace.onOperation?.([{ type: "upsert_claim", chapterId: chapter.id, claim: { ...claim, text: value } }]); }); group.append(item.wrap);
    const sourceWrap = el("label", "", { class: "gameplay-field" }); const source = el("select", "", { class: "gameplay-claim-source", "aria-label": "这条内容是怎么确认的" });
    [["material", "素材中明确展示"], ["reference_document", "参考文档明确说明"], ["inference", "根据前后内容推断"], ["planner", "策划已经确认"], ["pending", "还需要确认"]].forEach(([value, label]) => { const option = el("option", label, { value }); if (value === claim.sourceType) option.setAttribute("selected", "selected"); source.append(option); }); source.value = claim.sourceType || "pending";
    source.addEventListener("change", () => workspace.onOperation?.([{ type: "upsert_claim", chapterId: chapter.id, claim: { ...claim, sourceType: source.value } }])); sourceWrap.append(el("span", "这条内容是怎么确认的"), source); group.append(sourceWrap);
  });
  if (!(chapter.claims || []).length || showExisting) {
    const item = field("新增规则"); const add = button("添加规则", () => { const value = required(item.input, "规则说明"); if (value) workspace.onOperation?.([{ type: "upsert_claim", chapterId: chapter.id, claim: { text: value, sourceType: "material", sourceFrameIds: chapter.sourceFrameIds || [] } }]); }, "gameplay-add-claim"); group.append(item.wrap, add);
  }
  panel.append(group);
}
function renderParameters(panel, workspace, chapter) {
  const group = el("section", "", { class: "gameplay-group gameplay-parameters" }); group.append(el("h3", "需要填写的数值和条件"));
  const showAll = expanded(workspace.state || {}, chapter.id, "parameters");
  const fields = configuredParameterFields(chapter);
  const completeCount = fields.filter(({ key }) => parameterComplete(chapter.parameters?.[key])).length;
  if (!fields.length) group.append(el("p", "当前素材没有识别出需要单独配置的数值。发现明确数值后，系统会在这里列出。"));
  if (completeCount) group.append(button(showAll ? "只看缺失参数" : `查看完整参数（${completeCount}）`, () => workspace.onToggleGroup?.(chapter.id, "parameters"), "btn"));
  fields.filter(({ key }) => showAll || !parameterComplete(chapter.parameters?.[key])).forEach(({ key, label, helper }) => {
    const current = chapter.parameters?.[key] || {}; const card = el("article", "", { class: "gameplay-parameter" }); card.append(el("h4", label), el("p", helper));
    const controls = [["填写格式", "type"], ["数值单位", "unit"], ["可用范围", "range"], ["数值从哪里配置", "source"]].map(([name, prop]) => field(name, current[prop]));
    controls.forEach(({ wrap, input }) => { input.setAttribute("inputmode", "decimal"); input.addEventListener("blur", () => { const values = Object.fromEntries(controls.map(({ input: node }, index) => [["type", "unit", "range", "source"][index], text(node.value).trim()])); const empty = controls.find(({ input: node }) => !text(node.value).trim()); if (empty) return required(empty.input, "参数信息"); workspace.onOperation?.([parameterOperation(chapter.id, key, values)]); }); card.append(wrap); }); group.append(card);
  }); panel.append(group);
}
function renderIssues(panel, workspace, chapter) {
  const open = expanded(workspace.state || {}, chapter.id, "issues");
  const summary = el("section", "", { class: "gameplay-group" });
  const approved = Boolean(chapter.confirmation?.confirmed && chapter.status === "approved");
  const unknownCount = (chapter.decisionCards || []).filter((card) => card.status === "pending" || card.status === "skipped").length;
  summary.append(el("h3", approved ? "本章审核结果" : "需要你确认的问题"), el("p", approved
    ? unknownCount ? `本章已通过；仍有 ${unknownCount} 项尚未选择，不会写成已确认结论。` : "本章已通过，没有遗留的策划决策。"
    : `影响其他玩法 ${(chapter.dependencies || []).length} 项 · 检查方法 ${(chapter.acceptanceCases || []).length} 项 · 策划决策 ${unknownCount} 项`));
  if (!open) summary.append(button("查看并补充", () => workspace.onToggleGroup?.(chapter.id, "issues"), "btn")); panel.append(summary); if (!open) return;
  const dependencies = el("section", "", { class: "gameplay-group gameplay-dependency-editor" }); dependencies.append(el("h3", "这项规则还会影响哪些内容？"));
  const dep = field("选择会受到影响的内容", "", "select"); (workspace.model.chapters || []).filter((item) => item.id !== chapter.id).forEach((item) => dep.input.append(el("option", item.scope, { value: item.id })));
  dependencies.append(dep.wrap, button("添加受到影响的内容", () => { const value = required(dep.input, "受到影响的内容"); if (value) workspace.onOperation?.([{ type: "upsert_dependency", chapterId: chapter.id, dependencyId: value }]); }, "btn"));
  (chapter.dependencies || []).forEach((id) => dependencies.append(button(`移除 ${id}`, () => workspace.onOperation?.([{ type: "delete_dependency", chapterId: chapter.id, dependencyId: id }]), "btn"))); panel.append(dependencies);
  const acceptance = el("section", "", { class: "gameplay-group gameplay-acceptance-editor" }); acceptance.append(el("h3", "怎么判断这部分做对了？"), el("p", "写清楚进行什么操作，以及正确情况下应该看到什么结果。"));
  (chapter.acceptanceCases || []).forEach((item, index) => {
    const situationValue = item.case || item.scene || item.action || item.when || item.title || item.text || "";
    const expectedValue = item.expected || item.result || "";
    const situation = field("操作或情况", situationValue, "textarea");
    const expected = field("应该看到的结果", expectedValue, "textarea");
    const save = () => { const caseText = required(situation.input, "操作或情况"); const expectedText = required(expected.input, "应该看到的结果"); if (caseText && expectedText) workspace.onOperation?.([{ type: "upsert_acceptance", chapterId: chapter.id, acceptanceIndex: item.id ? undefined : index, acceptance: { ...item, case: caseText, expected: expectedText } }]); };
    situation.input.addEventListener("blur", save); expected.input.addEventListener("blur", save);
    acceptance.append(situation.wrap, expected.wrap, button("删除这条检查方法", () => workspace.onOperation?.([{ type: "delete_acceptance", chapterId: chapter.id, acceptanceId: item.id, acceptanceIndex: item.id ? undefined : index }]), "btn"));
  });
  const addSituation = field("新增操作或情况", "", "textarea"); const addExpected = field("新增后应该看到的结果", "", "textarea");
  acceptance.append(addSituation.wrap, addExpected.wrap, button("添加检查方法", () => { const caseText = required(addSituation.input, "操作或情况"); const expectedText = required(addExpected.input, "应该看到的结果"); if (caseText && expectedText) workspace.onOperation?.([{ type: "upsert_acceptance", chapterId: chapter.id, acceptance: { case: caseText, expected: expectedText } }]); }, "btn")); panel.append(acceptance);
}
function renderEditor(root, workspace, chapter) {
  const editor = el("main", "", { class: "gameplay-chapter-editor gameplay-rules-column" }); renderTabs(editor, workspace); if (!chapter) { editor.append(el("p", "暂无玩法章节")); root.append(editor); return editor; }
  const chapters = workspace.model.chapters || [];
  const chapterIndex = Math.max(0, chapters.findIndex((item) => item.id === chapter.id));
  const ruleHead = el("header", "", { class: "gameplay-rule-head" });
  const crumb = el("div", "", { class: "gameplay-rule-crumb" });
  crumb.append(el("span", "规则审核 /", { class: "gameplay-rule-parent" }), el("strong", chapter.scope), el("span", `${chapterIndex + 1} / ${chapters.length}`, { class: "gameplay-rule-position" }));
  const headActions = el("div", "", { class: "gameplay-rule-head-actions" });
  headActions.append(button("编辑规则", () => workspace.onEditRules?.(chapter.id), "btn"), button("确认通过", () => workspace.onDecision ? workspace.onDecision(chapter.id, "approved") : workspace.onConfirm?.(chapter.id, "approved"), "btn gameplay-rule-head-confirm"));
  ruleHead.append(crumb, headActions); editor.append(ruleHead);
  const content = el("div", "", { "data-gameplay-panel": "content" }); const summary = el("section", "", { class: "gameplay-summary" }); const plannerSections = chapter.plannerSections || {};
  summary.append(
    el("span", "一句话玩法 正常怎么玩 关键规则 特殊情况", { hidden: "" }),
    el("h3", chapter.scope)
  );
  renderRuleAuditSections(summary, chapter);
  renderReviewFocus(summary, workspace, chapter);
  renderDecisionCards(summary, workspace, chapter);
  renderPlanningDocument(summary, chapter);
  const anchor = (workspace.model.evidenceAnchors || []).find((item) => chapter.sourceFrameIds?.includes(item.frameId)); if (anchor && !(chapter.inlineEvidence || []).length) { const evidenceButton = button("查看参考画面", (event) => workspace.onOpenEvidence?.(anchor.id, event.currentTarget), "btn"); evidenceButton.setAttribute("data-evidence-anchor", anchor.id); summary.append(evidenceButton); } content.append(summary);
  const rules = el("details", "", { class: "gameplay-rule-details" }); keepDetailsState(rules, workspace, chapter.id, "rules"); rules.append(el("summary", rules.open ? "收起详细规则" : "展开详细规则"));
  renderClaimEditor(rules, workspace, chapter, claimNeedsReview(chapter, workspace.state || {}));
  const contextFields = contextFieldsFor(chapter); if (anchor && contextFields.length) { const contextButton = button("查看前后视频", (event) => workspace.onContext?.(chapter.id, anchor.frameId, contextFields, event.currentTarget), "btn gameplay-context-button"); contextButton.setAttribute("data-context-chapter", chapter.id); content.append(contextButton); }
  const parameters = el("div", "", { "data-gameplay-panel": "parameters" });
  const parameterDetails = el("details", "", { class: "gameplay-parameter-details" }); keepDetailsState(parameterDetails, workspace, chapter.id, "parameters");
  const parameterFields = configuredParameterFields(chapter);
  const missingParameters = parameterFields.filter(({ key }) => !parameterComplete(chapter.parameters?.[key])).length;
  parameterDetails.append(el("summary", missingParameters ? `需要填写的数值和条件（还有 ${missingParameters} 项）` : parameterFields.length ? "查看已确认的数值和条件" : "当前没有单独数值需要填写"));
  if (parameterFields.length) renderParameters(parameterDetails, workspace, chapter);
  parameters.append(parameterDetails);
  const issues = el("div", "", { "data-gameplay-panel": "issues" }); renderIssues(issues, workspace, chapter);
  if (workspace.state?.draftDecision === "needs_edit") renderSummaryEditor(content, workspace, chapter);
  const findings = workspace.model.reviewState?.findings || [];
  const openedGroups = workspace.state?.expandedGroups || [];
  const editedGroups = workspace.state?.editedGroups || [];
  const userOpenedSupplemental = ["supplemental", "rules", "parameters", "issues"].some((group) => openedGroups.includes(`${chapter.id}:${group}`)) || editedGroups.includes(`${chapter.id}:claims`);
  if (workspace.state?.draftDecision === "needs_edit" || hasSupplementalDetails(chapter, findings) || userOpenedSupplemental) {
    const supplemental = el("details", "", { class: "gameplay-supplemental-details" });
    keepDetailsState(supplemental, workspace, chapter.id, "supplemental");
    supplemental.append(el("summary", "补充细节"));
    if ((chapter.claims || []).length || workspace.state?.draftDecision === "needs_edit" || openedGroups.includes(`${chapter.id}:rules`) || editedGroups.includes(`${chapter.id}:claims`)) supplemental.append(rules);
    if (parameterFields.length || openedGroups.includes(`${chapter.id}:parameters`)) supplemental.append(parameterDetails);
    if ((chapter.dependencies || []).length || (chapter.acceptanceCases || []).length || (chapter.decisionCards || []).some((card) => card.status !== "resolved") || findings.some((item) => item.chapterId === chapter.id && item.status !== "resolved") || workspace.state?.draftDecision === "needs_edit" || openedGroups.includes(`${chapter.id}:issues`)) supplemental.append(issues);
    content.append(supplemental);
  }
  const decision = el("section", "", { class: "gameplay-decision gameplay-rule-footer" });
  const confirmedCount = chapters.filter((item) => item.confirmation?.confirmed && item.status === "approved").length;
  const pendingDecisions = (chapter.decisionCards || []).filter((card) => card.status === "pending" || card.status === "skipped").length;
  const gateText = pendingDecisions
    ? `门禁：本章还需处理 ${pendingDecisions} 项策划决策。全部 ${chapters.length} 章通过后自动进入图解审核。`
    : `门禁：确认本章规则、素材依据和必要数值。当前已通过 ${confirmedCount}/${chapters.length} 章；全部通过后自动进入图解审核。`;
  const gate = el("p", gateText, { class: "gameplay-review-gate", id: "gameplay-review-gate" });
  decision.append(gate);
  if (workspace.state?.confirmationStatus === "saving") decision.append(el("p", "正在保存审核结论…", { role: "status", "aria-live": "polite" }));
  else if (workspace.state?.confirmationMessage) decision.append(el("p", workspace.state.confirmationMessage, { role: "status", "aria-live": "polite" }));
  const footerNav = el("div", "", { class: "gameplay-rule-footer-nav" });
  [["上一节", chapterIndex - 1], ["下一节", chapterIndex + 1]].forEach(([label, index]) => { const control = button(label, () => chapters[index] && workspace.onSelectChapter?.(chapters[index].id), "btn"); control.disabled = !chapters[index]; footerNav.append(control); });
  const footerActions = el("div", "", { class: "gameplay-rule-footer-actions" });
  const back = button("返回修改", () => workspace.onDecision ? workspace.onDecision(chapter.id, "needs_edit") : workspace.onConfirm?.(chapter.id, "needs_edit"), "btn gameplay-decision-option"); back.setAttribute("data-gameplay-decision", "needs_edit");
  const save = button("保存修改", () => workspace.onSave?.(), "btn gameplay-rule-save");
  const approve = button("确认本节通过", () => workspace.onDecision ? workspace.onDecision(chapter.id, "approved") : workspace.onConfirm?.(chapter.id, "approved"), "btn primary gameplay-decision-option gameplay-rule-confirm"); approve.setAttribute("data-gameplay-decision", "approved"); approve.setAttribute("aria-describedby", "gameplay-review-gate");
  [back, save, approve].forEach((control) => { control.disabled = workspace.state?.confirmationStatus === "saving"; footerActions.append(control); });
  decision.append(footerNav, footerActions); content.append(decision);
  editor.append(content); root.append(editor); return editor;
}
const V2_RULE_LABELS = { logic: "逻辑规则", presentation: "表现规则", numeric: "数值规则", flow: "流程规则", interaction: "交互规则", config: "配置规则" };
const V2_SLOT_LABELS = {
  movement_trigger: "移动触发", movement_direction: "移动方向", movement_speed_source: "移动速度", movement_path: "移动路径", movement_stop_condition: "停止条件", movement_presentation: "移动表现",
  attack_trigger: "攻击触发", attack_target: "攻击目标", attack_range: "攻击范围", attack_frequency: "攻击频率", attack_method: "攻击方式", attack_exit_condition: "退出条件", attack_presentation: "攻击表现",
  random_trigger: "随机触发", candidate_pool_source: "候选池来源", pool_entry_condition: "入池条件", weight_rule: "权重", empty_result_rule: "空结果处理", refresh_rule: "刷新规则", confirm_effect_timing: "确认与生效",
  settlement_trigger: "结算触发", result_determination: "结果判定", reward_rule: "奖励", persistence_timing: "数据写入", exit_path: "离开路径", settlement_presentation: "结算表现",
  damage_death_definition: "受击及死亡", content_catalog_definition: "内容定义", presentation_definition: "表现定义", spawn_definition: "刷新规则", level_flow_definition: "关卡流程",
};
function renderV2(root, workspace) {
  const approved = workspace.model.approvedData || {};
  const temporalCandidates = workspace.model.ruleIntelligenceProjection?.ruleCandidates || [];
  const temporalFacts = new Map((workspace.model.temporalEvidence?.facts || []).map((fact) => [fact.factId, fact]));
  const chapters = approved.chapters || [];
  const selected = chapters.find((item) => item.chapterId === workspace.state?.selectedChapterId) || chapters[0];
  const shell = el("div", "", { class: "gameplay-review gameplay-rule-audit gameplay-rule-audit-v2" });
  shell.append(el("header", "", { class: "gameplay-studio-header" }));
  shell.children[0].append(el("strong", "结构化规则审核"), el("span", selected ? `${selected.system} / ${selected.object} / ${selected.title}` : "暂无规则"));
  const rail = el("nav", "", { class: "gameplay-directory-rail", "aria-label": "规则章节" });
  chapters.forEach((chapter) => rail.append(button(chapter.object === chapter.title ? chapter.title : `${chapter.object} · ${chapter.title}`, () => workspace.onSelectChapter?.(chapter.chapterId), chapter.chapterId === selected?.chapterId ? "btn active" : "btn")));
  shell.append(rail);
  const panel = el("main", "", { class: "gameplay-chapter-editor gameplay-rules-column" });
  if (!selected) panel.append(el("p", "暂无可审核规则"));
  const ruleById = new Map([...(approved.rules || []), ...temporalCandidates].map((rule) => [rule.ruleId, rule]));
  const rules = [...ruleById.values()].filter((rule) => rule.ownerChapterId === selected?.chapterId);
  if (selected && !rules.length) panel.append(el("p", "当前章节没有可审核的证据规则。", { class: "gameplay-empty-state" }));
  const grouped = new Map();
  rules.forEach((rule) => { const list = grouped.get(rule.schemaSlot) || []; list.push(rule); grouped.set(rule.schemaSlot, list); });
  grouped.forEach((items, slot) => {
    const group = el("section", "", { class: "gameplay-group gameplay-v2-rule-group", "data-schema-slot": slot });
    group.append(el("h3", V2_SLOT_LABELS[slot] || `${selected.title}规则`));
    items.forEach((rule) => {
      const card = el("article", "", { class: `gameplay-v2-rule rule-${rule.ruleType}`, "data-rule-id": rule.ruleId });
      card.append(el("span", V2_RULE_LABELS[rule.ruleType] || rule.ruleType, { class: "gameplay-rule-type" }), el("p", rule.behavior));
      if (rule.candidateKind === "temporal_rule_candidate") {
        card.append(el("p", "视频观察 · 待确认", { class: "gameplay-rule-warning" }));
        const timestamps = [...new Set((rule.sourceFactIds || []).flatMap((factId) => temporalFacts.get(factId)?.evidenceTimestamps || []))];
        if (timestamps.length) card.append(el("p", `视频证据时间：${timestamps.map((value) => `${value}s`).join("、")}`, { class: "gameplay-rule-temporal-evidence" }));
      }
      const semanticallyValid = rule.semanticValidity !== "invalid" && !(rule.validationErrors || []).length;
      if (!semanticallyValid) card.append(el("p", "该规则语义不完整，需要修正后才能通过。", { class: "gameplay-rule-warning" }));
      const evidenceCount = (rule.evidenceIds || []).length;
      card.append(button(evidenceCount ? `查看素材依据（${evidenceCount} 处）` : "暂无素材依据", () => evidenceCount && workspace.onOpenEvidence?.(rule.evidenceIds[0]), "btn gameplay-rule-evidence"));
      const approve = button("通过", () => workspace.onRuleReview?.(rule.ruleId, "approved"), "btn"); approve.disabled = !semanticallyValid;
      card.append(approve, button("退回修改", () => workspace.onRuleReview?.(rule.ruleId, "needs_revision"), "btn"));
      group.append(card);
    });
    panel.append(group);
  });
  shell.append(panel); root.append(shell); root.__gameplayChapterId = selected?.chapterId; return shell;
}
function renderFindings(root, workspace, target = root) { const panel = el("aside", "", { class: "gameplay-findings-panel", "data-gameplay-panel": "issues" }); panel.append(el("h3", "确认前需要补全")); const findings = workspace.model.reviewState?.findings || []; const missingParameters = (workspace.model.chapters || []).reduce((total, chapter) => total + configuredParameterFields(chapter).filter(({ key }) => !parameterComplete(chapter.parameters?.[key])).length, 0); if (!findings.length && !missingParameters) { root.setAttribute("class", `${root.getAttribute("class") || ""} no-findings`.trim()); return; } if (missingParameters) panel.append(el("p", `还有 ${missingParameters} 项数值和条件需要填写。`)); findings.forEach((item) => panel.append(el("p", item.message || item.title || "这里还需要补充一项内容"))); target.append(panel); }
function renderDrawer(root, workspace) {
  const anchor = (workspace.model.evidenceAnchors || []).find((item) => item.id === workspace.state?.evidenceDrawer); if (!anchor) return;
  const overlay = el("div", "", { class: "gameplay-evidence-drawer", role: "presentation" }); const dialog = el("section", "", { class: "gameplay-evidence-dialog", role: "dialog", "aria-modal": "true", "aria-label": "参考画面", tabindex: "-1" });
  const close = () => { workspace.state?.evidenceOpener?.focus?.(); workspace.onOpenEvidence?.(null); }; const closeButton = button("关闭参考画面", close, "btn"); dialog.append(closeButton, el("h3", "参考画面"), el("p", "这张截图用于核对当前规则。"));
  if (anchor.imageUrl) dialog.append(el("img", "", { src: workspace.resolveEvidenceUrl?.(anchor.imageUrl) || anchor.imageUrl, alt: `${anchor.frameId} 截图证据` }));
  if (anchor.source) dialog.append(el("p", [anchor.source.name, anchor.source.timestamp == null ? "" : `${anchor.source.timestamp}s`, anchor.source.sequenceIndex == null ? "" : `#${anchor.source.sequenceIndex}`].filter(Boolean).join(" · ")));
  overlay.append(dialog); overlay.addEventListener("keydown", (event) => { if (event.key === "Escape") { event.preventDefault(); close(); } if (event.key === "Tab") { event.preventDefault(); closeButton.focus(); } }); root.append(overlay);
}
function focusableNodes(root) {
  return ["input", "textarea", "select", "button"].flatMap((tag) => root.querySelectorAll(tag));
}
function captureRenderPosition(root, chapterId) {
  if (!root || root.__gameplayChapterId !== chapterId) return { scrollTop: 0, focusIndex: -1 };
  const nodes = focusableNodes(root); const active = typeof document !== "undefined" ? document.activeElement : null;
  return { scrollTop: root.querySelector(".gameplay-chapter-editor")?.scrollTop || 0, focusIndex: nodes.indexOf(active) };
}
function restoreRenderPosition(root, snapshot, chapterId) {
  const editor = root.querySelector(".gameplay-chapter-editor"); if (editor) editor.scrollTop = snapshot.scrollTop;
  if (snapshot.focusIndex >= 0) focusableNodes(root)[snapshot.focusIndex]?.focus?.();
  root.__gameplayChapterId = chapterId;
}
function render(workspace) {
  const { root, model, state = {} } = workspace;
  if (model.contentModelVersion === 2 && model.approvedData) { root.textContent = ""; return renderV2(root, workspace); }
  const chapter = (model.chapters || []).find((item) => item.id === state.selectedChapterId) || model.chapters?.[0];
  const renderPosition = captureRenderPosition(root, chapter?.id); root.textContent = ""; const shell = el("div", "", { class: "gameplay-review gameplay-rule-audit", "data-active-tab": state.activeTab || "content" });
  const system = systemsForDisplay(model).find((item) => (item.subsystems || []).some((sub) => (sub.chapterIds || []).includes(chapter?.id)));
  const subsystem = system?.subsystems?.find((item) => (item.chapterIds || []).includes(chapter?.id));
  const header = el("header", "", { class: "gameplay-studio-header" });
  const title = el("div", "", { class: "gameplay-studio-title" }); title.append(el("strong", "玩法拆解"), el("span", ["当前素材", system?.name, subsystem?.name !== "玩法机制" ? subsystem?.name : "", chapter?.scope].filter(Boolean).join(" / ")));
  const actions = el("div", "", { class: "gameplay-studio-actions" });
  actions.append(button("调整目录", () => workspace.onAdjustDirectory?.(), "btn"));
  header.append(title, actions); shell.append(header);
  const notices = el("div", "", { class: "gameplay-studio-notices" }); notices.append(el("p", saveStatusLabel(state.saveStatus), { class: "gameplay-save-status", role: "status", "aria-live": "polite" }), el("p", contextStatusLabel(state.contextStatus), { class: "gameplay-context-status", role: "status", "aria-live": "polite" })); shell.append(notices);
  renderRail(shell, workspace, chapter); renderEvidenceColumn(shell, workspace, chapter); const editor = renderEditor(shell, workspace, chapter); renderFindings(shell, workspace, editor); renderDrawer(shell, workspace); root.append(shell); if (state.evidenceDrawer) shell.querySelector(".gameplay-evidence-dialog button")?.focus?.(); else restoreRenderPosition(root, renderPosition, chapter?.id);
}

return { render, viewModel, statusLabel, saveStatusLabel, contextStatusLabel, contextFieldsFor, configuredParameterFields, reviewFocus, mobileTabs, decisionOptions, decisionAction, hasSupplementalDetails, nextPending, parameterOperation, chapterOperation };
});
