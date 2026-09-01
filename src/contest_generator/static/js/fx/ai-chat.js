// fx/ai-chat.js —— IDE AI 对话面板消息流渲染（工单 code-ide-ai/03）。
// 纯函数无副作用：消息流 HTML（气泡）+ 引用卡片（details 可折叠）+ 空态
// 引导。形态对齐生成页全局商量的 .sugg-msg 气泡系列（fx/task.js
// globalChatMessageHTML 同构但未导出且带会话操作按钮，语义不同不合并——
// 评审记录）；chat = 后端 /api/tasks/idea/chat/* 落盘形状
// {messages:[{role,content,at}], note}；pendingText = 发送中未确认的用户
// 消息（乐观气泡，成功后被服务端 chat 替换——与全局商量同先例）。
import { esc } from "./core.js";

/** 消息流 HTML：messages 逐条 .sugg-msg 气泡 + 尾部 pending 气泡；
 * 全空（无历史且无 pending）→ 引导文案。文本一律转义（防注入）。 */
export function aiChatMessagesHTML(messages, pendingText) {
  const msgs = Array.isArray(messages) ? messages : [];
  const body = msgs.map(aiChatMessageHTML).join("");
  const pending = pendingText
    ? '<div class="sugg-msg user"><span class="sugg-msg-role">我</span>：'
      + userMessageHTML(String(pendingText)) + "</div>"
    : "";
  if (!body && !pending) {
    return '<div class="code-ai-chat-empty muted">还没有对话——这是引导：'
      + "选中代码后点「问 AI」，或直接输入问题（例如：这个引脚配置对不对？）。"
      + "</div>";
  }
  return '<div class="code-ai-chat-msgs">' + body + pending + "</div>";
}

/** quoteRefParts(text) → {path, startLine, endLine, lang, code, rest} | null
 * 识别「选中代码问 AI」引用消息：首行「【代码引用 · path · 第 a-b 行】」+
 * 紧跟 ```lang 代码围栏；rest = 围栏后的用户问题文本（可为空）。不识别的
 * 文本 → null（平铺渲染）。lang 空 → "c"（与 selectionContextText 兜底同）。 */
export function quoteRefParts(text) {
  if (typeof text !== "string") return null;
  const m = /^【代码引用 · (.+?) · 第 (\d+)-(\d+) 行】\s*(?:\r?\n)?```([^\n`]*)\r?\n([\s\S]*?)```\s*(?:\r?\n)?([\s\S]*)$/
    .exec(String(text).trim());
  if (!m) return null;
  return {
    path: m[1],
    startLine: Number(m[2]),
    endLine: Number(m[3]),
    lang: m[4] || "c",
    code: m[5].trim(),
    rest: m[6].trim(),
  };
}

/** 单条消息气泡（私有）：assistant → 纯文本（<DIFF> 结构化块剥离显示——
 * 原始 JSON 无阅读价值，正文挂「预览改动」按钮由 ui 层注入，见工单 04）；
 * user → 引用消息卡片化。 */
function aiChatMessageHTML(msg) {
  if (!msg || typeof msg.content !== "string") return "";
  const isAi = msg.role === "assistant";
  const body = String(msg.content);
  const at = msg.at ? ' <span class="muted">' + esc(String(msg.at)) + "</span>" : "";
  const inner = isAi ? esc(stripDiffBlock(body)) : userMessageHTML(body);
  return '<div class="sugg-msg ' + (isAi ? "ai" : "user") + '">'
    + '<span class="sugg-msg-role">' + (isAi ? "AI" : "我") + "</span>："
    + inner + at + "</div>";
}

// stripDiffBlock(text)：含 <DIFF>...</DIFF> 块（含 ```json 围栏变体）→ 剥离
// 为占位提示文本（解析/按钮逻辑不在纯件——ui 层 parseAiDiff 单源）；无块
// → 原样返回。
function stripDiffBlock(text) {
  if (!/<DIFF>[\s\S]*?<\/DIFF>/i.test(text)) return text;
  const shown = text.replace(/<DIFF>[\s\S]*?<\/DIFF>/gi, "").trim();
  return shown
    ? shown + "\n〘此处含 AI 建议的代码改动，点「预览改动」查看〙"
    : "〘AI 建议了一处代码改动，点「预览改动」查看〙";
}

/** user 消息内容：引用消息 → details 折叠卡片（summary = 路径与行区间，
 * pre 内代码片段）+ 围栏后问题文本；非引用 → 平铺文本。 */
function userMessageHTML(text) {
  const ref = quoteRefParts(text);
  if (!ref) return esc(text);
  return '<details class="code-ai-ref"><summary>代码引用 · ' + esc(ref.path)
    + " · 第 " + ref.startLine + "-" + ref.endLine + " 行</summary>"
    + '<pre class="code-ai-ref-code"><code>' + esc(ref.code) + "</code></pre></details>"
    + (ref.rest ? '<div class="code-ai-ref-rest">' + esc(ref.rest) + "</div>" : "");
}

if (typeof window !== "undefined") {
  Object.assign(window, { aiChatMessagesHTML, quoteRefParts });
}
