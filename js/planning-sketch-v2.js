(function (root) {
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

  const contextLabel = (type) => ({
    ui_surface: "界面交互",
    gameplay_context: "玩法交互",
    system_context: "系统行为",
  }[type] || "玩法上下文");

  const visualState = (state) => {
    const value = String(state || "confirmed");
    if (value === "conflict") return "conflict";
    if (value === "inferred" || value === "proposed") return "yellow";
    return "confirmed";
  };

  const detailRow = (label, value, state) => {
    const text = Array.isArray(value) ? value.filter(Boolean).join("；") : String(value || "").trim();
    if (!text) return "";
    return `<div class="planning-sketch-detail" data-publication-visual="${visualState(state)}"><span>${escapeHtml(label)}</span><p>${escapeHtml(text)}</p></div>`;
  };

  const interactionHtml = (interaction) => {
    const state = interaction?.publicationState || "confirmed";
    const refs = (interaction?.ruleRefs || []).filter(Boolean);
    const action = String(interaction?.action || "").trim() || "该规则未提供可展示的行为正文。";
    return `<article class="planning-sketch-interaction" data-publication-state="${escapeHtml(state)}" data-publication-visual="${visualState(state)}"${refs.length ? ` data-rule-refs="${escapeHtml(refs.join(","))}"` : ""}>
      <p class="planning-sketch-action">${escapeHtml(action)}</p>
      ${detailRow("触发", interaction?.trigger, state)}
      ${detailRow("条件", interaction?.preconditions, state)}
      ${detailRow("结果", interaction?.result || interaction?.stateChange, state)}
      ${detailRow("异常", interaction?.exception, state)}
      ${detailRow("持续/保存", interaction?.persistence, state)}
      ${detailRow("重置", interaction?.reset, state)}
    </article>`;
  };

  const contextHtml = (context) => {
    const interactions = (context?.interactions || []).filter((item) => item && typeof item === "object");
    return `<section class="planning-sketch-context" data-context-type="${escapeHtml(context?.contextType || "system_context")}">
      <header><div><small>${escapeHtml(contextLabel(context?.contextType))}</small><h2>${escapeHtml(context?.title || "玩法上下文")}</h2></div><span>${interactions.length} 条规则</span></header>
      <div class="planning-sketch-interactions">${interactions.map(interactionHtml).join("")}</div>
    </section>`;
  };

  function render(sketch) {
    if (!sketch || sketch.version !== "planning_sketch_v2") {
      return `<section class="planning-sketch-empty"><h1>策划草图</h1><p>策划草图尚未生成。</p></section>`;
    }
    const contexts = (sketch.contexts || []).filter((item) => item && typeof item === "object");
    return `<section class="planning-sketch-v2" data-authority="canonical_rule_projection">
      <header class="planning-sketch-v2-head"><div><p>Canonical Rule Projection</p><h1>策划草图</h1></div><span>${contexts.length} 个玩法上下文 · ${Number(sketch.ruleCount || 0)} 条规则</span></header>
      <div class="planning-sketch-contexts">${contexts.map(contextHtml).join("")}</div>
    </section>`;
  }

  const api = { escapeHtml, contextLabel, visualState, render };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PlanningSketchV2 = api;
}(typeof window !== "undefined" ? window : globalThis));