// fx/codeeditor.js 纯函数单测（工单 code-viewer-editor/02）：标签条 HTML /
// 编辑器三明治 HTML / 光标行号 / Tab 缩进 / Enter 自动缩进。直接 import，
// 子串断言防脆。运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  codeTabBadge,
  codeTabStripHTML,
  codeEditorHTML,
  codeStatusHTML,
  moveTab,
  conflictHTML,
  editorLineRange,
  isTabSavable,
  dirtySavableTabs,
  caretLineOf,
  caretColOf,
  caretLineFromStarts,
  buildLineStarts,
  patchLineStarts,
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

test("codeEditorHTML：opts.taValue 覆盖 textarea 内容（窗口化：不内嵌全文）", () => {
  const src = "line one\nline two\nline three";
  const html = codeEditorHTML(src, "c", { windowed: true, taValue: "line two" });
  // textarea 只装窗口文本（真实换行转义）；默认情形仍是全文
  assert.match(html, />line two<\/textarea>/);
  assert.ok(!html.includes(">line one\nline two\nline three</textarea>"));
  assert.ok(!html.includes("line three</textarea>"));
  const def = codeEditorHTML(src, "c", { windowed: true });
  assert.match(def, />line one\nline two\nline three<\/textarea>/);
});

test("codeEditorHTML：窗口化空壳仍输出 .code-hl / .code-marks 空 pre（行高测量链契约）", () => {
  // ui/winLineHeight 在首次打开时（.code-hl-line 尚未渲染）从空壳 pre 实测
  // computed line-height（与 .code-hl-line 同 --code-font-size 单源）；空壳
  // 若省略这两个 pre，行高只能回退容器字号 → 136% 缩放下行高 20px vs 28.29px、
  // .code-edit 变矮、标记层底部被裁切（用户现场：文件尾括号无彩虹标色）。
  const html = codeEditorHTML("a\n", "c", { windowed: true });
  assert.match(html, /<pre class="code-hl" aria-hidden="true"><\/pre>/);
  assert.match(html, /<pre class="code-marks" aria-hidden="true"><\/pre>/);
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

test("caretColOf：光标列号（1 基，与 caretLineOf 同族成对）", () => {
  const v = "ab\ncd中文\nef\n";
  assert.equal(caretColOf(v, 0), 1);       // 首字符
  assert.equal(caretColOf(v, 1), 2);       // 行中
  assert.equal(caretColOf(v, 2), 3);       // \n 上 = 行尾后（浏览器光标语义）
  assert.equal(caretColOf(v, 3), 1);       // 新行首
  assert.equal(caretColOf(v, 5), 3);       // 中文按码元计数
  assert.equal(caretColOf(v, 7), 5);       // 行尾 \n 上
  assert.equal(caretColOf(v, 999), 1);     // 越界钳末行（尾 \n 后 = 空行首）
  assert.equal(caretColOf("", 0), 1);      // 空串
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

test("indentOnEnter：花括号对居中展开（`{}` 中间回车 → 缩进一格直接输入）", () => {
  // 现场场景：`void f() {}` 光标在 `{` 与 `}` 中间 → 回车后
  //   行 1: void f() {
  //   行 2:     |（4 空格，直接输入）
  //   行 3: }
  const r = indentOnEnter("void f() {}", 10, 10);
  assert.equal(r.value, "void f() {\n    \n}");
  assert.equal(r.start, 15);
  assert.equal(r.end, 15);
  assert.equal(r.value.slice(r.start, r.start + 1), "\n");  // 光标在中间缩进行行尾
});

test("indentOnEnter：花括号展开保留原前导空白（闭括号与原行同级）", () => {
  // 缩进行内：`    if (x) {}` → 中间行 = 原 4 空格 + 4 空格（8 格），
  // 闭括号回落原 4 空格
  const r = indentOnEnter("    if (x) {}", 12, 12);
  assert.equal(r.value, "    if (x) {\n        \n    }");
  assert.equal(r.start, 21);
  assert.equal(r.end, 21);
});

test("indentOnEnter：非花括号对 / 有选区 / 非空选区不触发展开", () => {
  // 圆括号对：走普通换行（既不展开也不缩进额外一级）
  const r1 = indentOnEnter("f()", 2, 2);
  assert.equal(r1.value, "f(\n)");
  // 相同位置但有选区（选中 `}`）→ 普通换行替换选区语义
  const r2 = indentOnEnter("{}", 1, 2);
  assert.equal(r2.value, "{\n");
  // 光标不在 `{}` 中间（前有空格）
  const r3 = indentOnEnter("{ }", 2, 2);
  assert.equal(r3.value, "{ \n}");
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

// codeStatusHTML：状态栏信息区纯件（工单 code-editor-vscode-polish/01）——
// 完整信息 / 非 UTF-8 / 自定义缩进缩放 / 语言徽标 / 空态（无活动文件 → 空串）。
test("codeStatusHTML：完整信息渲染（行/列/语言/编码/缩进/缩放）", () => {
  const html = codeStatusHTML({ line: 3, col: 5, lang: "c", utf8: true, indent: 4, zoomPct: 100 });
  assert.match(html, /Ln 3, Col 5/);
  assert.match(html, /class="code-statusbar-pos"/);   // 行列高亮段
  assert.match(html, />C</);                            // 语言徽标（复用 codeTabBadge）
  assert.match(html, /UTF-8/);
  assert.match(html, /空格: 4/);
  assert.match(html, /100%/);
});

test("codeStatusHTML：非 UTF-8 标注 / 自定义缩进 / 缩放百分比", () => {
  const html = codeStatusHTML({ line: 1, col: 1, lang: "md", utf8: false, indent: 2, zoomPct: 120 });
  assert.match(html, /非 UTF-8（只读）/);
  assert.match(html, /空格: 2/);
  assert.match(html, /120%/);
  assert.match(html, />MD</);   // md 语言徽标
});

test("codeStatusHTML：xml 语言徽标与空态（无 lang → 空串）", () => {
  const xml = codeStatusHTML({ line: 1, col: 1, lang: "xml", utf8: true, indent: 4, zoomPct: 100 });
  assert.match(xml, />XML</);
  assert.equal(codeStatusHTML({}), "");                // 无活动文件
  assert.equal(codeStatusHTML(null), "");
  assert.equal(codeStatusHTML({ lang: "" }), "");
});

test("codeStatusHTML：边界钳制（0/负行、列 → 1；缩放 0 → 默认 100%）", () => {
  const html = codeStatusHTML({ line: 0, col: 0, lang: "c", utf8: true, indent: 4, zoomPct: 0 });
  assert.match(html, /Ln 1, Col 1/);
  assert.match(html, /100%/);
  const neg = codeStatusHTML({ line: -3, col: -9, lang: "c" });
  assert.match(neg, /Ln 1, Col 1/);
  const noUtf8 = codeStatusHTML({ line: 2, col: 3, lang: "c" });
  assert.match(noUtf8, /UTF-8/);   // utf8 缺省按 UTF-8 展示
});

// moveTab：标签拖拽排序纯件（工单 code-editor-vscode-polish/03）——
// 前/后插入、拖到末尾、拖回原位（恒等）、未知路径（不变量保持）。
test("moveTab：目标前/后插入（中段）", () => {
  const t = [{ path: "a" }, { path: "b" }, { path: "c" }, { path: "d" }];
  assert.deepEqual(moveTab(t, "a", "c", "before").map((x) => x.path),
    ["b", "a", "c", "d"]);
  assert.deepEqual(moveTab(t, "a", "c", "after").map((x) => x.path),
    ["b", "c", "a", "d"]);
});

test("moveTab：拖到末尾（toPath 空）与拖回原位（恒等）", () => {
  const t = [{ path: "a" }, { path: "b" }, { path: "c" }];
  assert.deepEqual(moveTab(t, "a", null, "after").map((x) => x.path),
    ["b", "c", "a"]);
  assert.deepEqual(moveTab(t, "a", "", "before").map((x) => x.path),
    ["b", "c", "a"]);
  assert.equal(moveTab(t, "b", "b", "before"), t);   // 恒等（同引用）
});

test("moveTab：未知 from / 未知 to（还原原位 / 不变量保持）", () => {
  const t = [{ path: "a" }, { path: "b" }, { path: "c" }];
  assert.equal(moveTab(t, "x", "c", "before"), t);            // from 不存在
  assert.deepEqual(moveTab(t, "b", "x", "before").map((x) => x.path),
    ["a", "b", "c"]);                                          // 目标不存在 → 还原原位
  assert.deepEqual(moveTab([], "a", "b", "before"), []);       // 空清单
});

// ---- 行起点数组 + 二分行号（工单 code-editor-opt/02：O(log n) 替代 O(n) 扫）----

test("buildLineStarts：行数组 → 每行行首绝对偏移", () => {
  assert.deepEqual(buildLineStarts(["a", "b", "c"]), [0, 2, 4]);
  assert.deepEqual(buildLineStarts([""]), [0]);
  assert.deepEqual(buildLineStarts([]), []);
});

test("caretLineFromStarts：与 caretLineOf 语义一致（换行符上 = 前一行行尾）", () => {
  const text = "a\nb\n\nc";
  const ls = buildLineStarts(text.split("\n"));
  for (let p = 0; p <= text.length + 1; p++) {
    assert.equal(caretLineFromStarts(ls, p), caretLineOf(text, p), "pos=" + p);
  }
});

test("caretLineFromStarts：边界（空文/负值/越界/多行内容）", () => {
  assert.equal(caretLineFromStarts([], 5), 1);
  assert.equal(caretLineFromStarts([0], -3), 1);
  assert.equal(caretLineFromStarts([0], 0), 1);
  const ls = buildLineStarts(["x", "", "y"]);
  assert.equal(caretLineFromStarts(ls, 999), 3);   // 越界钳到末行
  assert.equal(caretLineFromStarts(ls, 0), 1);
  assert.equal(caretLineFromStarts(ls, 2), 2);     // 空第二行行首
  assert.equal(caretLineFromStarts(ls, 3), 3);     // 第三行行首
});

test("caretLineFromStarts：随机文本全偏移与 caretLineOf 对拍一致", () => {
  const lines = ["abc", "", "def ghi", "x"];
  const text = lines.join("\n");
  const ls = buildLineStarts(lines);
  for (let p = 0; p <= text.length; p++) {
    assert.equal(caretLineFromStarts(ls, p), caretLineOf(text, p), "pos=" + p);
  }
});

// ---- 行起点表增量修补（fix：第 2 行连打字符错行反转的根因守卫）----

test("patchLineStarts：非结构单行编辑后与全量重建一致（回归）", () => {
  // 现场场景：第 2 行为空行，连打 4 个字符——每次击键行 2 长度 +1，
  // 其后所有行起点必须整体平移，否则下一次击键的 editSpan.line 错算到第 3 行
  const lines = ["line1", "", "line3", "line4"];
  let ls = buildLineStarts(lines);
  lines[1] = "a";            // 第 2 行插入 'a'（delta +1）
  ls = patchLineStarts(ls, 1, 1);
  assert.deepEqual(ls, buildLineStarts(lines));   // 与全量重建一致
  // 第 2 行行尾（pos = 7）在修补后的表上仍属第 2 行；陈旧表 [0,6,7,...] 会误判第 3 行
  assert.equal(caretLineFromStarts(ls, 7), 2);
  lines[1] = "ab";           // 再插 'b'（delta +1）
  ls = patchLineStarts(ls, 1, 1);
  assert.deepEqual(ls, buildLineStarts(lines));
  assert.equal(caretLineFromStarts(ls, 8), 2);
});

test("patchLineStarts：边界（delta 0 / 越界 / 首行 / 不入参修改）", () => {
  const ls = [0, 6, 12, 18];
  assert.equal(patchLineStarts(ls, 1, 0), ls);        // delta 0 → 原引用
  assert.equal(patchLineStarts(ls, -1, 1), ls);       // idx 越界 → 原引用
  assert.equal(patchLineStarts(ls, 9, 1), ls);
  assert.deepEqual(patchLineStarts(ls, 0, 2), [0, 8, 14, 20]);   // 首行 +2
  assert.deepEqual(patchLineStarts(ls, 3, 3), [0, 6, 12, 18]);   // 末行自身不变
  assert.deepEqual(ls, [0, 6, 12, 18]);               // 入参未被修改
});
