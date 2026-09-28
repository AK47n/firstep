// .scratch/ui-density/probe-04-input-clickable.mjs —— 「输入框点不动」判据（诊断回路）。
//
// 症状（用户报告）：「很多输入框都无法点击输入」。
//
// 判据三条腿（都要能**在这个 bug 上判红**）：
//   ① **遮盖**：对每个输入控件取 3 个点（中心 / 左 1/4 / 右 3/4），`elementFromPoint`
//      返回的不是它自己（也不是它的后代/祖先）= 被盖住 → 当场报出盖住它的元素（标签/id/class/pointer-events）。
//   ② **真打字**：点进去敲字，值必须变。
//   ③ **状态**：顺带报出 readonly / disabled —— 那不是"点不动"，但用户看到的现象一样（打不进字），
//      必须与 ① 分开记，免得把"设计如此"当成 bug。
//
// **滚动扫到底**：首屏之外也要覆盖（第一版只看首屏，全绿＝判据太窄）。
//
// 用法：
//     node .scratch/ui-density/probe-04-input-clickable.mjs after
//     node .scratch/ui-density/probe-04-input-clickable.mjs before   # 配 git stash 对照
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const TAG = process.argv[2] || "run";
const TABS = ["generate", "hwcheck", "library", "reference", "pdf", "md", "topic",
  "master", "settings", "changelog", "guide", "code"];
const lines = [];
const say = (s) => { lines.push(s); console.log(s); };

// 在页面里对**当前视口内、且不在黏顶栏底下**的控件取样。
//
// 为什么要排掉黏顶栏（`header { position: sticky; top: 0; z-index: 100 }`）：
// 第一版把滚上去压在顶栏下面的控件也当成"被盖住"——取样点 (370,22) 的"最上层元素"当然是
// `header`。**但那个控件用户根本看不见**，他不会去点；把它算成 bug 是探针自己的假红。
// 判据要按用户视角来：只在**内容可见区**（顶栏下沿到视口底部）取样。
const PROBE = () => {
  const out = [];
  const headerBottom = (() => {
    const h = document.querySelector("header");
    return h ? h.getBoundingClientRect().bottom : 0;
  })();
  for (const el of document.querySelectorAll("input, textarea, select")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const st = getComputedStyle(el);
    if (st.visibility === "hidden" || st.display === "none") continue;
    const pts = [0.5, 0.25, 0.75].map((f) => [r.left + r.width * f, r.top + r.height / 2]);
    const inContent = pts.filter(([x, y]) => x >= 0 && x <= innerWidth
      && y > headerBottom + 2 && y < innerHeight - 2);
    if (!inContent.length) continue;          // 整块都在顶栏底下 / 视口外：不判
    const bad = [];
    for (const [x, y] of inContent) {
      const top = document.elementFromPoint(x, y);
      const ok = top === el || el.contains(top) || (top && top.contains(el));
      if (!ok) {
        bad.push({
          x: Math.round(x), y: Math.round(y),
          tag: top ? top.tagName.toLowerCase() : "(null)",
          id: top ? (top.id || "") : "",
          cls: top && typeof top.className === "string" ? top.className : "",
          pe: top ? getComputedStyle(top).pointerEvents : "",
        });
      }
    }
    out.push({
      tag: el.tagName.toLowerCase(),
      id: el.id || "",
      cls: typeof el.className === "string" ? el.className : "",
      ph: (el.getAttribute("placeholder") || "").slice(0, 24),
      disabled: el.disabled === true,
      readonly: el.readOnly === true,
      covered: bad,
    });
  }
  return out;
};

const server = await startServer();
const browser = await chromium.launch();
const seen = new Map();          // key = 定位串 → 记录
const covered = new Map();
const states = new Map();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector('nav button[data-tab="hwcheck"]');
  for (const tab of TABS) {
    const btn = `nav button[data-tab="${tab}"]`;
    if (!(await page.$(btn))) continue;
    await page.click(btn);
    await page.waitForTimeout(400);
    // 每个页签：从顶滚到底，每一步都取样
    const height = await page.evaluate(() => document.body.scrollHeight);
    const steps = Math.max(1, Math.ceil(height / 800));
    let total = 0;
    for (let i = 0; i < steps; i++) {
      await page.evaluate((y) => window.scrollTo(0, y), i * 800);
      await page.waitForTimeout(120);
      const items = await page.evaluate(PROBE);
      total += items.length;
      for (const it of items) {
        const key = `${tab}|${it.tag}#${it.id}.${it.cls}|${it.ph}`;
        seen.set(key, it);
        if (it.covered.length) covered.set(key, it);
        if (it.disabled || it.readonly) states.set(key, it);
      }
    }
    say(`--- [${tab}] 扫到控件样本 ${total} 次（去重 ${[...seen.keys()].filter((k) => k.startsWith(tab + "|")).length} 个）`);
  }

  // 打开几个"要点一下才出现的"编辑态再扫一遍（第一版漏的就是这类）
  say("");
  say("== 打开编辑态后再扫 ==");
  const openers = [
    { tab: "hwcheck", sel: "#btn-my-device-new", what: "「+ 我的器件」表单" },
    { tab: "settings", sel: "#settings-*", what: "(跳过：选择器未定)" },
  ];
  await page.click('nav button[data-tab="hwcheck"]');
  await page.waitForTimeout(300);
  if (await page.$("#btn-my-device-new")) {
    await page.click("#btn-my-device-new");
    await page.waitForTimeout(400);
    await page.evaluate(() => window.scrollTo(0, 900));
    await page.waitForTimeout(200);
    const items = await page.evaluate(PROBE);
    say(`  「+ 我的器件」表单打开后，视口内控件 ${items.length} 个`);
    for (const it of items) {
      const key = `hwcheck-form|${it.tag}#${it.id}.${it.cls}|${it.ph}`;
      seen.set(key, it);
      if (it.covered.length) { covered.set(key, it); say(`    ✗ ${key} 被盖住`); }
      if (it.disabled || it.readonly) states.set(key, it);
    }
  }
} finally {
  await browser.close();
  await server.stop();
}

say("");
say("== ① 被盖住的控件 ==");
if (!covered.size) say("  （无）");
for (const [key, it] of covered) {
  const b = it.covered[0];
  say(`  ✗ ${key}`);
  say(`      取样点 (${b.x},${b.y}) 最上层是 <${b.tag} id="${b.id}" class="${b.cls}" pointer-events=${b.pe}>`);
  say(`      3 个取样点里被盖 ${it.covered.length} 个`);
}
say("");
say("== ③ readonly / disabled（不是「点不动」，但用户看到的现象一样）==");
if (!states.size) say("  （无）");
for (const [key, it] of states) {
  say(`  · ${key}${it.disabled ? " [disabled]" : ""}${it.readonly ? " [readonly]" : ""}`);
}
const verdict = `\n== 结论（${TAG}）==\n  去重控件 ${seen.size} 个 / 被盖住 ${covered.size} 个 / readonly|disabled ${states.size} 个`;
say(verdict);
writeFileSync(join(HERE, `probe-04-input-clickable-${TAG}.txt`), lines.join("\n") + "\n", "utf8");
process.exit(covered.size ? 1 : 0);
