// ui/full-update.js — 设置页「完整包」区 DOM 胶水（工单 full-download/05）
//
// 交互：initFullUpdate 装当前版本行 + 绑定「检查完整包」；检查 →
// /api/update/full/check → 结果区；点「下载完整 firstep」→ 确认弹窗
// （版本 / 总量 / 卷数 / 重启语义）→ apply → 每 2s 轮询
// /api/update/full/status 显示进度（进度条 / 当前卷 / 速度 / 剩余时间 /
// 后台继续 / 取消）；done 提示重启、failed 可重试（已完成卷跳过）。
// 无基线时资料库区的主按钮也走这里（双轨选路：有基线走增量、无基线走全量）。
import { $, apiGet, apiPost, toast } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import {
  fullCheckCardHTML,
  fullConfirmHTML,
  fullProgressHTML,
  fullStateText,
} from "/js/fx/full-update.js";
import { overlayConfirmHTML } from "/js/fx/overlay.js";

let pollTimer = null;
let lastCheck = null;

export async function initFullUpdate() {
  const btn = $("btn-full-check");
  if (btn) btn.addEventListener("click", runCheck);
  // 资料库区「一键下载完整 firstep」（无基线时出现）：先检查再弹确认
  document.addEventListener("click", async (e) => {
    const target = e.target instanceof Element ? e.target.closest("#btn-materials-full-download") : null;
    if (!target) return;
    await runCheck();
    if (lastCheck && !lastCheck.error) openConfirmDialog();
  });
}

async function runCheck() {
  const box = $("full-update-results");
  const btn = $("btn-full-check");
  if (btn) btn.disabled = true;
  if (box) box.innerHTML = '<span class="spinner"></span>正在检查完整包…';
  try {
    lastCheck = await apiGet("/api/update/full/check");
    renderCheck();
  } catch (e) {
    if (box) box.innerHTML = `<div class="error">检查完整包失败：${esc(e.message)}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderCheck() {
  const box = $("full-update-results");
  if (!box || !lastCheck) return;
  box.innerHTML = fullCheckCardHTML(lastCheck);
  const download = $("btn-full-download");
  if (download) download.addEventListener("click", openConfirmDialog);
}

function openConfirmDialog() {
  if (!lastCheck || lastCheck.error || !(lastCheck.parts || []).length) return;
  const check = lastCheck;
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  overlay.innerHTML = overlayConfirmHTML({
    title: "下载完整 firstep",
    message: "确认后开始下载完整包",
    danger: false,
    // 主按钮由 extra 里的「开始下载」承担，骨架按钮隐藏（同资料库选择弹窗形态）
    confirmText: "开始下载",
    cancelText: "稍后",
    extra: fullConfirmHTML(check),
  });
  const ok = overlay.querySelector("[data-confirm-ok]");
  if (ok) ok.style.display = "none";
  overlay.querySelector("#btn-full-start").addEventListener("click", () => {
    overlay.remove();
    startDownload();
  });
  // 取消按钮由弹窗骨架承担（data-confirm-cancel）；内容区不再重复一个
  overlay.querySelector("[data-confirm-cancel]").addEventListener("click", () => overlay.remove());
  const close = overlay.querySelector(".ref-files-close");
  if (close) close.addEventListener("click", () => overlay.remove());
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

async function startDownload() {
  const box = $("full-update-results");
  const names = (lastCheck.parts || []).map((p) => p.name);
  if (!names.length) {
    toast("error", "没有可下载的分卷，请先检查更新");
    return;
  }
  try {
    await apiPost("/api/update/full/apply", { parts: names });
    if (box) box.innerHTML = '<div class="ok">已开始下载完整包…</div>';
    startPoll();
  } catch (e) {
    if (box) box.innerHTML = `<div class="error">${esc(e.message)}</div>`;
  }
}

function startPoll() {
  stopPoll();
  pollTimer = setInterval(pollStatus, 2000);
  pollStatus();
}

async function pollStatus() {
  const box = $("full-update-results");
  let status;
  try {
    status = await apiGet("/api/update/full/status");
  } catch {
    // 工具正在重启（替换完成）瞬间连不上：不是错误，提示刷新即可
    if (box) {
      box.innerHTML =
        '<div class="ok">工具正在重启以完成更新…若页面没有自动恢复，刷新即可。</div>';
    }
    return;
  }
  if (box) box.innerHTML = fullProgressHTML(status);
  wireProgressActions();
  if (["done", "failed", "cancelled"].includes(status.state)) {
    stopPoll();
    if (status.state === "done") toast("ok", "完整包已应用，工具即将重启");
    else if (status.state === "cancelled") toast("info", "已取消，已校验的卷会保留");
    else toast("error", (status.error || "完整包下载失败") + "（备份已保留）");
  }
}

function wireProgressActions() {
  const cancel = $("btn-full-cancel");
  if (cancel) {
    cancel.addEventListener("click", async () => {
      try {
        await apiPost("/api/update/full/cancel", {});
      } catch (e) {
        toast("error", e.message);
      }
    });
  }
  const retry = $("btn-full-retry");
  if (retry) retry.addEventListener("click", startDownload);
}

function stopPoll() {
  clearInterval(pollTimer);
  pollTimer = null;
}

export { fullStateText };
