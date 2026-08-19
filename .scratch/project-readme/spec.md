# Spec：随工程生成「上手即战」README

## Problem Statement

学生用工具生成工程后，打开 Keil / CCS 的第一反应是："接下来干嘛？"——编译入口在哪、怎么烧录、传感器接哪些脚、先验证哪个模块，全靠翻代码猜。工具现在做到了"打开就能编译"，但还没做到"打开就知道下一步"。四天三夜分秒必争，这个"从 0 到 1"的启动成本正是新手队最大的时间黑洞。

## Solution

生成工程时自动附带 `README.md`——一份纯确定性模板渲染的"上手即战"文档，不吃 LLM、无 AI 味、可逐字节测试。内容五章：工程概览、快速上手（编译/烧录）、引脚接线表、模块清单与依赖、验证顺序清单。学生照着 README 前 5 分钟就能把工具链跑通、照着接线表接线、按清单逐个验证模块。

## User Stories

1. 作为学生，我想在生成的工程里看到一份 `README.md`，以便知道这个工程是什么、用什么主控、什么板子。
2. 作为学生，我想看到编译与烧录步骤（按平台区分），以便 5 分钟内把工程跑起来。
3. 作为学生，我想看到所选模块的引脚接线表（模块/角色/引脚/说明），以便照着接线、不用翻代码。
4. 作为学生，我想看到引脚表反映我绑定的引脚（而非仅默认值），以便接线与实际生效配置一致。
5. 作为学生，我想看到选中模块的完整清单（含依赖展开与 AI 推荐结果）和依赖关系，以便知道工程里到底有什么。
6. 作为学生，我想看到一个验证顺序清单，以便知道先验证哪个模块、逐盏灯把整个工程点亮。
7. 作为开发者，我希望 README 是纯确定性渲染（不吃 LLM），以便逐字节测试、无 AI 味、生成快、跨运行稳定。
8. 作为开发者，我希望 README 是"总是生成"（无前端开关、无接口字段），以便不引入 UI 改动。

## Implementation Decisions

- **新模块 `readme.py`**：纯函数 `render_readme(...)` 输入（platform、board 名、依赖展开后的 manifest 集、绑定载荷/解析结果、多实例计划），返回 README 完整文本。写侧在 `generate()` 现有 try 块内、patcher 之后、返回之前落盘 `output_dir/README.md`（utf-8，尾部换行幂等；失败走既有 rmtree 兜底，保持生成原子性）。README 是纯新增文件，不触碰任何既有生成文件，逐字节契约不破。
- **工程概览章**：platform → 主控/平台中文名静态映射（mspm0 ↔ TI MSPM0G3507 / CCS，stm32 ↔ STM32F103C8T6 / Keil5）；板名 = `board_for_platform(platform).name`（取不到则优雅降级为不显示，不阻断生成）。
- **引脚接线表章（两平台统一数据源）**：遍历 manifest 集每个模块的该平台 `pins` 声明——列：模块 slug / 角色 id（label 不同时附注）/ 生效引脚 / 备注（类型 + required 标记）。生效引脚 = 绑定载荷覆盖值，否则 `PinDeclaration.default`。未声明任何 pins 的模块不硬猜：表尾固定尾注「其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准」。
- **模块清单与依赖章**：按 manifest 集顺序（= `resolve_dependencies` DFS 后序，依赖先于使用者）渲染每模块 slug + description + dependencies（有依赖才列）。
- **快速上手章**：平台静态步骤文本（mspm0 = CCS 打开/构建/下载；stm32 = Keil5 打开 uvprojx/编译/ST-Link 下载），渲染器内预写固定话术，不做逐模块拼装。
- **验证顺序清单章**：以 manifest 集顺序为基底做稳定分区排序——bring-up 模块（delay / debug_uart / led / led_beep）前置（保持相互间依赖序），其余保持原序；渲染为 Markdown checkbox（`- [ ] slug — description`），附固定引导语「按顺序逐个验证，前一个过了再接下一个」。
- **多实例（工单 03 范围）**：多实例计划（ModuleInstance：name / variant / pin）在引脚表中每实例一行，行内角色名 = 实例名。
- README **不含时间戳**（保持跨运行逐字节确定、可测试）。
- 不做 LLM、不做前端开关、不做报告生成。

## Testing Decisions

- **主 seam = `generate_project()` 流程级**：真实库生成到 tmp，断言 `output_dir/README.md` 存在、含全部五章标题、含所选模块 slug/description、引脚表含声明角色的生效引脚、验证清单顺序符合规则。沿用 `test_generator.py` / `test_default_layout.py` 既有接缝（生成→读输出断言），测试文件独立新增，不塞进旧测试。
- **渲染器纯函数直测**：排序规则（bring-up 前置 + 依赖序稳定）、绑定覆盖（默认与绑定两种载荷各断言生效引脚）、多实例行、空模块集 / 无 pins 声明的边界。
- 测试只断言 README 外部行为（文本内容/顺序），不测内部拼装细节。

## Out of Scope

- LLM 参与文案（用户明确排除 AI 味）。
- 前端开关 / 接口字段（总是生成）。
- 设计报告生成（用户明确排除，格式要求苛刻、AI 味风险）。
- stm32 解析 pin_config.h / mspm0 解析 syscfg 补全未声明引脚（当前用 manifest pins + 尾注兜底；led/beep 等未声明模块的详细引脚留痕后续扩展）。
- README 语言/模板用户自定义。

## Further Notes

- 用户诉求："从一个学生的视角看怎么优化适配帮助完成电赛"。本特性定位 = 消解「生成后不知道从哪开始」的启动成本。
- 起点对话 2026-08-17：用户拍板方向（先做 README，不做报告）、生成方式（纯确定性）、开关（总是生成）、章节（交给我定）。
