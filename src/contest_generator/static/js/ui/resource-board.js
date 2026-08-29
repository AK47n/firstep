// ui/resource-board.js — 资源总览视图切换 + 板图渲染（resource-overview-polish/02）。
// 视图态 view（list|board，默认 list）与板定义缓存（platform → GET /api/boards
// boards[0]）都是本簇私有；任务推进簇渲染时调 renderResourceSection(plan)，
// 切换按钮经 initResourceBoard 的 document 级委托响应（容器 innerHTML 每次被
// tasksRender 重建，绑定必须委托在 document 上）。
import { $, apiGet } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { aggregateResourceGroups, resourcesOverviewHTML } from "/js/fx/task.js";
import { resourceBoardHTML, resourcesToolbarHTML, resourceTaskColorMap } from "/js/fx/resource-board.js";
import { reviseGetPlatform } from "./generate-revise.js";

let view = "list";                    // list = 分组列表（01）｜board = 板图视角
const boards = new Map();             // platform → 板定义（切平台重取，同平台缓存）
let lastPlan = null;                  // 最近一次渲染的 plan（切视图时立即重渲染）

/** 当前视图（任务推进簇渲染工具栏高亮用）。 */
export function resourceView() {
  return view;
}

/** 同步工具栏按钮高亮（视图可能被失败回落等内部路径改掉，工具栏在任务推进簇手里）。 */
function refreshViewButtons() {
  document.querySelectorAll(".res-view-btn").forEach((btn) => {
    const on = btn.dataset.resView === view;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-pressed", String(on));
  });
}

/** 切换视图并重渲染（按钮委托入口；非法值忽略）。
 * 工具栏（.res-toolbar）由 generate-tasks tasksRender 渲染，本簇只在 body 里
 * 重渲染，所以切换后必须即时同步按钮高亮——否则选中光圈留在旧按钮上。 */
export function setResourceView(v) {
  if (v !== "list" && v !== "board") return;
  view = v;
  refreshViewButtons();
  renderResourceSection(lastPlan);
}

/** 渲染资源总览主体（#res-view-body）：list → resourcesOverviewHTML(plan)；
 * board → 平台板定义（缓存）→ resourceBoardHTML；无平台/板定义失败 → 引导行。
 * 空聚合（无资源标注）由调用方（generate-tasks tasksRender）整段隐藏，本函数不处理。 */
export async function renderResourceSection(plan) {
  lastPlan = plan;
  const body = $("res-view-body");
  if (!body || !aggregateResourceGroups(plan)) return;
  if (view === "list") {
    body.innerHTML = resourcesOverviewHTML(plan);
    return;
  }
  const platform = reviseGetPlatform();
  if (!platform) {
    body.innerHTML = '<div class="res-board-msg muted">尚未加载上下文——板图需要项目平台信息。</div>';
    return;
  }
  let board = boards.get(platform);
  if (!board) {
    body.innerHTML = '<div class="res-board-msg muted">板定义加载中…</div>';
    try {
      const data = await apiGet("/api/boards?platform=" + encodeURIComponent(platform));
      board = (data.boards || [])[0] || null;
      boards.set(platform, board);
    } catch (e) {
      // 加载失败（resource-overview-polish/02 规格）：给出错误行并自动回落列表视图，
      // 避免用户停留在没有内容的板图视角；按钮高亮同步（工具栏由 generate-tasks 渲染，
      // 下次 tasksRender 也会与 view 一致，这里先即时同步）
      view = "list";
      refreshViewButtons();
      body.innerHTML =
        '<div class="res-board-msg error">板定义加载失败：' + esc(e.message) + "，已回列表视图</div>" +
        resourcesOverviewHTML(plan);
      return;
    }
    // 竞态防护：等待期间视图可能已被切走/重新渲染（lastPlan 变化），
    // 板定义就绪后若已不是板图视图则丢弃过期渲染
    if (view !== "board" || lastPlan !== plan || !$("res-view-body")) return;
  }
  body.innerHTML = resourceBoardHTML(board, aggregateResourceGroups(plan), resourceTaskColorMap(plan));
}

/** 资源总览视图切换委托（文档级：容器每次渲染重建，绑定一次即可）。 */
export function initResourceBoard() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest ? e.target.closest(".res-view-btn") : null;
    if (!btn) return;
    setResourceView(btn.dataset.resView);
  });
}
