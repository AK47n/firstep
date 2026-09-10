// 诊断（B9）：mspm0.syscfg 在详情弹窗里为什么没有 tok-* 高亮 span？
// 分两层查：① 纯件 highlightText/languageOf 对真实 syscfg 文本的产出；
//            ② 页面里实际渲染的容器 HTML 类名。
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251;
const t = await rebuildTab({ port: PORT });
if (!t) { console.error("重建失败"); process.exit(1); }
const c = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => c.Eval(e);

for (let i = 0; i < 80; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('master-rows')`)) break;
  await new Promise((r) => setTimeout(r, 250));
}

// ① 纯件层：拿真实 syscfg 文本（经后端端点）跑 languageOf + highlightText
const pure = await Eval(`(async () => {
  const hl = await import('/js/fx/highlight.js');
  const txt = (await (await fetch('/api/masters/mspm0/files/' + encodeURIComponent('mspm0.syscfg'))).json()).content || '';
  const lang = hl.languageOf('mspm0.syscfg');
  const html = hl.highlightText(txt, lang);
  const classes = [...new Set((html.match(/class="([^"]+)"/g) || []).map((s) => s.slice(7, -1)))];
  return { lang, len: txt.length, first120: txt.slice(0, 120), classes, htmlHead: html.slice(0, 160) };
})()`);
console.log("① 纯件：", JSON.stringify(pure, null, 1));

// ② 页面层：打开 mspm0 详情 → 点 syscfg → 数 tok-* 与容器 HTML
await Eval(`(() => { const b = [...document.querySelectorAll('nav button')].find((x) => x.dataset.tab === 'master'); if (b) b.click(); })()`);
await new Promise((r) => setTimeout(r, 800));
await Eval(`document.querySelector('#master-rows [data-master-detail="mspm0"]')?.click()`);
for (let i = 0; i < 40; i++) {
  if (await Eval(`!!document.querySelector('.ref-files-overlay [data-master-file="mspm0.syscfg"]')`)) break;
  await new Promise((r) => setTimeout(r, 200));
}
await Eval(`document.querySelector('.ref-files-overlay [data-master-file="mspm0.syscfg"]')?.click()`);
await new Promise((r) => setTimeout(r, 900));
const dom = await Eval(`(() => {
  const el = document.querySelector('.ref-files-overlay [data-master-content]');
  if (!el) return { err: '无容器' };
  const inner = el.querySelector('.master-file-pre');
  return {
    hasPre: !!inner,
    tokCount: el.querySelectorAll('[class*="tok-"]').length,
    classes: [...new Set([...el.querySelectorAll('*')].map((n) => n.className).filter(Boolean))].slice(0, 12),
    htmlHead: (inner ? inner.innerHTML : el.innerHTML).slice(0, 200),
  };
})()`);
console.log("② 页面：", JSON.stringify(dom, null, 1));
c.close();
