"""工具链探测 / 编译执行 / 日志采集域模块（工单 autocompile-loop/01）。

闭环"生成 → 自动编译 → 采集报错 → 修复 → 重编译验证"的服务端执行层：
探测工具链（UV4 / gmake / CCS 三件套，自动 + config 覆盖）→ 起子进程全量
重建工程 → 原样采集编译输出（error_text 与 fix-errors 解析契约
parse_compile_errors 天然对齐，warnings 引用行一并保留）。域判决全部在本
模块（纯函数、可单测），webapp 只做薄壳（路由 + SSE 装配），前端状态机
驱动循环（≤3 轮）。

工具链缺失是两种终态之一（决策记录 7）：/api/compile 路由在起流前判工具链
缺失 → 400 中文（登记 errors.py），前端据此置灰按钮回退贴文本模式；工程
结构异常（没有 .uvprojx / Debug/makefile）发生在流内 → error 事件如实报告
（文案写具体，不沿用泛化的"AI 服务调用失败"——工单观察记录 2）。

编译粒度（决策记录 4）：全量重建——UV4 `-j0 -r`（历史真机坑：`-b` 增量构建
日志无编译行、Build Time 00:00:00，必须 `-r` 强制重建才有报错输出）；
gmake `-B`（等价 clean + all 单次调用）。编译输出原样采集，不解析不裁剪。

超时（决策记录 7）：默认 180s，超时如实报告（timed_out=True，含已采集的
部分输出），不静默、不挂死。编译失败（工具链报错）与"编译有错"是两种终态：
前者走异常（流内 error / 起流前 400），后者是正常 done（携带 exit_code 与
error_text 走修复循环）。

依赖方向：import platforms / events / fix_errors（解析契约）与标准库；sse 仅
类型注解（TYPE_CHECKING）。run_compile（流内编排）与 resolve_compile_toolchain
（起流前 400）为 /api/compile 的域归位（工单 route-orchestration-homing/01），
webapp 只取参 + 转调。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .events import EVENT_COMPILE_START, ProgressEvent
from .fix_errors import parse_compile_errors, summarize_compile_output
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32

if TYPE_CHECKING:
    # 仅类型注解用（emit 是 sse 运行器装配的发射面；sse 是叶子模块，运行时
    # 导入无环——本模块不持 sse 运行时依赖）
    from .sse import SseEmitter

# 编译子进程超时（决策记录 7）：180s 对全量重建（Keil 大工程 ~40s）宽裕
COMPILE_TIMEOUT_SECONDS = 180.0

# UV4 常见安装路径（决策记录 6）：实测 C:\Keil5\Core\UV4\UV4.exe；
# C:\Keil_v5 是另一常见版本目录；最后走 PATH（shutil.which）
_UV4_CANDIDATES = (
    r"C:\Keil5\Core\UV4\UV4.exe",
    r"C:\Keil_v5\UV4\UV4.exe",
)

# mspm0 线构建脚本落位（决策记录 5，工单 mspm0-build-makefiles/01 起由
# makefiles.py 在生成时自动产出）：CCS 命令行构建标准 makefile 集生成在
# <工程根>/Debug/makefile（IDE 生成同款，SHELL = cmd.exe），
# gmake -C Debug -f makefile 即可全量构建
_MSPM0_MAKEFILE = "Debug/makefile"


class CompileRunnerError(Exception):
    """编译执行层的业务失败（登记 errors.py → 400 中文）。

    两种触发：工具链缺失（起流前 400，前端置灰回退贴文本）与工程结构异常
    （没有 .uvprojx / Debug/makefile——流内 error 事件，文案写具体）。
    """


@dataclass(frozen=True)
class CompileRun:
    """一次子进程编译的结果：exit_code（超时为 None）+ 原始输出 + 超时标记。

    非零退出不炸（工具链报错是正常返回，由调用方判读）；超时 = 终端状态，
    输出为已采集的部分内容（如实报告，不静默）。duration = 子进程实际耗时
    （time.monotonic 计时，超时场景同样如实记录——展示层「耗时 Xs」数据源，
    工单 compile-experience-ui/01）。
    """

    exit_code: int | None
    output: str
    timed_out: bool
    duration: float


@dataclass(frozen=True)
class BuildLog:
    """collect_build_log 的产物：定位到的工程文件 + 实际命令 + 编译结果。

    project_file 为域内判定的编译入口（uvprojx / makefile 路径），命令
    原样记录（前端 / 日志可复述）。
    """

    platform: str
    project_file: str
    command: tuple[str, ...]
    run: CompileRun


def find_uv4(override: str = "") -> Path | None:
    """探测 Keil UV4：配置覆盖 > 常见路径 > PATH。找不到返回 None。

    override 是 config.json 的 uv4_path（可选覆盖，决策记录 6）——非空但
    指向不存在的文件按未找到处理（返回 None → 400 中文，不静默）。
    """
    if override.strip():
        candidate = Path(override.strip())
        return candidate if candidate.is_file() else None
    for common in _UV4_CANDIDATES:
        path = Path(common)
        if path.is_file():
            return path
    found = shutil.which("UV4.exe") or shutil.which("uv4.exe")
    return Path(found) if found else None


def find_make(override: str = "") -> Path | None:
    """探测 gmake：配置覆盖 > PATH（gmake 优先，make 兜底）。找不到返回 None。"""
    if override.strip():
        candidate = Path(override.strip())
        return candidate if candidate.is_file() else None
    found = shutil.which("gmake") or shutil.which("make")
    return Path(found) if found else None


@dataclass(frozen=True)
class CcsTools:
    """CCS 工具链三件套（mspm0 命令行构建三依赖，工单 mspm0-build-makefiles/01）。

    真机两版本共存（SDK 在 ccs2051、编译器在 ccs2050）——三件逐件独立探测，
    不存在"同一个 CCS 版本目录"假设（决策记录 4）。
    """

    sdk_dir: Path  # mspm0_sdk_*（startup / CMSIS / .metadata/product.json）
    compiler_dir: Path  # ccs/tools/compiler/ti-cgt-armllvm_*（tiarmclang）
    sysconfig_cli: Path  # sysconfig_*/sysconfig_cli.bat（.syscfg → 生成文件）


# CCS 探测根（决策记录 4）：扫描 C:/ti/ccs*/ 目录；测试 monkeypatch 到 fake 树
_CCS_SCAN_ROOT = "C:/ti"

# 探测失败提示（决策记录 3）：生成照常、build_hint 透传给用户，不阻断
CCS_NOT_FOUND_HINT = (
    "未探测到 CCS 工具链路径（SDK / 编译器 / SysConfig CLI），命令行构建"
    "不可用——可在设置页填写 ccs_sdk_dir / ccs_compiler_dir / ccs_sysconfig_cli"
    "覆盖后重新生成"
)


def find_ccs_tools(
    sdk_override: str = "",
    compiler_override: str = "",
    sysconfig_override: str = "",
) -> CcsTools | None:
    """探测 CCS 工具链三件套：config 覆盖 > C:/ti/ccs*/ 自动扫描。

    逐件独立（决策记录 4）：SDK（<ccs>/mspm0_sdk_*）、编译器
    （<ccs>/ccs/tools/compiler/ti-cgt-armllvm_*）、SysConfig CLI
    （<ccs>/sysconfig_*/sysconfig_cli.bat）各找各的；同件多版本取目录名
    排序最大（版本号后缀大者新）。三件缺任一件 = 整体 None（调用方跳过
    makefile 生成 + build_hint 提示，不阻断生成）。覆盖值非空但指向不存在
    路径 = 该件未找到（与 find_uv4 同规，不静默）。
    """
    sdk = _piece(sdk_override, _sdk_candidates, kind="dir")
    compiler = _piece(compiler_override, _compiler_candidates, kind="dir")
    sysconfig = _piece(
        sysconfig_override, _sysconfig_candidates, kind="file", by_parent=True
    )
    if sdk is None or compiler is None or sysconfig is None:
        return None
    return CcsTools(sdk_dir=sdk, compiler_dir=compiler, sysconfig_cli=sysconfig)


def _piece(
    override: str,
    finder: Callable[[str], list[Path]],
    *,
    kind: str,
    by_parent: bool = False,
) -> Path | None:
    """单件探测：覆盖优先（kind=dir → is_dir / kind=file → is_file），非空但
    不存在 = 未找到；否则自动扫描取目录名排序最大（by_parent = 版本号在父
    目录名——SysConfig CLI 的候选是 .bat 文件，版本在其目录名）。"""
    if override.strip():
        candidate = Path(override.strip())
        ok = candidate.is_dir() if kind == "dir" else candidate.is_file()
        return candidate if ok else None
    return _newest(finder(_CCS_SCAN_ROOT), by_parent=by_parent)


def _newest(candidates: Sequence[Path], *, by_parent: bool = False) -> Path | None:
    """多版本取目录名排序最大（版本号后缀大者新）；同名并列取路径排序靠后
    （确定性，不随 glob 顺序漂移）。"""
    if not candidates:
        return None
    name = (lambda p: p.parent.name) if by_parent else (lambda p: p.name)
    return max(candidates, key=lambda p: (name(p), str(p)))


def _ccs_install_dirs(root: str) -> list[Path]:
    """扫描根下的 ccs* 安装目录（不存在 / 非目录静默跳过）。"""
    base = Path(root)
    if not base.is_dir():
        return []
    return [p for p in sorted(base.glob("ccs*")) if p.is_dir()]


def _sdk_candidates(root: str) -> list[Path]:
    hits: list[Path] = []
    for ccs in _ccs_install_dirs(root):
        hits.extend(p for p in ccs.glob("mspm0_sdk_*") if p.is_dir())
    return hits


def _compiler_candidates(root: str) -> list[Path]:
    hits: list[Path] = []
    for ccs in _ccs_install_dirs(root):
        tools = ccs / "ccs" / "tools" / "compiler"
        hits.extend(p for p in tools.glob("ti-cgt-armllvm_*") if p.is_dir())
    return hits


def _sysconfig_candidates(root: str) -> list[Path]:
    hits: list[Path] = []
    for ccs in _ccs_install_dirs(root):
        for sc in ccs.glob("sysconfig_*"):
            cli = sc / "sysconfig_cli.bat"
            if cli.is_file():
                hits.append(cli)
    return hits


def run_compile_command(
    command: Sequence[str],
    cwd: Path,
    timeout: float = COMPILE_TIMEOUT_SECONDS,
) -> CompileRun:
    """起子进程编译：超时不炸（如实报告部分输出），非零退出不炸（正常返回）。

    stdout + stderr 合并为 output（两种编译器的输出都在其一或两者）。
    超时（TimeoutExpired）→ exit_code=None + timed_out=True；子进程不存在
    （FileNotFoundError）属调用方传错命令，大声抛——工具链路径已判过存在。
    duration 用 time.monotonic 包整个子进程调用（超时分支同样如实记录）。
    """
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CompileRun(
            exit_code=proc.returncode,
            output=(proc.stdout or "") + (proc.stderr or ""),
            timed_out=False,
            duration=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        # text=True 时 stdout/stderr 是 str；类型桩对超时分支不收缩（bytes 可能
        # 有）——统一按 str 处理（bytes 解 bytes 兜底）
        def _as_text(value: str | bytes | None) -> str:
            if value is None:
                return ""
            return value.decode(errors="replace") if isinstance(value, bytes) else value

        partial = _as_text(exc.stdout) + _as_text(exc.stderr)
        return CompileRun(
            exit_code=None,
            output=partial,
            timed_out=True,
            duration=time.monotonic() - started,
        )


def collect_build_log(
    platform: str,
    out_dir: Path,
    *,
    uv4: Path | None = None,
    make: Path | None = None,
    timeout: float = COMPILE_TIMEOUT_SECONDS,
) -> BuildLog:
    """按平台定位工程文件并全量重建，返回原始编译输出（域判决唯一出处）。

    stm32：rglob 定位 .uvprojx（母版产物在 user/ 子目录）→ UV4 `-j0 -r -b`
    （-r 强制重建，历史真机坑：-b 增量构建日志无编译行）→ 日志经临时文件
    采集（-o 参数，编译输出不落进工程目录污染产物）。
    mspm0：定位 Debug/makefile（CCS 标准命令行构建脚本）→ gmake `-C Debug
    -f makefile -B`（-B 等价 clean + all 单次调用）。

    工具链缺失（uv4 / make 为 None 或指向不存在文件）→ CompileRunnerError
    （400 中文，文案列常见路径 / 配置覆盖入口）；工程结构异常（没有工程文件）
    → CompileRunnerError（流内 error 事件，文案写具体）。
    """
    if platform not in KNOWN_PLATFORMS:
        raise CompileRunnerError(f"不支持的平台：{platform}")
    root = out_dir.resolve()
    if not root.is_dir():
        raise CompileRunnerError(f"输出目录不存在：{out_dir}")

    if platform == PLATFORM_STM32:
        if uv4 is None or not uv4.is_file():
            raise CompileRunnerError(
                "未检测到 Keil UV4 工具链（常见路径 C:\\Keil5\\Core\\UV4\\UV4.exe；"
                "可在设置页填 uv4_path 覆盖）"
            )
        uvprojx = next(root.rglob("*.uvprojx"), None)
        if uvprojx is None:
            raise CompileRunnerError(
                f"工程里没有 .uvprojx，无法编译（{root} 不是完整的生成产物？）"
            )
        # UV4 把构建日志写进 -o 指定文件（stdout/stderr 基本为空）——用临时
        # 文件采集，编译输出不落进工程目录（fix-errors 只读源码，但产物干净
        # 是硬要求）；临时文件用后即删
        log_path = Path(
            tempfile.NamedTemporaryFile(delete=False, suffix=".log").name
        )
        command = (str(uv4), "-j0", "-r", "-b", str(uvprojx), "-o", str(log_path))
        try:
            run = run_compile_command(command, root, timeout=timeout)
            # UV4 把日志写进 -o 文件（stdout/stderr 基本为空）；超时被杀时
            # 文件可能没落盘 → 回退到已采集的部分输出（如实报告）
            text = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.exists()
                else ""
            )
        finally:
            log_path.unlink(missing_ok=True)
        output = (text or run.output).strip()
        return BuildLog(
            platform=platform,
            project_file=str(uvprojx),
            command=command,
            run=CompileRun(
                exit_code=run.exit_code,
                output=output,
                timed_out=run.timed_out,
                duration=run.duration,
            ),
        )

    # mspm0：CCS 命令行构建（生成器产物 Debug/makefile，决策记录 5）
    if make is None or not make.is_file():
        raise CompileRunnerError(
            "未检测到 gmake / make 工具链（可在设置页填 gmake_path 覆盖）"
        )
    makefile = root / _MSPM0_MAKEFILE
    if not makefile.is_file():
        raise CompileRunnerError(
            f"工程里没有 {_MSPM0_MAKEFILE} 构建脚本，无法编译"
            "（CCS 命令行构建产物缺失）"
        )
    command = (
        str(make), "-C", str(makefile.parent), "-f", makefile.name, "-B", "all",
    )
    run = run_compile_command(command, root, timeout=timeout)
    return BuildLog(
        platform=platform,
        project_file=str(makefile),
        command=command,
        run=run,
    )


def compile_passed(platform: str, exit_code: int | None) -> bool:
    """退出码 → 是否编译通过（前端循环的"无错可出活"判定单源）。

    UV4：0 = 无错无警、1 = 有警告无错（都算通过，warnings 如实展示）；
    2 = 有错误、其他 = 异常。gmake：0 = 通过（warnings 不影响退出码）。
    超时（exit_code=None）不算通过（前端按超时终态处理，不进修复循环）。
    """
    if exit_code is None:
        return False
    if platform == PLATFORM_STM32:
        return exit_code in (0, 1)
    return exit_code == 0


def resolve_compile_toolchain(
    platform: str, uv4_override: str = "", make_override: str = ""
) -> tuple[Path | None, Path | None]:
    """工具链探测（起流前 400 判定单源，工单 route-orchestration-homing/01）。

    平台对应工具链缺失 → CompileRunnerError（400 中文，前端据此置灰按钮回退
    贴文本模式）。探测顺序 = config 覆盖 > 常见路径 / PATH（find_uv4 /
    find_make 空覆盖语义 = 自动探测）；返回 (uv4, make)——对应平台缺失即抛错，
    调用方拿到的必是所需件非 None。与 collect_build_log 的流内缺失兜底分开：
    这里在起流前判（HTTP 400），collect_build_log 在流内兜底（error 事件）。
    """
    uv4 = find_uv4(uv4_override)
    make = find_make(make_override)
    if platform == PLATFORM_STM32 and uv4 is None:
        raise CompileRunnerError(
            "未检测到 Keil UV4 工具链（常见路径 C:\\Keil5\\Core\\UV4\\UV4.exe；"
            "可在设置页填 uv4_path 覆盖）——已回退贴文本模式"
        )
    if platform == PLATFORM_MSPM0 and make is None:
        raise CompileRunnerError(
            "未检测到 gmake / make 工具链（可在设置页填 gmake_path 覆盖）"
            "——已回退贴文本模式"
        )
    return uv4, make


def run_compile(
    platform: str,
    output_dir: Path,
    *,
    uv4: Path | None,
    make: Path | None,
    emit: SseEmitter,
) -> None:
    """/api/compile 的流内编排（工单 route-orchestration-homing/01）：compile_start
    → collect_build_log → parse_compile_errors → done（11 字段）。

    工具链探测（find_uv4 / find_make + 缺失 400）不在这里——缺失必须在起流前
    判定（400 中文，前端据此置灰按钮回退贴文本），归 resolve_compile_toolchain
    （路由在 run_sse 前调用）；本函数收已解析工具链跑编译。工程结构异常（没有
    .uvprojx / Debug/makefile）由 collect_build_log 抛 CompileRunnerError，run_sse
    转流内 error 事件（文案写具体）。done 载荷形状的家在此，webapp docstring
    只指向本函数。
    """
    emit.progress(ProgressEvent(type=EVENT_COMPILE_START))
    build = collect_build_log(platform, output_dir, uv4=uv4, make=make)
    parsed = parse_compile_errors(build.run.output)
    emit.done(
        {
            "platform": build.platform,
            "output_dir": str(output_dir),
            "exit_code": build.run.exit_code,
            "error_text": build.run.output,
            "passed": compile_passed(build.platform, build.run.exit_code),
            "timed_out": build.run.timed_out,
            "project_file": build.project_file,
            "command": list(build.command),
            # 展示层（工单 compile-experience-ui/01）：耗时 / 结构化错误列表 /
            # 数字汇总——只追加不改既有字段，旧前端忽略即可
            "duration": build.run.duration,
            "parsed_errors": [
                {"path": e.path, "line": e.line, "message": e.message}
                for e in parsed
            ],
            "summary": summarize_compile_output(build.run.output, parsed),
        }
    )
