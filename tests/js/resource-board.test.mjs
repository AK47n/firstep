// tests/js/resource-board.test.mjs — 资源总览板图视角纯件（resource-overview-polish/02）：
// 任务配色分配 / 工具栏 / 板图 SVG（引脚着色 + 冲突环 + 悬停 title）/ 整块 HTML
//（图例 + 不在板上资源 chips）/ 空态与转义。
import test from "node:test";
import assert from "node:assert/strict";
import {
  RESOURCE_TASK_COLORS, resourceTaskColorMap, resourcesToolbarHTML,
  resourceBoardSVG, resourceBoardHTML,
} from "../../src/contest_generator/static/js/fx/resource-board.js";

const board = {
  name: "地猛星 MSPM0G3507",
  platform: "mspm0",
  pcb_color: "rgba(63,185,80,.05)",
  pins: [
    { name: "PA0", kind: "io", x: 0, y: 0 },
    { name: "PA1", kind: "io", x: 0, y: 1 },
    { name: "PB9", kind: "io", x: 1, y: 8 },
    { name: "PA12", kind: "io", x: 1, y: 16 },
    { name: "GND", kind: "gnd", x: 1, y: 0 },
  ],
  landmarks: [{ kind: "usb_typec", edge: "bottom", note: "USB Type-C", label: "Type-C" }],
};

const groups = {
  pins: [
    { names: ["PA0"], users: [{ id: "t1", title: "循迹" }], conflict: false },
    { names: ["PA12", "PB9"], users: [{ id: "t1", title: "循迹" }, { id: "t2", title: "显示" }], conflict: true },
  ],
  other: [{ names: ["TIMG0"], users: [{ id: "t2", title: "显示" }], conflict: false }],
  soft: [{ names: ["xunji"], users: [{ id: "t2", title: "显示" }] }],
};

test("RESOURCE_TASK_COLORS: 12 色循环板（与配置引脚 MODULE_COLORS 同值）", () => {
  assert.equal(RESOURCE_TASK_COLORS.length, 12);
  assert.ok(RESOURCE_TASK_COLORS.every((c) => /^#[0-9a-f]{6}$/i.test(c)));
});

test("resourceTaskColorMap: 任务按出现顺序循环分配（groups 直传 / plan 自动聚合）", () => {
  const m = resourceTaskColorMap(groups);
  assert.equal(m.get("t1"), RESOURCE_TASK_COLORS[0]);
  assert.equal(m.get("t2"), RESOURCE_TASK_COLORS[1]);
  assert.equal(m.size, 2);
  // plan 路径：t1 先出现（PA0 在 t1 更早）
  const m2 = resourceTaskColorMap({
    tasks: [
      { id: "t1", title: "循迹", resources: ["PA0"] },
      { id: "t2", title: "显示", resources: ["PA0"] },
    ],
  });
  assert.equal(m2.get("t1"), RESOURCE_TASK_COLORS[0]);
  assert.equal(m2.get("t2"), RESOURCE_TASK_COLORS[1]);
  assert.equal(resourceTaskColorMap(null).size, 0);
});

test("resourcesToolbarHTML: 列表/板图按钮 + active 高亮 + aria-pressed", () => {
  const list = resourcesToolbarHTML("list");
  assert.ok(list.includes('class="res-view-btn active" data-res-view="list"'));
  assert.ok(list.includes('data-res-view="board"'));
  assert.ok(list.includes('aria-pressed="true"'));
  assert.ok(list.includes('aria-pressed="false"'));
  assert.ok(list.includes("资源总览"));
  const boardHtml = resourcesToolbarHTML("board");
  assert.ok(boardHtml.includes('class="res-view-btn active" data-res-view="board"'));
  assert.ok(boardHtml.includes('data-res-view="list"'));
});

test("resourceBoardSVG: 占用引脚着色/冲突环/悬停 title、空闲灰显、无引脚空串", () => {
  const pinAttr = new Map([
    ["PA0", { color: RESOURCE_TASK_COLORS[0], conflict: false, users: [{ id: "t1", title: "循迹" }] }],
    ["PA12", { color: RESOURCE_TASK_COLORS[0], conflict: true, users: [{ id: "t1", title: "循迹" }, { id: "t2", title: "显示" }] }],
  ]);
  const svg = resourceBoardSVG(board, pinAttr);
  assert.ok(svg.startsWith("<svg viewBox=\"0 0 460 "));
  assert.ok(svg.includes("res-pin-used"));
  assert.ok(svg.includes(">PA0 · t1：循迹<"));
  assert.ok(svg.includes("PA12 · t1：循迹、t2：显示 · ⚠ 多任务共享"));
  assert.ok(svg.includes("res-pin-conflict"));
  // 空闲与固定/电源脚：未占用样式
  assert.ok(svg.includes('class="res-pin-idle"'));
  assert.ok(svg.includes(">GND（固定/电源）<"));
  // 板名/地标转义
  assert.ok(svg.includes("Type-C"));
  assert.equal(resourceBoardSVG({ pins: [] }, pinAttr), "");
  assert.equal(resourceBoardSVG(null, pinAttr), "");
});

test("resourceBoardHTML: 板名/图例/SVG/不在板上资源 chips/空态", () => {
  const html = resourceBoardHTML(board, groups);
  assert.ok(html.includes("地猛星 MSPM0G3507 · 引脚资源占用"));
  assert.ok(html.includes(">t1<"));     // 图例
  assert.ok(html.includes(">t2<"));
  assert.ok(html.includes("⚠ 多任务共享（联调冲突）"));
  assert.ok(html.includes("空闲 IO"));
  assert.ok(html.includes("<svg"));
  // 不在板上的资源：TIMG0（硬件 chip）+ xunji（soft chip）+ 悬停 title
  assert.ok(html.includes("不在板上的资源（外设/中断/软资源）："));
  assert.ok(html.includes(">TIMG0<"));
  assert.ok(html.includes('class="res-chip res-soft" title="t2：显示">xunji<'));
  assert.ok(html.includes('title="t2：显示">TIMG0<'));
  // 空态
  assert.ok(resourceBoardHTML(null, groups).includes("板定义缺失"));
  assert.ok(resourceBoardHTML(board, null).includes("尚无资源标注"));
});

test("resourceBoardHTML: 转义（板名/任务标题/资源名含特殊字符）", () => {
  const evilBoard = { ...board, name: "A<b>板" };
  const evilGroups = {
    pins: [{ names: ["PA0"], users: [{ id: "t1", title: "<img src=x>" }], conflict: false }],
    other: [],
    soft: [{ names: ["X\"Y"], users: [{ id: "t1", title: "循迹" }] }],
  };
  const html = resourceBoardHTML(evilBoard, evilGroups);
  assert.ok(!html.includes("<img src=x>"));
  assert.ok(html.includes("&lt;img src=x&gt;"));
  assert.ok(!html.includes("A<b>板"));
  assert.ok(html.includes("A&lt;b&gt;板"));
  assert.ok(!html.includes("X\"Y<"));
  assert.ok(html.includes("X&quot;Y"));
});
