// tab-register-guard.test.mjs — 「最早的标签登记在模块图之前」的结构判据（工单 launcher-exit-race/01）。
//
// ## 这条不变量守的是什么
//
// 启动器模式（`FIRSTEP_LAUNCHER=1`）下「关掉浏览器最后一个标签 = 停服务」：前端 `pagehide`
// 时 `POST /api/tabs/bye`，服务端见注册表空了就起 `_EXIT_GRACE`（1.5 秒）宽限，宽限内没有
// 新的 register 就 `os._exit(0)`。而 register 一旦住在 `app.js` 里，它就要等 `boot.js` 整张
// 模块图（132 个模块 + 4,668 行的 index.html）装载完才发得出来 —— F5 时旧页面的 bye 先到、
// 新页面的 register 迟到 ⇒ **应用把自己的服务关掉**（用户看到死页面）。现场与读数：
// `.scratch/launcher-exit-race/probe-00-order.*`（10 轮里第 4 轮命中）与本单 spec。
//
// 所以"登记必须早于模块图"是**功能正确性**，不是风格。本文件把它变成闸门里的判据：
//   · 判据本体（单源）= `tests/js/boot-contract.mjs` 的 `earlyRegisterProblems`（纯函数）；
//   · 本文件只做两件事：喂**真源码**（必须为 0）+ 喂**合成注入**（每条子判据各自的反例，
//     必须报出，且注入自带"真的落上了"的自检 —— 先例：`export-surface-guard.test.mjs`
//     那种"注入没落上就静默空转"的坑）。
//
// **为什么不给每条子判据各写一份真源码反例**：真源码只有一份，"把登记从 HTML 挪回 app.js"
// 这类改动只能靠合成注入演示（真红证由 `.scratch/launcher-exit-race/probe-01-red-proof.mjs`
// 在**修复前那个提交**上跑同一套判据给出）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  TAB_REGISTER_ENDPOINT, earlyRegisterProblems, scriptBlocks, sessionStorageKeys,
} from "./boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const html = readFileSync(STATIC + "index.html", "utf8");
const appJs = readFileSync(STATIC + "js/app.js", "utf8");

// 合成注入的基线：从**真源码**里抠出那段登记所在的 `<script>` 块，再按需改坏。
// 为什么不手写一份"像真的"HTML：手写的那份迟早与真源码分叉，判据就会开始测一个
// 不存在的页面（本仓库的先例：C5a 两条裸镜像）。
const inlineBlock = scriptBlocks(html).find(
  (b) => b.src === null && b.text.includes(TAB_REGISTER_ENDPOINT));
assert.ok(inlineBlock, `index.html 的内联脚本里找不到 ${TAB_REGISTER_ENDPOINT}`
  + "——登记被挪走了？（本断言失败 = 判据的注入基线没了，下面的用例会全部空转）");

// 判据的注入锚点**从真源码里取**（不手抄键名：手抄的那份改了名以后用例会静默测空气——
// 先例：`ui-contract.spec.mjs` 从产品源码里抠存储键的理由）。
const TAB_KEY = [...sessionStorageKeys(inlineBlock.text)][0];
assert.ok(TAB_KEY, "内联脚本里抠不到 sessionStorage 键——注入锚点没了（下面的用例会全部空转）");

/** 把内联脚本整块替换成 `next`（其余源码一字不动）→ 合成 HTML。 */
function withInline(next) {
  assert.ok(inlineBlock.raw.includes(TAB_REGISTER_ENDPOINT), "注入锚点没对准（整块原文里没有端点字样）");
  return html.replace(inlineBlock.raw, `<script>${next}</script>`);
}

/** 判据报出清单里有没有提到某个关键词（断言用，避免子串匹配散在各处）。 */
const reports = (problems, needle) => problems.some((p) => p.why.includes(needle));

// ---------------------------------------------------------------------------
// 一、抽取面体检：判据"能报出"的证据（断言为空之前先证明它不是真空绿）
// ---------------------------------------------------------------------------
test("抽取面体检：脚本块按字符偏移取得对，sessionStorage 键抽得到", () => {
  const blocks = scriptBlocks(html);
  assert.ok(blocks.length >= 2, `index.html 只抽到 ${blocks.length} 个脚本块（抽取器失效？）`);
  assert.ok(blocks.every((b) => Number.isInteger(b.index) && b.index >= 0),
    "scriptBlocks 必须给每个块字符偏移 index（判据⑥ 的先后比较靠它）");
  assert.ok(blocks[0].index < blocks[blocks.length - 1].index, "块顺序应按出现位置递增");
  // 正向对照：判据对**没登记**的页面必须报出（合成一份最小 HTML，与真源码无关）
  const bare = '<html><head><script>\n  var x = 1;\n</script></head>'
    + '<body><script type="module" src="/js/boot.js"></script></body></html>';
  assert.ok(earlyRegisterProblems(bare, appJs).length > 0,
    "earlyRegisterProblems 对没有任何登记的页面没反应（抽取器失效？）");
  // 键抽取器本身：掩码后注释里的键不算
  assert.deepEqual([...sessionStorageKeys('sessionStorage.getItem("a"); // sessionStorage.getItem("b")')],
    ["a"], "sessionStorageKeys 把注释里的键也算了进去");
});

// ---------------------------------------------------------------------------
// 二、真源码：判据为 0
// ---------------------------------------------------------------------------
test("真源码：最早的标签登记在装载标签之前，两侧同源，两处都带文档实例令牌", () => {
  const problems = earlyRegisterProblems(html, appJs).map((p) => "  · " + p.why);
  assert.deepEqual(problems, [],
    "早注册契约破了（它直接决定 F5 会不会把服务自己关掉）：\n" + problems.join("\n"));
});

test("真源码：登记的端点字面量只有一处（登记点单源 = head 内联脚本）", () => {
  const inApp = appJs.includes(TAB_REGISTER_ENDPOINT) ? 1 : 0;
  const sites = scriptBlocks(html).filter((b) => b.text.includes(TAB_REGISTER_ENDPOINT)).length + inApp;
  assert.equal(sites, 1, `登记端点出现在 ${sites} 处（内联脚本里一处 + app.js 里 ${inApp} 处）`
    + "——两处登记 = 两处会漂的 payload，且「谁更早」重新变成隐式约定");
});

// ---------------------------------------------------------------------------
// 三、合成红证：每条子判据各自的假绿反例（全部内存注入，不写盘）
// ---------------------------------------------------------------------------

test("① 内联脚本里没有登记（挪回模块里）→ 报出", () => {
  const problems = earlyRegisterProblems(withInline("\n  // 登记已经挪回 app.js 了\n"), appJs);
  assert.ok(reports(problems, "内联"), `没报出内联脚本缺登记：${JSON.stringify(problems)}`);
});

test("① 反例：端点字样只出现在**注释**里 → 照样报出（掩码不许被注释喂绿）", () => {
  const injected = withInline(`\n  // 早注册：见 ${TAB_REGISTER_ENDPOINT}（这段只是注释）\n`);
  assert.ok(injected.includes(TAB_REGISTER_ENDPOINT), "注入没落上（锚点变了？）");
  const problems = earlyRegisterProblems(injected, appJs);
  assert.ok(reports(problems, "内联"), `注释里的端点字样把判据喂绿了：${JSON.stringify(problems)}`);
});

test("② 登记挪到**装载标签之后**（另一个内联块）→ 报出", () => {
  const early = inlineBlock.text;
  const after = html.replace(`<script>${early}</script>`, "<script>\n  /* 主题脚本留空 */\n</script>")
    .replace("</body>", `<script>${early}</script>\n</body>`);
  assert.ok(after !== html, "注入没落上（锚点变了？）");
  const problems = earlyRegisterProblems(after, appJs);
  assert.ok(reports(problems, "装载标签之后"),
    `登记挪到装载标签之后没报出：${JSON.stringify(problems)}`);
});

test("③ 两侧 sessionStorage 键不一致（内联脚本改了键名）→ 报出", () => {
  const renamed = withInline(inlineBlock.text.split(TAB_KEY).join(TAB_KEY + "_v2"));
  assert.ok(renamed.includes(TAB_KEY + "_v2"), "注入没落上（键名变了？）");
  const problems = earlyRegisterProblems(renamed, appJs);
  assert.ok(reports(problems, "sessionStorage 键不一致"),
    `两侧键分叉没报出：${JSON.stringify(problems)}`);
});

test("③ 两侧 sessionStorage 键不一致（app.js 改了键名）→ 报出", () => {
  const renamedApp = appJs.split(TAB_KEY).join(TAB_KEY + "_v2");
  assert.ok(renamedApp.includes(TAB_KEY + "_v2"), "注入没落上（键名变了？）");
  const problems = earlyRegisterProblems(html, renamedApp);
  assert.ok(reports(problems, "sessionStorage 键不一致"),
    `两侧键分叉没报出：${JSON.stringify(problems)}`);
});

test("④ 内联脚本的 payload 去掉文档实例令牌 → 报出", () => {
  const stripped = withInline(
    inlineBlock.text.replace(/,\s*epoch\s*:\s*performance\.timeOrigin/, ""));
  assert.ok(!/epoch\s*:/.test(stripped), "注入没落上（payload 形状变了？）");
  const problems = earlyRegisterProblems(stripped, appJs);
  assert.ok(reports(problems, "epoch"), `内联 register 少了 epoch 没报出：${JSON.stringify(problems)}`);
});

test("④ 反例：令牌只出现在**别处**的同名字段里 → 照样报出（判据只看 payload 窗口）", () => {
  // payload 里没有令牌，但脚本别处有一个同名字段：判据若拿"整份源码里有 `epoch:`"当判据，
  // 这一处就能把它喂绿（评审指出的假绿）。注入自带自检：确认那个干扰字段真的落上了。
  const injected = withInline(inlineBlock.text
    .replace(/,\s*epoch\s*:\s*performance\.timeOrigin/, "")
    + "\n  window.__probeDecoy = { epoch: 1 };\n");
  assert.ok(injected.includes("__probeDecoy"), "注入没落上（干扰字段没加上）");
  const problems = earlyRegisterProblems(injected, appJs);
  assert.ok(reports(problems, "epoch"),
    `别处的同名字段把判据喂绿了：${JSON.stringify(problems)}`);
});

test("④ 注销的 payload 去掉文档实例令牌 → 报出", () => {
  const strippedApp = appJs.replace(/,\s*epoch\s*:\s*TAB_EPOCH/, "")
    .replace(/,\s*epoch\s*:\s*performance\.timeOrigin/, "");
  assert.ok(!/epoch\s*:/.test(strippedApp), "注入没落上（payload 形状变了？）");
  const problems = earlyRegisterProblems(html, strippedApp);
  assert.ok(reports(problems, "epoch"), `bye 少了 epoch 没报出：${JSON.stringify(problems)}`);
});
