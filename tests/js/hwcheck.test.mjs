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
  hwcheckDevicePick, hwcheckDeviceSlugs, hwcheckDevicePool, hwcheckDeviceKit,
  hwcheckDeviceChipsHTML, hwcheckDeviceEmptyHTML, hwcheckMissingDevicesHTML,
  hwcheckDeviceGroupNoticeHTML,
  hwcheckWiringErrorHTML, hwcheckWiringTableHTML, hwcheckPinGroupsHTML,
  hwcheckBoardSharesHTML, hwcheckOrderHTML, hwcheckOrderDesc, hwcheckBoardState,
  hwcheckPinFixHTML,
  hwcheckSectionsState, hwcheckSectionsHTML, hwcheckUnspecializedHTML,
  hwcheckSectionPlanText, hwcheckSectionNoteHTML,
  hwcheckConsoleState, hwcheckConsoleHTML,
  hwcheckSymptomText, hwcheckCanTriage, hwcheckTriagePayload,
  hwcheckChecklistPayload, hwcheckAdviceState, hwcheckRecordState,
  hwcheckChecklistState, hwcheckTriageErrorHTML, hwcheckAdviceHTML,
  hwcheckAdviceEmptyHTML,
} from "../../src/contest_generator/static/js/fx/hwcheck.js";
// 单平台件的「需切换平台」标记落在既有网格渲染上（工单 09 的行为判据要真跑它）
import { moduleGridHTML } from "../../src/contest_generator/static/js/fx/module.js";

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

test("hwcheckRequestPayload：只带平台 / 两个通道 / 器件（不带题面 / 已选模块）", () => {
  const payload = hwcheckRequestPayload({
    platform: "stm32", debug_uart: false, oled: true, preview: "x", junk: 1,
  });
  assert.deepEqual(payload, {
    platform: "stm32", debug_uart: false, oled: true, devices: [],
  });
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
    platform: "stm32", debug_uart: true, oled: false, devices: [], parent_dir: "C:/out",
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

test("hwcheckChannelNoteHTML：mspm0 双通道说清「会自动移开」（工单 pin-conflict-exit）", () => {
  // spec 用户故事 4「一个器件都不选也能生成」在 mspm0 默认态本来不成立（两路默认脚
  // 重叠）。工单 hwcheck-pin-conflict-exit/01 起**检测页自己在生成前解开**，所以这句
  // 话不能再教「先只勾一个通道」——那是把母版布局的账算到学生头上。
  const note = hwcheckChannelNoteHTML("mspm0", true, true);
  assert.ok(note.includes("hwcheck-warn"), "要显眼，不是一句灰字");
  assert.ok(note.includes("重叠"), "说清会出什么事");
  assert.ok(note.includes("自动"), "出路：生成前自动移开，不用学生自己改");
  assert.ok(!/只勾一个/.test(note), "不再教「先只勾一个通道」（那是指向赛题页的旧出路）");
  assert.equal(hwcheckChannelNoteHTML("stm32", true, true), "", "stm32 默认不撞脚");
  assert.equal(hwcheckChannelNoteHTML("mspm0", true, false), "", "只勾一个就不提示");
  assert.equal(hwcheckChannelNoteHTML("mspm0", false, true), "");
  assert.equal(hwcheckChannelNoteHTML("mspm0", false, false), "");
});

test("hwcheckPinFixHTML：自动移开的脚逐根如实打出（接线表已是新脚）", () => {
  const html = hwcheckPinFixHTML([
    "oled.OLED_SPI_RES → PA0（原 PA22 与 debug_uart.DEBUG_UART_RX 冲突，已自动移开）",
  ]);
  assert.ok(html.includes("hwcheck-warn"), "要显眼");
  assert.ok(html.includes("自动移开"), "说清发生了什么");
  assert.ok(html.includes("PA0") && html.includes("PA22"), "原脚与新脚都在");
  assert.ok(html.includes("hwcheck-pin-fix"), "一根线一行");
  assert.ok(html.includes("不按原厂默认脚"), "点明照新脚接线");
  assert.equal(hwcheckPinFixHTML([]), "", "一根都没动 = 不渲染（不制造错觉）");
  assert.equal(hwcheckPinFixHTML(null), "");
  assert.equal(hwcheckPinFixHTML(["", null]), "");
  assert.ok(hwcheckPinFixHTML(["<x> → PA0"]).includes("&lt;x&gt;"), "转义");
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

// ---------------------------------------------------------------------------
// ⑤ 工单 03：器件选择 + 接线表 + 默认脚冲突 + 建议顺序（fx 纯函数）
// ---------------------------------------------------------------------------

const MODULES = [
  { slug: "led", description: "板载 LED", kind: "device", requires_identity: true,
    platforms: { mspm0: { pins: [{ id: "LED", default: "PA15" }], kit: "板载" } } },
  { slug: "ml_mpu6050", description: "MPU6050 六轴", kind: "device",
    requires_identity: true,
    platforms: { mspm0: { pins: [], kit: "MPU6050" } } },
  { slug: "delay", description: "软件延时", kind: "internal", requires_identity: false,
    platforms: { mspm0: {} } },
  { slug: "filter", description: "滤波切片", kind: "protocol", requires_identity: false,
    platforms: { mspm0: {} } },
];

test("hwcheckDevicePick：加 / 去一件器件，保序去重，幂等，返回新对象", () => {
  const state = { platform: "mspm0", devices: [] };
  const one = hwcheckDevicePick(state, "ml_mpu6050", true);
  assert.deepEqual(one.devices, ["ml_mpu6050"]);
  const two = hwcheckDevicePick(one, "led", true);
  assert.deepEqual(two.devices, ["ml_mpu6050", "led"], "后加的排在后面");
  assert.equal(hwcheckDevicePick(two, "ml_mpu6050", true), two,
    "已经选中的再点一次 = no-op（不许把它挪到末尾，那会顺带改顺序分区）");
  assert.equal(hwcheckDevicePick(two, "sr04", false), two, "没选过的取消也是 no-op");
  assert.deepEqual(hwcheckDevicePick(two, "led", false).devices, ["ml_mpu6050"]);
  assert.notEqual(one, state, "应返回新对象（纯函数）");
  assert.equal(hwcheckDevicePick(state, "", true), state, "空 slug 不生效");
  assert.deepEqual(hwcheckDevicePick({ platform: "mspm0" }, "led", true).devices, ["led"]);
});

test("两个请求体都带器件数组（去重保序；空 = 一件都没选）", () => {
  const state = { platform: "mspm0", debug_uart: true, oled: false,
                  devices: ["ml_mpu6050", "ml_mpu6050", "led"], parentDir: " C:/out " };
  assert.deepEqual(hwcheckRequestPayload(state).devices, ["ml_mpu6050", "led"]);
  assert.deepEqual(hwcheckGeneratePayload(state).devices, ["ml_mpu6050", "led"]);
  assert.equal(hwcheckGeneratePayload(state).parent_dir, "C:/out");
  assert.deepEqual(hwcheckRequestPayload({ platform: "stm32" }).devices, []);
  assert.deepEqual(hwcheckDeviceSlugs({ devices: [null, "", "led", "led"] }), ["led"]);
});

test("hwcheckDevicePool：挑选面 = 模块库全量（不按 kind 过滤——adc 属 internal，必须可达）", () => {
  const pool = hwcheckDevicePool(MODULES).map((m) => m.slug);
  assert.deepEqual(pool, ["led", "ml_mpu6050", "delay", "filter"],
    "内部件也要能选（spec 的 v1 专精清单里 adc 就是 internal）");
  assert.deepEqual(hwcheckDevicePool(null), []);
  assert.deepEqual(hwcheckDevicePool([null, { slug: "" }, { slug: "ok" }]).map((m) => m.slug),
    ["ok"], "坏条目丢掉（没有 slug 的渲染不出卡片）");
});

test("hwcheckDeviceChipsHTML：复用推荐 chip 渲染（✕ 移除 + 说明按钮 + 套件小字）", () => {
  const html = hwcheckDeviceChipsHTML(["ml_mpu6050"], MODULES, "mspm0");
  assert.ok(html.includes('data-remove="ml_mpu6050"'), "chip 本体 = 移除开关（既有契约）");
  assert.ok(html.includes('data-mod-info="ml_mpu6050"'), "内嵌说明按钮（既有渲染）");
  assert.ok(html.includes("MPU6050"), "套件型号进 chip 小字（载荷里人补的那个字段）");
  assert.ok(html.includes('title="点击从工程里移除"'), "文案与推荐区同一份");
  assert.equal(hwcheckDeviceChipsHTML([], MODULES, "mspm0"), "");
  assert.ok(hwcheckDeviceEmptyHTML().includes("灯在闪"),
    "一件都没选不是错误状态（先确认板子活着）");
});

test("hwcheckWiringTableHTML：列与 README 同序；板载共享注记挂在同一行", () => {
  const rows = [
    { slug: "ml_mpu6050", role: "I2C_0_SCL", role_id: "I2C_0_SCL", pin: "PA1",
      remark: "i2c_scl（必接）", pin_note: "板载 LED 共用（I2C_0 SCL，通信期间微闪）" },
    { slug: "led", role: "LED", role_id: "LED", pin: "PA15", remark: "gpio_out（必接）",
      pin_note: "" },
  ];
  const html = hwcheckWiringTableHTML(rows, "其余外设引脚以工程内 pin_config.h 为准");
  for (const head of ["模块", "角色", "引脚", "说明"]) {
    assert.ok(html.includes("<th>" + head + "</th>"), "缺列：" + head);
  }
  assert.ok(html.includes("I2C_0_SCL") && html.includes("PA1"));
  assert.ok(html.includes("板载共享：板载 LED 共用"), "板上共享注记必须在行里");
  assert.ok(html.includes("pin_config.h"), "尾注与 README 同一句");
  const noNote = hwcheckWiringTableHTML([rows[1]], "");
  assert.ok(!noNote.includes("板载共享"), "板上没注记就不编一句");
  const empty = hwcheckWiringTableHTML([], "");
  assert.ok(empty.includes("没有已声明引脚角色"), "空表要说清为什么空");
  assert.ok(hwcheckWiringTableHTML([{ slug: "<x>", pin: "<PA0>" }], "")
    .includes("&lt;PA0&gt;"), "必须转义");
});

test("hwcheckPinGroupsHTML：冲突 ⚠ / 合法共享 ✓（kind 由服务端判，前端只上色）", () => {
  const rows = [
    { slug: "ml_mpu6050", role: "I2C_0_SCL", role_id: "I2C_0_SCL", pin: "PA1" },
    { slug: "relay", role: "RELAY_OUT", role_id: "RELAY_OUT", pin: "PA1" },
  ];
  const groups = [
    { pin: "PA1", roles: ["ml_mpu6050.I2C_0_SCL", "relay.RELAY_OUT"],
      kind: "conflict", reason: "同引脚但分属不同外设（物理不通）——请改线" },
    { pin: "PA6", roles: ["hmc5883l.HMC5883L_SCL"], kind: "share",
      reason: "I2C 总线共享" },
  ];
  const html = hwcheckPinGroupsHTML(groups, rows);
  assert.ok(html.includes("hwcheck-group conflict"), "冲突行要单独一类（红框）");
  assert.ok(html.includes("⚠ 引脚冲突"));
  assert.ok(html.includes("物理不通"));
  assert.ok(html.includes("hwcheck-group share") && html.includes("✓ 可共享"));
  assert.ok(html.includes("ml_mpu6050·I2C_0_SCL"), "角色键显示成「模块·角色」");
  assert.ok(html.includes("hmc5883l.HMC5883L_SCL"),
    "接线表里没有那一行时原样带出角色键（不猜、不丢）");
  // 空集那句话不许自称"没有共用同一个引脚"（那是假安心：板上自带的共享不在这里）
  const empty = hwcheckPinGroupsHTML([], rows);
  assert.ok(empty.includes("没有两件模块抢同一个引脚"));
  assert.ok(empty.includes("板上自带的共享"), "要指向板载共享那一条");
});

test("hwcheckBoardSharesHTML：板载共享单独成条（板载 LED / 上拉这类暗雷）", () => {
  const rows = [
    { slug: "ml_mpu6050", role: "I2C_0_SCL", role_id: "I2C_0_SCL", pin: "PA1" },
    { slug: "ml_mpu6050", role: "I2C_0_SDA", role_id: "I2C_0_SDA", pin: "PA0" },
  ];
  const shares = [
    { pin: "PA0", note: "板载 LED 共用（I2C_0 SDA，通信期间微闪）",
      roles: ["ml_mpu6050.I2C_0_SDA"] },
    { pin: "PA1", note: "板载 LED 共用（I2C_0 SCL）；板载 4.7k 上拉",
      roles: ["ml_mpu6050.I2C_0_SCL"] },
  ];
  const html = hwcheckBoardSharesHTML(shares, rows);
  assert.ok(html.includes("板上自带的共享"), "要说清这不是接线错误");
  assert.ok(html.includes("⚠ 板上共享"));
  assert.ok(html.includes("hwcheck-group board-share"));
  assert.ok(html.includes("板载 LED 共用"));
  assert.ok(html.includes("ml_mpu6050·I2C_0_SCL"), "涉及哪些角色要列出来");
  assert.equal(hwcheckBoardSharesHTML([], rows), "");
  assert.equal(hwcheckBoardSharesHTML(null), "");
  assert.ok(hwcheckBoardSharesHTML([{ pin: "<PA0>", note: "<x>" }], [])
    .includes("&lt;PA0&gt;"), "必须转义");
});

test("hwcheckOrderHTML：编号 + 「先做·板子活着」标记 + 引导语与理由", () => {
  const order = [
    { slug: "delay", description: "软件延时", bring_up: true },
    { slug: "led", description: "板载 LED", bring_up: true },
    { slug: "ml_mpu6050", description: "MPU6050 六轴", bring_up: false },
  ];
  const html = hwcheckOrderHTML(order, "按顺序逐个验证，前一个过了再接下一个",
    "先确认「板子活着」——延时 / 串口 / 灯这类 bring-up 模块排在最前");
  assert.ok(html.includes("hwcheck-order-index"), "要编号（这是「顺序」）");
  assert.equal((html.match(/先做·板子活着/g) || []).length, 2, "只有 bring-up 模块带标记");
  assert.ok(html.includes("按顺序逐个验证"));
  assert.ok(html.includes("为什么是这个次序："));
  assert.ok(html.includes("板子活着"));
  assert.equal(hwcheckOrderHTML([], "x", "y"), "");
});

test("hwcheckOrderDesc：顺序行只留一句话（库内简介常有整段）", () => {
  assert.equal(hwcheckOrderDesc("软件延时。附带说明。"), "软件延时。");
  assert.equal(hwcheckOrderDesc("先这样；再那样。"), "先这样；");
  assert.equal(hwcheckOrderDesc(""), "");
  assert.equal(hwcheckOrderDesc(null), "");
  const long = "字".repeat(100);
  const cut = hwcheckOrderDesc(long);
  assert.equal(cut.length, 61, "超长按上限截断并加省略号");
  assert.ok(cut.endsWith("…"));
  assert.ok(!hwcheckOrderDesc(long).includes("<"), "纯文本（转义在渲染处做）");
});

test("hwcheckMissingDevicesHTML：本平台没有条目 = 点名（不静默省略）", () => {
  const html = hwcheckMissingDevicesHTML([
    { slug: "sr04", message: "sr04：该模块无本平台版本，无法检测（模块库里没有它在 stm32 上的条目）" },
  ]);
  assert.ok(html.includes("hwcheck-warn"));
  assert.ok(html.includes("无本平台版本") && html.includes("无法检测"));
  assert.ok(html.includes("sr04"));
  assert.equal(hwcheckMissingDevicesHTML([]), "");
  assert.equal(hwcheckMissingDevicesHTML(null), "");
  assert.ok(hwcheckMissingDevicesHTML([{ slug: "<x>" }]).includes("&lt;x&gt;"));
  assert.ok(hwcheckWiringErrorHTML("库中不存在模块 nope").includes("接线表"));
});

test("hwcheckBoardState：板侧载荷归一（缺键 = 保留当前选择，不抹掉用户刚选的）", () => {
  const state = { devices: ["led"], wiring: null };
  const next = hwcheckBoardState(state, {
    devices: ["ml_mpu6050"], wiring: { rows: [], groups: [], order: [] },
  });
  assert.deepEqual(next.devices, ["ml_mpu6050"]);
  assert.deepEqual(next.wiring.rows, []);
  const kept = hwcheckBoardState(next, { main_c: "x" });
  assert.deepEqual(kept.devices, ["ml_mpu6050"], "载荷缺 devices 不许清空选择");
  assert.deepEqual(kept.wiring.rows, [], "缺 wiring 也不许把视图抹掉");
});

test("hwcheckProjectState：回读把器件与板侧视图一起带回来", () => {
  const state = hwcheckProjectState({}, {
    output_dir: "C:/out/hwcheck-mspm0-1", platform: "mspm0", debug_uart: true,
    oled: false, main_c: "int main(void){}", output_hint: "只有串口",
    checklist: [{ id: "flash", expect: "e", check: "c" }],
    devices: ["ml_mpu6050"],
    wiring: { rows: [{ slug: "led", pin: "PA15" }], groups: [], order: [], footnote: "f" },
  });
  assert.deepEqual(state.devices, ["ml_mpu6050"]);
  assert.equal(state.wiring.rows[0].pin, "PA15");
  assert.equal(state.project.outputDir, "C:/out/hwcheck-mspm0-1");
});

// ---------------------------------------------------------------------------
// ⑥ 工单 03：接线守卫（控件齐备 / ui 只做胶水 / 器件池走既有载荷）
// ---------------------------------------------------------------------------

test("新控件齐备：器件搜索 / 计数 / chips / 网格 / 接线表 / 冲突 / 顺序容器", () => {
  for (const id of ["hwcheck-device-search", "hwcheck-device-count",
    "hwcheck-device-chips", "hwcheck-device-grid", "hwcheck-device-missing",
    "hwcheck-wiring", "hwcheck-conflicts", "hwcheck-order"]) {
    assert.ok(html.includes('id="' + id + '"'), "缺少控件 #" + id);
  }
});

test("ui 的接线表 / 冲突 / 顺序 / chips 都走 fx 单源（不手拼表格与标记）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  for (const name of ["hwcheckWiringTableHTML(", "hwcheckPinGroupsHTML(",
    "hwcheckOrderHTML(", "hwcheckDeviceChipsHTML(", "hwcheckMissingDevicesHTML(",
    "hwcheckDevicePick(", "hwcheckDevicePool("]) {
    assert.ok(ui.includes(name), "ui 应调用 fx 的 " + name + "）");
  }
  assert.ok(!ui.includes("<table"), "ui 不得手拼接线表（单源在 fx/hwcheck.js）");
  assert.ok(!ui.includes("板载共享"), "板载共享标记的单源在 fx/hwcheck.js");
  // 器件选择复用既有卡片 / chip 渲染，不自造模块清单渲染器
  assert.ok(ui.includes("moduleGridHTML("), "模块卡片应复用模块库既有渲染");
  assert.ok(ui.includes('from "/js/fx/module.js"'), "器件池与卡片渲染取自既有纯件");
  assert.ok(!/class="module-card/.test(ui), "ui 不得手拼模块卡（双源）");
});

test("ui 的说明弹窗走既有委托（捕获阶段拦，否则点说明会把器件去掉）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("bindModuleInfoEntry("), "chip 里的说明按钮要用既有委托");
  assert.ok(ui.includes("openModuleInfo("), "模块卡片的详情按钮走既有弹窗入口");
  const recommend = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/generate-recommend.js", import.meta.url),
    "utf8");
  assert.ok(/export function bindModuleInfoEntry\(root, platformOf\)/.test(recommend),
    "既有委托要能带「用哪个平台展示」（检测页有自己的平台选择）");
});

test("ui 的视图刷新守并发纪律（过期响应不写状态 + 在途触发排队）", () => {
  // CONTEXT.md「展开收口」同款：响应里带着 devices 回显，慢响应回来会把刚选的
  // 那件抹掉。这条钉住三条纪律在（改坏了只有真机连点才看得出来）。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckViewBusy") && ui.includes("hwcheckViewPending"),
    "在途触发要记 pending（不是静默丢弃）");
  assert.ok(ui.includes("hwcheckSelectionKey()"),
    "落地前要比请求体快照（选择集变了 = 这次结果属于旧选择）");
  assert.ok(/if \(hwcheckViewPending\) \{[\s\S]{0,160}?await refreshHwcheckView\(\)/
    .test(ui), "收尾要用当前选择集重跑一次（不是只把标志清掉）");
});

test("ui 的自动回读不抹掉用户刚动的选择（工单 06 会话实测的静默抹除）", () => {
  // 页面加载时的自动回读是异步的；用户可能已经点了平台 / 加了器件。旧工程里的
  // 器件集（常见是空的）一到就把刚选的那件抹掉——页面上看着像"点了没反应"，
  // 真机验收连着五条用例超时才暴露出来。判据同上：比选择集快照，变了就不覆盖。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(/keepSelection: hwcheckSelectionKey\(\) !== requestKey/.test(ui),
    "自动回读落地前要比选择集快照（变了 = 用户已动过，别覆盖）");
  assert.ok(/adoptProject\(payload, dir, \{[\s\S]{0,80}?keepSelection/
    .test(ui), "adoptProject 要能只带工程本体、不碰器件");
});

test("ui 的接线表失败不连坐预览（main.c 只依赖平台与通道）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const clears = ui.match(/hwcheckUI\.preview = ""/g) || [];
  assert.equal(clears.length, 2,
    "只允许「换平台」「换通道」两处清预览（那两处渲染输入真的变了）；"
    + "接线表取不到不许把 02 已交付的 main.c 预览抹掉");
});

// ---------------------------------------------------------------------------
// ⑦ 工单 04：这一趟真测哪几件（专精小节 + 未专精点名）
// ---------------------------------------------------------------------------

const SECTION_LED = {
  slug: "led", platform: "stm32", specialized: true, tag: "[专精]",
  prereq: [], init: ["led_init(LED_RED)"], init_expect: "0",
  probe: null, has_probe: false,
  read: [{ expression: "LED_CHANNEL_COUNT", unit: "通道" }],
  console: null,
  note: ["stm32 板载三色 LED 在 PC13 / PC14 / PC15"],
};

test("hwcheckSectionPlanText：按服务端事实说清这一节到底测什么", () => {
  assert.ok(hwcheckSectionPlanText(SECTION_LED).includes("初始化返回值判定"));
  assert.ok(hwcheckSectionPlanText(SECTION_LED).includes("1 项读数回显"));

  const probed = {
    ...SECTION_LED, has_probe: true,
    probe: { calls: ["mpu6050_who_am_i()"], expect: "0x68" },
  };
  const text = hwcheckSectionPlanText(probed);
  assert.ok(text.includes("通信探头带判定"), "有探头就要说带判定");
  assert.ok(text.includes("0x68"), "期望值要写出来（学生能对照）");

  // 只做动作不判定的探头：**不许说成"测过了"**（spec「不假装测过」）
  const actingOnly = { ...SECTION_LED, probe: { calls: ["OLED_ShowString(0, 0, \"x\")"] } };
  const acting = hwcheckSectionPlanText(actingOnly);
  assert.ok(acting.includes("不做判定"), "只做动作的探头必须如实说不判定");

  assert.equal(hwcheckSectionPlanText({}), "这一节没有实际动作");
});

test("hwcheckSectionsHTML：专精件带 [专精] 徽章 + 判定档位 + 平台说明", () => {
  const htmlOut = hwcheckSectionsHTML([SECTION_LED]);
  assert.ok(htmlOut.includes("[专精]"), "专精标记来自服务端 tag（外观可区分的判据）");
  assert.ok(htmlOut.includes("led"));
  assert.ok(htmlOut.includes("只看现象"), "没探头的件要标「只看现象」而不是「板上判定」");
  assert.ok(htmlOut.includes("PC13"), "平台差异说明直接印出来（不折叠、不翻 manifest）");
  assert.equal(hwcheckSectionsHTML([]), "", "一件都没有 = 空串（调用方不渲染空卡）");
});

test("hwcheckSectionsHTML：有探头的件标「板上判定」（两种外观真的不同）", () => {
  const probed = {
    ...SECTION_LED, has_probe: true,
    probe: { calls: ["mpu6050_who_am_i()"], expect: "0x68" },
  };
  const out = hwcheckSectionsHTML([probed]);
  assert.ok(out.includes("板上判定"));
  assert.ok(!out.includes("只看现象"));
});

test("hwcheckSectionsHTML：文案转义（配方里出现 < > 也不破页面）", () => {
  const nasty = { ...SECTION_LED, slug: "<img>", note: ["a < b"] };
  const out = hwcheckSectionsHTML([nasty]);
  assert.ok(!out.includes("<img>"));
  assert.ok(out.includes("&lt;img&gt;"));
});

test("hwcheckUnspecializedHTML：没配方的件逐条点名 + 说清这一趟做什么（工单 07）", () => {
  const out = hwcheckUnspecializedHTML([
    {
      slug: "sht20",
      label: "未专精：只验总线和初始化",
      plan: "初始化 sht20_init()（无参调用，不判返回值） + 总线地址扫描（SHT20_SCL PA6 / SHT20_SDA PA7，只 ping 地址、不读寄存器）",
      message: "sht20：未专精：只验总线和初始化——这一趟对它做的事：…。",
    },
  ]);
  assert.ok(out.includes("sht20"));
  assert.ok(out.includes("未专精：只验总线和初始化"), "官方标注来自服务端 label（单源）");
  assert.ok(out.includes("总线地址扫描"), "说清这一趟真做什么，不是一句走过场话术");
  assert.ok(out.includes("不算通过"), "通用件没有板上判定，必须明说（不假装测过）");
  assert.ok(!out.includes("[专精]"), "通用件不许带专精徽章（外观可区分是验收线）");
  assert.equal(hwcheckUnspecializedHTML([]), "");
});

test("hwcheckUnspecializedHTML：旧载荷（只有 slug + message）不炸也不编造", () => {
  // 缺 label / plan 的旧载荷：照渲染 message，但**不许**给徽章编一句兜底
  // 措辞（同一句话两处写、迟早两种说法——06 的评审同款）。
  const out = hwcheckUnspecializedHTML([
    { slug: "sr04", message: "sr04：未专精：只验总线和初始化" },
  ]);
  assert.ok(out.includes("sr04"));
  assert.ok(out.includes("只验总线和初始化"), "message 原样带出");
  assert.ok(!out.includes("hwcheck-section-tag"), "没有 label 就不画徽章（不编造）");
});

test("hwcheckUnspecializedHTML：文案转义（slug / 说明里带 < > 也不破页面）", () => {
  const out = hwcheckUnspecializedHTML([
    { slug: "<img>", label: "未专精", plan: "a < b", message: "m < n" },
  ]);
  assert.ok(!out.includes("<img>"));
  assert.ok(out.includes("&lt;img&gt;"));
});

test("hwcheckSectionsState：载荷缺键 = 保留当前状态（旧后端不抹掉已有计划）", () => {
  const state = { sections: [SECTION_LED], unspecialized: [{ slug: "x" }] };
  const kept = hwcheckSectionsState(state, { platform: "stm32" });
  assert.deepEqual(kept.sections, [SECTION_LED]);
  assert.deepEqual(kept.unspecialized, [{ slug: "x" }]);
  const replaced = hwcheckSectionsState(state, { sections: [], unspecialized: [] });
  assert.deepEqual(replaced.sections, []);
  assert.deepEqual(replaced.unspecialized, []);
});

test("hwcheckProjectState：回读把逐件小节与未专精点名一起带回来", () => {
  const next = hwcheckProjectState({}, {
    output_dir: "C:/out/hwcheck-stm32-20260920-153012",
    platform: "stm32",
    sections: [SECTION_LED],
    unspecialized: [{ slug: "sr04", message: "sr04：…" }],
  });
  assert.deepEqual(next.sections, [SECTION_LED]);
  assert.equal(next.unspecialized.length, 1);
});

test("hwcheckProjectState：三个归一器叠加后互不覆盖（spread 顺序回归）", () => {
  // 每个归一器都返回"自己那几个键"；若它们各自 `...state` 展开旧状态，那么
  // 后展开的那个会把前一个刚更新的键按**旧 state** 覆盖回去——回读一次，
  // 器件与检测计划就退回上一次的值（评审实测的回归）。
  const state = {
    devices: ["old"], sections: [{ slug: "old" }], unspecialized: [],
    console: null, exclusiveGroups: [],
  };
  const next = hwcheckProjectState(state, {
    output_dir: "C:/out/hwcheck-stm32-20260920-153012",
    platform: "stm32",
    devices: ["ml_mpu6050"],
    exclusive_groups: GROUPS,
    sections: [SECTION_LED],
    unspecialized: [{ slug: "sr04", message: "sr04：…" }],
    console: CONSOLE_PAYLOAD,
  });
  assert.deepEqual(next.devices, ["ml_mpu6050"], "器件不许被后展开的归一器回退");
  assert.deepEqual(next.sections, [SECTION_LED], "检测计划同理");
  assert.equal(next.unspecialized.length, 1);
  assert.deepEqual(next.exclusiveGroups, GROUPS);
  assert.deepEqual(next.console, CONSOLE_PAYLOAD);
  assert.equal(next.project.platform, "stm32");
});

test("新控件齐备：专精小节容器在检测页（在顺序之后、工程之前）", () => {
  assert.ok(html.includes('id="hwcheck-sections"'), "缺少控件 #hwcheck-sections");
  const orderAt = html.indexOf('id="hwcheck-order"');
  const sectionsAt = html.indexOf('id="hwcheck-sections"');
  const projectAt = html.indexOf('id="hwcheck-project"');
  assert.ok(orderAt < sectionsAt && sectionsAt < projectAt,
    "检测计划的阅读顺序：顺序 → 这一趟真测哪几件 → 检测工程");
});

test("ui 的小节渲染走 fx 单源（不手拼 [专精] 标记与徽章）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  for (const name of ["hwcheckSectionsHTML(", "hwcheckUnspecializedHTML(",
    "hwcheckSectionsState("]) {
    assert.ok(ui.includes(name), "ui 应调用 fx 的 " + name + "）");
  }
  assert.ok(!ui.includes("[专精]"), "[专精] 标记的单源在 fx/hwcheck.js");
  assert.ok(!/class="hwcheck-section/.test(ui), "ui 不得手拼小节壳（双源漂移）");
});

test("ui 换平台 / 换通道时清掉旧检测计划（配方按平台分，留着会误导）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const clears = ui.match(/hwcheckUI\.sections = \[\]/g) || [];
  assert.equal(clears.length, 3,
    "三处该清：换平台 / 换通道 / 取视图失败（清 failed 视图时一并清计划）");
});

// ---------------------------------------------------------------------------
// 工单 module-hwcheck/05：同组互斥 = 单选交换 + 提示（判据来自服务端载荷）
// ---------------------------------------------------------------------------

// 载荷形状与后端 `_hwcheck_view` 的 exclusive_groups 一致：按**平台**过滤后的
// 库级功能组（成员取自整库，单成员组不出）。
const GROUPS = [
  { id: "attitude-hold", label: "航向保持 / 姿态传感器",
    members: ["imu_uart", "jy61p", "ml_mpu6050"] },
  { id: "display", label: "显示 / 屏幕", members: ["lcd", "max7219", "oled"] },
];

test("hwcheckDevicePick：点同组第二件 = 单选交换（旧的自动去掉）", () => {
  const before = { devices: ["ml_mpu6050"] };
  const after = hwcheckDevicePick(before, "jy61p", true, GROUPS);
  assert.deepEqual(after.devices, ["jy61p"], "同组只能留一件，且留的是刚点的那件");
  assert.deepEqual(before.devices, ["ml_mpu6050"], "不许改原对象");
});

test("hwcheckDevicePick：不同组 / 没给组清单时不误伤别的件", () => {
  const state = { devices: ["ml_mpu6050", "sr04", "lcd"] };
  // 点 display 组的另一件：只清掉同组的 lcd，姿态件与另一件都不动
  assert.deepEqual(
    hwcheckDevicePick(state, "max7219", true, GROUPS).devices,
    ["ml_mpu6050", "sr04", "max7219"]);
  // 没给组清单（旧载荷 / 还没拿到预览）→ 老行为：只加不换
  assert.deepEqual(
    hwcheckDevicePick(state, "max7219", true).devices,
    ["ml_mpu6050", "sr04", "lcd", "max7219"]);
  // 不在任何组里的件照常加
  assert.deepEqual(
    hwcheckDevicePick({ devices: ["ml_mpu6050"] }, "sr04", true, GROUPS).devices,
    ["ml_mpu6050", "sr04"]);
});

test("hwcheckDevicePick：取消不做交换、重复点幂等（返回原对象）", () => {
  assert.deepEqual(
    hwcheckDevicePick({ devices: ["ml_mpu6050", "jy61p"] }, "jy61p", false, GROUPS)
      .devices, ["ml_mpu6050"]);
  const once = hwcheckDevicePick({ devices: [] }, "led", true, GROUPS);
  assert.equal(hwcheckDevicePick(once, "led", true, GROUPS), once,
    "已经选中再点一次 = 原样返回（不把它挪到列表末尾，那会改变建议顺序里的位置）");
});

test("hwcheckDeviceGroupNoticeHTML：一件时预告交换、两件时点名冲突", () => {
  const one = hwcheckDeviceGroupNoticeHTML(GROUPS, ["ml_mpu6050"]);
  assert.ok(one.includes("同组互斥") && one.includes("航向保持"),
    "要说清是哪一组：" + one);
  assert.ok(one.includes("jy61p") && one.includes("imu_uart"),
    "要让用户知道还有哪些同组成员：" + one);
  assert.ok(one.includes("会自动换掉 ml_mpu6050"), "预告交换规则：" + one);

  const two = hwcheckDeviceGroupNoticeHTML(GROUPS, ["ml_mpu6050", "jy61p"]);
  assert.ok(two.includes("只能选一件") && two.includes("请去掉一件"),
    "回读 / 历史态可能出现同组两件，如实报冲突：" + two);

  assert.equal(hwcheckDeviceGroupNoticeHTML(GROUPS, []), "", "一件都没选 = 不占版面");
  assert.equal(hwcheckDeviceGroupNoticeHTML(GROUPS, ["sr04"]), "",
    "不在任何互斥组里的件不出提示");
  assert.equal(hwcheckDeviceGroupNoticeHTML([], ["ml_mpu6050"]), "",
    "没有组定义（stm32 上这一组只剩一件）→ 一个字都不说");
});

test("hwcheckDeviceGroupNoticeHTML：文案过转义（组名来自库内数据）", () => {
  const html = hwcheckDeviceGroupNoticeHTML(
    [{ id: "g", label: "<img src=x>", members: ["a", "b"] }], ["a"]);
  assert.ok(!html.includes("<img"), "库内文案也要转义：" + html);
});

test("hwcheckBoardState：接纳 exclusive_groups，缺键时保留旧值", () => {
  const adopted = hwcheckBoardState({}, { devices: [], exclusive_groups: GROUPS });
  assert.deepEqual(adopted.exclusiveGroups, GROUPS);
  assert.deepEqual(
    hwcheckBoardState({ exclusiveGroups: GROUPS }, {}).exclusiveGroups, GROUPS,
    "旧后端 / 出错响应不许把已拿到的组清单抹掉");
  assert.deepEqual(
    hwcheckBoardState({ exclusiveGroups: GROUPS }, { exclusive_groups: [] })
      .exclusiveGroups, [],
    "载荷明确给空数组 = 这个平台没有可互斥的组（stm32 的 attitude-hold）");
});

test("ui：器件挑选把组清单喂给单选交换，并渲染互斥提示", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url),
    "utf8");
  assert.ok(ui.includes("hwcheckDeviceGroupNoticeHTML("),
    "同组互斥提示的渲染要走 fx 单源");
  assert.ok(/hwcheckDevicePick\([^)]*exclusiveGroups/.test(ui),
    "pick 时必须带上组清单，否则单选交换不会发生");
  assert.ok(html.includes('id="hwcheck-device-groups"'),
    "index.html 要有提示的落点");
});

// ---------------------------------------------------------------------------
// 工单 module-hwcheck/06：串口命令台（命令表来自服务端，前端只渲染）
// ---------------------------------------------------------------------------
// 载荷形状与后端 `console_payload` 一致：配方命令（字符 + 哪件 + 说明 + 与板上
// 同一句回显）+ 既有命令 + 帮助字符 + 那句"能不能交互式复测"。
const CONSOLE_PAYLOAD = {
  available: true,
  hint: "有串口 = 能交互式复测：程序跑完上电那一遍后进命令循环…",
  help_command: "?",
  commands: [
    { command: "l", slug: "led", description: "板载 LED：重跑一次点灯初始化",
      echo: "测的是：板载 LED：重跑一次点灯初始化" },
    { command: "m", slug: "ml_mpu6050", description: "MPU6050 通信：读 WHO_AM_I",
      echo: "测的是：MPU6050 通信：读 WHO_AM_I" },
  ],
  legacy: [
    { command: "r", description: "红灯亮，其余灭" },
    { command: "y", description: "黄灯亮，其余灭" },
    { command: "g", description: "绿灯亮，其余灭" },
    { command: "o", description: "全灭" },
    { command: "b", description: "蜂鸣器响 N 毫秒（如 b50）" },
  ],
};

test("hwcheckConsoleHTML：配方命令逐条列出（敲什么 / 哪一件 / 测什么）", () => {
  const out = hwcheckConsoleHTML(CONSOLE_PAYLOAD);
  assert.ok(out.includes("l") && out.includes("led"), "字符与哪一件都要在：" + out);
  assert.ok(out.includes("m") && out.includes("ml_mpu6050"));
  assert.ok(out.includes("板载 LED：重跑一次点灯初始化"), "配方说明要原样印出来");
  assert.ok(out.includes("能交互式复测"), "服务端那句提示原样渲染（前端不另写一版）");
});

test("hwcheckConsoleHTML：既有 r/y/g/o/b 单列，说清语义没变", () => {
  const out = hwcheckConsoleHTML(CONSOLE_PAYLOAD);
  for (const command of ["r", "y", "g", "o", "b"]) {
    assert.ok(out.includes(command), "既有命令 " + command + " 要在表里");
  }
  assert.ok(out.includes("红灯亮，其余灭"), "含义来自服务端（与库内文档单源）");
  assert.ok(out.includes("语义"), "要说明这几条既有命令的语义没变");
});

test("hwcheckConsoleHTML：没有串口时**明说**不能交互式复测，且不摆一张用不了的命令表", () => {
  const out = hwcheckConsoleHTML({
    ...CONSOLE_PAYLOAD,
    available: false,
    hint: "**没有串口 = 不能交互式复测**：这一趟只跑上电那一遍…",
  });
  assert.ok(out.includes("不能交互式复测"), "票面要求：明说不静默降级");
  assert.ok(!out.includes("<table"), "不能用的一趟不摆命令表（免得像「敲了就行」）");
});

test("hwcheckConsoleHTML：没有配方命令时如实说，不留一块空白", () => {
  const out = hwcheckConsoleHTML({
    ...CONSOLE_PAYLOAD, commands: [],
    hint: "有串口，但这一趟没有配方命令…敲 ? 看帮助",
  });
  assert.ok(out.includes("没有配方命令"));
  assert.ok(out.includes("?"), "帮助命令照旧在（固定的那条）");
});

test("hwcheckConsoleHTML：文案过转义（配方说明里出现 < > 也不破页面）", () => {
  const out = hwcheckConsoleHTML({
    ...CONSOLE_PAYLOAD,
    commands: [{ command: "l", slug: "<img>", description: "a < b" }],
  });
  assert.ok(!out.includes("<img>"), "转义：" + out);
  assert.ok(out.includes("&lt;img&gt;"));
  // 说明那一列也要转义（判据强度探针实测：只判 slug 时，把 description 的 esc
  // 拿掉不会红——两列都要钉）
  assert.ok(out.includes("a &lt; b"), "说明列没转义：" + out);
  assert.ok(!out.includes("a < b"));
});

test("hwcheckConsoleHTML：空载荷 = 空串（调用方不渲染空卡）", () => {
  assert.equal(hwcheckConsoleHTML(null), "");
  assert.equal(hwcheckConsoleHTML({}), "");
});

test("hwcheckConsoleState：载荷缺键 = 保留当前状态（旧后端不抹掉已有的命令表）", () => {
  const kept = hwcheckConsoleState({ console: CONSOLE_PAYLOAD }, { platform: "stm32" });
  assert.deepEqual(kept.console, CONSOLE_PAYLOAD);
  const replaced = hwcheckConsoleState({ console: CONSOLE_PAYLOAD },
    { console: { ...CONSOLE_PAYLOAD, available: false } });
  assert.equal(replaced.console.available, false, "明确给了新表就用新的");
});

test("hwcheckProjectState：回读把命令表一起带回来", () => {
  const next = hwcheckProjectState({}, {
    output_dir: "C:/out/hwcheck-stm32-20260920-153012",
    platform: "stm32", console: CONSOLE_PAYLOAD,
  });
  assert.deepEqual(next.console, CONSOLE_PAYLOAD);
});

test("新控件齐备：命令台容器在检测页（在小节之后、工程之前）", () => {
  assert.ok(html.includes('id="hwcheck-console"'), "缺少控件 #hwcheck-console");
  const sectionsAt = html.indexOf('id="hwcheck-sections"');
  const consoleAt = html.indexOf('id="hwcheck-console"');
  const projectAt = html.indexOf('id="hwcheck-project"');
  assert.ok(sectionsAt < consoleAt && consoleAt < projectAt,
    "阅读顺序：这一趟真测哪几件 → 怎么复测 → 检测工程");
});

test("ui 的命令台渲染走 fx 单源（不手拼命令表）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckConsoleHTML("), "ui 应调用 fx 的 hwcheckConsoleHTML(");
  assert.ok(ui.includes("hwcheckConsoleState("), "载荷归一走 fx 的 hwcheckConsoleState(");
  assert.ok(!ui.includes("<table"), "ui 不得手拼表格（双源漂移）");
});

test("ui 换平台 / 换通道时清掉旧命令表（配方按平台分，留着会误导）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const clears = ui.match(/hwcheckUI\.console = null/g) || [];
  assert.equal(clears.length, 3,
    "三处该清：换平台 / 换通道 / 取视图失败（与 sections 同处置）");
});


// ---------------------------------------------------------------------------
// 工单 module-hwcheck/08：现象回填 + AI 排障（唯一的 LLM 入口）
// ---------------------------------------------------------------------------
// 载荷形状与后端 `/api/hwcheck/triage` 一致：建议（定性 + 判断 + 原因 + 下一步
// + 反馈出口）+ degraded/message（模型失败不阻断）。
const ADVICE_PAYLOAD = {
  advice: {
    verdict: "wiring",
    verdict_label: "更像接线问题",
    summary: "串口没字、灯也不闪，先看供电与烧录链路。",
    causes: ["烧录其实没成功（灯不闪说明程序没跑）", "串口 TX/RX 没交叉接"],
    steps: ["按一次复位，看灯闪不闪", "把 TX 与 RX 对调再上电"],
    issue_hint: "排查完还是指向驱动就往反馈里带上检测目录。",
    degraded: false,
  },
  degraded: false,
  message: "",
  record: { version: 1, symptom: "灯也不闪", checked_ids: ["flash"], advice: null },
};

const DEGRADED_PAYLOAD = {
  advice: {
    verdict: "unknown",
    verdict_label: "证据还不够，先按下面的线索查",
    summary: "AI 排障暂时用不了：先按下面的线索自查",
    causes: ["还没确认这条：串口出现「板子活着」"],
    steps: ["逐根核对接线（先这四根）：led 的 LED_RED → PA15"],
    issue_hint: "把检测目录与现象一起反馈，我们可以照着开一张修复单。",
    degraded: true,
  },
  degraded: true,
  message: "连接被拒绝",
  record: { version: 1, symptom: "灯也不闪", checked_ids: [], advice: null },
};

test("hwcheckTriagePayload：只带工程目录 / 现象 / 当前勾选（现象去空白）", () => {
  const payload = hwcheckTriagePayload({
    project: { outputDir: "C:/out/hwcheck-stm32-x" },
    symptom: "  灯在闪，串口没字  ",
    checklistChecked: ["flash", "heartbeat"],
  });
  assert.deepEqual(payload, {
    output_dir: "C:/out/hwcheck-stm32-x",
    symptom: "灯在闪，串口没字",
    checked_ids: ["flash", "heartbeat"],
  });
});

test("hwcheckCanTriage：没有工程或没填现象都不给点（后端必拒，别让人白点）", () => {
  assert.equal(hwcheckCanTriage({ project: null, symptom: "灯不亮" }), false);
  assert.equal(hwcheckCanTriage({ project: { outputDir: "C:/x" }, symptom: "   " }), false);
  assert.equal(hwcheckCanTriage({ project: { outputDir: "C:/x" }, symptom: "灯不亮" }), true);
});

test("hwcheckChecklistPayload：勾选落盘请求体（目录 + 勾选）", () => {
  assert.deepEqual(hwcheckChecklistPayload({
    project: { outputDir: "C:/x" }, checklistChecked: ["flash"],
  }), { output_dir: "C:/x", checked_ids: ["flash"] });
  assert.deepEqual(hwcheckChecklistPayload({}).checked_ids, []);
});

test("hwcheckAdviceState：建议 / 原因 / 降级标记各自落位", () => {
  const ok = hwcheckAdviceState({}, ADVICE_PAYLOAD);
  assert.equal(ok.advice.verdict, "wiring");
  assert.equal(ok.adviceDegraded, false);
  assert.equal(ok.adviceMessage, "");
  const bad = hwcheckAdviceState({}, DEGRADED_PAYLOAD);
  assert.equal(bad.advice.degraded, true);
  assert.equal(bad.adviceDegraded, true);
  assert.equal(bad.adviceMessage, "连接被拒绝", "失败原因单独存，不进建议正文");
});

test("hwcheckAdviceState：载荷缺 advice = 保留现有面板（出错响应不抹掉上一次结论）", () => {
  const kept = hwcheckAdviceState({ advice: ADVICE_PAYLOAD.advice }, {});
  assert.equal(kept.advice.verdict, "wiring");
});

test("hwcheckRecordState：工程回读把现象 / 勾选 / 建议一起带回来", () => {
  const next = hwcheckRecordState({}, {
    record: {
      version: 1, symptom: "屏全黑", checked_ids: ["flash", "oled"],
      advice: ADVICE_PAYLOAD.advice,
    },
  });
  assert.equal(next.symptom, "屏全黑");
  assert.deepEqual(next.checklistChecked, ["flash", "oled"]);
  assert.equal(next.advice.verdict, "wiring");
});

test("hwcheckRecordState：载荷没有 record 键 = 什么都不动（preview / generate 不带它）", () => {
  assert.deepEqual(hwcheckRecordState({ symptom: "保持" }, { platform: "stm32" }), {});
});

test("hwcheckRecordState：记录里没有建议 = advice 为 null（按「还没分析过」渲染）", () => {
  const next = hwcheckRecordState({}, {
    record: { version: 1, symptom: "灯不亮", checked_ids: [], advice: null },
  });
  assert.equal(next.advice, null);
  assert.equal(next.adviceDegraded, false);
});

test("hwcheckChecklistState：只认勾选（别把还没提交的现象覆盖掉）", () => {
  const next = hwcheckChecklistState({}, {
    record: { symptom: "服务端旧值", checked_ids: ["flash"], advice: null },
  });
  assert.deepEqual(next, { checklistChecked: ["flash"] });
  assert.equal("symptom" in next, false, "现象的真源是输入框，不由这个端点回写");
});

test("hwcheckAdviceHTML：定性 + 判断 + 两个列表 + 反馈出口都渲染", () => {
  const out = hwcheckAdviceHTML(ADVICE_PAYLOAD.advice);
  assert.ok(out.includes("更像接线问题"), "服务端给的定性标签原样渲染：" + out);
  assert.ok(out.includes("串口没字、灯也不闪"));
  assert.ok(out.includes("可能原因") && out.includes("下一步查什么"));
  assert.ok(out.includes("按一次复位，看灯闪不闪"));
  assert.ok(out.includes("反馈里带上检测目录"), "修复单出口要在");
  assert.ok(!out.includes("兜底文案"), "正常建议不打兜底徽章");
});

test("hwcheckAdviceHTML：degraded 明说「兜底文案 + 可重试」，不装成模型结论", () => {
  const out = hwcheckAdviceHTML(DEGRADED_PAYLOAD.advice);
  assert.ok(out.includes("兜底文案"), out);
  assert.ok(out.includes("degraded"), "样式上与真结论分开：" + out);
  assert.ok(out.includes("还没确认这条：串口出现"));
});

test("hwcheckAdviceHTML：空建议 = 空态引导（不是一块空白）", () => {
  assert.ok(hwcheckAdviceHTML(null).includes("让 AI 分析"));
  assert.equal(hwcheckAdviceHTML(null), hwcheckAdviceEmptyHTML());
});

test("hwcheckAdviceHTML：文案过转义（模型输出含 < > 也不破页面）", () => {
  const out = hwcheckAdviceHTML({
    verdict: "unknown", verdict_label: "证据 < 不足 >",
    summary: "a < b", causes: ["<img>"], steps: ["<b>x</b>"], issue_hint: "",
  });
  assert.ok(!out.includes("<img>") && !out.includes("<b>x</b>"));
  assert.ok(out.includes("&lt;img&gt;") && out.includes("a &lt; b"));
});

test("hwcheckTriageErrorHTML：请求失败单独一句（与模型失败的兜底分开）", () => {
  const out = hwcheckTriageErrorHTML("目录不存在");
  assert.ok(out.includes("没能提交") && out.includes("目录不存在"));
  assert.ok(out.includes("error"));
});

test("新控件齐备：现象输入框 / 分析按钮 / 状态行 / 建议容器都在检测页", () => {
  for (const id of ["hwcheck-symptom", "btn-hwcheck-triage",
    "hwcheck-triage-status", "hwcheck-advice"]) {
    assert.ok(html.includes('id="' + id + '"'), "缺少控件 #" + id);
  }
  // 阅读顺序：清单（勾完之后）→ 现象回填与排障 → 最近几次检测
  const checklistAt = html.indexOf('id="hwcheck-checklist"');
  const triageAt = html.indexOf('id="hwcheck-symptom"');
  const recentAt = html.indexOf('id="hwcheck-recent"');
  assert.ok(checklistAt < triageAt && triageAt < recentAt,
    "现象回填应在清单之后（照清单确认完才填现象）");
  assert.ok(html.replace(/\s+/g, "").includes("检测没过是正常结果"),
    "要明说「没过是正常结果」，不含糊");
});

test("ui 的建议渲染走 fx 单源 + 勾选落服务端（不手拼建议 HTML）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckAdviceHTML("), "ui 应调用 fx 的 hwcheckAdviceHTML(");
  assert.ok(ui.includes("hwcheckAdviceState(") && ui.includes("hwcheckRecordState("));
  assert.ok(ui.includes("hwcheckChecklistState("),
    "勾选落盘响应只认勾选（整份采纳会吃掉还没提交的现象）");
  assert.ok(ui.includes('"/api/hwcheck/triage"') && ui.includes('"/api/hwcheck/checklist"'));
  assert.ok(!ui.includes("<li>"), "ui 不得手拼建议列表（双源漂移）");
});

test("ui 提交现象前先读输入框（现象的真源是 DOM，不是可能过期的 state）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const submitAt = ui.indexOf("async function submitHwcheckTriage");
  assert.ok(submitAt > 0);
  const body = ui.slice(submitAt, submitAt + 600);
  assert.ok(body.includes('$("hwcheck-symptom")'),
    "提交前要把输入框的当前值收进 state：\n" + body);
});

test("ui 生成新工程时清掉上一次的现象与建议（旧建议属于另一个工程）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const genAt = ui.indexOf("async function generateHwcheck");
  const body = ui.slice(genAt, genAt + 1200);
  assert.ok(body.includes("hwcheckUI.symptom = \"\"") && body.includes("hwcheckUI.advice = null"),
    "生成成功后要归零现象与建议：\n" + body);
});

test("ui 回读勾选的判据是「这次带没带记录」而不是「记录里的勾选空不空」", () => {
  // 评审整改：服务端把勾选全清空也是**有效状态**，拿"空"当"没有记录"会让
  // localStorage 里的旧勾选复活（同一个页面两份真源，谁也说不清哪份对）。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const adoptAt = ui.indexOf("function adoptProject");
  const body = ui.slice(adoptAt, adoptAt + 1400);
  assert.ok(body.includes("payload && payload.record"),
    "判据要看 record 键在不在：\n" + body);
  assert.ok(!/serverTicks\.length/.test(body),
    "不得再用「勾选为空」当「没有记录」：\n" + body);
});

// ---------------------------------------------------------------------------
// 工单 module-hwcheck/09：单平台件不误导（选它时页面不许像"另一平台也能测"）
// ---------------------------------------------------------------------------

test("单平台件不误导：器件挑选面按**本栏目当前平台**标记「需切换平台」", () => {
  // 判据在既有网格渲染里（fx/module.js moduleGridHTML：platform 参数决定
  // 卡片是否带 .off + 「需切换平台」）——检测页要做的只有"把当前平台传进去"。
  // 不传 = sr04 / jy61p / xunji 这类只有 mspm0 条目的件在 stm32 页面上看着能测。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const call = ui.match(/moduleGridHTML\(\s*([^)]*)\)/);
  assert.ok(call, "ui 应复用既有网格渲染 moduleGridHTML");
  assert.ok(call[1].includes("hwcheckUI.platform"),
    "器件卡片必须带上本栏目当前平台（否则单平台件不会标「需切换平台」）：" + call[0]);
});

test("单平台件不误导：**行为**上，未选中的卡片就被标成需切换平台", () => {
  // 上一条是源码文本判据（挡"忘了传平台"），这条真跑一遍挑选面的组合：
  // 挑选池 → 网格渲染 → 卡片上必须带 .off + 「需切换平台」。
  // 误导发生在**未选中**的卡片上，所以这里断言的是"还没点它之前"的样子。
  const onlyMspm0 = {
    slug: "sr04", description: "超声波测距", platforms: { mspm0: { files: [] } },
  };
  const both = {
    slug: "led", description: "板载灯", platforms: { stm32: { files: [] }, mspm0: { files: [] } },
  };
  const pool = hwcheckDevicePool([onlyMspm0, both]);
  const stm32View = moduleGridHTML(pool, [], "", "stm32");
  assert.ok(stm32View.includes("需切换平台"),
    "stm32 页面上 sr04 应被标「需切换平台」：" + stm32View);
  assert.ok(moduleGridHTML([onlyMspm0], [], "", "stm32").includes("module-card off"),
    "单平台件在无条目平台上应带 .off 样式");
  assert.ok(!moduleGridHTML([onlyMspm0], [], "", "mspm0").includes("需切换平台"),
    "它有 mspm0 条目，在 mspm0 页面上不该标");
});

test("单平台件不误导：已选中的单平台件由服务端载荷点名，前端只渲染不另写文案", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const panel = readFileSync(
    new URL("../../src/contest_generator/static/js/fx/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckMissingDevicesHTML("),
    "「本平台无条目」的逐条点名走 fx 单源（判据在服务端 wiring.missing）");
  assert.ok(panel.includes("item.message"),
    "点名文案取服务端给的那句（item.message）");
  assert.ok(!panel.includes("无本平台版本"),
    "前端不另写一版「无本平台版本」——文案单源在服务端（hwcheck_board）");
});


