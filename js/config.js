// API 配置管理

let publicApiConfig = null;
const DEFAULT_PRODUCTION_API_BASE = "https://ws-pht7pri9ebffuga3.cn-beijing.maas.aliyuncs.com/compatible-mode/v1";
const DEFAULT_PRODUCTION_MODEL = "qwen3.6plus";

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
    ? "已检测到本浏览器保存的 API 配置。生成前会先验证 Key 与模型是否真实可用。"
    : "首次进入请填写视觉模型 API。每位体验者都需要使用自己的 Key；页面不会使用分享者的内置 Key。";
  if (builtIn) {
    summary.textContent = "已内置模型 API，可直接使用";
    notice.textContent = "当前使用内置模型配置；生成前仍会验证服务是否可用。";
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
    $("apiUrl").value = publicApiConfig.apiBase || DEFAULT_PRODUCTION_API_BASE;
    $("model").value = publicApiConfig.model || DEFAULT_PRODUCTION_MODEL;
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
  $("apiUrl").value = apiUrl || DEFAULT_PRODUCTION_API_BASE;
  $("model").value = model || DEFAULT_PRODUCTION_MODEL;
  $("rememberKey").checked = remember;
  if (remember && key) $("apiKey").value = key;
  renderApiConfigGate();
}

async function validateConfiguredApi() {
  const payload = {
    apiBase: $("apiUrl").value.trim() || DEFAULT_PRODUCTION_API_BASE,
    model: $("model").value.trim() || DEFAULT_PRODUCTION_MODEL,
    apiKey: $("apiKey").value.trim(),
  };
  const response = await fetch(`${BACKEND_BASE}/api/config/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`API 连通性检查失败：HTTP ${response.status}`);
  }
  const result = await response.json();
  if (!result.ok) {
    const labels = {
      authentication: "API Key 无效或没有模型权限",
      rate_limit: "模型服务请求过于频繁",
      timeout: "模型服务响应超时",
      network: "无法连接模型服务",
      provider: "模型服务暂时不可用",
      configuration: "API 配置不完整",
      invalid_json: "模型服务返回格式异常",
      invalid_response: "模型服务响应结构异常",
    };
    throw new Error(labels[result.kind] || result.message || "模型 API 不可用");
  }
  return result;
}
if (typeof window !== "undefined") window.validateConfiguredApi = validateConfiguredApi;

async function checkLocalProxy() {
  const configuredUrl = $("apiUrl").value.trim();
  const isLocal = configuredUrl.includes("127.0.0.1") || configuredUrl.includes("localhost");
  if (!isLocal) {
    setProgress(0, "正在验证模型 API");
    try {
      await validateConfiguredApi();
      setProgress(0, "模型 API 已验证");
      setStatus("模型 API 已通过真实连通性验证，可以开始分析。" );
    } catch (error) {
      setProgress(0, "模型 API 验证失败");
      setStatus(error.message || "模型 API 不可用，请检查 API Key、地址和模型名称。" );
    }
    return;
  }
  try {
    const res = await fetch("http://127.0.0.1:8787/health", { cache: "no-store" });
    if (res.ok) {
      setProgress(0, "本地代理已连接");
      setStatus("本地代理已连接。可以上传素材后点击提取关键帧并 AI 解读。" );
    } else {
      setProgress(0, "本地代理异常");
      setStatus(`本地代理异常：HTTP ${res.status}`);
    }
  } catch (error) {
    const directUrl = publicApiConfig?.apiBase || DEFAULT_PRODUCTION_API_BASE;
    const directModel = publicApiConfig?.model || DEFAULT_PRODUCTION_MODEL;
    $("apiUrl").value = directUrl;
    $("model").value = directModel;
    localStorage.setItem("vpr_api_url", directUrl);
    localStorage.setItem("vpr_model", directModel);
    setProgress(0, "已切换模型后端直连");
    try {
      await validateConfiguredApi();
      setStatus("本地代理未运行，已切换后端直连并完成 API 验证。" );
    } catch (validationError) {
      setStatus(validationError.message || "已切换后端直连；请检查自己的 API Key。" );
    }
  }
}
