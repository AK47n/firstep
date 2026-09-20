// ui-contract.spec.mjs — ui 层的**行为契约**（工单 ui-dom-contract-gate/04）：
// 在真页面（index.html 就是夹具）+ 真后端上，断言"用户做一个动作 → 看到什么结果"，
// 包括**跨刷新的持久化契约**。
//
// ## 为什么要有这一层
//
// `ui/` 是 57 个模块 / 17,996 行 / 513 个 `addEventListener`，而 `tests/js/` 里涉及它的
// 断言几乎全是"读源码字符串"。静态那一半已经由 `tests/js/ui-dom-contract.test.mjs` 守住了
// （id 真的存在、模块真的被装载）；**"点下去到底还灵不灵"只有真浏览器能作证**——
// 事件委托、label 激活控件、localStorage 往返、重绘后绑定是否还在，这些都在源码文本之外。
//
// ## 选件口径（下一个人按这三条扩展，别凭手感）
//
//   ① **监听器密度高**（前三名：codeview 37 / codeeditor 35 / reference 34）；
//   ② 交互是**纯本地**的——只有 DOM + localStorage，不起 LLM、不编译、不生成
//      （要起后端的那些留给既有的三个 spec：module-intro / code-tree-click / hwcheck）；
//   ③ 一个模块一条用例，断言"用户动作 → 可观察结果"，不绑内部函数名与 DOM 结构细节。
//
// 本轮取三条（都满足口径）：`ui/guide.js`（子页签 roving tabindex + 面板显隐）、
// `ui/step-state.js`（卡片折叠 + 记忆落盘 + 刷新后生效）、`ui/welcome.js`（欢迎卡关闭 + 记住）。
//
// ## 运行
//
//     node --test --test-concurrency=1 tests/browser/ui-contract.spec.mjs
//     （与另三个 spec 一起跑：node --test --test-concurrency=1 "tests/browser/*.spec.mjs"）
//
// 依赖：`npm install` + `npx playwright install chromium`。零 LLM、零编译。
import test from "node:test";
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { startServer } from "./server.mjs";
import { openApp, gotoNavTab } from "./ui-contract-fixture.mjs";

// 两个存储键**从产品源码里抠出来**，不手抄（手抄的那份迟早与产品分叉——
// 那正是 C5a 两条裸镜像的教训）。抠法：读真源码 + 正则取字符串字面量。
//
// ⚠ **这带来一条必须配套的钉法**（红证实测发现的）：既然用例与产品读**同一个常量**，
// 那"把键改个名"（产品改名 + 用例跟着读）**两侧一起漂、契约照样绿**——存储键本身
// 没有被这条契约钉住。所以键值的冻结由 `tests/js/welcome-responsive.test.mjs`
// （welcome 键，那里已有 `WELCOME_DISMISS_KEY 与 spec 一致`）与
// `tests/js/step-state*.test.mjs` 一侧的纯函数用例负责；**本文件负责的是行为**：
// 折叠了会不会落盘、刷新后记不记得住。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const STATIC = fileURLToPath(
  new URL("../../src/contest_generator/static/", import.meta.url));

function literalFrom(source, name) {
  const m = new RegExp(`${name}\\s*=\\s*"([^"]+)"`).exec(source);
  assert.ok(m, `产品源码里找不到 ${name} 的字面量——键名改了？`);
  return m[1];
}
const COLLAPSE_KEY = literalFrom(readFileSync(STATIC + "js/fx/generate.js", "utf8"),
  "GEN_CARD_COLLAPSE_KEY");
const WELCOME_KEY = literalFrom(readFileSync(STATIC + "js/fx/welcome.js", "utf8"),
  "WELCOME_DISMISS_KEY");

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

// ---------------------------------------------------------------------------
// 契约一：ui/guide.js —— 子页签切换（点击 + 方向键 + Home/End），四态一致
// ---------------------------------------------------------------------------
test("契约：新手指引子页签——点击与方向键都切面板，active/aria/hidden/tabindex 四态一致", async () => {
  const { page, problems } = await openApp(browser, server);
  try {
    await gotoNavTab(page, "guide");
    const tabs = ["prepare", "build", "compile", "deliver"];
    const btn = (k) => page.locator(`#guide-tabs .guide-tab[data-guide-tab="${k}"]`);
    const state = () => page.evaluate((keys) => {
      const out = {};
      for (const k of keys) {
        const b = document.querySelector(`#guide-tabs .guide-tab[data-guide-tab="${k}"]`);
        const p = document.getElementById(`guide-panel-${k}`);
        out[k] = {
          active: b.classList.contains("active"),
          selected: b.getAttribute("aria-selected"),
          tabIndex: b.tabIndex,
          panelHidden: p ? p.hidden : null,
        };
      }
      return out;
    }, tabs);
    const assertConsistent = (snap, current, where) => {
      for (const k of tabs) {
        const on = k === current;
        assert.equal(snap[k].active, on, `${where}：${k} 的 .active 不对`);
        assert.equal(snap[k].selected, String(on), `${where}：${k} 的 aria-selected 不对`);
        assert.equal(snap[k].tabIndex, on ? 0 : -1, `${where}：${k} 的 roving tabindex 不对`);
        assert.equal(snap[k].panelHidden, !on, `${where}：${k} 的面板显隐不对`);
      }
    };
    // 初始态（静态标记只给首个按钮 active，tabindex 由 initGuide 一次给全）
    assertConsistent(await state(), "prepare", "初始");

    // ① 真点击切面板
    await btn("compile").click();
    assertConsistent(await state(), "compile", "点 compile");

    // ② 方向键循环（compile → deliver → 回绕 prepare）
    await page.keyboard.press("ArrowRight");
    assertConsistent(await state(), "deliver", "ArrowRight");
    await page.keyboard.press("ArrowRight");
    assertConsistent(await state(), "prepare", "ArrowRight 回绕");
    await page.keyboard.press("ArrowLeft");
    assertConsistent(await state(), "deliver", "ArrowLeft 回绕");

    // ③ Home / End
    await page.keyboard.press("Home");
    assertConsistent(await state(), "prepare", "Home");
    await page.keyboard.press("End");
    assertConsistent(await state(), "deliver", "End");

    // ④ 焦点跟随当前页签（键盘用户的下一次 Tab 从这儿继续）
    const focused = await page.evaluate(() =>
      document.activeElement && document.activeElement.dataset
        ? document.activeElement.dataset.guideTab : null);
    assert.equal(focused, "deliver", "切换后焦点应落在当前页签上");
    assert.deepEqual(problems, []);
  } finally {
    await page.close();
  }
});

// ---------------------------------------------------------------------------
// 契约二：ui/step-state.js —— 卡片折叠 + 记忆（跨刷新）
// ---------------------------------------------------------------------------
test("契约：生成页卡片折叠——点卡头翻转 .collapsed 并落盘，刷新后记忆仍生效", async () => {
  const { page, problems } = await openApp(browser, server, { clearStorage: true });
  try {
    await gotoNavTab(page, "generate");
    // 第 3 步（目标平台）卡：拿它当样本——它的卡头是 h2，折叠按钮由 initCardCollapse 追加
    const selector = "#tab-generate .gen-steps > .card";
    const cardNo = await page.evaluate((sel) =>
      [...document.querySelectorAll(sel)]
        .map((c) => c.querySelector(".step-no"))
        .filter(Boolean).map((n) => n.textContent.trim()).find((t) => t === "3"), selector);
    assert.equal(cardNo, "3", "生成页应有第 3 步卡（样本卡）");

    const cardState = () => page.evaluate((sel) => {
      const card = [...document.querySelectorAll(sel)]
        .find((c) => c.querySelector(".step-no")?.textContent.trim() === "3");
      const btn = card.querySelector("h2 .card-collapse");
      return {
        collapsed: card.classList.contains("collapsed"),
        hasToggle: !!btn,
        btnOn: btn ? btn.classList.contains("on") : null,
      };
    }, selector);
    const stored = () => page.evaluate((key) => {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    }, COLLAPSE_KEY);

    const before = await cardState();
    assert.equal(before.hasToggle, true, "卡头应被 initCardCollapse 追加折叠按钮（无按钮 = 没绑上）");

    // 点卡头 → 折叠态翻转 + 记忆落盘
    await page.click(`${selector} >> nth=2 >> h2`);
    await page.waitForFunction((sel) => {
      const card = [...document.querySelectorAll(sel)]
        .find((c) => c.querySelector(".step-no")?.textContent.trim() === "3");
      return card.classList.contains("collapsed");
    }, selector, { timeout: 5000 }).catch(async () => {
      const now = await cardState();
      assert.fail(`点卡头没有折叠第 3 步卡（现状 ${JSON.stringify(now)}）——`
        + "initCardCollapse 的 h2 监听没生效？");
    });
    const memo = await stored();
    assert.ok(memo && Object.prototype.hasOwnProperty.call(memo, "3"),
      `折叠后应把第 3 步写进记忆（${COLLAPSE_KEY}），实际 ${JSON.stringify(memo)}`);
    assert.equal(memo["3"], true, "记忆里第 3 步应是 true（折叠）");

    // 刷新 → 记忆生效（**跨刷新的持久化契约**）
    await page.reload({ waitUntil: "domcontentloaded" });
    await gotoNavTab(page, "generate");
    await page.waitForFunction((sel) => {
      const card = [...document.querySelectorAll(sel)]
        .find((c) => c.querySelector(".step-no")?.textContent.trim() === "3");
      return card && card.querySelector("h2 .card-collapse");
    }, selector, { timeout: 15000 });
    const after = await cardState();
    assert.equal(after.collapsed, true,
      `刷新后第 3 步应仍是折叠态（记忆键 ${COLLAPSE_KEY} = ${JSON.stringify(await stored())}）`);

    // 再点一次 → 展开 + 记忆也跟着变（不是单向的一次性写入）
    await page.click(`${selector} >> nth=2 >> h2`);
    await page.waitForFunction((sel) => {
      const card = [...document.querySelectorAll(sel)]
        .find((c) => c.querySelector(".step-no")?.textContent.trim() === "3");
      return !card.classList.contains("collapsed");
    }, selector, { timeout: 5000 });
    assert.equal((await stored())["3"], false, "展开后记忆应记为 false（两向都落盘）");
    assert.deepEqual(problems, []);
  } finally {
    await page.evaluate((key) => localStorage.removeItem(key), COLLAPSE_KEY);
    await page.close();
  }
});

// ---------------------------------------------------------------------------
// 契约三：ui/welcome.js —— 欢迎卡的显示态、行动路径与「不再显示」的持久化
//
// 这条契约的**可达性**要说清（否则会写成一条永远到不了的假绿）：
// `welcomeMode` 三态由后端配置决定——测试态的真后端是"已配 key、无草稿"→ **compact**
// （只有「开始做题」「打开新手指引」两个按钮）；`btn-welcome-dismiss` 只在 **full 态**
// （未配 key）出现，而验收**不许去改用户机器上的配置**（那是真身文件）。
// 所以拆成两段，各自都可真跑：
//   · 真后端 compact 态 → 卡片可见 + 「打开新手指引」真的切到 guide 页签（行动路径契约）；
//   · 用产品自己的 HTML 生成器造出 full 态标记 → 点「不再显示」写记忆 + 隐藏，且**刷新后
//     真的不再出现**（持久化契约——dismissed 优先级最高，与当前是哪个态无关）。
// ---------------------------------------------------------------------------
test("契约：欢迎卡——compact 态可见，点「打开新手指引」真的切到指引页签", async () => {
  const { page, problems } = await openApp(browser, server, { clearStorage: true });
  try {
    await page.waitForFunction(
      () => document.getElementById("welcome-card").innerHTML.trim().length > 0,
      undefined, { timeout: 15000 });
    const visible = () => page.evaluate(() =>
      !document.getElementById("welcome-card").classList.contains("hidden"));
    assert.equal(await visible(), true, "首屏欢迎卡应可见");

    const guideBtn = page.locator("#welcome-card #btn-welcome-guide");
    assert.equal(await guideBtn.count(), 1, "欢迎卡应有「打开新手指引」按钮（initWelcome 渲染）");
    await guideBtn.click();
    await page.waitForSelector("#tab-guide", { state: "visible", timeout: 5000 });
    const active = await page.evaluate(() =>
      document.querySelector('nav button[data-tab="guide"]').classList.contains("active"));
    assert.equal(active, true, "点欢迎卡的按钮应真的切到指引页签（导航按钮也被点亮）");
    assert.deepEqual(problems, []);
  } finally {
    await page.close();
  }
});

test("契约：欢迎卡「不再显示」——写记忆、立刻隐藏，刷新后不再出现", async () => {
  const { page, problems } = await openApp(browser, server, { clearStorage: true });
  try {
    // 关键点：**不要**自己往里塞标记——`initWelcome()` 会按 `welcomeMode()` 重新渲染，
    // 塞进去的按钮连同它的接线一起被覆盖（本轮实测踩到：点了没反应，因为按钮已经不在）。
    // 走产品的真实路径：把"未配 key"这一路喂给它——`state.api_configured` 是它读的唯一输入。
    const fired = await page.evaluate(async () => {
      const app = await import("/js/app.js");
      app.setState({ ...app.state, api_configured: false });
      const ui = await import("/js/ui/welcome.js");
      ui.initWelcome();
      const btn = document.getElementById("btn-welcome-dismiss");
      if (btn) btn.click();
      return {
        hadButton: !!btn,
        hidden: document.getElementById("welcome-card").classList.contains("hidden"),
        inner: document.getElementById("welcome-card").innerHTML.trim(),
      };
    });
    assert.equal(fired.hadButton, true,
      "把 state.api_configured 置假后 initWelcome 应渲染完整欢迎卡（带「不再显示」）");
    assert.equal(fired.hidden, true, "点「不再显示」应立刻隐藏卡片");
    assert.equal(fired.inner, "", "隐藏时同时清空内容（避免下次 start 前读到残留）");

    const memo = await page.evaluate((key) => localStorage.getItem(key), WELCOME_KEY);
    assert.equal(memo, "1", `点「不再显示」应写 ${WELCOME_KEY}，实际 ${JSON.stringify(memo)}`);

    // 刷新 → 不再出现（**跨刷新的持久化契约**：dismissed 优先级最高）
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(
      () => document.querySelectorAll("#platforms .platform-card").length > 0,
      undefined, { timeout: 30000 });
    await page.waitForTimeout(300);   // 给 initWelcome 一点落地时间（同步渲染，宽裕）
    const after = await page.evaluate(() => ({
      hidden: document.getElementById("welcome-card").classList.contains("hidden"),
      inner: document.getElementById("welcome-card").innerHTML.trim(),
    }));
    assert.equal(after.hidden, true, "刷新后欢迎卡不该再出现（记忆没生效）");
    assert.equal(after.inner, "", "hidden 态应清空卡片内容（welcomeCardHTML('hidden') 返回空串）");
    assert.deepEqual(problems, []);
  } finally {
    await page.evaluate((key) => localStorage.removeItem(key), WELCOME_KEY);
    await page.close();
  }
});

// 上一条是"点下去会记住"；这一条是"记住之后真的不再打扰"——**冷启动**读记忆那条路
// （另一个浏览器上下文 = 干净 localStorage，只预置那一把记忆键）。
test("契约：欢迎卡记忆（冷启动）——预置 dismissed 后首屏就不渲染卡片", async () => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const problems = [];
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  try {
    await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
    await page.evaluate((key) => localStorage.setItem(key, "1"), WELCOME_KEY);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(
      () => document.querySelectorAll("#platforms .platform-card").length > 0,
      undefined, { timeout: 30000 });
    const state = await page.evaluate(() => ({
      hidden: document.getElementById("welcome-card").classList.contains("hidden"),
      inner: document.getElementById("welcome-card").innerHTML.trim(),
    }));
    assert.equal(state.hidden, true, "预置了 dismissed 的冷启动不该显示欢迎卡");
    assert.equal(state.inner, "", "dismissed 时卡片内容应为空串");
    assert.deepEqual(problems, []);
  } finally {
    await context.close();
  }
});
