// multiInstanceModules / instancePayload 纯函数单测（工单 instance-config-deps/01）：
// 依赖带入的多实例模块（led_beep → led）也显示实例卡并随装载发实例清单——后端
// parse_instances 认"选中 ∪ 依赖"全集（照 collect-bindings.test.mjs 先例：从 HTML
// 抽函数体喂 node:test，闭包变量以参数注入，不碰 DOM / fetch）。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const extract = (name) => {
  const match = html.match(new RegExp("function " + name + "[\\s\\S]*?\\n\\}"));
  assert.ok(match, "index.html 中未找到 " + name + " 函数体（改名了？）");
  return new Function("expanded", "instances", "return (" + match[0] + ")");
};
// 照 code-zoom.test.mjs 先例：工厂调用时传参（闭包捕获）→ 返回函数 → 立即执行
const multiInstanceModules = (expandedArg) => extract("multiInstanceModules")(expandedArg)();
const instancePayload = (expandedArg, instancesArg) =>
  extract("instancePayload")(expandedArg, instancesArg)();

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
