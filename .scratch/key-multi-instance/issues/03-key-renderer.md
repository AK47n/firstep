# 03 — KeyInstanceRenderer 渲染 hook

**要做什么：** key 多实例的渲染闭环：实例计划 → 生成工程里的通道表头覆写 +
mspm0 syscfg 多实例改写，并注册进多实例渲染注册表；骨架 / 冒烟接口块自动注入
同一份宏清单（喂 LLM 的通道宏 = 工程实际生成的宏）。空计划 = 单实例默认 =
零写侧变化。

**被谁阻塞：** 02（通道表默认文件与驱动已就位）。

**状态：** resolved

**评审结论（2026-08-31 双轴评审）：** Standards 无硬违规（判断项：key 层与 led
层同构克隆——被「led 渲染为同构先例」文档化标准覆盖，折减；syscfg 直写绕过
syscfg_model 单源——led 既定写法沿袭，文件头已注明「只碰 $assign + 追加块」；
Data Clumps 四参同游——同构先例下接受）。整改：instance_render.py 文件头
docstring 更新为「led 首个、key 第二个、beep/motor 留口」。Spec 轴无实质缺失
（SysConfig 宏名验真与 mspm0 追加块真机编译归 07，issue 已声明）；跨工单
触碰（stm32 默认表 KEY_CHANNEL_0_GPIO→PORT 列名修正）为「默认文本逐字节一致」
验收所需的缺陷修复；默认 5 别名 vs 单实例计划单宏的不对称与 led 同构
（越界钳回首通道，语义闭合）。959 passed（multi-instance/skeleton/generator/
selection/llm/webapp 聚焦）。

- [x] 渲染纯函数：实例计划 → 通道表头全文（COUNT + 通道索引宏 + 每通道 (port, pin)
      对表），空计划 = 与库内默认文件逐字节一致（沿用 led 渲染常量钉死先例）。
- [x] mspm0 syscfg 改写纯函数：通道 0 复用母版 KEY 输入实例（计划脚 ≠ PA2 →
      改 `KEY.associatedPins[0].pin.$assign`，head/tail/eol 原样保留、CRLF 接回）；
      通道 1+ 追加 `KEY_<实例号>` GPIO 输入实例块（pin `$name` = `KEY<实例号>`
      全局唯一，direction = INPUT，不配内部电阻——沿母版输入实例先例）。
- [x] KeyInstanceRenderer：render（空计划不写，写侧变化才落盘）/ inject_blocks
      （通道表全文 + key_init() 与逐个 get_key_state(<通道宏>) 提示）/
      managed_headers（声明接管文件，接口块剔除库内基线）。
- [x] 默认渲染注册表注册 KeyInstanceRenderer（新模块多实例 = 加一条的扩展口）。
- [x] 骨架 / 冒烟接口块经既有管线自动带上 key 块（通用层零改动）。

**验收标准备注：** 含 mspm0 syscfg 追加块真机编译验证——SysConfig 生成环节纯单测
覆盖不了，归 07；本单以纯函数单测 + 文本形态断言验收。
