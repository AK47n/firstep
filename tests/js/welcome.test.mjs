// tests/js/welcome.test.mjs — 首次欢迎卡纯函数（newcomer-onboarding/03）：
// welcomeMode 四态判定（已选不再显示 > 未配 key > 有草稿 > 精简）、完整卡
// 三步与按钮文案、精简卡一句话、隐藏空串、DOM 无依赖。仿 wiring.test.mjs
// 先例（node:test + assert/strict）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  WELCOME_DISMISS_KEY,
  welcomeMode,
  welcomeCardHTML,
} from "../../src/contest_generator/static/js/fx/welcome.js";

test("welcomeMode 优先级：已选不再显示 → hidden（即使未配 key）", () => {
  assert.equal(
    welcomeMode({ apiConfigured: false, hasDraft: false, dismissed: true }),
    "hidden"
  );
  assert.equal(
    welcomeMode({ apiConfigured: false, hasDraft: true, dismissed: true }),
    "hidden"
  );
});

test("welcomeMode：未配 key（未选不再显示）→ full，无论是否有草稿", () => {
  assert.equal(
    welcomeMode({ apiConfigured: false, hasDraft: false, dismissed: false }),
    "full"
  );
  assert.equal(
    welcomeMode({ apiConfigured: false, hasDraft: true, dismissed: false }),
    "full"
  );
});

test("welcomeMode：已配 key 且有草稿 → hidden（不打扰进行中）", () => {
  assert.equal(
    welcomeMode({ apiConfigured: true, hasDraft: true, dismissed: false }),
    "hidden"
  );
});

test("welcomeMode：已配 key 无草稿 → compact（低打扰）", () => {
  assert.equal(
    welcomeMode({ apiConfigured: true, hasDraft: false, dismissed: false }),
    "compact"
  );
});

test("welcomeCardHTML：hidden 返回空串", () => {
  assert.equal(welcomeCardHTML("hidden"), "");
});

test("welcomeCardHTML：full 含三步引导与三个行动按钮", () => {
  const html = welcomeCardHTML("full");
  assert.match(html, /欢迎使用电赛工程生成器/);
  assert.match(html, /去配置 API key/);
  assert.match(html, /btn-welcome-goto-key/);
  assert.match(html, /检查环境/);
  assert.match(html, /btn-welcome-env-check/);
  assert.match(html, /不再显示/);
  assert.match(html, /btn-welcome-dismiss/);
  assert.match(html, /DeepSeek API key/);
});

test("welcomeCardHTML：compact 一句话，无按钮、不指向不存在元素", () => {
  const html = welcomeCardHTML("compact");
  assert.match(html, /12 步向导/);
  assert.doesNotMatch(html, /和 AI 商量/);
  assert.doesNotMatch(html, /btn-welcome-/);
});

test("WELCOME_DISMISS_KEY 与 spec 一致", () => {
  assert.equal(WELCOME_DISMISS_KEY, "firstep.welcome-dismissed.v1");
});
