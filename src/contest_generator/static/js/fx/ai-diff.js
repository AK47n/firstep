// fx/ai-diff.js — AI 回复结构化 diff 契约解析 + 选区上下文拼装（工单 code-ide-ai/01）
//
// 契约（spec「一期 C2」定稿）：AI 回复中改动以 <DIFF>{json}</DIFF> 块输出，
// 与既有 main_diff 同构：{path, stats:{additions,deletions,hunks},
// hunks:[{line,title,lines:[{kind:"ctx"|"del"|"add", text}]}]}。
// parseAiDiff 严格校验——任何不符 → null（前端不猜测、不半接受）；
// selectionContextText 拼装「选中代码问 AI」的引用消息（文件/行区间/fence）。
// 纯函数无副作用。
//
// 安全口径：path 拒绝绝对路径/../（相对当前代码目录；后端 apply-diff 二次校验）。

/** parseAiDiff(text) → {path, stats, hunks} | null
 * 提取首个 <DIFF>...</DIFF> 块（块内允许 ```json 围栏），JSON.parse +
 * 结构校验（stats 非负整数、hunk.line ≥1 整数、kind 枚举、text 字符串、
 * path 非空安全相对路径）；非法 → null。 */
export function parseAiDiff(text) {
  if (typeof text !== "string" || !text) return null;
  const m = /<DIFF>([\s\S]*?)<\/DIFF>/i.exec(text);
  if (!m) return null;
  let raw = m[1].trim();
  // 剥 ```json / ``` 围栏（AI 格式漂移容忍）
  const fence = /^```(?:json)?\s*([\s\S]*?)\s*```$/i.exec(raw);
  if (fence) raw = fence[1].trim();
  // 剥注释包裹（AI 可能把 JSON 放进 /** */ 或 // 注释——宽容剥离行注释与
  // 块注释仅当 JSON.parse 失败后重试一次）
  let obj;
  try { obj = JSON.parse(raw); } catch {
    const cleaned = raw.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")
      .trim();
    try { obj = JSON.parse(cleaned); } catch { return null; }
  }
  if (!obj || typeof obj !== "object") return null;
  if (typeof obj.path !== "string" || !isSafeRelPath(obj.path)) return null;
  if (!Array.isArray(obj.hunks)) return null;
  for (const h of obj.hunks) {
    if (!h || typeof h !== "object" || !isPosInt(h.line)) return null;
    if (h.title != null && typeof h.title !== "string") return null;
    if (!Array.isArray(h.lines) || !h.lines.length) return null;
    if (!h.lines.some((ln) => ln.kind !== "add")) return null;   // 应用器需匹配锚点（ctx/del）
    for (const ln of h.lines) {
      if (!ln || typeof ln !== "object"
          || (ln.kind !== "ctx" && ln.kind !== "del" && ln.kind !== "add")
          || typeof ln.text !== "string") return null;
    }
  }
  // stats 派生自 hunks（additions/deletions/hunks 计数自洽——AI 提供的
  // stats 字段数值不校验不信任，LLM 计数常不准，展示以派生值为准）。
  let add = 0, del = 0;
  for (const h of obj.hunks) {
    for (const ln of h.lines) {
      if (ln.kind === "add") add += 1;
      else if (ln.kind === "del") del += 1;
    }
  }
  return {
    path: obj.path,
    stats: { additions: add, deletions: del, hunks: obj.hunks.length },
    hunks: obj.hunks,
  };
}

/** selectionContextText(path, lang, startLine, endLine, code) → 用户消息文本
 * 引用卡片格式：`【代码引用 · path · 第 a-b 行】\n```lang\n<code>\n````
 * lang 空串 → "c" 兜底（电赛工程）。 */
export function selectionContextText(path, lang, startLine, endLine, code) {
  const l = (typeof lang === "string" && lang) ? lang : "c";
  return "【代码引用 · " + path + " · 第 " + startLine + "-" + endLine + " 行】\n"
    + "```" + l + "\n" + (typeof code === "string" ? code : "") + "\n```";
}

// —— 内部校验（不导出，纯件私有）——
function isPosInt(v) { return Number.isInteger(v) && v >= 1; }
// isSafeRelPath(p)：路径预筛——**复刻后端 is_unsafe_path 四规则**
// （entry_store.py:145-152 单源：正斜杠开头 / 含冒号 / 含反斜杠 /
// split 后有空段或 .. 段；后端 _resolve_in_root + resolve-in-root 为权威
// 兜底，前端仅预筛）。相对路径语义（无开头 ./ 也合法——与树路径一致）。
function isSafeRelPath(p) {
  if (!p || p.length > 512) return false;
  if (p.startsWith("/") || p.includes(":") || p.includes("\\")) return false;
  if (p.split("/").some((part) => part === "" || part === "..")) return false;
  return true;
}

if (typeof window !== "undefined") {
  Object.assign(window, { parseAiDiff, selectionContextText });
}
