"""本地模型零代码 drop-in 实测（spike）。

走项目真实的 DeepSeekLLM + 真实提示词 + 真实严格解析器，只把 base_url
指向本地 Ollama 的 OpenAI 兼容端点（http://localhost:11434/v1）。
测四类代表性调用：
  1. summarize_topic       —— 中文文本摘要（easy 组）
  2. clarify               —— JSON mode（探 response_format 是否被 Ollama 接收）
  3. summarize_module      —— C 代码 → 中文简介（easy 组）
  4. validate_module_description —— JSON 判断（中等，入库门禁）
  5. generate_main_skeleton —— main.c 代码生成（风险组：要能编译）

每个调用打时间和完整输出，不吞错——JSON 调用失败大概率 = response_format
协议问题，是本次 spike 的头号发现项。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.llm import DeepSeekLLM  # noqa: E402

# ---- 本地配置 ----
LOCAL_BASE_URL = "http://localhost:11434/v1"
LOCAL_MODEL = "qwen2.5-coder:7b-instruct"

# ---- 真实赛题输入（2026C，取任务+要求两节，截短） ----
_TOPIC = Path(__file__).resolve().parents[2] / "library" / "topics" / "2026C" / "topic.md"
problem_text = _TOPIC.read_text(encoding="utf-8")
problem_text = problem_text[problem_text.index("一、任务") : problem_text.index("三、说明")][:2200]

# ---- 真实模块代码样本（手写等价的干净 C，避免 GBK 编码干扰） ----
SAMPLE_LED_C = '''#include "led.h"
#include "ti_msp_dl_config.h"

static const led_pin_t LED_PINS[LED_CHANNEL_COUNT] = LED_PIN_TABLE;

void led_init(uint8_t channel)
{
    led_off(channel);
}

void led_on(uint8_t channel)
{
    led_pin_t led = LED_PINS[channel];
    DL_GPIO_setPins(led.port, led.pin_mask);
}

void led_off(uint8_t channel)
{
    led_pin_t led = LED_PINS[channel];
    DL_GPIO_clearPins(led.port, led.pin_mask);
}
'''

SAMPLE_LED_DESC = (
    "LED 指示驱动模块（双平台）：提供 led_init/led_on/led_off/led_toggle 四个函数，"
    "通过 led_instances.h 的 LED_CHANNEL_COUNT + LED_PIN_TABLE 支持多实例渲染；"
    "可用于声光提示、状态指示等电赛功能。"
)

# ---- 骨架生成用模块接口（贴合 2026C 需求） ----
MODULE_INTERFACES = [
    "debug_uart: void debug_uart_init(void); void debug_uart_send(const char *s); int fputc(int ch, FILE *f);",
    "led: void led_init(uint8_t channel); void led_on(uint8_t channel); void led_off(uint8_t channel);",
    "beep: void beep_init(void); void beep_on(void); void beep_off(void);",
    "oled: void oled_init(void); void oled_show_string(uint8_t page, const char *s); void oled_clear(void);",
    "key: void key_init(void); uint8_t key_scan(void);",
    "digit_uart: void digit_uart_init(void); void digit_uart_send(const char *s);",
]


def main() -> None:
    config = AppConfig(
        base_url=LOCAL_BASE_URL,
        api_key="local",  # 本地服务不校验，占位即可
        model=LOCAL_MODEL,
    )
    llm = DeepSeekLLM(config)
    print(f"== 本地端点: {LOCAL_BASE_URL}  模型: {LOCAL_MODEL} ==")

    def run(label: str, fn, **kw) -> None:
        print(f"\n{'='*70}\n[{label}]")
        t0 = time.time()
        try:
            result = fn(**kw)
            dt = time.time() - t0
            print(f"--- OK in {dt:.1f}s ---")
            print(result if isinstance(result, str) else repr(result))
        except Exception as exc:  # 不吞错：打印异常与类别
            dt = time.time() - t0
            print(f"--- FAIL in {dt:.1f}s: {type(exc).__name__}: {exc}")

    run("1 赛题简介 summarize_topic", llm.summarize_topic, problem_text=problem_text)
    run("2 澄清 clarify (JSON mode)", llm.clarify, problem_text=problem_text, clarifications=[])
    run("3 模块简介 summarize_module", llm.summarize_module, code=SAMPLE_LED_C)
    run(
        "4 简介一致性校验 validate_module_description (JSON)",
        llm.validate_module_description,
        description=SAMPLE_LED_DESC,
        code=SAMPLE_LED_C,
    )
    run(
        "5 main.c 骨架 generate_main_skeleton",
        llm.generate_main_skeleton,
        problem_text=problem_text,
        module_interfaces=MODULE_INTERFACES,
    )


if __name__ == "__main__":
    main()
