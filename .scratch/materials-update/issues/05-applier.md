# 05 — 用户侧：应用器（解压 / 备份 / 删除 / 写基线）

**要做什么：** 全部所选卷下载并校验通过后，自动把资料库更新到位：安全解压覆盖 → 废弃文件按清单删除 → 旧文件先备份 → 写回新基线清单；全程不需要 7-Zip、不停服、不动软件本体与四个库。

**被谁阻塞：** 04

**状态：** resolved

- [x] zip 条目路径安全校验：`..` / 绝对路径 / 盘符前缀 / 反斜杠一律整体拒绝（规则同 `tools/update-app.py`）；解压目标 = 资料库根 `sources/materials`
- [x] 备份：将被覆盖与将被删除的旧文件复制到 `updates\materials-backup\<时间戳>\`（保留相对目录结构）；备份失败 = 应用中止并中文提示
- [x] 应用顺序：逐卷解压覆盖 → 按该批次 `removed` 清单删除（删除前同样路径校验）→ 全部完成后写回新 `.materials-manifest.json`（含 `batches: {slug: version}`——只更新选中批次，未选批次保留旧版本）
- [x] 状态联动：应用期 `state=applying`；部分批次成功 / 部分失败 = `partial` + 中文提示可重试
- [x] 测试：临时目录集成测试——迷你旧资料库 + 迷你增量 zip + 删除清单 → 断言落位 / 备份 / 删除 / 新清单写回 / 包外文件（`.materials-manifest.json` 之外、未选批次）原样；恶意 zip（`../evil`）整体拒绝；part 顺序应用

## Answer

`src/contest_generator/materials_apply.py`：MaterialApplyError（中文 400/失败态）、safe_join（zip slip 拒绝面同 update-app：反斜杠/绝对/盘符/`..`/resolve 逃逸）、`_validate_zip_members`（预检整体拒绝）、`_backup_entries`（被覆盖+被删除镜像备份，失败中止）、`_extract_zip`（`.update-tmp` + os.replace 不半写）、`_remove_paths`（删文件跳非普通文件）、`apply_materials_update`（备份 → 分卷按序解压 → removed+整批删除（old_manifest 推导）→ 写回新清单）。任务衔接：ApplyTask 增 `on_complete` 挂钩（下载完成后自动应用，APPLYING 状态，应用失败记 failed 中文）；webapp apply 端点构造新基线 manifest（check 响应的 files/removed/zip_names）并挂 `_apply`；check 响应增 `files/removed/zip_names` 字段（仅 apply 消费）。测试 `tests/test_materials_apply.py` 12 项 + task 组合 25 项全绿；mypy 干净。说明：spec「批次粒度记版本」的实现 = 新清单只含选中批次（未选批次文件原样保留、下次 check 继续提示），与 spec 语义一致。
