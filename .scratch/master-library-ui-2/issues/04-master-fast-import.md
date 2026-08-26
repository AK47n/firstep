# 04 — 母版快速导入（免提炼替换入口）：选文件夹 → 确认 → 原子替换

**要做什么：** 母版卡新增「直接导入替换」：选文件夹整夹暂存（复用既有暂存
流程）→ 平台下拉（复用既有平台选项渲染）→ 确认弹窗（「将整体替换该平台
旧母版」警告 + 不可恢复提示，走共享确认弹窗）→ 后端免提炼入库（结构校验
+ 临时目录 + 原子替换 + 备份回滚 + autocommit，复用既有入库编排，全程零
LLM 调用）→ toast + 刷新母版库列表。单工程母版升级（如官方模板换新版
SDK）不必再走「扫描 → AI 提炼 → 报告」全流程。

**被谁阻塞：** 03（需共享确认弹窗已就位，且母版卡 UI 改动与 01-03 同文件
防冲突）

**状态：** ready-for-agent

## 验收标准

- [ ] master_store 域函数 `import_master_direct(masters_dir, platform,
  source_dir)`：复用 import_master（结构校验失败不动盘 / 备份回滚 / 占用
  中文说明 / autocommit 自动提交），sources = [源目录名]；平台非法 /
  源目录不存在 → 中文 MasterError
- [ ] API：POST /api/masters/import（body {platform, project_dir}；
  project_dir = 服务器本地路径，与既有 /api/masters/scan 同风险面）；
  结构校验失败 400 中文、成功返回 {platform, sources, warnings}（复用
  MasterMeta 形状）
- [ ] UI：母版卡「直接导入替换」按钮（卡片1 母版提炼区侧）→ 选文件夹 →
  平台下拉（复用 renderNewPlatformOptions）→ 确认弹窗（替换警告 + 双钮）
  → POST → toast + 刷新列表；失败弹窗保留可重试
- [ ] pytest：test_master_store.py（import_master_direct：成功替换旧母版
  元数据更新 / 结构校验失败零盘面改动 / 平台非法）+ test_webapp.py
  （import 200 / 400 中文）
- [ ] 冒烟：导入弹窗打开（平台下拉选项数断言）→ 确认按钮存在（**不真导**，
  探针可直接 400 路径：空 project_dir / 非法平台）；零写库
- [ ] 既有全量回归保持绿；中文提交

## 实施记录

（待实施）
