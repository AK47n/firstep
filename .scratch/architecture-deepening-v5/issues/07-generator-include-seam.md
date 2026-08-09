# 07 — 架构深化 v5：generator include 读侧接缝——读缝成真，mspm0 门禁空基座补齐（工单 04 边界点名）

**What to build:** 工单 04 边界点名遗留（"registry 不是读侧接缝、mspm0 门禁空基座，留待下轮候选"）。现状两缝：① **依赖缝**——generator.py:19 运行时 `from .keil import include_search_dirs`，生成核心（平台无关，自称"只认识平台名"）直接 import 平台模块；② **语义缝（mspm0 门禁空基座）**——include 搜索目录只按 Keil 语义算（`include_search_dirs` 读 .uvprojx IncludePath，找不到 .uvprojx 静默返回 `[]`），mspm0 走生成路径时 `master_search_dirs` 恒空，`_check_unresolved_includes` 门禁只剩"模块 own_dir + C 标准头白名单"（白名单 `stm32f10x_conf.h` 是 Keil 特供，TI 侧无对偶）——mspm0 母版首次入库即咬人（真机库现只有 stm32，无样本，本工单为预防性补齐）。本轮收口：**读侧 registry 对偶（patchers.py 收 `include_search_dirs(platform, project_dir)` 分派）+ ccs.py 读侧对偶函数（.cproject buildIncludePath 解析，与 keil 版逐字对偶）**。行为零变化（stm32 逐字同函数、文案逐字、门禁语义不动，mspm0 无真机母版 → 无真机影响）。

1. **ccs.py 新增公开函数 `include_search_dirs(project_dir: Path) -> list[Path]`**（读侧对偶 keil.py:207，格式知识归格式模块）：
   - `_find_cproject` 定位工程文件，`except CcsProjectError: return []`（与 keil 版兜底逐字对偶："生成路径母版必有 cproject（CcsPatcher 兜底报错），此函数只为解析 include 搜索目录"）；
   - 遍历 `_build_configurations(root)` 全部 configuration 的 buildIncludePath 值（复用既有 `_option_values(configuration, "ti.ccs.misc.options.buildIncludePath")`——与 `extract_config_summary` 同源认知，不另抄 XML 走查）；
   - 值规范化（CCS 惯例，写侧 `_ccs_include_value` 同款认知）：`${PROJECT_LOC}` 前缀 → .cproject 所在目录（宏 = 工程根）；绝对路径原样保留；其余相对路径 → .cproject 所在目录/值；**按出现顺序去重**（keil 版同款）——不做变量引擎（无真机样本，YAGNI）；
   - docstring 写明 CCS 语义（引号头搜索范围对偶：先当前文件目录，再 buildIncludePath 顺序）。
2. **patchers.py 收读侧分派 `include_search_dirs(platform: str, project_dir: Path) -> list[Path]`**（写侧 registry 同文件对偶——patchers.py 已 `from .ccs import CcsPatcher` / `from .keil import KeilPatcher` / `from .platforms import PLATFORM_MSPM0, PLATFORM_STM32`，零新增依赖）：
   - `PLATFORM_STM32` → `keil.include_search_dirs`、`PLATFORM_MSPM0` → `ccs.include_search_dirs`，未知平台抛 **UnknownPlatformError**（既有，与 `PatcherRegistry.get` 同款契约、errors.py 已登记 400）；
   - docstring 与模块头呼应："生成核心只认识平台名，不绑定任何平台格式"（读侧与写侧同规则）。
3. **generator.py:19 换源**：`from .keil import include_search_dirs` → **并入 :24 既有 `from .patchers import ...` 行**；:405 `master_search_dirs=tuple(include_search_dirs(master_project_dir))` 调用与语义逐字不动——generator 对平台模块（keil/ccs）运行时 import 清零。
4. **测试**：
   - ccs.include_search_dirs 合成 .cproject fixture 四态：`${PROJECT_LOC}` 展开 / 绝对路径保留 / 相对路径解析 / 无 .cproject → `[]`，去重保序；
   - 分派：`patchers.include_search_dirs(PLATFORM_STM32, ...)` 结果 ≡ keil 版逐字、mspm0 ≡ ccs 版、未知平台抛 UnknownPlatformError（match 文案同 registry.get）；
   - mspm0 门禁全链：合成 mspm0 母版（.cproject buildIncludePath 指向含 SDK 头的临时目录）→ `build_module_corpus` 走 ccs 语义 → 模块 include SDK 头通过 / 缺失头 → `UnresolvedIncludeError`（构造照 test_unresolved_include_checks_master_search_dirs 同款，master_search_dirs 换 ccs 解析结果）；
   - 结构测试防回退（先例 03 工单 hasattr 断言）：`"keil" not in generator.__dict__` 且 `"ccs" not in generator.__dict__`（generator 对平台模块 import 面清零 pin）；`def include_search_dirs` 单址 = keil.py + ccs.py（ccs 对偶存在 pin）。
5. **CONTEXT.md 词表更新**（同批提交）：「生成流程」（或对应词条）实现列补"include 读侧接缝：patchers.include_search_dirs 按平台分派——stm32 走 keil 版 .uvprojx IncludePath、mspm0 走 ccs 版 .cproject buildIncludePath（${PROJECT_LOC} 展开）"；「架构要点」补一句：生成侧读缝成真——include 搜索目录按平台分派（写侧 patcher registry 对偶），generator 不再 import 平台模块。

**明确不动的（边界，勿越）**：行为零变化（stm32 搜索目录逐字同函数、门禁文案逐字、既有断言原样过）；keil.py 零改动；ccs.py 只增只读函数（patch 写侧 / extract_config_summary 摘要零改动）；`_check_unresolved_includes` / `_check_module_self_include` / `_check_macro_conflicts` 门禁逻辑零改动（只换 master_search_dirs 来源）；patchers.py 写侧（PatcherRegistry / default_registry / ProjectPatcher / patch）零改动；**_EXTERNAL_HEADERS 白名单不动**（无 mspm0 真机样本——TI SDK 头走 buildIncludePath 目录搜索命中，白名单补 TI 头名 = 猜死代码，工单 04 D3 先例"无样本不猜"）；platforms.py / config.py / webapp 零改动；不引入新模块。

**Status:** resolved（2026-08-09 同批 PR 勾选，835 绿 + mypy 干净）

## 验收

- [x] 全量 pytest 绿（基线 823 → 835，+12：ccs 四态 5 条 + 分派 3 条 + mspm0 门禁全链 2 条 + 结构 2 条）+ mypy 干净；stm32 门禁既有断言原样过（test_unresolved_include_checks_master_search_dirs 等逐字，行为零变化）
- [x] `grep -rn "from .keil import include_search_dirs" src` 无结果（generator 对 keil 运行时 import 清零；对 ccs 亦然——import 面只有 patchers）
- [x] `grep -rn "def include_search_dirs" src` = keil.py:207 + ccs.py:68 格式定义（读侧对偶单址；另 patchers.py:71 分派——结构测试 pin 三处 ["ccs.py", "keil.py", "patchers.py"]，格式知识归格式模块）
- [x] `grep -rn "include_search_dirs" src/contest_generator/generator.py` = `from .patchers import` 一行（:23）+ :404 消费一处（平台参数随调用传入）
- [x] 结构测试过：generator.__dict__ 无 keil / ccs 键；patchers.include_search_dirs 分派 stm32/mspm0 各归其位（结果逐字等于 keil/ccs 版）、未知平台 UnknownPlatformError（文案同 registry.get）
- [x] CONTEXT.md 两处更新到位（修改器词条实现列补 include 读侧接缝 + 架构要点新 bullet 生成侧读缝成真）

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/07-generator-include-seam.md（架构深化 v5：generator include 读侧接缝——读缝成真，mspm0 门禁空基座补齐）

先读工单全文，按 1-5 节执行。独立 worktree（勿在主检出改，必须 -b 形式）：
git worktree add -b v5-07-generator-include-seam ../firstep-v5-07 main

1. ccs.py 加 include_search_dirs（读 .cproject buildIncludePath，与 keil.py:207 逐字对偶：_find_cproject 失败返回 []、_build_configurations + _option_values 复用、${PROJECT_LOC} 展开 / 绝对保留 / 相对解析 / 去重保序）
2. patchers.py 加 include_search_dirs(platform, project_dir) 分派（stm32 → keil 版、mspm0 → ccs 版、未知抛 UnknownPlatformError；与写侧 registry 同文件，零新增依赖）
3. generator.py:19 的 `from .keil import include_search_dirs` 并入 :24 既有 patchers import 行（:405 调用逐字不动）
4. 测试：ccs fixture 四态 + 分派三态 + mspm0 门禁全链（SDK 头通过 / 缺失拒绝）+ 结构测试 2 条（generator.__dict__ 无 keil/ccs、include_search_dirs 定义双址 pin）
5. CONTEXT.md 按工单 5 节更新
6. 全量 pytest 绿 + mypy 干净 + 验收全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main

注意：编辑前先确认 cwd 在 worktree；勿串行做别的工单。
```

## Comments

（2026-08-09 立项：用户选了 include 读缝（"2"），勘察后定稿。D1 接缝形态：**读侧分派收进 patchers.py**（写侧 registry 同文件对偶——patchers 已 import keil/ccs/platforms 零新增依赖，generator 已 import patchers（:24）→ :19 换源一行；核心"只认识平台名"读侧写侧同规则）；否决"platforms.py 收分派"（词表层语义变"平台知识中枢"，04 Comments 定位是词表 + 识别知识）；否决"新建适配器模块"（2 平台 1 函数，YAGNI）。D2 ccs 对偶：`_find_cproject` 失败返回 []（与 keil 版"找不到 .uvprojx 返回 []"逐字对偶，注释逻辑同款——生成路径母版必有 .cproject，CcsPatcher 兜底报错）；值规范化只认 `${PROJECT_LOC}`（CCS 惯例，写侧 _ccs_include_value 同款认知）+ 绝对/相对路径，不做变量引擎（无真机样本，YAGNI）。D3 分派契约：未知平台抛 UnknownPlatformError（registry.get 同款，errors.py 已登记 400——未知平台与 patcher 查找同契约）；不新造异常。D4 白名单不动：无 mspm0 真机样本（真机母版库只有 stm32+stm32.json），TI SDK 头走 buildIncludePath 目录搜索命中；白名单补 TI 头名 = 猜死代码（工单 04 D3 先例）。D5 边界：keil.py 零改动、ccs.py 只增只读、门禁逻辑零改动、mspm0 无真机数据可验 → 合成 fixture 钉语义，诚实记录；mspm0 母版入库后若有漏（真机首跑）再补。）
