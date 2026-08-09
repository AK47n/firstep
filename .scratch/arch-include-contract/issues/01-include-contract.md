# 01 — include 解析契约单实现（同构核心共享，宏策略留平台）

**What to build:** keil.include_search_dirs 与 ccs.include_search_dirs 曾自称"逐字对偶"（cb8ce74 自述）——实查后并非字面同构：宏策略是实质差异（ccs 展开 ${PROJECT_LOC}/${PROJECT_ROOT}、跳过 SDK 环境宏、跳过 ${ 残留；keil 无宏处理），真正同构的只有 绝对保留 / 相对以工程文件所在目录为基准 / 去重保序 / resolve。另有孪生查找器 _find_uvprojx / _find_cproject（10 行同构，仅 pattern 与错误类不同）。本工单把同构核心收进 projectfile.py 底座，宏策略与 XML 提取留在各自平台模块——契约从"注释里互相引用"变成"共享函数 + 单套测试"。

**Blocked by:** 无

**Status:** resolved（2026-08-09 同批 PR 勾选，916 绿 + mypy 干净）

## 需求

1. **projectfile.py 增两个共享原语**（底座同族，keil/ccs 都依赖它）：
   - `find_project_file(project_dir, pattern, error_cls) -> Path`：孪生查找器收敛——iter_project_files（treewalk 噪音规则保持）→ 0 个 / 多个报错，文案逐字派生（`f"工程目录里没有 {pattern[1:]} 文件：{project_dir}"` / `f"工程目录里有多个 {pattern[1:]}，无法确定改哪个：" + "、".join(...)`），错误类型参数化（KeilProjectError / CcsProjectError）
   - `resolve_include_entries(entries, base) -> list[Path]`：同构解析核心——strip + 反斜杠归一 + 空条目跳过 → 绝对保留 / 相对以 base 为基准 → 去重保序 → resolve
2. **keil.include_search_dirs**：XML 提取（split(";") 后）→ resolve_include_entries（行为逐字，归一已有）；`_find_uvprojx` 删除，调用点（include_search_dirs / extract_config_summary 等）换 find_project_file
3. **ccs.include_search_dirs**：宏预处理（${PROJECT_LOC}/${PROJECT_ROOT} 展开、SDK 宏跳过、${ 残留跳过——**CCS 格式知识留本模块**）→ resolve_include_entries（新增反斜杠归一：Windows 上 Path 行为等价，更稳，补 fixture 验证）；`_find_cproject` 删除，调用点换 find_project_file
4. **patchers 分派不动**（include_search_dirs / external_headers 已是单缝）；generator 消费不动
5. **结构测试**：find_project_file / resolve_include_entries 定义单址；keil/ccs 模块内无 `_find_uvprojx` / `_find_cproject` 定义（grep 式先例）
6. **CONTEXT.md**：修改器词条实现列补"查找器与解析核心共享 projectfile 底座，宏策略归平台模块"

## 文件边界

- `src/contest_generator/projectfile.py`（+find_project_file + resolve_include_entries；import treewalk——叶子，无环）
- `src/contest_generator/keil.py`（include_search_dirs 消费共享核心；删 _find_uvprojx，调用点 3 处换）
- `src/contest_generator/ccs.py`（宏预处理保留；删 _find_cproject，调用点换）
- `tests/test_projectfile.py` 或新建 test_include_contract（find_project_file 三态 + 文案逐字 + 噪音跳过；resolve_include_entries：绝对保留 / 相对基准 / 去重保序 / 归一 / 空条目）
- `tests/test_keil.py` / `tests/test_ccs.py`：**既有 fixture 零改动**（行为逐字）+ ccs 反斜杠归一补一条
- 结构测试（test_keil/test_ccs 或新文件）：单址 pin
- `CONTEXT.md`

## 验收

- [x] 全量测试绿（基线 902 → 916，+14：共享原语单测 / 结构自证 / ccs 反斜杠归一 / keil 读侧直测）+ mypy 干净
- [x] keil/ccs include_search_dirs 行为逐字——既有 fixture 零改动通过（ccs 经典 + Theia 全套原样过；keil 读侧补直测 `.\inc;.\src` → 绝对目录）
- [x] find_project_file 三态 + 文案逐字（"没有 .uvprojx 文件：" / "多个 .uvprojx，无法确定改哪个："，从 pattern 派生）
- [x] 结构自证：keil/ccs 无 `def _find_uvprojx` / `def _find_cproject` 定义、find_project_file / resolve_include_entries 定义单址 projectfile.py
- [x] ccs 反斜杠归一新 fixture 通过（sdk\headers 与 sdk/headers 去重为同一目录）
- [x] CONTEXT.md 修改器词条更新（查找器与解析核心共享 projectfile 底座，宏策略归平台模块）
- [x] 独立 worktree（.claude/worktrees/include-contract）+ 独立 commit（refactor a007181 + docs）

## Comments

- 2026-08-09 立项（架构评审 2026-08-09 候选 4，用户授权代决）：实查发现"逐字对偶"不精确——宏策略（ccs 独有）是实质差异而非实现巧合，共享面收窄为同构核心（绝对保留/相对基准/去重保序/resolve）+ 孪生查找器；宏策略留 ccs（CCS 格式知识，keil 无宏，硬参数化是生搬）；共享核心落 projectfile.py（底座同族，keil/ccs 都依赖，无新环）；错误文案从 pattern 派生逐字；ccs 补反斜杠归一是行为等价增强（Windows Path 原生接受反斜杠，fixture 验证）；patchers 分派与 generator 消费不动
