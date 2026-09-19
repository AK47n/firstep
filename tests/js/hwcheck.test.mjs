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
  hwcheckHintHTML, hwcheckErrorHTML, hwcheckGenerateErrorHTML, hwcheckEmptyHTML,
  hwcheckPanelHTML,
  hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
  HWCHECK_CHANNEL_KEYS,
  hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
  hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
  hwcheckProjectState, hwcheckChannelText, hwcheckProjectInfoHTML,
  hwcheckToolchainNote, hwcheckChannelNoteHTML, hwcheckActionsHTML,
  hwcheckProjectPanelHTML,
  hwcheckRecentHTML, hwcheckRecentEmptyHTML, hwcheckProjectEmptyHTML,
  HWCHECK_PARENT_KEY, HWCHECK_LAST_DIR_KEY,
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

// ---------------------------------------------------------------------------
// ③ 工单 02：生成请求 / 上板清单 / 最近几次检测（纯函数）
// ---------------------------------------------------------------------------

const PROJECT_PAYLOAD = {
  output_dir: "C:/out/hwcheck-stm32-20260920-153012",
  platform: "stm32",
  debug_uart: true,
  oled: false,
  main_c: "int main(void){}\n",
  output_hint: "输出通道：只有调试串口（115200）。",
  checklist: [
    { id: "heartbeat", expect: "灯在闪", check: "先按复位" },
    { id: "serial", expect: "串口出那一行", check: "TX/RX 交叉接" },
  ],
  modules: ["led", "delay", "debug_uart", "config"],
  build_hint: "",
};

test("hwcheckGeneratePayload：带输出父目录（去空白），空 = 交后端按桌面处理", () => {
  const payload = hwcheckGeneratePayload({
    platform: "stm32", debug_uart: true, oled: false, parentDir: "  C:/out  ", junk: 1,
  });
  assert.deepEqual(payload, {
    platform: "stm32", debug_uart: true, oled: false, parent_dir: "C:/out",
  });
  assert.equal(hwcheckGeneratePayload({ platform: "stm32" }).parent_dir, "");
});

test("hwcheckChecklistKey：勾选态按检测工程目录分开（换工程 = 换一套勾选）", () => {
  const a = hwcheckChecklistKey("C:/out/hwcheck-stm32-1");
  const b = hwcheckChecklistKey("C:/out/hwcheck-stm32-2");
  assert.notEqual(a, b);
  assert.ok(a.startsWith("firstep.hwcheck."), "键名沿既有 firstep.* 命名域");
  assert.equal(a, hwcheckChecklistKey("C:/out/hwcheck-stm32-1"));
});

test("hwcheckCheckedIds：坏值一律当「一条都没勾」（本地备忘坏了不许炸页面）", () => {
  assert.deepEqual(hwcheckCheckedIds(null), []);
  assert.deepEqual(hwcheckCheckedIds(""), []);
  assert.deepEqual(hwcheckCheckedIds("{不是 JSON"), []);
  assert.deepEqual(hwcheckCheckedIds('{"a":1}'), [], "非数组不认");
  assert.deepEqual(hwcheckCheckedIds('["flash",3,null,"reset"]'), ["flash", "reset"]);
});

test("hwcheckChecklistToggle：勾上 / 取消勾 → 新的序列化串（幂等，不重复）", () => {
  const once = hwcheckChecklistToggle("[]", "flash", true);
  assert.deepEqual(hwcheckCheckedIds(once), ["flash"]);
  const twice = hwcheckChecklistToggle(once, "flash", true);
  assert.deepEqual(hwcheckCheckedIds(twice), ["flash"], "重复勾不许存两条");
  const off = hwcheckChecklistToggle(twice, "flash", false);
  assert.deepEqual(hwcheckCheckedIds(off), []);
  assert.deepEqual(
    hwcheckCheckedIds(hwcheckChecklistToggle('["a"]', "b", true)), ["a", "b"]);
});

test("hwcheckChecklistHTML：逐项一个勾选框 + 「应看到 / 不对先查」两行 + 转义", () => {
  const html = hwcheckChecklistHTML(
    [{ id: "flash", expect: "看到 <OK>", check: "查 A & B" }], ["flash"]);
  assert.ok(html.includes('data-hwcheck-check="flash"'));
  assert.ok(html.includes("checked"), "已勾的项要回显勾选态");
  assert.ok(html.includes("hwcheck-check done"));
  assert.ok(html.includes("&lt;OK&gt;"), "文案必须转义");
  assert.ok(html.includes("A &amp; B"));
  assert.ok(html.includes("应看到：") && html.includes("不对先查："));
  assert.equal(hwcheckChecklistHTML([], []), "", "空清单 = 空串（调用方放占位）");
  assert.equal(hwcheckChecklistHTML(null, null), "");
});

test("hwcheckChecklistProgressHTML：已确认 n / 总数（全勾时给一句收尾）", () => {
  const items = [{ id: "a" }, { id: "b" }];
  assert.ok(hwcheckChecklistProgressHTML(items, []).includes("已确认 0 / 2 条"));
  const all = hwcheckChecklistProgressHTML(items, ["a", "b"]);
  assert.ok(all.includes("已确认 2 / 2 条"));
  assert.equal(hwcheckChecklistProgressHTML([], []), "");
});

test("hwcheckProjectState：后端载荷 → project（字段只在 fx 对一次）", () => {
  const next = hwcheckProjectState({ platform: "stm32" }, PROJECT_PAYLOAD);
  assert.equal(next.project.outputDir, PROJECT_PAYLOAD.output_dir);
  assert.equal(next.project.platform, "stm32");
  assert.equal(next.project.debugUart, true);
  assert.equal(next.project.oled, false);
  assert.equal(next.project.mainC, PROJECT_PAYLOAD.main_c);
  assert.deepEqual(next.project.checklist, PROJECT_PAYLOAD.checklist);
  assert.deepEqual(next.project.modules, PROJECT_PAYLOAD.modules);
  // 空载荷 / 半截载荷不炸（防御）
  const empty = hwcheckProjectState({}, null);
  assert.deepEqual(empty.project.checklist, []);
  assert.equal(empty.project.outputDir, "");
});

test("hwcheckChannelText：四种通道形态说实话", () => {
  assert.equal(hwcheckChannelText({ debugUart: true, oled: true }), "调试串口 + OLED");
  assert.equal(hwcheckChannelText({ debugUart: true, oled: false }), "只有调试串口");
  assert.equal(hwcheckChannelText({ debugUart: false, oled: true }), "只有 OLED");
  assert.ok(hwcheckChannelText({}).includes("灯闪"));
});

test("hwcheckProjectInfoHTML：工程路径 / 通道 / 模块 + 通道说明，文案转义", () => {
  const html = hwcheckProjectInfoHTML(
    { ...hwcheckProjectState({}, PROJECT_PAYLOAD).project, outputHint: "串口 <115200>" },
    "STM32F103C8T6 最小系统板 · Keil5");
  assert.ok(html.includes('class="slug"'), "路径走 .slug 观感");
  assert.ok(html.includes("hwcheck-stm32-20260920-153012"));
  assert.ok(html.includes("STM32F103C8T6"));
  assert.ok(html.includes("只有调试串口"));
  assert.ok(html.includes("debug_uart"));
  assert.ok(html.includes("&lt;115200&gt;"));
  assert.equal(hwcheckProjectInfoHTML(null), "");
});

test("hwcheckToolchainNote：缺工具链要大声明说「未经验证」；齐了不吭声", () => {
  assert.equal(hwcheckToolchainNote("stm32", true, "STM32"), "");
  const note = hwcheckToolchainNote("stm32", false, "STM32F103C8T6");
  assert.ok(note.includes("未经验证"), "不许让用户以为生成完就验证过了");
  assert.ok(note.includes("Keil UV4"), "说清缺的是哪一套工具链");
  assert.ok(hwcheckToolchainNote("mspm0", false, "地猛星").includes("gmake"));
  assert.ok(hwcheckToolchainNote("未知平台", false, "").includes("编译工具链"),
    "平台词表外也要有话说（不拼出 undefined）");
});

test("hwcheckChannelNoteHTML：mspm0 双通道在**生成前**就给出路（评审整改）", () => {
  // spec 用户故事 4「一个器件都不选也能生成」在 mspm0 默认态不成立（两路默认脚重叠），
  // 而检测页原本没有任何引导——这条钉住"生成前就告诉用户怎么办"。
  const note = hwcheckChannelNoteHTML("mspm0", true, true);
  assert.ok(note.includes("hwcheck-warn"), "要显眼，不是一句灰字");
  assert.ok(note.includes("引脚冲突"), "说清会出什么事");
  assert.ok(/只勾一个|取消勾选/.test(note), "给出路：先只勾一个通道");
  assert.equal(hwcheckChannelNoteHTML("stm32", true, true), "", "stm32 默认不撞脚");
  assert.equal(hwcheckChannelNoteHTML("mspm0", true, false), "", "只勾一个就不提示");
  assert.equal(hwcheckChannelNoteHTML("mspm0", false, true), "");
  assert.equal(hwcheckChannelNoteHTML("mspm0", false, false), "");
});

test("hwcheckActionsHTML：三个动作带工程目录；编译不可用时按钮置灰", () => {
  const dir = "C:/out/hwcheck-stm32-1";
  const ready = hwcheckActionsHTML(dir, { compileReady: true });
  assert.ok(ready.includes(`data-hwcheck-compile="${dir}"`));
  assert.ok(ready.includes(`data-hwcheck-flash="${dir}"`));
  assert.ok(ready.includes(`data-hwcheck-open="${dir}"`));
  assert.ok(!ready.includes("disabled"));
  assert.ok(ready.includes('id="hwcheck-compile-status"'));
  assert.ok(ready.includes('id="hwcheck-compile-errors"'));
  assert.ok(ready.includes('id="hwcheck-flash-result"'));
  const degraded = hwcheckActionsHTML(dir, { compileReady: false });
  assert.ok(degraded.includes("disabled"), "缺工具链时编译按钮置灰（不假装能编）");
  assert.equal(hwcheckActionsHTML(""), "");
});

test("hwcheckProjectPanelHTML：没有工程 = 空串（调用方放占位）", () => {
  assert.equal(hwcheckProjectPanelHTML(null), "");
  const html = hwcheckProjectPanelHTML(
    hwcheckProjectState({}, PROJECT_PAYLOAD).project, { compileReady: true });
  assert.ok(html.includes("data-hwcheck-compile"));
});

test("hwcheckRecentHTML：点一行带目录；正在看的那个高亮", () => {
  const items = [
    { name: "hwcheck-stm32-20260920-153012", dir: "C:/out/a",
      platform: "stm32", created_at: "2026-09-20 15:30:12" },
    { name: "hwcheck-mspm0-20260920-101010", dir: "C:/out/b",
      platform: "mspm0", created_at: "2026-09-20 10:10:10" },
  ];
  const html = hwcheckRecentHTML(items, "C:/out/a");
  assert.ok(html.includes('data-hwcheck-open-project="C:/out/a"'));
  assert.ok(html.includes("2026-09-20 15:30:12"));
  assert.ok(html.includes("正在看"), "当前工程要标出来");
  assert.equal((html.match(/正在看/g) || []).length, 1, "只标当前那一条");
  assert.equal(hwcheckRecentHTML([], "C:/out/a"), "");
  assert.equal(hwcheckRecentHTML(null), "");
});

test("两个占位都是中文、非空（还没生成 / 还没检测过都不是错误）", () => {
  assert.ok(hwcheckProjectEmptyHTML().includes("还没有检测工程"));
  assert.ok(hwcheckRecentEmptyHTML().includes("还没有检测工程"));
  assert.ok(HWCHECK_PARENT_KEY.startsWith("firstep.hwcheck."));
  assert.ok(HWCHECK_LAST_DIR_KEY.startsWith("firstep.hwcheck."));
});

test("生成失败的提示与预览失败分开写（原因常是引擎如实拒绝，别引到错的地方查）", () => {
  const preview = hwcheckErrorHTML("平台 <x> 不存在");
  const generate = hwcheckGenerateErrorHTML("引脚冲突：PA22");
  assert.ok(preview.includes("预览失败"));
  assert.ok(generate.includes("检测工程") && generate.includes("没有生成成功"));
  assert.ok(generate.includes("PA22"));
  assert.ok(hwcheckGenerateErrorHTML("冲突 <a>").includes("&lt;a&gt;"), "必须转义");
});

// ---------------------------------------------------------------------------
// ④ 工单 02：接线守卫（控件齐备 / 复用既有执行体 / 不双源拼壳）
// ---------------------------------------------------------------------------

test("新控件齐备：父目录输入 / 选择文件夹 / 生成按钮 / 工程 + 清单 + 最近容器", () => {
  for (const id of ["hwcheck-parent", "btn-hwcheck-pick-parent", "btn-hwcheck-generate",
    "hwcheck-project", "hwcheck-checklist", "hwcheck-recent", "hwcheck-channel-note"]) {
    assert.ok(html.includes('id="' + id + '"'), "缺少控件 #" + id);
  }
});

test("ui 复用既有编译与烧录执行体（不写第三个 SSE 编译消费器）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes('from "/js/ui/fix-center-core.js"'),
    "编译应复用既有执行体 runCompileOnceCore");
  assert.ok(ui.includes("runCompileOnceCore("), "应真的调用它");
  assert.ok(ui.includes('from "/js/ui/flash.js"'),
    "烧录应复用既有共享执行体 flashRunShared");
  assert.ok(ui.includes("flashRunShared("), "应真的调用它");
  assert.ok(!/fetch\(\s*"\/api\/compile"/.test(ui),
    "不得自己再写一个 SSE 编译消费器（第三个复制品）");
  assert.ok(!/new EventSource|parseSSE\(/.test(ui), "SSE 解析归既有执行体");
});

test("ui 的清单勾选态走 fx 的键与编解码单源（不手拼 localStorage 键名）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckChecklistKey("), "键名应来自 fx");
  assert.ok(ui.includes("hwcheckChecklistToggle("), "编解码应来自 fx");
  assert.ok(!/firstep\.hwcheck\./.test(ui), "ui 不得手写 firstep.hwcheck.* 键名（双源）");
});

test("ui 不手拼工程面板 / 清单 / 最近的壳（壳的单源在 fx/hwcheck.js）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckProjectPanelHTML("));
  assert.ok(ui.includes("hwcheckChecklistHTML("));
  assert.ok(ui.includes("hwcheckRecentHTML("));
  // 壳体的样式标记不许在 ui 里手写（双源漂移 + 丢 esc，工单 01 评审同款）
  assert.ok(!/class="hwcheck-(check|recent-row|actions|path|warn)/.test(ui),
    "ui 不得手拼这些壳的样式标记（单源在 fx/hwcheck.js）");
  // 带值的 data-* 标记只允许出现在 querySelector 的选择器里（取按钮用）
  const markers = ui.match(/data-hwcheck-(compile|check|open-project|flash)="/g) || [];
  const inSelector = ui.match(/\[data-hwcheck-(compile|check|open-project|flash)="/g) || [];
  assert.equal(markers.length, inSelector.length,
    "带值的 data-* 标记只许出现在选择器里（壳的唯一出处是 fx/hwcheck.js）");
});

