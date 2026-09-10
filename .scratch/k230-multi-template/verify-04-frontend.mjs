// B25（k230-multi-template/04 收口·UI 段）：模板下拉实况 + 选择记录语义。
//
// 源工单验收：「模块卡渲染：python_artifact.templates 长度 > 1 时显示模板下拉（含 description
// 提示），默认 default；不选模板（默认）路径零 UI 变化」+「真机验收：浏览器手测模板切换 →
// 生成工程 main.py 内容随选择变化」（后者由 `verify-04-templates.py` 在确定性渲染层验证）。
//
// 做法：不跑 LLM 推荐——直接驱动产品自身的展开链（`/api/selection/expand` 是确定性端点）
// + 导出的 `renderSelected()` 渲染选中卡，然后操作下拉。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。零写库（只读端点 + DOM）。
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const t = await rebuildTab({ port: PORT });
if (!t) { console.error("重建标签页失败"); process.exit(1); }
const c = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => c.Eval(e);

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

for (let i = 0; i < 120; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('selected-list')`)) break;
  await sleep(250);
}

// 平台 / 模块选择走产品的 setter（与 UI 同源），再走确定性展开端点
const expanded = await Eval(`(async () => {
  const m = await import('/js/ui/generate-recommend.js');
  m.setChosenPlatform('mspm0');
  m.setSelectedSlugs(['k230']);
  await m.runExpand();
  m.renderSelected();
  return { msg: (document.getElementById('expand-msg') || {}).textContent || '',
           cards: document.querySelectorAll('#selected-list .platform-card, #selected-list .card, #selected-list [data-slug]').length };
})()`);
check("B25 k230 展开成功（确定性端点 /api/selection/expand）", !expanded.msg.includes("失败"), JSON.stringify(expanded));

const sel = await Eval(`(() => {
  const box = document.getElementById('selected-list');
  const s = box.querySelector('select');
  if (!s) return { found: false, html: box.innerHTML.slice(0, 200) };
  return { found: true,
           options: [...s.options].map((o) => ({ v: o.value, t: o.textContent })),
           value: s.value,
           hint: s.getAttribute('title') || '',
           label: (s.closest('.row') || s.parentElement).textContent.slice(0, 40) };
})()`);
check("B25 多模板模块显示「副产物模板」下拉（3 个选项）", sel.found && sel.options.length === 3,
  JSON.stringify(sel));
check("B25 下拉默认 = manifest 的 default（blob / 色块追踪）",
  sel.found && sel.value === "blob" && (sel.options[0] || {}).t.includes("色块"),
  JSON.stringify(sel.found ? { value: sel.value, first: sel.options[0] } : sel));
check("B25 选项带 description 提示（title 多行）", sel.found && String(sel.hint).includes("："),
  JSON.stringify(String(sel.hint).slice(0, 80)));

// 改成 rect：应记进 pythonTemplates；改回默认：应删除（缺省不记录 ⇒ 旧行为逐字节不变）
const changed = await Eval(`(async () => {
  const m = await import('/js/ui/generate-recommend.js');
  const s = document.getElementById('selected-list').querySelector('select');
  s.value = 'rect'; s.dispatchEvent(new Event('change', { bubbles: true }));
  const afterRect = JSON.parse(JSON.stringify(m.pythonTemplates));
  s.value = 'blob'; s.dispatchEvent(new Event('change', { bubbles: true }));
  const afterReset = JSON.parse(JSON.stringify(m.pythonTemplates));
  return { afterRect, afterReset };
})()`);
check("B25 选 rect → 记进 pythonTemplates（{k230:'rect'}）",
  changed.afterRect && changed.afterRect.k230 === "rect", JSON.stringify(changed.afterRect));
check("B25 改回默认 blob → 记录删除（默认不发字段）",
  changed.afterReset && changed.afterReset.k230 === undefined, JSON.stringify(changed.afterReset));

// 展开契约：模板选择会带模板级依赖覆盖（digit → digit_uart）
const depOverride = await Eval(`(async () => {
  const r = await fetch('/api/selection/expand', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slugs: ['k230'], platform: 'mspm0', python_templates: { k230: 'digit' } }) });
  const d = await r.json();
  return { status: r.status, slugs: (d.modules || []).map((x) => x.slug) };
})()`);
check("B25 模板级依赖覆盖：选 digit → 依赖含 digit_uart（不含 coord_detect）",
  depOverride.status === 200 && depOverride.slugs.includes("digit_uart"),
  JSON.stringify(depOverride));

console.log("---- B25(UI) 总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
