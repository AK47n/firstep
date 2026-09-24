# -*- coding: utf-8 -*-
"""工单 hwcheck-acceptance/01 的反证探针：**证明那几条绿是真判据绿**。

三针，各扎产品代码里一处判据，看三条路的文本断言当不当场变红；每针前后逐字节
复原 + sha256 复核，finally 里无条件复原。

* **针 A：关掉"构建期外部接口面"**（`syscfg_init_functions_for` 恒返回 None——
  等于平台不是 mspm0 / 拿不到母版，产品就是这样退回现状的）。此时接口块与生成
  门禁都不认那几个名字：
  * 赛题这一路：门禁不并入 → `UndefinedCallsError`（红）；
  * 骨架这一路：出稿里那行被判不存在 → 注释占位；但**补行那一道仍然兜住**
    （本单的两道保险互相独立），所以骨架这一路要针 B 才红——这本身是个读数。
* **针 B：关掉"确定性补行"**（`ensure_sysconfig_init` 恒返回原文），叠在针 A 上：
  出稿没写 init 时骨架这一路终于红（注释占位）。两针**缺一不可**——这就是
  "门禁放行" 与 "确定性补行" 两道保险的分工证据。
* **针 C：故意写一个真不存在的调用**（把检测页渲染器的启动行换成
  `SYSCFG_DL_TYPO_init();`）——这条**不关任何东西**，验的是"放行面是精确判据、
  不是前缀白名单"：门禁必须仍然红。

用法：
    python .scratch/hwcheck-acceptance/probe-01-reverse.py
读数落 `probe-01-reverse.txt`（先落盘再打印）。
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKELETON_PY = REPO / "src" / "contest_generator" / "skeleton.py"
HWCHECK_PY = REPO / "src" / "contest_generator" / "hwcheck.py"
SYSCFG_MODEL_PY = REPO / "src" / "contest_generator" / "syscfg_model.py"
TARGETS = (SKELETON_PY, HWCHECK_PY, SYSCFG_MODEL_PY)
MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
REPORT = REPO / ".scratch" / "hwcheck-acceptance" / "probe-01-reverse.txt"

# ---- 针 A：关掉"构建期外部接口面" -------------------------------------------
# 注在**判据单源**上（`syscfg_model.syscfg_init_functions`）：01 评审整改后，
# 骨架的接口块、生成门禁、检测页的"这个名字在不在接口面里"三处都从这一处投影
# ——扎在转调层（`syscfg_init_functions_for`）只扎得中骨架那一路，门禁走的是
# 语料文本入口，扎不中（第一版就是这么假绿的：针 A 下去赛题这一路仍放行）。
_ANCHOR_A = '''    instance_functions = (
        f"SYSCFG_DL_{name}_init"
        for name, instance in model.instances.items()
        if instance.module != MSPM0_GPIO_MODULE
    )
'''
_INJECT_A = '''    return ()  # [反证针 A] 关掉构建期外部接口面（判据单源）
    instance_functions = (
        f"SYSCFG_DL_{name}_init"
        for name, instance in model.instances.items()
        if instance.module != MSPM0_GPIO_MODULE
    )
'''
_INJECT_A_PATH = SYSCFG_MODEL_PY

# ---- 针 B：关掉"确定性补行"（`ensure_sysconfig_init` 恒返回原文）----------
_ANCHOR_B = '''    body = _main_function_body(main_c)
    if body is None:
        return main_c
'''
_INJECT_B = '''    return main_c  # [反证针 B] 关掉确定性补行
    body = _main_function_body(main_c)
    if body is None:
        return main_c
'''

# ---- 针 C：检测页渲染器写一个真不存在的调用 ------------------------------
_ANCHOR_C = '''    PLATFORM_MSPM0: (
        f"    {MSPM0_SYSCFG_INIT_NAME}();  /* SysConfig 外设初始化（构建期生成，"'''
_INJECT_C = '''    PLATFORM_MSPM0: (
        "    SYSCFG_DL_TYPO_init();  /* [反证针 C] 故意写一个真不存在的调用 */"
        f"    {MSPM0_SYSCFG_INIT_NAME}();  /* SysConfig 外设初始化（构建期生成，"'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def drop_module_cache() -> list[str]:
    """清掉被测模块的**进程内缓存**——注入是否真生效的关键一步。

    探针与产品代码同在一个进程：`import contest_generator.skeleton` 一次之后，
    后续调用跑的是 `sys.modules` 里那份**注入前的字节码**。第一版探针没清缓存，
    三条路"注入后全绿"，看着像断言是摆设，其实是探针自己没换代码。

    ⚠ **整包清**（不是只清被改的那一个文件）：针 A 注在
    `contest_generator.syscfg_model` 上，而 `skeleton` / `generator` /
    `syscfg_prune` 都是 `from .syscfg_model import syscfg_init_functions`——
    只清 syscfg_model 的话，那些**已经 import 过**的模块仍握着旧函数对象，
    注入看着"没生效"（本轮第二版就是这么假绿的）。
    """
    dropped = [
        name for name in sys.modules if name.startswith("contest_generator")
    ]
    for name in dropped:
        del sys.modules[name]
    return sorted(dropped)


def patch(path: Path, anchor: str, injected: str, tag: str) -> None:
    """把 anchor 换成本文注入版（锚点必须唯一命中，否则当场失败不猜）。"""
    text = path.read_text(encoding="utf-8")
    assert text.count(anchor) == 1, f"{tag} 的锚点在 {path.name} 里不唯一/不存在"
    path.write_text(text.replace(anchor, injected), encoding="utf-8")


def write_report(lines: list[str]) -> None:
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")   # 先落盘


def _surface_names() -> tuple[str, ...]:
    from contest_generator.syscfg_model import parse_syscfg, syscfg_init_functions

    text = (MASTERS / "mspm0" / "mspm0.syscfg").read_text(encoding="utf-8")
    return syscfg_init_functions(
        parse_syscfg(text).prune(["led", "delay", "debug_uart"])
    )


def skeleton_route(*, draft_writes_init: bool = False) -> str:
    """骨架这一路（真库真母版）：看补行 / 占位谁赢。

    `draft_writes_init` 两种出稿各有各的用处：
    * False（默认）= LLM **没写** init——扎的是"确定性补行"那一道；
    * True = LLM **写了** init——扎的是"sanitize 会不会把它当不存在的调用
      注释掉"（本单票面点名的原始失败形态：`/* TODO: SYSCFG_DL_init(); … */`）。
    """
    from contest_generator.clex import strip_comments
    from contest_generator.platforms import PLATFORM_MSPM0
    from contest_generator.selection import resolve_selection
    from contest_generator.skeleton import generate_skeleton
    from tests.fakes import FakeLLM

    manifests = resolve_selection(
        MODULES, PLATFORM_MSPM0, ["led", "delay", "debug_uart"]
    ).manifests
    call = "  SYSCFG_DL_init();\n" if draft_writes_init else ""
    main_c, blocked = generate_skeleton(
        FakeLLM(
            main_skeleton=(
                '#include "ti_msp_dl_config.h"\n'
                '#include "debug_uart_mspm0.h"\n'
                "int main(void)\n{\n"
                f"{call}"
                "  debug_uart_init();\n  while (1) { }\n}\n"
            )
        ),
        "反证用题面",
        manifests,
        PLATFORM_MSPM0,
        MODULES,
        MASTERS / "mspm0",
    )
    live = "SYSCFG_DL_init();" in strip_comments(main_c)
    note = ""
    if not live:
        # 判不出来时把"它被怎么写掉的"如实记下：sanitize 的形态是
        # `/* TODO: SYSCFG_DL_init(); —— …已注释占位… */`（含原调用文本），
        # 不是裸露的 `/* SYSCFG_DL_init(); */`——两种都算"不是活调用"。
        todo = [line.strip() for line in main_c.splitlines()
                if "SYSCFG_DL_init" in line and "TODO" in line]
        note = f"、写掉的形态={'TODO 注释占位' if todo else '没出现'}"
    tag = "出稿写了 init" if draft_writes_init else "出稿没写 init"
    return f"骨架这一路（{tag}）：活调用={live}{note}、blocked={blocked!r}"


def contest_route() -> str:
    """赛题这一路：那一行是活的 main.c 喂真生成内核，看门禁放不放。"""
    from contest_generator.generator import UndefinedCallsError, generate_project
    from contest_generator.platforms import PLATFORM_MSPM0

    main_c = (
        '#include "ti_msp_dl_config.h"\n'
        '#include "debug_uart_mspm0.h"\n'
        "int main(void)\n{\n    SYSCFG_DL_init();\n    while (1) { }\n}\n"
    )
    out = Path(tempfile.mkdtemp(prefix="firstep-rev-contest-"))
    try:
        try:
            generate_project(
                platform=PLATFORM_MSPM0, slugs=["debug_uart"],
                main_c_content=main_c, output_dir=out,
                module_library_dir=MODULES, masters_dir=MASTERS,
            )
        except UndefinedCallsError as exc:
            return ("赛题这一路：门禁红（UndefinedCallsError）——"
                    + str(exc).splitlines()[0][:70])
        return "赛题这一路：门禁放行（生成成功）"
    finally:
        shutil.rmtree(out, ignore_errors=True)


def hwcheck_route() -> str:
    """检测页这一路：渲染器的启动行是不是活调用 + 那个名字在接口面里吗。"""
    from contest_generator.clex import strip_comments
    from contest_generator.hwcheck import HwCheckConfig, render_main_c
    from contest_generator.platforms import PLATFORM_MSPM0

    code = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=True)
    )
    live = "SYSCFG_DL_init();" in strip_comments(code)
    in_surface = "SYSCFG_DL_init" in _surface_names()
    ok = live and in_surface
    return (
        f"检测页这一路：启动行活调用={live}、该名字在构建期接口面里={in_surface}"
        + ("" if ok else "  ← 对不上（红）")
    )


def typo_gate_check() -> str:
    """针 C：渲染器写一个真不存在的调用，门禁必须仍然红。"""
    from contest_generator.generator import UndefinedCallsError, generate_project
    from contest_generator.hwcheck import HwCheckConfig, render_main_c
    from contest_generator.platforms import PLATFORM_MSPM0

    code = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=False)
    )
    assert "SYSCFG_DL_TYPO_init()" in code, "针 C 没生效（渲染器没出那个名字）"
    out = Path(tempfile.mkdtemp(prefix="firstep-rev-typo-"))
    try:
        try:
            generate_project(
                platform=PLATFORM_MSPM0, slugs=["debug_uart"],
                main_c_content=code, output_dir=out,
                module_library_dir=MODULES, masters_dir=MASTERS,
            )
        except UndefinedCallsError as exc:
            return ("针 C：门禁仍红（UndefinedCallsError）——"
                    + str(exc).splitlines()[0][:70])
        return "针 C：**门禁被削弱了**——一个真不存在的调用居然放行"
    finally:
        shutil.rmtree(out, ignore_errors=True)


def git_dirty(paths: tuple[Path, ...]) -> str:
    """工作树里这几份文件相对 HEAD 的状态（复原的旁证；本单不许 commit）。"""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", *[str(p) for p in paths]],
            cwd=str(REPO), capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        return f"（git 查询失败：{type(exc).__name__}）"
    return proc.stdout.strip() or "（无差异）"


def _routes() -> list[str]:
    """三条路各一条读数（骨架那一路两种出稿都跑：写了 / 没写 init）。"""
    return [
        skeleton_route(),
        skeleton_route(draft_writes_init=True),
        contest_route(),
        hwcheck_route(),
    ]


def main() -> int:
    lines: list[str] = ["=== 工单 01 反证探针（三针）===", ""]
    failures: list[str] = []
    originals = {p: p.read_bytes() for p in TARGETS}
    digests = {p: sha256(p) for p in TARGETS}
    lines.append("注入前 sha256：")
    for path, digest in digests.items():
        lines.append(f"  {path.name}: {digest[:16]}…")
    try:
        lines.append("")
        lines.append("--- 基线（未注入）---")
        baseline = _routes()
        lines.extend(baseline)
        if not all("活调用=True" in row for row in baseline[:2]) \
                or "门禁放行" not in baseline[2] or "对不上" in baseline[3]:
            failures.append("基线不是绿的（探针起点就不对）")
        else:
            lines.append("基线四条读数都绿——开始扎针。")

        # ---- 针 A：关掉构建期外部接口面 -----------------------------------
        lines.append("")
        lines.append(
            "--- 针 A：`syscfg_model.syscfg_init_functions` 恒空（关掉放行面，"
            "注在**判据单源**上）---"
        )
        patch(_INJECT_A_PATH, _ANCHOR_A, _INJECT_A, "针 A")
        lines.append(f"（清进程内缓存 {len(drop_module_cache())} 个模块后重跑判据）")
        after_a = _routes()
        lines.extend(after_a)
        if "门禁红" not in after_a[2]:
            failures.append("针 A 没能让赛题这一路变红")
        if "活调用=False" not in after_a[1] or "TODO 注释占位" not in after_a[1]:
            failures.append("针 A 没能让「出稿写了 init」的骨架这一路变回注释占位")
        if "活调用=False" not in after_a[0]:
            lines.append(
                "（出稿没写 init 的那一路仍绿：**补行那一道兜住了**——两道保险"
                "互相独立，针 B 才扎得动它）"
            )

        # ---- 针 B：叠上"关掉确定性补行" -----------------------------------
        lines.append("")
        lines.append("--- 针 B：再让 `ensure_sysconfig_init` 恒返回原文（叠在针 A 上）---")
        patch(SKELETON_PY, _ANCHOR_B, _INJECT_B, "针 B")
        drop_module_cache()
        after_b = _routes()
        lines.extend(after_b)
        if "活调用=False" not in after_b[0]:
            failures.append("针 A+B 都没能让「出稿没写 init」的骨架这一路变红")

        # ---- 复原（针 A 在 syscfg_model.py、针 B 在 skeleton.py）------------
        for path, tag in ((_INJECT_A_PATH, "针 A"), (SKELETON_PY, "针 B")):
            path.write_bytes(originals[path])
            assert sha256(path) == digests[path], f"{tag} 复原失败"
        drop_module_cache()
        lines.append(
            f"syscfg_model.py / skeleton.py 已复原（sha256 "
            f"{'一致 ✓' if all(sha256(p) == digests[p] for p in (_INJECT_A_PATH, SKELETON_PY)) else '不一致 ✗'}）"
        )

        # ---- 针 C：故意写一个真不存在的调用 -------------------------------
        lines.append("")
        lines.append("--- 针 C：渲染器写 `SYSCFG_DL_TYPO_init()`（不许被放行）---")
        patch(HWCHECK_PY, _ANCHOR_C, _INJECT_C, "针 C")
        drop_module_cache()
        typo = typo_gate_check()
        lines.append(typo)
        if "门禁仍红" not in typo:
            failures.append("针 C 说明门禁被削弱了")
        HWCHECK_PY.write_bytes(originals[HWCHECK_PY])
        assert sha256(HWCHECK_PY) == digests[HWCHECK_PY], "针 C 复原失败"
        drop_module_cache()
        lines.append("hwcheck.py 已复原")

        # ---- 复原复核 -----------------------------------------------------
        lines.append("")
        lines.append("--- 复原复核 ---")
        for path, digest in digests.items():
            now = sha256(path)
            lines.append(
                f"{path.name}: {now[:16]}… "
                f"{'== 注入前 ✓' if now == digest else '!= 注入前 ✗'}"
            )
        lines.append(f"git 工作树（这两份文件）：{git_dirty(TARGETS)}")
        restored = _routes()
        lines.extend(restored)
        if restored != baseline:
            failures.append("复原后三条路与基线不一致")
        else:
            lines.append("复原后三条路与基线逐字一致。")
    finally:
        for path, original in originals.items():
            if path.read_bytes() != original:
                path.write_bytes(original)
                lines.append(f"[finally] {path.name} 强制复原")

    lines.append("")
    lines.append(
        "=== 结论：" + ("反证成立（A 扎红赛题路、A+B 扎红骨架路、C 证明门禁仍红）"
                        if not failures else "**反证不成立**：" + "、".join(failures))
        + " ==="
    )
    write_report(lines)
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
