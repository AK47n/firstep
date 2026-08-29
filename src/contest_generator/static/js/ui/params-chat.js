// ui/params-chat.js — 参数速调 AI 咨询对话（工单 params-chat-ai/02）DOM 胶水。
//
// 对话区在「参数速调」页签内第二个 card-group："问 AI：我该调哪个参数？"
// 展开/收起（多轮历史落盘 .contest_params_chat.json——与工程级全局商量
// 独立）；发送回合 = /api/params/chat/send（后端注入当前参数清单 + 题面 +
// 任务清单现状）；AI 回复里提及的参数名（fx 已包成 .btn-param-ref chip）
// 点击 → 滚动到对应参数卡 + 高亮 + 聚焦输入框（「AI 说改哪个 → 一键定位 →
// 改 → 应用」闭环）。纯函数渲染在 fx/params-chat.js，本层只喂状态 + 委托
// + 跨簇重置。与 ui/params.js 共用目录闸（tasksIsBusy），但对话读写不写
// main.c，自己不置全局忙。
//
// 事件词表：无 SSE（同步端点，照全局商量）；失败回填 draft、pending 撤出。
import { $, apiPost, toast } from "/js/app.js";
import { paramsChatHTML } from "/js/fx/params-chat.js";
import { reviseGetDir } from "./generate-revise.js";
import { tasksIsBusy } from "./generate-tasks.js";
import { paramsBusy, paramsPlan } from "./params.js";

// 本簇状态（会话级；落盘真相 = .contest_params_chat.json）：chat = 后端
// {messages} 全量（read/send 后替换）；pending = 发送中乐观展示的用户消息；
// draft = 输入框未发送内容（失败回填，重试免重打）。
let paramsChatState = {
  open: false,
  busy: false,
  chat: null,
  pending: "",
  draft: "",
};

function paramsChatDir() {
  return reviseGetDir();
}

function paramsChatStatus(text) {
  const el = $("params-chat-status");
  if (el) el.textContent = text || "";
}

/** 对话区 + 开关按钮渲染：open 时渲染对话区（历史 + 输入行），关闭清空隐藏；
 * 开关按钮文案随 open 切换。paramNames = 当前参数表参数名（fx 契约：字符串
 * 数组——提及 chip 只包真实存在的参数名；参数表刷新/识别后随
 * step11-state-changed 重渲染同步）。 */
function paramsChatRender() {
  const area = $("params-chat");
  if (!area) return;
  const paramNames = (paramsPlan() || []).map((p) => String((p && p.name) || ""));
  area.innerHTML = paramsChatHTML(paramsChatState, paramNames);
  area.classList.toggle("hidden", !paramsChatState.open);
  const btn = $("btn-params-chat");
  if (btn) btn.textContent = paramsChatState.open
    ? "收起问 AI"
    : "问 AI：我该调哪个参数？";
}

/** 读盘加载对话历史（首次展开调用）；无文件 = 空聊天（不 400）。 */
async function paramsChatLoad() {
  const dir = paramsChatDir();
  if (!dir) throw new Error("请先在「修订」页签加载当前会话或历史目录");
  const data = await apiPost("/api/params/chat/read", { output_dir: dir });
  paramsChatState.chat = data.chat || { messages: [] };
}

/** 展开 / 收起；首次展开读盘加载历史（失败回卷为收起 + 错误提示，防
 * 「空区展开」误导——照全局商量同款）。目录未加载时提示先去修订页签。 */
async function paramsChatToggle() {
  if (paramsBusy() || tasksIsBusy()) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = paramsChatDir();
  const msgEl = $("params-chat-msg");
  if (!paramsChatState.open && !dir) {
    if (msgEl) msgEl.textContent = "请先在「修订」页签加载当前会话或历史目录";
    return;
  }
  paramsChatState.open = !paramsChatState.open;
  if (paramsChatState.open && !paramsChatState.chat) {
    if (msgEl) msgEl.textContent = "";
    try {
      await paramsChatLoad();
    } catch (e) {
      paramsChatState.open = false;
      if (msgEl) msgEl.textContent = e.message;
    }
  }
  paramsChatRender();
}

/** 发送一轮咨询：历史单通道（history 含本轮 user 末条——与 /api/tasks/
 * idea/chat/send 同契约）；成功服务端落 user+assistant 两条并返回全量 chat
 * → 替换本地缓存；失败 pending 撤出、draft 回填（用户可重试），历史不动。
 * 目录 / 空消息前置校验（中文提示，照 params.js apply 语感）。 */
async function paramsChatSend() {
  if (paramsChatState.busy || paramsBusy() || tasksIsBusy()) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = paramsChatDir();
  const msgEl = $("params-chat-msg");
  if (!dir) {
    if (msgEl) msgEl.textContent = "请先在「修订」页签加载当前会话或历史目录";
    return;
  }
  const input = $("params-chat-input");
  const message = ((input && input.value) || "").trim();
  if (!message) {
    if (msgEl) msgEl.textContent = "请先描述现象（如：小车直行跑偏 / 循迹丢线）";
    return;
  }
  const history = ((paramsChatState.chat && paramsChatState.chat.messages) || [])
    .map((m) => ({ role: m.role, content: m.content }));
  history.push({ role: "user", content: message });
  paramsChatState.pending = message;
  paramsChatState.draft = "";
  paramsChatState.busy = true;
  if (msgEl) msgEl.textContent = "";
  paramsChatStatus("AI 诊断中…（分钟级调用，请等待）");
  paramsChatRender();
  try {
    const data = await apiPost("/api/params/chat/send", { output_dir: dir, history });
    paramsChatState.chat = data.chat || paramsChatState.chat;
    paramsChatStatus("");
    toast("ok", "AI 已回复——回复里的参数名可直接点击定位");
  } catch (e) {
    paramsChatState.draft = message;   // 失败回填：历史不动（后端原子轮次）
    paramsChatStatus("");
    if (msgEl) msgEl.textContent = e.message;
  } finally {
    paramsChatState.pending = "";
    paramsChatState.busy = false;
    paramsChatRender();
  }
}

/** 定位联动（工单 params-chat-ai/02）：chip 点击 → 参数卡滚动到视线中心 +
 * 高亮约 2.2s（重复点击先移除 class 再强制 reflow 重触发动画）+ 聚焦输入框。
 * 参数不在当前表（已失效 / 未识别）→ toast 告知，不滚动。 */
function paramsLocateParam(name) {
  const input = $("params-input-" + name);
  const card = input ? input.closest(".param-card") : null;
  const inPlan = (paramsPlan() || [])
    .some((p) => String((p && p.name) || "") === name);
  if (!card || !inPlan) {
    toast("info", "参数「" + name + "」不在当前参数表（可能已失效或尚未识别）");
    return;
  }
  card.classList.remove("param-card-locate");
  void card.offsetWidth;   // 强制 reflow：重复点击重触发动画
  card.classList.add("param-card-locate");
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  if (input) input.focus();
  setTimeout(() => card.classList.remove("param-card-locate"), 2200);
}

/** 跨簇重置（目录切换 / 清单作废）：关区清状态 + 清容器 + 按钮文案回默认，
 * 对话历史在磁盘（.contest_params_chat.json）——重开目录时由读盘带回。 */
function paramsChatReset() {
  paramsChatState.busy = false;
  paramsChatState.open = false;
  paramsChatState.chat = null;
  paramsChatState.pending = "";
  paramsChatState.draft = "";
  const area = $("params-chat");
  if (area) { area.innerHTML = ""; area.classList.add("hidden"); }
  const msgEl = $("params-chat-msg");
  if (msgEl) msgEl.textContent = "";
  paramsChatStatus("");
  const btn = $("btn-params-chat");
  if (btn) btn.textContent = "问 AI：我该调哪个参数？";
}

// 监听器（import 时绑定：module 脚本延迟执行，DOM 已就绪）
$("btn-params-chat").addEventListener("click", () => paramsChatToggle());
$("params-chat").addEventListener("click", (event) => {
  const send = event.target.closest(".btn-params-chat-send");
  if (send) { paramsChatSend(); return; }
  const ref = event.target.closest(".btn-param-ref");
  if (ref && ref.dataset.paramRef) paramsLocateParam(ref.dataset.paramRef);
});
// 输入框内 Enter 直接发送（与点「发送」同路径——busy 守卫 / 空值校验在内）
$("params-chat").addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  const input = event.target.closest("#params-chat-input");
  if (!input) return;
  event.preventDefault();
  paramsChatSend();
});
// 参数表刷新（识别/应用/重读/重置）后：对话开着则重渲染——提及 chip 集合
// 同步当前参数表（旧的失效参数名不再可点）。
window.addEventListener("step11-state-changed", () => {
  if (paramsChatState.open) paramsChatRender();
});
// 跨簇重置：目录切换 / 清单作废 → 关区清状态
window.addEventListener("revise-context-loaded", () => paramsChatReset());
window.addEventListener("tasks-invalidated", () => paramsChatReset());

export { paramsChatReset };
