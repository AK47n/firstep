"""烧录执行层（工单 flash-deploy/01）：固件定位 / 烧录工具探测 / 命令构建 / 执行。

闭环"生成 → 编译 → 烧录上板"的烧录腿：点一个按钮，工具自动定位固件产物
（STM32 → user/Objects/*.hex，MSPM0 → Debug/*.out）、探测本机烧录器 CLI
（MSPM0/XDS110 走 CCS 自带 DSLite，零安装；STM32/ST-Link 走 OpenOCD 或
st-flash）、构建命令行、起子进程烧录并中文回报结果。纯确定性、不 import
llm（与编译 / 烧录无 LLM 参与一致——决策记录 1）。

工具探测顺序（决策记录 2）：config 覆盖（openocd_path / stflash_path /
dslite_path）> 自动（shutil.which / C:/ti/ccs* 扫 DSLite——本机实测
CCS 20.5.0 自带 DSLite.exe + FlashMSPM0.dll，MSPM0 零安装）> 缺失
（FlashError → 400 中文 + 指引，前端渲染指引卡）。

超时（决策记录 3，对照编译 180s 先例）：默认 180s，超时如实报告
（timed_out=True，含已采集的部分输出），不静默、不挂死。烧录失败
（工具报错 / 探针未接）是正常返回（ok=False 携带输出尾 + 排查提示），
不是异常；产物缺失 / 工具缺失 / 平台未知才是域内业务异常（FlashError）。

依赖方向：import platforms 与标准库；无 webapp 依赖。resolve_flash_tool
（起流前 400）与 flash_project（流内/同步编排）为 /api/flash 的域归位，
webapp 只取参 + 转调（工单 route-orchestration-homing/01 同款）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32

# 烧录子进程超时（决策记录 3）：180s 对烧录（秒级~分钟级）宽裕
FLASH_TIMEOUT_SECONDS = 180.0

# 固件产物后缀（决策记录 4）：stm32 → hex（母版已开 <CreateHexFile>1，
# 产物 user/Objects/*.hex）；mspm0 → out（CCS 链接产物 Debug/*.out）
_FIRMWARE_SUFFIXES = {
    PLATFORM_STM32: (".hex",),
    PLATFORM_MSPM0: (".out",),
}

# CCS 烧录工具扫描根（决策记录 5）：扫 C:/ti/ccs*/ 装 DSLite（与
# compile_runner._CCS_SCAN_ROOT 同思路；本模块独立常量，测试 monkeypatch
# 本模块名）。DSLite 相对 CCS 安装目录的落位固定（实测 20.5.0.4019）。
_CCS_SCAN_ROOT = "C:/ti"
_DSLITE_RELATIVE = Path("ccs") / "ccs_base" / "DebugServer" / "bin" / "DSLite.exe"

# rglob 定位产物时跳过的目录名子串（决策记录 6）：备份镜像 / 版本管理 /
# IDE 元数据目录里也可能有 hex/out 同名文件（旧档），只认工程实况的最新产物。
# 注意不能跳 "Debug"——MSPM0 产物就在 Debug/ 下。
_SKIPPED_DIR_NAMES = ("backup", "backups", ".git", ".idea", ".vscode", ".vs")

# 烧录失败的输出展示行数（决策记录 7）：尾 40 行截断（指导性提示在前几行，
# 报错栈在尾部——取尾不取头，与编译 error_text 全量不同：烧录日志长且多为
# 探针/握手噪音，尾部才是有用信息）
OUTPUT_TAIL_LINES = 40


class FlashError(Exception):
    """烧录执行层的业务失败（登记 errors.py → 400 中文）。

    三种触发：平台未知 / 固件产物缺失（未先编译）/ 烧录工具缺失（含 MSPM0
    无 DSLite、STM32 无 OpenOCD 且无 st-flash——message 带安装指引）。
    工具缺失是"流程前置条件不满足"（对照 compile 起流前 400 先例），不是
    烧录失败（烧录失败正常返回 ok=False）。
    """


@dataclass(frozen=True)
class FlashTool:
    """定位到的一台烧录器：kind（dslite / openocd / stflash）+ 可执行文件
    路径 + 中文 display（前端按钮 / 结果行展示）。"""

    kind: str
    exe: Path
    display: str


@dataclass(frozen=True)
class FlashRun:
    """一次烧录子进程的结果：exit_code（超时为 None）+ 原始输出 + 超时标记
    （对照 CompileRun 同构，决策记录 3）。非零退出不炸（工具报错是正常返回，
    由调用方判读）；duration 用 time.monotonic 计时（超时场景同样如实记录——
    前端「耗时 Xs」数据源）。"""

    exit_code: int | None
    output: str
    timed_out: bool
    duration: float


def find_firmware(output_dir: Path, platform: str) -> Path | None:
    """定位固件产物：平台后缀集 rglob，取 mtime 最新；跳过备份类目录。

    返回 None = 未找到（未编译 / 编译产物被清）——调用方抛 FlashError
    「请先完成编译」，不把旧备份里的固件当产物。
    """
    suffixes = _FIRMWARE_SUFFIXES.get(platform)
    if suffixes is None:
        raise FlashError(f"未知平台：{platform}（支持 {'/'.join(KNOWN_PLATFORMS)}）")
    if not output_dir.is_dir():
        raise FlashError(f"输出目录不存在：{output_dir}")
    candidates = list(_iter_candidates(output_dir, suffixes))
    if not candidates:
        return None
    return max(candidates, key=_artifact_key)


def find_ccxml(output_dir: Path) -> Path | None:
    """定位 CCS 目标配置文件：rglob *.ccxml 取 mtime 最新（跳过备份类目录）。

    DSLite 烧录必须带 --config=<ccxml>（XDS110 探针与目标芯片描述）；
    缺失由 build_flash_command 抛 FlashError（400 中文）。
    """
    candidates = list(_iter_candidates(output_dir, (".ccxml",)))
    if not candidates:
        return None
    return max(candidates, key=_artifact_key)


def resolve_flash_tool(
    platform: str,
    *,
    dslite_path: str = "",
    openocd_path: str = "",
    stflash_path: str = "",
) -> FlashTool | None:
    """探测烧录工具：config 覆盖 > 自动（which / C:/ti/ccs* 扫 DSLite）。

    mspm0 → 只认 DSLite（XDS110 路线；覆盖 dslite_path 非空但文件不存在 =
    未找到，与 find_uv4 同规不静默）；stm32 → OpenOCD 优先、st-flash 兜底
    （二者覆盖独立；都缺失 = None → 调用方抛 400 指引）。覆盖非空但指向
    不存在的文件按未找到处理。
    """
    if platform == PLATFORM_MSPM0:
        dslite = _resolve_override_or_scan(
            dslite_path, _find_dslite_candidates
        )
        if dslite is None:
            return None
        return FlashTool(
            kind="dslite",
            exe=dslite,
            display="CCS DSLite（XDS110，CCS 自带）",
        )
    if platform == PLATFORM_STM32:
        openocd = _resolve_override_or_which(openocd_path, "openocd")
        if openocd is not None:
            return FlashTool(kind="openocd", exe=openocd, display="OpenOCD（ST-Link）")
        stflash = _resolve_override_or_which(stflash_path, "st-flash")
        if stflash is not None:
            return FlashTool(kind="stflash", exe=stflash, display="st-flash（ST-Link）")
        return None
    raise FlashError(f"未知平台：{platform}（支持 {'/'.join(KNOWN_PLATFORMS)}）")


def build_flash_command(tool: FlashTool, firmware: Path, output_dir: Path) -> list[str]:
    """构建烧录命令行：三条 builder 精确参数（决策记录 8，单元断言逐字）。

    dslite：`DSLite.exe flash --config=<ccxml> <out> -u`（-u = 烧完运行；
    ccxml 缺失 → FlashError）；openocd：`-f interface/stlink.cfg
    -f target/stm32f1x.cfg -c "program <hex> verify reset exit"`（F103 系列
    目标文件 stm32f1x.cfg）；stflash：`st-flash write <hex> 0x08000000`。
    output_dir 仅 dslite 分支用（定位 ccxml）；openocd / stflash 两分支
    忽略（产物路径已含全部信息）。
    """
    if tool.kind == "dslite":
        ccxml = find_ccxml(output_dir)
        if ccxml is None:
            raise FlashError(
                "未找到 CCS 目标配置文件（.ccxml，应在 targetConfigs/ 下）——"
                "MSPM0 烧录需要它来定位 XDS110 探针与芯片"
            )
        return [
            str(tool.exe),
            "flash",
            f"--config={ccxml}",
            str(firmware),
            "-u",
        ]
    if tool.kind == "openocd":
        return [
            str(tool.exe),
            "-f",
            "interface/stlink.cfg",
            "-f",
            "target/stm32f1x.cfg",
            "-c",
            f"program {firmware} verify reset exit",
        ]
    if tool.kind == "stflash":
        return [str(tool.exe), "write", str(firmware), "0x08000000"]
    raise FlashError(f"未知烧录工具类型：{tool.kind}")


def run_flash(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = FLASH_TIMEOUT_SECONDS,
) -> FlashRun:
    """起子进程烧录：超时不炸（如实报告部分输出），非零退出不炸（正常返回）。

    stdout + stderr 合并为 output（探针工具输出可能在其一或两者）。超时
    （TimeoutExpired）→ exit_code=None + timed_out=True；可执行文件不存在
    （FileNotFoundError / OSError）属调用方传错命令，大声抛——工具路径已判
    过存在。duration 用 time.monotonic 包整个子进程调用（超时分支同样如实
    记录）。
    """
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return FlashRun(
            exit_code=proc.returncode,
            output=(proc.stdout or "") + (proc.stderr or ""),
            timed_out=False,
            duration=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        def _as_text(value: str | bytes | None) -> str:
            if value is None:
                return ""
            return value.decode(errors="replace") if isinstance(value, bytes) else value

        partial = _as_text(exc.stdout) + _as_text(exc.stderr)
        return FlashRun(
            exit_code=None,
            output=partial,
            timed_out=True,
            duration=time.monotonic() - started,
        )


def flash_project(
    platform: str,
    output_dir: Path,
    *,
    dslite_path: str = "",
    openocd_path: str = "",
    stflash_path: str = "",
    timeout: float = FLASH_TIMEOUT_SECONDS,
) -> dict:
    """烧录编排（/api/flash 的域归位，webapp 只转调）：定位产物 → 探测工具 →
    构建命令 → 执行 → 中文结果 dict。

    返回 {ok, tool, command, firmware, output, message, timed_out, duration,
    exit_code}：ok=False 是烧录失败（工具报错 / 探针未接 / 超时——输出原样
    带出 + 排查提示），不是异常。产物缺失 / 工具缺失 / 平台未知 = FlashError
    （400 中文 + 指引）。产出定位失败时 hint 区分平台（与产物路径约定一致）。
    """
    if platform not in KNOWN_PLATFORMS:
        raise FlashError(f"未知平台：{platform}（支持 {'/'.join(KNOWN_PLATFORMS)}）")
    if not output_dir.is_dir():
        raise FlashError(f"输出目录不存在：{output_dir}")
    firmware = find_firmware(output_dir, platform)
    if firmware is None:
        artifact = "user/Objects/*.hex" if platform == PLATFORM_STM32 else "Debug/*.out"
        raise FlashError(
            f"未找到固件产物（{artifact}）——请先完成编译再烧录；另外注意："
            "备份目录里的同名文件不算产物"
        )
    tool = resolve_flash_tool(
        platform,
        dslite_path=dslite_path,
        openocd_path=openocd_path,
        stflash_path=stflash_path,
    )
    if tool is None:
        raise FlashError(_tool_missing_message(platform))
    command = build_flash_command(tool, firmware, output_dir)
    run = run_flash(command, cwd=output_dir, timeout=timeout)
    ok = run.exit_code == 0 and not run.timed_out
    if ok:
        message = f"烧录成功：{tool.display}（{run.duration:.1f}s）"
    elif run.timed_out:
        message = (
            f"烧录超时（{int(timeout)}s）：探针可能未连接或设备无响应——"
            "请检查 ST-Link/XDS110 接线与目标板供电后重试"
        )
    else:
        message = (
            f"烧录失败（退出码 {run.exit_code}）：工具报错见下方输出——"
            "常见排查：探针未接 / 目标板未供电 / 板子在 DFU/ISP 状态"
        )
    return {
        "ok": ok,
        "tool": {
            "kind": tool.kind,
            "exe": str(tool.exe),
            "display": tool.display,
        },
        "command": command,
        "command_text": _join_command(command),
        "firmware": str(firmware),
        "output": _tail_output(run.output),
        "output_tail_lines": OUTPUT_TAIL_LINES,
        "message": message,
        "timed_out": run.timed_out,
        "duration": run.duration,
        "exit_code": run.exit_code,
    }


def _join_command(command: Sequence[str]) -> str:
    """命令文本（前端「复制烧录命令」用，粘贴到 shell 可直接执行）：含空白
    的参数用双引号包裹——openocd 的 `-c "program <hex> …"` 内固件路径含空格
    时裸拼会被拆成多个实参（工单 flash-deploy/02 评审观察）。子进程执行仍用
    原始 command 列表（不带引号），此函数只服务展示 / 复制。"""
    return " ".join(
        '"' + part + '"' if " " in part or "\t" in part else part
        for part in command
    )


def _tool_missing_message(platform: str) -> str:
    """工具缺失的中文指引（决策记录 9）：不甩裸报错，给安装 / 配置路径。"""
    if platform == PLATFORM_MSPM0:
        return (
            "未找到 CCS 烧录工具（DSLite.exe）——MSPM0/XDS110 烧录依赖 "
            "CCS 自带的 DebugServer（C:\\ti\\ccs*\\ccs\\ccs_base\\DebugServer\\"
            "bin\\DSLite.exe）。请安装 CCS（或设置页填 dslite_path 指向现有 "
            "DSLite.exe）"
        )
    return (
        "未找到 STM32 烧录工具（OpenOCD / st-flash）——ST-Link 烧录需要其一。"
        "请任选一种：① 安装 OpenOCD 并加入 PATH；② 安装 st-flash 并加入 PATH；"
        "③ 手动安装后在设置页填 openocd_path / stflash_path。"
        '参考命令：openocd -f interface/stlink.cfg -f target/stm32f1x.cfg '
        '-c "program <hex> verify reset exit"（或 st-flash write <hex> 0x08000000）'
    )


def _resolve_override_or_which(override: str, name: str) -> Path | None:
    """单工具覆盖 > PATH（与 find_uv4 同规：覆盖非空但文件不存在 = 未找到）。"""
    if override.strip():
        candidate = Path(override.strip())
        return candidate if candidate.is_file() else None
    found = shutil.which(name)
    return Path(found) if found else None


def _resolve_override_or_scan(
    override: str,
    finder: Callable[[], list[Path]],
) -> Path | None:
    """单工具覆盖 > 自动扫描取目录名排序最大（多版本取新版，与
    compile_runner._newest 同思路）。"""
    if override.strip():
        candidate = Path(override.strip())
        return candidate if candidate.is_file() else None
    candidates = finder()
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.name, str(p)))


def _find_dslite_candidates() -> list[Path]:
    """扫 C:/ti/ccs*/ccs/ccs_base/DebugServer/bin/DSLite.exe（多版本取新）。"""
    root = Path(_CCS_SCAN_ROOT)
    if not root.is_dir():
        return []
    return [
        p
        for ccs in sorted(root.glob("ccs*"))
        if ccs.is_dir()
        for p in [ccs / _DSLITE_RELATIVE]
        if p.is_file()
    ]


def _iter_candidates(root: Path, suffixes: tuple[str, ...]) -> Iterator[Path]:
    """os.walk 手写 rglob（可跳过目录）：后缀小写匹配，产出候选 Path。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if not _is_skipped_dir(d)
        ]
        for name in filenames:
            if name.lower().endswith(suffixes):
                yield Path(dirpath) / name


def _is_skipped_dir(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in _SKIPPED_DIR_NAMES)


def _artifact_key(path: Path) -> tuple[float, str]:
    """mtime 最新优先，同名并列取路径排序靠后（确定性，不随 walk 顺序漂移）。"""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (mtime, str(path))


def _tail_output(output: str, lines: int = OUTPUT_TAIL_LINES) -> str:
    """输出尾 lines 行截断（保留原样字符，只切行——去掉为空串则原样返回）。"""
    if not output:
        return ""
    tail = "\n".join(output.splitlines()[-lines:])
    return tail
