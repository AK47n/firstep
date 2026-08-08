"""真机验证：2026C + 2021F 推荐 → 骨架 → 生成全流程一次跑完。

用法：python generate_check.py [topic...]（默认 2026C 2021F）
依赖：服务在 127.0.0.1:8000 运行（python -m contest_generator.webapp）。
输出目录：.scratch/real-run/out_<topic>（不碰桌面原工程）。
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PLATFORM = "stm32"
TOPICS = Path.home() / ".contest_generator" / "topics"
HERE = Path(__file__).parent

# 编译产物级校验（Keil 语义）：真机编译失败的对应断言。
# 1) 代码围栏：LLM 输出带 ```c 围栏直接落盘 → Keil 报 unrecognized token。
# 2) include 解析：#include "x.h" 先找当前文件目录，再找 uvprojx IncludePath；
#    工程树里找不到且不是标准库/器件包头 → Keil 报 cannot open source input file。
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})[a-zA-Z0-9_-]*\s*$")
# Keil 在工程外也能解析的头：ARMCC 标准库（引号形式）与器件包（stm32f10x_conf.h）
EXTERNAL_HEADERS = frozenset(
    {
        "math.h", "stdio.h", "stdlib.h", "string.h", "stdint.h", "stdbool.h",
        "stddef.h", "limits.h", "float.h", "assert.h", "errno.h", "ctype.h",
        "time.h", "inttypes.h", "stdarg.h", "setjmp.h", "signal.h", "locale.h",
        "wchar.h", "wctype.h", "complex.h", "fenv.h", "tgmath.h", "iso646.h",
        "stdatomic.h", "threads.h", "uchar.h", "stm32f10x_conf.h",
    }
)
_INCLUDE_RE = re.compile(r'#\s*include\s*"([^"]+)"')


def check_artifacts(out_dir: Path) -> list[str]:
    """产物检查：返回问题列表（空 = 干净）。围栏 + include 解析两断言。"""
    problems: list[str] = []
    sources = [p for p in out_dir.rglob("*") if p.suffix.lower() in (".c", ".h")]
    include_dirs = _uvprojx_include_dirs(out_dir)
    for src in sources:
        rel = src.relative_to(out_dir).as_posix()
        text = src.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if FENCE_RE.match(line):
                problems.append(f"{rel}:{i} 代码围栏残留: {line.strip()!r}")
        for m in _INCLUDE_RE.finditer(text):
            header = m.group(1)
            if _resolves(header, src.parent, include_dirs):
                continue
            if header.lower() in EXTERNAL_HEADERS:
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            problems.append(f"{rel}:{line_no} 引用不存在的头文件: {header}")
    return problems


def _resolves(header: str, own_dir: Path, include_dirs: list[Path]) -> bool:
    return any((d / header).is_file() for d in [own_dir, *include_dirs])


def _uvprojx_include_dirs(out_dir: Path) -> list[Path]:
    """解析最终 .uvprojx 的 IncludePath（相对 .uvprojx 所在目录）→ 工程根相对目录。"""
    uvprojx = next(out_dir.rglob("*.uvprojx"), None)
    if uvprojx is None:
        return []
    dirs: list[Path] = []
    try:
        root = ET.parse(uvprojx).getroot()
    except ET.ParseError:
        return []
    for el in root.findall("Targets/Target"):
        path_el = el.find(
            "TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
        )
        if path_el is None or not path_el.text:
            continue
        for entry in path_el.text.split(";"):
            p = Path(entry.strip().replace("\\", "/"))
            if not entry.strip():
                continue
            resolved = p if p.is_absolute() else (uvprojx.parent / p)
            try:
                dirs.append(resolved.resolve())
            except OSError:
                continue
    return dirs


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}: {body[:400]}") from e


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

    # 产物级断言：围栏 + include 解析（真机编译失败的对应检查）
    problems = check_artifacts(out_dir)
    if problems:
        for p in problems:
            print(f"  ✗ 产物: {p}")
        ok = False
    else:
        print("  [产物] 无围栏残留、全部 include 可解析")
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
