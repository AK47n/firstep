// fx/draft.js — 步骤导航 / 草稿 / 步骤状态纯函数（工单 frontend-es-modules/07，
// 迁自 index.html 生成页步骤域纯函数组：步骤导航标题/条目/当前步、草稿
// 状态/存取/恢复元数据、步骤 7 完成判定、进度条、步骤 4 完成判定）。
// 域内常量无（DRAFT_KEY / STEP_TOTAL / STEP_NAV_CARD_SELECTOR 由胶水层使用，
// 留内联传入/传参）；无共享件依赖。syncStep4 原引用主体脚本模块级状态
// （selectedReferenceIds / autoReferenceIds）并调 markStepDone / markStepUndone，
// 迁入后显式参数传递（行为零变化，调用点同步传参）。
// 模块约定见 fx/core.js 头部。

// ---------------------------------------------------------------------------
// 生成页步骤导航（工单 ui-polish/02）：左侧圆点随滚动高亮，完成变绿 ✓
// ---------------------------------------------------------------------------
export function stepNavTitles(cards) {
  return Array.from(cards).map((c) => {
    const no = c.querySelector(".step-no");
    const h2 = c.querySelector("h2");
    return {
      n: no ? parseInt(no.textContent, 10) : NaN,
      title: h2 ? h2.textContent.replace(/^\d+/, "").trim() : "",
    };
  });
}

export function stepNavItemsHTML(titles) {
  return titles.map((t) => {
    const full = String(t.title || "");
    const label = full.length > 12 ? full.slice(0, 12) + "…" : full;
    return '<button type="button" class="step-dot" data-step="' + t.n + '" title="'
      + full.replace(/"/g, "&quot;") + '"><span class="dot">' + t.n + '</span><span class="label">'
      + label.replace(/"/g, "&quot;") + "</span></button>";
  }).join("");
}

export function stepNavCurrent(entries, threshold) {
  let cur = entries.length ? entries[0].n : NaN;
  for (const e of entries) if (e.top <= threshold) cur = e.n;
  return cur;
}

// ---------------------------------------------------------------------------
// 生成页草稿自动记忆（工单 ui-polish-3/01）：localStorage 防误刷新丢失；
// 只存表单态，恢复不触发任何后端请求
// ---------------------------------------------------------------------------
export function draftState(problem, topicId, platform, slugs, mainC, qa) {
  return {
    problem: String(problem || ""),
    topicId: String(topicId || ""),
    platform: String(platform || ""),
    slugs: Array.isArray(slugs) ? slugs.filter((s) => typeof s === "string") : [],
    mainC: String(mainC || ""),
    qa: String(qa || ""),
  };
}

export function draftSave(storage, state) {
  try { storage.setItem("firstep.draft.v1", JSON.stringify(state)); return true; }
  catch (e) { return false; }
}

export function draftLoad(storage) {
  let raw = null;
  try { raw = storage.getItem("firstep.draft.v1"); } catch (e) { return null; }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  }
  catch (e) { return null; }   // 损坏 JSON / 被改坏 = 静默降级为新会话
}

export function draftRestoreMeta(json) {
  if (!json || typeof json !== "object" || Array.isArray(json)) return null;
  const out = {};
  for (const f of ["problem", "topicId", "platform", "slugs", "mainC", "qa"]) {
    const v = json[f];
    if (f === "slugs") out[f] = Array.isArray(v) ? v.filter((s) => typeof s === "string") : [];
    else out[f] = typeof v === "string" ? v : "";
  }
  return out;
}

// ---------------------------------------------------------------------------
// 顶部流程进度条（工单 ui-polish-3/02）：完成步骤集合 → 细进度条 + 计数；
// 与 markStepDone / markStepUndone 联动（STEP_TOTAL 与步骤总数保持同步）
// ---------------------------------------------------------------------------
export function stepProgress(doneCount, total) {
  const t = Number(total);
  const n = Number(doneCount);
  const safeTotal = Number.isFinite(t) && t > 0 ? t : 12;
  const safeDone = Number.isFinite(n) ? Math.max(0, Math.min(n, safeTotal)) : 0;
  return { pct: Math.round((safeDone / safeTotal) * 100), text: "已完成 " + safeDone + "/" + safeTotal };
}

// ---------------------------------------------------------------------------
// 步骤 7 完成判定（工单 step7-done/01 修正：默认布线 / 无需配置时从未显示完成）。
// 完成 = 平台已选且已展开模块，且满足其一：① 无引脚角色（无需配置）
// ② 有角色已显式绑定 ③ 多实例已配引脚 ④ 已按默认布线生成成功（隐式接受默认）
// ---------------------------------------------------------------------------
export function step7DoneState(state) {
  if (!state.chosenPlatform || !state.expandedCount) return false;
  if (!state.roles.length || state.roleBound || state.instBound || state.generated) return true;
  return false;
}

// 步骤 7 布线模式（工单 ux-polish-02/01：区分「已配置引脚」与「按默认布线生
// 成（隐式接受默认）」——后者完成但未手动配置，不能显示绿「✓ 已就绪」）。
// 返回 'configured'（无角色需配 / 已显式绑定 / 多实例已配引脚）/ 'default'
// （有角色未绑定但已按默认布线生成）/ 'none'（未完成 / 信息不足）。
// 判据与 step7DoneState 同源（同一组输入），只做完成后的模式细分。
export function step7WireMode(state) {
  if (!state.chosenPlatform || !state.expandedCount) return "none";
  if (!state.roles.length || state.roleBound || state.instBound) return "configured";
  if (state.generated) return "default";
  return "none";
}

// ---------------------------------------------------------------------------
// 步骤 4（参考资料）完成判定：手动勾选或自动关联任一有值即视为完成（可选
// 步骤，全空 = 未处理，不取消其它步骤）；勾选变更、AI 推荐自动关联后调用
// （selectedReferenceIds / autoReferenceIds 与 markStepDone / markStepUndone
// 由调用方显式传入——主体脚本模块级状态 + DOM 胶水，迁入后参数化）。
// ---------------------------------------------------------------------------
export function syncStep4(selectedReferenceIds, autoReferenceIds, markStepDone, markStepUndone) {
  if (selectedReferenceIds.length || autoReferenceIds.length) markStepDone(4);
  else markStepUndone(4);
}

if (typeof window !== "undefined") {
  Object.assign(window, { stepNavTitles, stepNavItemsHTML, stepNavCurrent, draftState, draftSave, draftLoad, draftRestoreMeta, stepProgress, step7DoneState, step7WireMode, syncStep4 });
}
