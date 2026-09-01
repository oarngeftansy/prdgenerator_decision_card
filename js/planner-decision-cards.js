(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PlannerDecisionCards = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  function node(doc, tag, text = "", className = "") {
    const item = doc.createElement(tag); item.textContent = text; if (className) item.className = className; return item;
  }
  function actionable(cards) {
    return (cards || []).filter((card) => card && ["pending", "skipped"].includes(card.status || "pending") && (card.options || []).length >= 2);
  }
  function resolveOperation(value) {
    return { type: "resolve_decision_card", chapterId: value.chapterId, cardId: value.cardId, selectedOptionIds: value.selectedOptionIds, customValue: value.customValue || "" };
  }
  function skipOperation(value) { return { type: "skip_decision_card", chapterId: value.chapterId, cardId: value.cardId }; }
  function render({ root, cards, context = {}, onResolve = () => {}, onSkip = () => {}, document: doc = globalThis.document }) {
    const items = actionable(cards); if (!items.length) return null;
    const section = node(doc, "section", "", "planner-decision-cards");
    section.append(node(doc, "h4", "需要策划决定"), node(doc, "p", "只有素材无法唯一判断的问题才会出现在这里；选择前不会写入正式结论。"));
    items.forEach((card) => {
      const article = node(doc, "article", "", "planner-decision-card");
      article.setAttribute?.("data-decision-card-id", card.id || "");
      article.setAttribute?.("data-decision-chapter-id", context.chapterId || "");
      article.setAttribute?.("tabindex", "-1");
      article.append(node(doc, "h5", card.question || "请选择处理方式"));
      const recommended = (card.options || []).find((option) => option.recommended);
      if (recommended) article.append(node(doc, "p", `AI 推荐：${recommended.label}${recommended.reason ? `。${recommended.reason}` : ""}`, "planner-decision-recommendation"));
      const controls = [];
      const choices = node(doc, "div", "", "planner-decision-options");
      (card.options || []).forEach((option) => {
        const label = node(doc, "label", "", "planner-decision-option"); const input = node(doc, "input");
        input.type = card.selectionMode === "multiple" ? "checkbox" : "radio"; input.name = `decision-${card.id}`; input.value = option.id; input.checked = false;
        input.setAttribute?.("type", input.type); input.setAttribute?.("name", input.name); input.setAttribute?.("value", input.value);
        if (input.type === "radio") input.onclick = () => {
          controls.forEach((other) => { if (other !== input) other.checked = false; });
          custom.value = "";
          error.textContent = "";
        };
        controls.push(input); label.append(input, node(doc, "span", option.label)); choices.append(label);
      });
      article.append(choices);
      const customLabel = node(doc, "label", "", "planner-decision-custom"); customLabel.append(node(doc, "span", "自己填写")); const custom = node(doc, "input"); custom.value = "";
      custom.oninput = () => {
        if (card.selectionMode !== "multiple" && String(custom.value || "").trim()) controls.forEach((input) => { input.checked = false; });
        error.textContent = "";
      };
      customLabel.append(custom); customLabel.hidden = card.allowCustom === false; article.append(customLabel);
      if ((card.evidence || []).length) article.append(node(doc, "p", `判断依据：${card.evidence.map((item) => item.label || item.frameId || item.reference).filter(Boolean).join("、")}`, "planner-decision-evidence"));
      if ((card.impacts || []).length) article.append(node(doc, "p", `保存后会更新：${card.impacts.join("、")}`, "planner-decision-impacts"));
      article.append(node(doc, "p", card.selectionMode === "multiple" ? "可以多选，也可以自己填写。" : "只能选择一项，也可以自己填写。", "planner-decision-limit"));
      const error = node(doc, "p", "", "planner-decision-error");
      const actions = node(doc, "div", "", "planner-decision-actions");
      const bindClick = (element, handler) => { if (typeof element.addEventListener === "function") element.addEventListener("click", handler); else element.onclick = handler; };
      const skip = node(doc, "button", "暂时跳过", "btn planner-decision-skip"); skip.type = "button"; bindClick(skip, () => onSkip({ ...context, cardId: card.id }));
      const apply = node(doc, "button", "应用选择", "btn primary planner-decision-apply"); apply.type = "button"; bindClick(apply, () => {
        const selectedOptionIds = controls.filter((input) => input.checked).map((input) => input.value); const customValue = String(custom.value || "").trim();
        if (!selectedOptionIds.length && !customValue) { error.textContent = "请选择一个选项或自己填写"; return; }
        if (card.selectionMode !== "multiple" && selectedOptionIds.length + Boolean(customValue) !== 1) { error.textContent = "这道题只能选择一项"; return; }
        error.textContent = ""; onResolve({ ...context, cardId: card.id, selectedOptionIds, customValue });
      });
      actions.append(skip, apply); article.append(error, actions); section.append(article);
    });
    root.append(section); return section;
  }
  return { actionable, render, resolveOperation, skipOperation };
});
