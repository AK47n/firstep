// full-update.test.mjs — 完整包更新纯函数测试（工单 full-download/05）
//
// 覆盖：检查结果卡片（未知版本 / 有新版本 / 已是最新 / 各类降级）、确认弹窗、
// 下载进度（进度条 / 当前卷 / 速度 / 剩余时间 / 分卷列表）、终态文案（完成 /
// 失败 / 取消 / 重启中）、未知状态兜底、XSS 转义。
import test from "node:test";
import assert from "node:assert/strict";

import {
  fullCheckCardHTML,
  fullConfirmHTML,
  fullProgressHTML,
  fullStateText,
  fullResultText,
  fullPlanText,
} from "../../src/contest_generator/static/js/fx/full-update.js";

test("fullCheckCardHTML：未知版本 → 提示可下完整包", () => {
  const html = fullCheckCardHTML({
    current_version: "",
    latest_version: "v1.1.0",
    update_available: true,
    total_bytes: 1024 * 1024 * 1024,
    parts: [{ name: "a.zip", size: 1, sha256: "x", url: "u" }],
    reason: "no-installed",
    error: "",
    message: "本地完整包版本未知",
  });
  assert.match(html, /v1\.1\.0/);
  assert.match(html, /1024 MB|1\.0 GB/);
  assert.match(html, /btn-full-download/);
});

test("fullCheckCardHTML：有新版 → 显示当前→最新与体积", () => {
  const html = fullCheckCardHTML({
    current_version: "v1.0.0",
    latest_version: "v1.1.0",
    update_available: true,
    total_bytes: 512 * 1024 * 1024,
    parts: [
      { name: "p1.zip", size: 1, sha256: "x", url: "u" },
      { name: "p2.zip", size: 1, sha256: "y", url: "v" },
    ],
    reason: "outdated",
    error: "",
    message: "",
  });
  assert.match(html, /v1\.0\.0/);
  assert.match(html, /v1\.1\.0/);
  assert.match(html, /2 卷/);
  assert.match(html, /512 MB/);
});

test("fullCheckCardHTML：已是最新 → 仍给主动重下入口", () => {
  const html = fullCheckCardHTML({
    current_version: "v1.1.0",
    latest_version: "v1.1.0",
    update_available: false,
    total_bytes: 512 * 1024 * 1024,
    parts: [{ name: "p1.zip", size: 1, sha256: "x", url: "u" }],
    reason: "up-to-date",
    error: "",
    message: "已是最新完整包",
  });
  assert.match(html, /已是最新/);
  assert.match(html, /btn-full-download/);
  assert.match(html, /重新下载/);
});

test("fullCheckCardHTML：错误态文案走 message，不抛", () => {
  for (const error of ["network", "no-release", "no-asset", "bad-manifest"]) {
    const html = fullCheckCardHTML({
      current_version: "",
      latest_version: "",
      update_available: false,
      total_bytes: 0,
      parts: [],
      reason: "",
      error,
      message: "中文提示",
    });
    assert.match(html, /中文提示/);
    assert.doesNotMatch(html, /btn-full-download/);
  }
});

test("fullCheckCardHTML：无 message 时有兜底文案", () => {
  const html = fullCheckCardHTML({ error: "network", parts: [] });
  assert.match(html, /network|网络|失败/);
});

test("fullConfirmHTML：版本 + 总量 + 分卷数 + 开始按钮", () => {
  const html = fullConfirmHTML({
    latest_version: "v1.1.0",
    total_bytes: 1024 * 1024 * 1024,
    parts: [
      { name: "p1.zip", size: 1, sha256: "x", url: "u" },
      { name: "p2.zip", size: 1, sha256: "y", url: "v" },
    ],
  });
  assert.match(html, /v1\.1\.0/);
  assert.match(html, /2 卷/);
  assert.match(html, /btn-full-start/);
  assert.match(html, /重启/);
  // 取消由弹窗骨架的 data-confirm-cancel 承担，内容区不重复
  assert.doesNotMatch(html, /data-confirm-cancel/);
});

test("fullProgressHTML：进度条宽度 / 当前卷 / 速度 / 剩余时间", () => {
  const html = fullProgressHTML({
    state: "downloading",
    parts: [
      { name: "p1.zip", downloaded_bytes: 100, total_bytes: 100, ok: true },
      { name: "p2.zip", downloaded_bytes: 50, total_bytes: 150, ok: false },
    ],
    total_downloaded_bytes: 150,
    total_bytes: 250,
    speed_bps: 50 * 1024 * 1024,
    current_part_name: "p2.zip",
    error: "",
    message: "",
  });
  assert.match(html, /width:60%/);
  assert.match(html, /p2\.zip/);
  assert.match(html, /50\.0 MB\/s/);
  // 剩余时间说人话（工单 resumable-download/05）：不再是「剩余 N 秒」
  assert.match(html, /不到 1 分钟/);
  assert.doesNotMatch(html, /剩余 \d+ 秒/);
  assert.match(html, /btn-full-cancel/);
});

test("fullProgressHTML：总量为 0 不出现 NaN", () => {
  const html = fullProgressHTML({
    state: "idle",
    parts: [],
    total_downloaded_bytes: 0,
    total_bytes: 0,
    speed_bps: 0,
    current_part_name: "",
    error: "",
    message: "",
  });
  assert.doesNotMatch(html, /NaN/);
  assert.match(html, /width:0%/);
});

test("fullProgressHTML：失败态显示中文错误", () => {
  const html = fullProgressHTML({
    state: "failed",
    parts: [],
    total_downloaded_bytes: 0,
    total_bytes: 100,
    speed_bps: 0,
    current_part_name: "",
    error: "下载失败（卷 p1.zip）：模拟断网",
    message: "",
  });
  assert.match(html, /模拟断网/);
  assert.match(html, /btn-full-retry/);
});

test("fullStateText：状态 → 中文文案", () => {
  assert.equal(fullStateText("idle"), "等待开始…");
  assert.match(fullStateText("downloading"), /下载/);
  assert.match(fullStateText("applying"), /重启|替换|应用/);
  assert.match(fullStateText("done"), /完成|重启/);
  assert.match(fullStateText("failed"), /失败/);
  assert.match(fullStateText("cancelled"), /取消/);
  assert.equal(fullStateText("不存在的状态"), "");
});

test("fullResultText：终态文案（完成提示重启 / 取消说明保留卷）", () => {
  assert.match(fullResultText({ state: "done", version: "v1.1.0" }), /v1\.1\.0/);
  assert.match(fullResultText({ state: "cancelled" }), /已完成|保留/);
  assert.equal(fullResultText({ state: "downloading" }), "");
});

test("fullPlanText：体积与卷数描述（GB / MB 自适应）", () => {
  assert.match(fullPlanText(1024 * 1024 * 1024, 1), /1\.0 GB/);
  assert.match(fullPlanText(300 * 1024 * 1024, 2), /300 MB/);
  assert.match(fullPlanText(300 * 1024 * 1024, 2), /2 卷/);
  assert.match(fullPlanText(0, 0), /未知/);
});

test("转义：名字与错误里的 HTML 被转义", () => {
  const html = fullProgressHTML({
    state: "failed",
    parts: [{ name: "<img src=x onerror=alert(1)>", downloaded_bytes: 0, total_bytes: 1, ok: false }],
    total_downloaded_bytes: 0,
    total_bytes: 1,
    speed_bps: 0,
    current_part_name: "<script>bad()</script>",
    error: "<b>坏</b>",
    message: "",
  });
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(html, /<img src=x/);
  assert.match(html, /&lt;/);
});
