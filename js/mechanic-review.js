(async function () {
  const root = document.getElementById("review-root");
  const nav = document.getElementById("mechanic-nav");
  const mechanicNames = {
    "MDES-CHOICE": "战斗等级与三选一", "MDES-WEAPON": "武器处理",
    "MDES-MONSTER": "普通怪物行为", "MDES-DRAW": "独立武器抽取",
    "MDES-STATS": "伤害统计", "MDES-OUTCOME": "胜负判定",
  };
  const relationNames = {
    applies_result_to: "将确认结果写入",
    pauses_and_resumes: "暂停并恢复",
    consumes_committed_result: "接收已确认结果自",
    produces_attributed_damage: "输出归因伤害至",
    consumes_pause_state: "响应暂停状态自",
    damages_vehicle: "向载具结算伤害并影响",
  };

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const section = (title) => {
    const block = el("section", "model-section");
    block.append(el("h4", "section-title", title));
    return block;
  };

  const renderReadableTopics = (topics) => {
    const list = el("div", "readable-topics");
    topics.forEach((topic) => {
      const group = el("div", "readable-topic");
      group.append(el("h5", "readable-topic-title", topic.topicTitle));
      const bullets = el("ul", "readable-rules");
      topic.bullets.forEach((item) => {
        const row = el("li", item.knowledgeClass === "confirmed" ? "is-confirmed" : "is-inference");
        row.append(el("span", "knowledge-dot", ""), el("span", "", item.text));
        bullets.append(row);
      });
      group.append(bullets);
      list.append(group);
    });
    return list;
  };

  const renderDensityRules = (rules) => {
    const list = el("ul", "readable-rules density-rules");
    rules.forEach((item) => {
      const row = el("li", item.knowledgeClass === "confirmed" ? "is-confirmed" : "is-inference");
      row.append(el("span", "knowledge-dot", ""), el("span", "", item.text));
      list.append(row);
    });
    return list;
  };

  const renderModel = (model, readable, index) => {
    const article = el("article", "mechanic-card");
    article.id = `mechanic-${index + 1}`;
    const head = el("header", "mechanic-head");
    const number = el("span", "mechanic-number", String(index + 1).padStart(2, "0"));
    const titleWrap = el("div");
    titleWrap.append(el("p", "eyebrow", "Mechanic Review"));
    titleWrap.append(el("h3", "mechanic-title", model.reviewTitle));
    head.append(number, titleWrap);
    article.append(head);

    const plannerRules = readable.plannerGameplayRules || readable.defaultReview;
    const core = section("核心规则");
    core.append(renderDensityRules(plannerRules.coreRules));
    article.append(core);

    if (plannerRules.specialRules.length) {
      const special = section("分支 / 特殊规则");
      special.append(renderDensityRules(plannerRules.specialRules));
      article.append(special);
    }

    if (readable.defaultReview.decisionPoints.length) {
      const alternatives = section("设计分叉");
      readable.defaultReview.decisionPoints.forEach((group) => {
        alternatives.append(el("h5", "alternative-title", group.designPoint));
        const grid = el("div", "option-grid");
        group.options.forEach((option) => {
          const card = el("div", `option-card ${option.optionId === group.recommendedOptionId ? "recommended" : ""}`);
          card.append(el("span", "option-label", option.optionId === group.recommendedOptionId ? "推荐方案" : "备选方案"));
          card.append(el("p", "", option.text));
          card.append(el("small", "", option.impact));
          grid.append(card);
        });
        alternatives.append(grid);
      });
      article.append(alternatives);
    }

    if (readable.defaultReview.parameters.length) {
      const params = section("参数");
      readable.defaultReview.parameters.forEach((param) => params.append(el("p", "detail-row", `${param.meaning}：${param.value} ${param.unit}`)));
      article.append(params);
    }

    const folded = el("details", "technical-details review-evidence expand-detail");
    folded.append(el("summary", "", "展开完整机制详情"));
    const depth = el("p", "detail-row", `Core Design Depth：${readable.expandDetail.depth.before.coverage.toFixed(1)} → ${readable.expandDetail.depth.after.coverage.toFixed(1)}%`);
    folded.append(depth);
    const dependencies = el("ul", "qa-list");
    readable.expandDetail.crossMechanicReferences.forEach((ref) => dependencies.append(el(
      "li", "", `${relationNames[ref.relationType] || ref.relationType} ${mechanicNames[ref.targetMechanicId] || ref.targetMechanicId}`
    )));
    folded.append(el("h5", "readable-topic-title", "跨系统依赖"), dependencies);
    const original = el("ul", "qa-list");
    model.designItems.forEach((item) => original.append(el("li", "", item.text)));
    folded.append(el("h5", "readable-topic-title", "原始规则与依据"), original);
    const qaList = el("ul", "qa-list");
    readable.expandDetail.qaOutcomes.forEach((text) => qaList.append(el("li", "", text)));
    folded.append(el("h5", "readable-topic-title", "QA 可验证结果"), qaList);
    const gaps = el("ul", "qa-list");
    readable.expandDetail.remainingGaps.forEach((text) => gaps.append(el("li", "", text)));
    folded.append(el("h5", "readable-topic-title", "主策审核后仍需补齐"), gaps);
    article.append(folded);
    return article;
  };

  try {
    const response = await fetch("/api/mechanic-review", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    root.replaceChildren();
    if (payload.reviewState === "accepted" && payload.approvalSummary) {
      const notice = el("aside", "review-acceptance-notice");
      notice.append(
        el("strong", "", "本轮机制方案已全部接受"),
        el("span", "", `已批准 ${payload.approvalSummary.approvedRuleCount} 条设计规则；复用 ${payload.approvalSummary.retainedConfirmedRuleCount} 条已确认规则。`)
      );
      root.append(notice);
    }
    const readableById = new Map(payload.plannerReadabilityProjection.map((item) => [item.mechanicDesignId, item]));
    payload.models.forEach((model, index) => {
      const link = el("a", "nav-item", model.reviewTitle);
      link.href = `#mechanic-${index + 1}`;
      nav.append(link);
      root.append(renderModel(model, readableById.get(model.mechanicDesignId), index));
    });
  } catch (error) {
    root.replaceChildren(el("p", "error", `机制稿载入失败：${error.message}`));
  }
})();
