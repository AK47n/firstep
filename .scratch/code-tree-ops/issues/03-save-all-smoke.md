# 03 — 保存全部按钮 + Ctrl+Shift+S + CDP 冒烟 + 收尾

**要做什么：** 状态栏「保存全部」按钮（#btn-code-save-all）+ 全局
Ctrl+Shift+S 快捷键（复用 saveAllDirtyTabs 单源；无脏 → toast「没有未保存
的修改」）；.scratch/code-tree-ops/smoke.mjs（真实 API + 真实磁盘样本）；
回归（node 全量 + pytest 全量）；中文提交 + 工单 resolved。

**被谁阻塞：** 02（树 UI 可用，saveAllDirtyTabs 已有）。

**状态：** resolved

- [ ] 验收 1：状态栏「保存全部」按钮常显；点击 → saveAllDirtyTabs；无脏 →
  toast 中文；保存冲突流程走既有 409 模态。
- [ ] 验收 2：Ctrl+Shift+S 全局触发（与 Ctrl+S 不冲突）；多脏一次落盘
  （mock 计数 = 脏标签数）。
- [ ] 验收 3：smoke.mjs 全 PASS：新建文件（树+tab+写盘）、新建文件夹、
  重命名文件（tab 路径更新）、重命名目录（子树 tab 路径更新）、删除文件
  （tab 关闭）、删除空目录、非空目录删除 → toast 400、脏文件删除 →
  两键确认、保存全部按钮/快捷键计数。
- [ ] 验收 4：回归——node 全量 + pytest 全量 + code-tab-compile /
  code-write-guard 冒烟全绿；提交/工单/CHANGELOG 中文。

**结论：** 已落地。状态栏 #btn-code-save-all + initCodeSaveAll（saveAllFromBar
+ Ctrl+Shift+S，仅 #tab-code.active 拦截；ui/codeeditor.js:727 既有 Ctrl+S
处理器加 `if (e.shiftKey) return;` 让位——之前 Ctrl+Shift+S 被截走导致「假绿」）；
复用 saveAllDirtyTabs 单源；无脏 → toast「没有未保存的修改」；冲突走既有 409
模态；saveAllFromBar 曾缺 import dirtySavableTabCount（ReferenceError，冒烟
抓出后补）。冒烟 .scratch/code-tree-ops/smoke.mjs 24/24 ALL PASS（真实 API +
真实磁盘样本 .scratch/code-tree-ops/sample-proj：main.c + src/app.h + empty/，
跑前 rm 重建、跑后清理）；调试要点：Edge HTTP 缓存吞静态 JS 改动 → smoke 加
Network.enable + Network.setCacheDisabled（Page.reload ignoreCache 对模块
脚本不生效）；toast 断言改 [...querySelectorAll('.toast-text')].some()（前序
常驻 toast 占首槽）。回归：node 1016 全绿、pytest 3101 全绿、code-tab-compile
17 + code-write-guard 11 全 PASS（code-tree-ops 本次改动后已重跑 24/24）。
验收 1-4 全部满足。
