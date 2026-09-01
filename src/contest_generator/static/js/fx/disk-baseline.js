// fx/disk-baseline.js — 磁盘基线对比纯函数（工单 code-ide-flow/01）
//
// 事实源 = 磁盘基线对比：代码 tab 打开目录时记录基线（见 spec.md），
// 树刷新 / 切回 tab 时重扫磁盘对比，输出三类变更（新增 / 修改 / 消失），
// 供「磁盘变更」面板与标签联动消费。纯函数：无 DOM / localStorage /
// 网络副作用（localStorage 键读写一律进 ui 胶水层，模块约定见 fx/core.js
// 头部）；mtime 比较为字符串相等（与后端 409 冲突检测同口径——base_mtime_ns
// 以字符串传输，前端不做数值化，避免大整数精度失真）。

// baselineSnapshot(files)：文件清单 → 规范化快照 {path → {mtime_ns, size_bytes}}。
// files = /api/code/open 直出条目 [{path, mtime_ns?, size_bytes?, is_dir?}...]；
// 目录条目（is_dir）与空路径跳过；mtime_ns 缺失 → 空串（对比上视为「无基准」，
// 与后端树条目未带 mtime 时的降级行为一致）；mtime_ns 数字输入转字符串。
// size_bytes 保留原值（仅展示用，不参与对比）。
export function baselineSnapshot(files) {
  const out = {};
  for (const f of files || []) {
    if (f.is_dir) continue;
    const p = String(f.path == null ? "" : f.path);
    if (!p) continue;
    const m = f.mtime_ns;
    out[p] = {
      mtime_ns: m == null ? "" : String(m),
      size_bytes: f.size_bytes == null ? "" : f.size_bytes,
    };
  }
  return out;
}

// mtimeEq(a, b)：mtime 值相等比较——字符串化 + null/undefined 视为 ""
// （与后端 409 base_mtime_ns 字符串口径一致）。基线 diff、标签重载守卫、
// 快照建库守卫共用（评审整改：三处 String(x||"") 比较归一单源）。
export function mtimeEq(a, b) {
  return String(a == null ? "" : a) === String(b == null ? "" : b);
}

// baselineDiff(prev, now)：基线快照 vs 当前快照 → {added[], modified[], removed[]}
// （均为相对路径数组，插入序 = 输入序）。added = 现快照有基线无；removed = 基线
// 有现快照无；modified = 都有但 mtime_ns 不同（mtimeEq 比较）。mtime 相同
// （含同为空串/同数字）不算修改——内容未变，与 /api/code/save 的 409 检测
// 同口径。prev / now 传 null/undefined 按空快照处理（幂等防调用方分支）。
export function baselineDiff(prev, now) {
  const p = prev || {};
  const n = now || {};
  const added = [];
  const modified = [];
  const removed = [];
  for (const path of Object.keys(n)) {
    if (!Object.prototype.hasOwnProperty.call(p, path)) {
      added.push(path);
    } else if (!mtimeEq(p[path].mtime_ns, n[path].mtime_ns)) {
      modified.push(path);
    }
  }
  for (const path of Object.keys(p)) {
    if (!Object.prototype.hasOwnProperty.call(n, path)) {
      removed.push(path);
    }
  }
  return { added, modified, removed };
}

// baselineHasChanges(diff)：diff 非空（三类任一有条目）→ true；diff 为
// null/undefined 视为无变更。面板空态 / 标签联动前置判断用。
export function baselineHasChanges(diff) {
  return !!(diff && (diff.added.length > 0 || diff.modified.length > 0
    || diff.removed.length > 0));
}

// ===== 内容快照（工单 code-ide-ai/07）：打开过的文件才有行级 diff 数据源 =====
// 基线条目可选项 content = 文件内容快照（cap 256KB/文件，超限不存 = 无行级，
// 文件级照常）。**只进基线 store**（目录隔离 + evict 预算沿用）；快照维护
// （建/推进）在 ui 胶水层（fx 无副作用约定）。

// SNAPSHOT_MAX：快照上限（字节 = JS 字符串 length——UTF-16 码元，与后端
// 256KB 预算同口径的近似，超限 → null）。
export const SNAPSHOT_MAX = 256 * 1024;

// snapshotOf(content)：内容 → 快照（合法字符串且 ≤ 上限 → 内容本身；否则
// null = 无行级）。main.c 特例与通用文件统一用这一个（旧 maincSnap 单源化）。
export function snapshotOf(content) {
  return typeof content === "string" && content.length <= SNAPSHOT_MAX
    ? content : null;
}

// migrateBaselineStore(store)：旧数据兼容（字段统一化，删除 maincContent
// 特例——旧版本每目录级 maincContent → files["main.c"].content）。
// - 旧 maincContent 存在且 files 含 main.c 且 content 缺失 → 迁移；
// - 无 main.c（磁盘上该文件已不在）→ 旧残值丢弃（基线 = 磁盘快照）；
// - 新结构 content 已有 → 不覆盖（新结构优先）；
// - 返回**新对象**，不修改入参；null/非对象 → 原样返回。迁移幂等。
export function migrateBaselineStore(store) {
  if (!store || typeof store !== "object") return store;
  const out = {};
  for (const dir of Object.keys(store)) {
    const entry = store[dir];
    if (!entry || typeof entry !== "object"
      || !Object.prototype.hasOwnProperty.call(entry, "maincContent")) {
      out[dir] = entry;   // 无旧字段：引用共享（未修改过，无拷贝必要）
      continue;
    }
    const files = { ...(entry.files || {}) };
    const mc = files["main.c"];
    if (mc && typeof mc.content !== "string" && typeof entry.maincContent === "string") {
      files["main.c"] = { ...mc, content: entry.maincContent };
    }
    out[dir] = { ...entry, files };
    delete out[dir].maincContent;
  }
  return out;
}

// baselineEvict(store, maxDirs)：多目录基线 store 裁剪（LRU 上限）——
// store = {dir → {ts, files}}（ts = 最近访问时间戳，files = 规范化快照）；
// 超过 maxDirs 个目录时保留 ts 最大的 maxDirs 个；ts 相同时保留先插入者
// （Array.sort 稳定，Object.keys 顺序 = 插入序）。返回**新对象**，不修改入参；
// maxDirs 非法（非有限数 / 负数）或条目数不超限 → 原样返回 store。
export function baselineEvict(store, maxDirs) {
  const max = Number(maxDirs);
  if (!Number.isFinite(max) || max < 0) return store;
  const dirs = Object.keys(store || {});
  if (dirs.length <= max) return store;
  const ranked = dirs
    .map((dir) => ({ dir, ts: Number((store[dir] || {}).ts) || 0 }))
    .sort((a, b) => (a.ts === b.ts ? 0 : a.ts > b.ts ? -1 : 1));
  const keep = new Set(ranked.slice(0, max).map((r) => r.dir));
  const out = {};
  for (const dir of dirs) {
    if (keep.has(dir)) out[dir] = store[dir];
  }
  return out;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    baselineSnapshot,
    baselineDiff,
    baselineHasChanges,
    baselineEvict,
    snapshotOf,
    migrateBaselineStore,
    mtimeEq,
  });
}
