// .scratch/code-contrast/probe-08-disabled-state.mjs —— **禁用态 / 不可选形态的真像素量具**
// （工单 code-contrast/03 立；工单 disabled-forms/02 **扩口径**）。
//
// 为什么另立一支（而不是接着用 probe-07）：`probe-07` 的禁用桶**实测是空的**——
// 那些禁用按钮坐在带渐变的容器里（`.card` 有 `background-image: linear-gradient(...)`），
// 被"祖先渐变跳过"规则滤掉了。扫描看不见 ≠ 达标（这正是那一单要治的那条口径）。
//
// 这一支干三件事：
//   ① **找得到**：认人面 = 老那半（`el.disabled === true` / `.disabled` 类）
//      **＋ 新那半**（守卫 `tests/js/css-tokens.test.mjs` 的 `CONTRAST_DISABLED_FORMS` 里
//      类别为 `disabled` 的选择器）——**直接从守卫里读**，探针里不另写一份名单
//      （工单 disabled-forms/02 的口径要求："别在探针里另写一份名单而不加镜像断言"）；
//   ② **拍得下**：逐个元素截图（一个元素一张 PNG）——真像素，落在盘上可人眼复核；
//      登记表命中的**整块形态**连带它的**文字子元素**各拍一张（整块只告诉你"最强的字"，
//      而票面要的是"说明字 / 原因行 / 提示行"那几处的比值）；
//   ③ **对得上**：JSON 里连"静态预测要用到的原料"一起记（自己的 `color` / `background-color` /
//      `opacity` / 祖先合成底 `behind`），由 `probe-08-disabled-state-read.py` 把它与
//      "实测字形像素 vs 实测主色底"逐格对差。
//
// **"最少操作路径"（工单 02）**：初始态下三处形态有两处看不见（要选平台 / 选模块 / 开引脚菜单 /
// 有生成过的工程），所以这一支带了 `PREPARE` / `PREPARE_OVERLAY` 两小段准备代码——
// 用**真页面**把状态造出来再拍，而不是另做一个 HTML 夹具（夹具拍的就不是产品了）。
//
// **`--tag` 的用法**：改的是**产品面**（`index.html` 的样式块），所以要拿改前/改后两份像素对照——
// `--tag before` 在改动前跑（旧树）、`--tag after` 在改动后跑。
// **`--out` 把 PNG/JSON 写到指定目录**（默认本目录）：后来的轮次用 `--out` + 自己的 tag，
// **不覆盖**上一轮留档的证据。
//
// 跑法（仓库根；跑完接 probe-08-disabled-state-read.py）：
//     node .scratch/code-contrast/probe-08-disabled-state.mjs --tag before
//     node .scratch/code-contrast/probe-08-disabled-state.mjs --tag after
//     node .scratch/code-contrast/probe-08-disabled-state.mjs --tag forms-after --out .scratch/disabled-forms
// ⚠ 不要与全量 pytest 同时跑（本机负载下浏览器用例会抖）。
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const arg = (name, dflt) => {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
};
const TAG = arg("--tag", "cur").replace(/[^\w.-]/g, "");
const OUT_ARG = arg("--out", "").replace(/[\\/]+$/, "");
// ⚠ `--out` **不给就写本目录**（`HERE`）：第一版写成 `join(HERE, "..", "..", "")`，
// 不给参数时落到**仓库根**（docstring 还写着"默认本目录"）——照文档跑会把 PNG 撒在仓库根。
const OUT = OUT_ARG ? join(HERE, "..", "..", OUT_ARG) : HERE;
mkdirSync(OUT, { recursive: true });

// —— 认人面的**新那半**：从守卫里读登记表（单源；读不到就大声失败，别静默退化成"只有老那半"）——
const GUARD = readFileSync(join(HERE, "..", "..", "tests", "js", "css-tokens.test.mjs"), "utf8");
const DISABLED_FORMS = (() => {
  const m = /const CONTRAST_DISABLED_FORMS = \[([\s\S]*?)\n\];/.exec(GUARD);
  if (!m) throw new Error("守卫里找不到 CONTRAST_DISABLED_FORMS——认人面会静默变成另一份名单");
  const rows = [...m[1].matchAll(/^\s*\["([^"]*)",\s*"([^"]*)",\s*"([^"]*)",/gm)]
    .map((r) => ({ scope: r[1], sel: r[2], kind: r[3] }));
  if (rows.length < 3) throw new Error(`只从守卫里解析出 ${rows.length} 条不可选形态——格式变了`);
  const targets = rows.filter((r) => r.kind === "disabled");
  if (targets.length < 3) throw new Error("登记表里 `disabled` 档少于 3 条——量具的靶子不全");
  return targets;
})();
console.log(`认人面新那半（读自守卫）：${DISABLED_FORMS.map((f) => f.sel).join("  |  ")}`);

const TABS = ["generate", "hwcheck", "settings", "guide", "changelog", "code",
  "master", "library", "reference", "pdf", "md", "topic"];

/** 每趟最多拍这么多张。**按"每张登记表"各自封顶**（`MAX_FORM_SHOTS`）+ 老那半一个总顶
 *  （`MAX_SHOTS`）：登记表那三处是**靶子**，不许被"页面上有一堆禁用按钮"或
 *  "模块网格里有 48 张 off 卡"挤掉（第一次跑就是这么丢的：`.param-stale` 一张没拍到）。 */
const MAX_SHOTS = 16;
const MAX_FORM_SHOTS = 10;

/** 参数卡锚失效那处用的假数据目录（**两次 tag 共用同一个路径**，状态才可比）。
 *  只放两个文件、**不跑生成**：`main.c`（任意非空正文）+ `.contest_params.json`
 *  （anchor 不在 main.c 里 ⇒ `/api/tasks/params/read` 判 `valid: false` ⇒ `.param-stale`）。
 *  这是"最少的操作路径"：造**数据状态**，渲染仍走真产品。 */
const PARAM_DIR = join(tmpdir(), "df-probe08-param-stale");

// ⚠ `COLLECT` 里的 `parse` / `behindOf` / `hasText` / `path` / `slug` **必须自带一份**：
// 它是 `page.evaluate` 的载荷，会被**序列化后丢进浏览器**，看不到模块作用域——所以
// `probe-07` 与这里各有一份是结构使然，不是抄漏（Python 读数半那边能共用，已经抽进 `pixel_lib.py`）。
const COLLECT = (payload) => {
  const { tab: TAB, max: MAX, maxForm: MAX_FORM, scope: SCOPE, forms: FORMS } = payload;
  const parse = (c) => (c.match(/[\d.]+/g) || [0, 0, 0, 1]).map(Number);
  /** 祖先（**不含自己**）背景按 alpha 合成到白 —— 预测"半透明元素压在什么上"要用它。 */
  const behindOf = (el) => {
    const chain = [];
    for (let n = el.parentElement; n; n = n.parentElement) chain.unshift(n);
    let acc = [255, 255, 255];
    for (const n of chain) {
      const [r, g, b, a = 1] = parse(getComputedStyle(n).backgroundColor);
      if (a > 0) acc = [0, 1, 2].map((i) => Math.round(a * [r, g, b][i] + (1 - a) * acc[i]));
    }
    return acc;
  };
  /** 元素的**直接**文本子节点（控件自己的字）。 */
  const hasText = (el) => {
    const tag = el.tagName.toLowerCase();
    if (["input", "select", "textarea", "button"].includes(tag)) {
      if (tag === "input" && ["checkbox", "radio", "range", "file", "color"].includes(el.type)) return false;
      return true;
    }
    return [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
  };
  const path = (el) => {
    const bits = [];
    for (let n = el; n && bits.length < 3; n = n.parentElement) {
      bits.unshift(n.id ? `#${n.id}` : (n.className && typeof n.className === "string"
        ? "." + n.className.trim().split(/\s+/).slice(0, 2).join(".") : n.tagName.toLowerCase()));
    }
    return bits.join(" > ");
  };
  const slug = (s) => s.replace(/[^\w\u4e00-\u9fa5]+/g, "-").replace(/^-|-$/g, "").slice(0, 28);

  const out = { theme: document.documentElement.dataset.theme || "dark", tab: TAB, scope: SCOPE,
    shots: [], disabled: 0, missing: false,
    // **没量到的那些也要记账**（工单 03 的口径："扫描看不见"不许当达标）：逐条报出原因，
    // 免得下一轮把"几格全 ✅"读成"全站禁用态都达标了"。`skippedDetail` 是**靶子那份**的明细
    // （老那半一堆按钮不逐条列），最多 8 条——"为什么这处形态没量到"要能一眼看见。
    skipped: { 不可见: 0, 零尺寸: 0, 无文字: 0, "超过上限（登记表）": 0, "超过上限（老那半）": 0 },
    skippedDetail: [] };
  const btn = document.querySelector(`nav button[data-tab="${TAB}"]`);
  if (!btn) { out.missing = true; return out; }
  if (SCOPE === "panel") btn.click();
  for (const d of document.querySelectorAll("details:not([open])")) d.open = true;
  const root = SCOPE === "overlay"
    ? document.querySelector(".pin-menu-overlay")
    : document.getElementById(`tab-${TAB}`);
  if (!root) { out.missing = true; return out; }
  const seen = { legacy: 0 };
  const seenForm = new Map();      // 每张登记表各自计数
  let key = 0;

  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) < 0.05) return "不可见";
    const box = el.getBoundingClientRect();
    if (box.width < 4 || box.height < 4) return "零尺寸";
    return null;
  };
  /** `bucket` = `"form"`（登记表靶子，按表各自封顶）/ `"legacy"`（老那半，一个总顶）。 */
  const push = (el, how, form, subtree, bucket) => {
    out.disabled++;
    const why = visible(el);
    if (why) {
      out.skipped[why]++;
      if (bucket === "form" && out.skippedDetail.length < 8) {
        out.skippedDetail.push(`${how} @ ${path(el)} —— ${why}`);
      }
      return;
    }
    // 登记表命中的是**整块形态**（卡 / 行）——它的字在子元素里，所以判据取子树文本；
    // 老那半是**控件**（按钮那些），判据取自身。两把尺子分开写，别互相将就。
    const text = subtree ? String(el.textContent || "").trim() : String(el.value || el.textContent || "").trim();
    if (!text) { out.skipped.无文字++; return; }
    const cap = bucket === "form" ? (seenForm.get(form) || 0) >= MAX_FORM : seen.legacy >= MAX;
    if (cap) {
      out.skipped[bucket === "form" ? "超过上限（登记表）" : "超过上限（老那半）"]++;
      return;
    }
    const box = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    el.setAttribute("data-probe08", String(key));
    // 祖先里有没有渐变（`.card` 那种）——记下来：probe-07 的禁用桶就是被这条滤空的
    let ancGrad = false;
    for (let n = el.parentElement; n; n = n.parentElement) {
      if (getComputedStyle(n).backgroundImage !== "none") { ancGrad = true; break; }
    }
    out.shots.push({
      key: String(key), tab: TAB, idx: bucket === "form" ? (seenForm.get(form) || 0) : seen.legacy,
      sel: path(el), slug: slug(path(el)), form: form || "",
      // `<input>` / `<textarea>` 的字在 `value` 里、不在 `textContent` 里——两处都取
      // （空串 = 这一格**没有字形像素**，读数半会跳过它的比值，不拿边框像素当证据）
      text: text.slice(0, 40),
      tag: el.tagName.toLowerCase(), how, subtree,
      color: cs.color, background: cs.backgroundColor, border: cs.borderTopColor,
      opacity: Number(cs.opacity), fontSize: cs.fontSize,
      ownGradient: cs.backgroundImage !== "none", ancestorGradient: ancGrad,
      behind: behindOf(el),
      box: { x: Math.round(box.x), y: Math.round(box.y),
        width: Math.round(box.width), height: Math.round(box.height) },
    });
    if (bucket === "form") seenForm.set(form, (seenForm.get(form) || 0) + 1);
    else seen.legacy++;
    key++;
  };

  // **登记表那一半先收**（它是靶子）：整块 + 它的文字子元素（后面那些才有
  // "说明字 / 原因行 / 提示行"的比值），再收老那半。
  for (const f of FORMS) {
    for (const el of root.querySelectorAll(f.sel)) {
      push(el, `登记表 ${f.sel}`, f.sel, true, "form");
      for (const d of el.querySelectorAll("*")) {
        if (hasText(d)) push(d, `登记表 ${f.sel} · 文字`, f.sel, false, "form");
      }
    }
  }
  for (const el of root.querySelectorAll("*")) {
    if (el.disabled === true) push(el, "disabled 属性", "", false, "legacy");
    else if (typeof el.className === "string" && el.classList.contains("disabled")) push(el, ".disabled 类", "", false, "legacy");
  }
  return out;
};

/** 把页签切过去：`page.click` 要求元素**可见**，而隐藏页签里的控件是 `display:none` 的
 *  ——准备代码第一步都得先点页签，否则那条路径会静默失败（第一次跑就是这么失败的）。 */
const focusTab = (page, tab) => page.click(`nav button[data-tab="${tab}"]`, { timeout: 8000 }).catch(() => {});

// —— 每个页签的**最少操作路径**（工单 02）：让"初始态看不见"的形态出现。
//    每步都返回一句人话（**成功与失败都报**）：造不出来的要能在读数里看见原因，
//    不能静默变成"这个页签本来就没有那种形态"。 ——
const PREPARE = {
  // 检测页：选 STM32 + 搜 sr04（只有 mspm0 条目的件 → 器件网格里出现 `.module-card.off`）。
  // ⚠ 第一步必须**先点页签**：隐藏面板里的控件是 `display:none`，`page.click` 会等超时。
  hwcheck: async (page) => {
    await focusTab(page, "hwcheck");
    await page.click('[data-hwcheck-platform="stm32"]', { timeout: 8000 }).catch(() => {});
    await page.fill("#hwcheck-device-search", "sr04", { timeout: 8000 }).catch(() => {});
    const ok = await page.waitForSelector("#hwcheck-device-grid .module-card.off", { timeout: 15000 })
      .then(() => true).catch(() => false);
    return ok ? "点了 STM32 + 搜 sr04 → `.module-card.off`（单平台件）"
      : "**没造出来**：点了 STM32 + 搜 sr04，但 15 s 内没等到 `.module-card.off`";
  },
  // 生成页：`.param-stale` 住在这里（`#params-grid` 在 `#tab-generate` 的 `#card-revise`
  // **卡内页签**「参数速调」里——不是代码页，第一次按名字猜错了页签，量到一排 0 尺寸）。
  // 造一份"锚已失效"的参数表（**不跑生成、不调 LLM**：写三个文件 + 走真 `reviseLoad`）。
  generate: async (page) => {
    mkdirSync(PARAM_DIR, { recursive: true });
    writeFileSync(join(PARAM_DIR, "main.c"),
      "/* probe-08 夹具：main.c 与参数表里的 anchor 对不上 ⇒ 参数卡判 stale */\n"
      + "int main(void) { return 0; }\n", "utf8");
    // 认平台用：`/api/revise/context` 无清单时按工程配置文件后缀反推（stm32 = .uvprojx）
    writeFileSync(join(PARAM_DIR, "probe.uvprojx"), "<Project/>\n", "utf8");
    writeFileSync(join(PARAM_DIR, ".contest_params.json"), JSON.stringify({
      version: 1, generated_at: "2026-10-01T00:00:00",
      params: [{ name: "PROBE_THRESHOLD", label: "演示阈值", old_value: "800",
        anchor: "#define PROBE_THRESHOLD 800", unit: "ms", range_hint: "0–3000" }],
    }, null, 2), "utf8");
    await focusTab(page, "generate");
    const res = await page.evaluate(async (dir) => {
      const m = await import("/js/ui/generate-revise.js");
      try {
        await m.reviseLoad(dir);          // 真加载：设 outputDir + 派发 revise-context-loaded → 参数簇去读表
        for (let i = 0; i < 40; i++) {
          if (document.querySelector("#params-grid .param-stale")) return { ok: true };
          await new Promise((r) => setTimeout(r, 150));
        }
        return { ok: false, why: "`#params-grid .param-stale` 6 s 内没出现" };
      } catch (e) {
        return { ok: false, why: String((e && e.message) || e) };
      }
    }, PARAM_DIR).catch((e) => ({ ok: false, why: String(e.message) }));
    if (!res.ok) return `**没造出来**：${res.why}`;
    // `#params-grid` 住在**卡内页签** `#revise-panel-params` 里（默认 `hidden`）——
    // 不切过去，元素在、`getBoundingClientRect()` 全是 0。
    await page.click('#revise-tabs .revise-tab[data-tab="params"]', { timeout: 8000 }).catch(() => {});
    const visible = await page.waitForFunction(() => {
      const el = document.querySelector("#params-grid .param-stale");
      if (!el) return false;
      const r = el.getBoundingClientRect();
      return r.width > 4 && r.height > 4;
    }, undefined, { timeout: 10000 }).then(() => true).catch(() => false);
    return visible ? `锚失效的参数表 + 真 \`reviseLoad\` + 切到卡内页签「参数速调」（\`${PARAM_DIR}\`）→ \`.param-stale\``
      : "**没造出来**：参数卡渲染出来了，但切到卡内页签后 10 s 内仍是零尺寸";
  },
};

/** 浮层（引脚菜单）**单开一趟**：它盖住整页，和面板里的元素混在一趟里拍，
 *  面板那几张会被浮层糊掉（本轮实测的设计约束）。菜单挂在 `body` 下、不在 `#tab-generate` 里。
 *
 *  **2026-10-01 口径修正（工单 `contrast-residue/05`）**——上一版量不到 `li.cant`，原因是三处：
 *    ① 平台选的是 **STM32**：它的 uart 是纯类型级 selectable、i2c 没有实例 token，
 *       默认形态下**根本不会出 `cant`**（要人为先占住"同实例的对脚"才行）；
 *    ② 模块选的是"第一张可点的卡"，未必有单端口宏那一族角色；
 *    ③ 点圆点前**没有等判据模型**：模型未到时 `pinCanHost` 降级成类型级 ⇒ 一行 `cant` 都不出。
 *  现在：**MSPM0 + `step_motor` + 点第一根脚**——`step_motor` 的 4 个 gpio_out 角色默认全在 B 口，
 *  后端因此下发 `{kind:"port", port:"B"}` 约束（`pin_bindings.py`），点 A 口的脚（PA0）当场 4 行
 *  `li.cant`，**零预备绑定**。等价备选：MSPM0 + `nrf24l01` → 点任意 B 口脚 ⇒ 6 行。
 *
 *  返回 `{ note, open }`：`open` = 菜单确实开着（可以收一趟）；`note` 里**分开报**两件事
 *  ——"菜单能不能开"与"里面有没有 `li.cant`"。 */
async function prepareOverlay(page, tab) {
  if (tab !== "generate") return null;
  await focusTab(page, "generate");
  await page.locator("#platforms .platform-card", { hasText: "MSPM0" }).first()
    .click({ timeout: 8000 }).catch(() => {});
  const cards = await page.waitForFunction(
    () => document.querySelectorAll("#module-grid .module-card:not(.off)").length > 0,
    undefined, { timeout: 20000 }).then(() => true).catch(() => false);
  if (!cards) return { note: "**没造出来**：等了 20 s，生成页的模块网格里没有可选的卡", open: false };
  // 判据模型那一发要在**加模块之前**就挂上等（请求由加模块触发）
  const matrix = page.waitForResponse(
    (r) => r.url().includes("/api/bindings/matrix") && r.status() === 200,
    { timeout: 25000 }).catch(() => null);
  await page.fill("#module-search", "step_motor", { timeout: 8000 }).catch(() => {});
  const card = page.locator('#module-grid .module-card[data-add="step_motor"]').first();
  const had = await card.count();
  if (had) await card.click({ timeout: 8000 }).catch(() => {});
  const pinned = await page.waitForSelector("#pin-board-svg circle[data-pin]", { timeout: 20000 })
    .then(() => true).catch(() => false);
  if (!pinned) return { note: "**没造出来**：选了模块，但 20 s 内引脚图上没有 `circle[data-pin]`", open: false };
  // ⚠ **等判据模型**：模型未到时 `pinCanHost` 降级成类型级，一行 `cant` 都不会出（假红的主要来源）。
  // ⚠ 草稿恢复那条路（`had` 为假）**不会再发** `/api/bindings/matrix`——那时模型早就在位，
  //    拿"等不到新响应"去判它会得到假的"没等到"（第一版就这样冤枉了暗色那一趟）。
  const gotMatrix = had ? await matrix : true;
  await page.waitForFunction(() => {
    const cap = document.getElementById("pin-board-caption");
    const t = cap ? cap.textContent || "" : "";
    return !t.includes("正在核对可绑引脚") && !t.includes("判据加载失败");
  }, undefined, { timeout: 15000 }).catch(() => {});
  const draftNote = had ? "" : "（`step_motor` 的卡不在网格里 = 草稿已恢复，跳过添加）";
  const circles = await page.locator("#pin-board-svg circle[data-pin]").all();
  let opened = 0, tried = 0;
  for (const c of circles.slice(0, 40)) {
    tried++;
    await c.click({ force: true }).catch(() => {});
    const st = await page.evaluate(() => ({
      menu: !!document.querySelector(".pin-menu-overlay"),
      cant: document.querySelectorAll(".pin-menu-list li.cant").length,
      rows: document.querySelectorAll(".pin-menu-list li").length,
    }));
    if (st.menu) opened++;
    if (st.cant) {
      return { note: `MSPM0 + step_motor + 第 ${tried} 根脚 → 引脚菜单里有 **${st.cant} 条 \`li.cant\`**`
        + `（判据模型 ${gotMatrix ? "已到位" : "**没等到**（降级态下也可能有 cant，读数要打折）"}）`
        + `（第 ${tried} 根脚试中）`,
      open: true };
    }
    if (st.menu) await page.keyboard.press("Escape").catch(() => {});   // 菜单挡住下一脚：先关掉再试
  }
  return {
    note: `引脚菜单**能开**（试了 ${tried} 根脚，${opened} 次开成）但没有一条 \`li.cant\``
      + `（判据模型 ${gotMatrix ? "已到位" : "**没等到**——这一发不可信，先查等待那一步"}）`
      + "。**这一处靶子没量到**",
    open: opened > 0,
  };
}

/** 收一趟 + 当场拍。`scope` = `"panel"`（页签面板）/ `"overlay"`（引脚菜单浮层）。
 *  **文件名必须唯一**：第一版用"分桶计数 idx + slug"，两个桶各自从 0 数、slug 又截 28 字
 *  ⇒ **同名覆盖**（`#params-input-PROBE_THRESHOLD` 覆盖了 `.param-card-head > .slug`），
 *  读数半读到的就是别的元素的像素（评审逮到的假证据）。现在用**这一趟内全局唯一的 `key`**
 *  （`data-probe08` 那个编号）+ scope 一起拼，撞名不可能。 */
async function shootPass(page, theme, tab, scope, shots, notes) {
  const data = await page.evaluate(COLLECT,
    { tab, max: MAX_SHOTS, maxForm: MAX_FORM_SHOTS, scope, forms: DISABLED_FORMS });
  if (data.missing) {
    console.log(`  ${tab.padEnd(10)}${scope === "overlay" ? "（没有浮层）" : "（没找到页签 / 面板）"}`);
    notes.push({ theme, tab, scope, missing: true });
    return;
  }
  // **"没量到"的账要跟着读数一起落盘**（评审点名：只在控制台里，等于没记账）
  notes.push({ theme, tab, scope, hit: data.disabled, shot: data.shots.length,
    skipped: data.skipped, skippedDetail: data.skippedDetail || [], failedShots: [] });
  const skipped = Object.entries(data.skipped).filter(([, n]) => n)
    .map(([k, n]) => `${k} ${n}`).join(" / ");
  console.log(`  ${tab.padEnd(10)}${scope === "overlay" ? "[浮层] " : ""}命中 ${String(data.disabled).padStart(2)}`
    + `　拍得 ${data.shots.length}` + (skipped ? `　**没量到**：${skipped}` : ""));
  for (const d of data.skippedDetail || []) console.log(`      · 没量到：${d}`);
  let shotFail = 0;
  for (const s of data.shots) {
    const file = `probe-08-${TAG}-${theme}-${s.tab}-${scope}-${s.key}-${s.slug}.png`;
    // 元素截图：Playwright 会先把它滚进视口（页面上加了 `data-probe08` 标记，不影响外观）
    // ⚠ **先拍再收**：拍不到就不留这一行——盘上没有 PNG 而 JSON 里有格子，
    // 读数半会去读一个不存在的文件（第一次跑就是这么留下两行幽灵格的）。
    const shot = await page.locator(`[data-probe08="${s.key}"]`).screenshot({ path: join(OUT, file), timeout: 15000 })
      .then(() => true).catch(() => false);
    if (!shot) {
      shotFail++;
      console.log(`      ⚠ 截图失败（${s.sel} ｜ <${s.tag}> ｜ ${s.box.width}×${s.box.height}）——这一格**没量到**，不写进 JSON`);
      notes[notes.length - 1].failedShots.push({ sel: s.sel, tag: s.tag, how: s.how,
        box: `${s.box.width}×${s.box.height}`, text: s.text });
      continue;
    }
    shots.push({ theme, scope, ...s, file });
    console.log(`    ${s.how.padEnd(24)} opacity ${s.opacity}  ${s.color} on ${s.background}`
      + `  「${s.text}」${s.ancestorGradient ? "  ⚠祖先渐变" : ""}  → ${file}`);
  }
  if (shotFail) console.log(`      ⚠ 本轮截图失败 ${shotFail} 格（原因见上；它们不在 JSON 里）`);
  // 擦掉标记，别让下一轮看到上一轮的 residue
  await page.evaluate(() => {
    for (const el of document.querySelectorAll("[data-probe08]")) el.removeAttribute("data-probe08");
  });
}

const server = await startServer();
const browser = await chromium.launch();
const shots = [];
const notes = [];          // "没量到"与"准备"的账（跟着 JSON 一起落盘）
const prepares = [];
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(600);
    console.log(`\n===== ${theme} =====`);
    for (const tab of TABS) {
      // **一个页签收一次、当场拍**：切走之后那个面板 `display:none`，元素截图会超时
      // （第一版就是一口气收完全部页签再拍，撞在这上面）。
      const prep = PREPARE[tab] ? await PREPARE[tab](page).catch((e) => `**准备抛错**：${e.message}`) : null;
      if (prep) { console.log(`  ${tab.padEnd(10)}准备：${prep}`); prepares.push({ theme, tab, note: prep }); }
      await shootPass(page, theme, tab, "panel", shots, notes);
      const menu = await prepareOverlay(page, tab).catch((e) => ({ note: `**准备（浮层）抛错**：${e.message}`, open: false }));
      if (menu) {
        console.log(`  ${tab.padEnd(10)}准备（浮层）：${menu.note}`);
        prepares.push({ theme, tab, note: `（浮层）${menu.note}` });
        if (menu.open) {
          await shootPass(page, theme, tab, "overlay", shots, notes);
          // **拍完就关**：浮层盖住整页，留着它下一个页签的元素截图上会糊着它
          await page.keyboard.press("Escape").catch(() => {});
          await page.evaluate(() => {
            for (const o of document.querySelectorAll(".pin-menu-overlay")) o.remove();
          });
        }
      }
    }
  }
  writeFileSync(join(OUT, `probe-08-shots-${TAG}.json`),
    JSON.stringify({ tag: TAG, forms: DISABLED_FORMS, prepares, notes, shots }, null, 2), "utf8");
  console.log(`\n已落盘 ${join(OUT, `probe-08-shots-${TAG}.json`)}（${shots.length} 格；`
    + `准备 ${prepares.length} 条、"没量到"账 ${notes.length} 条也写进了 JSON）`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
