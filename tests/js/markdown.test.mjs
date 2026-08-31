// fx/markdown.js 纯函数单测（工单 code-viewer-md-preview/01）：块解析（带
// 1 基行号）/ 预览 HTML / 大纲投影 / 行内与安全（转义、URL 白名单、图片
// 回调）。三个公开出入口：parseMarkdownBlocks(text) → blocks；
// markdownPreviewHTML(blocks, {imageUrl}) → html；markdownOutline(blocks)
// → [{kind, name, line, level}]。直接 import，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  parseMarkdownBlocks,
  markdownPreviewHTML,
  markdownOutline,
} from "../../src/contest_generator/static/js/fx/markdown.js";

test("parseMarkdownBlocks：ATX 标题各层级 + 闭井号剥离 + 1 基行号", () => {
  const blocks = parseMarkdownBlocks("# 一级\n## 二级 ##\n### 三级\n正文");
  assert.deepEqual(blocks, [
    { type: "heading", level: 1, text: "一级", line: 1 },
    { type: "heading", level: 2, text: "二级", line: 2 },
    { type: "heading", level: 3, text: "三级", line: 3 },
    { type: "paragraph", text: "正文", line: 4 },
  ]);
});

test("parseMarkdownBlocks：段落软换行合并为空格（块内物理行保留在 text）", () => {
  const blocks = parseMarkdownBlocks("第一行\n第二行");
  assert.deepEqual(blocks, [{ type: "paragraph", text: "第一行 第二行", line: 1 }]);
});

test("parseMarkdownBlocks：围栏代码块带语言；未闭合兜底到文末", () => {
  const a = parseMarkdownBlocks("```c\nint x;\n```\n尾");
  assert.deepEqual(a[0], { type: "fence", lang: "c", text: "int x;", line: 1 });
  assert.equal(a[1].type, "paragraph");
  const b = parseMarkdownBlocks("```\na\nb");
  assert.deepEqual(b, [{ type: "fence", lang: "", text: "a\nb", line: 1 }]);
});

test("parseMarkdownBlocks：引用连续行（> 前缀剥离）", () => {
  const blocks = parseMarkdownBlocks("> 一\n> 二");
  assert.deepEqual(blocks, [{ type: "blockquote", text: "一\n二", line: 1 }]);
});

test("parseMarkdownBlocks：无序/有序列表嵌套（缩进层级）", () => {
  const ul = parseMarkdownBlocks("- a\n- b\n  - c\n  - d\n- e");
  assert.equal(ul.length, 1);
  assert.equal(ul[0].type, "list");
  assert.equal(ul[0].ordered, false);
  assert.equal(ul[0].items.length, 3);
  assert.deepEqual(ul[0].items.map((i) => i.text), ["a", "b", "e"]);
  assert.deepEqual(ul[0].items[1].items.map((i) => i.text), ["c", "d"]);
  const ol = parseMarkdownBlocks("1. a\n2. b");
  assert.equal(ol[0].ordered, true);
  assert.equal(ol[0].start, 1);
});

test("parseMarkdownBlocks：任务清单（- [ ] / - [x]）", () => {
  const blocks = parseMarkdownBlocks("- [ ] 待办\n- [x] 完成");
  assert.equal(blocks[0].items[0].task, true);
  assert.equal(blocks[0].items[0].checked, false);
  assert.equal(blocks[0].items[1].checked, true);
});

test("parseMarkdownBlocks：管道表（表头 + 分隔 + 数据行）", () => {
  const blocks = parseMarkdownBlocks("| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |");
  assert.deepEqual(blocks, [
    {
      type: "table",
      header: ["A", "B"],
      rows: [["1", "2"], ["3", "4"]],
      line: 1,
    },
  ]);
});

test("parseMarkdownBlocks：水平线（--- / ***）与列表/表格互不误判", () => {
  assert.deepEqual(parseMarkdownBlocks("---"), [{ type: "hr", line: 1 }]);
  assert.deepEqual(parseMarkdownBlocks("***"), [{ type: "hr", line: 1 }]);
  assert.equal(parseMarkdownBlocks("- a")[0].type, "list");
  assert.equal(parseMarkdownBlocks("| A |\n| --- |")[0].type, "table");
});

test("markdownPreviewHTML：标题 h1-h6 带 data-md-line，嵌套结构完整", () => {
  const html = markdownPreviewHTML(parseMarkdownBlocks("# 甲\n## 乙\n### 丙"));
  assert.match(html, /<h1 data-md-line="1">甲<\/h1>/);
  assert.match(html, /<h2 data-md-line="2">乙<\/h2>/);
  assert.match(html, /<h3 data-md-line="3">丙<\/h3>/);
  assert.match(html, /<div class="code-md-preview">/);
});

test("markdownPreviewHTML：围栏代码块 → pre/code，语言经高亮单源着色", () => {
  const html = markdownPreviewHTML(parseMarkdownBlocks("```c\nint x;\n```"));
  assert.match(html, /<pre data-md-line="1"><code>/);
  assert.match(html, /tok-kw/);
});

test("markdownPreviewHTML：引用/列表/任务/表格/hr 均有对应结构", () => {
  const html = markdownPreviewHTML(parseMarkdownBlocks(
    "> 引\n\n- a\n- [x] 完成\n\n| A |\n| --- |\n| 1 |\n\n---"
  ));
  assert.match(html, /<blockquote data-md-line="/);
  assert.match(html, /<ul data-md-line="/);
  assert.match(html, /<input type="checkbox" disabled checked>/);
  assert.match(html, /<table data-md-line="6"><thead><tr><th>A<\/th><\/tr><\/thead>/);
  assert.match(html, /<tbody><tr><td>1<\/td><\/tr><\/tbody>/);
  assert.match(html, /<hr data-md-line="/);
});

test("markdownPreviewHTML：行内粗体/斜体/行内码/删除线/链接", () => {
  const html = markdownPreviewHTML(parseMarkdownBlocks(
    "**粗** *斜* `码` ~~删~~ [链](http://x)"
  ));
  assert.match(html, /<strong>粗<\/strong>/);
  assert.match(html, /<em>斜<\/em>/);
  assert.match(html, /<code>码<\/code>/);
  assert.match(html, /<del>删<\/del>/);
  assert.match(html, /<a href="http:\/\/x">链<\/a>/);
});

test("markdownPreviewHTML：原始 HTML 不透传（全部转义）", () => {
  const html = markdownPreviewHTML(parseMarkdownBlocks("<b>x</b> <script>alert(1)</script>"));
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("<b>"));
  assert.ok(html.includes("&lt;b&gt;x&lt;/b&gt;"));
  assert.ok(html.includes("&lt;script&gt;"));
});

test("markdownPreviewHTML：javascript:/data:/vbscript:/file: 链接 → 文本兜底不产 <a>", () => {
  for (const bad of ["javascript:alert(1)", "data:text/html,x", "vbscript:x", "file:///etc/passwd"]) {
    const html = markdownPreviewHTML(parseMarkdownBlocks("[x](" + bad + ")"));
    assert.ok(!html.includes("<a "), bad);
    assert.ok(!html.includes("javascript:") && !html.includes("vbscript:") && !html.includes("data:") && !html.includes("file:"), bad);
    assert.match(html, />x</, bad); // 标签文本保留（不产生链接形态）
  }
});

test("markdownPreviewHTML：图片经 imageUrl 回调；../ 与协议路径 → 占位；注入拒绝", () => {
  const calls = [];
  const html = markdownPreviewHTML(
    parseMarkdownBlocks("![图](a.png) ![图](../x.png) ![离](https://e/x.png) ![坏](javascript:bad)"),
    {
      imageUrl(src) {
        calls.push(src);
        if (src === "../x.png") return null;                     // 不再被调（渲染器先行拒绝）
        if (src === "javascript:bad") return "javascript:alert(1)"; // 同样不被调
        if (src.startsWith("http")) return src;                  // 协议路径原样
        return "/raw/" + src;
      },
    }
  );
  assert.deepEqual(calls, ["a.png", "https://e/x.png"]);
  assert.match(html, /src="\/raw\/a\.png"/);
  assert.equal((html.match(/md-img-fallback/g) || []).length, 2);  // ../ 与 javascript: 均占位
  assert.match(html, /src="https:\/\/e\/x\.png"/);
  assert.ok(!html.includes("javascript:"));   // 毒 URL 全链路不出现
  assert.ok(!html.includes("src=\"../\""));
});

test("markdownPreviewHTML：无回调时 ../ 与绝对/盘符路径 → 占位（不产可请求 img）", () => {
  const html = markdownPreviewHTML(
    parseMarkdownBlocks("![a](../y.png) ![b](/abs.png) ![c](C:/win.png) ![d](//host/x.png)")
  );
  assert.equal((html.match(/md-img-fallback/g) || []).length, 4);
  assert.ok(!html.includes("src=\"../"));
  assert.ok(!html.includes("src=\"/abs"));
  assert.ok(!html.includes("src=\"C:"));
  assert.ok(!html.includes("src=\"//"));
});

test("markdownPreviewHTML：全部块级元素带 data-md-line（预览内滚动寻址）", () => {
  const html = markdownPreviewHTML(parseMarkdownBlocks(
    "# 题\n\n正文\n\n```\nx\n```\n\n> 引\n\n- a\n\n| A |\n| --- |\n| 1 |\n\n---"
  ));
  assert.match(html, /<h1 data-md-line="1">/);
  assert.match(html, /<p data-md-line="3">/);
  assert.match(html, /<pre data-md-line="5"><code>/);
  assert.match(html, /<blockquote data-md-line="9">/);
  assert.match(html, /<ul data-md-line="11">/);
  assert.match(html, /<table data-md-line="13">/);
  assert.match(html, /<hr data-md-line="17">/);
});

test("markdownPreviewHTML：嵌套有序子列表保留起始号 start", () => {
  const blocks = parseMarkdownBlocks("- a\n  3. b\n  4. c\n- d");
  assert.equal(blocks[0].items[0].ordered, true);
  assert.equal(blocks[0].items[0].start, 3);
  assert.match(markdownPreviewHTML(blocks), /<ol start="3">/);
});

test("markdownPreviewHTML：图片 alt 转义；无回调时相对路径原样透出", () => {
  const html = markdownPreviewHTML(parseMarkdownBlocks("![a<b](c.png)"));
  assert.match(html, /alt="a&lt;b"/);
  assert.match(html, /src="c\.png"/);
});

test("markdownOutline：从同一块列表投影标题清单（kind/name/line/level）", () => {
  const blocks = parseMarkdownBlocks("# A\n## B\n\n### C\n正文\n# 尾");
  assert.deepEqual(markdownOutline(blocks), [
    { kind: "heading", name: "A", line: 1, level: 1 },
    { kind: "heading", name: "B", line: 2, level: 2 },
    { kind: "heading", name: "C", line: 4, level: 3 },
    { kind: "heading", name: "尾", line: 6, level: 1 },
  ]);
  const html = markdownPreviewHTML(blocks);
  assert.match(html, /data-md-line="4"/);     // 行号与大纲一致（不漂移）
});

test("parseMarkdownBlocks：空串/纯空白 → 无块", () => {
  assert.deepEqual(parseMarkdownBlocks(""), []);
  assert.deepEqual(parseMarkdownBlocks("\n\n  \n"), []);
});
