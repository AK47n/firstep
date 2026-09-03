// fx/code-compile.js 纯函数单测（工单 code-tab-compile/03）：状态行 / 错误行
// HTML。直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  compileStatusText,
  compileStatusClass,
  compileErrorRowsHTML,
  compileErrorLinesForFile,
  compileErrorPathNorm,
  compileErrorPathBase,
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

// ---- 错误行映射（工单 code-editor-refine/05：行号色点 + 错误行标记）----

test("compileErrorPathNorm/Base：POSIX 归一（\\→/、去 . 段、保 ..）+ basename", () => {
  assert.equal(compileErrorPathNorm("..\\Core\\Src\\main.c"), "../Core/Src/main.c");
  assert.equal(compileErrorPathNorm("./Core/Src/main.c"), "Core/Src/main.c");
  assert.equal(compileErrorPathNorm("a/./b/"), "a/b");
  assert.equal(compileErrorPathNorm(""), "");
  assert.equal(compileErrorPathBase("Core\\Src\\main.c"), "main.c");
  assert.equal(compileErrorPathBase(""), "");
});

const ERR = [
  { path: "Core/Src/main.c", line: 7, message: "未声明标识符 'x'" },
  { path: "..\\Core\\Src\\main.c", line: 7, message: "第二处错误（反斜杠 + ..\\ 前缀归一）" },
  { path: "./Core/Src/main.c", line: 12, message: "./ 前缀归一" },
  { path: "Core/Inc/led.h", line: 3, message: "无符号比较" },
  { path: "Core/Src/main.c", line: 0, message: "无行号错误（line 0 跳过）" },
  { path: "Core/Src/main.c", line: 19, message: "" },
];

test("compileErrorLinesForFile：path 归一（\\→/、去 ./、全等→basename 兜底）+ 按 line 排序", () => {
  assert.deepEqual(compileErrorLinesForFile(ERR, "Core/Src/main.c"), [
    { line: 7, message: "未声明标识符 'x'\n第二处错误（反斜杠 + ..\\ 前缀归一）" },
    { line: 12, message: "./ 前缀归一" },
    { line: 19, message: "" },
  ]);
  assert.deepEqual(compileErrorLinesForFile(ERR, "Core\\Src\\main.c"), [
    { line: 7, message: "未声明标识符 'x'\n第二处错误（反斜杠 + ..\\ 前缀归一）" },
    { line: 12, message: "./ 前缀归一" },
    { line: 19, message: "" },
  ]);
});

test("compileErrorLinesForFile：basename 兜底（路径不匹配但文件名一致）", () => {
  assert.deepEqual(compileErrorLinesForFile(
    [{ path: "build/dir/Core/Src/main.c", line: 42, message: "basename 命中" }],
    "Core/Src/main.c"
  ), [{ line: 42, message: "basename 命中" }]);
});

test("compileErrorLinesForFile：无匹配文件 / 空输入 → []；line 0 与非法行跳过", () => {
  assert.deepEqual(compileErrorLinesForFile(ERR, "Other/file.c"), []);
  assert.deepEqual(compileErrorLinesForFile([], "Core/Src/main.c"), []);
  assert.deepEqual(compileErrorLinesForFile(null, "Core/Src/main.c"), []);
  assert.deepEqual(compileErrorLinesForFile(
    [{ path: "Core/Src/main.c", line: 0, message: "skip" },
      { path: "Core/Src/main.c", line: -3, message: "skip" },
      { path: "Core/Src/main.c", line: "abc", message: "skip" }],
    "Core/Src/main.c"
  ), []);
});
