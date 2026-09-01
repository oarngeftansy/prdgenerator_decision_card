(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ClientCache = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  const SCHEMA_KEY = "vpr_client_cache_schema";
  const CURRENT_SCHEMA = "workbench-ui-20260820-v1";
  const UI_CACHE_PREFIXES = ["vpr_gameplay_review_ui_", "vpr_planning_board_ui_"];

  function keys(storage) {
    const result = [];
    for (let index = 0; index < Number(storage?.length || 0); index += 1) {
      const key = storage.key(index);
      if (key) result.push(key);
    }
    return result;
  }

  function cleanup(storage) {
    if (!storage || storage.getItem(SCHEMA_KEY) === CURRENT_SCHEMA) return [];
    const removed = keys(storage).filter((key) => UI_CACHE_PREFIXES.some((prefix) => key.startsWith(prefix)));
    removed.forEach((key) => storage.removeItem(key));
    storage.setItem(SCHEMA_KEY, CURRENT_SCHEMA);
    return removed;
  }

  return { CURRENT_SCHEMA, SCHEMA_KEY, cleanup };
});
