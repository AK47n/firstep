# 02 — 表格精修 + 客户端即时检索（过滤 / 排序 / 统计条）+ 详情弹窗

**要做什么：** 把参考文件库浏览体验升级为：关键字即时过滤（标题 / 类型 /
锚定值 / 简介 / 文件名四合一）+ 平台 chips + 锚定类型 chips + 排序下拉 +
统计条，替换现有 4 个服务端输入框 + 搜索按钮；行渲染令牌化（截断 + tooltip、
锚定徽章、平台 chip、命中文件直出链接）；「查看」升级为完整详情弹窗
（元数据 + 文件清单合并一窗）。操作列 = 详情 · 删除（编辑按钮下一工单）。

**被谁阻塞：** 无——可立即开始（列表数据源 = 既有无参 GET /api/references，
零后端改动；与工单 01 互不依赖）。

**状态：** resolved

- [x] 旧筛选区（4 输入框 + 搜索 / 清空按钮）移除，换成关键字即时输入（防抖）
      + 平台 chips + 锚定类型 chips + 排序下拉；刷新 / 统计 / 空态随之更新
- [x] 关键字过滤匹配：标题 / 类型 / 锚定值 / 简介 / 文件名任一子串命中即显，
      大小写不敏感；文件名命中时标题列直出文件链接（同旧 matched_files UX，
      客户端从条目 files 清单计算）
- [x] 排序：标题 / 类型 / 体量 / 文件数 / 平台五维，稳定排序（同键保序）
- [x] 统计条：条目总数、锚定类型分布（赛题 / 套件 / 未锚定）、平台分布
      （any / stm32 / mspm0）、未锚定数、总体积（formatSize 汇总）——统计
      随过滤结果联动
- [x] 行渲染：标题列截断 + 全文 tooltip、简介截断 + tooltip、锚定三色徽章
      （赛题 / 套件 / 未锚定）、平台 chip 统一样式、体量列保留文件数 + 大小
      口径；删除按钮保持 danger + confirm（含体量）
- [x] 「详情」弹窗：元数据段（标题 / 类型 / 锚定徽章 + 值 / 平台 / 简介全文 /
      体量）+ 文件清单段（过滤输入 + 逐文件大小 + 打开行为沿用：PDF 预览、
      文本内联、其余下载）；Esc / 遮罩 / × 关闭
- [x] 纯函数（挂 window）：refFilterEntries / refSortEntries / refStats /
      refRowHTML / refMatchFiles 等；tests/js 新增单测全绿（过滤规则、排序
      稳定性、统计汇总、渲染子串断言），tests/js 全量保持绿（326 项）
- [x] 空态 / 加载态 / 错误态文案与视觉对齐全站；页面冒烟验证通过（26 项 PASS）

**实现备注（评审修订后）：**

- Spec 轴 C1（主发现）：搜索框 `id="ref-search"` 与生成页参考资料 picker 的
  输入框重名，getElementById 永远取 DOM 靠前的 picker 输入框 → 防抖监听 /
  清空操作全部绑错元素，参考库 tab 关键字检索真实失效（纯函数单测绕过 DOM
  故未捕获）。修订 = 参考库搜索框改名 `ref-filter`；冒烟新增「id 唯一」+「
  防抖态 refUI.q 已更新」两项防回归检查（改造后原冒烟之所以 PASS 正是因为在
  eval 里也取到了同一个 picker 输入框——假阳性，已修正）。
- Spec 轴 C2：`.ref-title-cell` 的 nowrap + overflow:hidden 会单行硬裁
  `.ref-matched` 命中文件链接 → 补 `.ref-title-cell .ref-matched {
  white-space: normal; }` 恢复多行（链接本身 word-break break-all）。
- Standards 轴（判断级，采纳两项）：① loadReferences 失败时不清 ref-rows →
  页面停留「正在读取」假加载态与错误同行 → catch 清空占位（对偶模块库先例）；
  ② refSortEntries 按 by 三次分派（num/val/比较器嵌套三元）Repeated Switches
  → 集中为单一 key() 分派 + 按值类型比较。
- 判断性不修：refStats / refStatsText 硬编码 {any,stm32,mspm0} 与
  {topic,kit,none} 封闭词表（CONTEXT.md 与后端词表确为封闭三值，统计条固定
  口径）；refChipRowHTML 与 libChipRowHTML 字面重复（data-* 前缀不同，对偶
  有意为之）；统计条随过滤联动 vs 模块库全量口径（spec 验收明确要求联动，
  注释已明示）。

**后续修复备注（05 轮后，用户反馈）：**

- 用户反馈「删除按钮只看得到一半」：操作列 nth-child(6) 宽度 140px 是
  「查看 / 删除」两按钮时代的旧值；02 轮加「详情」、03 轮加「编辑」后
  三按钮（button padding 7px 14px，各 ~56px ≈ 190px）超宽被裁（fixed 布局）。
  模块库表 auto 布局无此问题。修订 = 列宽 140px → 210px，CSS 注释明文记录
  旧值来历；probe-action-cols.mjs 断言三按钮完整可见（56px×3、无溢出）。
