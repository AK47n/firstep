// cHighlight / cLineCount 纯函数单测（工单 ui-polish-8/01）：
// main.c 语法着色 token 化与行号生成。
import test from "node:test";
import assert from "node:assert/strict";
import { cHighlight, cLineCount } from "../../src/contest_generator/static/js/fx/code.js";

test("行注释 → tok-com", () => {
  const out = cHighlight("// 初始化时钟");
  assert.match(out, /<span class="tok-com">\/\/ 初始化时钟<\/span>/);
});

test("块注释 → tok-com（含换行）", () => {
  const out = cHighlight("/* 多行\n注释 */");
  assert.match(out, /<span class="tok-com">\/\* 多行\n注释 \*\/<\/span>/);
});

test("双引号字符串 → tok-str", () => {
  const out = cHighlight('printf("hello");');
  assert.match(out, /<span class="tok-str">&quot;hello&quot;<\/span>/);
});

test("单引号字符 → tok-str（含转义）", () => {
  const out = cHighlight("char c = '\\n';");
  assert.match(out, /<span class="tok-str">&#39;\\n&#39;<\/span>/);
});

test("关键字 → tok-kw", () => {
  const out = cHighlight("int main(void) { return 0; }");
  assert.match(out, /<span class="tok-kw">int<\/span>/);
  assert.match(out, /<span class="tok-kw">return<\/span>/);
  assert.match(out, /<span class="tok-kw">void<\/span>/);
});

test("注释 / 字符串内的关键字不着色", () => {
  const out = cHighlight('// int return\n"int"');
  assert.doesNotMatch(out, /<span class="tok-kw">int<\/span><span class="tok-kw">return/);
  assert.equal((out.match(/<span class="tok-kw">/g) || []).length, 0);
});

test("数字 → tok-num", () => {
  const out = cHighlight("x = 42; y = 0x1A;");
  assert.match(out, /<span class="tok-num">42<\/span>/);
  assert.match(out, /<span class="tok-num">0x1A<\/span>/);
});

test("行首预处理 → tok-pre", () => {
  const out = cHighlight("#include <ti/devices/msp/msp.h>\nint main;");
  assert.match(out, /<span class="tok-pre">#include &lt;ti\/devices\/msp\/msp.h&gt;<\/span>/);
});

test("非行首 # 不着色为预处理", () => {
  const out = cHighlight("a = b # c;");
  assert.doesNotMatch(out, /tok-pre/);
});

test("HTML 特殊字符转义", () => {
  const out = cHighlight('a < b && c > d');
  assert.ok(out.includes("&lt;"));
  assert.ok(out.includes("&amp;&amp;"));
  assert.ok(out.includes("&gt;"));
  assert.ok(!out.includes("<b"));
});

test("空串 / null / undefined → 空 HTML", () => {
  assert.equal(cHighlight(""), "");
  assert.equal(cHighlight(null), "");
  assert.equal(cHighlight(undefined), "");
});

test("混合真实代码行：token 齐全且顺序不串", () => {
  const out = cHighlight("// 配置\nGPIO_setConfig(GPIO_PORT, GPIO_PIN_0);");
  assert.ok(out.indexOf('tok-com">// 配置<') >= 0);
  assert.ok(out.indexOf("GPIO_setConfig") > out.indexOf("tok-com"));
});

test("函数调用 → tok-fn（关键字后 ( 仍 tok-kw）", () => {
  const out = cHighlight("GPIO_setConfig(GPIO_PORT, GPIO_PIN_0);\nif (x) { helper(); }");
  assert.match(out, /<span class="tok-fn">GPIO_setConfig<\/span>\(/);
  assert.match(out, /<span class="tok-fn">helper<\/span>\(/);
  assert.match(out, /<span class="tok-kw">if<\/span> \(x\)/);
  assert.doesNotMatch(out, /<span class="tok-fn">if<\/span>/);
});

test("函数声明的形参列表 → tok-fn", () => {
  const out = cHighlight("void printNumber(int n) { }");
  assert.match(out, /<span class="tok-fn">printNumber<\/span>\(<span class="tok-kw">int<\/span> n\)/);
});

test("全大写宏常量（含下划线）→ tok-const", () => {
  const out = cHighlight("x = LED_GPIO; y = GPIO_PIN_0;");
  assert.match(out, /<span class="tok-const">LED_GPIO<\/span>/);
  assert.match(out, /<span class="tok-const">GPIO_PIN_0<\/span>/);
});

test("无下划线全大写短词不染为常量（如 A）", () => {
  const out = cHighlight("x = A; y = B + O;");
  assert.doesNotMatch(out, /tok-const/);
});

test("函数名与 ( 之间有空白 → 仍 tok-fn", () => {
  const out = cHighlight("GPIO_setConfig (GPIO_PORT);");
  assert.match(out, /<span class="tok-fn">GPIO_setConfig<\/span> \(/);
});

test("非函数标识符（空格后非 (）不着 tok-fn", () => {
  const out = cHighlight("a + (b);\nx = y;");
  assert.doesNotMatch(out, /tok-fn/);
});

test("#define NAME → NAME tok-const、其余 tok-pre", () => {
  const out = cHighlight("#define LED_GPIO 2\nint x;");
  assert.match(out, /<span class="tok-pre">#define <\/span><span class="tok-const">LED_GPIO<\/span><span class="tok-pre"> 2<\/span>/);
});

test("#include 行仍整行 tok-pre（不误拆）", () => {
  const out = cHighlight("#include <ti/devices/msp/msp.h>");
  assert.match(out, /<span class="tok-pre">#include &lt;ti\/devices\/msp\/msp.h&gt;<\/span>/);
  assert.doesNotMatch(out, /tok-const/);
});

test("cLineCount：空串 → 1 行", () => {
  assert.equal(cLineCount(""), "1");
});

test("cLineCount：3 行 → 1/2/3", () => {
  assert.equal(cLineCount("a\nb\nc"), "1\n2\n3");
});

test("cLineCount：结尾换行 → 空行也算", () => {
  assert.equal(cLineCount("a\n"), "1\n2");
});

test("cLineCount：null / undefined → 1 行", () => {
  assert.equal(cLineCount(null), "1");
  assert.equal(cLineCount(undefined), "1");
});
