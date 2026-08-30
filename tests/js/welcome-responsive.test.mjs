// tests/js/welcome-responsive.test.mjs — 欢迎卡 compact 入口 + 窄屏响应式守卫
// （工单 ux-walkthrough-02/24）：compact 含主入口（开始做题 / 打开新手指引）且
// ui 层绑定；≤900px 媒体查询含 tab-group 换行 + 卡片收紧 + 工具栏收窄（防溢出）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);
const welcomeUi = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/welcome.js", import.meta.url),
  "utf8",
);
const welcomeFx = readFileSync(
  new URL("../../src/contest_generator/static/js/fx/welcome.js", import.meta.url),
  "utf8",
);

test("compact 态：fx 渲染主入口按钮（开始做题 / 打开新手指引）", () => {
  assert.match(welcomeFx, /btn-welcome-compact-go/, "fx 渲染开始做题按钮");
  assert.match(welcomeFx, /btn-welcome-guide/, "compact 复用新手指引按钮（full 路径呼应）");
});

test("compact 态：ui 层绑定开始做题 → 切生成页聚焦赛题原文", () => {
  assert.match(welcomeUi, /btn-welcome-compact-go/, "ui 绑定按钮");
  assert.match(welcomeUi, /gotoNavTab\("generate", "problem"\)/, "切生成页 + 聚焦题面");
});

test("窄屏 ≤900px 媒体查询：顶栏分组换行 + 卡片收紧 + 工具栏收窄 + 内容边距", () => {
  const block = html.match(/@media \(max-width: 900px\) \{[\s\S]*?\.guide-tabs[\s\S]*?\}/);
  // 守卫拆开断言（媒体块可能多处）：找含 tab-group wrap 与卡片收紧的块
  const narrow = html.match(/基础窄屏响应式[\s\S]*?@media \(max-width: 900px\) \{([\s\S]*?)\n  \}/);
  assert.ok(narrow, "应存在基础窄屏媒体块");
  const css = narrow[1];
  assert.match(css, /\.tab-group \{ flex-wrap: wrap; \}/, "顶栏分组换行");
  assert.match(css, /\.card \{ padding: 12px 14px; \}/, "卡片收紧");
  assert.match(css, /#tab-generate \.gen-steps > \.card \{ padding: 14px 16px; \}/, "生成卡收紧");
  assert.match(css, /\.lib-toolbar \{ gap: 6px; \}/, "库工具栏收窄");
  assert.match(css, /main \{ padding: 0 12px; \}/, "内容边距减小");
});
