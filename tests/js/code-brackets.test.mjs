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
