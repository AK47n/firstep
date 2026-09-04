// fx/highlight.js 纯函数单测（工单 master-library-ui-2/03）：语言判定 /
// XML 高亮 / 分发与超限回退。直接 import，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  languageOf,
  highlightXml,
  highlightText,
  highlightLineHTML,
  lineStatesOf,
  HIGHLIGHT_MAX_BYTES,
} from "../../src/contest_generator/static/js/fx/highlight.js";
import { highlightCodeLines } from "../../src/contest_generator/static/js/fx/codeview.js";

test("languageOf：.c/.h → c；.syscfg/.uvprojx/.cproject/.xml → xml；其余 plain", () => {
  assert.equal(languageOf("main.c"), "c");
  assert.equal(languageOf("user/oled.h"), "c");
  assert.equal(languageOf("MAIN.C"), "c"); // 大小写不敏感
  assert.equal(languageOf("mspm0.syscfg"), "xml");
  assert.equal(languageOf("user/Project.uvprojx"), "xml");
  assert.equal(languageOf(".cproject"), "xml");
  assert.equal(languageOf("design.xml"), "xml");
  assert.equal(languageOf("readme.txt"), "plain");
  assert.equal(languageOf("no-ext"), "plain");
  assert.equal(languageOf(""), "plain");
  // .md/.markdown → md（工单 code-viewer-md-preview/01：预览路由单源）
  assert.equal(languageOf("README.md"), "md");
  assert.equal(languageOf("方案.markdown"), "md");
  assert.equal(languageOf("x.MD"), "md"); // 大小写不敏感
});

test("highlightXml：注释/声明/PI/标签/属性/引号值分类", () => {
  const out = highlightXml('<?xml version="1.0"?>\n<!-- 注 -->\n<Root a="1" b=\'2\'>\n  <Child/>\n</Root>');
  assert.match(out, /<span class="tok-pre">&lt;\?xml version=&quot;1\.0&quot;\?&gt;<\/span>/);
  assert.match(out, /<span class="tok-com">&lt;!-- 注 --&gt;<\/span>/);
  assert.match(out, /<span class="tok-tag">&lt;Root<\/span>/);
  assert.match(out, /<span class="tok-attr">a<\/span/);
  assert.match(out, /<span class="tok-val">&quot;1&quot;<\/span>/);
  assert.match(out, /<span class="tok-val">&#39;2&#39;<\/span>/);
  assert.match(out, /<span class="tok-tag">&lt;\/Root&gt;<\/span>/);
});

test("highlightXml：CDATA 与 DOCTYPE 落入预定义类", () => {
  const out = highlightXml('<!DOCTYPE root [<!ELEMENT root EMPTY>]>\n<![CDATA[raw <b>]]>');
  assert.match(out, /<span class="tok-pre">/);
  assert.match(out, /<span class="tok-str">&lt;!\[CDATA\[raw &lt;b&gt;\]\]&gt;<\/span>/);
});

test("highlightXml：注入样本转义（无裸 <script> 与 &）", () => {
  const out = highlightXml('<a href="x"><script>alert("&")</script></a>');
  assert.ok(!out.includes("<script>"));
  assert.ok(out.includes("&lt;script"));
  assert.ok(out.includes("&amp;"));
});

test("highlightText：C 分发到 cHighlight（tok-kw），plain 纯转义无高亮", () => {
  const c = highlightText("int x = 1;", "c");
  assert.match(c, /<span class="tok-kw">int<\/span>/);
  const plain = highlightText("a < b && c", "plain");
  assert.ok(plain.includes("&lt;"));
  assert.ok(!plain.includes("tok-"));
  const xml = highlightText("<a b='1'>", "xml");
  assert.match(xml, /<span class="tok-tag">&lt;a<\/span>/);
  // md 语言不回退到语法高亮（预览路由专用，源码态=纯文本行号视图）
  const md = highlightText("a < b", "md");
  assert.ok(md.includes("&lt;"));
  assert.ok(!md.includes("tok-"));
});

test("highlightText：超过 HIGHLIGHT_MAX_BYTES 回退纯文本（无高亮 span）", () => {
  const big = "0123456789abcdef".repeat(HIGHLIGHT_MAX_BYTES / 16 + 1);
  assert.ok(big.length > HIGHLIGHT_MAX_BYTES);
  const out = highlightText(big, "c");
  assert.ok(!out.includes("tok-"));
  assert.ok(out.includes("0123456789abcdef"));
});

// ---- 行级跨行态（fix：窗口化编辑器逐行惰性高亮的多行注释/字符串）----

test("highlightLineHTML：多行块注释承接行仍 tok-com（用户现场）", () => {
  const text = "/* 蜂鸣器驱动（MSPM0 占位实现）。\n"
    + " * 接线后按 stm32 侧同款实现。\n"
    + " * 保留本模块是为了两平台 API 统一。 */\n"
    + "void beep_on(void);";
  const lines = text.split("\n");
  const states = lineStatesOf(lines, "c");
  const html = lines.map((l, i) => highlightLineHTML(l, states[i], "c"));
  assert.match(html[0], /tok-com/);
  assert.match(html[1], /tok-com/);   // 此前漏：承接行被当普通代码
  assert.match(html[2], /tok-com/);
  assert.ok(!html[2].includes("tok-kw"));   // 注释内 API 不着关键字
  assert.match(html[3], /tok-fn/);          // 注释结束后正常着色
});

test("行级高亮与整段 highlightCodeLines 逐行严格一致（跨行注释/字符串，C）", () => {
  const samples = [
    "/* a\nb */\nint x;",
    "/* a\nb\nc */\nint y;",
    '/** doc\n * @param x\n */\nvoid f();',
    'char *s = "a\nb";\nint z;',
    'int a = "x\\\ny";',              // 反斜杠续行字符串
    "/* 开\n/* 内层 */\n尾 */\nint w;",
    '/* "引号" 注释内 */\nint q;',
    "a /* b */ c",
    '// "a"\nint k;',
    "/* 未闭合\n仍在注释",
  ];
  for (const text of samples) {
    const full = highlightCodeLines(text, "c");
    const lines = text.split("\n");
    const states = lineStatesOf(lines, "c");
    const per = lines.map((ln, i) => highlightLineHTML(ln, states[i], "c"));
    assert.deepEqual(per, full, "样本不一致: " + JSON.stringify(text));
  }
});

test("行级高亮与整段 highlightCodeLines 逐行严格一致（XML 注释/CDATA/PI/DOCTYPE）", () => {
  const samples = [
    "<!-- a\nb -->\n<x y=\"1\"/>",
    "<r>\n<![CDATA[\nraw <b>\n]]>\n</r>",
    "<?xml\nversion=\"1.0\"?>\n<r/>",
    "<!DOCTYPE root [\n<!ELEMENT root EMPTY>\n]>\n<root/>",
  ];
  for (const text of samples) {
    const full = highlightCodeLines(text, "xml");
    const lines = text.split("\n");
    const states = lineStatesOf(lines, "xml");
    const per = lines.map((ln, i) => highlightLineHTML(ln, states[i], "xml"));
    assert.deepEqual(per, full, "XML 样本不一致: " + JSON.stringify(text));
  }
});

test("lineStatesOf：逐行起始态（注释开合 / 字符串跨越 / plain 恒 null）", () => {
  const lines = ["int a; /* 开", "中", "*/ int b;", '"s', 't"'];
  const states = lineStatesOf(lines, "c");
  assert.equal(states[0], null);                                   // 首行起始恒无跨行态
  assert.deepEqual(states[1], { comment: true, quote: null });
  assert.deepEqual(states[2], { comment: true, quote: null });
  assert.deepEqual(states[3], { comment: false, quote: null });
  assert.deepEqual(states[4], { comment: false, quote: '"' });
  assert.deepEqual(lineStatesOf(["a", "b"], "plain"), [null, null]);
});
