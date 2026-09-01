// ui/code-ai-chat.js — IDE AI 对话面板胶水（工单 code-ide-ai/03）
//
// 一期 C1：编辑器内「选中代码 → 问 AI」。浮动按钮（选区末行右侧）→ 选区
// 上下文引用文本插入输入框 → 面板打开聚焦 → 用户补问题发送；对话复用生成
// 页全局商量端点 /api/tasks/idea/chat/send|read（零后端新增）：history 单
// 通道（旧 → 新，末条 user = 本轮；服务端原子轮——LLM 失败不落半轮且报错，
// 前端失败后回填输入框可重发）。chat = 落盘真相 {messages:[{role,content,at}],
// note}；pendingText = 发送中乐观气泡。渲染纯件 = fx/ai-chat.js。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { aiChatMessagesHTML } from "/js/fx/ai-chat.js";
import { parseAiDiff, selectionContextText } from "/js/fx/ai-diff.js";
import { caretLineOf } from "/js/fx/codeeditor.js";
import { maincDiffCompute } from "/js/fx/mainc-diff.js";
import { mainDiffHTML } from "/js/fx/diff.js";
import { WRITE_GUARD_ACTIONS } from "/js/fx/write-guard.js";
import { getActiveTab, getCodeDir, onActiveTabChanged } from "/js/ui/codeeditor.js";
import { aiActionStart, aiActionStop } from "/js/ui/ai-banner.js";  // 全局「AI 行动中」横幅（ai-action-banner/02 同 crate 先例）
// 写盘守卫为动态 import：code-write-guard 静态 import codeview（isMainCDiskDir），
// 而 codeview → code-ai-chat —— 静态链路成环（codeview → code-ai-chat →
// code-write-guard → codeview）；previewDiff 内运行时加载打破静态环。
import { confirmModal } from "/js/ui/confirm.js";

// ---- 模块态 ----
let chat = { messages: [], note: "" };   // 后端落盘形状（read/send 响应）
let pendingText = "";                   // 发送中未确认的用户消息（乐观气泡）
let busy = false;

// ===== 面板 =====
function panelBox() { return $("code-ai-chat-panel"); }

/** 渲染面板：消息流（滚到底）+ 忙态状态行 + 发送钮可用性。 */
function renderPanel() {
  const panel = panelBox();
  if (!panel) return;
  const body = $("code-ai-chat-body");
  if (body) {
    body.innerHTML = aiChatMessagesHTML(chat.messages, pendingText);
    attachDiffButtons();
    body.scrollTop = body.scrollHeight;
  }
  const status = $("code-ai-chat-status");
  if (status) status.textContent = busy ? "AI 回应中…（分钟级调用，请等待）" : "";
  setSendEnabled();
}

function setSendEnabled() {
  const send = $("btn-code-ai-send");
  const input = $("code-ai-chat-input");
  if (send) send.disabled = busy || !(input && input.value.trim());
}

/** 展开面板（收起态展开 + 聚焦输入框）。 */
function openPanel() {
  const panel = panelBox();
  if (!panel) return;
  if (panel.classList.contains("collapsed")) {
    panel.classList.remove("collapsed");
    const btn = $("btn-code-ai-collapse");
    if (btn) { btn.textContent = "收起"; btn.title = "收起对话区"; }
  }
  panel.classList.remove("hidden");
  focusInput();
}

function focusInput() {
  const input = $("code-ai-chat-input");
  if (input) input.focus();
}

// ===== 浮动按钮（选区末行右侧，挂 .code-edit 内容坐标系——随滚动天然跟随）=====

// ensureSelectionBtn(edit)：.code-edit 内无按钮则创建（renderPane 每次覆盖
// 内容，按钮随渲染丢失——惰性重建，安全网兜底；按钮只在编辑态有意义）。
function ensureSelectionBtn(edit) {
  const existing = edit.querySelector(".code-ai-selection-btn");
  if (existing) return existing;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "code-ai-selection-btn hidden";
  btn.title = "把选中片段作为上下文提问（引用会插入输入框）";
  btn.textContent = "问 AI";
  edit.appendChild(btn);
  return btn;
}

// selectionState()：活动编辑器的选区快照（textarea + 选区起止）——浮动按钮
// 显示判定与 askSelection 共用（无选区/无编辑器 → null）。
function selectionState() {
  const ta = document.querySelector(".code-ta");
  const tab = getActiveTab();
  if (!ta || !tab || !(ta.selectionEnd > ta.selectionStart)) return null;
  return { ta, tab };
}

// updateSelectionButton()：刷新浮动按钮（有选区 → 定位到选区末行右端显示；
// 无选区/非编辑态 → 隐藏）。选区变化事件（textarea keyup/mouseup/click/
// input 委托）+ 活动 tab 变化时调用；.md 预览态或无内容文件无 .code-ta。
function updateSelectionButton() {
  const edit = document.querySelector(".code-edit");
  if (!edit) return;
  const btn = ensureSelectionBtn(edit);
  const sel = selectionState();
  if (!sel) {
    btn.classList.add("hidden");
    return;
  }
  const lineNo = caretLineOf(sel.ta.value, sel.ta.selectionEnd);
  const lineEl = edit.querySelector('.code-hl-line[data-code-line="' + lineNo + '"]');
  if (!lineEl) { btn.classList.add("hidden"); return; }
  const r = lineEl.getBoundingClientRect();
  const e = edit.getBoundingClientRect();
  btn.classList.remove("hidden");
  btn.style.left = (r.right - e.left + 6) + "px";
  btn.style.top = (r.top - e.top + 2) + "px";
}

// askSelection()：浮动按钮点击——选区引用插入输入框（追加，已有草稿保留）
// + 展开面板聚焦。mousedown 时 preventDefault 防 textarea 失焦清选区。
function askSelection() {
  const sel = selectionState();
  if (!sel) return;
  const code = sel.ta.value.slice(sel.ta.selectionStart, sel.ta.selectionEnd);
  const startLine = caretLineOf(sel.ta.value, sel.ta.selectionStart);
  // 选区止于换行（selectionEnd 落在下一行行首）→ 末行号 -1（评审 s1 整改）
  const endRaw = caretLineOf(sel.ta.value, sel.ta.selectionEnd)
    - (sel.ta.value.slice(0, sel.ta.selectionEnd).endsWith("\n") ? 1 : 0);
  const ref = selectionContextText(sel.tab.path, sel.tab.lang, startLine, endRaw, code);
  const input = $("code-ai-chat-input");
  if (!input) return;
  input.value = (input.value.trim() ? input.value.trimEnd() + "\n\n" : "") + ref;
  openPanel();
}

// ===== 发送 / 读盘 =====
async function sendMessage() {
  const input = $("code-ai-chat-input");
  if (!input || busy) return;
  const text = input.value.trim();
  if (!text) return;
  const dir = getCodeDir();
  if (!dir) { toastError(new Error("未打开目录"), "无法发送"); return; }
  pendingText = text;
  input.value = "";
  busy = true;
  renderPanel();
  aiActionStart("AI 对话");   // 全局「AI 行动中」横幅（与生成页各 AI 动作同 crate）
  const history = chat.messages.map((m) => ({ role: m.role, content: m.content }))
    .concat([{ role: "user", content: text }]);
  try {
    const data = await apiPost("/api/tasks/idea/chat/send", { output_dir: dir, history });
    if (data && data.chat) chat = data.chat;   // 服务端落盘真相替换乐观态
  } catch (e) {
    toastError(e, "AI 回应失败");
    input.value = text;   // 失败回填：该轮未落盘（服务端原子轮），改后可重发
  } finally {
    aiActionStop();
    busy = false;
    pendingText = "";
    renderPanel();
  }
}

// ===== C2 应用闭环（工单 code-ide-ai/04）：<DIFF> → 预览 → 确认 → 写盘 → 感知 =====
// attachDiffButtons()：renderPanel 后调用——assistant 消息含有效 <DIFF> 块
// → 气泡尾部挂「预览改动」按钮（parseAiDiff 单源；无块不挂）。按钮
// data-ai-preview = assistant 序号（第 N 条 assistant 消息，0 起）。
function attachDiffButtons() {
  const body = $("code-ai-chat-body");
  if (!body) return;
  const ais = body.querySelectorAll(".sugg-msg.ai");
  let aiIdx = 0;
  for (const msg of chat.messages) {
    if (!msg || msg.role !== "assistant") continue;
    const el = ais[aiIdx];
    aiIdx += 1;
    if (!el || el.querySelector("[data-ai-preview]")) continue;
    if (!parseAiDiff(String(msg.content || ""))) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "code-ai-preview-btn";
    btn.dataset.aiPreview = String(aiIdx - 1);
    btn.textContent = "预览改动";
    el.appendChild(btn);
  }
}

// previewDiff(aiIdx)：预览第 N 条 assistant 消息的 diff——读盘 →
// preview（只算不写）→ 生成行级 diff（maincDiffCompute 磁盘 vs new_content，
// 与服务端 main_diff 同构——diff 超限/无差异 → 占位文案但可确认）→
// confirmModal（复用 mainDiffHTML 渲染）→ 写盘守卫 → apply（写模式携带
// base_mtime_ns = 读盘值）→ 成功 toast + 感知钩子；409 → 提示重预览。
async function previewDiff(aiIdx) {
  const ais = chat.messages.filter((m) => m && m.role === "assistant");
  const msg = ais[aiIdx];
  if (!msg) return;
  const d = parseAiDiff(String(msg.content || ""));
  if (!d) return;
  const dir = getCodeDir();
  if (!dir) { toastError(new Error("未打开目录"), "无法预览"); return; }
  let file;
  try {
    file = await apiGet("/api/code/file?dir=" + encodeURIComponent(dir)
      + "&path=" + encodeURIComponent(d.path));
  } catch (e) {
    toastError(e, "读取文件失败");
    return;
  }
  let preview;
  try {
    preview = await apiPost("/api/code/apply-diff", {
      dir, path: d.path, hunks: d.hunks, preview: true,
    });
  } catch (e) {
    toastError(e, "计算改动失败");
    return;
  }
  const diffObj = maincDiffCompute(String(file.content || ""), String(preview.new_content || ""));
  const inner = diffObj
    ? mainDiffHTML(diffObj, "AI 改动")
    : '<div class="muted">内容差异明细不可用（无变化或差异过大）。'
      + "确认后将按 AI 建议直接应用。</div>"
      + '<div class="diff-stats reason"><strong>AI 改动：</strong>新增 <span class="diff-count add">+'
      + (preview.stats.additions || 0) + "</span> 行 · 删除 <span class=\"diff-count del\">−"
      + (preview.stats.deletions || 0) + "</span> 行 · " + (preview.stats.hunks || 0) + " 处改动</div>";
  const yes = await confirmModal({
    title: "预览 AI 改动 · " + d.path,
    message: "",
    danger: false,
    confirmText: "应用改动",
    cancelText: "取消",
    extra: '<div class="code-ai-preview-body">' + inner + "</div>",
  });
  if (!yes) return;
  const guard = await import("/js/ui/code-write-guard.js");   // 动态 import 破静态环（见头部注释）
  const allowed = await guard.guardCodeTabWrite(
    WRITE_GUARD_ACTIONS.codeAiApply, { anyDir: true });   // 任意目录：脏标签都先确认（IDE 内写盘语义）
  if (!allowed) return;   // 守卫取消：中止（不写盘）
  try {
    const result = await apiPost("/api/code/apply-diff", {
      dir, path: d.path, hunks: d.hunks, base_mtime_ns: file.mtime_ns,
    });
    toast("ok", "已应用 AI 改动：" + result.path);
    notifyApplied(result.path);
  } catch (e) {
    if (e && e.status === 409) {
      toastError(e, "磁盘内容已变化，请重新预览后再应用");
    } else {
      toastError(e, "应用 AI 改动失败");
    }
  }
}

// 感知钩子（工单 04）：apply 成功 → codeview 注册的 checkCodeDiskChanges
// 立即执行（变更面板自动出现；干净标签自动重载版本文——用户见证 AI 落盘）。
// code-ai-chat 不 import codeview（避免环），经注册回调解耦。
const appliedListeners = new Set();
export function onCodeAiApplied(cb) { appliedListeners.add(cb); }
function notifyApplied(path) {
  appliedListeners.forEach((cb) => { try { cb(path); } catch (e) { /* 监听器异常不阻断 */ } });
}

// setCodeAiDir(dir)：目录打开钩子（codeview.loadCodeDir 调用）——隐藏/显示
// 面板 + 拉取该目录聊天历史。非生成上下文目录读不到 = 空聊天（不报错）。
export async function setCodeAiDir(dir) {
  const panel = panelBox();
  if (!panel) return;
  if (!dir) { panel.classList.add("hidden"); return; }
  panel.classList.remove("hidden");
  chat = { messages: [], note: "" };
  pendingText = "";
  renderPanel();
  try {
    const data = await apiPost("/api/tasks/idea/chat/read", { output_dir: dir });
    if (data && data.chat) chat = data.chat;
  } catch (e) {
    // 非生成上下文 / 目录不可用：静默保持空聊天（send 时服务端给明确中文错）
  }
  renderPanel();
}

// ===== 接线 =====
export function initCodeAiChat() {
  const send = $("btn-code-ai-send");
  if (send) send.addEventListener("click", sendMessage);

  const input = $("code-ai-chat-input");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
      e.preventDefault();
      sendMessage();
    });
    input.addEventListener("input", () => setSendEnabled());
  }

  const collapse = $("btn-code-ai-collapse");
  if (collapse) collapse.addEventListener("click", () => {
    const panel = panelBox();
    if (!panel) return;
    const collapsed = panel.classList.toggle("collapsed");
    collapse.textContent = collapsed ? "展开" : "收起";
    collapse.title = collapsed ? "展开对话区" : "收起对话区";
  });

  // 「预览改动」按钮委托（工单 04）：按钮动态注入（attachDiffButtons），
  // 容器静态——body 委托零重绑。
  const chBody = $("code-ai-chat-body");
  if (chBody) chBody.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-ai-preview]");
    if (btn) previewDiff(parseInt(btn.dataset.aiPreview, 10));
  });

  // 选区 → 浮动按钮：textarea 事件委托（textarea 由 codeeditor 动态渲染，
  // 直接绑定会被重建覆盖；keyup/mouseup/click/input 覆盖键盘/鼠标选区变化，
  // 同一判定合一台处理——评审整改）
  const onTaEvent = (e) => {
    if (e.target && e.target.classList && e.target.classList.contains("code-ta")) {
      updateSelectionButton();
    }
  };
  document.addEventListener("keyup", onTaEvent);
  for (const evt of ["mouseup", "click", "input"]) {
    document.addEventListener(evt, onTaEvent);
  }
  // 点击别处（非按钮/非 textarea）→ 隐藏；按钮 mousedown preventDefault 保选区
  document.addEventListener("click", (e) => {
    if (e.target && e.target.closest && e.target.closest(".code-ai-selection-btn")) return;
    if (e.target && e.target.classList && e.target.classList.contains("code-ta")) return;
    const edit = document.querySelector(".code-edit");
    const btn = edit && edit.querySelector(".code-ai-selection-btn");
    if (btn) btn.classList.add("hidden");
  }, true);   // 捕获：先于按钮 click 冒泡处理？—— 按钮 click 已 return，无冲突
  document.addEventListener("mousedown", (e) => {
    if (e.target && e.target.closest && e.target.closest(".code-ai-selection-btn")) {
      e.preventDefault();   // 保 textarea 选区（失焦清除）
    }
  }, true);
  document.addEventListener("click", (e) => {
    if (e.target && e.target.closest && e.target.closest(".code-ai-selection-btn")) {
      askSelection();
    }
  });

  // 活动 tab 变化（renderPane 之后触发）→ 按钮挂载/刷新 + md 预览态清除
  onActiveTabChanged(() => {
    updateSelectionButton();
  });
}
