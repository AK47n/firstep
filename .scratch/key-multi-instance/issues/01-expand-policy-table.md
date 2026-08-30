# 01 — 展开策略表下沉（led 行为钉死）

**要做什么：** 把实例展开（expand_instances）里 led 专属的具体语义（内置色 → 通道宏名、
内置色指定默认脚）从通用代码里抽成「按 slug 的策略表」，led 行 = 现行为零变化，
为 key 行（04）腾出接缝；声明了 multi_instance 但策略表未登记的 slug 大声失败
（防半吊子 manifest）。纯预制工单——不改任何外部行为，只变内部结构。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**评审结论（2026-08-31 双轴评审）：** Standards 无硬违规（判断项：Feature Envy
——策略函数读 policy 数据，权衡后保留模块级纯函数（仓库偏好）；Data Clumps——
8 参函数沿用旧形状；Speculative Generality——first_pin/pin_capability 为 key
预留，spec 驱动非空泛；frozen 浅不可变——现无写方，接受）。Spec 轴两处整改已
落地：① 字面量单源真吸收（宏名/指定脚/首实例脚只在策略行，LED_COLOR_MACROS
转为策略投影的兼容别名，llm 词表消费归工单 05 泛化）；② 未登记 slug 空清单
行为变化（有意——破损 manifest 不静默走单实例）已写进 docstring 声明。
全量测试 2852 passed。

- [x] 展开策略表单源（内置变体 token → 宏名映射、非内置回退宏前缀、平台首实例默认脚、
      可用脚能力类型）存在于 selection 层一处；led 的 `LED_COLOR_MACROS` /
      `STM32_LED_COLOR_PINS` / `MSPM0_LED_FIRST_PIN` 原语义被策略表吸收，改词表只改那一处。
- [x] 策略表建好后 led 实例展开的宏名 / 默认脚结果与现状完全一致（现有
      tests/test_module_multi_instance.py 与 tests/test_selection.py 全部断言不改而绿——若
      必须改断言，说明行为变了，回去重做）。
- [x] manifest 声明了 multi_instance 但策略表未登记 slug → 中文可读的错误
      （SelectionError 语义），不静默走通用猜测。
- [x] 引号 include 自目录优先、越界钳回首通道等既有契约不回退。

**验收标准备注：** 本单无用户可见行为变化；验收以测试全绿 + 策略表结构评审通过为准。
