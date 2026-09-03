// fx/overlay.js 确认弹窗纯件单测（工单 master-library-ui-2/04：共享 confirm
// 工厂的 HTML 纯件，05 全仓库迁移复用）。直接 import，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import { overlayConfirmHTML, menuClamp } from "../../src/contest_generator/static/js/fx/overlay.js";

test("overlayConfirmHTML：标题 + 消息 + 危险确认钮 + 取消钮", () => {
  const out = overlayConfirmHTML({
    title: "确认删除？",
    message: "删除后不可恢复。",
    danger: true,
    confirmText: "确认删除",
    cancelText: "取消",
  });
  assert.ok(out.includes("确认删除？"));
  assert.ok(out.includes("删除后不可恢复。"));
  assert.ok(out.includes('class="ref-files-close"'));
  assert.ok(out.includes('class="danger" data-confirm-ok'));
  assert.ok(out.includes("确认删除")); // 确认钮文案
  assert.ok(out.includes('data-confirm-cancel'));
  assert.ok(out.includes("取消"));
});

test("overlayConfirmHTML：默认文案（确认/取消，danger 缺省 true）", () => {
  const out = overlayConfirmHTML({ title: "T", message: "M" });
  assert.ok(out.includes('class="danger" data-confirm-ok'));
  assert.ok(out.includes(">确认</button>"));
  assert.ok(out.includes(">取消</button>"));
});

// ---- 浮层菜单定位钳制（工单 code-editor-refine/06 创建、07 随共享组件归位）----

test("menuClamp：视口内原样 / 右/下溢出钳到贴边（8px 边距）", () => {
  assert.deepEqual(menuClamp(100, 120, 160, 180, 800, 600), { left: 100, top: 120 });
  assert.deepEqual(menuClamp(700, 500, 160, 180, 800, 600), { left: 632, top: 412 });
  assert.deepEqual(menuClamp(-20, -20, 160, 180, 800, 600), { left: 8, top: 8 });
  // 菜单比视口大 → 贴 8px 边（不产生负坐标）
  assert.deepEqual(menuClamp(50, 50, 1200, 900, 800, 600), { left: 8, top: 8 });
});

test("overlayConfirmHTML：safe 模式 = 主钮非危险；extra 透传", () => {
  const out = overlayConfirmHTML({
    title: "T", message: "M", danger: false,
    extra: '<select data-confirm-value><option value="stm32">STM32</option></select>',
  });
  assert.ok(out.includes('class="primary" data-confirm-ok'));
  assert.ok(out.includes('data-confirm-value'));
});

test("overlayConfirmHTML：标题与消息转义（无注入面）", () => {
  const out = overlayConfirmHTML({ title: "<b>x</b>", message: '<img src=1>' });
  assert.ok(out.includes("&lt;b&gt;x&lt;/b&gt;"));
  assert.ok(out.includes("&lt;img src=1&gt;"));
  assert.ok(!out.includes("<b>x</b>"));
  assert.ok(!out.includes("<img src=1>"));
});
