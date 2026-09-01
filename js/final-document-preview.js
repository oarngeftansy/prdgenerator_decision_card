(function (global) {
  const DecisionCards = typeof module !== "undefined" && module.exports ? require("./planner-decision-cards.js") : global.PlannerDecisionCards;
  function el(doc, tag, className = "", text = "") {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function outline(model) {
    const chapters = model.chapters || [];
    const used = new Set();
    const groups = (model.systems || []).map((system) => ({
      title: system.name || "玩法系统",
      sections: (system.subsystems || []).map((subsystem) => ({
        title: subsystem.name || "玩法模块",
        chapters: (subsystem.chapterIds || []).map((id) => chapters.find((chapter) => chapter.id === id)).filter(Boolean).map((chapter) => { used.add(chapter.id); return chapter; }),
      })).filter((section) => section.chapters.length),
    })).filter((group) => group.sections.length);
    const remainder = chapters.filter((chapter) => !used.has(chapter.id));
    if (remainder.length) groups.push({ title: "其他玩法", sections: [{ title: "补充规则", chapters: remainder }] });
    return groups;
  }

  function textOf(value) {
    if (typeof value === "string" || typeof value === "number") return String(value).trim();
    if (!value || typeof value !== "object") return "";
    return String(value.text || value.description || value.value || value.rule || value.expected || "").trim();
  }

  function valuesOf(...values) {
    const result = [];
    values.flat(Infinity).forEach((value) => {
      if (value && typeof value === "object" && !Array.isArray(value) && !textOf(value)) Object.values(value).forEach((item) => { const text = textOf(item); if (text) result.push(text); });
      else { const text = textOf(value); if (text) result.push(text); }
    });
    return [...new Set(result)];
  }

  function scopeSvgIds(svg, scope) {
    const safeScope = String(scope || "figure").replace(/[^a-zA-Z0-9_-]+/g, "-");
    const ids = new Map();
    String(svg || "").replace(/\bid=["']([^"']+)["']/g, (match, id) => {
      ids.set(id, `${safeScope}-${id}`);
      return match;
    });
    let scoped = String(svg || "");
    ids.forEach((nextId, id) => {
      const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      scoped = scoped
        .replace(new RegExp(`(\\bid=["'])${escaped}(["'])`, "g"), `$1${nextId}$2`)
        .replace(new RegExp(`url\\(#${escaped}\\)`, "g"), `url(#${nextId})`)
        .replace(new RegExp(`((?:xlink:)?href=["'])#${escaped}(["'])`, "g"), `$1#${nextId}$2`);
    });
    return scoped;
  }

  function scopeEmbeddedSvgs(html, scope) {
    let index = 0;
    return String(html || "").replace(/<svg\b[\s\S]*?<\/svg>/gi, (svg) => scopeSvgIds(svg, `${scope}-${index++}`));
  }

  function attributeAnchorId(chapterId, kind, index = 0) {
    return `final-doc-${chapterId}-attribute-${kind}-${index}`;
  }

  function clearObservedText(value) {
    const text = textOf(value);
    return Boolean(text) && !/(待确认|未知|可能|推测|需要配置视觉模型|unknown|undefined)/i.test(text);
  }

  function interactionStageIsReady(stage, interaction) {
    const transitions = Array.isArray(interaction.transitions) ? interaction.transitions : Object.values(interaction.transitions || {});
    const sourceStore = interaction.sources || interaction.frames || {};
    const sources = Array.isArray(sourceStore) ? sourceStore : Object.entries(sourceStore).map(([id, source]) => ({ id, ...source }));
    const stageFacts = [
      stage.pagePurpose, stage.purpose, stage.objective, stage.description,
      stage.operationBefore, stage.before, stage.entryCondition, stage.smallLoop?.before, stage.smallLoop?.trigger,
      stage.playerAction, stage.operation, stage.smallLoop?.action,
      stage.systemFeedback, stage.feedback, stage.smallLoop?.feedback,
      stage.operationResult, stage.result, stage.exitCondition, stage.smallLoop?.result,
    ].filter(clearObservedText);
    const sourceFacts = sources.filter((source) => source.stageId === stage.id || (stage.representativeFrames || []).some((frame) => frame.frameId === (source.frameId || source.id)))
      .flatMap((source) => [source.pageInfo?.action, source.pageInfo?.feedback, source.pageInfo?.result]).filter(clearObservedText);
    if (stageFacts.length || sourceFacts.length) return true;
    return transitions.some((transition) => {
      const inferred = transition.inferred === true || transition.triggerType === "unknown" || /推测|可能|unknown|inferred/i.test(String(transition.sourceLevel || transition.evidenceLevel || ""));
      return transition.sourceStageId === stage.id && transition.included !== false && !inferred && clearObservedText(transition.triggerLabel);
    });
  }

  function appendListSection(doc, section, heading, values) {
    const items = valuesOf(values);
    if (!items.length) return;
    section.append(el(doc, "h4", "final-document-h4", heading));
    const list = el(doc, "ol", "final-document-list");
    items.forEach((item) => list.append(el(doc, "li", "", item))); section.append(list);
  }

  function appendPlainList(doc, section, values) {
    const items = valuesOf(values);
    if (!items.length) return;
    const list = el(doc, "ul", "final-document-list final-document-compact-list");
    items.forEach((item) => list.append(el(doc, "li", "", item))); section.append(list);
  }

  function appendFlow(doc, section, values) {
    const items = valuesOf(values);
    if (!items.length) return;
    if (items.length < 3) return appendPlainList(doc, section, items);
    const list = el(doc, "ol", "final-document-list");
    items.forEach((item) => list.append(el(doc, "li", "", item))); section.append(list);
  }

  function deliveryTableData(table) {
    const columns = table.columns || [];
    const fieldIndex = columns.indexOf("字段");
    const typeIndex = columns.indexOf("类型");
    const suggestedIndex = columns.indexOf("AI 建议值");
    const modifiedIndex = columns.indexOf("修改值");
    const auditTable = fieldIndex >= 0 && suggestedIndex >= 0 && modifiedIndex >= 0;
    if (!auditTable) return { columns, rows: table.rows || [] };
    const rows = (table.rows || []).map((row) => {
      const value = String(row[modifiedIndex] ?? "").trim() || String(row[suggestedIndex] ?? "").trim();
      const type = String(row[typeIndex] ?? "");
      const unit = type.match(/[（(]([^）)]+)[）)]/)?.[1] || "";
      const confirmedValue = unit && value && !value.endsWith(unit) ? `${value}${unit}` : value;
      return [row[fieldIndex], confirmedValue];
    });
    return { columns: ["参数", "确认值"], rows };
  }

  function comparableText(value) {
    return textOf(value).toLowerCase().replace(/[\s，。；：、,.!?！？“”'"（）()\-—]/g, "");
  }

  function sparseChapter(chapter) {
    if ((chapter.inlineFigures || []).length) return false;
    const planner = chapter.plannerSections || {};
    const flow = valuesOf(planner.normalFlow || planner.normalPlay || planner.flow || chapter.flow || chapter.steps);
    const groups = [
      flow.length,
      valuesOf(planner.keyRules, chapter.mechanism?.description, chapter.claims, chapter.rules).length,
      valuesOf(planner.specialCases, planner.edgeCases, chapter.edgeCases, chapter.boundaries, chapter.resetRules).length,
      (chapter.parameters && Object.keys(chapter.parameters).length) || (chapter.parameterSchema || []).length,
      (chapter.formulae || chapter.formulas || []).length || (chapter.workedExamples || []).length,
      (chapter.acceptanceCases || []).length || valuesOf(planner.validation, planner.acceptance, planner.acceptanceExamples).length,
      (chapter.configurationSources || []).length || (chapter.dependencies || []).length,
    ].filter(Boolean).length;
    return flow.length < 3 && groups <= 2;
  }

  function chapterContent(doc, chapter, model, interaction, { merged = false } = {}) {
    const section = el(doc, "section", "final-document-chapter");
    section.id = `final-doc-${chapter.id}`;
    const planner = chapter.plannerSections || {};
    const objectHeading = textOf(planner.attributeHeading);
    const documentHeading = objectHeading || chapter.scope || "玩法规则";
    const intro = textOf(planner.summary || chapter.plannerSummary || chapter.summary || chapter.oneSentence || chapter.description
      || (chapter.claims || []).find((item) => item && item.status !== "deleted")?.text);
    const plannerHasStructuredCopy = !!textOf(planner.summary || chapter.plannerSummary)
      || valuesOf(planner.normalFlow, planner.normalPlay, planner.flow, planner.keyRules, planner.specialCases, planner.edgeCases).length > 0;
    if (merged) {
      const label = String(chapter.scope || "玩法规则").replace(/(?:机制|状态管理)$/, "") || chapter.scope || "玩法规则";
      const mergedDetails = valuesOf(planner.normalFlow, planner.keyRules, planner.specialCases, plannerHasStructuredCopy ? [] : chapter.claims, chapter.rules)
        .filter((value) => comparableText(value) !== comparableText(intro));
      const mergedCopy = [intro, ...mergedDetails].filter(Boolean).join("；").replace(/[。；]+；/g, "；");
      const lead = el(doc, "p", "final-document-paragraph final-document-merged-rule");
      if (doc.createTextNode) {
        lead.append(el(doc, "strong", "", `${label}：`));
        if (mergedCopy) lead.append(doc.createTextNode(mergedCopy));
      } else {
        lead.textContent = `${label}：${mergedCopy}`;
      }
      section.append(lead);
    } else {
      const heading = el(doc, "h3", "final-document-h3", documentHeading);
      if (objectHeading) heading.setAttribute("id", attributeAnchorId(chapter.id, "object"));
      section.append(heading);
      if (intro) section.append(el(doc, "p", "final-document-paragraph", intro));
    }
    const normalFlow = valuesOf(planner.normalFlow || planner.normalPlay || planner.flow || chapter.flow || chapter.steps);
    const rawClaims = (plannerHasStructuredCopy ? (chapter.rules || []) : (chapter.claims || chapter.rules || []))
      .filter((item) => item && item.status !== "deleted");
    const depthGroups = [normalFlow, rawClaims.length || valuesOf(planner.keyRules, chapter.mechanism?.description).length,
      Object.keys(chapter.parameters || {}).length || (chapter.parameterSchema || []).length,
      (chapter.formulae || chapter.formulas || []).length || (chapter.workedExamples || []).length,
      (chapter.acceptanceCases || []).length || valuesOf(planner.validation, planner.acceptance, planner.acceptanceExamples).length,
      valuesOf(planner.specialCases, planner.edgeCases, chapter.edgeCases, chapter.boundaries, chapter.resetRules).length,
      (chapter.configurationSources || []).length || (chapter.dependencies || []).length].filter((value) => Array.isArray(value) ? value.length : value).length;
    const compact = depthGroups <= 1;
    if (!merged && normalFlow.length >= 3) {
      const flowName = chapter.flowHeading || `${String(chapter.scope || "玩法").replace(/(?:机制|系统|规则)$/, "") || "玩法"}流程`;
      section.append(el(doc, "h4", "final-document-h4", flowName));
    }
    const anchoredDiagrams = (model.diagrams || []).filter((diagram) => diagram.status !== "deleted" && diagram.placement?.chapterId === chapter.id);
    if (!merged) {
      if (!anchoredDiagrams.length) appendFlow(doc, section, normalFlow);
      else {
        const renderDiagram = (diagram) => {
          const safeSvg = global.ExportPreview?.sanitizeBoardSvg?.(diagram.svg || "") || "";
          if (!safeSvg) return;
          section.append(el(doc, "h4", "final-document-h4", diagram.title || "玩法图示"));
          const canvas = el(doc, "div", "final-document-gameplay-diagram");
          canvas.setAttribute("aria-label", diagram.title || "玩法图示"); canvas.innerHTML = scopeSvgIds(safeSvg, `diagram-${diagram.id || chapter.id}`); section.append(canvas);
        };
        // A diagram supports a complete rule group; it must not split a numbered
        // sequence or publish placement/review metadata as planner copy.
        appendFlow(doc, section, normalFlow);
        anchoredDiagrams.forEach(renderDiagram);
      }
    }
    if (!merged) {
      const sourceStore = interaction?.sources || interaction?.frames || {};
      const sources = Array.isArray(sourceStore) ? sourceStore : Object.entries(sourceStore).map(([id, value]) => ({ id, frameId: id, ...value }));
      (chapter.inlineFigures || []).forEach((figureSpec) => {
        const source = sources.find((item) => (item.frameId || item.id) === figureSpec.frameId);
        const src = source?.imageUrl || source?.previewUrl || source?.url || source?.src;
        if (!src) return;
        const figure = el(doc, "figure", "final-document-inline-figure");
        const image = el(doc, "img", "final-document-inline-image");
        image.src = src; image.alt = figureSpec.alt || figureSpec.caption || `${chapter.scope || "玩法"}说明图`;
        figure.append(image);
        if (figureSpec.caption) figure.append(el(doc, "figcaption", "final-document-inline-caption", figureSpec.caption));
        section.append(figure);
      });
    }
    const usedGameplayCopy = new Set([intro, ...normalFlow].map(comparableText).filter(Boolean));
    const mechanismRules = chapter.mechanism && typeof chapter.mechanism === "object"
      ? Object.entries(chapter.mechanism).filter(([key]) => !["type", "description"].includes(key)).map(([, value]) => value)
      : [];
    const claims = rawClaims.filter((item) => {
      if (!item || item.status === "deleted") return false;
      const copy = comparableText(item.text || item.value || item.description);
      if (copy && usedGameplayCopy.has(copy)) return false;
      if (copy) usedGameplayCopy.add(copy);
      return true;
    });
    let ruleHeadingRendered = false;
    const appendRuleHeading = () => {
      if (ruleHeadingRendered || !chapter.ruleHeading) return;
      const heading = el(doc, "h4", "final-document-h4", chapter.ruleHeading);
      heading.setAttribute("id", `final-doc-${chapter.id}-rule-heading`);
      section.append(heading);
      ruleHeadingRendered = true;
    };
    if (!merged && claims.length) appendRuleHeading();
    if (!merged) claims.forEach((claim) => {
      section.append(el(doc, "p", "final-document-paragraph final-document-compact-rule", claim.text || claim.value || claim.description || ""));
    });
    if (!merged && !claims.length) {
      const keyRules = valuesOf(
        planner.keyRules,
        plannerHasStructuredCopy ? [] : chapter.mechanism?.description,
        plannerHasStructuredCopy ? [] : mechanismRules,
      ).filter((value) => !usedGameplayCopy.has(comparableText(value)));
      if (keyRules.length) appendRuleHeading();
      appendPlainList(doc, section, keyRules);
    }
    const boundaryRules = valuesOf(planner.specialCases, planner.edgeCases, chapter.edgeCases, chapter.boundaries, chapter.resetRules);
    if (!merged && boundaryRules.length) {
      appendRuleHeading();
      appendPlainList(doc, section, boundaryRules);
    }
    const attributeSections = Array.isArray(planner.attributeSections) ? planner.attributeSections : [];
    if (!merged) attributeSections.forEach((group, groupIndex) => {
      const items = valuesOf(group?.items || group?.rules || group?.content);
      if (!items.length) return;
      const block = el(doc, "section", "final-document-attribute-section");
      if (group.heading || group.title) {
        const heading = el(doc, "h4", "final-document-h4", group.heading || group.title);
        heading.setAttribute("id", attributeAnchorId(chapter.id, "group", groupIndex));
        block.append(heading);
      }
      appendPlainList(doc, block, items);
      section.append(block);
    });
    const linkedTables = (model.tables || []).filter((table) => table.status !== "deleted" && (table.chapterIds || []).includes(chapter.id));
    // chapter.parameters / parameterSchema are internal review carriers. The
    // final PRD renders only reviewed, mechanism-specific tables linked below;
    // a universal parameter audit table is not planner-facing documentation.
    const fieldMappings = (chapter.fieldDictionary || []).filter((item) => item && (item.plannerName || item.suggestedCodeName));
    if (fieldMappings.length) {
      section.append(el(doc, "p", "final-document-paragraph final-document-parameter-naming-title", "参数命名"));
      const list = el(doc, "ul", "final-document-list final-document-parameter-naming");
      fieldMappings.forEach((item) => {
        const decisionState = String(item.decisionStatus || item.status || "").trim().toLowerCase();
        const adopted = item.confirmed === true || ["accepted", "confirmed", "adopted", "已采用", "已确认"].includes(decisionState);
        const line = `${item.plannerName || "策划字段"}：${item.suggestedCodeName || "—"}${adopted ? "" : "（建议）"}`;
        list.append(el(doc, "li", "", line));
      });
      section.append(list);
    }
    const formulae = (chapter.formulae || chapter.formulas || []).map((formula) => typeof formula === "string" ? formula : [formula.name || formula.title, formula.expression || formula.formula].filter(Boolean).join(" = ")).filter(Boolean);
    if (formulae.length) formulae.forEach((formula) => section.append(el(doc, "div", "final-document-formula", formula)));
    const examples = valuesOf((chapter.workedExamples || []).map((item) => {
      if (typeof item === "string") return item;
      const title = item.name || item.title || "";
      const detail = item.expression || item.calculation || item.steps || item.result || "";
      return [/^(?:计算示例|示例|算例)$/.test(title) ? "" : title, detail].filter(Boolean).join("：");
    }));
    appendPlainList(doc, section, examples);
    const configurationSources = valuesOf((chapter.configurationSources || []).map((item) => typeof item === "string" ? item : [item.title || item.name, item.field].filter(Boolean).join(" · ")));
    if (!linkedTables.length) appendPlainList(doc, section, configurationSources);
    linkedTables.forEach((table) => {
      const delivery = deliveryTableData(table);
      if (table.title) section.append(el(doc, "h4", "final-document-h4 final-document-table-title", table.title));
      const tableNode = el(doc, "table", "final-document-table");
      const head = el(doc, "thead"); const headRow = el(doc, "tr");
      delivery.columns.forEach((column) => headRow.append(el(doc, "th", "", column))); head.append(headRow); tableNode.append(head);
      const body = el(doc, "tbody");
      delivery.rows.forEach((values) => { const row = el(doc, "tr"); values.forEach((value) => row.append(el(doc, "td", "", String(value ?? "")))); body.append(row); });
      tableNode.append(body); section.append(tableNode);
    });
    const diagramLabels = { state_flow: "玩法流程图", probability: "随机算法流程图", spatial: "空间关系图", effect_chain: "效果链路图", formula: "计算关系图" };
    (model.diagrams || []).filter((diagram) => diagram.status !== "deleted" && !diagram.placement && (diagram.chapterIds || [])[0] === chapter.id).forEach((diagram) => {
      const safeSvg = global.ExportPreview?.sanitizeBoardSvg?.(diagram.svg || "") || "";
      if (!safeSvg) return;
      section.append(el(doc, "h4", "final-document-h4", diagram.title || diagramLabels[diagram.type] || "玩法图示"));
      const canvas = el(doc, "div", "final-document-gameplay-diagram");
      canvas.setAttribute("aria-label", diagram.title || diagramLabels[diagram.type] || "玩法图示");
      canvas.innerHTML = scopeSvgIds(safeSvg, `diagram-${diagram.id || chapter.id}`);
      section.append(canvas);
    });
    return section;
  }

  function interactionValue(stage, ...keys) {
    for (const key of keys) {
      const value = key.split(".").reduce((current, part) => current && current[part], stage);
      const text = textOf(value);
      if (text && !/(未知|待确认|unknown|undefined|需要配置视觉模型|可能|推测)/i.test(text) && !/^[\s'"`()，。,.：:；;、-]+$/.test(text)) return text;
    }
    return "";
  }

  function interactionStageContent(doc, stage, interaction, index) {
    const section = el(doc, "section", "final-document-interaction-stage");
    section.id = `final-doc-stage-${stage.id || index}`;
    section.append(el(doc, "h3", "final-document-h3", stage.title || stage.name || stage.pageName || `交互环节 ${index + 1}`));
    const sourceStore = interaction.sources || interaction.frames || [];
    const sources = (Array.isArray(sourceStore) ? sourceStore : Object.values(sourceStore)).filter((source) => source.stageId === stage.id);
    const source = sources.find((item) => item.imageUrl || item.previewUrl || item.url || item.src);
    if (source) {
      const figure = el(doc, "figure", "final-document-interaction-figure");
      const image = el(doc, "img", "final-document-interaction-image");
      image.src = source.imageUrl || source.previewUrl || source.url || source.src; image.alt = `${stage.title || stage.name || "交互环节"}原始画面`;
      figure.append(image); section.append(figure);
    }
    const transitions = (interaction.transitions || []).filter((transition) => transition.sourceStageId === stage.id || transition.fromStageId === stage.id);
    const primaryTransition = transitions.find((transition) => transition.primary !== false && transition.included !== false) || transitions[0] || {};
    const rows = [
      ["页面用途", interactionValue(stage, "pagePurpose", "purpose", "objective", "description")],
      ["操作前", interactionValue(stage, "operationBefore", "before", "smallLoop.before", "entryCondition")],
      ["玩家操作", interactionValue(stage, "playerAction", "operation", "smallLoop.action") || interactionValue(primaryTransition, "triggerLabel", "trigger", "action")],
      ["系统反馈", interactionValue(stage, "systemFeedback", "feedback", "smallLoop.feedback") || interactionValue(primaryTransition, "response")],
      ["操作结果", interactionValue(stage, "operationResult", "result", "smallLoop.result", "exitCondition") || interactionValue(primaryTransition, "resultState")],
    ].filter(([, value]) => value);
    if (rows.length) {
      const details = el(doc, "dl", "final-document-interaction-details");
      rows.forEach(([label, value]) => { details.append(el(doc, "dt", "", label), el(doc, "dd", "", value)); });
      section.append(details);
    }
    if (transitions.length) {
      section.append(el(doc, "h4", "final-document-h4", "页面跳转"));
      const list = el(doc, "ul", "final-document-list");
      transitions.forEach((transition) => {
        const targetId = transition.targetStageId || transition.toStageId;
        const target = (interaction.stages || []).find((candidate) => candidate.id === targetId);
        const trigger = interactionValue(transition, "triggerLabel", "trigger", "action", "description") || "完成当前操作";
        list.append(el(doc, "li", "", `${trigger} → ${target?.title || target?.name || target?.pageName || "下一页面"}`));
      });
      section.append(list);
    }
    return section;
  }

  function collapsibleTocGroup(doc, title, build) {
    const box = el(doc, "section", "final-document-toc-group");
    const toggle = el(doc, "button", "final-document-toc-toggle", `▾ ${title}`); toggle.type = "button"; toggle.setAttribute("aria-expanded", "true");
    const panel = el(doc, "div", "final-document-toc-panel"); build(panel);
    toggle.tocPanel = panel;
    toggle.onclick = () => { const current = typeof toggle.getAttribute === "function" ? toggle.getAttribute("aria-expanded") : toggle.attributes?.["aria-expanded"]; const expanded = String(current) !== "false"; toggle.setAttribute("aria-expanded", String(!expanded)); panel.hidden = expanded; toggle.textContent = `${expanded ? "▸" : "▾"} ${title}`; };
    box.append(toggle, panel); return box;
  }

  function render({ root, preview = {}, model = {}, interaction = {}, interactionPreview = null, view = {}, completion = {}, publication = {}, onRegenerate = () => {}, onMarkdown = () => {}, onExport = () => {}, onPublish = () => {}, onFeishuAction = () => {}, onBack = () => {}, onResolveIncomplete = onBack, onResolvePending = onBack, onDecisionOperation = () => {}, document: doc = global.document }) {
    root.replaceChildren();
    const completionSnapshot = preview.completionSnapshot || { ready: false, percent: 0, checks: [], steps: [] };
    const shell = el(doc, "section", "final-document-shell");
    const stepbar = el(doc, "nav", "final-document-stepbar");
    const stepNodes = [];
    stepbar.setAttribute("aria-label", "策划案交付准备进度；当前页面为文档导出");
    const snapshotSteps = completionSnapshot.steps || [];
    snapshotSteps.forEach((item, index, labels) => {
      const isCurrentPage = index === labels.length - 1;
      const step = el(doc, "span", `final-document-step ${item.done ? "is-done" : "is-pending"}${isCurrentPage ? " is-current" : ""}`);
      if (isCurrentPage) step.setAttribute("aria-current", "step");
      stepNodes.push(step);
      step.append(el(doc, "b", "", item.done ? "✓" : String(index + 1)), el(doc, "span", "", item.label));
      stepbar.append(step);
      if (index < labels.length - 1) stepbar.append(el(doc, "i", "final-document-step-arrow", "›"));
    });
    const back = el(doc, "button", "btn final-document-back", "返回修改"); back.type = "button"; back.onclick = onBack; stepbar.append(back);
    shell.append(stepbar);
    const titlebar = el(doc, "header", "final-document-titlebar");
    const titleBlock = el(doc, "div", "final-document-titleblock");
    const titleLine = el(doc, "div", "final-document-titleline");
    titleLine.append(el(doc, "h2", "", preview.documentTitle || preview.title || "移动端交互与玩法完整策划案"), el(doc, "span", "final-document-version", "V1.0"));
    const missingChapters = completion.missingChapters || preview.missingChapters || [];
    const confirmedChapters = (model.chapters || []).filter((chapter) => chapter.confirmation?.confirmed).length;
    const readyStages = (interaction.stages || []).filter((stage) => stage.confirmation?.confirmed && interactionStageIsReady(stage, interaction)).length;
    const activeTables = (model.tables || []).filter((item) => item.status !== "deleted");
    const activeDiagrams = (model.diagrams || []).filter((item) => item.status !== "deleted");
    const allDecisionCards = (model.chapters || []).flatMap((chapter) => chapter.decisionCards || []);
    const pendingDecisionCards = (model.chapters || []).flatMap((chapter) => (DecisionCards?.actionable?.(chapter.decisionCards || []) || []).map((card) => ({ ...card, chapterId: chapter.id })));
    const granularityAudit = preview.granularityAudit || { passed: false, findings: [{ message: "尚未获得真实内容颗粒度审核结果，暂不能导出。" }], chapters: [] };
    const granularityFindings = granularityAudit.findings || [];
    const languageAudit = preview.languageAudit || { passed: false, findings: [{ message: "尚未获得真实语言与表述审核结果，暂不能导出。" }], chapters: [] };
    const languageFindings = languageAudit.findings || [];
    const tablesDone = Boolean(activeTables.length) && activeTables.every((item) => item.status === "reviewed");
    const noDiagramIds = new Set(model.diagramReview?.noDiagramChapterIds || []);
    const diagramsDone = activeDiagrams.length
      ? activeDiagrams.every((item) => item.status === "reviewed")
      : Boolean((model.chapters || []).length) && (model.chapters || []).every((chapter) => noDiagramIds.has(chapter.id));
    const complete = completionSnapshot.ready === true && !view.exportDisabled && !completion.busy;
    titleBlock.append(titleLine, el(doc, "p", "final-document-meta", `${complete ? "● 已完成" : "● 正在完善"}　·　交互版本 ${preview.interactionRevision ?? "—"}　·　玩法版本 ${preview.gameplayRevision ?? "—"}　·　共 ${model.chapters?.length || 0} 节`));
    const actions = el(doc, "div", "final-document-title-actions");
    const regenerate = el(doc, "button", "btn", "↺ 重新生成"); regenerate.type = "button"; regenerate.onclick = onRegenerate;
    const markdownButton = el(doc, "button", "btn final-document-markdown", "导出 Markdown"); markdownButton.type = "button"; markdownButton.disabled = !complete; markdownButton.onclick = onMarkdown;
    actions.append(regenerate, markdownButton); titlebar.append(titleBlock, actions); shell.append(titlebar);

    const layout = el(doc, "div", "final-document-layout");
    const groups = outline(model);
    const missingById = new Map(missingChapters.map((item) => [item.id, item]));
    const toc = el(doc, "aside", "final-document-toc");
    const totalSections = (interaction.stages?.length || 0) + (model.chapters?.length || 0);
    const tocHead = el(doc, "div", "final-document-panel-head"); tocHead.append(el(doc, "strong", "", "文档目录"), el(doc, "span", "", `${totalSections} 项`)); toc.append(tocHead);
    const tocBody = el(doc, "nav", "final-document-toc-body");
    const navigationIds = [];
    if ((interaction.stages || []).length) tocBody.append(collapsibleTocGroup(doc, "策划草图", (panel) => {
      const id = "planning-board"; navigationIds.push(id);
      const item = el(doc, "button", "final-document-toc-item", "策划草图"); item.type = "button"; item.onclick = () => focusSection(navigationIds.indexOf(id)); panel.append(item);
    }));
    groups.forEach((group) => {
      tocBody.append(collapsibleTocGroup(doc, group.title, (panel) => group.sections.forEach((subsection) => {
        panel.append(el(doc, "h4", "", subsection.title));
        subsection.chapters.forEach((chapter) => {
          const planner = chapter.plannerSections || {};
          const objectHeading = textOf(planner.attributeHeading);
          const id = `chapter-${chapter.id}`; navigationIds.push(id);
          const item = el(doc, "button", "final-document-toc-item", objectHeading || chapter.scope || "玩法规则"); item.type = "button";
          if (missingById.has(chapter.id)) item.append(el(doc, "span", "final-document-toc-missing", "缺失"));
          item.onclick = () => focusSection(navigationIds.indexOf(id)); panel.append(item);
          const attributeGroups = Array.isArray(planner.attributeSections) ? planner.attributeSections.filter((group) => valuesOf(group?.items || group?.rules || group?.content).length) : [];
          if (attributeGroups.length && planner.attributeHeading) {
            item.onclick = () => focusAnchor(attributeAnchorId(chapter.id, "object"));
            if (chapter.ruleHeading) {
              const ruleItem = el(doc, "button", "final-document-toc-item final-document-toc-leaf", chapter.ruleHeading); ruleItem.type = "button";
              ruleItem.onclick = () => focusAnchor(`final-doc-${chapter.id}-rule-heading`); panel.append(ruleItem);
            }
            attributeGroups.forEach((group, groupIndex) => {
              const title = group.heading || group.title;
              if (!title) return;
              const groupItem = el(doc, "button", "final-document-toc-item final-document-toc-leaf", title); groupItem.type = "button";
              groupItem.onclick = () => focusAnchor(attributeAnchorId(chapter.id, "group", groupIndex)); panel.append(groupItem);
            });
          }
        });
      })));
    }); toc.append(tocBody);

    let activeSectionIndex = 0;
    function focusSection(index) {
      if (!navigationIds.length) return;
      activeSectionIndex = Math.max(0, Math.min(navigationIds.length - 1, index));
      const key = navigationIds[activeSectionIndex];
      const domId = key === "planning-board" ? "final-doc-planning-board" : `final-doc-${key.replace("chapter-", "")}`;
      doc.getElementById?.(domId)?.scrollIntoView?.({ block: "start", behavior: "smooth" });
    }
    function focusAnchor(domId) {
      const target = doc.getElementById?.(domId);
      if (!target) return;
      const view = doc.defaultView || global;
      let container = target.parentElement;
      while (container) {
        const style = view?.getComputedStyle?.(container);
        const overflowY = style?.overflowY || "";
        if (container.scrollHeight > container.clientHeight + 4 && /auto|scroll|overlay/.test(overflowY)) {
          const targetRect = target.getBoundingClientRect();
          const containerRect = container.getBoundingClientRect();
          container.scrollTo?.({ top: container.scrollTop + targetRect.top - containerRect.top - 12, behavior: "auto" });
          return;
        }
        container = container.parentElement;
      }
      target.scrollIntoView?.({ block: "start", behavior: "auto" });
    }
    const reader = el(doc, "main", "final-document-reader");
    const toolbar = el(doc, "div", "final-document-toolbar");
    toolbar.append(el(doc, "span", "", "▣ 完整策划案　·　飞书正文预览"));
    const readerActions = el(doc, "div", "final-document-reader-actions");
    const previous = el(doc, "button", "final-document-reader-button final-document-prev", "‹ 上一项"); previous.type = "button"; previous.onclick = () => focusSection(activeSectionIndex - 1);
    const next = el(doc, "button", "final-document-reader-button final-document-next", "下一项 ›"); next.type = "button"; next.onclick = () => focusSection(activeSectionIndex + 1);
    const fullscreen = el(doc, "button", "final-document-reader-button final-document-fullscreen", "全屏阅读"); fullscreen.type = "button"; fullscreen.onclick = () => reader.requestFullscreen?.();
    readerActions.append(previous, next, fullscreen); toolbar.append(readerActions); reader.append(toolbar);
    const scroll = el(doc, "div", "final-document-scroll"); const content = el(doc, "article", "final-document-content");
    const intro = el(doc, "h1", "final-document-h1", "文档概述"); intro.append(el(doc, "span", "", "第一章")); content.append(intro);
    content.append(el(doc, "p", "final-document-paragraph", preview.analysisNote || "本文档根据已确认的交互流程、玩法规则、参数表格与有效图解生成，作为完整策划案统一导出。"));
    const overview = (model.chapters || []).map((chapter) => chapter.plannerSections?.summary || chapter.plannerSummary || chapter.summary || chapter.oneSentence).find(Boolean);
    if (overview) content.append(el(doc, "p", "final-document-one-liner", `核心玩法一句话：${overview}`));
    const understanding = model.directory?.understanding || {};
    const overviewSummary = textOf(understanding.summary || understanding.overview || understanding.description);
    const overviewRows = [
      ["玩家目标", textOf(understanding.playerGoal || understanding.goal)],
      ["基础操作", textOf(understanding.basicControls || understanding.controls)],
      ["核心循环", textOf(understanding.coreLoop || understanding.loop)],
      ["成长与资源", textOf(understanding.progression || understanding.resourceDriver)],
      ["怎样获胜", textOf(understanding.completion || understanding.winCondition)],
      ["怎样失败", textOf(understanding.failure || understanding.failCondition)],
    ].filter(([, value]) => value);
    const compactGroups = groups.map((group) => group.sections.flatMap((section) => section.chapters).every(sparseChapter));
    const mergeOverview = groups.length === 1 && compactGroups[0] && !overviewRows.length;
    if ((overviewSummary || overviewRows.length) && !mergeOverview) {
      const gameplayOverview = el(doc, "section", "final-document-gameplay-overview");
      gameplayOverview.append(el(doc, "h1", "final-document-h1", "玩法概述"));
      if (overviewSummary) {
        overviewSummary.split(/\n+/).map((line) => line.trim()).filter(Boolean).forEach((line) => {
          gameplayOverview.append(el(doc, "p", "final-document-paragraph final-document-overview-line", line));
        });
      }
      if (overviewRows.length) { const details = el(doc, "dl", "final-document-interaction-details"); overviewRows.forEach(([label, value]) => details.append(el(doc, "dt", "", label), el(doc, "dd", "", value))); gameplayOverview.append(details); }
      content.append(gameplayOverview);
    }
    if ((interaction.stages || []).length) {
      const boardSection = el(doc, "section", "final-document-planning-board"); boardSection.id = "final-doc-planning-board";
      const interactionHeading = el(doc, "h1", "final-document-h1", "策划草图"); interactionHeading.append(el(doc, "span", "", "第二章")); boardSection.append(interactionHeading);
      const safeBoard = global.ExportPreview?.sanitizeBoardSvg?.(interactionPreview?.boardPreviewSvg || "") || "";
      if (safeBoard) {
        const board = el(doc, "div", "final-document-planning-board-canvas"); board.setAttribute("aria-label", "策划草图预览"); board.innerHTML = scopeSvgIds(safeBoard, "planning-board"); boardSection.append(board);
        const svg = board.querySelector?.("svg");
        const nativeWidth = Number(svg?.getAttribute?.("width")) || Number(String(svg?.getAttribute?.("viewBox") || "").split(/\s+/)[2]) || 0;
        if (svg && nativeWidth) { svg.style.width = `${nativeWidth}px`; svg.style.maxWidth = "none"; }
      } else boardSection.append(el(doc, "p", "final-document-paragraph", "策划草图尚未生成，请返回交付物预览重新生成；最终飞书不会用普通交互正文替代画板。"));
      content.append(boardSection);
    }
    groups.forEach((group, groupIndex) => {
      const chapterOffset = (interaction.stages || []).length ? 3 : 2;
      const heading = el(doc, "h1", "final-document-h1", group.title); heading.append(el(doc, "span", "", `第${groupIndex + chapterOffset}章`)); content.append(heading);
      if (mergeOverview && overviewSummary) content.append(el(doc, "p", "final-document-paragraph", overviewSummary));
      const mergedGroup = compactGroups[groupIndex];
      group.sections.forEach((subsection, subsectionIndex) => {
        if (!mergedGroup) content.append(el(doc, "h2", "final-document-h2", `${groupIndex + chapterOffset}.${subsectionIndex + 1} ${subsection.title}`));
        subsection.chapters.forEach((chapter) => { content.append(chapterContent(doc, chapter, model, interaction, { merged: mergedGroup })); if (missingById.has(chapter.id)) content.append(el(doc, "div", "final-document-missing", `${missingById.get(chapter.id).title || chapter.scope}：内容需要补充后才能发布`)); });
      });
    });
    // The browser preview and Feishu must show the same ordered delivery
    // artifact. The server replaces every whiteboard slot with the exact SVG
    // payload later written to that Feishu whiteboard.
    if (preview.deliveryPreviewHtml) content.innerHTML = scopeEmbeddedSvgs(preview.deliveryPreviewHtml, "delivery");
    scroll.append(content); reader.append(scroll);

    const status = el(doc, "aside", "final-document-status");
    const statusHead = el(doc, "div", "final-document-panel-head"); statusHead.append(el(doc, "strong", "", "发布状态"), el(doc, "span", "final-document-ready", complete ? "● 已就绪" : "● 完善中")); status.append(statusHead);
    const statusBody = el(doc, "div", "final-document-status-body"); const decisionChecksDone = !pendingDecisionCards.length; const granularityDone = granularityAudit.passed !== false; const percent = Number(completionSnapshot.percent) || 0;
    const score = el(doc, "section", "final-document-score"); score.append(el(doc, "strong", "", `${percent}%`), el(doc, "span", "", "文档完整度")); const track = el(doc, "div", "final-document-score-track"); track.setAttribute("role", "progressbar"); track.setAttribute("aria-valuemin", "0"); track.setAttribute("aria-valuemax", "100"); track.setAttribute("aria-valuenow", String(percent)); const fill = el(doc, "i"); fill.style.width = `${percent}%`; track.append(fill); score.append(track); statusBody.append(score);
    const checks = el(doc, "section", "final-document-checks"); checks.append(el(doc, "h3", "", "审核章节"));
    const checkItems = (completionSnapshot.checks || []).map((item) => [item.label, item.detail || (item.done ? "已完成" : "未完成"), item.done]);
    checkItems.forEach(([name, count, done]) => { const row = el(doc, "div", `final-document-check${done ? " is-complete" : " is-incomplete"}`); row.append(el(doc, "b", "", done ? "✓" : "○"), el(doc, "span", "", name), el(doc, "small", "", count)); checks.append(row); }); statusBody.append(checks);
    const alignmentChapters = preview.sampleAlignment?.chapters || [];
    if (alignmentChapters.length) {
      statusBody.append(el(doc, "h3", "final-document-side-title", "样例颗粒度逐项对照"));
      const alignmentBox = el(doc, "section", "final-document-alignment");
      alignmentChapters.forEach((chapter) => {
        alignmentBox.append(el(doc, "h4", "final-document-alignment-chapter", chapter.title || "当前章节"));
        (chapter.granularity || []).forEach((item) => {
          const statusLabel = item.status === "satisfied" ? "已覆盖" : item.status === "missing" ? "缺失" : "不适用";
          alignmentBox.append(el(doc, "div", `final-document-alignment-row is-${item.status || "unknown"}`, `${item.label || "检查项"}：${statusLabel}。${item.basis || "尚未提供判定依据。"}`));
        });
      });
      statusBody.append(alignmentBox);
    }
    if (granularityFindings.length) { statusBody.append(el(doc, "h3", "final-document-side-title", "颗粒度缺口")); const gaps = el(doc, "section", "final-document-missing-box final-document-granularity-gaps"); granularityFindings.forEach((item) => gaps.append(el(doc, "div", "", `• ${item.message || "本章节存在有依据但尚未写入正文的内容"}`))); statusBody.append(gaps); }
    if (languageFindings.length) { statusBody.append(el(doc, "h3", "final-document-side-title", "语言与表述问题")); const gaps = el(doc, "section", "final-document-missing-box final-document-language-gaps"); languageFindings.forEach((item) => gaps.append(el(doc, "div", "", `• ${item.message || "本章节的内容选择或表达需要调整"}`))); statusBody.append(gaps); }
    (model.chapters || []).forEach((chapter) => DecisionCards?.render?.({
      root: statusBody, cards: chapter.decisionCards || [], context: { chapterId: chapter.id }, document: doc,
      onResolve: (value) => onDecisionOperation([DecisionCards.resolveOperation(value)]),
      onSkip: (value) => onDecisionOperation([DecisionCards.skipOperation(value)]),
    }));
    if (missingChapters.length) { statusBody.append(el(doc, "h3", "final-document-side-title", "缺失内容")); const missing = el(doc, "section", "final-document-missing-box"); missingChapters.forEach((item) => missing.append(el(doc, "div", "", `• ${item.title || "待补充章节"}`))); statusBody.append(missing); }
    statusBody.append(el(doc, "h3", "final-document-side-title", "文档统计")); const stats = el(doc, "section", "final-document-stats");
    [[model.chapters?.length || 0, "章节数"], [(model.tables || []).filter((item) => item.status !== "deleted").reduce((sum, item) => sum + (item.rows?.length || 0), 0), "参数项"], [interaction?.stages?.length || 0, "交互流程"], [(model.diagrams || []).filter((item) => item.status !== "deleted").length, "配图"]].forEach(([value, label]) => { const cell = el(doc, "div"); cell.append(el(doc, "strong", "", String(value)), el(doc, "span", "", label)); stats.append(cell); }); statusBody.append(stats);
    statusBody.append(el(doc, "h3", "final-document-side-title", "生成日志")); const log = el(doc, "div", "final-document-log"); (completion.logs || []).slice(-7).forEach((entry) => log.append(el(doc, "div", "", `✓ ${entry.message || "已完成"}`))); if (!log.children.length) log.append(el(doc, "div", "", "✓ 文档预览已生成")); statusBody.append(log); status.append(statusBody);
    const pendingChecks = (completionSnapshot.checks || []).filter((item) => !item.done);
    const gateSummary = el(doc, "section", "final-document-gate-summary");
    gateSummary.setAttribute("role", "status");
    gateSummary.setAttribute("aria-live", "polite");
    if (complete) {
      gateSummary.textContent = "全部门禁已完成，可以导出到飞书。";
    } else {
      const pendingNames = pendingChecks.slice(0, 2).map((item) => item.label).filter(Boolean);
      const pendingDetail = pendingNames.length ? ` 当前阻塞项：${pendingNames.join("、")}。` : "";
      gateSummary.textContent = `门禁：当前还需完成 ${pendingChecks.length || 1} 项。${pendingDetail}点击“处理未完成项”会跳到第一个阻塞步骤。`;
    }
    status.append(gateSummary);
    const footer = el(doc, "footer", "final-document-footer");
    if (complete) {
      const publicationState = el(doc, "div", "feishu-publication final-document-feishu-state final-document-feishu-action");
      publicationState.setAttribute("aria-live", "polite");
      publicationState.innerHTML = global.FeishuPublish?.renderFeishuPublication?.(publication, true)
        || '<button class="btn primary" type="button" data-feishu-action="new_version">导出到飞书</button>';
      publicationState.onclick = (event = {}) => {
        const action = event.target?.closest?.("[data-feishu-action]");
        if (action) onFeishuAction(action.dataset.feishuAction);
        else onExport();
      };
      footer.append(publicationState);
    } else {
      const pendingLabel = pendingDecisionCards.length ? `处理 ${pendingDecisionCards.length} 项策划决策` : "处理未完成项";
      const resolve = el(doc, "button", "btn primary final-document-resolve", completion.busy ? "正在自动补全" : pendingLabel); resolve.type = "button"; resolve.disabled = Boolean(completion.busy);
      resolve.onclick = pendingDecisionCards.length
        ? () => onResolvePending({ chapterId: pendingDecisionCards[0].chapterId, cardId: pendingDecisionCards[0].id })
        : onResolveIncomplete;
      footer.append(resolve);
    }
    status.append(footer);
    layout.append(toc, reader, status); shell.append(layout); root.append(shell); return shell;
  }

  const api = { outline, render };
  if (typeof module !== "undefined") module.exports = api; else global.FinalDocumentPreview = api;
})(typeof window !== "undefined" ? window : globalThis);
