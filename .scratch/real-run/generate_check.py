"""真机验证：赛题 推荐 → 骨架 → 生成 全流程一次跑完（stm32/Keil 与 mspm0/CCS 两线）；
编译失败自动进入修复循环（报错 → /api/fix-errors → 重编译验证 ≤3 轮，与 web
修复中心同语义，工单 gen-check-fix-loop/01）。

用法：python generate_check.py [--platform stm32|mspm0] [--topic-file <题面.md>]
      [--reference-ids <id1,id2,...>] [--reuse-recommend] [topic...]
      topic 从题库读（默认 2026C 2021F）；--topic-file 从外部 md 读题面（如 2026H）；
      --reference-ids 参考注入真机验证（前端同款语义：锚定命中 ∪ 手动选）；
      --reuse-recommend 复用推荐缓存（done 载荷跨运行落盘 .scratch/real-run/
      cache/，回归跑修复循环/编译链路时推荐段秒过；缓存缺失报错退出，不静默
      回退真实调用）。
依赖：服务在 127.0.0.1:8000 运行（python -m contest_generator.webapp）。
输出目录：.scratch/real-run/out_<topic>_<platform>（不碰桌面原工程）。
"""
import hashlib
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PLATFORM = "stm32"
TOPICS = Path.home() / ".contest_generator" / "topics"
HERE = Path(__file__).parent
# 推荐缓存目录（工单 check-recommend-cache/01 决策 3；环境变量
# GENERATE_CHECK_CACHE_DIR 可在 recommend_cache_path 处覆盖）
CACHE_DIR = HERE / "cache"

# 修复循环轮数上限，与前端一致（index.html FIX_MAX_ROUNDS = 3，改动须两处
# 同步——tests/test_generate_check_contract.py 钉两处文本一致，改前端忘改
# CLI 即红）。停滞检测（0 applied 即停）属前端循环工单 fix-loop-progress/01，
# 本脚本循环独立实现最小语义：3 轮内 passed 即出活，0 applied 也走完。
FIX_MAX_ROUNDS = 3

# 产物检查与生成门禁同源（工单 generate-check-parity/01）：门禁镜像段
# （FENCE_RE / include 解析 / EXTERNAL_HEADERS 豁免集，曾逐字重实现门禁——
# 门禁一改脚本静默漂移，验收给假信心）已删，改为对产物树重建语料跑生产
# 同一个 run_generation_gates；豁免集（C 标准库 + 平台工具链头，含 mspm0
# ti_msp_dl_* 前缀）门禁内部持有，删镜像即天然同源。
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from contest_generator.compile_runner import (
    CompileRunnerError,
    collect_build_log,
    compile_passed,
    find_make,
    find_uv4,
)
from contest_generator.fix_errors import parse_compile_errors, summarize_compile_output
from contest_generator.generator import (
    GeneratorError,
    build_output_tree_corpus,
    run_generation_gates,
)


def check_artifacts(out_dir: Path, platform: str = PLATFORM) -> list[str]:
    """产物检查：返回问题列表（空 = 干净）。对产物树重建语料跑真门禁。

    manifests 传空：file_path_conflicts 查 manifest 声明（产物树无声明可查，
    跨模块同名由库内不变量 + 生成前门禁管），空表直过；其余五道吃语料的
    门照常跑。搜索目录 = 补丁后 .uvprojx/.cproject 的 IncludePath（补丁器
    验证段，patch 没把模块目录写进 IncludePath → include 解析门在此失败）。
    """
    if platform == "stm32":
        search_dirs = _uvprojx_include_dirs(out_dir)
    else:
        search_dirs = _cproject_include_dirs(out_dir)
    corpus = build_output_tree_corpus(out_dir, platform, search_dirs)
    try:
        run_generation_gates(corpus, [], platform)
    except GeneratorError as e:
        return [str(e)]
    return []


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


def uv4_build(out_dir: Path) -> tuple[bool | None, str, str]:
    """真机编译：UV4 全量重建（工单 compile-verdict-align/01 换闸，与生产
    collect_build_log 同源——曾自带 `-j0 -b` 增量命令 + `(\\d+) Error\\(s\\)`
    正则，增量日志无编译行 = 假绿风险（autocompile-loop 决策记录 4），且
    判读域已单源在 compile_runner / fix_errors，禁止调用方另写正则）。
    返回 (是否通过, 摘要, 编译输出原文)——原文供修复循环回喂 /api/fix-errors
    （与 web /api/compile done 的 error_text 同款"原样采集"契约，工单
    gen-check-fix-loop/01）；UV4 不可用返回 (None, 原因, "")。
    """
    uv4 = find_uv4(os.environ.get("KEIL_UV4") or "")
    if uv4 is None:
        return None, "未找到 UV4，跳过真机编译", ""
    try:
        build = collect_build_log("stm32", out_dir, uv4=uv4)
    except CompileRunnerError as exc:
        return False, str(exc), ""
    summary = summarize_compile_output(
        build.run.output, parse_compile_errors(build.run.output)
    )
    tail = build.run.output.strip().splitlines()[-1] \
        if build.run.output.strip() else f"exit={build.run.exit_code} 无日志"
    passed = compile_passed(build.platform, build.run.exit_code)
    return passed, f"UV4 exit={build.run.exit_code} {tail}（{summary['errors']} 错误）", \
        build.run.output


def gmake_build(out_dir: Path) -> tuple[bool | None, str, str]:
    """真机编译：gmake 全量重建（mspm0/CCS 线，工单 mspm0-build-makefiles/01——
    Debug/makefile 集由生成器自动产出，CCS 命令行构建不再依赖 scratch 后处理，
    与 uv4_build 同源走生产 collect_build_log）。返回 (是否通过, 摘要, 编译
    输出原文)——原文供修复循环回喂（与 uv4_build 同款契约）；gmake 不可用返回
    (None, 原因, "")。摘要带首编耗时（真机计时观察，决策记录 7）。"""
    make = find_make(os.environ.get("GMAKE") or "")
    if make is None:
        return None, "未找到 gmake，跳过真机编译", ""
    try:
        build = collect_build_log("mspm0", out_dir, make=make)
    except CompileRunnerError as exc:
        return False, str(exc), ""
    summary = summarize_compile_output(
        build.run.output, parse_compile_errors(build.run.output)
    )
    tail = build.run.output.strip().splitlines()[-1] \
        if build.run.output.strip() else f"exit={build.run.exit_code} 无日志"
    passed = compile_passed(build.platform, build.run.exit_code)
    return passed, (
        f"gmake exit={build.run.exit_code} {tail}"
        f"（{summary['errors']} 错误，{build.run.duration:.1f}s）"
    ), build.run.output


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
    # 读超时 1800s（曾 600s）：提速棱镜 A"一轮问全"后单轮 LLM 响应分钟级，
    # 2026-08-14 真机实测首轮静默窗口超 600s → 流被 TimeoutError 误杀（整次
    # 推荐白跑）。SSE 轮间无事件 = LLM 在算，不是挂起；杀流比等更贵。
    with urllib.request.urlopen(req, timeout=1800) as r:
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


# ---------- 推荐缓存（工单 check-recommend-cache/01） ----------
#
# 推荐段是回归大头（单题 ~10-15 min 真实 LLM 调用）；done 载荷跨运行落盘，
# --reuse-recommend 命中直进骨架。缓存 json = done 载荷逐字 + 元数据
# （topic_key / platform / problem_sha256）——下游消费变量对齐 recommend_stream
# 返回的 done，不发明新形状。缺失 / 失效报错退出，不静默回退真实调用
# （回归确定性优先，防止"以为复用了其实又烧了 15 min"）。骨架不缓存
# （修复循环需要真实 main_c，1-2 min 保留）。


def problem_fingerprint(problem_text: str) -> str:
    """题面 sha256 指纹（无 topic_id 时兼作缓存键；复用时校验题面未变）。"""
    return hashlib.sha256(problem_text.encode("utf-8")).hexdigest()


def cache_key(topic_id: str | None, problem_text: str) -> str:
    """缓存键：topic_id 优先（topic 模式）；无 topic_id（topic_file 手动准入）
    用题面 sha256（决策 2——题面变 → 键变自然失效）。"""
    return topic_id or problem_fingerprint(problem_text)


def recommend_cache_path(key: str, cache_dir: Path | None = None) -> Path:
    """缓存键 → 缓存文件路径 recommend_<key>.json（决策 3）。

    目录覆盖顺序：显式参数 > 环境变量 GENERATE_CHECK_CACHE_DIR > 缺省
    .scratch/real-run/cache/（测试经 cache_dir=tmp_path 注入）。
    """
    base = cache_dir or Path(
        os.environ.get("GENERATE_CHECK_CACHE_DIR") or CACHE_DIR
    )
    return base / f"recommend_{key}.json"


def cache_recommend(
    path: Path,
    done: dict,
    *,
    topic_key: str,
    problem_text: str,
    platform: str,
) -> None:
    """写缓存：done 载荷逐字 + 元数据。done = recommend_stream 终态 data
    （modules/requirements/references/topic_id），下游 selectedSlugs / expand
    / generate 零改动语义（决策 1）。platform 元数据防跨平台复用（推荐层按
    平台过滤模块，stm32 推荐结果喂 mspm0 生成会假绿）。"""
    payload = {
        "topic_key": topic_key,
        "platform": platform,
        "problem_sha256": problem_fingerprint(problem_text),
        "done": done,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_recommend(path: Path) -> dict:
    """读缓存：json 读回 + 形状校验（自写自读，校验是复用安全网——坏 json /
    缺字段 → ValueError，调用方报错退出而非带假数据进下游）。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"缓存不可读: {path}（{exc}）") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"缓存形状错误: {path}（顶层非对象）")
    for field in ("topic_key", "platform", "problem_sha256"):
        if not isinstance(raw.get(field), str) or not raw[field]:
            raise ValueError(f"缓存形状错误: {path}（缺 {field}）")
    done = raw.get("done")
    if not isinstance(done, dict) or not isinstance(done.get("modules"), list):
        raise ValueError(f"缓存形状错误: {path}（done 非对象或缺 modules 列表）")
    return raw


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


def fix_stream(payload: dict) -> dict:
    """消费 SSE：parse_done → fix_start → apply_result… → done/error，返回
    终态事件（recommend_stream 同款写法；fix 流分钟级真实 DeepSeek，读超时
    1800s——2026-08-14 真机教训）。HTTP 4xx（如输出目录不存在）如实转 error
    终态，不打断真机验收主流程。

    事件词表单源 = contest_generator/events.py（EVENT_PARSE_DONE /
    EVENT_FIX_START / EVENT_APPLY_RESULT / EVENT_DONE / EVENT_ERROR，终端
    事件 = done / error），改词表须同步——tests/test_generate_check_contract.py
    强制本分支词表与 events.py 一致（recommend 词表同款机制）。
    """
    req = urllib.request.Request(
        BASE + "/api/fix-errors",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    result = None
    try:
        # 读超时 1800s（曾 600s）：与 recommend_stream 同款教训（2026-08-14
        # 真机实测首轮静默窗口超 600s）——修复调用单次分钟级，静默窗口超
        # 600s 即误杀循环
        with urllib.request.urlopen(req, timeout=1800) as r:
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
                    # 事件词表单源 = contest_generator/events.py（修复段，
                    # 注释同 recommend_stream），改词表须同步 CLI 分支
                    if event == "parse_done":
                        pass
                    elif event == "fix_start":
                        pass
                    elif event == "apply_result":
                        pass  # 逐处结果以 done 载荷 fixes 为准（单源）
                    elif event in ("done", "error"):
                        result = {"event": event, "data": json.loads(data) if data else None}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        result = {"event": "error", "data": {"message": f"HTTP {e.code}: {body[:300]}"}}
    except OSError as e:
        # 流中途断线（服务重启 / 连接被重置，2026-08-13 真机观察）：如实转
        # error 终态而非打断验收主流程（recommend_stream 无此兜底，本函数
        # 循环 3 轮更不该一轮断线就抛栈）
        result = {"event": "error", "data": {"message": f"流连接中断: {e}"}}
    if result is None:
        result = {"event": "error", "data": {"message": "流未以终态事件收尾"}}
    return result


# /api/fix-errors 请求契约（服务端校验唯一出处 = webapp.py:713 fix_errors 路由
# docstring，本函数是其 CLI 侧对偶；前端 index.html:1712 恒发全部六字段）。
# 字段规则：error_text（必填，编译报错全文）+ output_dir（必填，生成结果
# 目录）+ problem_text / platform / slugs / main_c（可选上下文，check_topic
# 内已有全部变量，恒发；缺省不放）。不带 previous_fixes（fix-loop-progress/01
# 的请求体字段，服务端可选向后兼容，本工单循环不依赖停滞回喂）。改契约
# 字段须同步三处：webapp 校验 + 前端 + 本函数，
# tests/test_generate_check_contract.py 强制字段集一致。
def build_fix_payload(
    output_dir: Path | str,
    error_text: str,
    *,
    problem_text: str = "",
    platform: str = "",
    slugs: list[str] | tuple[str, ...] = (),
    main_c: str = "",
) -> dict:
    payload: dict = {"output_dir": str(output_dir), "error_text": error_text}
    if problem_text:
        payload["problem_text"] = problem_text
    if platform:
        payload["platform"] = platform
    if slugs:
        payload["slugs"] = list(slugs)
    if main_c:
        payload["main_c"] = main_c
    return payload


def run_fix_loop(
    out_dir: Path,
    error_text: str,
    problem_text: str,
    platform: str,
    slugs: list[str],
    main_c: str,
) -> bool:
    """修复循环（web 修复中心 CLI 对偶，工单 gen-check-fix-loop/01）：编译
    报错 → /api/fix-errors → 重编译验证，≤ FIX_MAX_ROUNDS 轮——与 index.html
    startFixCenter 同语义（首编失败由 check_topic 转入，第 3 轮后如实报告
    剩余错误数）。停滞检测本工单不做：0 applied 也走完 3 轮（前端循环工单
    fix-loop-progress/01，如先合可顺手同步 applied==0 即停，一行之差）。
    返回是否通过。
    """
    build_fn = uv4_build if platform == "stm32" else gmake_build
    for round_no in range(1, FIX_MAX_ROUNDS + 1):
        # 轮次文案错误数：判读单源 summarize_compile_output（工单
        # compile-verdict-align/01 约定，不另写正则）
        summary = summarize_compile_output(
            error_text, parse_compile_errors(error_text)
        )
        print(
            f"  第 {round_no}/{FIX_MAX_ROUNDS} 轮：{summary['errors']} 条 Error"
            f" → AI 修复…"
        )
        fix = fix_stream(
            build_fix_payload(
                out_dir,
                error_text,
                problem_text=problem_text,
                platform=platform,
                slugs=slugs,
                main_c=main_c,
            )
        )
        if fix["event"] == "error":
            msg = (fix.get("data") or {}).get("message", "无错误信息")
            print(f"  ✗ 修复失败: {msg[:300]}")
            return False
        done = fix.get("data") or {}
        fixes = list(done.get("fixes", []))
        applied = [f for f in fixes if f.get("status") == "applied"]
        skipped = [f for f in fixes if f.get("status") != "applied"]
        print(f"  应用 {len(applied)} 处 / 跳过 {len(skipped)} 处")
        # 逐条打印（file:line status reason，与 web 结果列表同信息量）
        for f in fixes:
            mark = "✓" if f.get("status") == "applied" else "·"
            print(
                f"    {mark} {f.get('file')}:{f.get('line')} "
                f"[{f.get('status')}] {f.get('reason', '')}"
            )
        if done.get("degraded"):
            print("  [提示] 未定位到可修复文件（降级），修复未落盘")
        if done.get("backup_id"):
            print(f"  [备份] {done['backup_id']}（回滚: POST /api/fix-errors/rollback）")
        # 重编译验证：passed 出活；仍错下一轮喂最新报错（原样采集原文）
        passed, build_summary, next_errors = build_fn(out_dir)
        if passed:
            print(f"  第 {round_no} 轮重编译 ✓ {build_summary}")
            return True
        print(f"  第 {round_no} 轮重编译 ✗ {build_summary}")
        if passed is None:
            return False  # 工具链缺失，如实收工不空转
        error_text = next_errors
    # 3 轮后如实报告剩余错误数（summary 单源，不另写正则）
    summary = summarize_compile_output(error_text, parse_compile_errors(error_text))
    print(
        f"  ✗ 已达 {FIX_MAX_ROUNDS} 轮上限，剩余 {summary['errors']} 条 Error"
        f"（见最后编译输出）"
    )
    return False


def check_topic(
    key: str,
    clarify_map: dict[str, str] | None = None,
    drop: tuple[str, ...] = (),
    platform: str = PLATFORM,
    topic_file: Path | None = None,
    add: tuple[str, ...] = (),
    reference_ids: tuple[str, ...] = (),
    reuse_recommend: bool = False,
) -> bool:
    ok = True
    print(f"\n===== {key} ({platform}) =====")
    topic_md = TOPICS / key / "topic.md"
    src = topic_file or topic_md
    problem_text = src.read_text(encoding="utf-8")
    print(f"[题面] {src} {len(problem_text)} 字符")

    # 1) 推荐（topic_file 模式 = no-topic 手动准入（题库无该编号），不带
    # topic_id）。--reuse-recommend（工单 check-recommend-cache/01）命中缓存
    # 直进下游，缺失 / 失效报错退出；否则真实推荐（补问循环：question 终态
    # → 从 clarify_map 取答案 → 带澄清历史重发，最多 5 轮；答案不进题面，
    # 收敛判定的句子编号不受污染。clarify_map 全量预置进历史：模型能看到
    # 已答问题，避免换措辞反复补问）并写缓存（写失败不阻断主流程）
    topic_id = None if topic_file else key
    clarify_hist: list[dict[str, str]] = [
        {"question": q, "answer": a} for q, a in (clarify_map or {}).items()
    ]
    ckey = cache_key(topic_id, problem_text)
    cpath = recommend_cache_path(ckey)
    if reuse_recommend:
        # 决策 4：缓存缺失 → 报错退出，不静默回退真实调用（回归确定性优先，
        # 防止"以为复用了其实又烧了 15 min"）；题面指纹 / 平台不符同样报错
        # （决策 6：题面变 → 指纹变自然失效；platform 防跨平台复用——推荐层
        # 按平台过滤模块，stm32 推荐结果喂 mspm0 生成会假绿）
        if not cpath.exists():
            print(f"  ✗ 缓存不存在: {cpath}")
            print("    （先跑一次不带 --reuse-recommend 生成缓存）")
            return False
        try:
            cached = load_recommend(cpath)
        except ValueError as exc:
            print(f"  ✗ {exc}")
            print("    （删除该缓存文件后重跑真实推荐可重建）")
            return False
        if (
            cached["problem_sha256"] != problem_fingerprint(problem_text)
            or cached["platform"] != platform
        ):
            print(f"  ✗ 缓存失效: {cpath}（题面或平台已变，指纹不符）")
            print("    （先跑一次不带 --reuse-recommend 重建缓存）")
            return False
        data = cached["done"]
        print(f"[缓存] 复用 {cpath}（推荐段跳过）")
    else:
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
        # 决策 5：默认行为不变——真实推荐后写缓存（done 载荷逐字），写失败
        # 打印警告不阻断（缓存是加速手段，不是流程依赖）
        try:
            cache_recommend(
                cpath, data, topic_key=key,
                problem_text=problem_text, platform=platform,
            )
            print(f"[缓存] 已写 {cpath}")
        except OSError as exc:
            print(f"  [缓存] 写失败（不阻断主流程）: {exc}")
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
    if gen.get("build_hint"):
        # mspm0 未探测到 CCS 工具链（工单 mspm0-build-makefiles/01）：生成照常
        # 但无 Debug/makefile 集，真机编译段必然失败——先如实提示
        print(f"  [提示] {gen['build_hint']}")
    files = [f.relative_to(out_dir).as_posix() for f in out_dir.rglob("*") if f.is_file()]
    print(f"  文件数 {len(files)}")
    for f in files:
        print(f"    - {f}")
    need = {"main.c", "user/Project.uvprojx"} if platform == "stm32" else {"main.c", "mspm0.syscfg"}
    missing = need - set(files)
    if missing:
        print(f"  ✗ 缺关键文件: {missing}")
        ok = False

    # 产物级断言：对产物树重建语料跑生产同源门禁（真机编译失败的对应检查；
    # 门禁镜像曾静默漂移，工单 generate-check-parity/01 换闸，验收测的就是
    # run_generation_gates 本身）
    problems = check_artifacts(out_dir, platform)
    if problems:
        for p in problems:
            print(f"  ✗ 产物: {p}")
        ok = False
    else:
        print("  [产物] 门禁全过（产物树语料重建，与生成同源）")

    # 真机编译（符号级完整性的唯一证明）：stm32/Keil 线 UV4 全量重建；
    # mspm0/CCS 线 gmake 全量重建（Debug/makefile 集由生成器自动产出，
    # 工单 mspm0-build-makefiles/01——旧"无命令行"文案随 gmake 通路落地删除）。
    # 编译失败 → 进入修复循环（工单 gen-check-fix-loop/01，与 web 修复中心
    # 同语义：编译报错 → /api/fix-errors → 重编译验证 ≤3 轮，第 3 轮后
    # 如实报告剩余错误）
    build_fn = uv4_build if platform == "stm32" else gmake_build
    passed, summary, raw_output = build_fn(out_dir)
    if passed is None:
        print(f"  [真机] {summary}")
    elif passed:
        print(f"  [真机] ✓ {summary}")
    else:
        print(f"  [真机] ✗ {summary}")
        print("  [真机] 进入修复循环（≤3 轮：编译报错 → AI 修复 → 重编译）")
        if not run_fix_loop(
            out_dir, raw_output, problem_text, platform, slugs, main_c
        ):
            ok = False
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
    reuse_recommend = "--reuse-recommend" in args
    if reuse_recommend:
        del args[args.index("--reuse-recommend")]
    topics = args or ["2026C", "2021F"]
    results = {
        t: check_topic(
            t, clarify_map, drop, platform, topic_file, add, reference_ids,
            reuse_recommend=reuse_recommend,
        )
        for t in topics
    }
    print("\n===== 汇总 =====")
    for t, ok in results.items():
        print(f"{t}: {'✓ 通过' if ok else '✗ 失败'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
