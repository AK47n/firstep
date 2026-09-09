// 滚动窗口化纯件单测（工单 code-page-vscode-overhaul/08）：
// codeWindowRange（滚动窗口范围）、codeWindowSpacerHTML / codeWindowSpacers
// （上下留白——在途盘点补口，原只在 ui 层）与 gutter 分段（codeGutterLineHTML /
// codeFoldGutterLines）。期望值全部手工推算。
import test from "node:test";
import assert from "node:assert/strict";
import {
  codeWindowRange,
  codeWindowSpacerHTML,
  codeWindowSpacers,
} from "../../src/contest_generator/static/js/fx/codeeditor.js";
import { codeGutterLineHTML } from "../../src/contest_generator/static/js/fx/codeview.js";
import { codeFoldGutterLines, codeFoldGutterHTML, codeFoldVisible } from "../../src/contest_generator/static/js/fx/code-fold.js";

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

test("codeWindowSpacerHTML：>0 出占位块，0/负/非数 → 空串，四舍五入", () => {
  assert.equal(codeWindowSpacerHTML(240), '<div class="code-window-spacer" style="height:240px"></div>');
  assert.equal(codeWindowSpacerHTML(239.6), '<div class="code-window-spacer" style="height:240px"></div>');
  assert.equal(codeWindowSpacerHTML(0), "");
  assert.equal(codeWindowSpacerHTML(-5), "");
  assert.equal(codeWindowSpacerHTML(undefined), "");
  assert.equal(codeWindowSpacerHTML("abc"), "");
});

test("codeWindowSpacers：顶部窗口 → 上 0 下 (n-end)*行高", () => {
  assert.deepEqual(codeWindowSpacers(0, 35, 100, 20), { top: 0, bottom: 1300 });
});

test("codeWindowSpacers：中部窗口 → 上下按行高换算", () => {
  assert.deepEqual(codeWindowSpacers(39, 85, 100, 20), { top: 780, bottom: 300 });
});

test("codeWindowSpacers：底部窗口 → 下 0；越界钳制 + 行高下限 1", () => {
  assert.deepEqual(codeWindowSpacers(80, 100, 100, 20), { top: 1600, bottom: 0 });
  assert.deepEqual(codeWindowSpacers(-3, 999, 10, 0), { top: 0, bottom: 0 });
  assert.deepEqual(codeWindowSpacers(2, 5, 10, 0), { top: 2, bottom: 5 });
});

test("折叠 → 窗口行映射：视图行数 = 折叠后可见行，窗口范围按视图行算", () => {
  // 10 行内容，第 2-6 行折叠 → 视图 7 行（1、2、占位行、7、8、9、10）
  const content = Array.from({ length: 10 }, (_, i) => "line" + (i + 1)).join("\n");
  const folds = [{ startLine: 2, endLine: 6 }];
  const vm = codeFoldVisible(content, folds, new Set([0]));
  assert.equal(vm.lines.length, 7);
  assert.equal(vm.lines[2].placeholder, true);
  // 窗口按视图行算：视口 40px / 行高 20px / overscan 0 → 前两视图行
  const r = codeWindowRange(0, 40, 20, vm.lines.length, 0);
  assert.deepEqual(r, { start: 0, end: 2 });
  // 上下留白按视图行算（视图 7 行、窗口 [0,2)）
  assert.deepEqual(codeWindowSpacers(r.start, r.end, vm.lines.length, 20),
    { top: 0, bottom: 100 });
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
