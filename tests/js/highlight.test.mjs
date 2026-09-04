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
  lineStatesRefresh,
  stateEq,
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

// ---- lineStatesRefresh：编辑后增量续算 + 状态收敛早停（工单 editor-line-state-opt/01）----

test("lineStatesRefresh：真实路径（行已更新、起始态为旧值）与全量重算一致，返回首个变化行", () => {
  // 每个用例：orig = 编辑前文本；apply 原地改行（模拟非结构/结构编辑后的行数组）；
  // edit = 变更起始行索引；end = 变更区末行（排他，缺省 edit+1 = 单行）——
  // 真实路径：states 仍是编辑前的旧起始态，lines[edit, end) 已是新文本。
  const cases = [
    // 常见输入：行内注释结构未变 → 单行变更区第 1 行即收敛（早停），返回 -1
    {
      lang: "c",
      orig: ["int a;", "int b;", "/* 开", "中", "*/ int c;"],
      edit: 1,
      apply: (l) => { l[1] = "int bb;"; },
    },
    // 打开块注释：状态变化直到注释关闭行收敛
    {
      lang: "c",
      orig: ["int a;", "int b;", "int c;", "/* 开", "*/ int d;", "int e;"],
      edit: 1,
      apply: (l) => { l[1] = "/* 开"; },
    },
    // 提前闭合注释：第 2 行补上闭注释 → 其后起始态在闭合行收敛
    {
      lang: "c",
      orig: ["int a;", "/* 开", "中", "int d;", "int e;"],
      edit: 2,
      apply: (l) => { l[2] = "*/ int dd;"; },
    },
    // 跨行字符串开启（未闭合至文末：变化段 = 剩余行，早停不适用但结果仍全量一致）
    {
      lang: "c",
      orig: ['char *s = "a', "b\";", "int x;", "int y;"],
      edit: 0,
      apply: (l) => { l[0] = 'char *s = "a'; },
    },
    // 行内注释打开（未闭合）：变化段延伸到下一行开注释处收敛
    {
      lang: "c",
      orig: ["int a;", "int b;", 'char *s = "x', 'y";', "int z;"],
      edit: 1,
      apply: (l) => { l[1] = "int bb; /* 开"; },
    },
    // XML 注释提前闭合
    {
      lang: "xml",
      orig: ["<r/>", "<!-- 开", "中", "<x/>"],
      edit: 2,
      apply: (l) => { l[2] = "中 -->"; },
    },
    // XML CDATA 开启后闭合（收敛于 ]]>
    {
      lang: "xml",
      orig: ["<r/>", "<x/>", "]]>", "</r>"],
      edit: 1,
      apply: (l) => { l[1] = "<![CDATA["; },
    },
    // plain：恒 null
    {
      lang: "plain",
      orig: ["a", "b", "c"],
      edit: 0,
      apply: (l) => { l[0] = "aa"; },
    },
    // 多行变更区（[2,4) 行文本都被替换）：区内起始态碰巧未变也不得早停——
    // 第 4 行（索引 3）新开 /* 使其后承接行起始态变化（评审实测案例；旧契约
    // 在区内收敛会漏算并在错误状态上续算 —— 用户故事 2 守护）
    {
      lang: "c",
      orig: ["int a;", "int b;", "old3", "old4", "old5", "old6"],
      edit: 2,
      end: 4,
      apply: (l) => { l[2] = "int bb;"; l[3] = "/* 开"; },
    },
    // 多行变更区内开合自平衡（第 4 行开注释并在本行闭合）：变化只发生在区内，
    // 越过变更区状态回旧值 → 无变化行（-1），但区内行仍需逐个扫描
    {
      lang: "c",
      orig: ["int a;", "int b;", "old3", "old4", "old5", "old6"],
      edit: 2,
      end: 4,
      apply: (l) => { l[2] = "int bb;"; l[3] = "/* 开 */"; },
    },
  ];
  for (const c of cases) {
    const lang = c.lang || "c";
    const orig = c.orig.slice();
    const oldStates = lineStatesOf(orig, lang);
    const lines = orig.slice();
    c.apply(lines);
    const states = oldStates.slice();          // 编辑前起始态
    const ref = states;
    const changed = lineStatesRefresh(lines, states, c.edit, lang, c.end == null ? c.edit + 1 : c.end);
    assert.equal(states, ref, "必须原地写（不换引用）: " + JSON.stringify(c.orig));
    const full = lineStatesOf(lines, lang);
    assert.deepEqual(states, full,
      "与全量重算不一致: " + JSON.stringify(c.orig) + " 编辑行=" + c.edit);
    // 期望变化索引 = 首个（> edit）起始态与旧值不同的行；无变化 → -1
    let expected = -1;
    for (let i = c.edit + 1; i < lines.length; i++) {
      if (!stateEq(full[i], oldStates[i])) { expected = i; break; }
    }
    assert.equal(changed, expected,
      "变化索引不符: " + JSON.stringify(c.orig) + " 编辑行=" + c.edit);
  }
});

test("lineStatesRefresh：边界（空数组 / fromIdx 越界 / 末行 / 幂等收敛）", () => {
  const lines = ["a", "b", "c"];
  const states = lineStatesOf(lines, "plain");
  assert.equal(lineStatesRefresh([], [], 0, "c"), -1);
  assert.equal(lineStatesRefresh(lines, states, -1, "plain"), -1);
  assert.equal(lineStatesRefresh(lines, states, 3, "plain"), -1);
  assert.equal(lineStatesRefresh(lines, states, 2, "plain"), -1);  // 末行：其后无行
  assert.deepEqual(states, [null, null, null]);                    // 越界路径不改动
  // 幂等：对已等于全量重算结果的 states 再刷（单行区）→ 第 1 行即收敛 → -1
  const cLines = ["int a; /* 开", "中", "*/ int b;", "int c;"];
  const cStates = lineStatesOf(cLines, "c");
  assert.equal(lineStatesRefresh(cLines, cStates, 0, "c", 1), -1);
  assert.deepEqual(cStates, lineStatesOf(cLines, "c"));
  // changedEndIdx 越界钳制：> n 退化为到文末（正确但无早停）；< fromIdx+1 钳到单行区
  const dStates = lineStatesOf(cLines, "c");
  assert.equal(lineStatesRefresh(cLines, dStates, 0, "c", 999), -1);
  const eLines = ["int a;", "int b;", "int c;"];
  const eStates = lineStatesOf(eLines, "c");
  eLines[1] = "/* 开";
  assert.equal(lineStatesRefresh(eLines, eStates, 1, "c", 0), 2);  // 钳到 [1,2)
  assert.deepEqual(eStates, lineStatesOf(eLines, "c"));
});
