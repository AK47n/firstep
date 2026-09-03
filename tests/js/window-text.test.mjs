// fx/window-text.js 纯函数单测（工单 editor-textarea-viewport/01）：
// 窗口文本构建 / 窗口编辑→视图(模型)绝对段映射 / 折叠态模型回写 / 一致性校验。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  windowTextBuild,
  windowEditToView,
  windowEditToModel,
  windowTextMatches,
  windowTextMatchesModel,
  windowPosFromView,
  windowPosToView,
} from "../../src/contest_generator/static/js/fx/window-text.js";
import { editChangeSpan } from "../../src/contest_generator/static/js/fx/edit-patch.js";
import { buildLineStarts } from "../../src/contest_generator/static/js/fx/codeeditor.js";
import {
  codeFoldRanges,
  codeFoldVisible,
  codeFoldMapEdit,
} from "../../src/contest_generator/static/js/fx/code-fold.js";

const lineStartsOf = (lines) => buildLineStarts(lines);   // 单源（生产函数）

test("windowTextBuild：窗口文本 = 视图行切片 join，行起点表正确", () => {
  const lines = ["int a;", "int b;", "int c;", "int d;"];
  const w = windowTextBuild(lines, 1, 3, lineStartsOf(lines));
  assert.equal(w.text, "int b;\nint c;");
  assert.deepEqual(w.winLineStarts, [0, 7]);
  assert.equal(w.absStart, "int a;\n".length);
  assert.equal(w.start, 1);
  assert.equal(w.end, 3);
});

test("windowTextBuild：边界（空窗口 / 单行 / 全量 / 末行无尾随换行 / 钳制）", () => {
  assert.deepEqual(windowTextBuild([], 0, 0).text, "");
  assert.deepEqual(windowTextBuild(["x"], 0, 1).text, "x");
  const lines = ["a", "b"];
  assert.deepEqual(windowTextBuild(lines, 0, 2), {
    start: 0, end: 2, text: "a\nb", winLineStarts: [0, 2], absStart: 0,
  });
  assert.deepEqual(windowTextBuild(lines, 2, 2).text, "");
  // start > len 钳制到 len（空窗口，不越界取行）
  assert.equal(windowTextBuild(lines, 5, 9).start, 2);
  assert.equal(windowTextBuild(lines, 5, 9).end, 2);
});

test("windowEditToView：窗口内首行/中行/末行插入 → 视图绝对段正确", () => {
  const lines = ["root", "abc def", "z", "last"];
  const abs = lineStartsOf(lines);
  const cases = [
    { start: 0, oldText: "root\nabc def\nz", newText: "xroot\nabc def\nz", p: 0 },
    { start: 0, oldText: "root\nabc def\nz", newText: "root\nabc xdef\nz", p: "root\nabc ".length },
    { start: 1, oldText: "abc def\nz", newText: "abc def\nzz", p: "abc def\n".length },
  ];
  for (const c of cases) {
    const span = editChangeSpan(c.oldText, c.newText);
    const w = windowTextBuild(lines, c.start, c.start + c.oldText.split("\n").length, abs);
    const m = windowEditToView(span, w, abs);
    const direct = lines.join("\n");
    const expect = direct.slice(0, abs[c.start] + span.p)
      + c.newText.slice(span.p, span.p + span.newSegLen)
      + direct.slice(abs[c.start] + span.p + span.oldSegLen);
    assert.equal(m.p, abs[c.start] + span.p);
    assert.equal(m.oldSegLen, span.oldSegLen);
    assert.equal(m.newSegLen, span.newSegLen);
    const actual = direct.slice(0, m.p) + c.newText.slice(span.p, span.p + span.newSegLen)
      + direct.slice(m.p + m.oldSegLen);
    assert.equal(actual, expect);
  }
});

test("windowEditToView：跨行编辑段（粘贴多行）绝对映射正确", () => {
  const lines = ["aaa", "bbb", "ccc", "ddd"];
  const abs = lineStartsOf(lines);
  const start = 1;
  const oldText = "bbb\nccc";
  const newText = "B1\nB2\nccc";
  const span = editChangeSpan(oldText, newText);
  const w = windowTextBuild(lines, start, start + oldText.split("\n").length, abs);
  const m = windowEditToView(span, w, abs);
  const direct = lines.join("\n");
  const expect = direct.slice(0, abs[start] + span.p)
    + newText.slice(span.p, span.p + span.newSegLen)
    + direct.slice(abs[start] + span.p + span.oldSegLen);
  const actual = direct.slice(0, m.p) + newText.slice(span.p, span.p + span.newSegLen)
    + direct.slice(m.p + m.oldSegLen);
  assert.equal(actual, expect);
  assert.equal(m.p, abs[start] + span.p);
});

test("windowEditToView：空窗口插入映射到窗口起点（评审整改：此前恒 p=0 写进文件头）", () => {
  const lines = ["a", "b", "c"];
  const abs = lineStartsOf(lines);
  const w = windowTextBuild(lines, 2, 2, abs);      // 空窗口（文档末）
  assert.equal(w.text, "");
  const span = editChangeSpan("", "X");
  const m = windowEditToView(span, w, abs);
  assert.equal(m.p, abs[2]);                         // = 4（文档末）
  assert.equal(m.newSegLen, 1);
});

test("windowEditToView：窗口与行起点表不同步（start 越界）→ null 不静默归零", () => {
  const lines = ["a", "b", "c"];
  const abs = lineStartsOf(lines);
  const w = windowTextBuild(lines, 9, 9, abs);       // start 钳到末（3）→ absStart 有值
  assert.equal(w.start, 3);
  // 手工构造「start 越界且行起点表缺该行」→ 失配
  const wBad = windowTextBuild(lines, 0, 1, []);
  assert.equal(wBad.absStart, 0);
  const m = windowEditToView(editChangeSpan("a", "ax"), wBad, []);
  assert.equal(m, null);
});

test("windowEditToModel：非折叠窗口编辑 → 模型 = 直接改模型（含跨行粘贴）", () => {
  const model = "aaa\nbbb\nccc";
  const lines = model.split("\n");
  const abs = lineStartsOf(lines);
  const cases = [
    { start: 0, end: 3, oldWin: "aaa\nbbb\nccc", newWin: "aaa\nbbX\nccc" },
    { start: 1, end: 3, oldWin: "bbb\nccc", newWin: "BB\nCC\nccc" },   // 跨行粘贴
  ];
  for (const c of cases) {
    const w = windowTextBuild(lines, c.start, c.end, abs);
    const r = windowEditToModel(model, null, model, w, abs, c.newWin);
    const span = editChangeSpan(c.oldWin, c.newWin);
    const v = windowEditToView(span, w, abs);
    const mid = c.newWin.slice(span.p, span.p + span.newSegLen);
    const expect = model.slice(0, v.p) + mid + model.slice(v.p + v.oldSegLen);
    assert.equal(r.model, expect);
    assert.deepEqual(r.expand, []);
  }
});

test("windowEditToModel：折叠态与 codeFoldMapEdit 语义一致（普通行 + 触碰占位展开）", () => {
  const model = "f() {\n    x;\n    y;\n}\nz();";
  const folds = codeFoldRanges(model, "c");
  // 折叠 f() 区（第 1-4 行）
  const foldedSet = new Set([0]);
  const vm = codeFoldVisible(model, folds, foldedSet);
  assert.ok(vm.segs.some((s) => s.placeholder));
  const viewLines = vm.text.split("\n");
  const abs = lineStartsOf(viewLines);
  const vp = vm.segs.find((s) => s.placeholder);
  assert.ok(vp);

  // ① 普通可见行编辑（视图第 3 行 "z();" 追加）：窗口 [2,3)
  const w1 = windowTextBuild(viewLines, 2, 3, abs);
  const r1 = windowEditToModel(model, vm.segs, vm.text, w1, abs, "z();x");
  const span1 = editChangeSpan("z();", "z();x");
  const v1 = windowEditToView(span1, w1, abs);
  const mid1 = "z();x".slice(span1.p, span1.p + span1.newSegLen);   // 增量段 = "x"
  const newView1 = vm.text.slice(0, v1.p) + mid1 + vm.text.slice(v1.p + v1.oldSegLen);
  const expect1 = codeFoldMapEdit(model, vm.segs, vm.text, newView1);
  assert.equal(r1.model, expect1.model);
  assert.deepEqual(r1.expand, expect1.expand);
  assert.ok(r1.model.includes("z();x"));

  // ② 触碰占位行（窗口 = 占位行所在行）：输入新内容替换占位 → 展开 + 整块覆盖语义
  const phLine = viewLines.find((l) => l.includes("…"));
  const li = viewLines.indexOf(phLine);
  const w2 = windowTextBuild(viewLines, li, li + 1, abs);
  const newWin = "int total;";
  const r2 = windowEditToModel(model, vm.segs, vm.text, w2, abs, newWin);
  assert.ok(r2.expand.length > 0, "触碰占位应返回展开索引");
  const span2 = editChangeSpan(phLine, newWin);
  const v2 = windowEditToView(span2, w2, abs);
  const newView2 = vm.text.slice(0, v2.p) + newWin + vm.text.slice(v2.p + v2.oldSegLen);
  const expect2 = codeFoldMapEdit(model, vm.segs, vm.text, newView2);
  assert.equal(r2.model, expect2.model);
  assert.deepEqual(r2.expand, expect2.expand);
  assert.equal(r2.caret, expect2.caret);
});

test("windowTextMatches：一致 true / 错位或行区间不符 false", () => {
  const lines = ["a", "b", "c"];
  assert.equal(windowTextMatches(lines, 0, 3, "a\nb\nc"), true);
  assert.equal(windowTextMatches(lines, 1, 3, "b\nc"), true);
  assert.equal(windowTextMatches(lines, 0, 3, "a\nb"), false);
  assert.equal(windowTextMatches(lines, 0, 2, "a\nb\nc"), false);
  assert.equal(windowTextMatches(lines, 0, 3, "a\nx\nc"), false);
});

test("windowTextMatchesModel：非折叠直接切模型；折叠态经 viewModel 推导视图", () => {
  const model = "a\nb\nc";
  assert.equal(windowTextMatchesModel(model, null, 0, 3, "a\nb\nc"), true);
  assert.equal(windowTextMatchesModel(model, null, 1, 3, "b\nc"), true);
  assert.equal(windowTextMatchesModel(model, null, 0, 3, "a\nx\nc"), false);
  // 折叠态
  const fm = "f() {\n  x;\n}\ng();";
  const vm = codeFoldVisible(fm, codeFoldRanges(fm, "c"), new Set([0]));
  assert.equal(windowTextMatchesModel(fm, vm, 0, 2, vm.text.split("\n").slice(0, 2).join("\n")), true);
  assert.equal(windowTextMatchesModel(fm, vm, 0, 2, "f() {\n  ???"), false);
});

test("windowEditToView：随机微小编辑与全量对拍一致", () => {
  const lines = [];
  for (let i = 0; i < 20; i++) lines.push("line" + i + " abc def");
  const abs = lineStartsOf(lines);
  const seeds = [
    [5, "abc", "abXc"],
    [9, "def", ""],
    [0, "line0", "line00"],
    [19, "def", "deff"],
  ];
  for (const [li, oldSub, newSub] of seeds) {
    const viewText = lines.join("\n");
    const lineStart = abs[li];
    const nl = viewText.indexOf("\n", lineStart);
    const lineEnd = nl === -1 ? viewText.length : nl;
    const lineText = viewText.slice(lineStart, lineEnd);
    const at = lineText.indexOf(oldSub);
    const winNew = lineText.slice(0, at) + newSub + lineText.slice(at + oldSub.length);
    const span = editChangeSpan(lineText, winNew);
    const w = windowTextBuild(lines, li, li + 1, abs);
    const m = windowEditToView(span, w, abs);
    const direct = viewText.slice(0, lineStart + at) + newSub + viewText.slice(lineStart + at + oldSub.length);
    const actual = viewText.slice(0, m.p) + winNew.slice(span.p, span.p + span.newSegLen) + viewText.slice(m.p + m.oldSegLen);
    assert.equal(actual, direct, "seed " + li);
  }
});

test("windowPosFromView：窗口内视图偏移 → 窗口偏移（首/中/末）；越界 → null", () => {
  const lines = ["aaa", "bbb", "ccc", "ddd"];
  const abs = lineStartsOf(lines);
  const w = windowTextBuild(lines, 1, 3, abs);   // 窗口 "bbb\nccc"，absStart = 4
  assert.equal(w.text, "bbb\nccc");
  assert.equal(windowPosFromView(w, abs[1]), 0);           // 窗口首行行首
  assert.equal(windowPosFromView(w, abs[1] + 1), 1);       // 行中
  assert.equal(windowPosFromView(w, abs[2] + 3), w.text.length);  // 窗口末（ccc 行尾）
  assert.equal(windowPosFromView(w, abs[1] - 1), null);    // 窗口上方（aaa 内）
  assert.equal(windowPosFromView(w, abs[3]), null);        // 窗口下方（ddd 行首）
  assert.equal(windowPosFromView(w, 0), null);             // 文档首（窗口起点前）
});

test("windowPosToView：窗口偏移 → 视图绝对偏移；非法 winInfo → null", () => {
  const lines = ["aaa", "bbb", "ccc", "ddd"];
  const abs = lineStartsOf(lines);
  const w = windowTextBuild(lines, 1, 3, abs);
  assert.equal(windowPosToView(w, 0), abs[1]);
  assert.equal(windowPosToView(w, 4), abs[1] + 4);        // "bbb\nccc" 中段
  assert.equal(windowPosToView(w, w.text.length), abs[2] + 3);
  assert.equal(windowPosToView(null, 0), null);           // 防御
  assert.equal(windowPosToView({}, 0), null);
});
