// tests/js/css-tokens.test.mjs — CSS 令牌化守卫（工单 ux-walkthrough-02/20/21）：
// ①:root 定义 --radius-*/--space-*；②可见文本字号无 13.5/10.5/10px 裸值；
// ③border-radius 全部走令牌（var(--radius-*)）或圆形 50%/0（无裸 3/4/6/8/10/12/99/999）；
// ④工具类 .mt-2/4/6/8/.flex-1 已定义。
// ⑤排版契约：字号角色表（六档）+ 页面分区表 + 逐页腿 + 进度尺（SITEWIDE_BACKLOG /
//   FROZEN_FONT_SIZES）——见文件下半部分那两段说明块。
// ⑥**描边登记簿**（工单 border-guard/01）：`BORDER_KINDS`（10 类）+ `BORDER_REGISTER`（115 条）
//   + 腿⑥（盘上 ↔ 登记簿双向对账 + 透明不变量 + 类别表形状）——见那两张表的说明块。
// ⑦**渲染方描边登记簿**（工单 border-guard/02）：`JS_BORDER_REGISTER`（10 条）
//   + 腿⑦（`static/js/**` 内联整圈框的双向对账，认人键 = 文件 + 行内锚点）。
//   **描边与字号两条线都是"不许回潮"的闸**：字号那条的尺是取值集合，描边这条的尺是逐条登记簿，
//   而且**样式块面与渲染方面各有一张**（08 单给内联字号补第五条腿的同一条理由）。
// 静态标记守卫，直接读 index.html。
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
  // 08 单评审 Standards 点名：这两个函数走同一棵树 = Duplicated Code。
  // 现在 `jsSources()` 直接站在 `jsFiles()` 上（带路径那份是单一出处）。
  return jsFiles().map(([, text]) => text).join("\n");
}

/** 同上，但带路径——08 单的"内联字号"那条腿要能指出是哪个文件哪一行。 */
function jsFiles() {
  const dir = fileURLToPath(new URL("../../src/contest_generator/static/js/", import.meta.url));
  const out = [];
  const walk = (d, prefix) => {
    for (const f of readdirSync(d)) {
      const p = join(d, f);
      if (statSync(p).isDirectory()) walk(p, prefix + f + "/");
      else if (f.endsWith(".js")) out.push([prefix + f, readFileSync(p, "utf8")]);
    }
  };
  walk(dir, "");
  return out;
}

/**
 * 腿⑤（08 单）：渲染方（`static/js/**`）里**内联写的裸 px 字号**。
 *
 * 两种拼法都要抓（评审 Standards 点名第一版只认第一种）：
 *   · CSS 语法：`style="…font-size: 12px…"` / `cssText = "…font-size:12px…"`（冒号两侧空格随意）；
 *   · JS 驼峰：`el.style.fontSize = "11px"`。
 * ⚠ 已知留白：**跨行拼起来的** `cssText` 字符串抓不到（本仓库没有这种写法；
 *    真要抓得靠 AST——那是 09 或独立一笔的事，记在 08 票尾的账里）。
 * ⚠ `font-size="8.5"` 那种 **SVG 用户单位**不算（矢量图里的字号属性，随图缩放）。
 */
function jsInlineFontOffenders(files = jsFiles()) {
  const re = /font-size\s*:\s*[0-9.]+px|fontSize\s*=\s*["'][0-9.]+px/i;
  const out = [];
  for (const [rel, text] of files) {
    text.split("\n").forEach((line, i) => {
      if (re.test(line)) out.push(`${rel}:${i + 1}  ${line.trim().slice(0, 90)}`);
    });
  }
  return out;
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

/**
 * 「整圈完整框」口径里算**死声明**的首段取值（与 `scope_lib.DEAD_BORDER` 逐字相同）。
 * 只比**第一段**：`border: none` / `border: 0` 是撤框，`border: 0 solid red` 也算撤框；
 * 而 `transparent` **不在这里**——它是"占位"（登记簿里那一类），不是"撤框"
 * （`border: 1px solid transparent` 仍然是一条完整声明，占着位置、随时可以变成真框）。
 */
const DEAD_BORDER = ["none", "0"];

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
  ["master", /#tab-master|\.master-|\.prog-|\.decision|\.distill|\.stepper|\.import-platform-field/],
  ["settings", /#tab-settings|\.settings-|\.env-|\.delivery|\.materials-|\.update-|\.disk-|\.recent-wf-/],
  ["changelog", /#tab-changelog|\.release-|\.rel-tag/],
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
 * 派生；整圈完整描边 **24 → 19**，5 处内层盒去框，19 条全在申报的例外里）、
 * `settings`（工单 05，设置页：**10** 处裸字号 / **9** 条声明（10 处取值）裸令牌间距清零，
 * 卡内小节标题升到 `--fs-block` 并转正文色；整圈完整描边 **4 → 3**——去框 2 条
 * （`.recent-wf-summary` 数据块 / `.materials-pick-list` 弹层内清单），**另新加 1 条**
 * `#tab-settings .error:not(.ok):not(:empty)`（更新/保存失败的**语义告警块**，例外①，票面点名要它
 * 保留那一条描边；`:not(.ok)` 是因为保存成功那一态同时带 `error ok` 两个类，`:not(:empty)` 是因为
 * 那个 div 默认就是空的、不然页面一打开就挂一条空红框）；
 * 另加 **8 条新规则**（体检失败行的重量 `:has()` / 更新与进度结果块 3 条 / 该告警块 /
 * 死类 `.warning` 补实 / 分组带 2 条）+ **5 条 `.settings-band` 分组标题元素** +
 * 给不可逆按钮（`#btn-reset-records`）补 `class="danger"`——设置页规则数 40 → 48）。
 * （`generate` 的两处计数与本文件头上那句「111 处」差在 `.recent-wf-*` 那一处：它归设置页，
 * 03 单把谓词按渲染方改对之后就不再算在生成页头上。）
 * （`code` 的 66 处里含 **5 处渲染方其实在生成页**（`.code-wrap` / `.code-zoom`，main.c 编辑器
 * 与它的缩放工具条）与 **2 处跨页共享件**（`.diff-*`：代码页 + 生成页都用）—— 谓词按
 * "第一命名页"归了 `code`，04 单把它们就地令牌化、**没有改谓词**（改了会当场把 `generate`
 * 那条腿打红）；它们照样在腿③的射程里（`code` 已完工）。细则见工单 04 的「账」。）
 * （`settings` 的三处 `.recent-wf-*`（1 字号 + 1 整圈框 + 3 处令牌间距）是 03 单按渲染方
 * 归还给本页的——05 单接手时它们还在原地，本单一并收进账里。）
 * `library` / `reference` / `pdf` / `md` / `topic`（工单 06，素材与库五页：**63** 处裸字号 /
 * **51** 处取值（47 条声明）裸令牌间距清零，五页一次做完——它们共用同一套列表骨架
 * （全局 `table` + `.lib-*`）与同一套详情弹层（`.ref-files-*` / `.module-info-*` / `.mi-*`），
 * 所以"改一处、五页同时生效"；整圈完整描边 **20 → 13**：去框 7 条
 * （`.mi-reason` / `.mi-plat` / `.lib-edit-old` / `.add-section` 左条 / `.ref-scroll` /
 * `.md-preview-body` / `.topic-detail-problem`），留 13 条（可点卡片与控件 / 语义告警 /
 * 弹层外壳 / 表格网格与图片框——逐条理由在工单 06 的逐层清单里）。
 * 另把**行内 ⚠ 警示标**一族（`.dangling-tag` / `.ref-dangling-tag` / `.topic-warn`）的
 * 字号 / 字重 / 颜色对齐成同一套表达（`--fs-tag` / 600 / `--danger`）。）
 */
const SITEWIDE_BACKLOG = new Set([
  // 07 单摘掉最后三条（`master` / `changelog` / `guide`）之后，**页面尺空了**：
  // 全站十四个作用域都是 0 裸字号 / 0 裸令牌间距。照约定，**空集合不是「关掉这条腿」**——
  // 腿② 仍然逐页核「已完工的作用域必须在盘上真的是 0」，腿③ 仍然逐页核「新建的规则
  // 不许再落裸 px」（本单按 05/06 的先例给新摘的三页各补了一行合成红证）。
  // ⚠ 注释里别用 ASCII 双引号写作用域名——`probe-01` / `probe-04` 是按
  //    `new Set([ … ])` 里的引号串读这张尺的，会被当成一条待做作用域（07 单踩过）。
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
 *   · `11.5` / `15` / `18`（06 单：素材与库五页——赛题的元数据行与警示标 11.5 → `--fs-note` /
 *     `--fs-tag`；参考库详情弹窗标题 15 → `--fs-block`；弹层关闭 ✕ 18 → `--fs-body`
 *     （行内图标随所附那一面）。三个取值都是**全站最后一处**，改完实测 0 处）
 *   · `11` / `12` / `12.5` / `13` / `14` / `16.5` / `20`（07 单：最后三页做完，
 *     **`index.html` 样式块里的裸 px 字号归零**——`16.5`（使用指南章节标题）与 `20`（页标题）
 *     也是最后几处；07 之前站上只剩 36 处，全在 `master` / `guide` / `changelog`）
 *
 * ⚠ **口径说清**：这里的"全站"= **`index.html` 的 `<style>` 块**（本守卫与四支探针的口径）。
 * `static/js/**` 里还有 7 处**内联** `font-size: 11/12px`（渲染方写死的），
 * spec 四与 README 的 08 行都点名**留给收尾单**——那 7 处不在本轮的射程里，别把这条读成
 * "连内联也做完了"（07 单评审 Standards 抓到注释原先写成"全站"）。
 *
 * **页面尺与取值尺现在都是空的**（这不是"关掉守卫"）：腿② 仍然逐页核"已完工的作用域
 * 在盘上真的是 0"，腿③ 仍然核"新建的规则不许再落裸 px"，腿① 是"盘上出现的裸字号取值
 * 必须都在本清单里"——清单空了，**任何一处新裸字号都会当场判红** ✅
 * （08 收尾单的巡检就是在这个状态下跑的）。
 */
const FROZEN_FONT_SIZES = new Set([
  // index.html 样式块 0 处裸 px 字号（07 单达成）；此处**故意留空**——
  // 加回任何一个取值 = 加回一处裸字号。
]);

/**
 * **描边类别表**（工单 border-guard/01，单源）：回答「这条框为什么可以留」。
 *
 * **它不重推类别**——机器判不了"这是语义告示还是内层框"（那正是 08 账第 1 条说的判据问题）。
 * 类别是**人判过一次、写进 BORDER_REGISTER 的数据**；守卫只保证：
 *   · 每条登记项的类别值在**本表**里（新造一个类别把框塞进来这条路走不通）；
 *   · **每个类别至少有一条**（类别表不长出空档——空类别 = 判据退化成摆设）。
 *
 * 类别出处 = `.scratch/ui-density-sitewide/spec.md` 的例外 ①–⑥ 与那张轮的逐层清单；
 * 本表把它们机械化。**判据边界**：不判"该不该留"、不判好不好看。
 * 格式固定（`["id", "判据"],` 一行一条，判据里**不写 ASCII 双引号**）——
 * `.scratch/border-guard/probe-03-register.py` 与 `scope_lib.load_border_kinds()` 按同一格式解析。
 *
 * ⚠ **两个 id 与 CSS / HTML 的同名词不是一回事**（03 单评审点过）：这里的 `float` 是
 * "浮在内容之上的自己的面"（悬浮保存条 / 只读标注 / 缩放浮标），**不是 CSS 的 `float`**；
 * 这里的 `placeholder` 是"透明占位"，**不是 HTML 的 `placeholder` 属性**。
 * 它们是**这一列**（登记项第三格）的取值——读的时候按本表那一行的判据读，别按 CSS/HTML 的语感读。
 */
const BORDER_KINDS = [
  ["block", "顶层块：一屏里自成一块的容器（页面主体卡 / 页级汇总条）——「一屏一层」要留的就是它"],
  ["control", "可点控件：按钮 / 输入 / 下拉 / 勾选框 / 可点卡片 / 可点 chip / 标签页——那是控件的形状"],
  ["tag", "徽章与标签（不可点）：身份 / 计数 / 图例胶囊，用一条边把自己从正文里拎出来"],
  ["alert", "语义告示块：带警示或状态语义的告示（编译条 / 未选功能组 / 未上板 / 服务已停止 / 保存失败）"],
  ["modal", "弹层外壳：弹层 / 菜单 / toast——它自己是一屏，那一条要留"],
  ["float", "浮在内容之上的自己的面：悬浮保存条 / 只读标注 / 缩放浮标（不然与背后的字糊在一起）"],
  ["doc", "文档与表格语法：表格网格线 / md 预览的表格与图片框 / 指南表——去掉文档就散了"],
  ["editor", "编辑器形状：代码编辑器本体与它的悬浮工具条"],
  ["nonbox", "不是框：用 border 画的圆点 / 对勾字形 / 转圈环 / 滚动条 thumb——画得出像素，但不是盒子"],
  ["placeholder", "透明占位（★ 唯一带机器不变量）：取值含 transparent、默认态画不出框——要么是给悬停 / 选中态留的位置，要么是浏览器 chrome（滚动条 thumb）的透明声明"],
];

/**
 * **描边登记簿**（工单 border-guard/01）：`index.html` 样式块里**允许留框**的整圈完整框，逐条登记。
 *
 * **认人键 = `(作用域, 选择器)`**（选择器是**剥掉前导块注释、空白归一**后的形态，与 `scopeOf` 同口径
 * ——那条样式块大量规则写成「注释 + 选择器」，最长的一段前导注释有 **465 字符**
 * （`#tab-settings .error:not(.ok):not(:empty)`），拿原始选择器当键等于把注释一起冻进表里）。
 * 取值**不进键**：换个描边色 / 换令牌不该动这张表（那轮"守卫不判好不好看"的边界）。
 *
 * **腿⑥ 四条判据**（判据本体在 `borderRegisterProblems`，红证在文件末尾那条合成用例里）：
 *   ① 盘上 ⊆ 本表（新增一条框必须**显式登记**，否则当场判红）；
 *   ② 本表 ⊆ 盘上（改名 / 删规则会让登记项**过期**——反向对账，这份数据因此不会烂）；
 *   ③ `placeholder` ⟺ 取值含 `transparent`（**抓"透明占位偷偷变成真框"**）；
 *   ④ 类别表形状（类别值必须在 `BORDER_KINDS` 里、每类至少一条）。
 *
 * **口径分列（别混着读）**：本表 115 条 = **94 条可见框** + **21 条非框**
 * （12 `placeholder` + 9 `nonbox`）。"整圈完整框 115"是**声明数**口径（`scope_lib.full_borders`），
 * 与"渲染出来的框元素数"不是同一把尺——那一条 `local-environment` 记过。
 *
 * **两条容易贴错、已经核过一遍的**（写在这里，免得下一轮又有人按类名想当然）：
 *   · `.code-view::-webkit-scrollbar-thumb`（`3px solid transparent`）登记为 `placeholder` **不是**
 *     `nonbox`——透明不变量是"`placeholder` ⟺ 取值含 transparent"，它含 transparent，
 *     所以按不变量归 `placeholder`；它的"滚动条"身份是次要的（那条声明本来就画不出东西）。
 *   · `.gen-recent` 登记为 `block` **不是** `control`——它是 `<div id="gen-recent" class="gen-recent hidden">`
 *     这个容器（`recent.js` 只读写它内部的 `#gen-recent-list`），本身**不可点**。
 *     类名前缀/语义像什么不算判据，"渲染出来点不点得动"才算（那轮"类名前缀不是归属判据"的同一条教训）。
 *
 * **不在射程内（明写的边界）**：`border-color` 这类**单声明**不是"完整框"，
 * 所以悬停 / 选中态才出现的框**本来就不在这个口径里**（`.code-tab` 那族占位的意义正是这个）；
 * `border-top` / `border-bottom` 的单边分隔线同理不在射程。
 *
 * 格式固定（`["作用域", "选择器", "类别"],` 一行一条，`// ---- <作用域> ----` 是分组注释）——
 * 探针与 `scope_lib.load_border_register()` 按同一格式解析，格式变了会**大声失败**。
 */
const BORDER_REGISTER = [
  // ---- shell（22 条）----
  ["shell", "header nav button", "control"],
  ["shell", ".card", "block"],
  ["shell", "textarea, input[type=text], input[type=password], select", "control"],
  ["shell", "input[type=search]", "control"],
  ["shell", "button", "control"],
  ["shell", ".banner", "alert"],
  ["shell", ".welcome-card", "alert"],
  ["shell", ".platform-card", "control"],
  ["shell", "#compile-banner.running", "alert"],
  ["shell", "#compile-banner.success", "alert"],
  ["shell", "#compile-banner.fail", "alert"],
  ["shell", "#compile-banner.notool", "alert"],
  ["shell", ".mod-info-btn", "control"],
  ["shell", "#btn-score-export", "control"],
  ["shell", "input[type=checkbox], input[type=radio]", "control"],
  ["shell", "input[type=checkbox]:checked::after", "nonbox"],
  ["shell", "input[type=file]", "control"],
  ["shell", "input[type=file]::file-selector-button", "control"],
  ["shell", "::-webkit-scrollbar-thumb", "nonbox"],
  ["shell", "#btn-code-ai-send", "control"],
  ["shell", "#btn-recent-refresh", "control"],
  ["shell", ".card-step-status", "placeholder"],
  // ---- components（9 条）----
  ["components", ".btn", "control"],
  ["components", ".chip", "control"],
  ["components", ".btn-param-ref", "control"],
  ["components", ".btn-params-reset", "control"],
  ["components", ".badge.needs-choice-badge", "alert"],
  ["components", ".spinner", "nonbox"],
  ["components", ".service-stopped-box", "alert"],
  ["components", ".toast", "modal"],
  ["components", ".toast-copy, .toast-action, .wait-cancel", "control"],
  // ---- settings（3 条）----
  ["settings", ".env-jump", "control"],
  ["settings", ".settings-stickybar", "float"],
  ["settings", "#tab-settings .error:not(.ok):not(:empty)", "alert"],
  // ---- library（8 条）----
  ["library", ".module-card", "control"],
  ["library", ".module-card .mc-offtag", "alert"],
  ["library", ".module-card .mc-info", "control"],
  ["library", ".module-info-modal", "modal"],
  ["library", ".module-info-off", "alert"],
  ["library", ".mi-pins th, .mi-pins td", "doc"],
  ["library", ".lib-edit-modal", "modal"],
  ["library", ".lib-chip", "control"],
  // ---- generate（33 条）----
  ["generate", ".fix-row", "placeholder"],
  ["generate", ".task-more-menu", "modal"],
  ["generate", ".param-card-head .param-unit-chip", "tag"],
  ["generate", ".group-card.needs-choice", "alert"],
  ["generate", ".topic-preread", "alert"],
  ["generate", ".preread-slot", "alert"],
  ["generate", ".sp-item", "placeholder"],
  ["generate", ".pin-role", "placeholder"],
  ["generate", ".pin-fixed-list .fx", "tag"],
  ["generate", ".pin-warn-list .wx", "alert"],
  ["generate", ".pin-legend .lg", "tag"],
  ["generate", ".pin-menu", "modal"],
  ["generate", ".step-nav .step-dot", "placeholder"],
  ["generate", ".step-nav .step-dot .dot", "nonbox"],
  ["generate", ".gen-overview", "block"],
  ["generate", ".ov-chip", "control"],
  ["generate", ".ov-chip .ov-dot", "nonbox"],
  ["generate", ".ov-actions .ov-fill", "control"],
  ["generate", ".gen-recent", "block"],
  ["generate", ".recent-chip", "placeholder"],
  ["generate", ".recent-platform", "tag"],
  ["generate", ".revise-tab", "control"],
  ["generate", ".revise-tab-badge", "tag"],
  ["generate", ".task-phase", "alert"],
  ["generate", ".task-phase .task-spinner", "nonbox"],
  ["generate", ".tasks-done-line .btn-task-goto-delivery", "control"],
  ["generate", ".res-chip", "tag"],
  ["generate", ".res-view-btn", "control"],
  ["generate", ".res-board-legend .dot", "nonbox"],
  ["generate", ".res-board-legend .res-legend-conflict", "nonbox"],
  ["generate", ".score-chip", "tag"],
  ["generate", ".task-next-hint", "alert"],
  ["generate", ".rc-summary", "block"],
  // ---- hwcheck（8 条）----
  ["hwcheck", ".hwcheck-warn", "alert"],
  ["hwcheck", ".hwcheck-check", "placeholder"],
  ["hwcheck", ".hwcheck-recent-row", "placeholder"],
  ["hwcheck", ".hwcheck-order-index", "tag"],
  ["hwcheck", ".hwcheck-section-tag", "tag"],
  ["hwcheck", ".hwcheck-symptom", "control"],
  ["hwcheck", "#tab-hwcheck .hwcheck-band-num", "tag"],
  ["hwcheck", "#tab-hwcheck .hwcheck-jump", "control"],
  // ---- master（4 条）----
  ["master", ".stepper .step .dot", "nonbox"],
  ["master", ".prog-badge", "alert"],
  ["master", ".master-file-btn", "control"],
  ["master", ".master-health-pill", "placeholder"],
  // ---- reference（2 条）----
  ["reference", ".ref-files-modal", "modal"],
  ["reference", ".ref-files-filter", "control"],
  // ---- changelog（1 条）----
  ["changelog", ".rel-tag.tag-other", "tag"],
  // ---- topic（3 条）----
  ["topic", ".topic-card", "control"],
  ["topic", ".topic-year", "tag"],
  ["topic", ".topic-page img", "doc"],
  // ---- code（19 条）----
  ["code", ".code-pane-action, .code-compile-head button, .code-statusbar button", "control"],
  ["code", ".code-kbd", "tag"],
  ["code", ".code-bottom-tab", "placeholder"],
  ["code", ".code-ai-preview-btn", "control"],
  ["code", ".code-ai-chat-input", "control"],
  ["code", ".code-change-badge.b-removed", "tag"],
  ["code", ".code-tab", "placeholder"],
  ["code", ".code-tab-ro", "tag"],
  ["code", ".code-back-preview, .code-md-edit", "control"],
  ["code", ".code-view::-webkit-scrollbar-thumb", "placeholder"],
  ["code", ".code-ro-note", "float"],
  ["code", ".code-zoom-badge", "float"],
  ["code", ".code-ctx-menu", "modal"],
  ["code", ".quick-open-box", "modal"],
  ["code", ".code-tree-name-input", "control"],
  ["code", ".code-md-preview th, .code-md-preview td", "doc"],
  ["code", ".code-md-preview img", "doc"],
  ["code", ".code-wrap", "editor"],
  ["code", ".code-zoom", "editor"],
  // ---- guide（3 条）----
  ["guide", ".guide-tab", "control"],
  ["guide", ".guide-table th", "doc"],
  ["guide", ".guide-table td", "doc"],
];

/**
 * **渲染方描边登记簿**（工单 border-guard/02）：`static/js/**` 里**内联写出来的**整圈完整框。
 *
 * 为什么另起一张（而不是并进上面那张）：08 单给「内联字号」补第五条腿时就是"样式块面先做、
 * 渲染方面后补"两步——两面的**认人键根本不同**（那边是 CSS 选择器，这边是模板串里的一行），
 * 混进一张表只会让两边都读不清。这一面对称地补上：**内联写出来的框也不许绕过守卫**。
 *
 * **认人键 = `(文件, 锚点)`**，锚点取**该行的一段可认片段**：
 *   · **不取行号**——行号随插行漂，锚点不漂；
 *   · **同一锚点登记两次 = 盘上真有两条逐字相同的行**（`.role-type` 那条，
 *     `generate-pins.js` 里两个渲染函数各写了一遍），所以对账是**多重集**不是集合；
 *   · 锚点必须**足够独特**：一行只许命中一条登记项，一条登记项只许命中它该命中的那几行
 *     （施工脚本 `.scratch/border-guard/generate-02-js-register.py` 逐个验过；不独特它当场停手）。
 *
 * **口径与样式块面差一处（明写）**：内联样式写在 HTML 属性里，取值可能以 `"` 收尾而不是 `;`
 * （`style="…border:1px dashed var(--warn)">`），所以取值终止符是 **`;` 或 `"`**。
 * 样式块面那条要求 `;` 收尾——**两条正则不是同一条**，别互抄（`test_border_register_mirror.py`
 * 分别钉住它们各自跨语言的镜像）。
 *
 * **腿⑦ 两条判据**（本体在 `jsBorderRegisterProblems`）：盘上 ⊆ 本表（新增内联框判红）/
 * 本表 ⊆ 盘上（改名 / 删掉那一行会让登记项过期）。红证在文件末尾那条合成用例里。
 */
const JS_BORDER_REGISTER = [
  ["fx/flash.js", 'style="border:1px solid var(--warn);', "alert"],
  ["fx/task.js", 'border:1px solid var(--border);border-radius:var(--radius-md);background:var(--panel-2)', "alert"],
  ["ui/codeeditor.js", 'border:1px solid #888', "float"],
  ["ui/generate-recommend.js", 'border:1px solid var(--border,#ccc)', "doc"],
  ["ui/generate-recommend.js", 'class="warn-box" style="border:1px solid var(--border)"', "alert"],
  ["ui/generate-pins.js", 'background:var(--pin-pad);border:1px solid var(--border-strong)', "nonbox"],
  ["ui/generate-pins.js", 'border:1px dashed var(--warn)"', "nonbox"],
  ["ui/generate-pins.js", 'background:var(--pin-fixed-pad);border:1px solid var(--border)"', "nonbox"],
  ["ui/generate-pins.js", 'class="role-type" style="color:${st[0]};background:${st[1]};border:1px solid ${st[0]}"', "tag"],
  ["ui/generate-pins.js", 'class="role-type" style="color:${st[0]};background:${st[1]};border:1px solid ${st[0]}"', "tag"],
];

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
 * 盘上的**整圈完整框**：完整 `border:` 声明、值不是 `none` / `0`。
 *
 * 这是 `.scratch/ui-density-sitewide/scope_lib.py` 的 `full_borders` 的**跨语言镜像**
 * （判据一字不差：同一条正则 + 同一个 DEAD 前缀判定）。为什么要镜像而不是"另定一套"：
 * 那条轮的读数（**115 处**）就是按那个口径量的，腿⑥ 与读数必须是同一把尺，
 * 否则"腿绿而读数红"（或反过来）就是新的假账。
 *
 * ⚠ **两个解析口径在描边这一面已实测逐条相同**（`.scratch/border-guard/probe-02-caliber-styleblock.py`）：
 * 本函数吃的是 `cssRulesCached(css)`，它按**整文件**跑正则（`<style>` 之外那 14 段
 * 内联脚本的 `{}` 也会配成"规则"），而 Python 侧只在 `<style>` 块里跑——
 * 规则数差 14 条，但**都不含完整 `border:` 声明**，所以描边这一面 115 ↔ 115、双向 0 差。
 * （那条探针就是为这件事立的；将来若谁把内联脚本写出 `border:`，这里会当场露出来。）
 *
 * 选择器取**剥掉前导块注释 + 空白归一**后的形态——认人键必须是稳定的那一部分：
 * 115 条里有规则的前导注释长达 **465 字符**（`#tab-settings .error:not(.ok):not(:empty)` 那条，
 * 写满了两个 `:not()` 为什么必需；条数/长度按 `probe-03-register.py` 复算，别按记忆写），
 * 拿原始选择器当键等于把那段注释一起冻进表里。
 */
function fullBorderEntries(css) {
  const out = [];
  for (const { sel, body } of cssRulesCached(css)) {
    for (const m of body.matchAll(/(?<![\w-])border:\s*([^;]+);/g)) {
      const value = m[1].trim();
      if (DEAD_BORDER.includes(value.split(/\s+/)[0])) continue;
      const clean = stripLeadComments(sel);
      out.push({ scope: scopeOf(sel), sel: clean, value });
    }
  }
  return out;
}

/** 登记簿里的复合键（JS 的 Map 只吃字符串键）。**只用于查表，不许再拆回来**——
 * 印给人看的那一行跟着数据走（`{count, label}`），见 `multisetBorderProblems`。 */
function borderKey(a, b) {
  return a + "\u0000" + b;
}

/** 登记项的**类别值**校验（腿⑥ / 腿⑦ **共用同一张 `BORDER_KINDS`**——"这是什么"是一回事）。 */
function borderKindProblems(kinds, register) {
  const ids = new Set(kinds.map(([id]) => id));
  return register.flatMap((entry) => {
    const kind = entry[2];
    return ids.has(kind) ? [] : [`登记项用了类别表里没有的类别：${entry[1]} → ${kind}`];
  });
}

/**
 * **登记簿对账的公共骨架**（腿⑥ 描边登记簿 / 腿⑦ 渲染方登记簿共用）。
 *
 * `want` / `got` 都是 `Map<键, {count, label}>`（`label` = 印给人看的那一行）。
 * 按**多重集**比，三类都报（少报哪一类都是洞）：
 *   · 盘上有、登记侧没有 → 新写的东西必须**显式登记**；
 *   · 两边都有但**条数不等** → 盘上多一条（同一个认人键被复制了一份）/ 少一条（改名或删了）；
 *   · 登记侧有、盘上没有 → 登记项**过期**。
 *
 * ⚠ 条数不等必须**两个方向都报**：只判 `m < n`（第一版就是）会放过"盘上多出一条"——
 * 而那正是"同一个选择器/锚点又写了一遍"这种最像意外的坏法（01 单双轴评审点过同一个洞）。
 *
 * `talk` 提供三句**对症**的中文：两条腿的处置建议不一样，所以文案由调用方给——
 * 抽成一句通用话会让被拦下的人不知道该改哪一边。
 */
function multisetBorderProblems(want, got, talk) {
  const out = [];
  for (const [key, g] of got) {
    if (!want.has(key)) out.push(talk.unregistered(g.label));
  }
  for (const [key, w] of want) {
    const g = got.get(key);
    if (!g) out.push(talk.stale(w.label));
    else if (g.count !== w.count) out.push(talk.countMismatch(w.label, w.count, g.count));
  }
  return out;
}

/** 往 `Map<键, {count, label}>` 里加一条（键相同就只加计数）。 */
function bump(map, key, label) {
  const hit = map.get(key);
  if (hit) hit.count += 1;
  else map.set(key, { count: 1, label });
}

/**
 * 盘上渲染方（`static/js/**`）里**内联写出来的整圈完整框**：一行一条。
 *
 * **两种拼法都抓**（照第五条腿 `jsInlineFontOffenders` 的先例——那条腿的教训就是
 * "只认一种拼法"漏了一半）：
 *   · CSS 语法：`style="…border:1px solid var(--border)…"` / `cssText = "…border:…"`（冒号两侧空格随意）；
 *   · JS 属性语法：`el.style.border = "1px solid var(--red)"`。
 * 盘上今天这两种写法**各 0 处**（`probe-04-js-register.py` 的「覆盖审计」那一节盯着）——
 * 认它们是为了"以后写了也进得来"，不是为了现在有货。
 *
 * **口径与样式块面差一处（明写）**：内联样式写在 HTML 属性里，取值可能以 `"` 收尾而不是 `;`
 * （`style="…border:1px dashed var(--warn)">`），所以取值终止符是 **`;` 或 `"`**。
 * `DEAD_BORDER`（`none` / `0` 开头的算撤框）两边共用。
 *
 * **不跨行拼**：`'…' + 'border:…'` 那种拼接在本仓库都是**一条声明独占一行**，
 * 所以逐行扫就够；真出现跨行拼的写法时这条腿会**看不见**它（与第五条腿的已知留白同一类，
 * 那一条记在 08 账第 3 条里）。探针的「覆盖审计」把每一处 `border…:` 都归了类，专门盯这个留白。
 */
function jsInlineBorderEntries(files = jsFiles()) {
  const out = [];
  for (const [rel, text] of files) {
    text.split("\n").forEach((raw, i) => {
      for (const m of raw.matchAll(/(?<![\w-])border\s*:\s*([^;"]+)|\.border\s*=\s*["\u0027]([^"\u0027]+)["\u0027]/g)) {
        const value = (m[1] || m[2] || "").trim();
        if (!value || DEAD_BORDER.includes(value.split(/\s+/)[0])) continue;
        out.push({ file: rel, line: i + 1, raw, value });
      }
    });
  }
  return out;
}

/**
 * **腿⑦ 的判据**（纯函数，三条；锚点语义见 `JS_BORDER_REGISTER` 的说明块）：
 *   ① 盘上每一条内联整圈框都要被**恰好一条**登记项认领（锚点是那行的一段片段）；
 *      一行命中 0 条 = 没登记；命中 >1 条 = 锚点不够独特（那会让对账悄悄失真，也得报）；
 *   ② 每条登记项都要有行认领它，且**条数相等**（多重集：同一锚点登记 N 次就得有 N 行）；
 *   ③ 类别值必须在 `BORDER_KINDS` 里（与样式块面共用同一张类别表）。
 */
function jsBorderRegisterProblems(files = jsFiles(), register = JS_BORDER_REGISTER, kinds = BORDER_KINDS) {
  const out = borderKindProblems(kinds, register);
  const labelOf = ([file, anchor]) => `${file} / ${anchor}`;
  const want = new Map();
  for (const entry of register) bump(want, borderKey(entry[0], entry[1]), labelOf(entry));
  const got = new Map();
  for (const e of jsInlineBorderEntries(files)) {
    const hits = [...want.keys()].filter((key) => {
      const [file, anchor] = key.split("\u0000");
      return file === e.file && e.raw.includes(anchor);
    });
    if (hits.length === 0) {
      bump(got, `\u0000${e.file}:${e.line}`, `static/js/${e.file}:${e.line} → ${e.value}`);
    } else if (hits.length > 1) {
      out.push(`static/js/${e.file}:${e.line} 同时命中 ${hits.length} 条登记项（锚点不够独特，`
        + `对账会失真）：${hits.map((k) => want.get(k).label).join(" ｜ ")}`);
    } else {
      bump(got, hits[0], want.get(hits[0]).label);
    }
  }
  out.push(...multisetBorderProblems(want, got, {
    unregistered: (label) => `渲染方这条内联整圈框没有登记：${label}`,
    stale: (label) => `渲染方登记项在盘上一条都找不到（改名 / 删行之后忘了同步）：${label}`,
    countMismatch: (label, n, m) => `渲染方这条登记了 ${n} 条、盘上有 ${m} 条`
      + `（同一个锚点被复制 / 少了一份）：${label}`,
  }));
  return out;
}

/**
 * **腿⑥ 的判据**（纯函数，四条；照本文件"判据返回问题清单"的既有形状写，
 * 好让"判据被改坏能不能判出来"有合成红证）：
 *   ① 盘上 ⊆ 登记簿 —— 新写一条整圈框必须**显式登记**并挑一个类别；
 *   ② 登记簿 ⊆ 盘上 —— 改名 / 删规则会让登记项**过期**（反向对账；这条是"防腐烂"的本体）；
 *   ③ `placeholder` ⟺ 取值含 `transparent` —— **抓"透明占位偷偷变成真框"**（两个方向都判）；
 *   ④ 类别表形状 —— 登记项的类别必须在 `kinds` 里、每个类别至少一条、同一条不重复登记。
 *
 * **它不判什么**（边界，免得被当成"什么都管"）：不判"这条框该不该留"（机器判不了，
 * 那是 08 账第 1 条说的判据问题）、不判好不好看、不判取值该用哪个令牌。
 */
function borderRegisterProblems(css, register = BORDER_REGISTER, kinds = BORDER_KINDS) {
  let out = borderKindProblems(kinds, register);
  const registered = new Map();
  for (const entry of register) {
    if (!Array.isArray(entry) || entry.length !== 3) {
      out.push("登记项形状不对（应为 [作用域, 选择器, 类别]）：" + JSON.stringify(entry));
      continue;
    }
    const [scope, sel, kind] = entry;
    const key = borderKey(scope, sel);
    if (registered.has(key)) out.push(`同一条登记了两次：[${scope}] ${sel}`);
    registered.set(key, { scope, sel, kind, label: `[${scope}] ${sel}` });
  }
  for (const [id] of kinds) {
    if (![...registered.values()].some((e) => e.kind === id)) {
      out.push(`类别 ${id} 一条登记都没有——判据退化成摆设`);
    }
  }
  const want = new Map();
  for (const [key, e] of registered) want.set(key, { count: 1, label: e.label });
  const onDisk = new Map();
  const got = new Map();
  for (const e of fullBorderEntries(css)) {
    const key = borderKey(e.scope, e.sel);
    onDisk.set(key, e);
    bump(got, key, `[${e.scope}] ${e.sel} → ${e.value}`);
  }
  out = out.concat(multisetBorderProblems(want, got, {
    unregistered: (label) => `盘上这条整圈完整框没有登记（要留就加进 BORDER_REGISTER 并挑一个类别，`
      + `不然请改成留白 / 单条分隔线 / 淡底）：${label}`,
    stale: (label) => `登记簿里这条在盘上找不到了（改名 / 删规则之后忘了同步）：${label}`,
    countMismatch: (label, n, m) => `盘上这条有 ${m} 条整圈完整框声明、登记簿里 ${n} 条`
      + `（同一作用域里同一个选择器写了不止一条带框规则，认人键会把它们折叠成一条）：${label}`,
  }));
  for (const [key, e] of onDisk) {
    const reg = registered.get(key);
    if (!reg) continue;
    const transparent = /(?:^|\s)transparent(?:\s|$)/.test(e.value);
    if (reg.kind === "placeholder" && !transparent) {
      out.push(`登记为 placeholder（透明占位）但取值已不是透明——占位变成真框了：`
        + `[${e.scope}] ${e.sel} → ${e.value}`);
    } else if (reg.kind !== "placeholder" && transparent) {
      out.push(`取值是 transparent（默认态画不出框）却登记成了 ${reg.kind}：`
        + `[${e.scope}] ${e.sel} → ${e.value}（画不出框的请登记为 placeholder）`);
    }
  }
  return out;
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

test("全站推广：渲染方（static/js/**）里也不许有内联裸 px 字号（08 单新增的第五条腿）", () => {
  // 08 单把最后 7 处内联取值（`style="font-size:11px"` / `cssText = "…font-size:12px"`）
  // 收进了令牌。这条腿让"JS 侧不许回潮"有机器看着——原先只有**探针**看得到这一层，
  // 而探针是取证、不是闸门（README 坑 3：标记里有、守卫不管的，只有人眼看得见）。
  // 判据见 `jsInlineFontOffenders`（含两种拼法与已知留白）；红证在这个文件末尾那条合成用例里。
  const offenders = jsInlineFontOffenders();
  assert.deepEqual(offenders, [],
    "static/js/** 里又有内联裸 px 字号了（请改用 var(--fs-*) 令牌）：\n" + offenders.join("\n"));
});

test("工单 03：全站裸字号集合只许减不许增（冻结清单）", () => {
  const added = bareFontSizesSitewide(html).filter((v) => !FROZEN_FONT_SIZES.has(v));
  assert.deepEqual(added, [],
    "出现了冻结清单外的裸字号。要么改用 --fs-* 令牌，要么把它登记进 FROZEN_FONT_SIZES "
    + "并写清为什么非它不可：" + added.join(", "));
});

test("描边（工单 01，第六条腿）：整圈完整框逐条登记，盘上 ↔ 登记簿双向对账 + 透明不变量", () => {
  // 为什么要有这条腿（08 账第 1 条）：字号那条线到收尾单为止是干净的，**描边那条没有**——
  // 115 处例外只活在七张工单的散文清单里，机器读不出来。于是谁往样式块里新写一条
  // `border: 1px solid var(--border)`，115 就安静地变成 116，没有任何东西会红。
  //
  // 这一轮不判"这条框该不该留"（机器判不了），改判"**这条框是不是被登记过的**"：
  // 登记簿（BORDER_REGISTER，115 条）+ 四条对账判据见 `borderRegisterProblems`。
  // 判据的强度由文件末尾那条合成用例自证（塞新框 / 改名 / 删规则 / 占位变真框 / 未知类别 /
  // 掏空类别，六种注入各判一次红，复原转绿）。
  const problems = borderRegisterProblems(html);
  assert.deepEqual(problems, [],
    "描边登记簿与盘上对不上（新增框就登记它、去掉框就摘掉登记项、"
    + "透明占位别改成真框——三条各有各的改法）：\n" + problems.join("\n"));
  // 登记簿是**数据**：115 条这个数本身就是进度/规模读数，别让它悄悄缩水
  // （缩水会让上面的"⊆"判据永远绿——那是最容易发生的一种假绿）。
  assert.equal(BORDER_REGISTER.length, 115,
    "登记簿条数变了（应为 115 = 94 可见框 + 21 非框）。真去掉了一条框就同步改这个数，"
    + "并在票尾写清去掉的是哪一条、为什么");
  // 这条是**条数**口径的独立兜底：`borderRegisterProblems` 按 (作用域, 选择器) 认人，
  // 万一有两条声明撞成同一个键，对账会把它折成一条而漏报——条数断言就是那一处的第二道。
  assert.equal(fullBorderEntries(html).length, BORDER_REGISTER.length,
    "盘上声明数与登记簿条数不等——上面的对账会指出差在哪几条；若它没报，就是有两条声明撞了同一个认人键");
});

test("描边（工单 02，第七条腿）：渲染方内联整圈框逐条登记，盘上 ↔ 登记簿双向对账", () => {
  // 08 单给「内联字号」补第五条腿的先例：**样式块做完了不等于渲染方也干净**。
  // 这一面对称地补上——`static/js/**` 里那 10 处内联 `border:` 简写（指引卡 / 提示块 /
  // 诊断浮标 / 题面图片框 / 警示块 / 图例色块 / 角色标记）逐条登记（认人键 = 文件 + 行内锚点），
  // 判据见 `jsBorderRegisterProblems`，红证在文件末尾那条合成用例里。
  const problems = jsBorderRegisterProblems();
  assert.deepEqual(problems, [],
    "渲染方描边登记簿与盘上对不上（新增内联框就登记它、去掉就摘掉登记项）：\n" + problems.join("\n"));
  assert.equal(JS_BORDER_REGISTER.length, 10,
    "渲染方登记条数变了（应为 10）。真去掉了一条就同步改这个数，并在票尾写清是哪一条、为什么");
  assert.equal(jsInlineBorderEntries().length, JS_BORDER_REGISTER.length,
    "盘上内联框数与登记条数不等——上面的对账会指出差在哪几条");
});

test("全站推广：动作三级的口径**单源**（主实心 / 危险红描边淡红底 / 次要幽灵）", () => {
  // 口径来自检测页样板（ui-density/02），全站推广轮（02 单）把它升到全局
  assert.deepEqual(actionWeightProblems(html), []);
  assert.ok(/class="[^"]*\bghost\b/.test(html),
    "ghost 类要真的被元素用到——否则'补实一个类'就只是又造了一个死类");
});

test("全站推广合成红证：七条腿各自都判得红（防'永远绿'的守卫）", () => {
  // ① 已完工作用域各塞一个越界字号——**锚点只取规则头（不带令牌值）**，锚变了就当场报，
  //    不让这条自检静默空转。三个作用域：
  //      · `hwcheck` = 上一轮的样板页（腿③最早看着的那一页）；
  //      · `code` = 04 单刚摘掉进度尺的那一页——**摘尺 ≠ 腿跟着走**，它得真在射程里；
  //      · `settings` = 05 单刚摘的那一页（同一条理由；05 评审 Standards 点名"少一层自证"）。
  //    ⚠ 锚点**别带令牌值**：04 单的整改把 `.code-pane-title` 的 `--fs-block` 换成 `--fs-note`，
  //    带令牌的锚点当场判红（"这条自检会静默空转"）——它做得对，但下一次换令牌还会误报。
  for (const [scope, head] of [
    ["hwcheck", "#tab-hwcheck .card h2 {"],
    ["code", ".code-pane-title { font-weight: 650;"],
    ["settings", ".settings-section { margin-top: var(--space-4);"],
    // 06 单一次摘掉五页（素材与库）——照 05 的先例**逐页补一行**：摘尺 ≠ 腿跟着走。
    ["library", ".module-card { border: 1px solid var(--border);"],
    ["reference", ".ref-pick-head {"],
    ["pdf", "#tab-pdf table {"],
    ["md", "#tab-md table {"],
    ["topic", ".topic-card { border: 1px solid var(--border);"],
    // 07 单摘掉最后三页（母版库 / 使用指南 / 版本更新记录）——同样逐页补一行。
    ["master", ".decision button {"],
    ["guide", "#tab-guide .guide-panel p, #tab-guide .guide-panel li {"],
    ["changelog", ".release-ver {"],
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
  // ⑥ 第五条腿（08 单加的"渲染方里不许有内联裸 px 字号"）也必须判得红——
  //    照 05/06/07 的先例：**新加的腿要自证**，不然它就是一条"永远绿"的摆设。
  assert.deepEqual(jsInlineFontOffenders(), [], "盘上 static/js/** 本来就不该有内联裸 px 字号");
  const fakeJs = [["ui/whatever.js", '  el.style.cssText = "padding:2px;font-size:12px;";']];
  assert.equal(jsInlineFontOffenders(fakeJs).length, 1, "塞进去的内联裸 px 字号没被判出");
  assert.equal(jsInlineFontOffenders([["ui/ok.js", '  el.style.cssText = "font-size:var(--fs-tag);";']]).length, 0,
    "令牌形态被误判成裸值");
  // ⑦ **第六条腿（描边登记簿）的坏法各判一次红**——01 单加的腿，照 05/06/07 的先例自证。
  //    判据的"注入点"取**真实源码里的锚点**并断言锚点还在（锚变了就当场报，别静默空转）。
  //    ⚠ 每条必须是**真注入**：spec 点名的六种坏法各对应一次真改动。
  //    第一版有两条是假的（"塞新框"其实只改了选择器名、"删规则"其实只往表里加了一条），
  //    双轴评审当场点了名——改名与删表**都不是**"往页面里加了一条框"那条主路径。
  assert.deepEqual(borderRegisterProblems(html), [], "盘上本来就不该有对账问题");
  //    (a) 往一条**原本没有框**的规则里真加一条 `border:` 声明 → 判红（这是主路径：
  //        有人新写了一个内层面板）。锚点 = `.gen-recent-head`（真实规则，原本没有 border）。
  const noBorderAnchor = ".gen-recent-head { display: flex; align-items: center; gap: var(--space-2); }";
  assert.ok(html.includes(noBorderAnchor), `锚点变了（.gen-recent-head）—— 这条自检会静默空转`);
  const injectedBorder = html.replace(noBorderAnchor,
    ".gen-recent-head { display: flex; align-items: center; gap: var(--space-2); border: 1px solid var(--border); }");
  assert.notEqual(injectedBorder, html, "注入没生效（锚点没命中）");
  assert.equal(fullBorderEntries(injectedBorder).length, 116, "注入的那条完整框没被盘上侧认出来");
  assert.ok(
    borderRegisterProblems(injectedBorder).some((p) => p.includes("没有登记") && p.includes(".gen-recent-head")),
    "往没有框的规则里新加一条 border 没被判出（这是本腿最该抓的坏法）",
  );
  //    (b) 把一个**已登记**的选择器改名 → 两个方向都要报（盘上没登记 + 登记簿过期）
  //    ⚠ 锚点必须**唯一命中那条带框的规则**：`.mod-info-btn {` 全文第一处是
  //    `.chip.rec.unsel .mod-info-btn {`（一条没有框的规则）——按它注入等于什么都没改，
  //    这条自检第一版就是这么假绿的（正是那轮"按行号挑规则会挑错人"的同一个坑）。
  const renameAnchor = ".mod-info-btn { flex: none;";
  assert.ok(html.includes(renameAnchor), `锚点变了（${renameAnchor}）—— 这条自检会静默空转`);
  const renamed = html.replace(renameAnchor, ".mod-info-btn-x { flex: none;");
  assert.notEqual(renamed, html, "注入没生效（锚点没命中）");
  assert.ok(borderRegisterProblems(renamed).some((p) => p.includes("没有登记") && p.includes(".mod-info-btn-x")),
    "改名之后盘上那条没被判成未登记");
  assert.ok(borderRegisterProblems(renamed).some((p) => p.includes("[shell] .mod-info-btn") && p.includes("找不到了")),
    "改名之后登记簿里那条没被判成过期");
  //    (c) **真把一条已登记的规则从盘上删掉** → 登记项过期判红（不是"往表里塞一条"）
  const delAnchor = ".env-jump {";
  const delRule = html.slice(html.indexOf(".env-jump {"), html.indexOf("}", html.indexOf(".env-jump {")) + 1);
  const deleted = html.replace(delRule, ".env-jump-renamed-placeholder { }");
  assert.notEqual(deleted, html, "注入没生效（锚点没命中）");
  assert.equal(fullBorderEntries(deleted).length, 114, "删掉的那条完整框没从盘上侧消失");
  assert.ok(borderRegisterProblems(deleted).some((p) => p.includes("[settings] .env-jump") && p.includes("找不到了")),
    "真删掉一条已登记规则之后，登记项没被判成过期");
  //    (c2) **登记项过期**的另一半：给表里塞一条盘上根本没有的登记项，也要判红
  const extraRegister = [...BORDER_REGISTER, ["guide", ".guide-table caption", "doc"]];
  assert.ok(borderRegisterProblems(html, extraRegister).some((p) => p.includes(".guide-table caption") && p.includes("找不到了")),
    "登记簿里多出一条盘上没有的登记项时没被判出（反向对账失效）");
  //    (d) **透明占位偷偷变成真框** → 判红；反方向（真框登记成 placeholder）也要判红
  const phAnchor = "font-weight: 600; border: 1px solid transparent;";
  assert.ok(html.includes(phAnchor), `锚点变了（${phAnchor}）—— 这条自检会静默空转`);
  assert.ok(
    borderRegisterProblems(html.replace(phAnchor, "font-weight: 600; border: 1px solid var(--border);"))
      .some((p) => p.includes("占位变成真框了")),
    "透明占位被改成可见框时没被判出",
  );
  const wrongKind = BORDER_REGISTER.map((e) => (e[1] === ".card-step-status" ? [e[0], e[1], "control"] : e));
  assert.ok(
    borderRegisterProblems(html, wrongKind).some((p) => p.includes("却登记成了 control")),
    "画不出框的声明被登记成可见类别时没被判出",
  );
  //    (e) 类别表形状：未知类别 / 掏空一个类别 → 都要判红
  const bogusKind = BORDER_REGISTER.map((e) => (e[1] === ".card" ? [e[0], e[1], "内层框"] : e));
  assert.ok(borderRegisterProblems(html, bogusKind).some((p) => p.includes("类别表里没有的类别")),
    "新造一个类别把框塞进去这条后门没被堵住");
  const emptied = BORDER_REGISTER.filter((e) => e[2] !== "editor");
  assert.ok(borderRegisterProblems(html, emptied).some((p) => p.includes("类别 editor 一条登记都没有")),
    "空类别没被判出（判据退化成摆设）");
  //    (f) 判据自己的两个防御分支也要自证（它们是 01 单加在 spec 四条之外的）：
  //        登记项形状不对 / 同一条登记两次
  assert.ok(borderRegisterProblems(html, [...BORDER_REGISTER, ["shell", ".card"]]).some((p) => p.includes("形状不对")),
    "登记项形状不对时没被判出");
  assert.ok(borderRegisterProblems(html, [...BORDER_REGISTER, ["shell", ".card", "block"]]).some((p) => p.includes("登记了两次")),
    "同一条登记了两次没被判出");
  //    (g) 盘上侧的多重集分支：同一个选择器再来一条带框规则（认人键会折叠它）→ 判红。
  //        这是 Standards 轴点名的"Map 折叠"洞——判据自己得先站得住，红证才不是摆设。
  const dupKey = html.replace(".card {", ".card { border: 1px solid var(--danger);");
  assert.notEqual(dupKey, html, "注入没生效（锚点没命中）");
  assert.ok(borderRegisterProblems(dupKey).some((p) => p.includes("有 2 条整圈完整框声明、登记簿里 1 条")),
    "同一作用域里同选择器的第二条框没被判出（多重集分支失效）");
  // ⑧ **第七条腿（渲染方内联框）的坏法各判一次红**——判据吃 `files` 参数，所以注入走内存
  //    （照 08 单第五条腿用假 JS 源的先例：这一面本来就是"逐行文本"，不必碰真文件）。
  assert.deepEqual(jsBorderRegisterProblems(), [], "盘上渲染方本来就不该有对账问题");
  const fakeBorderJs = (line) => [["ui/whatever.js", line]];
  //    (a) 新写一条**没登记**的内联框 → 判红
  assert.ok(
    jsBorderRegisterProblems(fakeBorderJs('  el.style.cssText = "padding:2px;border:1px solid var(--border);";'))
      .some((p) => p.includes("没有登记") && p.includes("ui/whatever.js")),
    "塞进去的未登记内联框没被判出",
  );
  //    (b) 登记项的锚点改坏（盘上那一行还在，只是没人认领）→ 判红
  const brokenAnchor = JS_BORDER_REGISTER.map(([f, a, k]) =>
    (a === "border:1px solid #888" ? [f, "border:1px solid #999", k] : [f, a, k]));
  assert.ok(jsBorderRegisterProblems(jsFiles(), brokenAnchor).some((p) => p.includes("ui/codeeditor.js") && p.includes("没有登记")),
    "锚点改坏之后盘上那条没被判成未登记");
  assert.ok(jsBorderRegisterProblems(jsFiles(), brokenAnchor).some((p) => p.includes("一条都找不到")),
    "锚点改坏之后登记项没被判成过期");
  //    (c) 锚点**不够独特**（一行命中两条登记项）→ 判红（那会让对账悄悄失真）
  const loose = [...JS_BORDER_REGISTER, ["ui/codeeditor.js", "border:1px solid", "float"]];
  assert.ok(jsBorderRegisterProblems(jsFiles(), loose).some((p) => p.includes("锚点不够独特")),
    "过宽的锚点没被判出（它会让一条登记项去认领别人的行）");
  //    (e) **口径边界要自证**：单边分隔线（`border-top:`）与撤框（`border: none` / `0`）都不算。
  //        这里断言**判据本身**（`jsInlineBorderEntries`），不喂登记簿——喂合成文件会让
  //        每一条真实登记项都"过期"，那是另一件事，会把这条边界证明淹掉。
  //        ⚠ 注入串里必须**真有 `border-top:`**：第一版写的是 `x.style.borderTop = "…"`，
  //        那串里根本没有 `border:`，对任何正则都返回空 —— **空断言**，什么都没证明
  //        （02 单双轴评审点名；边界本身成立，但用例得真的把它钉住）。
  assert.deepEqual(jsInlineBorderEntries(fakeBorderJs('  el.style.cssText = "border-top:1px dashed var(--border);";')), [],
    "单边分隔线被误判成整圈完整框（口径写宽了）");
  assert.deepEqual(jsInlineBorderEntries(fakeBorderJs('  el.style.cssText = "border:none;border-top:0";')), [],
    "撤框声明（none / 0）被误判成整圈完整框（DEAD_BORDER 没生效）");
  //    正例：真有一条内联框时它得认出来（否则上面两条"不判红"可能只是整个判据不工作）
  assert.equal(jsInlineBorderEntries(fakeBorderJs('  el.style.cssText = "border:2px dashed var(--ok)";')).length, 1,
    "真有一条内联整圈框时判据没认出来（上一条的'不判红'因此不算证据）");
  //    **两种拼法都要抓**（照第五条腿的先例）：JS 属性写法也得进得来
  assert.equal(jsInlineBorderEntries(fakeBorderJs('  el.style.border = "1px solid var(--danger)";')).length, 1,
    "JS 属性拼法（`el.style.border = \"…\"`）没被抓到——那就是第五条腿踩过的'只认一种拼法'");
  //    (d2) **条数"变多"那个方向也要判红**：同一个锚点被复制了一份（有人复制粘贴了那段渲染）
  //         —— 只判"盘上比登记少"会静默放过它（01 单双评点过同一个洞）。
  const dupedJs = jsFiles().map(([rel, text]) =>
    rel === "ui/codeeditor.js" ? [rel, text + '\n  d.style.cssText = "border:1px solid #888;";\n'] : [rel, text]);
  assert.equal(jsInlineBorderEntries(dupedJs).length, 11, "注入没生效（复制那一行没被算进盘上）");
  assert.ok(jsBorderRegisterProblems(dupedJs).some((p) => p.includes("登记了 1 条、盘上有 2 条")),
    "盘上同锚点多出一条时没被判出（条数不等只判了'少'这一个方向）");
  // ⑨ 复原后转绿（七条腿都回到空/子集）
  assert.deepEqual(bareFontSizesInScope(html, "hwcheck"), []);
  assert.deepEqual(bareTokenSpacesInScope(html, "hwcheck"), []);
  assert.deepEqual(bareFontSizesSitewide(html).filter((v) => !FROZEN_FONT_SIZES.has(v)), []);
  assert.deepEqual(doneScopeOffenders(bareFontSizesInScope), []);
  assert.deepEqual(actionWeightProblems(html), []);
  assert.deepEqual(borderRegisterProblems(html), []);
  assert.deepEqual(jsBorderRegisterProblems(), []);
});
