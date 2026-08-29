// ui/generate-recommend.js — 生成页推荐簇 A（题面 viewer / 推荐流 / 参考选择 /
// 模块池 / 选中 / 警告 / renderPlatforms / useTopic）DOM 胶水（阶段 2 工单 12）
//
// 步骤 1-3 + 5 的 DOM 胶水全量迁入：题面 PDF viewer（页图 / 文字切换 / 上传 /
// 历史赛题取题面事务 useTopic）/ AI 推荐 SSE 流（recPanel 实例 / 进度 / 澄清
// 问题）/ 参考文件勾选与自动关联 / 模块池与推荐结果展示 / 已选清单与副产物
// 模板 / 平台警告与功能组冲突 / 平台卡 renderPlatforms。纯件在 fx/*.js
// （draft / module / score / reference / llm / platform / core）。
// 状态所有权表（本模块 = 主写簇；host 经 import 活绑定读，写经各 setter）：
//   chosenPlatform（setChosenPlatform）/ selectedSlugs（setSelectedSlugs）/
//   currentTopicId（setCurrentTopicId——工单 15 起 export let，生成簇/生成执行
//   读取方 import）/ recommendClarifications（setRecommendClarifications）
//   expanded / pythonTemplates / warnings / scorePoints / lastRecommend /
//   topicPdfTextVisible / recProblem / selectedReferenceIds / autoReferenceIds /
//   referenceEntries —— 读写均在本模块；host 只读点名见下表。
// instances / instancePinTarget 属引脚-多实例簇（已随工单 13 迁 ui/generate-pins.js）。
// host → 本簇的跨簇服务调用经 setClusterDeps 接缝（模块无法 import host）：
//   scheduleDraftSave（草稿——工单 18 迁）/ updateFixCenterAvailability（修复
//   中心——已随工单 16 迁 ui/generate-fix.js，经 host 注册闭包）/ resetPinState / resetInstances / clearInstanceTarget /
//   renderInstanceConfig / renderPinCard / loadPinBoard / backfillInstances
//   （引脚-多实例——工单 13 已迁入 ui/generate-pins.js，host 启动区注册改挂
//   静态 import）。其余项迁出后同改。
// 顶层 addEventListener / initModuleGrid() 在 import 时绑定（module 脚本延迟
// 执行，DOM 已就绪）。
import { $, handle, apiGet, apiPost, state, KIND_TEXT, toast } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { platformClickAction } from "/js/fx/platform.js";
import { moduleBadges, applyGroupRadio, autoAddDedup, groupConflicts, renderGroupCards, groupRequirementNote, moduleGridCountText, moduleGridHTML, moduleInfoHTML } from "/js/fx/module.js";
import { referencePlatformChip } from "/js/fx/reference.js";
import {
  suggestionChipHTML, decisionPayload, suggestionKey,
  loadBuyDecisions, saveBuyDecisions, matchBuyDecision,
  recommendCoverageNote,
} from "/js/fx/recommend.js";
import { renderScorePointPanel } from "/js/fx/score.js";
import { formatLLMTelemetry, parseSSE } from "/js/fx/llm.js";
import { stepNavTitles, syncStep4 } from "/js/fx/draft.js";
import { prereadHTML, prereadSlotHTML, prereadReminderGroups } from "/js/fx/topic-preread.js";
import { makeProgressPanel } from "/js/ui/progress.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { markStepDone, markStepUndone, unmarkSteps, STEP_NAV_CARD_SELECTOR } from "/js/ui/step-state.js";

export let chosenPlatform = null;
export function setChosenPlatform(v) { chosenPlatform = v; }

export let selectedSlugs = [];     // 当前选择的模块 slug（含用户增删，未展开）
export function setSelectedSlugs(v) { selectedSlugs = v; }
export let expanded = [];                // 展开后的模块 manifest（含依赖）
export let pythonTemplates = {};         // 副产物模板选择（工单 k230-multi-template/04）：{slug: template_id}（只含用户改过的，=默认不记录）
export let warnings = [];                // 平台警告
export let scorePoints = [];              // 推荐解析出的题面评分点（只读增强信息）
export let prereadOverviewText = "";      // 步骤 2 赛题预读的一句话总览（交接提示词读取方 import，工单 topic-preread/02）
export let prereadReminders = [];         // 步骤 2 赛题预读提醒（工单 03 钉卡分发读取方 import）
export let currentTopicId = "";      // 当前生效的赛题编号（历史赛题入口；工单 15 起
                                          // export——生成簇 generateMain 读取方 import）
export function setCurrentTopicId(v) { currentTopicId = v; }
let topicPdfTextVisible = true;   // 题面页图 / 文字版切换（纯展示态）
export let lastRecommend = null;         // 最近一次推荐结果（移除勾选 chip 后重渲染用）
let recProblem = "";              // 当前推荐题面：澄清回答后重启流程仍用原文
let recommendClarifications = []; // 澄清历史 [{question, answer}]
export function setRecommendClarifications(v) { recommendClarifications = v; }
export let selectedReferenceIds = [];    // 手动勾选的参考文件 id
export let autoReferenceIds = [];        // 推荐自动关联的参考文件 id
let referenceEntries = [];        // 参考文件条目（GET /api/references）

// ---- 跨簇接缝（host 启动区 setClusterDeps 注册；13 / 16 / 18 迁出后改静态 import）----
const clusterDeps = {};
export function setClusterDeps(deps) { Object.assign(clusterDeps, deps); }

// ---------------------------------------------------------------------------
// 生成页：2. 平台选择
// ---------------------------------------------------------------------------
export function renderPlatforms() {
  const box = $("platforms");
  box.innerHTML = "";
  for (const p of state.platforms) {
    const card = document.createElement("div");
    card.className = "platform-card" + (chosenPlatform === p.id ? " selected" : "") + (p.status !== "ready" ? " disabled" : "");
    const badge = p.status === "ready"
      ? '<span class="badge ok">可用</span>'
      : '<span class="badge no-master">暂不可用：尚未导入母版</span>';
    card.innerHTML = `<div class="name">${esc(p.name)}</div>${badge}`;
    if (p.status === "ready") {
      card.addEventListener("click", () => {
        const action = platformClickAction(chosenPlatform, p.id);
        if (action === "same") return;  // 重复点击已选平台：无操作（防误触丢选择）
        chosenPlatform = p.id;
        markStepDone(3);
        unmarkSteps(action === "switch" ? [5, 6, 7, 8, 9, 10, 11, 12] : [6, 7, 8, 9, 10, 11, 12]);  // 首次选平台保留推荐（步骤 5 不退）
        renderPlatforms();
        renderModulePool();  // 模块网格（工单 module-grid/01）：平台切换刷新置灰态
        clusterDeps.scheduleDraftSave();
        clusterDeps.updateFixCenterAvailability();
        if (action === "switch") {
          // 换平台：清空选择与配置，下游全部重来
          selectedSlugs = []; expanded = []; warnings = []; renderSelected(); renderWarnings();
          // 引脚配置（工单 03）：切平台清空绑定重取板定义
          clusterDeps.resetPinState();
          // 多实例配置（工单 04）：切平台清空实例清单与选脚目标
          clusterDeps.resetInstances();
        } else {
          // 首次选平台：保留既有选择（如推荐勾选）与实例清单，只重展开做平台兼容检查
          expanded = []; warnings = []; renderSelected(); renderWarnings();
          if (selectedSlugs.length) runExpand();
          // 引脚配置（工单 03）：首次选平台同样重取板定义（实例清单保留）
          clusterDeps.resetPinState();
          clusterDeps.clearInstanceTarget();
        }
        clusterDeps.loadPinBoard();
      });
    }
    box.appendChild(card);
  }
}

// ---------------------------------------------------------------------------
// 生成页：1. 上传抽取 + 历史赛题取题面
// ---------------------------------------------------------------------------
$("btn-upload").addEventListener("click", async () => {
  const file = $("problem-file").files[0];
  $("upload-msg").textContent = "";
  if (!file) { $("upload-msg").textContent = "请先选择文件"; return; }
  const form = new FormData();
  form.append("upload", file);
  try {
    const data = await handle(await fetch("/api/extract", { method: "POST", body: form }));
    $("problem").value = data.text;
    currentTopicId = "";
    clearTopicPreread();
    // 页图展示（工单 upload-pdf-pages/02 + upload-image-preview/02）：
    // 图片上传 → 原图箱；PDF 上传 → 页图箱；都没有 → 只显示文字
    if (data.image_data_url) {
      $("topic-pdf-box").classList.add("hidden");
      $("topic-pdf-pages").innerHTML = "";
      $("topic-image-box").classList.remove("hidden");
      $("topic-image-view").src = data.image_data_url;
      setTopicPdfTextVisible(false, $("btn-topic-image-text"));
    } else if (data.pages && data.pages.length) {
      $("topic-image-box").classList.add("hidden");
      setTopicPdfTextVisible(false);
      showTopicPdfViewer(data);
    } else {
      $("topic-image-box").classList.add("hidden");
      hideTopicPdfViewer();
    }
    $("upload-msg").classList.add("ok");
    $("upload-msg").textContent = "抽取成功：" + file.name;
    markStepDone(1);
    toast("ok", "题面抽取成功");
  } catch (e) {
    $("upload-msg").classList.remove("ok");
    $("upload-msg").textContent = e.message;
    toast("error", "题面抽取失败");
  }
});

$("btn-topic-load").addEventListener("click", async () => {
  const key = $("topic-id").value.trim().toUpperCase();
  $("topic-msg").textContent = "";
  if (!key) { $("topic-msg").textContent = "请先填写赛题编号"; return; }
  try {
    const data = await handle(await fetch("/api/topics/" + encodeURIComponent(key)));
    $("problem").value = data.problem_text;
    currentTopicId = data.key;
    clearTopicPreread();
    $("topic-msg").textContent = "已取题面：" + data.key;
    markStepDone(1);
    toast("ok", "已取题面：" + data.key);
    loadTopicPdf(data.key);
  } catch (e) {
    $("topic-msg").textContent = e.message;
    currentTopicId = "";
  }
});

// ---------------------------------------------------------------------------
// 取题面页图（工单 topic-pdf-viewer/01）：默认展示原题 PDF 页，文字可切换
// ---------------------------------------------------------------------------
function setTopicPdfTextVisible(visible, btn) {
  topicPdfTextVisible = visible;
  $("problem").classList.toggle("hidden", !visible);
  const el = btn || $("btn-topic-pdf-text");
  if (el) el.textContent = visible ? "收起文字版" : "显示文字版（可编辑）";
}

function showTopicPdfViewer(data) {
  const pagesEl = $("topic-pdf-pages");
  pagesEl.innerHTML = "";
  $("topic-image-box").classList.add("hidden");  // 与图片原图箱互斥
  data.pages.forEach(p => {
    const img = document.createElement("img");
    img.src = p.data_url;
    img.alt = "原题第 " + p.page_no + " 页";
    img.loading = "lazy";
    img.style.cssText = "width:100%;max-width:640px;display:block;margin:0 auto 10px;border:1px solid var(--border,#ccc);border-radius:4px;cursor:zoom-in;background:#fff";
    img.addEventListener("click", () => {
      $("pdf-zoom-img").src = p.data_url;
      $("pdf-zoom").classList.remove("hidden");
    });
    pagesEl.appendChild(img);
  });
  // 上传 PDF 截断提示（工单 upload-pdf-pages/02）：页数超上限只显示前 M 页；
  // 题库 /pages 响应无 total_pages 字段 → 不提示
  if (data.total_pages && data.total_pages > data.pages.length) {
    const hint = document.createElement("div");
    hint.className = "muted";
    hint.style.cssText = "text-align:center;font-size:12px;margin:4px 0 8px";
    hint.textContent = "共 " + data.total_pages + " 页，已显示前 "
      + data.pages.length + " 页（其余页未展示）。";
    pagesEl.appendChild(hint);
  }
  $("topic-pdf-box").classList.remove("hidden");
  // 不再强制收起文字版（工单 ui-polish-10/02）：加载期 loadTopicPdf 已默认收起文字；
  // 若用户在渲染期手动打开了文字版，页图到达后尊重用户选择。
}

function hideTopicPdfViewer() {
  $("topic-pdf-box").classList.add("hidden");
  $("topic-image-box").classList.add("hidden");
  $("pdf-zoom").classList.add("hidden");
  setTopicPdfTextVisible(true);
}

async function loadTopicPdf(key) {
  // 渲染期占位（工单 ui-polish-10/02）：页图要几秒才渲染完，期间不先露文字版，
  // 显示「渲染中…」占位；文字版保持「显示文字版（可编辑）」可随时手动打开。
  $("topic-pdf-box").classList.remove("hidden");
  $("topic-pdf-pages").innerHTML =
    '<div class="empty-state" style="padding:18px 0">' +
    '<div class="es-icon">📄</div>' +
    '<div class="es-title">原题 PDF 页渲染中…</div>' +
    '<div class="es-hint">题面文字已就绪，可点上方「显示文字版（可编辑）」提前查看；页图渲染完成后自动展示。</div>' +
    '</div>';
  setTopicPdfTextVisible(false);
  try {
    const data = await apiGet("/api/topics/" + encodeURIComponent(key) + "/pages");
    showTopicPdfViewer(data);
  } catch (e) {
    hideTopicPdfViewer();
    toast("error", "原题 PDF 页加载失败");
    $("topic-msg").textContent = "无法展示原题 PDF 页：" + e.message;
  }
}

$("btn-topic-pdf-text").addEventListener("click", () => {
  setTopicPdfTextVisible(!topicPdfTextVisible);
});

$("btn-topic-image-text").addEventListener("click", () => {
  setTopicPdfTextVisible(!topicPdfTextVisible, $("btn-topic-image-text"));
});

$("topic-image-view").addEventListener("click", () => {
  $("pdf-zoom-img").src = $("topic-image-view").src;
  $("pdf-zoom").classList.remove("hidden");
});

$("pdf-zoom").addEventListener("click", () => {
  $("pdf-zoom").classList.add("hidden");
  $("pdf-zoom-img").src = "";  // 释放大图引用（评审提示：陈旧位图驻留内存）
});

$("problem").addEventListener("input", () => {
  if (currentTopicId) { currentTopicId = ""; $("topic-msg").textContent = ""; }
  clearTopicPreread();  // 题面变了 = 旧预读对不上，立即清掉（wait-what 要的是当前题面）
  hideTopicPdfViewer();  // 手动改写/粘贴题面 = 旧题页图对不上（工单 topic-pdf-viewer/01）
  if (!$("problem").value.trim()) markStepUndone(1);
});

// ---------------------------------------------------------------------------
// 生成页：2. 赛题预读（工单 topic-preread/02）——提炼"题面已锁死什么"+
// 决策点提醒（每条 = 影响步骤 + 提醒文本 + 题面原文引用），只展示不进下游
// ---------------------------------------------------------------------------
function topicPrereadStepTitles() {
  // 步骤名从 DOM h2 单源读取（step-nav 同款），前端不硬编码步骤名。
  // h2 尾部含卡片折叠按钮图标（▾/▸，step-state.js 追加），组标题剥掉。
  const out = {};
  for (const t of stepNavTitles(Array.from(document.querySelectorAll(STEP_NAV_CARD_SELECTOR)))) {
    const title = String(t.title || "").replace(/[▾▸]\s*$/, "").trim();
    if (Number.isFinite(t.n) && title) out[t.n] = title;
  }
  return out;
}

function clearTopicPreread() {
  $("topic-preread-box").classList.add("hidden");
  $("topic-preread-box").innerHTML = "";
  $("topic-preread-msg").textContent = "";
  $("btn-topic-preread").innerHTML = "预读题面";
  prereadOverviewText = "";
  prereadReminders = [];
  // 工单 03 的提醒槽位统一清空路径：步骤卡上的 [data-preread-slot] 一次全清（无槽位则无操作）
  document.querySelectorAll("[data-preread-slot]").forEach((el) => {
    el.classList.add("hidden");
    el.innerHTML = "";
  });
  scorePoints = [];  // 题面变更后评分点失效，避免旧题验收清单串进生成 / 交接
  unmarkSteps([2, 5, 6, 7, 8, 9, 10, 11, 12]);  // 题面变了：AI 产物与生成结果全部失效
}

// 钉卡分发（工单 topic-preread/03）：结果渲染到所有目标步骤卡槽位，
// 每卡只显该卡相关条目；无相关条目的槽位保持隐藏（无提醒不占位）。
// 注意：groups.find 只匹配数值步骤组——「其他限定」（step:null，尺寸/
// 电源/时长等通用要求）有意不钉卡，只在步骤 2 卡分组展示。
function renderPrereadSlots(reminders) {
  const groups = prereadReminderGroups(reminders);
  document.querySelectorAll("[data-preread-slot]").forEach((slot) => {
    const step = parseInt(slot.dataset.step, 10);
    const group = groups.find((g) => g.step === step);
    if (!group || !group.items.length) { slot.innerHTML = ""; slot.classList.add("hidden"); return; }
    slot.innerHTML = prereadSlotHTML(group.items);
    slot.classList.remove("hidden");
  });
}

$("btn-topic-preread").addEventListener("click", async () => {
  $("topic-preread-msg").textContent = "";
  const problem = $("problem").value.trim();
  if (!problem) { $("topic-preread-msg").textContent = "请先填写赛题原文"; return; }
  $("btn-topic-preread").disabled = true;
  $("btn-topic-preread").innerHTML = '<span class="spinner"></span>AI 预读中…';
  try {
    const data = await apiPost("/api/topic/preread", { problem_text: problem });
    prereadOverviewText = String(data.overview || "");
    prereadReminders = Array.isArray(data.reminders) ? data.reminders : [];
    $("topic-preread-box").innerHTML = prereadHTML(
      { overview: prereadOverviewText, reminders: prereadReminders },
      topicPrereadStepTitles()
    );
    $("topic-preread-box").classList.remove("hidden");
    renderPrereadSlots(prereadReminders);
    $("btn-topic-preread").innerHTML = "重新预读";
    markStepDone(2);  // 预读成功即视为完成（题面变更时 clearTopicPreread 会取消）
  } catch (e) {
    $("topic-preread-msg").textContent = e.message;
  } finally {
    $("btn-topic-preread").disabled = false;
  }
});

// ---------------------------------------------------------------------------
// 生成页：3. AI 推荐
// ---------------------------------------------------------------------------
function recommendChip(slug, reason) {
  return '<span class="chip rec" data-remove="' + esc(slug) + '">' + esc(slug)
    + (reason ? '<span class="reason">' + esc(reason) + '</span>' : "")
    + '<span class="chip-x">✕</span></span>';
}

// 库外建议 chip（工单 buy-guide/02 + 工单 buy-discuss/05）：chip 展开 /
// 讨论区开关 / 发送 / 确定全部走 state + 重渲染（discussions Map 按建议名
// 键存 {openPanel, open, busy, history, review, decision}——渲染函数纯输出，
// 交互态不回写 DOM，重渲染不丢；data-sugg-key 反查建议对象）。
const DISCUSS_MAX_ROUNDS = 8;   // 讨论轮数上限（spec 预算/费用防线）
const discussions = new Map();

function newDiscussionState() {
  return { openPanel: false, open: false, busy: false, history: [], review: null, decision: null };
}

function findSuggestion(key) {
  if (!lastRecommend) return null;
  for (const req of lastRecommend.requirements || []) {
    for (const s of req.suggestions || []) {
      if (s && suggestionKey(s) === key) return s;
    }
  }
  return null;
}

// 已定结论恢复（localStorage 记忆 → 本轮 suggestion.decision）：重推 / 刷新
// 后徽标即现；「本轮已确定」（s.decision 已有）不被旧记忆覆盖。
function hydrateDecisions(data) {
  const memory = loadBuyDecisions(localStorage);
  if (!Object.keys(memory).length) return;
  for (const req of data.requirements || []) {
    for (const s of req.suggestions || []) {
      if (typeof s !== "object" || !s) continue;
      const d = matchBuyDecision(memory, suggestionKey(s));
      if (d && !s.decision) s.decision = decisionPayload(d);
    }
  }
}

function applyDecision(key, s, decision) {
  const st = discussions.get(key) || newDiscussionState();
  st.decision = decision;
  discussions.set(key, st);
  s.decision = decisionPayload(decision);   // 写回载荷 —— 生成请求上行原文
  const memory = loadBuyDecisions(localStorage);
  memory[key] = decision;                   // 键 = 建议名（会话间记忆）
  saveBuyDecisions(localStorage, memory);
  renderRecommendResult(lastRecommend, false);
}

function suggestRequirement(s) {
  for (const req of lastRecommend.requirements || []) {
    if ((req.suggestions || []).some((x) => x === s)) return req.requirement || "";
  }
  return "";
}

async function sendDiscuss(wrap) {
  const key = wrap.dataset.suggKey;
  const st = discussions.get(key) || newDiscussionState();
  const s = findSuggestion(key);
  const input = wrap.querySelector(".sugg-discuss-input");
  const text = (input.value || "").trim();
  const userRounds = st.history.filter((m) => m.role === "user").length;
  if (!text || st.busy || userRounds >= DISCUSS_MAX_ROUNDS || !s) return;
  st.history.push({ role: "user", content: text });
  input.value = "";
  st.busy = true;
  renderRecommendResult(lastRecommend, false);
  try {
    const data = await apiPost("/api/buy/discuss", {
      problem_text: $("problem").value.trim(),
      requirement: suggestRequirement(s),
      platform: chosenPlatform || undefined,
      suggestion_name: s.name,
      history: st.history.map((m) => ({ role: m.role, content: m.content })),
    });
    st.history.push({ role: "assistant", content: data.reply || "（无回复）" });
    st.review = data.review || null;
  } catch (err) {
    st.history.push({ role: "assistant", content: "（讨论失败：" + err.message + "）" });
  } finally {
    st.busy = false;
    renderRecommendResult(lastRecommend, false);
  }
}

function pickCustom(wrap) {
  const key = wrap.dataset.suggKey;
  const s = findSuggestion(key);
  const st = discussions.get(key) || newDiscussionState();
  const input = wrap.querySelector(".sugg-discuss-input");
  // 输入框可能已被「发送」清空：回退到最后一条用户消息（AI 校核的正是它）。
  // verdict 只在「用最后一条消息」（typed 为空）时借用——新输入未经校核
  // （评审项 buy-discuss/07：别把上一轮的审核意见贴到新想法上）
  const typed = (input.value || "").trim();
  const lastUser = [...st.history].reverse().find((m) => m.role === "user");
  const text = typed || (lastUser ? String(lastUser.content || "").trim() : "");
  if (!text || !s) { toast("先把你的想法写在输入框里（AI 会校核可行性）"); return; }
  const verdict = (!typed && st.review) ? st.review.verdict : "";
  applyDecision(key, s, {
    source: "custom",
    name: text.length > 30 ? text.slice(0, 30) + "…" : text,
    note: text,
    verdict,
  });
}

document.addEventListener("click", (e) => {
  const chip = e.target.closest(".sugg-chip");
  if (chip) {
    const wrap = chip.closest(".sugg-wrap");
    const key = wrap && wrap.dataset.suggKey;
    if (key) {
      const st = discussions.get(key) || newDiscussionState();
      st.openPanel = !st.openPanel;
      discussions.set(key, st);
      renderRecommendResult(lastRecommend, false);
    }
    return;
  }
  const toggle = e.target.closest(".sugg-discuss-toggle");
  if (toggle) {
    const wrap = toggle.closest(".sugg-wrap");
    const key = wrap && wrap.dataset.suggKey;
    if (key) {
      const st = discussions.get(key) || newDiscussionState();
      st.open = !st.open;
      discussions.set(key, st);
      renderRecommendResult(lastRecommend, false);
    }
    return;
  }
  const send = e.target.closest(".sugg-discuss-send");
  if (send) { sendDiscuss(send.closest(".sugg-wrap")); return; }
  const custom = e.target.closest("[data-buy-self]");
  if (custom) { pickCustom(custom.closest(".sugg-wrap")); return; }
  const pick = e.target.closest("[data-buy-pick]");
  if (pick) {
    const wrap = pick.closest(".sugg-wrap");
    const key = wrap && wrap.dataset.suggKey;
    const s = findSuggestion(key);
    if (s) applyDecision(key, s, { source: "wordlist", name: pick.dataset.buyPick, note: "", verdict: "" });
  }
});

export function renderRecommendResult(data, autoAdd = true) {
  markStepDone(5);  // AI 推荐成功返回即视为完成（含"未推荐到模块"的空结果）
  if (data.topic_id) { currentTopicId = data.topic_id; }  // 粘贴题面被 AI 识别出编号时回填
  renderReferenceResult(data);  // 本次注入的参考资料（含来源标注）展示在第 3 步
  hydrateDecisions(data);  // 已定结论恢复（localStorage → suggestion.decision，工单 buy-discuss/05）
  const groups = data.exclusive_groups || [];  // 旧载荷无该键 = 无组卡（工单 04）
  if (autoAdd) {
    // autoAdd 同组去重（工单 recommend-exclusive-groups/04）：data.modules 逐个
    // 加入时，若该 slug 属某组且已选里已有同组任一成员 → 跳过（仅首个入集；
    // AI 的其它同组推荐仅以组卡徽标展示，不重复进已选）
    selectedSlugs = autoAddDedup(groups, selectedSlugs, data.modules);
    // 多实例回填（工单 module-multi-instance/06）：AI 猜的实例清单进 6.5 实例卡
    // （显示名/颜色，引脚恒空 = 自动分配）；用户确认后仍可增删改。载荷里带
    // 实例的模块 = 新猜测覆盖旧清单；AI 未猜（题面无明确数量）的模块保留用户
    // 已配清单——上限守卫是 expand_instances 的活（生成时拦），前端不截断
    if (data.instances) {
      clusterDeps.backfillInstances(data.instances);  // 回填实例清单（instances 属 B 簇 ui/generate-pins.js——工单 13 已迁）
    }
  }
  expanded = []; warnings = [];
  scorePoints = data.score_points || [];
  lastRecommend = data;  // 组卡渲染/冲突警告/单选交换共用（exclusive_groups 在此）
  renderSelected(); renderWarnings();
  const box = $("rec-list");
  const requirements = data.requirements || [];
  const scorePanel = renderScorePointPanel(scorePoints);
  const groupPanel = renderGroupCards(groups, data.modules, selectedSlugs);
  // 空结果分支（工单 recommend-covered-note/01）：本分支先于
  // recommendCoverageNote 执行——真实载荷下 data.modules 必覆盖所有
  // requirements[].modules 引用（:528 找 reason 同源），故「模块空 + 某需求
  // 命中」的病态组合不可达；早退后无库外建议也不显示覆盖提示（互斥设计）。
  if (!data.modules.length && !requirements.some((r) => (r.suggestions || []).length) && !groups.length) {
    box.innerHTML = scorePanel + '<div class="muted">AI 没有推荐任何模块——可到「模块库」页添加模块后重试。</div>';
    return;
  }
  box.innerHTML = scorePanel + groupPanel + requirements.map((r) => `
    <div class="item">
      <div class="head"><span class="slug">句子${r.sentence} · ${esc(r.requirement)}</span></div>
      <div class="rec-chips">
        ${r.modules.map((slug) => {
          const reason = (data.modules.find((m) => m.slug === slug) || {}).reason;
          return groupRequirementNote(groups, slug, reason) || recommendChip(slug, reason);
        }).join("") || '<span class="muted">库内无命中</span>'}
        ${(r.suggestions || []).map((s) => {
          const key = suggestionKey(s);
          let st = discussions.get(key);
          if (!st) { st = newDiscussionState(); discussions.set(key, st); }
          // 已定结论升格（hydrate 写回 s.decision / applyDecision 已写 st）：
          // 刷新 / 重推后从 localStorage 恢复的结论直接进交互态（徽标可见）
          if (!st.decision && s.decision && s.decision.name) st.decision = s.decision;
          return suggestionChipHTML(s, st);
        }).join("")}
      </div>
    </div>`).join("") + recommendCoverageNote(data);
  box.querySelectorAll("[data-remove]").forEach((b) =>
    b.addEventListener("click", () => {
      selectedSlugs = selectedSlugs.filter((s) => s !== b.dataset.remove);
      reRenderAfterSelectionChange();
    }));
  // 组卡单选交互（工单 04）：点击 radio → 换选（同组互斥）/ 再点已选 = 取消
  // 整组。用 click 而非 change——再点已选 radio 不触发 change（原生行为），
  // 取消整组会丢。
  box.querySelectorAll("[data-group-slug]").forEach((input) =>
    input.addEventListener("click", () => {
      selectedSlugs = applyGroupRadio((lastRecommend || {}).exclusive_groups || [],
        selectedSlugs, input.dataset.groupId, input.dataset.groupSlug);
      reRenderAfterSelectionChange();
    }));
  if (autoAdd && data.modules.length) runExpand();
}

function reRenderAfterSelectionChange() {
  // chip 移除 / 组卡单选共用：选择集变化后清空展开与警告、重绘已选/警告/推荐区
  // （照原 data-remove 回调尾段行为——重渲染推荐卡不 autoAdd，避免重复加入）
  expanded = []; warnings = [];
  renderSelected(); renderWarnings(); renderRecommendResult(lastRecommend, false);
}

function showRecommendError(message) {
  $("recommend-msg").textContent = message;
  $("btn-recommend").innerHTML = "让 AI 推荐";
  $("btn-recommend").disabled = false;
}

function showRecommendQuestions(problem, questions) {
  const box = $("rec-list");
  box.innerHTML = '<div class="warn-box" style="border:1px solid var(--border)">'
    + '<div class="muted">AI 拿不准，需要你确认（回答只用于澄清，不改写题面）：</div>'
    + questions.map((q, i) => '<div class="item" style="margin-top:6px">' + esc(q)
      + '<input id="recommend-answer-' + i + '" style="margin-top:4px;width:100%" placeholder="补充说明（可选）"></div>').join("")
    + '<div class="row" style="margin-top:8px"><button id="btn-recommend-answer" class="primary">补充回答并继续</button></div></div>';
  $("btn-recommend-answer").addEventListener("click", () => {
    // 回答进澄清历史（随请求体发送），题面保持原文——收敛判定依赖题面句子
    // 编号稳定，拼进题面会污染"两轮一致"对照（工单 01）
    questions.forEach((q, i) => {
      recommendClarifications.push({ question: q, answer: ($("recommend-answer-" + i).value || "").trim() });
    });
    startRecommend(problem);
  });
}

// 推荐进度面板实例（共享模块 makeProgressPanel）。生命周期 = 一次点击到
// done / question / error / 断线；词表镜像 events.py：round / converged /
// done / question / error（JS 侧单点声明，改词表须同步）。
function startRecProgress() {
  recPanel.start();
  $("rec-progress").classList.remove("hidden");
  $("rec-prog-text").textContent = "";        // 新生命周期：旧进度文本 / telemetry 清掉
  const telemetryEl = $("rec-llm-telemetry");
  telemetryEl.classList.add("hidden");
  telemetryEl.textContent = "";
  $("rec-bar").classList.add("hidden");   // 首条 round 事件带 round_total 后再显示条
  $("rec-bar-fill").style.width = "0";    // 补问回答重启 = 新生命周期，条从第 1 轮重新开始
}

function stopRecProgress() {   // 流未起 / 断线路径：停表 + 收起面板（终态路径由事件表 finish）
  recPanel.finish();
  $("rec-progress").classList.add("hidden");
}

export async function startRecommend(problem) {
  recProblem = problem;   // 补问回答重启时仍走同一实例（同一生命周期语义）
  scorePoints = [];       // 新推荐生命周期开始，避免旧题评分点串进生成 / 交接
  discussions.clear();    // 讨论态随新生命周期清空（已定结论经 localStorage 恢复）
  $("recommend-msg").textContent = "";
  $("btn-recommend").disabled = true;
  $("btn-recommend").innerHTML = '<span class="spinner"></span>AI 思考中…';
  $("rec-list").innerHTML = "";   // 旧结果清空，状态文本进进度面板
  startRecProgress();
  let resp;
  try {
    resp = await fetch("/api/recommend", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ problem_text: problem, topic_id: currentTopicId || undefined, reference_ids: selectedReferenceIds, clarifications: recommendClarifications, platform: chosenPlatform || undefined, qa_text: $("qa-text").value.trim() }),
    });
  } catch (e) { stopRecProgress(); showRecommendError(e.message); return; }
  if (!resp.body) { stopRecProgress(); showRecommendError("服务响应无流"); return; }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    stopRecProgress();
    showRecommendError(err.detail || ("请求失败（HTTP " + resp.status + "）"));
    return;
  }
  try {
    await parseSSE(resp, recPanel.handleEvent);
  } catch (e) { if (recPanel.p.finished) return; }   // 终态已到后的读流出错忽略，防重复提示
  if (!recPanel.p.finished) {   // 流结束 / 读流出错但没等到终态 = 断线：推荐不落任何东西，可安全重试
    stopRecProgress();
    showRecommendError("连接中断：本次推荐未完成，可安全重试");
  }
}

const recPanel = makeProgressPanel({
  timerTotalId: "rec-timer-total",
  timerCallId: "rec-timer-round",
  totalLabel: "总用时 ",
  callLabel: "当前轮已等待 ",
  events: {
    round: (ev) => {
      $("rec-prog-text").textContent = "AI 收敛自检：第 " + ev.round + "/" + ev.round_total + " 轮…";
      $("rec-bar").classList.remove("hidden");
      $("rec-bar-fill").style.width = (ev.round_total ? Math.min(100, ev.round * 100 / ev.round_total) : 100) + "%";
    },
    converged: (ev) => {
      $("rec-prog-text").textContent = "功能需求层已收敛（第 " + ev.round + " 轮）…";
      $("rec-bar").classList.remove("hidden");
      $("rec-bar-fill").style.width = "100%";   // round_total 是上限非保证：提前收敛就跳满
    },
    cache_hit: (ev) => {
      // 推荐缓存命中（工单 llm-cost-control/02）：直出上次结果，不调 LLM
      $("rec-prog-text").textContent = (ev.warns && ev.warns.length)
        ? "⚠ 复用本地推荐缓存，但输入与缓存时不同：" + ev.warns.join("；")
        : "复用本地推荐缓存（题面 / 平台未变）…";
      $("rec-bar").classList.remove("hidden");
      $("rec-bar-fill").style.width = "100%";
    },
    llm_telemetry: (ev) => {
      // 每次 LLM 调用完成的观测快照（照修复流程 telemetry 先例）：调用数 /
      // provider 分流 / 最新 operation / 耗时——模型调用期间"AI 正在干什么"
      const el = $("rec-llm-telemetry");
      el.textContent = formatLLMTelemetry(ev);
      el.classList.remove("hidden");
      recordLLMUsage(ev);
    },
    done: (ev) => {
      recPanel.finish();
      $("rec-progress").classList.add("hidden");
      renderRecommendResult(ev);
      $("btn-recommend").innerHTML = "重新推荐";
      $("btn-recommend").disabled = false;
    },
    question: (ev) => {
      recPanel.finish();
      $("rec-progress").classList.add("hidden");
      $("btn-recommend").innerHTML = "让 AI 推荐";
      $("btn-recommend").disabled = false;
      showRecommendQuestions(recProblem, ev.questions || []);
    },
    error: (ev) => {
      recPanel.finish();
      $("rec-progress").classList.add("hidden");
      showRecommendError(ev.message || "推荐失败");
    },
  },
});

$("btn-recommend").addEventListener("click", () => {
  const problem = $("problem").value.trim();
  if (!problem) { $("recommend-msg").textContent = "请先填写赛题原文"; return; }
  recommendClarifications = [];   // 手动重推 = 新生命周期，清空澄清历史
  startRecommend(problem);
});

// ---------------------------------------------------------------------------
// 生成页：3. 参考资料（可选）——手动勾选 = 追加准入 + 全文直读（工单 01）
// ---------------------------------------------------------------------------
function referenceAnchorLabel(e) {
  if (e.anchor_kind === "topic") return "赛题 " + esc(e.anchor_value) + " 关联";
  if (e.anchor_kind === "kit") return "套件 " + esc(e.anchor_value) + " 关联";
  return "未关联";
}

export async function loadReferencePicker() {
  try {
    referenceEntries = await apiGet("/api/references");
    renderReferencePicker();
    $("ref-picker-msg").textContent = "";
  } catch (e) { $("ref-picker-msg").textContent = e.message; }
}

function renderReferencePicker() {
  const q = ($("ref-search").value || "").trim().toLowerCase();
  const visible = referenceEntries.filter((e) =>
    !q || (e.id + " " + (e.title || "") + " " + (e.description || "") + " " + referenceAnchorLabel(e)).toLowerCase().includes(q));
  $("ref-count").textContent = referenceEntries.length
    ? (q ? `匹配 ${visible.length} / ${referenceEntries.length} 条` : `共 ${referenceEntries.length} 条`)
    : "";
  $("ref-picker").innerHTML = visible.length
    ? '<div class="ref-pick-head"><span></span><span>资料</span><span>平台</span><span>说明</span></div>'
      + visible.map((e) => {
          const isAuto = autoReferenceIds.includes(e.id);
          const isManual = selectedReferenceIds.includes(e.id);
          const checked = isAuto || isManual ? "checked" : "";
          const disabled = isAuto ? "disabled" : "";
          const autoChip = isAuto ? ' <span class="chip out">自动</span>' : "";
          return `
    <label class="ref-pick-row">
      <input type="checkbox" data-ref-pick="${esc(e.id)}" ${checked} ${disabled}>
      <span class="ref-pick-title" title="${esc(e.title)}">${esc(e.title)}</span>
      <span>${referencePlatformChip(e)}${autoChip}</span>
      <span class="ref-pick-desc" title="${esc(referenceAnchorLabel(e) + (e.description ? " · " + e.description : ""))}">${referenceAnchorLabel(e)}${e.description ? " · " + esc(e.description) : ""}</span>
    </label>`;
        }).join("")
    : (referenceEntries.length
      ? '<div class="muted">没有匹配的资料。</div>'
      : '<div class="muted">参考文件库为空——可到「参考文件库」页录入资料。</div>');
  $("ref-picker").querySelectorAll("[data-ref-pick]").forEach((cb) =>
    cb.addEventListener("change", () => {
      const id = cb.dataset.refPick;
      selectedReferenceIds = selectedReferenceIds.filter((x) => x !== id);
      if (cb.checked) selectedReferenceIds.push(id);
      renderRefSelected();
      syncStep4(selectedReferenceIds, autoReferenceIds, markStepDone, markStepUndone);  // 勾选变更 = 参考资料集合变化，重算步骤 4 完成状态
    }));
  renderRefSelected();
}

$("ref-search").addEventListener("input", renderReferencePicker);

function renderRefSelected() {
  const box = $("ref-selected");
  const byId = new Map(referenceEntries.map((e) => [e.id, e]));
  const selected = [];
  for (const id of selectedReferenceIds) {
    const e = byId.get(id);
    selected.push({ id, title: e ? e.title : id, source: "手动" });
  }
  for (const id of autoReferenceIds) {
    if (selectedReferenceIds.includes(id)) continue;  // 手动也勾了 = 只显示手动
    const e = byId.get(id);
    selected.push({ id, title: e ? e.title : id, source: "自动" });
  }
  box.innerHTML = selected.length
    ? '<div class="muted" style="margin-bottom:4px">已选中（将注入 AI 上下文）：</div>'
      + selected.map((s) =>
          `<span class="chip out" title="${esc(s.id)}">✔ ${esc(s.title)} · ${s.source}</span>`).join(" ")
    : '<div class="muted">尚未选中参考资料（AI 推荐后会自动关联赛题 / 套件资料）。</div>';
}

function renderReferenceResult(data) {
  const refs = data.references || [];
  autoReferenceIds = refs.filter((r) => r.source !== "manual").map((r) => r.id);
  renderReferencePicker();
  renderRefSelected();
  syncStep4(selectedReferenceIds, autoReferenceIds, markStepDone, markStepUndone);  // 推荐自动关联后重算步骤 4（无自动关联也不取消手动勾选）
}

// ---------------------------------------------------------------------------
// 生成页：5. 模块清单（增删 + 依赖展开 + 平台警告）
// ---------------------------------------------------------------------------
export function renderModulePool() {
  const box = $("module-grid");
  if (!box) return;
  const q = ($("module-search") ? $("module-search").value : "") || "";
  box.innerHTML = moduleGridHTML(state.modules || [], selectedSlugs, q, chosenPlatform);
  const count = $("module-count");
  if (count) count.textContent = moduleGridCountText(state.modules || [], selectedSlugs, q);
}

export function openModuleInfo(slug, platform = chosenPlatform) {
  const module = (state.modules || []).find((mo) => mo.slug === slug);
  if (!module) { toast("info", "未找到模块 " + slug); return; }
  // 重复打开 = 替换（同 showPinMenu 先例）
  document.querySelectorAll(".module-info-overlay").forEach((o) => o.remove());
  const overlay = document.createElement("div");
  overlay.className = "module-info-overlay";
  const modal = document.createElement("div");
  modal.className = "module-info-modal";
  modal.innerHTML = '<div class="module-info-head"><strong>模块详情</strong>'
    + '<button class="ref-files-close" title="关闭">×</button></div>'
    + '<div class="module-info-scroll">' + moduleInfoHTML(module, platform) + "</div>";
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  modal.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
}

function initModuleGrid() {
  const box = $("module-grid");
  if (!box) return;
  box.addEventListener("click", (ev) => {
    // 详情按钮优先（工单 module-info-dialog/01）：先判 .mc-info，卡片本体仍添加模块
    const infoBtn = ev.target.closest ? ev.target.closest(".mc-info") : null;
    if (infoBtn) { openModuleInfo(infoBtn.dataset.info); return; }
    const card = ev.target.closest ? ev.target.closest(".module-card") : null;
    if (!card) return;
    const slug = card.dataset.add;
    if (!slug) return;
    if (card.classList.contains("off")) {
      toast("info", "该模块不支持当前平台，请先切换目标平台");
      return;
    }
    addModule(slug);
  });
}

function addModule(slug) {
  if (!slug || selectedSlugs.includes(slug)) return;
  selectedSlugs.push(slug);
  expanded = []; warnings = [];
  renderSelected(); renderWarnings(); renderModulePool();
  runExpand();  // 添加后直接展开，步骤 7 立即可配置引脚
}

async function runExpand() {
  $("expand-msg").textContent = "";
  if (!chosenPlatform) { $("expand-msg").textContent = "请先在步骤 3 选择目标平台"; return; }
  if (!selectedSlugs.length) { $("expand-msg").textContent = "请先选择至少一个模块"; return; }
  try {
    const data = await apiPost("/api/selection/expand", { slugs: selectedSlugs, platform: chosenPlatform });
    expanded = data.modules;
    warnings = data.warnings;
    renderSelected(); renderWarnings();
    clusterDeps.renderPinCard();  // 引脚配置卡（工单 03）：角色清单随展开结果重算
    clusterDeps.renderInstanceConfig();  // 多实例配置卡（工单 04）：随展开结果重算
  } catch (e) { $("expand-msg").textContent = e.message; }
}

$("btn-expand").addEventListener("click", runExpand);

$("module-search").addEventListener("input", renderModulePool);

initModuleGrid();

export function renderSelected() {
  const box = $("selected-list");
  if (selectedSlugs.length) markStepDone(6); else markStepUndone(6);
  clusterDeps.scheduleDraftSave();
  if (!expanded.length) {
    $("selected-count").textContent = "";
    box.innerHTML = selectedSlugs.length
      ? '<div class="muted">已选（未展开依赖）：' + selectedSlugs.map(esc).join("、") + '</div>'
      : '<div class="muted">尚未选择模块。</div>';
    return;
  }
  const depCount = expanded.filter((m) => !selectedSlugs.includes(m.slug)).length;
  $("selected-count").textContent = `已展开 ${expanded.length} 个模块（含 ${depCount} 个自动带入）`;
  const notes = (m) => Object.entries(m.platforms || {}).map(([platform, entry]) =>
    entry.notes ? `【${platform} 配置】${entry.notes}` : "").filter(Boolean).join(" ");
  const bringers = new Map();
  for (const m of expanded) {
    if (!selectedSlugs.includes(m.slug)) continue;
    for (const dep of (m.dependencies || [])) bringers.set(dep, m.slug);
  }
  // 副产物模板下拉（工单 k230-multi-template/04）：多模板模块（k230）显示，
  // 选项 = manifest.python_artifact.templates（name + description 提示）；
  // 改动 ≠ 默认才记进 pythonTemplates（缺省 = 不发字段 = 旧行为逐字节不变）
  const templateSelect = (m) => {
    const pa = m.python_artifact;
    if (!pa || !pa.templates || pa.templates.length < 2) return "";
    const current = pythonTemplates[m.slug] || pa.default;
    const options = pa.templates.map((t) =>
      `<option value="${esc(t.id)}" ${t.id === current ? "selected" : ""}>${esc(t.name || t.id)}</option>`).join("");
    const hints = pa.templates.map((t) => `${t.name || t.id}：${t.description || ""}`).join("\n");
    return `
      <div class="row" style="margin:6px 0 0;align-items:center;gap:6px">
        <label style="font-size:12px;color:var(--muted)">副产物模板</label>
        <select data-template="${esc(m.slug)}" title="${esc(hints)}" style="font-size:12px;max-width:260px">${options}</select>
      </div>`;
  };
  box.innerHTML = expanded.map((m) => {
    const isDep = !selectedSlugs.includes(m.slug);
    const bringer = bringers.get(m.slug);
    return `
    <div class="item">
      <div class="head" title="${esc((m.description || "") + " " + notes(m))}">
        <span class="slug">${esc(m.slug)}</span>
        ${isDep ? `<span class="badge dep" title="由 ${esc(bringer || "其它模块")} 依赖带入">自动带入${bringer ? "·" + esc(bringer) : ""}</span>` : ""}
        ${moduleBadges(m)}
        ${isDep ? "" : `<button class="danger" data-remove="${esc(m.slug)}">移除</button>`}
      </div>
      <div class="desc" title="${esc((m.description || "") + " " + notes(m))}">${esc(m.description || "")}${(m.dependencies || []).length ? ` · 依赖：${esc(m.dependencies.join("、"))}` : ""}</div>
      ${isDep ? "" : templateSelect(m)}
    </div>`;
  }).join("");
  box.querySelectorAll("[data-remove]").forEach((b) =>
    b.addEventListener("click", () => {
      selectedSlugs = selectedSlugs.filter((s) => s !== b.dataset.remove);
      expanded = []; warnings = [];
      delete pythonTemplates[b.dataset.remove];  // 模板选择随模块移除清理（工单 04）
      clusterDeps.clearInstanceTarget();  // 选脚目标随清单变化失效（工单 04）
      renderSelected(); renderWarnings(); renderModulePool();
      clusterDeps.renderPinCard();  // 引脚配置卡（工单 03）：清单变化后回到占位态
      clusterDeps.renderInstanceConfig();  // 多实例配置卡（工单 04）：被移除模块的实例清单随之清掉
    }));
  box.querySelectorAll("[data-template]").forEach((sel) =>
    sel.addEventListener("change", () => {
      const slug = sel.dataset.template;
      const pa = expanded.find((m) => m.slug === slug)?.python_artifact;
      if (sel.value === (pa && pa.default)) delete pythonTemplates[slug];
      else pythonTemplates[slug] = sel.value;
    }));
}

export function renderWarnings() {
  const box = $("warnings");
  box.innerHTML = "";
  // 功能组冲突警告（工单 recommend-exclusive-groups/04）：selectedSlugs 同组
  // ≥2 成员 → 黄字警告（共用同一硬件，建议只留一个）；不硬拦（用户选择权）。
  // 与平台警告并列展示，仍在时不影响平台警告/绿 OK 框逻辑。
  const groupIssues = groupConflicts((lastRecommend || {}).exclusive_groups || [], selectedSlugs);
  for (const issue of groupIssues) {
    const div = document.createElement("div");
    div.className = "warn-box group";
    div.textContent = "[功能组冲突] 同属一组「" + issue.label + "」共用同一硬件，建议只留一个（已选：" + issue.slugs.join("、") + "）";
    box.appendChild(div);
  }
  if (!warnings.length) {
    if (expanded.length && !groupIssues.length) box.innerHTML = '<div class="warn-box ok">所选模块在该平台均可直接用。</div>';
    return;
  }
  for (const w of warnings) {
    const div = document.createElement("div");
    div.className = "warn-box " + w.kind;
    div.textContent = "[" + KIND_TEXT[w.kind] + "] " + w.message;
    box.appendChild(div);
  }
}

// ---------------------------------------------------------------------------
// 赛题库「用此题生成」（topic 簇使用）：取题面 → 填生成页 → 步 1 完成 →
// 切 tab + 滚顶。与 btn-topic-load 同端点、同失效语义（clearTopicPreread 清下游）
// ---------------------------------------------------------------------------
export async function useTopic(key) {
  try {
    const data = await handle(await fetch("/api/topics/" + encodeURIComponent(key)));
    $("problem").value = data.problem_text;
    currentTopicId = data.key;
    clearTopicPreread();
    markStepDone(1);
    toast("ok", "已载入赛题 " + data.key);
    document.querySelector('[data-tab="generate"]').click();
    window.scrollTo({ top: 0, behavior: "smooth" });
    loadTopicPdf(data.key);
  } catch (e) {
    toast("error", "载入赛题失败");
    $("topic-browse-msg").textContent = e.message;
  }
}
