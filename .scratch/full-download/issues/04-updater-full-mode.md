# 04 — 更新器：全量模式（分卷解压 → 备份 → 覆盖 → 基线写回）

**要做什么：** 全部卷下载校验完成后，由一个**独立进程**把工具目录安全替换到新版本：先做恶意路径整体拒绝，再把将被覆盖的文件备份出来，然后落位包内全部文件、写回资料库基线清单、按删除清单清理废弃文件，并记录结果。任何一步失败都保留备份与中文失败原因，不留下半替换状态。

**被谁阻塞：** 03（替换由下载完成后的编排拉起）

**状态：** resolved

- [x] 更新器新增全量模式入口：接受「分卷清单 + 删除清单 + 资料库基线清单」三样输入（命令行可驱动，便于集成测试）
- [x] 多分卷按序解压：全部卷的条目**先整体预检**（`..` / 绝对路径 / 盘符前缀 / 反斜杠一律拒绝，越界即整体拒绝且不写任何文件）
- [x] 备份：将被覆盖且已存在的文件镜像到用户数据目录 `updates\backup\<时间戳>\`，日志给出备份位置
- [x] 覆盖落位：逐条目「先写临时文件再原子替换」，不出现半写文件
- [x] 基线写回：把完整包清单里的资料库基线清单写入 `sources/materials/.materials-manifest.json`（该文件不在包内也照样生成）——完成后本地从「无基线」转为「有基线」
- [x] 删除清单：按基线清理废弃文件（路径校验落工具根内；不存在 / 非普通文件跳过并记日志）
- [x] 包外文件原样：用户配置、任务状态、生成的工程、`.venv`、以及资料库里那些**不进包的第三方安装包**在更新后逐个仍在（专项断言：干扰件不被误删）
- [x] 结果与失败：成功 / 失败都写结果文件（状态、版本、时间、备份位置、错误），失败保留待处理标记并有中文提示
- [x] 集成测试：临时目录构造迷你完整包（两卷 zip + 清单 + 删除清单 + 基线清单）→ 断言覆盖落位、备份生成、删除生效、基线写回、包外文件与干扰件原样
- [x] 集成测试：恶意条目（`../evil`）整体拒绝且目标目录零改动；分卷顺序打乱仍按清单序应用

## 实施记录（2026-09-13）

**实现面**
- `tools/update-app.py` 扩展全量模式：`UpdateOptions` 新增 `full_parts` / `full_manifest_path` 与 `is_full_mode`；新增 `load_full_manifest`（**本地路径或 http(s) URL 都能读**，容忍 BOM）、`full_zip_paths`、`validate_all_parts`（整体预检）、`extract_all_parts`、`write_materials_baseline`、`remove_named_files`（与小发版 `remove_removed_list` 共用路径校验单源）；结果文件新增 `mode` 字段；成功后写「已装版本」标记 `updates/full-installed.json`（检查更新端点据此报当前版本）。CLI 新增 `--full-manifest` 与可重复的 `--part`。
- 新增 `src/contest_generator/full_apply.py`：应用编排（写 `pending-update.json` → **以独立进程**拉起更新器 → 返回中文摘要），`build_updater_command` 可单测、`spawn` 可注入。清单走 URL 交给更新器自己拉（清单含全量文件清单，几 MB 级，不在前端与后端之间搬运）。
- `webapp.py` 的 `_full_apply_complete` 接通编排（此前是抛错占位）；check 响应新增 `manifest_url` 字段供编排使用。
- 测试：`tests/test_full_updater.py` 11 例 + `tests/test_full_apply.py` 9 例；小发版旧路径（`test_update_app.py` / `test_update_apply.py`）全绿无回归。合计 73 passed。

**关键决策**
- **整体预检先于任何写盘**：任一越界条目 → 全部卷一起拒绝，目标目录零改动（测试钉死「合法卷也不落位」）。
- **删除清单只以完整包清单为基线**：用户本机那些**不进包**的第三方安装包永远不会出现在 `removed` 里，故不会被误删（专项断言）。
- **已装标记必须落盘**：丢了它检查更新会报「版本未知」并建议再下一次完整包——这也是当前所有用户的状态来源，故成功路径强制写入。

**踩坑记录**
- `apply_full_package` 的 `spawn` 参数默认值在**函数定义时**绑定 `default_spawn`，`monkeypatch.setattr(full_apply, "default_spawn", ...)` 改不到它——测试要 patch webapp 里对 `apply_full_package` 的引用（假编排），或直接给 `spawn=` 具名注入。已在测试注释里写明。
