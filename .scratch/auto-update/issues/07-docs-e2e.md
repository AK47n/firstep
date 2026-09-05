# 07 — 用户文档 + 端到端演练（模拟小发版更新全流程）

**要做什么：** 普通用户能在 README / 指南里找到「怎么更新」的答案（不用重下 6.2 GB）；发布者能照 releasing.md 完成一次完整小发版，并演练「发版 → 老版本一键更新 → 更新后正常使用」的全链路。

**被谁阻塞：** 06（端到端演练需要 UI 可用）

**状态：** resolved

- [x] README「版本与发布」节改写：小发版（更新包）/ 大发版（完整包）两级说明 + 用户视角「在设置页检查更新与一键更新」，并说明 git pull 路线平级
- [x] 「常见问题」补充 4 条更新相关条目（怎么更新到新版 / 更新失败怎么办（备份位置 + updater.log）/ 更新中启动器提示 / 更新后配置与资料库是否保留）
- [x] 端到端演练：`.scratch/auto-update/e2e/e2e_update.py`——本地 mock 更新源（release JSON + zip + sha256 + removed）+ 假旧版工具根 → 检查更新（真实 HTTP）/ 下载 + SHA256 校验 / 更新器（备份→覆盖→删除→依赖判定）→ 验证版本号 1.0.0→1.1.0、新文件落位、removed 删除、配置保留、资料库与 .venv 未动、git 仓库未受影响（git pull 路线）
- [x] 演练结论记录到工单（见 Answer；6 步全绿，无回归）

## Answer

端到端演练通过（6 步全绿，可重复执行 `python .scratch/auto-update/e2e/e2e_update.py`）：
① mock 更新源就绪 → ② 检查更新发现 v1.1.0（sha256/removed 契约齐）→ ③ 下载 + SHA256 校验通过 → ④ 更新器完成（备份 3 / 覆盖 4 / 删除 1 / pyproject 未变跳过 pip）→ ⑤ 验证：`__version__` 升到 1.1.0、NEW.md 落位、old.txt 删除、config.json 保留、sources/materials 与 .venv 原样 → ⑥ git status / archive HEAD 正常。README 两级发布说明 + 4 条更新 FAQ 已落地；releasing.md 小发版流程（工单 01）与之配套。
