# 生成前覆盖保护（E1）——规格说明

## 问题陈述

同题同平台再生成目前必然 400（「桌面上已有同名工程…请先删除该目录或修改题名后再生成」）——护栏安全但体验断头：用户明明想重生成（改了题面/模块/引脚），却只能手动去桌面删目录（误删风险）或放弃。安全护栏正确，缺的是**有确认的覆盖通道**：用户明确确认后，旧工程先快照再覆盖——数据不丢、流程不断。

现有守卫（工单 generate-conflict-guard/01）保持不动：`exists` → 400、`clean` 残渣 → 清理后生成、失败不留半成品、成功 explorer 聚焦。本特性只给 `exists` 分支加一条**显式确认 + 先备份后覆盖**的路径。

## 方案

### 后端（webapp.py + generation_output.py）

- `payload.overwrite`（可选布尔，缺省/非 `True` = 关闭——向后兼容，旧请求行为逐字节不变）：
  - `exists` + overwrite 缺省 → 现行 400 原文案（一字不改）。
  - `exists` + overwrite=True → **先备份后覆盖**：`backup_project_dir(output_dir)`（generation_output.py 新函数）把旧目录整体改名为 `<name>.bak`（同目录、原子、零复制），随后正常生成到原名目录。
  - `new`/`clean` + overwrite=True → 忽略（幂等，无备份行为）。
  - 手动模式：verdict 恒为 `manual`，overwrite 不生效（范围外）。
- `backup_project_dir(output_dir) -> Path`：
  - 目标 = `output_dir.with_name(output_dir.name + ".bak")`。
  - **单份策略**（用户决策）：目标已存在则先移除（目录 rmtree / 文件 unlink——被破坏的旧备份视同垃圾），再 `rename`。
  - rename 失败（如 Keil 正打开工程占用 → WinError 32）→ OSError 上抛 → errors.py 既有 `OSError → 400「文件操作失败：…」`，用户关闭 Keil 后重试；**绝不遗留半状态**（先删旧 .bak 后 rename 失败 = 旧工程仍在原名目录未被破坏——rename 失败即原目录未动，安全）。
  - override 快照命名冲突：`.bak` 目录本身含 `.contest_context.json`/main.c 不影响后续 `desktop_topic_dir_verdict`（verdict 只查名称 = `output_dir.name` 的目录，不含 `.bak` 后缀）。
- 失败语义：备份成功后生成失败 → 既有桌面失败清理 `rmtree(output_dir)` 只清新目录半成品，`.bak` 保留（旧工程数据不丢，下次可重试）。
- 400 冲突文案不变（E2 已补「换平台自动带后缀新目录」提示）；覆盖成功走既有成功路径（explorer 聚焦新目录、recent.json 记新目录——`.bak` 不入记录）。

### 前端（index.html，btn-generate catch 冲突分支）

- 纯函数（tests/js 正则抽取）：
  - `isConflictError(message)`：400 detail 以「桌面上已有同名工程」开头 → true。
  - `conflictDirName(message)`：正则 `/「([^」]+)」/` 提取目录名（如 `Auto_Car_STM32`）；提取失败返回空串。
- catch 分支：`isConflictError(e.message)` → `confirm("桌面上已有同名工程「<name>」：旧工程将先备份为「<name>.bak」，然后覆盖生成全新工程。确定覆盖并重新生成？")`：
  - 确认 → **自动重发** `apiPost("/api/generate", {...payload, overwrite: true})` → 成功走渲染（抽取 `renderGenerateSuccess(data)` 与主成功路径共用，含自动编译修复触发）；失败显示 e2.message。
  - 取消 → 显示原 400 文案（`e.message`），不重发。
- 覆盖重发的 payload = 原 payload + `overwrite: true`（用户确认时的题面/模块/引脚/模板等全部沿用，无重新输入）。
- 不确定目录名（conflictDirName 空）时 confirm 文案降级为「旧工程将先备份为同名 .bak 备份」。

### 一致性护栏

- pytest 防漂移测试：断言 index.html 与 webapp.py 都含「桌面上已有同名工程」字形（冲突文案前缀前后端单源锚定）。
- 后端 `backup_project_dir` 单测（tests/test_generation_output.py）：正常改名 / 旧 .bak 被替换 / .bak 是文件时 unlink / 原目录不受影响。

## 测试决策

- 后端 pytest（tests/test_webapp.py，桌面端到端先例 = E2 家族 test_generate_desktop_*）：
  - `test_generate_desktop_overwrite_backs_up_and_succeeds`：预置 exists 工程（.contest_context.json + main.c + 旧标记文件）→ POST（topic_id + overwrite=true）→ 200；断言 `<name>.bak` 存在且含旧标记；`<name>` 为新工程（含新 .contest_context.json、无旧标记）。
  - `test_generate_desktop_overwrite_replaces_old_backup`：连续两次覆盖 → .bak 只剩一代（内容 = 第一代工程标记，第二代工程在原名目录）。
  - `test_generate_desktop_overwrite_missing_still_conflict`：overwrite 缺省或 False → 400 原文案（含「请先删除该目录」）。
  - `test_generate_desktop_overwrite_non_boolean_ignored`：`"true"`（字符串）→ 视为缺省 → 400（严格 `is True`）。
  - `test_generate_desktop_overwrite_ignored_when_new`：目录不存在 + overwrite=true → 正常生成、无 `.bak`。
- 前端 JS 单测（tests/js/generate-overwrite.test.mjs）：isConflictError（命中/未命中/空串）、conflictDirName（正常/无「」/空串）。
- headless 冒烟（.scratch/generate-overwrite/smoke.mjs，CDP 9231 + 环境上下文 + mock window.apiPost/confirm）：点击生成 → 第一次 apiPost reject（construct conflict 400 Error）→ confirm 断言收到 → 确认 → 第二次 apiPost 断言 payload 含 `overwrite: true` → 成功渲染（mock data 完整构造；冒烟前置 `toolchains = {}` + 短路 startFixCenter 防真编译）。
- 回归：全量 pytest 绿 + 全量 tests/js 绿；既有 generate-conflict-guard 测试（400/clean/busy/清理/explorer）零改动。

## 范围外

- 手动模式（用户自选 output_dir）非空目录覆盖——语义不同（用户精心的非工程目录），另议。
- 多代备份保留 / .bak 清理入口 / .bak 可视化管理——单份策略（用户决策）。
- 覆盖的「撤销恢复」入口（用户可自行把 .bak 改回原名）。
- 生成前预检端点（避免 name_topic_english 重复调用）——确认覆盖场景重复调用成本 = 一次 AI 短名 + 一次报告草稿，与正常生成同量级，可接受。

## 补充说明

- 确认框样式沿用仓库 `confirm()` 先例（12 处），不做自定义弹窗（护栏场景原生阻塞够用）。
- `overwrite` 只影响桌面模式 exists 分支；其余路径（clean 清理/busy 409/未知平台 400）行为不变。
