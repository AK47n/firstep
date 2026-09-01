# 07 — 内容快照泛化（打开过的文件才有行级 diff）

**要做什么：** 三期：基线 store 文件条目增可选项 `content` 快照：
- **规则**：cap 256KB/文件（超限不存=无行级）；「打开过的文件」才持有——
  openEditorFile/loadFile 读盘成功后：若文件 mtime == 基线 mtime → 快照 =
  读盘内容；mtime != 基线 → 不动旧快照（保留 diff 基准=用户确认版）；
  从未打开/无快照 → 无行级（文件级照常）。
- **推进维护**：基线推进点（onFileSaved/树操作 refreshCodeTreeOnly/清空
  确认 clearCodeDiskChanges）对持有快照的文件 re-fetch 当前内容更新快照
  （fetch 失败/超限 → 清 null 保底）；新增了「快照文件清单」域（推进时无需
  全目录 fetch）。
- localStorage 键结构扩展（旧数据兼容：无 content 字段 → 视为无快照）；
  evict/预算沿用（LRU 8 目录；主预算说明 spec 已记）。
- 快照数据源特殊化：main.c 既有 maincContent 迁移/统一为 content 字段
  （**决策：统一到一个字段，删除 maincContent 特例——规整单源**，迁移兼容
  旧键）。

**被谁阻塞：** 03（openEditorFile 接入点；三期在一期完成后）。

**状态：** ready-for-agent（待一期完成后启动）

- [ ] 验收 1：打开文件 → 快照入基线；同 mtime 重开 → 快照刷新不误报。
- [ ] 验收 2：外部改已打开过的文件 → 变更集合该文件 content（旧值）
  → change-panel 数据源可用（工单 08 消费）。
- [ ] 验收 3：从未打开的文件外部改动 → content=null（无行级，文件级照常）；
  超限文件 → null。
- [ ] 验收 4：基线推进后快照 = 新确认内容（diff 基准正确）；old 数据兼容
  （旧 localStorage 无 content 不崩）。
- [ ] 验收 5：node 单测全绿；smoke 回归。

**结论：** 已实现（待双轴评审整改确认）：
- fx/disk-baseline.js：SNAPSHOT_MAX=256*1024 + `snapshotOf(content)`（合法
  字符串且 ≤cap → 内容本身；否则 null）+ `migrateBaselineStore(store)`
  （旧每目录 maincContent → files["main.c"].content 字段统一化：仅 files
  含 main.c 且 content 缺失才迁移、无 main.c 丢旧残值、已有 content 不
  覆盖、返回新对象不改入参、幂等）。
- ui/codeeditor.js：`onFileLoaded(cb)` 读盘成功监听（openEditorFile 新建
  标签路径触发；激活既有标签不走读盘——快照维持）；结构三段式与
  onFileSaved/onActiveTabChanged 同型（try/catch 不阻断）。
- ui/codeview.js：
  - maincSnap/MAINc_SNAP_MAX/fetchMaincContent/maincContent 特例全删；
    maincSnap→fx snapshotOf 单源；fetchMaincContent→fetchCodeFile 通用。
  - baselineStoreLoad 过 migrateBaselineStore（幂等迁移）。
  - baselineCommitDisk 推进语义：snapshotFiles 清单保留（旧 content 先搬
    入新快照防丢）→ 逐文件 re-fetch 当前内容覆盖（删除/失败/超限 →
    null 保底并剔清单）。
  - baselineUpdateFile 第 5 参 maincContent→content 通用（任意文件保存推
    进快照 = 用户确认版）；setSnapshot(entry, path, snap) 为快照写入+清单
    维护单源（onFileLoaded 与 baselineUpdateFile 共用）。
  - onFileLoaded 注册：mtime == 基线 mtime → 快照=读盘内容；mtime 不等 →
    不动旧快照（diff 基准 = 用户确认版）；无基线条目 → 不落域。
  - renderChangePanel main.c diff：oldContent 改读 files["main.c"].content
    （统一字段），curContent = fetchCodeFile（与旧语义一致）。
- 测试：tests/js/disk-baseline.test.mjs 增 4 用例（snapshotOf 边界/migrate
  两例/非对象原样返回）；node 1080 全绿；smoke-08.mjs 13 项全 PASS（S1
  打开建快照/S1b 同 mtime 重开无误报/S2 外部改→面板行级区/S3 未打开无
  content+文件级照常/S4 mtime 不等不建/S5 清空 re-fetch 后快照=磁盘/
  S6 保存=用户确认版/S7 旧格式迁移落盘+特例键删/S8 超限 null 无行级）；
  回归 smoke-02/03/05/06/07 全 PASS。
- 发现并修复的缺陷：baselineCommitDisk 初版重建 store[dir] 时丢
  snapshotFiles 域与旧 content（快照被推进吞掉）——修复为旧域搬迁+re-fetch
  覆盖（smoke-08 S5 首查失败暴露）。
- 已知偏离记录：baselineCommitDisk 推进时 snapshotFiles 清单为空（目录
  从未打开过任何文件）→ 零额外读盘（与 spec 成本段一致）。
- **双轴评审整改（s7）**：①快照清单域删除改派生（files content 非空 =
  持有——平行索引漂移消除；issue 字面「清单域」记录偏离）；②setSnapshot
  → setSnapshotContent；③mtimeEq 抽 fx（baselineDiff/onFileLoaded/
  reloadTabFromDisk 三处单源）；④Spec 主发现「删除/改名文件推进崩溃」
  （旧结构清单枚举无守卫）在派生 + Object.keys(snap) 下已消灭——smoke-08
  补 S9 删除场景验证；carry-over 职责澄清（打开过的文件识别）与 re-fetch
  （null 保底）不矛盾；⑤smoke 裸 setTimeout 全删（await 读盘 + waitFor）。

- [x] 验收 1：打开文件 → 快照入基线；同 mtime 重开 → 快照刷新不误报。
- [x] 验收 2：外部改已打开过的文件 → 变更集合该文件 content（旧值）
  → change-panel 数据源可用（工单 08 消费）。
- [x] 验收 3：从未打开的文件外部改动 → content=null（无行级，文件级照常）；
  超限文件 → null。
- [x] 验收 4：基线推进后快照 = 新确认内容（diff 基准正确）；old 数据兼容
  （旧 localStorage 无 content 不崩）。
- [x] 验收 5：node 单测全绿；smoke 回归。

（双轴评审记录见 spec.md「评审确认」段，整改后更新。）
