const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";
const original = "载具沿预设路线自动前进；玩家可控制载具横向移动，以调整行进位置、规避敌人或对准攻击目标。";

(async () => {
  let model = await fetch(`${origin}/api/jobs/${jobId}/gameplay-review-model`).then(response => response.json());
  const operations = [];
  const first = model.directory.entries[0];
  if (first.summary !== original) operations.push({ type: "update_directory_entry_summary", entryId: first.id, summary: original });
  model.directory.entries.slice(7).filter(entry => !(entry.claimIds || []).length).forEach(entry => {
    operations.push({ type: "delete_directory_entry", entryId: entry.id });
  });
  if (operations.length) {
    model = await fetch(`${origin}/api/jobs/${jobId}/gameplay-review-model/operations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: model.revision, operations }),
    }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(JSON.stringify(body));
      return body;
    });
  }
  const result = { revision: model.revision, count: model.directory.entries.length, firstSummary: model.directory.entries[0].summary, operations };
  if (result.count !== 7 || result.firstSummary !== original) throw new Error(`清理失败：${JSON.stringify(result)}`);
  console.log(JSON.stringify(result, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
