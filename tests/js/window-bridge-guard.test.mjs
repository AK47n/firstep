// window-bridge-guard.test.mjs — 「模块正文不许靠 window 全局桥解析名字」不变量
// （工单 hwcheck-hygiene/01；判据本体单源在 `tests/js/boot-contract.mjs` 判据 ⑧）。
//
// ## 为什么单开一个守卫文件
//
// 现有守卫管的是**反方向**：`import-usage-guard.test.mjs` 说"import 了必须用"；这一条说
// "**用了必须有 import**"。两个方向各自成守卫文件，判据本体同在 `boot-contract.mjs`——
// 照 `static-import-guard` / `export-surface-guard` / `ui-cycle` 的先例（一个文件一个职责，
// 判据单源，调用点各自成闸门）。
//
// ## 这条不变量要挡的是什么
//
// `Object.assign(window, { … })` 是全仓 **611 个名字**的老式全局出口（**66 个模块**在发布；
// 现算口径，量具 `.scratch/hwcheck-hygiene/probe-01-bridge-count.mjs`）。**桥本身不删**
// （浏览器探针与 `index.html` 内联脚本还在用），禁的是**模块正文依赖它**：靠桥解析的名字
// 运行态真的能跑（真浏览器用例照样绿），但在导出面判据 D 眼里它是**死导出**
// ——`ui/hwcheck.js` 调 `hwcheckErrorHTML` 就是这个形态（工单 `hwcheck-hardening/07` 的产物）。
//
// 口径、排除面与已知边界写在 `boot-contract.mjs` 判据 ⑧ 的段头，改判据前先读那一段。
//
// ## 红证
//
// `.scratch/hwcheck-hygiene/probe-01-red.py`（撤掉 `ui/hwcheck.js` 那条 import → 本文件必须红；
// 复原后 sha256 逐字节相同），读数 `probe-01-red.txt`。
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import {
  readJsModules, bridgeDependencyProblems, windowBridgeNames, callPositionNames,
} from "./boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const MODULES = readJsModules(STATIC);

const patch = (entries, key, fn) =>
  entries.map((e) => (e.key === key ? { ...e, text: fn(e.text) } : e));
const KEY = "ui/hwcheck.js";                    // 注入锚点：一个真在判据面里的模块
const BRIDGE_KEY = "fx/core.js";                // 桥注入锚点：一个真在发布桥条目的模块
const PROBE_NAME = "probeBridgeOnlyFn";         // 只存在于桥上的名字（源码里没有）

test("取数面体检：判据面与桥清单都抽得到（那种绿比红更坏）", () => {
  const face = MODULES.filter((m) => /^(fx|ui)\//.test(m.key));
  assert.ok(face.length >= 100, `判据面只抽到 ${face.length} 个 fx/ui 模块（目录结构变了？）`);
  const names = new Set();
  for (const m of MODULES) for (const n of windowBridgeNames(m.text)) names.add(n);
  assert.ok(names.size >= 400,
    `window 桥只抽到 ${names.size} 个名字（下限 400）——判据会真空绿（发布清单解析器失效？）`);
  // 桥清单**从源码现算**：换个模块文本，清单跟着变
  const one = windowBridgeNames('Object.assign(window, { alpha, beta: gamma });');
  assert.deepEqual([...one].sort(), ["alpha", "beta"]);
  assert.deepEqual([...windowBridgeNames("// Object.assign(window, { alpha });")], [],
    "注释里举例的 Object.assign(window, …) 被当成真发布 —— 清单没走掩码");
});

test("判据 ⑧：模块正文的调用位自由标识符不命中 window 桥（违规 = 0）", () => {
  const bad = bridgeDependencyProblems(MODULES)
    .map((v) => `  ${v.key}:${v.sites.join(",")} 用了 ${v.name}（只挂在 window 上，由 ${v.from} 发布）`);
  assert.deepEqual(bad, [],
    "这些调用位靠 `Object.assign(window, { … })` 那条全局桥侥幸解析 —— 运行态能跑，\n"
    + "但在导出面判据 D 眼里它们不是消费者（= 那条导出仍是死导出）。\n"
    + "改法：把名字并进该文件的 import 段（口径见 tests/js/boot-contract.mjs 判据 ⑧）：\n"
    + bad.join("\n"));
});

test("判据 ⑧ 正向对照：注入一处「只靠桥解析」的调用，必须报出", () => {
  // 两侧都注入：桥那一侧**新增**一个名字（证明清单是现算的），调用侧不 import 直接调。
  let patched = patch(MODULES, BRIDGE_KEY, (t) => t.replace(
    /Object\.assign\(window,\s*\{/, `Object.assign(window, {\n    ${PROBE_NAME},`));
  patched = patch(patched, KEY, (t) => `${t}\n${PROBE_NAME}(1);\n`);
  // 注入自检：键写错会让这条自检**静默空转**（照 export-surface-guard 的先例）
  assert.ok(patched.some((e) => e.key === BRIDGE_KEY && e.text.includes(PROBE_NAME)),
    `桥注入没落上（锚点键 \`${BRIDGE_KEY}\` 没有 Object.assign(window, { …) 形态？）`);
  assert.ok(patched.some((e) => e.key === KEY && e.text.includes(`${PROBE_NAME}(1)`)),
    `调用注入没落上（锚点键 \`${KEY}\` 不存在？）`);
  const hit = bridgeDependencyProblems(patched)
    .some((v) => v.key === KEY && v.name === PROBE_NAME && v.from === BRIDGE_KEY);
  assert.ok(hit, "只靠桥解析的调用没被报出 —— 判据静默失效（清单没现算？调用位没扫到？）");
});

test("判据 ⑧ 掩码自检：名字只出现在注释 / 字符串里 → 不算依赖", () => {
  let patched = patch(MODULES, BRIDGE_KEY, (t) => t.replace(
    /Object\.assign\(window,\s*\{/, `Object.assign(window, {\n    ${PROBE_NAME},`));
  patched = patch(patched, KEY, (t) => `${t}\n// ${PROBE_NAME}(1) 未 import 的墓碑注释\nconst _probeNote = "${PROBE_NAME}(1)";\n`);
  // 两侧注入都要自检：只断言注释那一侧，字符串那一侧落空时这条自检会**静默空转**仍绿
  assert.ok(patched.some((e) => e.key === KEY && e.text.includes(`// ${PROBE_NAME}(1)`)),
    `注释注入没落上（锚点键 \`${KEY}\` 不存在？）—— 这条自检会静默空转`);
  assert.ok(patched.some((e) => e.key === KEY && e.text.includes(`"${PROBE_NAME}(1)"`)),
    "字符串注入没落上 —— 字符串那一侧的掩码自检会静默空转");
  const hit = bridgeDependencyProblems(patched).some((v) => v.key === KEY && v.name === PROBE_NAME);
  assert.ok(!hit, "名字只出现在注释 / 字符串里却被判成桥依赖 —— 被注释喂红了（掩码口径失效）");
});

test("判据 ⑧ 边界：import 过的 / 本模块声明的 / 属性访问 / 方法定义都不算", () => {
  const bridged = [{ key: "fx/other.js", text: "Object.assign(window, { probeA, probeB, probeC, probeD });" }];
  const cases = [
    ['import { probeA } from "/js/fx/other.js";\nprobeA(1);\n', []],
    ["function probeB() {}\nprobeB(1);\n", []],
    ["const o = {};\no.probeC(1);\n", []],
    ["const o = { probeC(x) { return x; } };\n", []],
    ["probeC(1);\n", ["probeC"]],
    ["probeD?.();\n", ["probeD"]],                         // 可选调用也是调用位
  ];
  for (const [body, expect] of cases) {
    const hits = bridgeDependencyProblems([...bridged, { key: "ui/probe.js", text: body }])
      .map((v) => v.name);
    assert.deepEqual(hits, expect, `边界用例判错（语料：${JSON.stringify(body)}）`);
  }
  // 调用位扫描本身的分寸：关键字 / 函数声明 / 方法定义 / 属性访问都不是"自由标识符被调用"
  assert.deepEqual(callPositionNames("if (x) {}\nfunction f(a) {}\nconst o = { m() {} };\n"), []);
  assert.deepEqual(callPositionNames("foo(1);\n").map((c) => c.name), ["foo"]);
  assert.deepEqual(callPositionNames("const o = {};\no.bar(1);\n"), [],
    "`o.bar(` 是属性访问，不是自由标识符 —— 判进来说明边界正则失效");
  assert.deepEqual(callPositionNames("const s = `x${bar(1)}`;\n").map((c) => c.name), ["bar"],
    "模板串表达式里的调用**算**代码（maskNonCode 口径）—— 漏掉它就是一个洞");
});
