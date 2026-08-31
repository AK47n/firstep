// fx/write-guard.js — 反向写盘保护纯件（工单 code-write-guard/01）
//
// 生成页写盘动作（AI 修复 / 修订 / 深化 / 任务 / 参数改值）发起前的提示判定
// 与文案：代码栏目录 = 生成上下文 且 有未保存（脏且非只读）文件 → 需要提示。
// 胶水（ui/code-write-guard.js）只做确认模态 + 保存全部编排。文案含动作名与
// 文件数，动态部分 esc（confirmModal message 按 HTML 渲染先例）。模块约定
// 见 fx/core.js 头部。
import { esc } from "./core.js";

// writeGuardNeeded(isContextDir, dirtyCount)：是否弹确认——仅当打开目录 =
// 生成上下文 且 脏标签数 > 0；其余（非上下文 / 无脏 / 空目录）一律 false
//（直通零打扰）。
export function writeGuardNeeded(isContextDir, dirtyCount) {
  return !!isContextDir && Number(dirtyCount) > 0;
}

// writeGuardTitle()：模态标题（固定）。
export function writeGuardTitle() {
  return "代码栏有未保存修改";
}

// WRITE_GUARD_ACTIONS：写盘动作名单源（评审整改——动作名原先散落 5 模块
// 裸字符串，改名需动 5 处；统一从此取）。冻结对象防意外改写。
export const WRITE_GUARD_ACTIONS = Object.freeze({
  fix: "一键编译修复",
  continueFix: "继续修复",
  revise: "执行修订",
  deepen: "深化",
  task: "做这一步",
  taskFeedback: "按反馈修复",
  params: "改值并编译",
});

// writeGuardMessage(actionLabel, dirtyCount)：模态正文——动作名 + 未保存文件数
// + 引导「保存全部并继续」；actionLabel 空 → 「该操作」兜底。
export function writeGuardMessage(actionLabel, dirtyCount) {
  const n = Number(dirtyCount) || 0;
  return "『" + esc(String(actionLabel || "该操作")) + "』将写入磁盘，代码栏有 "
    + n + " 个文件未保存——建议先保存全部，以免磁盘被覆盖后还需处理冲突。";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    writeGuardNeeded,
    writeGuardTitle,
    writeGuardMessage,
    WRITE_GUARD_ACTIONS,
  });
}
