# 01 — 磁盘基线对比纯件（快照 / diff / LRU 裁剪）

**要做什么：** 新增 fx 纯件：把文件清单（`{path, mtime_ns, size_bytes}`）规范化为
按路径索引的快照；给定前后两个快照，输出三类变更（新增 / 修改（mtime 不同）/
消失）；多目录 store 的 LRU 裁剪（超上限丢最旧目录条目）。全为纯函数，
无 DOM / localStorage 副作用；node 单测覆盖。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 验收 1：快照规范化——输入文件列表 → `{path: {mtime_ns, size_bytes}}`；
  mtime_ns / size_bytes 为空的条目保留但值为空串，不丢弃。
- [x] 验收 2：diff 三分类——added（现快照有、基线无）、modified（都有但
  mtime_ns 不同）、removed（基线有、现快照无）；mtime 相同 → 三类均不含。
- [x] 验收 3：边界——空基线 + 全文件 = 全 added；空现快照 + 满基线 = 全 removed；
  相同快照 = 三类全空；路径含中文 / 子目录 / 空格不误判。
- [x] 验收 4：mtime 比较为字符串相等（非数值），空串 vs 非空串算修改。
- [x] 验收 5：LRU 裁剪——store `{dir → {ts, files}}`，超过 maxDirs 保留最近
  ts 的 maxDirs 个；ts 相同保留先入者（稳定性）；返回新 store 不修改入参。
- [x] 验收 6：node 单测全绿（`node --test tests/js/`（新文件名 `disk-baseline.test.mjs`））。

**结论：** 已落地。新增 `src/contest_generator/static/js/fx/disk-baseline.js`：
`baselineSnapshot(files)`（is_dir 排除、空路径跳过、mtime 缺失→""、数字
mtime 转字符串）→ 规范化快照；`baselineDiff(prev, now)`（mtime **字符串相等**
比较——与 /api/code/save 409 检测同口径，大整数精度不丢）→
{added, modified, removed}；`baselineHasChanges(diff)`；`baselineEvict(store,
maxDirs)`（ts 最大保留、同 ts 先入稳定——Array.sort 稳定 + Object.keys
插入序、返回新对象不改入参、maxDirs 非法原样）。全纯函数无副作用，
window Object.assign 暴露（fx 惯例）。测试：tests/js/disk-baseline.test.mjs
8 用例全绿；全量 node --test 1024 全绿。验收 1-6 全部满足。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
