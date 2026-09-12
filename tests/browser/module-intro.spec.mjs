// 真机验收（工单 module-intro-detail/05）：**真浏览器 + 真后端**点一遍「说明」入口。
//
// 为什么要有这一层：`tests/js/*.test.mjs` 是纯函数 + 静态接线断言——它能证明
// 「渲染出来的 HTML 里有 data-mod-info」「代码里写了 stopPropagation」，但证明不了
// **点下去真的弹窗、真的没顺手把模块移除、真的没顺手选中 radio、Esc 真的关掉**。
// 这些是运行时行为（事件冒泡 / label 激活控件 / 键盘监听），只有真浏览器能作证。
//
// 前置（一次性）：npm install && npx playwright install chromium
// 运行：node --test tests/browser/module-intro.spec.mjs
// **不在默认 `node --test "tests/js/*.test.mjs"` 里**——真机验收要起服务 + 开浏览器，
// 不该让每次改前端都付这个成本；改动推荐区交互时手动跑。
//
// 假件只有一个：拦截 /api/recommend 回合成 SSE（真推荐要花 LLM 额度）。其余全真——
// 真 python 后端、真 /api/modules（真库 93 个模块 + 真 intro 拆段）、真 SSE 解析、
// 真渲染、真事件委托。
import test from "node:test";
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { startServer } from "./server.mjs";

// 已知的页面级 400（**与本特性无关、既有行为**）：无编号题面时
// /api/generate/preview-dir 返回 400「缺少必填字段：platform」，产品侧注释写明
// 「请求失败静默降级（预览不阻断检查单）」——故这里只过滤它，不放宽其它 console 错误。
const KNOWN_NOISE = ["/api/generate/preview-dir", "status of 400 (Bad Request)"];

let server = null;
let browser = null;

test.before(async () => {
  server = await startServer();
  browser = await chromium.launch();
});

test.after(async () => {
  if (browser) await browser.close();
  if (server) await server.stop();
});

// 合成推荐载荷（形状 = /api/recommend 的 done 载荷；ir_beam/pid/xunji/huidu 都是真库模块）
const RECOMMEND = {
  topic_id: "",
  modules: [
    { slug: "ir_beam", reason: "可选点/起始做辅助" },
    { slug: "pid", reason: "巡线核心" },
  ],
  requirements: [
    { sentence: 1, requirement: "检测物体是否经过", modules: ["ir_beam"], suggestions: [] },
    { sentence: 2, requirement: "沿黑线行驶", modules: ["pid"], suggestions: [] },
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

// 合成 SSE 帧（事件序与真端点一致：start → round → done；线格式同 sse._sse_frame）
const sseStream = () => [
  { event: "start", data: { stage: "分析题面", problem_chars: 24, clarify: false } },
  { event: "round", data: { round: 1, round_total: 4 } },
  { event: "done", data: RECOMMEND },
].map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`).join("");

// 新页面 + 选平台 + 粘题面 + 点「让 AI 推荐」（走真链路：按钮 → fetch → SSE 解析 →
// 渲染）。每条用例独立开页：互不干扰，也顺带验证冷启动。
async function openAppWithRecommend() {
  const page = await browser.newPage();
  const problems = [];
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const text = m.text();
    if (KNOWN_NOISE.some((n) => text.includes(n))) return;   // 既有噪声，见文件头
    problems.push("console: " + text);
  });
  page.on("dialog", (d) => d.dismiss());   // 兜底：原生对话框一律关掉，别卡住验收
  await page.route("**/api/recommend", (route) => route.fulfill({
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
    body: sseStream(),
  }));

  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
  await page.fill("#problem", "1. 检测物体是否经过。2. 沿黑线行驶。");
  await page.click("#btn-recommend");
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"]').waitFor({ state: "visible", timeout: 15000 });
  return { page, problems };
}

const modal = (page) => page.locator(".module-info-overlay .module-info-modal");

test("推荐 chip：点「说明」弹窗，且不把模块从工程移除", async () => {
  const { page, problems } = await openAppWithRecommend();
  const chip = page.locator('#rec-list .chip.rec[data-remove="ir_beam"]');
  await chip.locator('[data-mod-info="ir_beam"]').click();

  await modal(page).waitFor({ state: "visible" });
  assert.match(await modal(page).locator(".module-info-head").innerText(), /ir_beam/);
  // chip 还在 = 点说明没有连带触发移除（stopPropagation 生效）
  assert.equal(await chip.count(), 1, "点「说明」把推荐 chip 移除了（冒泡没拦住）");
  // 工程里也仍带着它（说明按钮没有改选择集）
  assert.match(await page.locator("#selected-list").innerText(), /ir_beam/);
  assert.deepEqual(problems, []);
  await page.close();
});

test("弹窗内容：四问分段 + 为什么推荐它 + 引脚表/源码文件", async () => {
  const { page, problems } = await openAppWithRecommend();
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"] [data-mod-info="ir_beam"]').click();
  await modal(page).waitFor({ state: "visible" });
  const text = await modal(page).innerText();

  // 四问标题（后端 module_intro 单源）逐条在位
  for (const label of ["这是干什么的", "怎么接线", "怎么用（接口）", "什么时候用"]) {
    assert.ok(text.includes(label), `弹窗缺「${label}」段：\n${text}`);
  }
  // 分段里是「讲人话」的那几句（不是 slug + 一句代号）
  assert.match(text, /红外发射管和接收管相对安装/);
  assert.match(text, /三线制接线/);
  assert.match(text, /ir_beam_read\(\)/);
  // chip 上那句短线推荐理由在弹窗里有上下文
  assert.ok(text.includes("为什么推荐它"), "弹窗缺推荐理由段");
  assert.match(text, /可选点\/起始做辅助/);
  // 既有内部字段没被挤掉
  assert.match(text, /IR_BEAM_OUT/);
  assert.match(text, /code\/ir_beam\.c/);
  assert.deepEqual(problems, []);
  await page.close();
});

test("Esc 与点遮罩都能关掉弹窗", async () => {
  const { page, problems } = await openAppWithRecommend();
  const overlay = page.locator(".module-info-overlay");
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"] [data-mod-info="ir_beam"]').click();
  await overlay.waitFor({ state: "visible" });
  await page.keyboard.press("Escape");
  await overlay.waitFor({ state: "detached" });

  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"] [data-mod-info="ir_beam"]').click();
  await overlay.waitFor({ state: "visible" });
  await overlay.click({ position: { x: 5, y: 5 } });
  await overlay.waitFor({ state: "detached" });
  assert.deepEqual(problems, []);
  await page.close();
});

test("功能组选中态：点成员行「说明」不顺手改选中（radio 未被激活）", async () => {
  const { page, problems } = await openAppWithRecommend();
  assert.equal(await page.locator('#rec-list .group-member.checked').count(), 0,
    "未点过的组不该有选中态（group-choice-required 口径）");

  await page.locator('#rec-list [data-mod-info="xunji"]').first().click();
  await modal(page).waitFor({ state: "visible" });
  assert.ok((await modal(page).innerText()).includes("这是干什么的"));
  // preventDefault 生效：label 没有把 radio 选中
  assert.equal(await page.locator('#rec-list .group-member.checked').count(), 0,
    "点「说明」顺手选中了组内成员（label 激活控件没拦住）");
  assert.equal(await page.locator('#rec-list input[data-group-slug="xunji"]').isChecked(), false);
  assert.deepEqual(problems, []);
  await page.close();
});

test("需求清单灰注（进了功能组的模块）+ 已选清单行：同样能点开说明", async () => {
  const { page, problems } = await openAppWithRecommend();
  // 进了功能组的模块在需求清单里渲染成灰注（不是 chip）
  await page.locator("#rec-list .muted", { hasText: "pid" }).first()
    .locator('[data-mod-info="pid"]').click();
  await modal(page).waitFor({ state: "visible" });
  assert.ok((await modal(page).innerText()).includes("怎么用（接口）"));
  await page.keyboard.press("Escape");
  await modal(page).waitFor({ state: "detached" });

  // 已选清单行（xunji 的说明按钮在组卡里，已选清单走 ir_beam）
  const selectedBtn = page.locator('#selected-list [data-mod-info="ir_beam"]');
  assert.equal(await selectedBtn.count(), 1, "已选清单行缺说明入口");
  await selectedBtn.click();
  await modal(page).waitFor({ state: "visible" });
  assert.ok((await modal(page).innerText()).includes("这是干什么的"));
  assert.deepEqual(problems, []);
  await page.close();
});

// 并发收口（工单 module-intro-detail/07）：展开比点击慢时，**过期响应不得被写进状态**
// ——修前真机实测：点回 chip 后约 120ms，已选清单被带旧选择集的 expand 响应刷成只剩
// motor（ir_beam/pid 一起消失），要等下一次展开才恢复。
//
// 口径：终态断言抓不到这种 bug（收口后的重跑总会把终态修对），所以这里用
// MutationObserver **盯住中间帧**：整个连点过程里，已选清单任何一帧都不得丢掉
// 当前已选的模块；并且给 expand 响应注入延迟，让「旧响应迟到」必然发生。
test("展开并发：过期响应不写状态——连点过程任何一帧都不丢已选模块", async () => {
  const page = await browser.newPage();
  const problems = [];
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  // 关键：给 expand 响应注入延迟并记录请求序号 → 旧响应必然晚于新点击落地
  let expandCalls = 0;
  await page.route("**/api/selection/expand", async (route) => {
    const nth = ++expandCalls;
    await new Promise((r) => setTimeout(r, 500));   // 第一个请求故意更慢
    return route.continue();
  });
  await page.route("**/api/recommend", (route) => route.fulfill({
    status: 200, headers: { "Content-Type": "text/event-stream" }, body: sseStream(),
  }));

  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
  await page.fill("#problem", "1. 检测物体是否经过。2. 沿黑线行驶。");
  await page.click("#btn-recommend");
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"]').waitFor({ state: "visible", timeout: 15000 });
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled, undefined, { timeout: 15000 });

  // 开始盯帧：记录「已选清单文本」的每一次变化
  await page.evaluate(() => {
    window.__frames = [];
    const box = document.getElementById("selected-list");
    const rec = () => window.__frames.push(box.innerText.replace(/\s+/g, " "));
    rec();
    new MutationObserver(rec).observe(box, { childList: true, subtree: true, characterData: true });
  });

  // 连点（展开在途时继续点）——旧响应会在这些点击之后才回来
  const chip = () => page.locator('#rec-list .chip.rec[data-remove="ir_beam"]');
  await chip().locator(".chip-x").click();
  await chip().click();
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled, undefined, { timeout: 15000 });
  await page.waitForTimeout(800);

  const frames = await page.evaluate(() => window.__frames);
  // 中间帧不得出现「pid 在、ir_beam 不在」的塌陷态——pid 一直在选，ir_beam 点回来后也一直在选
  const collapsed = frames.filter((f) => f.includes("pid") && !f.includes("ir_beam")
    && !f.includes("未展开依赖"));
  assert.deepEqual(collapsed, [],
    "过期 expand 响应把已选清单写成了旧集合（中间帧丢失 ir_beam）：\n" + collapsed.join("\n---\n"));
  // 终态：两个模块都在，且已展开
  const selected = await page.locator("#selected-list").innerText();
  assert.ok(selected.includes("ir_beam") && selected.includes("pid"), selected);
  await page.waitForFunction(() => !document.getElementById("selected-list").innerText.includes("未展开依赖"),
    undefined, { timeout: 10000 });
  assert.deepEqual(problems, []);
  await page.close();
});
// 回归：chip 本体是**双向选择开关**，且界面与实际必须一致（工单 module-intro-detail/06// 修的既有 bug：点 ✕ 后模块已从工程移除，chip 却仍显示成已选绿标——界面说在、
// 实际不在，而且没有任何路径能加回来）。
//
// 断言口径：本用例验「chip 选择态 ↔ 选择集」这层（点掉 → 未选态 + 选择集去掉；
// 点回 → 已选态 + 选择集回填）。后台那次 /api/selection/expand 的时序收敛由上面的
// 并发用例负责（工单 07）——两者一起才保证「界面、选择集、展开结果」三者一致。
test("推荐 chip 选择开关：点掉变未选态、点回加回来（界面与选择集一致）", async () => {
  const { page, problems } = await openAppWithRecommend();
  const chip = page.locator('#rec-list .chip.rec[data-remove="ir_beam"]');
  const chipHTML = () => page.locator('#rec-list .chip.rec[data-remove="ir_beam"]').innerHTML();
  const unselected = () => page.locator('#rec-list .chip.rec.unsel[data-remove="ir_beam"]').count();

  // 初始：已选态（绿标、✕）
  assert.equal(await unselected(), 0, "初始应是已选态");
  assert.ok((await page.locator("#selected-list").innerText()).includes("ir_beam"));

  // 点掉：chip 立刻变未选态（灰显虚线 + ＋），选择集里也去掉
  await chip.locator(".chip-x").click();
  await page.waitForFunction(
    () => document.querySelector('#rec-list .chip.rec.unsel[data-remove="ir_beam"]') !== null,
    undefined, { timeout: 10000 });
  assert.match(await chip.getAttribute("title"), /加回/);
  assert.match(await chipHTML(), /＋/, "未选态应显示加回符号");
  assert.ok(!(await page.locator("#selected-list").innerText()).includes("ir_beam"),
    "点掉后选择集里不该还有它");

  // 点回：chip 回已选态 + 选择集回填（原 bug 的另一半：点掉了加不回来）
  await chip.click();
  await page.waitForFunction(
    () => document.querySelector('#rec-list .chip.rec.unsel[data-remove="ir_beam"]') === null,
    undefined, { timeout: 10000 });
  assert.match(await chipHTML(), /✕/);
  assert.ok((await page.locator("#selected-list").innerText()).includes("ir_beam"),
    "点回后选择集里应重新有它");
  assert.deepEqual(problems, []);
  await page.close();
});

test("说明弹窗键盘无障碍：打开即聚焦、Tab 不外逃、关闭后焦点归位（工单 10）", async () => {
  const { page, problems } = await openAppWithRecommend();
  const trigger = page.locator('#rec-list .chip.rec[data-remove="ir_beam"] [data-mod-info="ir_beam"]');
  await trigger.click();
  await modal(page).waitFor({ state: "visible" });

  // ① 打开即聚焦：焦点进弹窗（否则读屏不播报，键盘用户不知道弹窗开了）
  const focusIn = await page.evaluate(() => {
    const m = document.querySelector(".module-info-overlay .module-info-modal");
    return { inModal: !!(m && m.contains(document.activeElement)),
      el: document.activeElement ? document.activeElement.className : "" };
  });
  assert.equal(focusIn.inModal, true, `打开说明后焦点仍在弹窗外（${focusIn.el}）—— 未聚焦弹窗`);
  assert.match(focusIn.el, /ref-files-close/, "打开即聚焦应落在关闭按钮（Tab 循环第一站，口径同 codeview 快捷键帮助）");

  // ② Tab 焦点陷阱：连按多次 Tab 焦点都必须留在弹窗内（含 Shift+Tab 回绕）
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press("Tab");
    const inside = await page.evaluate(() => {
      const m = document.querySelector(".module-info-overlay .module-info-modal");
      return !!(m && m.contains(document.activeElement));
    });
    assert.equal(inside, true, `第 ${i + 1} 次 Tab 后焦点跑出了弹窗 —— 无焦点陷阱`);
  }
  await page.keyboard.press("Shift+Tab");
  const backInside = await page.evaluate(() => {
    const m = document.querySelector(".module-info-overlay .module-info-modal");
    return !!(m && m.contains(document.activeElement));
  });
  assert.equal(backInside, true, "Shift+Tab 回绕后焦点跑出了弹窗");

  // ③ 关闭后焦点归位：回到触发它的那个「说明」按钮
  await page.keyboard.press("Escape");
  await page.locator(".module-info-overlay").waitFor({ state: "detached" });
  const focusAfter = await page.evaluate(() => {
    const ae = document.activeElement;
    return { cls: ae ? String(ae.className || "") : "", slug: ae && ae.dataset ? ae.dataset.modInfo : null };
  });
  assert.match(focusAfter.cls, /mod-info-btn/, `关闭后焦点 = ${focusAfter.cls}（期望回到「说明」按钮）`);
  assert.equal(focusAfter.slug, "ir_beam", "关闭后焦点回到的应是同一个模块的说明按钮");
  // Esc 只解绑一次（✕ / 遮罩 / Esc 三条路径幂等）：再按一次不该报错
  await page.keyboard.press("Escape");
  await page.waitForTimeout(80);
  assert.equal(await page.locator(".module-info-overlay").count(), 0);
  assert.deepEqual(problems, []);
  await page.close();
});

// 失败路径（工单 module-intro-detail/09）：`/api/selection/expand` **失败**时不许自动
// 重跑。原实现把「结果被作废」与「请求失败」合并成同一个 `!ok` 一起重跑：失败 →
// 同参数立刻再打 → 再失败，真机实测恒 500 时打出 ~10 次/秒，且
//   * `expandBusy` 恒 true → 「展开检查」按钮永久禁用（用户连手动重试都做不到）；
//   * `expandBegin` 每次都把 `#expand-msg` 清空 → 报错在被看到前就被自己擦掉。
// 口径：失败要**停下来**——请求数有上界、按钮可点、原因留在界面上。
test("展开失败：不自动重跑（无自激）、按钮可点、失败原因留在界面上", async () => {
  const page = await browser.newPage();
  const problems = [];
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  let expandCalls = 0;
  await page.route("**/api/selection/expand", (route) => {
    expandCalls++;
    return route.fulfill({
      status: 500, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ detail: "内部错误（用例注入）" }),
    });
  });
  await page.route("**/api/recommend", (route) => route.fulfill({
    status: 200, headers: { "Content-Type": "text/event-stream" }, body: sseStream(),
  }));

  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
  await page.fill("#problem", "1. 检测物体是否经过。2. 沿黑线行驶。");
  await page.click("#btn-recommend");
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"]').waitFor({ state: "visible", timeout: 15000 });

  await page.waitForTimeout(2500);   // 给自激足够的时间显形（修前这里已经是两位数请求）
  assert.ok(expandCalls <= 4,
    `expand 恒失败却打了 ${expandCalls} 次请求 —— 收尾重跑把「失败」也当成「结果被作废」在自激`);
  assert.equal(await page.locator("#btn-expand").isDisabled(), false,
    "expand 失败后「展开检查」仍是禁用态 —— 用户无法手动重试");
  assert.ok((await page.locator("#expand-msg").innerText()).trim().length > 0,
    "expand 失败后 #expand-msg 为空 —— 报错被重跑自己清掉了，用户看不到原因");

  // 手动再点一次：失败后不粘滞，仍能再试（请求数增长 = 用户手点的）
  const before = expandCalls;
  await page.click("#btn-expand");
  await page.waitForTimeout(800);
  assert.equal(expandCalls, before + 1,
    `手动重试打了 ${expandCalls - before} 次请求（期望正好 1 次：用户点一次 = 一次请求）`);

  // 500 必然在控制台留 resource 错误（浏览器行为，不是产品 bug）——只收集页面级异常
  assert.deepEqual(problems, []);
  await page.close();
});
