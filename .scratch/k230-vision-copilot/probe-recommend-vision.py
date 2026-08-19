"""探查：视觉题面推荐链路是否命中库内 k230（而非库外建议）。

真库 + 真 DeepSeek 单轮收敛循环，两个视觉题面：
  1. 找球小车（色块追踪/球检测 → 期望 k230 + ball_detect）
  2. 识别数字（数字识别 → 期望不推荐 k230，可库外建议视觉模块）

用法：python .scratch/k230-vision-copilot/probe-recommend-vision.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.config import load_config  # noqa: E402
from contest_generator.llm import DeepSeekLLM  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.selection import select_modules_convergent  # noqa: E402

PROBLEMS = {
    "找球小车": (
        "设计并制作一辆智能寻球小车。比赛场地随机放置一个红色小球，"
        "小车从出发区启动后自主行驶寻找小球，通过摄像头识别小球位置，"
        "行驶到小球旁停止，并点亮指示灯提示寻球完成。"
    ),
    "识别数字": (
        "设计并制作一个智能送药小车。小车经过病房门口时，需通过摄像头"
        "识别房间号数字，按识别出的数字行驶到对应房间，到达后蜂鸣提示。"
    ),
}


def main() -> None:
    config = load_config()
    llm = DeepSeekLLM(config)
    summaries = build_manifest_summaries(list_modules(Path(config.module_library_dir)))
    for name, text in PROBLEMS.items():
        print(f"\n===== {name} =====")
        print(text)
        sel = select_modules_convergent(llm, text, summaries)
        print(f"顶层 modules: {list(sel.modules)}")
        for req in sel.requirements:
            print(
                f"  句子{req.sentence_index} {req.requirement}"
                f"  -> modules={list(req.modules)}"
                f"  suggestions={[s.name for s in req.suggestions]}"
            )
        if sel.questions:
            print(f"  questions: {list(sel.questions)}")


if __name__ == "__main__":
    main()
