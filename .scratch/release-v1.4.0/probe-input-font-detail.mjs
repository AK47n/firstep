// 追查：沙箱验收里那 5 条「字号取值不在六档角色内」的例外到底是哪些控件（发版 v1.4.0，工单 03）。
//
// 验收探针只报到「input / 13.3333px」这一层——按本仓库的纪律（"看着像" ≠ "量出来"），
// 先把**是哪些元素、带不带可见文字**量清楚，再决定是修还是记账。
//
// 两条口径（第一次跑时没写，导致把自绘控件也算成例外）：
//   ① 只看**有文字的元素**：`checkbox` / `radio` / `file` 是自绘控件（没有文字、字号不影响渲染），
//      它们的 computed font-size 是浏览器默认值，不构成"字号档位"的问题；
//      `input`（文本型）/ `select` / `textarea` / `button` 按定义算有文字；
//      其余元素要求**直接文本子节点非空**。
//   ② 每个页签里折叠的 `<details>` **全展开**后再量——否则"默认收起的那些输入框"永远在射程外。
//
// 用法：node .scratch/release-v1.4.0/probe-input-font-detail.mjs [--base http://127.0.0.1:8020]

import { chromium } from "playwright";
import process from "node:process";

const argv = process.argv.slice(2);
const at = argv.indexOf("--base");
const BASE = at >= 0 && argv[at + 1] ? argv[at + 1] : "http://127.0.0.1:8020";
const TABS = ["generate", "hwcheck", "topic", "code", "settings", "library",
              "reference", "pdf", "md", "master", "guide", "changelog"];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(BASE, { waitUntil: "domcontentloaded" });
await page.waitForSelector("button[data-tab]", { timeout: 15000 });

let total = 0;
for (const tab of TABS) {
  await page.click(`button[data-tab="${tab}"]`);
  await page.waitForTimeout(200);
  await page.evaluate((tabId) => {
    for (const d of document.getElementById(`tab-${tabId}`).querySelectorAll("details")) d.open = true;
  }, tab);
  await page.waitForTimeout(250);
  const rows = await page.evaluate((tabId) => {
    const root = document.getElementById(`tab-${tabId}`);
    const textBearing = (el) => {
      const tag = el.tagName.toLowerCase();
      if (tag === "input") {
        const t = (el.getAttribute("type") || "text").toLowerCase();
        return !["checkbox", "radio", "file", "range", "hidden", "color"].includes(t);
      }
      if (tag === "select" || tag === "textarea" || tag === "button") return true;
      return Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim() !== "");
    };
    const out = [];
    for (const el of root.querySelectorAll("*")) {
      if (el.closest("svg")) continue;
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (!textBearing(el)) continue;
      const fs = parseFloat(cs.fontSize);
      if (!Number.isFinite(fs) || [12, 13, 14, 16, 20, 22].some((x) => Math.abs(fs - x) < 0.06)) continue;
      out.push({
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute("type") || "(无 type 属性)",
        id: el.id || "",
        cls: (el.className || "").toString().trim().split(/\s+/).slice(0, 3).join("."),
        fs: cs.fontSize,
        text: (el.value || el.textContent || "").trim().slice(0, 24),
      });
    }
    return out;
  }, tab);
  total += rows.length;
  if (rows.length === 0) continue;
  console.log(`\n[${tab}] 例外 ${rows.length} 个：`);
  for (const r of rows) {
    console.log(`  ${r.tag}[type=${r.type}]${r.id ? "#" + r.id : ""}${r.cls ? "." + r.cls : ""} ` +
                `→ ${r.fs} ｜ 文字：「${r.text}」`);
  }
}
console.log(`\n合计例外 ${total} 个（口径：有文字的元素 + 折叠区全展开）`);
await browser.close();
