# Spec — 多实例默认兜底（instance-default-fallback）

## 问题陈述

AI 猜实例（module-multi-instance/06）依赖模型按题面数量输出 instances——题面没写数量（如 2026C 只有"声光提示"）时模型不猜，推荐结果 done 载荷无 instances，前端实例卡为空，用户要手动逐个添加。

## 方案

推荐结果装配时兜底：**命中多实例模块（led）且 AI 未猜实例 → 按平台默认实例清单自动填入**（实例卡直接可见，用户可增删改）。AI 猜了则用 AI 结果（现行为不变）。默认清单与「不配置 = 单默认实例」的生成结果等价（stm32 红黄绿 3 实例 / mspm0 单实例无颜色），渲染零回归。

## 用户故事

1. 作为用户，我推荐 2026C（题面没说 LED 数量）时，实例卡自动填好平台默认（stm32 红/黄/绿），我改数量/颜色即可。
2. 作为用户，AI 猜到数量/颜色时（如"4 个指示灯"→ led×4），用 AI 结果（现行为不变）。
3. 作为用户，我没选任何多实例模块时，done 载荷不带 instances（旧载荷逐字节不变）。
4. 作为用户，默认实例的生成产物与不配置时逐字节一致（零回归）。

## 实现决策

- 平台默认实例清单单源函数 `default_instance_plan(platform) -> tuple[ModuleInstance, ...]`（selection.py，紧邻 expand_instances）：stm32 → 红/黄/绿 3 实例（名称"红灯/黄灯/绿灯"）；mspm0 → 单实例（名称"LED"，variant 空串 = 非内置色 → LED_1 通用编号 + 默认脚）；未知/空平台 → 空（不兜底）。
- `run_recommendation` 加 `platform: str = ""` 参数（webapp recommend 路由传 chosenPlatform；缺省空 = 旧调用不兜底）。
- 装配兜底（result 装配处）：`selection.instances` 为空 且 platform 非空 且 命中模块含 multi_instance（从 topic.manifest_summaries 的 multi_instance 取能力清单）→ 对每个命中且缺实例的多实例 slug 补 `default_instance_plan(platform)`。
- 前端零改动（done 载荷带 instances → 既有回填逻辑自动显示实例卡）。
- 契约：AI 有 instances → 原样；无多实例模块 → 不落键（旧载荷逐字节不变）。

## 测试决策

- selection 单测：stm32 兜底 3 实例（红黄绿）/ mspm0 兜底 1 实例 / AI 实例原样 / 无多实例模块不落键 / 空 platform 不兜底。
- webapp 集成：recommend done 载荷——命中 led 无 instances → 带默认；既有断言（dht11/oled 非多实例）原样绿。
- 渲染零回归：跑既有 test_module_multi_instance（红黄绿渲染 == 默认文件断言）。

## 范围外

- 不改变 AI 猜实例 prompt / 校验（module-multi-instance/06 现行为）。
- 不做"按题面猜数量"的启发式（那是 AI 的活）。
- 推荐缓存指纹校验 = backlog 第 1 项，另行立项。
