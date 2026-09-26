// bold-marker-guard.test.mjs — 「产品串里不许出现 markdown 粗体标记」不变量
// （工单 hwcheck-hygiene/02；判据本体单源在 `tests/js/boot-contract.mjs` 判据 ⑨）。
//
// ## 这条不变量要挡的是什么
//
// 提示文案里写 `**加粗**`，到页面上就是两个字面星号——学生看到 `**未经验证**` 而不是加粗的
// "未经验证"。这类回潮此前**没有任何东西挡着**：`includes("未经验证")` 那种断言照样绿
// （星号在短语**外面**），真浏览器用例只看行为。实测 5 处 / 3 个文件，跨 `innerHTML` 与
// `textContent` 两条渲染路径。
//
// ## 口径（详见 `boot-contract.mjs` 判据 ⑨ 段头）
//
//   只判**字符串 / 模板字面量文本段**的内容：注释里的 `**`（本仓满屏 `/** */`）不算、
//   正则字面量里的不算、幂运算符 `${a ** b}` 不算；唯一例外 `fx/markdown.js`（解析器本体，
//   `**` 就是语法），例外是**一条具名常量 + 自检**，不是可随手加行的名单。
//
// ## 红证
//
// `.scratch/hwcheck-hygiene/probe-02-red.py`（把「不用你自己改」那句的星号塞回去 → 本文件红；
// 复原后 sha256 逐字节相同），读数 `probe-02-red.txt`。
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import {
  readJsModules, boldMarkerProblems, stringTextSegments, maskNonCode,
  BOLD_MARKER_EXEMPT_KEY, BOLD_MARKER_EXEMPT_EXPORT, parseModuleExports,
} from "./boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const MODULES = readJsModules(STATIC);
const patch = (entries, key, fn) =>
  entries.map((e) => (e.key === key ? { ...e, text: fn(e.text) } : e));
const KEY = "ui/hwcheck.js";                    // 注入锚点：一个真在判据面里的模块

test("取数面体检：字符串段抽得到（那种绿比红更坏）", () => {
  const face = MODULES.filter((m) => /^(fx|ui)\//.test(m.key));
  assert.ok(face.length >= 100, `判据面只抽到 ${face.length} 个 fx/ui 模块（目录结构变了？）`);
  const segs = face.reduce((n, m) => n + stringTextSegments(m.text, maskNonCode(m.text)).length, 0);
  assert.ok(segs >= 5000, `字符串 / 模板文本段只抽到 ${segs} 段（下限 5000）——判据会真空绿`);
});

test("判据 ⑨：产品串里没有 markdown 粗体标记（违规 = 0）", () => {
  const bad = boldMarkerProblems(MODULES)
    .map((v) => `  ${v.key}:${v.line}  ${v.value}`);
  assert.deepEqual(bad, [],
    "这些**字符串 / 模板文本段**里含着 markdown 粗体标记 `**` —— 到了页面上就是两个字面星号。\n"
    + "改法：要么去掉星号，要么换成页面本来就有的行内元素（`<b>` / 既有样式类）；\n"
    + "`textContent` 那条路径只能去掉（那里不解释 HTML）。口径见 tests/js/boot-contract.mjs 判据 ⑨：\n"
    + bad.join("\n"));
});

test("判据 ⑨ 正向对照：往一个真模块的产品串里注入 `**` 必须报出", () => {
  const patched = patch(MODULES, KEY, (t) => `${t}\nconst _probeBold = "这一趟工程**未经验证**";\n`);
  assert.ok(patched.some((e) => e.key === KEY && e.text.includes("_probeBold")),
    `注入没落上（锚点键 \`${KEY}\` 不存在？）—— 这条自检会静默空转`);
  const hit = boldMarkerProblems(patched).some((v) => v.key === KEY && v.value.includes("未经验证"));
  assert.ok(hit, "注入的字面星号没被报出 —— 判据静默失效（取数面没扫到字符串？）");
});

test("判据 ⑨ 掩码自检：注释 / 正则 / 幂运算符里的 `**` 都不算", () => {
  const cases = [
    ["// 注释里的 ** 强调不算\nconst x = 1;\n", []],
    ["/* 块注释里的 ** 也不算 */\nconst x = 1;\n", []],
    ["const re = /\\*\\*/;\n", []],
    ['const s = `${a ** b}`;\n', []],                        // 模板表达式段 = 代码
    ['const s = "**不是强调**";\n', ["**不是强调**"]],        // 产品串 → 报
    ["const s = `前**中**后`;\n", ["前**中**后"]],            // 模板文本段 → 报
    ['const s = `a${x}**b**`;\n', ["**b**"]],                 // 表达式之后的文本段 → 报
    ['const s = "\\"含引号\\" **粗**";\n', ['\\"含引号\\" **粗**']],  // 转义不误判段边界
    // 表达式**内部**的字符串 / 嵌套模板照扫（本仓模板里套三元、三元里套模板是常态）
    ['const s = `前缀${a ? "**表达式内的串**" : ""}`;\n', ["**表达式内的串**"]],
    ['const s = `${`内层**文本段**`}`;\n', ["内层**文本段**"]],
  ];
  for (const [body, expect] of cases) {
    const hits = boldMarkerProblems([{ key: "ui/probe.js", text: body }]).map((v) => v.value);
    assert.deepEqual(hits, expect, `取数面判错（语料：${JSON.stringify(body)}）`);
  }
  // 未闭合字面量按掩码件的止损口径收尾（不许把后续代码整段吞成字符串）
  const unterminated = 'const s = "没闭合 ** ;\nconst t = "另一段";\n';
  assert.deepEqual(boldMarkerProblems([{ key: "ui/probe.js", text: unterminated }]).map((v) => v.value),
    ["没闭合 ** ;"], "未闭合字符串的止损口径变了 —— 会把后续代码整段当字符串");
  // 行号要指到 `**` 真正所在的那一行（不是字面量起始行）
  const multiline = 'const s = `第一行\n第二行\n第三行 **粗**`;\n';
  assert.deepEqual(boldMarkerProblems([{ key: "ui/probe.js", text: multiline }]).map((v) => v.line), [3],
    "跨行模板的行号指到了字面量起始行 —— 报错时人会看错地方");
});

test("判据 ⑨ 例外自检：唯一例外确实是 markdown 解析器本体，且例外没有腐烂", () => {
  const exempt = MODULES.find((m) => m.key === BOLD_MARKER_EXEMPT_KEY);
  assert.ok(exempt, `例外模块 \`${BOLD_MARKER_EXEMPT_KEY}\` 不存在了 —— 例外已过期，删掉它`);
  assert.ok(parseModuleExports(exempt.text).has(BOLD_MARKER_EXEMPT_EXPORT),
    `\`${BOLD_MARKER_EXEMPT_KEY}\` 不再导出 \`${BOLD_MARKER_EXEMPT_EXPORT}\` —— 例外已过期，删掉它`);
  // 例外必须**真的**还需要：那个文件里确实有含 `**` 的产品串（否则它不该留在例外里）
  const code = maskNonCode(exempt.text);
  assert.ok(stringTextSegments(exempt.text, code).some((s) => s.value.includes("**")),
    `\`${BOLD_MARKER_EXEMPT_KEY}\` 里已经没有含 \`**\` 的字符串了 —— 例外已过期，删掉它`);
  // 反向：**撤掉例外**必须报出（证明例外是"唯一被豁免的那一处"，不是把整条判据喂绿）
  // 注意：例外按**模块键**生效，所以这里把同一份源码换一个键喂进去 = 撤掉豁免
  const unexempt = boldMarkerProblems([{ key: "fx/probe-markdown-copy.js", text: exempt.text }]);
  assert.ok(unexempt.length > 0,
    "撤掉例外后解析器本体一条都不报 —— 这条自检空转（例外没在起作用？判据把它跳过了？）");
  // 例外是**语法 token** 粒度、不是"这个文件随便写"：同一个文件里写产品文案照样报
  const abused = boldMarkerProblems([{
    key: BOLD_MARKER_EXEMPT_KEY,
    text: `${exempt.text}\nconst _probeCopy = "这句是**产品文案**，不是语法";\n`,
  }]);
  assert.ok(abused.some((v) => v.value.includes("产品文案")),
    "在解析器文件里写 `**加粗**` 式产品文案没被报出 —— 例外变成了整文件豁免的漏洞");
});
