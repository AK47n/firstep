// fx/code-fold.js 纯函数单测（工单 code-editor-vscode-polish/07 代码折叠）：
// 折叠区计算（.c/.h 花括号 + .md 标题）、可见行映射（占位行 + 模型行号）、
// 视图↔模型偏移映射、编辑回写映射（含占位行触碰 → 展开）。直接 import。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  codeFoldRanges,
  codeFoldVisible,
  codeFoldViewToModel,
  codeFoldMapEdit,
  codeFoldMerge,
  codeFoldModelGutterLines,
  codeFoldGutterLines,
  codeFoldPlaceholderText,
} from "../../src/contest_generator/static/js/fx/code-fold.js";

// ================= 折叠区计算 =================
test("codeFoldRanges：.c 花括号配对（跨行才折叠、同行 {} 不折叠）", () => {
  assert.deepEqual(codeFoldRanges("void f() {\n    int x;\n}\n", "c"),
    [{ startLine: 1, endLine: 3 }]);
  assert.deepEqual(codeFoldRanges("void f() { return 0; }\n", "c"), []);  // 同行闭合
});

test("codeFoldRanges：嵌套折叠按深度（内层先）", () => {
  const r = codeFoldRanges("{\n{\n}\n}\n", "c");
  assert.deepEqual(r, [
    { startLine: 2, endLine: 3 },
    { startLine: 1, endLine: 4 },
  ]);
});

test("codeFoldRanges：跳过字符串与注释内的假花括号", () => {
  const text = 'const char *s = "{";\n// }\nint x;\n}\n';
  assert.deepEqual(codeFoldRanges(text, "c"), []);   // 全是假括号/未配对
});

test("codeFoldRanges：.md 标题层级（隐藏到同层/更高层标题前；子标题被并入上层区）", () => {
  const md = "# A\nbody\n## B\nbody2\n";
  assert.deepEqual(codeFoldRanges(md, "md"), [
    { startLine: 1, endLine: 5 },    // A 区吞并子标题 B（B 更深，不截断 A）；尾部空行随文件尾
    { startLine: 3, endLine: 5 },    // B 区
  ]);
  assert.deepEqual(codeFoldRanges("# A\n# B", "md"), []);   // 连续标题无内容 → 不折叠
});

test("codeFoldRanges：语言门控——xml/plain 无折叠区（评审整改 07b）", () => {
  const text = "{\n  x\n}\n";
  assert.deepEqual(codeFoldRanges(text, "xml"), []);
  assert.deepEqual(codeFoldRanges(text, "plain"), []);
  assert.deepEqual(codeFoldRanges(text, "md"), []);     // 花括号文本在 md 走标题规则
});

// ================= 占位文本 =================
test("codeFoldPlaceholderText：行数文案", () => {
  assert.equal(codeFoldPlaceholderText(5), "… 5 行");
  assert.equal(codeFoldPlaceholderText(1), "… 1 行");
});

// ================= 可见行映射 =================
test("codeFoldVisible：占位行替代隐藏区 + 模型真实行号", () => {
  const content = "a\nb\nc\nd\n";
  const folds = [{ startLine: 1, endLine: 3 }];   // 隐藏 2..3
  const v = codeFoldVisible(content, folds, new Set([0]));
  assert.deepEqual(v.lines.map((l) => l.no), [1, 2, 4, 5]);   // 行号 1、占位（2 号位）、4、尾空行 5
  assert.equal(v.lines[1].placeholder, true);
  assert.equal(v.lines[1].count, 2);
  assert.equal(v.text, "a\n… 2 行\nd\n");
});

test("codeFoldVisible：无折叠 = 原样（含尾空行；segs 逐行映射）", () => {
  const v = codeFoldVisible("a\nb\n", [], new Set());
  assert.deepEqual(v.lines.map((l) => l.no), [1, 2, 3]);   // 尾 \n 空行保留（与编辑器行号一致）
  assert.equal(v.text, "a\nb\n");
});

// ================= 视图 ↔ 模型偏移 =================
test("codeFoldViewToModel：占位区前后映射", () => {
  const content = "aa\nbb\ncc\n";
  const v = codeFoldVisible(content, [{ startLine: 1, endLine: 3 }], new Set([0]));
  // 视图: "aa\n… 2 行\ncc\n"  占位从视图偏移 3 起
  assert.equal(codeFoldViewToModel(v.segs, 0), 0);         // 行首
  assert.equal(codeFoldViewToModel(v.segs, 2), 2);         // aa 内
  assert.equal(codeFoldViewToModel(v.segs, 3), 3);         // 占位起点 → 隐藏区起点
  assert.equal(codeFoldViewToModel(v.segs, v.text.length), content.length);
});

// ================= 编辑回写映射 =================
test("codeFoldMapEdit：普通行内编辑（视图偏移 → 模型偏移）", () => {
  const content = "aa\nbb\ncc\n";
  const v = codeFoldVisible(content, [{ startLine: 1, endLine: 3 }], new Set([0]));
  const r = codeFoldMapEdit(content, v.segs, "aa\n… 2 行\ncc\n", "aXa\n… 2 行\ncc\n");
  assert.equal(r.model, "aXa\nbb\ncc\n");
  assert.deepEqual(r.expand, []);
});

test("codeFoldMapEdit：编辑触碰占位行 → 展开 + 隐藏块替换（VSCode 近似）", () => {
  const content = "aa\nbb\ncc\n";
  const v = codeFoldVisible(content, [{ startLine: 1, endLine: 2 }], new Set([0]));
  const r = codeFoldMapEdit(content, v.segs, "aa\n… 1 行\ncc\n", "aa\nxx\ncc\n");
  assert.deepEqual(r.expand, [0]);
  assert.equal(r.model, "aa\nxx\ncc\n");   // 隐藏的 bb 被替换为 xx
});

test("codeFoldMapEdit：粘贴/删除跨占位 → 整块替换", () => {
  const content = "aa\nL2\nL3\ncc\n";
  const v = codeFoldVisible(content, [{ startLine: 1, endLine: 3 }], new Set([0]));
  const r = codeFoldMapEdit(content, v.segs, "aa\n… 2 行\ncc\n", "aa\nNEW\ncc\n");
  assert.deepEqual(r.expand, [0]);
  assert.equal(r.model, "aa\nNEW\ncc\n");    // 隐藏整块被替换
});

// ---- codeFoldMerge（工单 11 性能整改：O(n) 键集实现，语义 = 签名配对保留）----

test("codeFoldMerge：签名相同保留折叠态；漂移/未折叠不保留；O(n) 大输入正确", () => {
  const folds = [{ startLine: 1, endLine: 3 }, { startLine: 5, endLine: 7 }];
  assert.deepEqual([...codeFoldMerge(folds, new Set([0]), folds)], [0]);
  assert.deepEqual([...codeFoldMerge(folds, new Set(), folds)], []);
  // 漂移后：仅 5-7 保留
  const next = [{ startLine: 1, endLine: 4 }, { startLine: 5, endLine: 7 }];
  assert.deepEqual([...codeFoldMerge(folds, new Set([0, 1]), next)], [1]);
  // 大输入（3000 折叠无折叠态）——与旧实现的语义一致（空集）
  const many = Array.from({ length: 3000 }, (_, i) => ({ startLine: i * 2 + 1, endLine: i * 2 + 2 }));
  assert.equal(codeFoldMerge(many, new Set(), many).size, 0);
});

// ---- codeFoldModelGutterLines（工单 code-fold-arrow/01：未折叠态 gutter 箭头）----

test("codeFoldModelGutterLines：单折叠区 → 开行标 foldStart/folded:false，其余平铺", () => {
  const lines = ["void f() {", "    int x;", "}"];
  const rows = codeFoldModelGutterLines(lines, [{ startLine: 1, endLine: 3 }]);
  assert.equal(rows.length, 3);
  assert.deepEqual(rows[0],
    { no: 1, text: "void f() {", placeholder: false, fold: 0, foldStart: true, folded: false });
  assert.deepEqual(rows[1],
    { no: 2, text: "    int x;", placeholder: false, fold: -1, foldStart: false, folded: false });
  assert.deepEqual(rows[2],
    { no: 3, text: "}", placeholder: false, fold: -1, foldStart: false, folded: false });
});

test("codeFoldModelGutterLines：多折叠区 → 行号与 fold 索引逐一对应（乱序 folds 也对）", () => {
  const lines = Array.from({ length: 9 }, (_, i) => "L" + (i + 1));
  // folds 未按行号排序：索引仍须按 folds 数组下标（foldedSet 的键就是它）
  const folds = [{ startLine: 6, endLine: 8 }, { startLine: 1, endLine: 3 }];
  const rows = codeFoldModelGutterLines(lines, folds);
  const starts = rows.filter((r) => r.foldStart).map((r) => [r.no, r.fold]);
  assert.deepEqual(starts, [[1, 1], [6, 0]]);
  assert.equal(rows.filter((r) => !r.foldStart).length, 7);
  assert.deepEqual(rows.map((r) => r.no), [1, 2, 3, 4, 5, 6, 7, 8, 9]);
});

test("codeFoldModelGutterLines：嵌套折叠区 → 内外层开行各自标（索引不串）", () => {
  const lines = Array.from({ length: 6 }, (_, i) => "L" + (i + 1));
  const folds = [{ startLine: 1, endLine: 6 }, { startLine: 2, endLine: 4 }];
  const rows = codeFoldModelGutterLines(lines, folds);
  assert.deepEqual(rows.filter((r) => r.foldStart).map((r) => [r.no, r.fold]),
    [[1, 0], [2, 1]]);
});

test("codeFoldModelGutterLines：无折叠区 → 全平铺（fold:-1、foldStart:false）", () => {
  const rows = codeFoldModelGutterLines(["a", "b"], []);
  assert.deepEqual(rows.map((r) => [r.no, r.fold, r.foldStart, r.folded]),
    [[1, -1, false, false], [2, -1, false, false]]);
  assert.deepEqual(codeFoldModelGutterLines([], [{ startLine: 1, endLine: 2 }]), []);
  assert.deepEqual(codeFoldModelGutterLines(null, null), []);
});

test("codeFoldModelGutterLines → codeFoldGutterLines：未折叠态渲染 ▾ 箭头（data-fold 单源）", () => {
  const lines = ["void f() {", "    int x;", "}"];
  const html = codeFoldGutterLines(codeFoldModelGutterLines(lines, [{ startLine: 1, endLine: 3 }]));
  assert.equal(html.length, 3);
  assert.match(html[0], /class="code-fold-arrow open" data-fold="0" role="button" title="折叠">▾</);
  assert.match(html[0], /data-code-line="1"/);
  assert.doesNotMatch(html[1], /code-fold-arrow/);
  assert.doesNotMatch(html[2], /code-fold-arrow/);
  assert.match(html[1], />2<\/span>$/);
  assert.match(html[2], />3<\/span>$/);
});
