// tests/js/css-tokens.test.mjs — CSS 令牌化守卫（工单 ux-walkthrough-02/20/21）：
// ①:root 定义 --radius-*/--space-*；②可见文本字号无 13.5/10.5/10px 裸值；
// ③border-radius 全部走令牌（var(--radius-*)）或圆形 50%/0（无裸 3/4/6/8/10/12/99/999）；
// ④工具类 .mt-2/4/6/8/.flex-1 已定义。静态标记守卫，直接读 index.html。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

function jsSources() {
  const dir = fileURLToPath(new URL("../../src/contest_generator/static/js/", import.meta.url));
  const out = [];
  const walk = (d) => {
    for (const f of readdirSync(d)) {
      const p = join(d, f);
      if (statSync(p).isDirectory()) walk(p);
      else if (f.endsWith(".js")) out.push(readFileSync(p, "utf8"));
    }
  };
  walk(dir);
  return out.join("\n");
}

test(":root 含令牌 --radius-xs/sm/md/lg/full 与 --space-1..6", () => {
  for (const t of ["--radius-xs", "--radius-sm", "--radius-md", "--radius-lg", "--radius-full",
    "--space-1", "--space-2", "--space-3", "--space-4", "--space-5", "--space-6"]) {
    assert.ok(html.includes(t + ":"), ":root 应定义 " + t);
  }
});

test("可见字号无 13.5 / 10.5 / 10px 裸值（12.5/11/11.5 保留）", () => {
  assert.ok(!/font-size:\s*13\.5px/.test(html), "13.5px 应归并 13px");
  assert.ok(!/font-size:\s*10\.5px/.test(html), "10.5px 应归并 11px");
  assert.ok(!/font-size:\s*10px/.test(html), "10px 应归并 11px");
});

test("border-radius 全走令牌：无裸 3/4/6/8/10/12/99/999px（50% 与 0 保留）", () => {
  const radii = [...html.matchAll(/border-radius:\s*([^;]+);/g)].map((m) => m[1].trim());
  assert.ok(radii.length > 50, "应有足量圆角声明（实际 " + radii.length + "）");
  const bad = radii.filter((v) => /^\d+px$/.test(v) || /^(3|4|6|8|10|12|99|999)px$/.test(v));
  assert.deepEqual(bad, [], "裸圆角值残留：" + bad.join("; "));
  // 其余只允许 var(--radius-*) / 50% / 0
  for (const v of radii) {
    if (v === "50%" || v === "0") continue;
    assert.ok(v.startsWith("var(--radius-"), "未知圆角值：" + v);
  }
  // JS 内联样式模板同样不放过（评审整改：flash/task/generate-recommend/step-state 曾漏网）
  const js = jsSources();
  const jsBad = [...js.matchAll(/border-radius:\s*(3|4|6|8|10|12|99|999)px/g)].map((m) => m[0]);
  assert.deepEqual(jsBad, [], "JS 内联裸圆角值残留：" + jsBad.join("; "));
  assert.ok(!/\bfont-size:\s*10px\b/.test(js), "JS 内联字号 10px 应归 11px（评审整改）");
});

test("工具类 .mt-2/4/6/8 与 .flex-1 已定义", () => {
  for (const cls of [".mt-2", ".mt-4", ".mt-6", ".mt-8", ".flex-1"]) {
    assert.ok(html.includes(cls + " {"), "应定义工具类 " + cls);
  }
});

test("按钮四类（.btn 基类 + 三类形态）已定义且有实际使用", () => {
  for (const cls of [".btn", ".btn-pill--sm", ".btn-pill--md", ".btn-icon"]) {
    assert.ok(html.includes(cls + " {"), "应定义按钮类 " + cls);
  }
  // 三类形态至少各有一个实际元素使用（评审整改：防定义未用 = 死类）
  for (const cls of ["btn-pill--sm", "btn-pill--md", "btn-icon"]) {
    assert.ok(new RegExp('class="[^"]*' + cls).test(html),
      "按钮类 " + cls + " 应至少被一个元素使用");
  }
});

test("主题裸色已令牌化：绿完成族 / 渐变端 / 深字 / 紫端 / 电源 / tok 全族无裸值（仅允许出现在令牌定义行）", () => {
  for (const bare of ["#34d399", "#059669", "#33dcff", "#00b8de", "#001018",
    "#04170c", "#8b5cf6", "#f59e0b"]) {
    const total = (html.split(bare).length - 1);
    const defs = html.match(new RegExp("--[a-z0-9-]+:\\s*" + bare.replace("#", "\\#") + "(?=;)", "g"));
    const defCount = defs ? defs.length : 0;
    assert.equal(total, defCount,
      "裸色 " + bare + " 应只出现在令牌定义（实际 " + total + " 处，定义 " + defCount + " 处）");
  }
  assert.ok(!/rgba\(0, 212, 255/.test(html), "accent 青 rgba 应走 var(--accent-rgb)");
  assert.ok(!/rgba\(0, 150, 199/.test(html), "亮色 accent rgba 应走 var(--accent-rgb)");
  assert.ok(!/\.tok-(com|str|pre|kw|num|tag|attr|val) \{ color: #[0-9a-f]{6}/.test(html),
    ".tok-* 应走 var(--tok-*) 令牌");
});

test("令牌无自引用循环（评审整改：--accent-hi 等曾被脚本写成 var(自身) → 计算值失效）", () => {
  const tokenLines = [...html.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)];
  for (const m of tokenLines) {
    const name = m[1];
    const value = m[2].trim();
    assert.ok(!value.includes("var(" + name + ")"),
      "令牌 " + name + " 自引用：" + value);
  }
});

test("间距魔法值收敛：margin-top / margin-bottom 无 2/3/5/7/9/10/14px 裸值（1px 发丝线例外）", () => {
  const m = [...html.matchAll(/margin-top:\s*(\d+)px/g)].map((x) => x[1]);
  assert.deepEqual(m, ["1", "1"], "margin-top 仅保留 1px 发丝线（实际 " + m.join(",") + "）");
  const mb = [...html.matchAll(/margin-bottom:\s*(\d+)px/g)].map((x) => x[1]);
  assert.deepEqual(mb, [], "margin-bottom 无裸值残留（实际 " + mb.join(",") + "）");
  const js = jsSources();
  assert.ok(!/\bmargin-bottom:\s*\d+px\b/.test(js), "JS 内联 margin-bottom 应走令牌");
});
