# 01 — mspm0 命令行构建脚本（Debug/makefile 集）产品化

**What to build:** 把 `.scratch/real-run/build_makefiles.py`（scratch 后处理脚本，硬编码 CCS 路径 + 静态 MODULES 表）产品化为生成器的一步：**mspm0 平台生成时自动产出 CCS 标准 Debug/makefile 集**（makefile + sources.mk + objects.mk + 逐源目录 subdir_vars.mk/subdir_rules.mk），模块条目按选中模块集推导。让 web 端 mspm0 线的"一键编译修复"真正可用，CLI 真机验收（generate_check）mspm0 线补 gmake 编译段。

**Status:** implemented

**Blocked by:** 无

## 断链证据（2026-08-13 已核实）

- `compile_runner.py:235-239` mspm0 编译只消费 `Debug/makefile`（`_MSPM0_MAKEFILE`），src 内**没有任何生产方**（grep 全 src 仅命中 compile_runner 三处）。
- mspm0 母版（`library/masters/mspm0/`）只有 main.c / mspm0.syscfg / targetConfigs，不带 Debug/。
- 真机产物里的 Debug/makefile 全部来自 scratch 脚本 `.scratch/real-run/build_makefiles.py` 后处理（2024H 真机 gmake 0 错已验证通路）。
- 因此现在 web 上 mspm0 生成后点"一键编译修复"**必报**"工程里没有 Debug/makefile 构建脚本（CCS 命令行构建产物缺失）"——一条龙对 mspm0 线是断的。
- `generate_check.py:369-370` 文案"mspm0/CCS 线：Theia 无命令行构建"已过时——gmake 通路真机跑通过。

## 决策记录（代决，用户可 grilling）

- **实施选点（实施注两案取后者）**：探测调用放 webapp 装配层（find_ccs_tools(config 三键)），generate / generate_project 经 `ccs_tools: CcsTools | None` 参数注入——理由：config 覆盖值归装配层持有（生成核心不持 config，三键入参会污染签名）；直接调用方不传 = 确定性跳过 makefile（既有 generate()/generate_project() 测试零 monkeypatch 即稳定，本机装了真 CCS 也不会让 theia 结构断言漂移）；webapp 已有 find_uv4 / find_make 同款先例。探测本体仍归 compile_runner（决策 1 落位不变）。mspm0 + None → generate/generate_project 出 CCS_NOT_FOUND_HINT（compile_runner 常量单源），装配层零文案。
- **模板与 scratch 脚本逐字节对照验证**（本机可跑原脚本）：11 文件集全对上；makefile 仅两处刻意清理 scratch 残留——死行 `-include /subdir_vars.mk`（不存在的绝对路径 include，gmake 静默忽略）与 all 目标行尾多余引号（f-string 拼写残留）。其余逐字节一致。首版移植曾在 ORDERED_OBJS 续行块插空行（gmake 空行终止变量定义 → 解析错误），对照验证抓出并已修。
- **真机 gmake 不在 PATH**：CCS 自带 gmake（C:/ti/ccs2050/ccs/utils/bin/gmake.exe）。验收时经 /api/settings 置 gmake_path 覆盖（既有键，本机 config 已生效）；CLI gmake_build 走 GMAKE 环境变量（KEIL_UV4 同款惯例）。
- **测试落位微调**：find_ccs_tools 用例落 test_compile_runner.py（模块归属，与 find_uv4/find_make 同区）而非 ticket 草案的 test_makefiles.py；test_makefiles.py 专注模板渲染/落盘。覆盖点无删减。

1. **落位：新域模块 `makefiles.py`（纯函数模板）+ 探测归 compile_runner**——makefiles.py 只做参数化模板（迁移 build_makefiles.py 的模板文本，路径全部入参）；CCS 工具链路径探测 `find_ccs_tools()` 放 compile_runner.py（它已是工具链探测域：find_uv4 / find_make 先例）。generator import makefiles + compile_runner 探针，**不 import keil/ccs**（生成侧读缝既定方向不破）。
2. **MODULES 不维护静态表**——从选中模块 manifest 的 mspm0 平台条目 files 字段推导（过滤 .c，子目录 = rel 路径父目录），与 build_makefiles.py 的"按工程模块集过滤"同语义，但知识源头 = manifest 单源（scratch 表已经和 manifest 重复一份，再搬进来就是第三份）。ml_mpu6050（ml_libs 子目录）形态天然覆盖。
3. **探测失败 = 跳过 makefile + 提示，不阻断生成**——生成与编译解耦（已有先例：/api/compile 不要求 AI 配置）。探测不到 CCS 路径时照常生成工程，`GenerationSummary` 加 `build_hint` 字段（中文，说明"未探测到 CCS 工具链路径，命令行构建不可用，可在设置页填 ccs_* 覆盖后重新生成"）；web /api/generate 响应透传、CLI 打印。
4. **探测策略**：config.json 三个新可选键 `ccs_sdk_dir` / `ccs_compiler_dir` / `ccs_sysconfig_cli`（空 = 自动探测）→ 自动探测扫描 `C:/ti/ccs*/` 目录（SDK = `mspm0_sdk_*`、编译器 = `ccs/tools/compiler/ti-cgt-armllvm_*`、sysconfig = `sysconfig_*/sysconfig_cli.bat`；多版本取……见实施注）。真机两版本共存（SDK 在 ccs2051、编译器在 ccs2050）——探测**逐件独立**，不要整包假设同版本目录。
5. **挂点**：`generator.generate()` 在 `patcher.patch()` 之后写（产物完整后生成构建脚本）；`generate()` 返回变三件套 `(output_dir, include_dirs, build_hint)`，`generate_project` / `GenerationSummary` 随之（build_hint: str = ""）。
6. **generate_check.py mspm0 线补 gmake 段**：`uv4_build` 对偶 `gmake_build(out_dir)`（`collect_build_log("mspm0", ...)` + `find_make`），删"无命令行构建"过时文案；`check_topic` 的 mspm0 分支走真编译（与 stm32 同款通过/失败判定）。
7. **超时观察**：gmake 首编含 sysconfig_cli 运行 + 全量编译，真机计时记录首编时长；若逼近 180s 再议分平台超时（实施时先观察，不预设改）。
8. **范围外（不混入本工单）**：修复循环无进展检测 / skipped 回喂（T2 另立）；骨架未用变量 warning；CCS Theia IDE 集成；`build_makefiles.py` 脚本保留至本工单验收闭环后删除。

## 实施

1. **新增 `src/contest_generator/makefiles.py`**：`write_makefile_set(output_dir, module_sources, sdk_dir, compiler_dir, sysconfig_cli)`——module_sources = ((slug, 子目录, (源文件名, ...)), ...)（生成侧从 manifest 推导后传入，本模块不 import manifest）；模板文本迁自 build_makefiles.py（HEADER / sources.mk / objects.mk / 根 subdir_vars+subdir_rules / 逐模块 subdir_vars+subdir_rules / makefile），路径全部参数化，零硬编码。
2. **`compile_runner.py`**：`find_ccs_tools()` 返回 `(sdk_dir, compiler_dir, sysconfig_cli)` 或 None——config 覆盖 > `C:/ti/ccs*/` 扫描（逐件独立：SDK / 编译器 / sysconfig 各找各的；同件多版本时取**目录名排序最大**（版本号后缀大者新），找不到该件 = 整体 None）。加单测（fake 目录树 + config 覆盖优先）。
3. **`config.py`**：`ccs_sdk_dir` / `ccs_compiler_dir` / `ccs_sysconfig_cli` 三可选键（空串 = 自动探测，类型非法大声失败，save/load 往返——uv4_path 同款）。
4. **`generator.py`**：`generate()` 加 `ccs_tools` 探针分支——platform == mspm0 时调 `find_ccs_tools()`（经入参注入或模块级 import，实施选点见注），命中则从 `copied_files`（`_copy_module_files` 产物，含 rel 路径）推导 module_sources 调 `write_makefile_set`，未命中 build_hint 非空；stm32 零改动。返回三件套 + `GenerationSummary.build_hint` 字段（web 摘要 / 报告透传）。
5. **`webapp.py`**：/api/generate 响应透传 build_hint（前端展示一行提示即可）；/api/settings GET/PUT 透传三键。
6. **`.scratch/real-run/generate_check.py`**：mspm0 分支跑 `gmake_build`（真编译判定 ok）；`check_artifacts` mspm0 线不动（已存在）。
7. **`index.html`**：生成成功摘要区展示 build_hint（非空时）；其余零改动（/api/state 的 gmake 探测已有，按钮置灰逻辑不动）。
8. **测试**：`tests/test_makefiles.py` 新增——模板确定性（固定入参 → 固定文本，含模块过滤：未选模块不出现）/ 三件套路径参数化 / find_ccs_tools（fake 树 + 覆盖优先 + 逐件独立多版本）；结构测试：mspm0 生成产物必含 Debug/makefile 且模块条目 = 选中集、stm32 产物不含；config 往返；generate_check 契约测试同步 mspm0 词表（如有词表断言）。
9. **不动**：fix_errors.py / llm.py / keil.py / ccs.py / 门禁（GENERATION_GATES）/ 前端修复循环 / 母版 / 模块库。

### 实施注

- `find_ccs_tools` 被 generator 用（生成侧）——compile_runner 是叶子（只 import platforms），generator import compile_runner 无环（compile_runner 不 import generator）；如实施时发现装配更顺，可把探测留 compile_runner、generator 经参数注入（webapp 探好传入）——两案皆可，优先前者（少一处路由装配）。
- makefile 模板含 `SHELL = cmd.exe` 与 `-Wl,-i` 反斜杠路径——迁移时逐字保留转义（build_makefiles.py 里 `chr(34)` / `chr(46)` 拼写可换成直写引号，语义不变即可，测试钉死输出）。
- Debug/ 目录进产物后，`build_output_tree_corpus` / 门禁不吃它（iter_project_files 跳过），确认无门禁红。

## 验收标准

- [x] pytest 全绿 + `mypy src` 干净 + node --check 内联 JS 通过（2026-08-13：1309 通过（基线 1282 + 27 新增），mypy Success 37 files，node --check OK + 新增元素 id 引用一致性核对过）
- [x] 真机：2024H（xunji 选中）mspm0 生成（**不跑 build_makefiles.py**）→ `generate_check --platform mspm0` 全绿（gmake 0 错）；记录首编耗时（2026-08-13：10 模块 motor/pid/imu_uart/huidu/xunji/led_beep/ntb_time/delay/oled/key，推荐 3 轮收敛 0 补问；Debug/makefile 集自动产出 57 文件；**gmake exit=0 0 error(s) 2 warning(s)，6.6s**——远低于 180s 超时，决策 7 观察结论：无需分平台超时。2 warning = SysConfig UART ovsRate 建议噪音（.syscfg 工具提示，非代码）；pid 本轮被选中（真库 mspm0 条目 code/pid_mspm0.c+gray_track_mspm0.c，manifest 推导天然覆盖））
- [x] 真机：web 端 mspm0 生成 → 一键编译修复可用（gmake 通路，不报"没有 Debug/makefile"）（2026-08-13：/api/generate 最小工程 build_hint 空 + Debug/makefile 落盘（structure 不含 Debug，treewalk 跳过）；/api/compile SSE done exit=0 passed=True 7.1s；gmake_path 经 /api/settings 置 C:/ti/ccs2050/ccs/utils/bin/gmake.exe（CCS 自带 gmake 不在 PATH），/api/state mspm0 工具链置亮）
- [x] 真机回归：generate_check 默认双题（2026C/2021F stm32）全绿不受影响（2026-08-13：2026C UV4 exit=0 0 错误；2021F UV4 exit=1 0 错误——exit=1 = 有警告无错（LLM 骨架未用变量，非回归），compile_passed 判定通过；stm32 产物无 Debug/（零改动验证））
- [x] 探测失败路径：无 CCS 路径环境（或 fake）→ 生成仍成功 + build_hint 非空（不阻断）（单测 fake 树/空根 + webapp monkeypatch 两路；真机：settings 置坏 ccs_sdk_dir 覆盖 → 生成 200 + build_hint 原文 + 无 Debug/，随后恢复空覆盖自动探测）
- [x] `git status` 只出现预期文件（新增 makefiles.py / test_makefiles.py，改 compile_runner/config/generator/webapp/index.html/generate_check/既有测试 7 件 + conftest；无越界改动）
- [x] 验收闭环后删除 `.scratch/real-run/build_makefiles.py`（scratch 后处理退役，2026-08-13 已删；产物侧引用清零——compile_runner 两处注释改指 makefiles.py，src 内无任何 build_makefiles 生产依赖）

## Comments
