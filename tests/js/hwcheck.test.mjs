// hwcheck.test.mjs — 硬件检测栏目（工单 module-hwcheck/01）：
// ① fx 纯函数（平台选择状态 / 请求体 / 卡片与提示渲染）；② 三处注册接线
// （静态 import / 启动调用 / 切换时懒加载）——三处缺一，栏目就是「点了没反应」
// 或者「首帧空白」，而这两种坏法在浏览器里都不会报错。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// 六件纯函数（工单 hwcheck-hygiene/09–10 把原 fx/hwcheck.js 按职责拆开）
import {
  hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
  hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
  hwcheckHintHTML, hwcheckErrorHTML, hwcheckGenerateErrorHTML,
  hwcheckEmptyHTML, hwcheckDroppedNoteHTML, hwcheckPanelHTML,
  hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
  HWCHECK_CHANNEL_KEYS, hwcheckDeviceSlugs,
} from "../../src/contest_generator/static/js/fx/hwcheck-state.js";
import {
  hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
  hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
  hwcheckProjectState, hwcheckChannelText, hwcheckProjectInfoHTML,
  hwcheckToolchainNote, hwcheckChannelNoteHTML, hwcheckActionsHTML,
  hwcheckUnverifiedNoteHTML, hwcheckProjectPanelHTML, hwcheckRecentHTML,
  hwcheckRecentEmptyHTML, hwcheckProjectEmptyHTML, HWCHECK_PARENT_KEY,
  HWCHECK_LAST_DIR_KEY, hwcheckBoardState,
} from "../../src/contest_generator/static/js/fx/hwcheck-project.js";
import {
  hwcheckDevicePick, hwcheckDevicePool, hwcheckDeviceKit,
  hwcheckDeviceChipsHTML, hwcheckDeviceEmptyHTML, hwcheckMissingDevicesHTML,
  hwcheckDeviceGroupNoticeHTML, hwcheckWiringTableHTML, hwcheckPinGroupsHTML,
  hwcheckBoardSharesHTML, hwcheckOrderHTML, hwcheckOrderDesc,
  hwcheckPinFixHTML, hwcheckPinCapacityNoteHTML,
} from "../../src/contest_generator/static/js/fx/hwcheck-wiring.js";
import {
  hwcheckSectionsState, hwcheckSectionsHTML, hwcheckUnspecializedHTML,
  hwcheckSectionPlanText, hwcheckSectionNoteHTML, hwcheckConsoleState,
  hwcheckConsoleHTML, hwcheckConsoleNoteHTML, hwcheckCustomState,
  hwcheckCustomPlanHTML, hwcheckCustomWiringHTML,
} from "../../src/contest_generator/static/js/fx/hwcheck-plan.js";
import {
  hwcheckSymptomText, hwcheckCanTriage, hwcheckTriagePayload,
  hwcheckChecklistPayload, hwcheckAdviceState, hwcheckRecordState,
  hwcheckChecklistState, hwcheckTriageErrorHTML, hwcheckAdviceHTML,
  hwcheckAdviceEmptyHTML,
} from "../../src/contest_generator/static/js/fx/hwcheck-triage.js";
import {
  hwcheckHandoffPlan, hwcheckHandoffHTML, hwcheckHandoffMerge,
  hwcheckHandoffPinNote, hwcheckHandoffResultText,
} from "../../src/contest_generator/static/js/fx/hwcheck-handoff.js";
// 转义单源（判定渲染出的 HTML 里有没有把用户文本原样吐出去）
import { esc } from "../../src/contest_generator/static/js/fx/core.js";
// 单平台件的「需切换平台」标记落在既有网格渲染上（工单 09 的行为判据要真跑它）
import { moduleGridHTML } from "../../src/contest_generator/static/js/fx/module.js";

// 工单 hwcheck-hygiene/09–10：纯函数层按职责拆成六件（`hwcheck.js` 那个过渡态 barrel 已删）。
// 凡"对 fx 这一层成立"的判据都作用在**整个层**上——钉某个路径的写法在搬迁后要么读到空壳
// （断言恒真）、要么读不到文件（报错或静默跳过），两种都是"守卫闭眼"。
const HWCHECK_FX_DIR = new URL("../../src/contest_generator/static/js/fx/", import.meta.url);
const HWCHECK_FX_FILES = [
  "hwcheck-state.js", "hwcheck-project.js", "hwcheck-wiring.js",
  "hwcheck-plan.js", "hwcheck-triage.js", "hwcheck-handoff.js",
];
const hwcheckFxSources = () =>
  HWCHECK_FX_FILES.map((name) => [name, readFileSync(new URL(name, HWCHECK_FX_DIR), "utf8")]);
const hwcheckFxText = () => hwcheckFxSources().map(([, text]) => text).join("\n");

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);
// 装载根（工单 frontend-boot-module/02 起装载清单与启动区都住在这里）
const boot = readFileSync(
  new URL("../../src/contest_generator/static/js/boot.js", import.meta.url),
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
    "ui 不得手写 data-hwcheck-code 标记（壳的单源在 fx/hwcheck-state.js）");
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

test("静态 import：装载根（boot.js）从 /js/ui/hwcheck.js 导入 renderHwcheckPanel + initHwcheck", () => {
  const m = boot.match(/import\s*\{([^}]*)\}\s*from\s*"\/js\/ui\/hwcheck\.js"/);
  assert.ok(m, "boot.js 应有 ui/hwcheck.js 的静态 import");
  const names = m[1].split(",").map((s) => s.trim()).filter(Boolean);
  assert.ok(names.includes("renderHwcheckPanel"), "应导入 renderHwcheckPanel");
  assert.ok(names.includes("initHwcheck"), "应导入 initHwcheck");
});

test("启动调用：initHwcheck() 在启动区被调一次", () => {
  assert.ok(/^initHwcheck\(\);/m.test(boot), "启动区应调用 initHwcheck()");
});

test("切换时懒加载：页签分发器对 hwcheck 调 renderHwcheckPanel()", () => {
  assert.ok(
    boot.includes('if (btn.dataset.tab === "hwcheck") renderHwcheckPanel();'),
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
  // 工单 hwcheck-hygiene/10：纯件层是六件（09 拆的、barrel 已删）——六条边**逐条**点名，
  // 少一条就是"那一类纯件没人取"（fx-guard 判据④ 也会红，这里先指到具体哪一件）。
  // ⚠ 这仍是**源码串**断言（结构守卫，不是行为断言）：12 号单重算"源码串断言"基线时按
  // 1 → 6 条记，别再按老数起算。
  for (const key of ["state", "project", "wiring", "plan", "triage", "handoff"]) {
    assert.ok(ui.includes(`from "/js/fx/hwcheck-${key}.js"`),
      `ui/hwcheck.js 应从 fx/hwcheck-${key}.js 导入纯件`);
  }
});

test("单向 import：ui → fx（fx 那六件都不得反向 import ui 或 app）", () => {
  // 工单 hwcheck-hygiene/09–10 把纯函数层拆成六件（barrel 是过渡态、10 号单已删除）。
  // 判据**不许钉在某一个文件上**：钉路径的写法在搬迁后要么读到 barrel 那种空壳（断言恒真）、
  // 要么读不到文件——两种都是"守卫闭眼"，而这条不变量（fx 不碰 DOM、不发请求、不反向依赖）
  // 要对**每一件**成立。
  for (const [name, fx] of hwcheckFxSources()) {
    assert.ok(!/from\s+"\/js\/ui\//.test(fx), `${name}：fx 不得 import ui（单向依赖）`);
    assert.ok(!/from\s+"\/js\/app\.js"/.test(fx), `${name}：fx 不得 import app（DOM/状态层）`);
    assert.ok(!/\bdocument\./.test(fx), `${name}：fx 不得碰 DOM`);
    assert.ok(!/\bfetch\(/.test(fx), `${name}：fx 不得发请求`);
  }
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

test("hwcheckUnverifiedNoteHTML：栏目顶部要把「尚未在真板上验证过」说出来（工单 hardening/02）", () => {
  // 为什么这条要在前端钉：页面上原先**一句都没有**交代这批检测的分量——
  // 各格自己的平台说明里有「未上板」，但那是"读到某一格"才看得到的东西。
  const html = hwcheckUnverifiedNoteHTML();
  assert.ok(html.includes("hwcheck-warn"), "要显眼，不是一句灰字");
  assert.ok(html.includes("尚未在真板上验证过"), "总口径的核心那句不许改写成别的说法");
  assert.ok(html.includes("能生成 + 能编译"), "如实说清现有证据到哪一步");
  assert.ok(html.includes("先按下面的清单查接线"), "判 FAIL 时的第一步指向页面已有的清单");
  assert.ok(!html.includes("**"), "HTML 串里不许出现 markdown 粗体标记（会原样显示成星号）");
});

test("hwcheckUnverifiedNoteHTML：与配方数据里那句同一个事实（两种粒度，不许互相矛盾）", () => {
  // 数据侧那句在 library/hwcheck_recipes.json 的每格 note 末条（57/57，pytest 侧有守卫）。
  const recipes = readFileSync(
    new URL("../../library/hwcheck_recipes.json", import.meta.url), "utf8");
  assert.ok(recipes.includes("**未上板**：本格的结论只到"), "配方侧的自述形态变了——本条前提要跟着改");
  assert.ok(hwcheckUnverifiedNoteHTML().includes("尚未在真板上验证过"));
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

test("hwcheckPinCapacityNoteHTML：没判容量就把原因说出来；判过了不渲染", () => {
  // 工单 hwcheck-hygiene/04：母版没导入时容量判定整段跳过——页面一声不吭就像
  // "检查过了、没问题"，而学生点到「生成」才吃 400。文案由服务端给（这里只渲染）。
  const note = "没导入 mspm0 母版（或母版里没有 mspm0.syscfg）：这一趟没判「装不装得下」";
  const html = hwcheckPinCapacityNoteHTML(note);
  assert.ok(html.includes("hwcheck-warn"), "要与其它警告同一视觉档");
  assert.ok(html.includes("没判"), "原话说的是「没判」");
  // 服务端那句文案本身**不许带 markdown 标记**（工单 02 的口径：产品串里的 `**…**`
  // 到了页面上就是两个字面星号；这里顺带把"前端不解释标记"这件事钉住——
  // 前端只渲染，标记该由服务端不写）
  assert.ok(!html.includes("**"), "渲染产物里出现了字面星号");
  assert.equal(hwcheckPinCapacityNoteHTML(""), "", "判过了 = 不渲染");
  assert.equal(hwcheckPinCapacityNoteHTML(null), "");
  assert.equal(hwcheckPinCapacityNoteHTML("   "), "");
  assert.ok(hwcheckPinCapacityNoteHTML("<b>x</b>").includes("&lt;b&gt;"), "转义");
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

// 工单 ci-gate-fixes/09：**已经不在器件库里**的自建件被服务端摘掉时，页面要如实说一句。
// 为什么不能静默：页面上少了一件，用户只看到"我明明选着它"；为什么不是错误文案：
// 那是用户自己删的件，不是他做错了什么。
test("被摘掉的自建件说明：点名 slug + 说清已摘掉；空清单/缺字段不渲染", () => {
  const note = hwcheckDroppedNoteHTML(["mine_gyro"]);
  assert.ok(note.includes("mine_gyro"), note);
  assert.ok(note.includes("已经不在你的器件里"), note);
  assert.ok(note.includes("摘掉"), note);
  assert.ok(!note.includes("错误") && !note.includes("失败"), "中性提示，不是报错：" + note);
  // 多件各说各的（一件一行），不合并成一句
  const two = hwcheckDroppedNoteHTML(["mine_a", "mine_b"]);
  assert.equal(two.split("hwcheck-dropped-note").length - 1, 2, two);
  // 空 / 缺字段（旧载荷）→ 空串：与从前逐字节一致
  assert.equal(hwcheckDroppedNoteHTML([]), "");
  assert.equal(hwcheckDroppedNoteHTML(undefined), "");
  assert.equal(hwcheckDroppedNoteHTML(null), "");
  // 转义（id 文法只允许 [A-Za-z0-9_]，但渲染层不该赌上游）
  assert.ok(hwcheckDroppedNoteHTML(["mine_<x>"]).includes("&lt;x&gt;"), "必须转义");
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

test("ui 不手拼工程面板 / 清单 / 最近的壳（壳的单源在 fx/hwcheck-project.js）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes("hwcheckProjectPanelHTML("));
  assert.ok(ui.includes("hwcheckChecklistHTML("));
  assert.ok(ui.includes("hwcheckRecentHTML("));
  // 壳体的样式标记不许在 ui 里手写（双源漂移 + 丢 esc，工单 01 评审同款）
  assert.ok(!/class="hwcheck-(check|recent-row|actions|path|warn)/.test(ui),
    "ui 不得手拼这些壳的样式标记（单源在 fx/hwcheck-project.js）");
  // 带值的 data-* 标记只允许出现在 querySelector 的选择器里（取按钮用）
  const markers = ui.match(/data-hwcheck-(compile|check|open-project|flash)="/g) || [];
  const inSelector = ui.match(/\[data-hwcheck-(compile|check|open-project|flash)="/g) || [];
  assert.equal(markers.length, inSelector.length,
    "带值的 data-* 标记只许出现在选择器里（壳的唯一出处是 fx/hwcheck-project.js）");
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
  assert.ok(!ui.includes("<table"), "ui 不得手拼接线表（单源在 fx/hwcheck-wiring.js）");
  assert.ok(!ui.includes("板载共享"), "板载共享标记的单源在 fx/hwcheck-wiring.js");
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

test("ui 的三处清预览：换平台 / 换通道 / **预览失败**（工单 hardening/07 更正）", () => {
  // 这条守卫原来写的是"接线表取不到不许把 main.c 预览抹掉"，依据是"检测程序只依赖平台与通道"。
  // 那个前提**不成立**：主程序是按所选器件渲染的（render_main_c(config, sections, generic, custom)），
  // 所以预览失败之后留着的那份属于**上一组器件**——照它去编译烧录就是烧错东西。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  // **先剥注释再数**（工单 hwcheck-hardening/10）：直接数原文的话，留一句注释就能凑数——
  // 同一批新写的那条结构钉已经这么做了，这条是补课。
  const code = ui.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
  const clears = code.match(/hwcheckUI\.preview = ""/g) || [];
  assert.equal(clears.length, 3,
    "三处清预览：换平台 / 换通道（渲染输入变了）+ 预览失败（那份属于上一组器件）");
  // 失败路径必须用专用文案，且不再借用"接线表取不到"
  assert.ok(ui.includes("hwcheckErrorHTML(hwcheckUI.previewError)"),
    "预览失败要显示「检测程序预览失败」那句（专用文案），别把学生引去查接线");
  assert.ok(!ui.includes("wiringError"), "wiringError 这条老路已删（它当年表达的正是「预览失败」）");
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

test("hwcheckSectionNoteHTML：多实例的实话说进 DOM，且本单新写的那句不带 markdown 标记（工单 07）", () => {
  // 为什么这条在**前端**：工单 07 的判据要求"页面渲染出来的文本里"必须有一句"只验第一路"。
  // pytest 那支（`tests/test_hwcheck_recipe.py`）只能看到服务端**载荷**（`sections_payload`），
  // 载荷 → HTML 这最后一跳只有这里跑得动（`ui` 件进不了 python）。两跳都钉住，链条才算闭合。
  //
  // 数据取**真配方**（`library/hwcheck_recipes.json` 的 led × stm32）：判据要的是"学生
  // 真会看到的那句话"，不是测试自己编的一句——编的那句绿了，真数据少一句照样漏。
  const doc = JSON.parse(readFileSync(
    new URL("../../library/hwcheck_recipes.json", import.meta.url), "utf8"));
  const note = doc.led.stm32.note.lines;
  const disclosure = note.filter((line) => line.includes("多实例只验"));
  assert.equal(disclosure.length, 1, "led × stm32 应当有且只有一条多实例自述");
  assert.ok(disclosure[0].includes("第一路"),
    "自述要含「第一路」这一层意思（「通道数」那半句正是误导的来源）：\n" + disclosure[0]);
  assert.ok(!disclosure[0].includes("**"),
    "本单新写的这句带了 markdown 标记——`esc()` 之后就是两个字面星号：\n" + disclosure[0]);

  const html = hwcheckSectionNoteHTML({ slug: "led", note });
  assert.ok(html.includes("第一路"), "自述没进渲染产物：\n" + html);
  assert.ok(html.includes("hwcheck-hint"), "平台说明按既有观感逐条印（不折叠）：\n" + html);
  // 负向自证：渲染件读的是载荷，不编句子（换个 note 就不该有那句话）
  assert.ok(!hwcheckSectionNoteHTML({ slug: "led", note: ["别的说明"] }).includes("第一路"));
  assert.equal(hwcheckSectionNoteHTML({ slug: "led", note: [] }), "");
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
  assert.ok(!ui.includes("[专精]"), "[专精] 标记的单源在 fx/hwcheck-plan.js");
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

// 载荷形状与后端 `hwcheck_board.hwcheck_view` 的 exclusive_groups 一致：按**平台**
// 过滤后的库级功能组（成员取自整库，单成员组不出）。
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

test("hwcheckConsoleNoteHTML / hwcheckConsoleState：余量提示由服务端给，空串不吭声（工单 hardening/05）", () => {
  // 为什么钉这两条：字符分不出来是**生成前 400**，学生在那之前没有任何信号；
  // 但也不能常驻一句警告——空串必须什么都不渲染。判据不在前端（分配器的账在服务端）。
  assert.equal(hwcheckConsoleNoteHTML(""), "");
  assert.equal(hwcheckConsoleNoteHTML(null), "");
  assert.equal(hwcheckConsoleNoteHTML(undefined), "");
  const note = hwcheckConsoleNoteHTML("⚠ 复测字符快用完了：只剩 1 个");
  assert.ok(note.includes("hwcheck-warn"), "要显眼（与其它警告同款外观）");
  assert.ok(note.includes("只剩 1 个"), "服务端那句原样带出（前端不拼数）");

  const state = hwcheckConsoleState({ console: null, consoleNote: "旧" }, { console_note: "新一句" });
  assert.equal(state.consoleNote, "新一句");
  assert.equal(hwcheckConsoleState({ consoleNote: "旧" }, {}).consoleNote, "旧",
    "载荷缺键 = 保留当前状态（旧后端不抹掉已有提示）");
  assert.equal(hwcheckConsoleState({}, {}).consoleNote, "", "从没有过就是空串，不是 undefined");
});

test("结构钉：余量提示有渲染落点 + ui 真调它（工单 hardening/05）", () => {
  const at = html.indexOf('id="hwcheck-console-note"');
  assert.ok(at > 0, "缺少余量提示容器 #hwcheck-console-note");
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes('$("hwcheck-console-note")'), "余量提示要有渲染落点");
  assert.ok(ui.includes("hwcheckConsoleNoteHTML(hwcheckUI.consoleNote)"), "要真的把服务端那句渲染出来");
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
  const panel = hwcheckFxText();
  assert.ok(ui.includes("hwcheckMissingDevicesHTML("),
    "「本平台无条目」的逐条点名走 fx 单源（判据在服务端 wiring.missing）");
  assert.ok(panel.includes("item.message"),
    "点名文案取服务端给的那句（item.message）");
  assert.ok(!panel.includes("无本平台版本"),
    "前端不另写一版「无本平台版本」——文案单源在服务端（hwcheck_board）");
});

// ---------------------------------------------------------------------------
// 工单 hwcheck-unknown-device/02：「我的器件」（库外件）这块卡片的接线
//
// 判据放在这里（而不是另开一个文件）：这块卡片住在**检测页**里，三处接线的坏法
// 与栏目其它部分一样——「点了没反应」「首帧空白」「换了平台把用户填的东西弄丢」。
// 纯函数判据在 tests/js/my-devices.test.mjs。
// ---------------------------------------------------------------------------

test("新控件齐备：「+ 我的器件」按钮 / 列表容器 / 表单容器都在检测页", () => {
  for (const id of ["btn-my-device-new", "my-devices-list", "my-devices-form"]) {
    assert.ok(html.includes('id="' + id + '"'), "缺少控件 #" + id);
  }
  // 位置：在器件挑选区之内（它就是"要测的器件"的一部分），且排在下拉搜索之前
  const cardAt = html.indexOf('id="my-devices"');
  const gridAt = html.indexOf('id="hwcheck-device-grid"');
  assert.ok(cardAt > 0 && gridAt > cardAt,
    "「我的器件」应排在器件挑选区里（库内挑选之前：库里没有的件是最先要说的）");
  assert.ok(html.replace(/\s+/g, "").includes("库外件"),
    "卡面要说明它是「库外件」——不与库内器件混为一谈");
});

test("ui 静态 import fx/my-devices.js（不 import = 点开表单就报 undefined）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes('from "/js/fx/my-devices.js"'),
    "ui/hwcheck.js 应静态 import fx/my-devices.js");
  for (const fn of ["myDeviceFormHTML(", "myDeviceFormCheck(", "myDevicePayload(",
    "myDeviceListHTML("]) {
    assert.ok(ui.includes(fn), "ui 应调用 fx 的 " + fn);
  }
  assert.ok(!ui.includes("<input type=\"text\" data-my-device-field"),
    "ui 不得手拼表单 HTML（双源漂移：校验理由与表单必须同源）");
});

test("ui 读写端点走既有 apiGet / apiPost / apiDelete（不自造 fetch）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes('apiGet("/api/my-devices")'));
  assert.ok(ui.includes('apiPost("/api/my-devices"'));
  assert.ok(ui.includes('apiDelete("/api/my-devices/"'));
  assert.ok(!/fetch\(\s*["']\/api\/my-devices/.test(ui), "不得绕开 app.js 的 api* 辅助");
});

test("ui 删掉一件时把它从**这次检测的选择**里去掉（否则下次预览 400 未知模块）", () => {
  // 删掉之后那个 id 既不在库里、也不再是自建件 —— 而页面上 chip 还挂着，
  // 学生根本不知道是自己刚删的那件（这是最容易变成"莫名其妙打不开"的一处）。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const delAt = ui.indexOf("async function deleteMyDevice");
  assert.ok(delAt > 0, "应有 deleteMyDevice");
  const body = ui.slice(delAt, delAt + 1100);
  assert.ok(body.includes("hwcheckUI.devices.filter"),
    "删除后要把它从选中集合里摘掉：\n" + body);
});

test("ui 的 id 建议不覆盖用户手填的 id（只在空 / 还是建议值时补）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const at = ui.indexOf("myDeviceSlugFromName(");
  assert.ok(at > 0, "应按名称给一个 id 建议");
  const body = ui.slice(Math.max(0, at - 700), at + 200);
  assert.ok(/current/.test(body) && /mine_/.test(body),
    "补建议前要先看用户填过没有：\n" + body);
});

test("ui 的 id 建议也只改那一个输入框（不许整块重绘把在填的字段清掉）", () => {
  // 同一个坑的另一处：`blur` 时按名称补 id 建议，若顺手整块重绘，用户刚填的
  // 地址 / 寄存器全被换成初值（浏览器验收实测：地址填了却报「必须填地址」）。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const at = ui.indexOf('myBox.addEventListener("blur"');
  assert.ok(at > 0, "应有按名称补 id 建议的 blur 委托");
  const body = ui.slice(at, at + 900);
  assert.ok(body.includes("syncMyDeviceForm()"),
    "补完建议要走就地同步：\n" + body);
  assert.ok(!body.includes("renderMyDevices("),
    "补建议不得整块重绘表单：\n" + body);
});

test("「我的器件」的行随选择集重绘（从 chip 侧取消加选后，行上按钮不许还说「已在」）", () => {
  // 两个容器（#hwcheck-device-chips 与 #my-devices-list）显示同一份选择集——
  // 只重绘一个就是界面自相矛盾：chip 没了、行上还写着「✓ 已在这次检测里」。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const at = ui.indexOf("function renderHwcheckDevices()");
  assert.ok(at > 0);
  const body = ui.slice(at, ui.indexOf("\n}", at) + 2);
  assert.ok(body.includes("myDeviceListHTML(hwcheckUI.myDevices, hwcheckUI.devices)"),
    "器件面重绘时要带上选中集重绘「我的器件」列表：\n" + body);
  assert.ok(!/renderMyDevices\(/.test(body),
    "不许整块 renderMyDevices（它会把正在填的表单刷掉）：\n" + body);
});

test("ui 打字期间**不整块重绘表单**（重绘 = 正在打字的输入框被换掉，字全丢）", () => {
  // 本单浏览器验收当场抓到的 bug：`input` 委托里调了整块 `renderMyDevices()`，
  // 于是用户刚敲进去的字符所在的 `<input>` 被 innerHTML 换掉——现象是"打一个字
  // 表单就清空"，而按钮与地址预览看着还正常。判据：syncMyDeviceForm 里一个
  // `innerHTML` 都不许有（就地更新那两个小节点），整块重绘只走显式动作。
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const at = ui.indexOf("function syncMyDeviceForm()");
  assert.ok(at > 0);
  const body = ui.slice(at, ui.indexOf("\n}", at) + 2);
  assert.ok(!/\brenderMyDevices\s*\(/.test(body),
    "syncMyDeviceForm 不得整块重绘表单：\n" + body);
  assert.ok(!/box\.innerHTML\s*=/.test(body),
    "syncMyDeviceForm 不得写 box.innerHTML：\n" + body);
  assert.ok(body.includes("data-my-device-address-preview-slot")
    && body.includes("data-my-device-form-error"),
    "预览与校验理由要就地更新（不重绘也要跟着走）：\n" + body);
});

test("「我的器件」不随平台清空（件与平台无关：切平台不该把用户填的件弄丢）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const at = ui.indexOf('const card = e.target.closest("[data-hwcheck-platform]")');
  assert.ok(at > 0);
  const body = ui.slice(at, at + 900);
  for (const key of ["myDevices", "myForm", "knownSlugs"]) {
    assert.ok(!body.includes("hwcheckUI." + key + " = []") && !body.includes("hwcheckUI." + key + " = null"),
      `换平台不该清掉 hwcheckUI.${key}：\n` + body);
  }
});

// ===========================================================================
// 工单 hwcheck-unknown-device/05：自建件的**检测计划**面板（接线行 / 标注 /
// 不出小节的原因）
//
// 分工照旧：判据与文案全在服务端（`hwcheck_custom`），本文件只把载荷渲染成
// HTML。所以这里的用例一条都不许自己拼文案——它们断言的是"服务端给的那句
// 原样出现在页面上"，以及"一件自建件都没有时一个字都不多"。
// ===========================================================================

// 计划载荷（形状 = `hwcheck_custom.CustomPlanEntry.to_payload`，服务端真源）
const CUSTOM_PLAN = [
  {
    slug: "mine_gyro", name: "卖家给的六轴模块", tag: "自建件",
    tag_text: "自建件：按你确认的事实探测",
    plan: "ping 地址 + 读身份寄存器并与期望值比较：板上判 OK / FAIL",
    address_text: "0x68", register_text: "0x75", expect_text: "0x68",
    echo_only: false, notes: "卖家页写的 WHO_AM_I",
    user_confirmed: true, probes: true, not_probed: "",
    pins: [{ role: "I2C_PROBE_SCL", pin: "PA6" }, { role: "I2C_PROBE_SDA", pin: "PA7" }],
    wiring_text: "你的器件 卖家给的六轴模块（地址 0x68）接到上面接线表里 i2c_probe 的那对脚："
      + "I2C_PROBE_SCL → PA6、I2C_PROBE_SDA → PA7",
  },
  {
    slug: "mine_spi_screen", name: "卖家给的 SPI 屏", tag: "自建件",
    tag_text: "自建件：按你确认的事实探测",
    plan: "这一版只对 I2C 器件生成探测程序：它这一趟没有探测小节（清单与 AI 排障照旧，不假装测过）",
    address_text: "", register_text: "", expect_text: "",
    echo_only: false, notes: "", user_confirmed: true, probes: false,
    not_probed: "这一版只对 I2C 器件生成探测程序：它这一趟没有探测小节（清单与 AI 排障照旧，不假装测过）",
    pins: [], wiring_text: "",
  },
];

test("hwcheckCustomState：载荷缺 custom 键 = 保留当前计划（出错响应不许把计划抹掉）", () => {
  const state = { custom: CUSTOM_PLAN };
  assert.deepEqual(hwcheckCustomState(state, {}).custom, CUSTOM_PLAN);
  assert.deepEqual(hwcheckCustomState(state, null).custom, CUSTOM_PLAN);
  assert.deepEqual(hwcheckCustomState(state, { custom: [] }).custom, []);
  assert.deepEqual(hwcheckCustomState(null, {}).custom, []);
});

test("计划面板：**一件自建件都没有 = 空串**（既有页面逐字不变）", () => {
  assert.equal(hwcheckCustomPlanHTML([]), "");
  assert.equal(hwcheckCustomPlanHTML(null), "");
  assert.equal(hwcheckCustomWiringHTML([]), "");
  assert.equal(hwcheckCustomWiringHTML(CUSTOM_PLAN.filter((d) => !d.probes)), "",
    "没有接线说明的那几件不进接线区（不许编一行脚）");
});

test("计划面板：标注词 / 名称 / 地址 / 这一趟做什么——全部照抄载荷，不另写一句", () => {
  const out = hwcheckCustomPlanHTML(CUSTOM_PLAN);
  for (const item of CUSTOM_PLAN) {
    assert.ok(out.includes(esc(item.tag_text)), "标注词要来自载荷 tag_text：" + item.slug);
    assert.ok(out.includes(esc(item.name)), item.slug);
  }
  assert.ok(out.includes(esc(CUSTOM_PLAN[0].plan)), "这一趟做什么要来自载荷 plan");
  assert.ok(out.includes("0x68") && out.includes("0x75"), "地址 / 寄存器照原样显示");
  assert.ok(out.includes(esc(CUSTOM_PLAN[1].not_probed)),
    "不出小节的那件要给出原因（页面不许留一块沉默的空白）");
  assert.ok(out.includes("不假装测过"), "非 I2C 那句「这版不给它生成」的意思要留着");
});

test("计划面板：与库内专精件**外观可区分**——自建件那一栏不许出现 [专精]", () => {
  const out = hwcheckCustomPlanHTML(CUSTOM_PLAN);
  assert.ok(!out.includes("[专精]"), "自建件不冒充库内验证过的结论：\n" + out);
  assert.ok(out.includes("hwcheck-custom-plan"), "要有自己的类名（不套 .hwcheck-section）");
});

test("计划面板：用户文本一律 esc（名称 / 备注是用户随手填的）", () => {
  const nasty = [{ ...CUSTOM_PLAN[0], name: "<img src=x onerror=alert(1)>", notes: "a & b" }];
  const out = hwcheckCustomPlanHTML(nasty);
  assert.ok(!out.includes("<img"), out);
  assert.ok(out.includes("&lt;img"), out);
  assert.ok(out.includes("a &amp; b"), out);
});

test("接线区：自建件那一行照抄服务端的 wiring_text（脚与接线表同源）", () => {
  const out = hwcheckCustomWiringHTML(CUSTOM_PLAN);
  assert.ok(out.includes(esc(CUSTOM_PLAN[0].wiring_text)), out);
  assert.ok(out.includes("i2c_probe"), "那一行要点出脚来自支点模块");
  assert.ok(!out.includes(esc(CUSTOM_PLAN[1].name)),
    "不出小节的那件不进接线区（它没有线可接）");
});

test("顺序表：自建件那几行带标注词与名称，且**不是** [专精] 徽章", () => {
  const order = [
    { slug: "led", description: "板载灯", bring_up: true },
    { slug: "mine_gyro", description: CUSTOM_PLAN[0].plan, bring_up: false,
      custom: true, name: CUSTOM_PLAN[0].name, tag_text: CUSTOM_PLAN[0].tag_text },
  ];
  const out = hwcheckOrderHTML(order, "引导语", "理由");
  assert.ok(out.includes(esc(CUSTOM_PLAN[0].tag_text)), out);
  assert.ok(out.includes(esc(CUSTOM_PLAN[0].name)), "顺序表要认得出是哪一件（slug 之外给名称）");
  assert.ok(!out.includes("[专精]"), out);
  // 库内那几行的既有渲染一个字没动
  assert.ok(out.includes("先做·板子活着"), out);
  assert.ok(out.indexOf("先做·板子活着") < out.indexOf(esc(CUSTOM_PLAN[0].tag_text)),
    "自建件排在库内 bring-up 件之后");
});

test("新控件齐备：计划容器在检测页里，紧跟在「这一趟真测哪几件」的专精小节之后", () => {
  const planAt = html.indexOf('id="hwcheck-custom"');
  assert.ok(planAt > 0, "缺少计划容器 #hwcheck-custom");
  const sectionsAt = html.indexOf('id="hwcheck-sections"');
  const consoleAt = html.indexOf('id="hwcheck-console"');
  assert.ok(sectionsAt < planAt && planAt < consoleAt,
    "自建件的计划要排在专精小节之后、命令台之前（同一张卡里）："
    + `${sectionsAt} / ${planAt} / ${consoleAt}`);
  // ⚠ 判据不许靠注释喂绿：容器必须在**卡片正文**里，而不是被写进 HTML 注释
  const cardAt = html.lastIndexOf("<div class=\"card\">", sectionsAt);
  assert.ok(cardAt > 0 && cardAt < sectionsAt, "找不到专精小节所在的卡片");
  assert.ok(!/<!--[\s\S]*id="hwcheck-custom"[\s\S]*?-->/.test(html.slice(cardAt, planAt + 40)),
    "计划容器落在注释里了 —— 那等于没有这个控件");
});

test("ui 接线：载荷 → 计划容器 + 接线区（fx 单源，不手拼 HTML）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  for (const fn of ["hwcheckCustomState(", "hwcheckCustomPlanHTML(", "hwcheckCustomWiringHTML("]) {
    assert.ok(ui.includes(fn), "ui 应调用 fx 的 " + fn);
  }
  assert.ok(ui.includes('$("hwcheck-custom")'), "计划容器要有渲染落点");
  assert.ok(!ui.includes("<span class=\"hwcheck-section-tag"),
    "ui 不得手拼标注（标注词单源在服务端载荷 + fx）");
});

// ---------------------------------------------------------------------------
// 工单 hwcheck-unknown-device/06：自建件也进命令台（字符由服务端分配、页面照渲染）
//
// 载荷形状与后端 `console_payload` 一致：自建件那几行**多两个键**（`tag` 标注词 /
// `name` 人读名），库内件那几行一个字不动。前端按"有没有 `tag`"分两种画法
// （缺字段 = 库内件），不在这里判"哪个字符是谁的"——判据全在服务端。
// ---------------------------------------------------------------------------
const CUSTOM_COMMAND = {
  command: "a",
  slug: "mine_gyro",
  description: "ping 地址 + 读身份寄存器并与期望值比较：板上判 OK / FAIL",
  echo: "测的是：ping 地址 + 读身份寄存器并与期望值比较：板上判 OK / FAIL",
  tag: "自建件",
  name: "卖家给的六轴模块",
};
const CUSTOM_CONSOLE_PAYLOAD = {
  ...CONSOLE_PAYLOAD,
  commands: [...CONSOLE_PAYLOAD.commands, CUSTOM_COMMAND],
};

test("命令表：自建件那行带标注词与名称（字符 / 说明照抄服务端）", () => {
  const out = hwcheckConsoleHTML(CUSTOM_CONSOLE_PAYLOAD);
  assert.ok(out.includes(esc(CUSTOM_COMMAND.command))
    && out.includes(esc(CUSTOM_COMMAND.slug)), out);
  assert.ok(out.includes(esc(CUSTOM_COMMAND.name)), "要认得出手上那件（slug 之外给名称）：" + out);
  assert.ok(out.includes(esc(CUSTOM_COMMAND.tag)), "标注词来自载荷 tag（前端不另写一版）：" + out);
  assert.ok(out.includes(esc(CUSTOM_COMMAND.description)), "复用说明那列（与板上回显同一句）");
  assert.ok(out.indexOf(esc(CONSOLE_PAYLOAD.commands[0].slug)) < out.indexOf(esc(CUSTOM_COMMAND.slug)),
    "库内件在前、自建件在后（与 main.c 里小节的顺序同一条）：" + out);
});

test("命令表：没有自建件那几行时逐字与改动前一致（不许冒出标注词）", () => {
  const out = hwcheckConsoleHTML(CONSOLE_PAYLOAD);
  assert.ok(!out.includes("自建件"), "库内配方那一趟不许出现自建件字样：\n" + out);
  assert.ok(!out.includes("hwcheck-custom-name"), out);
  // 旧载荷（缺 tag / name）= 按库内件画：slug 原样，不编一个徽章出来
  const legacy = hwcheckConsoleHTML({
    ...CONSOLE_PAYLOAD,
    commands: [{ command: "a", slug: "mine_gyro", description: "某一件" }],
  });
  assert.ok(legacy.includes("mine_gyro") && !legacy.includes("自建件"), legacy);
});

test("命令表：自建件的名称是用户随手填的，一律 esc", () => {
  const out = hwcheckConsoleHTML({
    ...CUSTOM_CONSOLE_PAYLOAD,
    commands: [{ ...CUSTOM_COMMAND, name: "<img src=x onerror=alert(1)>" }],
  });
  assert.ok(!out.includes("<img"), out);
  assert.ok(out.includes("&lt;img"), out);
});

test("ui 的空态文案把自建件也算进「哪些能复测」（否则页面在说谎）", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  // 判据落在**整段字面量**上（不截窗口：占位文案本身就是一句话，截窗口改措辞就误红）
  assert.ok(ui.includes("复测命令（库内器件按配方、自建件按它自己的探测小节）"),
    "自建件也有复测命令了，占位文案不能只说「由库内配方决定」");
});



// ---------------------------------------------------------------------------
// 工单 hwcheck-unknown-device/08：回读行上的快照出处标记
// ---------------------------------------------------------------------------

test("计划面板：快照行标出「来自我的器件 <id>」（回读以工程内快照为准）", () => {
  const row = {
    slug: "mine_gyro", name: "卖家给的六轴模块", tag: "custom",
    tag_text: "自建件：按你确认的事实探测", plan: "有寄存器有期望值 → 板上判定",
    address_text: "0x68", register_text: "0x75", expect_text: "0x68",
    echo_only: false, notes: "", probes: true,
    snapshot: true, stored: true,
  };
  const html = hwcheckCustomPlanHTML([row]);
  assert.ok(html.includes("来自我的器件 mine_gyro"), html);
  assert.ok(!html.includes("已从「我的器件」删除"), html);
});

test("计划面板：快照行 + 条目已删除 → 如实说明（不静默、不报错）", () => {
  const row = {
    slug: "mine_gyro", name: "卖家给的六轴模块", tag_text: "自建件：按你确认的事实探测",
    plan: "只 ping", address_text: "0x68", register_text: "", expect_text: "",
    echo_only: false, notes: "", probes: true,
    snapshot: true, stored: false,
  };
  const html = hwcheckCustomPlanHTML([row]);
  const flat = html.replace(/\s+/g, "");
  assert.ok(flat.includes("已从「我的器件」删除"), flat);
  assert.ok(flat.includes("工程内快照"), flat);
});

test("计划面板：现读行（预览 / 08 之前的工程）不画快照标记", () => {
  const row = {
    slug: "mine_gyro", name: "卖家给的六轴模块", tag_text: "自建件：按你确认的事实探测",
    plan: "只 ping", address_text: "0x68", register_text: "", expect_text: "",
    echo_only: false, notes: "", probes: true,
    snapshot: false, stored: true,
  };
  const html = hwcheckCustomPlanHTML([row]);
  assert.ok(!html.includes("来自我的器件"), html);
  assert.ok(html.includes("mine_gyro"), "行本体照旧渲染");
});

test("结构钉：表单收起 / 切换必须清掉资料与草稿（跨件来源污染的正面防线）", () => {
  // 评审 🔴：给 A 抽了草稿 → 改编辑 B → 保存会把 A 的资料 / 草稿写进 B 的条目。
  // 判据 = closeMyDeviceForm / openMyDeviceForm 的编辑分支都清 myMaterial 与 myDraft。
  const source = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  const closeBody = source.match(
    /function closeMyDeviceForm\(\) \{([\s\S]*?)\n\}/);
  assert.ok(closeBody, "ui/hwcheck.js 里应有 closeMyDeviceForm");
  assert.ok(closeBody[1].includes("myMaterial"), "收起表单要清资料原文");
  assert.ok(closeBody[1].includes("myDraft"), "收起表单要清草稿");
  const openBody = source.match(
    /function openMyDeviceForm\(device\) \{([\s\S]*?)\n\}/);
  assert.ok(openBody, "ui/hwcheck.js 里应有 openMyDeviceForm");
  assert.ok(/if \(device\) \{[\s\S]*?myMaterial[\s\S]*?myDraft/.test(openBody[1]),
    "编辑已有器件时不带任何残留的资料 / 草稿");
});

// ---------------------------------------------------------------------------
// 工单 hwcheck-acceptance/04：检测页 → 生成页的衔接（只带器件、不带引脚）
//
// 判据全在 fx 纯函数里：该带哪几件（库内词表）、不该带哪几件（库外自建件 /
// 词表外）各给一句中文理由；页面上那句"引脚不带"永远在。ui 侧只喂数据与落 DOM。
// ---------------------------------------------------------------------------
const LIB_SLUGS = ["led", "ml_mpu6050", "delay", "filter"];
const MY_DEVICES = [
  { id: "mine_gyro", name: "卖家给的六轴模块" },
  { id: "mine_lcd", name: "二手小屏" },
];

test("带入计划：库内件进 carry（保序去重）、自建件进 custom、词表外进 unknown", () => {
  const plan = hwcheckHandoffPlan(
    ["ml_mpu6050", "mine_gyro", "led", "ml_mpu6050", "ghost", "mine_lcd"],
    LIB_SLUGS, MY_DEVICES);
  assert.deepEqual(plan.carry, ["ml_mpu6050", "led"], "库内件按选中顺序、去重");
  assert.deepEqual(plan.custom, [
    { id: "mine_gyro", name: "卖家给的六轴模块" },
    { id: "mine_lcd", name: "二手小屏" },
  ], "自建件带人读名（页面上要点名是哪一件）");
  assert.deepEqual(plan.unknown, ["ghost"], "词表里没有的一件都不许进生成载荷");
});

test("带入计划：一件都没选 = 三类都空（不是错误状态）", () => {
  assert.deepEqual(hwcheckHandoffPlan([], LIB_SLUGS, MY_DEVICES),
    { carry: [], custom: [], unknown: [] });
  assert.deepEqual(hwcheckHandoffPlan(null, null, null),
    { carry: [], custom: [], unknown: [] });
});

test("带入计划：「库外件」的判据是**自建件清单**，不是 id 前缀", () => {
  // mine_ 前缀是 my_devices.DEVICE_ID_PATTERN 的事，页面再判一遍就是第二份实现。
  // 不在自建件清单里的 mine_xxx（已删除 / 换过输入）落 unknown，如实拒收。
  const plan = hwcheckHandoffPlan(["mine_gone"], LIB_SLUGS, MY_DEVICES);
  assert.deepEqual(plan.custom, []);
  assert.deepEqual(plan.unknown, ["mine_gone"]);
});

test("带入计划：slug 同时在词表与自建清单里 → 按库内算（分类顺序钉死）", () => {
  const plan = hwcheckHandoffPlan(["led"], LIB_SLUGS, [{ id: "led", name: "撞名的自建件" }]);
  assert.deepEqual(plan.carry, ["led"]);
  assert.deepEqual(plan.custom, []);
});

test("带入块：可带时按钮可点、点名要带哪几件；不可带时按钮置灰（不是点了没反应）", () => {
  const on = hwcheckHandoffHTML(hwcheckHandoffPlan(["led", "delay"], LIB_SLUGS, []), {});
  assert.ok(on.includes("data-hwcheck-handoff"), on);
  assert.ok(!on.includes("data-hwcheck-handoff disabled"), "有可带的件就不该置灰：" + on);
  assert.ok(on.includes("把这 2 件带进生成页"), on);
  assert.ok(on.includes("led") && on.includes("delay"), "要点名是哪几件：" + on);
  assert.ok(on.includes("已选过的不会重复加"), "说清与生成页既有选择的关系：" + on);

  const off = hwcheckHandoffHTML(
    hwcheckHandoffPlan(["mine_gyro"], LIB_SLUGS, MY_DEVICES), {});
  assert.ok(off.includes("data-hwcheck-handoff disabled"), "没有可带的就置灰：" + off);
  assert.ok(off.includes("都带不过去"), "置灰必须带理由（不让人对着灰按钮猜）：" + off);
});

test("带入块：一件都没选时的空态（不是「点了没反应」，也不是错误）", () => {
  const out = hwcheckHandoffHTML(hwcheckHandoffPlan([], LIB_SLUGS, []), {});
  assert.ok(out.includes("还没选器件"), out);
  assert.ok(out.includes("data-hwcheck-handoff disabled"), out);
});

test("带入块：「引脚不带」与「自动消解过的线也不带」两句永远在（与有没有取到接线表无关）", () => {
  const plan = hwcheckHandoffPlan(["led"], LIB_SLUGS, []);
  for (const opts of [{}, { pinFixes: 0 }, { pinFixes: 2 }]) {
    const out = hwcheckHandoffHTML(plan, opts);
    assert.ok(out.includes("只带器件、不带引脚"), JSON.stringify(opts) + "：" + out);
    assert.ok(out.includes("引脚到生成页第 7 步再配"), out);
    // 接线表还没取到时（pinFixes 恒 0）也**不许**把"自动移开过的线"说没了：
    // 那张表是异步来的，而"不替用户做这个决定"这句话与它取没取到无关。
    assert.ok(out.includes("不是你的选择"), JSON.stringify(opts) + "：" + out);
  }
  const plain = hwcheckHandoffHTML(plan, {});
  assert.ok(plain.includes("（如果有）"), "没数的时候如实说「如果有」：" + plain);
  assert.ok(!plain.includes("处默认脚冲突"), "没数就不许编一个处数：" + plain);

  const moved = hwcheckHandoffHTML(plan, { pinFixes: 2 });
  assert.ok(moved.includes("自动移开了 2 处默认脚冲突"), moved);
  assert.ok(moved.includes("那几根也不带过去"), moved);
});

test("带入块：库外自建件逐件给理由（点名 + 为什么不带）", () => {
  const out = hwcheckHandoffHTML(
    hwcheckHandoffPlan(["led", "mine_gyro"], LIB_SLUGS, MY_DEVICES), {});
  assert.ok(out.includes("卖家给的六轴模块"), "要认得出是哪一件（给人读名）：" + out);
  assert.ok(out.includes("mine_gyro"), out);
  assert.ok(out.includes("不在模块库里"), out);
  assert.ok(out.includes("不进 slugs"), "理由要说到点上（生成链不认它）：" + out);
  // 「我的器件」里没选的那些不出现（理由只针对选中的）
  assert.ok(!out.includes("二手小屏"), out);
});

test("带入块：既不在词表也不在自建件清单的一律拒收，且两个成因都说（不武断说「已删除」）", () => {
  const out = hwcheckHandoffHTML(
    hwcheckHandoffPlan(["ghost"], LIB_SLUGS, MY_DEVICES), {});
  assert.ok(out.includes("ghost"), out);
  assert.ok(out.includes("没有带过去"), out);
  // 两份清单各自读失败时都是空集——那时说"这件已经被删了"是句假话（双轴评审）
  assert.ok(out.includes("模块库清单里"), out);
  assert.ok(out.includes("「我的器件」里"), out);
  assert.ok(out.includes("没读出来"), "要给「清单可能没读到」这个成因：" + out);
  assert.ok(out.includes("已经删了"), "另一个成因也要给：" + out);
  assert.ok(out.includes("生成时被拒"), "说清为什么不硬塞（生成链不认）：" + out);
});

test("带入块：两个栏目平台不一致时提前讲明（展示名取自平台清单；一致就不出这句）", () => {
  const platforms = [
    { id: "stm32", name: "STM32F103C8T6 最小系统板 · Keil5" },
    { id: "mspm0", name: "地猛星 MSPM0G3507 · CCS" },
  ];
  const plan = hwcheckHandoffPlan(["led"], LIB_SLUGS, []);
  const same = hwcheckHandoffHTML(plan, { platforms, from: "mspm0", to: "mspm0" });
  assert.ok(!same.includes("检测页选的是"), "平台一致就不许编一句：" + same);
  const diff = hwcheckHandoffHTML(plan, { platforms, from: "mspm0", to: "stm32" });
  assert.ok(diff.includes("检测页选的是"), diff);
  assert.ok(diff.includes("地猛星 MSPM0G3507 · CCS"), "展示名单源 = 平台清单：" + diff);
  assert.ok(diff.includes("STM32F103C8T6 最小系统板 · Keil5"), diff);
  assert.ok(diff.includes("按生成页的平台校验"), diff);
  const half = hwcheckHandoffHTML(plan, { platforms, from: "mspm0", to: "" });
  assert.ok(!half.includes("检测页选的是"), "生成页还没选平台时不预告（那是那边的提示）：" + half);
});

test("带入块：自建件名称是用户随手填的，一律 esc", () => {
  const out = hwcheckHandoffHTML(
    hwcheckHandoffPlan(["mine_x"], LIB_SLUGS,
      [{ id: "mine_x", name: "<img src=x onerror=alert(1)>" }]), {});
  assert.ok(!out.includes("<img"), out);
  assert.ok(out.includes("&lt;img"), out);
});

test("并入判据：不重复加、保持原顺序，且如实回报哪几件本来就在", () => {
  assert.deepEqual(
    hwcheckHandoffMerge(["ai_rec"], ["led", "ai_rec", "led", "delay"]),
    { selected: ["ai_rec", "led", "delay"], added: ["led", "delay"], already: ["ai_rec"] },
    "重复的入参只算一次，已经选过的那件进 already（不进 added）");
  assert.deepEqual(hwcheckHandoffMerge([], ["led"]),
    { selected: ["led"], added: ["led"], already: [] });
  // 一件都没带（第二次点同一个按钮）= 选择集**一个字节不动**（不许把已选的洗掉）
  const same = hwcheckHandoffMerge(["led"], ["led"]);
  assert.deepEqual(same, { selected: ["led"], added: [], already: ["led"] });
  // 坏入参（null / 空串）不制造一个空 slug
  assert.deepEqual(hwcheckHandoffMerge(null, [null, "", "led", "led"]),
    { selected: ["led"], added: ["led"], already: [] });
});

test("回报文案：带了几件 / 几件本来就在 / 引脚那句恒在（单源在 fx）", () => {
  const both = hwcheckHandoffResultText(["led", "delay"], ["ai_rec"]);
  assert.ok(both.includes("已带进生成页 2 件：led、delay"), both);
  assert.ok(both.includes("另有 1 件本来就在工程里：ai_rec"), both);
  assert.ok(both.includes(hwcheckHandoffPinNote()), both);
  const none = hwcheckHandoffResultText([], ["led"]);
  assert.ok(!none.includes("已带进生成页"), "一件都没新加就不许说带过去了：" + none);
  assert.ok(none.includes("本来就在工程里"), none);
  assert.ok(none.includes(hwcheckHandoffPinNote()), none);
  // 引脚那一句**唯一出处**：块里那句与回报那句都以它开头——改口径只改 hwcheckHandoffPinNote
  const note = hwcheckHandoffPinNote();
  assert.ok(note.includes("只带器件、不带引脚"), note);
  assert.ok(note.includes("第 7 步"), note);
  const block = hwcheckHandoffHTML(hwcheckHandoffPlan(["led"], LIB_SLUGS, []), {});
  assert.ok(block.includes(note), "块里那句要含同一份文案：" + block);
});

test("结构钉：检测页有带入块容器（在卡片正文里，不在注释里）", () => {
  const at = html.indexOf('id="hwcheck-handoff"');
  assert.ok(at > 0, "缺少带入块容器 #hwcheck-handoff");
  const cardAt = html.lastIndexOf('<div class="card">', at);
  assert.ok(cardAt > 0 && cardAt < at, "找不到带入块所在的卡片");
  assert.ok(!/<!--[\s\S]*id="hwcheck-handoff"[\s\S]*?-->/.test(html.slice(cardAt, at + 40)),
    "带入块容器落在注释里了 —— 那等于没有这个控件");
  // 与它管的那个选择集在同一张卡里（器件清单）：chips 之后、保存位置之前
  const chipsAt = html.indexOf('id="hwcheck-device-chips"');
  const parentAt = html.indexOf('id="hwcheck-parent"');
  assert.ok(chipsAt < at && at < parentAt,
    `带入块应排在已选 chips 之后、保存位置之前：${chipsAt} / ${at} / ${parentAt}`);
});

test("结构钉：总口径那句真的被渲染出来（容器在卡片正文里 + ui 调了 fx）", () => {
  // 「函数写好了但没人调用」是这一栏出过的坏法（点了没反应/首帧空白）。
  // 判据两条腿：页面里有落点（且不在注释里）+ ui 在初始化路径上调它。
  const at = html.indexOf('id="hwcheck-unverified-note"');
  assert.ok(at > 0, "缺少总口径容器 #hwcheck-unverified-note");
  const cardAt = html.lastIndexOf('<div class="card">', at);
  assert.ok(cardAt > 0 && cardAt < at, "找不到总口径所在的卡片");
  assert.ok(!/<!--[\s\S]*id="hwcheck-unverified-note"[\s\S]*?-->/.test(html.slice(cardAt, at + 60)),
    "容器落在注释里了 —— 那等于没有这句话");
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  assert.ok(ui.includes('$("hwcheck-unverified-note")'), "总口径要有渲染落点");
  assert.ok(ui.includes("renderHwcheckUnverifiedNote();"), "初始化路径上要真的调它");
  // ui 不许自己再写一遍文案（单源在 fx）。判据**先剥注释**再查：ui 里那句注释引用了
  // 同一句话做说明（不是文案），直接子串匹配会被注释骗过——本仓库既有教训。
  const uiCode = ui.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
  assert.ok(!uiCode.includes("尚未在真板上验证过"), "文案单源在 fx/hwcheck-project.js，ui 只渲染");
});

test("结构钉：ui 侧走 fx（不手拼理由与回报文案）+ 并入入口在生成页那侧", () => {
  const ui = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/hwcheck.js", import.meta.url), "utf8");
  for (const fn of ["hwcheckHandoffPlan(", "hwcheckHandoffHTML(", "hwcheckHandoffResultText("]) {
    assert.ok(ui.includes(fn), "ui 应调用 fx 的 " + fn);
  }
  assert.ok(ui.includes('$("hwcheck-handoff")'), "带入块要有渲染落点");
  // 文案（理由 + 回报）单源在 fx：ui 不许再写一遍（两处各写一遍必然分叉）
  for (const sentence of ["不在模块库里", "没有带过去", "只带器件、不带引脚",
    "引脚到生成页第 7 步再配", "已带进生成页", "本来就在工程里"]) {
    assert.ok(!ui.includes(sentence), "ui 不得手拼文案：" + sentence);
  }
  // 生成页那侧：selectedSlugs 的唯一写者提供**一个**批量入口（工单 04）。
  // 只钉"这个入口存在、ui 调的是它"（接口面）；"只展开一次 / 回报 added·already"
  // 属行为，判据在 fx 的 hwcheckHandoffMerge 与真浏览器用例里，不在这里数源码。
  const rec = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/generate-recommend.js", import.meta.url),
    "utf8");
  assert.ok(rec.includes("export function addModulesFromHandoff("),
    "ui/generate-recommend.js 应导出 addModulesFromHandoff（selectedSlugs 的唯一写者）");
  assert.ok(ui.includes("addModulesFromHandoff("), "检测页应调这个入口（不自己写状态）");
});

test("结构钉：检测页头副标题如实说明这一栏能做什么（陈旧的最小自检文案已删）", () => {
  const h2 = html.match(/<h2>硬件检测([\s\S]*?)<\/h2>/);
  assert.ok(h2, "找不到检测页头副标题");
  const flat = h2[1].replace(/\s+/g, "");
  // 旧文案说的是「本版先做「板子活着」最小自检」——功能早扩到器件选择 / 配方 /
  // 命令台 / 库外件，留着会让学生以为这一栏测不了器件（核查报告第 6 条）。
  assert.ok(!flat.includes("本版先做"), "陈旧文案还在：" + flat);
  assert.ok(!flat.includes("最小自检"), "陈旧文案还在：" + flat);
  // 能做什么：不逐字钉措辞，钉覆盖面（选平台 / 选器件 → 接线表 / 冲突 → 判通断 →
  // 复测 → 排障）——少说一块就等于回到那次核查里的"说小了"。
  for (const kw of ["不用赛题", "选器件", "接线表", "复测", "排障"]) {
    assert.ok(flat.includes(kw), "副标题应说到「" + kw + "」—— 实际：" + flat);
  }
  // 导航 tab 的 title 是同一处口径（「后续可选器件」是同一句陈旧假设）
  const navBtn = html.match(/<button[^>]*data-tab="hwcheck"[^>]*>/);
  assert.ok(navBtn, "找不到硬件检测的导航按钮");
  assert.ok(!navBtn[0].includes("后续可选器件"), "导航 title 陈旧：" + navBtn[0]);
  assert.ok(navBtn[0].includes("器件"), "导航 title 应说到能选器件：" + navBtn[0]);
});

