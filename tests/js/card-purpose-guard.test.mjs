// tests/js/card-purpose-guard.test.mjs — 12 张步骤卡人话副标题结构护栏
// （工单 newcomer-glossary/02）：静态读 index.html，断言每张步骤卡 h2 后
// 紧跟 <p class="card-purpose">（「这步解决什么」），文案与 spec「卡片副标题」
// 12 句逐字一致；防删防改。仿 nav-tabs-guard.test.mjs 先例。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// spec「卡片副标题」12 句定稿（逐字，含全角标点与半角空格）
const PURPOSES = [
  "把赛题文字贴进来（或传 PDF / Word / 图片自动抽出），这是后面所有步骤的依据。",
  "让 AI 先读一遍题面，把关键信息、评分点和要提醒你的地方整理出来。",
  "选你的板子（STM32 或 MSPM0），决定用哪套工程和工具链。",
  "从参考文件库选套件例程 / 说明书作学习素材，AI 生成时会读它们。",
  "AI 对照题面推荐可复用的驱动模块，你可以勾选 / 调整。",
  "确认最终要进工程的模块，并看清哪些模块在你板子上没验证过。",
  "把模块需要的引脚绑到板子具体引脚上（不配就用默认，也能编译）。",
  "让 AI 生成一份初始化好所有模块的 main.c 草稿。",
  "选保存位置，生成完整可编译工程。",
  "编译报错时在这里看错误、让 AI 自动修。",
  "生成后继续打磨——补答疑修订、任务推进写逻辑、参数速调、交付打包。",
  "把这次生成上下文打包成一段话，方便复制给另一个 AI（可选）。",
];

const RE = /<span class="step-no">(\d+)<\/span>[^<]*<\/h2>\s*<p class="card-purpose">([^<]+)<\/p>/g;

test("12 张步骤卡（step-no 1..12）各恰好一次，且均有 card-purpose 紧随", () => {
  const seen = new Map();
  for (const m of html.matchAll(RE)) {
    const n = Number(m[1]);
    assert.ok(!seen.has(n), "step-no 重复：" + n);
    seen.set(n, m[2]);
  }
  assert.deepEqual([...seen.keys()].sort((a, b) => a - b), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
});

test("step-no 全局恰好 12 个（孤立重复的 step-no 也会被拦）", () => {
  const total = (html.match(/<span class="step-no">/g) || []).length;
  assert.equal(total, 12);
});

test("card-purpose 总数 = 12（无多余/无遗漏）", () => {
  const total = (html.match(/class="card-purpose"/g) || []).length;
  assert.equal(total, 12);
});

test("每句副标题非空且 ≥8 个中文字符", () => {
  for (const m of html.matchAll(RE)) {
    const text = m[2];
    const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length;
    assert.ok(cjk >= 8, `step ${m[1]} 副标题中文不足：${text}`);
  }
});

test("12 句副标题按 1..12 顺序与 spec 定稿逐字一致", () => {
  const got = [...html.matchAll(RE)].map((m) => [Number(m[1]), m[2]]);
  assert.deepEqual(got.map(([n]) => n), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  assert.deepEqual(got.map(([, t]) => t), PURPOSES);
});
