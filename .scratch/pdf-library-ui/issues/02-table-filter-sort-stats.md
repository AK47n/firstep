# 02 — 表格精修 + 客户端即时检索 + 统计条

**要做什么：** tab-pdf 从「1 个服务端搜索框 + 4 列原始表格」升级为「客户端
全量在手、即时过滤排序」的管理表格：`.lib-table` 令牌 6 列（文件名链接 /
批次 chip / 目录 / 大小 / 修改时间 / 操作），关键字即时输入（防抖）+ 批次
chips + 排序下拉（文件名 / 批次 / 目录 / 大小 / 修改时间）+ 统计条（总数 /
总体积 / 批次数）；旧服务端搜索框与搜索/清空按钮移除（`/api/pdfs?name=`
服务端参数保留——topic 页真题汇总链接仍用）。

**被谁阻塞：** 01（修改时间列与 mtime 排序需要后端字段）

**状态：** resolved（评审 + 修复完成，提交见下方）

**评审结论（双轴，两子代理并行）：**
- Standards 轴：无硬违反；判断句 3 处——① Speculative Generality：
  pdfFilterEntries 的 health/isDup/isBroken 谓词注入当时无调用者（死代码，
  与 ref 系列数据注入模式分道）——**修复**：谓词语义改为「health 置位但
  无谓词 = 不参与」，保留注释明示 04 接线职责（不删：语义修复 + 单测锁定
  后并非投机，04 直接接线）；② 单测未覆盖 pdfChipRowHTML——**修复**：
  补渲染子串断言；③ pdfStats 冗余 batchCount / pdfRowHTML 双重 title——
  保留（轻量、无害，先例一致即可）。CSS td:nth-child(6) nowrap 与全局
  td:last-child 重复 = #tab-reference 同款先例，不判违反。
- Spec 轴：实现忠实于 spec/工单，无 scope creep；3 处轻微——① 加载态缺失
  （spec「空态/加载/错误态」）——**修复**：loadPdfs 前置「正在读取 PDF
  资料库…」占位（对偶模块库/参考库）；② 健康谓词语义瑕疵（health 置位无
  谓词 → 静默清空）——**修复**：改为短路
  `health==="broken" && (f.isBroken ? !f.isBroken(p) : false)`，配单测；
  ③ pdfFilterContext 含 sortBy/sortDir 冗余字段——保留（上下文即 UI 状态
  全量，对偶 refFilterContext）。
- 补充自检：detail 按钮只渲染不接线 = 02 预期（弹窗归 03）；smoke exit code
  语义与 reference 一致（全 PASS=0）。

**验证：** tests/js 350 绿（336 + 14）；pytest 全量 2402 绿；冒烟 20 项
PASS（真实素材 66 份）。

- [x] 纯函数（function 声明 + tests/js extract 抽取范式）：
      `pdfFilterEntries`（关键字匹配文件名/批次/目录/完整路径，大小写不敏感
      × 批次 × 健康状态正交——健康谓词 isDup/isBroken 由调用方经 f 注入，
      无谓词 = 不过滤，工单 04 接线）、`pdfSortEntries`（五维稳定排序，同键
      保序）、`pdfStats`（总数/总体积/批次份数表 batchCounts）、
      `pdfStatsText`（统计条文案，formatSize 注入）、`pdfSubdir`（批次内
      子目录推导，空 = 批次根）、`formatMtime`（epoch 秒 → `YYYY-MM-DD
      HH:mm` 本地时间，缺失 → `—`）、`pdfFilterContext`（组装过滤上下文，
      对偶 refFilterContext）、`pdfChipRowHTML`（批次 chips，data-pdf-chip）
- [x] `pdfRowHTML` 行渲染：文件名链接（pdfFileUrl 打开，截断 + 全文 tooltip）/
      批次 chip / 目录列 / 大小 / 修改时间 / 操作（打开 · 详情按钮）；
      ⚠ 标注位与统计红段为 03/04 预留
- [x] 表格换 `.lib-table` 令牌（表头底纹 / 行 hover / 空态：库空态与过滤空态
      区分，对偶参考库）
- [x] DOM：`#tab-pdf` 旧 filter 输入 + 搜索/清空按钮移除 → 新工具栏
      （pdf-filter 关键字输入防抖 + pdf-batch-chips 批次 chips + pdf-sort /
      pdf-sort-dir 排序 + pdf-filter-clear）；新元素 id 全部 `pdf-` 前缀，
      不与既有 id 冲突
- [x] 统计条：`共 N 份 · 总体积 X · M 个批次`（红段位为 04 预留）
- [x] tests/js：tests/js/pdf-library.test.mjs（12 用例：过滤/排序稳定/统计/
      formatMtime/子目录/行渲染子串）；btn-icons.test.mjs 断言清单同步
      （移除 btn-pdf-search——旧搜索按钮按本工单删除）
- [x] 全量 tests/js 348 绿（336 + 12）+ 冒烟新增对偶脚本
      .scratch/pdf-library-ui/smoke.mjs（20 项 PASS，真实素材库 66 份）

**实现说明：**
- 数据源改 `GET /api/pdfs` 无参全量 + 客户端过滤（checkAndFilter 纯函数），
  `/api/pdfs?name=` 服务端参数未动（topic 页真题汇总链接仍用）。
- loadPdfs 每次进 tab 拉全量 → renderPdfs（过滤/排序/统计/行）→ 事件委托
  绑定 `[data-open-pdf]`（iframe 无：window.open 浏览器原生预览保持）。
- 排查记录：冒烟首跑发现 webapp 8000 是工单 01 前启动的旧进程（/api/pdfs
  无 mtime 字段）→ 重启后 mtime 就位、冒烟全绿（旧进程不加载新路由）。
- 既有失败修复（不属本系列，保回归全绿）：23fe9d8 录入 2026H 未登记
  TOPIC_EN_TITLES → generation_output.py 字典补
  `"2026 年全国大学生电子设计竞赛赛区赛（TI 杯）—— 暨模拟电子系统设计专题赛选拔赛赛题": "2026_TI_Cup_Analog_Electronics_Selection"`，
  注释「全部 9 题」，tests/test_generation_output.py 29 绿。
