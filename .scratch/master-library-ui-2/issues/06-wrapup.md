# 06 — 收尾：CONTEXT.md 词表 + backlog 更新 + 冒烟与全量回归

**要做什么：** 本轮五轴全部落地后收尾——CONTEXT.md「母版」词条补健康/统计/
文件树/树文件内容端点/免提炼导入/confirm 统一语义；backlog §3 标记
master-library-ui-2 已立项落地（替换入口 = 免提炼导入、单文件写侧替换
评估后不做，理由写入）；冒烟清单（CDP 全 tab 实况）与全量回归（pytest +
node --test）跑绿收口。

**被谁阻塞：** 05（全部工单落地后收尾）

**状态：** resolved

## 验收标准

- [ ] CONTEXT.md：母版词条补 health/stats（一次算好 + 徽章）、文件树端点
  与树文件安全语义（路径安全 + 二进制 + 1MB 上限）、/api/masters/import
  （免提炼 + 复用入库编排）、confirm 共享工厂（ui/confirm.js + fx/overlay.js）
- [ ] backlog.md §3：已立项条目改 ✅ 已落地（5 项）；「单文件写侧替换」
  评估后不做——理由一句（母版=生成根，关键文件为模板/默认值或渲染器
  现写）+ 指向本轮 spec 范围外
- [ ] 冒烟清单全绿（母版 tab：表格徽章 / 详情树 / 高亮复制 / 导入与提炼
  确认弹窗开合，零真删零真导）
- [ ] 全量回归：pytest 全量 + node --test 全量 + 仓库语言检查
  （test_repo_language / test_ps1_encoding 类）绿
- [ ] 中文提交

## 实施记录

（2026-08-27 完成）

- CONTEXT.md「母版」词条补本轮五个主轴语义：体检（health/stats 一次算好 +
  徽章行 + 统计行，_disk_master_dir/_master_key_catalog/_top_level_artifact_dirs
  单源收敛）、文件树（master_tree_files / read_master_tree_file 安全语义
  （is_unsafe_path 对齐 + resolve 兜底 + 二进制 + 1MB）/ tree 与 tree/{path}
  端点 / 前端树纯件与 _masterFileURL）、预览增强（highlight.js 复用
  cHighlight 单源 + XML + 128KB 回退；masterContentHTML 三态 + 复制钮）、
  免提炼导入（import_master_direct + POST /api/masters/import + 直接导入
  替换按钮）、confirm 统一（confirmModal / overlayConfirmHTML 共享工厂 +
  8 处迁移 + alert 归 toast + 守卫测试）。
- backlog.md §3：✅ 已落地（master-library-ui-2/01-06）；五项候选全部落地
  并注明落地形态；「单文件写侧替换」评估后不做——理由一句（母版=生成根，
  关键文件为模板/默认值或渲染器现写 → 破坏生成基线）+ 指向本轮 spec 范围外。
- 冒烟：新建 .scratch/master-library-ui-2/smoke.mjs（CDP 9251 + webapp
  8000，零真删零真导）17/17 ALL PASS——健康徽章/表头列/统计行/文件树渲染
  与树文件预览/高亮 span（[class*="tok-"] 选择器，.tok- 字面类名是初版
  冒烟自己的错）/复制钮/导入按钮就位/共享确认弹窗开合（经赛题库删除按钮
  实测工厂接线，取消与 Esc 均关闭且零写库）/mspm0.syscfg 内容；截图存档
  shot-06-detail-tree.png。注：旧冒烟（master-library-ui/smoke.mjs）的
  `state` 就绪判定在阶段 2 模块化后已失效（state 不再是全局），本轮冒烟
  全部改用 DOM 可观察事实；8000 webapp 是旧代码进程，重启后新端点生效
  （smoke 首轮 8 FAIL = 旧后端无 health/stats/tree，重启后 17 PASS）。
- 全量回归：pytest 2498 绿（含 test_repo_language / test_ps1_encoding）、
  node --test 473/473 绿。
- 评审：单一收尾工单无独立双轴评审（01-05 均已各自双轴通过并修正）。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
