# 06 — 收尾：CONTEXT.md 词表 + backlog 更新 + 冒烟与全量回归

**要做什么：** 本轮五轴全部落地后收尾——CONTEXT.md「母版」词条补健康/统计/
文件树/树文件内容端点/免提炼导入/confirm 统一语义；backlog §3 标记
master-library-ui-2 已立项落地（替换入口 = 免提炼导入、单文件写侧替换
评估后不做，理由写入）；冒烟清单（CDP 全 tab 实况）与全量回归（pytest +
node --test）跑绿收口。

**被谁阻塞：** 05（全部工单落地后收尾）

**状态：** ready-for-agent

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

（待实施）
