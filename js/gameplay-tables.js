(function (global) {
  const DecisionCards = typeof module !== "undefined" && module.exports ? require("./planner-decision-cards.js") : global.PlannerDecisionCards;
  function node(doc, tag, className, text) { const item = doc.createElement(tag); if (className) item.className = className; if (text !== undefined) item.textContent = text; return item; }
  function button(doc, className, text, handler, disabled) { const item = node(doc, "button", className, text); item.type = "button"; item.disabled = Boolean(disabled); item.addEventListener("click", handler); return item; }
  function reviewTable(item) {
    const approvedColumns = ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"];
    if (item.kind !== "chapter_parameters") return { columns: item.columns || [], rows: item.rows || [], details: item.rowDetails || [] };
    if ((item.columns || []).includes("策划含义")) {
      const rows = (item.rows || []).map((row) => {
        const type = row[3] && row[3] !== "—" ? `${row[2] || "数值"}（${row[3]}）` : (row[2] || "数值");
        return [row[0] || "参数", type, row[4] || "—", row[4] || "—", "待确认", "确认"];
      });
      const details = (item.rows || []).map((row) => ({ field: row[0], purpose: row[1], basis: row[5], source: row[5], formula: "" }));
      (item.rowReviews || []).forEach((review) => { if (rows[review.rowIndex]) { rows[review.rowIndex][3] = review.value; rows[review.rowIndex][4] = review.confirmed ? "已确认" : "待确认"; } });
      return { columns: approvedColumns, rows, details };
    }
    const rows = (item.rows || []).map((row) => [...row]);
    (item.rowReviews || []).forEach((review) => { if (rows[review.rowIndex]) { rows[review.rowIndex][3] = review.value; rows[review.rowIndex][4] = review.confirmed ? "已确认" : "待确认"; } });
    return { columns: approvedColumns, rows, details: item.rowDetails || [] };
  }
  function rowConfirmationComplete(item, display) {
    if (item.kind !== "chapter_parameters" && !(display.columns || []).includes("状态")) return true;
    return Boolean(display.rows.length) && display.rows.every((row) => row[4] === "已确认");
  }
  function render({ root, model, state = { generation: {}, byId: {} }, onGenerate = () => {}, onAction = () => {}, onSelect = () => {}, onSelectChapter = () => {}, onContinue = () => {}, onOperation = () => {}, document: doc = global.document }) {
    const section = node(doc, "section", "gameplay-tables");
    const contextBar = node(doc, "header", "review-context-bar"); contextBar.append(node(doc, "strong", "玩法表格"), node(doc, "span", "当前素材 / 参数、公式与配置 / 逐表审核")); section.append(contextBar);
    const layout = node(doc, "div", "gameplay-tables-layout");
    const navigation = node(doc, "nav", "gameplay-table-nav"); navigation.append(node(doc, "h3", "gameplay-table-nav-title", "参数目录"));
    const tables = (model.tables || []).filter((item) => item.status !== "deleted");
    const tableIsReviewed = (item) => item.status === "reviewed" && rowConfirmationComplete(item, reviewTable(item));
    const reviewedTableCount = tables.filter(tableIsReviewed).length;
    const allTablesReviewed = Boolean(tables.length) && reviewedTableCount === tables.length;
    if (!tables.length) section.setAttribute("class", "gameplay-tables has-no-artifacts");
    const tableChapterIds = new Set(tables.flatMap((item) => item.chapterIds || []));
    const chapterButtons = [];
    const listed = new Set();
    (model.systems || []).forEach((system) => {
      const ids = (system.subsystems || []).flatMap((subsystem) => subsystem.chapterIds || []).filter((id) => tableChapterIds.has(id));
      if (!ids.length) return;
      const group = node(doc, "section", "gameplay-table-nav-group"); group.append(node(doc, "h4", "", system.name || "玩法系统"));
      ids.forEach((id) => {
        const chapter = (model.chapters || []).find((candidate) => candidate.id === id); if (!chapter || listed.has(id)) return; listed.add(id);
        const item = button(doc, "gameplay-table-nav-item", chapter.scope || "待命名章节", () => {}); item.setAttribute("data-chapter-id", chapter.id || ""); chapterButtons.push({ chapter, item }); group.append(item);
      }); navigation.append(group);
    });
    (model.chapters || []).filter((chapter) => tableChapterIds.has(chapter.id) && !listed.has(chapter.id)).forEach((chapter) => {
      const item = button(doc, "gameplay-table-nav-item", chapter.scope || "待命名章节", () => {}); item.setAttribute("data-chapter-id", chapter.id || ""); chapterButtons.push({ chapter, item }); navigation.append(item);
    });
    const canvas = node(doc, "div", "gameplay-table-canvas");
    const decision = node(doc, "aside", "gameplay-table-decision"); decision.append(node(doc, "h3", "参数详情"), node(doc, "p", "点击表格中的参数，查看设计目的、生成依据、关联公式和配置来源。"));
    layout.append(navigation, canvas, decision); section.append(layout);
    const header = node(doc, "div", "gameplay-tables-header");
    header.append(node(doc, "p", "", "逐项核对 AI 建议值和修改值；确认后的参数将写入最终策划案。"));
    header.append(node(doc, "p", "gameplay-table-review-summary", `${reviewedTableCount}/${tables.length} 张表已通过`));
    const status = node(doc, "p", "gameplay-table-generation-status", state.generation?.message || ""); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); header.append(status);
    if (state.generation?.status === "error") header.append(button(doc, "gameplay-table-retry", "重新生成表格", () => onGenerate()));
    const continueButton = button(doc, "gameplay-table-continue", "进入文档预览", () => { if (allTablesReviewed) onContinue(); }, !allTablesReviewed);
    continueButton.setAttribute("aria-describedby", "gameplay-table-review-gate");
    header.append(continueButton);
    const gate = node(doc, "p", "gameplay-table-review-gate", allTablesReviewed
      ? "全部表格已通过，可以进入文档预览。"
      : `门禁：还需通过 ${Math.max(0, tables.length - reviewedTableCount)} 张表。请逐表核对数值、单位和范围；全部通过后进入文档预览。`);
    gate.id = "gameplay-table-review-gate";
    canvas.append(header, gate);
    (model.chapters || []).forEach((chapter) => DecisionCards?.render?.({
      root: canvas, cards: chapter.decisionCards || [], context: { chapterId: chapter.id }, document: doc,
      onResolve: (value) => onOperation([DecisionCards.resolveOperation(value)]),
      onSkip: (value) => onOperation([DecisionCards.skipOperation(value)]),
    }));
    const empty = node(doc, "p", "gameplay-table-empty", "当前素材没有可确认的玩法表格。");
    if (model.tableReview?.status === "ready" && state.generation?.status !== "error") canvas.append(empty); else empty.hidden = true;
    const tableCards = [];
    let detailInitialized = false;
    tables.forEach((item) => {
      const card = node(doc, "article", "gameplay-table-card");
      const display = reviewTable(item);
      const rowsComplete = rowConfirmationComplete(item, display);
      const showDetail = (detail, values, selectedRow) => {
        body?.children?.forEach?.((candidate) => { candidate.className = (candidate.className || "").replace(/\s*is-selected/g, ""); });
        if (selectedRow) selectedRow.className = `${selectedRow.className || ""} is-selected`.trim();
        const current = detail || { field: values?.[0], purpose: "用于当前玩法参数配置", basis: "素材明确展示", source: "当前素材", formula: "" };
        decision.replaceChildren(node(doc, "h3", "", "参数详情"));
        const name = node(doc, "div", "gameplay-table-detail-name", current.field || values?.[0] || "当前参数"); decision.append(name);
        [["设计目的", current.purpose], ["AI 生成依据", current.basis], ["关联公式", current.formula || "无"], ["配置来源", current.source]].forEach(([label, text]) => { const block = node(doc, "section", "gameplay-table-detail-block"); block.append(node(doc, "h4", "", label), node(doc, "p", "", text || "待策划补充")); decision.append(block); });
      };
      const workbar = node(doc, "header", "gameplay-table-workbar");
      const title = node(doc, "div", "gameplay-table-workbar-title"); title.append(node(doc, "strong", "", item.title || "玩法参数表"), node(doc, "span", "", `${display.rows.length} 个参数`));
      workbar.append(title, node(doc, "span", "gameplay-table-status", item.status === "reviewed" && rowsComplete ? "已通过" : "待审核")); card.append(workbar);
      const basis = node(doc, "p", "gameplay-table-ai-basis", "AI 依据　仅采用素材或参考文档中明确出现的数值；缺少依据的项目不会自动写入。"); card.append(basis);
      const table = node(doc, "table", "gameplay-generated-table"); const head = node(doc, "thead"); const headRow = node(doc, "tr"); display.columns.forEach((value) => headRow.append(node(doc, "th", "", value))); head.append(headRow); table.append(head);
      const body = node(doc, "tbody"); display.rows.forEach((values, rowIndex) => {
        const row = node(doc, "tr"); row.tabIndex = 0;
        values.forEach((value, columnIndex) => {
          const cell = node(doc, "td", "", value);
          if (columnIndex === 3) { cell.textContent = ""; const input = node(doc, "input", "gameplay-table-value-input"); input.value = value; input.setAttribute("aria-label", `${values[0]}修改值`); cell.append(input); }
          if (columnIndex === 4) cell.className = `gameplay-table-row-status ${item.status === "reviewed" ? "is-confirmed" : "is-pending"}`;
          if (columnIndex === 5) { cell.textContent = ""; cell.append(button(doc, "gameplay-table-row-confirm", values[4] === "已确认" ? "已确认" : "确认", () => { const valueInput = row.querySelector?.(".gameplay-table-value-input"); onSelect(item.id); onAction("confirm_row", item.id, JSON.stringify({ rowIndex, value: valueInput?.value ?? values[3] })); showDetail(display.details[rowIndex], values, row); }, false)); }
          row.append(cell);
        });
        row.addEventListener("click", () => showDetail(display.details[rowIndex], values, row));
        body.append(row);
      }); table.append(body); card.append(table);
      const formulas = display.details.map((detail) => detail?.formula).filter(Boolean);
      if (formulas.length) { const fold = node(doc, "details", "gameplay-table-fold-wrap"); const summary = node(doc, "summary", "gameplay-table-fold", `计算公式　${formulas.length} 个`); fold.append(summary); formulas.forEach((formula) => fold.append(node(doc, "code", "gameplay-table-formula", formula))); card.append(fold); }
      const showFirst = () => { if (display.rows.length) showDetail(display.details[0], display.rows[0], body.children[0]); };
      if (!detailInitialized && display.rows.length) { showFirst(); detailInitialized = true; }
      const busy = state.byId?.[item.id]?.status === "pending"; const actions = node(doc, "div", "gameplay-table-actions");
      const requiresRowReview = item.kind === "chapter_parameters" || (display.columns || []).includes("状态");
      const progressText = requiresRowReview
        ? `${display.rows.filter((row) => row[4] === "已确认").length}/${display.rows.length} 已确认`
        : (item.status === "reviewed" ? "整表已通过" : "整表待审核");
      actions.append(node(doc, "span", "gameplay-table-progress", progressText), button(doc, "gameplay-table-regenerate", "AI 重新生成此表", () => { onSelect(item.id); onAction("regenerate", item.id, "请重新核对此表参数"); }, busy), button(doc, "gameplay-table-approve", "通过此表", () => { onSelect(item.id); onAction("approve", item.id, ""); }, busy || !rowsComplete)); card.append(actions); canvas.append(card);
      tableCards.push({ id: item.id, card, chapterIds: item.chapterIds || [], showFirst, rowsComplete, reviewed: item.status === "reviewed" });
    });
    const selectChapter = (chapterId) => {
      chapterButtons.forEach(({ chapter, item }) => item.setAttribute("aria-current", chapter.id === chapterId ? "true" : "false"));
      let visibleCount = 0;
      let selectedCard = null;
      tableCards.forEach(({ card, chapterIds, showFirst }) => {
        card.hidden = Boolean(chapterId) && !chapterIds.includes(chapterId);
        if (!card.hidden) { visibleCount += 1; if (!selectedCard) selectedCard = { showFirst }; }
      });
      selectedCard?.showFirst();
      empty.hidden = model.tableReview?.status !== "ready" || state.generation?.status === "error" || visibleCount > 0;
    };
    chapterButtons.forEach(({ chapter, item }) => item.addEventListener("click", () => { selectChapter(chapter.id); onSelectChapter(chapter.id); }));
    const restoredTable = tableCards.find((entry) => entry.id === state.selectedTableId);
    const restoredChapterId = state.selectedChapterId || restoredTable?.chapterIds?.[0] || chapterButtons[0]?.chapter.id || "";
    selectChapter(restoredChapterId);
    if (restoredTable && !restoredTable.card.hidden) {
      restoredTable.card.className = `${restoredTable.card.className} is-active`.trim();
      restoredTable.showFirst();
    }
    root.replaceChildren(section);
    restoredTable?.card?.scrollIntoView?.({ block: "nearest" });
    if (!model.tableReview?.status && !state.generation?.status) onGenerate();
  }
  const api = { render, reviewTable }; if (typeof module !== "undefined") module.exports = api; else global.GameplayTables = api;
})(typeof window !== "undefined" ? window : globalThis);
