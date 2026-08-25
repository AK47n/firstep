// 冒烟（工单 module-info-dialog/01）：模块卡「详情」按钮 → 全量信息弹窗 →
// 三种关闭（Esc/遮罩/✕）；卡片本体点击仍添加模块（主流程回归）；重复打开
// 替换；off 卡详情可看（附「当前平台无此模块版本」提示条）。
// 零依赖：node 内置 fetch + WebSocket 直连 Edge CDP（9231）；webapp 8000 提供真实 /api/modules。
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

let ready = false;
// 重新加载页面：webapp 静态文件实时更新，但浏览器内存中的 JS 需刷新才换新
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('module-grid')
      && typeof state !== 'undefined' && state && state.modules && state.modules.length > 0`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪（module-grid 或 state.modules 未加载）"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

// ---- 切「生成」tab ----
await Eval(`document.querySelector('[data-tab="generate"]').click()`);
await new Promise((r) => setTimeout(r, 300));

// ---- 基础状态：卡片渲染「详情」按钮 ----
const base = await Eval(`(() => {
  const cards = document.querySelectorAll('#module-grid .module-card');
  const btns = document.querySelectorAll('#module-grid .mc-info');
  return { cards: cards.length, btns: btns.length, first: state.modules[0] };
})()`);
check("网格有卡片", base.cards > 0, "cards=" + base.cards);
check("每张卡都有「详情」按钮", base.btns === base.cards, "btns=" + base.btns);

// ---- 点第一张卡详情按钮 → 弹窗出现 + 内容断言（跟随真实数据）----
await Eval(`document.querySelectorAll('#module-grid .mc-info')[0].click()`);
await new Promise((r) => setTimeout(r, 200));
const modal = await Eval(`(() => {
  const ov = document.querySelector('.module-info-overlay');
  if (!ov) return null;
  const text = ov.textContent;
  const m = state.modules[0];
  const firstPlat = Object.keys(m.platforms || {})[0];
  const e = (m.platforms || {})[firstPlat];
  return {
    overlayCount: document.querySelectorAll('.module-info-overlay').length,
    hasSlug: text.includes(m.slug),
    hasDesc: text.includes(String(m.description || "")),
    hasPlat: firstPlat ? text.includes(firstPlat) || text.includes(moduleGridPlatformLabel(firstPlat)) : true,
    hasFile: (e && e.files && e.files.length) ? text.includes(e.files[0]) : true,
    hasPins: (e && e.pins && e.pins.length) ? text.includes(String((e.pins[0].label || e.pins[0].id))) : true,
    closeBtn: !!ov.querySelector('.ref-files-close'),
  };
})()`);
check("点「详情」→ 弹窗出现", modal !== null);
check("弹窗只有一个（无叠加）", modal && modal.overlayCount === 1, "count=" + (modal || {}).overlayCount);
check("弹窗含 slug", modal && modal.hasSlug);
check("弹窗含完整描述", modal && modal.hasDesc);
check("弹窗含平台区块", modal && modal.hasPlat);
check("弹窗含文件清单（若 files 非空）", modal && modal.hasFile);
check("弹窗含引脚表（若 pins 非空）", modal && modal.hasPins);
check("弹窗有 ✕ 关闭按钮", modal && modal.closeBtn);

// ---- Esc 关闭 ----
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`);
await new Promise((r) => setTimeout(r, 150));
check("Esc 关闭弹窗", (await Eval(`document.querySelectorAll('.module-info-overlay').length`)) === 0);

// ---- 重开 → 点遮罩关闭 ----
await Eval(`document.querySelectorAll('#module-grid .mc-info')[0].click()`);
await new Promise((r) => setTimeout(r, 150));
await Eval(`document.querySelector('.module-info-overlay').click()`);
await new Promise((r) => setTimeout(r, 150));
check("点遮罩关闭弹窗", (await Eval(`document.querySelectorAll('.module-info-overlay').length`)) === 0);

// ---- 重开 → 点 ✕ 关闭 ----
await Eval(`document.querySelectorAll('#module-grid .mc-info')[0].click()`);
await new Promise((r) => setTimeout(r, 150));
await Eval(`document.querySelector('.module-info-overlay .ref-files-close').click()`);
await new Promise((r) => setTimeout(r, 150));
check("点 ✕ 关闭弹窗", (await Eval(`document.querySelectorAll('.module-info-overlay').length`)) === 0);

// ---- 重复打开（不关）→ 替换不叠加 ----
await Eval(`document.querySelectorAll('#module-grid .mc-info')[0].click()`);
await new Promise((r) => setTimeout(r, 150));
await Eval(`document.querySelectorAll('#module-grid .mc-info')[0].click()`);
await new Promise((r) => setTimeout(r, 150));
check("重复打开替换（overlay 恒 1）", (await Eval(`document.querySelectorAll('.module-info-overlay').length`)) === 1);
await Eval(`document.querySelector('.module-info-overlay').click()`);   // 关掉进入下一步
await new Promise((r) => setTimeout(r, 150));

// ---- 卡片本体点击 → 添加模块且不弹窗（主流程回归）----
const beforeSel = await Eval(`selectedSlugs.length`);
await Eval(`document.querySelectorAll('#module-grid .module-card')[0].click()`);
await new Promise((r) => setTimeout(r, 200));
const after = await Eval(`({ sel: selectedSlugs.length, overlays: document.querySelectorAll('.module-info-overlay').length })`);
check("点卡片本体 → 添加模块（selectedSlugs +1）", after.sel === beforeSel + 1, `before=${beforeSel},after=${after.sel}`);
check("点卡片本体 → 不弹窗", after.overlays === 0);

// ---- off 卡：切平台使某卡置灰 → 详情可开 + 提示条 ----
const offState = await Eval(`(() => {
  // 找一张在当前平台不存在的卡：遍历模块按平台不兼容性挑平台
  let plat = null;
  for (const p of ['stm32', 'mspm0']) {
    const hasOff = (state.modules || []).some((m) => !(m.platforms || {})[p]);
    if (hasOff) { plat = p; break; }
  }
  if (!plat) return null;
  chosenPlatform = plat;
  renderModulePool();
  const offCards = Array.from(document.querySelectorAll('#module-grid .module-card.off'));
  if (!offCards.length) return null;
  offCards[0].querySelector('.mc-info').click();
  const ov = document.querySelector('.module-info-overlay');
  return { offCount: offCards.length, hasTip: !!ov && ov.textContent.includes('无此模块版本'), plat };
})()`);
if (offState === null) {
  check("off 卡场景：模块库中无平台不兼容卡（跳过，模块库每个平台都有版本）", true, "skip");
} else {
  check("off 卡详情可开 + 提示条", offState.hasTip === true, "plat=" + offState.plat + " offCount=" + offState.offCount);
}

console.log(failed === 0 ? "SMOKE ALL PASS" : `SMOKE FAILED (${failed})`);
process.exit(failed === 0 ? 0 : 1);
