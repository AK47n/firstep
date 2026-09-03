// fx/edit-patch.js 纯函数单测（工单 code-editor-opt/01）：
// editChangeSpan 变更段判定（与 textEditIsStructural 口径一致）+ marksPatch
// 标记清单行级增量修补（插入/删除/跨段/多行不变/与全量重算一致性）。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  editChangeSpan,
  marksPatch,
  marksPartition,
} from "../../src/contest_generator/static/js/fx/edit-patch.js";
import { codeIndentGuideMarks } from "../../src/contest_generator/static/js/fx/code-marks.js";
import { bracketDepthMarks } from "../../src/contest_generator/static/js/fx/code-brackets.js";

// ---- editChangeSpan ----

test("editChangeSpan：尾部纯字符插入 = 非结构，p/段长/行号正确", () => {
  const s = editChangeSpan("int a;\nint b;", "int a;\nint b;x");
  assert.equal(s.identical, false);
  assert.equal(s.structural, false);
  assert.equal(s.p, "int a;\nint b;".length);
  assert.equal(s.oldSegLen, 0);
  assert.equal(s.newSegLen, 1);
  assert.equal(s.line, 2);
});

test("editChangeSpan：行中插入 = 非结构，变更行 = p 所在行", () => {
  const s = editChangeSpan("int a;\nint bb;\nint c;", "int a;\nint bxbb;\nint c;");
  assert.equal(s.structural, false);
  assert.equal(s.p, "int a;\nint b".length);
  assert.equal(s.oldSegLen, 0);   // 旧 'b' 归入公共后缀
  assert.equal(s.newSegLen, 2);   // 新段 "xb"
  assert.equal(s.line, 2);
});

test("editChangeSpan：删除 = 非结构，段长为负向平移信息", () => {
  const s = editChangeSpan("int a;\nint bb;\nint c;", "int a;\nint b;\nint c;");
  assert.equal(s.structural, false);
  assert.equal(s.oldSegLen, 1);
  assert.equal(s.newSegLen, 0);
  assert.equal(s.line, 2);
});

test("editChangeSpan：无变化 = identical（调用方另有短路）", () => {
  const s = editChangeSpan("abc", "abc");
  assert.equal(s.identical, true);
  assert.equal(s.structural, true);
});

test("editChangeSpan：结构变更判定同 textEditIsStructural 口径", () => {
  assert.equal(editChangeSpan("ab", "a\nb").structural, true);   // 换行
  assert.equal(editChangeSpan("ab", "a{b").structural, true);    // 括号
  assert.equal(editChangeSpan("ab", 'a"b').structural, true);    // 引号
  assert.equal(editChangeSpan("ab", "a#b").structural, true);    // 井号
  assert.equal(editChangeSpan("ab", "a\tb").structural, true);   // tab
  assert.equal(editChangeSpan("    ab", "   ab").structural, true);   // 行首空白变化
  assert.equal(editChangeSpan("  ab", "   ab").structural, true);     // 插入在行首空白区 = 行首空白变化
  assert.equal(editChangeSpan("ab", "axb").structural, false);        // 纯字符（代码中）
  assert.equal(editChangeSpan("a b", "a xb").structural, false);      // 代码中空格后插入
  // 删除侧（评审整改：只看新段会把删除误判非结构——旧段也必须扫结构字符）
  assert.equal(editChangeSpan("ab(cd", "abcd").structural, true);     // 删括号
  assert.equal(editChangeSpan("a\nb", "ab").structural, true);        // 删换行
  assert.equal(editChangeSpan('a"b', "ab").structural, true);         // 删引号
  assert.equal(editChangeSpan("a#b", "ab").structural, true);         // 删井号
  assert.equal(editChangeSpan("a\tb", "ab").structural, true);        // 删 tab
  assert.equal(editChangeSpan("abx", "ab").structural, false);        // 删普通字符 = 非结构
});

test("editChangeSpan：空文/首行编辑 = 行 1", () => {
  assert.equal(editChangeSpan("", "x").line, 1);
  assert.equal(editChangeSpan("x", "").line, 1);
});

// ---- marksPatch：几何规则 ----

test("marksPatch：变更行外的标记逐字节不动（前行/后行）", () => {
  const oldMarks = [
    { line: 1, start: 3, end: 4, kind: "guide" },
    { line: 3, start: 7, end: 8, kind: "guide" },
    { line: 3, start: 11, end: 12, kind: "bracket-depth-0" },
  ];
  // 变更发生在第 2 行（插入 x），第 1/3 行标记必须逐字节不动
  const s = editChangeSpan("a b\ncde\nfg h ijk", "a b\ncxde\nfg h ijk");
  assert.equal(s.structural, false);
  assert.equal(s.line, 2);
  const out = marksPatch(oldMarks, "a b\ncde\nfg h ijk", "a b\ncxde\nfg h ijk", s);
  assert.deepEqual(out, oldMarks);
});

test("marksPatch：变更行内插入点之前的标记不动、之后的整体平移", () => {
  const oldMarks = [
    { line: 2, start: 3, end: 4, kind: "guide" },     // 在插入点前
    { line: 2, start: 7, end: 8, kind: "bracket-depth-0" }, // 在插入点后
  ];
  const oldText = "x\n    ab (cd";
  const newText = "x\n    abx (cd";
  const s = editChangeSpan(oldText, newText);
  assert.equal(s.structural, false);
  assert.equal(s.line, 2);
  const out = marksPatch(oldMarks, oldText, newText, s);
  assert.deepEqual(out, [
    { line: 2, start: 3, end: 4, kind: "guide" },
    { line: 2, start: 8, end: 9, kind: "bracket-depth-0" },
  ]);
});

test("marksPatch：删除使插入点后的标记负向平移、跨段标记只动尾端", () => {
  const oldMarks = [
    { line: 2, start: 3, end: 4, kind: "guide" },     // 删除段前
    { line: 2, start: 0, end: 12, kind: "line" },     // 跨段（防御性：非结构段不产生）
    { line: 2, start: 9, end: 10, kind: "bracket-depth-0" }, // 删除段前（col 9 < 11）
    { line: 2, start: 12, end: 13, kind: "bracket-depth-0" }, // 删除段后（col 12 ≥ 12）
  ];
  const oldText = "x\n    ab (cd ef";
  const newText = "x\n    ab (cd f";
  const s = editChangeSpan(oldText, newText);
  assert.equal(s.structural, false);
  const out = marksPatch(oldMarks, oldText, newText, s);
  assert.deepEqual(out, [
    { line: 2, start: 3, end: 4, kind: "guide" },
    { line: 2, start: 0, end: 11, kind: "line" },
    { line: 2, start: 9, end: 10, kind: "bracket-depth-0" },
    { line: 2, start: 11, end: 12, kind: "bracket-depth-0" },
  ]);
});

// ---- marksPatch 与全量重算一致性（重要验收）----

const cases = [
  ["行中插入", "int aa;\nint bb;\nint cc;", "int aa;\nint bxb;\nint cc;", 0, 4],
  ["行尾追加", "int aa;\nint bb;\nint cc;", "int aa;\nint bb;\nint cc;x", 0, 4],
  ["行首插入（非行首空白段）", "int aa;\nint bb;", "xint aa;\nint bb;", 0, 4],
  ["删除", "int aa;\nint bb;\nint cc;", "int aa;\nint b;\nint cc;", 0, 4],
  ["深嵌套行插入", "f() {\n    { (x); }\n}", "f() {\n    { (xy); }\n}", 0, 4],
  ["字符串行插入", 'char s[] = "{ 假括号";\nreturn;', 'char s[] = "{ 假括号";\nreturn x;', 0, 4],
];
for (const [name, oldText, newText] of cases) {
  test("marksPatch 与全量重算一致：" + name, () => {
    const allMarks = (t) => [...codeIndentGuideMarks(t), ...bracketDepthMarks(t)];
    const s = editChangeSpan(oldText, newText);
    assert.equal(s.structural, false, "用例应是非结构编辑");
    const patched = marksPatch(allMarks(oldText), oldText, newText, s);
    assert.deepEqual(patched, allMarks(newText));
  });
}

test("marksPatch：空标记清单原样返回", () => {
  const s = editChangeSpan("a", "ab");
  assert.deepEqual(marksPatch([], "a", "ab", s), []);
});

test("marksPatch：结构变更（含换行）不适用——标记按行号映射会失准，由调用方走全量", () => {
  const s = editChangeSpan("a\nb", "a\nxb");
  assert.equal(s.structural, false);  // 非结构（x 纯字符）
  // 插入换行才是结构变更
  const s2 = editChangeSpan("ab", "a\nb");
  assert.equal(s2.structural, true);
});

// ---- marksPartition：kind 命名域分区（评价整改：ui 不硬过滤 kind）----

test("marksPartition：guide / bracket-depth-* / others 分区且 all 同引用", () => {
  const marks = [
    { line: 1, start: 3, end: 4, kind: "guide" },
    { line: 1, start: 7, end: 8, kind: "bracket-depth-3" },
    { line: 2, start: 0, end: 2, kind: "hit" },
  ];
  const parts = marksPartition(marks);
  assert.equal(parts.all, marks);
  assert.deepEqual(parts.guides, [marks[0]]);
  assert.deepEqual(parts.rainbow, [marks[1]]);
  assert.deepEqual(parts.others, [marks[2]]);
});

test("marksPartition：空清单/空 kind 防御", () => {
  assert.deepEqual(marksPartition([]), { all: [], guides: [], rainbow: [], others: [] });
  assert.deepEqual(marksPartition(null).guides, []);
  const parts = marksPartition([{ line: 1, start: 0, end: 1, kind: "" }]);
  assert.deepEqual(parts.others.length, 1);
  assert.equal(parts.rainbow.length, 0);
});

test("marksPartition 与 marksPatch 组合：修补后分区 = 全量重算分区", () => {
  const all = (t) => [...codeIndentGuideMarks(t), ...bracketDepthMarks(t)];
  const oldText = "int aa;\nint bb;\nint cc;";
  const newText = "int aa;\nint bxb;\nint cc;";
  const s = editChangeSpan(oldText, newText);
  assert.equal(s.structural, false);
  const patched = marksPatch(all(oldText), oldText, newText, s);
  const p = marksPartition(patched);
  const fresh = marksPartition(all(newText));
  assert.deepEqual(p.guides, fresh.guides);
  assert.deepEqual(p.rainbow, fresh.rainbow);
});
