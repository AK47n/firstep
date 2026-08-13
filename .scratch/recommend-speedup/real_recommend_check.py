"""真机验收驱动（工单 recommend-speedup/01）：主检出 8000 被并行会话服务占用，
本工单服务起在 8001——覆写 generate_check.BASE 后跑 check_topic（其余全同源：
推荐 → 骨架 → 生成 → 产物门禁 → UV4 全量重建；产物落本 worktree 的
.scratch/real-run/，gitignore 不碰主检出基线产物）。

用法：python real_recommend_check.py [2026C] [2021F]
依赖：本 worktree 服务在 127.0.0.1:8001 运行（python -m uvicorn
contest_generator.webapp:app --port 8001，PYTHONPATH=src）。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL_RUN = HERE.parent / "real-run"

spec = importlib.util.spec_from_file_location(
    "generate_check", REAL_RUN / "generate_check.py"
)
generate_check = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(generate_check)

generate_check.BASE = "http://127.0.0.1:8001"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    topics = sys.argv[1:] or ["2026C", "2021F"]
    ok = True
    for key in topics:
        raw = json.loads(
            (REAL_RUN / f"clarify_{key}.json").read_text(encoding="utf-8")
        )
        clarify_map = {str(k): str(v) for k, v in raw.items()}
        ok = generate_check.check_topic(key, clarify_map, (), "stm32") and ok
    print("\n===== 汇总 =====")
    print(f"{topics}: {'✓ 通过' if ok else '✗ 失败'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
