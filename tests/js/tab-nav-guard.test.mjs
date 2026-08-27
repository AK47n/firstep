// 页签切换绑定守卫：tab 切换逻辑不得绑定到生成页 #step-nav 的按钮
// （bug：曾用 querySelectorAll("nav button") 把 12 个 step-dot + 收起按钮
// 一起绑进页签 handler——点击泡泡时 dataset.tab 为 undefined，
// section.page 全被剥 active → 整页黑屏、下面内容显示不出来）
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

test("页签切换绑定选择器限定 [data-tab]（防回退到裸 nav button）", () => {
  // 裸选择器会把 step-nav 的按钮（.step-dot / #btn-collapse-done）绑进页签逻辑
  assert.ok(
    !/querySelectorAll\(\s*["']nav\s+button["']\)/.test(html),
    "index.html 仍含裸 querySelectorAll(\"nav button\")——会将 step-nav 按钮绑进页签切换",
  );
  assert.ok(
    html.includes('querySelectorAll("nav button[data-tab]")'),
    "index.html 缺少 [data-tab] 限定选择器（绑定与清除两处）",
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
