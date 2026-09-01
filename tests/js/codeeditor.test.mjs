// fx/codeeditor.js 纯函数单测（工单 code-viewer-editor/02）：标签条 HTML /
// 编辑器三明治 HTML / 光标行号 / Tab 缩进 / Enter 自动缩进。直接 import，
// 子串断言防脆。运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  codeTabBadge,
  codeTabStripHTML,
  codeEditorHTML,
  conflictHTML,
  editorLineRange,
  isTabSavable,
  dirtySavableTabs,
  caretLineOf,
  indentOnEnter,
  indentLines,
  replaceAllText,
  EDITOR_TABS_MAX,
} from "../../src/contest_generator/static/js/fx/codeeditor.js";

test("codeTabBadge：语言徽标映射（与只读查看器同观感）", () => {
  assert.equal(codeTabBadge("c"), "C");
  assert.equal(codeTabBadge("xml"), "XML");
  assert.equal(codeTabBadge("md"), "MD");
  assert.equal(codeTabBadge("plain"), "TXT");
  assert.equal(codeTabBadge("json"), "TXT");  // 未知语言兜底 TXT
});

test("codeTabStripHTML：活动 tab、脏点、只读标记、关闭钮、转义", () => {
  const html = codeTabStripHTML(
    [
      { path: "main.c", lang: "c", dirty: true, readonly: false },
      { path: "src/app.h", lang: "c", dirty: false, readonly: true },
      { path: "a<b.c", lang: "c", dirty: false, readonly: false },
    ],
    "src/app.h",
  );
  assert.match(html, /class="code-tab on ro"/);    // 活动 + 只读（本用例活动 tab 恰为只读）
  assert.match(html, /data-tab-path="src\/app\.h"/);
  assert.match(html, /class="code-tab-dirty"/);    // 脏点
  assert.match(html, /class="code-tab-ro">只读<\/span>/);  // 只读可见小标
  assert.match(html, /data-tab-close/);            // 关闭钮
  assert.match(html, /data-tab-path="a&lt;b\.c"/); // 转义
  assert.ok(!html.includes("a<b.c"));
});

test("codeTabStripHTML：「磁盘已变更」徽章（code-ide-flow/02）——diskChanged 渲染、无标志不渲染", () => {
  const html = codeTabStripHTML(
    [{ path: "main.c", lang: "c", dirty: true, readonly: false, diskChanged: true }],
    "main.c",
  );
  assert.match(html, /class="code-tab-disk"/);
  assert.match(html, /data-tab-disk/);              // 事件层入口（弹三选）
  assert.match(html, /aria-label="磁盘已变更/);
  const plain = codeTabStripHTML(
    [{ path: "a.c", lang: "c", dirty: false, readonly: false }],
    "a.c",
  );
  assert.ok(!plain.includes("code-tab-disk"));     // 无标志前进化零
});

test("codeTabStripHTML：活动 tab 非只读时 class 组合正确", () => {
  const html = codeTabStripHTML(
    [{ path: "main.c", lang: "c", dirty: false, readonly: false }],
    "main.c",
  );
  assert.match(html, /class="code-tab on"/);
  assert.ok(!html.includes("on ro"));
});

test("codeTabStripHTML：无 tab 空态", () => {
  const html = codeTabStripHTML([], "");
  assert.equal(html, "");
});

test("codeEditorHTML：textarea + 高亮层 + 逐行 span（行号跳转语义保留）", () => {
  const html = codeEditorHTML("int main(void) {\n  return 0;\n}\n", "c");
  assert.match(html, /<textarea class="code-ta"/);
  assert.match(html, /<pre class="code-hl"/);
  assert.match(html, /class="code-hl-line" data-code-line="1"/);
  assert.match(html, /class="code-hl-line" data-code-line="3"/);
  assert.match(html, /<span class="tok-kw">int<\/span>/);  // 高亮存在
});

test("codeEditorHTML：内容转义（hl 与 textarea 均 &lt; 化）", () => {
  const html = codeEditorHTML("<script>alert(1)</script>\n", "plain");
  assert.match(html, /&lt;script&gt;/);
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("</textarea>alert"));  // 防 textarea 提前闭合
});

test("codeEditorHTML：readonly 标志（非 UTF-8 / 只读文件）", () => {
  const html = codeEditorHTML("x\n", "c", { readonly: true });
  assert.match(html, /<textarea class="code-ta"[^>]* readonly/);
  assert.match(html, /class="code-edit ro"/);
});

test("caretLineOf：光标行号（1 基，含中英混排）", () => {
  const v = "ab\ncd中文\nef\n";
  assert.equal(caretLineOf(v, 0), 1);      // 首字符
  assert.equal(caretLineOf(v, 2), 1);      // \n 前
  assert.equal(caretLineOf(v, 3), 2);      // \n 后首字符
  assert.equal(caretLineOf(v, 7), 2);      // 第二行行尾 \n
  assert.equal(caretLineOf(v, 8), 3);      // 第三行首字符
  assert.equal(caretLineOf(v, 999), 4);    // 越界钳末：尾 \n 后有第 4 空行
  assert.equal(caretLineOf("", 0), 1);     // 空串
});

test("indentOnEnter：单行光标 = 换行 + 拷贝前导空白", () => {
  const r = indentOnEnter("  int x;\n", 8, 8);   // 光标在行尾（; 后）
  assert.equal(r.value, "  int x;\n  \n");
  assert.equal(r.start, 11);
  assert.equal(r.end, 11);
});

test("indentOnEnter：无前导空白 = 普通换行", () => {
  const r = indentOnEnter("abc", 3, 3);
  assert.equal(r.value, "abc\n");
  assert.equal(r.start, 4);
  assert.equal(r.end, 4);
});

test("indentOnEnter：多行选区 = 替换为换行 + 起始行前导空白", () => {
  const r = indentOnEnter("  aaa\n  bbb\n", 3, 8);  // 选中 aaa 行尾前到 bbb 行首
  assert.equal(r.value, "  a\n  bbb\n");
  // 选区被换行替换，光标落新行
  assert.equal(r.value.slice(r.start, r.end), "");
  assert.equal(r.start, 6);
});

test("editorLineRange：委托 fx/code.js 单源——行选段 + 越界 null", () => {
  const txt = "int a;\nint b;\n";
  assert.deepEqual(editorLineRange(txt, 1), { start: 0, end: 6 });
  assert.deepEqual(editorLineRange(txt, 2), { start: 7, end: 13 });
  assert.deepEqual(editorLineRange(txt, 3), { start: 14, end: 14 });  // 尾 \n 空行（合法）
  assert.equal(editorLineRange(txt, 4), null);   // 越界
  assert.equal(editorLineRange(txt, 0), null);   // 非法行号
  assert.deepEqual(editorLineRange("", 1), { start: 0, end: 0 });  // 空串 = 单个空行
});

test("indentLines：单行 = 插入 4 空格", () => {
  const r = indentLines("int x;", 0, 0);
  assert.equal(r.value, "    int x;");
  assert.equal(r.start, 4);
  assert.equal(r.end, 4);
});

test("indentLines：单行选区 = 4 空格替换选区，光标落插入后", () => {
  const r = indentLines("xval", 0, 4);
  assert.equal(r.value, "    ");
  assert.equal(r.start, 4);
  assert.equal(r.end, 4);
});

test("indentLines：多行选区 = 每行前置 4 空格（触及行全缩进）", () => {
  const v = "int a;\nint b;\nint c;\n";
  const r = indentLines(v, 0, 15);  // 选中前三行（含第三行首字符）
  assert.equal(r.value, "    int a;\n    int b;\n    int c;\n");
  // 选区扩展为整段
  assert.equal(r.value.slice(r.start, r.end), "    int a;\n    int b;\n    int c;");
});

test("isTabSavable：保存判据单源（脏 + 非只读）", () => {
  const base = { content: "a", savedContent: "a", readonly: false };
  assert.equal(isTabSavable(null), false);
  assert.equal(isTabSavable({ ...base }), false);                       // 无差异
  assert.equal(isTabSavable({ ...base, content: "b" }), true);          // 脏
  assert.equal(isTabSavable({ ...base, content: "b", readonly: true }), false);  // 只读
});

test("dirtySavableTabs：保存全部的前置筛选（脏非只读；顺序保持）", () => {
  const mk = (path, dirty, ro) => ({
    path,
    content: dirty ? "b" : "a",
    savedContent: "a",
    readonly: ro,
  });
  assert.deepEqual(dirtySavableTabs([]), []);                            // 空清单
  assert.deepEqual(dirtySavableTabs([mk("a.c", false, false)]), []);     // 非脏
  assert.deepEqual(dirtySavableTabs([mk("a.c", true, true)]), []);       // 只读
  assert.deepEqual(
    dirtySavableTabs([mk("a.c", true, false), mk("b.c", false, false), mk("c.c", true, true)]),
    [mk("a.c", true, false)],
  );
});

test("conflictHTML：双列对比各前 10 行 + 转义 + 越界省略提示", () => {
  const disk = "#include <app.h>\n" + "x".repeat(20) + "\n";  // 3 行
  const edit = "<script>alert(1)</script>\n";
  const html = conflictHTML(disk, edit);
  assert.match(html, /class="code-conflict-cols"/);
  assert.match(html, /磁盘版（外部修改）/);
  assert.match(html, /我的编辑（未保存）/);
  assert.match(html, /&lt;script&gt;/);          // 转义
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("共 "));               // ≤10 行不显示省略提示
  // 超 10 行 → 截断提示
  const big = Array.from({ length: 12 }, (_, i) => "line" + i).join("\n");
  const html2 = conflictHTML(big, "");
  assert.match(html2, /仅展示前 10 行/);
  assert.match(html2, /line0/);
  assert.ok(!html2.includes("line10"));
});

test("EDITOR_TABS_MAX：上限常量存在且合理", () => {
  assert.equal(EDITOR_TABS_MAX, 10);
});

// replaceAllText：查找替换全部纯件（工单 code-editor-utilize/03）——空针不
// 改、无匹配 count 0、替换含特殊字符（$ 需防 replace 模式串语义）、空替换。
test("replaceAllText：空针/无匹配 → count 0 且原样返回", () => {
  assert.deepEqual(replaceAllText("abc", "", "x"), { count: 0, value: "abc" });
  assert.deepEqual(replaceAllText("abc", "z", "x"), { count: 0, value: "abc" });
  assert.deepEqual(replaceAllText(null, "a", "x"), { count: 0, value: "" });   // 防御
});

test("replaceAllText：单处/多处/空替换/特殊字符（split-join 语义无模式串）", () => {
  assert.deepEqual(replaceAllText("aXb", "X", "Y"), { count: 1, value: "aYb" });
  assert.deepEqual(replaceAllText("XaXbX", "X", "Y"), { count: 3, value: "YaYbY" });
  assert.deepEqual(replaceAllText("abc", "b", ""), { count: 1, value: "ac" });
  // $& / $1 等替换串必须按字面处理（split-join 天然规避 replace 模式串陷阱）
  assert.deepEqual(replaceAllText("a1a", "a", "$&"), { count: 2, value: "$&1$&" });
  assert.deepEqual(replaceAllText("a.b", ".", "-"), { count: 1, value: "a-b" });   // 正则元字符按字面
});
