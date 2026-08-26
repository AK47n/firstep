// fx/overview.js — 生成页就绪总览纯函数（工单 frontend-es-modules/07，迁自
// index.html gen-overview 域纯函数组：顶部 chips / 摘要 / 卡片状态徽章 /
// 补齐计划 / 就绪判定 / 警告内容判定）。域内常量无（GEN_CRITICAL_STEPS /
// GEN_RECOMMENDED_STEPS 由胶水层 refreshGenOverview 使用，留内联传入）；
// 无共享件依赖。模块约定见 fx/core.js 头部。
export function genOverviewChipsHTML(titles, doneSet, current) {
  const done = doneSet || [];
  return titles.map((t) => {
    const isDone = done.indexOf(t.n) !== -1;
    const title = String(t.title || "");
    const cls = "ov-chip" + (isDone ? " done" : "") + (current === t.n ? " current" : "");
    return '<button type="button" class="' + cls + '" data-step="' + t.n
      + '" title="' + title.replace(/"/g, "&quot;") + '"><span class="ov-dot">'
      + (isDone ? "✓" : t.n) + '</span><span class="ov-label">'
      + title.replace(/"/g, "&quot;") + "</span></button>";
  }).join("");
}

export function genOverviewSummaryHTML(doneSet, titles, critical, recommended, navHint) {
  const done = doneSet || [];
  const byN = {};
  for (const t of titles) byN[t.n] = t.title;
  const total = titles.length;
  const doneCount = titles.filter((t) => done.indexOf(t.n) !== -1).length;
  const missing = (critical || []).filter((n) => done.indexOf(n) === -1 && byN[n]);
  const advised = (recommended || []).filter((n) => done.indexOf(n) === -1 && byN[n]);
  const parts = ['<span class="ov-ready">已就绪 ' + doneCount + "/" + total + "</span>"];
  if (missing.length) {
    parts.push('<span class="ov-missing">还差：<b>'
      + missing.map((n) => byN[n]).join("、") + "</b>" + (navHint || "") + "</span>");
  } else {
    parts.push('<span class="ov-next">关键步骤齐了，可以点「生成工程」</span>');
  }
  if (advised.length) {
    parts.push('<span class="ov-missing">建议顺带完成：'
      + advised.map((n) => byN[n]).join("、") + "</span>");
  }
  return parts.join('<span class="ov-sep">·</span>');
}

// 一键补齐计划（工单 gen-overview-act/01）：关键路径待办序列；
// 9（生成）非缺失项而是行动——但其「输出目录」前置（手动模式为空）列入
// 补齐（已确认扩规；doneSet 不含 9，须以 outputDirMissing 显式传入）。
// action 语义：focus = 滚到并聚焦输入、spotlight = 滚到并高亮（平台不
// 自动选）、adopt = 有推荐且清单为空时自动采用（半自动——无推荐只高亮，
// 不替用户做主）
export function overviewFillPlan(doneSet, canAdopt, outputDirMissing) {
  const done = doneSet || [];
  const plan = [];
  if (done.indexOf(1) === -1) plan.push({ n: 1, action: "focus" });
  if (done.indexOf(3) === -1) plan.push({ n: 3, action: "spotlight" });
  if (done.indexOf(6) === -1) {
    plan.push({ n: 6, action: canAdopt ? "adopt" : "spotlight" });
  }
  if (outputDirMissing) plan.push({ n: 9, action: "focus-dir" });
  return plan;
}

// 就绪判定（工单 gen-overview-act/01）：直接复用 generateReadinessChecks
// （与 btn-generate 前置校验同源）——总览条「生成」按钮与「点了生成被拦」
// 永不吵架
export function overviewReadyToGenerate(checks) {
  return (checks || []).every((c) => c.ok);
}

export function cardStepStatusHTML(done, warn, current) {
  const cls = done ? "done" : (warn ? "warn" : (current ? "current" : ""));
  if (!cls) return "";
  const text = done ? "✓ 已就绪" : (warn ? "⚠ 有警告" : "● 当前");
  return '<span class="card-step-status ' + cls + '">' + text + "</span>";
}

// 警告内容判定：el 内有非 .ok 的子元素才算有警告（第 6 步「该平台均可直接用」
// 是绿色 ok 盒，不算警告——工单 gen-overview/01 细节）
export function hasWarnContent(el) {
  if (!el) return false;
  const kids = el.children || [];
  return Array.from(kids).some((c) => !(c.classList && c.classList.contains("ok")));
}

if (typeof window !== "undefined") {
  Object.assign(window, { genOverviewChipsHTML, genOverviewSummaryHTML, overviewFillPlan, overviewReadyToGenerate, cardStepStatusHTML, hasWarnContent });
}
