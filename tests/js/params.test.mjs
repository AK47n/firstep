// params.test.mjs — fx/params.js 参数速调展示纯函数（工单 param-tune/02）：
// 参数表（行渲染 / 默认值 / 失效禁用 / 空态 / 转义）+ 应用结果面板（编译
// 徽章 / diff / 备份回滚 / 烧录行 uid="params"）。
import test from "node:test";
import assert from "node:assert/strict";
import { paramListHTML, paramResultHTML } from "../../src/contest_generator/static/js/fx/params.js";

const SAMPLE = [
  {
    name: "THRESHOLD", label: "循迹阈值", old_value: "800",
    anchor: "#define THRESHOLD 800", unit: "", range_hint: "400-1500",
    valid: true,
  },
  {
    name: "PID_KP", label: "PID 比例系数", old_value: "1.2f",
    anchor: "float pid_kp = 1.2f;", range_hint: "0.5-5",
    valid: true,
  },
];

test("paramListHTML: 行渲染（名称 / 含义 / 默认值 / 建议范围 / 应用按钮）", () => {
  const html = paramListHTML(SAMPLE);
  assert.ok(html.includes("THRESHOLD"));
  assert.ok(html.includes("循迹阈值"));
  assert.ok(html.includes('value="800"'));
  assert.ok(html.includes("400-1500"));
  assert.ok(html.includes('data-param-name="THRESHOLD"'));
  assert.ok(html.includes("改这个并验证"));
  assert.ok(html.includes("PID_KP"));
  assert.ok(html.includes('value="1.2f"'));
});

test("paramListHTML: 失效行禁用 + 「锚已失效」标记", () => {
  const html = paramListHTML([
    { name: "STALE", label: "失效参数", old_value: "10", anchor: "x", valid: false },
  ]);
  assert.ok(html.includes("param-stale"));
  assert.ok(html.includes("disabled"));
  assert.ok(html.includes("锚已失效"));
  assert.ok(!html.includes("改这个并验证"));
});

test("paramListHTML: running 全部禁用（防并发 / 防重入）", () => {
  const html = paramListHTML(SAMPLE, { running: true });
  const inputs = html.match(/class="param-input"/g) || [];
  assert.equal(inputs.length, 2);
  assert.ok(html.includes("disabled"));
});

test("paramListHTML: 空态两分支——未识别引导 / 已识别无参数（评审整改）", () => {
  const html = paramListHTML([]);
  assert.ok(html.includes("data-param-empty"));
  assert.ok(html.includes("识别 main.c 参数"));
  assert.equal(paramListHTML(null), paramListHTML([]));
  const scanned = paramListHTML([], { emptyScan: true });
  assert.ok(scanned.includes("data-param-empty"));
  assert.ok(scanned.includes("未发现可调数值参数"));
  assert.ok(!scanned.includes("识别 main.c 参数"));
});

test("paramListHTML: 转义（名称 / 含义 / 值含引号与尖括号）", () => {
  const html = paramListHTML([
    { name: 'A"B', label: "<危险>", old_value: '1"2', anchor: "x", valid: true },
  ]);
  assert.ok(html.includes("A&quot;B"));
  assert.ok(html.includes("&lt;危险&gt;"));
  assert.ok(html.includes("1&quot;2"));
});

test("paramResultHTML: 结果面板 = 徽章 + 说明 + 备份回滚 + 烧录行 + diff", () => {
  const html = paramResultHTML({
    status: "verified",
    backup_id: "b-2026-1",
    main_diff: { stats: { additions: 1, deletions: 1, hunks: 1 },
                 hunks: [{ title: "THRESHOLD", line: 12,
                           lines: [{ kind: "del", text: "#define THRESHOLD 800" },
                                   { kind: "add", text: "#define THRESHOLD 900" }] }] },
    message: "编译通过",
  }, "C:/proj");
  assert.ok(html.includes("参数修改结果"));
  assert.ok(html.includes("b-2026-1"));
  assert.ok(html.includes("回滚本次参数修改"));
  assert.ok(html.includes("data-backup"));
  assert.ok(html.includes('id="tasks-flash-status-params"'));  // uid="params" 烧录容器
  assert.ok(html.includes("参数效果"));
  assert.ok(html.includes("#define THRESHOLD 900"));
});

test("paramResultHTML: 空载荷 → 空串（防御）", () => {
  assert.equal(paramResultHTML(null), "");
  assert.equal(paramResultHTML(undefined), "");
});

test("paramResultHTML: failed 徽章 + 失败说明（不甩裸报错）", () => {
  const html = paramResultHTML({
    status: "failed", backup_id: "", main_diff: null,
    message: "编译验证未通过",
  }, "");
  assert.ok(html.includes("未通过（编译验证失败）"));
  assert.ok(html.includes("编译验证未通过"));
});
