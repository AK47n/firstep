# 01 — 参考库文件清单域单源化（素材清单契约 + materials 根推导 + 文件清单三形状）

**What to build:** ① 素材清单.txt 格式契约写入侧收成 reference_library 公开原语（读取侧已单源，写读对偶）；② materials 备份根推导收进 config.py（webapp 启发式删除、脚本硬编码换推导）；③ "条目可匹配文件名"三形状收敛为一个内部原语 + resolve_entry_file 缺失改抛 ReferenceError（路由内联 404 通道删除）。

**Status:** drafted（2026-08-11，主会话已核实现状，待用户开新终端执行）

## 现状（已核实）

- 读取侧单源：reference_library.py:60-64（MANIFEST_FILENAME + _MANIFEST_LINE 锚尾正则）、:392-407（_read_manifest_records）。写入侧 5 份拷贝：register_materials.py:122-133、register_wireless_uart.py:49-60、register_esp32cam.py:49-60、register_tarkbot.py:100-111、register_canmv_k230.py:55-69（各自 build_manifest，行格式相同、表头字符串已漂移——register_materials 写 "sources/materials"，其余写 "Desktop/…"）。表头对读端无意义（锚尾正则跳过），行格式是契约。
- materials 根推导三处：webapp.py:237-251（_materials_dir 两级候选启发式：同级 sources/materials 优先、仓库根兜底、目录实况判定、都缺返回优先候选——唯一 src 侧实现）；脚本硬编码 REPO/sources/materials（register_materials.py:31、backup_new_batches.py:21,55、backup_materials.py:8,13-17）；config.py 只有 reference_library_dir（:122-128）无 materials 对应。reference_library.py:376 镜像按 entry.title 键取。
- 三形状同模块：reference_library.py:385-389（_entry_filename_haystack join 成串）、:331-353（match_entry_files 保序去重）、:310-328（list_entry_files 磁盘优先合并）；search_references 的 filename 谓词 = join 串子串（:288），与 match_entry_files 的逐路径判据可互不一致（含 \n 的 needle 搜索命中但 matched_files 空）。
- resolve_entry_file（:356-382）三态出口（元组 / ReferenceError / None）；webapp.py:1113-1116 内联 404。对照 read_fulltext 对缺失是大声 ReferenceError（"库损坏"，:429-434）。errors.py:61-65 ReferenceError → 400（条目不存在同通道，test_webapp.py:2405 断言 400）。
- 脚本布局引用：register 脚本 sys.path 插 src 后 import contest_generator.reference_library，硬编码 REFERENCE_ROOT = REPO_ROOT/library/references；repo 布局 module_library_dir = REPO_ROOT/library/modules（config.materials_dir 两级候选对 repo 布局返回仓库根 sources/materials，与脚本硬编码同值）。
- 结构测试：test_autocommit.py:359-427 公开函数分类注册表（commit / delegated / read，未知即红）；list_entry_files / resolve_entry_file / match_entry_files 已按 read 挂表（:425-427）；archive_reference 是 delegated（批次级由调用方链兜底，正常，不动）。

## 实施

1. **config.py** 加 `materials_dir(module_library_dir: Path) -> Path`：webapp._materials_dir 逻辑逐字迁入（两级候选 + 目录实况判定 + 都缺返回优先候选），docstring 同步；test_config.py 补三个用例（同级存在 → 同级 / 仅仓库根存在 → 仓库根 / 都缺 → 同级）。
2. **webapp.py** 删 _materials_dir（:237-251），reference_file 路由（:1101-1119）改 import config.materials_dir；:1113-1116 的 `if resolved is None: raise HTTPException(404, ...)` 内联块删除（缺失走 ReferenceError → 400，与条目不存在同通道，docstring 同步）。
3. **reference_library.py**：
   a. 公开 `build_material_manifest(src_dir: Path) -> str`：素材工具脚本的清单文本生成器——表头 + 空行 + 每行 "相对路径  大小 bytes"（sorted rglob、is_file、stat 失败 size=-1），与 register_materials.build_manifest 逐字同语义；表头字符串提为模块常量。**行格式（锚尾正则对偶）保持不动**。
   b. 内部原语 `_entry_file_records(reference_root: Path, entry_id: str) -> dict[str, int]`：_read_manifest_records 结果 + 条目目录 rglob（排除 reference.json，磁盘实况优先）→ dict（插入序 = 清单序 + 磁盘新增殿后）。list_entry_files / match_entry_files / _entry_filename_haystack 全部改用它（公共行为逐字不变）；search_references 的 filename 谓词改 `any(needle in rel.lower() for rel in records)`（逐路径判据，消灭 \n join 伪阳性）。
   c. resolve_entry_file 找不到改抛 `ReferenceError(f"参考文件条目 {entry_id!r} 中不存在文件：{rel_path}")`，docstring 同步（None 语义删除）。
   d. test_autocommit.py 补挂 build_material_manifest（read 类——不落 reference.json、不触发提交；注释说明在 add_reference 前调用、随条目事务入库）。
4. **脚本迁移**（.scratch/register_materials.py、register_wireless_uart.py、register_esp32cam.py、register_tarkbot.py、register_canmv_k230.py、backup_new_batches.py、backup_materials.py）：build_manifest → `reference_library.build_material_manifest`；`MATERIALS_ROOT` / `REFERENCE_ROOT` 硬编码 → `config.materials_dir(REPO_ROOT / "library" / "modules")` / `config.reference_library_dir(REPO_ROOT / "library" / "modules")`。脚本的 iter_text_files / zip/docx 解压 / 跳过逻辑不动。
5. **测试**：test_reference_library.py 补 build_material_manifest（行 + 大小 + 目录跳过 + stat 失败 -1）+ 写→读 round-trip（build 结果写入条目目录 → _read_manifest_records 解析一致）；search \n 伪阳性回归（needle "a\nb" 不命中 files=["a.txt","b.txt"] 的条目）；resolve_entry_file 缺失 → ReferenceError；test_webapp.py reference_file 缺失断言 404 → 400。

## 验收

- `python -m pytest` 全绿 + `mypy src` 干净。
- 真机 8001：搜 "TB6612" 命中 → 查看 → PDF 浏览器可预览 / 文本内联 / zip 下载照旧；缺失路径返回 400（错误映射统一，不再有 404 内联通道）。
- 任一 register 脚本重跑 = 全部跳过（幂等不破坏，磁盘不动）。
- 结构测试：build_material_manifest 已挂分类注册表。

## 文件边界

`src/contest_generator/config.py`、`src/contest_generator/webapp.py`、`src/contest_generator/reference_library.py`、`tests/test_config.py`、`tests/test_reference_library.py`、`tests/test_webapp.py`、`tests/test_autocommit.py`、`.scratch/register_materials.py`、`.scratch/register_wireless_uart.py`、`.scratch/register_esp32cam.py`、`.scratch/register_tarkbot.py`、`.scratch/register_canmv_k230.py`、`.scratch/backup_new_batches.py`、`.scratch/backup_materials.py`

**明确不动的：** 素材清单行格式（锚尾正则对偶——磁盘存量清单按旧格式，读端不变）；reference.json 形状；add_reference 签名与语义；脚本的 iter_text_files / 解压 / 跳过逻辑；sources/materials 与 library/references 磁盘内容；entry_store.py；archive_reference（delegated 设计，批次级提交归调用方链）。
