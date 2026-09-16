# A1 — `tools/prepush.py` 子集选择器 + 单测

**要做什么：** 给一串「本次要推的改动路径」，能算出「该跑哪些测试 / 是否必须整套 / 为什么」——这是闸门的判据本体，独立可测、可复跑，先于钩子存在。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved——`tools/prepush.py` + `tests/test_prepush.py`（27 passed）

- [x] `tools/prepush.py` 暴露纯函数 `select_tests(changed) -> Selection`（`paths` / `full` / `reasons`），吃相对路径字符串列表、不碰盘不碰 git
- [x] 映射规则：同名测试命中 / 公共面模块 → 全套 / `library/` 改动 → 库与母版守卫族（13 个文件）/ 纯文档 → 文档守卫族（5 个文件）/ **未知后缀或未知目录 → 全套**（倒向更严）
- [x] 支持 `--full` 与 `FIRSTEP_PREPUSH=full`（另有 `off`）；`--explain` 打印命中理由
- [x] 能从 git 读本次要推的改动（stdin 的 pre-push refs；无 refs 时退回「工作树 vs HEAD」）
- [x] `tests/test_prepush.py`：27 例，覆盖每类规则 + 空改动 + 多类并集 + **10 个"认不出来"的反例** + 守卫族清单真实性 + 闸门自身故障放行
- [x] `python tools/prepush.py --changed <文件> --dry-run` 只打印不执行（已实测四类）

## Comments

**判据来源（不手写名单）**：公共面 = 被 ≥10 个测试文件 import 的模块，从测试文件的
真实 import 行现算（2026-09-16 实测：86 个模块里 13 个过线，正是 manifest / generator /
selection / platforms / clex / webapp / boards / pin_bindings / errors / llm / patchers /
pinwriter 这一层）；配套断言 `test_wide_modules_are_derived_from_real_imports` 保证
「清单里的每个模块都真的过线」，名单长大/缩小时判据自己跟上。

**反向验证（两处注入，都变红）**：
① 把 `WIDE_IMPORT_THRESHOLD` 改成 9999 → `test_wide_module_change_runs_everything` +
`test_wide_modules_are_derived_from_real_imports` 2 failed；
② 把末条兜底从 `FULL` 改成 `NONE` → `test_unrecognized_paths_fall_back_to_full[Makefile]` 1 failed
（其余 9 个反例走的是更早的分支，各自仍全绿——说明每个分支都在独立起作用）。
还原后 27 passed。

