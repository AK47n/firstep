// fx/code-brackets.js 纯函数单测（工单 code-editor-vscode-polish/06）：
// 自动闭合（bracketOpen）/ 右括号跳过与整对替换（bracketClose）/
// 空括号对退格删除（bracketBackspace）/ 配对扫描
// （bracketPairAt——跳过字符串/字符/注释内假括号）。
// 直接 import；运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  bracketOpen,
  bracketClose,
  bracketBackspace,
  bracketPairAt,
  bracketDepthMarks,
} from "../../src/contest_generator/static/js/fx/code-brackets.js";

test("bracketOpen：空光标插入括号对、光标居中", () => {
  assert.deepEqual(bracketOpen("int x", 5, 5, "("),
    { value: "int x()", start: 6, end: 6 });
});

test("bracketOpen：有选区 → 括号对包裹选区", () => {
  const r = bracketOpen("ab", 1, 2, "{");
  assert.equal(r.value, "a{b}");
  assert.equal(r.start, 2);
  assert.equal(r.end, 2);   // 光标在开括号后
});

test("bracketClose：光标紧邻同款右括号 → 跳过不插入", () => {
  const r = bracketClose("a()", 2, 2, ")");
  assert.equal(r.value, "a()");
  assert.equal(r.start, 3);
  assert.equal(r.end, 3);
});

test("bracketClose：选区为成对括号 → 整对替换（typing over pair）", () => {
  const r = bracketClose("x()", 1, 3, "]");
  assert.equal(r.value, "x[]");
  assert.equal(r.start, 2);
  assert.equal(r.end, 2);
});

test("bracketClose：无跳过 / 无成对选区 → null（默认插入）", () => {
  assert.equal(bracketClose("ab", 1, 1, ")"), null);
  assert.equal(bracketClose("x(]", 1, 2, ")"), null);
});

test("bracketBackspace：空括号对中间退格 → 删除整对", () => {
  const r = bracketBackspace("a()", 2, 2);
  assert.equal(r.value, "a");
  assert.equal(r.start, 1);
  assert.equal(r.end, 1);
});

test("bracketBackspace：非空括号对 / 无选区 → null", () => {
  assert.equal(bracketBackspace("a(", 2, 2), null);       // 未闭合
  assert.equal(bracketBackspace("a()", 1, 2), null);      // 有选区
  assert.equal(bracketBackspace("ab", 1, 1), null);       // 非括号
});

test("bracketPairAt：光标在括号上/紧邻 → 配对位置（1 基行号）", () => {
  const text = "if (x) { y }";
  const openAt = text.indexOf("(");
  const closeAt = text.indexOf(")");
  assert.deepEqual(bracketPairAt(text, openAt), {   // 在 '(' 上
    open: { line: 1, start: openAt, end: openAt + 1 },
    close: { line: 1, start: closeAt, end: closeAt + 1 },
    openChar: "(",
    closeChar: ")",
  });
  assert.deepEqual(bracketPairAt(text, openAt + 1), {  // 紧邻 '(' 之后（光标在 x 前）
    open: { line: 1, start: openAt, end: openAt + 1 },
    close: { line: 1, start: closeAt, end: closeAt + 1 },
    openChar: "(",
    closeChar: ")",
  });
  const braceAt = text.indexOf("{");
  const r = bracketPairAt(text, braceAt);
  assert.equal(r.openChar, "{");
  assert.equal(r.closeChar, "}");
  assert.equal(r.open.start, braceAt);
  assert.equal(r.close.start, text.indexOf("}"));
});

test("bracketPairAt：无配对 / 光标不在括号 → null", () => {
  assert.equal(bracketPairAt("(", 0), null);
  assert.equal(bracketPairAt("int x;", 4), null);
});

test("bracketPairAt：跳过字符串与注释内假括号", () => {
  const text = 'printf("("); // (\nif (a) {}\n';
  const strOpen = text.indexOf('"(') + 1;     // 字符串内假 '('
  const comOpen = text.indexOf('//') + 3;     // 注释内假 '('
  const loneClose = text.indexOf(');');       // 字符串外的 ')'（真闭合 = printf 的真 '('）
  assert.equal(bracketPairAt(text, strOpen), null);
  assert.equal(bracketPairAt(text, comOpen), null);
  const r = bracketPairAt(text, loneClose);
  assert.equal(r.openChar, "(");
  assert.equal(r.open.start, 6);              // 第 1 行「printf(」的真 '('（列 6）
  const realOpen = text.indexOf('(a)');       // 真实 '('（if (a) 内，第 2 行）
  const r2 = bracketPairAt(text, realOpen);
  assert.equal(r2.openChar, "(");
  assert.equal(r2.closeChar, ")");
  assert.equal(r2.open.line, 2);
  assert.equal(r2.open.start, 3);             // "if (a)" 的 '(' 列 3
  assert.equal(r2.close.start, 5);            // 其配对 ')' 列 5
});

test("bracketPairAt：嵌套括号按深度配对", () => {
  const text = "f(g(h))";
  const g = text.indexOf("(g");          // 外层 '('
  const h = text.indexOf("(h");          // 内层 '('
  const outer = bracketPairAt(text, g);
  assert.equal(outer.open.start, g);
  assert.equal(outer.close.start, text.lastIndexOf(")"));
  const inner = bracketPairAt(text, h);
  assert.equal(inner.open.start, h);
  assert.equal(inner.close.start, h + 2);   // "(h)" 的 ')'（h 后两字符）
});

// ===== 括号彩虹深度标记（工单 code-editor-refine/04）=====

test("bracketDepthMarks：嵌套深度 0 基编号，开闭同深度；kind 带色环号", () => {
  const text = "f(g(h))";
  const simplified = bracketDepthMarks(text)
    .map((m) => [m.start, m.end, m.kind])
    .sort((a, b) => a[0] - b[0]);   // 渲染层按位置排序，断言不锁实现序
  assert.deepEqual(simplified, [
    [1, 2, "bracket-depth-0"],   // f( 开
    [3, 4, "bracket-depth-1"],   // g( 开
    [5, 6, "bracket-depth-1"],   // g( 闭
    [6, 7, "bracket-depth-0"],   // f( 闭
  ]);
  bracketDepthMarks(text).forEach((m) => {
    assert.equal(m.line, 1);
    assert.equal(m.end, m.start + 1);   // 单字符段
  });
});

test("bracketDepthMarks：字符串/注释内假括号不输出；跨行行号正确", () => {
  const text = 'printf("("); // (\nif (a) {}\n';
  const marks = bracketDepthMarks(text);
  const starts = new Set(marks.map((m) => m.line + ":" + m.start));
  assert.ok(starts.has("1:6"));     // printf( 真 '('
  assert.ok(starts.has("1:10"));    // 其 ')' 
  assert.ok(starts.has("2:3"));     // if (a) 的 '('
  assert.ok(starts.has("2:5"));     // 其 ')'
  assert.ok(starts.has("2:7"));     // { 
  assert.ok(starts.has("2:8"));     // }
  assert.ok(!starts.has("1:8"));    // 字符串内 '('
  assert.ok(!starts.has("1:16"));   // 注释内 '('
  assert.equal(marks.length, 6);
});

test("bracketDepthMarks：未配对开/闭括号不输出", () => {
  assert.deepEqual(bracketDepthMarks("("), []);
  assert.deepEqual(bracketDepthMarks(")"), []);
  assert.deepEqual(bracketDepthMarks("(x"), []);
  assert.deepEqual(bracketDepthMarks(")(("), []);        // 无配对
  assert.deepEqual(bracketDepthMarks("(a)("), [          // 仅第一对
    { line: 1, start: 0, end: 1, kind: "bracket-depth-0" },
    { line: 1, start: 2, end: 3, kind: "bracket-depth-0" },
  ]);
});

test("bracketDepthMarks：深嵌套按 8 色环取模（深度 8 → 同 0）", () => {
  const text = "{".repeat(9) + "}".repeat(9);
  const marks = bracketDepthMarks(text);
  assert.equal(marks.length, 18);
  assert.equal(marks[0].kind, "bracket-depth-0");   // 最内层（深度 8 → 0）
  assert.equal(marks[1].kind, "bracket-depth-0");
  assert.equal(marks[2].kind, "bracket-depth-7");
  assert.equal(marks[3].kind, "bracket-depth-7");
  assert.equal(marks[16].kind, "bracket-depth-0");  // 最外层（深度 0）
  assert.equal(marks[17].kind, "bracket-depth-0");
});
