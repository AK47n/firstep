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

// ===========================================================================
// 检测页排版契约（工单 ui-density/03）
//
// **为什么加在这里、不另起一个文件**：这一族守的就是"取值必须走令牌"（圆角 / margin /
// 字号），字号那条腿属于同一族。02 实测过：本轮我一写裸 `border-radius: 2px` 就被本文件
// 当场判红——那正是它该干的事；把字号另立一个文件，等于把"令牌纪律"劈成两处。
//
// **它挡的坏法**（都是真实发生过的，不是假想）：
//   · 02 在 `#tab-hwcheck` 里写了 `font-size: 22px`（空态图标）——**当场把 01 已勾选的
//     「检测页样式段里不再出现一次性字号」打假**，而当时没有守卫看着这一类；
//   · 04 写了 `#tab-hwcheck .card { padding: 20px 24px }` / `.hwcheck-jump { padding: 5px 12px }`
//     ——数值明明等于 `--space-5/6/3`，裸写之后"间距六档"这句话就不是机器可验的了。
//
// **它不判什么**（边界写清，免得被当成"什么都管"）：不判"好不好看"，不判非令牌取值的
// 多寡（这一页本来就有 9/10/14px 这类细内边距，属既有习惯），只判"该走令牌的走了没有"。
// ===========================================================================

/** 令牌数值集（单源 = `:root` 的 --space-1..6）。 */
const SPACE_TOKEN_VALUES = new Set([4, 8, 12, 16, 20, 24]);

/** 检测页那一面：`#tab-hwcheck` 作用域，或这一栏自己那两个类名前缀。 */
const HWCHECK_SCOPE_RE = /#tab-hwcheck|\.hwcheck-|\.my-device-/;

/**
 * 全站裸 px 字号的**冻结清单**（工单 03 落地那一刻的实况：13 种）。
 * 规矩：**只许减不许增**——新增取值必须先进这张表并写清理由，否则判红。
 * 全站推广（其余 8 页）时逐条摘，条目数本身就是"改造推进到哪了"的尺子。
 */
const FROZEN_FONT_SIZES = new Set([
  "8", "11", "11.5", "12", "12.5", "13", "14", "15", "16", "16.5", "18", "20", "30",
]);

/** 规则块（`选择器 { 声明 }`）：返回 [{ sel, body }]。 */
function cssRules(css) {
  const out = [];
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    out.push({ sel: m[1].replace(/\s+/g, " ").trim(), body: m[2] });
  }
  return out;
}

const inHwcheckScope = (sel) => HWCHECK_SCOPE_RE.test(sel);

/** 检测页那一段里**裸写的 px 字号**（应为空——全部走 `--fs-*`）。 */
function bareFontSizesInHwcheck(css) {
  const out = [];
  for (const { sel, body } of cssRules(css)) {
    if (!inHwcheckScope(sel)) continue;
    for (const m of body.matchAll(/font-size:\s*([0-9.]+)px/g)) out.push(`${sel} → ${m[1]}px`);
  }
  return out;
}

/** 检测页那一段里**等于令牌却裸写**的 padding / margin / gap 值（应为空）。 */
function bareTokenSpacesInHwcheck(css) {
  const out = [];
  for (const { sel, body } of cssRules(css)) {
    if (!inHwcheckScope(sel)) continue;
    for (const m of body.matchAll(/(?:padding|margin|gap)(?:-top|-right|-bottom|-left)?:\s*([^;]+);/g)) {
      for (const n of m[1].matchAll(/(\d+)px/g)) {
        if (SPACE_TOKEN_VALUES.has(Number(n[1]))) out.push(`${sel} → ${n[1]}px（应走 --space-*）`);
      }
    }
  }
  return out;
}

/** 全站**裸写的 px 字号**取值集合（用来与冻结清单比）。 */
function bareFontSizesSitewide(css) {
  return [...new Set([...css.matchAll(/font-size:\s*([0-9.]+)px/g)].map((m) => m[1]))];
}

test("工单 03：检测页样式段裸 px 字号 = 0（全部走 --fs-* 令牌）", () => {
  assert.deepEqual(bareFontSizesInHwcheck(html), [],
    "检测页段还有裸 px 字号——02 的 `font-size: 22px` 就是这么把 01 的验收打假的："
    + bareFontSizesInHwcheck(html).join(" ｜ "));
});

test("工单 03：检测页样式段里等于令牌的间距值不许裸写", () => {
  assert.deepEqual(bareTokenSpacesInHwcheck(html), [],
    "这些值等于 --space-* 却裸写，'间距走令牌'就不是机器可验的了："
    + bareTokenSpacesInHwcheck(html).join(" ｜ "));
});

test("工单 03：全站裸字号集合只许减不许增（冻结清单）", () => {
  const added = bareFontSizesSitewide(html).filter((v) => !FROZEN_FONT_SIZES.has(v));
  assert.deepEqual(added, [],
    "出现了冻结清单外的裸字号。要么改用 --fs-* 令牌，要么把它登记进 FROZEN_FONT_SIZES "
    + "并写清为什么非它不可：" + added.join(", "));
});

test("工单 03 合成红证：三条腿各自都判得红（防'永远绿'的守卫）", () => {
  // ① 检测页段塞一个越界字号（锚点取自真实源码；锚变了就当场报——不让自检静默空转）
  const fontAnchor = "#tab-hwcheck .card h2 { font-size: var(--fs-page);";
  assert.ok(html.includes(fontAnchor), `锚点变了（${fontAnchor}）—— 这条自检会静默空转`);
  const badFont = html.replace(fontAnchor, "#tab-hwcheck .card h2 { font-size: 19px;");
  assert.equal(bareFontSizesInHwcheck(badFont).length, 1, "越界字号没被判出");
  // ② 把卡片内边距改回裸写
  const spaceAnchor = "padding: var(--space-5) var(--space-6);";
  assert.ok(html.includes(spaceAnchor), `锚点变了（${spaceAnchor}）—— 这条自检会静默空转`);
  const badSpace = html.replace(spaceAnchor, "padding: 20px 24px;");
  assert.equal(bareTokenSpacesInHwcheck(badSpace).length, 2, "裸的令牌值没被判出（应报 20 与 24 两处）");
  // ③ 全站新字号
  const newFontAnchor = ".muted { color: var(--muted); font-size: 12px; }";
  assert.ok(html.includes(newFontAnchor), `锚点变了（${newFontAnchor}）—— 这条自检会静默空转`);
  const badNew = html.replace(newFontAnchor, ".muted { color: var(--muted); font-size: 13.75px; }");
  assert.deepEqual(bareFontSizesSitewide(badNew).filter((v) => !FROZEN_FONT_SIZES.has(v)),
    ["13.75"], "冻结清单外的新字号没被判出");
  // ④ 复原后转绿（三条腿都回到空/子集）
  assert.deepEqual(bareFontSizesInHwcheck(html), []);
  assert.deepEqual(bareTokenSpacesInHwcheck(html), []);
  assert.deepEqual(bareFontSizesSitewide(html).filter((v) => !FROZEN_FONT_SIZES.has(v)), []);
});
