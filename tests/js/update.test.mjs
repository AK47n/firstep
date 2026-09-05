// update.test.mjs — 应用内一键更新纯函数单测（工单 auto-update/06）：
// updateStateText / updateCheckCardHTML（有新版 / 已最新 / 网络失败 / 无资产
// 四分支）/ updateStatusHTML（applying / failed / done-ok / done-failed）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  updateStateText,
  updateCheckCardHTML,
  updateStatusHTML,
} from "../../src/contest_generator/static/js/fx/update.js";

test("updateStateText 映射四态", () => {
  assert.equal(updateStateText("idle"), "");
  assert.match(updateStateText("applying"), /自动重启/);
  assert.match(updateStateText("failed"), /未完成/);
  assert.match(updateStateText("done"), /完成/);
  assert.equal(updateStateText("unknown"), "");
});

test("check 结果卡：有新版 → 版本/大小/说明 + 一键更新按钮", () => {
  const html = updateCheckCardHTML({
    current_version: "1.0.0",
    latest_version: "1.1.0",
    update_available: true,
    size_bytes: 300 * 1024 * 1024,
    release_notes: "第一行说明\n第二行说明\n第三行说明\n第四行被截断",
    error: "",
    message: "",
  });
  assert.match(html, /发现新版本/);
  assert.match(html, /v1\.1\.0/);
  assert.match(html, /约 300 MB/);
  assert.match(html, /第一行说明/);
  assert.match(html, /第二行说明/);
  assert.match(html, /第三行说明/);
  assert.doesNotMatch(html, /第四行被截断/);
  assert.match(html, /btn-update-apply/);
  assert.match(html, /一键更新/);
});

test("check 结果卡：已是最新", () => {
  const html = updateCheckCardHTML({
    latest_version: "1.0.0", update_available: false, error: "", message: "",
  });
  assert.match(html, /已是最新版本/);
});

test("check 结果卡：网络失败（200 级 error）", () => {
  const html = updateCheckCardHTML({
    error: "network", message: "检查更新失败（网络原因），请检查网络后重试",
  });
  assert.match(html, /网络原因/);
  assert.doesNotMatch(html, /btn-update-apply/);
});

test("check 结果卡：无资产提示", () => {
  const html = updateCheckCardHTML({
    error: "no-asset", latest_version: "1.2.0",
    message: "最新版本没有发布更新包，请等待更新包发布",
  });
  assert.match(html, /没有发布更新包/);
  assert.match(html, /1\.2\.0/);
});

test("check 结果卡：release_notes 含 HTML 会被转义（XSS 防护）", () => {
  const html = updateCheckCardHTML({
    latest_version: "1.1.0", update_available: true,
    release_notes: "<script>alert(1)</script>", error: "", message: "",
  });
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
});

test("status 卡：applying / failed / done-ok / done-failed", () => {
  assert.match(updateStatusHTML({ state: "applying" }), /更新进行中/);
  const failed = updateStatusHTML({ state: "failed", message: "上次更新未完成", result: null });
  assert.match(failed, /更新失败/);
  const doneOk = updateStatusHTML({ state: "done", result: { status: "ok", version: "v1.1.0" } });
  assert.match(doneOk, /已更新到 v1\.1\.0/);
  assert.match(doneOk, /重新打开/);
  const doneFail = updateStatusHTML({
    state: "done",
    result: { status: "failed", error: "zip slip", backup_dir: "C:/backup" },
  });
  assert.match(doneFail, /上次更新失败/);
  assert.match(doneFail, /zip slip/);
});
