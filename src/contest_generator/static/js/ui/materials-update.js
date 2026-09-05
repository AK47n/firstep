// ui/materials-update.js — 设置页「资料库更新」区 DOM 胶水（工单 materials-update/06）
//
// 交互：initMaterialsUpdate 装当前版本 + 绑定「检查更新」；检查 →
// /api/update/materials/check → 结果区（baseline-missing / 无更新 / 有更新）；
// 有更新 → 「选择下载」弹窗（批次勾选 + 全选 + 已选大小）或「全部下载」；
// apply 后每 2s 轮询 /api/update/materials/status 显示进度（后台继续 / 取消）；
// done/failed/cancelled 中文结果，重试可继续（已完成卷跳过）。
import { $, apiGet, apiPost, toast } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import {
  materialsCheckCardHTML,
  aggregateSelection,
  materialsPickHTML,
  materialsPickFooterHTML,
  materialsProgressHTML,
} from "/js/fx/materials-update.js";
import { overlayConfirmHTML } from "/js/fx/overlay.js";

let pollTimer = null;
let lastCheck = null;

export async function initMaterialsUpdate() {
  $("btn-materials-check").addEventListener("click", runCheck);
}

async function runCheck() {
  const box = $("materials-update-results");
  const btn = $("btn-materials-check");
  btn.disabled = true;
  box.innerHTML = '<span class="spinner"></span>正在检查资料库更新…';
  try {
    const check = await apiGet("/api/update/materials/check");
    lastCheck = check;
    box.innerHTML = materialsCheckCardHTML(check);
    wireResultButtons();
  } catch (e) {
    box.innerHTML = `<div class="error">检查资料库更新失败：${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}

function wireResultButtons() {
  const pick = $("btn-materials-pick");
  if (pick) pick.addEventListener("click", openPickDialog);
  const all = $("btn-materials-apply-all");
  if (all) all.addEventListener("click", () => startApply(allSlugs()));
}

function allSlugs() {
  return (lastCheck.batches || []).map((b) => b.slug);
}

function openPickDialog() {
  const check = lastCheck;
  if (!check) return;
  const selected = new Set(allSlugs());
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  const render = () => {
    overlay.innerHTML = overlayConfirmHTML({
      title: "选择资料库更新",
      message: `资料库 ${check.latest_version || ""}：勾选要下载的批次（默认全选）`,
      danger: false,
      confirmText: "开始下载",
      cancelText: "稍后",
      extra: materialsPickHTML(check, selected) + materialsPickFooterHTML(check, selected),
    });
    overlay.querySelectorAll("[data-batch-check]").forEach((cb) => {
      cb.addEventListener("change", () => {
        if (cb.checked) selected.add(cb.value);
        else selected.delete(cb.value);
        overlay.querySelector(".materials-pick-footer").outerHTML =
          materialsPickFooterHTML(check, selected);
      });
    });
    overlay.querySelector("#btn-materials-start").addEventListener("click", () => {
      overlay.remove();
      startApply([...selected]);
    });
    overlay.querySelector("[data-confirm-cancel]").addEventListener("click", () => overlay.remove());
    overlay.querySelector(".ref-files-close").addEventListener("click", () => overlay.remove());
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
  };
  render();
  document.body.appendChild(overlay);
}

async function startApply(slugs) {
  if (!slugs.length) {
    toast("error", "请至少选择一个批次");
    return;
  }
  try {
    await apiPost("/api/update/materials/apply", { batches: slugs });
    $("materials-update-results").innerHTML =
      '<div class="ok">已开始下载资料库增量包…</div>';
    stopPoll();
    pollTimer = setInterval(pollStatus, 2000);
  } catch (e) {
    $("materials-update-results").innerHTML =
      `<div class="error">${esc(e.message)}</div>`;
  }
}

async function pollStatus() {
  try {
    const status = await apiGet("/api/update/materials/status");
    const box = $("materials-update-results");
    box.innerHTML = materialsProgressHTML(status) + progressActionsHTML(status);
    wireProgressActions();
    if (["done", "failed", "cancelled", "partial"].includes(status.state)) {
      stopPoll();
      if (status.state === "done") {
        toast("ok", "资料库更新完成");
      } else if (status.state === "cancelled") {
        toast("info", "已取消，已完成的部分不做重复下载");
      } else {
        toast("error", (status.error || "资料库更新失败") + "（备份已保留）");
      }
    }
  } catch {
    // 服务重启（工具更新）瞬间轮询断网：容忍后提示刷新
    // （资料库更新不重启服务，此处兜底）
  }
}

function progressActionsHTML(status) {
  if (!["downloading", "applying"].includes(status.state)) return "";
  return `<div class="row" style="margin-top:var(--space-2)">
    <button id="btn-materials-cancel" type="button" data-ico="stop">取消</button>
    <span class="muted">可在后台继续，页面关闭不影响下载</span>
  </div>`;
}

function wireProgressActions() {
  const cancel = $("btn-materials-cancel");
  if (cancel) cancel.addEventListener("click", async () => {
    try {
      await apiPost("/api/update/materials/cancel", {});
    } catch (e) {
      toast("error", e.message);
    }
  });
}

function stopPoll() {
  clearInterval(pollTimer);
  pollTimer = null;
}
