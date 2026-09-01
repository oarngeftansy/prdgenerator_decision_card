(function (root) {
function el(doc, tag, className = "", text = "") { const node = doc.createElement(tag); if (className) node.className = className; if (text) node.textContent = text; return node; }
function sourceUrl(source, resolveSourceUrl) { return resolveSourceUrl(source?.imageUrl || source?.url || ""); }
function meaningful(value) {
  const text = String(value || "").trim();
  if (!text || /待确认|未知|推测|可能|unknown|inferred/i.test(text)) return "";
  if (!/[\p{L}\p{N}]/u.test(text) || (!/[\u3400-\u9fff]/u.test(text) && /[A-Za-z]/.test(text))) return "";
  return text.replace(/[（(][^）)]*$/g, "").trim();
}
function transitionFrom(model, stageId) { return (model.transitions || []).find(item => item.included !== false && item.sourceStageId === stageId) || null; }
function validComponent(component) {
  const anchor = component?.anchor || {};
  return Number.isInteger(component?.number) && component.number > 0
    && meaningful(component.name) && meaningful(component.purpose)
    && Number.isFinite(anchor.x) && Number.isFinite(anchor.y)
    && anchor.x >= 0 && anchor.x <= 1 && anchor.y >= 0 && anchor.y <= 1;
}
function annotationPages(model) {
  const sourceIds = new Set(Object.keys(model.sources || {}));
  const stageIds = new Set((model.stages || []).map(stage => stage.id));
  return (model.ueFlowAnnotations?.pages || []).filter(page => sourceIds.has(page.frameId) && stageIds.has(page.stageId)
    && page.components?.length >= 1 && page.components.length <= 4
    && new Set(page.components.map(component => component.number)).size === page.components.length
    && page.components.every(validComponent));
}
function annotationLoops(model) {
  const pages = annotationPages(model);
  const pageStageIds = pages.map(page => page.stageId);
  const expected = new Set(pageStageIds);
  const pageById = new Map(pages.map(page => [page.id, page]));
  const transitionById = new Map((model.ueFlowAnnotations?.transitions || []).map(transition => [transition.id, transition]));
  return (model.ueFlowAnnotations?.loops || []).filter(loop => {
    if (!meaningful(loop.title) || !loop.groups?.length) return false;
    const grouped = loop.groups.flatMap(group => group.stageIds || []);
    return loop.groups.every(group => {
      const entry = pageById.get(group.entryPageId);
      const exit = transitionById.get(group.exitTransitionId);
      const source = pageById.get(exit?.sourcePageId);
      return meaningful(group.title) && group.stageIds?.length
        && entry && group.stageIds.includes(entry.stageId)
        && exit && source && group.stageIds.includes(source.stageId);
    })
      && grouped.length === new Set(grouped).size
      && grouped.length === expected.size
      && grouped.every(stageId => expected.has(stageId));
  });
}
function annotationTransitions(model) {
  const pages = annotationPages(model);
  const pageById = new Map(pages.map(page => [page.id, page]));
  const externalById = new Map((model.ueFlowAnnotations?.externalTargets || []).map(target => [target.id, target]));
  return (model.ueFlowAnnotations?.transitions || []).map(transition => {
    const source = pageById.get(transition.sourcePageId);
    const target = pageById.get(transition.targetPageId);
    const external = externalById.get(transition.targetExternalId);
    const triggerType = transition.triggerType || "control";
    const trigger = source?.components?.find(component => component.number === transition.triggerComponentNumber);
    const validTrigger = triggerType === "system" ? meaningful(transition.triggerLabel) : triggerType === "control" && trigger;
    const valid = String(transition.id || "").trim() && source && (target || external) && validTrigger
      && ["forward", "return", "branch"].includes(transition.direction)
      && meaningful(transition.condition);
    if (!valid) return null;
    return external ? { ...transition, targetTitle: meaningful(external.title) } : transition;
  }).filter(Boolean);
}
function authoritativeSource(model, stage, usedFrames = new Set()) {
  const transition = transitionFrom(model, stage.id);
  if (root.FlowReview?.sourceForStage) {
    const selected = root.FlowReview.sourceForStage(model, stage, transition, usedFrames);
    if (selected.frameId && !selected.supplemental && meaningful(selected.source?.pageInfo?.purpose)) return selected;
  }
  const candidates = [transition?.sourceFrameId, ...(stage.representativeFrames || []).map(item => item.frameId)].filter(Boolean);
  for (const frameId of [...new Set(candidates)]) {
    const source = model.sources?.[frameId];
    if (!usedFrames.has(frameId) && source?.stageId === stage.id && meaningful(source?.pageInfo?.purpose)) return { frameId, source };
  }
  for (const frameId of [...new Set((stage.representativeFrames || []).map(item => item.frameId).filter(Boolean))]) {
    const source = model.sources?.[frameId];
    if (!usedFrames.has(frameId) && source?.stageId === stage.id && sourceUrl(source, value => value)) {
      return { frameId, source, titleFromStage: true };
    }
  }
  return { frameId: "", source: {}, gap: "当前页面没有可核验的标题—截图绑定" };
}
function pageCopy(source = {}, stage = {}, previousStage = null, nextStage = null, frameId = "") {
  const purpose = meaningful(source?.pageInfo?.purpose);
  return [
    `页面职责：${stage.name || "当前页面"}`,
    purpose ? `画面内容：${purpose}` : `代表画面：${frameId || "素材缺失"}`,
    previousStage ? `由「${previousStage.name}」进入本页` : "当前流程入口",
    nextStage ? `完成本页后进入「${nextStage.name}」` : "当前流程终点",
  ];
}
function render({ root: mount, model = {}, resolveSourceUrl = value => value, onBack = () => {}, onConfirm = () => {}, onRegenerate = () => {} }) {
  const doc = mount.ownerDocument || document; mount.replaceChildren();
  const shell = el(doc, "div", "ue-review-layout"); const directory = el(doc, "aside", "ue-review-directory"); directory.append(el(doc, "h3", "", "流程目录"));
  const canvasPanel = el(doc, "section", "ue-review-main"); const toolbar = el(doc, "header", "ue-review-toolbar"); toolbar.append(el(doc, "strong", "", "UE 流转图审核"), el(doc, "span", "", "截图、编号和连线来自已确认交互数据；本页只读。")); canvasPanel.append(toolbar);
  const canvas = el(doc, "div", "ue-flow-canvas"); canvas.id = "ueFlowCanvas"; const stages = [...(model.stages || [])].sort((a,b)=>(a.order||0)-(b.order||0));
  const pages = annotationPages(model);
  if (pages.length) {
    const transitions = annotationTransitions(model);
    const loop = annotationLoops(model)[0] || null;
    if (loop) {
      directory.append(el(doc, "p", "ue-flow-loop-title", loop.title));
      canvas.append(el(doc, "h3", "ue-flow-loop-title", loop.title));
    }
    const groupByStage = new Map((loop?.groups || []).flatMap(group => group.stageIds.map(stageId => [stageId, group])));
    const renderedGroups = new Set();
    pages.forEach((page, pageIndex) => {
      const group = groupByStage.get(page.stageId);
      if (group && !renderedGroups.has(group.id)) {
        renderedGroups.add(group.id);
        directory.append(el(doc, "p", "ue-flow-stage-group-title", group.title));
        canvas.append(el(doc, "h4", "ue-flow-stage-group-title", group.title));
      }
      const nav = el(doc, "button", `ue-flow-directory-item${pageIndex === 0 ? " is-active" : ""}`, page.title); nav.type = "button"; directory.append(nav);
      const source = model.sources?.[page.frameId] || {}; const card = el(doc, "article", "ue-flow-page-card"); card.dataset.stageId = page.stageId; card.dataset.frameId = page.frameId; card.append(el(doc, "h4", "", page.title));
      const shot = el(doc, "div", "ue-flow-screen"); const img = el(doc, "img", "ue-flow-screen-image"); img.src = sourceUrl(source, resolveSourceUrl); img.alt = `${page.title}截图`; shot.append(img);
      page.components.slice().sort((a,b)=>a.number-b.number).forEach(component => { const marker=el(doc,"i","ue-flow-marker",String(component.number)); marker.style.left=`calc(${component.anchor.x*100}% - 12px)`; marker.style.top=`calc(${component.anchor.y*100}% - 12px)`; marker.title=`${component.name}：${component.purpose}`; shot.append(marker); }); card.append(shot);
      const rules=el(doc,"ol","ue-flow-numbered-rules"); page.components.slice().sort((a,b)=>a.number-b.number).forEach(component=>{const item=el(doc,"li"); item.append(el(doc,"b","",component.name),doc.createTextNode(`：${component.purpose}`)); rules.append(item);}); card.append(rules); canvas.append(card);
      const outgoing=transitions.filter(item=>item.sourcePageId===page.id);
      outgoing.forEach(item=>{const symbol=item.direction==="return"?"↩":item.direction==="branch"?"↱":"→";const edge=el(doc,"div",`ue-flow-readonly-edge is-${item.direction}`,symbol);edge.dataset.transitionId=item.id;const targetTitle=item.targetTitle||pages.find(target=>target.id===item.targetPageId)?.title||item.targetPageId;const trigger=item.triggerType==="system"?item.triggerLabel:`控件${item.triggerComponentNumber}`;edge.setAttribute("aria-label",`${trigger}；${item.condition}：${item.direction==="return"?"返回":"前往"}${targetTitle}`);edge.title=edge.getAttribute("aria-label");canvas.append(edge);}); nav.onclick=()=>card.scrollIntoView?.({behavior:"smooth",inline:"center"});
    });
    canvasPanel.append(canvas); const detail=el(doc,"aside","ue-review-detail"); detail.append(el(doc,"h3","","审核依据")); [["来源","P2 截图 + 控件级视觉拆解"],["图内标注","编号固定指向截图内的具体按钮、信息区或功能区"],["审核状态",model.ueFlowAnnotations.status === "ai_draft" ? "AI 草稿：请核对控件名称、位置和作用" : "已审核"]].forEach(([label,value])=>{const row=el(doc,"div","ue-review-detail-row");row.append(el(doc,"b","",label),el(doc,"p","",value));detail.append(row);});
    shell.append(directory,canvasPanel,detail); const footer=el(doc,"footer","ue-review-footer");const back=el(doc,"button","btn","返回 P2-1 修改");const regen=el(doc,"button","btn","重新生成");const confirm=el(doc,"button","btn primary","确认 UE 流转图并进入 P3");back.onclick=onBack;regen.onclick=onRegenerate;confirm.onclick=onConfirm;footer.append(back,regen,confirm);mount.append(shell,footer);return;
  }
  const usedFrames = new Set(); const bindingGaps = [];
  stages.forEach((stage, stageIndex) => {
    const selected = authoritativeSource(model, stage, usedFrames); const frameId = selected.frameId; const source = selected.source; if (frameId) usedFrames.add(frameId); else bindingGaps.push(stage.name || stage.id);
    const displayTitle = meaningful(source?.pageInfo?.purpose) || stage.name || `页面 ${stageIndex + 1}`;
    const nav = el(doc, "button", `ue-flow-directory-item${stageIndex === 0 ? " is-active" : ""}`, displayTitle); nav.type = "button"; directory.append(nav);
    const card = el(doc, "article", "ue-flow-page-card"); card.dataset.stageId = stage.id || ""; card.dataset.frameId = frameId; card.append(el(doc, "h4", "", displayTitle));
    const shot = el(doc, "div", `ue-flow-screen${frameId ? "" : " is-missing"}`);
    if (frameId) { const img = el(doc, "img", "ue-flow-screen-image"); img.src = sourceUrl(source, resolveSourceUrl); img.alt = `${stage.name || "页面"}代表截图`; shot.append(img); }
    else shot.append(el(doc, "p", "ue-flow-missing-copy", "未找到与本页标题一致的已确认截图"));
    const copies = pageCopy(source, { ...stage, name: displayTitle }, stages[stageIndex - 1] || null, stages[stageIndex + 1] || null, frameId);
    copies.forEach((copy, index) => { const marker = el(doc, "i", `ue-flow-marker marker-${index + 1}`, String(index + 1)); marker.title = copy; shot.append(marker); }); card.append(shot);
    const rules = el(doc, "ol", "ue-flow-numbered-rules"); copies.forEach(copy => rules.append(el(doc, "li", "", copy))); card.append(rules); canvas.append(card);
    if (stageIndex < stages.length - 1) { const edge = el(doc, "div", "ue-flow-readonly-edge", "→"); edge.setAttribute("aria-label", "页面流转"); canvas.append(edge); }
    nav.onclick = () => { canvas.querySelector(`[data-stage-id="${stage.id}"]`)?.scrollIntoView?.({behavior:"smooth",inline:"center"}); };
  });
  canvasPanel.append(canvas); const detail = el(doc, "aside", "ue-review-detail"); detail.append(el(doc, "h3", "", "审核依据"));
  [["来源", "P2-1 已确认 stages / transitions / representativeFrames"], ["图内标注", "每张截图固定显示 1 / 2 / 3 / 4，并与下方说明对应"], ["交付", "网页与飞书原生画板共用同一 fingerprint"]].forEach(([label,value])=>{ const row=el(doc,"div","ue-review-detail-row"); row.append(el(doc,"b","",label),el(doc,"p","",value)); detail.append(row); });
  if (bindingGaps.length) { const row=el(doc,"div","ue-review-detail-row ue-flow-binding-gaps"); row.append(el(doc,"b","","素材缺口"),el(doc,"p","",`${bindingGaps.join("、")}缺少可信的标题—截图绑定，请返回 P2-1 补充。`)); detail.append(row); }
  shell.append(directory, canvasPanel, detail); const footer=el(doc,"footer","ue-review-footer"); const back=el(doc,"button","btn","返回 P2-1 修改"); const regen=el(doc,"button","btn","重新生成"); const confirm=el(doc,"button","btn primary","确认 UE 流转图并进入 P3"); back.onclick=onBack; regen.onclick=onRegenerate; confirm.onclick=onConfirm; if(bindingGaps.length){confirm.disabled=true;confirm.title="仍有标题—截图绑定缺口，请先返回 P2-1 补充";} footer.append(back,regen,confirm); mount.append(shell,footer);
}
const api={render,pageCopy,meaningful,authoritativeSource,validComponent,annotationPages,annotationLoops,annotationTransitions}; if(typeof module!=="undefined")module.exports=api; else root.UeFlowReview=api;
}(typeof window!=="undefined"?window:globalThis));
