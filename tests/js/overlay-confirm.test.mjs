// fx/overlay.js 确认弹窗纯件单测（工单 master-library-ui-2/04：共享 confirm
// 工厂的 HTML 纯件，05 全仓库迁移复用）。直接 import，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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

// ---- 就地校验错误槽（工单 code-tree-ops/02 在途盘点补口）----

test("overlayConfirmHTML：含默认隐藏的校验错误槽 data-confirm-error", () => {
  const out = overlayConfirmHTML({ title: "T", message: "M" });
  assert.ok(out.includes('data-confirm-error'));
  assert.ok(out.includes('class="confirm-error error hidden"'));
  assert.ok(out.includes('role="alert"'));
});

test("ui/confirm.js：validate 钩子校验失败 → 不关闭弹窗、错误就地显示", () => {
  // DOM 胶水（ui 层）静态源断言：确认分支先跑 validate，返回消息即 return
  // （不 finish），把消息写进 data-confirm-error 并隐藏态移除。
  const src = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/confirm.js", import.meta.url), "utf8");
  assert.ok(src.includes("validate = null"));
  assert.ok(src.includes("const msg = validate(value);"));
  assert.ok(src.includes("if (msg) { showError(msg); return; }"));
  assert.ok(src.includes('overlay.querySelector("[data-confirm-error]")'));
  assert.ok(src.includes('errorBox.classList.remove("hidden")'));
  // 输入即清错误（用户改名字后提示不再残留）
  assert.ok(src.includes('valueEl.addEventListener("input"'));
});

test("ui/code-tree-ops.js：新建与重命名都挂 validate（非法名不关弹窗）", () => {
  const src = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/code-tree-ops.js", import.meta.url), "utf8");
  const hits = src.split("validate: (value) => treeNameValidate(String(value)).msg").length - 1;
  assert.equal(hits, 2, "新建与重命名各一处 validate");
});
