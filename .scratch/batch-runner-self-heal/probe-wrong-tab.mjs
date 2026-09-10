// 探针（第十四轮尾巴收口）：长连跑里「脚本会挑到哪个标签页」+「有没有孤儿页」。
//
// 背景：50+ 支冒烟脚本挑页用的是
//   `list.find(t => t.type === 'page' && t.url.startsWith(pageUrl))`   ← 取列表**第一个**匹配页
// 而 `cdp-harness.rebuildTab()` 只关**一个** page（`pageTarget(anyPage:true)` = 列表第一个）。
// 于是每轮重建 = 「关掉第一个 + 新开一个」，若列表里本来就有第二个匹配页，它**永不被关闭**
// （实测：9251 上 `1C933610` 跨数十支次恒定存在 = 孤儿页）。
//
// **顺序语义已实测**（`.scratch/batch-runner-self-heal/probe-list-order.mjs`）：
// `/json/list` 是**新页在前**（后建的页下标更小）。所以「关第一个」= 关最新的那个，
// 而脚本的 `find()` 取第一个 = 取最新的那个 ⇒ **在当前 Chrome 顺序下恰好命中批跑器刚重建的页**。
// 也就是说：挑页正确性是**依赖未文档化的列表顺序**得出的，不是由构造保证的。
//
// 本探针只读：列匹配页 + 对每页取一份「状态指纹」，并报出
//   ① 匹配页数（>1 即有孤儿）；② `find()` 会挑中哪个；③ 那个是不是最新页。
//
// 用法：node .scratch/batch-runner-self-heal/probe-wrong-tab.mjs [样本数] [间隔秒] [端口]

import { connect, listTargets } from "../cdp-harness.mjs";

const samples = Number(process.argv[2] || 1);
const gapS = Number(process.argv[3] || 15);
const PORT = Number(process.argv[4] || 9251);
const PAGE_URL = "http://127.0.0.1:8000/";

const FINGERPRINT = `JSON.stringify({
  ready: document.readyState,
  smokeMarker: typeof window.__smokeMarker,
  probe: typeof window.__probe,
  tabs: document.querySelectorAll('#code-tabs .code-tab').length,
  tabPaths: [...document.querySelectorAll('#code-tabs .code-tab')].map((t) => t.dataset.tabPath),
  activeTab: document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath || null,
  w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio,
  zoom: getComputedStyle(document.documentElement).zoom,
  activeNav: document.querySelector('nav button.on')?.dataset.tab || null,
})`;

const matching = async () => {
  const list = await listTargets(PORT);
  return (Array.isArray(list) ? list : [])
    .filter((t) => t.type === "page" && String(t.url).startsWith(PAGE_URL));
};

for (let i = 1; i <= samples; i++) {
  const pages = await matching();
  const newest = pages[0] || null;        // 实测：下标越小越新
  const picked = pages.find(() => true) || null;   // 脚本的 find() 语义 = 第一个匹配
  console.log(`\n== 样本 ${i}/${samples}  ${new Date().toISOString()} ==`);
  console.log(`   匹配页 target 数：${pages.length}${pages.length > 1 ? `（孤儿 ${pages.length - 1} 个）` : ""}`);
  for (const [idx, t] of pages.entries()) {
    let fp = "(取指纹失败)";
    try {
      const c = await connect({ port: PORT, timeoutMs: 8000, targetId: t.id });
      fp = await c.Eval(FINGERPRINT, 6000);
      c.close();
    } catch (e) {
      fp = "取指纹失败：" + String(e && e.message || e).slice(0, 80);
    }
    const tag = [];
    if (idx === 0) tag.push("←最新");
    if (idx === pages.length - 1 && pages.length > 1) tag.push("←最旧(孤儿)");
    if (t === picked) tag.push("←find()会挑中");
    console.log(`   [${idx}] ${t.id.slice(0, 8)} ${tag.join(" ")}`);
    console.log(`        ${fp}`);
  }
  console.log(`   ⇒ find() 挑中最新页 = ${picked && newest ? picked.id === newest.id : "n/a"}`);
  if (i < samples) await new Promise((r) => setTimeout(r, gapS * 1000));
}
