const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

test("所有飞书发布入口统一经过登录授权检查", () => {
  const source = fs.readFileSync(path.join(__dirname, "../../js/app.js"), "utf8");
  assert.match(
    source,
    /publishToFeishuWithAuthorization\(action\.dataset\.feishuAction\)/,
  );
  assert.doesNotMatch(
    source,
    /publishToFeishu\(action\.dataset\.feishuAction\)/,
  );
});
