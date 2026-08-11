# 01 — 库翻译骨架收尾（slug 键文法单源 + 第五库模板文档 + 不参数化留痕）

**What to build:** 架构评审候选 6（库翻译骨架收敛）评估后缩水——实查四库的 StoreError 翻译差异是真实语义差异（master_store 有 FileNotFoundError → "母版不存在"第四分支特判、manifest 合并 Read+Parse 分支且文案不同、topic 的 require_str 包装带目录名上下文），参数化共享（错误类 + 种类词 + id 呈现 + 分支策略）劣于现状的清晰重复，机制共享不做。真实可做的只剩：① `_SLUG_PATTERN` 逐字重复 ×2（library.py:44 与 master_store.py:51，`^[A-Za-z0-9_][A-Za-z0-9_-]*$`）→ 键文法单源；② 第五库入场成本 = 模板文档（reference_library 为最新模板），非机制抽象；③ 结论留痕防再建议。

**Blocked by:** 无

**Status:** resolved（2026-08-09 已合 main PR #33，922 绿 + mypy 干净）

## 需求

1. **entry_store.py 增 `SLUG_PATTERN`**（键文法单源：模块 slug 与母版平台名共用的目录名文法，字母数字开头、字母数字下划线连字符）：`library.py:44` / `master_store.py:51` 的 `_SLUG_PATTERN` 删除，改消费 entry_store.SLUG_PATTERN——**行为逐字**（文法完全相同，既有用例零改动）
2. **CONTEXT.md**：
   - 条目库原语词条补"键文法 SLUG_PATTERN 单源（模块 slug 与母版平台名共用）"
   - 词条补一句**有意不参数化留痕**："库的 StoreError 翻译骨架（3 分支映射 / require_str 包装 / key 校验包装）不参数化共享——各库语义差异真实（master 不存在特判 / manifest 合并分支 / topic 上下文文案），参数化劣于清晰重复；新库以 reference_library 为最新模板（错误类 + 元文件名 + 键文法 + 3 分支映射 + CRUD 形状）"
3. **结构测试**：`SLUG_PATTERN` 定义单址 entry_store（grep 式：library/master 源码无 `_SLUG_PATTERN =` 定义）

## 文件边界

- `src/contest_generator/entry_store.py`（+SLUG_PATTERN 常量）
- `src/contest_generator/library.py` / `master_store.py`（删本地 _SLUG_PATTERN，改 import 消费）
- `tests/test_entry_store.py` 或结构测试所在文件（单址 pin）
- `CONTEXT.md`（词条补两句）

## 验收

- [ ] 全量测试绿 + mypy 干净
- [ ] 既有用例零改动通过（slug / 平台名校验行为逐字）
- [ ] 结构自证：`SLUG_PATTERN` 定义单址 entry_store；library/master 无 `_SLUG_PATTERN =`
- [ ] CONTEXT.md 两句更新（键文法单源 + 不参数化留痕）
- [ ] 独立 worktree + 独立 commit

## Comments

- 2026-08-09 立项（架构评审 2026-08-09 候选 6，用户授权代决）：评估后缩水——探索报告"映射 ×4 / 正则逐字 ×3"不实：正则逐字仅 slug ×2（reference 的 _ENTRY_ID_PATTERN 允许中文、topic 用题号文法，均非重复）；翻译差异为语义差异（master FileNotFoundError 特判 / manifest 分支合并 / topic 上下文文案），参数化 = 4 参数抽象劣于 ~10 行清晰重复，deletion test 不过（删共享助手复杂度弹回各库且更难读）→ 机制共享不做；第五库入场成本用文档解决（reference_library 模板 + 搭建清单入 CONTEXT 词条），非机制抽象；SLUG_PATTERN 单源是唯一真实小赢（键文法 = 条目库原语域，entry_store 收符合"原语不持业务形状"——文法本身是参数，共享的是"两库传同一文法"的事实）
- 2026-08-09 实施提示词已交付聊天（文件边界 / 验收 grep / worktree 命令），待新会话执行；机制共享已裁决不做，执行会话只做 SLUG_PATTERN 单源 + CONTEXT 两句
- 2026-08-10 已合 main PR #33（2b53181，922 绿 + mypy 干净），Status 补勾 resolved
