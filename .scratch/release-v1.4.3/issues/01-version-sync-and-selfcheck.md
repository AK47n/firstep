# 01 — 三处版本号同步 + 发版前自检

**要做什么：** 把版本号改到 **v1.4.3** 并让产品自己的解析器认账：`__init__.py` / `pyproject.toml` /
`VERSIONS.md` 顶部新区块 / `README.md` 当前与上一版两行；版本相关的硬编码断言跟着改（追加而非替换）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-10-01）

- [ ] `src/contest_generator/__init__.py` → `__version__ = "1.4.3"`（注释里的对齐说明同步）
- [ ] `pyproject.toml` → `version = "1.4.3"`
- [ ] `VERSIONS.md` 顶部新增 `## v1.4.3 (2026-10-01)` 区块（主题 ＋ 用户视角条目；
      **「三条话变清楚了」「浅色焊盘换色」点名**）
- [ ] `README.md`：当前版本行 = v1.4.3、上一版行 = v1.4.2（当前行里点名本轮两条可见变化）
- [ ] `tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions`
      的版本清单与最新日期断言跟改（追加而非替换；v1.4.0 / v1.4.1 / v1.4.2 三轮同样的写法）
- [ ] `powershell -File tools\preflight.ps1` → **四项全绿**（读数 `.scratch/release-v1.4.3/preflight-01.txt`）
- [ ] 版本相关单测：`pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q`
      → 全绿（读数 `pytest-version-01.txt`）
- [ ] 提交信息中文（`chore` / `docs` 都行，照前三轮：`发布 v1.4.3：三处版本号同步 + …`）

## Comments

### 落地事实

| 项 | 值 |
|---|---|
| 三处版本号 | `__init__.py` = `1.4.3`；`pyproject.toml` = `1.4.3`；`VERSIONS.md` 首块 = `## v1.4.3 (2026-10-01)` |
| `README.md` | 当前版本行 = v1.4.3（点名「三条话变清楚了」＋「浅色焊盘换色」）、上一版行 = v1.4.2 |
| `preflight.ps1` | **四项全绿**，结论行 `全绿，可以发版（当前版本 v1.4.3）`（`preflight-01.txt`） |
| 版本相关单测 | `pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` → **86 passed**（`pytest-version-01.txt`） |

- 版本清单断言按「**追加而非替换**」改：`v1.4.3` 加在最前（`tests/test_changelog.py`
  的 docstring 与断言两处同步）。
- `preflight` 第 3 项是 `--offline` 版（只查 README 与包内文件），**线上那一半没查**——
  照流程留给 04 单的 `tools\check-download-docs.py` 完整版。
