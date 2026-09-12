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

// 回归：点 chip 本体仍是「移除模块」——chip-x 属既有交互（本单只往 chip 里加了个
// 说明按钮，不能把原交互顶掉）。断言口径按**实际行为**：移除的是工程里的模块
// （已选清单变化），推荐区 chip 本身由推荐载荷渲染、点完仍在（既有行为，不在本单范围）。
test("回归：点 chip 的 ✕ 仍把模块从工程里移除（说明按钮没顶掉原交互）", async () => {
  const { page, problems } = await openAppWithRecommend();
  assert.match(await page.locator("#selected-list").innerText(), /ir_beam/);
  await page.locator('#rec-list .chip.rec[data-remove="ir_beam"] .chip-x').click();
  await page.waitForFunction(() => {
    const box = document.getElementById("selected-list");
    return box && !box.innerText.includes("ir_beam");
  }, undefined, { timeout: 10000 });
  // 工程里没有了，也没有产生 pageerror/console 错误
  assert.deepEqual(problems, []);
  await page.close();
});
