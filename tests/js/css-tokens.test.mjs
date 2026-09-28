// tests/js/css-tokens.test.mjs — CSS 令牌化守卫（工单 ux-walkthrough-02/20/21）：
// ①:root 定义 --radius-*/--space-*；②可见文本字号无 13.5/10.5/10px 裸值；
// ③border-radius 全部走令牌（var(--radius-*)）或圆形 50%/0（无裸 3/4/6/8/10/12/99/999）；
// ④工具类 .mt-2/4/6/8/.flex-1 已定义。
// ⑤排版契约：字号角色表（六档）+ 页面分区表 + 逐页腿 + 进度尺（SITEWIDE_BACKLOG /
//   FROZEN_FONT_SIZES）——见文件下半部分那两段说明块。静态标记守卫，直接读 index.html。
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
// 排版契约：令牌纪律 + 逐页腿（检测页 ui-density/03 → 全站 ui-density-sitewide/01）
//
// **为什么加在这里、不另起一个文件**：这一族守的就是"取值必须走令牌"（圆角 / margin /
// 字号），字号那条腿属于同一族。上一轮 02 实测过：一写裸 `border-radius: 2px` 就被本文件
// 当场判红——那正是它该干的事；把字号另立一个文件，等于把"令牌纪律"劈成两处。
//
// **它挡的坏法**（都是真实发生过的，不是假想）：
//   · 上一轮 02 在 `#tab-hwcheck` 里写了 `font-size: 22px`（空态图标）——**当场把 01 已勾选的
//     「检测页样式段里不再出现一次性字号」打假**，而当时没有守卫看着这一类；
//   · 上一轮 04 写了 `#tab-hwcheck .card { padding: 20px 24px }` / `.hwcheck-jump { padding: 5px 12px }`
//     ——数值明明等于 `--space-5/6/3`，裸写之后"间距六档"这句话就不是机器可验的了。
//
// **它不判什么**（边界写清，免得被当成"什么都管"）：不判"好不好看"，不判"一屏一层描边"，
// 不判非令牌取值的多寡（页面上本来就有 9/10/14px 这类细内边距，属既有习惯），
// 只判"该走令牌的走了没有"。
// ===========================================================================

/** 令牌数值集（单源 = `:root` 的 --space-1..6）。 */
const SPACE_TOKEN_VALUES = new Set([4, 8, 12, 16, 20, 24]);

// ===========================================================================
// 全站推广轮：字号角色表 + 页面分区表 + 逐页腿（工单 ui-density-sitewide/01）
//
// **为什么要有分区表**：上一轮的守卫只有一条腿——`#tab-hwcheck|.hwcheck-|.my-device-`
// （检测页样板那 30 处）。全站还有 12 个页签、356 处裸字号，而"**哪一页还没做、
// 哪一页退化了**"没有任何机器判据——上一轮 02 就是在这个缝里写下 `font-size: 22px`，
// 把 01 已勾选的验收打假的。所以这一轮先立尺子再动手。
//
// **两条进度尺，各自单调**：
//   · **页面尺** `SITEWIDE_BACKLOG`：还没做完的作用域，每 resole 一单摘一条；
//   · **取值尺** `FROZEN_FONT_SIZES`：全站裸字号取值集合——某个取值**在全站彻底消失**
//     才摘得掉，所以它主要在收尾单清零；清零即"全站零裸 px 字号"。
//
// **它不判什么**：不判"好不好看"；不判"一屏一层描边"（一条边框是分组框还是可点控件 /
// 语义告警块，机器判不了——那条靠每单的逐层清单 + 人眼看图）；也不判非令牌取值的多寡。
// ===========================================================================

/**
 * 字号角色表（**单源**）：一档一个角色，改这里 = 改全站台阶。
 * 与 `.scratch/ui-density-sitewide/spec.md` 的「字号角色表」一节必须一致。
 *
 * **相对单位例外（写 `em`，随父级缩放）——两例，都是装饰性字形**（与 spec 同一份口径）：
 * ① `.badge` 邻域那个 8px 上标星号（上标的正确写法本来就是相对的）；
 * ② 编译错误行的 ● 色点 `.code-gutter-line.code-err-line::after`（04 单，`8px → .62em`）
 *    ——gutter 字号是 `--code-font-size`、跟着 Ctrl+滚轮缩放，写死 px 放大后会缩成一个小点。
 * 不进令牌表。本守卫按 **px 取值**判，em 天然不在它射程内：
 * 这条边界是刻意写下的，**不是**给裸 px 留后门（写 `font-size: 8px` 照样判红）。
 */
const FONT_ROLES = [
  ["--fs-page", "20px", "页面 / 卡片标题、弹层大标题"],
  ["--fs-block", "16px", "小节标题、主按钮字、欢迎语标题"],
  ["--fs-body", "14px", "正文 / 表单 / 表格 / 行内主字"],
  ["--fs-note", "13px", "次要说明 / .muted / 时间戳 / 表头"],
  ["--fs-tag", "12px", "徽章 / 标签 / 极小字"],
  ["--fs-icon", "22px", "**大号**装饰图标（空态 emoji）——行内小图标随正文走 --fs-body"],
];

/**
 * **有序分区表**：`[作用域 id, 谓词]`。**页面在前、兜底在后**，第一条命中的赢；
 * 最后一条是 catch-all（`/./`），因此这张表是样式块的一个**全覆盖、不重叠**的划分
 * ——"哪一页归哪一单"因此是单源、可复核的。
 *
 * 谓词按**这族类名是谁渲染的**写（拿 `static/js/**` 里出现的位置核），别按"看着像哪页"猜：
 * 兜底会把猜错的那些悄悄吞进 `shell`，而 `shell` 一旦做完，它们就再没人看着（评审实测：
 * 第一版漏了 `.tok-*`/`.gp-*`/`.rec-*`/`.card-group`/`.proofread-*` 等十余族）。
 * 03 单再审一遍（**按渲染方逐族核过**）：
 *   · `\.recent-` 把**设置页**「最近 LLM 工作流」的 `.recent-wf-*`（渲染方 = `ui/settings.js`）
 *     吞进了生成页 —— 改成 `\.recent-(?!wf-)`，`\.recent-wf-` 挂到 `settings`；
 *   · `\.quick-*`（Ctrl+P 快速打开浮层）渲染方是**代码页**（`ui/quick-open.js` 的
 *     `if (!codeTabActive()) return`）—— 从生成页挪到 `code`；
 *   · `\.topic-` 把**生成页第 2 步**那块预读面板（`#topic-preread-box`，渲染方 =
 *     `ui/generate-recommend.js` + `fx/topic-preread.js`）判给了赛题库 ——
 *     改成 `\.topic-(?!preread)`，`\.topic-preread` 挂到 `generate`。
 *   （类名前缀不是归属判据："这块讲的是赛题"和"这块在赛题库页"是两件事。）
 *
 * 格式固定（`["id", /正则/],` 一行一条，正则里不出现 `/`）：
 * `.scratch/ui-density-sitewide/probe-01-scope-draft.py` 按同一份表解析出读数，
 * 改这里就等于改读数的尺子（两处不一致会当场看出来）。
 */
const PAGE_SCOPES = [
  ["code", /#tab-code|#code-|\.code-|\.codeeditor|\.cx-|\.change-|\.diff-|\.line-|\.tok-|\.quick-/],
  ["master", /#tab-master|\.master-|\.prog-|\.decision|\.distill|\.stepper|\.rel-tag|\.import-platform-field/],
  ["settings", /#tab-settings|\.settings-|\.env-|\.delivery|\.materials-|\.update-|\.disk-|\.recent-wf-/],
  ["changelog", /#tab-changelog|\.release-/],
  ["guide", /#tab-guide|\.guide-|\.glossary/],
  ["library", /#tab-library|\.lib-|\.module-|\.mc-|\.mi-|\.add-|\.file-row/],
  ["reference", /#tab-reference|\.ref-/],
  ["pdf", /#tab-pdf|\.pdf-/],
  ["md", /#tab-md|\.md-/],
  ["topic", /#tab-topic|\.topic-(?!preread)|\.proofread/],
  ["generate", /\.step-|\.task-|\.tasks-|\.res-|\.pin-|\.sugg-|\.ov-|\.score-|\.param|\.group-|\.card-group|\.mainc-|\.revise|\.wiring|\.gen-|\.gp-|\.preread|\.topic-preread|\.recent-(?!wf-)|\.rec-|\.rc-|\.sp-|\.draft-|\.skeleton|\.llm-|\.fix-|\.slug|\.instance-|\.readiness-check/],
  ["hwcheck", /#tab-hwcheck|\.hwcheck-|\.my-device-/],
  ["components", /\.btn|\.badge|\.chip|\.toast|\.item\b|\.spinner|\.wait-|\.service-stopped|\.empty-state|\.es-|\.overlay|\.confirm|\.modal|\.dialog/],
  ["shell", /./],
];

/**
 * **页面尺**：还没做完的作用域。每 resole 一单摘掉对应的一条（合并单一次摘几条）。
 * 摘完 = 全站推广完成——**这张表空掉的时候，"全站一套台阶"才成立**。
 *
 * 已摘：`shell`（工单 01，全局文本基类 + 外壳）、`components`（工单 02，按钮 / 徽章 / chip /
 * 提示条 / 空态 / 弹层外壳）、`generate`（工单 03，生成页：**110** 处裸字号 / **106** 处
 * 裸令牌间距清零 + 24 处内层完整描边改语言——整圈完整描边 53 → 31，31 条全在申报的例外里）、
 * `code`（工单 04，代码页：**66** 处裸字号 / **84** 处取值（64 条声明）裸令牌间距清零，
 * 另把编辑器字号基准 `--code-font-size` 改成从 `--fs-note` 派生、md 预览根字号从 `--fs-body`
 * 派生；整圈完整描边 **24 → 19**，5 处内层盒去框，19 条全在申报的例外里）。
 * （`generate` 的两处计数与本文件头上那句「111 处」差在 `.recent-wf-*` 那一处：它归设置页，
 * 03 单把谓词按渲染方改对之后就不再算在生成页头上。）
 * （`code` 的 66 处里含 **5 处渲染方其实在生成页**（`.code-wrap` / `.code-zoom`，main.c 编辑器
 * 与它的缩放工具条）与 **2 处跨页共享件**（`.diff-*`：代码页 + 生成页都用）—— 谓词按
 * "第一命名页"归了 `code`，04 单把它们就地令牌化、**没有改谓词**（改了会当场把 `generate`
 * 那条腿打红）；它们照样在腿③的射程里（`code` 已完工）。细则见工单 04 的「账」。）
 */
const SITEWIDE_BACKLOG = new Set([
  "master", "settings", "changelog", "guide", "library", "reference",
  "pdf", "md", "topic",
]);

/**
 * 全站裸 px 字号的**冻结清单**（工单 03 落地那一刻的实况：13 种）。
 * 规矩：**只许减不许增**——新增取值必须先进这张表并写清理由，否则判红。
 *
 * **摘条 = 进度尺**：某个取值在**全站彻底消失**之后才摘得掉（摘了它就等于立了"不许再回来"
 * 的闸）。已摘：
 *   · `16`（02 单：`.card h2` → `--fs-page`、`.service-stopped-box h2` → `--fs-page`）
 *   · `30`（02 单：`.empty-state .es-icon` → `--fs-icon`）
 *   · `8`（04 单：代码页 gutter 的 ● 编译错误色点 `8px` → `.62em`——装饰字形随行号缩放；
 *     它是全站最后一处 `8px`，改完实测 0 处）
 */
const FROZEN_FONT_SIZES = new Set([
  "11", "11.5", "12", "12.5", "13", "14", "15", "16.5", "18", "20",
]);

/** 规则块（`选择器 { 声明 }`）：返回 [{ sel, body }]。 */
function cssRules(css) {
  const out = [];
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    out.push({ sel: m[1].replace(/\s+/g, " ").trim(), body: m[2] });
  }
  return out;
}

/** 同一份源码只解析一次（分区表那条自检要按作用域反复取规则，1581 条 × 14 次太慢）。 */
const _rulesCache = new Map();
function cssRulesCached(css) {
  if (!_rulesCache.has(css)) _rulesCache.set(css, cssRules(css));
  return _rulesCache.get(css);
}

/** 去掉选择器**前面**那段块注释（这个样式块里大量规则是"注释 + 选择器"同段写的）。 */
function stripLeadComments(sel) {
  return sel.replace(/^(\/\*[\s\S]*?\*\/\s*)+/, "").trim();
}

/**
 * 规则归谁：分区表里**第一条命中的**作用域（兜底 = 表最后一条，因此恒有归属）。
 *
 * ⚠ **必须先剥掉选择器前面那段注释**（02 单评审抓到的真漏洞）：这文件里大量规则写成
 * 「注释 + 选择器」，注释正文里常提到别的页的类名（`.btn-param-ref` 的注释里写着
 * `.task-dialog-box`）——按原始文本判，规则会被判给注释里那个词命中的作用域，
 * 于是它落到**另一页的腿**上，那一页的"裸字号 = 0"就成了有水分的绿。
 */
function scopeOf(sel) {
  const clean = stripLeadComments(sel);
  for (const [id, re] of PAGE_SCOPES) if (re.test(clean)) return id;
  return PAGE_SCOPES[PAGE_SCOPES.length - 1][0];
}

/** 某个作用域名下的规则（做完了的作用域要逐条过腿）。 */
function rulesInScope(css, id) {
  return cssRulesCached(css).filter(({ sel }) => scopeOf(sel) === id);
}

/** 已完工的作用域（= 分区表里不在进度清单上的那些）；上一轮的检测页走的是这里。 */
function doneScopes() {
  return PAGE_SCOPES.map(([id]) => id).filter((id) => !SITEWIDE_BACKLOG.has(id));
}

/**
 * 分区表的**形状问题**（纯函数，好让"表坏了能不能判出来"有合成红证）。
 * 为什么要判：谓词写错或类名被改名时，那条腿会**静默空转**——它照样绿，
 * 而它本该看着的东西没人看（评审实测：第一版兜底悄悄吞了十余族页面类名）。
 */
function scopeTableProblems(scopes, css) {
  const out = [];
  const ids = scopes.map(([id]) => id);
  if (new Set(ids).size !== ids.length) out.push("作用域 id 重复：" + ids.join(", "));
  const last = scopes[scopes.length - 1];
  if (!last || last[0] !== "shell") {
    out.push("最后一条必须是兜底（shell）");
  } else if (!last[1].test("随便一个选择器")) {
    out.push("兜底谓词必须命中任意选择器");
  }
  for (const [id, re] of scopes) {
    if (last && id === last[0]) continue;
    if (cssRulesCached(css).filter(({ sel }) => re.test(sel)).length === 0) {
      out.push(`作用域 ${id} 一条规则都没命中——谓词写错了，或者它守的类名被改名了`);
    }
  }
  return out;
}

/** 已完工作用域在某个判据下的违规清单（逐页过腿；字号 / 间距两条腿共用这套循环）。 */
function doneScopeOffenders(find) {
  const bad = [];
  for (const id of doneScopes()) {
    for (const line of find(html, id)) bad.push(`[${id}] ${line}`);
  }
  return bad;
}

/** 某个作用域里**裸写的 px 字号**（做完的作用域应为空——全部走 `--fs-*`）。 */
function bareFontSizesInScope(css, id) {
  const out = [];
  for (const { sel, body } of rulesInScope(css, id)) {
    for (const m of body.matchAll(/font-size:\s*([0-9.]+)px/g)) out.push(`${sel} → ${m[1]}px`);
  }
  return out;
}

/** 某个作用域里**等于令牌却裸写**的 padding / margin / gap 值（做完的作用域应为空）。 */
function bareTokenSpacesInScope(css, id) {
  const out = [];
  for (const { sel, body } of rulesInScope(css, id)) {
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

/**
 * 动作三级的**口径问题**（纯函数——照本文件"判据返回问题清单"的既有形状写，
 * 好让"口径被改坏能不能判出来"有合成红证）：
 * 主 = 实心 accent；不可逆 = 红描边 + 淡红底、悬停实心红；次要 = 幽灵（透明底）。
 * 另判**单源**：任何带页面前缀的 `danger` 覆盖都算问题（两处说同一件事，将来只会改一处）。
 */
function actionWeightProblems(css) {
  const out = [];
  const bodies = (selector) => cssRulesCached(css)
    .filter(({ sel }) => stripLeadComments(sel) === selector)
    .map(({ body }) => body);
  const need = (selector, re, why) => {
    const all = bodies(selector);
    if (all.length === 0) out.push(`${selector}：规则不见了（${why}）`);
    else if (!all.some((b) => re.test(b))) out.push(`${selector}：${why}（现有声明：${all.join(" ｜ ")}）`);
  };
  need("button.primary", /background:\s*(var\(--accent\)|linear-gradient)/, "主操作 = 实心 accent");
  need("button.danger", /border-color:\s*var\(--danger\)/, "不可逆动作 = 红描边");
  need("button.danger", /background:\s*var\(--danger-dim\)/, "不可逆动作 = 淡红底");
  need("button.danger:hover", /background:\s*var\(--danger\)/, "不可逆悬停 = 实心红");
  need("button.ghost", /background:\s*transparent/, "次要动作 = 幽灵（透明底）");
  const scoped = cssRulesCached(css)
    .map(({ sel }) => stripLeadComments(sel))
    .filter((sel) => /\bdanger\b/.test(sel) && /#tab-/.test(sel));
  if (scoped.length) out.push("危险动作的口径出现了带页面前缀的副本：" + scoped.join(" / "));
  return out;
}

test("全站推广：字号角色表是**有限六档**，且页面里的 --fs-* 定义与它逐条一致", () => {
  const defined = [...html.matchAll(/(--fs-[a-z-]+):\s*([0-9.]+px)/g)].map((m) => [m[1], m[2]]);
  const names = defined.map(([n]) => n);
  assert.equal(new Set(names).size, names.length, "同一个 --fs-* 定义了两次：" + names.join(", "));
  assert.deepEqual(
    names.slice().sort(),
    FONT_ROLES.map(([n]) => n).slice().sort(),
    "页面里的 --fs-* 与角色表对不上——加档位要先改角色表（并写清为什么六档不够），"
    + "否则'有限台阶'这句话就不是机器可验的了",
  );
  for (const [name, value] of FONT_ROLES) {
    const hit = defined.find(([n]) => n === name);
    assert.equal(hit && hit[1], value, `${name} 的值应是 ${value}（实际 ${hit && hit[1]}）`);
  }
});

test("全站推广：分区表是全覆盖、不重叠的划分（兜底在最后、每条谓词都真的命中）", () => {
  assert.deepEqual(scopeTableProblems(PAGE_SCOPES, html), []);
  const ids = PAGE_SCOPES.map(([id]) => id);
  for (const id of SITEWIDE_BACKLOG) {
    assert.ok(ids.includes(id), "进度清单里有分区表不认识的作用域：" + id);
  }
});

test("全站推广：已完工作用域裸 px 字号 = 0（逐页过腿）", () => {
  assert.deepEqual(doneScopeOffenders(bareFontSizesInScope), [],
    "这些已完工的作用域又出现裸 px 字号了（新写的请改用 --fs-* 令牌）：\n"
    + doneScopeOffenders(bareFontSizesInScope).join("\n"));
});

test("全站推广：已完工作用域里等于令牌的间距值不许裸写", () => {
  assert.deepEqual(doneScopeOffenders(bareTokenSpacesInScope), [],
    "这些值等于 --space-* 却裸写（'间距走令牌'在已完工的页面上必须成立）：\n"
    + doneScopeOffenders(bareTokenSpacesInScope).join("\n"));
});

test("工单 03：全站裸字号集合只许减不许增（冻结清单）", () => {
  const added = bareFontSizesSitewide(html).filter((v) => !FROZEN_FONT_SIZES.has(v));
  assert.deepEqual(added, [],
    "出现了冻结清单外的裸字号。要么改用 --fs-* 令牌，要么把它登记进 FROZEN_FONT_SIZES "
    + "并写清为什么非它不可：" + added.join(", "));
});

test("全站推广：动作三级的口径**单源**（主实心 / 危险红描边淡红底 / 次要幽灵）", () => {
  // 口径来自检测页样板（ui-density/02），全站推广轮（02 单）把它升到全局
  assert.deepEqual(actionWeightProblems(html), []);
  assert.ok(/class="[^"]*\bghost\b/.test(html),
    "ghost 类要真的被元素用到——否则'补实一个类'就只是又造了一个死类");
});

test("全站推广合成红证：四条腿各自都判得红（防'永远绿'的守卫）", () => {
  // ① 已完工作用域各塞一个越界字号——**锚点只取规则头（不带令牌值）**，锚变了就当场报，
  //    不让这条自检静默空转。两个作用域：
  //      · `hwcheck` = 上一轮的样板页（腿③最早看着的那一页）；
  //      · `code` = 04 单刚摘掉进度尺的那一页——**摘尺 ≠ 腿跟着走**，它得真在射程里。
  //    ⚠ 锚点**别带令牌值**：04 单的整改把 `.code-pane-title` 的 `--fs-block` 换成 `--fs-note`，
  //    带令牌的锚点当场判红（"这条自检会静默空转"）——它做得对，但下一次换令牌还会误报。
  for (const [scope, head] of [
    ["hwcheck", "#tab-hwcheck .card h2 {"],
    ["code", ".code-pane-title { font-weight: 650;"],
  ]) {
    assert.ok(html.includes(head), `锚点变了（${head}）—— 这条自检会静默空转`);
    const bad = html.replace(head, `${head} font-size: 19px;`);
    assert.equal(bareFontSizesInScope(bad, scope).length, 1, `${scope} 作用域的越界字号没被判出`);
  }
  // ② 把卡片内边距改回裸写
  const spaceAnchor = "padding: var(--space-5) var(--space-6);";
  assert.ok(html.includes(spaceAnchor), `锚点变了（${spaceAnchor}）—— 这条自检会静默空转`);
  const badSpace = html.replace(spaceAnchor, "padding: 20px 24px;");
  assert.equal(bareTokenSpacesInScope(badSpace, "hwcheck").length, 2, "裸的令牌值没被判出（应报 20 与 24 两处）");
  // ③ 全站新字号（走 .muted 那条规则：改后它是 var(--fs-note)，注入一个清单外的裸值）
  const newFontAnchor = ".muted { color: var(--muted); font-size: var(--fs-note); }";
  assert.ok(html.includes(newFontAnchor), `锚点变了（${newFontAnchor}）—— 这条自检会静默空转`);
  const badNew = html.replace(newFontAnchor, ".muted { color: var(--muted); font-size: 13.75px; }");
  assert.deepEqual(bareFontSizesSitewide(badNew).filter((v) => !FROZEN_FONT_SIZES.has(v)),
    ["13.75"], "冻结清单外的新字号没被判出");
  // ④ **分区表形状自检本身要判得红**：拿三张坏表各喂一次（这才是"注入 → 判红"，
  //    不是"看一眼真实表觉得没问题"——第一版就是后者，等于没自证）
  const tail = PAGE_SCOPES[PAGE_SCOPES.length - 1];
  assert.ok(scopeTableProblems(PAGE_SCOPES, html).length === 0, "真实分区表本身就有形状问题");
  assert.ok(scopeTableProblems([...PAGE_SCOPES, tail], html).length > 0, "重复 id 没被判出");
  assert.ok(scopeTableProblems(PAGE_SCOPES.slice(0, -1), html).length > 0, "缺兜底没被判出");
  assert.ok(
    scopeTableProblems([["ghost", /zzz-这个谓词一条都命不中/], tail], html).length > 0,
    "空转的谓词没被判出（它守的那条腿会静默绿）",
  );
  // ⑤ 动作三级的口径：退回"只有红字"、或又冒出带页面前缀的副本，都必须判得红
  const dangerFull = "button.danger { border-color: var(--danger); background: var(--danger-dim); color: var(--danger); }";
  assert.ok(html.includes(dangerFull), `锚点变了（${dangerFull}）—— 这条自检会静默空转`);
  assert.ok(actionWeightProblems(html.replace(dangerFull, "button.danger { color: var(--danger); }")).length > 0,
    "危险动作退回'只有红字'没被判出");
  assert.ok(actionWeightProblems(html + "\n  #tab-hwcheck button.danger { color: red; }\n").length > 0,
    "带页面前缀的 danger 副本没被判出");
  // ⑥ 复原后转绿（四条腿都回到空/子集）
  assert.deepEqual(bareFontSizesInScope(html, "hwcheck"), []);
  assert.deepEqual(bareTokenSpacesInScope(html, "hwcheck"), []);
  assert.deepEqual(bareFontSizesSitewide(html).filter((v) => !FROZEN_FONT_SIZES.has(v)), []);
  assert.deepEqual(doneScopeOffenders(bareFontSizesInScope), []);
  assert.deepEqual(actionWeightProblems(html), []);
});
