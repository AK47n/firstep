// flash.test.mjs — fx/flash.js 烧录展示纯函数（工单 flash-deploy/02）：
// 忙碌文案（探针名分平台）/ 结果行（成功 / 失败 / 空载荷）/ 指引卡 /
// 输出明细 / 命令复制行。
import test from "node:test";
import assert from "node:assert/strict";
import {
  flashBusyText, flashResultHTML, flashGuideHTML,
  flashOutputHTML, flashCommandHTML, flashPanelHTML, flashContainer,
} from "../../src/contest_generator/static/js/fx/flash.js";

test("flashBusyText: 平台 → 探针名（mspm0=XDS110 / stm32=ST-Link）", () => {
  assert.ok(flashBusyText("mspm0").includes("XDS110"));
  assert.ok(flashBusyText("mspm0").includes("勿拔线"));
  assert.ok(flashBusyText("stm32").includes("ST-Link"));
  assert.ok(flashBusyText("").includes("烧录中"));
});

test("flashResultHTML: 成功 → ✓ 已烧录 + 工具 + 固件 + 命令复制", () => {
  const html = flashResultHTML({
    ok: true,
    message: "烧录成功：OpenOCD（ST-Link）（3.2s）",
    tool: { display: "OpenOCD（ST-Link）" },
    firmware: "C:/proj/user/Objects/proj.hex",
    output: "wrote 8192 bytes",
    command_text: "openocd -f interface/stlink.cfg -c \"program C:/proj/proj.hex verify reset exit\"",
    duration: 3.2,
  });
  assert.ok(html.includes("✓ 已烧录"));
  assert.ok(html.includes("烧录成功"));
  assert.ok(html.includes("OpenOCD"));
  assert.ok(html.includes("proj.hex"));
  assert.ok(html.includes("查看烧录输出（尾 40 行）"));
  assert.ok(html.includes("wrote 8192 bytes"));
  assert.ok(html.includes("btn-flash-copy-cmd"));
});

test("flashResultHTML: 失败 → ✗ + 排查提示 + 输出明细 + 超时标注", () => {
  const html = flashResultHTML({
    ok: false,
    message: "烧录失败（退出码 1）：工具报错见下方输出——常见排查：探针未接 / 目标板未供电 / 板子在 DFU/ISP 状态",
    output: "Error: target not found",
    command_text: "st-flash write C:/proj/proj.hex 0x08000000",
    exit_code: 1,
  });
  assert.ok(html.includes("✗ 烧录未成功"));
  assert.ok(html.includes("常见排查"));
  assert.ok(html.includes("Error: target not found"));
  assert.ok(html.includes("st-flash write"));
  assert.ok(!html.includes("时间"));
});

test("flashResultHTML: 超时 → 超时标注", () => {
  const html = flashResultHTML({
    ok: false, timed_out: true, message: "烧录超时（180s）", output: "",
  });
  assert.ok(html.includes("超时"));
});

test("flashResultHTML: 空载荷 → 空串（防御）", () => {
  assert.equal(flashResultHTML(null), "");
  assert.equal(flashResultHTML(undefined), "");
});

test("flashGuideHTML: 指引卡带中文引导（不甩裸报错）", () => {
  const html = flashGuideHTML("未找到固件产物（user/Objects/*.hex）——请先完成编译再烧录");
  assert.ok(html.includes("烧录未就绪"));
  assert.ok(html.includes("请先完成编译再烧录"));
  assert.ok(html.includes("btn-flash-goto-settings"));  // 设置页跳转按钮（spec 前端决策）
});

test("flashOutputHTML: 空输出 → 空串；非空 → 可折叠明细", () => {
  assert.equal(flashOutputHTML(""), "");
  assert.equal(flashOutputHTML(null), "");
  const html = flashOutputHTML("wrote 8192 bytes");
  assert.ok(html.includes("<details"));
  assert.ok(html.includes("wrote 8192 bytes"));
});

test("flashCommandHTML: 空 → 空串；非空 → 命令 + 复制按钮 data-cmd", () => {
  assert.equal(flashCommandHTML(""), "");
  const html = flashCommandHTML("openocd -f interface/stlink.cfg -c \"program x.hex verify reset exit\"");
  assert.ok(html.includes("命令："));
  assert.ok(html.includes("openocd -f interface/stlink.cfg"));
  assert.ok(html.includes('data-cmd="openocd -f interface/stlink.cfg'));
  assert.ok(html.includes(">复制<"));
});

test("flashContainer: uid → 容器 id 契约（缺省 result / 参数化 task.id）", () => {
  assert.deepEqual(flashContainer("t1"), {
    uid: "t1", statusId: "tasks-flash-status-t1", resultId: "tasks-flash-result-t1",
  });
  // 缺省 uid = "result"（任务执行结果面板哨兵；与 flashPanelHTML 同源）
  assert.deepEqual(flashContainer(), {
    uid: "result", statusId: "tasks-flash-status-result", resultId: "tasks-flash-result-result",
  });
});

test("flashPanelHTML: dir 空 → 空串；非空 → 按钮 + 状态位 + 结果容器（uid 参数化）", () => {
  assert.equal(flashPanelHTML(""), "");
  assert.equal(flashPanelHTML(null), "");
  const html = flashPanelHTML("C:/proj");
  assert.ok(html.includes('data-dir="C:/proj"'));
  assert.ok(html.includes("烧录到板子"));
  // 缺省 uid = "result"（任务执行结果面板既有调用不传即兼容）
  assert.ok(html.includes('id="tasks-flash-status-result"'));
  assert.ok(html.includes('id="tasks-flash-result-result"'));
  assert.ok(html.includes('data-task-flash="result"'));
  // uid 参数化：任务卡独立容器（uid = task.id，多卡并存不冲突）
  const card = flashPanelHTML("C:/proj", "t1");
  assert.ok(card.includes('id="tasks-flash-status-t1"'));
  assert.ok(card.includes('id="tasks-flash-result-t1"'));
  assert.ok(card.includes('data-task-flash="t1"'));
});
