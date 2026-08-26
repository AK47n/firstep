# 05 — confirm 仓库级统一：共享确认弹窗 + 8 处迁移

**要做什么：** 新建共享确认弹窗（Promise<boolean>，复用 .ref-files-overlay
遮罩语言与 Esc / × / 点遮罩取消），把仓库剩余 8 处原生 `confirm()` 全部
迁移：母版提炼确认「确认并入库」（pilot）/ 桌面同名工程覆盖 / 编译修复
回滚 / 修订深化回滚 / 模块删除 / 模块平台文件移除 / 参考文件条目删除 /
赛题条目删除；顺带把流程中的原生 `alert()` 错误提示统一为既有 toast（1:1
等价迁移，不做交互重设计）。

**被谁阻塞：** 04（母版卡 UI 在本系列 01-04 连续改动，pilot 的
btn-confirm 接线在 04 之后做防冲突）

**状态：** ready-for-agent

## 验收标准

- [ ] fx/overlay.js：`overlayConfirmHTML({title, message, danger})` 纯件
  （遮罩 + 标题 + 文案 + 取消/确认双钮，danger 类确认钮 + 不可恢复警示
  样式）；ui/confirm.js：`confirmModal(opts) -> Promise<boolean>` 工厂
  （Esc / × / 点遮罩 = 取消；重复调用时旧弹窗先关）
- [ ] 8 处确认全部迁移：母版提炼确认（btn-confirm，pilot）/ generate-core
  同名工程覆盖 / generate-fix 回滚 / generate-revise 回滚 / library 模块
  删除 + 平台文件移除 / reference 条目删除 / topic 条目删除；确认文案
  保持原文（弹窗渲染非 alert 拼接）
- [ ] 原生 `alert()` 错误提示审计并迁移为 toast（deleteTopic 等）；仓库
  静态扫描原生 confirm(/alert( 零命中（新守卫测试）
- [ ] tests/js：overlay-confirm.test.mjs（HTML 纯件：标题/文案/双钮/danger
  类）；守卫断言 ui 目录各文件无 `confirm(` / `alert(` 裸调用
- [ ] 冒烟：弹窗开合（Esc / 点遮罩取消 / 确认闭合）+ 母版提炼确认按钮
  点开弹窗（不真调）；全量 node --test + pytest 保持绿
- [ ] 中文提交

## 实施记录

（待实施）
