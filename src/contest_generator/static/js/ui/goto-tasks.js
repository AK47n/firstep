// ui/goto-tasks.js — 「去任务推进」跳转单源（工单 beginner-gap-closure/02）：
// 第 9 步生成结果区按钮与第 12 步交接卡按钮共用——滚动到第 11 步卡 +
// 激活「任务推进」页签（复用 ui/revise-tabs.js 的 switchReviseTab，不新写页签逻辑）。
// 上下文自动加载（工单 ux-polish-02/04）：主路径断点修复——只切页签会让任务
// 面板落入「尚未加载输出目录」空态；现在在「当前无已加载上下文」或「已加载
// 目录 ≠ 当前输出目录」时自动触发与「从当前会话加载」同一加载器（reviseLoad），
// 加载完成的既有事件链路自然激活任务推进页签；已加载同目录 = 跳过（不重置面板）。
import { $ } from "/js/app.js";
import { switchReviseTab } from "/js/ui/revise-tabs.js";
import { reviseLoad, reviseGetDir } from "/js/ui/generate-revise.js";

/** 当前生成结果目录（结果区文本优先，输出目录输入兜底——与修订页
 * 「从当前会话加载」同口径 reviseCurrentDir）。 */
function currentOutputDir() {
  return $("res-dir").textContent.trim() || $("output-dir").value.trim();
}

/** 去任务推进：滚动到第 11 步卡 + 激活「任务推进」页签（用户主动 → user:true）
 * + 必要时自动加载当前会话上下文（失败不阻塞页签切换，错误展示沿用修订页）。 */
export async function goTaskProgress() {
  const card = $("card-revise");
  if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
  switchReviseTab("tasks", { user: true });
  const dir = currentOutputDir();
  if (dir && reviseGetDir() !== dir) {
    try {
      await reviseLoad(dir);   // 内部错误展示；加载完成 → revise-context-loaded → 任务页徽章/清单就绪
    } catch (e) { /* reviseLoad 已处理（加载失败清目录 + 广播 step11-state-changed） */ }
  }
}
