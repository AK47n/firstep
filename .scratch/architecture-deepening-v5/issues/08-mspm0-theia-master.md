# 08 — 架构深化 v5：mspm0 首个真机母版（CCS Theia 格式）——ccs.py 双格式认知补齐 + 母版整理入库 + 端到端真机验证

**What to build:** mspm0 母版从未入库（真机母版库只有 stm32 + stm32.json，mspm0 生成从未在真实 CCS 工程上端到端验证过——工单 03 唯一未勾项就是 CCS 真实编译验证）。用户提供 TI 官方 empty 示例（`C:\Users\luoji\workspace_ccstheia\empty`，CCS Theia 20.5 导出、TMS470_TICLANG 4.0 格式）作母版源——比蒸馏旧工程干净，正合 ADR 0002"空的最小系统板工程"定义。但勘察确认：**该工程与 ccs.py 现有认知（CCS classic 格式）三处不匹配，直接入库后生成必报 CcsProjectError 拒绝**：① `_build_configurations`（ccs.py:147）只找 cconfiguration 内 settings storageModule 里的 cdtBuildSystem，Theia 把它放在独立的 `moduleId="cdtBuildSystem"` storageModule → 找不到配置；② include/define 选项 superClass（ccs.py:25）只认 `ti.ccs.misc.options.buildIncludePath`，Theia 是 `com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH` → 找不到选项；③ `include_search_dirs`（ccs.py:68）只展开 `${PROJECT_LOC}`，Theia 用 `${PROJECT_ROOT}`，SDK 环境宏（`${COM_TI_MSPM0_SDK_*}`）无法 Python 侧解析。本轮收口：**ccs.py 双格式认知补齐（classic 行为零变化）+ 母版整理入库（mspm0 成为首个真机母版）+ 端到端真机编译验证（用户手工，工单 03 未勾项在此闭合）**。

1. **ccs.py 双格式认知（classic / Theia 单实现路径，不分支双写）**：
   - `_build_configurations`（ccs.py:147-161）：对每个 cconfiguration 遍历**全部**内层 storageModule，找含 `cdtBuildSystem` 的那个再取 configuration——classic（settings storageModule 内）与 Theia（独立 cdtBuildSystem storageModule 内）同一条路径；cproject 根级 storageModule 的 `<project>` 元素不在 cconfiguration 内，天然不受影响；
   - include/define 选项匹配：`INCLUDE_OPTION_SUPERCLASS` 单值 → 双值（`ti.ccs.misc.options.buildIncludePath` + `com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH`），define 对偶（`ti.ccs.misc.options.buildDefine` + `...compilerID.DEFINE`）——`_include_option` / `_option_values` / `_append_include_dirs` / `extract_config_summary` 同源改动，superClass 匹配改为多值集合；
   - `include_search_dirs`（ccs.py:68-99）值规范化：`${PROJECT_ROOT}` 与 `${PROJECT_LOC}` 同语义展开（`==` → .cproject 所在目录，前缀 `/` → 目录/rest）；**以 `${` 开头且不可展开的条目跳过**（SDK/工具环境宏由 CCS 构建时解析，母版头不在这些目录，解析不了也不参与门禁——不做变量引擎）；绝对路径保留 / 相对路径按 .cproject 基准解析 / 去重保序不变；
   - docstring 补一句双格式认知（Theia 20.5 TMS470_TICLANG 4.0 与 classic 同结构语义，差异在 storageModule 位置与 superClass 命名空间）。
2. **母版整理与入库**（源目录 `C:\Users\luoji\workspace_ccstheia\empty` 只读不动，对副本操作；入库走 `master_store.import_master`，结构校验只查 .cproject/.project 存在即过）：
   - `empty.c` → `main.c`（内容不动：SYSCFG_DL_init() + while(1)，正合 ADR 0002 模板 main.c 形态；不改名则残留工程里与骨架 main.c 双 main 符号链接冲突）；
   - 删 `.clangd`（绝对路径噪音，文件自声明不入库）、删 `Debug/`（构建产物，compile_commands.json 含 `C:/Users/luoji` 绝对路径）、删 `README.html` / `README.md`（SDK 示例文档）；
   - `empty.syscfg` → `mspm0.syscfg`，`.ccsproject` filesToOpen 同步只留 `mspm0.syscfg`（原 `README.md,empty.syscfg`）；
   - `.project` `<name>` → `mspm0_project`（生成工程在 CCS 工作区显示名；赛题级重命名留后续工单，.cproject/.project 原样保留语义不变）；
   - 保留：`.cproject`、`.ccsproject`（origin/templateProperties 信息性）、`targetConfigs/MSPM0G3507.ccxml`（烧录用）、`.settings/`（编码声明无害）；
   - 入库 sources 元数据 = `("empty_LP_MSPM0G3507_nortos_ticlang",)`（TI 示例工程名）；入库后 `~/.contest_generator/masters/mspm0/` + `mspm0.json`，warnings 应为空（无构建产物）。
3. **测试**：
   - fakes.py 增 Theia 格式 fixture（以真实 empty 工程 .cproject 为底）：`_build_configurations` 找到配置 / `patch` 双格式都成功（include 追加 ${PROJECT_LOC}/modules + modules sourceEntry 补齐，既有 classic fixture 断言原样过）/ `include_search_dirs` Theia 值四态（${PROJECT_ROOT} 展开、SDK 宏跳过、绝对保留、相对解析）+ 去重保序 / `extract_config_summary` 双格式（include path + defines 都读到）；
   - 结构测试 pin：双 superClass 字符串都出现在 ccs.py（classic/Theia 认知防回退）；
   - 端到端：合成 Theia 母版（整理后形态：main.c + mspm0.syscfg + .cproject + .project）→ `generate_project(platform="mspm0", slugs=(), main_c_content=最小可编译 main)` → patch 成功、输出树断言（main.c 落位、无 empty.c、无 .clangd/Debug/README）；
   - 母版入库路径：`import_master` 对该母版 analyze_structure 无警告（无构建产物目录）。
4. **CONTEXT.md 词表更新**（同批提交）：「母版」词条实现列补 mspm0 母版 = TI empty 示例（CCS Theia 20.5 导出，main.c 模板 = SYSCFG_DL_init + while(1)，.syscfg 由赛题工程按需改）；「修改器」（或 ccs 相关词条）补双格式认知：ccs.py 同时认 CCS classic 与 Theia 20.5（storageModule 位置 + superClass 命名空间差异，单实现路径）。
5. **真机验证（用户手工，验收后回填勾选）**：生成的最小 mspm0 工程拷入 CCS Theia 工作区打开 → 编译通过。这是工单 03 未勾项的历史首次闭合。已知限制如实记录：骨架 main.c 覆盖母版后不调 `SYSCFG_DL_init()`，syscfg 生成的初始化不执行（时钟走复位默认）——编译验收照常，init 注入是生成侧机制，留后续工单。

**明确不动的（边界，勿越）**：源目录 `C:\Users\luoji\workspace_ccstheia\empty` 零改动（只读源）；classic 格式行为零变化（既有 fixture 断言原样过，fakes.py 既有 FAKE_CPROJECT 不动）；不做变量引擎（`${...}` 环境宏跳过，不猜 SDK 路径）；SYSCFG_DL_init 骨架注入 / 生成工程赛题级重命名 / 母版 .syscfg 地猛星化（当前按 TI 官方 LP_MSPM0G3507 板，模板预期用户生成后自改）→ 均留后续工单；keil.py / generator 门禁逻辑 / patchers.py / platforms.py / webapp 零改动（generator 只消费 ccs 既有接口）；母版库 API 零改动（import_master / analyze_structure 语义不动）。

**Status:** resolved（2026-08-09 同批 PR 勾选，847 绿 + mypy 干净；真机编译 2026-08-09 用户勾选——CCS Theia 编译通过，工单 03 未勾项历史首次闭合）

## 验收

- [x] 全量 pytest 绿（基线 835 → 847，+12：Theia 双格式 8 条 + 端到端 2 条 + 入库 1 条 + 结构 pin 1 条）+ mypy 干净；既有 classic fixture 断言原样过（行为零变化，helpers 双格式化后逐字过）
- [x] `grep -rn "buildIncludePath" src/contest_generator/ccs.py` = 双 superClass 并存（classic `ti.ccs.misc.options.buildIncludePath` + Theia `com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH`），define 对偶同款（DEFINE_OPTION_SUPERCLASSES）
- [x] `grep -rn "PROJECT_ROOT" src/contest_generator/ccs.py` 有 `${PROJECT_ROOT}` 展开（include_search_dirs，与 ${PROJECT_LOC} 同语义）；以 `${` 开头不可展开宏跳过有注释（SDK/工具链环境宏 + 展开后仍含宏如 ${PROJECT_ROOT}/${ConfigName} 两处）
- [x] 母版已入库：`ls ~/.contest_generator/masters/mspm0/` = main.c + mspm0.syscfg + .cproject + .project + .ccsproject + targetConfigs/ + .settings/，无 .clangd / Debug / README；`grep -n "<name>" ~/.contest_generator/masters/mspm0/.project` = mspm0_project；`mspm0.json` 存在，sources = ["empty_LP_MSPM0G3507_nortos_ticlang"]，warnings 空
- [x] 端到端生成成功（slugs=() 最小工程，真机母版实跑）：无 CcsProjectError，输出树 = main.c 骨架 + mspm0.syscfg + 工程文件 + targetConfigs/，无 empty.c/.clangd/Debug/README；带模块端到端 .cproject 追加 ${PROJECT_LOC}/modules include + sourceEntries 根条目
- [x] **用户手工勾选：生成工程在 CCS Theia 编译通过**（2026-08-09 勾选：CCS Theia 20.5 编译日志全绿——SysConfig 生成 mspm0.syscfg → main.c / startup_mspm0g350x_ticlang.c / ti_msp_dl_config.c 编译 → 链接 mspm0_project.out，无错误无警告；工单 03 未勾项历史首次闭合；SYSCFG_DL_init 注入留后续工单，此处验收 = 编译通过）
- [x] CONTEXT.md 两处更新到位（母版词条补 mspm0 真机母版 = TI empty 示例 + 修改器词条补双格式认知）

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/08-mspm0-theia-master.md（架构深化 v5：mspm0 首个真机母版——ccs.py 双格式认知补齐 + 母版整理入库 + 端到端真机验证）

先读工单全文，按 1-5 节执行。独立 worktree（勿在主检出改，必须 -b 形式）：
git worktree add -b v5-08-mspm0-theia-master ../firstep-v5-08 main

代码部分（在 worktree）：
1. ccs.py 双格式认知：_build_configurations 对 cconfiguration 全部内层 storageModule 找 cdtBuildSystem；include/define superClass 改双值匹配（classic + Theia 20.5 TMS470_TICLANG 4.0）；include_search_dirs 补 ${PROJECT_ROOT} 展开、${...} 不可展开宏跳过；docstring 补双格式说明
2. 测试：fakes.py 加 Theia fixture（真实 empty 工程 .cproject 为底）→ 配置定位 / patch 双格式 / include_search_dirs Theia 四态 / summary 双格式 + 结构 pin 双 superClass；端到端合成 Theia 母版生成最小工程；既有 classic 断言原样过
3. CONTEXT.md 按工单 4 节更新

母版部分（worktree 外用户环境，对 C:\Users\luoji\workspace_ccstheia\empty 副本操作，源目录零改动）：
4. 整理：empty.c→main.c、empty.syscfg→mspm0.syscfg、删 .clangd/Debug/README.html/README.md、.project name→mspm0_project、.ccsproject filesToOpen 只留 mspm0.syscfg
5. 入库：python 调 master_store.import_master(masters_dir=~/.contest_generator/masters, platform="mspm0", source_dir=整理后目录, sources=("empty_LP_MSPM0G3507_nortos_ticlang",))，打印返回 meta 作验收证据（warnings 应为空）

收尾：
6. 全量 pytest 绿 + mypy 干净 + 验收项除真机编译外全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main
7. 告诉用户在 CCS Theia 打开生成的最小工程编译（真机验收最后一项，用户勾选后回填）

注意：编辑前先确认 cwd 在 worktree；勿串行做别的工单；母版整理入库操作别动 CCS 工作区原工程。
```

## Comments

（2026-08-09 立项：用户提供 workspace_ccstheia/empty（TI SDK 官方 empty 示例，CCS Theia 20.5 / TMS470_TICLANG 4.0 导出）并提议直接作 mspm0 母版。勘察后确认方向对（正合 ADR 0002，比蒸馏旧工程干净），但三处与 ccs.py 认知不匹配，生成必拒：D1 配置定位——Theia 把 cdtBuildSystem 移出 settings storageModule 放独立 cdtBuildSystem storageModule（classic fixture 在 settings 内），`_build_configurations` 返回空 → "没有 build configuration"；D2 选项 superClass——classic `ti.ccs.misc.options.buildIncludePath` vs Theia `com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH`（define 同款）；D3 宏——Theia include 值用 `${PROJECT_ROOT}`（代码只展开 `${PROJECT_LOC}`）+ SDK 环境宏。另：主文件是 empty.c 非 main.c（不改名则与骨架 main.c 双 main 链接冲突——CCS 不枚举源文件，根 sourceEntry 扫全树）；`.clangd`/Debug/README 为机器噪音（copytree 只忽略 .git，会原样带进每个生成工程）；`.project` 名 "empty" 会让所有生成工程撞名。边界决策：ccs.py 双格式单实现路径不分支双写（classic 行为零变化，fixture 原样过）；不做变量引擎（SDK 宏跳过）；SYSCFG_DL_init 骨架注入留后续工单（骨架覆盖母版后 init 不执行，时钟走复位默认——如实记录为已知限制，本工单验收=编译通过）；母版 syscfg 按 TI 官方板，地猛星外设用户生成后自改（模板预期）。这是 mspm0 线首个真机母版，工单 03 的 CCS 真实编译未勾项在此闭环。）

（2026-08-09 收尾：D2 实施时发现立项漏记的第四处差异——Theia 的 include/define 选项不在 toolChain 直接子元素里，而在编译器 `<tool>` 元素内（classic 是直接子元素），`_include_option` 先查 toolChain 再查 tool 内层，同一条多值匹配通吃。另有意的实现偏离一处：Theia 母版无 sourceEntries 元素（CDT 缺省 = 全树为源），`_ensure_modules_source_entry` 没有照字面只加 modules 条目，而是补 classic 同款根条目（name="" excluding=Debug）——sourceEntries 一旦存在 CDT 就把它当完整源集，只加 modules 会让 main.c 等母版源码不再被编译、真机验收必挂（根条目是 classic 实证形态，两格式输出一致）；测试断言随之改为根条目覆盖 modules/。母版整理入库全程对 `workspace_ccstheia/empty` 副本操作、源目录零改动（副本留在 %TEMP%\mspm0_master_tidy 可查）；import_master 返回 warnings=()。真机母版实跑 generate_project（slugs=()）无 CcsProjectError，输出树干净。真机编译留用户勾选。）

（2026-08-09 真机验收勾选：用户在 CCS Theia 20.5 编译生成的最小工程（%TEMP%\mspm0_theia_gen_test），日志全绿——Clean → SysConfig 生成（Debug/device_linker.cmd、device.opt、ti_msp_dl_config.c/h、device.cmd.genlibs）→ main.c / startup_mspm0g350x_ticlang.c / ti_msp_dl_config.c 三源编译（tiarmclang，`-I` 含工程根 = ${PROJECT_ROOT} 展开 + Debug = ${PROJECT_ROOT}/${ConfigName} 展开，SDK 宏在 CCS 侧解析）→ 链接 mspm0_project.out，无错误无警告。两点实证：① 编译源列表含 main.c（sourceEntries 根条目决策生效——只加 modules 条目则 main.c 不在扫描集）；② 构建生成的 Debug/syscfg 与 generated 源与根条目 excluding="Debug" 不冲突（syscfg 生成物走 makefile 规则进编译）。mspm0 线首个真机母版闭环，工单 03 的 CCS 真实编译未勾项历史首次闭合。）
