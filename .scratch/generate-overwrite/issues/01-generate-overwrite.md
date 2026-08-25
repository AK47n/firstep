# 01 — 生成前覆盖保护（确认覆盖 + 单份 .bak 快照）

**要做什么：** 同题同平台再生成撞「同名工程」400 时，前端弹确认框（旧工程将备份为 `<name>.bak`）→ 确认后自动重发 `payload + overwrite: true`；后端 `exists` + `overwrite` 分支改为**先备份后覆盖**（旧目录整体改名为 `<name>.bak`，单份策略），随后正常生成；overwrite 缺省/非 True = 现行 400 原文案（向后兼容）。手动模式与现有守卫（clean 清理/busy/失败清理/explorer）零改动，失败时 `.bak` 保留（旧工程数据不丢）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

## 验收记录（提交信息见 git log「工单 generate-overwrite/01」）

- 实现：generation_output.py `backup_project_dir(output_dir)`（目标 `<name>.bak`；已存在先移除——目录 rmtree / 文件 unlink——再 rename；rename 失败 OSError 上抛 → 400 文件操作失败，旧工程未动）；webapp.py generate 路由 `overwrite = payload.get("overwrite") is True`（严格，非布尔视为缺省），`exists`+False → 现行 400 原文案、`exists`+True → backup 后生成（new/clean 幂等忽略）；index.html 纯函数 `isConflictError(message)`（`CONFLICT_MSG_PREFIX` = 「桌面上已有同名工程」）+ `conflictDirName(message)`（`/「([^」]+)」/`），catch 冲突分支 = confirm（`.bak` 提示）→ 确认自动重发 `{...payload, overwrite: true}` 并 `renderGenerateSuccess(data)`（抽取自主成功路径，含自动编译修复触发）；取消 = 原 400 文案。
- 关键修复（冒烟抓到）：payload 原为 try 块内 `const`，catch 块引用会 ReferenceError（块级作用域）→ 声明提到 try 外（`let payload`）。
- 测试：tests/test_generation_output.py +3（改名/替换旧 .bak/.bak 是文件 unlink）；tests/test_webapp.py +6（覆盖成功 .bak 含旧标记/两次覆盖单代/缺省 400 原文案/非布尔忽略/new+overwrite 幂等/一致性护栏「桌面上已有同名工程」前后端锚点）；tests/js/generate-overwrite.test.mjs 5 项绿。
- headless 冒烟 12 项全 PASS（mock apiPost/confirm：确认→第三发 overwrite:true→成功渲染；取消→两发终止+原 400 文案；payload 沿用原值断言）。
- 全量 pytest 2364 绿（2355 基线 + 9）；全量 tests/js 278 绿（273 基线 + 5）。

- [x] `generation_output.py` 加 `backup_project_dir(output_dir) -> Path`：目标 `<name>.bak`；已存在先移除（目录 rmtree / 文件 unlink）再 rename；rename 失败 OSError 上抛（400 文件操作失败，用户关 Keil 重试；原目录未动不受损）
- [x] `webapp.py` generate 路由：`overwrite = payload.get("overwrite") is True`（严格）；`exists` + overwrite=False → 现行 400 原文案；`exists` + True → backup 后继续生成；new/clean + True → 忽略幂等；手动模式不生效
- [x] 前端纯函数 `isConflictError(message)`（前缀「桌面上已有同名工程」）+ `conflictDirName(message)`（`/「([^」]+)」/` 提取，空则降级文案）
- [x] btn-generate catch 冲突分支：confirm（含 .bak 备份提示与目录名）→ 确认 = 重发 `{...payload, overwrite: true}` 并渲染成功（抽 `renderGenerateSuccess(data)` 与主路径共用，含自动编译修复触发）；取消 = 显示原 400 文案
- [x] 一致性护栏：pytest 断言 index.html 与 webapp.py 均含「桌面上已有同名工程」
- [x] pytest：`backup_project_dir` 单测（正常/替换旧 .bak/.bak 是文件 unlink）；桌面端到端（overwrite 覆盖成功 + .bak 含旧标记 / 两次覆盖单代 / 缺省 400 原文案 / 非布尔忽略 / new+overwrite 无 .bak）
- [x] tests/js/generate-overwrite.test.mjs：isConflictError 与 conflictDirName 单测
- [x] headless 冒烟 `.scratch/generate-overwrite/smoke.mjs` 全 PASS（mock apiPost 第一次 conflict 400 + mock confirm true → 断言重发 payload.overwrite=true + 成功渲染；短路 startFixCenter/toolchains）
- [x] 全量 pytest 绿与全量 tests/js 绿（既有 generate-conflict-guard 测试零改动）
- [x] 中文提交信息（CHANGELOG 由 post-commit hook 自动补录）
