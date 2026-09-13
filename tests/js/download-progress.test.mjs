// download-progress.test.mjs — 下载进度/失败话术的纯函数测试（工单 resumable-download/05）
//
// 判的是什么：界面上「慢」「在重试」「真失败」要长得不一样。三者过去都是
// 「进度条不动 + 一行原始异常」，用户分不清该等还是该换网（spec 问题陈述第 3 条）。
//
// 四条状态的关键文案在场与**互斥**（不许两种话术同时出现），以及
// 「前端不许解析 error 文案」这条硬约定——分类只认 error_kind 字段。
import test from "node:test";
import assert from "node:assert/strict";

import {
  fmtEta, downloadFailureText, retryNoteText, SLOW_SPEED_BPS,
} from "../../src/contest_generator/static/js/fx/core.js";
import { fullProgressHTML, fullResultText } from "../../src/contest_generator/static/js/fx/full-update.js";
import { materialsProgressHTML } from "../../src/contest_generator/static/js/fx/materials-update.js";

function fullStatus(overrides = {}) {
  return {
    state: "downloading",
    parts: [{ name: "p1.zip", downloaded_bytes: 0, total_bytes: 1000, ok: false }],
    total_downloaded_bytes: 0,
    total_bytes: 1000,
    speed_bps: 1024 * 1024,
    current_part_name: "p1.zip",
    error: "",
    message: "",
    retry_count: 0,
    retrying: false,
    error_kind: "",
    ...overrides,
  };
}

test("fmtEta：边界（0 / 59 秒 / 60 秒 / 59 分 / 60 分 / 极大值）", () => {
  assert.equal(fmtEta(0), "不到 1 分钟");
  assert.equal(fmtEta(59), "不到 1 分钟");
  assert.equal(fmtEta(60), "约 1 分钟");
  assert.equal(fmtEta(30 * 60), "约 30 分钟");
  assert.equal(fmtEta(59 * 60), "约 59 分钟");
  assert.equal(fmtEta(60 * 60), "约 1 小时");
  assert.equal(fmtEta(80 * 60), "约 1 小时 20 分");
  assert.equal(fmtEta(100 * 3600), "约 99 小时以上");
  // 非法输入不产出 NaN / undefined 文案
  for (const bad of [undefined, null, NaN, Infinity, -5, "abc"]) {
    assert.equal(fmtEta(bad), "不到 1 分钟", String(bad));
  }
});

test("fmtEta 词形与 fmtDuration 同源（小时 / 分，不另起一套）", () => {
  assert.match(fmtEta(80 * 60), /小时/);
  assert.match(fmtEta(80 * 60), /分/);
  assert.match(fmtEta(12 * 60), /分钟/);
});

test("慢：速度低于阈值 → 明写「网络较慢」；达标则不写", () => {
  const slow = fullProgressHTML(fullStatus({ speed_bps: SLOW_SPEED_BPS - 1 }));
  assert.match(slow, /网络较慢/);
  const fast = fullProgressHTML(fullStatus({ speed_bps: SLOW_SPEED_BPS * 4 }));
  assert.doesNotMatch(fast, /网络较慢/);
  // 慢 ≠ 失败：慢的时候不该出现失败话术与重试按钮
  assert.doesNotMatch(slow, /网络中断/);
  assert.doesNotMatch(slow, /btn-full-retry/);
});

test("在重试：次数 / 原因 / 从多少接着下 各从自己的字段来（不许解析文案）", () => {
  const html = fullProgressHTML(fullStatus({
    retrying: true,
    retry_count: 3,
    message: "连接中断：本次声明 2097152 字节，只收到 838860 字节",
    resume_percent: 39,
  }));
  assert.match(html, /正在自动重试（第 3 次）/);
  assert.match(html, /连接中断/);
  assert.match(html, /从 39% 接着下/);
  // 同一件事不许说两遍（次数只出现在前缀里）
  assert.equal((html.match(/第 3 次/g) || []).length, 1);
  assert.doesNotMatch(html, /网络中断（已下载/);   // 不是失败话术
  assert.doesNotMatch(html, /btn-full-retry/);      // 重试中不给「重试」按钮
  assert.match(html, /btn-full-cancel/);            // 但要能取消
});

test("在重试：次数与百分比只认字段，不认文案里的数字", () => {
  // `message` 是「原因」这句话（后端保证），里面的数字属于原因本身，原样显示没问题；
  // 但**次数与百分比**必须来自字段——这条判据就是防「从文案里抠数字」那种写法回来。
  const html = fullProgressHTML(fullStatus({
    retrying: true,
    retry_count: 2,
    message: "连接中断（对端第 9 次重连）",
    resume_percent: 12,
  }));
  assert.match(html, /正在自动重试（第 2 次）/);
  assert.match(html, /从 12% 接着下/);
  assert.doesNotMatch(html, /88%/);        // 字段里没有的百分比，界面上不许出现
});

test("在重试：总量未知（resume_percent = -1）就不写百分比，也不编造原因", () => {
  const known = fullProgressHTML(fullStatus({
    retrying: true, retry_count: 1, resume_percent: -1, message: "",
  }));
  assert.match(known, /正在自动重试（第 1 次）：网络中断/);
  assert.doesNotMatch(known, /从 \d+% 接着下/);
});

test("失败话术两类互斥：verify 说「重下也不会有变化」，网络类说「接着下」", () => {
  const verify = downloadFailureText({
    state: "failed", error_kind: "verify",
    total_bytes: 1000, total_downloaded_bytes: 500,
  });
  const network = downloadFailureText({
    state: "failed", error_kind: "network",
    total_bytes: 1000, total_downloaded_bytes: 500,
  });
  assert.match(verify, /校验失败/);
  assert.match(verify, /重新下载也不会有变化/);
  assert.doesNotMatch(verify, /接着下/);
  assert.match(network, /网络中断/);
  assert.match(network, /已下载 50%/);
  assert.match(network, /接着下/);
  assert.doesNotMatch(network, /校验失败/);
  // 空 error_kind 归到网络类（spec：其余 → 网络话术）
  assert.match(downloadFailureText({ state: "failed", error_kind: "" }), /网络中断/);
  assert.doesNotMatch(verify, /网络中断/);
});

test("失败视图：两态话术互斥在场，且原始 error 只作明细", () => {
  const verify = fullProgressHTML(fullStatus({
    state: "failed", error_kind: "verify",
    error: "卷 p1.zip 校验失败（SHA256 不匹配）",
  }));
  assert.match(verify, /重新下载也不会有变化/);
  assert.doesNotMatch(verify, /点击重试会从这里接着下/);
  assert.match(verify, /SHA256 不匹配/);      // 明细保留，便于反馈
  // 校验失败**不给「重试」按钮**：文案刚说「重下也不会有变化」，再摆按钮就是自相矛盾
  assert.doesNotMatch(verify, /btn-full-retry/);

  const network = fullProgressHTML(fullStatus({
    state: "failed", error_kind: "network",
    error: "下载失败（卷 p1.zip）：连接中断",
  }));
  assert.match(network, /点击重试会从这里接着下/);
  assert.doesNotMatch(network, /重新下载也不会有变化/);
  assert.match(network, /btn-full-retry/);
});

test("前端不许解析 error 文案：文案乱写也不影响分类", () => {
  // 同样的 error 文案，分类不同 → 话术必须不同（说明判据是字段不是文案）
  const noise = "某天改了文案：网络中断 / 校验失败 两个词混在一起";
  const asVerify = downloadFailureText({ error_kind: "verify", error: noise });
  const asNetwork = downloadFailureText({ error_kind: "network", error: noise });
  assert.notEqual(asVerify, asNetwork);
  assert.match(asVerify, /重新下载也不会有变化/);
  assert.match(asNetwork, /接着下/);
});

test("完成行：重试过就留痕（它自己扛过去了），没重试就不提", () => {
  assert.match(fullResultText({ state: "done", version: "v1.1.0", retry_count: 2 }),
    /自动重试 2 次/);
  assert.doesNotMatch(fullResultText({ state: "done", version: "v1.1.0", retry_count: 0 }),
    /自动重试/);
});

test("取消：说明已下部分会保留（不再是「从头再来」）", () => {
  const text = fullResultText({ state: "cancelled" });
  assert.match(text, /已取消/);
  assert.match(text, /保留/);
});

test("资料库链路口径与完整包一致（同一套字段 → 同一套文案）", () => {
  const status = {
    state: "failed",
    parts: [],
    total_bytes: 1000,
    total_downloaded_bytes: 250,
    speed_bps: 0,
    current_part_name: "",
    error: "下载失败（卷 k230.zip）：连接中断",
    message: "",
    retry_count: 0,
    retrying: false,
    error_kind: "network",
    resume_percent: -1,
  };
  const html = materialsProgressHTML(status);
  assert.match(html, /网络中断（已下载 25%）/);
  assert.match(html, /点击重试会从这里接着下/);

  const retrying = materialsProgressHTML({
    ...status, state: "downloading", retrying: true, retry_count: 2,
    message: "连接中断", resume_percent: 25, error: "",
  });
  assert.match(retrying, /正在自动重试（第 2 次）/);
  assert.match(retrying, /从 25% 接着下/);
  assert.doesNotMatch(retrying, /网络中断（已下载/);

  // 完成行与完整包同一口径：重试过要留痕
  const done = materialsProgressHTML({
    ...status, state: "done", retry_count: 2, error: "",
  });
  assert.match(done, /资料库更新完成（下载中自动重试 2 次）/);
});

test("弱网 + 重试 + 失败三态在资料库链路上同样互斥", () => {
  const slow = materialsProgressHTML({
    state: "downloading", parts: [], total_bytes: 1000, total_downloaded_bytes: 10,
    speed_bps: 20 * 1024, current_part_name: "k230.zip", error: "", message: "",
    retry_count: 0, retrying: false, error_kind: "", resume_percent: -1,
  });
  assert.match(slow, /网络较慢/);
  assert.doesNotMatch(slow, /正在自动重试/);
  assert.doesNotMatch(slow, /网络中断/);
});

test("完成行留痕两条链路同源（retryNoteText 单源）", () => {
  assert.equal(retryNoteText(0), "");
  assert.equal(retryNoteText(undefined), "");
  assert.match(retryNoteText(3), /自动重试 3 次/);
  assert.match(fullResultText({ state: "done", retry_count: 1 }), /自动重试 1 次/);
});
