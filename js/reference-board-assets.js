(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReferenceBoardAssets = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  const BOARD_KEYS = ["planning", "competitor"];
  const LABELS = { planning: "策划草图", competitor: "竞品参考" };

  function manifest(files) { return JSON.stringify(Array.from(files || [], (file) => file.name)); }

  function summaries(boards = {}, planningCount = 0) {
    return BOARD_KEYS.map((key) => {
      const board = boards[key] || {};
      const assets = Array.isArray(board.assets) ? board.assets : [];
      const missingCount = assets.filter((asset) => asset.status === "missing").length;
      const status = missingCount ? "missing" : board.status || (key === "planning" ? "generated" : "pending");
      return {
        key, title: LABELS[key], label: status === "missing" ? "缺失" : status === "pending" ? "本次未提供" : key === "planning" ? "自动生成" : "已就绪", editable: key !== "planning",
        count: key === "planning" ? planningCount : assets.length,
        missingCount, status,
        assets,
      };
    });
  }

  function movedIds(assets, fromIndex, toIndex) {
    const ids = (assets || []).map((asset) => asset.id);
    if (fromIndex < 0 || toIndex < 0 || fromIndex >= ids.length || toIndex >= ids.length || fromIndex === toIndex) return ids;
    const [moved] = ids.splice(fromIndex, 1);
    ids.splice(toIndex, 0, moved);
    return ids;
  }

  function boardStatus(board, transient) {
    if (transient?.status === "uploading") return { status: "uploading", message: "正在保存素材…" };
    if (transient?.status === "failed") return { status: "failed", message: transient.error || "素材保存失败，请重试。" };
    const summary = typeof board === "object" && "key" in board ? board : summaries({ competitor: board }, 0)[1];
    return { status: summary.status, message: statusText(summary) };
  }

  function element(tag, text = "", attrs = {}) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    Object.entries(attrs).forEach(([name, value]) => node.setAttribute(name, String(value)));
    return node;
  }

  function button(text, callback, { disabled = false, label = text, className = "reference-board-action" } = {}) {
    const node = element("button", text, { type: "button", "aria-label": label });
    node.className = className;
    node.disabled = Boolean(disabled);
    node.addEventListener("click", callback);
    return node;
  }

  function statusText(summary) {
    if (summary.status === "missing") return `缺失 ${summary.missingCount} 张，可替换恢复`;
    if (summary.status === "pending") return "本次未提供竞品参考（可选，不影响导出）";
    return summary.key === "planning" ? `代表画面 ${summary.count} 张（自动生成）` : `已就绪 ${summary.count} 张`;
  }

  async function mutate(workspace, card, boardKey, request, assetId = null) {
    const controls = card.querySelectorAll("input, button");
    controls.forEach((node) => { node.disabled = true; });
    const status = card.querySelector("[data-reference-board-status]");
    if (status) status.textContent = "正在保存素材…";
    try {
      await workspace.onMutate(boardKey, request, assetId);
    } catch (_) {
      // The workspace rerender keeps the recoverable error beside this board.
    }
  }

  function editableCard(summary, workspace) {
    const card = element("section", "", "");
    card.className = "reference-board-card";
    card.append(element("h3", summary.title));
    const transient = workspace.states?.[summary.key];
    const state = element("p", boardStatus(summary, transient).message, { class: "reference-board-status", "data-reference-board-status": "", "aria-live": "polite" });
    card.append(state);
    const input = element("input", "", { type: "file", accept: "image/*", multiple: "", "aria-label": `选择${summary.title}图片` });
    input.className = "reference-board-input";
    input.disabled = Boolean(workspace.readOnly || workspace.busy);
    input.addEventListener("change", () => {
      const files = Array.from(input.files || []);
      if (!files.length) return;
      if (files.some((file) => !String(file.type || "").startsWith("image/"))) {
        state.textContent = "请选择图片文件后重试。";
        input.value = "";
        return;
      }
      if (summary.assets.length + files.length > 30) {
        state.textContent = "每个参考板最多 30 张图片。";
        input.value = "";
        return;
      }
      void mutate(workspace, card, summary.key, (revision) => workspace.client.uploadBoardAssets(summary.key, files, revision));
    });
    card.append(input);
    const assets = element("ol", "", { class: "reference-board-list", "aria-label": `${summary.title}排序` });
    summary.assets.forEach((asset, index) => {
      const row = element("li", "", { class: "reference-board-item" });
      if (asset.relativePath && workspace.resolveAssetUrl) {
        const image = element("img", "", { src: workspace.resolveAssetUrl(asset.relativePath), alt: asset.sourceName || asset.id, loading: "lazy" });
        image.className = "reference-board-thumb";
        row.append(image);
      }
      row.append(element("span", `${index + 1}. ${asset.sourceName || asset.id} · ${asset.status || "ready"}`));
      const actions = element("div", "", { class: "reference-board-actions" });
      const disabled = Boolean(workspace.readOnly || workspace.busy);
      if (asset.status === "missing") {
        const replacement = element("input", "", { type: "file", accept: "image/*", "aria-label": `替换缺失的 ${asset.sourceName || asset.id}` });
        replacement.className = "reference-board-replace";
        replacement.disabled = disabled;
        replacement.addEventListener("change", () => {
          const file = replacement.files?.[0];
          if (!file || !String(file.type || "").startsWith("image/")) return;
          void mutate(workspace, card, summary.key, (revision) => workspace.client.replaceBoardAsset(summary.key, asset.id, file, revision), asset.id);
        });
        actions.append(replacement);
      }
      actions.append(
        button("上移", () => void mutate(workspace, card, summary.key, (revision) => workspace.client.reorderBoardAssets(summary.key, movedIds(summary.assets, index, index - 1), revision)), { disabled: disabled || index === 0, label: `上移 ${asset.sourceName || asset.id}` }),
        button("下移", () => void mutate(workspace, card, summary.key, (revision) => workspace.client.reorderBoardAssets(summary.key, movedIds(summary.assets, index, index + 1), revision)), { disabled: disabled || index === summary.assets.length - 1, label: `下移 ${asset.sourceName || asset.id}` }),
        button("移除", () => void mutate(workspace, card, summary.key, (revision) => workspace.client.deleteBoardAsset(summary.key, asset.id, revision), asset.id), { disabled, label: `移除 ${asset.sourceName || asset.id}`, className: "reference-board-action btn warn" }),
      );
      row.append(actions);
      assets.append(row);
    });
    card.append(assets);
    if (transient?.status === "failed" && typeof transient.retry === "function") card.append(button("重试", () => void mutate(workspace, card, summary.key, transient.retry, transient.assetId), { label: `重试${summary.title}` }));
    return card;
  }

  function planningCard(summary) {
    const card = element("section", "", { class: "reference-board-card reference-board-planning" });
    card.append(element("h3", summary.title), element("p", statusText(summary), { class: "reference-board-status" }));
    card.append(element("p", "由已确认代表画面自动生成；此处不上传或编辑主截图帧。", { class: "rule-domain-muted" }));
    return card;
  }

  function render(workspace) {
    if (typeof document === "undefined" || !workspace?.root) return;
    const section = element("section", "", { class: "reference-board-assets", "aria-labelledby": "referenceBoardHeading" });
    section.append(element("h2", "UE 两画板准备", { id: "referenceBoardHeading" }));
    const grid = element("div", "", { class: "reference-board-grid" });
    summaries(workspace.boards, workspace.planningCount).forEach((summary) => grid.append(summary.editable ? editableCard(summary, workspace) : planningCard(summary)));
    section.append(grid);
    workspace.root.replaceChildren(section);
  }

  return { BOARD_KEYS, manifest, summaries, movedIds, boardStatus, render };
});
