// .scratch/pin-type-contrast/probe-01-pin-family-pixels.mjs —— **引脚类型配色族的真像素量具**
// （工单 `pin-type-contrast/01` 立）。
//
// ## 它为什么存在
//
// 这一族（角色类型标 / 状态文字 / 板图引脚名 / 色点）的取色住在 `generate-pins.js` 的
// `PIN_TYPE_STYLE` 表里，渲染时用模板串拼进内联 `style`——**腿⑨ 的认人正则认不到**，
// 所以它的比值从没被任何静态判据看过。`contrast-residue/05` 顺带量到一格（`.role-type`
// 浅 3.54 / 暗 4.94），本批要的是**整族、两主题、四个面**的对照读数：
// 改前基线（本单）与改后复核（收尾单）用**同一套配方**，逐格可比。
//
// ## 它复用谁（不另起一套量具）
//
//   · **机架**：`tests/browser/server.mjs` 的 `startServer`（真后端 + 真静态资源 + 独立数据目录）
//     ＋真 Chromium ＋**逐元素截图**（一个元素一张 PNG，可人眼复核）＋ JSON 里连
//     "静态预测的原料"一起记（computed `color` / `background` / SVG `fill`、`stroke`、
//     祖先合成底 `behind`、板图 PCB 底色 `pcbFill`）——形状照 `code-contrast/probe-08`；
//   · **读像素**：`.scratch/code-contrast/pixel_lib.py`（直方图 → 主色（底）→ 字形核心）；
//   · **颜色数学 / 令牌**：`.scratch/light-contrast/probe_lib.py`（与守卫腿⑧ 同源、镜像守卫钉住）。
//
// ⚠ **为什么另写一支、而不是往 `probe-08` 里塞**：`probe-08` 的认人面是**不可选形态登记表**
// 驱动的（它扫的是 `.pin-menu-list li.cant` 那类），往它身上再挂一套"引脚族四类元素"会把两件
// 事的口径搅在一起（一个量具两套认人面 = 下一轮读不懂任何一份读数）。这里只借机架与形状。
//
// ## 配方（"为什么是这几步"）
//
//   · **平台 = MSPM0**：库内 `spi_*` / `exti` 两个类型**零实例**（两支 recon 实测，见
//     `recon-03-mspm0.txt` / `recon-03-stm32.txt`），所以今天盘上真能出的是 **6 个色族**：
//     gpio / pwm / enc / uart / i2c / adc。spi 与 exti 的令牌仍在，只是没有角色能造出来——
//     读数如实记"造不出"，不当通过。
//   · **模块集 = `motor` + `adc` + `as32` + `i2c_probe`**：按 `pins[].type` 反查库贪心选出的
//     最小覆盖集（`recon-03-module-types.py`），四件合起来覆盖六个族。
//   · **先展开可选角色**：默认只列必接角色，可选的那些藏在「显示 N 个可选角色」后面——
//     不展开就会漏掉一部分色族（这是最容易"静默少几格"的一步）。
//   · **每个族至少绑一根线**（真 UI：点板图圆点 → 菜单里点该族第一条可绑行）：状态文字
//     （「已绑 X」）与板图上已绑引脚的**名字**都只在有绑定时才带类型色。
//     `#btn-pin-auto` **不够**——它只解冲突、不做全量绑定（点完多数角色仍是"默认 X"）。
//   · **引脚菜单单开一趟**：菜单是浮层、盖住整页，和面板里的元素混在一趟里拍会互相糊。
//
// ## 跑法（仓库根；跑完接 `probe-01-read.py`）
//
//     node .scratch/pin-type-contrast/probe-01-pin-family-pixels.mjs --tag before
//     node .scratch/pin-type-contrast/probe-01-pin-family-pixels.mjs --tag after
//
// ⚠ 不要与全量 pytest 同时跑（本机负载下浏览器会抖）；读数的**时间戳必须晚于最后一次
//    改产品面**（`ui-density-sitewide` 那条纪律）。
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
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
const OUT = OUT_ARG ? join(HERE, "..", "..", OUT_ARG) : HERE;
mkdirSync(OUT, { recursive: true });

/** 反查库得来的最小覆盖集（`recon-03-module-types.py` 的读数，别手改——改了要重跑那支）。 */
const MODULES = ["motor", "adc", "as32", "i2c_probe"];
/** 八个色族（类型前缀）；`spi` / `exti` 今天库里零实例——读数会如实记"造不出"。 */
const FAMILIES = ["gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"];
const MAX_PER_FACE = 40;   // 每个面最多拍这么多格（防"页面上一堆元素"把靶子挤掉）

const familyOfType = (t) => FAMILIES.find((f) => (t || "").startsWith(f)) || "";

// ⚠ `COLLECT` 是 `page.evaluate` 的载荷，会被**序列化后丢进浏览器**，看不到模块作用域
// ——所以 `parse` / `behindOf` / `path` / `slug` / `visible` 必须自带一份（`probe-08` 同理）。
const COLLECT = (payload) => {
  // ⚠ `FAMILIES` 必须**随载荷传进来**：这个函数被序列化丢进浏览器，看不到模块作用域
  const { maxPerFace, families: FAMILIES, scope: SCOPE } = payload;
  const out = { theme: document.documentElement.dataset.theme || "dark", rows: [], missing: false,
    counts: {}, skipped: { 不可见: 0, 零尺寸: 0, 无文字: 0, 超过上限: 0, 非家族色: 0 }, skippedDetail: [] };
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
  const path = (el) => {
    const bits = [];
    for (let n = el; n && bits.length < 3; n = n.parentElement) {
      bits.unshift(n.id ? `#${n.id}` : (typeof n.className === "string" && n.className.trim()
        ? "." + n.className.trim().split(/\s+/).slice(0, 2).join(".") : n.tagName.toLowerCase()));
    }
    return bits.join(" > ");
  };
  const slug = (s) => s.replace(/[^\w\u4e00-\u9fa5]+/g, "-").replace(/^-|-$/g, "").slice(0, 28);
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) < 0.05) return "不可见";
    const box = el.getBoundingClientRect();
    if (box.width < 3 || box.height < 3) return "零尺寸";
    return null;
  };

  const root = document.getElementById("tab-generate");
  if (!root) { out.missing = true; return out; }
  // ⚠ **浮层那一趟只收菜单里的元素**：菜单盖住整页，面板里的元素这趟拍下来的是菜单的像素
  //   （第一版没收这条，白拍了 100 多张"被糊住"的 PNG——读数半当场报出 6.41 vs 1.42 这种差）。
  const OVERLAY_ONLY = SCOPE === "overlay";
  for (const d of root.querySelectorAll("details:not([open])")) d.open = true;
  // 板图 PCB 本体 = 第一块 rect（`renderPinBoard` 里那句 `fill=pinBoard.pcb_color || var(--pin-pcb)`）：
  // 板上引脚名压在它上面，静态预测要用它当底（`behind` 只走 HTML 背景，看不见 SVG 的 fill）。
  const pcb = root.querySelector("#pin-board-svg rect");
  const pcbFill = pcb ? getComputedStyle(pcb).fill : "";

  let key = 0;
  const push = (el, face, note, familyHint) => {
    if (!el) return;
    const why = visible(el);
    if (why) {
      out.skipped[why]++;
      if (out.skippedDetail.length < 12) out.skippedDetail.push(`${face} ${note || ""} —— ${why}`);
      return;
    }
    const n = out.counts[face] || 0;
    if (n >= maxPerFace) {
      out.skipped.超过上限++;
      if (out.skippedDetail.length < 12) out.skippedDetail.push(`${face} ${note || ""} —— 超过上限`);
      return;
    }
    out.counts[face] = n + 1;
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    el.setAttribute("data-probe01", String(key));
    out.rows.push({
      key: String(key), face, note: note || "", familyHint: familyHint || "",
      tag: el.tagName.toLowerCase(), sel: path(el), slug: slug(path(el)),
      text: String(el.textContent || "").trim().slice(0, 40),
      color: cs.color, background: cs.backgroundColor,
      fill: cs.fill, stroke: cs.stroke, strokeWidth: cs.strokeWidth, fillOpacity: cs.fillOpacity,
      border: cs.borderTopColor, opacity: Number(cs.opacity), fontSize: cs.fontSize,
      behind: behindOf(el), pcbFill,
      box: { x: Math.round(box.x), y: Math.round(box.y),
        width: Math.round(box.width), height: Math.round(box.height) },
    });
    key++;
  };

  // ① 角色类型标 + ② 状态文字（同一个 `.pin-role` 里；类型从标上读，状态文字靠它认族）
  //    **认族 = 读 `data-pin-family` 属性**（工单 pin-type-contrast/02 之后渲染方就挂着它）：
  //    比"拿颜色去猜族"可靠得多——03 单把文字档与主色拆开之后，**同族两个颜色**，
  //    颜色反查会当场失手（实测：色点从 8 格掉到 4 格、焊盘 8 → 3，读数表跟着缩水）。
  const famOf = (el) => (el && el.dataset && el.dataset.pinFamily) || "";
  if (!OVERLAY_ONLY) {
    for (const role of root.querySelectorAll("#pin-role-items .pin-role")) {
      const badge = role.querySelector(".role-type");
      const type = badge ? String(badge.textContent || "").trim() : "";
      const fam = famOf(badge) || FAMILIES.find((f) => type.startsWith(f)) || "";
      const key2 = role.dataset.role || "";
      push(badge, "badge", `角色 ${key2}`, type);
      for (const sp of role.querySelectorAll(".role-status span")) {
        const famSp = famOf(sp);
        if (!famSp) {                          // 非家族色（`--danger-text` / `--warn-text` / `--muted`）如实记账
          out.skipped.非家族色++;
          continue;
        }
        push(sp, "status", `角色 ${key2}`, famSp);
      }
    }
    // ③ 图例色点（含"空闲 IO / 板载共用 / 固定电源"三个非族色点——它们没有属性，如实跳过）
    for (const lg of root.querySelectorAll("#pin-legend .lg")) {
      const dot = lg.querySelector(".dot");
      if (!famOf(dot)) { out.skipped.非家族色++; continue; }
      push(dot, "legend-dot", String(lg.textContent || "").trim(), famOf(dot));
    }
    // ④ 板图焊盘（填充 = 淡化色、描边 = 主色）+ ⑤ 板图引脚名（fill = 文字档，仅已绑脚）
    for (const c of root.querySelectorAll("#pin-board-svg circle[data-pin]")) {
      if (!famOf(c)) { out.skipped.非家族色++; continue; }
      push(c, "board-pad", c.dataset.pin || "", famOf(c));
    }
    for (const t of root.querySelectorAll("#pin-board-svg text")) {
      if (!famOf(t)) { out.skipped.非家族色++; continue; }
      push(t, "board-label", String(t.textContent || "").trim(), famOf(t));
    }
  }
  // ⑥ 引脚菜单（浮层那一趟）：类型标 + 色点
  const menu = document.querySelector(".pin-menu-overlay");
  if (menu) {
    for (const li of menu.querySelectorAll(".pin-menu-list li")) {
      const badge = li.querySelector(".role-type");
      const type = badge ? String(badge.textContent || "").trim() : "";
      const fam = famOf(badge) || FAMILIES.find((f) => type.startsWith(f)) || "";
      const note = li.classList.contains("cant") ? "不兼容行" : "可绑行";
      push(badge, "menu-badge", `${note} ${type}`, fam);
      const dot = li.querySelector(".dot");
      if (dot && famOf(dot)) push(dot, "menu-dot", `${note} ${type}`, famOf(dot));
    }
  }
  return out;
};

const focusTab = (page, tab) => page.click(`nav button[data-tab="${tab}"]`, { timeout: 8000 }).catch(() => {});

/** 选平台 + 加模块 + 展开可选角色。返回一句人话（成功与失败都报）。 */
async function preparePins(page) {
  await focusTab(page, "generate");
  await page.locator("#platforms .platform-card", { hasText: "MSPM0" }).first()
    .click({ timeout: 8000 }).catch(() => {});
  const cards = await page.waitForFunction(
    () => document.querySelectorAll("#module-grid .module-card:not(.off)").length > 0,
    undefined, { timeout: 20000 }).then(() => true).catch(() => false);
  if (!cards) return "**没造出来**：等了 20 s，生成页的模块网格里没有可选的卡";
  const added = [], missing = [];
  for (const slug of MODULES) {
    await page.fill("#module-search", slug, { timeout: 8000 }).catch(() => {});
    const card = page.locator(`#module-grid .module-card[data-add="${slug}"]`).first();
    if (await card.count()) {
      await card.click({ timeout: 8000 }).catch(() => {});
      added.push(slug);
    } else {
      missing.push(slug);   // 已选过的模块不再出现在网格里；真缺了就是库变了
    }
    await page.waitForTimeout(250);
  }
  const pinned = await page.waitForSelector("#pin-board-svg circle[data-pin]", { timeout: 20000 })
    .then(() => true).catch(() => false);
  if (!pinned) return `**没造出来**：加了模块，但 20 s 内引脚图上没有 \`circle[data-pin]\`（加入：${added.join("、")}）`;
  // 判据模型（`/api/bindings/matrix`）到位之后才能绑脚（模型未到时 `pinCanHost` 降级成类型级）
  await page.waitForFunction(() => {
    const cap = document.getElementById("pin-board-caption");
    const t = cap ? cap.textContent || "" : "";
    return !t.includes("正在核对可绑引脚") && !t.includes("判据加载失败");
  }, undefined, { timeout: 20000 }).catch(() => {});
  // **展开可选角色**：不展开就漏族
  const more = page.locator("#btn-pin-show-optional");
  let expanded = false;
  if (await more.count()) { await more.click({ timeout: 8000 }).catch(() => {}); expanded = true; }
  const types = await page.evaluate(() => [...document.querySelectorAll("#pin-role-items .role-type")]
    .map((el) => (el.textContent || "").trim()));
  const fams = [...new Set(types.map((t) => t.split("_")[0]))].sort();
  return `MSPM0 + 模块 ${added.join("、")}${missing.length ? `（网格里没找到：${missing.join("、")}）` : ""}`
    + ` + ${expanded ? "展开可选角色" : "**没找到「显示可选角色」按钮**"}`
    + ` → 角色类型 ${types.length} 个，覆盖族 ${fams.join("/")}`;
}

/** 每个族至少绑一根线（真 UI：点圆点 → 菜单里点该族第一条可绑行）。
 *  `#btn-pin-auto` 只解冲突、不做全量绑定，所以这里必须自己绑。
 *
 *  ⚠ **同脚让位**（`freePin`）：把 X 绑到已被 Y 占用的脚上时，**Y 会被解除绑定**。
 *  所以顺序绑完一轮之后必须**回头复验**、把被挤掉的族补回来（实测：第一版一轮绑完，
 *  enc / gpio 的绑定就被后面的族挤掉了，状态文字那一面少了两族的格子）。
 *  挑脚时**优先挑空脚**，减少这种互相挤。 */
async function ensureBindings(page) {
  const snapshot = () => page.evaluate(() => ({
    roles: [...document.querySelectorAll("#pin-role-items .pin-role")].map((el) => ({
      type: String((el.querySelector(".role-type") || {}).textContent || "").trim(),
      status: String((el.querySelector(".role-status") || {}).textContent || "").trim(),
    })),
    circles: [...document.querySelectorAll("#pin-board-svg circle[data-pin]")]
      .map((c) => c.dataset.pin || ""),
  }));
  const autoBtn = page.locator("#btn-pin-auto");
  let autoMsg = "（没有自动配置按钮）";
  if (await autoBtn.count()) {
    await autoBtn.click({ timeout: 8000 }).catch(() => {});
    await page.waitForFunction(() => {
      const b = document.getElementById("btn-pin-auto");
      return b && !b.disabled;
    }, undefined, { timeout: 20000 }).catch(() => {});
    autoMsg = await page.evaluate(() => {
      const m = document.getElementById("pin-config-msg");
      return m ? String(m.textContent || "").trim().replace(/\s+/g, " ").slice(0, 60) : "";
    });
  }
  /** 一族的绑定状态：`present` = 库里有这族的角色（没有 = 库内零实例）。 */
  const stateOf = async (snap) => {
    const st = {};
    for (const fam of FAMILIES) {
      const rs = snap.roles.filter((r) => r.type.startsWith(fam));
      st[fam] = { present: rs.length > 0,
        bound: rs.filter((r) => r.status.includes("已绑")).length,
        occupied: new Set(snap.roles.filter((r) => r.status.includes("已绑"))
          .map((r) => (r.status.match(/已绑\s+(\S+)/) || [])[1]).filter(Boolean)) };
    }
    return st;
  };
  const boundOnce = async (fam, occupied) => {
    const circles = (await page.locator("#pin-board-svg circle[data-pin]").all());
    const names = (await page.evaluate(() => [...document.querySelectorAll("#pin-board-svg circle[data-pin]")]
      .map((c) => c.dataset.pin || "")));
    // **空脚优先**（减少同脚让位带来的连锁解除）
    const order = names.map((n, i) => [n, i]).sort((a, b) =>
      (occupied.has(a[0]) ? 1 : 0) - (occupied.has(b[0]) ? 1 : 0) || a[1] - b[1]);
    for (const [, i] of order.slice(0, 40)) {
      const c = circles[i];
      if (!c) continue;
      await c.click({ force: true }).catch(() => {});
      const ok = await page.evaluate((f) => {
        const li = [...document.querySelectorAll(".pin-menu-list li.can")].find((x) => {
          const b = x.querySelector(".role-type");
          return b && String(b.textContent || "").trim().startsWith(f);
        });
        if (!li) return false;
        li.click();
        return true;
      }, fam).catch(() => false);
      if (ok) { await page.waitForTimeout(280); return true; }
      await page.keyboard.press("Escape").catch(() => {});
      await page.evaluate(() => {
        for (const o of document.querySelectorAll(".pin-menu-overlay")) o.remove();
      });
    }
    return false;
  };
  const log = [];
  for (let round = 1; round <= 3; round++) {
    const st = await stateOf(await snapshot());
    const todo = FAMILIES.filter((f) => st[f].present && st[f].bound === 0);
    const absent = FAMILIES.filter((f) => !st[f].present);
    if (!todo.length) {
      log.push(`第 ${round} 轮：${FAMILIES.filter((f) => st[f].present).map((f) =>
        `${f}×${st[f].bound}`).join(" ")}（复验通过）`
        + (absent.length ? `；库内零实例：${absent.join("、")}` : ""));
      break;
    }
    const done = [];
    for (const fam of todo) {
      const st2 = await stateOf(await snapshot());
      const ok = await boundOnce(fam, st2[fam].occupied);
      done.push(`${fam}:${ok ? "绑上" : "**没绑上**（40 根脚里没有可绑行）"}`);
    }
    log.push(`第 ${round} 轮：${done.join(" ")}`
      + (absent.length ? `；库内零实例：${absent.join("、")}` : ""));
  }
  const fin = await stateOf(await snapshot());
  log.push("最终：" + FAMILIES.map((f) => (fin[f].present ? `${f}×${fin[f].bound}` : `${f}=零实例`)).join(" "));
  return `自动配置：${autoMsg || "（空）"}；${log.join("；")}`;
}

/** 开一个引脚菜单（优先挑**类型最多的那一根脚**，菜单里才有多族可拍）。 */
async function openPinMenu(page) {
  const circles = await page.locator("#pin-board-svg circle[data-pin]").all();
  for (const c of circles.slice(0, 40)) {
    await c.click({ force: true }).catch(() => {});
    const info = await page.evaluate(() => {
      const menu = document.querySelector(".pin-menu-overlay");
      if (!menu) return null;
      const types = [...menu.querySelectorAll(".pin-menu-list li .role-type")]
        .map((el) => (el.textContent || "").trim());
      return { rows: menu.querySelectorAll(".pin-menu-list li").length,
        types: [...new Set(types)].length };
    }).catch(() => null);
    if (info && info.types >= 2) return { open: true, note: `菜单 ${info.rows} 行 / ${info.types} 个类型` };
    await page.keyboard.press("Escape").catch(() => {});
    await page.evaluate(() => {
      for (const o of document.querySelectorAll(".pin-menu-overlay")) o.remove();
    });
  }
  return { open: false, note: "**没造出来**：试了 40 根脚，没有菜单里带 ≥2 个类型的" };
}

/** 收一趟 + 当场拍。`scope` = `"panel"` / `"overlay"`。 */
async function shootPass(page, theme, scope, rows, notes) {
  const data = await page.evaluate(COLLECT, { maxPerFace: MAX_PER_FACE, families: FAMILIES, scope });
  if (data.missing) {
    notes.push({ theme, scope, missing: true });
    console.log(`  ${scope.padEnd(8)}（没找到生成页面板）`);
    return;
  }
  notes.push({ theme, scope, counts: data.counts, skipped: data.skipped,
    skippedDetail: data.skippedDetail || [], failedShots: [] });
  const skipped = Object.entries(data.skipped).filter(([, n]) => n)
    .map(([k, n]) => `${k} ${n}`).join(" / ");
  console.log(`  ${scope.padEnd(8)}四类元素：`
    + Object.entries(data.counts).map(([k, n]) => `${k} ${n}`).join("  ")
    + (skipped ? `　**没量到**：${skipped}` : ""));
  for (const d of data.skippedDetail || []) console.log(`      · 没量到：${d}`);
  let shotFail = 0;
  for (const s of data.rows) {
    const file = `probe-01-${TAG}-${theme}-${scope}-${s.face}-${s.key}-${s.slug}.png`;
    // ⚠ **先拍再收**：拍不到就不留这一行（盘上没有 PNG 而 JSON 里有格子 = 幽灵格）
    const shot = await page.locator(`[data-probe01="${s.key}"]`)
      .screenshot({ path: join(OUT, file), timeout: 15000 })
      .then(() => true).catch(() => false);
    if (!shot) {
      shotFail++;
      notes[notes.length - 1].failedShots.push({ face: s.face, sel: s.sel, text: s.text,
        box: `${s.box.width}×${s.box.height}` });
      continue;
    }
    rows.push({ theme, scope, ...s, file });
    console.log(`    ${s.face.padEnd(12)} ${String(s.text).slice(0, 14).padEnd(16)}`
      + ` color ${s.color}  bg ${s.background}  fill ${s.fill}  ${s.box.width}×${s.box.height}`);
  }
  if (shotFail) console.log(`      ⚠ 本轮截图失败 ${shotFail} 格（原因见上；它们不在 JSON 里）`);
  await page.evaluate(() => {
    for (const el of document.querySelectorAll("[data-probe01]")) el.removeAttribute("data-probe01");
  });
}

const server = await startServer();
const browser = await chromium.launch();
const rows = [];
const notes = [];
const prepares = [];
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  for (const theme of ["light", "dark"]) {
    // **清草稿、只留主题**：草稿恢复会让"这一趟加了哪些模块"不可控（`probe-08` 踩过）
    await page.evaluate((t) => {
      localStorage.clear();
      localStorage.setItem("firstep.theme", t);
    }, theme);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(600);      // 覆盖 0.15 s 的 color 过渡
    console.log(`\n===== ${theme} =====`);
    const prep = await preparePins(page).catch((e) => `**准备抛错**：${e.message}`);
    console.log(`  准备：${prep}`);
    prepares.push({ theme, tab: "generate", note: prep });
    if (String(prep).includes("没造出来")) {
      notes.push({ theme, scope: "panel", missing: true });
      continue;
    }
    const bind = await ensureBindings(page).catch((e) => `**绑脚抛错**：${e.message}`);
    console.log(`  绑脚：${bind}`);
    prepares.push({ theme, tab: "generate", note: `（绑定）${bind}` });
    await shootPass(page, theme, "panel", rows, notes);
    const menu = await openPinMenu(page).catch((e) => ({ open: false, note: `**开菜单抛错**：${e.message}` }));
    console.log(`  浮层：${menu.note}`);
    prepares.push({ theme, tab: "generate", note: `（浮层）${menu.note}` });
    if (menu.open) {
      await shootPass(page, theme, "overlay", rows, notes);
      await page.keyboard.press("Escape").catch(() => {});
      await page.evaluate(() => {
        for (const o of document.querySelectorAll(".pin-menu-overlay")) o.remove();
      });
    }
  }
  writeFileSync(join(OUT, `probe-01-shots-${TAG}.json`),
    JSON.stringify({ tag: TAG, modules: MODULES, families: FAMILIES, prepares, notes, rows }, null, 2),
    "utf8");
  console.log(`\n已落盘 ${join(OUT, `probe-01-shots-${TAG}.json`)}（${rows.length} 格；`
    + `准备 ${prepares.length} 条、"没量到"账 ${notes.length} 条也写进了 JSON）`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
