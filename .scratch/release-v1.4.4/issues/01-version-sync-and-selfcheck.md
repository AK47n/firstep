# 01 — 三处版本号同步 + 发版前自检

**要做什么：** 把版本号改到 **v1.4.4** 并让产品自己的解析器认账：`__init__.py` / `pyproject.toml` /
`VERSIONS.md` 顶部新区块 / `README.md` 当前与上一版两行；版本相关的硬编码断言跟着改（追加而非替换）。

**被谁阻塞：** 无——可立即开始。

**Status:** resolved（2026-10-02）

- [ ] `src/contest_generator/__init__.py` → `__version__ = "1.4.4"`（注释里的对齐说明同步）
- [ ] `pyproject.toml` → `version = "1.4.4"`
- [ ] `VERSIONS.md` 顶部新增 `## v1.4.4 (2026-10-02)` 区块（主题 ＋ 用户视角条目；
      **「浅色主题引脚配色变清楚」点名**）
- [ ] `README.md`：当前版本行 = v1.4.4、上一版行 = v1.4.3（当前行里点名本轮可见变化）
- [ ] `tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions`
      的版本清单与最新日期断言跟改（追加而非替换；v1.4.0 / v1.4.1 / v1.4.2 / v1.4.3 四轮同样的写法）
- [ ] `powershell -File tools\preflight.ps1` → **四项全绿**（读数 `.scratch/release-v1.4.4/preflight-01.txt`）
- [ ] 版本相关单测：`pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q`
      → 全绿（读数 `pytest-version-01.txt`）
- [ ] 提交信息中文（`chore` / `docs` 都行，照前四轮：`发布 v1.4.4：三处版本号同步 + …`）

## Comments

### 落地事实

| 项 | 值 |
|---|---|
| 三处版本号 | `__init__.py` = `1.4.4`；`pyproject.toml` = `1.4.4`；`VERSIONS.md` 首块 = `## v1.4.4 (2026-10-02)`（**LF 文件**，新区块按文件实际换行拼） |
| `README.md` | 当前版本行 = v1.4.4（点名「浅色主题下引脚卡片的配色变清楚了」，含 1.40 → 4.70 / 3.76 读数）、上一版行 = v1.4.3 |
| `preflight.ps1` | **四项全绿**，结论行 `全绿，可以发版（当前版本 v1.4.4）`（`preflight-01.txt`） |
| 版本相关单测 | `pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` → **86 passed**（`pytest-version-01.txt`，15.11 s） |

- 版本清单断言按「**追加而非替换**」改：`v1.4.4` 加在最前（`tests/test_changelog.py`
  的 docstring 与断言两处同步；docstring 口径照上一轮 = 列出版本数 − 1 块进前台）。
- 施工脚本 `.scratch/release-v1.4.4/_bump_version.py`（照 v1.4.0 那支，锚点逐条断言命中 1 次；
  只有 `VERSIONS.md` 的插入是跨行操作，其余六处都是整行替换）。
- `preflight` 第 3 项是 `--offline` 版（只查 README 与包内文件），**线上那一半没查**——
  照流程留给 03 单的 `tools\check-download-docs.py` 完整版。
