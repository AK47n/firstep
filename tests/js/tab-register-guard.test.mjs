// tab-register-guard.test.mjs — 标签会话的两条结构判据：**最早的登记在模块图之前**
//（工单 launcher-exit-race/01，判据⑥）与**bfcache 恢复时补登记**（工单
// bfcache-return-register/01，判据⑦）。
//
// ## 这两条不变量守的是什么
//
// 启动器模式（`FIRSTEP_LAUNCHER=1`）下「关掉浏览器最后一个标签 = 停服务」：前端 `pagehide`
// 时 `POST /api/tabs/bye`，服务端见注册表空了就起 `_EXIT_GRACE`（1.5 秒）宽限，宽限内没有
// 新的 register 就 `os._exit(0)`。于是有两个方向会误伤：
//   · **新文档登记迟到**（F5）：register 一旦住在 `app.js` 里，它要等 `boot.js` 整张模块图
//     （132 个模块 + 4,600 行的 index.html）装载完才发得出来 ⇒ 宽限内没到 ⇒ 服务自杀
//     （现场：`.scratch/launcher-exit-race/probe-00-order.*`，10 轮里第 4 轮命中）；
//   · **老文档回来不报到**（bfcache）：用户导航走时浏览器把本文档冻结进 bfcache（那一下同样
//     触发 pagehide ⇒ 照发告别），而按后退回来时**脚本一行都不重跑** ⇒ 没人补登记 ⇒ 服务
//     已经停了 ⇒ 死页面（现场：`.scratch/bfcache-return-register/probe-00-bfcache-red.*`）。
//
// 所以两条都是**功能正确性**，不是风格。本文件把它们变成闸门里的判据：
//   · 判据本体（单源）= `tests/js/boot-contract.mjs` 的 `earlyRegisterProblems`（判据⑥）与
//     `restoreRegisterProblems`（判据⑦），都是纯函数；
//   · 本文件只做两件事：喂**真源码**（必须为 0）+ 喂**合成注入**（每条子判据各自的反例，
//     必须报出，且注入自带"真的落上了"的自检 —— 先例：`export-surface-guard.test.mjs`
//     那种"注入没落上就静默空转"的坑）。
//
// **为什么不给每条子判据各写一份真源码反例**：真源码只有一份，"把登记从 HTML 挪回 app.js"
// 这类改动只能靠合成注入演示（真红证由 `.scratch/launcher-exit-race/probe-01-red-proof.mjs`
// 与 `.scratch/bfcache-return-register/probe-00-bfcache-red.mjs` 在**修复前那个提交**上跑
// 同一套判据给出）。
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  TAB_REGISTER_ENDPOINT, earlyRegisterProblems, restoreRegisterProblems,
  scriptBlocks, sessionStorageKeys, SERVICE_STOPPED_EVENT,
} from "./boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const html = readFileSync(STATIC + "index.html", "utf8");
const appJs = readFileSync(STATIC + "js/app.js", "utf8");
// 可见态那一半的对侧文件（工单 bfcache-return-register/01）。文件不该缺席，但**缺席时
// 要由判据报出来**（而不是本文件在 import 期就炸掉，让"红在哪"看不出来）。
const SERVICE_STOPPED_KEY = "js/ui/service-stopped.js";
const uiJs = existsSync(STATIC + SERVICE_STOPPED_KEY)
  ? readFileSync(STATIC + SERVICE_STOPPED_KEY, "utf8")
  : "";

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
  // 全局替换：块内现在有**两处** register payload（初载 + bfcache 恢复补登记，判据 ⑦），
  // 只去掉第一处会让第二处把判据喂绿（本用例的自我检查就是为此）。
  const stripped = withInline(
    inlineBlock.text.replace(/,\s*epoch\s*:\s*performance\.timeOrigin/g, ""));
  assert.ok(!/epoch\s*:/.test(stripped), "注入没落上（payload 形状变了？）");
  const problems = earlyRegisterProblems(stripped, appJs);
  assert.ok(reports(problems, "epoch"), `内联 register 少了 epoch 没报出：${JSON.stringify(problems)}`);
});

test("④ 反例：令牌只出现在**别处**的同名字段里 → 照样报出（判据只看 payload 窗口）", () => {
  // payload 里没有令牌，但脚本别处有一个同名字段：判据若拿"整份源码里有 `epoch:`"当判据，
  // 这一处就能把它喂绿（评审指出的假绿）。注入自带自检：确认那个干扰字段真的落上了。
  // 同样**全局**去掉两处 payload 的令牌（判据 ⑦ 落地后块内有两处），否则第二处会喂绿。
  const injected = withInline(inlineBlock.text
    .replace(/,\s*epoch\s*:\s*performance\.timeOrigin/g, "")
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

// ---------------------------------------------------------------------------
// 三点五、**登记那一发要能扛住一次失败**（工单 ci-gate-fixes/05）
//
// 为什么这条是功能正确性而不是风格：那一发丢在传输层时（浏览器从连接池里取到一条已被
// 服务端按 keep-alive 关掉的空闲连接 ⇒ `ERR_CONNECTION_REFUSED` / `ERR_CONNECTION_RESET`），
// 没有重试 = 登记永远不发生 ⇒ 旧文档的 bye 把注册表清空 ⇒ 1.5 秒宽限到点 ⇒ 应用把正在
// 装载的新页面拦腰掐断（现场读数 `.scratch/ci-gate-fixes/probe-05-catch2-logs/`，
// 确定性红回路 `.scratch/ci-gate-fixes/probe-05-redproof.mjs`）。
//
// 判据**不绑写法**：递归、循环、`Promise` 链都认；管的是三件事——① 首登记那一发真有重试；
// ② 重试的等待**压得比宽限短**（等太久，重试落在宽限之后照样是自杀）；③ 等待用延时而不是
// 立刻狂发（同步死循环会把页面的解析卡住，登记反而更晚）。
// ③ 的锚点是 `setTimeout`；①② 的锚点从**真源码**里抠（不手抄字面量——先例：存储键也是抠的）。
// ---------------------------------------------------------------------------

/** 真源码里登记那一发的重试参数：`{ attempts, delays[] }`（抠不到 = 空数组）。 */
function registerRetry(text) {
  const retries = [...text.matchAll(/setTimeout\s*\(\s*function\s*\(\s*\)\s*\{[^}]*attemptRegister\s*\(/g)]
    .map((m) => Number((/setTimeout\s*\(\s*function\s*\(\s*\)\s*\{[^}]*\}\s*,\s*(\d+)\s*\)/.exec(
      text.slice(m.index)) || [])[1]));
  const seed = /\}\s*\)\s*\(\s*(\d+)\s*\)\s*;/.exec(text);
  return { delays: retries.filter((n) => Number.isFinite(n)),
    attempts: seed ? Number(seed[1]) + 1 : 0 };
}

test("⑧ 真源码：登记那一发留着重试，等待压得比宽限短", () => {
  const retry = registerRetry(inlineBlock.text);
  assert.ok(retry.attempts >= 2,
    `登记那一发只有 ${retry.attempts} 次尝试——丢了就是丢了（服务会把自己关掉）`);
  assert.ok(retry.delays.length >= 1, "重试的等待没抠到（写法变了？判据要看一眼）");
  for (const ms of retry.delays) {
    assert.ok(ms < 1000, `重试等待 ${ms}ms 太长（宽限只有 1.5 秒，等下去重试也落在窗口外）`);
  }
});

test("⑧ 反例：把重试去掉（退回 `fetch(...).catch(() => {})`）→ 报出", () => {
  const stripped = withInline(inlineBlock.text
    .replace(/\(function attemptRegister\(left\) \{[\s\S]*?\}\)\(1\);/, "fetch(1);"));
  assert.ok(!stripped.includes("attemptRegister"), "注入没落上（重试还在）");
  assert.ok(registerRetry(scriptBlocks(stripped)
    .find((b) => b.src === null && b.text.includes(TAB_REGISTER_ENDPOINT)).text).attempts === 0,
  "反例没把重试拿干净——本用例会假绿");
});

test("⑧ 反例：重试不等待（同步立刻重发）→ 报出", () => {
  // 只改**重试那一处**的写法（内联脚本别处还有 setTimeout 的正当用法——本段不许有顶层
  // 定义，所以"能延时的写法"只有它；拿 `!/setTimeout/` 当注入自检会假红，本机踩过一次）。
  const noWait = withInline(inlineBlock.text
    .replace(/setTimeout\(function \(\) \{ attemptRegister\(left - 1\); \}, \d+\);/g,
      "attemptRegister(left - 1);"));
  assert.ok(noWait !== html, "注入没落上（重试那处没匹配到）");
  const retry = registerRetry(scriptBlocks(noWait)
    .find((b) => b.src === null && b.text.includes(TAB_REGISTER_ENDPOINT)).text);
  assert.deepEqual(retry.delays, [], "同步重发被当成了延时重试——判据的延时锚点失效了");
});

// ---------------------------------------------------------------------------
// 四、bfcache 恢复补登记（工单 bfcache-return-register/01；判据 ⑦）
// 与上面 ①–④ 是**同一件事的另一半**：① 管"新文档要早报到"，这一组管"被浏览器冻结的老文档
// 回来时要再报到一次"。用户按后退看到死页面的现场链路见 `restoreRegisterProblems` 的文件头。
// ---------------------------------------------------------------------------

test("真源码：pageshow 恢复补登记 + 两处 payload 同源 + 广播有人接", () => {
  const problems = restoreRegisterProblems(html, uiJs).map((p) => "  · " + p.why);
  assert.deepEqual(problems, [],
    "bfcache 恢复契约破了（用户导航走后按后退会看到死页面）：\n" + problems.join("\n"));
});

test("⑤ 内联脚本没监听 pageshow → 报出", () => {
  const renamed = withInline(inlineBlock.text.replace(/"pageshow"/, '"pagehide-x"'));
  assert.ok(!renamed.includes('"pageshow"'), "注入没落上（监听还在）");
  const problems = restoreRegisterProblems(renamed, uiJs);
  assert.ok(reports(problems, "没监听 pageshow"), `缺监听没报出：${JSON.stringify(problems)}`);
});

test("⑤ 反例：pageshow 字样只出现在**注释**里 → 照样报出（掩码不许被注释喂绿）", () => {
  const injected = withInline(inlineBlock.text.replace(/"pageshow"/, '"pagehide-x"')
    + '\n  // 这里提一句 pageshow 与 event.persisted 有用吗：注释不算实现\n');
  const problems = restoreRegisterProblems(injected, uiJs);
  assert.ok(reports(problems, "没监听 pageshow"), `注释里的字样把判据喂绿了：${JSON.stringify(problems)}`);
});

test("⑥ 监听里不判 persisted（每次加载都补登记）→ 报出", () => {
  const injected = withInline(inlineBlock.text.replace("!event.persisted", "false"));
  assert.ok(injected.includes("if (false)"), "注入没落上（persisted 判断还在？）");
  const problems = restoreRegisterProblems(injected, uiJs);
  assert.ok(reports(problems, "没判 event.persisted"),
    `不判 persisted 没报出：${JSON.stringify(problems)}`);
});

test("⑦ 两处 register payload 漂了（补登记那处多带一个字段）→ 报出", () => {
  const anchor = "epoch: performance.timeOrigin";
  const at = inlineBlock.text.lastIndexOf(anchor);
  assert.notEqual(at, inlineBlock.text.indexOf(anchor),
    "注入锚点失效：块内只有一处 epoch payload（补登记那处没了？）");
  const drifted = inlineBlock.text.slice(0, at + anchor.length) + ", probeDrift: 1"
    + inlineBlock.text.slice(at + anchor.length);
  const problems = restoreRegisterProblems(withInline(drifted), uiJs);
  assert.ok(reports(problems, "payload 不一致"), `两处 payload 漂了没报出：${JSON.stringify(problems)}`);
});

test("⑦ 失败时没广播（把 event 名改掉）→ 报出", () => {
  // 自我检查只看**块内文本**：整份 HTML 里 `"service-stopped"` 还出现在可见态那个
  // `<div id="service-stopped">` 上（拿整份 HTML 当自检面会假红）。
  const text = inlineBlock.text.replaceAll(`"${SERVICE_STOPPED_EVENT}"`, '"probe-silent"');
  assert.ok(!text.includes(`"${SERVICE_STOPPED_EVENT}"`), "注入没落上（事件名还在）");
  const problems = restoreRegisterProblems(withInline(text), uiJs);
  assert.ok(reports(problems, `没有广播 ${SERVICE_STOPPED_EVENT}`),
    `缺广播没报出：${JSON.stringify(problems)}`);
});

test("⑦ 反例：UI 侧事件名与广播不一致 → 报出（两侧同源）", () => {
  const renamedUi = uiJs.replaceAll(`"${SERVICE_STOPPED_EVENT}"`, '"probe-silent"');
  assert.ok(renamedUi !== uiJs, "注入没落上（UI 侧事件名没改到）");
  const problems = restoreRegisterProblems(html, renamedUi);
  assert.ok(reports(problems, "广播没人接"), `两侧事件名分叉没报出：${JSON.stringify(problems)}`);
});

test("② 补登记那处整个没了（监听器连着第二处调用一起删掉）→ 报出", () => {
  const at = inlineBlock.text.indexOf('window.addEventListener("pageshow"');
  assert.ok(at > 0, "注入锚点失效：块内找不到 pageshow 监听（判据 ⑦① 会先报出）");
  const problems = restoreRegisterProblems(withInline(inlineBlock.text.slice(0, at)), uiJs);
  assert.ok(reports(problems, "只有 1 处"), `补登记整块没了没报出：${JSON.stringify(problems)}`);
});

test("② 第二处 register 落在监听体**之外**（监听器改成空的）→ 报出", () => {
  // 合成注入：把真源码里那个监听器的"壳"去掉（内层 fetch 变成块内普通语句），再在末尾补一个
  // 空的 pageshow 监听 —— 于是有监听、也判 persisted、两处 payload 仍同源，**只有"补登记在不在
  // 监听体内"这一条**该红。注入本身不是合法 JS（判据是文本的），这正是它只该打一条的原因。
  const stripped = inlineBlock.text
    .replace('window.addEventListener("pageshow", function (event) {', "")
    .replace("      if (!event.persisted) return;", "");
  const injected = withInline(stripped
    + '\n  window.addEventListener("pageshow", function (e) {\n    if (!e.persisted) return;\n  });\n');
  assert.ok(injected.includes("if (!e.persisted) return;"), "注入没落上（补的那个空监听器不在）");
  const problems = restoreRegisterProblems(injected, uiJs);
  assert.ok(reports(problems, "不在 pageshow 监听体内"),
    `补登记挪出监听体没报出：${JSON.stringify(problems)}`);
});

test("⑦ 反例：广播挪到监听体之外（块内别处）→ 报出", () => {
  const text = inlineBlock.text.replace(
    "          window.dispatchEvent(new CustomEvent(\"service-stopped\"));",
    "          /* 广播挪走了 */");
  assert.ok(text !== inlineBlock.text, "注入没落上（catch 里那句广播没改到）");
  const injected = withInline(text
    + `\n  window.addEventListener("pageshow", function () {});\n`
    + `  if (false) window.dispatchEvent(new CustomEvent("${SERVICE_STOPPED_EVENT}"));\n`);
  const problems = restoreRegisterProblems(injected, uiJs);
  assert.ok(reports(problems, "不在 pageshow 监听体内"),
    `挪走的广播没报出：${JSON.stringify(problems)}`);
});

test("⑤ 失败只广播、没有可回读的落地态 → 报出", () => {
  // 锚点用**不含缩进与换行**的子串（本机 `core.autocrlf=true` 检出时块内是 CRLF，
  // 带 `\n` 的锚点会静默不落上 —— 第一版就是这么假红的）。
  const text = inlineBlock.text.replace(
    'document.documentElement.dataset.serviceStopped = "1";', "void 0;");
  assert.ok(!text.includes("documentElement.dataset.serviceStopped"), "注入没落上（落地态还在）");
  const problems = restoreRegisterProblems(withInline(text), uiJs);
  assert.ok(reports(problems, "没留可回读的落地态"),
    `缺落地态没报出：${JSON.stringify(problems)}`);
});

test("⑤ 反例：UI 侧回读的落地态键与内联脚本写的不是同一个 → 报出", () => {
  // `replaceAll`：注释里也提了一次同名键，只替第一处会改在注释上、代码那处没动（假红）。
  const renamedUi = uiJs.replaceAll("dataset.serviceStopped", "dataset.probeOtherKey");
  assert.ok(renamedUi !== uiJs, "注入没落上（UI 侧的键没改到）");
  const problems = restoreRegisterProblems(html, renamedUi);
  assert.ok(reports(problems, "落地态两侧不同源"),
    `落地态键分叉没报出：${JSON.stringify(problems)}`);
});
