// makeAbortable / isAbortError 纯函数单测（工单 ux-walkthrough-02/14）：
// 中止器生命周期（begin 新实例/abort 幂等/clear）、取消错误识别。
import test from "node:test";
import assert from "node:assert/strict";
import {
  makeAbortable, isAbortError,
} from "../../src/contest_generator/static/js/fx/abortable.js";

test("makeAbortable：begin 给新 signal，abort 后 signal.aborted = true", () => {
  const a = makeAbortable();
  assert.equal(a.isActive(), false);
  const signal = a.begin();
  assert.equal(a.isActive(), true);
  assert.equal(signal.aborted, false);
  assert.equal(a.abort(), true);
  assert.equal(signal.aborted, true);
});

test("makeAbortable：重复取消幂等（第二次 false），clear 后无操作", () => {
  const a = makeAbortable();
  a.begin();
  assert.equal(a.abort(), true);
  assert.equal(a.abort(), false);      // 已取消再取消 = 无操作
  a.clear();
  assert.equal(a.isActive(), false);
  assert.equal(a.abort(), false);      // 无进行中请求 = 无操作
});

test("makeAbortable：begin 重启 = 新一轮（旧实例作废）", () => {
  const a = makeAbortable();
  const s1 = a.begin();
  const s2 = a.begin();
  assert.notEqual(s1, s2);
  assert.equal(s2.aborted, false);
  assert.equal(s1.aborted, false);     // 旧实例未被新 begin 取消
  assert.equal(a.abort(), true);       // 只取消当前轮
  assert.equal(s2.aborted, true);
  assert.equal(s1.aborted, false);
});

test("isAbortError：AbortError 识别；普通错误/网络错误不误报", () => {
  const abortErr = new DOMException("aborted", "AbortError");
  assert.equal(isAbortError(abortErr), true);
  assert.equal(isAbortError(new Error("network")), false);
  assert.equal(isAbortError(new TypeError("Failed to fetch")), false);
  assert.equal(isAbortError(null), false);
  const fake = { name: "AbortError", message: "x" };
  assert.equal(isAbortError(fake), true);
});
