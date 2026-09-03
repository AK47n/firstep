// fx/undo-stack.js — 模型级快照撤销栈纯件（工单 editor-textarea-viewport/03）
//
// 视口化后 textarea 只装窗口文本，浏览器原生撤销栈只认「textarea=全量文本」
// 的旧世界（窗口内撤销必错乱、跨窗口无意义）——03 明确放弃原生栈，快照栈
// 全域接管。本模块是撤销栈的「状态机」，与 DOM 无关：
//   - 快照 = { value, selStart, selEnd }（**模型全文** + 模型选区偏移）——
//     与窗口文本无关，跨窗口/折叠态语义由「模型为唯一事实源」保证；
//   - 栈语义 = 编辑前快照：每次真实内容变更前 push 当前模型状态；
//     undo 弹出最近一次编辑前状态并把当前状态推入 redo；redo 反向；
//   - 上限 UNDO_LIMIT（200，压入超限丢最旧——与工单 code-page-vscode-overhaul/04
//     既有先例同值）；新编辑清空 redo（不串历史）。
// 模块约定见 fx/core.js 头部。UI 侧只负责：捕获快照（captureModelSnapshot）、
// 恢复快照（rebaseModelContent）——状态机本身零 DOM。
export const UNDO_LIMIT = 200;

// undoPush(undoStack, redoStack, snap)：编辑前快照入栈——返回 {undo, redo}
// （新数组，不就地改入参——纯件纪律）；超限丢最旧；redo 清空；snap 非法
// （null/undefined）→ 原栈原样返回（调用方先判空亦可，纯件不抛）。
export function undoPush(undoStack, redoStack, snap) {
  if (!snap) return { undo: undoStack, redo: redoStack };
  const undo = undoStack.concat([snap]);
  if (undo.length > UNDO_LIMIT) undo.splice(0, undo.length - UNDO_LIMIT);
  return { undo, redo: [] };
}

// undoStep(undoStack, redoStack, current)：撤销一步——弹出最近编辑前快照，
// 并把当前状态（current）推入 redo 侧。返回 {snap, undo, redo}；空栈 →
// null（调用方提示「无可撤销」，不静默改状态）。
export function undoStep(undoStack, redoStack, current) {
  if (!undoStack.length) return null;
  const snap = undoStack[undoStack.length - 1];
  return {
    snap,
    undo: undoStack.slice(0, -1),
    redo: redoStack.concat([current]),
  };
}

// redoStep(undoStack, redoStack, current)：重做一步——弹出最近 redo 快照，
// 当前状态推回 undo 侧。返回 {snap, undo, redo}；空栈 → null。redo 栈条目
// 以「撤销时压入的顺序」倒序弹回，因此重做序列与撤销逆序一致。
export function redoStep(undoStack, redoStack, current) {
  if (!redoStack.length) return null;
  const snap = redoStack[redoStack.length - 1];
  return {
    snap,
    undo: undoStack.concat([current]),
    redo: redoStack.slice(0, -1),
  };
}

if (typeof window !== "undefined") {
  Object.assign(window, { undoPush, undoStep, redoStep, UNDO_LIMIT });
}
