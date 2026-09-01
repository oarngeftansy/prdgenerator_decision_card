const SCREENSHOT_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const screenshotCollator = new Intl.Collator("zh-CN", { numeric: true, sensitivity: "base" });

function selectTopLevelScreenshots(files) {
  const all = Array.from(files || []);
  const relativePath = String(all.find((file) => file.webkitRelativePath)?.webkitRelativePath || "");
  const folderName = relativePath.split("/")[0] || "";
  let ignoredCount = 0;
  let nestedCount = 0;
  const accepted = all.filter((file) => {
    const path = String(file.webkitRelativePath || "");
    if (path && path.split("/").filter(Boolean).length !== 2) {
      nestedCount += 1;
      return false;
    }
    if (!SCREENSHOT_TYPES.has(file.type)) {
      ignoredCount += 1;
      return false;
    }
    return true;
  }).sort((left, right) => screenshotCollator.compare(left.name, right.name));
  return { accepted, ignoredCount, nestedCount, folderName };
}

function validateScreenshotCount(count) {
  if (count < 2) return { valid: false, message: "请至少选择 2 张截图。" };
  if (count > 50) return { valid: false, message: "一次最多分析 50 张截图。" };
  return { valid: true, message: `已选择 ${count} 张截图，可以开始分析。` };
}

function moveItem(items, fromIndex, toIndex) {
  const copy = [...items];
  if (fromIndex < 0 || fromIndex >= copy.length || toIndex < 0 || toIndex >= copy.length) return copy;
  const [item] = copy.splice(fromIndex, 1);
  copy.splice(toIndex, 0, item);
  return copy;
}

function buildImageManifest(assets) {
  return assets.map((asset, index) => ({ clientId: asset.id, originalName: asset.name, order: index + 1 }));
}

if (typeof module !== "undefined") {
  module.exports = { selectTopLevelScreenshots, validateScreenshotCount, moveItem, buildImageManifest };
}
