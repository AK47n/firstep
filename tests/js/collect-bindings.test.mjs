// collectBindings 纯函数单测（工单 pin-verdict-seam/01）：validate 与 generate
// 必须发同一份 bindings——校验通过但生成拿到不同绑定会撞 400，故抽成单源纯
// 函数后直测（照 sse-parser.test.mjs 先例：从 HTML 抽取函数体喂 node:test，
// 不碰 DOM / fetch）。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/function collectBindings[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 collectBindings 函数体（改名了？）");
const collectBindings = new Function("return (" + match[0] + ")")();

test("只带仍在选择集内的用户绑定（模块移除后不残留）", () => {
  assert.deepEqual(
    collectBindings(
      ["motor", "huidu"],
      { "motor.MOTOR_A_PWM": "PA6", "removed.GRAY_D1": "PB2" },
      {}
    ),
    { "motor.MOTOR_A_PWM": "PA6" }
  );
});

test("多实例模块（instanceMap[slug] 非空）不再发其角色绑定", () => {
  assert.deepEqual(
    collectBindings(
      ["led", "motor"],
      { "led.LED": "PA15", "motor.MOTOR_A_PWM": "PA6" },
      { led: [{ name: "红灯", variant: "red", pin: "" }] }
    ),
    { "motor.MOTOR_A_PWM": "PA6" }
  );
});

test("无绑定 → 空对象（缺省 = 全默认，不发 bindings 字段）", () => {
  assert.deepEqual(collectBindings(["motor"], {}, {}), {});
});

test("绑定含模块但 instanceMap 无该模块条目 → 照发", () => {
  assert.deepEqual(collectBindings(["led"], { "led.LED": "PA15" }, {}), {
    "led.LED": "PA15",
  });
});
