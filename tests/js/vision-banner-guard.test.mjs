// tests/js/vision-banner-guard.test.mjs — 视觉通道专用横幅守卫（工单 vision-eyes/04
// 在途盘点补口：此前只有主 key 的 settings-banner，视觉未启用没有任何提示）。
//
// 判据单源 = 后端 /api/settings 的 vision_effective（含「DeepSeek 端点留空 key
// 复用主 key」规则，见 webapp.py + vision.effective_vision_api_key），前端只读该
// 字段切换显隐——不在前端重写「复用主 key」规则。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const read = (p) => readFileSync(new URL("../../" + p, import.meta.url), "utf8");
const html = read("src/contest_generator/static/index.html");
const settingsUi = read("src/contest_generator/static/js/ui/settings.js");
const webapp = read("src/contest_generator/webapp.py");

test("index.html：视觉卡内有 vision-banner（默认隐藏）", () => {
  assert.ok(html.includes('id="vision-banner" class="banner hidden"'));
  assert.ok(html.includes("视觉通道当前未启用"));
});

test("ui/settings.js：按后端 vision_effective 切换横幅显隐（判据不重写）", () => {
  assert.ok(settingsUi.includes('$("vision-banner")'));
  assert.ok(settingsUi.includes('classList.toggle("hidden", !!s.vision_effective)'));
});

test("webapp.py：/api/settings 返回 vision_effective（复用主 key 规则单源）", () => {
  assert.ok(webapp.includes('"vision_effective"'));
  assert.ok(webapp.includes("effective_vision_api_key("));
  assert.ok(webapp.includes("vision_configured("));
});
