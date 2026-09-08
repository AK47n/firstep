// 冒烟（guide-jump-flash/01）：跳转目标高亮——用户反馈「打开新手词表只
// 跳转过去但没有任何光标提示，用户很难看到在哪里」。根因：gotoNavTab 只
// focus()（卡片等非交互元素无默认焦点样式）+ scrollIntoView，无可见落点。
// 修复：聚焦后加 .jump-flash（accent 描边 + 脉冲微光动画，1.8s 后移除）。
// 断言：① 点「打开新手词表」→ 切到生成页；② glossary-card 视口中央；
// ③ 带 .jump-flash 类；④ 1.9s 后类移除（动画结束）；⑤ 连续两次跳转重置
// 计时（第二次后仍带类且稍后消失）。零依赖 CDP（9251）。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || "?"));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 6000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
const { writeFileSync } = await import("node:fs");
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker && !!document.getElementById('tab-guide')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// 指南 → build 章 → 点「打开新手词表」
await Eval(`document.querySelector('nav button[data-tab="guide"]')?.click()`);
await waitFor(`getComputedStyle(document.getElementById('tab-guide')).display !== 'none'`);
await Eval(`document.querySelector('.guide-tab[data-guide-tab="build"]')?.click()`);
await waitFor(`document.getElementById('guide-panel-build')?.innerText.includes('打开新手词表')`);
await Eval(`[...document.querySelectorAll('#guide-panel-build .guide-jump')].find((b) => b.textContent.includes('打开新手词表'))?.click()`);
check("点「打开新手词表」→ 切到生成页", await waitFor(`getComputedStyle(document.getElementById('tab-generate')).display !== 'none' && !!document.getElementById('glossary-card')`));

// 卡片位于视口中央且带高亮类
const flashed = await waitFor(`document.getElementById('glossary-card').classList.contains('jump-flash')`);
check("跳转后 glossary-card 带 .jump-flash（可见高亮）", flashed);
const geo = await Eval(`(() => {
  const r = document.getElementById('glossary-card').getBoundingClientRect();
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), vh: innerHeight };
})()`);
check("卡片滚入视口（居中，top 在 150~750）", geo.top > 150 && geo.top < 750 && geo.bottom <= geo.vh, JSON.stringify(geo));
const shotA = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/code-viewer-editor/shot-jump-flash.png", Buffer.from(shotA.result.data, "base64"));

// 1.9s 后类移除
check("1.9s 后 .jump-flash 移除（动画只播一次）",
  await waitFor(`!document.getElementById('glossary-card').classList.contains('jump-flash')`, 3000));

// 连续两次跳转：第二次重置计时（跳转后仍带类 → 1.9s 后移除）
await Eval(`document.querySelector('nav button[data-tab="guide"]')?.click()`);
await waitFor(`getComputedStyle(document.getElementById('tab-guide')).display !== 'none'`);
await Eval(`[...document.querySelectorAll('#guide-panel-build .guide-jump')].find((b) => b.textContent.includes('打开新手词表'))?.click()`);
await new Promise((r) => setTimeout(r, 100));
// 立即再点一次（重置场景：从 guide 再跳）
await Eval(`document.querySelector('nav button[data-tab="guide"]')?.click()`);
await waitFor(`getComputedStyle(document.getElementById('tab-guide')).display !== 'none'`);
await Eval(`[...document.querySelectorAll('#guide-panel-build .guide-jump')].find((b) => b.textContent.includes('打开新手词表'))?.click()`);
check("连续跳转 → 高亮类重新出现（计时重置）",
  await waitFor(`document.getElementById('glossary-card').classList.contains('jump-flash')`, 2000));
check("重置后仍会在时限内移除",
  await waitFor(`!document.getElementById('glossary-card').classList.contains('jump-flash')`, 3000));

console.log(`---- 冒烟总览 ----`);
console.log(`PASS ${passed} / FAIL ${failed}`);
process.exit(failed ? 1 : 0);
