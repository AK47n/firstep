// ui/recent.js — 最近生成列表 DOM 胶水（阶段 2 工单 11）
//
// 生成成功自动落盘 recent.json（后端 GET /api/recent / POST /api/recent/status /
// DELETE /api/recent/{id}）后的顶部列表展示：状态点 / 平台徽章 / 模块数 /
// 时间 / 目录名；点击复制路径、✕ 删除、刷新重拉。纯件在 fx/recent.js
// （recentStatusMeta / recentTimeLabel / recentPlatformLabel / recentChipHTML /
// recentListHTML / recentStatusNow——工单 08 迁）。
// 跨簇调用方（调用方 import 本模块）：renderGenerateSuccess（生成成功 →
// refreshRecent）、fixHandleEvent（编译结束 → reportRecentStatus）；host 启动
// 区经 import 调 initRecent。无模块态。
import { $, apiGet, apiPost, apiDelete, toast, toastError } from "/js/app.js";
import { recentListHTML, recentStatusNow } from "/js/fx/recent.js";

export function renderRecentList(entries) {
  const list = $("gen-recent-list");
  const box = $("gen-recent");
  if (!list || !box) return;
  box.classList.remove("hidden");
  list.innerHTML = recentListHTML(entries || []);
}
export async function refreshRecent() {
  const box = $("gen-recent");
  if (!box) return;
  let entries = [];
  try { entries = await apiGet("/api/recent"); }
  catch (e) { toastError(e, "最近生成加载失败"); }
  renderRecentList(entries || []);
}
// 编译完成上报（fire-and-forget：失败不打断编译循环，静默）+ 刷新列表
export async function reportRecentStatus(outputDir, done) {
  try {
    await apiPost("/api/recent/status",
      { output_dir: outputDir, status: recentStatusNow(done) });
  } catch (e) { /* 上报失败不打断编译循环 */ }
  refreshRecent();
}
export function initRecent() {
  const refresh = $("btn-recent-refresh");
  if (refresh) refresh.addEventListener("click", () => refreshRecent());
  const list = $("gen-recent-list");
  if (!list) return;
  list.addEventListener("click", async (e) => {
    const del = e.target.closest(".recent-del");
    if (del) {
      e.stopPropagation();
      try {
        await apiDelete("/api/recent/" + encodeURIComponent(del.dataset.id || ""));
      } catch (err) { toastError(err, "删除失败"); }
      refreshRecent();
      return;
    }
    const chip = e.target.closest(".recent-chip");
    if (!chip) return;
    const dir = chip.dataset.dir || "";
    // 复制路径（与 btn-copy-dir / main.c 工具栏同款：clipboard 失败 → execCommand 兜底）
    const done = () => toast("ok", "已复制路径");
    const fallback = () => {
      try {
        const ta = document.createElement("textarea");
        ta.value = dir;
        document.body.appendChild(ta);
        ta.select();
        if (document.execCommand && document.execCommand("copy")) { toast("ok", "已复制路径"); return; }
        toast("error", "复制失败：请手动复制");
      } catch (err) { toastError(err, "复制失败"); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(dir).then(done).catch(fallback);
    } else fallback();
  });
  refreshRecent();
}
