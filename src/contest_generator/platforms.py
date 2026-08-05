"""平台标识词表。

manifest 的 platforms 键、修改器注册表的键、生成器的 platform 参数共用
这套词表——三个模块各自硬编码字符串会静默漂移。manifest 本身保持通用：
它允许任何平台键，只是已知平台只有这两个。
"""

PLATFORM_STM32 = "stm32"  # STM32F103C8T6 最小系统板，Keil5
PLATFORM_MSPM0 = "mspm0"  # 地猛星开发板 MSPM0G3507，CCS

KNOWN_PLATFORMS = (PLATFORM_STM32, PLATFORM_MSPM0)
