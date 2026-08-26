// multiInstanceModules / instancePayload / ensureDefaultInstances 纯函数单测
//（工单 instance-config-deps/01 + instance-config-defaults/01）：依赖带入的多实例
// 模块（led_beep → led）也显示实例卡并随装载发实例清单——后端 parse_instances
// 认"选中 ∪ 依赖"全集。直接 import fx/module.js（迁入后显式参数传 expanded /
// instances）；不碰 DOM / fetch。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  multiInstanceModules, instancePayload, ensureDefaultInstances,
} from "../../src/contest_generator/static/js/fx/module.js";

const led = { slug: "led", multi_instance: { max: 4, variant: 2 } };
const ledBeep = { slug: "led_beep", multi_instance: null };
const dht = { slug: "dht11", multi_instance: null };
// expanded = 依赖展开结果（选中 ∪ 依赖；依赖先于使用者）
const expanded = [ledBeep, led, dht];

test("依赖带入的多实例模块（led_beep → led）也进实例卡", () => {
  assert.deepEqual(multiInstanceModules(expanded, {}), [led]);
});

test("未展开（expanded 空）→ 实例卡模块为空（旧行为：不显示）", () => {
  assert.deepEqual(multiInstanceModules([], {}), []);
});

test("instancePayload：只带 multi_instance 且配了 ≥1 实例的模块（含依赖带入）", () => {
  assert.deepEqual(
    instancePayload(expanded, {
      led: [{ name: "红", variant: "red", pin: "" }],
    }),
    { led: [{ name: "红", variant: "red", pin: "" }] }
  );
});

test("instancePayload：空清单不发（旧行为）；未展开 → 空对象", () => {
  assert.deepEqual(instancePayload(expanded, { led: [] }), {});
  assert.deepEqual(
    instancePayload([], { led: [{ name: "红", variant: "red", pin: "" }] }),
    {}
  );
});

test("instancePayload：非多实例模块的清单即使有也不发", () => {
  assert.deepEqual(
    instancePayload(expanded, { dht11: [{ name: "温", variant: "", pin: "" }] }),
    {}
  );
});

// ensureDefaultInstances：实例卡首次呈现预填平台默认（工单 instance-config-defaults/01）
const ledWithDefaults = {
  ...led,
  default_instances: [
    { name: "红灯", variant: "red", pin: "" },
    { name: "黄灯", variant: "yellow", pin: "" },
    { name: "绿灯", variant: "green", pin: "" },
  ],
};

test("ensureDefaultInstances：键不存在 → 预填平台默认清单", () => {
  const instances = {};
  ensureDefaultInstances([ledBeep, ledWithDefaults], instances);
  assert.deepEqual(instances, {
    led: [
      { name: "红灯", variant: "red", pin: "" },
      { name: "黄灯", variant: "yellow", pin: "" },
      { name: "绿灯", variant: "green", pin: "" },
    ],
  });
});

test("ensureDefaultInstances：键已存在（AI 猜过 / 用户配过）→ 不覆盖", () => {
  const instances = { led: [{ name: "自定义", variant: "red", pin: "PA15" }] };
  ensureDefaultInstances([ledBeep, ledWithDefaults], instances);
  assert.deepEqual(instances, {
    led: [{ name: "自定义", variant: "red", pin: "PA15" }],
  });
});

test("ensureDefaultInstances：用户删空（键在、清单空）→ 不复活默认", () => {
  const instances = { led: [] };
  ensureDefaultInstances([ledBeep, ledWithDefaults], instances);
  assert.deepEqual(instances, { led: [] });
});

test("ensureDefaultInstances：模块无 default_instances → 不填", () => {
  const instances = {};
  ensureDefaultInstances([ledBeep, led, dht], instances);
  assert.deepEqual(instances, {});
});
