# 02 — key 模块多实例化（manifest + 泛型驱动 + 默认通道表）

**要做什么：** key 模块具备多实例能力的基础形态：manifest 声明 multi_instance，
模块驱动从「单键 get_key_state(void)」泛型化为「通道式 get_key_state(channel) +
key_init()」，新增默认通道表头（1 通道，落模块 code 目录、随模块复制进工程）。
旧式单键（不配实例）行为与现状等价——库内数据与驱动一致性由本单与 07 编译矩阵
共同验收。

**被谁阻塞：** 无——可立即开始（库侧独立，与 01 并行）。

**状态：** ready-for-agent

- [ ] key manifest 增加 `multi_instance` 块（max 8，variant = function），manifest
      解析 / ManifestSummary 标注（多实例：上限 8，变体 = function）自动生效。
- [ ] 驱动 API 泛型化：`get_key_state(uint8_t channel)`（上拉低电平按下返回 1，
      channel 越界钳回首通道）+ `key_init(void)`（stm32 逐通道配置内部上拉输入；
      mspm0 空实现，syscfg 已配）。
- [ ] 默认通道表头 = 1 通道（沿 led 两落点：stm32 在母版根、随母版复制；mspm0 在模块
      code 目录、随模块复制）：stm32 引用 pin_config.h 的 KEY_GPIO/KEY_PIN（接线单源
      照旧），mspm0 引用 syscfg 生成的 KEY_PORT/KEY_START_PIN；表头含
      KEY_CHANNEL_COUNT + 通道索引宏 + 每通道 (port, pin) 对表。
- [ ] 母版关键文件白名单（MASTER_KEY_FILES）为 stm32 增加 key_instances.h 条目
      （与 led_instances.h 同构，「按键多实例通道宏」），母版浏览 UI 可见。
- [ ] 单实例（旧请求不配实例）行为与现状等价：通道 0 = 原默认键脚（PA2/PB3）、
      上拉低电平按下语义不变。
- [ ] 默认通道表头文本与库内盘上文件逐字节一致（渲染钉死单测放 03；本单保证文件
      就位且语义正确）。

**验收标准备注：** 本单验收 = manifest/模块文件就位 + 单实例语义等价；跨层零回归与
编译矩阵归 07。
