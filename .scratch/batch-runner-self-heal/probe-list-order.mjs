// 探针（第十四轮尾巴收口）：`/json/list` 的**顺序语义**是什么？
//
// 为什么重要：50+ 支冒烟脚本挑页用的都是
//   `list.find(t => t.type === 'page' && t.url.startsWith(pageUrl))`
// 即「列表里第一个匹配页」。而 `cdp-harness.rebuildTab()` 只关**第一个** page，
// 于是长连跑里会留下一个**永不被关闭的孤儿页**（实测：9251 上 1C933610 跨数十支次恒定存在）。
// 若列表顺序是「新页在后」，脚本就会挑到孤儿页而不是批跑器刚重建的那一个。
//
// 本探针只回答顺序问题，且**不碰 8000 的页**（用 about:blank，避免干扰正在跑的批次）：
//   ① 记录当前列表顺序；② 连开两个可识别的页；③ 再记录——新页落在头部还是尾部。
// 用完即关（不留残留）。
//
// 用法：node .scratch/batch-runner-self-heal/probe-list-order.mjs [port]

import { listTargets, fetchT } from "../cdp-harness.mjs";

const PORT = Number(process.argv[2] || 9251);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const snap = async (label) => {
  const list = await listTargets(PORT);
  const pages = list.filter((t) => t.type === "page");
  console.log(`\n[${label}] page 数 ${pages.length}（从上到下 = 列表顺序）`);
  for (const [i, t] of pages.entries()) {
    console.log(`   [${i}] ${t.id.slice(0, 8)}  ${String(t.url).slice(0, 48)}`);
  }
  return pages;
};

await snap("起始");

const made = [];
for (const tag of ["A", "B"]) {
  const r = await fetchT(`http://127.0.0.1:${PORT}/json/new?about:blank`, 8000, { method: "PUT" });
  const t = await r.json().catch(() => null);
  if (t && t.id) made.push({ tag, id: t.id });
  console.log(`新建页 ${tag} → ${t && t.id ? t.id.slice(0, 8) : "(失败)"}`);
  await sleep(600);
}

const after = await snap("新建 A、B 之后");
const idx = made.map((m) => ({ ...m, at: after.findIndex((t) => t.id === m.id) }));
console.log(`\n新页落位：${idx.map((m) => `${m.tag}@${m.at}`).join("  ")}`);
const ok = idx.length === 2 && idx[0].at >= 0 && idx[1].at >= 0;
if (ok) {
  const [a, b] = idx;      // A 先建、B 后建
  console.log(b.at < a.at
    ? `⇒ 顺序 = **新页在前**（后建的 B@${b.at} 排在先建的 A@${a.at} 之前 ⇒ 下标越小越新）`
    : `⇒ 顺序 = **新页在后**（后建的 B@${b.at} 排在先建的 A@${a.at} 之后 ⇒ 下标越小越旧）`);
}

for (const m of made) {
  await fetchT(`http://127.0.0.1:${PORT}/json/close/${m.id}`, 5000).catch(() => {});
}
await sleep(400);
await snap("清理后");
