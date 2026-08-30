"""母版库 CRUD（入库 / 浏览 / 删除）与域错误定义（MasterError）唯一出处。

母版库：磁盘目录即数据库，母版库根下每个平台一个目录（工程文件本体）+ 同名
<platform>.json 元数据（提炼来源、入库时结构分析的警告）。元数据放目录外的
平级文件：母版目录会被生成器整体复制，内部带 json（如 master.json）会污染
生成的工程。

任何从平台名拼路径的操作（浏览 / 删除 / 入库）都先校验平台名合法性，杜绝
借平台名逃出母版库的路径穿越。母版库的物理位置由调用方传入（后续工单接入
本机配置），测试用 tmp_path。

架构深化 v5 三轴拆块（工单 01）：母版库 CRUD 从 master.py 拆出，master 只留
蒸馏编排；本模块不 import categories（防环：categories 的启动验证要用本模块
的 MasterError，依赖方向 master_store → categories 不存在）。工程配置文件
后缀表（PLATFORM_CONFIG_FILE_SUFFIXES）单源在 platforms.py（工单 04 收敛，
词表层谁都能 import 无循环），本模块只消费。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .autocommit import commit_after_write
from .entry_store import (
    SLUG_PATTERN,
    StoreError,
    StoreParseError,
    StoreReadError,
    StoreShapeError,
    delete_entry,
    read_json,
    require_str,
    validate_store_key,
)
# 入库结构校验是母版库域操作（存储域），不走蒸馏编排接缝（工单 04）：其唯一
# 生产消费方就是入库；蒸馏适配器不设 validate 能力，避免死方法
from .keil import KeilProjectError, validate_project_structure
from .platforms import (
    KNOWN_PLATFORMS,
    PLATFORM_CONFIG_FILE_SUFFIXES,
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from .treewalk import BUILD_ARTIFACT_DIRS, iter_project_files


class MasterError(ValueError):
    """母版提炼 / 管理失败，message 说明具体问题。"""


@dataclass(frozen=True)
class KeyFileInfo:
    """母版关键文件的浏览目录项（工单 master-library-ui/01）。

    浏览列表每条带出：路径（相对母版根，正斜杠）/ 中文标签 / 磁盘实况
    （存在与否 + 字节数，一次算好，前端不按条回查——对偶 topic 轮 health 先例）。
    白名单 = MASTER_KEY_FILES（单一出处，内容端点复用），清单外文件不可见。
    """

    path: str
    label: str
    size_bytes: int  # 文件缺失 = 0
    exists: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "label": self.label,
            "size_bytes": self.size_bytes,
            "exists": self.exists,
        }


# 母版关键文件白名单（平台 → (rel_path, label) 有序元组）：浏览清单与内容端点
# 共用的单一出处。母版是生成根（模板 main.c / 板级配置 / 工程配置文件），
# 只读预览、不开放任意路径（工单 master-library-ui/01，方案 A 七条）。
MASTER_KEY_FILES: dict[str, tuple[tuple[str, str], ...]] = {
    PLATFORM_STM32: (
        ("main.c", "模板 main.c"),
        ("pin_config.h", "板级引脚宏"),
        ("led_instances.h", "LED 多实例通道宏"),
        ("key_instances.h", "按键多实例通道宏"),
        ("user/Project.uvprojx", "Keil 工程配置"),
    ),
    PLATFORM_MSPM0: (
        ("main.c", "模板 main.c"),
        ("mspm0.syscfg", "SysConfig 配置"),
        (".cproject", "CCS 工程配置"),
    ),
}


@dataclass(frozen=True)
class StructureAnalysis:
    """入库时的结构分析结果。"""

    platform: str
    warnings: tuple[str, ...]  # 非致命问题（构建产物残留等）


@dataclass(frozen=True)
class MasterMeta:
    """母版元数据（母版库根下的 <platform>.json）。"""

    platform: str
    sources: tuple[str, ...]  # 提炼来源工程名
    warnings: tuple[str, ...]  # 入库时结构分析的警告

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "sources": list(self.sources),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MasterMeta":
        platform = _require_str(data, "platform")
        sources = _require_str_list(data, "sources")
        warnings = _require_str_list(data, "warnings")
        return cls(
            platform=platform, sources=tuple(sources), warnings=tuple(warnings)
        )


@dataclass(frozen=True)
class MasterHealth:
    """母版健康实况（工单 master-library-ui-2/01，一次算好随列表带出）。

    三项体检：关键文件缺失（白名单内文件磁盘不在）/ 工程配置文件是否存在
    （平台能否被 IDE 打开）/ 构建产物残留（顶层构建目录，与入库结构分析
    analyze_structure 同口径）。ok = 三项全部无恙；否则前端以 ⚠ 徽章提示并
    悬停展示明细。
    """

    ok: bool
    missing_key_files: tuple[str, ...]  # 白名单内缺失（相对路径，正斜杠）
    config_file_ok: bool  # 平台工程配置文件在否（后缀表单源
    # platforms.PLATFORM_CONFIG_FILE_SUFFIXES，任意层级命中即可——平台能否被
    # IDE 打开，与入库结构分析 analyze_structure 同口径）
    artifact_dirs: tuple[str, ...]  # 顶层构建产物目录名（Debug / Release / …）

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "missing_key_files": list(self.missing_key_files),
            "config_file_ok": self.config_file_ok,
            "artifact_dirs": list(self.artifact_dirs),
        }


@dataclass(frozen=True)
class BigFileInfo:
    """大文件统计条目：体积统计的 Top N 清单项。"""

    path: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size_bytes": self.size_bytes}


@dataclass(frozen=True)
class MasterStats:
    """母版体积统计实况（工单 master-library-ui-2/01，一次算好随列表带出）。

    口径 = 统一噪音跳过后的全部文件（iter_project_files：构建产物目录与
    .git 不计入——与浏览/校验同口径，发现母版膨胀源头时不疑心构建残留）。
    big_files = 严格大于 BIG_FILE_THRESHOLD_BYTES 的文件按大小降序取
    BIG_FILE_TOP_N 条（大小相同按路径排序，确定性）。
    """

    total_size_bytes: int
    file_count: int
    big_files: tuple[BigFileInfo, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_size_bytes": self.total_size_bytes,
            "file_count": self.file_count,
            "big_files": [bf.to_dict() for bf in self.big_files],
        }


# 大文件阈值与清单上限（体量统计）：>256KB 且按大小降序 Top 10
BIG_FILE_THRESHOLD_BYTES = 256 * 1024
BIG_FILE_TOP_N = 10

# 树文件全文预览上限（工单 master-library-ui-2/02）：超过即按 400 中文拒绝，
# 不读全文——母版是生成根，树是浏览面，任何单文件都不应大到需要读全文
TREE_FILE_MAX_PREVIEW_BYTES = 1024 * 1024


@dataclass(frozen=True)
class TreeFileInfo:
    """母版全部文件的树清单项（工单 master-library-ui-2/02）。

    path = 相对母版根（正斜杠）；size_bytes = 磁盘实况一次算好。
    清单口径 = master_stats 同一次噪音跳过遍历（iter_project_files），
    树与统计互不矛盾。
    """

    path: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size_bytes": self.size_bytes}


# ---------------------------------------------------------------------------
# 母版库：入库（结构分析 + 可更换）、浏览、删除
# ---------------------------------------------------------------------------


def master_key_files(masters_dir: Path, platform: str) -> tuple[KeyFileInfo, ...]:
    """平台母版的关键文件目录（浏览列表用）：按白名单 MASTER_KEY_FILES 逐条
    报磁盘实况（存在 / 字节数），清单外文件不可见——白名单墙，无任意路径面。

    平台不在库（目录不存在）→ MasterError 与 get_master 同文案；未知平台
    （目录在但不在词表）→ 大声失败（与 analyze_structure 同口径）。
    """
    master_dir = _disk_master_dir(masters_dir, platform)  # 存在性 + 平台合法性
    catalog = _master_key_catalog(platform)
    infos: list[KeyFileInfo] = []
    for rel_path, label in catalog:
        path = master_dir / rel_path
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        infos.append(KeyFileInfo(path=rel_path, label=label, size_bytes=size, exists=exists))
    return tuple(infos)


def _disk_master_dir(masters_dir: Path, platform: str) -> Path:
    """母版磁盘目录校验（浏览域唯一出处）：平台名文法 → 目录存在（缺失 =
    「不存在」）→ 未知平台大声失败；返回校验后的目录路径。

    关键文件 / 健康 / 体积统计共用的存在性判定——「母版 {platform!r} 不存在」
    文案曾三处各写一份，一处改易漂移（评审修正）。
    """
    master_dir = master_project_dir(masters_dir, platform)
    if not master_dir.is_dir():
        raise MasterError(f"母版 {platform!r} 不存在")
    _validate_known_platform(platform)
    return master_dir


def _master_key_catalog(platform: str) -> tuple[tuple[str, str], ...]:
    """白名单查询（浏览域唯一出处）：已知平台没配白名单 = 开发错误
    （platforms.py 与白名单不同模块，漏配是真实风险）：大声失败，绝不静默
    回空清单误导浏览。
    """
    catalog = MASTER_KEY_FILES.get(platform)
    if catalog is None:
        raise MasterError(f"平台 {platform!r} 的关键文件白名单未配置")
    return catalog


def _top_level_artifact_dirs(master_dir: Path) -> tuple[str, ...]:
    """顶层构建产物目录名（入库分析 / 体检共用口径，BUILD_ARTIFACT_DIRS 单源）。"""
    return tuple(
        sorted(name for name in BUILD_ARTIFACT_DIRS if (master_dir / name).is_dir())
    )


def read_master_file(
    masters_dir: Path, platform: str, rel_path: str
) -> dict[str, Any]:
    """关键文件内容（详情预览用，工单 master-library-ui/02）：白名单墙。

    只允许 MASTER_KEY_FILES 内的 rel_path——无任意路径读取面（白名单判定
    在路径拼接之前，../ 等穿越进不了白名单即拒绝）；平台不在库 / 白名单外 /
    文件缺失各报中文 MasterError。读取 = utf-8 errors=\"replace\"（仓库读文本
    惯例，防 GBK 注释乱码，与 skeleton.read_module_sources 同读法），返回
    {path, label, size_bytes, content}。
    """
    infos = master_key_files(masters_dir, platform)  # 平台存在性 + 白名单判定
    found = next((info for info in infos if info.path == rel_path), None)
    if found is None:
        # 文件真实存在但不在白名单 = 不可预览（评审修正：与「关键文件缺失」
        # 区分——后者是白名单内文件真没了，前者只是不在预览清单）
        raise MasterError(f"非关键文件，不可预览：{rel_path}")
    if not found.exists:
        raise MasterError(f"关键文件缺失：{found.path}")
    content = (master_project_dir(masters_dir, platform) / found.path).read_text(
        encoding="utf-8", errors="replace"
    )
    # size_bytes = 磁盘字节数（Windows 文本写入含 \\r\\n，stat 实况）；
    # content = 通用换行归一化（\\r\\n → \\n）后的全文，两者不相等属正常
    return {
        "path": found.path,
        "label": found.label,
        "size_bytes": found.size_bytes,
        "content": content,
    }


def master_health(masters_dir: Path, platform: str) -> MasterHealth:
    """母版健康实况（工单 master-library-ui-2/01）：关键文件缺失 / 工程配置
    文件 / 构建产物残留三项一次算好，随列表带出不按条回查。

    平台不存在 / 未知平台 / 非法平台名与 master_key_files 同文案同路径
    （本函数委托其做存在性与白名单判定——关键文件缺失清单即其口径）。
    构建产物残留检测与入库结构分析 analyze_structure 同口径（顶层目录名，
    BUILD_ARTIFACT_DIRS 单源）。
    """
    master_dir = _disk_master_dir(masters_dir, platform)
    catalog = _master_key_catalog(platform)
    missing = tuple(
        rel_path
        for rel_path, _ in catalog
        if not (master_dir / rel_path).is_file()
    )
    config_file_ok = any(
        _find_config_files(master_dir, f"*{suffix}")
        for suffix in PLATFORM_CONFIG_FILE_SUFFIXES[platform]
    )
    artifact_dirs = _top_level_artifact_dirs(master_dir)
    return MasterHealth(
        ok=not missing and config_file_ok and not artifact_dirs,
        missing_key_files=missing,
        config_file_ok=config_file_ok,
        artifact_dirs=artifact_dirs,
    )


def master_stats(masters_dir: Path, platform: str) -> MasterStats:
    """母版体积统计（工单 master-library-ui-2/01）：统一噪音跳过后的全部文件
    总字节 / 文件数 / 大文件 Top 10（>256KB，降序）。

    平台不存在 / 未知平台与 master_health 同文案。遍历走 treewalk 统一噪音
    跳过（构建产物目录不计入），与浏览 / 校验口径一致。
    """
    master_dir = _disk_master_dir(masters_dir, platform)
    entries = [
        (path, path.stat().st_size) for path in iter_project_files(master_dir)
    ]
    total = sum(size for _, size in entries)
    big = sorted(
        (
            BigFileInfo(path=path.relative_to(master_dir).as_posix(), size_bytes=size)
            for path, size in entries
            if size > BIG_FILE_THRESHOLD_BYTES
        ),
        key=lambda bf: (-bf.size_bytes, bf.path),
    )[:BIG_FILE_TOP_N]
    return MasterStats(
        total_size_bytes=total,
        file_count=len(entries),
        big_files=tuple(big),
    )


def master_project_dir(masters_dir: Path, platform: str) -> Path:
    """母版在库里的目录位置：<masters_dir>/<platform>（库布局的唯一出处）。

    import_master / get_master / delete_master 与生成流程共用这一条布局规则；
    平台名先过合法性校验——借平台名拼路径逃出母版库在入口处就被拦住。
    """
    _validate_store_key(platform)
    return masters_dir / platform


def master_tree_files(masters_dir: Path, platform: str) -> tuple[TreeFileInfo, ...]:
    """母版全部文件的树清单（工单 master-library-ui-2/02）：平台目录下统一
    噪音跳过后的全部文件（构建产物目录 / .git 不计入），每条 {path, size_bytes}
    一次算好（path 为相对母版根的正斜杠）。

    平台不存在 / 未知平台与 master_health 同文案。排序确定性 = treewalk
    iter_project_files 的全路径排序（sorted rglob）。
    """
    master_dir = _disk_master_dir(masters_dir, platform)
    return tuple(
        TreeFileInfo(
            path=path.relative_to(master_dir).as_posix(),
            size_bytes=path.stat().st_size,
        )
        for path in iter_project_files(master_dir)
    )


def read_master_tree_file(
    masters_dir: Path, platform: str, rel_path: str
) -> dict[str, Any]:
    """树内文件全文（工单 master-library-ui-2/02，详情树点选预览用）。

    平台目录内任意文本文件读面，三重约束收窄（与参考文件库 read_fulltext
    同安全立场，判定在盘访问之前）：路径安全（与 entry_store.is_unsafe_path
    同拒绝面——首字符 `/`、`:`（NTFS ADS）、`\\`、任意层级 `..` 与空段
    `a//b`，另有 resolve 后必须在平台目录内的兜底判定）、二进制拒绝
    （NUL 字节）、超 TREE_FILE_MAX_PREVIEW_BYTES 拒绝——三类均 400 中文
    MasterError；文件缺失单独报错。读取沿用仓库惯例 utf-8 errors="replace"
    + 换行归一化（与 read_master_file 同读法）。返回 {path, size_bytes,
    content}（树文件无 label——与关键文件白名单端点 read_master_file 区分）。
    """
    master_dir = _disk_master_dir(masters_dir, platform)
    parts = rel_path.split("/")
    if (
        rel_path.startswith("/")
        or ":" in rel_path
        or "\\" in rel_path
        or any(seg in ("", "..") for seg in parts)
    ):
        raise MasterError(f"非法路径：{rel_path}")
    candidate = (master_dir / rel_path).resolve()
    try:
        candidate.relative_to(master_dir.resolve())  # 父解析必须是平台目录内
    except ValueError:
        raise MasterError(f"非法路径：{rel_path}") from None
    if not candidate.is_file():
        raise MasterError(f"文件不存在：{rel_path}")
    size = candidate.stat().st_size
    if size > TREE_FILE_MAX_PREVIEW_BYTES:
        limit_mb = TREE_FILE_MAX_PREVIEW_BYTES // (1024 * 1024)
        raise MasterError(f"文件超过预览上限（{limit_mb}MB）：{rel_path}")
    data = candidate.read_bytes()
    if b"\x00" in data:
        raise MasterError(f"二进制文件不可预览：{rel_path}")
    # 换行归一化与 read_master_file 同惯例（read_text 通用换行：
    # \r\n / \r → \n），读取与预览两侧行为一致
    content = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return {
        "path": rel_path,
        "size_bytes": size,
        "content": content,
    }


def analyze_structure(master_dir: Path, platform: str) -> StructureAnalysis:
    """入库前的结构分析：平台配置文件缺失 / 编译链结构残缺硬失败，其余进警告。

    平台配置文件缺失说明母版无法被 IDE 打开，拒绝入库；Keil 母版还校验
    .uvprojx 的编译链完整性（配置节点齐全 + 工程树引用覆盖全部保留源码，
    见 _validate_keil_structure）——AI 整合出的 .uvprojx"XML 合法但结构残缺"
    曾照样入库，生成时才被 KeilPatcher 拒绝（判例 09）。构建产物目录等
    非母版内容只给警告（生成器复制时会忽略 .git，构建目录会原样带进新工程，
    建议清理）。
    """
    _validate_known_platform(platform)
    if not master_dir.is_dir():
        raise MasterError(f"母版目录不存在：{master_dir}")
    for suffix in PLATFORM_CONFIG_FILE_SUFFIXES[platform]:
        if not _find_config_files(master_dir, f"*{suffix}"):
            raise MasterError(
                f"母版缺少平台 {platform} 的工程配置文件（{suffix}），拒绝入库"
            )
    if platform == PLATFORM_STM32:
        _validate_keil_structure(master_dir)
    warnings = [
        f"母版含 {name}/ 构建产物目录，建议清理"
        for name in _top_level_artifact_dirs(master_dir)
    ]
    return StructureAnalysis(platform=platform, warnings=tuple(warnings))


def _validate_keil_structure(master_dir: Path) -> None:
    """Keil 母版入库前的编译链结构校验（格式知识归 keil.py）。

    判例 09（用户实测）：AI 把两工程各自的 .uvprojx 判了 merge，整合产物
    XML 合法但组被清空（丢了启动文件 / system_stm32f10x.c 的引用）、连
    Cads/IncludePath 节点都没了——旧校验只查配置文件存在，坏母版照样入库、
    到生成时 KeilPatcher 才拒绝。校验失败在入库前大声拒绝（中文说明缺什么），
    兑现"绝不产出残缺工程"不变量。工程内保留源码清单按扫描同一套忽略规则
    计算（.git / 构建输出目录不进清单）。
    """
    expected: list[str] = []
    for path in iter_project_files(master_dir):
        if path.suffix.lower() in (".c", ".s"):
            expected.append(path.relative_to(master_dir).as_posix())
    try:
        validate_project_structure(master_dir, expected)
    except KeilProjectError as exc:
        raise MasterError(f"母版 .uvprojx 结构不完整，拒绝入库：{exc}") from exc


def import_master(
    masters_dir: Path,
    platform: str,
    source_dir: Path,
    sources: Sequence[str] = (),
) -> MasterMeta:
    """母版入库：结构分析 → 复制到临时目录 → 整体替换同平台旧母版。

    每平台一个母版：目标已存在时整体更换。先分析后动盘，分析失败不落任何
    文件；旧母版先挪到备份目录再换入新母版，中途失败把备份换回来——既有
    母版在任意失败点都完好。旧母版被占用（Keil µVision / 文件资源管理器
    开着）时改名失败：绝不碰旧母版（rmtree 会把只锁住部分的旧母版删残，
    真实事故），抛中文占用说明。
    """
    _validate_store_key(platform)
    analysis = analyze_structure(source_dir, platform)
    masters_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = masters_dir / f".{platform}.importing"
    backup_dir = masters_dir / f".{platform}.backup"
    shutil.rmtree(temp_dir, ignore_errors=True)  # 清掉上次失败残留
    shutil.copytree(source_dir, temp_dir)
    target_dir = masters_dir / platform
    if target_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
        if backup_dir.exists():
            # 备份目录清理不掉（被占用）：改名只会撞上非空目录，Windows 报
            # WinError 5，这里用中文讲清原因而不是裸抛拒绝访问
            raise MasterError(
                f"旧备份 {backup_dir.name} 目录清理失败（可能被占用），"
                "请先关闭占用程序后重试导入"
            )
    moved_to_backup = False
    try:
        if target_dir.exists():
            os.replace(target_dir, backup_dir)  # 旧母版先挪开
            moved_to_backup = True
        os.replace(temp_dir, target_dir)  # 新母版原子换入
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if moved_to_backup:
            # 旧母版已在备份目录：清掉半换入的新母版，把旧母版换回来
            shutil.rmtree(target_dir, ignore_errors=True)
            if backup_dir.exists():
                os.replace(backup_dir, target_dir)  # 回滚旧母版
            raise
        if target_dir.exists():
            # 旧母版从未挪动（改名失败）：绝不能碰它——rmtree 会把只锁住
            # 部分文件的旧母版删残（判例：真实事故，母版只剩空壳）
            raise MasterError(
                f"母版替换失败：旧母版目录 {target_dir.name} 被占用，无法挪动。"
                "通常是 Keil µVision 或文件资源管理器还打开着该目录，"
                "请先关闭再重试导入（杀毒软件扫描期间偶发，稍后重试亦可）"
            ) from None
        raise
    shutil.rmtree(backup_dir, ignore_errors=True)

    meta = MasterMeta(
        platform=platform,
        sources=tuple(sources),
        warnings=analysis.warnings,
    )
    _write_meta(masters_dir, meta)
    commit_after_write(masters_dir, f"lib: import master {platform}")
    return meta


def import_master_direct(
    masters_dir: Path, platform: str, source_dir: Path
) -> MasterMeta:
    """免提炼快速入库（工单 master-library-ui-2/04）：单工程直接替换母版。

    复用 import_master 全编排（结构校验 → 临时目录 → 原子替换 → 备份回滚 →
    autocommit），仅 sources 语义不同 = [源目录名]（免提炼：没有合成来源，
    来源名即目录名——官方模板升级等单工程场景不必走扫描/AI 提炼/报告）。
    源目录不存在 → 中文说明（防到 import_master 里报成「母版目录不存在」
    误导）；平台名非法与 import_master 同入口校验——平台名校验前置：非法
    平台名优先于源目录检查报错（次序刻意，与 webapp 层校验兜底一致）。
    """
    _validate_store_key(platform)
    if not source_dir.is_dir():
        raise MasterError(f"源目录不存在：{source_dir}")
    return import_master(masters_dir, platform, source_dir, sources=(source_dir.name,))


def list_masters(masters_dir: Path) -> list[MasterMeta]:
    """返回母版库中全部母版（按平台排序）；元数据缺失或损坏抛 MasterError。"""
    if not masters_dir.is_dir():
        return []
    metas: list[MasterMeta] = []
    for entry in sorted(masters_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue  # 散文件与导入中的临时目录不影响浏览
        metas.append(get_master(masters_dir, entry.name))
    return metas


def get_master(masters_dir: Path, platform: str) -> MasterMeta:
    """读取单个母版元数据；不存在或损坏抛 MasterError。

    读盘 / 解析 / 形状校验走 entry_store 原语（read_json），错误类型与文案
    仍归本模块。
    """
    _validate_store_key(platform)
    meta_path = masters_dir / f"{platform}.json"
    try:
        data = read_json(masters_dir, f"{platform}.json")
    except StoreReadError as exc:
        if isinstance(exc.error, FileNotFoundError):
            raise MasterError(f"母版 {platform!r} 不存在") from None
        raise MasterError(f"母版 {platform!r} 的元数据无法读取：{exc.error}") from exc
    except StoreParseError as exc:
        raise MasterError(f"母版 {platform!r} 的元数据不是合法 JSON：{exc.error}") from exc
    except StoreShapeError:
        raise MasterError(f"{meta_path} 必须是 JSON 对象") from None
    try:
        return MasterMeta.from_dict(data)
    except MasterError as exc:
        raise MasterError(f"母版 {platform!r} 的元数据不合法：{exc}") from exc


def delete_master(masters_dir: Path, platform: str) -> None:
    """删除母版：工程目录与元数据文件一并移除（目录存在校验走 entry_store 原语）。"""
    _validate_store_key(platform)
    try:
        delete_entry(masters_dir, platform)
    except StoreError:
        raise MasterError(f"母版 {platform!r} 不存在") from None
    (masters_dir / f"{platform}.json").unlink(missing_ok=True)
    commit_after_write(masters_dir, f"lib: delete master {platform}")


# ---------------------------------------------------------------------------
# 校验与辅助
# ---------------------------------------------------------------------------


def _find_config_files(project_dir: Path, pattern: str) -> list[Path]:
    """递归查找工程配置文件：统一噪音跳过规则（treewalk.iter_project_files）。"""
    return list(iter_project_files(project_dir, pattern=pattern))


def _validate_store_key(platform: str) -> None:
    try:
        validate_store_key(platform, SLUG_PATTERN, "平台名")
    except StoreError:
        raise MasterError(
            f"非法平台名：{platform!r}（只能含字母数字下划线连字符，且以字母或数字开头）"
        ) from None


def _validate_known_platform(platform: str) -> None:
    if platform not in KNOWN_PLATFORMS:
        raise MasterError(f"未知平台 {platform!r}（已知：{'、'.join(KNOWN_PLATFORMS)}）")


def _write_meta(masters_dir: Path, meta: MasterMeta) -> None:
    """写元数据：先写临时文件再原子换入，写失败不会留下损坏的 json。"""
    target = masters_dir / f"{meta.platform}.json"
    temp = masters_dir / f".{meta.platform}.json.tmp"
    temp.write_text(
        json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, target)


def _require_str(data: dict[str, Any], key: str) -> str:
    try:
        return require_str(data, key)
    except StoreError:
        raise MasterError(f"缺少必填字段：{key}") from None


def _require_str_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise MasterError(f"{key} 必须是非空字符串列表")
    return value
