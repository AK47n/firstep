# 04 — 母版快速导入（免提炼替换入口）：选文件夹 → 确认 → 原子替换

**要做什么：** 母版卡新增「直接导入替换」：选文件夹整夹暂存（复用既有暂存
流程）→ 平台下拉（复用既有平台选项渲染）→ 确认弹窗（「将整体替换该平台
旧母版」警告 + 不可恢复提示，走共享确认弹窗）→ 后端免提炼入库（结构校验
+ 临时目录 + 原子替换 + 备份回滚 + autocommit，复用既有入库编排，全程零
LLM 调用）→ toast + 刷新母版库列表。单工程母版升级（如官方模板换新版
SDK）不必再走「扫描 → AI 提炼 → 报告」全流程。

**被谁阻塞：** 03（需共享确认弹窗已就位，且母版卡 UI 改动与 01-03 同文件
防冲突）

**状态：** resolved

## 验收标准

- [x] master_store 域函数 `import_master_direct(masters_dir, platform,
  source_dir)`：复用 import_master（结构校验失败不动盘 / 备份回滚 / 占用
  中文说明 / autocommit 自动提交），sources = [源目录名]；平台非法 /
  源目录不存在 → 中文 MasterError
- [x] API：POST /api/masters/import（body {platform, project_dir}；
  project_dir = 服务器本地路径，与既有 /api/masters/scan 同风险面）；
  结构校验失败 400 中文、成功返回 {platform, sources, warnings}（复用
  MasterMeta 形状）
- [x] UI：母版卡「直接导入替换」按钮 → 选文件夹 → 平台下拉（复用 renderNewPlatformOptions）→ 确认弹窗（替换警告 + 双钮）→ POST → toast + 刷新列表；失败弹窗保留可重试。**落位** = 母版库卡顶部工具栏（原写「卡片1 母版提炼区侧」，实施期调整，功能等价）。
- [x] pytest：test_master_store.py（import_master_direct：成功替换旧母版
  元数据更新 / 结构校验失败零盘面改动 / 平台非法）+ test_webapp.py
  （import 200 / 400 中文）
- [ ] 冒烟：导入弹窗打开（平台下拉选项数断言）→ 确认按钮存在（**不真导**，
  探针可直接 400 路径：空 project_dir / 非法平台）；零写库
- [x] 既有全量回归保持绿；中文提交

## 实施记录

（2026-08-27 完成）

- 后端：master_store.py 新增 `import_master_direct`（复用 import_master 全编排
  ——结构校验（失败零盘面）/ 临时目录 / 原子替换 / 备份回滚 / 占用中文 /
  autocommit；sources = [源目录名]；源目录不存在 → 「源目录不存在：…」；
  平台名校验前置（非法平台名先于源目录检查报错，注释说明次序意图））；
  webapp 新增 POST /api/masters/import（payload {platform, project_dir}，
  与 /api/masters/scan 同风险面——scan 的 project_dirs 同样来自请求体，
  本机工具语义；成功返回 MasterMeta.to_dict()）。
- 共享确认工厂（本工单创建，pilot = 快速导入确认；spec 05 的 pilot 表述为
  「母版提炼确认」，两处不一致但 05 会迁移全部 8 处，先引入工厂不构成冲突）：
  新建 fx/overlay.js overlayConfirmHTML（title/message/danger/confirmText/
  cancelText/extra 纯件，消息 esc、extra 由调用方保证）+ ui/confirm.js
  confirmModal（Promise 解析：取消/遮罩/Esc → false；确认 → true，或有
  [data-confirm-value] 时解析其 value——spec 只写 Promise<boolean>，为平台
  下拉加 string 型，属 pilot 所需合理扩展）；交互与既有 .ref-files-overlay
  模式一致（Esc/×/点遮罩）。
- UI：母版库卡顶部工具栏「直接导入替换（免提炼）」+ 隐藏 webkitdirectory
  输入（复用 /api/masters/stage 整夹暂存：穿越拒绝/清洗/噪音跳过/512MB）→
  confirmModal（平台下拉选项 = 既有「新增平台」select 的当前选项，同源
  /api/state，未新开数据面）→ POST → toast + loadMasters()；
  失败弹窗保留可重试：失败原因并入消息、确认弹窗重开（免重选文件夹）。
- 测试：test_master_store.py 增 4 例（成功替换旧母版 sources=[目录名] /
  结构校验失败零盘面 / 源目录不存在 / 平台非法）；test_webapp.py 增 3 例
  （200 形状 / 非法平台 400 / 结构失败 400 零库写入）；test_autocommit.py：
  import_master_direct 登记 delegated，并把 delegated 校验从「调用方链」扩展
  为「调用方 ∪ 被调用链」（_reaches_commit 双向 BFS）——薄委托的调用方在
  webapp（五模块外），旧规则必红；扩展为旧规则超集（既有 delegated 无一
  放宽变绿），注册表注释同步改写；tests/js/overlay-confirm.test.mjs 新增
  （纯件 4 例：结构/默认文案/extra 透传/转义）。
- 回归：pytest 全量 2498 绿、node --test 472/472。
- 评审：code-review 双轴——Standards 无硬违反，判断项 4 留档（_reaches_commit
  放宽经论证合理——注释说明放宽理由；import_master_direct 与 import_master
  双平台校验——次序意图注释已补；confirm 选项 schema 双处解构——纯件单源
  记录在案，超小先不抽象；通用弹窗复用特性域类名——与既有先例一致）；
  Spec 采纳 2 项（弹窗保留可重试按工单落实、平台校验前置注释），其余偏差
  可接受（confirmModal string 返回/extra、客户端 .git 预滤、按钮落母版库卡
  而非卡片1、文案走「备份+git 兜底」而非「不可恢复」——与 spec 的 git
  回滚表述一致）。

## 验收口径修订（2026-09-09 在途盘点）

- 「直接导入替换」按钮落位 = 母版库卡顶部工具栏（原写「卡片1 母版提炼区侧」，功能等价）；冒烟项（开弹窗 / 下拉选项数 / 400 路径）仍未做实，故留空。

