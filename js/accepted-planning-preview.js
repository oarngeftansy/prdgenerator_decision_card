(async function () {
  const escapeHtml = (text) => String(text ?? "").replace(/[&<>]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[char]));
  const cells = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
  const separator = (line) => cells(line).every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s/g, "")));
  const renderTable = (lines) => {
    const rows = lines.filter((line) => !separator(line)).map(cells);
    if (!rows.length) return "";
    const [head, ...body] = rows;
    return `<div class="table-scroll"><table><thead><tr>${head.map((cell) => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead><tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  };
  const renderP6Table = (table, headingLevel = 4) => {
    const columns = table.publicationColumns || ["参数", "含义", "当前值"];
    const rows = table.publicationRows || (table.rows || []).map((row) => [row[0], row[1], row[3]]);
    return `<h${headingLevel}>配置表：${escapeHtml(table.title)}</h${headingLevel}>${renderTable([`|${columns.join("|")}|`, "|" + columns.map(() => "---").join("|") + "|", ...rows.map((row) => `|${row.join("|")}|`)])}`;
  };
  const renderMarkdown = (markdown = "", embeds = {}) => {
    const lines = String(markdown || "").split(/\r?\n/); let html = "", list = null, table = [];
    const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
    const closeTable = () => { if (table.length) { html += renderTable(table); table = []; } };
    for (const raw of lines) {
      const line = raw.trimEnd(); const heading = /^(#{1,5})\s+(.+)$/.exec(line);
      const embed = /^\s*<!--\s*EMBED:(P5|P6|BOARD):([A-Za-z0-9-]+)\s*-->\s*$/.exec(line);
      if (embed) {
        closeList(); closeTable();
        const item = embeds[embed[1]]?.[embed[2]];
        // Legacy BOARD:planning is intentionally ignored. The canonical sketch
        // is rendered from planning_sketch_v2 below and must not be replaced by
        // screenshot/stage board data.
        if (embed[1] === "BOARD" && embed[2] === "planning") continue;
        if (!item && embed[1] === "BOARD" && ["ue", "competitor"].includes(embed[2])) continue;
        if (!item) throw new Error(`缺少正文内嵌交付：${embed[1]}:${embed[2]}`);
        html += embed[1] === "P5"
          ? `<section class="diagram-card inline-delivery"><h4>图示：${escapeHtml(item.title)}</h4><div class="diagram-canvas">${item.svg}</div></section>`
          : embed[1] === "BOARD"
            ? `<section class="native-board-card inline-delivery"><h4>图示：${escapeHtml(item.title)}</h4><div class="native-board-canvas">${item.svg}</div></section>`
            : `<section class="inline-delivery">${renderP6Table(item)}</section>`;
        continue;
      }
      if (/^\s*<!--/.test(line)) continue;
      if (heading) { closeList(); closeTable(); html += `<h${heading[1].length}>${escapeHtml(heading[2])}</h${heading[1].length}>`; continue; }
      if (/^\|/.test(line)) { closeList(); table.push(line); continue; }
      closeTable();
      const bullet = /^\s*[-*]\s+(.+)$/.exec(line); const ordered = /^\s*\d+[.)]\s+(.+)$/.exec(line);
      if (bullet || ordered) { const type = bullet ? "ul" : "ol"; if (list !== type) { closeList(); html += `<${type}>`; list = type; } html += `<li>${escapeHtml((bullet || ordered)[1])}</li>`; continue; }
      if (!line.trim()) { closeList(); continue; }
      closeList(); html += `<p>${escapeHtml(line)}</p>`;
    }
    closeList(); closeTable(); return html;
  };
  const renderP6 = (tables = []) => `<h1>参数配置表</h1>${tables.filter((table) => table.status === "reviewed").map((table) => renderP6Table(table, 2)).join("")}`;

  const response = await fetch("/api/accepted-planning-preview", {cache:"no-store"});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const payload = await response.json();
  const nativeBoards = Array.isArray(payload.nativeBoards) ? payload.nativeBoards : [];
  const boards = Object.fromEntries(nativeBoards.map((board) => [board.key, board]));
  const p5Diagrams = Array.isArray(payload.p5Diagrams) ? payload.p5Diagrams : [];
  const p6Tables = Array.isArray(payload.p6Tables) ? payload.p6Tables : [];
  const embeds = {
    BOARD: boards,
    P5: Object.fromEntries(p5Diagrams.filter((item) => item.status === "reviewed").map((item) => [item.id, item])),
    P6: Object.fromEntries(p6Tables.filter((item) => item.status === "reviewed").map((item) => [item.id, item])),
  };
  document.getElementById("planning").innerHTML = renderMarkdown(payload.planningMarkdown, embeds);

  const canonicalSketch = payload.masterPlanningSketch || payload.planningSketch || payload.masterPlanning?.planningSketch || null;
  const sketchRenderer = globalThis.PlanningSketchV2;
  document.getElementById("sketch").innerHTML = sketchRenderer?.render
    ? sketchRenderer.render(canonicalSketch)
    : renderMarkdown(payload.planningSketchMarkdown || "## 策划草图\n\n策划草图尚未生成。");

  document.getElementById("diagrams").innerHTML = `<h1>P5 必要图解</h1>${p5Diagrams.map((item) => `<section class="diagram-card"><h2>${escapeHtml(item.title)}</h2><div class="diagram-canvas">${item.svg}</div></section>`).join("")}`;
  document.getElementById("parameters").innerHTML = renderP6(p6Tables);
  const crosswalk = payload.bodyCrosswalk || {lines: [], comparisonMethod: ""};
  const grouped = (crosswalk.lines || []).reduce((result, item) => {
    const owner = String(item.ownerPath || "未分类").split(" / ")[0];
    (result[owner] ||= []).push(item);
    return result;
  }, {});
  document.getElementById("benchmark").innerHTML = `<h1>职责核对</h1><p>${escapeHtml(crosswalk.comparisonMethod || "")}</p>${Object.entries(grouped).map(([owner, items]) => `<h2>${escapeHtml(owner)}</h2><div class="table-scroll"><table><thead><tr><th>Final 行</th><th>当前 Owner</th><th>最终实际文字</th><th>职责参照</th><th>第一手范围</th></tr></thead><tbody>${items.map(item => `<tr><td>${escapeHtml(item.finalLine)}</td><td>${escapeHtml(item.ownerPath)}</td><td>${escapeHtml(item.renderedFinalText)}</td><td>${escapeHtml(item.gve16ResponsibilityReference)}</td><td>${escapeHtml(item.sourceRange)}</td></tr>`).join("")}</tbody></table></div>`).join("")}`;
  const activate = (button) => {
    document.querySelector("main").classList.toggle("flow-wide", ["sketch","diagrams"].includes(button.dataset.target));
    document.querySelectorAll(".tabs button").forEach(item => item.classList.toggle("active", item === button));
    ["planning","sketch","diagrams","parameters","benchmark"].forEach(id => document.getElementById(id).hidden = id !== button.dataset.target);
  };
  document.querySelectorAll(".tabs button").forEach(button => button.onclick = () => activate(button));
  const requested = new URLSearchParams(location.search).get("tab");
  const requestedTarget = ["ue", "competitor"].includes(requested) ? "sketch" : requested;
  const requestedButton = requestedTarget && document.querySelector(`.tabs button[data-target="${requestedTarget}"]`);
  if (requestedButton) activate(requestedButton);
})();