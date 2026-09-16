# spec —— 清理线回归：母版工程配置被当编译产物删掉（purge-regression）

## 问题陈述

2026-09-15 的「编译产物不入库」清理（`5ea37e97` 加忽略规则 + `c0f33697` 重写历史删文件）
把 `library/masters/mspm0/.settings/` **整个扫掉了**，其中
`org.eclipse.core.resources.prefs` 里钉着 CCS 工程编码 `encoding/<project>=UTF-8`。

它不是可再生的构建产物，而是随母版分发给**生成工程**的工程配置。后果有两层：

1. **用户侧**（当时没被任何人看见）：从那以后生成的 CCS 工程在默认 GBK 的工作区里打开，
   中文注释有乱码风险；
2. **仓库侧**：`tests/test_readme.py::test_directory_structure_syncs_with_master_templates`
   当场变红（README 目录结构章 ↔ 母版实况双向同步），但**这条红在 main 上挂了一整天**
   ——因为没人跑全套（正是 `test-speedup` 那条线要解决的事）。

根因不是"删错一个文件"，而是**两处机制都漏了它**：忽略规则按目录名 `.settings/` 一刀切；
清理器的人工确认闸门只认「像源码」的扩展名，而 `.prefs` 不在名单里。

## 方案

1. **还原**两个文件（内容取自两处独立的清理前来源：线上 `firstep-full-v1.2.0.zip` 与沙箱
   `firstep-sim`，逐字节对比同源）；
2. **让 git 看得见**：`.gitignore` 给母版 `.settings/` 加例外（不加 = 文件在盘上但不会进包）；
3. **让清理器不再静默删**：`scripts/make-purge-list.mjs` 加显式 `KEEP` 例外（母版 `.settings/`
   视为工程配置），并把 `.prefs` / `.ccsproject` / `.cproject` / `.project` 加进「命中即要求
   人工确认」的扩展名闸门；
4. **守卫**：`tests/test_master_template_config.py` 钉住「母版必须带 UTF-8 编码钉」与
   「codan 设置也在场」（同一批工程配置，只钉一个的话下次可以只删另一个而不被发现）。

## 用户故事

1. 作为用 CCS 打开生成工程的人，我想要工程的编码设置是 UTF-8，以便中文注释不乱码。
2. 作为维护者，我想要「清理产物」这类动作在碰到工程配置时**停下来问人**，以便不再靠事后发现。
3. 作为下一个接手的人，我想要这条判例**写在代码旁边**（测试文件顶部 + `.gitignore` 注释 +
   脚本 `KEEP` 注释三处互相指路），以便不会又删一遍。

## 测试决策

- 守卫落在 `tests/test_master_template_config.py`：判据是**内容里那一行**
  （`encoding/<project>=UTF-8`），不是「文件存在」——空文件或写坏的同名文件同样致命。
- 反向验证（本仓库惯例，新守卫必须证明「破坏它就红」）：搬走编码钉 → 红；搬回 → 绿（sha256 复核）。
- 清理器的闸门用**反证实测**证明：把 `KEEP` 临时清空重跑工具 → 退出码 1 并点名那两个文件。

## 范围外

- **给老用户补上这两个文件**：那要发下一个版本（线上 v1.2.0 包里仍是缺的）。见
  `docs/agents/local-environment.md` 第 0 节与第 7.1 节。
- **重写历史/second purge**：不复盘——历史里已经被删掉的这两个文件内容已由本次还原回到工作树，
  重写历史不会让它们"回来"。
- **`sources/materials/` 的历史清理**：另一笔账，数字已测，见 `.scratch/materials-history-purge/`。
