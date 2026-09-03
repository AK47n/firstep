// fx/ai-actions.js — 选中代码快捷动作纯函数（工单 code-editor-refine/07）
//
// 浮动按钮（现「问 AI」）升级为动作菜单：解释 / 加中文注释 / 重构 / 问 AI。
// 前三者 = 固定 prompt 模板 + 选区上下文（selectionContextText 单源，路径/
// 语言/行号/代码形态同引用卡片）；「问 AI」= 原行为（只插引用，用户补充后
// 发送）。注释/重构模板内置 <DIFF> 块格式约定（与 fx/ai-diff.js parseAiDiff
// 契约同构），引导 AI 输出可应用的结构化改动；解析失败自然回退纯文本展示
//（面板既有行为）。纯函数无副作用；模块约定见 fx/core.js 头部。
import { selectionContextText } from "./ai-diff.js";

// AI_ASK_ACTION_ID：问 AI 动作 id 单源（分发判定与清单共用——ui 层不再
// 硬编码字符串；模板表无此 id = 原行为只插引用）。
export const AI_ASK_ACTION_ID = "ask";

// AI_SELECTION_ACTIONS：动作清单（菜单顺序稳定；id 交 buildActionPrompt 与
// 胶水分发，label 中文展示）。
export const AI_SELECTION_ACTIONS = [
  { id: "explain", label: "解释" },
  { id: "comment", label: "加中文注释" },
  { id: "refactor", label: "重构" },
  { id: AI_ASK_ACTION_ID, label: "问 AI" },
];

// DIFF_FORMAT_HINT：<DIFF> 块契约提示（与 fx/ai-diff.js parseAiDiff 校验同构）
// ——注释/重构两个模板共用同一段（评审整改：重构模板单独调用时也看得到契约，
// 否则 AI 可能产出解析不了的 diff）。
const DIFF_FORMAT_HINT = "只输出修改后的完整代码片段，并把改动放进 <DIFF> 块"
  + "（{\"path\",\"hunks\":[{\"line\",\"title\",\"lines\":[{\"kind\":\"ctx\"|\"del\"|\"add\",\"text\"}]}]}，"
  + "path 用下面的相对路径）；不要输出多余解释。";

// AI_ACTION_TEMPLATES：三个固定模板（问 AI 无模板——原行为只插引用）。
// 模板措辞承担两类约束：解释 = 只解释不修改；注释/重构 = 只输出修改后的
// 完整片段 + <DIFF> 块契约（降低 diff 解析失败率）。
export const AI_ACTION_TEMPLATES = {
  explain: "请用中文解释以下代码的功能、输入输出与实现思路（只解释，不要修改代码）。",
  comment: "请为以下代码添加简洁的中文注释（关键变量 / 函数作用 / 边界分支）。"
    + DIFF_FORMAT_HINT,
  refactor: "请重构以下代码（提高可读性与可维护性，保持行为不变）。" + DIFF_FORMAT_HINT,
};

// buildActionPrompt(action, ctx) → 用户消息文本：模板（若有）+ 选区引用卡片。
// ctx = {path, lang, startLine, endLine, code}（selectionContextText 同型）；
// 未知/缺省动作 → 纯引用卡片（问 AI 语义）；ctx 缺省/空 code → 各字段归一
// 默认（path ""、行号 1、code ""，不落字面 undefined——评审整改），纯件不抛。
export function buildActionPrompt(action, ctx) {
  const c = ctx || {};
  const path = c.path == null ? "" : String(c.path);
  const start = Number.isFinite(Number(c.startLine)) ? Number(c.startLine) : 1;
  const end = Number.isFinite(Number(c.endLine)) ? Number(c.endLine) : 1;
  const ref = selectionContextText(path, c.lang, start, end,
    c.code == null ? "" : String(c.code));
  const t = AI_ACTION_TEMPLATES[action];
  if (!t) return ref;
  return t + "\n\n" + ref;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    AI_SELECTION_ACTIONS,
    AI_ACTION_TEMPLATES,
    AI_ASK_ACTION_ID,
    buildActionPrompt,
  });
}
