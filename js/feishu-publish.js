(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.FeishuPublish = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  const busyStates = new Set(["checking_auth", "creating_folder", "creating_document", "uploading_evidence", "uploading_board_media", "creating_whiteboard", "verifying"]);
  const labels = {
    checking_auth: "正在检查飞书登录",
    creating_folder: "正在准备飞书文件夹",
    creating_document: "正在创建飞书文档",
    uploading_evidence: "正在上传关键帧",
    uploading_board_media: "正在上传策划草图素材",
    creating_whiteboard: "正在创建策划草图",
    verifying: "正在检查发布结果",
  };

  function publicationBusy(status) {
    return busyStates.has(status);
  }

  function makePublicationRequestId() {
    const random = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID().replace(/-/g, "")
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
    return `pub_${random}`.slice(0, 80);
  }

  function safeUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" ? url.href : "";
    } catch (_) {
      return "";
    }
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
  }

  function previewCanPublish(preview, model, mutationBlocked = false) {
    if (model?.interaction && model?.gameplay) {
      return !mutationBlocked && Boolean(preview?.exportReady)
        && preview.interactionRevision === model.interaction.revision
        && preview.gameplayRevision === model.gameplay.revision;
    }
    return !mutationBlocked && Boolean(preview?.exportReady) && preview.revision === model?.revision;
  }

  function renderFeishuPublication(publication = {}, canPublish = false, blockedReason = "") {
    const status = publication.status || "not_published";
    if (publicationBusy(status)) {
      return `<div class="feishu-publication-copy"><b>${labels[status]}</b><span>请保持当前页面打开，完成后会自动显示文档链接。</span></div><button class="btn primary" type="button" disabled>导出中…</button>`;
    }
    if (blockedReason) {
      return `<div class="feishu-publication-copy"><b>交付物尚未就绪</b><span>${blockedReason}</span></div><button class="btn primary" type="button" disabled>重试成功后导出</button>`;
    }
    if (status === "published") {
      const url = safeUrl(publication.documentUrl);
      const folderName = escapeHtml(publication.folderName || "我的空间 / 策划案");
      return `<div class="feishu-publication-copy"><b>已导出到飞书云盘</b><span>保存位置：${folderName}</span></div><div class="feishu-publication-actions">${url ? `<a class="btn primary" href="${url}" target="_blank" rel="noopener noreferrer">打开飞书文档</a>` : ""}<button class="btn" type="button" data-feishu-action="update">重新导出</button><button class="btn" type="button" data-feishu-action="new_version">另存为新版本</button></div>`;
    }
    if (status === "conflict") {
      if (/审核版本/.test(publication.message || "")) {
        return `<div class="feishu-publication-copy"><b>审核版本已变化</b><span>请重新生成导出预览，确认最新内容后再发布。</span></div><button class="btn primary" type="button" disabled>重新生成导出预览后发布</button>`;
      }
      return `<div class="feishu-publication-copy"><b>飞书文档已有修改</b><span>为保护策划在飞书中的编辑，本次不会覆盖原文档。</span></div><button class="btn primary" type="button" data-feishu-action="new_version">另存为新版本</button>`;
    }
    if (status === "partial" || status === "failed") {
      const message = publication.message || "导出没有完成，本地策划案不受影响。";
      const needsAuth = /飞书|登录|授权|Feishu/i.test(message);
      if (status === "failed" && needsAuth) {
        return `<div class="feishu-publication-copy"><b>需要授权飞书</b><span>授权后会自动把完整策划案生成到你的飞书云盘。</span></div><button class="btn primary" type="button" data-feishu-action="auth" ${canPublish ? "" : "disabled"}>授权飞书并导出</button>`;
      }
      return `<div class="feishu-publication-copy"><b>${status === "partial" ? "文档已创建，导出未完成" : "暂时无法导出"}</b><span>${message}</span></div><button class="btn primary" type="button" data-feishu-action="update" ${canPublish ? "" : "disabled"}>重试导出</button>`;
    }
    return `<div class="feishu-publication-copy"><b>${canPublish ? "导出到我的飞书云盘" : "完成策划案后可导出"}</b><span>正文使用飞书文档，策划草图以内嵌画板呈现。</span></div><button class="btn primary" type="button" data-feishu-action="update" ${canPublish ? "" : "disabled"}>导出到飞书</button>`;
  }

  return { makePublicationRequestId, publicationBusy, previewCanPublish, renderFeishuPublication };
});

let activeFeishuRequestId = "";
let feishuPollTimer = null;
let pendingFeishuDeviceCode = "";
let pendingFeishuPublishMode = "new_version";
let pendingFeishuFolder = null;

async function chooseFeishuFolder() {
  return new Promise((resolve, reject) => {
    document.querySelector(".feishu-folder-picker")?.remove();
    const overlay = document.createElement("div");
    overlay.className = "feishu-folder-picker";
    overlay.innerHTML = `<section class="feishu-folder-dialog" role="dialog" aria-modal="true" aria-labelledby="feishuFolderTitle">
      <header><div><h3 id="feishuFolderTitle">选择飞书保存位置</h3><p>默认保存到“我的空间 / 策划案”；也可以选择你有权限的文件夹。</p></div><button class="btn" type="button" data-folder-close>取消</button></header>
      <nav class="feishu-folder-breadcrumb" aria-label="飞书目录"><button class="btn" type="button" data-folder-root>我的空间</button><span data-folder-path></span></nav>
      <div class="feishu-folder-list" role="listbox" aria-label="可用文件夹"><p>正在读取文件夹…</p></div>
      <footer><button class="btn" type="button" data-folder-default>使用“我的空间 / 策划案”</button><button class="btn primary" type="button" data-folder-confirm disabled>保存到当前文件夹</button></footer>
    </section>`;
    document.body.append(overlay);
    const list = overlay.querySelector(".feishu-folder-list");
    const confirm = overlay.querySelector("[data-folder-confirm]");
    const path = overlay.querySelector("[data-folder-path]");
    let current = { token: "", name: "我的空间" };
    const stack = [];
    const close = (value) => { overlay.remove(); resolve(value); };
    const load = async (folder, reset = false) => {
      if (reset) stack.splice(0);
      current = folder;
      path.textContent = stack.length ? ` / ${stack.map((item) => item.name).join(" / ")}` : "";
      confirm.disabled = !current.token;
      confirm.textContent = current.token ? `保存到“${current.name}”` : "保存到当前文件夹";
      list.innerHTML = "<p>正在读取文件夹…</p>";
      try {
        const query = current.token ? `?parent_token=${encodeURIComponent(current.token)}` : "";
        const response = await fetch(`${BACKEND_BASE}/api/feishu/folders${query}`, { cache: "no-store" });
        if (!response.ok) throw new Error(await response.text());
        const payload = await response.json();
        list.replaceChildren();
        if (!(payload.folders || []).length) list.innerHTML = "<p>当前目录没有子文件夹。</p>";
        (payload.folders || []).forEach((folderItem) => {
          const button = document.createElement("button");
          button.type = "button"; button.className = "feishu-folder-item";
          button.textContent = `📁 ${folderItem.name}`;
          button.addEventListener("click", () => { stack.push(folderItem); load(folderItem); });
          list.append(button);
        });
      } catch (error) {
        list.replaceChildren();
        const message = document.createElement("p");
        message.className = "feishu-folder-error";
        message.textContent = `读取文件夹失败：${String(error.message || error)}`;
        list.append(message);
      }
    };
    overlay.querySelector("[data-folder-close]").addEventListener("click", () => close(null));
    overlay.querySelector("[data-folder-default]").addEventListener("click", () => close({ token: "", name: "我的空间 / 策划案" }));
    overlay.querySelector("[data-folder-confirm]").addEventListener("click", () => close(current));
    overlay.querySelector("[data-folder-root]").addEventListener("click", () => load({ token: "", name: "我的空间" }, true));
    overlay.addEventListener("click", (event) => { if (event.target === overlay) close(null); });
    load(current, true).catch(reject);
  });
}

function renderFeishuPublicationState(publication = {}, canPublish = Boolean($("output")?.value.trim() && lastCompletedJobId)) {
  const targets = [$("feishuPublication"), ...document.querySelectorAll(".final-document-feishu-state")].filter(Boolean);
  if (!targets.length) return;
  const blockedReason = typeof ReviewWorkspace !== "undefined" ? ReviewWorkspace.competitorMutationBlockMessage?.(state.reviewWorkspace) || "" : "";
  if (state.gameplayReviewWorkspace?.preview && state.reviewWorkspace?.model) {
    canPublish = FeishuPublish.previewCanPublish(
      state.gameplayReviewWorkspace.preview,
      { interaction: state.reviewWorkspace.model, gameplay: state.gameplayReviewWorkspace.model },
      Boolean(blockedReason),
    );
  } else if (state.reviewWorkspace?.model) canPublish = FeishuPublish.previewCanPublish(state.reviewWorkspace.preview, state.reviewWorkspace.model, Boolean(blockedReason));
  currentFeishuPublication = publication;
  targets.forEach((target) => { target.innerHTML = FeishuPublish.renderFeishuPublication(publication, canPublish, blockedReason); });
}

async function publishToFeishuWithAuthorization(mode = "new_version") {
  if (mode === "complete_auth") return completeFeishuAuthorization();
  if (mode === "auth") mode = pendingFeishuPublishMode;
  pendingFeishuPublishMode = mode;
  const authWindow = window.open("about:blank", "feishu-authorization", "noopener,noreferrer");
  const response = await fetch(`${BACKEND_BASE}/api/feishu/auth/status`, { cache: "no-store" });
  if (!response.ok) {
    authWindow?.close();
    throw new Error(`检查飞书登录失败：${await response.text()}`);
  }

  const auth = await response.json();
  if (!auth.authenticated) return startFeishuAuthorization(authWindow, mode);
  authWindow?.close();
  if (mode === "new_version" || currentFeishuPublication?.status !== "published") {
    pendingFeishuFolder = await chooseFeishuFolder();
    if (!pendingFeishuFolder) return;
  }
  return publishToFeishu(mode);
}

async function publishToFeishu(mode = "update") {
  const blockedReason = typeof ReviewWorkspace !== "undefined" ? ReviewWorkspace.competitorMutationBlockMessage?.(state.reviewWorkspace) || "" : "";
  if (blockedReason) throw new Error(blockedReason);
  if (mode === "auth") return startFeishuAuthorization();
  if (mode === "complete_auth") return completeFeishuAuthorization();
  if (!lastCompletedJobId) throw new Error("请先打开一个已完成的长视频任务。");
  if (mode === "new_version" || !activeFeishuRequestId) activeFeishuRequestId = FeishuPublish.makePublicationRequestId();
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${lastCompletedJobId}/feishu/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      requestId: activeFeishuRequestId, mode,
      folderToken: pendingFeishuFolder?.token || "",
      folderName: pendingFeishuFolder?.name || "",
    }),
  });
  if (!response.ok) throw new Error(`发布到飞书失败：${await response.text()}`);
  const publication = await response.json();
  renderFeishuPublicationState(publication, true);
  pollFeishuPublication();
}

async function pollFeishuPublication() {
  clearTimeout(feishuPollTimer);
  const response = await fetch(`${BACKEND_BASE}/api/jobs/${lastCompletedJobId}/feishu/publication`, { cache: "no-store" });
  if (!response.ok) throw new Error(`读取飞书发布进度失败：${response.status}`);
  const publication = await response.json();
  renderFeishuPublicationState(publication, true);
  if (FeishuPublish.publicationBusy(publication.status)) {
    feishuPollTimer = setTimeout(() => pollFeishuPublication().catch((error) => setStatus(error.message)), 1200);
    return;
  }
  if (publication.status === "published" || publication.status === "conflict") activeFeishuRequestId = "";
  setStatus(publication.message || (publication.status === "published" ? "策划案已发布到飞书。" : "飞书发布流程已停止。"));
}

async function startFeishuAuthorization(authWindow = null, mode = "new_version") {
  pendingFeishuPublishMode = mode;
  const response = await fetch(`${BACKEND_BASE}/api/feishu/auth/start`, { method: "POST" });
  if (!response.ok) throw new Error(`发起飞书授权失败：${await response.text()}`);
  const payload = await response.json();
  pendingFeishuDeviceCode = payload.deviceCode || "";
  if (payload.verificationUrl && authWindow) authWindow.location.href = payload.verificationUrl;
  else if (payload.verificationUrl) window.open(payload.verificationUrl, "_blank", "noopener,noreferrer");
  renderFeishuPublicationState({
    status: "failed",
    message: "请在弹出的飞书页面完成授权，然后回到这里继续导出。",
  }, true);
  const html = `<div class="feishu-publication-copy"><b>等待飞书授权</b><span>授权页已打开。完成后点击右侧按钮，系统会从当前步骤继续导出。</span></div><button class="btn primary" type="button" data-feishu-action="complete_auth">我已授权，继续导出</button>`;
  [$("feishuPublication"), ...document.querySelectorAll(".final-document-feishu-state")].filter(Boolean).forEach((target) => { target.innerHTML = html; });
}

async function completeFeishuAuthorization() {
  if (!pendingFeishuDeviceCode) throw new Error("请先点击“授权飞书并导出”。");
  const response = await fetch(`${BACKEND_BASE}/api/feishu/auth/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deviceCode: pendingFeishuDeviceCode }),
  });
  if (!response.ok) throw new Error(`完成飞书授权失败：${await response.text()}`);
  pendingFeishuDeviceCode = "";
  pendingFeishuFolder = await chooseFeishuFolder();
  if (!pendingFeishuFolder) return;
  return publishToFeishu(pendingFeishuPublishMode);
}
