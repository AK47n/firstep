// hwcheck.test.mjs — 硬件检测栏目（工单 module-hwcheck/01）：
// ① fx 纯函数（平台选择状态 / 请求体 / 卡片与提示渲染）；② 三处注册接线
// （静态 import / 启动调用 / 切换时懒加载）——三处缺一，栏目就是「点了没反应」
// 或者「首帧空白」，而这两种坏法在浏览器里都不会报错。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
  hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
  hwcheckHintHTML, hwcheckErrorHTML, hwcheckEmptyHTML, hwcheckPanelHTML,
  hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
  HWCHECK_CHANNEL_KEYS,
} from "../../src/contest_generator/static/js/fx/hwcheck.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

const PLATFORMS = [
  { id: "stm32", name: "STM32F103C8T6 最小系统板 · Keil5", status: "ready" },
  { id: "mspm0", name: "地猛星 MSPM0G3507 · CCS", status: "no-master" },
];

// ---------------------------------------------------------------------------
// ① fx 纯函数
// ---------------------------------------------------------------------------

test("未选过时继承全局当前平台（仅当它可用）", () => {
  assert.equal(hwcheckPlatformState(PLATFORMS, "stm32", "").platform, "stm32");
});

test("继承的平台不可用 → 退到第一个可用平台（不留一个点不动的选择）", () => {
  assert.equal(hwcheckPlatformState(PLATFORMS, "mspm0", "").platform, "stm32");
});

test("本栏目已选过 → 保留自己的选择（不被全局平台改动带走）", () => {
  // 已选 mspm0 且它可用（换成可用清单）→ 保留；全局变成 stm32 也不动
  const both = [{ id: "stm32", status: "ready" }, { id: "mspm0", status: "ready" }];
  assert.equal(hwcheckPlatformState(both, "stm32", "mspm0").platform, "mspm0");
});

test("一个可用平台都没有 → 空选择（页面提示先导入母版，不静默选一个不可用的）", () => {
  const none = [{ id: "stm32", status: "no-master" }];
  assert.equal(hwcheckPlatformState(none, "stm32", "").platform, "");
  assert.equal(hwcheckPlatformState(null, "", "").platform, "");
});

test("hwcheckSelectPlatform：不可用平台不换、可用平台换（返回新对象不改原对象）", () => {
  const state = { platform: "stm32", debug_uart: true, oled: true };
  assert.deepEqual(hwcheckSelectPlatform(PLATFORMS, state, "mspm0"), state);
  assert.equal(hwcheckSelectPlatform(PLATFORMS, state, "nope").platform, "stm32");
  const next = hwcheckSelectPlatform(PLATFORMS, state, "stm32");
  assert.equal(next.platform, "stm32");
  assert.notEqual(next, state, "应返回新对象（纯函数）");
});

test("hwcheckPickState：通道词表内的键才生效（写错键名不静默多存字段）", () => {
  const state = { platform: "stm32", debug_uart: true, oled: true };
  assert.equal(hwcheckPickState(state, "debug_uart", false).debug_uart, false);
  assert.equal(hwcheckPickState(state, "oled", 0).oled, false, "非布尔按真值归一");
  const wrong = hwcheckPickState(state, "uart", false);
  assert.deepEqual(wrong, state, "词表外的键应原样返回");
  assert.deepEqual(HWCHECK_CHANNEL_KEYS, ["debug_uart", "oled"]);
});

test("hwcheckRequestPayload：只带平台与两个通道开关（不带题面 / 已选模块）", () => {
  const payload = hwcheckRequestPayload({
    platform: "stm32", debug_uart: false, oled: true, preview: "x", junk: 1,
  });
  assert.deepEqual(payload, { platform: "stm32", debug_uart: false, oled: true });
});

test("hwcheckCanPreview：没选平台不给点（后端必拒）", () => {
  assert.equal(hwcheckCanPreview({ platform: "stm32" }), true);
  assert.equal(hwcheckCanPreview({ platform: "" }), false);
  assert.equal(hwcheckCanPreview(null), false);
});

test("平台卡：选中态 + 不可用置灰 + 中文 title + 非转义 id", () => {
  const out = hwcheckPlatformCardsHTML(PLATFORMS, "stm32");
  assert.ok(out.includes('data-hwcheck-platform="stm32"'));
  assert.ok(out.includes("platform-card selected"), "选中平台应带 selected");
  assert.ok(/data-hwcheck-platform="mspm0"[^>]*/.test(out));
  assert.ok(out.includes("platform-card disabled"), "未导入母版的平台应置灰");
  assert.ok(out.includes('role="button"'));
  assert.ok(out.includes('aria-pressed="true"'));
  assert.ok(/title="[^"]*母版/.test(out), "不可用平台应说明为什么不可用");
});

test("提示 / 错误 / 占位都做 HTML 转义（后端文案含 < > 也不破页面）", () => {
  assert.ok(hwcheckHintHTML("串口 <115200>").includes("&lt;115200&gt;"));
  assert.ok(hwcheckErrorHTML("平台 <x> 不存在").includes("&lt;x&gt;"));
  assert.ok(hwcheckEmptyHTML("先选 <平台>").includes("&lt;平台&gt;"));
});

test("hwcheckPanelHTML：没产物 = 空串（调用方据此放占位）", () => {
  assert.equal(hwcheckPanelHTML("", ""), "");
  const out = hwcheckPanelHTML("int main(void){}", "只有调试串口");
  assert.ok(out.includes("只有调试串口"));
  assert.ok(out.includes("data-hwcheck-code"), "产物区应带 main.c 容器标记");
});

test("hwcheckCodeTarget：产物区壳的唯一出处（ui 不手拼同一段 HTML）", () => {
  // 极简假容器：只实现 querySelector 的语义（本用例不引入 DOM 依赖）
  const fake = (found) => ({ querySelector: (sel) => (sel === "[data-hwcheck-code]" ? found : null) });
  assert.equal(hwcheckCodeTarget(fake("el")), "el");
  assert.equal(hwcheckCodeTarget(fake(null)), null);
  assert.equal(hwcheckCodeTarget(null), null, "没有容器时不得抛");
});

test("产物区壳在 fx 单源：ui/hwcheck.js 不得手拼 hwcheck-hint / data-hwcheck-code", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckPanelHTML"), "ui 应调用 fx 的 hwcheckPanelHTML");
  assert.ok(ui.includes("hwcheckCodeTarget"), "ui 应经 hwcheckCodeTarget 取容器");
  assert.ok(!/["'`]<div class="hwcheck-hint"/.test(ui),
    "ui 不得手拼 hwcheck-hint 壳（双源漂移 + 丢 esc）");
  assert.ok(!/data-hwcheck-code/.test(ui),
    "ui 不得手写 data-hwcheck-code 标记（壳的单源在 fx/hwcheck.js）");
});

test("hwcheckPreviewState：记下文本与通道说明（重绘不重发请求）", () => {
  const next = hwcheckPreviewState({ platform: "stm32" }, {
    main_c: "int main(void){}", output_hint: "只有 OLED",
  });
  assert.equal(next.preview, "int main(void){}");
  assert.equal(next.outputHint, "只有 OLED");
  assert.equal(hwcheckPreviewState({}, null).preview, "");
});

test("hwcheckPlatformLabel：取展示名，找不到回 id", () => {
  assert.equal(hwcheckPlatformLabel(PLATFORMS, "stm32"), PLATFORMS[0].name);
  assert.equal(hwcheckPlatformLabel(PLATFORMS, "nope"), "nope");
});

// ---------------------------------------------------------------------------
// ② 三处注册接线（静态 import / 启动调用 / 切换时懒加载）
// ---------------------------------------------------------------------------

test("静态 import：index.html 从 /js/ui/hwcheck.js 导入 renderHwcheckPanel + initHwcheck", () => {
  const m = html.match(/import\s*\{([^}]*)\}\s*from\s*"\/js\/ui\/hwcheck\.js"/);
  assert.ok(m, "index.html 应有 ui/hwcheck.js 的静态 import");
  const names = m[1].split(",").map((s) => s.trim()).filter(Boolean);
  assert.ok(names.includes("renderHwcheckPanel"), "应导入 renderHwcheckPanel");
  assert.ok(names.includes("initHwcheck"), "应导入 initHwcheck");
});

test("启动调用：initHwcheck() 在启动区被调一次", () => {
  assert.ok(/^initHwcheck\(\);/m.test(html), "启动区应调用 initHwcheck()");
});

test("切换时懒加载：页签分发器对 hwcheck 调 renderHwcheckPanel()", () => {
  assert.ok(
    html.includes('if (btn.dataset.tab === "hwcheck") renderHwcheckPanel();'),
    "页签分发器应在本栏目激活时重渲染（全局状态到达 / 切回来都要刷新平台卡）",
  );
});

test("本栏目 section 容器与平台 / 通道 / 预览控件齐备", () => {
  assert.ok(html.includes('<section id="tab-hwcheck" class="page">'));
  for (const id of ["hwcheck-platforms", "hwcheck-channels", "hwcheck-output", "btn-hwcheck-preview"]) {
    assert.ok(html.includes('id="' + id + '"'), "缺少控件 #" + id);
  }
  // 通道勾选走容器级委托 → 两个 checkbox 必须在委托容器内
  const box = html.match(/<div id="hwcheck-channels"[\s\S]*?<\/div>/);
  assert.ok(box, "应有通道勾选容器");
  for (const key of HWCHECK_CHANNEL_KEYS) {
    assert.ok(box[0].includes('data-hwcheck-channel="' + key + '"'),
      "通道容器内应有 " + key + " 勾选框");
  }
});

test("纯件留在 fx：ui/hwcheck.js 不得重复定义 fx 里的函数（防双源漂移）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  for (const name of ["hwcheckPlatformState", "hwcheckPlatformCardsHTML", "hwcheckRequestPayload"]) {
    assert.ok(!new RegExp("function\\s+" + name + "\\s*\\(").test(ui),
      "ui/hwcheck.js 不应重新定义 " + name + "（双源漂移）");
  }
  assert.ok(ui.includes('from "/js/fx/hwcheck.js"'), "ui/hwcheck.js 应从 fx/hwcheck.js 导入纯件");
});

test("单向 import：ui → fx（fx/hwcheck.js 不得反向 import ui 或 app）", () => {
  const fx = readFileSync(
    new URL("../../src/contest_generator/static/js/fx/hwcheck.js", import.meta.url), "utf8");
  assert.ok(!/from\s+"\/js\/ui\//.test(fx), "fx 不得 import ui（单向依赖）");
  assert.ok(!/from\s+"\/js\/app\.js"/.test(fx), "fx 不得 import app（DOM/状态层）");
  assert.ok(!/\bdocument\./.test(fx), "fx 不得碰 DOM");
  assert.ok(!/\bfetch\(/.test(fx), "fx 不得发请求");
});
