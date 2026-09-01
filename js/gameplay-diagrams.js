(function (global) {
  const DecisionCards = typeof module !== "undefined" && module.exports ? require("./planner-decision-cards.js") : global.PlannerDecisionCards;
  const TYPE_LABELS = { spatial: "空间关系", state_flow: "状态流程", probability: "概率与抽取", effect_chain: "效果关系", formula: "计算公式" };
  const STATUS_LABELS = { open: "待审核", stale: "内容已更新，需要重修", revising: "正在重修", reviewed: "已通过" };
  function node(doc, tag, className, text) { const item = doc.createElement(tag); if (className) item.setAttribute("class", className); if (text !== undefined) item.textContent = text; return item; }
  function actionButton(doc, className, text, handler, disabled = false) { const button = node(doc, "button", className, text); button.setAttribute("type", "button"); button.disabled = disabled; button.addEventListener("click", handler); return button; }
  function diagramHasVisualStructure(diagram = {}) {
    if (diagram.type === "formula") return false;
    const svg = String(diagram.svg || "");
    const hasText = /<text\b/i.test(svg);
    const hasVisualMark = /<(?:path|line|polyline|polygon|circle|ellipse|image)\b/i.test(svg);
    // Older persisted diagrams may not retain their SVG payload. Keep those reviewable;
    // only suppress artifacts that are explicitly formula/text-only.
    return !hasText || hasVisualMark;
  }
  function effectiveStatus(diagram = {}, model = {}) {
    if (diagram.status === "reviewed" && Number.isInteger(model.interactionRevision)
      && diagram.interactionRevision !== model.interactionRevision) return "reconfirm";
    return diagram.status || "open";
  }
  function render({ root, model, state = { generation: {}, byId: {} }, onAction = () => {}, onGenerate = () => {}, onContinue = () => {}, onOperation = () => {}, onSelectChapter = () => {}, document: doc = global.document }) {
    const section = node(doc, "section", "gameplay-diagrams");
    const contextBar = node(doc, "header", "review-context-bar"); contextBar.append(node(doc, "strong", "玩法图解"), node(doc, "span", "当前素材 / 玩法结构图 / 逐图审核")); section.append(contextBar);
    const layout = node(doc, "div", "gameplay-diagrams-layout");
    const navigation = node(doc, "nav", "gameplay-diagram-nav");
    const navHead = node(doc, "div", "gameplay-diagram-nav-head");
    const navCount = node(doc, "span", "gameplay-diagram-count", "0");
    navHead.append(node(doc, "h3", "gameplay-diagram-nav-title", "关联章节"), navCount);
    navigation.append(navHead);
    const diagrams = (model.diagrams || []).filter((diagram) => diagram.status !== "deleted" && diagramHasVisualStructure(diagram));
    if (!diagrams.length) section.setAttribute("class", "gameplay-diagrams has-no-artifacts");
    const diagramChapterIds = new Set(diagrams.flatMap((diagram) => diagram.chapterIds || []));
    const chapterButtons = [];
    (model.chapters || []).filter((chapter) => diagramChapterIds.has(chapter.id)).forEach((chapter) => {
      const item = node(doc, "button", "gameplay-diagram-nav-item", chapter.scope || "待命名章节");
      item.setAttribute("type", "button");
      item.setAttribute("data-chapter-id", chapter.id || "");
      const chapterDiagrams = diagrams.filter((diagram) => (diagram.chapterIds || []).includes(chapter.id));
      const statuses = chapterDiagrams.map((diagram) => effectiveStatus(diagram, model));
      const chapterStatus = statuses.includes("stale") ? "stale" : statuses.every((status) => status === "reviewed") ? "reviewed" : "open";
      item.setAttribute("data-status", chapterStatus);
      item.setAttribute("data-status-label", { open: "待审核", stale: "需更新", reviewed: "已通过" }[chapterStatus]);
      chapterButtons.push({ chapter, item });
      navigation.append(item);
    });
    navCount.textContent = String(chapterButtons.length);
    const canvas = node(doc, "div", "gameplay-diagram-canvas");
    const decision = node(doc, "aside", "gameplay-diagram-decision");
    decision.append(node(doc, "h3", "", "图解审核"), node(doc, "p", "gameplay-diagram-decision-hint", "选择左侧图解后，在这里核对关联玩法、图解类型和修改意见。"));
    layout.append(navigation, canvas, decision); section.append(layout);
    const header = node(doc, "div", "gameplay-diagrams-header");
    const workbar = node(doc, "div", "gameplay-diagram-workbar");
    workbar.append(node(doc, "strong", "gameplay-diagram-workbar-title", `图解审核 / ${chapterButtons[0]?.chapter.scope || "玩法图解"}`));
    const staleCount = diagrams.filter((item) => effectiveStatus(item, model) === "stale").length;
    const reconfirmCount = diagrams.filter((item) => effectiveStatus(item, model) === "reconfirm").length;
    const reviewedCount = diagrams.filter((item) => effectiveStatus(item, model) === "reviewed").length;
    const openCount = diagrams.length - reviewedCount - staleCount - reconfirmCount;
    const summary = node(doc, "p", "gameplay-diagram-summary", `已生成 ${diagrams.length} 张图解　${reviewedCount} 已通过　${openCount} 待审核${reconfirmCount ? `　${reconfirmCount} 张需重新确认` : ""}${staleCount ? `　${staleCount} 张需按最新正文更新` : ""}`);
    header.append(workbar, summary);
    if (staleCount) {
      const staleNotice = node(doc, "div", "gameplay-diagram-stale-notice");
      staleNotice.append(
        node(doc, "p", "", "关联玩法正文已经修改。请先更新这些图，再逐张确认；更新不会自动把图判为通过。"),
        actionButton(doc, "gameplay-diagram-refresh-stale btn primary", `按最新正文更新 ${staleCount} 张图`, () => onGenerate(), state.generation?.status === "pending")
      );
      header.append(staleNotice);
    }
    const reviewStatus = model.diagramReview?.status;
    const unresolvedCount = openCount + staleCount + reconfirmCount;
    const diagramGateReady = diagrams.length ? unresolvedCount === 0 : reviewStatus === "ready";
    const gateCopy = state.generation?.status === "pending"
      ? "门禁：正在生成或更新图解，完成后逐张确认。"
      : staleCount
        ? `门禁：先按最新正文更新 ${staleCount} 张图，再逐张确认；全部通过后进入参数审核。`
        : unresolvedCount
          ? `门禁：还需确认 ${unresolvedCount} 张图；全部通过后进入参数审核。`
          : diagrams.length
            ? "全部图解已通过，可以进入参数审核。"
            : reviewStatus === "ready"
              ? "当前玩法无需额外图解，确认后进入参数审核。"
              : "门禁：等待必要图解生成完成，再逐张确认。";
    if (diagrams.length) {
      const gate = node(doc, "section", "gameplay-diagram-review-gate");
      gate.id = "gameplay-diagram-review-gate";
      gate.append(
        node(doc, "p", "gameplay-diagram-review-gate-copy", gateCopy),
        actionButton(doc, "gameplay-diagram-continue btn primary", "进入参数审核", onContinue, !diagramGateReady || state.generation?.status === "pending")
      );
      gate.querySelector?.(".gameplay-diagram-continue")?.setAttribute("aria-describedby", gate.id);
      header.append(gate);
    }
    const generationStatus = node(doc, "p", "gameplay-diagram-generation-status", state.generation?.message || (reviewStatus === "generating" ? "正在自动生成图解…" : ""));
    generationStatus.setAttribute("role", "status"); generationStatus.setAttribute("aria-live", "polite"); header.append(generationStatus);
    if (state.generation?.status === "error") header.append(actionButton(doc, "gameplay-diagram-retry", "重新生成图解", () => onGenerate()));
    canvas.append(header);
    (model.chapters || []).forEach((chapter) => DecisionCards?.render?.({
      root: canvas, cards: chapter.decisionCards || [], context: { chapterId: chapter.id }, document: doc,
      onResolve: (value) => onOperation([DecisionCards.resolveOperation(value)]),
      onSkip: (value) => onOperation([DecisionCards.skipOperation(value)]),
    }));
    const viewStatus = node(doc, "p", "gameplay-diagram-view-status", state.announcement?.message || "");
    viewStatus.setAttribute("role", "status"); viewStatus.setAttribute("aria-live", "polite"); canvas.append(viewStatus);
    const empty = node(doc, "section", "gameplay-diagram-empty");
    empty.append(
      node(doc, "h3", "gameplay-diagram-empty-title", "必要图解审核"),
      node(doc, "p", "gameplay-diagram-empty-purpose", "这里只保留确有助于理解玩法关系的结构图；纯文字、公式和重复信息直接使用正文表达。"),
      node(doc, "strong", "gameplay-diagram-empty-status", "当前素材无需额外图解")
    );
    if (reviewStatus === "ready" && state.generation?.status !== "error") {
      const emptyGate = node(doc, "section", "gameplay-diagram-review-gate");
      emptyGate.id = "gameplay-diagram-empty-gate";
      emptyGate.append(
        node(doc, "p", "gameplay-diagram-review-gate-copy", "当前素材无需额外图解；确认后进入参数审核。"),
        actionButton(doc, "gameplay-diagram-empty-confirm gameplay-diagram-continue btn primary", "确认无图解并进入参数审核", onContinue)
      );
      emptyGate.querySelector?.(".gameplay-diagram-empty-confirm")?.setAttribute("aria-describedby", emptyGate.id);
      empty.append(emptyGate);
      canvas.append(empty);
    }
    else empty.hidden = true;
    const diagramCards = [];
    diagrams.forEach((diagram) => {
      const displayStatus = effectiveStatus(diagram, model);
      const card = node(doc, "article", "gameplay-diagram-card"); card.setAttribute("data-status", displayStatus);
      card.setAttribute("data-diagram-id", diagram.id || "");
      const title = node(doc, "h4", "", TYPE_LABELS[diagram.type] || "玩法图解");
      const status = node(doc, "span", "gameplay-diagram-status", displayStatus === "reconfirm" ? "版本已更新，需要重新确认" : STATUS_LABELS[displayStatus] || "待审核"); status.setAttribute("aria-live", "polite");
      const chapterNames = (diagram.chapterIds || []).map((id) => (model.chapters || []).find((chapter) => chapter.id === id)?.scope).filter(Boolean);
      const meta = node(doc, "p", "gameplay-diagram-meta", `来源章节：${chapterNames.join("、") || "当前玩法章节"}`);
      const graphic = node(doc, "div", "gameplay-diagram-graphic"); graphic.setAttribute("role", "img"); graphic.setAttribute("aria-label", `${TYPE_LABELS[diagram.type] || "玩法"}图解`); graphic.innerHTML = diagram.svg || "";
      const label = node(doc, "label", "gameplay-diagram-feedback-label", "修改备注"); const feedback = node(doc, "textarea", "gameplay-diagram-feedback"); feedback.setAttribute("rows", "3"); feedback.setAttribute("placeholder", "只写这张图需要修改的地方"); label.append(feedback);
      const request = state.byId?.[diagram.id] || {}; const busy = diagram.status === "revising" || request.status === "pending";
      const choices = node(doc, "fieldset", "gameplay-diagram-review-choices"); choices.append(node(doc, "legend", "", "审核状态"));
      let selectedDecision = ["reviewed", "reconfirm"].includes(displayStatus) ? "approve" : diagram.status === "deleted" ? "delete" : "revise";
      let apply;
      [["通过", "approve"], ["需要修改", "revise"], ["删除", "delete"]].forEach(([choiceLabel, value]) => {
        const choice = node(doc, "label", "gameplay-diagram-review-choice"); const radio = node(doc, "input"); radio.setAttribute("type", "radio"); radio.setAttribute("name", `diagram-review-${diagram.id}`); radio.setAttribute("value", value); radio.checked = selectedDecision === value; radio.disabled = busy; radio.addEventListener("change", () => { selectedDecision = value; if (apply) apply.disabled = busy || diagram.status === "stale" && selectedDecision === "approve"; }); choice.append(radio, node(doc, "span", "gameplay-diagram-review-choice-label", choiceLabel)); choices.append(choice);
      });
      apply = actionButton(doc, "gameplay-diagram-apply", "应用审核结果", () => onAction(selectedDecision === "revise" ? "regenerate" : selectedDecision, diagram.id, selectedDecision === "revise" ? feedback.value.trim() : ""), busy || diagram.status === "stale" && selectedDecision === "approve");
      const operationStatus = node(doc, "p", "gameplay-diagram-operation-status", request.message || ""); operationStatus.setAttribute("role", "status"); operationStatus.setAttribute("aria-live", "polite");
      const detail = node(doc, "div", "gameplay-diagram-detail");
      detail.append(node(doc, "h4", "", "关联玩法"), node(doc, "p", "", chapterNames.join("、") || "当前玩法章节"), node(doc, "h4", "", "图解类型"), node(doc, "p", "", TYPE_LABELS[diagram.type] || "玩法图解"), choices, label, apply, operationStatus);
      card.append(title, status, meta, graphic); canvas.append(card);
      diagramCards.push({ card, detail, diagram, chapterIds: diagram.chapterIds || [] });
      card.addEventListener("click", () => decision.replaceChildren(node(doc, "h3", "", "图解审核"), detail));
      if (diagramCards.length === 1) decision.replaceChildren(node(doc, "h3", "", "图解审核"), detail);
    });
    const selectChapter = (chapterId) => {
      chapterButtons.forEach(({ chapter, item }) => {
        const active = chapter.id === chapterId;
        item.setAttribute("aria-current", active ? "true" : "false");
      });
      const selectedChapter = chapterButtons.find(({ chapter }) => chapter.id === chapterId)?.chapter;
      const workTitle = header.querySelector?.(".gameplay-diagram-workbar-title");
      if (workTitle) workTitle.textContent = `图解审核 / ${selectedChapter?.scope || "玩法图解"}`;
      let visibleCount = 0;
      diagramCards.forEach(({ card, chapterIds }) => {
        card.hidden = Boolean(chapterId) && !chapterIds.includes(chapterId);
        if (!card.hidden) visibleCount += 1;
      });
      const visibleDiagrams = diagramCards.filter(({ card }) => !card.hidden);
      const selectedDiagram = visibleDiagrams.find(({ diagram }) => diagram.status !== "reviewed") || visibleDiagrams[0];
      if (selectedDiagram) decision.replaceChildren(node(doc, "h3", "", "图解审核"), selectedDiagram.detail);
      empty.hidden = reviewStatus !== "ready" || state.generation?.status === "error" || visibleCount > 0;
    };
    chapterButtons.forEach(({ chapter, item }) => item.addEventListener("click", () => {
      selectChapter(chapter.id);
      onSelectChapter(chapter.id);
    }));
    const restoredChapterId = chapterButtons.some(({ chapter }) => chapter.id === state.selectedChapterId)
      ? state.selectedChapterId
      : chapterButtons[0]?.chapter.id || "";
    selectChapter(restoredChapterId);
    root.replaceChildren(section);
    if (!reviewStatus && !state.generation?.status) onGenerate();
    return section;
  }
  const api = { render, TYPE_LABELS, STATUS_LABELS, diagramHasVisualStructure, effectiveStatus };
  if (typeof module !== "undefined") module.exports = api; else global.GameplayDiagrams = api;
})(typeof window !== "undefined" ? window : globalThis);
