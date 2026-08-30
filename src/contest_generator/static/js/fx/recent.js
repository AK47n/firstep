// fx/recent.js — 最近生成列表纯函数（工单 frontend-es-modules/08，迁自
// index.html recent-jobs 域纯函数组：状态元数据 / 时间与平台标签 / 条目
// chip / 列表 HTML / 编译 done → 状态映射）。域内常量无；无共享件依赖
// （recentChipHTML 保留函数体内局部 esc：其 null 兜底语义与 core esc 不同，
// 照搬不合并）。模块约定见 fx/core.js 头部。
export function recentStatusMeta(status) {
  const meta = {
    generated: { label: "已生成", cls: "gen" },
    compiled_ok: { label: "编译成功", cls: "ok" },
    compiled_warn: { label: "有警告", cls: "warn" },
    compile_failed: { label: "编译失败", cls: "fail" },
  };
  return meta[status] || { label: "未知", cls: "gen" };
}

export function recentTimeLabel(ts) {
  const t = new Date(parseFloat(ts) * 1000);
  if (!Number.isFinite(t.getTime())) return "";
  const p = (n) => (n < 10 ? "0" + n : "" + n);
  return p(t.getMonth() + 1) + "-" + p(t.getDate()) + " "
    + p(t.getHours()) + ":" + p(t.getMinutes());
}

export function recentPlatformLabel(platform) {
  // 查表（前端展示层；后端 /api/generate 收的是平台别名 stm32/mspm0，
  // 兼容长 id 形态：历史记录或手工构造）
  const labels = {
    stm32: "STM32", stm32f103c8t6: "STM32",
    mspm0: "MSPM0", mspm0g3507: "MSPM0",
  };
  return labels[platform] || (platform || "");
}

export function recentChipHTML(entry) {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
  const meta = recentStatusMeta(entry.status);
  const dir = String(entry.output_dir || "");
  const base = dir.split(/[\\/]/).filter(Boolean).pop() || "（未知目录）";
  const mods = (entry.slugs || []).length;
  const cls = "recent-chip" + (meta.cls ? " st-" + meta.cls : "");
  return '<div class="' + cls + '" data-id="' + esc(entry.id)
    + '" data-dir="' + esc(dir) + '" title="点击复制路径：' + esc(dir) + '">'
    + '<span class="recent-status-dot" title="' + esc(meta.label) + '"></span>'
    + '<span class="recent-time">' + esc(recentTimeLabel(entry.ts)) + "</span>"
    + '<span class="recent-platform">' + esc(recentPlatformLabel(entry.platform)) + "</span>"
    + '<span class="recent-mods">' + mods + " 个模块</span>"
    + '<span class="recent-dir" title="' + esc(base) + '">' + esc(base) + "</span>"
    + '<button type="button" class="recent-code-open" data-code-dir="' + esc(dir)
    + '" title="在「代码」页只读查看该工程（文件树 + 行号 + 高亮 + 大纲 + 搜索）">查看代码</button>'
    + '<button type="button" class="recent-del" data-id="' + esc(entry.id)
    + '" title="删除这条记录" aria-label="删除">✕</button>'
    + "</div>";
}

export function recentListHTML(entries) {
  if (!entries || !entries.length) {
    return '<div class="recent-empty">还没有生成记录——完成一次生成后会出现在这里</div>';
  }
  return entries.map(recentChipHTML).join("");
}

// 编译 done 载荷 → 状态枚举（超时/失败/带错误 → failed；0 错 N 警 → warn；
// 否则 ok）。if (!done) 为防御默认：runCompileOnce 正常不会返回空（早 throw），
// 兜底语义 = 仅生成未编译。
export function recentStatusNow(done) {
  if (!done) return "generated";
  if (done.timed_out || !done.passed
      || ((done.summary || {}).errors || 0) > 0) return "compile_failed";
  if ((done.summary && done.summary.warnings || 0) > 0) return "compiled_warn";
  return "compiled_ok";
}

if (typeof window !== "undefined") {
  Object.assign(window, { recentStatusMeta, recentTimeLabel, recentPlatformLabel, recentChipHTML, recentListHTML, recentStatusNow });
}
