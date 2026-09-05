# 01 — 发布侧：清单生成与增量 diff 纯函数

**要做什么：** 发布者拿到一份命令即可使用的核心逻辑——给定资料库目录与上一版清单（或缺省），产出「新增 / 修改 / 删除」差异、按批次分组、超 1.9 GB 自动拆 part 并给每个 part 算 SHA256、生成新版全量清单；首次引入时用 `-Init` 只生成初始基线清单。全部纯函数化、临时目录 fixture 可单测。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] 清单（manifest）JSON 契约落地：顶层 `version / published_at / batches[{slug, name, files:[{path,size,sha256}], removed:[path], parts:[{zip_name,size,sha256}]}]`；slug = 顶级目录 ASCII 化标识，中文目录名映射表登记
- [x] 扫描当前资料库目录 → 全量文件集（path/size/sha256），排除 `.materials-manifest.json` 自身与 `.git` 等噪音
- [x] diff 纯函数：输入（上一版清单 files + 当前文件集）→ 新增 / 修改 / 删除三态；`-Init` 无基线 = 全量视为新增
- [x] 批次分组与分卷：单批次 zip 内容（新增+修改文件）超 1.9 GB 自动拆 `part<N>`，每 part 独立 SHA256；`removed` 汇总自基线起的删除文件
- [x] 产出校验：迷你资料库 fixture（改一文件 / 增一文件 / 删一文件 / 空批次）→ 断言清单各字段与 part 切分正确
- [x] 核心模块放 `src/contest_generator/` 下 Python 文件，纯函数无网络、无 I/O 副作用（扫描函数单独薄层）

## Answer

`src/contest_generator/materials_pack.py`：PartFile / BatchChange 数据模型、DIR_SLUGS 中文目录 slug 登记表（10 个现役目录 + 未登记报错）、scan_materials（排除自身清单 / .git / __pycache__）、scan_as_manifest、diff_manifest（三态 + 整批删除 + prev=None 全新增）、build_zip_parts（1.9 GB 分卷 `.part<N>` + 每卷 SHA256）、build_manifest、prepare_package（Init / Full / Diff 三模式编排）+ main(argv) CLI。测试 `tests/test_materials_pack.py` 20 项全绿；全库 3239 项通过；mypy 干净。清单契约与 spec 一致（files 全量 + removed 部分删除 + parts 增量元数据；整批删除 = 批次消失由用户侧推导）。
