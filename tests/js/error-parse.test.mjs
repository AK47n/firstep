// parseError / parseHttpError / isLongError 纯函数单测（工单 ux-walkthrough-02/11）：
// 前端错误统一解析——fetch（handle 抛的 Error{status,message}）/ SSE 内联
// （{detail,status}）/ AbortError / 字符串 / null；长错误策略判定。
import test from "node:test";
import assert from "node:assert/strict";
import {
  parseError, parseHttpError, isLongError, ERROR_LONG_THRESHOLD,
} from "../../src/contest_generator/static/js/fx/errors.js";

test("parseError：HTTP 错误带状态码且消息含 HTTP 前缀（含 detail）", () => {
  const p = parseError({ status: 400, detail: "备份编号不合法（x）" });
  assert.equal(p.text, "请求失败（HTTP 400）：备份编号不合法（x）");
  assert.equal(p.status, 400);
  assert.equal(p.kind, "error");
});

test("parseError：5xx → kind=server（长错误策略命中）", () => {
  const p = parseError({ status: 502, message: "AI 服务失败" });
  assert.equal(p.status, 502);
  assert.equal(p.kind, "server");
  assert.match(p.text, /^请求失败（HTTP 502）：AI 服务失败/);
});

test("parseError：message 已带请求失败前缀不重复叠加", () => {
  const p = parseError({ status: 404, message: "请求失败（HTTP 404）：页面不存在" });
  assert.equal(p.text, "请求失败（HTTP 404）：页面不存在");
});

test("parseError：AbortError → 取消语义", () => {
  const err = new Error("aborted");
  err.name = "AbortError";
  const p = parseError(err);
  assert.equal(p.kind, "cancelled");
  assert.match(p.text, /请求已取消/);
});

test("parseError：网络断 / 字符串 / null / 空对象兜底", () => {
  const net = parseError(new TypeError("Failed to fetch"));
  assert.equal(net.status, null);
  assert.equal(net.text, "Failed to fetch");
  assert.equal(parseError("纯文案").text, "纯文案");
  assert.equal(parseError(null).text, "请求失败（未知原因）");
  assert.equal(parseError({}).text, "请求失败（未知原因）");
  assert.equal(parseError(undefined, "自定义兜底").text, "自定义兜底");
});

test("parseHttpError：状态码 + 错误体归一（SSE 内联共用路径）", () => {
  assert.equal(
    parseHttpError(400, { detail: "缺少必填字段：name" }).text,
    "请求失败（HTTP 400）：缺少必填字段：name"
  );
  const f500 = parseHttpError(500, { detail: "服务器内部错误" });
  assert.equal(f500.kind, "server");
  assert.equal(parseHttpError("abc", {}).status, null);  // 非法状态兜底 null
  // json 解析失败（空错误体）：不留悬空冒号（评审整改）
  assert.equal(parseHttpError(400, {}).text, "请求失败（HTTP 400）");
});

test("isLongError：5xx（kind 单源）或超阈值 → true；短业务错误 → false", () => {
  assert.equal(isLongError({ kind: "server", status: 500, text: "x" }), true);
  assert.equal(isLongError({ kind: "error", status: 400, text: "短" }), false);
  assert.equal(isLongError({ kind: "unknown", status: null, text: "短" }), false);
  assert.equal(isLongError({ kind: "error", status: null, text: "长".repeat(ERROR_LONG_THRESHOLD + 1) }), true);
  assert.equal(isLongError(null), false);
});
