# 01 — README 渲染器核心 + 生成落盘

**What to build:** 生成工程时自动附带一份 `README.md`，含三章：工程概览（平台/主控/板名）、引脚接线表（默认脚）、模块清单与依赖。生成流程任何既有产物逐字节不变，只是工程根多出一个 README.md。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 新模块纯函数 `render_readme(...)` 输入（platform、板名、依赖展开后的 manifest 集），返回完整 README 文本；utf-8、尾部换行、不含时间戳（同一输入两次调用产出逐字节一致）。
- [x] `generate()` 写侧在 patcher 之后、返回之前落盘 `output_dir/README.md`；写入失败走既有 rmtree 兜底（生成原子性不破）。
- [x] 工程概览章显示平台/主控中文名（mspm0 ↔ TI MSPM0G3507 / CCS，stm32 ↔ STM32F103C8T6 / Keil5）+ 板名（取不到板名优雅降级为不显示，不阻断生成）。
- [x] 引脚接线表章列所选模块该平台 `pins` 声明：模块/角色/生效引脚/备注（类型 + required）；生效引脚 = 声明默认值（本工单不接绑定）；未声明 pins 的模块不硬猜，表尾固定尾注「其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准」。
- [x] 模块清单与依赖章按 manifest 集顺序（依赖先于使用者）渲染每模块 slug + description + dependencies（有依赖才列）。
- [x] 测试（走 `generate_project()` 流程级 seam）：生成 stm32 与 mspm0 各一例到 tmp，断言 README.md 存在、含五章标题中本工单覆盖的三章、含所选模块 slug/description、引脚表含声明角色的默认引脚、不含未选模块的引脚。
- [x] 全量测试绿 + mypy 干净（src 全部文件）。

**Comments（2026-08-17 主会话落地）：**

- 实现：`src/contest_generator/readme.py`（render_readme 纯函数 + README_FILENAME / PIN_TABLE_FOOTNOTE 单源）、generator.generate() try 块内 patcher 之后落盘 README.md；`tests/test_readme.py`（流程级双平台 + 渲染器直测 11 例）。
- 影响既有测试两处（README.md 进入产物树）：
  - `test_k230_artifact.py` 全树逐字节比对排除 README.md（README 随模块集渲染，非「既有生成文件」契约）。
  - `test_generator.py::test_generate_mspm0_theia_minimal_project_succeeds`：原「无 README」断言改为「README.md = 生成产物（母版 TI 噪音 README.html 仍剔除）」。
- 代码评审（双轴 sub-agent）处置：绑定路径复用已加载 board（避免二次读盘）；PLATFORM_TITLES 注释澄清与 webapp.PLATFORM_DISPLAY_NAMES 的差异（spec 逐字文案 vs 界面 chip）；补 board 降级流程级测试。留痕不展开：pin 行/测试 `_m` 的位置元组 = 模块单文件私有形状（_module_sources 先例），不引入 dataclass。
- 验收：全量 1787 绿 + mypy src 47 文件干净；本工单范围 = 三章（快速上手 / 验证顺序清单 / 多实例 / 绑定覆盖 = 后续工单）。
