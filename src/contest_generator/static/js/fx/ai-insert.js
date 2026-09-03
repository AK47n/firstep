// fx/ai-insert.js — AI 代码块提取 + 插入/替换位置纯函数（工单 code-editor-refine/08）
//
// 「插入到光标/选区」配套：aiFirstCodeBlock 提取 assistant 消息首个 ```fence
// 块（多块只取第一块——胶水层提示）；insertAtPosition 计算新内容与光标位
// （纯字符串运算，无 DOM——编辑器写缓冲经 codeeditor 的 applyEdit/rebase
// 路径，撤销/脏点/折叠映射全复用）。纯函数无副作用；模块约定见 fx/core.js
// 头部。

// aiFirstCodeBlock(text)：消息中首个 ```代码围栏``` → {code}（已 trim +
// CRLF 归一）｜null（无 fence / 空块 / 非字符串）。
export function aiFirstCodeBlock(text) {
  if (typeof text !== "string") return null;
  const m = /```([^\n`]*)\r?\n([\s\S]*?)```/.exec(text);
  if (!m) return null;
  const code = m[2].replace(/\r\n/g, "\n").trim();
  if (!code) return null;
  return { code };
}

// aiCodeFenceCount(text)：```fence 标记数（每对 = 2；多块判定 = 计数 > 2）——
// 块数判定归纯件（胶水层不重推正则，工单 08 评审整改）。
export function aiCodeFenceCount(text) {
  if (typeof text !== "string") return 0;
  return (text.match(/```/g) || []).length;
}

// insertAtPosition(content, text, {start, end}) → {value, selStart, selEnd}：
// 把 text 插入（无选区 start=end）或替换（有选区）；边界钳制（0..content 长度，
// end 不小于 start、反向选区退化为在 start 处插入）；光标 = 插入位后
// （selStart=selEnd）。纯字符串运算，空 text = 原内容 + 光标不动。
export function insertAtPosition(content, text, range) {
  const src = String(content == null ? "" : content);
  const ins = String(text == null ? "" : text);
  const r = range || {};
  const len = src.length;
  const s = Math.max(0, Math.min(len, Number(r.start) || 0));
  const endRaw = Number(r.end);
  const e = Math.max(s, Math.min(len, Number.isFinite(endRaw) ? endRaw : s));
  const value = src.slice(0, s) + ins + src.slice(e);
  const caret = s + ins.length;
  return { value, selStart: caret, selEnd: caret };
}

if (typeof window !== "undefined") {
  Object.assign(window, { aiFirstCodeBlock, aiCodeFenceCount, insertAtPosition });
}
