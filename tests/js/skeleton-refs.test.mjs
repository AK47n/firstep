// skeleton-module-refs 纯函数单测（工单 mainc-codeview-bridge/04）：
// 骨架文本静态提取「模块风格调用」并与已选模块 slug 匹配——合法调用命中 /
// 去重保序 / 关键字与注释字符串内不误收 / 前缀边界 / 无命中空。直接 import fx/skeleton-refs.js。
import test from "node:test";
import assert from "node:assert/strict";
import {
  skeletonModuleRefs, skeletonRefsHTML,
} from "../../src/contest_generator/static/js/fx/skeleton-refs.js";

test("骨架含模块风格调用 → 命中并带去重保序", () => {
  const mainC = [
    "int main(void) {",
    '    led_init(LED_RED);',
    "    adc_init();",
    "    led_write(LED_RED, 1);   // 第二次调用：去重",
    "    motor_init();",
    "    return 0;",
    "}",
  ].join("\n");
  const refs = skeletonModuleRefs(mainC, ["led", "adc", "motor", "beep"]);
  assert.deepEqual(refs, [
    { slug: "led", ident: "led_init" },
    { slug: "adc", ident: "adc_init" },
    { slug: "motor", ident: "motor_init" },
  ]);
});

test("关键字 / 控制流不误收（if / for / while / return）", () => {
  const mainC = [
    "int main(void) {",
    "    for (int i = 0; i < 3; i++) {",
    "        if (led_state()) { while (adc_read() > 10) {} }",
    "        return led_init_x;",
    "    }",
    "}",
  ].join("\n");
  // led_state() 命中（led_ 前缀、非关键字）；if/for/while/return 后随括号均不误报
  assert.deepEqual(skeletonModuleRefs(mainC, ["led", "adc"]), [{ slug: "led", ident: "led_state" }, { slug: "adc", ident: "adc_read" }]);
});

test("注释 / 字符串 / 字符字面量内不误收", () => {
  const mainC = [
    "// led_init(); 注释里的调用",
    '/*\n adc_init();\n*/',
    'const char *s = "led_init()";',
    "char c = 'x';",
    "int main(void) { return 0; }",
  ].join("\n");
  assert.deepEqual(skeletonModuleRefs(mainC, ["led", "adc"]), []);
});

test("前缀边界：slug=pid 不匹配 pidx_init / pid 自身不匹配拼写前缀", () => {
  const mainC = "int main(void){ pidx_init(); pid_set(1); }";
  assert.deepEqual(skeletonModuleRefs(mainC, ["pid"]), [{ slug: "pid", ident: "pid_set" }]);
});

test("无已选模块 / 无调用 → 空数组；空串防御", () => {
  assert.deepEqual(skeletonModuleRefs("led_init();", []), []);
  assert.deepEqual(skeletonModuleRefs("", ["led"]), []);
  assert.deepEqual(skeletonModuleRefs(null, ["led"]), []);
  assert.deepEqual(skeletonModuleRefs("led_init();", ["led", 42, null]), [{ slug: "led", ident: "led_init" }]);
});

test("skeletonRefsHTML：chips 渲染与转义；空 → 空串", () => {
  const html = skeletonRefsHTML([{ slug: "led", ident: "led_init" }, { slug: "beep", ident: "beep_init" }]);
  assert.match(html, /骨架引用的模块/);
  assert.match(html, /data-skeleton-ref="led"/);
  assert.match(html, /data-skeleton-ref="beep"/);
  assert.equal(skeletonRefsHTML([]), "");
  assert.equal(skeletonRefsHTML(null), "");
  const esc = skeletonRefsHTML([{ slug: "a&b", ident: "x" }]);
  assert.match(esc, /a&amp;b/);  // slug 转义
});
