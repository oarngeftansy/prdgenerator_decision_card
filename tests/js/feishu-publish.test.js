const test = require("node:test");
const assert = require("node:assert/strict");
const { makePublicationRequestId, renderFeishuPublication, publicationBusy, previewCanPublish } = require("../../js/feishu-publish.js");

test("not-published state exposes one primary export action", () => {
  const html = renderFeishuPublication({ status: "not_published" }, true);
  assert.match(html, /导出到飞书/);
  assert.match(html, /data-feishu-action="update"/);
});

test("published state exposes open, re-export, and new-version actions", () => {
  const html = renderFeishuPublication({ status: "published", documentUrl: "https://example.feishu.cn/docx/abc" }, true);
  assert.match(html, /打开飞书文档/);
  assert.match(html, /重新导出/);
  assert.match(html, /另存为新版本/);
});

test("published state reports the selected Feishu folder", () => {
  const html = FeishuPublish.renderFeishuPublication({ status: "published", documentUrl: "https://feishu.cn/docx/a", folderName: "策划组共享" }, true);
  assert.match(html, /保存位置：策划组共享/);
});

test("published folder names cannot inject markup", () => {
  const html = FeishuPublish.renderFeishuPublication({ status: "published", folderName: "<img src=x onerror=alert(1)>" }, true);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});

test("conflict explains that Feishu edits are protected", () => {
  const html = renderFeishuPublication({ status: "conflict" }, true);
  assert.match(html, /飞书文档已有修改/);
  assert.match(html, /不会覆盖/);
  assert.match(html, /另存为新版本/);
});

test("review invalidation conflict tells the user to regenerate the preview", () => {
  const html = renderFeishuPublication({ status: "conflict", message: "审核版本已变化，请重新生成导出预览。" }, false);
  assert.match(html, /审核版本已变化/);
  assert.match(html, /重新生成导出预览/);
  assert.doesNotMatch(html, /飞书文档已有修改/);
});

test("busy states disable duplicate publication", () => {
  assert.equal(publicationBusy("creating_document"), true);
  assert.equal(publicationBusy("uploading_board_media"), true);
  assert.equal(publicationBusy("published"), false);
  const html = renderFeishuPublication({ status: "uploading_board_media" }, true);
  assert.match(html, /正在上传策划草图素材/);
  assert.match(html, /disabled/);
});

test("publishing stays unavailable without a validated plan", () => {
  const html = renderFeishuPublication({ status: "not_published" }, false);
  assert.match(html, /完成策划案后可导出/);
  assert.match(html, /disabled/);
});

test("failed Feishu login exposes authorization CTA", () => {
  const html = renderFeishuPublication({ status: "failed", message: "飞书登录已过期" }, true);
  assert.match(html, /需要授权飞书/);
  assert.match(html, /data-feishu-action="auth"/);
  assert.match(html, /授权飞书并导出/);
});

test("partial state says the document exists but export is unfinished", () => {
  const html = renderFeishuPublication({ status: "partial", message: "飞书文档已创建，但导出尚未完成；可继续重试" }, true);
  assert.match(html, /文档已创建/);
  assert.match(html, /导出尚未完成/);
  assert.match(html, /重试导出/);
  assert.doesNotMatch(html, /飞书文档已保留/);
});

test("publication request ids satisfy the backend idempotency contract", () => {
  assert.match(makePublicationRequestId(), /^[A-Za-z0-9_-]{10,80}$/);
});

test("review publication requires a ready preview at the current revision", () => {
  assert.equal(previewCanPublish({ exportReady: true, revision: 4 }, { revision: 4 }), true);
  assert.equal(previewCanPublish({ exportReady: true, revision: 3 }, { revision: 4 }), false);
});

test("competitor mutation intent disables Feishu export with a visible retry explanation", () => {
  assert.equal(previewCanPublish({ exportReady: true, revision: 4 }, { revision: 4 }, true), false);
  const html = renderFeishuPublication(
    { status: "not_published" }, false, "竞品素材保存失败，请重试；成功后才能导出。",
  );
  assert.match(html, /竞品素材保存失败/);
  assert.match(html, /disabled/);
});

test("combined publication requires both preview revisions", () => {
  const preview = { exportReady: true, interactionRevision: 4, gameplayRevision: 7 };
  const models = { interaction: { revision: 4 }, gameplay: { revision: 7 } };
  assert.equal(previewCanPublish(preview, models, false), true);
  assert.equal(previewCanPublish(preview, { ...models, gameplay: { revision: 8 } }, false), false);
});
