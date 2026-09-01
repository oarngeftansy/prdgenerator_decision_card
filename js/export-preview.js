(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.ExportPreview = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  function viewModel(preview, model, mutationBlocked = false) {
    return { ...preview, referenceBoardSummary: (preview.referenceBoardSummary || []).filter((item) => item.key === "planning"), mutationBlocked: Boolean(mutationBlocked), exportDisabled: Boolean(mutationBlocked) || !preview.exportReady || preview.revision !== model.revision };
  }

  function combinedViewModel(preview, models, mutationBlocked = false) {
    const interaction = models?.interaction;
    const gameplay = models?.gameplay;
    const revisionsMatch = preview?.interactionRevision === interaction?.revision
      && preview?.gameplayRevision === gameplay?.revision;
    return { ...preview, referenceBoardSummary: (preview?.referenceBoardSummary || []).filter((item) => item.key === "planning"), mutationBlocked: Boolean(mutationBlocked), exportDisabled: Boolean(mutationBlocked) || !preview?.exportReady || !revisionsMatch };
  }

  function autoCompletionView(completion = {}) {
    const status = completion?.status || "idle";
    const progress = Number.isFinite(completion.progress) ? Math.max(0, Math.min(100, Math.round(completion.progress))) : 0;
    if (["queued", "running", "generating"].includes(status)) return {
      busy: true,
      progress,
      message: "正在自动补全已确认的玩法章节",
      detail: "系统会保留已确认结论，并根据原始素材补齐规则、验证方式和边界说明。",
    };
    if (status === "failed") return {
      busy: false,
      progress: 0,
      message: "自动补全失败",
      detail: "请重试；系统不会覆盖已经确认的策划结论。",
    };
    return { busy: false, progress, message: "", detail: "" };
  }

  function generationView(generation = {}) {
    const status = generation?.status || "idle";
    const busy = ["queued", "running", "generating"].includes(status);
    if (busy) {
      const progress = Number.isFinite(generation.progress) ? Math.max(0, Math.min(100, Math.round(generation.progress))) : 0;
      const latestLog = Array.isArray(generation.logs)
        ? [...generation.logs].reverse().find((item) => typeof item?.message === "string" && item.message.trim())
        : null;
      const detail = latestLog?.message?.trim() || (progress <= 5 ? "正在准备截图和模型请求" : "正在分析素材并整理玩法目录");
      return { busy: true, progress, message: "正在生成玩法章节", detail, failed: false };
    }
    if (status === "failed") {
      const progress = Number.isFinite(generation.progress) ? Math.max(0, Math.min(100, Math.round(generation.progress))) : 0;
      const issues = Array.isArray(generation.qualityIssues)
        ? generation.qualityIssues.filter((item) => typeof item === "string" && item.trim()).slice(0, 3)
        : [];
      const detail = issues.length
        ? `未通过：${issues.join("；")}。请重试；目录和已有审核内容不会丢失。`
        : "点击下方按钮重新生成玩法章节。";
      return { busy: false, progress, message: `生成失败：${generation.error || "视觉模型未能生成可用内容"}。`, detail, failed: true };
    }
    return { busy: false, progress: 0, message: "", detail: "", failed: false };
  }

  function generationProgress(view) {
    const section = element("section", "", "gameplay-generation-progress");
    section.setAttribute("aria-live", "polite");
    const heading = element("div", "", "gameplay-generation-progress-heading");
    heading.append(element("strong", view.message), element("span", `${view.progress}%`));
    const track = element("div", "", "gameplay-generation-progress-track");
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", "玩法章节生成进度");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", "100");
    track.setAttribute("aria-valuenow", String(view.progress));
    const bar = element("div", "", "gameplay-generation-progress-bar");
    bar.style.width = `${view.progress}%`;
    track.append(bar);
    section.append(heading, track, element("p", view.detail, "review-preview-muted"));
    return section;
  }

  function generationFailure(view) {
    const section = element("section", "", "gameplay-generation-progress gameplay-generation-failure");
    section.setAttribute("role", "alert");
    section.append(
      element("strong", view.message, "export-preview-blocked"),
      element("p", view.detail, "review-preview-muted")
    );
    return section;
  }

  function routeForIssue(id) {
    if (id.startsWith("STG-")) return { view: "stage", stageId: id };
    if (id.startsWith("TRN-") || id === "FLOW_NOT_CONFIRMED") return { view: "flow", transitionId: id.startsWith("TRN-") ? id : null };
    if (id.startsWith("CST-")) return { view: "flow", selection: { type: "constraint", id } };
    const domain = id.startsWith("NAR-") ? "narrative" : id.startsWith("GDE-") ? "guidance" : id.startsWith("RDT-") ? "redDots" : null;
    if (domain) return { view: "flow", issueId: id };
    return { view: "flow", issueId: id };
  }

  function sanitizeBoardSvg(svg) {
    if (typeof DOMParser === "undefined" || typeof XMLSerializer === "undefined" || typeof svg !== "string") return "";
    const document = new DOMParser().parseFromString(svg, "image/svg+xml");
    const root = document.documentElement;
    if (root.localName !== "svg" || document.querySelector("parsererror")) return "";
    root.querySelectorAll("script, style, foreignObject, iframe, object, embed").forEach((node) => node.remove());
    [root, ...root.querySelectorAll("*")].forEach((node) => {
      [...node.attributes].forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim();
        const isImageData = /^data:image\/(?:png|jpeg|gif|webp);base64,/i.test(value);
        if (name === "style" || name.startsWith("on") || (/url\(/i.test(value) && !/^url\(#[\w-]+\)$/i.test(value)) || ((name === "href" || name === "xlink:href") && value && !value.startsWith("#") && !isImageData)) node.removeAttribute(attribute.name);
      });
    });
    return new XMLSerializer().serializeToString(root);
  }

  function alignFirstPageSpec(board) {
    if (!board?.isConnected || typeof board.querySelector !== "function" || typeof board.getBoundingClientRect !== "function") return;
    const page = board.querySelector('[data-node-kind="page-spec"]');
    if (!page || typeof page.getBoundingClientRect !== "function") return;
    const maxScrollLeft = Number(board.scrollWidth) - Number(board.clientWidth);
    const currentScrollLeft = Number(board.scrollLeft);
    const boardRect = board.getBoundingClientRect();
    const pageRect = page.getBoundingClientRect();
    if (!Number.isFinite(maxScrollLeft) || !Number.isFinite(currentScrollLeft) || !Number.isFinite(boardRect?.left) || !Number.isFinite(pageRect?.left)) return;
    const target = Math.max(0, Math.min(Math.max(0, maxScrollLeft), currentScrollLeft + pageRect.left - boardRect.left - 24));
    board.scrollLeft = target;
  }

  function clampBoardZoom(value) { return Math.max(0.35, Math.min(5, Number(value) || 1)); }

  function loadBoardViewState(storage, key) {
    try {
      const value = key && storage?.getItem ? JSON.parse(storage.getItem(key) || "{}") : {};
      return { zoom: clampBoardZoom(value.zoom || 1.15), left: Math.max(0, Number(value.left) || 0), top: Math.max(0, Number(value.top) || 0) };
    } catch (_) { return { zoom: 1.15, left: 0, top: 0 }; }
  }

  function saveBoardViewState(storage, key, value) {
    if (!key || !storage?.setItem) return;
    storage.setItem(key, JSON.stringify({ zoom: clampBoardZoom(value.zoom), left: Math.max(0, Number(value.left) || 0), top: Math.max(0, Number(value.top) || 0) }));
  }

  function continueDisabled(view, hasContinue, busy) {
    if (!hasContinue) return Boolean(view?.exportDisabled);
    return Boolean(view?.mutationBlocked) || Boolean(busy);
  }

  function boardControls(board, storage, storageKey) {
    const toolbar = element("div", "", "export-preview-board-toolbar");
    const saved = loadBoardViewState(storage, storageKey);
    const zoomLabel = element("span", `${Math.round(saved.zoom * 100)}%`, "export-preview-board-zoom");
    let zoom = saved.zoom;
    const persist = () => saveBoardViewState(storage, storageKey, { zoom, left: board.scrollLeft, top: board.scrollTop });
    const apply = (next, shouldPersist = true) => {
      zoom = clampBoardZoom(next);
      const svg = board.querySelector?.("svg");
      if (svg?.style) svg.style.zoom = String(zoom);
      zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
      if (shouldPersist) persist();
    };
    const action = (label, handler) => { const control = element("button", label, "btn"); control.type = "button"; control.onclick = handler; return control; };
    toolbar.append(
      action("缩小", () => apply(zoom - 0.15)), zoomLabel,
      action("放大", () => apply(zoom + 0.15)),
      action("适应窗口", () => { const svg = board.querySelector?.("svg"); const natural = Number(svg?.viewBox?.baseVal?.width) || Number(svg?.getAttribute?.("width")) || 1380; apply((Number(board.clientWidth) - 28) / natural); board.scrollTo?.({ left: 0, top: 0 }); }),
      action("全屏查看", () => board.requestFullscreen?.())
    );
    board.addEventListener?.("wheel", (event) => {
      if (event.ctrlKey) { event.preventDefault?.(); apply(zoom + (event.deltaY < 0 ? 0.1 : -0.1)); }
      else if (event.shiftKey) { event.preventDefault?.(); board.scrollLeft += event.deltaY; }
    }, { passive: false });
    board.addEventListener?.("scroll", persist, { passive: true });
    board.__restoreBoardView = () => { board.scrollLeft = saved.left; board.scrollTop = saved.top; };
    apply(zoom, false);
    return toolbar;
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function issueList(title, ids, model, onRoute) {
    const section = element("section", "", "export-preview-issues");
    section.append(element("h4", title));
    if (!ids.length) section.append(element("p", "无", "review-preview-muted"));
    ids.forEach((id) => {
      const constraint = (model.crossStateConstraints || []).find((item) => item.id === id);
      const friendly = id === "COMPETITOR_BOARD_PENDING" ? "本次未提供竞品参考（可选，不影响导出）" : constraint?.text || "返回处理相关问题";
      const button = element("button", friendly, "btn");
      button.type = "button";
      button.setAttribute("aria-label", friendly);
      button.onclick = () => onRoute(routeForIssue(id));
      section.append(button);
    });
    return section;
  }

  function summaryList(view) {
    const section = element("section", "", "export-preview-summary");
    section.append(element("h4", "交付内容"));
    const list = element("ul", "", "export-preview-summary-list");
    (view.referenceBoardSummary || []).filter((summary) => summary.key === "planning").forEach((summary) => {
      list.append(element("li", `策划草图：已生成`));
    });
    section.append(list);
    return section;
  }

  function renderLoading(root, message = "正在整理页面关系") {
    root.replaceChildren();
    root.classList.add("interaction-page-preview", "interaction-page-loading");
    const nav = element("aside", "交互页面", "interaction-loading-nav");
    const canvas = element("main", "正在生成页面预览，请稍候…", "interaction-loading-canvas");
    const detail = element("aside", "", "interaction-loading-detail");
    detail.append(element("h3", "页面信息"), element("p", message), element("p", "门禁：等待策划草图生成完成并检查页面关系。完成后即可进入规则审核。", "interaction-step-gate"));
    const next = element("button", "生成完成后进入规则审核", "btn primary export-preview-continue");
    next.type = "button";
    next.disabled = true;
    next.setAttribute("aria-describedby", "interaction-preview-loading-gate");
    const gate = element("p", "正在生成策划草图，暂时不能进入下一步。", "export-preview-blocked");
    gate.id = "interaction-preview-loading-gate";
    root.append(nav, canvas, detail, gate, next);
  }

  function renderRecovery(root, { failed = false, message = "策划草图尚未生成", onRetry = () => {} } = {}) {
    root.replaceChildren();
    root.classList.add("interaction-page-preview", "interaction-page-recovery");
    const contextBar = element("header", "交互交付物 / 策划草图预览", "review-context-bar");
    const nav = element("aside", "", "interaction-loading-nav");
    nav.append(
      element("h3", "交互页面"),
      element("button", "当前页面关系", "interaction-recovery-page is-active"),
      element("button", "页面局部说明", "interaction-recovery-page"),
      element("button", "页面跳转关系", "interaction-recovery-page")
    );
    const canvas = element("main", "", "interaction-preview-empty-canvas");
    canvas.append(element("h3", failed ? "策划草图生成失败" : "策划草图尚未生成"), element("p", message, "review-preview-muted"));
    const retry = element("button", failed ? "重新生成策划草图" : "生成策划草图", "btn primary interaction-preview-retry");
    retry.type = "button";
    retry.onclick = onRetry;
    canvas.append(retry);
    const detail = element("aside", "", "interaction-loading-detail");
    detail.append(
      element("h3", "生成状态"),
      element("p", failed ? "需要重新生成" : "等待生成", "interaction-recovery-status"),
      element("p", "已上传的素材和审核结果会继续保留。生成完成后，可检查页面关系、局部说明与原始截图。"),
      element("p", "门禁：先成功生成策划草图；检查页面关系后再进入规则审核。", "interaction-step-gate")
    );
    root.append(contextBar, nav, canvas, detail);
  }

  function render({ root, preview, model, mutationBlocked = false, onRoute = () => {}, onPublish = () => {}, onContinue = null, onRetry = null, continueBusy = false, continueLabel = "", generation = null, boardStateKey = "", boardStateStorage = typeof localStorage !== "undefined" ? localStorage : null }) {
    const view = viewModel(preview, model, mutationBlocked);
    const safeSvg = sanitizeBoardSvg(view.boardPreviewSvg);
    if (!safeSvg) {
      renderRecovery(root, {
        failed: true,
        message: "策划草图暂时无法显示。点击重新生成即可继续，不需要重新上传素材。",
        onRetry: onRetry || (() => {}),
      });
      return view;
    }
    root.replaceChildren();
    root.classList.add("interaction-page-preview");
    const contextBar = element("header", "", "review-context-bar");
    contextBar.append(element("strong", "交互交付物"), element("span", "当前素材 / 页面与交互 / 策划草图预览"));
    root.append(contextBar);
    const header = element("div", "", "export-preview-header");
    header.append(element("h3", "页面信息"));
    header.append(element("p", "请检查策划草图；确认后继续审核玩法规则。", "review-preview-muted"));
    root.append(header);
    const relation = summaryList(view);
    relation.classList.add("interaction-page-relations");
    const relationTitle = relation.querySelector?.("h4");
    if (relationTitle) relationTitle.textContent = "关联交互";
    root.append(relation);
    const availability = view.mutationBlocked
      ? "竞品素材正在保存或等待重试；成功后才能重新生成预览并导出。"
      : view.exportDisabled ? "当前内容还不能发布；请先补全下方内容，或重新生成预览。" : "交互内容已经确认，可以继续审核玩法规则。";
    root.append(element("p", availability, view.exportDisabled ? "export-preview-blocked" : "export-preview-ready"));
    const board = element("div", "", "export-preview-board");
    board.setAttribute("aria-label", "策划草图预览");
    if (safeSvg) board.innerHTML = safeSvg;
    else board.append(element("p", "策划草图暂时无法显示，请重新生成预览。", "review-preview-muted"));
    const boardShell = element("section", "", "export-preview-board-shell");
    boardShell.append(boardControls(board, boardStateStorage, boardStateKey), board); root.append(boardShell);
    if (safeSvg) {
      alignFirstPageSpec(board);
      if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => {
        alignFirstPageSpec(board);
        board.__restoreBoardView?.();
        boardShell.scrollIntoView({ block: "start", behavior: "auto" });
      });
    }
    root.append(issueList("确认前需要补全", view.blockerIds || [], model, onRoute));
    const generationState = generationView(generation || {});
    if (generationState.busy) root.append(generationProgress(generationState));
    else if (generationState.message) root.append(generationFailure(generationState));
    const resolvedContinueLabel = continueBusy ? `正在生成玩法章节 ${generationState.progress}%…` : continueLabel || (generationState.failed ? "重新生成玩法章节" : "确认交互，生成玩法章节");
    const primary = element("button", onContinue ? resolvedContinueLabel : "发布到飞书", `btn primary${onContinue ? " export-preview-continue" : ""}`);
    primary.type = "button";
    primary.disabled = continueDisabled(view, Boolean(onContinue), continueBusy);
    primary.onclick = () => onContinue ? onContinue(view) : onPublish(view);
    if (continueBusy) primary.setAttribute("aria-busy", "true");
    root.append(primary);
    return view;
  }

  return { viewModel, combinedViewModel, autoCompletionView, generationView, routeForIssue, sanitizeBoardSvg, alignFirstPageSpec, clampBoardZoom, loadBoardViewState, saveBoardViewState, continueDisabled, renderLoading, renderRecovery, render };
});
