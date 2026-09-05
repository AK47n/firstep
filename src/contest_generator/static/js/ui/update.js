// ui/update.js — 设置页「软件更新」区 DOM 胶水（工单 auto-update/06）
//
// 交互：initUpdatePanel 启动时装当前版本（/api/health）+ 绑定「检查更新」；
// 检查 → /api/update/check 渲染结果卡（纯件 fx/update.js）；「一键更新」
// 确认弹窗 → POST /api/update/apply（下载+校验在服务端，请求期间显示
// 「正在下载」）→ 开始轮询 /api/update/status（applying → done/failed）。
// 服务重启瞬间轮询会断网：连续 3 次失败即停轮询并提示刷新（更新器在
// 后台完成替换后 start-app.vbs 会自动重开浏览器）。
import { $, apiGet, apiPost, toast } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { updateCheckCardHTML, updateStatusHTML } from "/js/fx/update.js";
import { confirmModal } from "/js/ui/confirm.js";

let statusTimer = null;
let pollFailures = 0;

export async function initUpdatePanel() {
  try {
    const health = await apiGet("/api/health");
    $("update-current-version").textContent = "v" + (health.version || "?");
  } catch {
    $("update-current-version").textContent = "?";
  }
  $("btn-update-check").addEventListener("click", runCheck);
}

async function runCheck() {
  const box = $("update-results");
  const btn = $("btn-update-check");
  btn.disabled = true;
  box.innerHTML = '<span class="spinner"></span>检查中…';
  try {
    const check = await apiGet("/api/update/check");
    box.innerHTML = updateCheckCardHTML(check);
    const apply = $("btn-update-apply");
    if (apply) apply.addEventListener("click", () => runApply(check));
  } catch (e) {
    box.innerHTML = `<div class="error">检查更新失败：${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}

async function runApply(check) {
  if (!await confirmModal({
    title: "确认一键更新？",
    message: "将下载更新包并停服替换、完成后自动重启。DeepSeek key、任务状态与 6 GB 资料库都不受影响；更新失败会保留备份。",
    confirmText: "开始更新",
  })) return;
  const box = $("update-results");
  const mb = Math.round((check.size_bytes || 0) / 1024 / 1024);
  box.innerHTML = `<div class="ok">正在下载更新包（约 ${mb} MB），下载完成后将自动停服与替换…</div>`;
  try {
    await apiPost("/api/update/apply", {
      zip_url: check.zip_url,
      sha256: check.sha256,
      version: check.latest_version,
      removed_url: check.removed_url || "",
    });
    pollFailures = 0;
    pollStatus();
  } catch (e) {
    box.innerHTML = `<div class="error">${esc(e.message)}</div>`;
  }
}

function pollStatus() {
  clearInterval(statusTimer);
  statusTimer = setInterval(async () => {
    try {
      const status = await apiGet("/api/update/status");
      pollFailures = 0;
      if (status.state === "applying") {
        $("update-results").innerHTML = updateStatusHTML(status);
        return;
      }
      if (status.state === "done") {
        clearInterval(statusTimer);
        $("update-results").innerHTML = updateStatusHTML(status);
        if (status.result && status.result.status === "ok") {
          toast("ok", "更新完成，浏览器将重新打开");
        } else {
          toast("error", "更新失败，备份已保留");
        }
        return;
      }
    } catch {
      // 更新器停服/替换期间轮询断网：容忍有限次，之后提示手动刷新
      pollFailures += 1;
      if (pollFailures >= 3) {
        clearInterval(statusTimer);
        $("update-results").innerHTML =
          '<div class="muted">服务已停止（更新正在进行）。完成后浏览器会重新打开；若未自动打开，请稍后刷新本页。</div>';
      }
    }
  }, 2000);
}
