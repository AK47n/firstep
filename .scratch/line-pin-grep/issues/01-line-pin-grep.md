# 01 — 行号钉死测试 grep 式化（ValidationResult / file_label 定时炸弹拆除）

**What to build:** 两个硬编码行号结构测试是 library.py 增删行的定时炸弹（工单 6 曾因净 -1 行位移双红）：test_selection.py:961 `assert hits == [("library.py", 52)]`（"class ValidationResult" 唯一命中行）与 test_reference_library.py:1208 `assert hits == [("library.py", 496)]`（"// ---- " 唯一命中行）。意图 = "定义唯一出处"（恒等断言已在前，如 :953 `llm.ValidationResult is library.ValidationResult`），行号只是把唯一性钉死的副产物。本工单去掉行号依赖、保留唯一性断言——library.py 任意增删行不再撞红。

**Blocked by:** 无

**Status:** resolved（2026-08-09 已合 main PR #35，commit 24393b7，924 绿 + mypy 干净）

## 需求

1. **tests/test_selection.py:961**：`assert hits == [("library.py", 52)]` → `assert [name for name, _ in hits] == ["library.py"]`（唯一出处 + 恰好一个命中保留，行号不再断言）；注释同步（"class 行（唯一出处）" → "定义文件（唯一出处）"）
2. **tests/test_reference_library.py:1208**：`assert hits == [("library.py", 496)]` → 同款 `assert [name for name, _ in hits] == ["library.py"]`；注释同步
3. 零 src 改动；恒等断言（ValidationResult / file_label 消费 pin）不动

## 文件边界

- `tests/test_selection.py`（1 行断言 + 注释）
- `tests/test_reference_library.py`（1 行断言 + 注释）

## 验收

- [x] 全量测试绿 + mypy 干净（924 绿）
- [x] 结构自证：`grep -n "class ValidationResult" src/contest_generator/*.py` 唯一 library.py；`grep -n "// ---- " src/contest_generator/*.py` 唯一 library.py（断言意图保持）
- [x] 注入自证：临时在无关文件加 "class ValidationResult"（或 "// ---- "）→ 断言红；还原绿
- [x] 库行位移自证：任意在 library.py 插入一行后断言仍绿（无行号依赖）
- [x] 独立 worktree + 独立 commit

## Comments

- 2026-08-09 立项（架构评审遗留小工单，用户点名做）：两 pin 意图 = 定义唯一出处（恒等断言 :953 / 消费 pin :1216 已独立存在），行号是唯一性钉死的副产物；grep 式化按 test_include_contract.py 先例（不含行号）；文件边界仅两个测试文件，零 src 改动
- 2026-08-10 闭环补录：该改动 2026-08-09 已随 PR #35（12128f0）合入 main（commit 24393b7），工单状态漏勾——现补：断言已为 `[name for name, _ in hits] == ["library.py"]`（test_selection.py:1079 / test_reference_library.py:1374），恒等断言未动（:1071 / :1382），全 tests 已无 (文件名, 行号) 元组断言
