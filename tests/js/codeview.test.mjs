// fx/codeview.js 纯函数单测（工单 code-viewer/04-05）：树构建与排序 /
// 树 HTML / 行号 gutter / 只读视图（高亮分发与转义）/ 大纲 / 搜索结果 /
// 文件内过滤。直接 import，子串断言防脆。运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  buildCodeTree,
  fileIconHTML,
  codeTreeHTML,
  breadcrumbSegments,
  breadcrumbHTML,
  codeLineNumbersHTML,
  highlightCodeLines,
  codeViewHTML,
  outlineHTML,
  outlineEmptyHTML,
  symbolFilter,
  searchListHTML,
  fileFindFilter,
  treeWidthClamp,
  parseTreeWidthStored,
  CODE_TREE_WIDTH_MIN,
  CODE_TREE_WIDTH_MAX,
  CODE_TREE_WIDTH_DEFAULT,
} from "../../src/contest_generator/static/js/fx/codeview.js";

test("buildCodeTree：目录在前、同级码点序，路径逐层聚合", () => {
  const nodes = buildCodeTree([
    { path: "main.c", size_bytes: 10 },
    { path: "src/app.h", size_bytes: 20 },
    { path: "src/ui.h", size_bytes: 30 },
    { path: "readme.md", size_bytes: 5 },
  ]);
  assert.deepEqual(nodes.map((n) => n.name), ["src", "main.c", "readme.md"]);
  assert.deepEqual(nodes[0].children.map((c) => c.name), ["app.h", "ui.h"]);
  assert.equal(nodes[0].isDir, true);
  assert.equal(nodes[1].isDir, false);
  assert.equal(nodes[1].size_bytes, 10);
});

test("buildCodeTree：顺序无关（后端直出任意序）", () => {
  const a = buildCodeTree([
    { path: "b/x.c", size_bytes: 1 },
    { path: "a/y.c", size_bytes: 1 },
  ]);
  const b = buildCodeTree([
    { path: "a/y.c", size_bytes: 1 },
    { path: "b/x.c", size_bytes: 1 },
  ]);
  assert.deepEqual(a, b);
});

test("codeTreeHTML：目录 details/summary，文件行按钮带 data 与转义", () => {
  const nodes = buildCodeTree([
    { path: "dir/z.c", size_bytes: 1 },
    { path: "a<b.c", size_bytes: 3 },
  ]);
  const html = codeTreeHTML(nodes);
  assert.match(html, /<details open[^>]*><summary>/);
  assert.match(html, /data-dir-path="dir"/);   // 面包屑定位（工单 05）
  assert.match(html, /<span class="code-tree-dir-name">dir<\/span>/);
  assert.match(html, /data-code-file="a&lt;b\.c"/);
  assert.ok(!html.includes("a<b.c"));
});

test("codeTreeHTML：节点含类型图标（目录文件夹 + 文件类型，树打磨 01）", () => {
  const nodes = buildCodeTree([
    { path: "src/digit.c", size_bytes: 1 },
    { path: "main.c", size_bytes: 3 },
    { path: "readme.md", size_bytes: 2 },
  ]);
  const html = codeTreeHTML(nodes);
  assert.ok(html.includes('class="code-tree-icon"'));
  assert.equal((html.match(/class="code-ico"/g) || []).length, 4);  // 目录 + 3 文件
  assert.match(html, /<summary><span class="code-tree-icon"/);
});

test("fileIconHTML：扩展名映射 + 未知兜底 + 文件夹（树打磨 01）", () => {
  assert.match(fileIconHTML("main.c", false), /^<svg class="code-ico"/);
  assert.match(fileIconHTML("main.C", false), /^<svg class="code-ico"/);   // 大小写宽容
  assert.match(fileIconHTML("main.c", false), /M6\.6 7/);                  // C <> 标记
  assert.match(fileIconHTML("app.h", false), /M6\.2 5\.8/);                // h 标记
  assert.match(fileIconHTML("notes.md", false), /M6\.3 6\.9/);             // md M 标记
  assert.match(fileIconHTML("board.syscfg", false), /M6\.9 5\.8/);         // 配置 {} 标记
  assert.match(fileIconHTML("blob.bin", false), /<circle/);                // 产物圆点
  assert.match(fileIconHTML("unknown.xyz", false), /^<svg class="code-ico"/);
  assert.ok(!fileIconHTML("unknown.xyz", false).includes("M6.6 7"));       // 未知无标记
  assert.match(fileIconHTML("some/dir", true), /M1\.5 4/);                 // 文件夹
});

test("codeLineNumbersHTML：1..n 逐行 span（带 data-code-line 同 data 键），下限 1", () => {
  assert.equal(
    codeLineNumbersHTML(3),
    '<span class="code-gutter-line" data-code-line="1">1</span>'
      + '<span class="code-gutter-line" data-code-line="2">2</span>'
      + '<span class="code-gutter-line" data-code-line="3">3</span>'
  );
  assert.equal(codeLineNumbersHTML(0), '<span class="code-gutter-line" data-code-line="1">1</span>');
});

test("codeViewHTML：gutter 行数 = pre 渲染行数（尾 \n 计空行），C 高亮走单源", () => {
  const html = codeViewHTML("int x;\nvoid f() {}\n", "c");
  assert.equal((html.match(/class="code-gutter-line"/g) || []).length, 3);
  assert.match(html, /<pre class="code-pre">/);
  assert.match(html, /<span class="tok-kw">int<\/span>/);
  assert.equal((html.match(/class="code-pre-line"/g) || []).length, 3);
  assert.match(html, /data-code-line="1"/);
});

test("codeViewHTML：注入样本转义（纯文本不加高亮 span）", () => {
  const evil = codeViewHTML('<script>alert("&")</script>', "plain");
  assert.ok(!evil.includes("<script>"));
  assert.ok(evil.includes("&lt;script&gt;"));
  assert.ok(!evil.includes("tok-"));
});

test("highlightCodeLines：跨行块注释在行界闭合并按同 class 重开（视觉不变）", () => {
  const lines = highlightCodeLines("/* a\nb */\nint x;", "c");
  assert.equal(lines.length, 3);
  assert.equal((lines[0].match(/class="tok-com"/g) || []).length, 1);
  assert.equal((lines[1].match(/class="tok-com"/g) || []).length, 1);
  assert.ok(lines[0].startsWith('<span class="tok-com">'));
  assert.ok(lines[0].endsWith("</span>"));
  assert.ok(lines[1].startsWith('<span class="tok-com">'));
  assert.ok(lines[2].includes("tok-kw"));
  assert.ok(!lines[2].includes("tok-com"));
});

test("highlightCodeLines：尾 \\n 空行 / 空内容各得独立元素（与 gutter 对齐）", () => {
  assert.deepEqual(highlightCodeLines("", "c"), [""]);
  const lines = highlightCodeLines("a\n", "plain");
  assert.equal(lines.length, 2);
  assert.equal(lines[1], "");
  // 转义样本：高亮输出不回引原文
  assert.deepEqual(highlightCodeLines("<script>", "plain"), ["&lt;script&gt;"]);
});

test("outlineHTML：kind 徽标 + name + 行号；空 → 空串", () => {
  const html = outlineHTML([
    { kind: "function", name: "main", line: 3 },
    { kind: "define", name: "LED", line: 1 },
    { kind: "include", name: "app.h", line: 1 },
    { kind: "heading", name: "方案", line: 2 },   // .md 标题（工单 code-viewer-md-preview/01）
  ]);
  assert.match(html, /data-outline-line="3"/);
  assert.match(html, /k-function/);
  assert.match(html, />main</);
  assert.match(html, />LED</);
  assert.match(html, /k-heading/);
  assert.match(html, />H</);
  assert.equal(outlineHTML([]), "");
  assert.equal(outlineHTML(null), "");
});

test("outlineEmptyHTML：中文空态文案", () => {
  assert.match(outlineEmptyHTML(), /当前文件无大纲/);
});

// ===== 大纲符号过滤（工单 code-editor-refine/03：Ctrl+Shift+O 符号速达）=====

test("symbolFilter：空 query 返回原序副本；null/undefined 安全", () => {
  const outline = [
    { kind: "function", name: "main", line: 10 },
    { kind: "define", name: "LED_PIN", line: 2 },
  ];
  assert.deepEqual(symbolFilter(outline, ""), outline);
  assert.deepEqual(symbolFilter(outline, "   "), outline);
  assert.deepEqual(symbolFilter(outline, null), outline);
  assert.deepEqual(symbolFilter(null, "x"), []);
  assert.notEqual(symbolFilter(outline, ""), outline);   // 副本，不共享引用
});

test("symbolFilter：大小写不敏感 name 子串", () => {
  const outline = [
    { kind: "function", name: "main", line: 10 },
    { kind: "define", name: "LED_PIN", line: 2 },
    { kind: "define", name: "led_delay", line: 30 },
  ];
  assert.deepEqual(symbolFilter(outline, "led"),
    [outline[1], outline[2]]);   // 两个前缀命中按 line 稳定
  assert.deepEqual(symbolFilter(outline, "LED"),
    [outline[1], outline[2]]);
  assert.deepEqual(symbolFilter(outline, "MAIN"), [outline[0]]);
});

test("symbolFilter：函数优先 > 名称前缀，同级按行号", () => {
  const outline = [
    { kind: "function", name: "setup_timer", line: 40 },
    { kind: "function", name: "setup", line: 70 },
    { kind: "define", name: "setup_led", line: 5 },     // define 前缀命中，但函数优先
    { kind: "function", name: "teardown_setup", line: 20 },
  ];
  assert.deepEqual(symbolFilter(outline, "setup"),
    [outline[1], outline[0], outline[3], outline[2]]);
  // 函数组内：精确 setup > 前缀 setup_timer > 普通子串 teardown_setup；define 最后
});

test("symbolFilter：kind 匹配（define/include/function/heading）", () => {
  const outline = [
    { kind: "function", name: "main", line: 10 },
    { kind: "define", name: "LED", line: 2 },
    { kind: "define", name: "BAUD", line: 7 },
    { kind: "include", name: "app.h", line: 1 },
    { kind: "heading", name: "方案设计", line: 4 },
  ];
  assert.deepEqual(symbolFilter(outline, "define"), [outline[1], outline[2]]);   // 按行号
  assert.deepEqual(symbolFilter(outline, "include"), [outline[3]]);
  assert.deepEqual(symbolFilter(outline, "function"), [outline[0]]);
  assert.deepEqual(symbolFilter(outline, "heading"), [outline[4]]);
});

test("symbolFilter：无匹配 → []", () => {
  const outline = [
    { kind: "function", name: "main", line: 10 },
    { kind: "define", name: "LED", line: 2 },
  ];
  assert.deepEqual(symbolFilter(outline, "zzz"), []);
});

test("searchListHTML：命中行 + active 高亮 + 转义；空态", () => {
  const html = searchListHTML(
    [
      { path: "main.c", line: 2, text: "void helper(){}" },
      { path: "app.h", line: 5, text: "x<y" },
    ],
    "main.c"
  );
  assert.match(html, /data-search-path="main\.c" data-search-line="2"/);
  assert.match(html, /class="code-search-hit on"/);
  assert.ok(html.includes("x&lt;y"));
  assert.match(searchListHTML([], "x"), /没有命中/);
});

test("fileFindFilter：大小写不敏感子串，返回 1 基行号；空 q → []", () => {
  const lines = ["#include <stdio.h>", "int main(void) {", "return 0;", "// STDIO"];
  assert.deepEqual(fileFindFilter(lines, "stdio"), [1, 4]);
  assert.deepEqual(fileFindFilter(lines, "STDIO"), [1, 4]);
  assert.deepEqual(fileFindFilter(lines, "  "), []);
  assert.deepEqual(fileFindFilter(lines, "nope"), []);
});

// ===== 树面板拖拽调宽纯函数（工单 code-viewer-tree-resize/01）=====

test("CODE_TREE_WIDTH_* 常量：160 / 720 / 240", () => {
  assert.equal(CODE_TREE_WIDTH_MIN, 160);
  assert.equal(CODE_TREE_WIDTH_MAX, 720);
  assert.equal(CODE_TREE_WIDTH_DEFAULT, 240);
});

test("treeWidthClamp：非数值 → 默认 240；下限 160；上限 min(720, layoutW-480)", () => {
  assert.equal(treeWidthClamp(NaN, 1000), 240);
  assert.equal(treeWidthClamp(undefined, 1000), 240);
  assert.equal(treeWidthClamp("x", 1000), 240);
  assert.equal(treeWidthClamp(50, 1000), 160);          // 下限
  assert.equal(treeWidthClamp(300, 1000), 300);          // 中段原样
  assert.equal(treeWidthClamp(299.6, 1000), 300);        // 四舍五入
  assert.equal(treeWidthClamp(5000, 1000), 520);         // cap = 1000-480
  assert.equal(treeWidthClamp(720, 2000), 720);          // 上限 720
  assert.equal(treeWidthClamp(300, 400), 160);           // 窄布局 cap 回落下限
  assert.equal(treeWidthClamp(300, 640), 160);           // 640-480=160 → 仅下限
  assert.equal(treeWidthClamp(300, NaN), 300);           // layoutW 非有限 → 不收缩
  assert.equal(treeWidthClamp(350, 0), 350);             // 隐藏态（display:none 取宽 0）→ 保留
});

test("parseTreeWidthStored：非法/空 → 240；parseInt 后收敛同 clamp", () => {
  assert.equal(parseTreeWidthStored(null, 1000), 240);
  assert.equal(parseTreeWidthStored("", 1000), 240);
  assert.equal(parseTreeWidthStored("abc", 1000), 240);
  assert.equal(parseTreeWidthStored("320", 1000), 320);
  assert.equal(parseTreeWidthStored("320px", 1000), 320);   // parseInt 容忍后缀
  assert.equal(parseTreeWidthStored("314.9", 1000), 314);   // parseInt 截断小数
  assert.equal(parseTreeWidthStored("50", 1000), 160);      // 下限收敛
  assert.equal(parseTreeWidthStored("5000", 1000), 520);    // 上限收敛
  assert.equal(parseTreeWidthStored("300", 400), 160);      // 窄布局收敛
  assert.equal(parseTreeWidthStored("350", 0), 350);        // 隐藏态恢复不塌到 160
});

test("buildCodeTree/codeTreeHTML：changes 参数标「新/变」徽章（code-ide-flow/02）", () => {
  const nodes = buildCodeTree([
    { path: "main.c", size_bytes: 10 },
    { path: "new/oled.c", size_bytes: 5 },
    { path: "readme.md", size_bytes: 2 },
  ], { "main.c": "modified", "new/oled.c": "new" });
  const html = codeTreeHTML(nodes);
  assert.match(html, /class="code-tree-badge b-mod"/);           // 修改 → 变
  assert.match(html, /class="code-tree-badge b-new"/);           // 新增 → 新
  assert.match(html, /title="新增文件"/);
  assert.match(html, /title="已修改"/);
  // 未命中 changes 的文件无徽章；节点带 change 字段（纯件契约）
  const mainNode = buildCodeTree([{ path: "main.c", size_bytes: 1 }],
    { "main.c": "modified" })[0];
  assert.equal(mainNode.change, "modified");
  // 无 changes → 行为与旧版一致（零徽章）
  const plain = codeTreeHTML(buildCodeTree([{ path: "main.c", size_bytes: 1 }]));
  assert.ok(!plain.includes("code-tree-badge"));
  // changes 命中目录路径不标（徽章只挂在文件行）
  const dirHtml = codeTreeHTML(buildCodeTree(
    [{ path: "src", is_dir: true }], { src: "new" }));
  assert.ok(!dirHtml.includes("code-tree-badge"));
});

// ---- 面包屑（工单 code-page-vscode-overhaul/05）----

test("breadcrumbSegments：相对路径逐段累积（目录/文件标记）", () => {
  assert.deepEqual(breadcrumbSegments("src/ui/main.c"), [
    { name: "src", path: "src", isDir: true },
    { name: "ui", path: "src/ui", isDir: true },
    { name: "main.c", path: "src/ui/main.c", isDir: false },
  ]);
  assert.deepEqual(breadcrumbSegments("main.c"), [
    { name: "main.c", path: "main.c", isDir: false },
  ]);
  assert.deepEqual(breadcrumbSegments(""), []);
  assert.deepEqual(breadcrumbSegments(null), []);
});

test("breadcrumbHTML：目录段按钮 data-breadcrumb-dir + 转义，文件段 data-breadcrumb-file，分隔符 ›", () => {
  const html = breadcrumbHTML(breadcrumbSegments("src/a<b/main.c"));
  assert.ok(html.includes('data-breadcrumb-dir="src"'));
  assert.ok(html.includes('data-breadcrumb-dir="src/a&lt;b"'));
  assert.ok(html.includes('data-breadcrumb-file="src/a&lt;b/main.c"'));
  assert.ok(html.includes("›"));
  assert.ok(!html.includes("a<b"));
  assert.ok(!html.includes('class="code-crumb-dir" data-breadcrumb-dir="src/a&lt;b/main.c"'));
});

test("breadcrumbHTML：超长段截断（…）并保留 title 全量路径", () => {
  const long = "very-long-directory-name-abcdefghijklmnopqrstuvwxyz-123";
  const html = breadcrumbHTML(breadcrumbSegments(long + "/x.c"));
  assert.ok(html.includes("…"));
  assert.ok(html.includes('title="' + long + '"'));
  assert.ok(!html.includes(long + ">"));   // 全名不出现在按钮文本
});

test("breadcrumbHTML：空分段 → 空串", () => {
  assert.equal(breadcrumbHTML([]), "");
  assert.equal(breadcrumbHTML(null), "");
});
