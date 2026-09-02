// 滚动窗口化纯件单测（工单 code-page-vscode-overhaul/08）：
// codeWindowRange（滚动窗口范围）与 gutter 分段（codeGutterLineHTML /
// codeFoldGutterLines）。期望值全部手工推算。
import test from "node:test";
import assert from "node:assert/strict";
import { codeWindowRange } from "../../src/contest_generator/static/js/fx/codeeditor.js";
import { codeGutterLineHTML } from "../../src/contest_generator/static/js/fx/codeview.js";
import { codeFoldGutterLines, codeFoldGutterHTML } from "../../src/contest_generator/static/js/fx/code-fold.js";

test("codeWindowRange：空文档 → {0,0}", () => {
  assert.deepEqual(codeWindowRange(0, 500, 20, 0, 10), { start: 0, end: 0 });
});

test("codeWindowRange：顶部窗口（含 overscan 与层顶 padding 8px）", () => {
  assert.deepEqual(codeWindowRange(0, 500, 20, 100, 10), { start: 0, end: 35 });
});

test("codeWindowRange：中部滚动窗口", () => {
  assert.deepEqual(codeWindowRange(1000, 500, 20, 100, 10), { start: 39, end: 85 });
});

test("codeWindowRange：底部钳制（end = lineCount）", () => {
  const r = codeWindowRange(999999, 500, 20, 100, 10);
  assert.equal(r.end, 100);
  assert.ok(r.start > 0 && r.start < 100);
});

test("codeWindowRange：overscan 0 → 只画可视行", () => {
  assert.deepEqual(codeWindowRange(1000, 500, 20, 100, 0), { start: 49, end: 75 });
});

test("codeWindowRange：单行文档", () => {
  assert.deepEqual(codeWindowRange(0, 500, 20, 1, 10), { start: 0, end: 1 });
});

test("codeGutterLineHTML：单行 span 带 data-code-line", () => {
  assert.equal(codeGutterLineHTML(3), '<span class="code-gutter-line" data-code-line="3">3</span>');
});

test("codeFoldGutterLines：与 codeFoldGutterHTML 拼接一致（含占位/箭头行）", () => {
  const lines = [
    { no: 1 },
    { no: 2, foldStart: 1, fold: "0", folded: false },
    { no: 3, placeholder: true, fold: "0", count: 5 },
    { no: 4 },
  ];
  assert.deepEqual(codeFoldGutterLines(lines).join(""), codeFoldGutterHTML(lines));
  assert.equal(codeFoldGutterLines(lines).length, 4);
  assert.match(codeFoldGutterLines(lines)[2], /code-gutter-ph/);
  assert.match(codeFoldGutterLines(lines)[1], /data-fold="0"/);
});
