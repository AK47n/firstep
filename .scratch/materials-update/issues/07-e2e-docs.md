# 07 — 端到端冒烟 + 文档

**要做什么：** 一条真实链路走通「发布 → 检查 → 弹窗选择 → 下载 → 应用 → 基线更新」，并让 README / 设置页文案与仓库语言规范一致。

**被谁阻塞：** 06

**状态：** resolved

- [x] 端到端冒烟：临时 HTTP 资产服务（本地起，模拟 GitHub releases 列表 + manifest + zip 资产）+ 迷你资料库 → 走 check → apply → status → 落位断言（参照 `.scratch/auto-update/e2e/e2e_update.py` 先例，脚本化）
- [x] README：更新路径段落补「资料库更新」说明（设置页入口 / 增量包 / 不再需要每次下 6 GB）；「大发版」行改写为增量包 + 完整包保留
- [x] 设置页 / 弹窗文案过一遍中文一致性；`VERSIONS.md` 无必须改动则说明理由
- [x] 全量测试套件 + `tests/test_repo_language.py` + ps1 编码检查全绿
- [x] 验收对照 spec 用户故事逐条勾验

## Answer

端到端脚本 `.scratch/materials-update/e2e/e2e_materials_update.py`：mock GitHub（本地 HTTP：releases 列表 + manifest + 批次 zip）→ check（增/改/删计数正确）→ ApplyTask 真下载（SHA256 校验）→ apply_materials_update（解压/备份/删除/写基线）→ 7 步断言全通（含备份镜像、未变更批次原样）。README 大发版改写为「资料库增量包（进度/断点续传/按批次勾选）」+ 完整包保留；更新路径 FAQ 增「资料库更新」条目。全量验收：Python 3281 项、JS 1334 项全绿；`tests/test_repo_language.py` / `test_ps1_encoding.py` 通过。顺带修复两处真实 bug：① 下载文件名双缀（slug 前缀 + part.name）导致应用器找不到 zip——`_download_one` 改用 part.name；② `MaterialApplyError` 未登记 errors 表（test_errors 兜底红）——已登记 400 业务组。VERSIONS.md 无需改动（用户可见发版说明由 README 承载，VERSIONS 属发版时人工记录，本特性落地时随下一版记录）。
