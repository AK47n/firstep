# 01 — egg-info 摘出产品文件：两个打包器都不再收 pip 的构建产物

**要做什么：** 升级后的工具根里不再出现 `src/contest_generator.egg-info/**`（6 件）——
完整包与小发版包**两边都不发**，于是「盘面与全新安装一致」这条判据在两条升级路径上都成立。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `full_pack.product_file_reason` 把 `*.egg-info` 目录名列为跳过项（与 `__pycache__` /
      `revise-backups` 同列），两个打包器自动同时生效（都问这个谓词，不许各写一份）
- [x] `tests/test_full_pack.py::test_product_file_predicate_is_the_single_source` 真值表补格：
      `src/contest_generator.egg-info/PKG-INFO` 判 False、原因串 `dir-name`
- [x] 反向注入探针：把那一条跳过规则拿掉 → 对应用例**必须转红**；跑完复原并复核 sha256
- [x] 既有守卫全绿：`tests/test_full_pack.py` / `tests/test_pack_update.py` /
      `tests/test_update_app.py`（跨包逐字节一致性、路径预算、清单形态、删除清单语义一个都不许改）
- [x] 真仓库实测：`scan_tree(仓库根)` 里不再出现 egg-info 六件；`excluded_paths` 里它们的原因
      是 `dir-name`

## Comments

### 落地事实（2026-09-19）

| 项 | 结果 |
|---|---|
| 改了什么 | `full_pack.SKIP_DIR_GLOBS = ("*.egg-info",)`（新常量，**目录名通配**）+ 三处判定改为「精确名 ∈ `SKIP_DIR_NAMES` **或** 通配命中」——`product_file_reason` / `register_materials_dirs` / `materials_excluded`（三处必须同口径，否则「清单里出现的文件必须在包里」那条不变量翻车） |
| 真仓库实测 | `scan_tree` 里 egg-info 条目 **6 → 0**；产品文件数 8152 → **8146**（正好差 6）；`excluded_paths` 六件原因均为 `dir-name` |
| 单测 | `python -m pytest tests/test_full_pack.py tests/test_pack_update.py tests/test_update_app.py -q` → **66 passed** |
| 全套 | `python -m pytest -n auto -q` → **4578 passed + 1 skipped**（93.43s） |
| 判据强度 | `.scratch/release-v1.2.2/probe-guard-strength.py` → **2/2 转红**、复原逐字节相同（证据 `verify-01-guard-strength.{txt,json}`） |

### 两处顺带改对的东西

1. **`SKIP_DIR_GLOBS` 是通配而不是精确名**：真实目录叫 `contest_generator.egg-info`，
   精确名一个都盖不住；而产者（pip / setuptools）对任何包都叫 `<包名>.egg-info`，
   规则天然是后缀通配。它走的是既有 `_matches_any`（`INSTALLER_GLOBS` 用的同一套）。
2. **旧探针的锚点跟着演进**：`.scratch/update-orphan-files/probe-guard-strength.py` 的
   ① 号注入锚定的是 `if any(part in dir_skips for part in parts[:-1]):`——这一行本轮变了，
   锚点命中数从 1 变 0，探针会**拒绝开跑**（前置干净性检查拦住的正是「探针自身退化」）。
   已把两处（① 锚点 + ③ 注入文本里的同一行）一起改成新形态，该探针仍可复跑。

- **为什么这一版要顺手做掉**：实测（v1.1.1 / v1.2.0 / v1.2.1 三版）egg-info **每个完整包都发、
  每个小发版包都不发**，且盘上 6 件与完整包清单 sha256 逐件相等。这正是 drill-01
  `not_in_official == 0` 这条判据会咬的那类落差——升级用户的盘上会多出「全新安装不会给」的
  文件（反向：全新安装有、升级后没有）。用户在澄清里选了「摘掉，两个包都不发」。
- **副作用是有意的**：升级用户的盘上那 6 件会被删除清单点名删掉（旧更新器照单执行，
  它已经支持「路径不存在就跳过」）。它们由 `pip install -e .` 现写，下次装/换 `.venv` 时重建；
  对 `start-app.bat`（`PYTHONPATH=src`）与 `.venv` 两种启动方式都无影响。
- **与 `update-orphan-files/01` 的关系**：那条修复把「哪些算产品文件」收成了一处判据
  （`full_pack.product_file_reason`），本单只是**给那份判据加一条目录规则**——不改架构、
  不加第二处判据。所以它是同一张单的自然收尾，而不是新架构。
