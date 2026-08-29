// ui/wiring.js — 任务卡接线图数据装配（task-wiring-diagram/04）。
// 职责 = ①拉接线快照（GET /api/wiring，output_dir 与烧录/任务推进同款透传）；
// ②快照缺失时取 /api/boards 静态板（tier-2 资源高亮退化的板）——两级都缓存；
// ③每任务的 wiring 装配字段（wiringOpts）与资源高亮退化图（复用既有资源总览
// 板图渲染器 resourceBoardHTML，资源判据 = fx 聚合的 resourceIsHardware）；
// ④「显示全部接线」开关：在占位 host（data-wiring-uid）内原位重渲（fx 纯函数
// 无副作用，本层只管数据句柄与 DOM 换血；开关状态不持久化——范围外）。
import { apiGet } from "/js/app.js";
import { aggregateResourceGroups } from "/js/fx/task.js";
import { resourceBoardHTML, resourceTaskColorMap } from "/js/fx/resource-board.js";
import { wiringDiagramHTML, wiringFromResources } from "/js/fx/wiring.js";
import { reviseGetPlatform } from "./generate-revise.js";

/** 装配单飞缓存：dir → Promise<assets>（进行中）；assetsValue = 已就绪值。 */
const assetsCache = new Map();
const assetsValue = new Map();

/** 板定义缓存（platform → board）：与 ui/resource-board.js 各备一份（该缓存
 * 私有未导出；本层仅退化路径用，数量级极小，重复拉取可接受）。 */
const boardsCache = new Map();

/** 拉装配：assets = {ctx, board}——ctx = {board, rows}（快照成功）或 null
 * （无快照）；board = 快照板，无快照 = /api/boards 静态板（tier-2 退化用），
 * 都取不到 = null。网络失败静默降级（按「无数据」处理，不打断卡渲染）。 */
export function loadWiringAssets(dir) {
  if (!dir) return Promise.resolve(null);
  if (assetsValue.has(dir)) return Promise.resolve(assetsValue.get(dir));
  if (assetsCache.has(dir)) return assetsCache.get(dir);
  const promise = (async () => {
    let ctx = null;
    let board = null;
    try {
      const data = await apiGet("/api/wiring?output_dir=" + encodeURIComponent(dir));
      if (data && data.board) {
        ctx = { board: data.board, rows: Array.isArray(data.rows) ? data.rows : [] };
        board = ctx.board;
      }
    } catch (e) {
      ctx = null;  // 网络/后端异常：按无快照处理（退化路径，不报错）
    }
    if (!board) {
      const platform = reviseGetPlatform();
      if (platform) board = await loadBoardFor(platform);
    }
    return { ctx, board };
  })();
  assetsCache.set(dir, promise);
  promise.then(
    (v) => { assetsValue.set(dir, v); assetsCache.delete(dir); },
    () => { assetsCache.delete(dir); },
  );
  return promise;
}

/** 同步取已就绪装配（未就绪 = undefined——渲染先给现况，就绪后调用方重渲）。 */
export function wiringAssetsSync(dir) {
  const v = dir && assetsValue.get(dir);
  return v === undefined ? undefined : v;
}

async function loadBoardFor(platform) {
  if (boardsCache.has(platform)) return boardsCache.get(platform);
  const promise = (async () => {
    try {
      const data = await apiGet("/api/boards?platform=" + encodeURIComponent(platform));
      return (data && data.boards && data.boards[0]) || null;
    } catch (e) {
      return null;
    }
  })();
  boardsCache.set(platform, promise);
  return promise;
}

/** 每任务 wiring 装配字段（任务卡 / 结果面板公用；kind = "card"|"result"
 * 分开 uid——同一任务两处各有一个 host，toggle 原位重渲互不干扰）。 */
export function wiringOptsFor(task, assets, kind, plan) {
  const uid = (kind || "card") + ":" + ((task && task.id) || "");
  if (!assets) return { wiringUid: uid };
  return {
    wiringCtx: assets.ctx,                       // null → tier-2/3
    wiringFallbackHTML: wiringFallbackHTML(task, plan, assets.board),
    wiringShowAll: false,
    wiringUid: uid,
  };
}

/** tier-2 资源高亮板图：本任务 resources 在板图上的占用视角——复用既有资源
 * 总览板图渲染器 resourceBoardHTML（判据 = 聚合共用 resourceIsHardware）；
 * 本任务无资源标注 / 无板定义 = 空串（走 tier-3 纯文字）。单任务视角无冲突
 * 语义 → conflictLegend 关闭（评审整改：多任务共享图例在单任务视图会误导）。 */
function wiringFallbackHTML(task, plan, board) {
  if (!board || !task) return "";
  const groups = aggregateResourceGroups(plan);
  if (!groups) return "";
  const focused = filterGroupsForTask(groups, task.id);
  if (!focused) return "";
  return '<div class="wiring-fallback">'
    + resourceBoardHTML(board, focused, resourceTaskColorMap(focused), { conflictLegend: false })
    + "</div>";
}

/** 聚合组过滤到指定任务（users 只留该任务，冲突随之消解——单任务视角）。
 * 无任何条目 → null（调用方走纯文字）。 */
function filterGroupsForTask(groups, taskId) {
  const pick = (rows) => rows
    .map((e) => {
      const users = e.users.filter((u) => u && u.id === taskId);
      return users.length ? { names: e.names.slice(), users, conflict: false } : null;
    })
    .filter(Boolean);
  const pins = pick(groups.pins || []);
  const other = pick(groups.other || []);
  const soft = pick(groups.soft || []);
  if (!pins.length && !other.length && !soft.length) return null;
  return { pins, other, soft };
}

/** 渲染后把接线图数据句柄挂到 host（供「显示全部接线」原位重渲）：host 存在
 * ⟺ wiringSectionHTML 走了接线图（tier-1 或工单 05 按资源标定）——句柄只在
 * 此时需要；wiring 取最新轮迭代（与装配同源），无 wiring 引用时用
 * wiringFromResources 反推结果（与 fx 层同一推导，toggle 对推断图同样可用）。 */
export function attachWiringInputs(root, tasksById, assets) {
  if (!root) return;
  root.querySelectorAll("[data-wiring-uid]").forEach((host) => {
    const uid = host.getAttribute("data-wiring-uid") || "";
    const sep = uid.indexOf(":");
    const taskId = sep >= 0 ? uid.slice(sep + 1) : "";
    const task = tasksById.get(taskId);
    const last = task && task.iterations ? task.iterations[task.iterations.length - 1] : null;
    const wiring = (last && last.wiring) || [];
    if (!assets || !assets.ctx) return;
    const effWiring = wiring.length
      ? wiring
      : wiringFromResources((task && task.resources) || [], assets.ctx.rows || []);
    if (!effWiring.length) return;
    host.__wiringInputs = { board: assets.ctx.board, rows: assets.ctx.rows || [], wiring: effWiring };
  });
}

/** 「显示全部接线」开关（document 级 change 委托：host 每次被渲染重建，
 * 绑定一次即可；开关状态不持久化——范围外）。原位重渲 = host.innerHTML 换血
 * （host 本体与 __wiringInputs 句柄保留，可反复开关）。 */
export function initWiringToggle() {
  document.addEventListener("change", (e) => {
    const box = e.target && e.target.closest
      ? e.target.closest("input[data-wiring-toggle]") : null;
    if (!box) return;
    const host = box.closest("[data-wiring-uid]");
    if (!host || !host.__wiringInputs) return;
    host.innerHTML = wiringDiagramHTML({
      ...host.__wiringInputs,
      showAll: !!box.checked,
    });
  });
}

/** 任务 id → task 的 Map（attachWiringInputs 查任务用）。 */
export function tasksByIdMap(plan) {
  const map = new Map();
  ((plan || {}).tasks || []).forEach((t) => {
    if (t && t.id) map.set(t.id, t);
  });
  return map;
}

/** 渲染后立刻批量挂句柄（渲染调用方一行接上）。 */
export function wireHosts(root, plan, assets) {
  attachWiringInputs(root, tasksByIdMap(plan), assets);
}
