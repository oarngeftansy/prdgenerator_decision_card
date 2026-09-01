// 工具函数

const $ = (id) => document.getElementById(id);

function setStatus(text) { $("statusText").innerHTML = text; }

function setProgress(percent, stage) {
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  $("progressBar").style.width = `${value}%`;
  $("progressPercent").textContent = `${value}%`;
  $("progressStage").textContent = stage || "";
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function escapeMd(text) {
  return String(text || "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
}