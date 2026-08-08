# 01 — 生成门禁：main.c 围栏剥离 + include 解析校验（真机编译双 bug）

**What to build:** 真机编译（2021F，Keil 5.06）暴露两个独立缺陷，均为「产物无法编译但生成流程静默通过」：

- **Bug A（main.c 代码围栏）**：`main.c(1): #7: unrecognized token`，第 1/101 行是字面 ` ```c ` / ` ``` `。根因：LLM 骨架输出带 Markdown 围栏直接落盘——`SKELETON_SYSTEM_PROMPT` 未禁止围栏、`sanitize_skeleton` 只处理不存在的函数调用、代码里没有任何剥离步骤。连锁炸掉 stm32f10x.h 解析（IRQn_Type undefined ×9），共 18 errors。
- **Bug B（悬空 include）**：`pid.c(2): #5: cannot open "digit_uart.h"`。根因：库模块引用了从未入库的头——pid 模块代码引用 K230 数字识别驱动 `digit_uart.h`（真实工程 `~/Desktop/2021F/21F/code/digit_uart.{c,h}` 里有，但当时 `module_import.py` 只显式导入了 `pid.c,pid.h`，digit_uart 没进清单）；`manifest.dependencies` 为空；**录入与生成环节都没有 include 解析校验**，悬空引用静默入库。同族：2026C 的 zone/uwb_uart/lock_control 三模块引用共享 `config.h`（`~/Desktop/2026C/code/config.h`，同样未入库）——用户未编译 2026C 所以没发现。

**反馈环缺口**：`generate_check.py` 只断言「main.c 存在 + uvprojx 存在」，对两个 bug 都不红——Keil 编译成了唯一红信号，且红在用户侧。已补两断言（围栏 + include 解析，按 Keil 语义：当前目录 → uvprojx IncludePath → 标准库/器件包 allowlist），旧产物上当场红 8 处（2021F×3 + 2026C×5）。

## 实现落点

- **skeleton.py**：`strip_code_fences()`（剥离 LLM 输出首尾 ` ```lang ` / `~~~` 围栏行，无围栏原样返回，中间位置不动）；`generate_skeleton` 在自检前先剥离；新增 `_strip_comments_keep_preprocessor()`（剥注释、`#` 行整行透传——include 文件名在引号里，普通字符串剥离会误删，判例见下）。
- **llm.py**：`SKELETON_SYSTEM_PROMPT` 追加「输出纯 C 代码，不要用 ``` 或 ~~~ 代码围栏包裹，不要输出任何 Markdown 标记」（第一道防线）。
- **generator.py**：两个生成前门禁（均在创建输出目录之前失败）：
  - `FencedMainCError`——main.c 含围栏行明确报错（兜底：输入绕过骨架阶段或手改带入）；
  - `UnresolvedIncludeError`——`_check_unresolved_includes` 扫描 main.c + 模块源码（剥注释后）的引号 include，解析范围 = 当前目录 + 模块代码目录 + 母版 IncludePath + 标准库/器件包 allowlist（`math.h` 等引号标准库头与 `stm32f10x_conf.h` 器件包头在工程外可解析，缺了会误报）。
- **keil.py**：`include_search_dirs()`（解析 .uvprojx IncludePath 为绝对目录，Keil 格式知识归位）。
- **harness**：`generate_check.py` 补 `check_artifacts()`（围栏 + include 解析两断言）。

## 判例（本工单两个，均被回归测试钉死）

1. **第 2 行起 `#` 行漏检**：`_strip_comments_keep_preprocessor` 初版用 `_at_line_start_after_ws`（回退跳过整段空白包括换行），只有第 1 行的 `#include` 命中透传分支，第 2 行起的文件名被当字符串剥掉——第一版门禁对真实 pid.c（第 2 行 `digit_uart.h`）漏检，end-to-end 时生成静默成功。修复后 fixture 把悬空 include 放第 2 行复刻。
2. **围栏落盘**：LLM 输出带 ` ```c ` 原样写进 main.c（2021F 与 2026C 同现），Keil 报 unrecognized token。

## 测试

+10（763 全绿）：`strip_code_fences`（首尾/无围栏透传/中间不动/全流程剥离）；`_strip_comments_keep_preprocessor`（第 2 行 include 文件名保留、注释里的 include 不算）；include 门禁（悬空拒绝并点名头文件、跨模块 include 正常、引号标准库头不误报）；围栏 main.c 拒绝（`FencedMainCError`）。

## 库变更（不落 git，全局库 ~/.contest_generator）

- 新模块：`digit_uart`（K230 数字识别串口驱动，2021F 真实工程导入，通用模块）；`config`（2026C 专用配置头——首版导入被专用性校验拒绝，按「2026C 数字钥匙题专用」标注后通过）。
- 依赖声明：`pid → digit_uart`；`zone/uwb_uart/lock_control → config`（生成时自动展开，推荐器无需专门选中）。

## 验收（真实 LLM 全流程，`generate_check.py 2021F 2026C`）

- 2021F：✓ 通过——模块 digit_uart(依赖展开)+motor+pid，产物 0 问题（无围栏、include 全解析）。
- 2026C：✓ 通过——模块 zone/uwb_uart/lock_control/filter+config(依赖展开)，产物 0 问题。
- 修复前行为：2021F 生成静默产出带围栏 main.c + 悬空 digit_uart.h 的工程（Keil 18 errors）；修复后门禁在落盘前报「模块 pid 的 code/pid.c 引用了最终工程中不存在的头文件 digit_uart.h」。
- 最终证明：用户 Keil 实际重编译 `out_2021F/user/Project.uvprojx` 一次。

**Status:** resolved

## Answer

- [x] 围栏三层修复：提示词禁 + `strip_code_fences` 剥离 + `FencedMainCError` 兜底。
- [x] include 门禁：`_check_unresolved_includes`（Keil 语义解析范围 + 标准库/器件包 allowlist），`UnresolvedIncludeError` 拒绝产出残缺工程。
- [x] 反馈环补断言：`generate_check.py` 围栏 + include 解析，旧产物红 8 处、修复后双题全绿。
- [x] 库内容补录：digit_uart / config 两模块 + 四组依赖声明（见「库变更」，全局库非 git）。
- [x] 回归测试 +10，763 全绿。
- [ ] 用户 Keil 真机重编译确认（修复后产物 `worktree/.scratch/real-run/out_2021F`）。
