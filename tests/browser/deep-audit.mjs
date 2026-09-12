// 深挖审计（真机 playwright）：把只被「静态断言 + 功能验收」覆盖过的链路，往
// **边界 / 失败路径 / 中间帧时序 / 无障碍 / 几何**方向再压一遍。
//
// 与 tests/browser/module-intro.spec.mjs 的分工：那份是「功能对不对」的**验收**
// （断言式，进 CI 口径）；这份是「还有哪里会塌」的**审计**（报告式，可以带红，
// 红的地方就是待修的问题）。两者用同一套真机夹具（本目录 server.mjs）。
//
// 运行：node tests/browser/deep-audit.mjs            ← 全部 7 节
//       node tests/browser/deep-audit.mjs A C2 D     ← 只跑指定节（调试用）
// 依赖：python 后端可起（server.mjs 夹具）、playwright chromium。
// **不进** `node --test "tests/js/*.test.mjs"`：要起服务 + 开浏览器，改动推荐区 /
// 说明弹窗 / 展开链路时手动跑。
//
// 分节：A 入口全扫 · B 弹窗自身（叠层/焦点/懒加载）· C 收敛压测（盯中间帧）·
//       C2 单点时间线（请求体 / 响应时刻 / 帧三线对齐）· D 失败路径 · E 视口几何 ·
//       F 键盘可达 · G 弹窗内容质量。
//
// ⚠ **写判据前先读这段**：本脚本第一版有两条「铁证」最后被证伪——判据本身把**正确行为**
// 当成了 bug（把「已选（未展开依赖）：<当前选择>」这个合法占位读成「过期视图写回」）。
// 宣称发现 bug 之前，**必须**：① 把嫌疑逻辑改回原实现形状，确认现象仍在；
// ② 读一遍真正执行路径的源码，确认时序；③ 判据只描述「绝不该出现的事实」，
// 不要描述「我以为应该出现却没出现」。
import { chromium } from "playwright";
import { startServer } from "./server.mjs";

const RECOMMEND = {
  topic_id: "",
  modules: [
    { slug: "ir_beam", reason: "可选点/起始做辅助" },
    { slug: "pid", reason: "巡线核心" },
    { slug: "motor", reason: "驱动车轮" },
  ],
  requirements: [
    { sentence: 1, requirement: "检测物体是否经过", modules: ["ir_beam"], suggestions: [] },
    { sentence: 2, requirement: "沿黑线行驶", modules: ["pid", "motor"], suggestions: [] },
  ],
  exclusive_groups: [{
    id: "gray-track", label: "8 路灰度传感器驱动", hint: false, choice_required: true,
    members: [
      { slug: "huidu", role: "仅 8 路灰度读取，不含巡线核心" },
      { slug: "pid", role: "灰度 + PID 巡线" },
      { slug: "xunji", role: "加权质心巡线（开环）" },
    ],
    recommended: ["pid"], candidates: ["huidu", "xunji"], dropped: ["xunji"],
  }],
  score_points: [],
  instances: {},
};

const sseStream = () => [
  { event: "start", data: { stage: "分析题面", problem_chars: 24, clarify: false } },
  { event: "round", data: { round: 1, round_total: 4 } },
  { event: "done", data: RECOMMEND },
].map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`).join("");

// 已知噪声（**不是产品 bug**）：
//   ① 无编号题面时 /api/generate/preview-dir 返回 400——产品侧注释写明「请求失败静默
//      降级」，既有行为；
//   ② D 节**自己注入**的 500（expand 失败路径）——浏览器必然在控制台留一条 resource
//      错误，那是注入的证物，不是缺陷。D 节另有专门的断言（请求数上界 / 按钮可点 /
//      msg 非空），所以这里过滤掉不会放过真问题。
const KNOWN_NOISE = [
  "/api/generate/preview-dir", "status of 400 (Bad Request)",
  "status of 500 (Internal Server Error)",
];

const findings = [];
const note = (level, area, detail) => {
  findings.push({ level, area, detail });
  console.log(`[${level}] ${area} :: ${detail}`);
};

let server = null;
let browser = null;

// —— 交互链（走真按钮 → 真 fetch → 真渲染；不直接调渲染函数）——
async function openApp({ viewport, expandDelay = 0, expandStatus = 200, expandBody = null } = {}) {
  const page = await browser.newPage({ viewport: viewport || { width: 1366, height: 768 } });
  const problems = [];
  const calls = { expand: 0, recommend: 0, api: [] };
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const t = m.text();
    if (KNOWN_NOISE.some((n) => t.includes(n))) return;
    problems.push("console: " + t);
  });
  page.on("dialog", (d) => d.dismiss());
  page.on("request", (r) => {
    const u = r.url();
    if (u.includes("/api/")) calls.api.push(r.method() + " " + u.replace(server.url, ""));
  });
  await page.route("**/api/recommend", (route) => {
    calls.recommend++;
    return route.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body: sseStream() });
  });
  await page.route("**/api/selection/expand", async (route) => {
    calls.expand++;
    if (expandDelay) await new Promise((r) => setTimeout(r, expandDelay));
    if (expandStatus !== 200) {
      return route.fulfill({ status: expandStatus, headers: { "Content-Type": "application/json" },
        body: expandBody || JSON.stringify({ detail: "内部错误（审计注入）" }) });
    }
    return route.continue();
  });

  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
  await page.fill("#problem", "1. 检测物体是否经过。2. 沿黑线行驶。");
  await page.click("#btn-recommend");
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"]').waitFor({ state: "visible", timeout: 20000 });
  // 等首次自动展开**收敛**再交页面出去：否则它在用例中途落地，会把「前后状态对比」
  // 变得不确定（A 节第一版就是这样误报「点说明污染了状态」——变的只是展开落地，
  // 与点击无关）。expand 注入延迟的用例（C/C2/D）同样需要它先静下来。
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled, undefined, { timeout: 20000 }).catch(() => {});
  await page.waitForFunction(
    () => !document.getElementById("selected-list").innerText.includes("未展开依赖"),
    undefined, { timeout: 20000 },
  ).catch(() => {});
  return { page, problems, calls };
}

const state = (page) => page.evaluate(() => ({
  overlay: document.querySelectorAll(".module-info-overlay").length,
  chips: document.querySelectorAll("#rec-list .chip.rec").length,
  unsel: document.querySelectorAll("#rec-list .chip.rec.unsel").length,
  checked: document.querySelectorAll("#rec-list .group-member.checked").length,
  radios: [...document.querySelectorAll('#rec-list input[data-group-slug]')].map((i) => i.dataset.groupSlug + "=" + i.checked),
  selected: document.getElementById("selected-list").innerText.replace(/\s+/g, " ").trim().slice(0, 200),
  selectedCount: document.getElementById("selected-count").textContent,
  expandMsg: document.getElementById("expand-msg").textContent,
  expandBtn: document.getElementById("btn-expand").innerHTML.trim(),
  expandDisabled: document.getElementById("btn-expand").disabled,
}));

async function closeAll(page) {
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(60);
  }
  await page.evaluate(() => document.querySelectorAll(".module-info-overlay").forEach((o) => o.remove()));
}

// =====================================================================
// A. 入口全扫：页面上每一个 [data-mod-info] 按钮都必须能开对弹窗、且不改任何状态
// =====================================================================
async function testA() {
  const { page, problems, calls } = await openApp();
  const before = await state(page);
  const targets = await page.evaluate(() =>
    [...document.querySelectorAll("[data-mod-info]")].map((b) => b.dataset.modInfo));
  const uniq = [...new Set(targets)];
  console.log(`\n=== A. 入口全扫：${targets.length} 个按钮 / ${uniq.length} 个模块 ===`);

  const apiBefore = calls.api.length;
  const failed = [];
  for (const slug of uniq) {
    // 第一个可见按钮（同一 slug 可能在推荐区/需求灰注/已选行/模块库多份）
    const btn = page.locator(`[data-mod-info="${slug}"]`).first();
    await btn.click({ timeout: 5000 }).catch((e) => failed.push(`${slug}: 点不动 ${e.message.split("\n")[0]}`));
    await page.waitForFunction(
      () => document.querySelectorAll(".module-info-overlay").length === 1, undefined, { timeout: 5000 },
    ).catch(() => failed.push(`${slug}: 弹窗未出现（或出现多份）`));
    const title = await page.locator(".module-info-overlay .module-info-head").innerText().catch(() => "");
    if (!title.includes(slug)) failed.push(`${slug}: 弹窗标题不符 → ${JSON.stringify(title)}`);
    const body = await page.locator(".module-info-overlay .module-info-scroll").innerText().catch(() => "");
    if (!body.trim()) failed.push(`${slug}: 弹窗内容为空`);
    if (body.includes("[object Object]")) failed.push(`${slug}: 弹窗渲染出 [object Object]（intro 投影未拆）`);
    await closeAll(page);
  }
  const after = await state(page);
  const apiDuringSweep = calls.api.slice(apiBefore).filter((r) => !r.includes("/api/modules"));

  if (failed.length) note("FAIL", "A 入口全扫", failed.join("\n    "));
  else note("PASS", "A 入口全扫", `${uniq.length} 个模块的说明入口全部开对弹窗`);

  const drift = [];
  for (const k of ["chips", "unsel", "checked", "selected", "selectedCount"]) {
    if (before[k] !== after[k]) drift.push(`${k}: ${JSON.stringify(before[k])} → ${JSON.stringify(after[k])}`);
  }
  if (before.radios.join() !== after.radios.join()) drift.push(`radios: ${before.radios} → ${after.radios}`);
  if (drift.length) note("FAIL", "A 点说明污染了状态", drift.join("; "));
  else note("PASS", "A 点说明不改状态", `chip/组卡/已选清单/radio 全未变（${targets.length} 次点击）`);

  if (apiDuringSweep.length) note("FAIL", "A 点说明打了多余的后端请求", apiDuringSweep.join(", "));
  else note("PASS", "A 点说明零副作用请求", "全扫期间除 /api/modules 外无新增 API 调用");
  if (problems.length) note("FAIL", "A 控制台/页面错误", problems.join(" | "));
  await page.close();
}

// =====================================================================
// B. 弹窗自身：叠层、焦点、Esc 双击、源码懒加载
// =====================================================================
async function testB() {
  const { page, problems } = await openApp();
  console.log("\n=== B. 弹窗自身（叠层/焦点/懒加载）===");
  const chip = page.locator('#rec-list .chip.rec[data-remove="ir_beam"]');

  // B1 第二次打开：鼠标走不通（遮罩全屏吃点击），只能用**程序化点击**测替换分支
  // ——openModuleInfo 里「重复打开 = 替换」那段代码鼠标永远到不了：先记下来。
  await chip.locator('[data-mod-info="ir_beam"]').click();
  await page.waitForTimeout(120);
  let mouseBlocked = false;
  try {
    await chip.locator('[data-mod-info="ir_beam"]').click({ timeout: 1500 });
  } catch (e) {
    mouseBlocked = /intercepts pointer events/.test(e.message);
  }
  await page.evaluate((slug) => {
    const b = document.querySelector(`#rec-list .chip.rec[data-remove="${slug}"] [data-mod-info="${slug}"]`);
    if (b) b.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  }, "ir_beam");
  await page.waitForTimeout(200);
  const overlays = await page.locator(".module-info-overlay").count();
  if (mouseBlocked) {
    note("INFO", "B1 替换分支鼠标不可达", "弹窗打开后第二次点其他入口被全屏遮罩吃掉 —— 预期行为（模态本就该挡住背景）；结论是 openModuleInfo 里「重复打开=替换」那段**鼠标走不到**，是死分支，别当防线");
  }
  if (overlays !== 1) note("FAIL", "B1 重复打开", `程序化重复打开后遮罩数量 = ${overlays}（期望 1）`);
  else note("PASS", "B1 重复打开", "程序化重复打开仍只有一份遮罩（替换式）");

  const openState = await page.evaluate(() => {
    const o = document.querySelector(".module-info-overlay");
    const m = document.querySelector(".module-info-modal");
    const ae = document.activeElement;
    const cs = getComputedStyle(o);
    return {
      activeEl: ae ? ae.tagName + (ae.className ? "." + String(ae.className).split(" ")[0] : "") : "BODY",
      focusInsideModal: !!(m && ae && m.contains(ae)),
      role: m ? m.getAttribute("role") : null,
      ariaModal: m ? m.getAttribute("aria-modal") : null,
      ariaLabel: m ? (m.getAttribute("aria-label") || "") : "",
      zIndex: cs.zIndex,
      containsChip: !!(o && o.querySelector(".chip.rec")),
    };
  });
  // B2 焦点：弹窗打开后焦点应进弹窗（键盘用户 / 读屏用户）
  if (!openState.focusInsideModal) {
    note("WARN", "B2 焦点未进弹窗", `打开说明后 document.activeElement = ${openState.activeEl}（焦点留在触发按钮上，键盘用户不会被告知弹窗已开）`);
  } else note("PASS", "B2 焦点", `焦点在弹窗内（${openState.activeEl}）`);

  // B3 语义：dialog role / aria-modal
  if (!openState.role || openState.ariaModal !== "true") {
    note("WARN", "B3 弹窗无对话语义", `role=${openState.role} aria-modal=${openState.ariaModal}（读屏不会播报这是弹窗，也不隔离背景内容）`);
  } else note("PASS", "B3 弹窗语义", `role=${openState.role} aria-modal=${openState.ariaModal}`);

  // B3b 口径对照：本仓**其它**遮罩有没有这套语义？有先例 → 本弹窗是漏做；
  // 全仓都没有 → 这是全仓性的无障碍欠账，别只在本单补一处（口径一致性优先）。
  const siblings = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll("[class*=overlay]").forEach((o) => {
      const m = o.firstElementChild;
      out.push({
        overlay: o.className,
        role: m ? m.getAttribute("role") : null,
        ariaModal: m ? m.getAttribute("aria-modal") : null,
      });
    });
    return out;
  });
  const withSemantics = siblings.filter((s) => s.role === "dialog" || s.ariaModal === "true");
  console.log(`  页面上遮罩类元素 ${siblings.length} 个；带 dialog 语义的 ${withSemantics.length} 个`);
  if (!withSemantics.length && siblings.length) {
    note("WARN", "B3b 全仓遮罩都无对话语义", `${siblings.length} 个遮罩（${siblings.map((s) => s.overlay).join(", ")}）都缺 role/aria-modal——无障碍是**全仓**欠账，不该只在本单补一处`);
  } else if (withSemantics.length) {
    note("PASS", "B3b 存在对话语义先例", `已有 ${withSemantics.length} 个遮罩带 role/aria-modal：${withSemantics.map((s) => s.overlay).join(", ")}`);
  }

  // B4 背景可操作性：遮罩打开时，点击遮罩外的底层按钮（如 chip ✕）是否被拦住
  await page.evaluate(() => {
    const o = document.querySelector(".module-info-overlay");
    window.__underneath = o ? null : "no-overlay";
  });
  // 用键盘 Tab 走：焦点不在弹窗内时 Tab 会跑到背景里
  await page.keyboard.press("Tab");
  const afterTab = await page.evaluate(() => {
    const ae = document.activeElement;
    const o = document.querySelector(".module-info-overlay");
    return { el: ae ? ae.tagName + "." + String(ae.className || "").split(" ")[0] : "BODY",
      insideModal: !!(o && ae && o.contains(ae)) };
  });
  if (!afterTab.insideModal) note("WARN", "B4 焦点可逃出弹窗", `Tab 后焦点 = ${afterTab.el}（弹窗外的元素；无焦点陷阱，键盘用户可能误触背景）`);
  else note("PASS", "B4 焦点陷阱", `Tab 后仍在弹窗内（${afterTab.el}）`);

  // B5 源码懒加载：点 .module-info-scroll 里的源码文件行
  const fileRow = page.locator(".module-info-overlay .module-info-scroll").locator("text=code/").first();
  const fileCount = await fileRow.count();
  if (fileCount) {
    const scrollBefore = await page.locator(".module-info-overlay .module-info-scroll").innerText();
    await fileRow.click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(600);
    const scrollAfter = await page.locator(".module-info-overlay .module-info-scroll").innerText();
    if (scrollAfter.length <= scrollBefore.length) {
      note("WARN", "B5 源码行点击无反应", "点了源码文件行但弹窗内容没变（懒加载没落地？）");
    } else note("PASS", "B5 源码懒加载", `点击后内容 +${scrollAfter.length - scrollBefore.length} 字`);
  } else note("WARN", "B5 源码行未找到", "弹窗里没有可点的源码文件行（选择器口径需确认）");

  // B6 Esc 关闭：连按两次（第二次不应报错 / 不应关掉别的东西）
  await page.keyboard.press("Escape");
  await page.waitForTimeout(120);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(120);
  const afterEsc = await state(page);
  if (afterEsc.overlay !== 0) note("FAIL", "B6 Esc 未关闭", `遮罩剩 ${afterEsc.overlay} 份`);
  else note("PASS", "B6 Esc 关闭", "两次 Esc 后遮罩清空且无异常");

  // B7 关闭后焦点归位：应回到触发「说明」的那个按钮（否则键盘用户从页首重新 Tab）
  const focusAfter = await page.evaluate(() => {
    const ae = document.activeElement;
    return ae ? ae.tagName + "." + String(ae.className || "").split(" ")[0] + (ae.dataset && ae.dataset.modInfo ? `[${ae.dataset.modInfo}]` : "") : "BODY";
  });
  if (!/mod-info-btn/.test(focusAfter)) {
    note("WARN", "B7 关闭后焦点未归位", `Esc 关闭后 document.activeElement = ${focusAfter}（期望回到触发它的「说明」按钮）`);
  } else note("PASS", "B7 焦点归位", `关闭后焦点回到 ${focusAfter}`);

  if (problems.length) note("FAIL", "B 控制台/页面错误", problems.join(" | "));
  await page.close();
}

// =====================================================================
// C. 收敛压测：expand 慢（700ms）+ 快速连点，盯每一帧
// =====================================================================
async function testC() {
  const { page, problems, calls } = await openApp({ expandDelay: 700 });
  console.log("\n=== C. 收敛压测（expand 700ms + 快速连点）===");
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled, undefined, { timeout: 20000 });

  await page.evaluate(() => {
    // 每帧记录：DOM 里出现的模块行 + 当时「用户已选」的那份（chip 态是同一份状态机的
    // 另一面，两者必须互相印证——这正是工单 06/07 的口径）。
    window.__frames = [];
    const box = document.getElementById("selected-list");
    const selectedNow = () => [...document.querySelectorAll("#rec-list .chip.rec:not(.unsel)")]
      .map((c) => c.dataset.remove);
    const snap = () => ({
      rows: [...box.querySelectorAll("[data-mod-info]")].map((b) => b.dataset.modInfo),
      selected: selectedNow(),
      text: box.innerText.replace(/\s+/g, " ").slice(0, 120),
    });
    window.__frames.push(snap());
    new MutationObserver(() => window.__frames.push(snap()))
      .observe(box, { childList: true, subtree: true, characterData: true });
  });

  // 连点序列：只点**推荐 chip**（pid 这类进了功能组的模块在推荐区渲染成组卡成员行，
  // 没有 chip——第一版脚本在这里点空超时，记一笔：chip 与组卡是两套 DOM）。
  const chipSlugs = await page.evaluate(() => [...document.querySelectorAll("#rec-list .chip.rec")]
    .map((c) => c.dataset.remove));
  const cycle = ["ir_beam", "motor", "ir_beam", "motor"].filter((s) => chipSlugs.includes(s));
  console.log(`  推荐区 chip：${chipSlugs.join(", ")}；连点序列：${cycle.join(" → ")}`);
  const expect = new Set(await page.evaluate(() => [...document.querySelectorAll("#rec-list .chip.rec:not(.unsel)")]
    .map((c) => c.dataset.remove)));
  const gaps = [30, 40, 40, 60];
  for (let i = 0; i < cycle.length; i++) {
    const slug = cycle[i];
    const on = await page.locator(`#rec-list .chip.rec[data-remove="${slug}"]:not(.unsel)`).count();
    if (on) expect.delete(slug); else expect.add(slug);
    await page.locator(`#rec-list .chip.rec[data-remove="${slug}"]`).click({ timeout: 5000 });
    await page.waitForTimeout(gaps[i] || 40);
  }
  // 等收敛
  await page.waitForTimeout(2500);
  const final = await page.evaluate(() => ({
    frames: window.__frames,
    selected: [...document.querySelectorAll("#rec-list .chip.rec:not(.unsel)")].map((c) => c.dataset.remove),
    rows: [...document.querySelectorAll("#selected-list [data-mod-info]")].map((b) => b.dataset.modInfo),
    text: document.getElementById("selected-list").innerText.replace(/\s+/g, " ").slice(0, 240),
    expandMsg: document.getElementById("expand-msg").textContent,
    disabled: document.getElementById("btn-expand").disabled,
    btn: document.getElementById("btn-expand").innerHTML.trim(),
  }));
  // 非法帧判据：上一帧「用户已选」里有 x，下一帧已选清单 DOM 里却没有 x 的行
  // （真机 bug 的形态：过期 expand 响应把清单刷成旧集合）
  // 非法帧判据（第三版）：**被移除的模块一个都不许出现在清单里**（既不能有它的行，
  // 也不能被列进「未展开依赖」占位文案）。前两版的失误记在文件头：① 第一版把
  // 「未展开依赖：<当前选择>」这种**合法占位**当成回退帧；② 第二版把占位行文本里的
  // 正常模块也当成「已列出」。真正的口径只有一条：**清单里不得出现已不在选择的 slug**。
  const offenders = [];
  const frames = final.frames || [];
  for (let i = 1; i < frames.length; i++) {
    const prev = frames[i - 1], cur = frames[i];
    const removed = prev.selected.filter((s) => !cur.selected.includes(s));
    const leaked = removed.filter((s) => cur.rows.includes(s) || cur.text.includes(s));
    if (leaked.length) {
      offenders.push({ i, leaked, removed, rows: cur.rows.join(","), text: cur.text });
    }
  }
  // 逐帧打印：真 bug 与合法过渡必须靠帧序列分开看
  console.log("  帧序列（chip 说已选 → 已选清单 DOM）：");
  frames.forEach((f, i) => console.log(`   #${i} 已选[${f.selected.join(",")}] 清单[${f.rows.join(",") || "—"}] 「${f.text.slice(0, 60)}」`));
  const want = [...expect].sort();
  const got = [...new Set(final.selected)].sort();
  console.log(`  连点 ${cycle.length} 次；expand 请求 ${calls.expand} 次；已选清单变动帧 ${frames.length} 帧`);
  if (offenders.length) {
    note("FAIL", "C 已选清单泄漏已移除模块",
      `${offenders.length} 帧里被移除的模块仍在清单中，例：第 ${offenders[0].i} 帧泄漏 [${offenders[0].leaked}]，该帧清单=「${offenders[0].text}」`);
  } else note("PASS", "C 中间帧无泄漏", `${frames.length} 帧中「刚被点掉的模块」从未出现在清单里（行与占位文案都算）`);
  if (want.join() !== got.join()) {
    note("FAIL", "C 终态与选择集不一致", `期望 ${want.join()}，实际 ${got.join()}；清单文本「${final.text}」`);
  } else note("PASS", "C 终态收敛", `chip 态 = 已选清单 = ${got.join()}（连点后三者一致）`);
  if (final.text.includes("未展开依赖")) note("FAIL", "C 停在未展开", `收敛后仍显示「未展开依赖」：${final.text}`);
  if (final.disabled) note("FAIL", "C 展开按钮卡死", "收敛后「展开检查」仍是禁用态");
  if (!final.rows.length) note("WARN", "C 已选清单为空", "收敛后已选清单没有任何行");
  if (calls.expand > cycle.length + 6) note("WARN", "C 请求放大", `连点 ${cycle.length} 次却打了 ${calls.expand} 次 expand（每次重绘都重跑的代价）`);
  if (problems.length) note("FAIL", "C 控制台/页面错误", problems.join(" | "));
  await page.close();
}

// =====================================================================
// C2. 单次点击的**精确时间线**：C 报出的"回退帧"到底是真·过期写回，还是判据误报
//     ——用「帧快照 + expand 请求/落地时间 + 全文」三条线对齐后才下结论。
// =====================================================================
async function testC2() {
  const { page, calls } = await openApp({ expandDelay: 700 });
  console.log("\n=== C2. 单点一次的时间线（expand 700ms）===");
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled, undefined, { timeout: 20000 });
  const t0 = await page.evaluate(() => performance.now());

  await page.evaluate((t0) => {
    window.__log = [];
    const now = () => Math.round(performance.now() - t0);
    const chips = () => [...document.querySelectorAll("#rec-list .chip.rec:not(.unsel)")].map((c) => c.dataset.remove).join(",");
    const box = document.getElementById("selected-list");
    const push = (tag, extra) => window.__log.push({ t: now(), tag, chips: chips(), list: box.innerText.replace(/\s+/g, " ").slice(0, 60), ...(extra || {}) });
    push("start");
    new MutationObserver(() => push("frame")).observe(box, { childList: true, subtree: true, characterData: true });
    // 网络线：expand 的发起与落地
    const origFetch = window.fetch;
    window.fetch = function (input, init) {
      const url = String(input && input.url ? input.url : input);
      if (url.includes("/api/selection/expand")) {
        push("expand→req", { body: String((init && init.body) || "").slice(0, 80) });
        return origFetch.apply(this, arguments).then((r) => { push("expand←resp", { status: r.status }); return r; });
      }
      return origFetch.apply(this, arguments);
    };
    window.__logT0 = t0;
  }, t0);

  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"]').click();
  await page.waitForTimeout(2500);
  const log = await page.evaluate(() => window.__log);
  log.forEach((e) => console.log(`   t+${String(e.t).padStart(5)}ms ${e.tag.padEnd(12)} chip已选[${e.chips}] 清单「${e.list}」${e.body ? " body=" + e.body : ""}${e.status ? " status=" + e.status : ""}`));
  console.log(`  expand 请求共 ${calls.expand} 次`);

  // 判据（第三版，前两版误报记在文件头）：**点掉的那个模块一个都不许再出现在清单里**
  // ——既不能有它的行，也不能被列进「未展开依赖」占位文案。前两版把「占位文案里出现
  // 其它正常模块」当成了违规，于是把正确的占位也报成过期视图写回。
  const goneIdx = log.findIndex((e) => e.tag === "frame" && !e.chips.includes("ir_beam"));
  const bad = [];
  if (goneIdx >= 0) {
    for (let i = goneIdx; i < log.length; i++) {
      const e = log[i];
      if (e.chips.includes("ir_beam")) break;              // 又点回来了
      if (e.list.includes("ir_beam")) bad.push(e);          // 已移除的模块还在清单里 = 泄漏
    }
  }
  if (bad.length) {
    note("FAIL", "C2 已移除模块仍显示在清单里", `点掉 ir_beam 之后有 ${bad.length} 帧清单里还有它：例 t+${bad[0].t}ms「${bad[0].list}」`);
  } else note("PASS", "C2 无过期视图写回", "点掉后每一帧清单里都不再出现该模块（占位文案 = 当前选择，行 = 新展开结果）");
  await page.close();
}

// =====================================================================
// D. 失败路径：expand 一直失败 / 一次失败再恢复
// =====================================================================
async function testD() {
  console.log("\n=== D. 失败路径（expand 500）===");
  // D1 一直失败：会不会进入无止境重试？
  {
    const { page, problems, calls } = await openApp({ expandStatus: 500, expandDelay: 80 });
    await page.waitForTimeout(3000);
    const n1 = calls.expand;
    await page.waitForTimeout(3000);          // 第二个窗口：确认是持续自激而不是收尾重试一次
    const n2 = calls.expand;
    const s = await state(page);
    console.log(`  常败：3s 内 ${n1} 次 → 再 3s 内共 ${n2} 次（约 ${(n2 / 6).toFixed(1)} 次/秒）；按钮 disabled=${s.expandDisabled}；msg=「${s.expandMsg}」`);
    if (n2 - n1 > 3) note("FAIL", "D1 失败重试无界", `expand 持续 500 时 6s 打了 ${n2} 次请求（后 3s 又打了 ${n2 - n1} 次）——收尾重跑没有退路，失败即自激打后台`);
    else note("PASS", "D1 失败重试有界", `持续 500 时 6s 共 ${n2} 次请求（未自激）`);
    if (s.expandDisabled) note("FAIL", "D1 按钮卡在禁用", "expand 失败后「展开检查」仍禁用——用户无法手动重试");
    if (!s.expandMsg.trim()) note("WARN", "D1 失败无提示", "expand 失败后 #expand-msg 为空，用户看不到原因");
    if (problems.length) note("FAIL", "D1 控制台错误", problems.join(" | "));
    await page.close();
  }
  // D2 先失败后成功：能否自愈到「已展开」
  {
    const { page, problems, calls } = await openApp({ expandDelay: 200 });
    let failNext = 1;
    await page.route("**/api/selection/expand", async (route) => {
      if (failNext > 0) { failNext--; return route.fulfill({ status: 500, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ detail: "注入的一次失败" }) }); }
      return route.continue();
    });
    await page.click("#btn-expand");
    await page.waitForTimeout(1200);
    const mid = await state(page);
    await page.click("#btn-expand");
    await page.waitForTimeout(1500);
    const end = await state(page);
    console.log(`  一次失败后手动重试：中间 msg=「${mid.expandMsg}」→ 终态「${end.selected.slice(0, 80)}」`);
    if (end.selected.includes("未展开依赖")) note("FAIL", "D2 失败后无法自愈", `手动重试后仍停在未展开：${end.selected}`);
    else note("PASS", "D2 失败后可自愈", "手动再点「展开检查」能恢复（失败不粘滞）");
    if (problems.length) note("FAIL", "D2 控制台错误", problems.join(" | "));
    await page.close();
  }
}

// =====================================================================
// E. 视口/几何：常见笔记本与窄屏下弹窗是否可用、是否溢出
// =====================================================================
async function testE() {
  console.log("\n=== E. 视口/几何 ===");
  for (const vp of [{ width: 1366, height: 768 }, { width: 1280, height: 720 }, { width: 900, height: 800 }]) {
    const { page, problems } = await openApp({ viewport: vp });
    await page.locator('#rec-list .chip.rec[data-remove="ir_beam"] [data-mod-info="ir_beam"]').click();
    await page.waitForTimeout(200);
    const geo = await page.evaluate(() => {
      const m = document.querySelector(".module-info-modal");
      const s = document.querySelector(".module-info-scroll");
      const r = m.getBoundingClientRect();
      const close = m.querySelector(".ref-files-close").getBoundingClientRect();
      return {
        modal: { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left),
          bottom: Math.round(r.bottom), right: Math.round(r.right) },
        closeVisible: close.top >= 0 && close.bottom <= window.innerHeight && close.right <= window.innerWidth && close.left >= 0,
        scrollOverflowX: s.scrollWidth - s.clientWidth,
        scrollH: s.clientHeight, scrollAll: s.scrollHeight,
        docOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        pageOverflow: document.querySelectorAll(".module-info-overlay").length ? 0
          : document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    const out = geo.modal.bottom > vp.height + 1 || geo.modal.right > vp.width + 1
      || geo.modal.top < -1 || geo.modal.left < -1;
    const label = `${vp.width}x${vp.height}`;
    if (out) note("FAIL", `E 弹窗超出视口 ${label}`, JSON.stringify(geo.modal));
    else note("PASS", `E 弹窗在视口内 ${label}`, `modal ${geo.modal.w}x${geo.modal.h}（关闭按钮可见=${geo.closeVisible}）`);
    if (geo.scrollOverflowX > 2) note("WARN", `E 弹窗内容横向溢出 ${label}`, `scrollWidth 超出 ${geo.scrollOverflowX}px（长串不换行？）`);
    if (!geo.closeVisible) note("FAIL", `E 关闭按钮不可见 ${label}`, "关闭按钮被挤出视口 / 被遮挡");
    if (problems.length) note("FAIL", `E 控制台错误 ${label}`, problems.join(" | "));
    await page.close();
  }
}

// =====================================================================
// F. 键盘可达性：能不能只用键盘打开说明
// =====================================================================
async function testF() {
  const { page, problems } = await openApp();
  console.log("\n=== F. 键盘可达性 ===");
  const ok = await page.evaluate(() => {
    const btns = [...document.querySelectorAll("[data-mod-info]")];
    return { count: btns.length, focusable: btns.filter((b) => b.tabIndex >= 0).length,
      tag: btns.length ? btns[0].tagName : null,
      nestedInChip: btns.filter((b) => b.closest(".chip.rec")).length };
  });
  if (ok.tag !== "BUTTON" || ok.focusable !== ok.count) {
    note("FAIL", "F 说明入口不可聚焦", `tag=${ok.tag} 可聚焦 ${ok.focusable}/${ok.count}`);
  } else note("PASS", "F 说明入口可聚焦", `${ok.count} 个入口都是可 Tab 的 button`);

  // 真的用键盘操作一次：聚焦第一个 chip 内的说明按钮并按 Enter
  const chipBtn = page.locator('#rec-list .chip.rec[data-remove="ir_beam"] [data-mod-info="ir_beam"]');
  await chipBtn.focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(250);
  const st = await state(page);
  if (st.overlay !== 1) note("FAIL", "F 键盘 Enter 打不开说明", `遮罩数量 = ${st.overlay}`);
  else note("PASS", "F 键盘 Enter 能开说明", "聚焦说明按钮 + Enter → 弹窗打开");
  if (st.selected.includes("ir_beam") === false) note("FAIL", "F 键盘 Enter 误移除了模块", st.selected);
  await closeAll(page);
  if (problems.length) note("FAIL", "F 控制台错误", problems.join(" | "));
  await page.close();
}

// =====================================================================
// G. 弹窗内容质量：四问分段在真库里落地情况 + 推荐理由串味
// =====================================================================
async function testG() {
  const { page, problems } = await openApp();
  console.log("\n=== G. 弹窗内容质量 ===");
  const mods = await page.evaluate(async () => (await (await fetch("/api/modules")).json()));
  const list = Array.isArray(mods) ? mods : (mods.modules || []);
  const withIntro = list.filter((m) => Array.isArray(m.intro) && m.intro.length);
  const fourBeat = withIntro.filter((m) => m.intro.length >= 4);
  console.log(`  库内模块 ${list.length} 个；带 intro 拆段 ${withIntro.length} 个；四拍齐全 ${fourBeat.length} 个`);
  const labelSet = new Set();
  withIntro.forEach((m) => m.intro.forEach((s) => labelSet.add(s.label)));
  console.log(`  实际出现的段标签：${[...labelSet].join(" / ")}`);
  if (withIntro.length < list.length) {
    note("WARN", "G 未拆段简介", `${list.length - withIntro.length} 个模块的 intro 为空 → 弹窗回落成一句简介（无四问小标题）`);
  }
  // 推荐理由串味检查：弹窗里「为什么推荐它」段落的内容是否与 chip 上那句一致
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"] [data-mod-info="ir_beam"]').click();
  await page.waitForTimeout(200);
  const text = await page.locator(".module-info-overlay").innerText();
  const chipReason = await page.locator('#rec-list .chip.rec[data-remove="ir_beam"] .reason').innerText();
  // 段序：四问标签必须按后端单一顺序出现（不是乱序拼装）
  const labels = await page.evaluate(() =>
    [...document.querySelectorAll(".module-info-overlay .mi-intro-label")].map((e) => e.textContent));
  const sorted = [...labels].sort((a, b) => a.localeCompare(b));
  console.log(`  ir_beam 段标签顺序：${labels.join(" → ")}`);
  if (labels.length < 4) note("WARN", "G 分段不足四拍", `ir_beam 只有 ${labels.length} 段：${labels.join("/")}`);
  if (!labels.includes("这是干什么的") || labels.indexOf("这是干什么的") !== 0) {
    note("FAIL", "G 首段不是「这是干什么的」", `实际顺序：${labels.join(" → ")}（新手第一眼看到的应是最基础的那问）`);
  }
  if (!text.includes(chipReason)) note("FAIL", "G 推荐理由未带进弹窗", `chip=「${chipReason}」不在弹窗文本里`);
  else note("PASS", "G 推荐理由带进弹窗", `「${chipReason}」在弹窗「为什么推荐它」段内`);
  // 模块库页打开时不该编造推荐理由
  await closeAll(page);
  const libBtn = page.locator('#module-grid .mc-info[data-info="ir_beam"]');
  if (await libBtn.count()) {
    await libBtn.click();
    await page.waitForTimeout(250);
    const libText = await page.locator(".module-info-overlay").innerText();
    if (libText.includes("为什么推荐它")) note("FAIL", "G 模块库页编造了推荐理由", "模块库入口打开时也渲染了「为什么推荐它」");
    else note("PASS", "G 模块库入口无推荐理由", "模块库页打开说明未渲染「为什么推荐它」段");
  }
  if (problems.length) note("FAIL", "G 控制台错误", problems.join(" | "));
  await page.close();
}

// =====================================================================
async function main() {
  server = await startServer();
  browser = await chromium.launch();
  console.log(`后端就绪：${server.url}`);
  const only = process.argv.slice(2).map((s) => s.toUpperCase());
  // 每条用例独立兜异常：一条塌了不能吃掉后面的证据（第一版正是这里吃亏）
  const run = async (name, fn) => {
    if (only.length && !only.includes(name)) return;
    try { await fn(); }
    catch (e) {
      note("FAIL", `${name} 用例崩溃`, (e.message || String(e)).split("\n").slice(0, 4).join(" / "));
    }
  };
  try {
    await run("A", testA);
    await run("B", testB);
    await run("C", testC);
    await run("C2", testC2);
    await run("D", testD);
    await run("E", testE);
    await run("F", testF);
    await run("G", testG);
  } finally {
    await browser.close();
    await server.stop();
  }
  const bad = findings.filter((f) => f.level === "FAIL");
  const warn = findings.filter((f) => f.level === "WARN");
  const info = findings.filter((f) => f.level === "INFO");
  console.log("\n================ 结论 ================");
  console.log(`FAIL ${bad.length} 条 / WARN ${warn.length} 条 / INFO ${info.length} 条 / PASS ${findings.length - bad.length - warn.length - info.length} 条`);
  for (const f of [...bad, ...warn]) console.log(`- [${f.level}] ${f.area}：${f.detail}`);
  if (bad.length) process.exitCode = 2;
}

await main();
