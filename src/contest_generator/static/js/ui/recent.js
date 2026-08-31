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
import { confirmModal } from "/js/ui/confirm.js";
import { recentDeleteMessage } from "/js/fx/danger.js";
import { openCodeViewer } from "/js/ui/codeview.js";  // 「查看代码」桥（工单 code-viewer/06）：切 tab + 加载该 output_dir
import { getMainCDiskDir, setMainCDiskContext, refreshMainCDiskState } from "/js/ui/generate-mainc-sync.js";  // main.c 磁盘同步（mainc-codeview-bridge/01）：无草稿上下文时按最近记录回退补位

// 最近记录快照缓存（工单 ux-walkthrough-02/15：删除确认点名 + 撤销恢复用）
let recentEntries = [];

export function renderRecentList(entries) {
  recentEntries = Array.isArray(entries) ? entries : [];
  const list = $("gen-recent-list");
  const box = $("gen-recent");
  if (!list || !box) return;
  box.classList.remove("hidden");
  list.innerHTML = recentListHTML(recentEntries);
}
export async function refreshRecent() {
  const box = $("gen-recent");
  if (!box) return;
  let entries = [];
  try { entries = await apiGet("/api/recent"); }
  catch (e) { toastError(e, "最近生成加载失败"); }
  renderRecentList(entries || []);
  // main.c 磁盘同步（工单 mainc-codeview-bridge/01，验收 #4）：刷新页面后若
  // 草稿未带生成上下文目录（新会话 / 草稿已清），用最近一条记录补位——
  // 状态行能显示此前生成的目录；草稿已恢复上下文时不覆盖（宁少不错）。
  if (!getMainCDiskDir()) {
    const latest = (entries || []).find((e) => e.output_dir);
    if (latest) { setMainCDiskContext(String(latest.output_dir)); void refreshMainCDiskState(); }
  }
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
    const codeBtn = e.target.closest(".recent-code-open");
    if (codeBtn) {
      e.stopPropagation();  // 不触发整卡复制路径行为
      openCodeViewer(codeBtn.dataset.codeDir || "");
      return;
    }
    const del = e.target.closest(".recent-del");
    if (del) {
      e.stopPropagation();
      const id = del.dataset.id || "";
      const entry = recentEntries.find((r) => String(r.id) === id);
      // 删除确认（工单 ux-walkthrough-02/15）：只移除历史记录 + 可撤销
      const ok = await confirmModal({
        title: "删除这条最近记录？",
        message: recentDeleteMessage(entry),
        confirmText: "确认删除",
      });
      if (!ok) return;
      try {
        await apiDelete("/api/recent/" + encodeURIComponent(id));
        toast("ok", entry ? "已删除最近记录（可撤销）" : "已删除最近记录", {
          ms: entry ? 8000 : 2500,   // 撤销窗口：8s（评审整改：2.5s 太短易错过）
          action: entry ? {
            label: "撤销",
            onClick: async () => {
              const data = await apiPost("/api/recent/restore", { entry });
              refreshRecent();
              toast("ok", "已恢复记录：" + (data.entry && data.entry.output_dir || ""));
            },
          } : undefined,
        });
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
