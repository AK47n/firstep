# 02 — 工具版本号对齐（__version__ 与 README / tag 同步）

**要做什么：** 让 `src/contest_generator/__init__.py` 的 `__version__` 成为唯一可信的工具版本，且与 Release tag、README「当前版本」一致；`/api/health` 与将来的「检查更新」都吃它。

**被谁阻塞：** 无——可立即开始（只动 `__init__.py` 一行与文档，与代码查看器优化零文件交集）。

**状态：** resolved

- [x] `__version__` 改为与当前最新 Release tag 一致的值（`1.0.0`，与 GitHub Release v1.0.0（2026-08-30）对齐；先前会话已落地）
- [x] releasing.md 发版流程加入「打 tag 前同步 `__version__` 与 README『当前版本』」明确步骤（工单 01 落地后并入其验收：releasing.md「发版前：三处版本号同步」——`__version__` / pyproject version / README + VERSIONS.md）
- [x] 全仓搜索确认没有第二个写死版本号的文本需要同步（`pyproject.toml project.version = "1.0.0"` 为打包元数据副本，已与 `__version__` 一致，并在 releasing.md 写明两处同步约定）

## Answer

`__version__ = "1.0.0"`（`src/contest_generator/__init__.py`）已与 v1.0.0 Release 对齐（先前会话提交 bf793d0d）。本次收尾：确认第二处版本号在 `pyproject.toml project.version`（1.0.0，一致），把它纳入 releasing.md 的三处同步清单，避免未来只改 `__init__.py` 造成漂移。
