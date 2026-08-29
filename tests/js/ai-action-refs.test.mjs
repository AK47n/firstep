// 结构护栏（工单 ai-action-banner/01）：静态断言「AI 行动中」横幅核心件存在
// ——ui/ai-banner.js 导出 aiActionStart/aiActionStop、fx/ai-action.js 导出
// aiActionStep/aiActionBannerLabel、index.html 槽位、预读接入点成对调用。
// 防删防改名。护栏断言含 :not(.hidden) 开关（评审抓到的阻断级坑：单类
// display:flex 会级联盖过 .hidden{display:none}，横幅永不隐藏）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const root = "../../src/contest_generator/static/js/";
const read = (p) => readFileSync(new URL(p, import.meta.url), "utf8");

const bannerSrc = read(root + "ui/ai-banner.js");
const actionSrc = read(root + "fx/ai-action.js");
const html = read("../../src/contest_generator/static/index.html");
const recommendSrc = read(root + "ui/generate-recommend.js");

test("ui/ai-banner.js 导出 aiActionStart / aiActionStop", () => {
  assert.match(bannerSrc, /export function aiActionStart\(label\)/);
  assert.match(bannerSrc, /export function aiActionStop\(\)/);
});

test("fx/ai-action.js 导出 aiActionStep 状态机与 aiActionBannerLabel 文案", () => {
  assert.match(actionSrc, /export function aiActionStep\(state, action\)/);
  assert.match(actionSrc, /export function aiActionBannerLabel\(label\)/);
});

test("index.html 含 #ai-action-banner 槽位与 #ai-action-label", () => {
  assert.match(html, /id="ai-action-banner" class="ai-action-banner hidden" role="status"/);
  assert.match(html, /id="ai-action-label"/);
});

test("index.html 横幅显隐走 :not(.hidden) 开关（防 display 级联盖过 .hidden）", () => {
  assert.match(html, /\.ai-action-banner \{ [^}]*display: none/);
  assert.match(html, /\.ai-action-banner:not\(\.hidden\) \{ display: flex; \}/);
});

test("index.html 横幅 CSS 含 sticky 吸顶与光带动画", () => {
  assert.match(html, /\.ai-action-banner \{ position: sticky; top: var\(--header-h\)/);
  assert.match(html, /@keyframes ai-flow/);
});

test("预读接入点成对调用（start 在请求前 / stop 在 finally）", () => {
  const startAt = recommendSrc.indexOf('aiActionStart("赛题预读")');
  const stopAt = recommendSrc.indexOf("aiActionStop();");
  assert.ok(startAt >= 0, "预读路径缺 aiActionStart");
  assert.ok(stopAt >= 0, "预读路径缺 aiActionStop");
  assert.ok(startAt < stopAt, "start 必须先于 stop");
});
