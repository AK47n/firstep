# 01 — 三处版本号同步 + 发版前自检

**要做什么：** 把版本号改到 **v1.4.2** 并让产品自己的解析器认账：`__init__.py` / `pyproject.toml` /
`VERSIONS.md` 顶部新区块 / `README.md` 当前与上一版两行；版本相关的硬编码断言跟着改。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-10-01）

- [x] `src/contest_generator/__init__.py` → `__version__ = "1.4.2"`
- [x] `pyproject.toml` → `version = "1.4.2"`
- [x] `VERSIONS.md` 顶部新增 `## v1.4.2 (2026-10-01)` 区块（主题 + 3 条：三处形态 / 形状信号 /
      读屏；**「三处『不可选』的样子变了」点了名**）
- [x] `README.md`：当前版本行 = v1.4.2、上一版行 = v1.4.1（当前行里点名三处形态）
- [x] `tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions` 的
      版本清单与最新日期断言跟着改（追加而非替换；v1.4.0 / v1.4.1 两轮同样的写法）
- [x] `powershell -File tools\preflight.ps1` → **四项全绿**（读数 `.scratch/release-v1.4.2/preflight-01.txt`）
- [x] 版本相关单测：`pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q`
      → **86 passed**（读数 `pytest-version-01.txt`）
