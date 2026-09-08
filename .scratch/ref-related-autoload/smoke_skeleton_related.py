"""工单 03 真实库冒烟：骨架侧 related_limit=4 全链路（resolve_topic_context →
build_reference_fulltexts / build_reference_sources），零 webapp。

出处：.scratch/ref-related-autoload/smoke_skeleton_related.py
运行：python .scratch/ref-related-autoload/smoke_skeleton_related.py
"""
from __future__ import annotations

from pathlib import Path

from contest_generator.config import reference_library_dir, topic_library_dir
from contest_generator.generator import (
    build_reference_fulltexts,
    build_reference_sources,
    resolve_topic_context,
)

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"
TOPICS = topic_library_dir(MODULES)
REFERENCES = reference_library_dir(MODULES)

CASES = (
    ("2026H", "mspm0", ("adc", "uart", "oled")),        # 滚球巡线——外设密集
    ("2021F", "stm32", ("xunji", "key", "oled")),       # 循迹送药
    ("2024H", "mspm0", ("adc", "pwm_motor", "xunji")),  # 滚球
    ("2026C", "stm32", ("uart", "key", "oled")),        # 数字钥匙
    ("", "mspm0", ()),                                  # no-topic 粘贴题面
)

NO_TOPIC_TEXT = "串口通信与 ADC 采样，定时器中断采集电压，OLED 显示"


def main() -> None:
    for topic_key, platform, slugs in CASES:
        problem_text = NO_TOPIC_TEXT if not topic_key else "粘贴片段不参与（显式路径）"
        try:
            ctx = resolve_topic_context(
                llm=None,
                topic_key=topic_key,
                problem_text=problem_text,
                module_library_dir=MODULES,
                topic_library_dir=TOPICS,
                reference_library_dir=REFERENCES,
                reference_ids=(),
                platform=platform,
                slugs=slugs,
                related_limit=4,
            )
        except Exception as exc:  # noqa: BLE001 —— 冒烟只报告
            print(f"[{topic_key or 'no-topic'}/{platform}] resolve 失败: {exc}")
            continue
        fulltexts = build_reference_fulltexts(ctx)
        sources = build_reference_sources(ctx)
        related = {
            rid: src
            for rid, src in (sources or {}).items()
            if src == "related"
        }
        print(
            f"[{topic_key or 'no-topic'}/{platform}] 锚定+相关 references={len(ctx.references)}"
            f" 清单={len(ctx.suggestions)} 注入全文={len(fulltexts) if fulltexts else 0}"
            f" related={sorted(related)}"
        )
        for rid, src in related.items():
            text = (fulltexts or {}).get(rid, "")
            print(f"    {rid} ({src}, {len(text)}B, 头 40: {text[:40]!r})")


if __name__ == "__main__":
    main()
