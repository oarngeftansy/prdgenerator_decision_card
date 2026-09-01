const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";
const titles = [
  "战场推进与载具生存", "武器槽位与自动攻击", "局内升级与三选一强化",
  "终极强化与攻击形态变化", "武器抽取界面与结果确认", "关卡阶段与首领战",
  "挑战成功、奖励与伤害统计",
];

(async () => {
  let model = await fetch(`${origin}/api/jobs/${jobId}/gameplay-review-model`).then(response => response.json());
  const byTitle = new Map(model.directory.entries.map(entry => [entry.title, entry.id]));
  const entryIds = titles.map(title => byTitle.get(title));
  if (entryIds.some(id => !id)) throw new Error("无法按标题恢复目录顺序");
  if (model.directory.entries.some((entry, index) => entry.id !== entryIds[index])) {
    model = await fetch(`${origin}/api/jobs/${jobId}/gameplay-review-model/operations`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: model.revision, operations: [{ type: "reorder_directory_entries", entryIds }] }),
    }).then(response => response.json());
  }
  const result = { revision: model.revision, titles: model.directory.entries.map(entry => entry.title) };
  if (JSON.stringify(result.titles) !== JSON.stringify(titles)) throw new Error(JSON.stringify(result));
  console.log(JSON.stringify(result, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
