// fx/params-chat.js — 参数速调 AI 咨询对话（工单 params-chat-ai/02）纯函数。
//
// 对话区视觉复用全局商量（.sugg-discuss-* / .sugg-msg / .task-dialog-box），
// 本模块只产出 HTML：消息行（AI 消息中提及的已识别参数名包成可点击定位
// chip）、输入行、整区渲染。与 ui/params-chat.js（状态 + 委托 + 定位滚动）
// 分层照 params.js 先例。
import { esc } from "./core.js";

// 参数标识词形（C 标识符）：匹配完整词（前后非字母数字下划线），
// 防 "THRESHOLDX" 误配 "THRESHOLD"。
const PARAM_TOKEN_RE = /[A-Za-z_][A-Za-z0-9_]*/g;

/** AI 回复中的参数名 → 定位 chip（工单 params-chat-ai/02）。
 *
 * msg = {role, content, at}；paramNames = 已识别参数名字符串数组（空 = 不包
 * 任何 chip）。只对 AI 消息包提及（用户消息原样转义——用户的话不是 AI 推荐
 * 的参数，无定位语义）；文本逐段转义后拼接（先词切分再逐段 esc——避免在
 * 转义后的实体（&amp; 等）里误配单词，也保证 chip 内文本安全）。
 * chip = <button class="btn-param-ref" data-param-ref="<name>" type="button"
 * title="点击定位到参数卡">（data 属性值经 esc，属性上下文防注入）。
 */
export function paramsChatMessageHTML(msg, paramNames) {
  const isAi = msg && msg.role === "assistant";
  const raw = String((msg && msg.content) || "");
  const names = new Set(paramNames || []);
  const roleLabel = isAi ? "AI" : "我";
  let text;
  if (isAi && names.size) {
    let out = "";
    let last = 0;
    let match;
    PARAM_TOKEN_RE.lastIndex = 0;
    while ((match = PARAM_TOKEN_RE.exec(raw)) !== null) {
      out += esc(raw.slice(last, match.index));
      const token = match[0];
      out += names.has(token)
        ? '<button class="btn-param-ref" data-param-ref="' + esc(token) + '"'
          + ' type="button" title="点击定位到参数卡">' + esc(token) + "</button>"
        : esc(token);
      last = match.index + token.length;
    }
    text = out + esc(raw.slice(last));
  } else {
    text = esc(raw);
  }
  const at = msg && msg.at
    ? ' <span class="muted">' + esc(String(msg.at)) + "</span>"
    : "";
  return '<div class="sugg-msg ' + (isAi ? "ai" : "user") + '">'
    + '<span class="sugg-msg-role">' + roleLabel + "</span>：" + text + at
    + "</div>";
}

/** 输入行（send 语义共享：输入框 + 发送按钮；busy 禁用防并发）。
 * draft = 输入框未发送内容（重渲染不丢）；busy 时按钮文案「回应中…」。 */
export function paramsChatInputHTML(s) {
  const busy = !!(s && s.busy);
  return '<div class="sugg-discuss-row"><input id="params-chat-input"'
    + ' class="sugg-discuss-input" placeholder="描述现象问 AI——如：小车直行跑偏 / 循迹丢线 / PWM 抖动…"'
    + ' value="' + esc((s && s.draft) || "") + '">'
    + '<button class="btn-params-chat-send"' + (busy ? " disabled" : "") + ">"
    + (busy ? "回应中…" : "发送") + "</button></div>";
}

/** 参数速调咨询对话区（工单 params-chat-ai/02）。
 *
 * st = {open, busy, chat, pending, draft}——chat = 后端 {messages} 落盘真相；
 * pending = 发送中尚未确认的用户消息（乐观展示，成功后被 chat 替换）；
 * 未展开 = 空串。paramNames 喂给消息行做提及 chip（参数表刷新后由胶水层
 * 重渲染同步）。空历史 + 无 pending → 引导文案（说明咨询区用途）。 */
export function paramsChatHTML(st, paramNames) {
  const s = st || {};
  if (!s.open) return "";
  const messages = ((s.chat && s.chat.messages) || []);
  const lines = messages
    .map((message) => paramsChatMessageHTML(message, paramNames))
    .join("");
  const pending = s.pending
    ? '<div class="sugg-msg user"><span class="sugg-msg-role">我</span>：'
      + esc(String(s.pending)) + "</div>"
    : "";
  const inner = (lines || pending)
    ? '<div class="sugg-discuss-msgs">' + lines + pending + "</div>"
    : '<div class="sugg-msg muted">这是「该调哪个参数」的咨询区：描述现象'
      + "（如：小车直行跑偏 / 循迹丢线 / PWM 抖动），AI 结合当前已识别参数"
      + "清单推荐调整对象与方向；回复里的参数名可直接点击定位。</div>";
  return '<div class="task-dialog-box">' + inner
    + paramsChatInputHTML(s)
    + (s.busy
      ? '<div class="sugg-discuss-note">AI 回应中…（分钟级调用，请等待）</div>'
      : "")
    + "</div>";
}
