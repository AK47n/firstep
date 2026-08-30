// delivery.test.mjs — fx/delivery.js 交付卡纯函数（工单 delivery-suite/02）：
// 检查结果 / 打包结果渲染（转义 / 未拆解 / 徽章统计）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  deliveryActionsHTML,
  deliveryCheckHTML,
  deliveryPackageHTML,
} from "../../src/contest_generator/static/js/fx/delivery.js";

test("deliveryActionsHTML: 三按钮 + busy 禁用 + 转义（无注入面）", () => {
  const html = deliveryActionsHTML(false);
  assert.ok(html.includes('id="btn-delivery-open"'));
  assert.ok(html.includes('id="btn-delivery-check"'));
  assert.ok(html.includes('id="btn-delivery-package"'));
  assert.ok(!html.includes("disabled"));
  const busy = deliveryActionsHTML(true);
  assert.ok(busy.includes("disabled"));
  assert.equal((busy.match(/disabled/g) || []).length, 3);
});

test("deliveryCheckHTML: 全部完成 → ✅ + 统计行", () => {
  const html = deliveryCheckHTML({
    ok: true,
    plan_present: true,
    stats: { verified: 3, skipped: 1, failed: 0, pending: 0, doing: 0, unverified: 0 },
    incomplete: [],
    message: "已完成 4/4——全部步骤完成，可以打包交付。",
  });
  assert.ok(html.includes("delivery-ok"));
  assert.ok(html.includes("已通过 3"));
  assert.ok(html.includes("已跳过 1"));
  assert.ok(html.includes("未完成 0"));
  assert.ok(html.includes("全部步骤完成"));
});

test("deliveryCheckHTML: 未完成 → ⚠ + 逐条列表（状态徽章 + 转义）", () => {
  const html = deliveryCheckHTML({
    ok: false,
    plan_present: true,
    stats: { verified: 1, skipped: 0, failed: 1, pending: 2, doing: 0, unverified: 1 },
    incomplete: [
      { id: "t2", title: "循迹 <调参>", status: "pending" },
      { id: "t3", title: "PID", status: "failed" },
    ],
    message: "已完成 1/4；还有 3 步未完成",
  });
  assert.ok(html.includes("delivery-warn"));
  assert.ok(html.includes("未完成 4"));  // failed 1 + pending 2 + unverified 1
  assert.ok(html.includes("循迹 &lt;调参&gt;"));
  assert.ok(html.includes("t3"));
  assert.ok(html.includes("失败"));  // taskStatusLabel("failed")
});

test("deliveryCheckHTML: 未拆解清单 → 只有提示行", () => {
  const html = deliveryCheckHTML({
    ok: false,
    plan_present: false,
    stats: null,
    incomplete: [],
    message: "尚未拆解任务清单——可先「拆解任务」或直接打包。",
  });
  assert.ok(html.includes("尚未拆解任务清单"));
  assert.ok(!html.includes("delivery-stat-row"));
  assert.ok(!html.includes("已验证"));
});

test("deliveryCheckHTML: 空结果 → 空串", () => {
  assert.equal(deliveryCheckHTML(null), "");
  assert.equal(deliveryCheckHTML(undefined), "");
});

test("deliveryPackageHTML: zip 路径 + 大小 + 文件数（转义）", () => {
  const html = deliveryPackageHTML({
    zip_path: "C:/desktop/工程-交付-20260101-120000.zip",
    size: 1024,
    files: 12,
    message: "已打包 12 个文件",
  });
  assert.ok(html.includes("delivery-zip"));
  assert.ok(html.includes("工程-交付-20260101-120000.zip"));
  assert.ok(html.includes("1.0 KB"));  // formatSize(1024)
  assert.ok(html.includes("12 个文件"));
});

test("deliveryPackageHTML: 空结果 → 空串", () => {
  assert.equal(deliveryPackageHTML(null), "");
  assert.equal(deliveryPackageHTML({}), "");
});
