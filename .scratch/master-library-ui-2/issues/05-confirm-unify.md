# 05 — confirm 仓库级统一：共享确认弹窗 + 8 处迁移

**要做什么：** 新建共享确认弹窗（Promise<boolean>，复用 .ref-files-overlay
遮罩语言与 Esc / × / 点遮罩取消），把仓库剩余 8 处原生 `confirm()` 全部
迁移：母版提炼确认「确认并入库」（pilot）/ 桌面同名工程覆盖 / 编译修复
回滚 / 修订深化回滚 / 模块删除 / 模块平台文件移除 / 参考文件条目删除 /
赛题条目删除；顺带把流程中的原生 `alert()` 错误提示统一为既有 toast（1:1
等价迁移，不做交互重设计）。

**被谁阻塞：** 04（母版卡 UI 在本系列 01-04 连续改动，pilot 的
btn-confirm 接线在 04 之后做防冲突）

**状态：** resolved

## 验收标准

- [x] fx/overlay.js：`overlayConfirmHTML({title, message, danger, confirmText, cancelText, extra})` 纯件（遮罩 + 标题 + 文案 + 双钮 + 就地错误槽）；ui/confirm.js：`confirmModal(opts) -> Promise<boolean | string>` 工厂（含 `[data-confirm-value]` 时解析其 value；Esc / × / 点遮罩 = 取消；重复调用时旧弹窗先关）——原写 `Promise<boolean>`，string 型为 04 平台下拉所需。
- [x] 8 处确认全部迁移：母版提炼确认（btn-confirm，pilot）/ generate-core
  同名工程覆盖 / generate-fix 回滚 / generate-revise 回滚 / library 模块
  删除 + 平台文件移除 / reference 条目删除 / topic 条目删除；确认文案
  保持原文（弹窗渲染非 alert 拼接）
- [x] 原生 `alert()` 错误提示审计并迁移为 toast（deleteTopic 等）；仓库
  静态扫描原生 confirm(/alert( 零命中（新守卫测试）
- [x] tests/js：overlay-confirm.test.mjs（HTML 纯件：标题/文案/双钮/danger
  类）；守卫断言 ui 目录各文件无 `confirm(` / `alert(` 裸调用
- [ ] 冒烟：弹窗开合（Esc / 点遮罩取消 / 确认闭合）+ 母版提炼确认按钮
  点开弹窗（不真调）；全量 node --test + pytest 保持绿
- [x] 中文提交

## 实施记录

（2026-08-27 完成）

- 8 处原生 confirm() 全部迁移到共享 confirmModal（既有工厂即本系列 04
  创建的 ui/confirm.js + fx/overlay.js 纯件）：母版提炼确认「确认并入库」
  （btn-confirm）/ generate-core 桌面同名工程覆盖 / generate-fix 修复回滚 /
  generate-revise 修订深化回滚 / library 平台文件移除与模块删除 / reference
  条目删除 / topic 条目删除；确认文案 message 保持原文（1:1 等价），
  title 为弹窗短标题；rollback 两处 title 评审修正为「确认回滚？」（避免与
  message 首句逐字重复）。
- 原生 alert() 8 处全部迁移 toast：files.js 文件名重复（补 toast import）、
  library 模块删除失败与「至少需要一个源文件」、reference 删除失败/未找到
  条目/文件打开失败/详情失败、topic 删除失败。
- 新增 tests/js/confirm-guard.test.mjs：static/js 全树（ui + fx + app.js
  递归）剥注释后扫描，断言无裸 \bconfirm( / \balert(（评审修正：原守卫只扫
  ui 目录，扩到仓库全静态面）。
- confirmModal 级联清理（评审修正）：新工厂创建时先关旧弹窗——cleanup
  解绑 keydown 监听并 resolve(false)，消除并发/重入时监听残留与 Promise
  永不 settle 的隐患（activeCleanup 单槽，无并发场景零影响）。
- 回归：node --test 473/473（新增守卫）、pytest 2498；node --check 全部
  改动 ui 模块语法通过。
- 评审：code-review 双轴——Standards 无硬违反（confirm.js 被 7 模块单向
  import 无环、overlay.js 纯件/桥合规、app.js 不入链）；判断项 3 已修 2
  （title/message 重复、keydown 残留）留档 1（8 文件同构迁移属规格所致）；
  Spec 部分实现 1（守卫仓库级覆盖，已修），confirmModal boolean|string 型
  为 04 既有差异（8 处均 boolean 路径），无 creep。

## 验收口径修订（2026-09-09 在途盘点）

- `confirmModal` 返回 `Promise<boolean | string>`（含 `[data-confirm-value]` 时解析其 value），原写 `Promise<boolean>`；冒烟项（点遮罩取消 / 确认闭合）仍未做实，故留空。

