// 测试 fx/fix-rows.js —— 修复结果行 HTML（工单 code-ide-ai/06）。
import test from "node:test";
import assert from "node:assert/strict";
import { fixRowHTML } from "../../src/contest_generator/static/js/fx/fix-rows.js";

test("applied → 已修复/fixed + file:line + reason", () => {
  const html = fixRowHTML({ file: "main.c", line: 3, status: "applied", reason: "补了分号" });
  assert.ok(html.includes("fix-tag fixed"));
  assert.ok(html.includes("已修复"));
  assert.ok(html.includes("main.c:3"));
  assert.ok(html.includes("补了分号"));
});

test("skipped / 其他状态 → 跳过/skipped", () => {
  const html = fixRowHTML({ file: "src/app.c", status: "skipped", reason: "无匹配上下文" });
  assert.ok(html.includes("fix-tag skipped"));
  assert.ok(html.includes("跳过"));
});

test("内容转义（防注入）：file/reason 含 <script>", () => {
  const html = fixRowHTML({
    file: '<img src=x onerror=alert(1)>', status: "applied",
    reason: '<script>alert(2)</script>',
  });
  assert.ok(!html.includes("<script>"), "reason 不许含原始 <script>");
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;script&gt;"));
});

test("缺 file → 用 path 兜底「?」；无 line 不带冒号", () => {
  const html = fixRowHTML({ path: "readme.md", status: "applied", reason: "ok" });
  assert.ok(html.includes("readme.md"));
  assert.ok(!html.includes(":"));
  const empty = fixRowHTML({ status: "skipped" });
  assert.ok(empty.includes("?"));
});

test("无 item（null/undefined）不抛错", () => {
  const html = fixRowHTML(null);
  assert.ok(html.includes("fix-row"));
});
