// ui/master.js — 母版页 + 更新记录 DOM 胶水（阶段 2 工单 04）
//
// 母版 tab 全部胶水：扫描 / 整夹暂存 / 提炼进度面板实例（distPanel，共享
// 工厂在 ui/progress.js）/ 报告渲染 / 报告确认入库 / 母版库表格与详情弹窗 /
// 删除确认 / 更新记录。纯件在 fx/master.js（masterTableRowHTML 等表格行 /
// 判定行 / 归档行 / URL / 详情 HTML），本模块只做 DOM 转发与事件接线。
// 顶层 addEventListener（btn-pick-dirs / pick-dirs / btn-scan / prog-log-head /
// btn-distill / btn-confirm / btn-usage-reset）在 import 时绑定——module
// 脚本延迟执行，DOM 已就绪（与 stage 1 桥接约定同理）。
import { $, handle, apiGet, apiPost, apiDelete, toast } from "/js/app.js";
import { makeProgressPanel } from "/js/ui/progress.js";
import { esc, fmtDuration } from "/js/fx/core.js";
import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { masterTableRowHTML, masterDeleteConfirmHTML, masterFileURL, masterDetailHTML, decisionItem, archiveItem, masterTreeFileURL, buildMasterTree, masterTreeNodeHTML, masterContentHTML } from "/js/fx/master.js";

let scannedProjects = null;   // 扫描结果（含报告确认所需）
let currentReport = null;
let stagedDirs = [];   // 「选择文件夹」整夹上传的暂存工程：{path, name}（浏览器不暴露绝对路径，只能整夹上传）

function projectDirs() {
  const typed = $("project-dirs").value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  return [...typed, ...stagedDirs.map((d) => d.path)];
}

function renderStagedDirs() {
  $("staged-dirs").innerHTML = stagedDirs.map((d) => `
    <div class="item"><span class="slug">${esc(d.name)}</span>
      <span class="muted">${esc(d.path)}</span>
      <button data-remove="${esc(d.path)}" class="danger" style="padding:2px 8px">移除</button></div>`).join("");
  $("staged-dirs").querySelectorAll("[data-remove]").forEach((b) =>
    b.addEventListener("click", () => {
      stagedDirs = stagedDirs.filter((d) => d.path !== b.dataset.remove);
      renderStagedDirs();
      $("scan-result").innerHTML = "";   // 工程列表变了，旧扫描结果作废
      $("btn-distill").disabled = true;
    }));
}

$("btn-pick-dirs").addEventListener("click", () => $("pick-dirs").click());
$("pick-dirs").addEventListener("change", async () => {
  const input = $("pick-dirs");
  const files = Array.from(input.files).filter((f) => {
    const parts = f.webkitRelativePath.split("/");
    return parts.length > 1 && !parts.includes(".git");
  });
  input.value = "";
  if (!files.length) return;
  $("scan-msg").classList.remove("ok");
  $("scan-msg").textContent = "";
  $("scan-result").innerHTML = "";
  const form = new FormData();
  for (const f of files) form.append("files", f, f.webkitRelativePath);
  $("btn-pick-dirs").disabled = true;
  try {
    const data = await handle(await fetch("/api/masters/stage", { method: "POST", body: form }));
    for (const s of data.staged) if (!stagedDirs.some((d) => d.path === s.path)) stagedDirs.push(s);
    renderStagedDirs();
    $("scan-msg").classList.add("ok");
    $("scan-msg").textContent = "已导入 " + data.staged.length + " 个文件夹（" + files.length
      + " 个文件），点「扫描工程」继续";
  } catch (e) {
    $("scan-msg").classList.remove("ok");
    $("scan-msg").textContent = e.message;
  } finally { $("btn-pick-dirs").disabled = false; }
});

$("btn-scan").addEventListener("click", async () => {
  $("scan-msg").classList.remove("ok");
  $("scan-msg").textContent = "";
  $("report").classList.add("hidden");
  $("distill-progress").classList.add("hidden");   // 重新扫描 = 新的提炼上下文，收起旧进度
  const dirs = projectDirs();
  if (!dirs.length) { $("scan-msg").textContent = "请先选择或填写至少一个旧工程目录"; return; }
  try {
    scannedProjects = await apiPost("/api/masters/scan", { project_dirs: dirs });
    $("scan-result").innerHTML = scannedProjects.map((p) => `
      <div class="item"><div class="head">
        <span class="slug">${esc(p.name)}</span>
        <span class="muted">平台：${esc(p.platform)}</span>
        <span class="muted">${p.files.length} 个文件</span>
      </div>
      <div class="reason">${esc(p.config_summary.join("；") || "无配置摘要")}</div></div>`).join("");
    $("btn-distill").disabled = false;
  } catch (e) { $("scan-msg").textContent = e.message; }
});

// 提炼进度面板实例（共享工厂 makeProgressPanel 在 ui/progress.js）。
// 生命周期 = 一次点击到 done / error / 断线；词表镜像 events.py：
// start / batch_start / batch_done / retry / phase_done / done / error。
// 流程自己的展示状态（phase / 批号 / 累计 / 日志计数）挂在 distPanel.p 上，
// 模块只管计时 / 心跳 / 分发。
const PHASE_LABEL = { summary: "摘要", decide: "判定" };
const MAX_LOG_LINES = 300;   // 日志上限：超出丢最旧，不撑爆页面
const distPanel = makeProgressPanel({
  timerTotalId: "prog-timer-total",
  timerCallId: "prog-timer-call",
  totalLabel: "总用时 ",
  callLabel: "当前调用已等待 ",
  events: {
    start: (data) => {
      const p = distPanel.p;
      p.judgmentCount = data.judgment_count || 0;
      p.phaseTotal.summary = p.phaseTotal.decide = p.judgmentCount;
      setStep(0, "done");
      addLogLine("", "开始：待判文件 " + p.judgmentCount + " 份（摘要 "
        + (data.summary_batch_count || 0) + " 批 / 判定 " + (data.decide_batch_count || 0) + " 批）");
    },
    batch_start: (data) => {
      const p = distPanel.p;
      if (p.phase && p.phase !== data.phase) p.processed = 0;   // 阶段切换：阶段内计数归零
      p.phase = data.phase;
      p.batchIndex = data.batch_index;
      p.batchCount = data.batch_count;
      setStep(data.phase === "decide" ? 2 : 1, "active");
      $("prog-badge").classList.add("hidden");
      addBatchLine(data);
      updateBatch();
    },
    batch_done: (data) => {
      distPanel.p.processed = data.processed_count || 0;
      $("prog-badge").classList.add("hidden");
      addLogLine("", (PHASE_LABEL[data.phase] || data.phase) + " 第 " + data.batch_index + "/"
        + (distPanel.p.batchCount || data.batch_index) + " 批完成（累计已读 " + distPanel.p.processed + " 份）");
      updateBatch();
    },
    retry: (data) => {
      $("prog-badge").classList.remove("hidden");
      $("prog-badge").textContent = "批 " + data.batch_index + " 补问中";
      addLogLine("", "批 " + data.batch_index + " 补问：第 " + (data.retry_round || 1) + " 轮，缺失 "
        + (data.missing_count || 0) + " 份");
    },
    phase_done: (data) => {
      setStep(data.phase === "decide" ? 2 : 1, "done");
      addLogLine("", (PHASE_LABEL[data.phase] || data.phase) + " 阶段完成，共 "
        + (data.file_count || 0) + " 份");
    },
    llm_telemetry: (data) => {
      // 每次 LLM 调用完成的观测快照（照修复 / 推荐流程先例）：调用数 /
      // provider 分流 / 最新 operation / 耗时——批次间"AI 正在干什么"
      const el = $("prog-llm-telemetry");
      el.textContent = formatLLMTelemetry(data);
      el.classList.remove("hidden");
      recordLLMUsage(data);
    },
    done: (data) => finishProgress(data),   // data = 完整提炼报告（与现状响应同构，原样渲染）
    error: (data) => failProgress(data.message || "提炼失败"),
  },
});

function setStep(n, state) {   // n = 步号（0 开始…3 完成）；state = "active" | "done"
  const steps = document.querySelectorAll("#prog-stepper .step");
  const conns = document.querySelectorAll("#prog-stepper .connector");
  steps.forEach((el, i) => {
    el.classList.remove("done", "active");
    el.querySelector(".dot").textContent = i < n ? "✓" : String(i + 1);
    if (i < n) el.classList.add("done");
    else if (i === n) el.classList.add(state);
  });
  conns.forEach((el, i) => el.classList.toggle("done", i < n));
}

function updateBatch() {
  const p = distPanel.p;
  if (p.phase && p.batchIndex) {
    $("prog-batch-text").textContent =
      (PHASE_LABEL[p.phase] || p.phase) + " 第 " + p.batchIndex + "/" + p.batchCount
      + " 批 · 已读 " + p.processed + "/" + (p.phaseTotal[p.phase] || p.processed);
    $("prog-bar").classList.remove("hidden");
    const total = p.phaseTotal[p.phase];
    $("prog-bar-fill").style.width = (total ? Math.min(100, p.processed * 100 / total) : 100) + "%";
  } else {
    $("prog-batch-text").textContent = "";
    $("prog-bar").classList.add("hidden");
  }
}

function addLogLine(cls, text) {
  const div = document.createElement("div");
  div.className = "line" + (cls ? " " + cls : "");
  const t = new Date();
  div.innerHTML = '<span class="t">' + String(t.getHours()).padStart(2, "0") + ":"
    + String(t.getMinutes()).padStart(2, "0") + ":" + String(t.getSeconds()).padStart(2, "0")
    + "</span>" + esc(text);
  const log = $("prog-log");
  log.appendChild(div);
  while (log.childElementCount > MAX_LOG_LINES) log.firstElementChild.remove();
  distPanel.p.logCount++;
  $("prog-log-count").textContent = "（" + distPanel.p.logCount + " 条）";
  log.scrollTop = log.scrollHeight;
}

function addBatchLine(ev) {
  const div = document.createElement("div");
  div.className = "line batch";
  const t = new Date();
  const label = (PHASE_LABEL[ev.phase] || ev.phase) + " 第 " + ev.batch_index + "/" + ev.batch_count
    + " 批开始";
  div.innerHTML = '<span class="t">' + String(t.getHours()).padStart(2, "0") + ":"
    + String(t.getMinutes()).padStart(2, "0") + ":" + String(t.getSeconds()).padStart(2, "0")
    + "</span>" + esc(label) + '<span class="muted">（' + ev.paths.length + ' 个文件）</span>'
    + '<span class="muted" data-toggle>[展开]</span>';
  const list = document.createElement("div");
  list.className = "file-list hidden";
  list.textContent = ev.paths.join("\n");
  div.addEventListener("click", () => {
    const open = list.classList.toggle("hidden");
    div.querySelector("[data-toggle]").textContent = open ? "[展开]" : "[收起]";
  });
  const log = $("prog-log");
  log.appendChild(div);
  log.appendChild(list);
  distPanel.p.logCount++;
  $("prog-log-count").textContent = "（" + distPanel.p.logCount + " 条）";
  log.scrollTop = log.scrollHeight;
}

$("prog-log-head").addEventListener("click", () => {
  const log = $("prog-log");
  $("prog-log-caret").textContent = log.classList.toggle("hidden") ? "▾" : "▸";
});

function startProgress() {
  distPanel.start();   // 计时归零 + 秒表跳起（自动清旧定时器，防双击）
  const p = distPanel.p;
  p.judgmentCount = 0;
  p.phaseTotal = { summary: 0, decide: 0 };   // 两阶段文件总数 = 待判文件数
  p.phase = ""; p.batchIndex = 0; p.batchCount = 0; p.processed = 0;
  p.logCount = 0;
  $("distill-progress").classList.remove("hidden");
  $("prog-done").classList.add("hidden");
  $("prog-body").classList.remove("hidden");
  $("prog-log").innerHTML = "";
  const telemetryEl = $("prog-llm-telemetry");   // 新生命周期：旧 telemetry 清掉
  telemetryEl.classList.add("hidden");
  telemetryEl.textContent = "";
  $("prog-log").classList.remove("hidden");
  $("prog-log-caret").textContent = "▾";
  $("prog-log-count").textContent = "";
  $("prog-badge").classList.add("hidden");
  setStep(0, "active");
  updateBatch();
}

function finishProgress(report) {
  distPanel.finish();
  setStep(3, "done");
  $("prog-body").classList.add("hidden");   // 完成态折叠为一行
  $("prog-done").classList.remove("hidden");
  $("prog-done").textContent = "提炼完成，用时 " + fmtDuration((Date.now() - distPanel.p.startedAt) / 1000);
  currentReport = report;
  currentReport.archive = report.archive || [];   // AI 出稿报告无 archive 键（动作由用户在确认时指定）
  renderReport();
}

function failProgress(message) {
  distPanel.finish();
  addLogLine("error", message);
  $("prog-log").classList.remove("hidden");   // 失败态：日志保留且展开，红行可见
  $("prog-log-caret").textContent = "▾";
  distPanel.tick();   // 计时器停在最后读数
}

$("btn-distill").addEventListener("click", async () => {
  $("distill-msg").textContent = "";
  $("btn-distill").disabled = true;   // 进度区替代按钮静态转圈
  startProgress();
  try {
    const dirs = projectDirs();
    const platform = scannedProjects[0].platform;
    const resp = await fetch("/api/masters/distill", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, project_dirs: dirs }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || ("请求失败（HTTP " + resp.status + "）"));
    }
    await parseSSE(resp, distPanel.handleEvent);
    if (!distPanel.p.finished) {   // 流结束但没等到 done / error = 断线：放弃本次，刷新安全重试
      failProgress("连接中断：本次提炼未完成（确认前不落任何东西），刷新页面后可安全重试");
    }
  } catch (e) {
    if (!distPanel.p.finished) failProgress(e.message);
  } finally {
    $("btn-distill").disabled = false;
    $("btn-distill").textContent = "重新提炼";
  }
});

function renderReport() {
  $("report").classList.remove("hidden");
  const r = currentReport;
  const body = $("report-body");
  const options = r.projects;
  const archive = r.archive || [];
  body.innerHTML = `
    <div class="report-group keep"><div class="title">保留（${r.keep.length}）</div>
      ${r.keep.map((d) => decisionItem(d)).join("")}</div>
    <div class="report-group merge"><div class="title">合并 — 选来源工程（${r.merge.length}）</div>
      ${r.merge.map((d) => decisionItem(d, options)).join("")}</div>
    <div class="report-group exclude"><div class="title">剔除（${r.exclude.length}）</div>
      ${r.exclude.map((d) => decisionItem(d)).join("")}</div>
    <div class="report-group archive"><div class="title">归档为该题参考文件（${archive.length}）<span class="muted">确认时复制入库参考文件库、锚定赛题编号，该文件不进母版</span></div>
      ${archive.length ? archive.map((a) => archiveItem(a)).join("") : ""}</div>`;
  body.querySelectorAll("select[data-path]").forEach((sel) =>
    sel.addEventListener("change", () => {
      const d = currentReport.merge.find((x) => x.path === sel.dataset.path);
      if (d) d.source = sel.value;
    }));
  // 归档动作（工单 02）：点「归档」把该判定移入 archive 段（不进母版、确认时复制入库）；
  // 移除归档回原判定组；锚定赛题编号由用户填（格式 / 词表校验在确认时后端做）
  body.querySelectorAll("[data-archive]").forEach((b) =>
    b.addEventListener("click", () => {
      const path = b.dataset.archive;
      const group = [r.keep, r.merge, r.exclude].find((g) => g.some((d) => d.path === path));
      const d = group && group.find((x) => x.path === path);
      if (!group || !d) return;
      group.splice(group.indexOf(d), 1);
      r.archive.push({ path: d.path, topic: "", reason: d.reason, _decision: d, _origin: group });
      renderReport();
    }));
  body.querySelectorAll("input[data-topic]").forEach((inp) =>
    inp.addEventListener("input", () => {
      const a = r.archive.find((x) => x.path === inp.dataset.topic);
      if (a) a.topic = inp.value.trim();
    }));
  body.querySelectorAll("[data-unarchive]").forEach((b) =>
    b.addEventListener("click", () => {
      const a = r.archive.find((x) => x.path === b.dataset.unarchive);
      if (!a) return;
      r.archive = r.archive.filter((x) => x !== a);
      (a._origin || r.exclude).push(a._decision || {
        path: a.path, action: "exclude", reason: a.reason,
      });
      renderReport();
    }));
}

$("btn-confirm").addEventListener("click", async () => {
  $("confirm-msg").textContent = "";
  if (!currentReport) return;
  const archiveCount = (currentReport.archive || []).length;
  const suffix = archiveCount
    ? "\n另有 " + archiveCount + " 条归档动作：复制入库参考文件库并锚定赛题编号（需 AI 服务，失败可去掉归档后重试）。"
    : "";
  if (!confirm("确认按此报告提炼母版并入库？（将整体替换该平台的旧母版）" + suffix)) return;
  $("btn-confirm").disabled = true;
  $("confirm-status").innerHTML = '<span class="spinner"></span>落盘与入库中…';
  try {
    const data = await apiPost("/api/masters/confirm", {
      platform: currentReport.platform,
      project_dirs: projectDirs(),
      projects: currentReport.projects,
      keep: currentReport.keep, merge: currentReport.merge, exclude: currentReport.exclude,
      // 归档动作（工单 02）：只透传 path / topic / reason 契约字段，内部标记不进载荷
      archive: (currentReport.archive || []).map((a) => ({ path: a.path, topic: a.topic, reason: a.reason })),
    });
    $("confirm-status").textContent = "";
    $("confirm-msg").classList.add("ok");
    $("confirm-msg").textContent = "母版已入库：平台 " + data.platform + "（来源：" + data.sources.join("、") + "）"
      + (data.warnings.length ? "，警告：" + data.warnings.join("；") : "");
    $("report").classList.add("hidden");
    loadMasters();
  } catch (e) {
    $("confirm-msg").classList.remove("ok");
    $("confirm-msg").textContent = e.message;
    $("confirm-status").textContent = "";  // 失败也要清掉"落盘与入库中"，不留进行中假象
  } finally { $("btn-confirm").disabled = false; }
});

// ===== 母版库表格（工单 master-library-ui/03）：增强行渲染 + 删除确认弹窗 =====
// 交互逻辑下沉纯函数（extract 范式对偶 pdf* / ref* 系列），DOM 层只转发。
// 纯件（masterTableRowHTML / masterDeleteConfirmHTML）在 fx/master.js。

let masterCache = [];

// openMasterDeleteConfirm(platform)：删除确认弹窗（对偶 pdf 轮 trash 确认：
// 复用 .ref-files-overlay 遮罩 + Esc / × / 点遮罩关闭；确认 → 既有 DELETE
// 端点 → toast + 重拉列表；失败 = 弹窗保留 + toast 错误，可重试或取消）。
function openMasterDeleteConfirm(platform) {
  const m = (masterCache || []).find((x) => x.platform === platform);
  if (!m) { toast("info", "未找到平台 " + platform + "（列表可能已刷新）"); return; }
  document.querySelectorAll(".ref-files-overlay").forEach((o) => o.remove());
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  overlay.innerHTML = `<div class="ref-files-modal">
    <div class="ref-files-head"><strong>删除母版？</strong><button class="ref-files-close" title="关闭">×</button></div>
    <div class="ref-detail-scroll">${masterDeleteConfirmHTML(m)}</div>
  </div>`;
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  overlay.querySelector("[data-master-del-cancel]").addEventListener("click", close);
  const confirmBtn = overlay.querySelector("[data-master-del-confirm]");
  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    try {
      await apiDelete(`/api/masters/${encodeURIComponent(m.platform)}`);
      close();
      toast("ok", "已删除平台 " + m.platform + " 的母版");
      loadMasters();
    } catch (e) {
      toast("error", e.message);   // 失败：弹窗保留，用户可重试或取消
      confirmBtn.disabled = false;
    }
  });
  document.body.appendChild(overlay);
}

// ---------------------------------------------------------------------------
// 母版详情弹窗（工单 master-library-ui/04）：元数据段 + 关键文件清单 +
// 内容懒加载（memo、三态）。交互逻辑下沉纯函数（extract 范式），
// DOM 层只做转发；对偶 topic 轮 detail 弹窗模式。纯件（masterFileURL /
// masterKeyFileRowHTML / masterDetailHTML）在 fx/master.js。
// ---------------------------------------------------------------------------

// 文件内容 memo（工单 04）：key = platform/path → {ok:true, content} |
// {ok:false, message}。业务 400 缓存（数据现状，重试无意义）；网络 /
// 服务端错误（e.status 缺失或 ≥500）不缓存——瞬时故障可重试
// （对偶 topic 轮 loadTopicPageState 先例）。
const masterFileCache = new Map();

async function loadMasterFileState(platform, path, url) {
  const key = platform + "/" + path;
  if (masterFileCache.has(key)) return masterFileCache.get(key);
  try {
    const data = await apiGet(url);
    const cached = { ok: true, content: data.content || "" };
    masterFileCache.set(key, cached);
    return cached;
  } catch (e) {
    const cached = { ok: false, message: e.message };
    if (e.status && e.status < 500) masterFileCache.set(key, cached);
    return cached;
  }
}

function renderMasterFileContent(box, cached, path) {
  box.innerHTML = masterContentHTML(cached, path);
  if (cached.ok) {
    const btn = box.querySelector("[data-master-copy]");
    if (btn) btn.addEventListener("click", () => copyMasterContent(cached.content || "", btn));
  }
}

// copyMasterContent(content, btn)：复制按钮行内反馈——成功 = 「✓ 已复制」1.5s
// 还原；失败 = toast 中文（非安全上下文 / 拒绝授权回退 execCommand 后再败）。
async function copyMasterContent(content, btn) {
  if (await writeClipboard(content)) {
    btn.textContent = "✓ 已复制";
    setTimeout(() => { btn.textContent = "复制"; }, 1500);
  } else {
    toast("error", "复制失败：当前页面环境不允许访问剪贴板（需要 HTTPS 或 localhost 页面，且浏览器已授权）");
  }
}

async function writeClipboard(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* 授权拒绝 / 非安全上下文 → 回退 execCommand */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch { return false; }
}

// openMasterPath(platform, path, url, box, btn)：点文件行 → 三态（加载中 /
// 成功 pre-wrap / 失败中文原因可重试），仅成功行高亮。memo 命中（含缓存
// 业务错误）不闪「加载中」直接渲染；网络 / ≥500 未缓存 → 再点重取。
// 关键文件（masterFileURL）与树文件（masterTreeFileURL）共用同一 memo
// 与渲染，key = platform/path 不变（工单 master-library-ui-2/02）。
async function openMasterPath(platform, path, url, box, btn) {
  const key = platform + "/" + path;
  if (!masterFileCache.has(key)) box.innerHTML = masterContentHTML(null, path);
  const cached = await loadMasterFileState(platform, path, url);
  renderMasterFileContent(box, cached, path);
  box.closest(".ref-files-modal").querySelectorAll("[data-master-file], [data-master-tree-file]")
    .forEach((b) => b.classList.remove("on"));
  if (btn && cached.ok) btn.classList.add("on");
}

function openMasterFile(platform, path, box, btn) {
  return openMasterPath(platform, path, masterFileURL(platform, path), box, btn);
}

function openMasterTreeFile(platform, path, box, btn) {
  return openMasterPath(platform, path, masterTreeFileURL(platform, path), box, btn);
}

// 树清单 memo（工单 02）：platform → {ok, files} | {ok:false, message}。
// 业务 400 缓存（数据现状）；网络 / ≥500 不缓存可重试；loadMasters 成功
// 拉新列表时整表失效（库变了树不旧）。
const masterTreeCache = new Map();

async function loadMasterTreeState(platform) {
  if (masterTreeCache.has(platform)) return masterTreeCache.get(platform);
  try {
    const files = await apiGet("/api/masters/" + encodeURIComponent(platform) + "/tree");
    const cached = { ok: true, files };
    masterTreeCache.set(platform, cached);
    return cached;
  } catch (e) {
    const cached = { ok: false, message: e.message };
    if (e.status && e.status < 500) masterTreeCache.set(platform, cached);
    return cached;
  }
}

function renderMasterTree(box, cached) {
  if (!cached.ok) {
    box.innerHTML = '<div class="error">加载失败：' + esc(cached.message) + "</div>";
    return;
  }
  const nodes = buildMasterTree(cached.files);
  box.innerHTML = nodes.length
    ? '<ul class="master-tree">' + masterTreeNodeHTML(nodes) + "</ul>"
    : '<span class="muted">（没有文件）</span>';
}

// 树点击接线：按钮在渲染后才存在，故渲染完再挂事件（对偶 openMasterDetail
// 关键文件行接线模式）；点树文件 → 同内容箱（与关键文件共用 data-master-content）。
function wireMasterTree(platform, box, contentBox) {
  box.querySelectorAll("[data-master-tree-file]").forEach((b) =>
    b.addEventListener("click", () =>
      openMasterTreeFile(platform, b.dataset.masterTreeFile, contentBox, b)));
}

// openMasterDetail(platform)：母版详情弹窗——复用 .ref-files-overlay 遮罩与
// 关闭模式（Esc / × / 点遮罩）；打开只渲染清单（零内容请求），点文件行才取。
function openMasterDetail(platform) {
  const m = (masterCache || []).find((x) => x.platform === platform);
  if (!m) { toast("info", "未找到平台 " + platform + "（列表可能已刷新）"); return; }
  document.querySelectorAll(".ref-files-overlay").forEach((o) => o.remove());
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  overlay.innerHTML = `<div class="ref-files-modal master-modal">
    <div class="ref-files-head"><strong>母版详情 · ${esc(m.platform_label || m.platform)}</strong>
      <button class="ref-files-close" title="关闭">×</button></div>
    <div class="ref-detail-scroll">${masterDetailHTML(m)}</div>
  </div>`;
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  const contentBox = overlay.querySelector("[data-master-content]");
  overlay.querySelectorAll("[data-master-file]").forEach((b) =>
    b.addEventListener("click", () =>
      openMasterFile(m.platform, b.dataset.masterFile, contentBox, b)));
  document.body.appendChild(overlay);
  // 全部文件树（工单 master-library-ui-2/02）：异步拉清单 → 渲染 → 接线
  const treeBox = overlay.querySelector("[data-master-tree]");
  loadMasterTreeState(m.platform).then((cached) => {
    renderMasterTree(treeBox, cached);
    if (cached.ok) wireMasterTree(m.platform, treeBox, contentBox);
  });
}

export async function loadMasters() {
  try {
    const masters = await apiGet("/api/masters");
    masterCache = masters;
    masterTreeCache.clear();   // 库变了树不旧：新列表成功拉取即失效树清单
    $("master-rows").innerHTML = masters.map(masterTableRowHTML).join("");
    $("master-rows").querySelectorAll("[data-master-detail]").forEach((b) =>
      b.addEventListener("click", () => openMasterDetail(b.dataset.masterDetail)));
    $("master-rows").querySelectorAll("[data-master-del]").forEach((b) =>
      b.addEventListener("click", () => openMasterDeleteConfirm(b.dataset.masterDel)));
    $("master-msg").textContent = "";
  } catch (e) { $("master-msg").textContent = e.message; }
}

// 新增平台下拉（评审工单 23 自 host 迁入）：母版 tab「新增平台」表单的平台选项，
// host 启动 IIFE 调 renderNewPlatformOptions(state.platforms)。
export function renderNewPlatformOptions(platforms) {
  $("new-platform").innerHTML = platforms.map((p) =>
    `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
}

// ---------------------------------------------------------------------------
// 更新记录页（工单 changelog-tab/01）：按天分组时间轴，数据源 CHANGELOG.md（提交后自动补录）
// ---------------------------------------------------------------------------
export async function loadChangelog() {
  const box = $("changelog-list");
  try {
    const groups = await apiGet("/api/changelog");
    if (!groups.length) {
      box.innerHTML = '<div class="empty-state"><div class="es-icon">📝</div><div class="es-title">暂无更新记录</div><div class="es-hint">每次提交代码后，这里会自动补录 CHANGELOG 条目。</div></div>';
      return;
    }
    box.innerHTML = groups.map((g) => `
      <div style="margin-bottom:14px">
        <h3 style="color:var(--accent);margin:0 0 6px">${esc(g.date)}</h3>
        <ul style="margin:0;padding-left:22px">
          ${g.items.map((i) => `<li style="margin-bottom:4px">${
            i.time ? `<span class="slug" style="margin-right:8px">${esc(i.time)}</span>` : ""
          }${esc(i.text)}</li>`).join("")}
        </ul>
      </div>`).join("");
  } catch (e) {
    box.innerHTML = `<div class="error">${esc(e.message)}</div>`;
  }
}
