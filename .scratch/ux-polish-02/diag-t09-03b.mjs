// 诊断（B15 / 03 项复现）：先让 llm-api 卡处于「展开」态，再走 probe-t09 的 03 序列
// （脚本逻辑：非 collapsed 就点 .card-collapse 把它折叠 → 然后点横幅「去设置」）。
// 目的：判断首次批跑里 03 红是「脚本前提/顺序」还是「产品在冷启动下点了没反应」。
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251;
const t = await rebuildTab({ port: PORT });
if (!t) { console.error("重建标签页失败"); process.exit(1); }
const c = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => c.Eval(e);

await c.cdp("Network.enable").catch(() => {});
await c.cdp("Network.setCacheDisabled", { cacheDisabled: true }).catch(() => {});
await c.cdp("Network.clearBrowserCache").catch(() => {});

const token = "np=" + Date.now();
await c.cdp("Page.navigate", { url: "http://127.0.0.1:8000/?" + token });
for (let i = 0; i < 120; i++) {
  const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`).catch(() => null);
  if (st && st.href.includes(token) && st.rs === "complete" && st.ov) break;
  await new Promise((r) => setTimeout(r, 250));
}

const state = () => Eval(`JSON.stringify({
  llmCard: (() => { const d = document.querySelector('[data-collapse-id="llm-api"]'); return d ? d.className : null; })(),
  collapseKey: localStorage.getItem('firstep.settingsCollapse.v1'),
  tabSettings: document.getElementById('tab-settings').classList.contains('active'),
  focused: document.activeElement ? document.activeElement.id : null,
})`);

console.log("A 就绪后：", await state());

// 复现 probe-t09 的 03 前操作：非 collapsed → 点 .card-collapse 折叠
const folded = await Eval(`(() => {
  const card = document.querySelector('[data-collapse-id="llm-api"]');
  if (!card.classList.contains('collapsed')) { card.querySelector('.card-collapse').click(); return 'clicked-collapse'; }
  return 'already-collapsed';
})()`);
console.log("B 折叠操作：", folded, await state());

await Eval(`document.getElementById('gen-banner').classList.remove('hidden')`);
await Eval(`document.getElementById('btn-banner-goto-settings').click()`);
await new Promise((r) => setTimeout(r, 600));
console.log("C 点「去设置」后：", await state());

// 再点一次（对照：第二次是否就好）
await Eval(`document.getElementById('btn-banner-goto-settings').click()`);
await new Promise((r) => setTimeout(r, 600));
console.log("D 再点一次后：", await state());

c.close();
