// .scratch/code-contrast/probe-08-disabled-state.mjs —— **禁用态的真像素量具**（工单 code-contrast/03）。
//
// 为什么另立一支（而不是接着用 probe-07）：`probe-07` 的禁用桶**实测是空的**——
// 那些禁用按钮坐在带渐变的容器里（`.card` 有 `background-image: linear-gradient(...)`），
// 被"祖先渐变跳过"规则滤掉了。扫描看不见 ≠ 达标（这正是本单要治的那条口径）。
//
// 这一支干三件事：
//   ① **找得到**：每个页签里凡 `el.disabled === true` 或 `classList.contains("disabled")` 且
//      **有文字**的元素都收进来（不再按"祖先渐变"跳过，但把这件事**如实记进 JSON**）；
//   ② **拍得下**：逐个元素截图（一个元素一张 PNG）——真像素，落在盘上可人眼复核；
//   ③ **对得上**：JSON 里连"静态预测要用到的原料"一起记（自己的 `color` / `background-color` /
//      `opacity` / 祖先合成底 `behind`），由 `probe-08-disabled-state-read.py` 把它与
//      "实测字形像素 vs 实测主色底"逐格对差。
//
// **`--tag` 的用法**：禁用态这一单改的是**产品面**（`index.html` 的样式块），所以要拿改前/改后
// 两份像素对照——`--tag before` 在改动前跑（旧树）、`--tag after` 在改动后跑。
// 旧树上 `opacity: .45` 会把字形与底**一起**往容器底上拉，这正是"2.66 / 2.06"那类低读数的来源；
// 这一支的第一份读数就该把那个机制重现出来（重现不了说明量具本身不可信）。
//
// 跑法（仓库根；跑完接 probe-08-disabled-state-read.py）：
//     node .scratch/code-contrast/probe-08-disabled-state.mjs --tag before
//     node .scratch/code-contrast/probe-08-disabled-state.mjs --tag after
// ⚠ 不要与全量 pytest 同时跑（本机负载下浏览器用例会抖）。
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const TAG = (() => {
  const i = process.argv.indexOf("--tag");
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1].replace(/[^\w-]/g, "") : "cur";
})();

const TABS = ["generate", "hwcheck", "settings", "guide", "changelog", "code",
  "master", "library", "reference", "pdf", "md", "topic"];

/** 每个主题最多拍这么多张（够覆盖各页的禁用态，又不至于让一轮跑上十分钟）。 */
const MAX_SHOTS = 16;

// ⚠ `COLLECT` 里的 `parse` / `behindOf` / `hasText` / `path` / `slug` **必须自带一份**：
// 它是 `page.evaluate` 的载荷，会被**序列化后丢进浏览器**，看不到模块作用域——所以
// `probe-07` 与这里各有一份是结构使然，不是抄漏（Python 读数半那边能共用，已经抽进 `pixel_lib.py`）。
const COLLECT = (payload) => {
  const { tab: TAB, max: MAX } = payload;
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

  const out = { theme: document.documentElement.dataset.theme || "dark", tab: TAB,
    shots: [], disabled: 0, missing: false,
    // **没量到的那些也要记账**（工单 03 的口径："扫描看不见"不许当达标）：逐条报出原因，
    // 免得下一轮把"5 格全 ✅"读成"全站禁用态都达标了"。
    skipped: { 不可见: 0, 零尺寸: 0, 无文字: 0, 超过上限: 0 } };
  const btn = document.querySelector(`nav button[data-tab="${TAB}"]`);
  if (!btn) { out.missing = true; return out; }
  btn.click();
  for (const d of document.querySelectorAll("details:not([open])")) d.open = true;
  const panel = document.getElementById(`tab-${TAB}`);
  if (!panel) { out.missing = true; return out; }
  let seen = 0, key = 0;
  for (const el of panel.querySelectorAll("*")) {
    const byAttr = el.disabled === true;
    const byClass = typeof el.className === "string" && el.classList.contains("disabled");
    if (!byAttr && !byClass) continue;
    out.disabled++;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) < 0.05) { out.skipped.不可见++; continue; }
    const box = el.getBoundingClientRect();
    if (box.width < 4 || box.height < 4) { out.skipped.零尺寸++; continue; }
    if (!hasText(el)) { out.skipped.无文字++; continue; }
    if (seen >= MAX) { out.skipped.超过上限++; continue; }
    el.setAttribute("data-probe08", String(key));
    // 祖先里有没有渐变（`.card` 那种）——记下来：probe-07 的禁用桶就是被这条滤空的
    let ancGrad = false;
    for (let n = el.parentElement; n; n = n.parentElement) {
      if (getComputedStyle(n).backgroundImage !== "none") { ancGrad = true; break; }
    }
    out.shots.push({
      key: String(key), tab: TAB, idx: seen, sel: path(el), slug: slug(path(el)),
      // `<input>` / `<textarea>` 的字在 `value` 里、不在 `textContent` 里——两处都取
      // （空串 = 这一格**没有字形像素**，读数半会跳过它的比值，不拿边框像素当证据）
      text: String(el.value || el.textContent || "").trim().slice(0, 40),
      tag: el.tagName.toLowerCase(),
      how: byAttr ? "disabled 属性" : ".disabled 类",
      color: cs.color, background: cs.backgroundColor, border: cs.borderTopColor,
      opacity: Number(cs.opacity), fontSize: cs.fontSize,
      ownGradient: cs.backgroundImage !== "none", ancestorGradient: ancGrad,
      behind: behindOf(el),
      box: { x: Math.round(box.x), y: Math.round(box.y),
        width: Math.round(box.width), height: Math.round(box.height) },
    });
    seen++;
    key++;
  }
  return out;
};

const server = await startServer();
const browser = await chromium.launch();
const shots = [];
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
      const data = await page.evaluate(COLLECT, { tab, max: MAX_SHOTS });
      if (data.missing) { console.log(`  ${tab.padEnd(10)}（没找到页签 / 面板）`); continue; }
      const skipped = Object.entries(data.skipped).filter(([, n]) => n)
        .map(([k, n]) => `${k} ${n}`).join(" / ");
      console.log(`  ${tab.padEnd(10)}禁用元素 ${String(data.disabled).padStart(2)}　拍得 ${data.shots.length}`
        + (skipped ? `　**没量到**：${skipped}` : ""));
      for (const s of data.shots) {
        const file = `probe-08-${TAG}-${theme}-${s.tab}-${s.idx}-${s.slug}.png`;
        // 元素截图：Playwright 会先把它滚进视口（页面上加了 `data-probe08` 标记，不影响外观）
        await page.locator(`[data-probe08="${s.key}"]`).screenshot({ path: join(HERE, file) });
        shots.push({ theme, ...s, file });
        console.log(`    ${s.how}  opacity ${s.opacity}  ${s.color} on ${s.background}`
          + `  「${s.text}」${s.ancestorGradient ? "  ⚠祖先渐变" : ""}  → ${file}`);
      }
      // 擦掉标记，别让下一轮看到上一轮的 residue
      await page.evaluate(() => {
        for (const el of document.querySelectorAll("[data-probe08]")) el.removeAttribute("data-probe08");
      });
    }
  }
  writeFileSync(join(HERE, `probe-08-shots-${TAG}.json`),
    JSON.stringify({ tag: TAG, shots }, null, 2), "utf8");
  console.log(`\n已落盘 probe-08-shots-${TAG}.json（${shots.length} 格）`);
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
