// 页签切换绑定守卫：tab 切换逻辑不得绑定到生成页 #step-nav 的按钮
// （bug：曾用 querySelectorAll("nav button") 把 12 个 step-dot + 收起按钮
// 一起绑进页签 handler——点击泡泡时 dataset.tab 为 undefined，
// section.page 全被剥 active → 整页黑屏、下面内容显示不出来）。
//
// **两个取数面都判**（工单 frontend-boot-module/02 重定根时评审抓出来的）：
// 页签分发器现在住在装载根 boot.js，但**案发地是 index.html**——哪天有人把裸选择器写回
// HTML 的内联脚本（或别的宿主位置），只读 boot.js 的守卫看不见。所以：
//   · 裸 `querySelectorAll("nav button")` —— index.html ∪ boot.js 都不许有；
//   · `[data-tab]` 限定选择器 —— 必须在 boot.js（分发器的实际落点）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL("../../src/contest_generator/static/" + rel, import.meta.url), "utf8");
const HOSTS = [["index.html", read("index.html")], ["boot.js", read("js/boot.js")]];
const boot = HOSTS[1][1];

test("页签切换绑定选择器限定 [data-tab]（防回退到裸 nav button）", () => {
  // 裸选择器会把 step-nav 的按钮（.step-dot / #btn-collapse-done）绑进页签逻辑
  for (const [name, src] of HOSTS) {
    assert.ok(
      !/querySelectorAll\(\s*["']nav\s+button["']\)/.test(src),
      `${name} 仍含裸 querySelectorAll("nav button")——会将 step-nav 按钮绑进页签切换`,
    );
  }
  assert.ok(
    boot.includes('querySelectorAll("nav button[data-tab]")'),
    "boot.js 缺少 [data-tab] 限定选择器（绑定与清除两处）",
  );
});

test("step-dot 渲染不含 data-tab 属性（与页签按钮语义隔离）", () => {
  const fxDraft = readFileSync(
    new URL("../../src/contest_generator/static/js/fx/draft.js", import.meta.url),
    "utf8",
  );
  // STEP_DOT 模板里不得出现 data-tab（一旦出现，[data-tab] 守卫也拦不住）
  assert.ok(!/data-tab/.test(fxDraft), "fx/draft.js 的 step-dot 模板含 data-tab");
});
