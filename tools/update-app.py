#!/usr/bin/env python
"""firstep 应用内更新器（工单 auto-update/04）——独立进程替换工具目录。

用法（由「一键更新」端点以独立进程拉起；也可手动运行）：
    .venv\\Scripts\\python.exe tools\\update-app.py --zip <firstep-update-vX.Y.Z.zip> [选项]

流程：停服（8000 LISTENING 先经 /api/health 确认是本应用再 kill，不误杀）
→ zip 条目安全校验（zip slip 整体拒绝）→ 备份将被覆盖的条目到
`<data-dir>\\updates\\backup\\<时间戳>\\` → 解压覆盖工具根（`.venv` /
`.contest_generator` / `sources/materials` 不在包内 = 天然保留）→ 按
removed.txt 删除（路径校验落工具根内）→ 依赖变更检测（覆盖前后
pyproject.toml SHA256 对比，变了才 pip install -e .）→ 清
`updating.lock` 与 `pending-update.json` → start-app.vbs 重启。

全流程日志写 `<data-dir>\\updates\\updater.log`；失败保留备份并提示位置
（不做自动回滚）。仅依赖标准库（zipfile / urllib / subprocess）。

测试友好：核心逻辑在 `run_update(opts)`，`main()` 只做参数解析与退出码；
`--no-stop --no-restart --skip-pip` 供集成测试在临时目录完整演练。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from optparse import OptionParser
from pathlib import Path
from typing import Any, Callable, Sequence

APP_ID = "contest-generator"
HEALTH_PATH = "/api/health"
DEFAULT_PORT = 8000
DEFAULT_DATA_DIR = Path.home() / ".contest_generator"


class UpdateError(RuntimeError):
    """更新流程错误（中文 message；调用方按非 0 退出码处理）。"""


@dataclass
class UpdateOptions:
    """run_update 的入参（命令行选项的解析结果）。"""

    zip_path: Path
    removed_path: Path | None = None
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path = DEFAULT_DATA_DIR
    port: int = DEFAULT_PORT
    stop: bool = True
    restart: bool = True
    check_deps: bool = True
    log: logging.Logger | None = None
    # 完整包模式（工单 full-download/04）：多分卷 + 完整包清单（清单里带
    # 资料库基线清单，落位时写回 sources/materials/.materials-manifest.json）。
    # `full_parts` 空 = 按清单 `parts` 顺序在下载目录里找（分卷乱序也无妨）。
    # `full_manifest_location` 是**字符串**（本地路径或 http(s) URL）——URL 绝
    # 不能进 Path（Windows 上 `//` 会被折叠成 `\`，见 load_full_manifest 注释）。
    full_parts: list[str] = field(default_factory=list)
    full_manifest_location: str = ""

    @property
    def is_full_mode(self) -> bool:
        return bool(self.full_manifest_location) or bool(self.full_parts)

    @property
    def updates_dir(self) -> Path:
        return self.data_dir / "updates"

    @property
    def updater_log_path(self) -> Path:
        return self.updates_dir / "updater.log"

    @property
    def lock_path(self) -> Path:
        return self.updates_dir / "updating.lock"

    @property
    def pending_path(self) -> Path:
        return self.updates_dir / "pending-update.json"

    @property
    def result_path(self) -> Path:
        return self.updates_dir / "last-update.json"

    @property
    def installed_marker_path(self) -> Path:
        """完整包「已装版本」标记（检查更新端点读它报当前版本）。"""
        return self.updates_dir / "full-installed.json"


# ---------------------------------------------------------------------------
# 停服：确认本体 → kill（避免误杀其他占用 8000 的程序）
# ---------------------------------------------------------------------------


def find_listening_pids(port: int) -> list[str]:
    """netstat -ano 解析：返回监听 port 的 PID 列表（标准库 subprocess）。"""
    try:
        output = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception as exc:  # netstat 不可用属于环境异常，报错不静默
        raise UpdateError(f"netstat 执行失败：{exc}") from exc
    pids: list[str] = []
    for line in output.splitlines():
        parts = line.split()
        # 形如：TCP  127.0.0.1:8000  0.0.0.0:0  LISTENING  12345
        if len(parts) >= 5 and parts[-2] == "LISTENING" and f":{port}" in parts[1]:
            pid = parts[-1]
            if pid not in pids:
                pids.append(pid)
    return pids


def is_firstep_service(host: str, port: int, timeout: float = 2.0) -> bool:
    """GET /api/health 判定端口上是不是本应用（故意不依赖任何配置）。"""
    try:
        with urllib.request.urlopen(
            f"http://{host}:{port}{HEALTH_PATH}", timeout=timeout
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("app") == APP_ID
    except Exception:
        return False


def stop_service(port: int, log: Callable[[str], None]) -> None:
    """停掉监听 port 的本应用；确认不是本应用 → 拒绝（防误杀）。"""
    pids = find_listening_pids(port)
    if not pids:
        log(f"端口 {port} 无监听进程，跳过停服")
        return
    if not is_firstep_service("127.0.0.1", port):
        raise UpdateError(
            f"端口 {port} 被其他程序占用（已确认不是本应用），拒绝停服——"
            "请先关闭占用该端口的程序后重试"
        )
    for pid in pids:
        log(f"停服：结束本应用进程 PID {pid}")
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)


# ---------------------------------------------------------------------------
# 安全路径：zip 条目 / removed 清单都必须落在工具根内（zip slip 防护）
# ---------------------------------------------------------------------------


def safe_join(root: Path, name: str) -> Path:
    """把 zip 内相对路径安全映射到 root 下；越界（../、绝对路径、盘符、
    前缀逃逸）抛 UpdateError。覆盖前对全部条目预检，任一越界整体拒绝。"""
    normalized = name.replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        raise UpdateError(f"更新包内含非法路径（绝对路径）：{name}")
    pure = Path(normalized)
    if pure.is_absolute() or pure.drive:
        raise UpdateError(f"更新包内含非法路径（盘符/绝对）：{name}")
    if ".." in pure.parts:
        raise UpdateError(f"更新包内含越界路径（..）：{name}")
    root_resolved = root.resolve()
    target = (root / pure).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise UpdateError(f"更新包内含越界路径（逃逸解析）：{name}")
    return target


def validate_zip_members(zip_path: Path, root: Path) -> list[zipfile.ZipInfo]:
    """预检全部 zip 成员：目录条目跳过，文件条目逐个 safe_join；
    任一非法 → 抛 UpdateError（此时尚未写任何文件，整体拒绝）。"""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            for member in members:
                safe_join(root, member.filename)
            return members
    except zipfile.BadZipFile as exc:
        raise UpdateError(f"更新包不是有效的 zip：{exc}") from exc


# ---------------------------------------------------------------------------
# 备份 / 解压 / 删除
# ---------------------------------------------------------------------------


def backup_overwritten(
    root: Path, members: Sequence[zipfile.ZipInfo], backup_dir: Path
) -> int:
    """备份「将被覆盖且已存在」的普通文件（相对路径镜像）；返回备份数。"""
    count = 0
    for member in members:
        target = safe_join(root, member.filename)
        if target.is_file():
            dest = backup_dir / member.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            count += 1
    return count


def extract_zip(zip_path: Path, root: Path, members: Sequence[zipfile.ZipInfo]) -> int:
    """逐条目解压覆盖：先写 `<目标>.update-tmp` 再 os.replace（不半写）。"""
    count = 0
    with zipfile.ZipFile(zip_path) as archive:
        for member in members:
            target = safe_join(root, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".update-tmp")
            with archive.open(member) as source, open(tmp, "wb") as dest:
                shutil.copyfileobj(source, dest)
            os.replace(tmp, target)
            count += 1
    return count


def remove_removed_list(
    removed_path: Path | None, root: Path, log: Callable[[str], None]
) -> int:
    """按 removed.txt 删除已废弃文件（路径校验落工具根内；不存在跳过）。"""
    if removed_path is None or not removed_path.exists():
        log("无删除清单，跳过删除")
        return 0
    return remove_named_files(
        removed_path.read_text(encoding="utf-8-sig").splitlines(), root, log
    )


def remove_named_files(
    names: Sequence[str], root: Path, log: Callable[[str], None]
) -> int:
    """按相对路径清单删除（路径校验落工具根内；不存在 / 非普通文件跳过）。

    完整包模式的删除清单直接来自清单 JSON 的 `removed` 数组，故与
    `remove_removed_list` 共用这一段（路径校验单源）。
    """
    count = 0
    for raw_line in names:
        name = str(raw_line).strip()
        if not name or name.startswith("#"):
            continue
        target = safe_join(root, name)
        if target.is_file():
            target.unlink()
            count += 1
            log(f"删除已废弃文件：{name}")
        elif target.exists():
            log(f"跳过（非普通文件）：{name}")
        else:
            log(f"跳过（已不存在）：{name}")
    return count


# ---------------------------------------------------------------------------
# 依赖变更检测（覆盖前后 pyproject.toml 哈希对比，自包含、无隐式状态）
# ---------------------------------------------------------------------------


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pick_python(root: Path) -> str:
    """解释器：`.venv\\Scripts\\python.exe` 优先、系统 Python 兜底。"""
    venv = root / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return str(venv)
    return sys.executable


def install_dependencies(root: Path, python: str) -> None:
    """pyproject 变了才跑 `pip install -e .`（失败抛错，不静默）。"""
    result = subprocess.run(
        [python, "-m", "pip", "install", "-e", str(root)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
        raise UpdateError("依赖安装失败（pip install -e . 退出码 "
                          f"{result.returncode}）：" + " / ".join(tail))


# ---------------------------------------------------------------------------
# 重启
# ---------------------------------------------------------------------------


def restart_app(root: Path, log: Callable[[str], None]) -> None:
    """调 start-app.vbs 重启（隐藏窗口，浏览器自动打开）。"""
    vbs = root / "start-app.vbs"
    if not vbs.is_file():
        raise UpdateError(f"未找到启动器：{vbs}")
    log("重启应用（start-app.vbs）")
    os.startfile(str(vbs))  # noqa: S606 — Windows 专用，无等待


def version_of(zip_path: Path) -> str:
    """从 `firstep-update-v1.1.0.zip` 提取版本标记 `v1.1.0`（结果记录用）。"""
    stem = zip_path.name
    for prefix in ("firstep-update-",):
        if stem.startswith(prefix):
            stem = stem.removeprefix(prefix)
    suffix = ".zip"
    if stem.endswith(suffix):
        stem = stem.removesuffix(suffix)
    return stem


# ---------------------------------------------------------------------------
# 完整包模式（工单 full-download/04）：多分卷 + 清单 → 覆盖 + 基线写回
# ---------------------------------------------------------------------------


def load_full_manifest(location: str) -> dict[str, Any]:
    """读完整包清单：本地路径或 http(s) URL（容忍 UTF-8 BOM；结构不对抛错）。

    走 URL 的理由：完整包清单带全部文件清单（几 MB 级），让浏览器先下再回传
    纯属浪费——更新器自己拉一次即可。

    **入参必须是 str，绝不能是 Path**：Windows 上 `Path("https://a/b")` 会把
    `//` 折叠成 `\\`（实测 Python 3.14：得到 `https:\\a\\b`），于是
    `startswith("https://")` 判 false、走本地路径分支失败（真机演练实测
    `[Errno 22] Invalid argument: 'https:\\\\github.com\\...'`）。
    """
    text_holder: dict[str, Any] = {}
    try:
        if location.startswith(("http://", "https://")):
            request = urllib.request.Request(
                location, headers={"User-Agent": "firstep-updater"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                text_holder["text"] = response.read().decode("utf-8-sig")
        else:
            text_holder["text"] = Path(location).read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise UpdateError(f"完整包清单不存在：{location}") from exc
    except Exception as exc:
        raise UpdateError(f"完整包清单获取失败：{exc}") from exc
    try:
        data = json.loads(text_holder["text"])
    except Exception as exc:
        raise UpdateError(f"完整包清单解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise UpdateError("完整包清单格式非法（顶层不是对象）")
    return data


def full_zip_paths(opts: UpdateOptions, manifest: dict[str, Any]) -> list[Path]:
    """待应用的分卷路径：显式列表优先，否则按清单 `parts` 顺序在下载目录里找。"""
    if opts.full_parts:
        paths = [Path(p) for p in opts.full_parts]
    else:
        names = [
            str(item.get("zip_name") or "")
            for item in manifest.get("parts") or []
            if isinstance(item, dict)
        ]
        if not names:
            raise UpdateError("完整包清单没有分卷（parts 为空）")
        paths = [opts.zip_path.parent / name for name in names]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise UpdateError("完整包分卷缺失：" + "、".join(missing))
    return paths


def validate_all_parts(paths: Sequence[Path], root: Path) -> list[list[zipfile.ZipInfo]]:
    """**先整体预检全部卷**：任一条目越界 → 整体拒绝，且此时尚未写任何文件。"""
    return [validate_zip_members(path, root) for path in paths]


def extract_all_parts(
    paths: Sequence[Path], members_per_part: Sequence[Sequence[zipfile.ZipInfo]], root: Path
) -> int:
    """按清单顺序逐卷解压（每卷内部仍逐条目原子替换）。"""
    total = 0
    for path, members in zip(paths, members_per_part):
        total += extract_zip(path, root, members)
    return total


def write_materials_baseline(
    manifest: dict[str, Any], root: Path, log: Callable[[str], None]
) -> bool:
    """把清单里的资料库基线写进 `sources/materials/.materials-manifest.json`。

    这一步是「无基线 → 有基线」的转折点：写完这次全量，用户之后检查更新就
    只收增量。清单没带基线（老资产）→ 跳过并记日志。
    """
    baseline = manifest.get("materials_manifest")
    if not isinstance(baseline, dict) or not baseline:
        log("清单未带资料库基线，跳过写回（下次检查更新仍会提示完整包）")
        return False
    target = safe_join(root, "sources/materials/.materials-manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    batches = len(baseline.get("batches") or [])
    log(f"已写回资料库基线清单：{batches} 个批次 → {target}")
    return True


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def _make_logger(path: Path) -> logging.Logger:
    logger = logging.getLogger("firstep-updater")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(logging.StreamHandler(sys.stdout))
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.addHandler(logging.FileHandler(path, encoding="utf-8"))
    return logger


def run_update(opts: UpdateOptions) -> int:
    """执行更新；返回进程退出码（0 = 成功；1 = 失败已保留备份与标记）。

    失败不删 pending-update.json（启动器据此提示手动处理）；无论成败都清
    updating.lock（更新器已退出，恢复启动器可用性）。
    """
    root = opts.root.resolve()
    if not root.is_dir():
        print(f"[错误] 工具根目录不存在：{root}", file=sys.stderr)
        return 1
    if not opts.zip_path.is_file():
        print(f"[错误] 更新包不存在：{opts.zip_path}", file=sys.stderr)
        return 1

    log = (opts.log or _make_logger(opts.updater_log_path)).info
    updates_dir = opts.updates_dir
    updates_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = updates_dir / "backup" / timestamp
    opts.lock_path.write_text(str(int(time.time() * 1000)), encoding="utf-8")

    try:
        log(f"=== firstep 更新开始（{timestamp}）===")
        log(f"更新包：{opts.zip_path}")
        log(f"工具根：{root}")

        full_manifest: dict[str, Any] = {}
        parts: list[Path] = []
        members_per_part: list[list[zipfile.ZipInfo]] = []
        if opts.is_full_mode:
            if opts.full_manifest_location:
                full_manifest = load_full_manifest(opts.full_manifest_location)
            parts = full_zip_paths(opts, full_manifest)
            # 全部卷整体预检（zip slip / 绝对路径 / 盘符 → 整体拒绝，写盘之前）
            members_per_part = validate_all_parts(parts, root)
            total_members = sum(len(m) for m in members_per_part)
            log(f"完整包模式：{len(parts)} 卷 / {total_members} 个条目，安全校验通过")
        else:
            members_per_part = [validate_zip_members(opts.zip_path, root)]
            parts = [opts.zip_path]
            log(f"更新包条目 {len(members_per_part[0])} 个，安全校验通过")

        # 2. 停服（确认是本应用才 kill）
        if opts.stop:
            stop_service(opts.port, log)
        else:
            log("跳过停服（--no-stop）")

        # 3. 备份将被覆盖的条目（全部卷合并备份一次）
        flat_members = [m for members in members_per_part for m in members]
        backup_count = backup_overwritten(root, flat_members, backup_dir)
        log(f"已备份 {backup_count} 个将被覆盖的文件到 {backup_dir}")

        # 4. 覆盖前记录依赖指纹（缺失 = 无旧记录，走「变了」语义 ——
        #    首次更新只要包内带 pyproject 就装依赖，等价于“记录缺失则装”）
        old_pyproject_hash = file_sha256(root / "pyproject.toml")

        # 5. 解压覆盖
        if opts.is_full_mode:
            written = extract_all_parts(parts, members_per_part, root)
        else:
            written = extract_zip(opts.zip_path, root, members_per_part[0])
        log(f"已落位 {written} 个文件")

        # 5b. 完整包：写回资料库基线（无基线 → 有基线的转折点）
        if opts.is_full_mode:
            write_materials_baseline(full_manifest, root, log)

        # 6. 按删除清单清理（完整包用清单里的 removed，小发版用 removed.txt）
        if opts.is_full_mode:
            removed_names = [str(p) for p in full_manifest.get("removed") or []]
            removed_count = remove_named_files(removed_names, root, log)
        else:
            removed_count = remove_removed_list(opts.removed_path, root, log)
        log(f"已删除 {removed_count} 个废弃文件")

        # 7. 依赖变更检测：覆盖前后 pyproject.toml 哈希对比
        if opts.check_deps:
            new_pyproject_hash = file_sha256(root / "pyproject.toml")
            if old_pyproject_hash != new_pyproject_hash:
                python = pick_python(root)
                log("pyproject.toml 已变化，重装依赖（pip install -e .）…")
                install_dependencies(root, python)
            else:
                log("pyproject.toml 未变化，跳过依赖安装")
        else:
            log("跳过依赖检测与安装（--skip-pip）")

        # 8. 清待更新标记（成功才算完成）
        if opts.pending_path.exists():
            opts.pending_path.unlink()
            log("已清除待更新标记（pending-update.json）")

        # 8b. 记录结果（status 端点据此报 done）
        result = {
            "status": "ok",
            "mode": "full" if opts.is_full_mode else "single",
            "version": (
                str(full_manifest.get("version") or "") or version_of(opts.zip_path)
                if opts.is_full_mode
                else version_of(opts.zip_path)
            ),
            "finished_at": timestamp,
            "backup_dir": str(backup_dir),
        }
        opts.result_path.write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        log(f"已记录更新结果：{opts.result_path}")

        # 8c. 完整包：写「已装版本」标记（检查更新端点读它报当前版本；
        #     丢失 = 未知版本，会让用户被建议再下一次完整包，故必须落盘）
        if opts.is_full_mode and result["version"]:
            marker = {
                "version": result["version"],
                "installed_at": timestamp,
                "backup_dir": str(backup_dir),
            }
            opts.installed_marker_path.write_text(
                json.dumps(marker, ensure_ascii=False), encoding="utf-8"
            )
            log(f"已记录已装完整包版本：{result['version']} → {opts.installed_marker_path}")

        # 9. 重启
        if opts.restart:
            restart_app(root, log)
        else:
            log("跳过重启（--no-restart）")

        log("=== 更新完成 ===")
        return 0
    except Exception as exc:
        log(f"[失败] {exc}")
        log(f"[失败] 备份保留在：{backup_dir}（未自动回滚）；"
            f"日志：{opts.updater_log_path}")
        # 失败也留结果（status 端点报 failed），pending 保留供启动器提示
        opts.result_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "mode": "full" if opts.is_full_mode else "single",
                    "error": str(exc),
                    "finished_at": timestamp,
                    "backup_dir": str(backup_dir),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"[失败] {exc}", file=sys.stderr)
        print(f"[失败] 备份保留在：{backup_dir}", file=sys.stderr)
        return 1
    finally:
        if opts.lock_path.exists():
            opts.lock_path.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = OptionParser(usage="%prog --zip <更新包.zip> [选项]")
    parser.add_option("--zip", dest="zip_path", metavar="PATH", help="更新包 zip 路径（必填）")
    parser.add_option("--removed", dest="removed_path", metavar="PATH", help="removed.txt 路径（可选）")
    parser.add_option("--root", dest="root", metavar="PATH", help="工具根目录（默认 = 本脚本上级目录）")
    parser.add_option("--data-dir", dest="data_dir", metavar="PATH", help="用户数据目录（默认 ~/.contest_generator）")
    parser.add_option("--port", dest="port", type="int", default=DEFAULT_PORT, help=f"服务端口（默认 {DEFAULT_PORT}）")
    parser.add_option("--no-stop", action="store_true", dest="no_stop", default=False, help="跳过停服（测试用）")
    parser.add_option("--no-restart", action="store_true", dest="no_restart", default=False, help="跳过重启（测试用）")
    parser.add_option("--skip-pip", action="store_true", dest="skip_pip", default=False, help="跳过依赖检测与安装（测试用）")
    parser.add_option(
        "--full-manifest",
        dest="full_manifest",
        metavar="PATH_OR_URL",
        help="完整包清单（本地路径或 http(s) URL；给了即走完整包模式：多分卷 + 资料库基线写回）",
    )
    parser.add_option(
        "--part",
        action="append",
        dest="parts",
        default=[],
        metavar="PATH",
        help="完整包分卷路径（可重复；不给则按清单 parts 顺序在 --zip 同目录里找）",
    )
    options, _args = parser.parse_args(list(argv) if argv is not None else None)

    if not options.zip_path:
        parser.error("缺少必填参数 --zip")
    root = Path(options.root) if options.root else Path(__file__).resolve().parent.parent
    opts = UpdateOptions(
        zip_path=Path(options.zip_path),
        removed_path=Path(options.removed_path) if options.removed_path else None,
        root=root,
        data_dir=Path(options.data_dir) if options.data_dir else DEFAULT_DATA_DIR,
        port=options.port,
        stop=not options.no_stop,
        restart=not options.no_restart,
        check_deps=not options.skip_pip,
        full_parts=list(options.parts or []),
        full_manifest_location=str(options.full_manifest or ""),
    )
    return run_update(opts)


if __name__ == "__main__":
    sys.exit(main())
