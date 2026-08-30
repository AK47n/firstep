// fx/danger.js — 危险操作确认文案纯函数（工单 ux-walkthrough-02/01）：
// 覆盖式重生成 / 平台切换清空下游 / 全部还原默认 三处确认弹窗的 message
// 单源。与 ui/* 接线解耦（confirmModal 的 message 走 esc，故只产纯文本），
// 测试直接驱动；模块约定见 fx/core.js 头部。
//
// 三处共同语义：破坏性操作（覆盖重建 / 清空配置）必须先明示影响再执行，
// 文案落在此处便于 tests/js 锚定防漂移。

/** 覆盖式重生成（修订「确认并执行」）确认文案。
 * diff = 分析结果的模块集确定性集合差 {added, removed, unchanged}（可为空）；
 * slugCount = 用户确认的模块数兜底（diff 为空时展示）。
 * 返回单段纯文本（换行/顿号分隔，无 HTML）。 */
export function reviseApplyConfirmMessage(diff, slugCount) {
  const d = diff || {};
  const added = (d.added || []).length;
  const removed = (d.removed || []).length;
  const unchanged = (d.unchanged || []).length;
  const head = (added || removed || unchanged)
    ? `模块集变更：新增 ${added} · 移除 ${removed} · 不变 ${unchanged}`
    : `将按确认模块集（${slugCount || 0} 个模块）重写工程`;
  return head
    + "。执行后输出目录将被覆盖重建（旧工程先整树备份，可回滚）。确定继续？";
}

/** 平台切换确认文案。cfg 可选计数（moduleCount / pinCount / instanceCount），
 * 无计数时给通用描述（调用方拿不到计数也语义完整）。 */
export function platformSwitchConfirmMessage(cfg = {}) {
  const detail = [];
  if (cfg.moduleCount != null) detail.push(`已选模块 ${cfg.moduleCount} 个`);
  if (cfg.pinCount != null) detail.push(`引脚绑定 ${cfg.pinCount} 处`);
  if (cfg.instanceCount != null) detail.push(`实例配置 ${cfg.instanceCount} 组`);
  const suffix = detail.length ? `（${detail.join("、")}）` : "";
  return "切换平台将清空已选模块、引脚绑定与实例配置" + suffix
    + "，下游需重新选择并检查平台兼容性。确定继续？";
}

/** 「全部还原默认」确认文案。count = 当前已绑定角色数；0 时语义为“无绑定可还原”。 */
export function pinResetConfirmMessage(count) {
  const n = Number.isFinite(count) ? count : 0;
  if (!n) return "当前没有引脚绑定，无需还原。";
  return `将把全部 ${n} 处引脚绑定还原为默认（改动可重新配置），并清空当前高亮。确定继续？`;
}

/** 覆盖生成确认补语（工单 ux-walkthrough-02/03）：.bak 找回说明。
 * dirName = 同名工程目录名（可空 → 通用描述）；返回单段纯文本。 */
export function overwriteBakHint(dirName) {
  const bak = dirName ? "「" + dirName + ".bak」" : "同名 .bak 备份";
  const target = dirName ? "「" + dirName + "」" : "原名";
  return "如需找回旧工程，把桌面上" + bak + "改名回" + target + "（生成后也可在结果区一键恢复）。";
}

/** 删除想法草稿确认文案（工单 ux-walkthrough-02/15）：点名草稿前 20 字，
 * 并明示删除后可在提示里「撤销」恢复（toast 动作）。 */
export function draftDeleteMessage(text) {
  const s = String(text || "").trim();
  const brief = s.length > 20 ? s.slice(0, 20) + "…" : s;
  return "将删除「" + (brief || "未命名草稿") + "」这条想法草稿？删除后该条草稿不在列表；确认后可点「撤销」恢复。";
}

/** 删除最近生成记录确认文案（工单 ux-walkthrough-02/15）：点名输出目录，
 * 明示「只移除历史记录，磁盘工程不受影响」+ 撤销入口。快照缺失（entry 空）
 * 时不给「可撤销」承诺（评审整改：无快照则无从恢复）。 */
export function recentDeleteMessage(entry) {
  if (!entry || !entry.output_dir) {
    return "将删除这条最近生成记录？只会移除历史列表上的记录，磁盘上的工程不受影响。确认删除？";
  }
  const dir = String(entry.output_dir);
  return "将删除最近生成记录（" + dir + "）？只会移除历史列表上的记录，磁盘上的工程不受影响；确认后可点「撤销」恢复。";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    reviseApplyConfirmMessage, platformSwitchConfirmMessage, pinResetConfirmMessage,
    overwriteBakHint, draftDeleteMessage, recentDeleteMessage,
  });
}
