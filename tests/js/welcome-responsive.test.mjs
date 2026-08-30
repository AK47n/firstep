// tests/js/welcome-responsive.test.mjs — 欢迎卡 compact 入口 + 窄屏响应式守卫
// （工单 ux-walkthrough-02/24）：compact 含主入口（开始做题 / 打开新手指引）且
// ui 层绑定完整（含 goto-key 不被注释吞掉）；≤900px 媒体查询含顶栏分组换行 +
// 生成卡收紧 + 工具栏收窄 + 内容边距（防溢出），且不改全站 .card（不越界）。
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

test("ui 绑定完整：开始做题 + goto-key（full 态主路径不被注释吞掉）", () => {
  assert.match(welcomeUi, /btn-welcome-compact-go/, "ui 绑定开始做题");
  assert.match(welcomeUi, /gotoNavTab\("generate", "problem"\)/, "切生成页 + 聚焦题面");
  // 回归守卫（工单 24 评审抓到）：goto-key 绑定必须独立成行、未被行尾注释吞并
  const gotoKeyLine = welcomeUi.split("\n").find((l) => l.includes("btn-welcome-goto-key"));
  assert.ok(gotoKeyLine, "goto-key 绑定行存在");
  assert.ok(!gotoKeyLine.trimStart().startsWith("//"), "goto-key 绑定未被注释");
  assert.match(gotoKeyLine, /gotoSettingsKey\(\)/, "goto-key 绑定调用完整");
});

test("窄屏 ≤900px 媒体查询：顶栏分组换行 + 生成卡收紧 + 工具栏收窄 + 内容边距；不改全站 .card", () => {
  const narrow = html.match(/基础窄屏响应式[\s\S]*?@media \(max-width: 900px\) \{([\s\S]*?)\n  \}/);
  assert.ok(narrow, "应存在基础窄屏媒体块");
  const css = narrow[1];
  assert.match(css, /\.tab-group \{ flex-wrap: wrap; \}/, "顶栏分组换行");
  assert.match(css, /#tab-generate \.gen-steps > \.card \{ padding: 14px 16px; \}/, "生成卡收紧");
  assert.match(css, /\.lib-toolbar \{ gap: 6px; \}/, "库工具栏收窄");
  assert.match(css, /main \{ padding: 0 12px; \}/, "内容边距减小");
  // 评审整改：全局 .card 收紧属越界（窄屏只保生成区与导航），不得出现
  assert.doesNotMatch(css, /^\s*\.card \{ padding:/m, "不改全站 .card");
});
