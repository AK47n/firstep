// fx/readiness.js — 生成就绪检查纯函数（工单 frontend-es-modules/08，迁自
// index.html a3-readiness-check 域纯函数组：硬判据 / 软条件 / 检查单行渲染 /
// 行列表渲染）。域内常量无；无共享件依赖（readinessRowHTML 保留函数体内
// 局部 esc：仅替换 &<>"（无 ' 且无 null 兜底），与 core esc 语义不同，
// 照搬不合并）。模块约定见 fx/core.js 头部。
export function generateReadinessChecks(state) {
  // 顺序 = btn-generate 原提示顺序（平台 → 模块 → 题面 → 目录）；reason 逐字复用
  return [
    { step: 3, title: "目标平台", reason: "请先选择目标平台",
      ok: !!state.chosenPlatform, autoFixable: false },
    { step: 6, title: "模块清单与平台警告", reason: "请先选择模块",
      ok: (state.selectedSlugs || []).length > 0, autoFixable: true },
    { step: 1, title: "赛题原文", reason: "请先填写赛题原文",
      ok: !state.desktopOutput || !!state.problem, autoFixable: false },
    { step: 9, title: "输出目录并生成", reason: "请填写输出目录",
      ok: state.desktopOutput || !!state.outputDir, autoFixable: false },
  ];
}

export function readinessSoftChecks(state) {
  // 软条件：不阻断生成，⚠ 展示。5 仅在模块非空时出现（空模块由硬检查 6 覆盖）
  const out = [];
  if ((state.selectedSlugs || []).length && !state.recommended) {
    out.push({ step: 5, title: "AI 推荐模块", reason: "未跑 AI 推荐（可选项）",
      ok: false, soft: true });
  }
  if (!state.hasMainC) {
    out.push({ step: 8, title: "main.c 骨架", reason: "骨架未生成（可选项，生成时可留空）",
      ok: false, soft: true });
  }
  return out;
}

/** 检查单顶部总结（工单 ux-walkthrough-02/17）：硬判据全就绪 → 绿色
 * 「点生成工程即可」总结；否则中性「还有未就绪项」引导。纯文本 HTML。 */
export function readinessSummaryHTML(hardOk) {
  return hardOk
    ? '<div class="rc-summary ok">✅ 硬判据全部就绪——直接点「生成工程」即可</div>'
    : '<div class="rc-summary">还有未就绪项：按每行「去第 N 步」补齐后即可生成</div>';
}

export function readinessRowHTML(check, opts) {
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const cls = check.ok ? "ok" : (check.soft ? "soft" : "bad");
  const ico = check.ok ? "✓" : (check.soft ? "⚠" : "✗");
  const reason = check.ok ? "已就绪" : check.reason;
  let actions = "";
  if (!check.ok) {
    actions = '<span class="rc-actions"><button type="button" class="rc-go" data-step="'
      + check.step + '">去第 ' + check.step + ' 步</button>';
    // 可自动补项：仅模块清单（❌ 且开启一键）——题面为空时 renderReadinessPanel
    // 不传 recommendEnabled，跳到第 1 步先填题面
    if (check.autoFixable && opts && opts.recommendEnabled) {
      actions += '<button type="button" class="rc-recommend" data-action="recommend"'
        + ' data-step="' + check.step + '">一键跑推荐</button>';
    }
    actions += "</span>";
  }
  return '<div class="rc-row ' + cls + '" data-step="' + check.step + '">'
    + '<span class="rc-ico">' + ico + '</span>'
    + '<span class="rc-title">' + esc(check.title) + '</span>'
    + '<span class="rc-reason">' + esc(reason) + '</span>'
    + actions + "</div>";
}

export function readinessRowsHTML(checks, opts) {
  return checks.map((c) => readinessRowHTML(c, opts)).join("");
}

/**
 * 输出目录预警行（工单 beginner-gap-closure/06）：/api/generate/preview-dir
 * 载荷（{dir, verdict}）→ 非阻塞 warn 行（soft，⚠ 不阻断生成）。适用
 * verdict = exists（桌面已有同名完整工程——生成时备份 .bak 再覆盖）/
 * occupied（手动目录已存在且非空——生成会被拒绝）才返回行对象，否则 null
 * （调用方不渲染；needs_title = 预览拿不到目录名，静默）。软条件判据
 * 与 readinessSoftChecks 同形（soft: true → ⚠ 展示，rowHTML 复用）。
 */
export function outputDirWarnRow(result) {
  if (!result || !result.dir) return null;
  if (result.verdict === "exists") {
    return {
      step: 9,
      title: "输出目录",
      reason: "桌面已有同名工程（生成时会把旧工程备份为 .bak 再覆盖；也可以先去删除旧工程）",
      ok: false,
      soft: true,
    };
  }
  if (result.verdict === "occupied") {
    return {
      step: 9,
      title: "输出目录",
      reason: "目录已存在且非空——生成会被拒绝；建议先清空目录或换个位置",
      ok: false,
      soft: true,
    };
  }
  return null;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    generateReadinessChecks, readinessSoftChecks, readinessRowHTML,
    readinessRowsHTML, readinessSummaryHTML, outputDirWarnRow,
  });
}
