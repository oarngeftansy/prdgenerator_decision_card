// API 配置管理

let publicApiConfig = null;

function normalizeChatCompletionsUrl(base) {
  const clean = base.replace(/\/+$/, "");
  if (clean.endsWith("/chat/completions")) return clean;
  return `${clean}/chat/completions`;
}

function rememberApiConfig() {
  localStorage.setItem("vpr_api_url", $("apiUrl").value.trim());
  localStorage.setItem("vpr_model", $("model").value.trim());
  localStorage.setItem("vpr_transcription_model", $("transcriptionModel").value.trim());
  localStorage.setItem("vpr_transcription_url", $("transcriptionApiUrl").value.trim());
  if ($("rememberKey").checked) {
    localStorage.setItem("vpr_api_key", $("apiKey").value.trim());
    localStorage.setItem("vpr_transcription_key", $("transcriptionApiKey").value.trim());
  } else {
    localStorage.removeItem("vpr_api_key");
    localStorage.removeItem("vpr_transcription_key");
  }
  localStorage.setItem("vpr_remember_key", $("rememberKey").checked ? "1" : "0");
  renderApiConfigGate();
}

function hasSavedApiConfig() {
  return Boolean(localStorage.getItem("vpr_api_key"));
}

function renderApiConfigGate() {
  const panel = $("apiConfigPanel");
  const summary = $("apiConfigSummary");
  const notice = $("apiConfigNotice");
  if (!panel || !summary || !notice) return;

  const builtIn = Boolean(publicApiConfig?.hasBuiltInApi);
  const configured = builtIn || Boolean($("apiKey").value.trim());
  panel.hidden = builtIn;
  panel.open = builtIn ? false : !configured;
  summary.textContent = configured ? "已保存，后续自动回填" : "首次使用需填写自己的 API";
  notice.textContent = configured
    ? "已检测到本浏览器保存的 API 配置。后续打开会自动回填；如需更换模型或 Key，再展开这里修改。"
    : "首次进入请填写视觉模型 API。每位体验者都需要使用自己的 Key；页面不会使用分享者的内置 Key。";
  if (builtIn) {
    summary.textContent = "已内置模型 API，可直接使用";
    notice.textContent = "当前使用内置阿里云 DashScope 视觉模型配置。体验者打开网页即可上传分析；如需更换 API，请联系项目维护者修改配置。";
  }
}

async function loadPublicApiDefaults() {
  const response = await fetch(`${BACKEND_BASE}/api/config/public`, { cache: "no-store" });
  if (!response.ok) return;
  publicApiConfig = await response.json();
  if (publicApiConfig.hasBuiltInApi) {
    if (publicApiConfig.apiBase) $("apiUrl").value = publicApiConfig.apiBase;
    if (publicApiConfig.model) $("model").value = publicApiConfig.model;
    $("apiKey").value = "";
    $("transcriptionApiKey").value = "";
    localStorage.removeItem("vpr_api_key");
    localStorage.removeItem("vpr_transcription_key");
    localStorage.setItem("vpr_api_url", $("apiUrl").value.trim());
    localStorage.setItem("vpr_model", $("model").value.trim());
  } else if (!$("apiKey").value.trim()) {
    if (publicApiConfig.apiBase) $("apiUrl").value = publicApiConfig.apiBase;
    if (publicApiConfig.model) $("model").value = publicApiConfig.model;
  }
  renderApiConfigGate();
}

function loadApiConfig() {
  const hashParams = new URLSearchParams(location.hash.replace(/^#/, ""));
  const hashKey = hashParams.get("apiKey");
  const hashUrl = hashParams.get("apiUrl");
  const hashModel = hashParams.get("model");
  if (hashUrl) localStorage.setItem("vpr_api_url", hashUrl);
  if (hashModel) localStorage.setItem("vpr_model", hashModel);
  if (hashKey) {
    localStorage.setItem("vpr_api_key", hashKey);
    localStorage.setItem("vpr_remember_key", "1");
    history.replaceState(null, document.title, location.pathname + location.search);
  }
  const apiUrl = localStorage.getItem("vpr_api_url");
  const model = localStorage.getItem("vpr_model");
  const remember = localStorage.getItem("vpr_remember_key") !== "0";
  const key = localStorage.getItem("vpr_api_key");
  $("transcriptionModel").value = localStorage.getItem("vpr_transcription_model") || "whisper-1";
  $("transcriptionApiUrl").value = localStorage.getItem("vpr_transcription_url") || "";
  $("transcriptionApiKey").value = localStorage.getItem("vpr_transcription_key") || "";
  if (apiUrl) $("apiUrl").value = apiUrl;
  if (model) $("model").value = model;
  $("rememberKey").checked = remember;
  if (remember && key) $("apiKey").value = key;
  renderApiConfigGate();
}

async function checkLocalProxy() {
  const configuredUrl = $("apiUrl").value.trim();
  const isLocal = configuredUrl.includes("127.0.0.1") || configuredUrl.includes("localhost");
  if (!isLocal) {
    setProgress(0, "模型后端直连模式");
    setStatus($("apiKey").value.trim() || publicApiConfig?.hasBuiltInApi
      ? "模型 API 已填写，将由本机后端代调用视觉模型。"
      : "请填写自己的 API Key；不会使用分享者的 Key。");
    return;
  }
  try {
    const res = await fetch("http://127.0.0.1:8787/health", { cache: "no-store" });
    if (res.ok) {
      setProgress(0, "本地代理已连接");
      setStatus("本地代理已连接。可以上传素材后点击提取关键帧并 AI 解读。");
    } else {
      setProgress(0, "本地代理异常");
      setStatus(`本地代理异常：HTTP ${res.status}`);
    }
  } catch (error) {
    const directUrl = publicApiConfig?.apiBase || "https://dashscope.aliyuncs.com/compatible-mode/v1";
    $("apiUrl").value = directUrl;
    localStorage.setItem("vpr_api_url", directUrl);
    setProgress(0, "已切换模型后端直连");
    setStatus($("apiKey").value.trim() || publicApiConfig?.hasBuiltInApi
      ? "本地代理未运行，已自动切换为后端直连。"
      : "已自动切换为后端直连；请填写自己的 API Key。");
  }
}
