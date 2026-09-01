(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.FrameReviewer = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  const fields = {
    gameplay: [
      { field: "gameState", label: "这一段在玩什么" },
      { field: "requirement", label: "玩家现在要完成什么" },
      { field: "userAction", label: "玩家做了什么" },
      { field: "systemResponse", label: "游戏接着发生了什么" },
      { field: "afterState", label: "什么时候算成功 / 失败" },
      { field: "gameMechanics", label: "有哪些玩法规则" },
      { field: "valueChanges", label: "数值和进度发生了什么变化" },
      { field: "gameFeedback", label: "画面和声音给了什么反馈" },
      { field: "unknowns", label: "还需要确认什么" },
    ],
    interaction: [
      { field: "what", label: "当前是什么界面" },
      { field: "components", label: "这个界面需要显示什么内容" },
      { field: "userAction", label: "用户进行了什么操作" },
      { field: "requirement", label: "进行操作需要满足什么条件" },
      { field: "systemResponse", label: "点击或操作后发生什么" },
      { field: "stateVariations", label: "不同情况下分别怎么显示" },
      { field: "promptText", label: "页面上出现什么提示文字" },
      { field: "afterState", label: "操作完成后进入哪里" },
      { field: "unknowns", label: "视频没有展示什么" },
    ],
  };

  function timestampOf(frame) {
    const value = Number(frame && frame.timestamp);
    return Number.isFinite(value) ? value : Number.MAX_SAFE_INTEGER;
  }

  function sortFrames(frames) {
    return (Array.isArray(frames) ? frames : [])
      .map((frame, originalIndex) => ({ frame, originalIndex }))
      .sort((a, b) => timestampOf(a.frame) - timestampOf(b.frame) || a.originalIndex - b.originalIndex)
      .map(({ frame }) => frame);
  }

  function moveIndex(index, delta, length) {
    if (!Number.isFinite(length) || length <= 0) return 0;
    const current = Number.isFinite(index) ? index : 0;
    return Math.min(length - 1, Math.max(0, current + delta));
  }

  function findFrameIndex(frames, frameId, timestamp) {
    const ordered = sortFrames(frames);
    if (!ordered.length) return -1;
    if (frameId !== undefined && frameId !== null) {
      const byId = ordered.findIndex((frame) => String(frame.id) === String(frameId));
      if (byId >= 0) return byId;
    }
    const target = Number(timestamp);
    if (Number.isFinite(target)) {
      const exact = ordered.findIndex((frame) => timestampOf(frame) === target);
      if (exact >= 0) return exact;
      let closest = 0;
      for (let index = 1; index < ordered.length; index += 1) {
        if (Math.abs(timestampOf(ordered[index]) - target) < Math.abs(timestampOf(ordered[closest]) - target)) closest = index;
      }
      return closest;
    }
    return 0;
  }

  function fieldsForMode(mode) {
    return fields[mode] || fields.gameplay;
  }

  function isTextEditingTarget(target) {
    if (!target) return false;
    return ["INPUT", "TEXTAREA", "SELECT"].includes(String(target.tagName || "").toUpperCase()) || Boolean(target.isContentEditable);
  }

  function filterOptions() {
    return [
      { value: "scene_representatives", label: "每个场景 1 帧" },
      { value: "all", label: "全部" },
      { value: "attention", label: "需要重点检查" },
      { value: "unknown", label: "视频没有明确展示" },
      { value: "unconfirmed", label: "尚未人工确认" },
    ];
  }

  function sceneRepresentativeFrames(frames) {
    const groups = new Map();
    for (const frame of sortFrames(frames)) {
      const scene = frame.sceneGroup ?? frame.sceneId ?? "unknown";
      if (!groups.has(scene)) groups.set(scene, []);
      groups.get(scene).push(frame);
    }
    return Array.from(groups.values()).map((items) => {
      const detailFrame = items.find((frame) => frame.isDetailFrame);
      return detailFrame || items[Math.floor(items.length / 2)];
    });
  }

  function isUnknown(frame) {
    const evidence = String(frame.evidenceLevel || "").toLowerCase();
    return evidence === "unknown" || evidence.includes("未知") || Boolean(String(frame.unknowns || "").trim());
  }

  function attentionReasons(frame, mode = "gameplay") {
    const reasons = [];
    const add = (label, suggestion) => {
      if (!reasons.some((reason) => reason.label === label)) reasons.push({ label, suggestion });
    };
    if (frame.hasConflict || (Array.isArray(frame.conflicts) && frame.conflicts.length)) {
      add("前后结论不一致", "请对照前后画面，确认操作和结果是否连贯。");
    }
    if (!String(frame.userAction || "").trim()) {
      add(mode === "interaction" ? "缺少用户操作" : "缺少玩家操作", mode === "interaction"
        ? "请回看前后 2–3 秒，补充用户进行了什么操作。"
        : "请回看前后 2–3 秒，补充玩家做了什么。");
    }
    const context = mode === "interaction"
      ? String(frame.what || "").trim()
      : String(frame.gameState || frame.what || "").trim();
    if (!context) {
      add(mode === "interaction" ? "当前界面不明确" : "玩法目的不明确", mode === "interaction"
        ? "请补充当前是什么界面，以及界面的主要用途。"
        : "请补充这一段在玩什么、玩家需要完成什么。");
    }
    const signalCopy = {
      state_chain_broken: ["前后状态无法连上", "请对照连续画面，补全操作前、操作后和系统反馈。"],
      text_unreadable: ["界面文字看不清", "请查看更清楚的相邻画面，确认关键文案和数值。"],
      visual_occlusion: ["画面被特效或弹窗遮挡", "请补取遮挡前后的画面，确认被遮住的玩法或界面信息。"],
      action_between_frames: ["关键操作可能发生在两帧之间", "建议补取前后画面，确认操作发生的准确时刻。"],
      result_not_shown: ["操作结果没有画面证明", "请补取操作后的画面，确认系统反馈和最终状态。"],
    };
    const signals = Array.isArray(frame.attentionSignals) ? frame.attentionSignals : [];
    let hasSpecificLowReason = false;
    for (const signal of Object.keys(signalCopy)) {
      if (!signals.includes(signal)) continue;
      add(...signalCopy[signal]);
      hasSpecificLowReason = true;
    }
    const isLow = ["低", "low"].includes(String(frame.confidence || "").toLowerCase());
    const unknownText = Array.isArray(frame.unknowns) ? frame.unknowns.join("；") : String(frame.unknowns || "");
    if (isLow && /继承场景摘要|未进行独立视觉模型分析/.test(unknownText)) {
      add(...signalCopy.action_between_frames);
      hasSpecificLowReason = true;
    }
    const meaningful = (value) => Boolean(String(value || "").trim()) && !/^(未知待确认|待确认)$/.test(String(value).trim());
    if (isLow && String(frame.userAction || "").trim() && (!meaningful(frame.systemResponse) || !meaningful(frame.afterState))) {
      add(...signalCopy.result_not_shown);
      hasSpecificLowReason = true;
    }
    if (isLow && !hasSpecificLowReason) {
      add("画面信息不足", "请检查画面是否清楚，或回看相邻画面补足依据。");
    }
    return reasons.slice(0, 3);
  }

  function filterFrames(frames, filter = "all", mode = "gameplay") {
    const ordered = sortFrames(frames);
    if (filter === "scene_representatives") return sceneRepresentativeFrames(ordered);
    if (filter === "attention") return ordered.filter((frame) => attentionReasons(frame, mode).length);
    if (filter === "unknown") return ordered.filter(isUnknown);
    if (filter === "unconfirmed") return ordered.filter((frame) => !frame.confirmed);
    return ordered;
  }

  function firstFrameIndexForScene(frames, sceneId, filter = "all", mode = "gameplay") {
    return filterFrames(frames, filter, mode).findIndex((frame) => String(frame.sceneGroup) === String(sceneId));
  }

  return { sortFrames, moveIndex, findFrameIndex, fieldsForMode, isTextEditingTarget, filterOptions, attentionReasons, filterFrames, sceneRepresentativeFrames, firstFrameIndexForScene };
});
