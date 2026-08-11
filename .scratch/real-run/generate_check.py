"""真机验证：赛题 推荐 → 骨架 → 生成 全流程一次跑完（stm32/Keil 与 mspm0/CCS 两线）。

用法：python generate_check.py [--platform stm32|mspm0] [--topic-file <题面.md>]
      [--reference-ids <id1,id2,...>] [topic...]
      topic 从题库读（默认 2026C 2021F）；--topic-file 从外部 md 读题面（如 2026H）；
      --reference-ids 参考注入真机验证（前端同款语义：锚定命中 ∪ 手动选）。
依赖：服务在 127.0.0.1:8000 运行（python -m contest_generator.webapp）。
输出目录：.scratch/real-run/out_<topic>_<platform>（不碰桌面原工程）。
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PLATFORM = "stm32"
TOPICS = Path.home() / ".contest_generator" / "topics"
HERE = Path(__file__).parent

# mspm0 豁免的头：ti_msp_dl_* 由 SysConfig 构建时生成进工程根（SDK 头同
# 前缀），产物树里本来就没有——与 Keil 语义的器件包头同地位。
# 标准库头 stm32 语义见 EXTERNAL_HEADERS，此处按前缀统一豁免 mspm0 器件层。
def is_external_header(header: str, platform: str) -> bool:
    if platform == "mspm0":
        return header.lower() in EXTERNAL_HEADERS or header.lower().startswith(
            "ti_msp_dl_"
        )
    return header.lower() in EXTERNAL_HEADERS

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


def check_artifacts(out_dir: Path, platform: str = PLATFORM) -> list[str]:
    """产物检查：返回问题列表（空 = 干净）。围栏 + include 解析两断言。"""
    problems: list[str] = []
    sources = [p for p in out_dir.rglob("*") if p.suffix.lower() in (".c", ".h")]
    if platform == "stm32":
        include_dirs = _uvprojx_include_dirs(out_dir)
    else:
        include_dirs = _cproject_include_dirs(out_dir)
    for src in sources:
        rel = src.relative_to(out_dir).as_posix()
        text = src.read_text(encoding="utf-8", errors="replace")
        in_block = False
        for i, line in enumerate(text.splitlines(), 1):
            if FENCE_RE.match(line):
                problems.append(f"{rel}:{i} 代码围栏残留: {line.strip()!r}")
            # 块注释内嵌套 /* → 提前闭合块注释，后续注释内容变裸代码
            # （2026H mspm0 真机实测：骨架 LLM 在注释里又写 /* */，10 错）
            if in_block and "/*" in line:
                problems.append(f"{rel}:{i} 块注释内嵌套 /*: {line.strip()!r}")
            j = 0
            while j < len(line):
                ch = line[j]
                if in_block:
                    if ch == "*" and j + 1 < len(line) and line[j + 1] == "/":
                        in_block = False
                        j += 2
                        continue
                elif ch == "/" and j + 1 < len(line) and line[j + 1] == "*":
                    in_block = True
                    j += 2
                    continue
                j += 1
        for m in _INCLUDE_RE.finditer(text):
            header = m.group(1)
            if _resolves(header, src.parent, include_dirs):
                continue
            if is_external_header(header, platform):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            problems.append(f"{rel}:{line_no} 引用不存在的头文件: {header}")
    return problems


def _resolves(header: str, own_dir: Path, include_dirs: list[Path]) -> bool:
    return any((d / header).is_file() for d in [own_dir, *include_dirs])


def _cproject_include_dirs(out_dir: Path) -> list[Path]:
    """解析最终 .cproject 的 IncludePath（CCS 语义，mspm0 线）→ 工程根相对目录。

    includePath option 的 listOptionValue value 含 ${PROJECT_LOC}（工程目录，
    .cproject 所在处）与 ${PROJECT_ROOT} 等宏；可展开的宏展开，不可展开的
    （${ConfigName} 等构建期值）跳过——静态检查只看模块路径可达。
    """
    cproject = next(out_dir.rglob(".cproject"), None)
    if cproject is None:
        return []
    dirs: list[Path] = []
    try:
        root = ET.parse(cproject).getroot()
    except ET.ParseError:
        return []
    for opt in root.iter("option"):
        if opt.get("valueType") != "includePath":
            continue
        for vo in opt.findall("listOptionValue"):
            val = (vo.get("value") or "").strip()
            if not val:
                continue
            p = Path(val.replace("${PROJECT_LOC}", str(cproject.parent))
                     .replace("${PROJECT_ROOT}", str(cproject.parent)))
            if "${" in str(p):
                continue
            try:
                dirs.append(p.resolve())
            except OSError:
                continue
    return dirs


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


def uv4_build(out_dir: Path) -> tuple[bool | None, str]:
    """真机编译：UV4 命令行构建最终 .uvprojx（工单 01 补洞——include 解析
    与自包含只是静态近似，符号级完整性只有真编译能证；pid.c 曾静态全绿但
    Keil 35 错）。返回 (是否通过, 摘要)；UV4 不可用返回 (None, 原因)。
    """
    uv4 = os.environ.get("KEIL_UV4") or r"C:\Keil5\Core\UV4\UV4.exe"
    if not Path(uv4).is_file():
        return None, f"未找到 UV4（{uv4}），跳过真机编译"
    uvprojx = next(out_dir.rglob("*.uvprojx"), None)
    if uvprojx is None:
        return False, "工程里没有 .uvprojx"
    log = out_dir.parent / "keil_build.log"
    proc = subprocess.run(
        [uv4, "-j0", "-b", str(uvprojx), "-o", str(log)],
        capture_output=True, text=True,
    )
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    m = re.search(r"(\d+) Error\(s\)", text)
    n_err = int(m.group(1)) if m else -1
    tail = text.strip().splitlines()[-1] if text.strip() else f"exit={proc.returncode} 无日志"
    return (n_err == 0, f"UV4 exit={proc.returncode} {tail}（{n_err} 错误）")


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
                # 事件词表单源 = contest_generator/events.py（EVENT_ROUND /
                # EVENT_CONVERGED / EVENT_DONE / EVENT_QUESTION / EVENT_ERROR，
                # 终端事件 = done / question / error），改词表须同步——前端
                # index.html 词表镜像同款注释；tests/test_generate_check_contract.py
                # 强制本分支词表与 events.py 一致（改词表忘改 CLI 即红）
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


# /api/recommend 请求契约（服务端校验唯一出处 = webapp.py:575-582，本函数是其
# CLI 侧对偶；前端 index.html:916 恒发全部五字段）。字段规则：problem_text 必填
# + platform 恒发（空 = 不过滤）+ topic_id 仅 topic 模式（topic_file = 无题号
# 手动准入）/ clarifications 非空才发 / reference_ids 非空才发（锚定命中 ∪
# 手动选，幻觉 / 重复 id 服务端 400 大声失败）。改契约字段须同步三处：webapp
# 校验 + 前端 + 本函数，tests/test_generate_check_contract.py 强制字段集一致。
def build_recommend_payload(
    problem_text: str,
    *,
    platform: str = PLATFORM,
    topic_id: str | None = None,
    clarify_hist: list[dict[str, str]] | tuple[dict[str, str], ...] = (),
    reference_ids: tuple[str, ...] = (),
) -> dict:
    payload: dict = {"problem_text": problem_text, "platform": platform}
    if topic_id:
        payload["topic_id"] = topic_id
    if clarify_hist:
        payload["clarifications"] = list(clarify_hist)
    if reference_ids:
        payload["reference_ids"] = list(reference_ids)
    return payload


def check_topic(
    key: str,
    clarify_map: dict[str, str] | None = None,
    drop: tuple[str, ...] = (),
    platform: str = PLATFORM,
    topic_file: Path | None = None,
    add: tuple[str, ...] = (),
    reference_ids: tuple[str, ...] = (),
) -> bool:
    ok = True
    print(f"\n===== {key} ({platform}) =====")
    topic_md = TOPICS / key / "topic.md"
    src = topic_file or topic_md
    problem_text = src.read_text(encoding="utf-8")
    print(f"[题面] {src} {len(problem_text)} 字符")

    # 1) 推荐（补问循环：question 终态 → 从 clarify_map 取答案 → 带澄清历史
    # 重发，最多 5 轮；答案不进题面，收敛判定的句子编号不受污染。
    # clarify_map 全量预置进历史：模型能看到已答问题，避免换措辞反复补问。
    # topic_file 模式 = no-topic 手动准入（题库无该编号），不带 topic_id）
    topic_id = None if topic_file else key
    clarify_hist: list[dict[str, str]] = [
        {"question": q, "answer": a} for q, a in (clarify_map or {}).items()
    ]
    rec: dict = {}
    for _round in range(5):
        # platform 随请求体透传（工单 ref-platform-filter）：推荐层按生成平台
        # 过滤模块候选——之前不带 platform，模型看全量库会推荐 stm32-only 模块
        # （如 2026H 的 filter/pid），生成门禁兜底 400 再手动 --drop。
        # reference_ids 随请求体透传（工单 03 契约对偶）：前端 selectedReferenceIds
        # 恒发、CLI 此前不发 → 真机验收永不覆盖参考注入路径；字段规则收敛在
        # build_recommend_payload（含 topic_id / clarifications 的既有条件语义）
        payload = build_recommend_payload(
            problem_text,
            platform=platform,
            topic_id=topic_id,
            clarify_hist=clarify_hist,
            reference_ids=reference_ids,
        )
        rec = recommend_stream(payload)
        print(f"[推荐] {rec['rounds']} 轮 → 终态 {rec['event']}")
        if rec["event"] != "question":
            break
        questions = list((rec.get("data") or {}).get("questions", []))
        missing = [q for q in questions if (clarify_map or {}).get(q) is None]
        if missing:
            print(f"  ✗ 补问无答案可答: {missing}")
            print(f"    （已答 {len(clarify_hist)} 条，补充 clarify 映射后重跑）")
            return False
        for q in questions:
            clarify_hist.append({"question": q, "answer": clarify_map[q]})
            print(f"  ↻ 补问第{len(clarify_hist)}条已回答: {q[:64]}…")
    if rec["event"] != "done":
        print(f"  ✗ 未收敛: {json.dumps(rec.get('data'), ensure_ascii=False)[:300]}")
        return False
    data = rec["data"]
    slugs = [m["slug"] for m in data.get("modules", [])]
    dropped = [s for s in slugs if s in drop]
    if dropped:
        slugs = [s for s in slugs if s not in drop]
        print(f"  → 按 --drop 去掉 {dropped}（无 {PLATFORM} 平台条目，前端同款手动增删语义）")
    if add:
        slugs += [s for s in add if s not in slugs]
        print(f"  → 按 --add 补选 {add}（include 门禁要求的依赖模块，前端同款手动增删语义）")
    print(f"  模块({len(slugs)}): {', '.join(slugs)}")
    for m in data.get("modules", []):
        print(f"    - {m['slug']}: {m['reason'][:80]}")
    if data.get("topic_id"):
        print(f"  识别 topic_id={data['topic_id']} related={data.get('related_modules')}")
    if data.get("requirements"):
        print(f"  功能需求层 {len(data['requirements'])} 条")
    refs = data.get("references")
    if refs:
        print(f"  参考资料 {len(refs)} 条（done 透明闭环）")
        for ref in refs:
            print(
                f"    - {ref['id']}: {ref['title'][:60]} "
                f"[{ref.get('source', '?')}/{ref.get('platform', '?')}]"
            )
    if not slugs:
        print("  ✗ done 但模块为空")
        return False
    for s in slugs:
        if not (Path.home() / ".contest_generator" / "modules" / s).is_dir():
            print(f"  ✗ 未知模块 slug: {s}")
            ok = False

    # 2) 骨架
    skel_payload: dict = {
        "problem_text": problem_text, "platform": platform, "slugs": slugs,
    }
    if topic_id:
        skel_payload["topic_id"] = topic_id
    skel = post("/api/skeleton", skel_payload)
    main_c = skel.get("main_c", "")
    print(f"[骨架] main.c {len(main_c)} 字符, 拦截幻觉调用 {len(skel.get('intercepted', []))} 处")
    if not main_c or "int main" not in main_c:
        print("  ✗ main.c 缺失或没有 main 函数")
        ok = False

    # 3) 生成
    out_dir = HERE / f"out_{key}_{platform}"
    gen_payload: dict = {
        "platform": platform, "slugs": slugs, "main_c": main_c,
        "output_dir": str(out_dir),
    }
    if topic_id:
        gen_payload["topic_id"] = topic_id
    gen = post("/api/generate", gen_payload)
    print(f"[生成] 输出 {out_dir}")
    files = [f.relative_to(out_dir).as_posix() for f in out_dir.rglob("*") if f.is_file()]
    print(f"  文件数 {len(files)}")
    for f in files:
        print(f"    - {f}")
    need = {"main.c", "user/Project.uvprojx"} if platform == "stm32" else {"main.c", "mspm0.syscfg"}
    missing = need - set(files)
    if missing:
        print(f"  ✗ 缺关键文件: {missing}")
        ok = False

    # 产物级断言：围栏 + include 解析（真机编译失败的对应检查）
    problems = check_artifacts(out_dir, platform)
    if problems:
        for p in problems:
            print(f"  ✗ 产物: {p}")
        ok = False
    else:
        print("  [产物] 无围栏残留、全部 include 可解析")

    # 真机编译：UV4 命令行构建（符号级完整性的唯一证明，仅 stm32/Keil 线；
    # mspm0/CCS 线 Theia 无命令行构建，最终证明走用户 GUI 编译）
    if platform == "stm32":
        passed, summary = uv4_build(out_dir)
        if passed is None:
            print(f"  [真机] {summary}")
        elif passed:
            print(f"  [真机] ✓ {summary}")
        else:
            print(f"  [真机] ✗ {summary}")
            ok = False
    else:
        print("  [真机] mspm0/CCS 线：Theia 无命令行构建，最终证明待用户 GUI 编译")
    return ok


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = sys.argv[1:]
    global PLATFORM
    platform = PLATFORM
    if "--platform" in args:
        idx = args.index("--platform")
        platform = args[idx + 1]
        PLATFORM = platform
        del args[idx:idx + 2]
    topic_file: Path | None = None
    if "--topic-file" in args:
        idx = args.index("--topic-file")
        topic_file = Path(args[idx + 1])
        del args[idx:idx + 2]
    clarify_map: dict[str, str] = {}
    if "--clarify" in args:
        idx = args.index("--clarify")
        raw = json.loads(Path(args[idx + 1]).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            clarify_map = {str(k): str(v) for k, v in raw.items()}
        elif isinstance(raw, list):
            clarify_map = {str(d["question"]): str(d["answer"]) for d in raw}
        del args[idx:idx + 2]
    drop: tuple[str, ...] = ()
    if "--drop" in args:
        idx = args.index("--drop")
        drop = tuple(s.strip() for s in args[idx + 1].split(",") if s.strip())
        del args[idx:idx + 2]
    add: tuple[str, ...] = ()
    if "--add" in args:
        idx = args.index("--add")
        add = tuple(s.strip() for s in args[idx + 1].split(",") if s.strip())
        del args[idx:idx + 2]
    reference_ids: tuple[str, ...] = ()
    if "--reference-ids" in args:
        idx = args.index("--reference-ids")
        reference_ids = tuple(
            s.strip() for s in args[idx + 1].split(",") if s.strip()
        )
        del args[idx:idx + 2]
    topics = args or ["2026C", "2021F"]
    results = {
        t: check_topic(t, clarify_map, drop, platform, topic_file, add, reference_ids)
        for t in topics
    }
    print("\n===== 汇总 =====")
    for t, ok in results.items():
        print(f"{t}: {'✓ 通过' if ok else '✗ 失败'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
