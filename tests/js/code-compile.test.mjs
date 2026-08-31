// fx/code-compile.js 纯函数单测（工单 code-tab-compile/03）：状态行 / 错误行
// HTML。直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  compileStatusText,
  compileStatusClass,
  compileErrorRowsHTML,
} from "../../src/contest_generator/static/js/fx/code-compile.js";

test("compileStatusText：成功/失败/超时状态行（单源 = fx/generate.js 同文案）", () => {
  assert.equal(compileStatusText(null), "");
  const ok = {
    passed: true, timed_out: false, duration: 12.34,
    summary: { errors: 0, warnings: 2 },
  };
  assert.match(compileStatusText(ok), /编译成功 · 0 Error 2 Warning · 耗时 12.3s/);
  const fail = {
    passed: false, timed_out: false, duration: 5.1,
    summary: { errors: 3, warnings: 0 },
  };
  assert.match(compileStatusText(fail), /编译失败 · 3 个错误 · 耗时 5.1s/);
  const to = {
    passed: false, timed_out: true, duration: 180,
    summary: { errors: 0, warnings: 0 },
  };
  assert.equal(compileStatusText(to), "编译超时（工具链 180s 未返回）");
});

test("compileStatusClass：配色类（ok / err / 运行中与超时不着色）", () => {
  assert.equal(compileStatusClass(null), "");
  assert.equal(compileStatusClass({ passed: true, timed_out: false }), "ok");
  assert.equal(compileStatusClass({ passed: false, timed_out: false }), "err");
  assert.equal(compileStatusClass({ passed: false, timed_out: true }), "");
});

test("compileErrorRowsHTML：路径+行号+消息 + 转义 + 空态", () => {
  const html = compileErrorRowsHTML([
    { path: "main.c", line: 45, message: "use of undeclared identifier 'y'" },
    { path: "src/app.h", line: 2, message: "<script>x</script>" },
  ]);
  assert.match(html, /data-compile-path="main\.c" data-compile-line="45"/);
  assert.match(html, /main\.c:45/);
  assert.match(html, /src\/app\.h:2/);
  assert.ok(html.includes("&lt;script&gt;"));         // 转义
  assert.ok(!html.includes("<script>"));
  assert.ok(html.includes("use of undeclared"));
  const empty = compileErrorRowsHTML([]);
  assert.match(empty, /无结构化错误信息/);
});
