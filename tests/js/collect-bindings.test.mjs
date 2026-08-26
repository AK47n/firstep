// collectBindings 纯函数单测（工单 frontend-es-modules/08）：validate 与 generate
// 必须发同一份 bindings——校验通过但生成拿到不同绑定会撞 400，故抽成单源纯
// 函数后直测。直接 import fx/generate.js，不碰 DOM / fetch。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import { collectBindings } from "../../src/contest_generator/static/js/fx/generate.js";

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
