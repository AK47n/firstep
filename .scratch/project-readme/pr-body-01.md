# 随工程生成「上手即战」README（工单 project-readme/01）

## 背景

工具生成的工程"打开就能编译"，但学生打开后不知道下一步干嘛——编译入口、接线、先验证哪个模块全靠翻代码。本特性：生成工程时自动附带 README.md，纯确定性模板渲染（不吃 LLM、无 AI 味、无时间戳、同一输入逐字节一致），总是生成、无前端开关。

## 本工单（01）三章

- **工程概览**：平台/主控中文名静态映射（stm32 ↔ STM32F103C8T6/Keil5、mspm0 ↔ TI MSPM0G3507/CCS）+ 板名（绑定路径复用已加载 board；缺省路径 `board_for_platform` 取不到优雅降级为不显示，不阻断生成）。
- **引脚接线表**：两平台统一取 manifest `pins` 声明——模块/角色（label 附注）/生效引脚（本工单 = 声明默认值，绑定覆盖留 03）/说明（类型 + 必接标记）；未声明 pins 的模块不硬猜，表尾固定尾注「其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准」。
- **模块清单与依赖**：按依赖展开后的 manifest 集顺序渲染 slug + description + dependencies。

## 实现

- `src/contest_generator/readme.py`（新）：`render_readme(platform, board_name, manifests)` 纯函数，`README_FILENAME` / `PIN_TABLE_FOOTNOTE` / `PLATFORM_TITLES` 单源。
- `generator.py`：`generate()` try 块内 patcher 之后、返回之前落盘 `output_dir/README.md`（失败走既有 rmtree 兜底，生成原子性不破；纯新增文件，既有生成文件逐字节不变）。
- `tests/test_readme.py`（新，11 例）：`generate_project()` 流程级 stm32/mspm0 双平台 seam + 渲染器直测 + board 降级 monkeypatch。
- 影响既有测试两处（README.md 进入产物树）：`test_k230_artifact.py` 全树比对排除 README.md；`test_generator.py::test_generate_mspm0_theia_minimal_project_succeeds` 原「无 README」断言改为「README.md = 生成产物」。

## 验收

- 全量 1787 绿 + mypy src 47 文件干净
- 提交：1781eb9 + CHANGELOG hook 6df826f

## 后续工单

- 02：快速上手（编译/烧录步骤）+ 验证顺序清单（依赖拓扑 + bring-up 前置）
- 03：绑定覆盖 + 多实例进引脚表
