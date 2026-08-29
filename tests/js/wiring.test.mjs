// tests/js/wiring.test.mjs — 任务卡接线图渲染纯件（task-wiring-diagram/03）：
// 高亮线解析（命中行 / 端子 label 匹配 / 板内直连 / 非法丢弃 / 去重）/ 全量线 /
// SVG 结构（端子盒齐全、每线一条边、高亮与淡显类名）/ 电源配色 / 折叠开关 /
// 空态与全量转义。仿 resource-board.test.mjs 先例（node:test + assert/strict）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  isPowerKind,
  highlightWiringLines,
  wiringAllLines,
  wiringDiagramHTML,
} from "../../src/contest_generator/static/js/fx/wiring.js";

const board = {
  name: "STM32F103C8T6 最小系统板（蓝药丸）",
  platform: "stm32",
  pcb_color: "rgba(0,150,200,.05)",
  pins: [
    { name: "PA0", kind: "io", x: 0, y: 0 },
    { name: "PB3", kind: "io", x: 1, y: 1 },
    { name: "3V3", kind: "power", x: 1, y: 2 },
    { name: "GND", kind: "gnd", x: 1, y: 3 },
  ],
  landmarks: [{ kind: "usb_typec", edge: "bottom", note: "USB Type-C", label: "Type-C" }],
  fixed: [{ name: "板载 LED", occupies: ["PC13"], note: "" }],
};

const rows = [
  { slug: "key", role: "KEY_START（启动按键）", role_id: "KEY_START", role_label: "启动按键", pin: "PB3", remark: "gpio_in（必接）" },
  { slug: "led", role: "LED_RED", role_id: "LED_RED", role_label: "", pin: "PA0", remark: "gpio_out" },
];

test("isPowerKind: power/gnd/reset → true，其余 false", () => {
  assert.equal(isPowerKind("power"), true);
  assert.equal(isPowerKind("gnd"), true);
  assert.equal(isPowerKind("reset"), true);
  assert.equal(isPowerKind("io"), false);
  assert.equal(isPowerKind(undefined), false);
});

test("highlightWiringLines: 命中行用行数据 + 高亮；label 合法为端子名；非法丢弃；去重", () => {
  const entries = [
    { pin: "PB3", target: "KEY_START", note: "注意极性" },   // 命中 role_id
    { pin: "PA0", target: "LED_RED" },                        // 命中通道宏（role_id）
    { pin: "PB3", target: "启动按键" },                        // label 不同时也接受（重复 pin+target 不同 → 画）
    { pin: "PA99", target: "KEY_START" },                     // 幻觉引脚 → 丢
    { pin: "PB3", target: "" },                               // target 空 → 丢
    { pin: "PB3", target: "KEY_START" },                      // 与首条重复 → 去重
  ];
  const lines = highlightWiringLines(board, rows, entries);
  assert.equal(lines.length, 3);
  const first = lines[0];
  assert.equal(first.pin, "PB3");
  assert.equal(first.target, "KEY_START");
  assert.equal(first.label, "key · KEY_START（启动按键）");
  assert.equal(first.remark, "gpio_in（必接）");
  assert.equal(first.note, "注意极性");
  assert.equal(first.hl, true);
  // 板内直连 / 板载资源 / 供电线（未命中行 → 端子名 = target 自身）
  const power = highlightWiringLines(board, rows, [
    { pin: "3V3", target: "板载 LED", note: "供电" },
    { pin: "GND", target: "PA0" },
  ]);
  assert.equal(power.length, 2);
  assert.equal(power[0].label, "板载 LED");
  assert.equal(power[0].power, true);
  assert.equal(power[1].power, true);
  assert.equal(power[1].target, "PA0");
  assert.equal(highlightWiringLines(board, null, null).length, 0);
});

test("highlightWiringLines: 评审整改回归——target=渲染合成串（role）也命中行", () => {
  const lines = highlightWiringLines(board, rows, [
    { pin: "PB3", target: "KEY_START（启动按键）" },  // 照抄展示值（role 合成串）
  ]);
  assert.equal(lines.length, 1);
  assert.equal(lines[0].hl, true);
  assert.equal(lines[0].label, "key · KEY_START（启动按键）");
  assert.equal(lines[0].remark, "gpio_in（必接）");
});

test("wiringAllLines: 缺省全量 = 每行一条；命中行高亮、其余淡显；供电引用线附后", () => {
  const highlight = highlightWiringLines(board, rows, [{ pin: "PB3", target: "KEY_START" }]);
  const all = wiringAllLines(board, rows, highlight);
  assert.equal(all.length, 2);
  assert.equal(all[0].hl, true);       // 命中行高亮
  assert.equal(all[1].hl, false);      // 其余淡显
  // 未命中的引用线（供电）附后
  const withPower = wiringAllLines(board, rows, [
    ...highlight,
    { pin: "3V3", target: "板载 LED", power: true, hl: true },
  ]);
  assert.equal(withPower.length, 3);
  assert.equal(withPower[2].target, "板载 LED");
});

test("wiringDiagramHTML: SVG 结构（端子盒齐全、每线一条边、高亮/淡显类名、电源配色）", () => {
  const wiring = [{ pin: "PB3", target: "KEY_START", note: "注意极性" }];
  const html = wiringDiagramHTML({ board, rows, wiring, showAll: false });
  assert.ok(html.includes("<svg viewBox=\"0 0 "));
  assert.ok(html.includes("接线图"));
  // 每线一条边：1 条高亮路径 + 端子盒
  assert.equal((html.match(/class="wiring-line wiring-hl"/g) || []).length, 1);
  assert.ok(html.includes("wiring-term"));
  assert.ok(html.includes("key · KEY_START（启动按键）"));
  assert.ok(html.includes("gpio_in（必接） · 注意极性"));
  // 板丝印名 + 已画引脚
  assert.ok(html.includes(">PB3<"));
  assert.ok(html.includes(">PA0<"));
  // 电源线独立配色（供电引用）
  const powerHTML = wiringDiagramHTML({
    board, rows, wiring: [{ pin: "3V3", target: "板载 LED" }], showAll: false,
  });
  assert.ok(powerHTML.includes("wiring-power"));
  assert.ok(powerHTML.includes("wiring-dot-power"));
  // 空 rows → 空态文案；全非法 → 空态文案（不崩溃、不空白）
  assert.ok(wiringDiagramHTML({ board, rows: [], wiring: [], showAll: false })
    .includes("本步无接线引用"));
  assert.ok(wiringDiagramHTML({ board, rows, wiring: [{ pin: "PA99", target: "X" }], showAll: false })
    .includes("本步无接线引用"));
  assert.ok(wiringDiagramHTML({ board: null, rows, wiring, showAll: false })
    .includes("板定义缺失"));
});

test("wiringDiagramHTML: 显示全部接线（其余线淡显 + 开关勾选）", () => {
  const wiring = [{ pin: "PB3", target: "KEY_START" }];
  const html = wiringDiagramHTML({ board, rows, wiring, showAll: true });
  assert.equal((html.match(/class="wiring-line wiring-hl"/g) || []).length, 1);
  assert.equal((html.match(/class="wiring-line wiring-dim"/g) || []).length, 1);
  assert.ok(html.includes("data-wiring-toggle checked"));
  assert.ok(html.includes("显示全部接线"));
  const collapsed = wiringDiagramHTML({ board, rows, wiring, showAll: false });
  assert.ok(!collapsed.includes("wiring-dim"));
  assert.ok(!collapsed.includes(" checked"));
});

test("wiringDiagramHTML: 全部转义（板名/行内容/引用含特殊字符）", () => {
  const evilBoard = { ...board, name: "A<b>板 \"x\"" };
  const evilRows = [
    { slug: "<img src=x>", role: "R<1>", role_id: "R<1>", role_label: "", pin: "PA0", remark: "\"r\"" },
  ];
  const html = wiringDiagramHTML({
    board: evilBoard, rows: evilRows,
    wiring: [{ pin: "PA0", target: "R<1>", note: "<i>极性</i>" }], showAll: false,
  });
  assert.ok(!html.includes("<img src=x>"));
  assert.ok(html.includes("&lt;img src=x&gt;"));
  assert.ok(!html.includes("A<b>"));
  assert.ok(html.includes("A&lt;b&gt;板"));
  assert.ok(!html.includes("R<1>"));
  assert.ok(html.includes("R&lt;1&gt;"));
  assert.ok(!html.includes("<i>极性</i>"));
  assert.ok(html.includes("&lt;i&gt;极性&lt;/i&gt;"));
});
