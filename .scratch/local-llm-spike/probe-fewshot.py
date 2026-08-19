"""few-shot 实验：能否修掉本地 7B 的「围栏包 JSON」格式漂移。

对照实验：clarify 与 validate_module_description 两类 JSON 调用，各
「无示例」vs「带示例」跑 N 轮，用项目真实严格解析器判成败。

消息组装 = 项目真实 system 提示词 + [示例注入] + 项目真实 user 提示词，
传输走项目真实 _chat（Ollama 本地端点），解析走项目真实 parse 函数。
只改消息内容，不动任何项目源码。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.llm import (  # noqa: E402
    CLARIFY_SYSTEM_PROMPT,
    DeepSeekLLM,
    VALIDATION_SYSTEM_PROMPT,
    _clarify_user_prompt,
    _validation_user_prompt,
    parse_clarify_questions,
    parse_validation_result,
)

LOCAL_BASE_URL = "http://localhost:11434/v1"
LOCAL_MODEL = "qwen2.5-coder:7b-instruct"

# 真实赛题（2026C 任务+要求，截短）
_TOPIC = Path(__file__).resolve().parents[2] / "library" / "topics" / "2026C" / "topic.md"
problem_text = _TOPIC.read_text(encoding="utf-8")
problem_text = problem_text[problem_text.index("一、任务") : problem_text.index("三、说明")][:2200]

SAMPLE_LED_DESC = (
    "LED 指示驱动模块（双平台）：提供 led_init/led_on/led_off/led_toggle 四个函数，"
    "通过 led_instances.h 的 LED_CHANNEL_COUNT + LED_PIN_TABLE 支持多实例渲染；"
    "可用于声光提示、状态指示等电赛功能。"
)
SAMPLE_LED_C = '''#include "led.h"
#include "ti_msp_dl_config.h"

void led_init(uint8_t channel) { led_off(channel); }
void led_on(uint8_t channel) { DL_GPIO_setPins(LED_PINS[channel].port, LED_PINS[channel].pin_mask); }
void led_off(uint8_t channel) { DL_GPIO_clearPins(LED_PINS[channel].port, LED_PINS[channel].pin_mask); }
'''

# ---- 示例注入块（唯一实验变量） ----
FEWSHOT_CLARIFY = (
    "\n\n严格按下面的示例输出格式，只输出 JSON 对象本身，不要任何多余文字、"
    "不要 Markdown 代码围栏（不要 ```json）：\n"
    '示例：{"questions": ["题面未说明识别方式，请确认使用哪种传感器？", '
    '"题面未给出精度指标，请确认允许的误差范围？"]}'
)
FEWSHOT_VALIDATE = (
    "\n\n严格按下面的示例输出格式，只输出 JSON 对象本身，不要任何多余文字、"
    "不要 Markdown 代码围栏（不要 ```json）：\n"
    '示例：{"consistent": true, "issues": ""}'
)
# 贴合实际的示例：consistent:false + 长中文 issues（模型要输出的真实形态）
FEWSHOT_VALIDATE_REPRESENTATIVE = (
    "\n\n严格按下面的示例输出格式，只输出 JSON 对象本身，不要任何多余文字、"
    "不要 Markdown 代码围栏（不要 ```json）：\n"
    '示例：{"consistent": false, "issues": "简介声明该模块可用于声光提示、'
    '状态指示等赛题功能，但代码中未包含任何功能逻辑，仅定义了初始化函数，'
    '简介与实际代码不一致。"}'
)


def main() -> None:
    config = AppConfig(base_url=LOCAL_BASE_URL, api_key="local", model=LOCAL_MODEL)
    llm = DeepSeekLLM(config)
    rounds = 3

    def run_case(label: str, messages: list[dict], parse) -> tuple[list[str], int]:
        ok = 0
        results = []
        for i in range(rounds):
            t0 = time.time()
            try:
                content = llm._chat(messages, json_mode=True)
                parse(content)
                ok += 1
                results.append(f"  r{i+1}: OK {time.time()-t0:.1f}s  {content[:60]!r}")
            except Exception as exc:
                results.append(
                    f"  r{i+1}: FAIL {time.time()-t0:.1f}s  {type(exc).__name__}: {str(exc)[:60]}"
                )
        return results, ok

    clarify_user = _clarify_user_prompt(problem_text, [])
    validate_user = _validation_user_prompt(SAMPLE_LED_DESC, SAMPLE_LED_C)

    cases = [
        ("clarify 无示例", [
            {"role": "system", "content": CLARIFY_SYSTEM_PROMPT},
            {"role": "user", "content": clarify_user},
        ], parse_clarify_questions),
        ("clarify 带示例", [
            {"role": "system", "content": CLARIFY_SYSTEM_PROMPT},
            {"role": "user", "content": clarify_user + FEWSHOT_CLARIFY},
        ], parse_clarify_questions),
        ("validate 无示例", [
            {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": validate_user},
        ], parse_validation_result),
        ("validate 带示例", [
            {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": validate_user + FEWSHOT_VALIDATE},
        ], parse_validation_result),
        ("validate 带贴合示例", [
            {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": validate_user + FEWSHOT_VALIDATE_REPRESENTATIVE},
        ], parse_validation_result),
    ]

    for label, messages, parse in cases:
        results, ok = run_case(label, messages, parse)
        print(f"\n[{label}]  {ok}/{rounds} 通过")
        for r in results:
            print(r)


if __name__ == "__main__":
    main()
