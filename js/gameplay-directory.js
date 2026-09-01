(function (root, factory) {
const api = factory(typeof module !== "undefined" && module.exports ? require("./planner-decision-cards.js") : root.PlannerDecisionCards);
if (typeof module !== "undefined" && module.exports) module.exports = api;
else root.GameplayDirectory = api;
})(typeof window !== "undefined" ? window : globalThis, function (DecisionCards) {
function node(doc, tag, text = "", className = "") { const item = doc.createElement(tag); item.textContent = text; if (className) item.className = className; return item; }
function button(doc, text, action, className = "btn") { const item = node(doc, "button", text, className); item.type = "button"; item.addEventListener("click", action); return item; }
function saveStatusText(status) {
  return ({ queued: "等待保存…", saving: "正在保存…", saved: "已保存", synced: "已保存", conflict: "正在同步最新内容…", failed: "目录保存失败，请重试。" })[status]
    || "修改后会自动保存，确认目录后进入下一步。";
}
function render({ root, model, state = {}, onOperation, onConfirm }) {
  const doc = root.ownerDocument || document; const directory = model.directory || {}; const understanding = directory.understanding || {};
  const structurePhase = model.reviewState?.structurePhase || "legacy";
  root.replaceChildren(); const shell = node(doc, "div", "", "gameplay-directory");
  const contextBar = node(doc, "header", "", "review-context-bar"); contextBar.append(node(doc, "strong", "玩法目录"), node(doc, "span", "当前素材 / 玩法系统与章节 / 目录确认")); shell.append(contextBar);
  const layout = node(doc, "div", "", "gameplay-directory-layout");
  const treeColumn = node(doc, "div", "", "gameplay-directory-tree-column");
  const confirmColumn = node(doc, "aside", "", "gameplay-directory-confirm-column");
  const renderDecisions = () => (model.chapters || []).forEach((chapter) => DecisionCards?.render?.({
    root: confirmColumn, cards: chapter.decisionCards || [], context: { chapterId: chapter.id }, document: doc,
    onResolve: (value) => onOperation?.([DecisionCards.resolveOperation(value)]),
    onSkip: (value) => onOperation?.([DecisionCards.skipOperation(value)]),
  }));
  const renderGate = (title, description, pendingOperations) => {
    const gate = node(doc, "section", "", "gameplay-directory-gate");
    gate.append(
      node(doc, "span", "进入下一步", "gameplay-directory-gate-label"),
      node(doc, "strong", title, "gameplay-directory-gate-title"),
      node(doc, "p", description, "gameplay-directory-gate-copy")
    );
    const status = node(doc, "p", saveStatusText(state.saveStatus), "gameplay-directory-status");
    status.setAttribute("aria-live", "polite");
    const confirm = button(doc, state.confirming ? "正在确认…" : title, () => onConfirm?.(pendingOperations?.()), "btn primary");
    confirm.disabled = state.confirming || state.saveStatus === "failed";
    confirm.setAttribute("aria-describedby", "gameplay-directory-gate-copy");
    gate.querySelector?.(".gameplay-directory-gate-copy")?.setAttribute("id", "gameplay-directory-gate-copy");
    gate.append(status, confirm);
    confirmColumn.append(gate);
  };
  const intro = node(doc, "section", "", "gameplay-directory-understanding");
  const introHead = node(doc, "header", "", "gameplay-directory-understanding-head"); introHead.append(node(doc, "h3", "AI玩法理解"), node(doc, "span", "只读", "gameplay-directory-readonly")); intro.append(introHead);
  const summaryBody = node(doc, "div", "", "gameplay-directory-understanding-body");
  const summaryText = understanding.summary || "尚未形成可确认的玩法理解。";
  summaryText.split(/(?<=[。！？])/).map((part) => part.trim()).filter(Boolean).slice(0, 4).forEach((part) => summaryBody.append(node(doc, "p", part)));
  intro.append(summaryBody);
  const familyTags = node(doc, "div", "", "gameplay-directory-family-tags");
  const primary = node(doc, "section", "", "gameplay-directory-tag-group"); primary.append(node(doc, "span", "主玩法"), node(doc, "b", understanding.primaryFamily || "待确认", "gameplay-directory-chip")); familyTags.append(primary);
  if ((understanding.supportingMechanics || []).length) { const support = node(doc, "section", "", "gameplay-directory-tag-group"); support.append(node(doc, "span", "辅助玩法")); (understanding.supportingMechanics || []).forEach((item) => support.append(node(doc, "b", item, "gameplay-directory-chip is-aux"))); familyTags.append(support); }
  intro.append(familyTags);
  const summary = node(doc, "textarea"); summary.value = understanding.summary || ""; summary.rows = 4; summary.hidden = true; summary.setAttribute("aria-label", "玩法概述，最多四句话"); intro.append(summary);
  if ((understanding.uncertainties || []).length) intro.append(node(doc, "p", `AI还不确定：${understanding.uncertainties.join("；")}`, "gameplay-directory-question"));
  const editUnderstanding = button(doc, "编辑玩法理解", () => { const editing = summary.hidden; summary.hidden = !editing; summaryBody.hidden = editing; editUnderstanding.textContent = editing ? "保存玩法理解" : "编辑玩法理解"; if (!editing) onOperation?.([{ type: "update_gameplay_understanding", understanding: { ...understanding, summary: summary.value } }]); }); editUnderstanding.className = "btn gameplay-directory-understanding-edit"; intro.append(editUnderstanding); layout.append(intro, treeColumn, confirmColumn); shell.append(layout);
  const heading = node(doc, "div", "", "gameplay-directory-heading");
  if (structurePhase === "systems") heading.append(node(doc, "h3", "第一步：确认玩法系统"), node(doc, "p", "先确认素材包含哪些玩法大类。这里只判断整体结构，不填写规则、参数或公式。"));
  else if (structurePhase === "mechanisms") heading.append(node(doc, "h3", "第二步：确认具体机制"), node(doc, "p", "检查每个玩法系统下需要讲清楚的具体机制；确认后，系统再按这份目录补全详细规则。"));
  else { const headingText = node(doc, "div", "", "gameplay-directory-heading-text"); headingText.append(node(doc, "h3", "玩法目录"), node(doc, "p", `共 ${(directory.entries || []).length} 章节 · ${(model.systems || []).length} 系统`)); const headingActions = node(doc, "div", "", "gameplay-directory-heading-actions"); headingActions.append(button(doc, "+ 添加系统", () => { const name = typeof window === "undefined" ? "新玩法系统" : window.prompt("请输入玩法系统名称", "新玩法系统"); if (name?.trim()) onOperation?.([{ type: "add_gameplay_system", name: name.trim() }]); }), button(doc, "+ 添加章节", () => onOperation?.([{ type: "add_directory_entry", title: "待命名玩法" }]), "btn primary")); heading.append(headingText, headingActions); }
  treeColumn.append(heading);
  if (structurePhase === "systems") {
    (model.systems || []).forEach((system) => {
      const group = node(doc, "section", "", "gameplay-directory-system");
      group.append(node(doc, "h4", system.name || "其他玩法"));
      const names = (system.subsystems || []).map((item) => item.name).filter(Boolean);
      if (names.length) group.append(node(doc, "p", `包含：${names.join("、")}`));
      treeColumn.append(group);
    });
    renderDecisions();
    renderGate("确认系统划分，继续检查具体机制", "门禁：确认素材中包含哪些玩法系统。完成后继续检查每个系统下的具体机制，不会直接跳过目录细化。");
    root.append(shell); return;
  }
  let currentSection = "";
  let currentGroupBody = null;
  const sectionFor = (entry) => entry.sectionTitle || (model.systems || []).find((system) => (system.subsystems || []).some((subsystem) => (subsystem.chapterIds || []).includes(entry.chapterId)))?.name || "其他玩法";
  const pendingSummaryEdits = new Map();
  let selectedEntry = (directory.entries || [])[0] || null;
  let editorHeading = null; let editorTitle = null; let editorSummary = null; let editorEntryActions = null; let renderEditorEntryActions = null;
  const selectEntry = (entry) => {
    selectedEntry = entry;
    treeColumn.querySelectorAll?.(".gameplay-directory-tree-item").forEach((item) => {
      item.classList.toggle("is-selected", item.getAttribute?.("data-entry-id") === entry.id);
    });
    if (!editorTitle) return;
    editorHeading.textContent = `编辑章节 · ${entry.title || "待命名玩法"}`;
    editorTitle.value = entry.title || "";
    editorSummary.value = entry.summary || "";
    renderEditorEntryActions?.();
  };
  (directory.entries || []).forEach((entry, index, entries) => {
    const systemTitle = sectionFor(entry);
    if (systemTitle !== currentSection) {
      const group = node(doc, "section", "", "gameplay-directory-group");
      const groupHead = node(doc, "header", "", "gameplay-directory-group-head");
      groupHead.append(node(doc, "span", "▼", "gameplay-directory-group-caret"), node(doc, "h3", systemTitle), node(doc, "span", String(entries.filter((item) => sectionFor(item) === systemTitle).length), "gameplay-directory-group-count"));
      currentGroupBody = node(doc, "section", "", "gameplay-directory-group-body");
      group.append(groupHead, currentGroupBody); treeColumn.append(group); currentSection = systemTitle;
    }
    const chapter = (model.chapters || []).find((item) => item.id === entry.chapterId) || {};
    const claims = (chapter.claims || []).filter((item) => (entry.claimIds || []).includes(item.id));
    const card = node(doc, "section", "", "gameplay-directory-card gameplay-directory-tree-item"); card.setAttribute("data-entry-id", entry.id); card.tabIndex = 0; card.addEventListener("click", () => selectEntry(entry)); card.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectEntry(entry); } }); const title = node(doc, "input"); title.value = entry.title || ""; title.readOnly = true; title.setAttribute("aria-label", `第${index + 1}章名称`);
    title.addEventListener("change", () => onOperation?.([{ type: "rename_directory_entry", entryId: entry.id, title: title.value }]));
    const summaryLabel = node(doc, "label", "这一章主要讲什么", "gameplay-directory-summary-label");
    const chapterSummary = node(doc, "textarea"); chapterSummary.value = entry.summary || ""; chapterSummary.rows = 3;
    chapterSummary.placeholder = "用一两句话说明这章需要讲清的玩法，不要写页面操作步骤。";
    chapterSummary.setAttribute("aria-label", `${entry.title || `第 ${index + 1} 章`}的章节说明`);
    const summaryPreview = node(doc, "span", entry.summary || "尚未填写章节说明", "gameplay-directory-summary-preview");
    chapterSummary.addEventListener("input", () => {
      const value = chapterSummary.value.trim();
      if (value && value !== (entry.summary || "").trim()) pendingSummaryEdits.set(entry.id, value);
      else pendingSummaryEdits.delete(entry.id);
    });
    chapterSummary.addEventListener("change", () => {
      const value = chapterSummary.value.trim();
      if (value && value !== (entry.summary || "").trim()) onOperation?.([{ type: "update_directory_entry_summary", entryId: entry.id, summary: value }]);
      pendingSummaryEdits.delete(entry.id);
    });
    summaryLabel.append(chapterSummary, summaryPreview); card.append(title, summaryLabel);
    const actions = node(doc, "div", "", "gameplay-directory-actions");
    if (index) actions.append(button(doc, "上移", () => { const order = entries.map(item => item.id); [order[index], order[index - 1]] = [order[index - 1], order[index]]; onOperation?.([{ type: "reorder_directory_entries", entryIds: order }]); }));
    if (index < entries.length - 1) actions.append(button(doc, "下移", () => { const order = entries.map(item => item.id); [order[index], order[index + 1]] = [order[index + 1], order[index]]; onOperation?.([{ type: "reorder_directory_entries", entryIds: order }]); }));
    if (index < entries.length - 1) actions.append(button(doc, "与下一项合并", () => {
      if ((typeof window === "undefined" || window.confirm(`确定合并“${entry.title}”和“${entries[index + 1].title}”吗？两部分内容会保留在同一章节。`))) onOperation?.([{ type: "merge_directory_entries", sourceEntryId: entries[index + 1].id, targetEntryId: entry.id }]);
    }));
    const splitPanel = node(doc, "section", "", "gameplay-directory-split"); splitPanel.hidden = true;
    if ((entry.claimIds || []).length > 1) actions.append(button(doc, "拆成两项", () => { splitPanel.hidden = !splitPanel.hidden; }));
    if (!(entry.claimIds || []).length && entries.length > 1) actions.append(button(doc, "删除空章节", () => {
      if (typeof window === "undefined" || window.confirm(`确定删除空章节“${entry.title}”吗？`)) onOperation?.([{ type: "delete_directory_entry", entryId: entry.id }]);
    }, "btn warn"));
    if ((entry.claimIds || []).length > 1) {
      splitPanel.append(node(doc, "h4", "选择要放进新章节的内容"));
      const newTitle = node(doc, "input"); newTitle.value = "新玩法章节"; newTitle.setAttribute("aria-label", "新章节名称"); splitPanel.append(newTitle);
      const selections = claims.map((claim, claimIndex) => {
        const label = node(doc, "label", "", "gameplay-directory-claim-choice"); const checkbox = node(doc, "input"); checkbox.type = "checkbox"; checkbox.checked = claimIndex === claims.length - 1;
        label.append(checkbox, node(doc, "span", claim.text || `内容 ${claimIndex + 1}`)); splitPanel.append(label); return { id: claim.id, checkbox };
      });
      const error = node(doc, "p", "", "gameplay-directory-split-error"); error.setAttribute("role", "alert"); splitPanel.append(error);
      splitPanel.append(button(doc, "确认拆分", () => {
        const selected = selections.filter((item) => item.checkbox.checked).map((item) => item.id); const title = newTitle.value.trim();
        if (!title || !selected.length || selected.length === entry.claimIds.length) { error.textContent = "请填写新章节名称，并选择部分内容移入新章节。"; return; }
        error.textContent = ""; onOperation?.([{ type: "split_directory_entry", entryId: entry.id, title, claimIds: selected }]);
      }, "btn primary"));
    }
    currentGroupBody.append(card);
  });
  if (selectedEntry) {
    const editor = node(doc, "section", "", "gameplay-directory-editor");
    editorHeading = node(doc, "h3", "编辑章节");
    editor.append(editorHeading, node(doc, "p", "从中间目录选择章节后，在这里修改名称和说明。"));
    editorTitle = node(doc, "input"); editorTitle.setAttribute("aria-label", "当前章节名称");
    editorSummary = node(doc, "textarea"); editorSummary.rows = 5; editorSummary.setAttribute("aria-label", "当前章节说明");
    editor.append(node(doc, "label", "章节名称"), editorTitle, node(doc, "label", "章节说明"), editorSummary);
    editorEntryActions = node(doc, "section", "", "gameplay-directory-entry-actions");
    renderEditorEntryActions = () => {
      const entries = directory.entries || [];
      const index = entries.findIndex((item) => item.id === selectedEntry.id);
      const chapter = (model.chapters || []).find((item) => item.id === selectedEntry.chapterId) || {};
      const claims = (chapter.claims || []).filter((item) => (selectedEntry.claimIds || []).includes(item.id));
      const controls = node(doc, "div", "", "gameplay-directory-editor-actions");
      if (index > 0) controls.append(button(doc, "\u2191 \u4e0a\u79fb", () => { const order = entries.map((item) => item.id); [order[index], order[index - 1]] = [order[index - 1], order[index]]; onOperation?.([{ type: "reorder_directory_entries", entryIds: order }]); }));
      if (index >= 0 && index < entries.length - 1) {
        controls.append(button(doc, "\u2193 \u4e0b\u79fb", () => { const order = entries.map((item) => item.id); [order[index], order[index + 1]] = [order[index + 1], order[index]]; onOperation?.([{ type: "reorder_directory_entries", entryIds: order }]); }));
        controls.append(button(doc, "\u4e0e\u4e0b\u4e00\u9879\u5408\u5e76", () => { if (typeof window === "undefined" || window.confirm(`\u786e\u5b9a\u5408\u5e76\u201c${selectedEntry.title}\u201d\u548c\u201c${entries[index + 1].title}\u201d\u5417\uff1f`)) onOperation?.([{ type: "merge_directory_entries", sourceEntryId: entries[index + 1].id, targetEntryId: selectedEntry.id }]); }));
      }
      const splitPanel = node(doc, "section", "", "gameplay-directory-split"); splitPanel.hidden = true;
      if ((selectedEntry.claimIds || []).length > 1) {
        controls.append(button(doc, "\u62c6\u6210\u4e24\u9879", () => { splitPanel.hidden = !splitPanel.hidden; }));
        splitPanel.append(node(doc, "h4", "\u9009\u62e9\u8981\u653e\u8fdb\u65b0\u7ae0\u8282\u7684\u5185\u5bb9"));
        const newTitle = node(doc, "input"); newTitle.value = "\u65b0\u73a9\u6cd5\u7ae0\u8282"; newTitle.setAttribute("aria-label", "\u65b0\u7ae0\u8282\u540d\u79f0"); splitPanel.append(newTitle);
        const selections = claims.map((claim, claimIndex) => { const label = node(doc, "label", "", "gameplay-directory-claim-choice"); const checkbox = node(doc, "input"); checkbox.type = "checkbox"; checkbox.checked = claimIndex === claims.length - 1; label.append(checkbox, node(doc, "span", claim.text || `\u5185\u5bb9 ${claimIndex + 1}`)); splitPanel.append(label); return { id: claim.id, checkbox }; });
        const error = node(doc, "p", "", "gameplay-directory-split-error"); error.setAttribute("role", "alert"); splitPanel.append(error);
        splitPanel.append(button(doc, "\u786e\u8ba4\u62c6\u5206", () => { const selected = selections.filter((item) => item.checkbox.checked).map((item) => item.id); const title = newTitle.value.trim(); if (!title || !selected.length || selected.length === selectedEntry.claimIds.length) { error.textContent = "\u8bf7\u586b\u5199\u65b0\u7ae0\u8282\u540d\u79f0\uff0c\u5e76\u9009\u62e9\u90e8\u5206\u5185\u5bb9\u79fb\u5165\u65b0\u7ae0\u8282\u3002"; return; } error.textContent = ""; onOperation?.([{ type: "split_directory_entry", entryId: selectedEntry.id, title, claimIds: selected }]); }, "btn primary"));
      }
      if (!(selectedEntry.claimIds || []).length && entries.length > 1) controls.append(button(doc, "\u5220\u9664\u7a7a\u7ae0\u8282", () => { if (typeof window === "undefined" || window.confirm(`\u786e\u5b9a\u5220\u9664\u7a7a\u7ae0\u8282\u201c${selectedEntry.title}\u201d\u5417\uff1f`)) onOperation?.([{ type: "delete_directory_entry", entryId: selectedEntry.id }]); }, "btn warn"));
      editorEntryActions.replaceChildren(controls, splitPanel);
    };
    editor.append(editorEntryActions);
    const moduleField = node(doc, "section", "", "gameplay-directory-module-field");
    moduleField.append(node(doc, "h4", "所属模块"));
    const systems = (model.systems || []).length ? model.systems : [{ name: selectedEntry.sectionTitle || "其他玩法" }];
    systems.forEach((system, index) => {
      const systemName = system.name || "其他玩法";
      const label = node(doc, "label", "", "gameplay-directory-module-option"); const radio = node(doc, "input"); radio.type = "radio"; radio.name = "gameplay-directory-module"; radio.checked = selectedEntry.sectionTitle ? selectedEntry.sectionTitle === systemName : index === 0;
      radio.addEventListener("change", () => { if (radio.checked && selectedEntry.sectionTitle !== systemName) onOperation?.([{ type: "move_directory_entry_to_system", entryId: selectedEntry.id, systemName }]); });
      label.append(radio, node(doc, "span", systemName)); moduleField.append(label);
    });
    editor.append(moduleField, node(doc, "h4", "操作"));
    const editorActions = node(doc, "div", "", "gameplay-directory-editor-actions");
    editorActions.append(
      button(doc, "↑ 上移", () => {
        const entries = directory.entries || []; const index = entries.findIndex((item) => item.id === selectedEntry.id); if (index <= 0) return;
        const order = entries.map((item) => item.id); [order[index], order[index - 1]] = [order[index - 1], order[index]]; onOperation?.([{ type: "reorder_directory_entries", entryIds: order }]);
      }),
      button(doc, "↓ 下移", () => {
        const entries = directory.entries || []; const index = entries.findIndex((item) => item.id === selectedEntry.id); if (index < 0 || index >= entries.length - 1) return;
        const order = entries.map((item) => item.id); [order[index], order[index + 1]] = [order[index + 1], order[index]]; onOperation?.([{ type: "reorder_directory_entries", entryIds: order }]);
      })
    );
    renderEditorEntryActions();
    const editorFooter = node(doc, "footer", "", "gameplay-directory-editor-footer");
    editorFooter.append(button(doc, "取消", () => selectEntry(selectedEntry)), button(doc, "保存修改", () => {
      const operations = [];
      const title = editorTitle.value.trim();
      const summary = editorSummary.value.trim();
      if (title && title !== (selectedEntry.title || "").trim()) operations.push({ type: "rename_directory_entry", entryId: selectedEntry.id, title });
      if (summary && summary !== (selectedEntry.summary || "").trim()) operations.push({ type: "update_directory_entry_summary", entryId: selectedEntry.id, summary });
      if (operations.length) onOperation?.(operations);
    }, "btn primary"));
    editor.append(editorFooter);
    selectEntry(selectedEntry);
    confirmColumn.prepend?.(editor);
    if (!confirmColumn.prepend) confirmColumn.children.unshift(editor);
  }
  renderDecisions();
  const confirmLabel = structurePhase === "mechanisms" ? "确认机制目录，开始生成详细规则" : "确认理解和目录，开始审核";
  const gateCopy = structurePhase === "mechanisms"
    ? "门禁：确认每个玩法系统下的具体机制与章节归属。完成后生成详细规则并进入交互审核。"
    : "门禁：确认玩法理解、章节归属和章节说明。完成后进入交互审核。";
  renderGate(confirmLabel, gateCopy, () => Array.from(pendingSummaryEdits, ([entryId, summary]) => ({ type: "update_directory_entry_summary", entryId, summary })));
  root.append(shell);
}
return { render, saveStatusText };
});
