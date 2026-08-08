"""真机验证：2026C + 2021F 推荐 → 骨架 → 生成全流程一次跑完。

用法：python generate_check.py [topic...]（默认 2026C 2021F）
依赖：服务在 127.0.0.1:8000 运行（python -m contest_generator.webapp）。
输出目录：.scratch/real-run/out_<topic>（不碰桌面原工程）。
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PLATFORM = "stm32"
TOPICS = Path.home() / ".contest_generator" / "topics"
HERE = Path(__file__).parent


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def recommend_stream(payload: dict) -> dict:
    """消费 SSE：round → converged → done/question/error，返回终态事件。"""
    req = urllib.request.Request(
        BASE + "/api/recommend",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    rounds = 0
    result = None
    with urllib.request.urlopen(req, timeout=600) as r:
        buf = ""
        while True:
            chunk = r.read(4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buf:
                frame, buf = buf.split("\n\n", 1)
                event = data = None
                for line in frame.splitlines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                if event == "round":
                    rounds += 1
                elif event == "converged":
                    pass
                elif event in ("done", "question", "error"):
                    result = {"event": event, "data": json.loads(data) if data else None}
    if result is None:
        result = {"event": "error", "data": {"message": "流未以终态事件收尾"}}
    result["rounds"] = rounds
    return result


def check_topic(key: str) -> bool:
    ok = True
    print(f"\n===== {key} =====")
    topic_md = TOPICS / key / "topic.md"
    problem_text = topic_md.read_text(encoding="utf-8")
    print(f"[题面] {key}/topic.md {len(problem_text)} 字符")

    # 1) 推荐
    rec = recommend_stream({"problem_text": problem_text, "topic_id": key})
    print(f"[推荐] {rec['rounds']} 轮 → 终态 {rec['event']}")
    if rec["event"] != "done":
        print(f"  ✗ 未收敛: {json.dumps(rec['data'], ensure_ascii=False)[:300]}")
        return False
    data = rec["data"]
    slugs = [m["slug"] for m in data.get("modules", [])]
    print(f"  模块({len(slugs)}): {', '.join(slugs)}")
    for m in data.get("modules", []):
        print(f"    - {m['slug']}: {m['reason'][:80]}")
    if data.get("topic_id"):
        print(f"  识别 topic_id={data['topic_id']} related={data.get('related_modules')}")
    if data.get("requirements"):
        print(f"  功能需求层 {len(data['requirements'])} 条")
    if not slugs:
        print("  ✗ done 但模块为空")
        return False
    for s in slugs:
        if not (Path.home() / ".contest_generator" / "modules" / s).is_dir():
            print(f"  ✗ 未知模块 slug: {s}")
            ok = False

    # 2) 骨架
    skel = post("/api/skeleton", {
        "problem_text": problem_text, "platform": PLATFORM,
        "slugs": slugs, "topic_id": key,
    })
    main_c = skel.get("main_c", "")
    print(f"[骨架] main.c {len(main_c)} 字符, 拦截幻觉调用 {len(skel.get('intercepted', []))} 处")
    if not main_c or "int main" not in main_c:
        print("  ✗ main.c 缺失或没有 main 函数")
        ok = False

    # 3) 生成
    out_dir = HERE / f"out_{key}"
    gen = post("/api/generate", {
        "platform": PLATFORM, "slugs": slugs, "main_c": main_c,
        "output_dir": str(out_dir), "topic_id": key,
    })
    print(f"[生成] 输出 {out_dir}")
    files = [f.relative_to(out_dir).as_posix() for f in out_dir.rglob("*") if f.is_file()]
    print(f"  文件数 {len(files)}")
    for f in files:
        print(f"    - {f}")
    need = {"main.c", "user/Project.uvprojx"}
    missing = need - set(files)
    if missing:
        print(f"  ✗ 缺关键文件: {missing}")
        ok = False
    return ok


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    topics = sys.argv[1:] or ["2026C", "2021F"]
    results = {t: check_topic(t) for t in topics}
    print("\n===== 汇总 =====")
    for t, ok in results.items():
        print(f"{t}: {'✓ 通过' if ok else '✗ 失败'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
